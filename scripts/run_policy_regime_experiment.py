"""Compare Federal Reserve regimes on the existing 2036 inflation path.

The experiment holds the inherited Treasury cohort stock and macro-fiscal path
constant, then changes the policy response. Federal Reserve balance-sheet values
are incremental from 2036Q4; pinning a full historical H.4.1 path is a separate
roadmap item.
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
from debt_sim.model import run_simulation
from debt_sim.policy import PolicyRegime, PolicyRule, run_policy_simulation
from debt_sim.scenarios import build_baseline_scenario, prepare_starting_state

SHOCK_START = pd.Period("2026Q4", freq="Q")
PASS_THE_BUCK_END = pd.Period("2036Q3", freq="Q")
POLICY_START = pd.Period("2036Q4", freq="Q")
POLICY_END = pd.Period("2046Q3", freq="Q")
CONFIDENCE_PREMIUM_BASIS_POINTS = 500.0
LIQUIDITY_STRESS_BASIS_POINTS = 100.0
LIQUIDITY_STRESS_QUARTERS = 4
OUTPUT_DIR = Path("data/processed")
CONFIG_DIR = Path("config/scenarios")


def _inherited_state(bundle):
    starting_state = prepare_starting_state(bundle, SHOCK_START)
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
        starting_state.stock,
        stress,
        initial_nominal_gdp_billions_saar=starting_state.initial_nominal_gdp_billions_saar,
        initial_real_gdp_billions_chained_saar=(
            starting_state.initial_real_gdp_billions_chained_saar
        ),
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


def _reference_inflation_path(bundle, stock, nominal_gdp: float, real_gdp: float):
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
        raise RuntimeError("the reference inflation path did not solve")
    return solution


def _summary_row(name: str, result) -> dict[str, float | str | bool]:
    path = result.quarterly
    ending = path.iloc[-1]
    debt_ratios = path["debt_held_by_public_gdp_ratio"]
    return {
        "scenario": name,
        "policy_regime": str(ending["policy_regime"]),
        "terminal_debt_gdp_ratio": float(ending["debt_held_by_public_gdp_ratio"]),
        "final_four_quarter_debt_gdp_change": float(debt_ratios.iloc[-1] - debt_ratios.iloc[-5]),
        "average_inflation_rate": float(path["annual_inflation_rate"].mean()),
        "average_shadow_short_rate": float(path["shadow_short_issuance_rate"].mean()),
        "average_actual_short_rate": float(path["short_issuance_rate"].mean()),
        "average_iorb_rate": float(path["iorb_rate"].mean()),
        "average_nominal_yield_suppression_basis_points": float(
            path["average_nominal_yield_suppression_basis_points"].mean()
        ),
        "maximum_required_fed_purchase_gross_issuance_share": float(
            path["required_fed_purchase_equivalent_gross_issuance_share"].max()
        ),
        "cumulative_required_fed_purchases_billions": float(
            path["required_fed_treasury_purchases_billions"].sum()
        ),
        "cumulative_actual_fed_purchases_billions": float(
            path["fed_treasury_purchases_billions"].sum()
        ),
        "cumulative_unfilled_fed_purchases_billions": float(
            path["unfilled_fed_treasury_purchases_billions"].sum()
        ),
        "ending_incremental_fed_treasury_holdings_billions": float(
            ending["fed_treasury_holdings_billions"]
        ),
        "ending_incremental_reserve_balances_billions": float(
            ending["fed_reserve_balances_billions"]
        ),
        "cumulative_treasury_interest_billions": float(
            ending["cumulative_modeled_interest_billions"]
        ),
        "cumulative_consolidated_financing_cost_billions": float(
            ending["cumulative_consolidated_public_financing_cost_billions"]
        ),
        "fed_purchase_requirement_fully_covered": bool(
            path["fed_purchase_requirement_covered"].all()
        ),
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    bundle = load_baseline_bundle()
    stock, nominal_gdp, real_gdp = _inherited_state(bundle)
    reference_solution = _reference_inflation_path(
        bundle,
        stock,
        nominal_gdp,
        real_gdp,
    )
    reference_assumptions = reference_solution.assumptions
    liquidity_premium = pd.Series(0.0, index=reference_assumptions.index)
    liquidity_premium.iloc[:LIQUIDITY_STRESS_QUARTERS] = LIQUIDITY_STRESS_BASIS_POINTS

    results = {}
    for regime in PolicyRegime:
        name = regime.value
        results[name] = run_policy_simulation(
            stock,
            reference_assumptions,
            initial_nominal_gdp_billions_saar=nominal_gdp,
            initial_real_gdp_billions_chained_saar=real_gdp,
            issuance_strategy=bundle.issuance_strategy,
            policy_rule=PolicyRule(regime=regime),
            liquidity_premium_basis_points=liquidity_premium,
            scenario_name=name,
            data_vintage=bundle.cbo_vintage,
        )

    paths = pd.concat(
        [result.quarterly.assign(scenario=name) for name, result in results.items()],
        ignore_index=True,
    )
    paths.to_csv(OUTPUT_DIR / "policy_regime_2036_paths.csv", index=False)
    pd.DataFrame([_summary_row(name, result) for name, result in results.items()]).to_csv(
        OUTPUT_DIR / "policy_regime_2036_summary.csv", index=False
    )

    config = {
        "experiment": "Federal Reserve policy regimes on the 2036 inflation path",
        "policy_start": str(POLICY_START),
        "policy_end": str(POLICY_END),
        "inherited_confidence_premium_basis_points": CONFIDENCE_PREMIUM_BASIS_POINTS,
        "reference_additional_price_level_change": reference_solution.value,
        "reference_average_inflation_rate": reference_solution.diagnostics[
            "total_annualized_inflation_during_episode"
        ],
        "policy_regimes": [regime.value for regime in PolicyRegime],
        "inflation_target": 0.02,
        "inflation_response": 1.5,
        "reaction_smoothing": 0.5,
        "initial_liquidity_stress_basis_points": LIQUIDITY_STRESS_BASIS_POINTS,
        "liquidity_stress_quarters": LIQUIDITY_STRESS_QUARTERS,
        "purchase_elasticity_basis_points_per_gross_issuance": 500.0,
        "policy_inflation_measure": (
            "model GDP-price inflation used provisionally as the policy-inflation proxy; "
            "a separate PCE path remains to be added"
        ),
        "inflation_behavior": (
            "the reference inflation path remains imposed; policy rates do not yet feed "
            "back into inflation or output"
        ),
        "fed_balance_sheet_scope": (
            "incremental purchases and reserves beginning in 2036Q4; existing SOMA and "
            "reserve balances are excluded pending a pinned historical balance-sheet path"
        ),
        "warning": (
            "The purchase elasticity is an explicit placeholder, not an empirical estimate. "
            "Scenario comparisons are conditional and are not crisis probabilities."
        ),
    }
    (CONFIG_DIR / "policy_regimes_2036.json").write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n"
    )
    print("Wrote policy-regime paths, summary, and configuration")


if __name__ == "__main__":
    main()
