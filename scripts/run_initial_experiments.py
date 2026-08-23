#!/usr/bin/env python3
"""Run the v0.1 deterministic inflation experiments and save reproducible outputs."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pandas as pd

from debt_sim.data import load_baseline_bundle
from debt_sim.debt_stock import DebtStock, IssuanceStrategy
from debt_sim.instruments import InstrumentType
from debt_sim.model import run_simulation
from debt_sim.scenarios import (
    apply_manual_primary_deficit,
    build_baseline_scenario,
    build_custom_scenario,
    build_preset_scenario,
    compare_scenarios,
    prepare_starting_state,
)

OUTPUT_DIR = Path("data/processed")
CONFIG_DIR = Path("config/scenarios")
SHOCK_START = pd.Period("2027Q1", freq="Q")
END = pd.Period("2036Q3", freq="Q")


def execute(bundle, scenario, *, stock=None, strategy=None, state=None):
    if state is None:
        initial_stock = stock or bundle.initial_stock
        nominal = bundle.initial_nominal_gdp_billions_saar
        real = bundle.initial_real_gdp_billions_chained_saar
    else:
        initial_stock = state.stock if stock is None else stock
        nominal = state.initial_nominal_gdp_billions_saar
        real = state.initial_real_gdp_billions_chained_saar
    return run_simulation(
        initial_stock,
        scenario.quarterly_assumptions,
        initial_nominal_gdp_billions_saar=nominal,
        initial_real_gdp_billions_chained_saar=real,
        issuance_strategy=strategy or bundle.issuance_strategy,
        scenario_name=scenario.name,
        data_vintage=bundle.cbo_vintage,
    ).quarterly


def summarize(name, parameters, baseline, result):
    comparison = compare_scenarios(baseline, result)
    shock_end = SHOCK_START + int(parameters.get("inflation_duration_quarters", 4)) - 1
    first = comparison[comparison["quarter"] == str(SHOCK_START)].iloc[0]
    at_shock_end = comparison[comparison["quarter"] == str(shock_end)].iloc[0]
    ending = comparison.iloc[-1]
    minimum = comparison.loc[comparison["difference_debt_held_by_public_gdp_ratio"].idxmin()]
    after = comparison[
        (comparison["quarter"] > str(shock_end))
        & (comparison["difference_debt_held_by_public_gdp_ratio"] >= 0)
    ]
    return {
        "scenario": name,
        **parameters,
        "first_shock_quarter_debt_gdp_difference_pp": 100
        * first["difference_debt_held_by_public_gdp_ratio"],
        "shock_end_quarter": str(shock_end),
        "shock_end_debt_gdp_difference_pp": 100
        * at_shock_end["difference_debt_held_by_public_gdp_ratio"],
        "shock_end_nominal_debt_difference_billions": at_shock_end[
            "difference_debt_held_by_public_billions"
        ],
        "shock_end_nominal_gdp_difference_billions_saar": at_shock_end[
            "difference_nominal_gdp_billions_saar"
        ],
        "minimum_debt_gdp_difference_quarter": minimum["quarter"],
        "minimum_debt_gdp_difference_pp": 100 * minimum["difference_debt_held_by_public_gdp_ratio"],
        "end_debt_gdp_difference_pp": 100 * ending["difference_debt_held_by_public_gdp_ratio"],
        "end_nominal_debt_difference_billions": ending["difference_debt_held_by_public_billions"],
        "end_nominal_gdp_difference_billions_saar": ending["difference_nominal_gdp_billions_saar"],
        "end_cumulative_interest_difference_billions": ending[
            "difference_cumulative_modeled_interest_billions"
        ],
        "debt_gdp_benefit_erased_quarter": None if after.empty else after.iloc[0]["quarter"],
    }


def write_config(bundle, scenario, extra=None):
    payload = {
        "scenario_name": scenario.name,
        "description": scenario.description,
        "cbo_vintage": bundle.cbo_vintage,
        "treasury_observation_date": bundle.treasury_observation_date,
        "start_period": str(scenario.quarterly_assumptions.index.min()),
        "end_period": str(scenario.quarterly_assumptions.index.max()),
        "imposed_parameters": scenario.imposed_parameters,
    }
    if extra:
        payload.update(extra)
    path = CONFIG_DIR / f"{scenario.name}.json"
    path.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            default=lambda value: value.item() if hasattr(value, "item") else str(value),
        )
        + "\n"
    )


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    bundle = load_baseline_bundle()
    baseline_scenario = build_baseline_scenario(bundle)
    baseline = execute(bundle, baseline_scenario)
    write_config(bundle, baseline_scenario)

    named_presets = [
        "inflation_no_rate_response",
        "inflation_immediate_rate_response",
        "inflation_delayed_rate_response",
        "persistent_financial_repression",
    ]
    summaries = []
    quarterly_outputs = [baseline.assign(scenario="baseline")]
    named_results = {}
    for preset in named_presets:
        scenario = build_preset_scenario(bundle, preset)
        result = execute(bundle, scenario)
        named_results[preset] = result
        quarterly_outputs.append(result.assign(scenario=preset))
        summaries.append(summarize(preset, scenario.imposed_parameters, baseline, result))
        write_config(bundle, scenario)

    stress_rows = []
    regimes = {
        "rates_unchanged": (0.0, 0),
        "rates_plus_500bp_immediate": (500.0, 0),
        "rates_plus_500bp_delayed_4q": (500.0, 4),
    }
    for inflation in (0.05, 0.10, 0.15, 0.20):
        for duration in (4, 8):
            for regime, (rate_shock, lag) in regimes.items():
                scenario = build_custom_scenario(
                    bundle,
                    start_period="2025Q4",
                    end_period=END,
                    shock_start_period=SHOCK_START,
                    shock_duration_quarters=duration,
                    inflation_rate=inflation,
                    short_rate_shock_basis_points=rate_shock,
                    intermediate_rate_shock_basis_points=rate_shock,
                    long_rate_shock_basis_points=rate_shock,
                    tips_real_rate_shock_basis_points=rate_shock,
                    rate_response_lag_quarters=lag,
                )
                result = execute(bundle, scenario)
                params = {
                    "inflation_rate": inflation,
                    "inflation_duration_quarters": duration,
                    "rate_regime": regime,
                    "rate_shock_basis_points": rate_shock,
                    "rate_response_lag_quarters": lag,
                }
                stress_rows.append(
                    summarize(
                        f"stress_{inflation}_{duration}_{regime}",
                        params,
                        baseline,
                        result,
                    )
                )

    permanent_rows = []
    permanent_duration = len(pd.period_range(SHOCK_START, END, freq="Q"))
    for basis_points in (300.0, 500.0, 800.0):
        scenario = build_custom_scenario(
            bundle,
            start_period="2025Q4",
            end_period=END,
            shock_start_period=SHOCK_START,
            shock_duration_quarters=4,
            inflation_rate=0.10,
            short_rate_shock_basis_points=basis_points,
            intermediate_rate_shock_basis_points=basis_points,
            long_rate_shock_basis_points=basis_points,
            tips_real_rate_shock_basis_points=basis_points,
            rate_shock_duration_quarters=permanent_duration,
        )
        scenario = replace(
            scenario,
            name=f"inflation_10pct_permanent_rates_plus_{int(basis_points)}bp",
        )
        result = execute(bundle, scenario)
        params = {
            "inflation_rate": 0.10,
            "inflation_duration_quarters": 4,
            "rate_regime": "parallel shock through 2036Q3",
            "rate_shock_basis_points": basis_points,
            "rate_response_lag_quarters": 0,
        }
        permanent_rows.append(summarize(scenario.name, params, baseline, result))
        write_config(bundle, scenario)

    # Mechanical TIPS counterfactual: reclassify TIPS as fixed notes without
    # changing principal, maturity, or inherited real financing rate. This
    # isolates indexation; it is not an alternative debt-management forecast.
    no_tips_cohorts = [
        replace(cohort, instrument_type=InstrumentType.NOTE)
        if cohort.instrument_type is InstrumentType.TIPS
        else cohort
        for cohort in bundle.initial_stock.cohorts
    ]
    no_tips_stock = DebtStock(no_tips_cohorts, bundle.initial_stock.other_public_debt_billions)
    no_tips_shares = dict(bundle.issuance_strategy.new_borrowing_shares)
    no_tips_shares[InstrumentType.NOTE] += no_tips_shares[InstrumentType.TIPS]
    no_tips_shares[InstrumentType.TIPS] = 0.0
    no_tips_strategy = IssuanceStrategy(new_borrowing_shares=no_tips_shares)
    no_tips_baseline = execute(
        bundle, baseline_scenario, stock=no_tips_stock, strategy=no_tips_strategy
    )
    no_tips_shock = execute(
        bundle,
        build_preset_scenario(bundle, "inflation_no_rate_response"),
        stock=no_tips_stock,
        strategy=no_tips_strategy,
    )
    tips_comparison = compare_scenarios(
        baseline, named_results["inflation_no_rate_response"]
    ).set_index("quarter")
    no_tips_comparison = compare_scenarios(no_tips_baseline, no_tips_shock).set_index("quarter")

    # Compare a fixed nominal primary deficit with a GDP-share deficit. Both
    # begin at the same annual amount in 2027Q1.
    state_2027 = prepare_starting_state(bundle, SHOCK_START)
    baseline_2027 = build_baseline_scenario(bundle, start_period=SHOCK_START)
    shock_2027 = build_preset_scenario(
        bundle,
        "inflation_no_rate_response",
        start_period=SHOCK_START,
        shock_start_period=SHOCK_START,
    )
    first_row = baseline_2027.quarterly_assumptions.iloc[0]
    first_baseline_gdp = (
        state_2027.initial_nominal_gdp_billions_saar
        * (1 + first_row["annual_real_gdp_growth_rate"]) ** 0.25
        * (1 + first_row["annual_inflation_rate"]) ** 0.25
    )
    matched_annual_nominal = 0.025 * first_baseline_gdp
    primary_mode_results = {}
    for mode, value in (
        ("annual_nominal_billions", matched_annual_nominal),
        ("percent_gdp", 0.025),
    ):
        base_mode = apply_manual_primary_deficit(
            baseline_2027,
            bundle,
            mode=mode,
            value=value,
            initial_nominal_gdp_billions_saar=state_2027.initial_nominal_gdp_billions_saar,
        )
        shock_mode = apply_manual_primary_deficit(
            shock_2027,
            bundle,
            mode=mode,
            value=value,
            initial_nominal_gdp_billions_saar=state_2027.initial_nominal_gdp_billions_saar,
        )
        primary_mode_results[mode] = compare_scenarios(
            execute(bundle, base_mode, state=state_2027),
            execute(bundle, shock_mode, state=state_2027),
        ).set_index("quarter")

    cross_checks = {
        "tips_counterfactual": {
            quarter: {
                "with_tips_debt_gdp_difference_pp": 100
                * tips_comparison.loc[quarter, "difference_debt_held_by_public_gdp_ratio"],
                "without_tips_debt_gdp_difference_pp": 100
                * no_tips_comparison.loc[quarter, "difference_debt_held_by_public_gdp_ratio"],
                "with_tips_nominal_debt_difference_billions": tips_comparison.loc[
                    quarter, "difference_debt_held_by_public_billions"
                ],
                "without_tips_nominal_debt_difference_billions": no_tips_comparison.loc[
                    quarter, "difference_debt_held_by_public_billions"
                ],
            }
            for quarter in ("2027Q4", "2036Q3")
        },
        "primary_deficit_mode": {
            "matched_initial_annual_primary_deficit_billions": matched_annual_nominal,
            **{
                mode: {
                    quarter: {
                        "debt_gdp_difference_pp": 100
                        * frame.loc[quarter, "difference_debt_held_by_public_gdp_ratio"],
                        "nominal_debt_difference_billions": frame.loc[
                            quarter, "difference_debt_held_by_public_billions"
                        ],
                    }
                    for quarter in ("2027Q4", "2036Q3")
                }
                for mode, frame in primary_mode_results.items()
            },
        },
        "baseline_repricing": {
            baseline.iloc[index]["quarter"]: baseline.iloc[index][
                "share_marketable_debt_repriced_since_scenario_start"
            ]
            for index in (0, 3, 7, 19, 39, 43)
        },
        "immediate_rate_response_interest_changes_billions": {
            quarter: {
                column: named_results["inflation_immediate_rate_response"]
                .set_index("quarter")
                .loc[quarter, column]
                - baseline.set_index("quarter").loc[quarter, column]
                for column in (
                    "bills_interest_cost_billions",
                    "frns_interest_cost_billions",
                    "notes_interest_cost_billions",
                    "bonds_interest_cost_billions",
                    "tips_inflation_compensation_billions",
                )
            }
            for quarter in ("2027Q1", "2027Q2", "2027Q4", "2028Q4")
        },
    }

    pd.concat(quarterly_outputs, ignore_index=True).to_csv(
        OUTPUT_DIR / "named_scenarios_quarterly_2026-02.csv", index=False
    )
    pd.DataFrame(summaries).to_csv(OUTPUT_DIR / "named_scenarios_summary_2026-02.csv", index=False)
    pd.DataFrame(stress_rows).to_csv(OUTPUT_DIR / "inflation_stress_grid_2026-02.csv", index=False)
    pd.DataFrame(permanent_rows).to_csv(
        OUTPUT_DIR / "persistent_rate_stress_2026-02.csv", index=False
    )
    (OUTPUT_DIR / "experiment_cross_checks_2026-02.json").write_text(
        json.dumps(
            cross_checks,
            indent=2,
            sort_keys=True,
            default=lambda value: value.item() if hasattr(value, "item") else str(value),
        )
        + "\n"
    )
    print(f"Wrote named scenarios, {len(stress_rows)} stress cases, and cross-checks")


if __name__ == "__main__":
    main()
