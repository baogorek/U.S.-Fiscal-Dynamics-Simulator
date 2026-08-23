"""Deterministic quarterly fiscal accounting and Treasury refinancing model."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from debt_sim.debt_stock import DebtStock, IssuanceRates, IssuanceStrategy
from debt_sim.economy import advance_gdp, annualized_flow_gdp_share, federal_fiscal_year
from debt_sim.instruments import InstrumentType

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
            strategy,
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
            new_financing = stock.issue_new_borrowing(period, cash_financing_need, rates, strategy)
            debt_repayment = 0.0
        else:
            debt_repayment = stock.retire_debt(-cash_financing_need)
            new_financing = None

        new_issuance_principal = (
            0.0 if new_financing is None else new_financing.principal_issued_billions
        )
        new_issuance_weight = (
            rollover.principal_issued_billions * rollover.weighted_stated_issuance_rate
            + (
                0.0
                if new_financing is None
                else new_financing.principal_issued_billions
                * new_financing.weighted_stated_issuance_rate
            )
        )
        gross_issuance = rollover.principal_issued_billions + new_issuance_principal
        average_new_rate = new_issuance_weight / gross_issuance if gross_issuance else 0.0

        ending_debt = stock.debt_held_by_public_billions
        expected_ending_debt = beginning_debt + total_deficit + other_financing
        debt_identity_residual = ending_debt - expected_ending_debt
        cumulative_interest += modeled_interest
        composition = stock.composition_billions()
        marketable = stock.marketable_debt_billions
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
                "principal_maturing_billions": maturity.principal_maturing_billions,
                "principal_refinanced_billions": rollover.principal_issued_billions,
                "frn_principal_reset_billions": accrual.frn_principal_reset_billions,
                "principal_repriced_or_reset_billions": (
                    rollover.principal_issued_billions + accrual.frn_principal_reset_billions
                ),
                "net_new_borrowing_requirement_billions": cash_financing_need,
                "genuinely_new_borrowing_billions": max(cash_financing_need, 0.0),
                "debt_repayment_billions": debt_repayment,
                "gross_treasury_issuance_billions": gross_issuance,
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
