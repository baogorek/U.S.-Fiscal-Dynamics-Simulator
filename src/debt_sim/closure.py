"""Inverse closure solvers built around the quarterly cohort simulator.

The functions in this module repeatedly call :func:`run_simulation`; they do
not replace Treasury cohorts with a reduced-form debt equation. Results are
conditional mechanical requirements, not predictions of policy behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Literal

import numpy as np
import pandas as pd
from scipy.optimize import brentq

from debt_sim.debt_stock import DebtStock, IssuanceStrategy
from debt_sim.instruments import InstrumentType, annual_to_quarterly_rate, quarterly_to_annual_rate
from debt_sim.model import SimulationResult, run_simulation

ClosureTargetKind = Literal["stabilize_at_start", "specified_ratio", "immediate_flow"]
SolutionStatus = Literal["solved", "already_satisfied", "no_solution"]


@dataclass(frozen=True, slots=True)
class ClosureTarget:
    """A transparent condition applied to the end of a closure simulation."""

    kind: ClosureTargetKind = "stabilize_at_start"
    target_debt_gdp_ratio: float | None = None
    require_final_four_quarter_stability: bool = True
    max_final_four_quarter_increase: float = 0.001

    def __post_init__(self) -> None:
        if self.kind == "specified_ratio" and self.target_debt_gdp_ratio is None:
            raise ValueError("specified_ratio target requires target_debt_gdp_ratio")
        if self.target_debt_gdp_ratio is not None and self.target_debt_gdp_ratio < 0:
            raise ValueError("target debt/GDP cannot be negative")
        if self.max_final_four_quarter_increase < 0:
            raise ValueError("final-four-quarter tolerance cannot be negative")
        if self.kind in {"specified_ratio", "immediate_flow"} and (
            self.require_final_four_quarter_stability
        ):
            object.__setattr__(self, "require_final_four_quarter_stability", False)

    @classmethod
    def stabilize_at_start(
        cls, *, max_final_four_quarter_increase: float = 0.001
    ) -> ClosureTarget:
        return cls(
            kind="stabilize_at_start",
            max_final_four_quarter_increase=max_final_four_quarter_increase,
        )

    @classmethod
    def specified_ratio(cls, ratio: float) -> ClosureTarget:
        return cls(
            kind="specified_ratio",
            target_debt_gdp_ratio=ratio,
            require_final_four_quarter_stability=False,
        )

    @classmethod
    def immediate_flow(cls) -> ClosureTarget:
        return cls(kind="immediate_flow", require_final_four_quarter_stability=False)

    def resolved_ratio(self, starting_debt_gdp_ratio: float) -> float:
        if self.kind in {"stabilize_at_start", "immediate_flow"}:
            return starting_debt_gdp_ratio
        assert self.target_debt_gdp_ratio is not None
        return self.target_debt_gdp_ratio


@dataclass(frozen=True, slots=True)
class ClosureEvaluation:
    target_debt_gdp_ratio: float
    terminal_debt_gdp_ratio: float
    final_four_quarter_change: float | None
    endpoint_gap: float
    stability_gap: float | None
    binding_gap: float
    satisfies_target: bool


@dataclass(frozen=True, slots=True)
class ClosureSolution:
    mechanism: str
    status: SolutionStatus
    value: float | None
    unit: str
    bounds: tuple[float, float]
    target: ClosureTarget
    evaluation: ClosureEvaluation
    boundary_evaluation: ClosureEvaluation
    result: SimulationResult
    baseline_result: SimulationResult
    assumptions: pd.DataFrame
    iterations: int
    diagnostics: dict[str, float | int | str | bool | None] = field(default_factory=dict)

    @property
    def solved(self) -> bool:
        return self.status in {"solved", "already_satisfied"}


@dataclass(frozen=True, slots=True)
class InflationRateResponse:
    """Conditional pass-through from extra inflation to new nominal Treasury yields."""

    mode: Literal["none", "contemporaneous", "delayed"] = "none"
    beta_bills: float = 0.0
    beta_intermediate: float = 0.0
    beta_long: float = 0.0
    lag_quarters: int = 0

    def __post_init__(self) -> None:
        if self.mode not in {"none", "contemporaneous", "delayed"}:
            raise ValueError("unknown inflation rate-response mode")
        if min(self.beta_bills, self.beta_intermediate, self.beta_long) < 0:
            raise ValueError("inflation pass-through betas cannot be negative")
        if self.lag_quarters < 0:
            raise ValueError("rate-response lag cannot be negative")
        if self.mode == "none" and any(
            value != 0
            for value in (self.beta_bills, self.beta_intermediate, self.beta_long)
        ):
            raise ValueError("no-response mode requires zero pass-through betas")
        if self.mode == "contemporaneous" and self.lag_quarters != 0:
            raise ValueError("contemporaneous response requires a zero-quarter lag")

    @classmethod
    def no_response(cls) -> InflationRateResponse:
        return cls()

    @classmethod
    def uniform(
        cls, beta: float, *, lag_quarters: int = 0
    ) -> InflationRateResponse:
        return cls(
            mode="contemporaneous" if lag_quarters == 0 else "delayed",
            beta_bills=beta,
            beta_intermediate=beta,
            beta_long=beta,
            lag_quarters=lag_quarters,
        )

    @property
    def label(self) -> str:
        if self.mode == "none":
            return "Isolation experiment: no additional interest-rate response."
        timing = "contemporaneous" if self.lag_quarters == 0 else f"lagged {self.lag_quarters}q"
        return (
            f"{timing} pass-through; beta bills={self.beta_bills:g}, "
            f"intermediate={self.beta_intermediate:g}, long={self.beta_long:g}."
        )


@dataclass(frozen=True, slots=True)
class InflationEpisode:
    """Temporary additional price-level path and its conditional yield response."""

    duration_quarters: int = 20
    shape: Literal["one_year", "multi_year", "immediate_price_level"] = "multi_year"
    rate_response: InflationRateResponse = field(default_factory=InflationRateResponse.no_response)
    primary_deficit_scales_with_gdp: bool = False

    def __post_init__(self) -> None:
        if self.duration_quarters <= 0:
            raise ValueError("inflation duration must be positive")
        if self.shape == "one_year" and self.duration_quarters != 4:
            raise ValueError("one-year inflation burst must last four quarters")
        if self.shape == "immediate_price_level" and self.duration_quarters != 1:
            raise ValueError("immediate price-level approximation must last one quarter")


@dataclass(frozen=True, slots=True)
class ScalarTrial:
    result: SimulationResult
    assumptions: pd.DataFrame
    evaluation: ClosureEvaluation
    extra: dict[str, float | int | str | bool | None] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StressLadderResult:
    table: pd.DataFrame
    paths: dict[float, pd.DataFrame]


def _run(
    stock: DebtStock,
    assumptions: pd.DataFrame,
    *,
    initial_nominal_gdp_billions_saar: float,
    initial_real_gdp_billions_chained_saar: float,
    issuance_strategy: IssuanceStrategy,
    scenario_name: str,
    data_vintage: str,
) -> SimulationResult:
    return run_simulation(
        stock,
        assumptions,
        initial_nominal_gdp_billions_saar=initial_nominal_gdp_billions_saar,
        initial_real_gdp_billions_chained_saar=initial_real_gdp_billions_chained_saar,
        issuance_strategy=issuance_strategy,
        scenario_name=scenario_name,
        data_vintage=data_vintage,
    )


def evaluate_closure(
    result: SimulationResult,
    target: ClosureTarget,
    *,
    starting_debt_gdp_ratio: float,
    numerical_tolerance: float = 1e-8,
) -> ClosureEvaluation:
    ratios = result.quarterly["debt_held_by_public_gdp_ratio"]
    terminal = float(ratios.iloc[-1])
    target_ratio = target.resolved_ratio(starting_debt_gdp_ratio)
    endpoint_gap = terminal - target_ratio
    final_change: float | None = None
    stability_gap: float | None = None
    if target.require_final_four_quarter_stability:
        if len(ratios) < 5:
            raise ValueError("a final-four-quarter stability check requires at least five quarters")
        final_change = terminal - float(ratios.iloc[-5])
        stability_gap = final_change - target.max_final_four_quarter_increase
    binding_gap = max(endpoint_gap, stability_gap if stability_gap is not None else -np.inf)
    return ClosureEvaluation(
        target_debt_gdp_ratio=target_ratio,
        terminal_debt_gdp_ratio=terminal,
        final_four_quarter_change=final_change,
        endpoint_gap=endpoint_gap,
        stability_gap=stability_gap,
        binding_gap=binding_gap,
        satisfies_target=binding_gap <= numerical_tolerance,
    )


def project_nominal_gdp(
    assumptions: pd.DataFrame, initial_nominal_gdp_billions_saar: float
) -> pd.Series:
    nominal = float(initial_nominal_gdp_billions_saar)
    values = []
    for _, row in assumptions.iterrows():
        real_q = annual_to_quarterly_rate(float(row["annual_real_gdp_growth_rate"]))
        inflation_q = annual_to_quarterly_rate(float(row["annual_inflation_rate"]))
        nominal *= (1.0 + real_q) * (1.0 + inflation_q)
        values.append(nominal)
    return pd.Series(values, index=assumptions.index, dtype=float)


def apply_fiscal_adjustment(
    assumptions: pd.DataFrame,
    adjustment_gdp_share: float,
    *,
    initial_nominal_gdp_billions_saar: float,
    phase_in_quarters: int = 0,
) -> pd.DataFrame:
    """Improve the primary balance by a constant share of contemporaneous GDP."""

    if phase_in_quarters < 0:
        raise ValueError("phase-in quarters cannot be negative")
    adjusted = assumptions.copy()
    gdp = project_nominal_gdp(adjusted, initial_nominal_gdp_billions_saar)
    if phase_in_quarters in {0, 1}:
        scale = np.ones(len(adjusted))
    else:
        scale = np.minimum(np.arange(1, len(adjusted) + 1) / phase_in_quarters, 1.0)
    adjusted["primary_deficit_billions"] -= adjustment_gdp_share * gdp * scale / 4.0
    return adjusted


def _solve_bounded(
    *,
    mechanism: str,
    unit: str,
    bounds: tuple[float, float],
    target: ClosureTarget,
    baseline_result: SimulationResult,
    evaluate: callable,
    scan_points: int = 2,
    xtol: float = 1e-8,
) -> ClosureSolution:
    lower, upper = map(float, bounds)
    if lower >= upper:
        raise ValueError("solver lower bound must be below upper bound")
    cache: dict[float, ScalarTrial] = {}

    def trial(value: float) -> ScalarTrial:
        key = float(value)
        if key not in cache:
            cache[key] = evaluate(key)
        return cache[key]

    low = trial(lower)
    if low.evaluation.satisfies_target:
        boundary = trial(upper)
        return ClosureSolution(
            mechanism,
            "already_satisfied",
            lower,
            unit,
            (lower, upper),
            target,
            low.evaluation,
            boundary.evaluation,
            low.result,
            baseline_result,
            low.assumptions,
            0,
            low.extra,
        )

    grid = np.linspace(lower, upper, max(2, scan_points))
    trials = [trial(float(value)) for value in grid]
    bracket: tuple[float, float] | None = None
    first_tolerance_feasible: tuple[float, ScalarTrial] | None = None
    for index in range(1, len(grid)):
        if (
            first_tolerance_feasible is None
            and trials[index].evaluation.satisfies_target
        ):
            first_tolerance_feasible = (float(grid[index]), trials[index])
        if trials[index].evaluation.binding_gap <= 0.0:
            bracket = (float(grid[index - 1]), float(grid[index]))
            break
    boundary = trials[-1]
    if bracket is None:
        if first_tolerance_feasible is not None:
            value, feasible = first_tolerance_feasible
            return ClosureSolution(
                mechanism,
                "solved",
                value,
                unit,
                (lower, upper),
                target,
                feasible.evaluation,
                boundary.evaluation,
                feasible.result,
                baseline_result,
                feasible.assumptions,
                0,
                feasible.extra,
            )
        best_index = int(np.argmin([item.evaluation.binding_gap for item in trials]))
        best = trials[best_index]
        diagnostics = dict(best.extra)
        diagnostics.update(
            {
                "best_sampled_value": float(grid[best_index]),
                "best_sampled_terminal_debt_gdp_ratio": (
                    best.evaluation.terminal_debt_gdp_ratio
                ),
                "upper_boundary_terminal_debt_gdp_ratio": (
                    boundary.evaluation.terminal_debt_gdp_ratio
                ),
            }
        )
        return ClosureSolution(
            mechanism,
            "no_solution",
            None,
            unit,
            (lower, upper),
            target,
            best.evaluation,
            boundary.evaluation,
            best.result,
            baseline_result,
            best.assumptions,
            0,
            diagnostics,
        )

    def residual(value: float) -> float:
        return trial(value).evaluation.binding_gap

    root, root_result = brentq(
        residual,
        bracket[0],
        bracket[1],
        xtol=xtol,
        rtol=max(4 * np.finfo(float).eps, 1e-12),
        full_output=True,
    )
    solved = trial(float(root))
    return ClosureSolution(
        mechanism,
        "solved",
        float(root),
        unit,
        (lower, upper),
        target,
        solved.evaluation,
        boundary.evaluation,
        solved.result,
        baseline_result,
        solved.assumptions,
        int(root_result.iterations),
        solved.extra,
    )


def solve_fiscal_adjustment(
    initial_stock: DebtStock,
    assumptions: pd.DataFrame,
    *,
    initial_nominal_gdp_billions_saar: float,
    initial_real_gdp_billions_chained_saar: float,
    issuance_strategy: IssuanceStrategy,
    target: ClosureTarget | None = None,
    bounds: tuple[float, float] = (0.0, 0.20),
    phase_in_quarters: int = 0,
    data_vintage: str = "unspecified",
) -> ClosureSolution:
    """Solve for a permanent primary-balance improvement, in GDP-share units."""

    target = target or ClosureTarget.stabilize_at_start()
    start_ratio = initial_stock.debt_held_by_public_billions / initial_nominal_gdp_billions_saar
    baseline = _run(
        initial_stock,
        assumptions,
        initial_nominal_gdp_billions_saar=initial_nominal_gdp_billions_saar,
        initial_real_gdp_billions_chained_saar=initial_real_gdp_billions_chained_saar,
        issuance_strategy=issuance_strategy,
        scenario_name="closure_baseline",
        data_vintage=data_vintage,
    )

    def evaluate(adjustment: float) -> ScalarTrial:
        adjusted = apply_fiscal_adjustment(
            assumptions,
            adjustment,
            initial_nominal_gdp_billions_saar=initial_nominal_gdp_billions_saar,
            phase_in_quarters=phase_in_quarters,
        )
        result = _run(
            initial_stock,
            adjusted,
            initial_nominal_gdp_billions_saar=initial_nominal_gdp_billions_saar,
            initial_real_gdp_billions_chained_saar=initial_real_gdp_billions_chained_saar,
            issuance_strategy=issuance_strategy,
            scenario_name="fiscal_closure",
            data_vintage=data_vintage,
        )
        return ScalarTrial(
            result,
            adjusted,
            evaluate_closure(result, target, starting_debt_gdp_ratio=start_ratio),
            {
                "adjustment_percentage_points_of_gdp": adjustment * 100.0,
                "phase_in_quarters": phase_in_quarters,
                "starting_debt_gdp_ratio": start_ratio,
            },
        )

    # A very large primary surplus can extinguish all modeled debt before the
    # horizon, after which v0.1 intentionally refuses to create a negative debt
    # stock. Find the largest representable trial inside the user's unchanged
    # bound; the closure root, when it exists, lies below debt exhaustion.
    lower, requested_upper = bounds
    effective_upper = requested_upper
    try:
        evaluate(effective_upper)
    except ValueError as error:
        if "financing surplus exceeds all debt" not in str(error):
            raise
        valid = lower
        invalid = requested_upper
        for _ in range(60):
            midpoint = (valid + invalid) / 2.0
            try:
                evaluate(midpoint)
                valid = midpoint
            except ValueError as inner_error:
                if "financing surplus exceeds all debt" not in str(inner_error):
                    raise
                invalid = midpoint
        effective_upper = valid

    solution = _solve_bounded(
        mechanism="Required primary-balance adjustment",
        unit="share of GDP",
        bounds=(lower, effective_upper),
        target=target,
        baseline_result=baseline,
        evaluate=evaluate,
    )
    if effective_upper == requested_upper:
        return solution
    diagnostics = dict(solution.diagnostics)
    diagnostics["requested_upper_bound_share_of_gdp"] = requested_upper
    diagnostics["largest_bound_before_debt_extinction_share_of_gdp"] = effective_upper
    return replace(solution, bounds=bounds, diagnostics=diagnostics)


def _apply_inflation_episode(
    assumptions: pd.DataFrame,
    cumulative_extra_price_level_change: float,
    episode: InflationEpisode,
    *,
    initial_nominal_gdp_billions_saar: float,
    include_tips_indexation: bool = True,
    include_rate_response: bool = True,
) -> pd.DataFrame:
    if cumulative_extra_price_level_change < 0:
        raise ValueError("cumulative inflationary price-level change cannot be negative")
    if episode.duration_quarters > len(assumptions):
        raise ValueError("inflation episode is longer than the closure horizon")
    shocked = assumptions.copy()
    shock_periods = shocked.index[: episode.duration_quarters]
    extra_quarterly = (1.0 + cumulative_extra_price_level_change) ** (
        1.0 / episode.duration_quarters
    ) - 1.0
    for period in shock_periods:
        baseline_q = annual_to_quarterly_rate(
            float(assumptions.loc[period, "annual_inflation_rate"])
        )
        combined_q = (1.0 + baseline_q) * (1.0 + extra_quarterly) - 1.0
        shocked.loc[period, "annual_inflation_rate"] = quarterly_to_annual_rate(combined_q)

    if include_tips_indexation:
        tips_periods = (shock_periods + 1).intersection(shocked.index)
        for period in tips_periods:
            baseline_q = annual_to_quarterly_rate(
                float(assumptions.loc[period, "annual_tips_reference_inflation_rate"])
            )
            combined_q = (1.0 + baseline_q) * (1.0 + extra_quarterly) - 1.0
            shocked.loc[period, "annual_tips_reference_inflation_rate"] = (
                quarterly_to_annual_rate(combined_q)
            )

    response = episode.rate_response
    if include_rate_response and response.mode != "none":
        extra_annualized = quarterly_to_annual_rate(extra_quarterly)
        rate_start = response.lag_quarters
        rate_stop = min(rate_start + episode.duration_quarters, len(shocked))
        rate_periods = shocked.index[rate_start:rate_stop]
        for column, beta in {
            "short_issuance_rate": response.beta_bills,
            "intermediate_issuance_rate": response.beta_intermediate,
            "long_issuance_rate": response.beta_long,
        }.items():
            shocked.loc[rate_periods, column] += beta * extra_annualized

    if episode.primary_deficit_scales_with_gdp:
        baseline_gdp = project_nominal_gdp(assumptions, initial_nominal_gdp_billions_saar)
        shocked_gdp = project_nominal_gdp(shocked, initial_nominal_gdp_billions_saar)
        shocked["primary_deficit_billions"] = (
            assumptions["primary_deficit_billions"] * shocked_gdp / baseline_gdp
        )
    return shocked


def apply_inflation_episode(
    assumptions: pd.DataFrame,
    cumulative_extra_price_level_change: float,
    episode: InflationEpisode,
    *,
    initial_nominal_gdp_billions_saar: float,
) -> pd.DataFrame:
    """Apply an extra cumulative price-level change through all v0.1 channels."""

    return _apply_inflation_episode(
        assumptions,
        cumulative_extra_price_level_change,
        episode,
        initial_nominal_gdp_billions_saar=initial_nominal_gdp_billions_saar,
    )


def _episode_price_metrics(
    assumptions: pd.DataFrame, duration_quarters: int
) -> tuple[float, float]:
    episode_rows = assumptions.iloc[:duration_quarters]
    factor = float(
        np.prod((1.0 + episode_rows["annual_inflation_rate"].to_numpy(dtype=float)) ** 0.25)
    )
    return factor - 1.0, factor ** (4.0 / duration_quarters) - 1.0


def _inflation_diagnostics(
    *,
    initial_stock: DebtStock,
    baseline: SimulationResult,
    result: SimulationResult,
    assumptions: pd.DataFrame,
    cumulative_extra: float,
    episode: InflationEpisode,
    target: ClosureTarget,
    starting_ratio: float,
) -> dict[str, float | int | str | bool | None]:
    duration = episode.duration_quarters
    total_cumulative, total_annualized = _episode_price_metrics(assumptions, duration)
    baseline_episode = baseline.quarterly.iloc[:duration]
    scenario_episode = result.quarterly.iloc[:duration]
    ending = result.quarterly.iloc[-1]
    baseline_ending = baseline.quarterly.iloc[-1]
    extra_annualized = (1.0 + cumulative_extra) ** (4.0 / duration) - 1.0
    gross_refinanced = float(scenario_episode["principal_refinanced_billions"].sum())
    return {
        "starting_debt_gdp_ratio": starting_ratio,
        "target_debt_gdp_ratio": target.resolved_ratio(starting_ratio),
        "closure_horizon_quarters": len(result.quarterly),
        "required_additional_cumulative_price_level_increase": cumulative_extra,
        "total_episode_cumulative_price_level_increase": total_cumulative,
        "additional_annualized_inflation_during_episode": extra_annualized,
        "total_annualized_inflation_during_episode": total_annualized,
        "nominal_debt_beginning_billions": initial_stock.debt_held_by_public_billions,
        "nominal_debt_end_billions": float(ending["debt_held_by_public_billions"]),
        "nominal_gdp_beginning_billions_saar": (
            initial_stock.debt_held_by_public_billions / starting_ratio
        ),
        "nominal_gdp_end_billions_saar": float(ending["nominal_gdp_billions_saar"]),
        "gross_principal_refinanced_during_episode_billions": gross_refinanced,
        "gross_refinancing_share_of_starting_marketable_debt": (
            gross_refinanced / initial_stock.marketable_debt_billions
        ),
        "marketable_debt_repriced_share_at_episode_end": float(
            scenario_episode.iloc[-1]["share_marketable_debt_repriced_since_scenario_start"]
        ),
        "increase_in_tips_principal_compensation_billions": float(
            scenario_episode["tips_inflation_compensation_billions"].sum()
            - baseline_episode["tips_inflation_compensation_billions"].sum()
        ),
        "cumulative_interest_cost_relative_to_baseline_billions": float(
            ending["cumulative_modeled_interest_billions"]
            - baseline_ending["cumulative_modeled_interest_billions"]
        ),
        "terminal_debt_gdp_improvement_vs_baseline_percentage_points": 100.0
        * (
            float(baseline_ending["debt_held_by_public_gdp_ratio"])
            - float(ending["debt_held_by_public_gdp_ratio"])
        ),
        "rate_response_assumption": episode.rate_response.label,
        "primary_deficit_treatment": (
            "constant share of scenario GDP"
            if episode.primary_deficit_scales_with_gdp
            else "unchanged nominal baseline path"
        ),
        "inflation_shape": episode.shape,
        "inflation_duration_quarters": duration,
    }


def solve_inflation_closure(
    initial_stock: DebtStock,
    assumptions: pd.DataFrame,
    *,
    initial_nominal_gdp_billions_saar: float,
    initial_real_gdp_billions_chained_saar: float,
    issuance_strategy: IssuanceStrategy,
    episode: InflationEpisode,
    target: ClosureTarget | None = None,
    bounds: tuple[float, float] = (0.0, 10.0),
    data_vintage: str = "unspecified",
) -> ClosureSolution:
    """Solve for an additional cumulative price-level change over an episode."""

    target = target or ClosureTarget.stabilize_at_start()
    start_ratio = initial_stock.debt_held_by_public_billions / initial_nominal_gdp_billions_saar
    baseline = _run(
        initial_stock,
        assumptions,
        initial_nominal_gdp_billions_saar=initial_nominal_gdp_billions_saar,
        initial_real_gdp_billions_chained_saar=initial_real_gdp_billions_chained_saar,
        issuance_strategy=issuance_strategy,
        scenario_name="closure_baseline",
        data_vintage=data_vintage,
    )

    def evaluate(cumulative_extra: float) -> ScalarTrial:
        shocked = apply_inflation_episode(
            assumptions,
            cumulative_extra,
            episode,
            initial_nominal_gdp_billions_saar=initial_nominal_gdp_billions_saar,
        )
        result = _run(
            initial_stock,
            shocked,
            initial_nominal_gdp_billions_saar=initial_nominal_gdp_billions_saar,
            initial_real_gdp_billions_chained_saar=initial_real_gdp_billions_chained_saar,
            issuance_strategy=issuance_strategy,
            scenario_name="inflationary_closure",
            data_vintage=data_vintage,
        )
        diagnostics = _inflation_diagnostics(
            initial_stock=initial_stock,
            baseline=baseline,
            result=result,
            assumptions=shocked,
            cumulative_extra=cumulative_extra,
            episode=episode,
            target=target,
            starting_ratio=start_ratio,
        )
        return ScalarTrial(
            result,
            shocked,
            evaluate_closure(result, target, starting_debt_gdp_ratio=start_ratio),
            diagnostics,
        )

    requested_bounds = bounds
    lower, requested_upper = bounds
    effective_upper = requested_upper
    try:
        evaluate(effective_upper)
    except ValueError as error:
        if "issuance rates above 100%" not in str(error):
            raise
        valid = lower
        invalid = requested_upper
        for _ in range(60):
            midpoint = (valid + invalid) / 2.0
            try:
                evaluate(midpoint)
                valid = midpoint
            except ValueError as inner_error:
                if "issuance rates above 100%" not in str(inner_error):
                    raise
                invalid = midpoint
        effective_upper = valid

    solution = _solve_bounded(
        mechanism="Inflationary closure",
        unit="additional cumulative price-level change",
        bounds=(lower, effective_upper),
        target=target,
        baseline_result=baseline,
        evaluate=evaluate,
        scan_points=33,
    )
    if effective_upper != requested_upper:
        diagnostics = dict(solution.diagnostics)
        diagnostics["requested_upper_cumulative_price_change"] = requested_upper
        diagnostics["largest_bound_with_issuance_rates_at_or_below_100_percent"] = (
            effective_upper
        )
        solution = replace(solution, bounds=requested_bounds, diagnostics=diagnostics)
    if not solution.solved or solution.value is None:
        return solution

    # Sequential accounting bridge. It is deliberately labeled order-dependent:
    # denominator, then TIPS, then rate response, then optional deficit scaling.
    cumulative = solution.value
    denominator_assumptions = _apply_inflation_episode(
        assumptions,
        cumulative,
        replace(episode, primary_deficit_scales_with_gdp=False),
        initial_nominal_gdp_billions_saar=initial_nominal_gdp_billions_saar,
        include_tips_indexation=False,
        include_rate_response=False,
    )
    tips_assumptions = _apply_inflation_episode(
        assumptions,
        cumulative,
        replace(episode, primary_deficit_scales_with_gdp=False),
        initial_nominal_gdp_billions_saar=initial_nominal_gdp_billions_saar,
        include_rate_response=False,
    )
    rate_assumptions = _apply_inflation_episode(
        assumptions,
        cumulative,
        replace(episode, primary_deficit_scales_with_gdp=False),
        initial_nominal_gdp_billions_saar=initial_nominal_gdp_billions_saar,
    )
    counterfactuals = []
    for name, counterfactual_assumptions in (
        ("denominator", denominator_assumptions),
        ("tips", tips_assumptions),
        ("rates", rate_assumptions),
    ):
        counterfactual = _run(
            initial_stock,
            counterfactual_assumptions,
            initial_nominal_gdp_billions_saar=initial_nominal_gdp_billions_saar,
            initial_real_gdp_billions_chained_saar=initial_real_gdp_billions_chained_saar,
            issuance_strategy=issuance_strategy,
            scenario_name=f"inflation_bridge_{name}",
            data_vintage=data_vintage,
        )
        counterfactuals.append(float(counterfactual.quarterly.iloc[-1]["debt_held_by_public_gdp_ratio"]))
    baseline_ratio = float(baseline.quarterly.iloc[-1]["debt_held_by_public_gdp_ratio"])
    final_ratio = float(solution.result.quarterly.iloc[-1]["debt_held_by_public_gdp_ratio"])
    denominator_ratio, tips_ratio, rates_ratio = counterfactuals
    diagnostics = dict(solution.diagnostics)
    diagnostics.update(
        {
            "decomposition_order": (
                "denominator -> TIPS -> refinancing/rates -> deficit scaling -> other"
            ),
            "denominator_effect_percentage_points": 100 * (denominator_ratio - baseline_ratio),
            "tips_indexation_effect_percentage_points": 100 * (tips_ratio - denominator_ratio),
            "refinancing_interest_effect_percentage_points": 100 * (rates_ratio - tips_ratio),
            "primary_deficit_scaling_effect_percentage_points": 100 * (final_ratio - rates_ratio),
            "other_financing_effect_percentage_points": 0.0,
        }
    )
    return replace(solution, diagnostics=diagnostics)


def haircut_stock(
    stock: DebtStock,
    haircut: float,
    *,
    eligible_instrument_types: frozenset[InstrumentType] | None = None,
    include_other_public_debt: bool = False,
) -> tuple[DebtStock, float, float]:
    """Apply a mechanical face-value reduction to explicitly eligible debt."""

    if not 0.0 <= haircut <= 1.0:
        raise ValueError("haircut must lie between zero and one")
    eligible = (
        frozenset(InstrumentType)
        if eligible_instrument_types is None
        else eligible_instrument_types
    )
    reduced = stock.copy()
    eligible_amount = sum(
        cohort.principal_billions
        for cohort in reduced.cohorts
        if cohort.instrument_type in eligible
    )
    if include_other_public_debt:
        eligible_amount += reduced.other_public_debt_billions
    updated = []
    for cohort in reduced.cohorts:
        if cohort.instrument_type not in eligible:
            updated.append(cohort)
            continue
        original = cohort.original_principal_billions
        updated.append(
            replace(
                cohort,
                principal_billions=cohort.principal_billions * (1.0 - haircut),
                original_principal_billions=(
                    None if original is None else original * (1.0 - haircut)
                ),
            )
        )
    # Retain zero-principal cohort shells at a 100% haircut so DebtStock.copy()
    # can preserve the valid ledger object until new deficit borrowing is issued.
    reduced.cohorts = updated
    if include_other_public_debt:
        reduced.other_public_debt_billions *= 1.0 - haircut
    return reduced, eligible_amount, eligible_amount * haircut


def apply_parallel_rate_shock(
    assumptions: pd.DataFrame,
    shock_basis_points: float,
    *,
    duration_quarters: int | None = None,
    floor: float = 0.0,
    include_tips_real_rate: bool = True,
) -> pd.DataFrame:
    """Apply an exogenous parallel shock to new-issuance rates."""

    shocked = assumptions.copy()
    duration = len(shocked) if duration_quarters is None else duration_quarters
    if duration <= 0 or duration > len(shocked):
        raise ValueError("rate-shock duration must fall within the simulation horizon")
    periods = shocked.index[:duration]
    columns = ["short_issuance_rate", "intermediate_issuance_rate", "long_issuance_rate"]
    if include_tips_real_rate:
        columns.append("tips_real_issuance_rate")
    change = shock_basis_points / 10_000.0
    for column in columns:
        shocked.loc[periods, column] = np.maximum(floor, shocked.loc[periods, column] + change)
    return shocked


def solve_haircut_equivalent(
    initial_stock: DebtStock,
    assumptions: pd.DataFrame,
    *,
    initial_nominal_gdp_billions_saar: float,
    initial_real_gdp_billions_chained_saar: float,
    issuance_strategy: IssuanceStrategy,
    target: ClosureTarget | None = None,
    eligible_instrument_types: frozenset[InstrumentType] | None = None,
    include_other_public_debt: bool = False,
    post_default_yield_shock_basis_points: float = 0.0,
    bounds: tuple[float, float] = (0.0, 1.0),
    data_vintage: str = "unspecified",
) -> ClosureSolution:
    """Solve for a one-time mechanical face-value haircut equivalent."""

    target = target or ClosureTarget.stabilize_at_start()
    start_ratio = initial_stock.debt_held_by_public_billions / initial_nominal_gdp_billions_saar
    post_assumptions = apply_parallel_rate_shock(
        assumptions, post_default_yield_shock_basis_points
    )
    baseline = _run(
        initial_stock,
        assumptions,
        initial_nominal_gdp_billions_saar=initial_nominal_gdp_billions_saar,
        initial_real_gdp_billions_chained_saar=initial_real_gdp_billions_chained_saar,
        issuance_strategy=issuance_strategy,
        scenario_name="closure_baseline",
        data_vintage=data_vintage,
    )

    def evaluate(haircut: float) -> ScalarTrial:
        reduced, eligible_amount, reduction = haircut_stock(
            initial_stock,
            haircut,
            eligible_instrument_types=eligible_instrument_types,
            include_other_public_debt=include_other_public_debt,
        )
        result = _run(
            reduced,
            post_assumptions,
            initial_nominal_gdp_billions_saar=initial_nominal_gdp_billions_saar,
            initial_real_gdp_billions_chained_saar=initial_real_gdp_billions_chained_saar,
            issuance_strategy=issuance_strategy,
            scenario_name="mechanical_haircut_equivalent",
            data_vintage=data_vintage,
        )
        return ScalarTrial(
            result,
            post_assumptions,
            evaluate_closure(result, target, starting_debt_gdp_ratio=start_ratio),
            {
                "starting_debt_gdp_ratio": start_ratio,
                "eligible_debt_billions": eligible_amount,
                "face_value_reduction_billions": reduction,
                "haircut_fraction": haircut,
                "post_default_yield_shock_basis_points": post_default_yield_shock_basis_points,
                "zero_rate_response_warning": post_default_yield_shock_basis_points == 0,
            },
        )

    return _solve_bounded(
        mechanism="Mechanical face-value haircut equivalent",
        unit="fraction of eligible debt",
        bounds=bounds,
        target=target,
        baseline_result=baseline,
        evaluate=evaluate,
    )


def apply_yield_suppression(
    assumptions: pd.DataFrame,
    suppression_basis_points: float,
    *,
    duration_quarters: int | None = None,
    nominal_yield_floor: float = 0.0,
) -> pd.DataFrame:
    if suppression_basis_points < 0:
        raise ValueError("yield suppression must be nonnegative")
    return apply_parallel_rate_shock(
        assumptions,
        -suppression_basis_points,
        duration_quarters=duration_quarters,
        floor=nominal_yield_floor,
        include_tips_real_rate=False,
    )


def solve_financial_repression(
    initial_stock: DebtStock,
    assumptions: pd.DataFrame,
    *,
    initial_nominal_gdp_billions_saar: float,
    initial_real_gdp_billions_chained_saar: float,
    issuance_strategy: IssuanceStrategy,
    target: ClosureTarget | None = None,
    duration_quarters: int | None = None,
    nominal_yield_floor: float = 0.0,
    bounds_basis_points: tuple[float, float] = (0.0, 2_000.0),
    data_vintage: str = "unspecified",
) -> ClosureSolution:
    """Solve for uniform suppression of new nominal Treasury issuance yields."""

    target = target or ClosureTarget.stabilize_at_start()
    duration = len(assumptions) if duration_quarters is None else duration_quarters
    start_ratio = initial_stock.debt_held_by_public_billions / initial_nominal_gdp_billions_saar
    baseline = _run(
        initial_stock,
        assumptions,
        initial_nominal_gdp_billions_saar=initial_nominal_gdp_billions_saar,
        initial_real_gdp_billions_chained_saar=initial_real_gdp_billions_chained_saar,
        issuance_strategy=issuance_strategy,
        scenario_name="closure_baseline",
        data_vintage=data_vintage,
    )

    def evaluate(suppression_basis_points: float) -> ScalarTrial:
        suppressed = apply_yield_suppression(
            assumptions,
            suppression_basis_points,
            duration_quarters=duration,
            nominal_yield_floor=nominal_yield_floor,
        )
        result = _run(
            initial_stock,
            suppressed,
            initial_nominal_gdp_billions_saar=initial_nominal_gdp_billions_saar,
            initial_real_gdp_billions_chained_saar=initial_real_gdp_billions_chained_saar,
            issuance_strategy=issuance_strategy,
            scenario_name="financial_repression_closure",
            data_vintage=data_vintage,
        )
        window = result.quarterly.iloc[:duration]
        weights = window["gross_treasury_issuance_billions"].to_numpy(dtype=float)
        rates = window["average_new_issuance_stated_rate"].to_numpy(dtype=float)
        average_financing = float(np.average(rates, weights=weights)) if weights.sum() else 0.0
        inflation_factor = float(
            np.prod((1.0 + window["annual_inflation_rate"].to_numpy(dtype=float)) ** 0.25)
        )
        average_inflation = inflation_factor ** (4.0 / len(window)) - 1.0
        real_financing = (1.0 + average_financing) / (1.0 + average_inflation) - 1.0
        return ScalarTrial(
            result,
            suppressed,
            evaluate_closure(result, target, starting_debt_gdp_ratio=start_ratio),
            {
                "starting_debt_gdp_ratio": start_ratio,
                "required_yield_suppression_basis_points": suppression_basis_points,
                "average_nominal_new_financing_rate": average_financing,
                "average_inflation_rate": average_inflation,
                "approximate_ex_post_real_financing_rate": real_financing,
                "repression_duration_quarters": duration,
                "cumulative_interest_savings_vs_baseline_billions": float(
                    baseline.quarterly.iloc[-1]["cumulative_modeled_interest_billions"]
                    - result.quarterly.iloc[-1]["cumulative_modeled_interest_billions"]
                ),
                "resulting_debt_gdp_ratio": float(
                    result.quarterly.iloc[-1]["debt_held_by_public_gdp_ratio"]
                ),
                "nominal_yield_floor": nominal_yield_floor,
            },
        )

    return _solve_bounded(
        mechanism="Financial-repression closure",
        unit="basis points of new-issuance yield suppression",
        bounds=bounds_basis_points,
        target=target,
        baseline_result=baseline,
        evaluate=evaluate,
    )


def solve_immediate_flow_primary_balance(
    initial_stock: DebtStock,
    assumptions: pd.DataFrame,
    *,
    initial_nominal_gdp_billions_saar: float,
    initial_real_gdp_billions_chained_saar: float,
    issuance_strategy: IssuanceStrategy,
    primary_balance_bounds: tuple[float, float] = (-0.50, 0.50),
    data_vintage: str = "unspecified",
) -> ClosureSolution:
    """Solve the one-period diagnostic for the primary deficit share of GDP."""

    one_quarter = assumptions.iloc[:1].copy()
    target = ClosureTarget.immediate_flow()
    start_ratio = initial_stock.debt_held_by_public_billions / initial_nominal_gdp_billions_saar
    baseline = _run(
        initial_stock,
        one_quarter,
        initial_nominal_gdp_billions_saar=initial_nominal_gdp_billions_saar,
        initial_real_gdp_billions_chained_saar=initial_real_gdp_billions_chained_saar,
        issuance_strategy=issuance_strategy,
        scenario_name="immediate_flow_baseline",
        data_vintage=data_vintage,
    )

    # _solve_bounded expects improvement to make the residual fall. Parameterize
    # the scalar as negative primary-deficit share, then report the actual share.
    lower_pb, upper_pb = primary_balance_bounds

    def evaluate(negative_primary_share: float) -> ScalarTrial:
        primary_share = -negative_primary_share
        adjusted = one_quarter.copy()
        gdp = project_nominal_gdp(adjusted, initial_nominal_gdp_billions_saar).iloc[0]
        adjusted.iloc[0, adjusted.columns.get_loc("primary_deficit_billions")] = (
            primary_share * gdp / 4.0
        )
        result = _run(
            initial_stock,
            adjusted,
            initial_nominal_gdp_billions_saar=initial_nominal_gdp_billions_saar,
            initial_real_gdp_billions_chained_saar=initial_real_gdp_billions_chained_saar,
            issuance_strategy=issuance_strategy,
            scenario_name="immediate_flow_stabilization",
            data_vintage=data_vintage,
        )
        return ScalarTrial(
            result,
            adjusted,
            evaluate_closure(result, target, starting_debt_gdp_ratio=start_ratio),
            {
                "required_primary_deficit_gdp_share": primary_share,
                "required_primary_balance_gdp_share": -primary_share,
            },
        )

    solution = _solve_bounded(
        mechanism="Immediate flow-stabilizing primary balance",
        unit="negative primary-deficit share of GDP",
        bounds=(-upper_pb, -lower_pb),
        target=target,
        baseline_result=baseline,
        evaluate=evaluate,
    )
    return replace(
        solution,
        value=(None if solution.value is None else -solution.value),
        unit="primary-deficit share of GDP (negative = surplus)",
    )


def fiscal_inflation_frontier(
    initial_stock: DebtStock,
    assumptions: pd.DataFrame,
    *,
    initial_nominal_gdp_billions_saar: float,
    initial_real_gdp_billions_chained_saar: float,
    issuance_strategy: IssuanceStrategy,
    fiscal_adjustments: list[float] | np.ndarray,
    episode: InflationEpisode,
    target: ClosureTarget | None = None,
    inflation_bounds: tuple[float, float] = (0.0, 10.0),
    data_vintage: str = "unspecified",
) -> pd.DataFrame:
    """Solve the minimum inflation adjustment at each imposed fiscal improvement."""

    target = target or ClosureTarget.stabilize_at_start()
    rows = []
    for fiscal_adjustment in fiscal_adjustments:
        fiscal_assumptions = apply_fiscal_adjustment(
            assumptions,
            float(fiscal_adjustment),
            initial_nominal_gdp_billions_saar=initial_nominal_gdp_billions_saar,
        )
        solution = solve_inflation_closure(
            initial_stock,
            fiscal_assumptions,
            initial_nominal_gdp_billions_saar=initial_nominal_gdp_billions_saar,
            initial_real_gdp_billions_chained_saar=initial_real_gdp_billions_chained_saar,
            issuance_strategy=issuance_strategy,
            episode=episode,
            target=target,
            bounds=inflation_bounds,
            data_vintage=data_vintage,
        )
        rows.append(
            {
                "primary_balance_improvement_gdp_share": float(fiscal_adjustment),
                "additional_cumulative_price_level_change": solution.value,
                "status": solution.status,
                "terminal_debt_gdp_ratio": solution.evaluation.terminal_debt_gdp_ratio,
                "target_debt_gdp_ratio": solution.evaluation.target_debt_gdp_ratio,
                "target_gap": solution.evaluation.binding_gap,
                "satisfies_target": solution.evaluation.satisfies_target,
                "rate_response_assumption": episode.rate_response.label,
            }
        )
    return pd.DataFrame(rows)


def fiscal_haircut_frontier(
    initial_stock: DebtStock,
    assumptions: pd.DataFrame,
    *,
    initial_nominal_gdp_billions_saar: float,
    initial_real_gdp_billions_chained_saar: float,
    issuance_strategy: IssuanceStrategy,
    fiscal_adjustments: list[float] | np.ndarray,
    target: ClosureTarget | None = None,
    data_vintage: str = "unspecified",
) -> pd.DataFrame:
    target = target or ClosureTarget.stabilize_at_start()
    rows = []
    for adjustment in fiscal_adjustments:
        fiscal_assumptions = apply_fiscal_adjustment(
            assumptions,
            float(adjustment),
            initial_nominal_gdp_billions_saar=initial_nominal_gdp_billions_saar,
        )
        solution = solve_haircut_equivalent(
            initial_stock,
            fiscal_assumptions,
            initial_nominal_gdp_billions_saar=initial_nominal_gdp_billions_saar,
            initial_real_gdp_billions_chained_saar=initial_real_gdp_billions_chained_saar,
            issuance_strategy=issuance_strategy,
            target=target,
            data_vintage=data_vintage,
        )
        rows.append(
            {
                "primary_balance_improvement_gdp_share": float(adjustment),
                "haircut_fraction_of_eligible_debt": solution.value,
                "status": solution.status,
                "terminal_debt_gdp_ratio": solution.evaluation.terminal_debt_gdp_ratio,
                "target_gap": solution.evaluation.binding_gap,
                "satisfies_target": solution.evaluation.satisfies_target,
            }
        )
    return pd.DataFrame(rows)


def fiscal_repression_frontier(
    initial_stock: DebtStock,
    assumptions: pd.DataFrame,
    *,
    initial_nominal_gdp_billions_saar: float,
    initial_real_gdp_billions_chained_saar: float,
    issuance_strategy: IssuanceStrategy,
    fiscal_adjustments: list[float] | np.ndarray,
    target: ClosureTarget | None = None,
    bounds_basis_points: tuple[float, float] = (0.0, 2_000.0),
    data_vintage: str = "unspecified",
) -> pd.DataFrame:
    target = target or ClosureTarget.stabilize_at_start()
    rows = []
    for adjustment in fiscal_adjustments:
        fiscal_assumptions = apply_fiscal_adjustment(
            assumptions,
            float(adjustment),
            initial_nominal_gdp_billions_saar=initial_nominal_gdp_billions_saar,
        )
        solution = solve_financial_repression(
            initial_stock,
            fiscal_assumptions,
            initial_nominal_gdp_billions_saar=initial_nominal_gdp_billions_saar,
            initial_real_gdp_billions_chained_saar=initial_real_gdp_billions_chained_saar,
            issuance_strategy=issuance_strategy,
            target=target,
            bounds_basis_points=bounds_basis_points,
            data_vintage=data_vintage,
        )
        rows.append(
            {
                "primary_balance_improvement_gdp_share": float(adjustment),
                "yield_suppression_basis_points": solution.value,
                "status": solution.status,
                "terminal_debt_gdp_ratio": solution.evaluation.terminal_debt_gdp_ratio,
                "target_gap": solution.evaluation.binding_gap,
                "satisfies_target": solution.evaluation.satisfies_target,
            }
        )
    return pd.DataFrame(rows)


def run_rate_stress_ladder(
    initial_stock: DebtStock,
    assumptions: pd.DataFrame,
    *,
    initial_nominal_gdp_billions_saar: float,
    initial_real_gdp_billions_chained_saar: float,
    issuance_strategy: IssuanceStrategy,
    shocks_basis_points: tuple[float, ...] = (0.0, 100.0, 250.0, 500.0, 750.0, 1_000.0),
    target: ClosureTarget | None = None,
    reference_debt_gdp_ratio: float = 2.10,
    data_vintage: str = "unspecified",
) -> StressLadderResult:
    """Rerun the cohort baseline under progressively higher issuance-rate paths."""

    target = target or ClosureTarget.stabilize_at_start()
    baseline = _run(
        initial_stock,
        assumptions,
        initial_nominal_gdp_billions_saar=initial_nominal_gdp_billions_saar,
        initial_real_gdp_billions_chained_saar=initial_real_gdp_billions_chained_saar,
        issuance_strategy=issuance_strategy,
        scenario_name="rate_ladder_baseline",
        data_vintage=data_vintage,
    )
    rows = []
    paths: dict[float, pd.DataFrame] = {}
    for shock in shocks_basis_points:
        shocked = apply_parallel_rate_shock(assumptions, shock)
        result = _run(
            initial_stock,
            shocked,
            initial_nominal_gdp_billions_saar=initial_nominal_gdp_billions_saar,
            initial_real_gdp_billions_chained_saar=initial_real_gdp_billions_chained_saar,
            issuance_strategy=issuance_strategy,
            scenario_name=f"rate_stress_{shock:g}bp",
            data_vintage=data_vintage,
        )
        paths[float(shock)] = result.quarterly
        fiscal = solve_fiscal_adjustment(
            initial_stock,
            shocked,
            initial_nominal_gdp_billions_saar=initial_nominal_gdp_billions_saar,
            initial_real_gdp_billions_chained_saar=initial_real_gdp_billions_chained_saar,
            issuance_strategy=issuance_strategy,
            target=target,
            data_vintage=data_vintage,
        )
        crossed = result.quarterly[
            result.quarterly["debt_held_by_public_gdp_ratio"] >= reference_debt_gdp_ratio
        ]
        ending = result.quarterly.iloc[-1]
        rows.append(
            {
                "issuance_rate_shock_basis_points": float(shock),
                "terminal_debt_gdp_ratio": float(ending["debt_held_by_public_gdp_ratio"]),
                "terminal_interest_gdp_ratio": float(
                    ending["modeled_interest_gdp_ratio_annualized"]
                ),
                "cumulative_additional_interest_billions": float(
                    ending["cumulative_modeled_interest_billions"]
                    - baseline.quarterly.iloc[-1]["cumulative_modeled_interest_billions"]
                ),
                "required_fiscal_adjustment_gdp_share": fiscal.value,
                "fiscal_closure_status": fiscal.status,
                "reference_debt_gdp_ratio": reference_debt_gdp_ratio,
                "reference_crossing_quarter": None if crossed.empty else crossed.iloc[0]["quarter"],
            }
        )
    return StressLadderResult(pd.DataFrame(rows), paths)


def closure_start_after_threshold(
    baseline_result: SimulationResult,
    threshold_debt_gdp_ratio: float,
) -> pd.Period | None:
    """Return the quarter after a baseline first reaches a debt/GDP reference level.

    The reference is not a crisis threshold. Acting in the following quarter
    makes the closure state equal to an actually simulated quarter-end stock.
    """

    if threshold_debt_gdp_ratio < 0:
        raise ValueError("debt/GDP threshold cannot be negative")
    reached = baseline_result.quarterly[
        baseline_result.quarterly["debt_held_by_public_gdp_ratio"]
        >= threshold_debt_gdp_ratio
    ]
    if reached.empty:
        return None
    return pd.Period(str(reached.iloc[0]["quarter"]), freq="Q") + 1
