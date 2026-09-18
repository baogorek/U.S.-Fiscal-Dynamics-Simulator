"""Deterministic quarterly fiscal accounting and Treasury refinancing model."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

from debt_sim.debt_stock import DebtStock, IssuanceRates, IssuanceStrategy
from debt_sim.economy import advance_gdp, annualized_flow_gdp_share, federal_fiscal_year
from debt_sim.instruments import InstrumentType
from debt_sim.treasury import (
    TreasuryBuybackInstruction,
    TreasuryBuybackPlan,
    buyback_financing_strategy,
    execute_treasury_buyback,
)

REQUIRED_ASSUMPTION_COLUMNS = {
    "annual_real_gdp_growth_rate",
    "annual_inflation_rate",
    "annual_tips_reference_inflation_rate",
    "primary_deficit_billions",
    "other_financing_adjustment_billions",
    "short_issuance_rate",
    "intermediate_issuance_rate",
    "long_issuance_rate",
    "tips_real_issuance_rate",
    "new_frn_spread",
    "other_public_debt_interest_rate",
}


@dataclass(frozen=True, slots=True)
class SimulationResult:
    quarterly: pd.DataFrame
    ending_stock: DebtStock
    scenario_name: str
    data_vintage: str


def validate_assumptions(assumptions: pd.DataFrame) -> pd.DataFrame:
    """Validate and return a sorted copy of the quarterly assumption table."""

    missing = REQUIRED_ASSUMPTION_COLUMNS - set(assumptions.columns)
    if missing:
        raise ValueError(f"assumption table is missing columns: {sorted(missing)}")
    if not isinstance(assumptions.index, pd.PeriodIndex):
        raise ValueError("assumption table index must be a pandas PeriodIndex")
    if not all(period.freqstr.startswith("Q") for period in assumptions.index):
        raise ValueError("assumption table must use calendar quarters")
    if assumptions.index.has_duplicates:
        raise ValueError("assumption table cannot contain duplicate quarters")
    ordered = assumptions.sort_index().copy()
    expected = pd.period_range(ordered.index.min(), ordered.index.max(), freq="Q")
    if not ordered.index.equals(expected):
        raise ValueError("assumption table must contain a contiguous sequence of quarters")
    numeric = ordered[list(REQUIRED_ASSUMPTION_COLUMNS)].astype(float)
    if not np.isfinite(numeric.to_numpy()).all():
        raise ValueError("assumption table contains non-finite values")
    growth_columns = [
        "annual_real_gdp_growth_rate",
        "annual_inflation_rate",
        "annual_tips_reference_inflation_rate",
    ]
    if (numeric[growth_columns] <= -1.0).any().any():
        raise ValueError("growth and inflation rates must be greater than -100%")
    nominal_rate_columns = [
        "short_issuance_rate",
        "intermediate_issuance_rate",
        "long_issuance_rate",
        "other_public_debt_interest_rate",
    ]
    if (numeric[nominal_rate_columns] < 0).any().any():
        raise ValueError("nominal Treasury and other-public-debt rates cannot be negative")
    if (numeric[[*nominal_rate_columns, "tips_real_issuance_rate"]] > 1.0).any().any():
        raise ValueError("issuance rates above 100% are outside v0.1 bounds")
    if (numeric[["tips_real_issuance_rate", "new_frn_spread"]] <= -1.0).any().any():
        raise ValueError("TIPS real rates and FRN spreads must be greater than -100%")
    return ordered


def run_simulation(
    initial_stock: DebtStock,
    assumptions: pd.DataFrame,
    *,
    initial_nominal_gdp_billions_saar: float,
    initial_real_gdp_billions_chained_saar: float,
    issuance_strategy: IssuanceStrategy | None = None,
    issuance_strategy_path: Mapping[pd.Period, IssuanceStrategy] | None = None,
    treasury_buyback_plan: TreasuryBuybackPlan | None = None,
    scenario_name: str = "custom",
    data_vintage: str = "unspecified",
) -> SimulationResult:
    """Run the quarterly accounting model.

    The assumption table contains one row per simulated calendar quarter.
    Primary deficits and other financing are quarterly flows in billions;
    macro growth and all rates are effective annual rates expressed as decimals.
    """

    assumptions = validate_assumptions(assumptions)
    strategy = issuance_strategy or IssuanceStrategy()
    stock = initial_stock.copy()
    nominal_gdp = float(initial_nominal_gdp_billions_saar)
    real_gdp = float(initial_real_gdp_billions_chained_saar)
    if nominal_gdp <= 0 or real_gdp <= 0:
        raise ValueError("initial GDP levels must be positive")

    records: list[dict[str, float | int | str | pd.Timestamp]] = []
    cumulative_interest = 0.0

    for period, row in assumptions.iterrows():
        period_strategy = (
            strategy
            if issuance_strategy_path is None
            else issuance_strategy_path.get(period, strategy)
        )
        beginning_debt = stock.debt_held_by_public_billions
        nominal_gdp, real_gdp = advance_gdp(
            nominal_gdp,
            real_gdp,
            float(row["annual_real_gdp_growth_rate"]),
            float(row["annual_inflation_rate"]),
        )

        rates = IssuanceRates(
            short_rate=float(row["short_issuance_rate"]),
            intermediate_rate=float(row["intermediate_issuance_rate"]),
            long_rate=float(row["long_issuance_rate"]),
            tips_real_rate=float(row["tips_real_issuance_rate"]),
            new_frn_spread=float(row["new_frn_spread"]),
        )
        accrual = stock.accrue_quarter(
            float(row["annual_tips_reference_inflation_rate"]),
            rates.short_rate,
        )
        other_public_interest = (
            stock.other_public_debt_billions * float(row["other_public_debt_interest_rate"]) / 4.0
        )
        maturity = stock.mature_at_end_of(period)

        modeled_interest = (
            accrual.marketable_interest_excluding_tips_inflation_billions
            + accrual.tips_inflation_compensation_billions
            + maturity.tips_deflation_floor_cost_billions
            + other_public_interest
        )
        primary_deficit = float(row["primary_deficit_billions"])
        other_financing = float(row["other_financing_adjustment_billions"])
        total_deficit = primary_deficit + modeled_interest

        rollover = stock.issue_rollover(
            period,
            maturity.principal_by_type_billions,
            rates,
            period_strategy,
        )

        buyback_program = (
            None if treasury_buyback_plan is None else treasury_buyback_plan.get(period)
        )
        if isinstance(buyback_program, TreasuryBuybackInstruction):
            buyback_instructions: Sequence[TreasuryBuybackInstruction] = (buyback_program,)
        else:
            buyback_instructions = buyback_program or ()
        if not all(
            isinstance(instruction, TreasuryBuybackInstruction)
            for instruction in buyback_instructions
        ):
            raise TypeError("each Treasury buyback plan entry must contain buyback instructions")
        buyback_operation_count = len(buyback_instructions)
        buyback_cash_limit = 0.0
        buyback_face_limit = 0.0
        buyback_cash_spent = 0.0
        buyback_face_retired = 0.0
        buyback_adjustment = 0.0
        buyback_unfilled_cash_limit = 0.0
        buyback_unfilled_face_limit = 0.0
        buyback_price = 0.0
        buyback_financing_principal = 0.0
        buyback_financing_rate_weight = 0.0
        buyback_financing_instrument = "none"
        buyback_retired_by_type = {instrument_type: 0.0 for instrument_type in InstrumentType}
        for buyback_instruction in buyback_instructions:
            buyback = execute_treasury_buyback(
                stock,
                period,
                buyback_instruction,
                rates,
            )
            buyback_cash_limit += buyback.cash_limit_billions
            buyback_face_limit += buyback.maximum_face_value_billions
            buyback_cash_spent += buyback.cash_spent_billions
            buyback_face_retired += buyback.face_value_retired_billions
            buyback_adjustment += buyback.premium_or_discount_billions
            buyback_unfilled_cash_limit += buyback.unfilled_cash_limit_billions
            buyback_unfilled_face_limit += buyback.unfilled_face_value_limit_billions
            buyback_price = (
                buyback_cash_spent / buyback_face_retired if buyback_face_retired > 0 else 0.0
            )
            instruction_financing_instrument = buyback_instruction.financing_instrument.value
            if buyback_financing_instrument == "none":
                buyback_financing_instrument = instruction_financing_instrument
            elif buyback_financing_instrument != instruction_financing_instrument:
                buyback_financing_instrument = "mixed"
            for instrument_type, amount in buyback.principal_retired_by_type_billions.items():
                buyback_retired_by_type[instrument_type] += amount
            if buyback.cash_spent_billions > 0:
                financing = stock.issue_new_borrowing(
                    period,
                    buyback.cash_spent_billions,
                    rates,
                    buyback_financing_strategy(period_strategy, buyback_instruction),
                )
                buyback_financing_principal += financing.principal_issued_billions
                buyback_financing_rate_weight += (
                    financing.principal_issued_billions * financing.weighted_stated_issuance_rate
                )

        # TIPS indexation and any maturity floor already increase the cohort
        # ledger directly. Only the remaining interest cost needs cash financing.
        cash_financing_need = (
            primary_deficit
            + accrual.marketable_interest_excluding_tips_inflation_billions
            + other_public_interest
            + other_financing
        )
        if cash_financing_need >= 0:
            new_financing = stock.issue_new_borrowing(
                period,
                cash_financing_need,
                rates,
                period_strategy,
            )
            debt_repayment = 0.0
        else:
            debt_repayment = stock.retire_debt(-cash_financing_need)
            new_financing = None

        new_issuance_principal = (
            0.0 if new_financing is None else new_financing.principal_issued_billions
        )
        new_issuance_weight = (
            rollover.principal_issued_billions * rollover.weighted_stated_issuance_rate
            + buyback_financing_rate_weight
            + (
                0.0
                if new_financing is None
                else new_financing.principal_issued_billions
                * new_financing.weighted_stated_issuance_rate
            )
        )
        gross_issuance = (
            rollover.principal_issued_billions
            + buyback_financing_principal
            + new_issuance_principal
        )
        average_new_rate = new_issuance_weight / gross_issuance if gross_issuance else 0.0

        ending_debt = stock.debt_held_by_public_billions
        expected_ending_debt = beginning_debt + total_deficit + other_financing + buyback_adjustment
        debt_identity_residual = ending_debt - expected_ending_debt
        cumulative_interest += modeled_interest
        composition = stock.composition_billions()
        marketable = stock.marketable_debt_billions
        weighted_average_maturity_quarters = stock.weighted_average_remaining_maturity_quarters(
            period
        )
        principal_maturing_next_four_quarters = stock.principal_maturing_within_quarters(
            period,
            4,
        )
        principal_maturing_next_eight_quarters = stock.principal_maturing_within_quarters(
            period,
            8,
        )
        avg_effective_ex_tips = stock.average_effective_rate_excluding_tips_inflation()
        avg_effective_including_tips = (
            4.0 * modeled_interest / beginning_debt if beginning_debt else 0.0
        )

        records.append(
            {
                "quarter": str(period),
                "quarter_end": period.end_time.normalize(),
                "calendar_year": period.year,
                "calendar_quarter": period.quarter,
                "fiscal_year": federal_fiscal_year(period),
                "nominal_gdp_billions_saar": nominal_gdp,
                "real_gdp_billions_chained_saar": real_gdp,
                "annual_real_gdp_growth_rate": float(row["annual_real_gdp_growth_rate"]),
                "annual_inflation_rate": float(row["annual_inflation_rate"]),
                "annual_tips_reference_inflation_rate": float(
                    row["annual_tips_reference_inflation_rate"]
                ),
                "primary_deficit_billions": primary_deficit,
                "marketable_interest_excluding_tips_inflation_billions": (
                    accrual.marketable_interest_excluding_tips_inflation_billions
                ),
                "bills_interest_cost_billions": accrual.financing_cost_by_type_billions[
                    InstrumentType.BILL
                ],
                "notes_interest_cost_billions": accrual.financing_cost_by_type_billions[
                    InstrumentType.NOTE
                ],
                "bonds_interest_cost_billions": accrual.financing_cost_by_type_billions[
                    InstrumentType.BOND
                ],
                "tips_real_interest_cost_billions": accrual.financing_cost_by_type_billions[
                    InstrumentType.TIPS
                ],
                "frns_interest_cost_billions": accrual.financing_cost_by_type_billions[
                    InstrumentType.FRN
                ],
                "other_public_debt_interest_billions": other_public_interest,
                "tips_inflation_compensation_billions": (
                    accrual.tips_inflation_compensation_billions
                ),
                "tips_deflation_floor_cost_billions": (maturity.tips_deflation_floor_cost_billions),
                "modeled_debt_interest_cost_billions": modeled_interest,
                "modeled_total_deficit_billions": total_deficit,
                "other_financing_adjustment_billions": other_financing,
                "treasury_debt_management_adjustment_billions": buyback_adjustment,
                "beginning_debt_held_by_public_billions": beginning_debt,
                "debt_held_by_public_billions": ending_debt,
                "debt_held_by_public_gdp_ratio": ending_debt / nominal_gdp,
                "primary_deficit_gdp_ratio_annualized": annualized_flow_gdp_share(
                    primary_deficit, nominal_gdp
                ),
                "modeled_interest_gdp_ratio_annualized": annualized_flow_gdp_share(
                    modeled_interest, nominal_gdp
                ),
                "modeled_total_deficit_gdp_ratio_annualized": annualized_flow_gdp_share(
                    total_deficit, nominal_gdp
                ),
                "marketable_debt_billions": marketable,
                "other_public_debt_billions": stock.other_public_debt_billions,
                "bills_outstanding_billions": composition[InstrumentType.BILL],
                "notes_outstanding_billions": composition[InstrumentType.NOTE],
                "bonds_outstanding_billions": composition[InstrumentType.BOND],
                "nominal_fixed_rate_debt_outstanding_billions": (
                    composition[InstrumentType.NOTE] + composition[InstrumentType.BOND]
                ),
                "tips_outstanding_billions": composition[InstrumentType.TIPS],
                "frns_outstanding_billions": composition[InstrumentType.FRN],
                "bill_share_of_marketable_debt": (
                    composition[InstrumentType.BILL] / marketable if marketable else 0.0
                ),
                "weighted_average_remaining_maturity_quarters": (
                    weighted_average_maturity_quarters
                ),
                "principal_maturing_next_four_quarters_billions": (
                    principal_maturing_next_four_quarters
                ),
                "principal_maturing_next_eight_quarters_billions": (
                    principal_maturing_next_eight_quarters
                ),
                "share_marketable_debt_maturing_next_four_quarters": (
                    principal_maturing_next_four_quarters / marketable if marketable else 0.0
                ),
                "share_marketable_debt_maturing_next_eight_quarters": (
                    principal_maturing_next_eight_quarters / marketable if marketable else 0.0
                ),
                "principal_maturing_billions": maturity.principal_maturing_billions,
                "principal_refinanced_billions": rollover.principal_issued_billions,
                "treasury_buyback_operation_count": buyback_operation_count,
                "treasury_buyback_cash_limit_billions": buyback_cash_limit,
                "treasury_buyback_face_value_limit_billions": buyback_face_limit,
                "treasury_buyback_cash_spent_billions": buyback_cash_spent,
                "treasury_buyback_face_value_retired_billions": buyback_face_retired,
                "treasury_buyback_premium_or_discount_billions": buyback_adjustment,
                "treasury_buyback_unfilled_cash_limit_billions": (buyback_unfilled_cash_limit),
                "treasury_buyback_unfilled_face_value_limit_billions": (
                    buyback_unfilled_face_limit
                ),
                "treasury_buyback_weighted_price_per_dollar_face": buyback_price,
                "treasury_buyback_notes_retired_billions": buyback_retired_by_type[
                    InstrumentType.NOTE
                ],
                "treasury_buyback_bonds_retired_billions": buyback_retired_by_type[
                    InstrumentType.BOND
                ],
                "treasury_buyback_financing_issuance_billions": (buyback_financing_principal),
                "treasury_buyback_financing_instrument": buyback_financing_instrument,
                "frn_principal_reset_billions": accrual.frn_principal_reset_billions,
                "principal_repriced_or_reset_billions": (
                    rollover.principal_issued_billions + accrual.frn_principal_reset_billions
                ),
                "net_new_borrowing_requirement_billions": cash_financing_need,
                "genuinely_new_borrowing_billions": max(cash_financing_need, 0.0),
                "debt_repayment_billions": debt_repayment,
                "gross_treasury_issuance_billions": gross_issuance,
                "new_borrowing_bill_share": period_strategy.new_borrowing_shares[
                    InstrumentType.BILL
                ],
                "new_borrowing_note_share": period_strategy.new_borrowing_shares[
                    InstrumentType.NOTE
                ],
                "new_borrowing_bond_share": period_strategy.new_borrowing_shares[
                    InstrumentType.BOND
                ],
                "new_borrowing_tips_share": period_strategy.new_borrowing_shares[
                    InstrumentType.TIPS
                ],
                "new_borrowing_frn_share": period_strategy.new_borrowing_shares[InstrumentType.FRN],
                "average_effective_marketable_rate_excluding_tips_inflation": (
                    avg_effective_ex_tips
                ),
                "average_effective_debt_cost_rate_including_tips_inflation": (
                    avg_effective_including_tips
                ),
                "average_new_issuance_stated_rate": average_new_rate,
                "share_marketable_debt_repriced_since_scenario_start": stock.repriced_share(),
                "cumulative_modeled_interest_billions": cumulative_interest,
                "debt_identity_residual_billions": debt_identity_residual,
            }
        )

    result = pd.DataFrame.from_records(records)
    return SimulationResult(result, stock, scenario_name, data_vintage)
