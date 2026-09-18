"""Transparent Federal Reserve and Treasury-market policy regimes.

This module is a behavioral layer around the security-level accounting engine.
It preserves the reference assumptions, records the yields that would prevail
without intervention, and then applies one of four explicit policy regimes.

The purchase calculation is deliberately reduced form. It reports purchases as
an equivalent share of gross Treasury issuance and should not be interpreted as
an estimated demand curve until its elasticity is empirically calibrated.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np
import pandas as pd

from debt_sim.debt_stock import DebtStock, IssuanceStrategy
from debt_sim.economy import annualized_flow_gdp_share
from debt_sim.model import SimulationResult, run_simulation, validate_assumptions
from debt_sim.treasury import TreasuryBuybackPlan


class PolicyRegime(StrEnum):
    """Federal Reserve treatment of inflation and Treasury-market stress."""

    PRICE_STABILITY = "price_stability"
    MARKET_FUNCTIONING = "market_functioning"
    STERILIZED_YIELD_CAP = "sterilized_yield_cap"
    FISCAL_DOMINANCE = "fiscal_dominance"


@dataclass(frozen=True, slots=True)
class PolicyRule:
    """Visible coefficients for the first policy-reaction layer.

    The reference Treasury-rate path is treated as the rate consistent with the
    reference macro path. ``inflation_response`` therefore applies to the gap
    between scenario inflation and the policy target. A coefficient of 1.5
    includes both nominal pass-through and a positive real-rate response.
    """

    regime: PolicyRegime = PolicyRegime.PRICE_STABILITY
    inflation_target: float = 0.02
    inflation_response: float = 1.5
    output_gap_response: float = 0.5
    reaction_smoothing: float = 0.5
    intermediate_policy_pass_through: float = 0.75
    long_policy_pass_through: float = 0.5
    tips_real_policy_pass_through: float = 0.5
    market_function_support_fraction: float = 0.75
    yield_cap_spread_basis_points: float = 0.0
    purchase_elasticity_basis_points_per_gross_issuance: float = 500.0
    maximum_issuance_rate: float = 0.99

    def __post_init__(self) -> None:
        if not isinstance(self.regime, PolicyRegime):
            object.__setattr__(self, "regime", PolicyRegime(self.regime))
        if not 0 <= self.inflation_target < 1:
            raise ValueError("inflation_target must be between zero and 100 percent")
        if (
            min(
                self.inflation_response,
                self.output_gap_response,
                self.intermediate_policy_pass_through,
                self.long_policy_pass_through,
                self.tips_real_policy_pass_through,
            )
            < 0
        ):
            raise ValueError("policy-response coefficients cannot be negative")
        if not 0 <= self.reaction_smoothing < 1:
            raise ValueError("reaction_smoothing must be at least zero and less than one")
        if not 0 <= self.market_function_support_fraction <= 1:
            raise ValueError("market_function_support_fraction must be between zero and one")
        if self.yield_cap_spread_basis_points < 0:
            raise ValueError("yield_cap_spread_basis_points cannot be negative")
        if self.purchase_elasticity_basis_points_per_gross_issuance <= 0:
            raise ValueError("purchase_elasticity_basis_points_per_gross_issuance must be positive")
        if not 0 < self.maximum_issuance_rate <= 1:
            raise ValueError("maximum_issuance_rate must be positive and no more than 100%")


@dataclass(frozen=True, slots=True)
class FedBalanceSheetState:
    """Aggregate Federal Reserve positions needed for consolidated accounting."""

    treasury_holdings_billions: float = 0.0
    reserve_balances_billions: float = 0.0
    average_treasury_yield: float = 0.0
    deferred_remittances_billions: float = 0.0

    def __post_init__(self) -> None:
        if (
            min(
                self.treasury_holdings_billions,
                self.reserve_balances_billions,
                self.deferred_remittances_billions,
            )
            < 0
        ):
            raise ValueError("Federal Reserve balance-sheet amounts cannot be negative")
        if not -1 < self.average_treasury_yield <= 1:
            raise ValueError("average_treasury_yield must be greater than -100% and at most 100%")

    def advance(
        self,
        *,
        requested_treasury_purchases_billions: float,
        purchase_yield: float,
        iorb_rate: float,
        marketable_debt_billions: float,
        treasury_rollover_billions: float = 0.0,
    ) -> FedBalanceSheetQuarter:
        """Accrue income and add end-of-quarter secondary-market purchases."""

        if min(requested_treasury_purchases_billions, treasury_rollover_billions) < 0:
            raise ValueError("requested Treasury purchases and rollovers cannot be negative")
        if treasury_rollover_billions > self.treasury_holdings_billions + 1e-12:
            raise ValueError("Federal Reserve rollover cannot exceed its Treasury holdings")
        if marketable_debt_billions < 0:
            raise ValueError("marketable debt cannot be negative")
        if not -1 < purchase_yield <= 1 or not 0 <= iorb_rate <= 1:
            raise ValueError("purchase yield and IORB rate are outside supported bounds")

        treasury_interest_income = (
            self.treasury_holdings_billions * self.average_treasury_yield / 4.0
        )
        reserve_interest_expense = self.reserve_balances_billions * iorb_rate / 4.0
        net_income = treasury_interest_income - reserve_interest_expense

        if net_income < 0:
            ending_deferred = self.deferred_remittances_billions - net_income
            remittance = 0.0
        else:
            deferred_reduction = min(self.deferred_remittances_billions, net_income)
            ending_deferred = self.deferred_remittances_billions - deferred_reduction
            remittance = net_income - deferred_reduction

        private_treasury_supply = max(
            marketable_debt_billions - self.treasury_holdings_billions,
            0.0,
        )
        actual_purchases = min(
            requested_treasury_purchases_billions,
            private_treasury_supply,
        )
        unfilled_purchases = requested_treasury_purchases_billions - actual_purchases
        ending_holdings = self.treasury_holdings_billions + actual_purchases
        ending_reserves = self.reserve_balances_billions + actual_purchases
        if ending_holdings > 0:
            ending_average_yield = (
                (self.treasury_holdings_billions - treasury_rollover_billions)
                * self.average_treasury_yield
                + (treasury_rollover_billions + actual_purchases) * purchase_yield
            ) / ending_holdings
        else:
            ending_average_yield = 0.0

        ending_state = FedBalanceSheetState(
            treasury_holdings_billions=ending_holdings,
            reserve_balances_billions=ending_reserves,
            average_treasury_yield=ending_average_yield,
            deferred_remittances_billions=ending_deferred,
        )
        return FedBalanceSheetQuarter(
            ending_state=ending_state,
            treasury_rollover_billions=treasury_rollover_billions,
            requested_treasury_purchases_billions=requested_treasury_purchases_billions,
            actual_treasury_purchases_billions=actual_purchases,
            unfilled_treasury_purchases_billions=unfilled_purchases,
            treasury_interest_income_billions=treasury_interest_income,
            reserve_interest_expense_billions=reserve_interest_expense,
            net_income_billions=net_income,
            remittance_to_treasury_billions=remittance,
        )


@dataclass(frozen=True, slots=True)
class FedBalanceSheetQuarter:
    ending_state: FedBalanceSheetState
    treasury_rollover_billions: float
    requested_treasury_purchases_billions: float
    actual_treasury_purchases_billions: float
    unfilled_treasury_purchases_billions: float
    treasury_interest_income_billions: float
    reserve_interest_expense_billions: float
    net_income_billions: float
    remittance_to_treasury_billions: float


@dataclass(frozen=True, slots=True)
class PolicySimulationResult:
    quarterly: pd.DataFrame
    ending_stock: DebtStock
    ending_fed_balance_sheet: FedBalanceSheetState
    policy_assumptions: pd.DataFrame
    scenario_name: str
    data_vintage: str


PathInput = float | pd.Series
RegimePathInput = pd.Series | None


def _numeric_path(index: pd.PeriodIndex, value: PathInput, name: str) -> pd.Series:
    if isinstance(value, pd.Series):
        path = value.reindex(index)
        if path.isna().any():
            raise ValueError(f"{name} must specify every simulated quarter")
        path = path.astype(float)
    else:
        path = pd.Series(float(value), index=index, dtype=float)
    if not np.isfinite(path.to_numpy()).all():
        raise ValueError(f"{name} contains non-finite values")
    return path


def _policy_regime_path(
    index: pd.PeriodIndex,
    rule: PolicyRule,
    regimes: RegimePathInput,
) -> pd.Series:
    if regimes is None:
        return pd.Series(rule.regime, index=index, dtype=object)
    path = regimes.reindex(index)
    if path.isna().any():
        raise ValueError("policy_regimes must specify every simulated quarter")
    try:
        return path.map(PolicyRegime)
    except ValueError as error:
        raise ValueError("policy_regimes contains an unknown policy regime") from error


def _bounded_nominal_rate(value: float, maximum: float) -> float:
    return min(max(value, 0.0), maximum)


def _bounded_real_rate(value: float, maximum: float) -> float:
    return min(max(value, -0.99), maximum)


def apply_policy_regime(
    reference_assumptions: pd.DataFrame,
    rule: PolicyRule,
    *,
    fiscal_risk_premium_basis_points: PathInput = 0.0,
    liquidity_premium_basis_points: PathInput = 0.0,
    output_gap: PathInput = 0.0,
    policy_regimes: RegimePathInput = None,
) -> pd.DataFrame:
    """Return assumptions with shadow yields and explicit policy intervention.

    ``fiscal_risk_premium_basis_points`` and ``liquidity_premium_basis_points``
    are separate so market-functioning support can remove the latter without
    silently erasing compensation demanded for fiscal or inflation risk.
    """

    assumptions = validate_assumptions(reference_assumptions)
    index = assumptions.index
    fiscal_path = _numeric_path(
        index,
        fiscal_risk_premium_basis_points,
        "fiscal_risk_premium_basis_points",
    )
    liquidity_path = _numeric_path(
        index,
        liquidity_premium_basis_points,
        "liquidity_premium_basis_points",
    )
    output_gap_path = _numeric_path(index, output_gap, "output_gap")
    regimes = _policy_regime_path(index, rule, policy_regimes)
    if (fiscal_path < 0).any() or (liquidity_path < 0).any():
        raise ValueError("fiscal and liquidity premiums cannot be negative")

    records: list[dict[str, float | str | bool]] = []
    previous_reaction = 0.0
    cap_spread = rule.yield_cap_spread_basis_points / 10_000.0

    for period, row in assumptions.iterrows():
        regime = PolicyRegime(regimes.loc[period])
        inflation_gap = float(row["annual_inflation_rate"]) - rule.inflation_target
        desired_reaction = (
            rule.inflation_response * inflation_gap
            + rule.output_gap_response * float(output_gap_path.loc[period])
        )
        policy_reaction = (
            rule.reaction_smoothing * previous_reaction
            + (1.0 - rule.reaction_smoothing) * desired_reaction
        )
        previous_reaction = policy_reaction
        fiscal_premium = float(fiscal_path.loc[period]) / 10_000.0
        liquidity_premium = float(liquidity_path.loc[period]) / 10_000.0

        reference_short = float(row["short_issuance_rate"])
        reference_intermediate = float(row["intermediate_issuance_rate"])
        reference_long = float(row["long_issuance_rate"])
        reference_tips = float(row["tips_real_issuance_rate"])
        raw_policy_rate = reference_short + policy_reaction
        policy_rate = _bounded_nominal_rate(raw_policy_rate, rule.maximum_issuance_rate)

        raw_shadow = {
            "short": raw_policy_rate + fiscal_premium + liquidity_premium,
            "intermediate": (
                reference_intermediate
                + rule.intermediate_policy_pass_through * policy_reaction
                + fiscal_premium
                + liquidity_premium
            ),
            "long": (
                reference_long
                + rule.long_policy_pass_through * policy_reaction
                + fiscal_premium
                + liquidity_premium
            ),
            "tips": (
                reference_tips
                + rule.tips_real_policy_pass_through * policy_reaction
                + fiscal_premium
                + liquidity_premium
            ),
        }
        shadow = {
            "short": _bounded_nominal_rate(raw_shadow["short"], rule.maximum_issuance_rate),
            "intermediate": _bounded_nominal_rate(
                raw_shadow["intermediate"], rule.maximum_issuance_rate
            ),
            "long": _bounded_nominal_rate(raw_shadow["long"], rule.maximum_issuance_rate),
            "tips": _bounded_real_rate(raw_shadow["tips"], rule.maximum_issuance_rate),
        }

        if regime is PolicyRegime.PRICE_STABILITY:
            actual = shadow.copy()
        elif regime is PolicyRegime.MARKET_FUNCTIONING:
            liquidity_relief = liquidity_premium * rule.market_function_support_fraction
            actual = {
                "short": _bounded_nominal_rate(
                    shadow["short"] - liquidity_relief,
                    rule.maximum_issuance_rate,
                ),
                "intermediate": _bounded_nominal_rate(
                    shadow["intermediate"] - liquidity_relief,
                    rule.maximum_issuance_rate,
                ),
                "long": _bounded_nominal_rate(
                    shadow["long"] - liquidity_relief,
                    rule.maximum_issuance_rate,
                ),
                "tips": _bounded_real_rate(
                    shadow["tips"] - liquidity_relief,
                    rule.maximum_issuance_rate,
                ),
            }
        else:
            actual = {
                "short": min(shadow["short"], reference_short + cap_spread),
                "intermediate": min(
                    shadow["intermediate"],
                    reference_intermediate + cap_spread,
                ),
                "long": min(shadow["long"], reference_long + cap_spread),
                "tips": min(shadow["tips"], reference_tips + cap_spread),
            }

        nominal_suppression = [
            max(shadow[tenor] - actual[tenor], 0.0) for tenor in ("short", "intermediate", "long")
        ]
        average_suppression_basis_points = (
            sum(nominal_suppression) / len(nominal_suppression) * 10_000.0
        )
        purchase_share = (
            average_suppression_basis_points
            / rule.purchase_elasticity_basis_points_per_gross_issuance
        )
        iorb_rate = actual["short"] if regime is PolicyRegime.FISCAL_DOMINANCE else policy_rate

        records.append(
            {
                "policy_regime": regime.value,
                "inflation_gap_to_target": inflation_gap,
                "output_gap": float(output_gap_path.loc[period]),
                "policy_reaction_rate_adjustment": policy_reaction,
                "policy_rate_proxy": policy_rate,
                "iorb_rate": iorb_rate,
                "fiscal_risk_premium_basis_points": float(fiscal_path.loc[period]),
                "liquidity_premium_basis_points": float(liquidity_path.loc[period]),
                "reference_short_issuance_rate": reference_short,
                "reference_intermediate_issuance_rate": reference_intermediate,
                "reference_long_issuance_rate": reference_long,
                "reference_tips_real_issuance_rate": reference_tips,
                "shadow_short_issuance_rate": shadow["short"],
                "shadow_intermediate_issuance_rate": shadow["intermediate"],
                "shadow_long_issuance_rate": shadow["long"],
                "shadow_tips_real_issuance_rate": shadow["tips"],
                "short_yield_suppression_basis_points": (shadow["short"] - actual["short"])
                * 10_000.0,
                "intermediate_yield_suppression_basis_points": (
                    shadow["intermediate"] - actual["intermediate"]
                )
                * 10_000.0,
                "long_yield_suppression_basis_points": (shadow["long"] - actual["long"]) * 10_000.0,
                "average_nominal_yield_suppression_basis_points": (
                    average_suppression_basis_points
                ),
                "required_fed_purchase_equivalent_gross_issuance_share": purchase_share,
                "rate_bound_binding": any(
                    not np.isclose(raw_shadow[key], shadow[key]) for key in raw_shadow
                )
                or not np.isclose(raw_policy_rate, policy_rate),
                "short_issuance_rate": actual["short"],
                "intermediate_issuance_rate": actual["intermediate"],
                "long_issuance_rate": actual["long"],
                "tips_real_issuance_rate": actual["tips"],
            }
        )

    policy_columns = pd.DataFrame(records, index=index)
    for column in policy_columns:
        assumptions[column] = policy_columns[column]
    return assumptions


def add_fed_balance_sheet_diagnostics(
    simulation: SimulationResult,
    policy_assumptions: pd.DataFrame,
    initial_fed_balance_sheet: FedBalanceSheetState,
) -> tuple[pd.DataFrame, FedBalanceSheetState]:
    """Attach Federal Reserve and consolidated financing flows to a simulation."""

    policy = policy_assumptions.copy()
    result_periods = pd.PeriodIndex(simulation.quarterly["quarter"], freq="Q")
    if not result_periods.equals(policy.index):
        raise ValueError("policy assumptions and simulation quarters must align")

    combined = simulation.quarterly.copy().reset_index(drop=True)
    diagnostic_columns = [
        column
        for column in policy.columns
        if column.startswith(("policy_", "iorb_", "reference_", "shadow_", "fiscal_", "liquidity_"))
        or "yield_suppression" in column
        or column
        in {
            "inflation_gap_to_target",
            "output_gap",
            "required_fed_purchase_equivalent_gross_issuance_share",
            "rate_bound_binding",
            "short_issuance_rate",
            "intermediate_issuance_rate",
            "long_issuance_rate",
            "tips_real_issuance_rate",
        }
    ]
    for column in diagnostic_columns:
        combined[column] = policy[column].to_numpy()

    state = initial_fed_balance_sheet
    fed_records: list[dict[str, float | bool]] = []
    cumulative_consolidated_interest = 0.0
    for row in combined.to_dict(orient="records"):
        required_share = float(row["required_fed_purchase_equivalent_gross_issuance_share"])
        gross_issuance = float(row["gross_treasury_issuance_billions"])
        required_total_market_absorption = required_share * gross_issuance
        marketable_debt = float(row["marketable_debt_billions"])
        beginning_fed_share = (
            min(state.treasury_holdings_billions / marketable_debt, 1.0)
            if marketable_debt > 0
            else 0.0
        )
        fed_rollover = min(
            float(row["principal_maturing_billions"]) * beginning_fed_share,
            state.treasury_holdings_billions,
        )
        requested_purchases = max(required_total_market_absorption - fed_rollover, 0.0)
        purchase_yield = (
            float(row["average_new_issuance_stated_rate"])
            if gross_issuance > 0
            else float(row["intermediate_issuance_rate"])
        )
        quarter = state.advance(
            requested_treasury_purchases_billions=requested_purchases,
            purchase_yield=purchase_yield,
            iorb_rate=float(row["iorb_rate"]),
            marketable_debt_billions=marketable_debt,
            treasury_rollover_billions=fed_rollover,
        )
        treasury_interest = float(row["modeled_debt_interest_cost_billions"])
        consolidated_interest = (
            treasury_interest
            - quarter.treasury_interest_income_billions
            + quarter.reserve_interest_expense_billions
        )
        cumulative_consolidated_interest += consolidated_interest
        purchase_coverage = (
            1.0
            if requested_purchases <= 1e-12
            else quarter.actual_treasury_purchases_billions / requested_purchases
        )
        state = quarter.ending_state
        fed_records.append(
            {
                "required_total_fed_market_absorption_billions": required_total_market_absorption,
                "fed_treasury_rollover_billions": fed_rollover,
                "required_fed_treasury_purchases_billions": requested_purchases,
                "fed_treasury_purchases_billions": quarter.actual_treasury_purchases_billions,
                "unfilled_fed_treasury_purchases_billions": (
                    quarter.unfilled_treasury_purchases_billions
                ),
                "fed_purchase_requirement_covered": purchase_coverage >= 1.0 - 1e-12,
                "fed_purchase_requirement_coverage_ratio": purchase_coverage,
                "fed_treasury_holdings_billions": state.treasury_holdings_billions,
                "fed_reserve_balances_billions": state.reserve_balances_billions,
                "fed_average_treasury_yield": state.average_treasury_yield,
                "fed_treasury_interest_income_billions": (
                    quarter.treasury_interest_income_billions
                ),
                "fed_reserve_interest_expense_billions": (
                    quarter.reserve_interest_expense_billions
                ),
                "fed_net_income_billions": quarter.net_income_billions,
                "fed_remittance_to_treasury_billions": (quarter.remittance_to_treasury_billions),
                "fed_deferred_remittances_billions": state.deferred_remittances_billions,
                "consolidated_public_financing_cost_billions": consolidated_interest,
                "consolidated_public_financing_cost_gdp_ratio_annualized": (
                    annualized_flow_gdp_share(
                        consolidated_interest,
                        float(row["nominal_gdp_billions_saar"]),
                    )
                ),
                "cumulative_consolidated_public_financing_cost_billions": (
                    cumulative_consolidated_interest
                ),
            }
        )

    fed_frame = pd.DataFrame(fed_records)
    for column in fed_frame:
        combined[column] = fed_frame[column]
    return combined, state


def run_policy_simulation(
    initial_stock: DebtStock,
    reference_assumptions: pd.DataFrame,
    *,
    initial_nominal_gdp_billions_saar: float,
    initial_real_gdp_billions_chained_saar: float,
    policy_rule: PolicyRule,
    initial_fed_balance_sheet: FedBalanceSheetState | None = None,
    issuance_strategy: IssuanceStrategy | None = None,
    issuance_strategy_path: dict[pd.Period, IssuanceStrategy] | None = None,
    treasury_buyback_plan: TreasuryBuybackPlan | None = None,
    fiscal_risk_premium_basis_points: PathInput = 0.0,
    liquidity_premium_basis_points: PathInput = 0.0,
    output_gap: PathInput = 0.0,
    policy_regimes: RegimePathInput = None,
    scenario_name: str = "policy_regime",
    data_vintage: str = "unspecified",
) -> PolicySimulationResult:
    """Run the cohort engine under an explicit policy regime and Fed balance sheet."""

    policy_assumptions = apply_policy_regime(
        reference_assumptions,
        policy_rule,
        fiscal_risk_premium_basis_points=fiscal_risk_premium_basis_points,
        liquidity_premium_basis_points=liquidity_premium_basis_points,
        output_gap=output_gap,
        policy_regimes=policy_regimes,
    )
    simulation = run_simulation(
        initial_stock,
        policy_assumptions,
        initial_nominal_gdp_billions_saar=initial_nominal_gdp_billions_saar,
        initial_real_gdp_billions_chained_saar=initial_real_gdp_billions_chained_saar,
        issuance_strategy=issuance_strategy,
        issuance_strategy_path=issuance_strategy_path,
        treasury_buyback_plan=treasury_buyback_plan,
        scenario_name=scenario_name,
        data_vintage=data_vintage,
    )
    quarterly, ending_fed_balance = add_fed_balance_sheet_diagnostics(
        simulation,
        policy_assumptions,
        initial_fed_balance_sheet or FedBalanceSheetState(),
    )
    return PolicySimulationResult(
        quarterly=quarterly,
        ending_stock=simulation.ending_stock,
        ending_fed_balance_sheet=ending_fed_balance,
        policy_assumptions=policy_assumptions,
        scenario_name=scenario_name,
        data_vintage=data_vintage,
    )
