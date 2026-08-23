#!/usr/bin/env python3
"""Run reproducible v0.2 closure experiments and save research tables."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from debt_sim.closure import (
    ClosureTarget,
    InflationEpisode,
    InflationRateResponse,
    apply_inflation_episode,
    closure_start_after_threshold,
    fiscal_inflation_frontier,
    run_rate_stress_ladder,
    solve_financial_repression,
    solve_fiscal_adjustment,
    solve_haircut_equivalent,
    solve_inflation_closure,
)
from debt_sim.data import load_baseline_bundle
from debt_sim.debt_stock import DebtStock, IssuanceStrategy
from debt_sim.instruments import InstrumentType
from debt_sim.model import run_simulation
from debt_sim.scenarios import (
    build_baseline_scenario,
    compare_scenarios,
    prepare_starting_state,
)

OUTPUT_DIR = Path("data/processed")
CONFIG_DIR = Path("config/closure")
MAX_PERIOD = pd.Period("2056Q3", freq="Q")
DEFAULT_HORIZON_QUARTERS = 40


def execute(bundle, state, assumptions, name):
    return run_simulation(
        state.stock,
        assumptions,
        initial_nominal_gdp_billions_saar=state.initial_nominal_gdp_billions_saar,
        initial_real_gdp_billions_chained_saar=state.initial_real_gdp_billions_chained_saar,
        issuance_strategy=bundle.issuance_strategy,
        scenario_name=name,
        data_vintage=bundle.cbo_vintage,
    )


def closure_setup(bundle, start: pd.Period):
    available = MAX_PERIOD.ordinal - start.ordinal + 1
    horizon = min(DEFAULT_HORIZON_QUARTERS, available)
    if horizon < 5:
        raise ValueError("closure setup requires at least five quarters")
    end = start + horizon - 1
    state = prepare_starting_state(bundle, start)
    assumptions = build_baseline_scenario(
        bundle, start_period=start, end_period=end
    ).quarterly_assumptions
    common = {
        "initial_nominal_gdp_billions_saar": state.initial_nominal_gdp_billions_saar,
        "initial_real_gdp_billions_chained_saar": state.initial_real_gdp_billions_chained_saar,
        "issuance_strategy": bundle.issuance_strategy,
        "data_vintage": bundle.cbo_vintage,
    }
    return state, assumptions, common, end


def pure_closures(bundle, start: pd.Period):
    state, assumptions, common, end = closure_setup(bundle, start)
    target = ClosureTarget.stabilize_at_start()
    episode = InflationEpisode(
        duration_quarters=min(20, len(assumptions)),
        shape="multi_year",
        rate_response=InflationRateResponse.uniform(1.0),
    )
    return {
        "state": state,
        "assumptions": assumptions,
        "common": common,
        "start": start,
        "end": end,
        "horizon_quarters": len(assumptions),
        "starting_ratio": (
            state.stock.debt_held_by_public_billions
            / state.initial_nominal_gdp_billions_saar
        ),
        "target": target,
        "episode": episode,
        "fiscal": solve_fiscal_adjustment(
            state.stock, assumptions, target=target, **common
        ),
        "inflation": solve_inflation_closure(
            state.stock,
            assumptions,
            episode=episode,
            target=target,
            bounds=(0.0, 10.0),
            **common,
        ),
        "haircut": solve_haircut_equivalent(
            state.stock, assumptions, target=target, **common
        ),
        "repression": solve_financial_repression(
            state.stock, assumptions, target=target, **common
        ),
    }


def closure_row(result, reference_ratio: float | None = None):
    fiscal = result["fiscal"]
    inflation = result["inflation"]
    haircut = result["haircut"]
    repression = result["repression"]
    return {
        "reference_debt_gdp_ratio": reference_ratio,
        "closure_start": str(result["start"]),
        "closure_end": str(result["end"]),
        "horizon_quarters": result["horizon_quarters"],
        "starting_debt_gdp_ratio": result["starting_ratio"],
        "target_debt_gdp_ratio": fiscal.evaluation.target_debt_gdp_ratio,
        "target_final_four_quarter_max_increase": 0.001,
        "fiscal_adjustment_gdp_share": fiscal.value,
        "fiscal_status": fiscal.status,
        "inflation_cumulative_price_change": inflation.value,
        "inflation_status": inflation.status,
        "inflation_duration_quarters": result["episode"].duration_quarters,
        "inflation_rate_response": result["episode"].rate_response.label,
        "haircut_fraction": haircut.value,
        "haircut_status": haircut.status,
        "haircut_eligible_set": "modeled marketable Treasury debt held by public",
        "haircut_post_event_yield_shock_basis_points": 0.0,
        "repression_basis_points": repression.value,
        "repression_status": repression.status,
        "repression_duration_quarters": result["horizon_quarters"],
        "repression_nominal_yield_floor": 0.0,
    }


def fixed_inflation_experiments(bundle):
    start = pd.Period("2045Q1", freq="Q")
    state, assumptions, _, _ = closure_setup(bundle, start)
    baseline = execute(bundle, state, assumptions, "experiment_2_baseline")
    baseline_factor = float(
        np.prod((1.0 + assumptions.iloc[:4]["annual_inflation_rate"]) ** 0.25)
    )
    regimes = {
        "no_additional_rate_response": InflationRateResponse.no_response(),
        "one_for_one_contemporaneous": InflationRateResponse.uniform(1.0),
        "one_for_one_lagged_8q": InflationRateResponse.uniform(1.0, lag_quarters=8),
    }
    rows = []
    for annual_inflation in (0.05, 0.10, 0.15, 0.20):
        cumulative_extra = (1.0 + annual_inflation) / baseline_factor - 1.0
        for regime, response in regimes.items():
            episode = InflationEpisode(4, "one_year", response)
            shocked = apply_inflation_episode(
                assumptions,
                cumulative_extra,
                episode,
                initial_nominal_gdp_billions_saar=state.initial_nominal_gdp_billions_saar,
            )
            result = execute(bundle, state, shocked, f"inflation_{annual_inflation}_{regime}")
            comparison = compare_scenarios(baseline.quarterly, result.quarterly)
            scenario = result.quarterly
            after = scenario.iloc[4:].copy()
            after["ratio_change"] = after["debt_held_by_public_gdp_ratio"].diff()
            rising = after[after["ratio_change"] > 0]
            rows.append(
                {
                    "closure_start": str(start),
                    "episode_annualized_inflation": annual_inflation,
                    "additional_cumulative_price_change": cumulative_extra,
                    "rate_response_regime": regime,
                    "rate_response_assumption": response.label,
                    "initial_quarter_debt_gdp_change_pp": 100
                    * comparison.iloc[0]["difference_debt_held_by_public_gdp_ratio"],
                    "episode_end_debt_gdp_change_pp": 100
                    * comparison.iloc[3]["difference_debt_held_by_public_gdp_ratio"],
                    "five_year_debt_gdp_change_pp": 100
                    * comparison.iloc[19]["difference_debt_held_by_public_gdp_ratio"],
                    "ten_year_debt_gdp_change_pp": 100
                    * comparison.iloc[39]["difference_debt_held_by_public_gdp_ratio"],
                    "first_absolute_ratio_increase_after_episode": (
                        None if rising.empty else rising.iloc[0]["quarter"]
                    ),
                    "gross_refinanced_during_episode_billions": float(
                        scenario.iloc[:4]["principal_refinanced_billions"].sum()
                    ),
                    "repriced_share_at_episode_end": float(
                        scenario.iloc[3][
                            "share_marketable_debt_repriced_since_scenario_start"
                        ]
                    ),
                    "tips_compensation_increase_billions": float(
                        scenario.iloc[:4]["tips_inflation_compensation_billions"].sum()
                        - baseline.quarterly.iloc[:4][
                            "tips_inflation_compensation_billions"
                        ].sum()
                    ),
                    "ten_year_cumulative_interest_difference_billions": float(
                        comparison.iloc[39][
                            "difference_cumulative_modeled_interest_billions"
                        ]
                    ),
                    "ten_year_nominal_debt_difference_billions": float(
                        comparison.iloc[39]["difference_debt_held_by_public_billions"]
                    ),
                }
            )
    return pd.DataFrame(rows)


def no_tips_counterfactual(stock: DebtStock, strategy: IssuanceStrategy):
    cohorts = [
        replace(cohort, instrument_type=InstrumentType.NOTE)
        if cohort.instrument_type is InstrumentType.TIPS
        else cohort
        for cohort in stock.cohorts
    ]
    no_tips_stock = DebtStock(cohorts, stock.other_public_debt_billions)
    shares = dict(strategy.new_borrowing_shares)
    shares[InstrumentType.NOTE] += shares[InstrumentType.TIPS]
    shares[InstrumentType.TIPS] = 0.0
    no_tips_strategy = IssuanceStrategy(
        new_borrowing_shares=shares,
        tenor_quarters=strategy.tenor_quarters,
        preserve_instrument_type_on_rollover=strategy.preserve_instrument_type_on_rollover,
    )
    return no_tips_stock, no_tips_strategy


def endpoint_sensitivities(bundle):
    start = pd.Period("2045Q1", freq="Q")
    state, assumptions, common, end = closure_setup(bundle, start)
    starting_ratio = (
        state.stock.debt_held_by_public_billions
        / state.initial_nominal_gdp_billions_saar
    )
    target = ClosureTarget.specified_ratio(starting_ratio)
    regimes = {
        "no_additional_rate_response": InflationRateResponse.no_response(),
        "one_for_one_contemporaneous": InflationRateResponse.uniform(1.0),
        "one_for_one_lagged_8q": InflationRateResponse.uniform(1.0, lag_quarters=8),
    }
    inflation = {}
    for name, response in regimes.items():
        solution = solve_inflation_closure(
            state.stock,
            assumptions,
            episode=InflationEpisode(20, "multi_year", response),
            target=target,
            bounds=(0.0, 10.0),
            **common,
        )
        inflation[name] = {
            "status": solution.status,
            "additional_cumulative_price_change": solution.value,
            "total_annualized_inflation": solution.diagnostics.get(
                "total_annualized_inflation_during_episode"
            ),
            "cumulative_interest_difference_billions": solution.diagnostics.get(
                "cumulative_interest_cost_relative_to_baseline_billions"
            ),
            "gross_refinancing_share_of_starting_marketable_debt": (
                solution.diagnostics.get(
                    "gross_refinancing_share_of_starting_marketable_debt"
                )
            ),
        }

    no_tips_stock, no_tips_strategy = no_tips_counterfactual(
        state.stock, bundle.issuance_strategy
    )
    episode = InflationEpisode(20, "multi_year")
    with_tips = solve_inflation_closure(
        state.stock,
        assumptions,
        episode=episode,
        target=target,
        bounds=(0.0, 10.0),
        **common,
    )
    no_tips_common = dict(common)
    no_tips_common["issuance_strategy"] = no_tips_strategy
    without_tips = solve_inflation_closure(
        no_tips_stock,
        assumptions,
        episode=episode,
        target=target,
        bounds=(0.0, 10.0),
        **no_tips_common,
    )

    haircuts = {}
    for shock in (0.0, 500.0, 1_000.0):
        solution = solve_haircut_equivalent(
            state.stock,
            assumptions,
            target=target,
            post_default_yield_shock_basis_points=shock,
            **common,
        )
        haircuts[f"post_event_yield_shock_{int(shock)}bp"] = {
            "status": solution.status,
            "haircut_fraction": solution.value,
            "eligible_debt_billions": solution.diagnostics.get(
                "eligible_debt_billions"
            ),
            "face_value_reduction_billions": solution.diagnostics.get(
                "face_value_reduction_billions"
            ),
        }
    return {
        "closure_start": str(start),
        "closure_end": str(end),
        "target_definition": "endpoint debt/GDP no higher than starting debt/GDP",
        "starting_debt_gdp_ratio": starting_ratio,
        "inflation_rate_response_sensitivity": inflation,
        "tips_sensitivity": {
            "with_tips_required_cumulative_price_change": with_tips.value,
            "without_tips_required_cumulative_price_change": without_tips.value,
            "additional_cumulative_change_due_to_tips": (
                None
                if with_tips.value is None or without_tips.value is None
                else with_tips.value - without_tips.value
            ),
        },
        "haircut_post_event_rate_sensitivity": haircuts,
    }


def state_endpoint_sensitivities(pure_by_state):
    inflation_rows = []
    haircut_rows = []
    regimes = {
        "no_additional_rate_response": InflationRateResponse.no_response(),
        "one_for_one_contemporaneous": InflationRateResponse.uniform(1.0),
        "one_for_one_lagged_8q": InflationRateResponse.uniform(1.0, lag_quarters=8),
    }
    for threshold, setup in pure_by_state.items():
        target = ClosureTarget.specified_ratio(setup["starting_ratio"])
        for name, response in regimes.items():
            solution = solve_inflation_closure(
                setup["state"].stock,
                setup["assumptions"],
                episode=InflationEpisode(
                    min(20, setup["horizon_quarters"]),
                    "multi_year",
                    response,
                ),
                target=target,
                bounds=(0.0, 10.0),
                **setup["common"],
            )
            inflation_rows.append(
                {
                    "reference_debt_gdp_ratio": threshold,
                    "closure_start": str(setup["start"]),
                    "closure_end": str(setup["end"]),
                    "target_definition": "endpoint no higher than starting ratio",
                    "rate_response_regime": name,
                    "rate_response_assumption": response.label,
                    "status": solution.status,
                    "additional_cumulative_price_change": solution.value,
                    "total_annualized_inflation": solution.diagnostics.get(
                        "total_annualized_inflation_during_episode"
                    ),
                    "terminal_debt_gdp_ratio": (
                        solution.evaluation.terminal_debt_gdp_ratio
                    ),
                    "cumulative_interest_difference_billions": (
                        solution.diagnostics.get(
                            "cumulative_interest_cost_relative_to_baseline_billions"
                        )
                    ),
                }
            )
        for shock in (0.0, 500.0):
            solution = solve_haircut_equivalent(
                setup["state"].stock,
                setup["assumptions"],
                target=target,
                post_default_yield_shock_basis_points=shock,
                **setup["common"],
            )
            haircut_rows.append(
                {
                    "reference_debt_gdp_ratio": threshold,
                    "closure_start": str(setup["start"]),
                    "closure_end": str(setup["end"]),
                    "target_definition": "endpoint no higher than starting ratio",
                    "post_event_yield_shock_basis_points": shock,
                    "status": solution.status,
                    "haircut_fraction": solution.value,
                    "face_value_reduction_billions": solution.diagnostics.get(
                        "face_value_reduction_billions"
                    ),
                    "terminal_debt_gdp_ratio": (
                        solution.evaluation.terminal_debt_gdp_ratio
                    ),
                }
            )
    return pd.DataFrame(inflation_rows), pd.DataFrame(haircut_rows)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    bundle = load_baseline_bundle()
    baseline_scenario = build_baseline_scenario(bundle, end_period=MAX_PERIOD)
    baseline = run_simulation(
        bundle.initial_stock,
        baseline_scenario.quarterly_assumptions,
        initial_nominal_gdp_billions_saar=bundle.initial_nominal_gdp_billions_saar,
        initial_real_gdp_billions_chained_saar=bundle.initial_real_gdp_billions_chained_saar,
        issuance_strategy=bundle.issuance_strategy,
        scenario_name="extended_baseline",
        data_vintage=bundle.cbo_vintage,
    )
    baseline.quarterly.to_csv(
        OUTPUT_DIR / "extended_baseline_simulation_quarterly_2026-02-25.csv",
        index=False,
    )

    date_rows = []
    pure_by_date = {}
    for year in (2030, 2035, 2040, 2045, 2050, 2055):
        result = pure_closures(bundle, pd.Period(f"{year}Q1", freq="Q"))
        pure_by_date[year] = result
        date_rows.append(closure_row(result))
        print(f"Solved pure mechanisms from {result['start']} through {result['end']}")
    pd.DataFrame(date_rows).to_csv(
        OUTPUT_DIR / "closure_requirements_by_start_2026-02-25.csv", index=False
    )

    state_rows = []
    pure_by_state = {}
    for threshold in (1.20, 1.40, 1.60, 1.80, 2.00):
        start = closure_start_after_threshold(baseline, threshold)
        if start is None or start > MAX_PERIOD:
            state_rows.append(
                {
                    "reference_debt_gdp_ratio": threshold,
                    "reachable_in_baseline": False,
                    "fiscal_status": "reference_not_reached",
                    "inflation_status": "reference_not_reached",
                    "haircut_status": "reference_not_reached",
                    "repression_status": "reference_not_reached",
                }
            )
            continue
        result = pure_closures(bundle, start)
        pure_by_state[threshold] = result
        row = closure_row(result, threshold)
        row["reachable_in_baseline"] = True
        state_rows.append(row)
        print(f"Solved state table at {threshold:.0%} reference ({start})")
    pd.DataFrame(state_rows).to_csv(
        OUTPUT_DIR / "closure_requirements_by_debt_state_2026-02-25.csv",
        index=False,
    )

    fixed = fixed_inflation_experiments(bundle)
    fixed.to_csv(
        OUTPUT_DIR / "inflation_5_10_15_20_experiments_2026-02-25.csv",
        index=False,
    )
    print(f"Wrote {len(fixed)} fixed-inflation experiments")

    sensitivities = endpoint_sensitivities(bundle)
    (OUTPUT_DIR / "closure_endpoint_sensitivities_2026-02-25.json").write_text(
        json.dumps(sensitivities, indent=2, sort_keys=True) + "\n"
    )
    state_inflation, state_haircuts = state_endpoint_sensitivities(pure_by_state)
    state_inflation.to_csv(
        OUTPUT_DIR / "inflation_closure_by_debt_state_2026-02-25.csv",
        index=False,
    )
    state_haircuts.to_csv(
        OUTPUT_DIR / "haircut_equivalent_by_debt_state_2026-02-25.csv",
        index=False,
    )

    ladder_base = pure_by_date[2045]
    ladder = run_rate_stress_ladder(
        ladder_base["state"].stock,
        ladder_base["assumptions"],
        target=ladder_base["target"],
        reference_debt_gdp_ratio=2.10,
        **ladder_base["common"],
    )
    ladder.table.to_csv(
        OUTPUT_DIR / "rate_stress_ladder_2026-02-25.csv", index=False
    )
    pd.concat(
        [
            path.assign(issuance_rate_shock_basis_points=shock)
            for shock, path in ladder.paths.items()
        ],
        ignore_index=True,
    ).to_csv(
        OUTPUT_DIR / "rate_stress_ladder_paths_2026-02-25.csv", index=False
    )
    print("Wrote rate-shock stress ladder")

    frontier_rows = []
    for threshold in (1.20, 1.50, 1.80, 2.00):
        start = closure_start_after_threshold(baseline, threshold)
        if start is None or start > MAX_PERIOD:
            frontier_rows.append(
                pd.DataFrame(
                    [
                        {
                            "reference_debt_gdp_ratio": threshold,
                            "status": "reference_not_reached",
                        }
                    ]
                )
            )
            continue
        setup = pure_by_state.get(threshold) or pure_closures(bundle, start)
        fiscal_value = setup["fiscal"].value or 0.10
        grid = np.linspace(0.0, min(0.12, fiscal_value * 1.25), 9)
        # This frontier uses closure target B (the same endpoint ratio as the
        # starting state) so temporary inflation and fiscal adjustment can form
        # an informative tradeoff. The stricter default target A remains in the
        # pure-mechanism tables and additionally requires a flat final-year flow.
        frontier_target = ClosureTarget.specified_ratio(setup["starting_ratio"])
        frontier = fiscal_inflation_frontier(
            setup["state"].stock,
            setup["assumptions"],
            fiscal_adjustments=grid,
            episode=setup["episode"],
            target=frontier_target,
            inflation_bounds=(0.0, 10.0),
            **setup["common"],
        )
        frontier.insert(0, "reference_debt_gdp_ratio", threshold)
        frontier.insert(1, "closure_start", str(start))
        frontier.insert(2, "closure_end", str(setup["end"]))
        frontier.insert(
            3,
            "frontier_target_definition",
            "endpoint debt/GDP no higher than starting debt/GDP",
        )
        frontier_rows.append(frontier)
        print(f"Solved mixed frontier at {threshold:.0%} reference")
    pd.concat(frontier_rows, ignore_index=True).to_csv(
        OUTPUT_DIR / "fiscal_inflation_frontiers_2026-02-25.csv", index=False
    )

    default = pure_by_date[2045]
    path_results = (
        ("unchanged_baseline", default["fiscal"].baseline_result),
        ("fiscal_closure", default["fiscal"].result),
        ("inflationary_closure_or_best_bound", default["inflation"].result),
        ("haircut_equivalent_or_best_bound", default["haircut"].result),
        ("financial_repression_closure", default["repression"].result),
    )
    pd.concat(
        [
            result.quarterly.assign(mechanism=mechanism)
            for mechanism, result in path_results
        ],
        ignore_index=True,
    ).to_csv(
        OUTPUT_DIR / "pure_closure_paths_2045_2026-02-25.csv", index=False
    )

    configuration = {
        "model_version": "0.2",
        "ten_year_baseline_release": "2026-02-11",
        "long_term_extension_release": "2026-02-25",
        "maximum_period": str(MAX_PERIOD),
        "default_closure_horizon_quarters": DEFAULT_HORIZON_QUARTERS,
        "default_closure_target": {
            "endpoint": "no higher than starting debt/GDP",
            "final_four_quarter_max_increase": 0.001,
        },
        "fiscal_bounds_gdp_share": [0.0, 0.20],
        "inflation_bounds_additional_cumulative_price_change": [0.0, 10.0],
        "haircut_bounds": [0.0, 1.0],
        "repression_bounds_basis_points": [0.0, 2_000.0],
        "inflation_requirement_assumption": (
            "five-year episode; one-for-one contemporaneous pass-through"
        ),
        "haircut_eligible_set": "modeled marketable Treasury debt held by public",
        "post_default_yield_shock_default_basis_points": 0.0,
        "repression_inflation_path": "CBO baseline",
    }
    (CONFIG_DIR / "v02_experiments.json").write_text(
        json.dumps(configuration, indent=2, sort_keys=True) + "\n"
    )
    print("v0.2 experiments complete")


if __name__ == "__main__":
    main()
