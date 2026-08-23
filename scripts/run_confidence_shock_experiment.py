"""Run the pinned 2045 bond-market confidence-premium stress experiment."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from debt_sim.closure import ClosureTarget, solve_fiscal_adjustment
from debt_sim.confidence import ConfidenceShock, apply_confidence_shock
from debt_sim.data import load_baseline_bundle
from debt_sim.model import SimulationResult, run_simulation
from debt_sim.scenarios import build_baseline_scenario, prepare_starting_state

START = pd.Period("2045Q1", freq="Q")
END = pd.Period("2054Q4", freq="Q")
OUTPUT_DIR = Path("data/processed")
CONFIG_DIR = Path("config/scenarios")

SCENARIOS = {
    "unchanged_baseline": None,
    "recession_only": ConfidenceShock(0.0),
    "rate_only_500bp": ConfidenceShock(500.0, include_recession=False),
    "fiscal_scare_250bp": ConfidenceShock(250.0),
    "serious_crisis_500bp": ConfidenceShock(500.0),
    "loss_of_confidence_1000bp": ConfidenceShock(1_000.0),
}


def _run(bundle, state, assumptions: pd.DataFrame, name: str) -> SimulationResult:
    return run_simulation(
        state.stock,
        assumptions,
        initial_nominal_gdp_billions_saar=state.initial_nominal_gdp_billions_saar,
        initial_real_gdp_billions_chained_saar=state.initial_real_gdp_billions_chained_saar,
        issuance_strategy=bundle.issuance_strategy,
        scenario_name=name,
        data_vintage=bundle.cbo_vintage,
    )


def _state_after_prefix(bundle, initial_state, assumptions: pd.DataFrame, length: int):
    if length == 0:
        return (
            initial_state.stock,
            initial_state.initial_nominal_gdp_billions_saar,
            initial_state.initial_real_gdp_billions_chained_saar,
        )
    prefix = _run(bundle, initial_state, assumptions.iloc[:length], "confidence_shock_prefix")
    ending = prefix.quarterly.iloc[-1]
    return (
        prefix.ending_stock,
        float(ending["nominal_gdp_billions_saar"]),
        float(ending["real_gdp_billions_chained_saar"]),
    )


def _solve_delayed_adjustments(bundle, state, assumptions_by_name):
    """Resolve closure if fiscal action waits until each annual start.

    Every point uses the debt ratio inherited on that date as its target and
    the fixed 2054Q4 endpoint. The shrinking horizon is an intentional measure
    of delay, and is recorded with every row.
    """

    rows = []
    for name, assumptions in assumptions_by_name.items():
        for year in range(2045, 2054):
            period = pd.Period(f"{year}Q1", freq="Q")
            offset = assumptions.index.get_loc(period)
            stock, nominal_gdp, real_gdp = _state_after_prefix(
                bundle, state, assumptions, offset
            )
            remaining = assumptions.iloc[offset:]
            solution = solve_fiscal_adjustment(
                stock,
                remaining,
                initial_nominal_gdp_billions_saar=nominal_gdp,
                initial_real_gdp_billions_chained_saar=real_gdp,
                issuance_strategy=bundle.issuance_strategy,
                target=ClosureTarget.stabilize_at_start(),
                bounds=(0.0, 0.20),
                data_vintage=bundle.cbo_vintage,
            )
            rows.append(
                {
                    "scenario": name,
                    "closure_start": str(period),
                    "closure_end": str(END),
                    "remaining_horizon_quarters": len(remaining),
                    "starting_debt_gdp_ratio": (
                        stock.debt_held_by_public_billions / nominal_gdp
                    ),
                    "required_fiscal_adjustment_gdp_share": solution.value,
                    "status": solution.status,
                    "boundary_terminal_debt_gdp_ratio": (
                        solution.boundary_evaluation.terminal_debt_gdp_ratio
                    ),
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    bundle = load_baseline_bundle()
    state = prepare_starting_state(bundle, START)
    baseline_assumptions = build_baseline_scenario(
        bundle, start_period=START, end_period=END
    ).quarterly_assumptions
    assumptions_by_name = {
        name: (
            baseline_assumptions.copy()
            if shock is None
            else apply_confidence_shock(baseline_assumptions, shock)
        )
        for name, shock in SCENARIOS.items()
    }
    results = {
        name: _run(bundle, state, assumptions, name)
        for name, assumptions in assumptions_by_name.items()
    }

    history_scenario = build_baseline_scenario(bundle, end_period=END)
    history = run_simulation(
        bundle.initial_stock,
        history_scenario.quarterly_assumptions,
        initial_nominal_gdp_billions_saar=bundle.initial_nominal_gdp_billions_saar,
        initial_real_gdp_billions_chained_saar=bundle.initial_real_gdp_billions_chained_saar,
        issuance_strategy=bundle.issuance_strategy,
        scenario_name="unchanged_baseline",
        data_vintage=bundle.cbo_vintage,
    ).quarterly
    pre_shock = history[history["quarter"].map(lambda value: pd.Period(value, freq="Q") < START)]
    paths = []
    for name, result in results.items():
        prefix = pre_shock.assign(scenario=name)
        post = result.quarterly.assign(scenario=name)
        paths.append(pd.concat([prefix, post], ignore_index=True))
    path_table = pd.concat(paths, ignore_index=True)
    premiums = {
        name: 0.0 if shock is None else shock.premium_basis_points
        for name, shock in SCENARIOS.items()
    }
    recession_flags = {
        name: False if shock is None else shock.include_recession
        for name, shock in SCENARIOS.items()
    }
    path_table["confidence_premium_basis_points"] = path_table["scenario"].map(premiums)
    path_table["includes_recession"] = path_table["scenario"].map(recession_flags)
    path_table.to_csv(
        OUTPUT_DIR / "confidence_shock_paths_2045_2026-02-25.csv", index=False
    )

    delayed = _solve_delayed_adjustments(bundle, state, assumptions_by_name)
    delayed.to_csv(
        OUTPUT_DIR / "confidence_shock_delayed_fiscal_adjustment_2045_2026-02-25.csv",
        index=False,
    )

    baseline_result = results["unchanged_baseline"]
    baseline_ending = baseline_result.quarterly.iloc[-1]
    summary = []
    for name, result in results.items():
        ending = result.quarterly.iloc[-1]
        initial_closure = delayed[
            delayed["scenario"].eq(name) & delayed["closure_start"].eq("2045Q1")
        ].iloc[0]
        summary.append(
            {
                "scenario": name,
                "confidence_premium_basis_points": path_table.loc[
                    path_table["scenario"].eq(name), "confidence_premium_basis_points"
                ].iloc[0],
                "includes_recession": recession_flags[name],
                "starting_debt_gdp_ratio": (
                    state.stock.debt_held_by_public_billions
                    / state.initial_nominal_gdp_billions_saar
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
                "required_fiscal_adjustment_if_immediate_gdp_share": initial_closure[
                    "required_fiscal_adjustment_gdp_share"
                ],
                "equivalent_adjustment_at_pinned_2025_gdp_billions": (
                    initial_closure["required_fiscal_adjustment_gdp_share"]
                    * bundle.initial_nominal_gdp_billions_saar
                ),
            }
        )
    pd.DataFrame(summary).to_csv(
        OUTPUT_DIR / "confidence_shock_summary_2045_2026-02-25.csv", index=False
    )

    config = {
        "experiment": "2045 bond-market confidence-premium stress",
        "model_version": "0.2",
        "closure_start": str(START),
        "simulation_end": str(END),
        "starting_debt_gdp_ratio": (
            state.stock.debt_held_by_public_billions
            / state.initial_nominal_gdp_billions_saar
        ),
        "confidence_premiums_basis_points": [250, 500, 1000],
        "premium_duration_quarters": 40,
        "premium_scope": (
            "new bill, note, bond, and TIPS issuance; FRNs reset from the shocked bill rate"
        ),
        "real_growth_path": {
            "2045Q1_to_2045Q4_annualized": -0.02,
            "2046Q1_to_2046Q4_annualized": 0.0,
            "thereafter": "CBO baseline without level catch-up",
        },
        "primary_deficit_path": "unchanged nominal baseline",
        "inflation_path": "unchanged baseline",
        "other_financing_path": "unchanged baseline",
        "default_or_haircut": "none",
        "closure_definition": (
            "terminal debt/GDP no higher than the ratio inherited when fiscal action begins; "
            "final-four-quarter increase no more than 0.1 percentage point"
        ),
        "delayed_closure_endpoint": str(END),
        "warning": "Exogenous stress scenario, not a forecast or estimated crisis probability.",
    }
    (CONFIG_DIR / "confidence_shock_2045.json").write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n"
    )
    print("Wrote confidence-shock paths, delayed fiscal closures, summary, and config")


if __name__ == "__main__":
    main()
