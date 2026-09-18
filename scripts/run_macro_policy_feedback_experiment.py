"""Let Federal Reserve policy feed back into inflation, output, and deficits.

This run starts from the same model-solved 2036 inflation state used by the
policy-regime engineering check. Unlike that check, only the initial inflation
rate is inherited: subsequent inflation, the output gap, real growth, and the
automatic-stabilizer component of the primary deficit evolve endogenously under
the visible reduced-form feedback coefficients.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from debt_sim.closure import (
    ClosureTarget,
    InflationEpisode,
    InflationRateResponse,
    solve_inflation_closure,
)
from debt_sim.confidence import ConfidenceShock, apply_confidence_shock
from debt_sim.data import load_baseline_bundle
from debt_sim.feedback import MacroFeedbackRule, run_macro_policy_simulation
from debt_sim.model import run_simulation
from debt_sim.policy import PolicyRegime, PolicyRule
from debt_sim.scenarios import build_baseline_scenario, prepare_starting_state

SHOCK_START = pd.Period("2026Q4", freq="Q")
PASS_THE_BUCK_END = pd.Period("2036Q3", freq="Q")
POLICY_START = pd.Period("2036Q4", freq="Q")
POLICY_END = pd.Period("2046Q3", freq="Q")
CONFIDENCE_PREMIUM_BASIS_POINTS = 500.0
LIQUIDITY_STRESS_BASIS_POINTS = 100.0
LIQUIDITY_STRESS_QUARTERS = 4
PRIVATE_CREDIT_SPREAD_BASIS_POINTS = 200.0
PRIVATE_CREDIT_STRESS_QUARTERS = 8
OUTPUT_DIR = Path("data/processed")
CONFIG_DIR = Path("config/scenarios")


def _inherited_state(bundle):
    starting = prepare_starting_state(bundle, SHOCK_START)
    assumptions = build_baseline_scenario(
        bundle,
        start_period=SHOCK_START,
        end_period=PASS_THE_BUCK_END,
    ).quarterly_assumptions
    stress = apply_confidence_shock(
        assumptions,
        ConfidenceShock(
            CONFIDENCE_PREMIUM_BASIS_POINTS,
            duration_quarters=len(assumptions),
        ),
    )
    result = run_simulation(
        starting.stock,
        stress,
        initial_nominal_gdp_billions_saar=starting.initial_nominal_gdp_billions_saar,
        initial_real_gdp_billions_chained_saar=(starting.initial_real_gdp_billions_chained_saar),
        issuance_strategy=bundle.issuance_strategy,
        scenario_name="pre_policy_confidence_stress",
        data_vintage=bundle.cbo_vintage,
    )
    ending = result.quarterly.iloc[-1]
    stock = result.ending_stock.copy()
    stock.reset_scenario_markers()
    return (
        stock,
        float(ending["nominal_gdp_billions_saar"]),
        float(ending["real_gdp_billions_chained_saar"]),
    )


def _initial_inflation_state(bundle, stock, nominal_gdp: float, real_gdp: float):
    assumptions = build_baseline_scenario(
        bundle,
        start_period=POLICY_START,
        end_period=POLICY_END,
    ).quarterly_assumptions
    solution = solve_inflation_closure(
        stock,
        assumptions,
        initial_nominal_gdp_billions_saar=nominal_gdp,
        initial_real_gdp_billions_chained_saar=real_gdp,
        issuance_strategy=bundle.issuance_strategy,
        episode=InflationEpisode(
            duration_quarters=len(assumptions),
            shape="multi_year",
            rate_response=InflationRateResponse.no_response(),
            primary_deficit_scales_with_gdp=True,
        ),
        target=ClosureTarget.stabilize_at_start(),
        bounds=(0.0, 5.0),
        data_vintage=bundle.cbo_vintage,
    )
    if not solution.solved:
        raise RuntimeError("the initial inflation state did not solve")
    initial_inflation = float(solution.assumptions.iloc[0]["annual_inflation_rate"])
    return solution.assumptions, initial_inflation, solution.value


def _quarters_to_rate(path: pd.Series, threshold: float) -> int:
    reached = path.index[path <= threshold]
    return int(reached[0]) if len(reached) else -1


def _summary_row(name: str, result) -> dict[str, float | int | str | bool]:
    path = result.quarterly
    ending = path.iloc[-1]
    inflation = path["annual_inflation_rate"].reset_index(drop=True)
    return {
        "scenario": name,
        "terminal_inflation_rate": float(ending["annual_inflation_rate"]),
        "quarters_to_inflation_at_or_below_3_percent": _quarters_to_rate(inflation, 0.03),
        "minimum_output_gap": float(path["macro_feedback_output_gap"].min()),
        "minimum_annual_real_gdp_growth_rate": float(path["annual_real_gdp_growth_rate"].min()),
        "cumulative_negative_output_gap_years": float(
            -path["macro_feedback_output_gap"].clip(upper=0.0).sum() / 4.0
        ),
        "cumulative_automatic_stabilizer_deficit_billions": float(
            path["automatic_stabilizer_primary_deficit_billions"].sum()
        ),
        "peak_total_deficit_gdp_ratio_annualized": float(
            path["modeled_total_deficit_gdp_ratio_annualized"].max()
        ),
        "terminal_debt_gdp_ratio": float(ending["debt_held_by_public_gdp_ratio"]),
        "cumulative_treasury_interest_billions": float(
            ending["cumulative_modeled_interest_billions"]
        ),
        "cumulative_consolidated_financing_cost_billions": float(
            ending["cumulative_consolidated_public_financing_cost_billions"]
        ),
        "cumulative_fed_purchases_billions": float(path["fed_treasury_purchases_billions"].sum()),
        "ending_incremental_reserves_billions": float(ending["fed_reserve_balances_billions"]),
        "feedback_converged": bool(result.feedback_solution.converged),
        "maximum_absolute_debt_identity_residual_billions": float(
            path["debt_identity_residual_billions"].abs().max()
        ),
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    bundle = load_baseline_bundle()
    stock, nominal_gdp, real_gdp = _inherited_state(bundle)
    reference, initial_inflation, solved_price_level_change = _initial_inflation_state(
        bundle,
        stock,
        nominal_gdp,
        real_gdp,
    )
    liquidity_premium = pd.Series(0.0, index=reference.index)
    liquidity_premium.iloc[:LIQUIDITY_STRESS_QUARTERS] = LIQUIDITY_STRESS_BASIS_POINTS
    private_spread = pd.Series(0.0, index=reference.index)
    private_spread.iloc[:PRIVATE_CREDIT_STRESS_QUARTERS] = PRIVATE_CREDIT_SPREAD_BASIS_POINTS
    feedback_rule = MacroFeedbackRule()

    results = {}
    for regime in PolicyRegime:
        name = regime.value
        results[name] = run_macro_policy_simulation(
            stock,
            reference,
            initial_nominal_gdp_billions_saar=nominal_gdp,
            initial_real_gdp_billions_chained_saar=real_gdp,
            issuance_strategy=bundle.issuance_strategy,
            policy_rule=PolicyRule(regime=regime),
            feedback_rule=feedback_rule,
            initial_inflation_rate=initial_inflation,
            liquidity_premium_basis_points=liquidity_premium,
            private_credit_spread_basis_points=private_spread,
            scenario_name=name,
            data_vintage=bundle.cbo_vintage,
        )

    paths = pd.concat(
        [result.quarterly.assign(scenario=name) for name, result in results.items()],
        ignore_index=True,
    )
    paths.to_csv(OUTPUT_DIR / "macro_policy_feedback_2036_paths.csv", index=False)
    summaries = pd.DataFrame([_summary_row(name, result) for name, result in results.items()])
    summaries.to_csv(OUTPUT_DIR / "macro_policy_feedback_2036_summary.csv", index=False)

    config = {
        "experiment": "Lagged monetary and macro-fiscal feedback from the 2036 inflation state",
        "policy_start": str(POLICY_START),
        "policy_end": str(POLICY_END),
        "initial_inflation_rate": initial_inflation,
        "prior_closure_additional_price_level_change": solved_price_level_change,
        "liquidity_stress_basis_points": LIQUIDITY_STRESS_BASIS_POINTS,
        "liquidity_stress_quarters": LIQUIDITY_STRESS_QUARTERS,
        "private_credit_spread_basis_points": PRIVATE_CREDIT_SPREAD_BASIS_POINTS,
        "private_credit_stress_quarters": PRIVATE_CREDIT_STRESS_QUARTERS,
        "feedback_rule": {
            field: getattr(feedback_rule, field) for field in feedback_rule.__dataclass_fields__
        },
        "warnings": [
            "Feedback coefficients are transparent scenario assumptions, not estimates.",
            "The model GDP-price rate remains a provisional proxy for PCE inflation.",
            (
                "The inherited solved inflation path supplies only the first-quarter state; "
                "later inflation is endogenous."
            ),
            (
                "Private credit stress is imposed and is not yet generated by banks, "
                "dealers, or defaults."
            ),
            "Federal Reserve balance-sheet values remain incremental from 2036Q4.",
            "Scenario comparisons are conditional and are not crisis probabilities.",
        ],
    }
    (CONFIG_DIR / "macro_policy_feedback_2036.json").write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n"
    )
    print(summaries.to_string(index=False))
    print("Wrote macro-policy feedback paths, summary, and configuration")


if __name__ == "__main__":
    main()
