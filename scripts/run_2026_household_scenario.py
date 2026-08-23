"""Run the 2026 confidence shock and its wage-tax-only household closure."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from debt_sim.closure import (
    ClosureTarget,
    solve_fiscal_adjustment,
    solve_immediate_flow_primary_balance,
)
from debt_sim.confidence import ConfidenceShock, apply_confidence_shock
from debt_sim.data import load_baseline_bundle
from debt_sim.model import run_simulation
from debt_sim.scenarios import build_baseline_scenario, prepare_starting_state

START = pd.Period("2026Q4", freq="Q")
END = pd.Period("2036Q3", freq="Q")
PASSING_THE_BUCK_END = pd.Period("2056Q3", freq="Q")
WAGE_SHARE_OF_GDP = 0.42
OUTPUT_DIR = Path("data/processed")
CONFIG_DIR = Path("config/scenarios")


def _run(bundle, state, assumptions, name):
    return run_simulation(
        state.stock,
        assumptions,
        initial_nominal_gdp_billions_saar=state.initial_nominal_gdp_billions_saar,
        initial_real_gdp_billions_chained_saar=state.initial_real_gdp_billions_chained_saar,
        issuance_strategy=bundle.issuance_strategy,
        scenario_name=name,
        data_vintage=bundle.cbo_vintage,
    )


def _state_after_prefix(bundle, state, assumptions, length):
    if length == 0:
        return (
            state.stock,
            state.initial_nominal_gdp_billions_saar,
            state.initial_real_gdp_billions_chained_saar,
        )
    prefix = _run(bundle, state, assumptions.iloc[:length], "2026_household_prefix")
    ending = prefix.quarterly.iloc[-1]
    return (
        prefix.ending_stock,
        float(ending["nominal_gdp_billions_saar"]),
        float(ending["real_gdp_billions_chained_saar"]),
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    bundle = load_baseline_bundle()
    state = prepare_starting_state(bundle, START)
    baseline = build_baseline_scenario(
        bundle, start_period=START, end_period=END
    ).quarterly_assumptions
    scenarios = {
        "unchanged_baseline": baseline,
        "recession_only": apply_confidence_shock(baseline, ConfidenceShock(0.0)),
        "rate_only_500bp": apply_confidence_shock(
            baseline, ConfidenceShock(500.0, include_recession=False)
        ),
        "fiscal_scare_250bp": apply_confidence_shock(
            baseline, ConfidenceShock(250.0)
        ),
        "serious_crisis_500bp": apply_confidence_shock(
            baseline, ConfidenceShock(500.0)
        ),
        "loss_of_confidence_1000bp": apply_confidence_shock(
            baseline, ConfidenceShock(1_000.0)
        ),
    }
    common = {
        "initial_nominal_gdp_billions_saar": state.initial_nominal_gdp_billions_saar,
        "initial_real_gdp_billions_chained_saar": state.initial_real_gdp_billions_chained_saar,
        "issuance_strategy": bundle.issuance_strategy,
        "data_vintage": bundle.cbo_vintage,
    }
    results = {
        name: _run(bundle, state, assumptions, name)
        for name, assumptions in scenarios.items()
    }
    closures = {
        name: solve_fiscal_adjustment(
            state.stock,
            assumptions,
            target=ClosureTarget.stabilize_at_start(),
            **common,
        )
        for name, assumptions in scenarios.items()
    }
    baseline_ending = results["unchanged_baseline"].quarterly.iloc[-1]
    summary = []
    for name, result in results.items():
        ending = result.quarterly.iloc[-1]
        closure = closures[name]
        summary.append(
            {
                "scenario": name,
                "starting_debt_gdp_ratio": (
                    state.stock.debt_held_by_public_billions
                    / state.initial_nominal_gdp_billions_saar
                ),
                "required_fiscal_adjustment_gdp_share": closure.value,
                "static_all_wage_surcharge_rate": closure.value / WAGE_SHARE_OF_GDP,
                "equivalent_annual_revenue_at_start_billions": (
                    closure.value * state.initial_nominal_gdp_billions_saar
                ),
                "terminal_debt_gdp_ratio": ending["debt_held_by_public_gdp_ratio"],
                "terminal_effective_marketable_rate": ending[
                    "average_effective_marketable_rate_excluding_tips_inflation"
                ],
                "terminal_interest_gdp_ratio": ending[
                    "modeled_interest_gdp_ratio_annualized"
                ],
                "terminal_total_deficit_gdp_ratio": ending[
                    "modeled_total_deficit_gdp_ratio_annualized"
                ],
                "terminal_repriced_share": ending[
                    "share_marketable_debt_repriced_since_scenario_start"
                ],
                "cumulative_additional_interest_vs_baseline_billions": (
                    ending["cumulative_modeled_interest_billions"]
                    - baseline_ending["cumulative_modeled_interest_billions"]
                ),
            }
        )
    pd.DataFrame(summary).to_csv(
        OUTPUT_DIR / "confidence_shock_household_2026_summary.csv", index=False
    )

    serious = results["serious_crisis_500bp"].quarterly.assign(
        scenario="no_fiscal_response"
    )
    closure_path = closures["serious_crisis_500bp"].result.quarterly.assign(
        scenario="wage_tax_only_closure"
    )
    pd.concat([serious, closure_path], ignore_index=True).to_csv(
        OUTPUT_DIR / "confidence_shock_household_2026_paths.csv", index=False
    )

    delayed_rows = []
    serious_assumptions = scenarios["serious_crisis_500bp"]
    for period in (
        pd.Period("2026Q4", freq="Q"),
        pd.Period("2028Q4", freq="Q"),
        pd.Period("2030Q4", freq="Q"),
        pd.Period("2032Q4", freq="Q"),
        pd.Period("2034Q4", freq="Q"),
    ):
        offset = serious_assumptions.index.get_loc(period)
        stock, nominal_gdp, real_gdp = _state_after_prefix(
            bundle, state, serious_assumptions, offset
        )
        remaining = serious_assumptions.iloc[offset:]
        solution = solve_fiscal_adjustment(
            stock,
            remaining,
            initial_nominal_gdp_billions_saar=nominal_gdp,
            initial_real_gdp_billions_chained_saar=real_gdp,
            issuance_strategy=bundle.issuance_strategy,
            target=ClosureTarget.stabilize_at_start(),
            data_vintage=bundle.cbo_vintage,
        )
        delayed_rows.append(
            {
                "closure_start": str(period),
                "closure_end": str(END),
                "remaining_horizon_quarters": len(remaining),
                "starting_debt_gdp_ratio": stock.debt_held_by_public_billions / nominal_gdp,
                "required_fiscal_adjustment_gdp_share": solution.value,
                "static_all_wage_surcharge_rate": solution.value / WAGE_SHARE_OF_GDP,
                "annual_tax_on_80000_wages": (
                    solution.value / WAGE_SHARE_OF_GDP * 80_000
                ),
            }
        )
    pd.DataFrame(delayed_rows).to_csv(
        OUTPUT_DIR / "confidence_shock_household_2026_delayed.csv", index=False
    )

    long_baseline_assumptions = build_baseline_scenario(
        bundle,
        start_period=START,
        end_period=PASSING_THE_BUCK_END,
    ).quarterly_assumptions
    passing_the_buck_assumptions = apply_confidence_shock(
        long_baseline_assumptions,
        ConfidenceShock(
            500.0,
            duration_quarters=len(long_baseline_assumptions),
        ),
    )
    long_results = {
        "long_term_baseline": _run(
            bundle,
            state,
            long_baseline_assumptions,
            "long_term_baseline",
        ),
        "passing_the_buck_500bp": _run(
            bundle,
            state,
            passing_the_buck_assumptions,
            "passing_the_buck_500bp",
        ),
    }
    long_paths = pd.concat(
        [
            result.quarterly.assign(scenario=name)
            for name, result in long_results.items()
        ],
        ignore_index=True,
    )
    long_paths.to_csv(
        OUTPUT_DIR / "confidence_shock_household_2026_passing_the_buck_paths.csv",
        index=False,
    )

    checkpoint_periods = {
        "2026Q4",
        "2030Q4",
        "2036Q3",
        "2040Q4",
        "2046Q4",
        "2050Q4",
        "2055Q4",
        "2056Q3",
    }
    checkpoint_rows = []
    for name, result in long_results.items():
        for _, row in result.quarterly.iterrows():
            if row["quarter"] not in checkpoint_periods:
                continue
            checkpoint_rows.append(
                {
                    "scenario": name,
                    "quarter": row["quarter"],
                    "debt_held_by_public_trillions": (
                        row["debt_held_by_public_billions"] / 1_000.0
                    ),
                    "debt_gdp_ratio": row["debt_held_by_public_gdp_ratio"],
                    "effective_marketable_rate": row[
                        "average_effective_marketable_rate_excluding_tips_inflation"
                    ],
                    "interest_gdp_ratio": row[
                        "modeled_interest_gdp_ratio_annualized"
                    ],
                    "primary_deficit_gdp_ratio": row[
                        "primary_deficit_gdp_ratio_annualized"
                    ],
                    "total_deficit_gdp_ratio": row[
                        "modeled_total_deficit_gdp_ratio_annualized"
                    ],
                    "quarterly_net_new_borrowing_trillions": (
                        row["genuinely_new_borrowing_billions"] / 1_000.0
                    ),
                    "quarterly_gross_issuance_trillions": (
                        row["gross_treasury_issuance_billions"] / 1_000.0
                    ),
                    "cumulative_interest_trillions": (
                        row["cumulative_modeled_interest_billions"] / 1_000.0
                    ),
                }
            )
    pd.DataFrame(checkpoint_rows).to_csv(
        OUTPUT_DIR / "confidence_shock_household_2026_passing_the_buck_checkpoints.csv",
        index=False,
    )

    terminal_stock, terminal_nominal_gdp, terminal_real_gdp = _state_after_prefix(
        bundle,
        state,
        passing_the_buck_assumptions,
        len(passing_the_buck_assumptions) - 1,
    )
    terminal_flow_solution = solve_immediate_flow_primary_balance(
        terminal_stock,
        passing_the_buck_assumptions.iloc[-1:],
        initial_nominal_gdp_billions_saar=terminal_nominal_gdp,
        initial_real_gdp_billions_chained_saar=terminal_real_gdp,
        issuance_strategy=bundle.issuance_strategy,
        data_vintage=bundle.cbo_vintage,
    )
    if terminal_flow_solution.value is None:
        raise RuntimeError("2056 immediate-flow diagnostic unexpectedly had no solution")
    terminal_baseline_row = terminal_flow_solution.baseline_result.quarterly.iloc[-1]
    required_primary_deficit_share = terminal_flow_solution.value
    baseline_primary_deficit_share = float(
        terminal_baseline_row["primary_deficit_gdp_ratio_annualized"]
    )
    required_primary_improvement = (
        baseline_primary_deficit_share - required_primary_deficit_share
    )
    pd.DataFrame(
        [
            {
                "scenario": "passing_the_buck_500bp",
                "diagnostic_quarter": str(PASSING_THE_BUCK_END),
                "starting_debt_gdp_ratio": (
                    terminal_stock.debt_held_by_public_billions
                    / terminal_nominal_gdp
                ),
                "baseline_primary_deficit_gdp_share": baseline_primary_deficit_share,
                "required_primary_deficit_gdp_share": required_primary_deficit_share,
                "required_primary_surplus_gdp_share": -required_primary_deficit_share,
                "required_primary_balance_improvement_gdp_share": (
                    required_primary_improvement
                ),
                "illustrative_all_wage_surcharge_rate_at_42pct_base": (
                    required_primary_improvement / WAGE_SHARE_OF_GDP
                ),
            }
        ]
    ).to_csv(
        OUTPUT_DIR / "confidence_shock_household_2026_passing_the_buck_endgame.csv",
        index=False,
    )

    config = {
        "experiment": "2026Q4 confidence shock with wage-tax-only fiscal closure",
        "model_version": "0.2",
        "start": str(START),
        "end": str(END),
        "confidence_premium_basis_points": 500,
        "premium_duration_quarters": 40,
        "recession": {
            "first_four_quarters_real_growth_annualized": -0.02,
            "next_four_quarters_real_growth_annualized": 0.0,
            "thereafter": "baseline without level catch-up",
        },
        "primary_deficits": "unchanged nominal baseline before solved adjustment",
        "inflation": "unchanged baseline",
        "selected_closure": "permanent employee-side surcharge on all wages and salaries",
        "wages_and_salaries_gdp_share": WAGE_SHARE_OF_GDP,
        "tax_translation": (
            "static required primary-balance improvement divided by the CBO 2026-2036 "
            "wages-and-salaries share; no behavioral or incidence adjustment"
        ),
        "passing_the_buck_scenario": {
            "end": str(PASSING_THE_BUCK_END),
            "confidence_premium_basis_points": 500,
            "premium_duration_quarters": len(long_baseline_assumptions),
            "primary_deficits": "unchanged CBO long-term path",
            "financing_rule": (
                "every modeled primary deficit, cash interest cost, and maturing "
                "principal is financed through the existing Treasury cohort engine"
            ),
            "interpretation_of_indefinitely": (
                "through the final supported CBO quarter; no extrapolation beyond 2056Q3"
            ),
            "terminal_immediate_flow_diagnostic": {
                "required_primary_deficit_gdp_share": required_primary_deficit_share,
                "required_primary_balance_improvement_gdp_share": (
                    required_primary_improvement
                ),
            },
        },
    }
    (CONFIG_DIR / "confidence_shock_2026_household.json").write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n"
    )
    print("Wrote the 2026 household confidence-shock scenario outputs")


if __name__ == "__main__":
    main()
