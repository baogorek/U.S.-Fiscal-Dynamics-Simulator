"""Lagged monetary, financial, inflation, output, and fiscal feedback.

The equations in this module are deliberately small and inspectable. They are
scenario mechanics, not estimated forecasts. Every semi-elasticity is exposed
so the initial experiments can show which conclusions depend on them.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from debt_sim.debt_stock import DebtStock, IssuanceStrategy
from debt_sim.policy import (
    FedBalanceSheetState,
    PathInput,
    PolicyRule,
    PolicySimulationResult,
    RegimePathInput,
    apply_policy_regime,
    run_policy_simulation,
)
from debt_sim.treasury import TreasuryBuybackPlan


@dataclass(frozen=True, slots=True)
class MacroFeedbackRule:
    """Configurable reduced-form quarterly macro-fiscal transmission."""

    output_gap_persistence: float = 0.80
    policy_tightening_output_semi_elasticity: float = 0.25
    private_spread_output_semi_elasticity: float = 0.15
    financial_stress_output_effect: float = 0.01
    policy_effect_lag_quarters: int = 2
    inflation_persistence: float = 0.98
    inflation_output_gap_sensitivity: float = 0.06
    inflation_gap_lag_quarters: int = 2
    automatic_stabilizer_semi_elasticity: float = 0.45
    minimum_output_gap: float = -0.20
    maximum_output_gap: float = 0.05
    minimum_inflation_rate: float = -0.05
    maximum_inflation_rate: float = 0.20
    convergence_tolerance: float = 1e-10

    def __post_init__(self) -> None:
        if not 0 <= self.output_gap_persistence < 1:
            raise ValueError("output-gap persistence must be at least zero and less than one")
        if not 0 <= self.inflation_persistence <= 1:
            raise ValueError("inflation persistence must be between zero and one")
        if (
            min(
                self.policy_tightening_output_semi_elasticity,
                self.private_spread_output_semi_elasticity,
                self.financial_stress_output_effect,
                self.inflation_output_gap_sensitivity,
                self.automatic_stabilizer_semi_elasticity,
            )
            < 0
        ):
            raise ValueError("macro-feedback semi-elasticities cannot be negative")
        if min(self.policy_effect_lag_quarters, self.inflation_gap_lag_quarters) < 1:
            raise ValueError("feedback lags must be at least one quarter")
        if not -1 < self.minimum_output_gap < self.maximum_output_gap:
            raise ValueError("output-gap bounds are invalid")
        if not -1 < self.minimum_inflation_rate < self.maximum_inflation_rate <= 1:
            raise ValueError("inflation bounds are invalid")
        if self.convergence_tolerance <= 0:
            raise ValueError("convergence tolerance must be positive")


@dataclass(frozen=True, slots=True)
class MacroFeedbackSolution:
    assumptions: pd.DataFrame
    output_gap: pd.Series
    policy_assumptions: pd.DataFrame
    iterations: int
    converged: bool
    maximum_change: float


@dataclass(frozen=True, slots=True)
class MacroPolicySimulationResult:
    quarterly: pd.DataFrame
    ending_stock: DebtStock
    ending_fed_balance_sheet: FedBalanceSheetState
    policy_assumptions: pd.DataFrame
    feedback_solution: MacroFeedbackSolution
    scenario_name: str
    data_vintage: str


def _numeric_path(index: pd.PeriodIndex, value: PathInput, name: str) -> pd.Series:
    if isinstance(value, pd.Series):
        result = value.reindex(index).astype(float)
        if result.isna().any():
            raise ValueError(f"{name} must specify every simulated quarter")
    else:
        result = pd.Series(float(value), index=index, dtype=float)
    if not np.isfinite(result.to_numpy()).all():
        raise ValueError(f"{name} contains non-finite values")
    return result


def _potential_nominal_gdp_path(
    reference_growth: np.ndarray,
    inflation: np.ndarray,
    initial_nominal_gdp_billions_saar: float,
) -> np.ndarray:
    if initial_nominal_gdp_billions_saar <= 0:
        raise ValueError("initial nominal GDP must be positive")
    result = np.empty(len(reference_growth), dtype=float)
    level = initial_nominal_gdp_billions_saar
    for position, real_growth in enumerate(reference_growth):
        nominal_factor = ((1.0 + real_growth) * (1.0 + inflation[position])) ** 0.25
        level *= nominal_factor
        result[position] = level
    return result


def _feedback_assumptions(
    reference: pd.DataFrame,
    output_gap: np.ndarray,
    inflation: np.ndarray,
    initial_nominal_gdp_billions_saar: float,
    rule: MacroFeedbackRule,
    private_spread: pd.Series,
    financial_stress: pd.Series,
    supply_inflation_pressure: pd.Series,
    initial_output_gap: float,
) -> pd.DataFrame:
    assumptions = reference.copy()
    reference_growth = reference["annual_real_gdp_growth_rate"].to_numpy(dtype=float)
    potential_nominal_gdp = _potential_nominal_gdp_path(
        reference_growth,
        inflation,
        initial_nominal_gdp_billions_saar,
    )
    actual_growth = np.empty(len(reference), dtype=float)
    prior_gap = initial_output_gap
    for position, current_gap in enumerate(output_gap):
        reference_quarterly_factor = (1.0 + reference_growth[position]) ** 0.25
        actual_quarterly_factor = (
            reference_quarterly_factor * (1.0 + current_gap) / (1.0 + prior_gap)
        )
        actual_growth[position] = actual_quarterly_factor**4 - 1.0
        prior_gap = current_gap

    stabilizers = (
        -rule.automatic_stabilizer_semi_elasticity * output_gap * potential_nominal_gdp / 4.0
    )
    assumptions["reference_annual_real_gdp_growth_rate"] = reference_growth
    assumptions["reference_annual_inflation_rate"] = reference["annual_inflation_rate"].to_numpy(
        dtype=float
    )
    assumptions["reference_primary_deficit_billions"] = reference[
        "primary_deficit_billions"
    ].to_numpy(dtype=float)
    assumptions["potential_nominal_gdp_billions_saar"] = potential_nominal_gdp
    assumptions["macro_feedback_output_gap"] = output_gap
    assumptions["automatic_stabilizer_primary_deficit_billions"] = stabilizers
    assumptions["private_credit_spread_basis_points"] = private_spread.to_numpy()
    assumptions["financial_stress_index"] = financial_stress.to_numpy()
    assumptions["supply_inflation_pressure_rate"] = supply_inflation_pressure.to_numpy()
    assumptions["annual_real_gdp_growth_rate"] = actual_growth
    assumptions["annual_inflation_rate"] = inflation
    assumptions["annual_tips_reference_inflation_rate"] = inflation
    assumptions["primary_deficit_billions"] = (
        assumptions["reference_primary_deficit_billions"] + stabilizers
    )
    return assumptions


def build_macro_feedback_path(
    reference_assumptions: pd.DataFrame,
    *,
    initial_nominal_gdp_billions_saar: float,
    policy_rule: PolicyRule,
    feedback_rule: MacroFeedbackRule | None = None,
    initial_inflation_rate: float | None = None,
    initial_output_gap: float = 0.0,
    fiscal_risk_premium_basis_points: PathInput = 0.0,
    liquidity_premium_basis_points: PathInput = 0.0,
    private_credit_spread_basis_points: PathInput = 0.0,
    financial_stress_index: PathInput = 0.0,
    supply_inflation_pressure_rate: PathInput = 0.0,
    policy_regimes: RegimePathInput = None,
) -> MacroFeedbackSolution:
    """Solve the causal policy--macro path by forward-propagating its lags."""

    from debt_sim.model import validate_assumptions

    reference = validate_assumptions(reference_assumptions)
    rule = feedback_rule or MacroFeedbackRule()
    index = reference.index
    private_spread = _numeric_path(
        index,
        private_credit_spread_basis_points,
        "private_credit_spread_basis_points",
    )
    financial_stress = _numeric_path(index, financial_stress_index, "financial_stress_index")
    supply_pressure = _numeric_path(
        index,
        supply_inflation_pressure_rate,
        "supply_inflation_pressure_rate",
    )
    if (private_spread < 0).any() or (financial_stress < 0).any():
        raise ValueError("private credit spreads and financial stress cannot be negative")
    if not rule.minimum_output_gap <= initial_output_gap <= rule.maximum_output_gap:
        raise ValueError("initial output gap is outside the configured bounds")

    initial_inflation = (
        float(reference.iloc[0]["annual_inflation_rate"])
        if initial_inflation_rate is None
        else float(initial_inflation_rate)
    )
    if not rule.minimum_inflation_rate <= initial_inflation <= rule.maximum_inflation_rate:
        raise ValueError("initial inflation is outside the configured bounds")

    count = len(reference)
    output_gap = np.full(count, initial_output_gap, dtype=float)
    inflation = np.full(count, initial_inflation, dtype=float)
    if initial_nominal_gdp_billions_saar <= 0:
        raise ValueError("initial nominal GDP must be positive")
    max_iterations = (
        count
        + max(
            rule.policy_effect_lag_quarters,
            rule.inflation_gap_lag_quarters,
        )
        + 5
    )
    converged = False
    maximum_change = float("inf")

    for _iteration in range(1, max_iterations + 1):
        assumptions = _feedback_assumptions(
            reference,
            output_gap,
            inflation,
            initial_nominal_gdp_billions_saar,
            rule,
            private_spread,
            financial_stress,
            supply_pressure,
            initial_output_gap,
        )
        policy = apply_policy_regime(
            assumptions,
            policy_rule,
            fiscal_risk_premium_basis_points=fiscal_risk_premium_basis_points,
            liquidity_premium_basis_points=liquidity_premium_basis_points,
            output_gap=pd.Series(output_gap, index=index),
            policy_regimes=policy_regimes,
        )
        # IORB is the operating-rate proxy when the Fed caps Treasury yields
        # but sterilizes the intervention. It falls with Treasury rates only
        # in the fiscal-dominance regime.
        monetary_tightening = policy["iorb_rate"].to_numpy(dtype=float) - reference[
            "short_issuance_rate"
        ].to_numpy(dtype=float)
        next_gap = np.empty(count, dtype=float)
        next_inflation = np.empty(count, dtype=float)
        next_gap[0] = initial_output_gap
        next_inflation[0] = initial_inflation
        private_spread_rate = private_spread.to_numpy(dtype=float) / 10_000.0
        stress_values = financial_stress.to_numpy(dtype=float)
        supply_values = supply_pressure.to_numpy(dtype=float)
        for position in range(1, count):
            policy_source = position - rule.policy_effect_lag_quarters
            if policy_source >= 0:
                demand_impulse = (
                    rule.policy_tightening_output_semi_elasticity
                    * monetary_tightening[policy_source]
                    + rule.private_spread_output_semi_elasticity
                    * private_spread_rate[policy_source]
                    + rule.financial_stress_output_effect * stress_values[policy_source]
                )
            else:
                demand_impulse = 0.0
            next_gap[position] = np.clip(
                rule.output_gap_persistence * next_gap[position - 1] - demand_impulse,
                rule.minimum_output_gap,
                rule.maximum_output_gap,
            )

            inflation_source = position - rule.inflation_gap_lag_quarters
            lagged_gap = next_gap[inflation_source] if inflation_source >= 0 else initial_output_gap
            next_inflation[position] = np.clip(
                policy_rule.inflation_target
                + rule.inflation_persistence
                * (next_inflation[position - 1] - policy_rule.inflation_target)
                + rule.inflation_output_gap_sensitivity * lagged_gap
                + supply_values[position],
                rule.minimum_inflation_rate,
                rule.maximum_inflation_rate,
            )

        maximum_change = float(
            max(
                np.max(np.abs(next_gap - output_gap)),
                np.max(np.abs(next_inflation - inflation)),
            )
        )
        output_gap = next_gap
        inflation = next_inflation
        if maximum_change <= rule.convergence_tolerance:
            converged = True
            break

    final_assumptions = _feedback_assumptions(
        reference,
        output_gap,
        inflation,
        initial_nominal_gdp_billions_saar,
        rule,
        private_spread,
        financial_stress,
        supply_pressure,
        initial_output_gap,
    )
    final_policy = apply_policy_regime(
        final_assumptions,
        policy_rule,
        fiscal_risk_premium_basis_points=fiscal_risk_premium_basis_points,
        liquidity_premium_basis_points=liquidity_premium_basis_points,
        output_gap=pd.Series(output_gap, index=index),
        policy_regimes=policy_regimes,
    )
    final_assumptions["monetary_tightening_rate_gap"] = final_policy["iorb_rate"].to_numpy(
        dtype=float
    ) - reference["short_issuance_rate"].to_numpy(dtype=float)
    return MacroFeedbackSolution(
        assumptions=final_assumptions,
        output_gap=pd.Series(output_gap, index=index, name="output_gap"),
        policy_assumptions=final_policy,
        iterations=_iteration,
        converged=converged,
        maximum_change=maximum_change,
    )


def run_macro_policy_simulation(
    initial_stock: DebtStock,
    reference_assumptions: pd.DataFrame,
    *,
    initial_nominal_gdp_billions_saar: float,
    initial_real_gdp_billions_chained_saar: float,
    policy_rule: PolicyRule,
    feedback_rule: MacroFeedbackRule | None = None,
    initial_inflation_rate: float | None = None,
    initial_output_gap: float = 0.0,
    initial_fed_balance_sheet: FedBalanceSheetState | None = None,
    issuance_strategy: IssuanceStrategy | None = None,
    treasury_buyback_plan: TreasuryBuybackPlan | None = None,
    fiscal_risk_premium_basis_points: PathInput = 0.0,
    liquidity_premium_basis_points: PathInput = 0.0,
    private_credit_spread_basis_points: PathInput = 0.0,
    financial_stress_index: PathInput = 0.0,
    supply_inflation_pressure_rate: PathInput = 0.0,
    policy_regimes: RegimePathInput = None,
    scenario_name: str = "macro_policy_feedback",
    data_vintage: str = "unspecified",
) -> MacroPolicySimulationResult:
    """Build a lagged macro path, then run policy and cohort accounting on it."""

    solution = build_macro_feedback_path(
        reference_assumptions,
        initial_nominal_gdp_billions_saar=initial_nominal_gdp_billions_saar,
        policy_rule=policy_rule,
        feedback_rule=feedback_rule,
        initial_inflation_rate=initial_inflation_rate,
        initial_output_gap=initial_output_gap,
        fiscal_risk_premium_basis_points=fiscal_risk_premium_basis_points,
        liquidity_premium_basis_points=liquidity_premium_basis_points,
        private_credit_spread_basis_points=private_credit_spread_basis_points,
        financial_stress_index=financial_stress_index,
        supply_inflation_pressure_rate=supply_inflation_pressure_rate,
        policy_regimes=policy_regimes,
    )
    policy_result: PolicySimulationResult = run_policy_simulation(
        initial_stock,
        solution.assumptions,
        initial_nominal_gdp_billions_saar=initial_nominal_gdp_billions_saar,
        initial_real_gdp_billions_chained_saar=initial_real_gdp_billions_chained_saar,
        policy_rule=policy_rule,
        initial_fed_balance_sheet=initial_fed_balance_sheet,
        issuance_strategy=issuance_strategy,
        treasury_buyback_plan=treasury_buyback_plan,
        fiscal_risk_premium_basis_points=fiscal_risk_premium_basis_points,
        liquidity_premium_basis_points=liquidity_premium_basis_points,
        output_gap=solution.output_gap,
        policy_regimes=policy_regimes,
        scenario_name=scenario_name,
        data_vintage=data_vintage,
    )
    quarterly = policy_result.quarterly.copy()
    diagnostic_columns = [
        column
        for column in solution.assumptions.columns
        if column.startswith(
            (
                "reference_",
                "macro_feedback_",
                "automatic_stabilizer_",
                "private_credit_",
                "financial_stress_",
                "supply_inflation_",
                "monetary_tightening_",
                "potential_nominal_",
            )
        )
    ]
    for column in diagnostic_columns:
        quarterly[column] = solution.assumptions[column].to_numpy()
    quarterly["macro_feedback_iterations"] = solution.iterations
    quarterly["macro_feedback_converged"] = solution.converged
    quarterly["macro_feedback_maximum_change"] = solution.maximum_change
    return MacroPolicySimulationResult(
        quarterly=quarterly,
        ending_stock=policy_result.ending_stock,
        ending_fed_balance_sheet=policy_result.ending_fed_balance_sheet,
        policy_assumptions=policy_result.policy_assumptions,
        feedback_solution=solution,
        scenario_name=scenario_name,
        data_vintage=data_vintage,
    )
