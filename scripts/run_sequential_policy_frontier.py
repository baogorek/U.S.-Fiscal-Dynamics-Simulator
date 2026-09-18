"""Map finite-horizon inflation ceilings across Fed and interest-spending assumptions."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from debt_sim.crisis import (
    InterestIncomeRule,
    SequentialFeedbackRule,
    run_sequential_crisis_simulation,
    summarize_crisis_path,
)
from debt_sim.data import load_baseline_bundle
from debt_sim.policy import PolicyRegime, PolicyRule
from debt_sim.scenarios import build_baseline_scenario, prepare_starting_state

START = pd.Period("2026Q4", freq="Q")
END = pd.Period("2056Q3", freq="Q")
PREMIUM_BASIS_POINTS = 500.0
PREMIUM_QUARTERS = 40
PRIVATE_CREDIT_SPREAD_BASIS_POINTS = 200.0
PRIVATE_CREDIT_SPREAD_QUARTERS = 8
INFLATION_CEILING = 0.04
SUSTAINED_BREACH_QUARTERS = 4
CENTRAL_BENCHMARK_INTEREST_DEMAND_FRACTION = 0.15668784534991487
INTEREST_DEMAND_FRACTIONS = (
    0.0,
    0.05,
    0.06,
    0.07,
    0.08,
    0.09,
    0.095,
    0.10,
    0.15,
    CENTRAL_BENCHMARK_INTEREST_DEMAND_FRACTION,
    0.20,
    0.25,
    0.325,
    0.40,
)
FED_INFLATION_RESPONSES = (0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 12.0)
SAVED_PATH_DEMAND_FRACTIONS = (
    0.05,
    0.08,
    0.09,
    0.095,
    0.10,
    CENTRAL_BENCHMARK_INTEREST_DEMAND_FRACTION,
)
OUTPUT_DIR = Path("data/processed")
CONFIG_DIR = Path("config/scenarios")
HOLDER_CALIBRATION_PATH = Path("config/calibration/interest_recipient_shares_2026.json")


def _income_rule(domestic_demand_fraction: float) -> InterestIncomeRule:
    """Collapse recipient allocation into one effective spending parameter."""

    return InterestIncomeRule(
        domestic_private_share=1.0,
        foreign_share=0.0,
        federal_reserve_share=0.0,
        domestic_private_spending_fraction=domestic_demand_fraction,
        foreign_domestic_spending_fraction=0.0,
        federal_reserve_spending_fraction=0.0,
    )


def _select_defense(frontier: pd.DataFrame) -> pd.DataFrame:
    records = []
    for demand_fraction, group in frontier.groupby(
        "interest_income_domestic_demand_fraction",
        sort=True,
    ):
        completed = group.loc[group["simulation_completed"]]
        strict = completed.loc[
            completed["strict_ceiling_defended"] & ~completed["rate_bound_ever_binding"]
        ]
        strict_with_nonincreasing_inflation_pressure = strict.loc[
            strict["terminal_inflation_pressure_nonincreasing"]
        ]
        durable = strict_with_nonincreasing_inflation_pressure.loc[
            strict_with_nonincreasing_inflation_pressure["terminal_debt_gdp_nonincreasing"]
        ]
        sustained = completed.loc[
            completed["sustained_ceiling_defended"] & ~completed["rate_bound_ever_binding"]
        ]
        if not strict.empty:
            selected = strict.sort_values(["peak_policy_rate", "fed_inflation_response"]).iloc[0]
            selection = "strict_ceiling_defended"
        elif not sustained.empty:
            selected = sustained.sort_values(["peak_inflation_rate", "peak_policy_rate"]).iloc[0]
            selection = "only_sustained_breach_avoided"
        elif not completed.empty:
            selected = completed.sort_values(["peak_inflation_rate", "peak_policy_rate"]).iloc[0]
            selection = "no_defense_found"
        else:
            records.append(
                {
                    "interest_income_domestic_demand_fraction": demand_fraction,
                    "selection": "all_grid_points_hit_model_boundaries",
                    "strict_defense_available": False,
                    "sustained_defense_available": False,
                    "failed_grid_points": len(group),
                }
            )
            continue
        records.append(
            {
                "interest_income_domestic_demand_fraction": demand_fraction,
                "selection": selection,
                "strict_defense_available": not strict.empty,
                "sustained_defense_available": not sustained.empty,
                "strict_defense_with_nonincreasing_inflation_pressure_available": (
                    not strict_with_nonincreasing_inflation_pressure.empty
                ),
                "strict_defense_with_both_terminal_trends_nonincreasing_available": (
                    not durable.empty
                ),
                "failed_grid_points": int((~group["simulation_completed"]).sum()),
                "selected_fed_inflation_response": selected["fed_inflation_response"],
                "selected_peak_policy_rate": selected["peak_policy_rate"],
                "selected_peak_inflation_rate": selected["peak_inflation_rate"],
                "selected_terminal_inflation_rate": selected["terminal_inflation_rate"],
                "selected_terminal_inflation_change": selected[
                    "terminal_four_quarter_inflation_change"
                ],
                "selected_terminal_inflation_deviation_change": selected[
                    "terminal_four_quarter_inflation_deviation_change"
                ],
                "selected_terminal_inflation_pressure_nonincreasing": selected[
                    "terminal_inflation_pressure_nonincreasing"
                ],
                "selected_terminal_debt_gdp_ratio": selected["terminal_debt_gdp_ratio"],
                "selected_terminal_debt_gdp_nonincreasing": selected[
                    "terminal_debt_gdp_nonincreasing"
                ],
                "selected_first_ceiling_breach": selected["first_inflation_ceiling_breach"],
                "selected_first_sustained_breach": selected[
                    "first_sustained_inflation_ceiling_breach"
                ],
            }
        )
    return pd.DataFrame(records)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    bundle = load_baseline_bundle()
    starting = prepare_starting_state(bundle, START)
    reference = build_baseline_scenario(
        bundle,
        start_period=START,
        end_period=END,
    ).quarterly_assumptions
    premium = pd.Series(0.0, index=reference.index)
    premium.iloc[:PREMIUM_QUARTERS] = PREMIUM_BASIS_POINTS
    private_spread = pd.Series(0.0, index=reference.index)
    private_spread.iloc[:PRIVATE_CREDIT_SPREAD_QUARTERS] = PRIVATE_CREDIT_SPREAD_BASIS_POINTS
    feedback_rule = SequentialFeedbackRule()

    output_path = OUTPUT_DIR / "sequential_policy_frontier_2026.csv"
    if output_path.exists():
        prior_frontier = pd.read_csv(output_path)
        allowed_keys = {
            (round(demand_fraction, 6), round(inflation_response, 6))
            for demand_fraction in INTEREST_DEMAND_FRACTIONS
            for inflation_response in FED_INFLATION_RESPONSES
        }
        prior_frontier = prior_frontier.loc[
            prior_frontier.apply(
                lambda row: (
                    round(float(row["interest_income_domestic_demand_fraction"]), 6),
                    round(float(row["fed_inflation_response"]), 6),
                )
                in allowed_keys,
                axis=1,
            )
        ]
        records = prior_frontier.to_dict("records")
        completed_keys = {
            (
                round(float(row["interest_income_domestic_demand_fraction"]), 6),
                round(float(row["fed_inflation_response"]), 6),
            )
            for row in records
        }
    else:
        records = []
        completed_keys = set()
    for demand_fraction in INTEREST_DEMAND_FRACTIONS:
        income_rule = _income_rule(demand_fraction)
        for inflation_response in FED_INFLATION_RESPONSES:
            key = (round(demand_fraction, 6), round(inflation_response, 6))
            if key in completed_keys:
                continue
            policy_rule = PolicyRule(
                regime=PolicyRegime.PRICE_STABILITY,
                inflation_response=inflation_response,
            )
            name = f"demand_{demand_fraction:.4f}_phi_{inflation_response:.1f}"
            try:
                result = run_sequential_crisis_simulation(
                    starting.stock,
                    reference,
                    initial_nominal_gdp_billions_saar=starting.initial_nominal_gdp_billions_saar,
                    initial_real_gdp_billions_chained_saar=(
                        starting.initial_real_gdp_billions_chained_saar
                    ),
                    policy_rule=policy_rule,
                    feedback_rule=feedback_rule,
                    interest_income_rule=income_rule,
                    treasury_premium_basis_points=premium,
                    private_credit_spread_basis_points=private_spread,
                    issuance_strategy=bundle.issuance_strategy,
                    scenario_name=name,
                    data_vintage=bundle.cbo_vintage,
                )
            except ValueError as error:
                records.append(
                    {
                        "scenario": name,
                        "interest_income_domestic_demand_fraction": demand_fraction,
                        "fed_inflation_response": inflation_response,
                        "simulation_completed": False,
                        "simulation_error": str(error),
                        "strict_ceiling_defended": False,
                        "sustained_ceiling_defended": False,
                        "inflation_ceiling_breached": False,
                        "inflation_ceiling_breached_sustained": False,
                        "rate_bound_ever_binding": False,
                    }
                )
                print(f"Boundary failure for {name}: {error}", flush=True)
                continue
            summary = summarize_crisis_path(
                result,
                inflation_ceiling=INFLATION_CEILING,
                sustained_quarters=SUSTAINED_BREACH_QUARTERS,
            )
            summary.update(
                {
                    "interest_income_domestic_demand_fraction": demand_fraction,
                    "fed_inflation_response": inflation_response,
                    "simulation_completed": True,
                    "simulation_error": "",
                    "strict_ceiling_defended": not summary["inflation_ceiling_breached"],
                    "sustained_ceiling_defended": not summary[
                        "inflation_ceiling_breached_sustained"
                    ],
                    "maximum_absolute_debt_identity_residual_billions": float(
                        result.quarterly["debt_identity_residual_billions"].abs().max()
                    ),
                }
            )
            records.append(summary)

    frontier = pd.DataFrame(records).sort_values(
        ["interest_income_domestic_demand_fraction", "fed_inflation_response"]
    )
    terminal_lag = min(4, len(reference) - 1)
    reference_terminal_inflation_change = float(
        reference.iloc[-1]["annual_inflation_rate"]
        - reference.iloc[-1 - terminal_lag]["annual_inflation_rate"]
    )
    frontier["terminal_four_quarter_inflation_deviation_change"] = (
        frontier["terminal_four_quarter_inflation_change"] - reference_terminal_inflation_change
    )
    frontier["terminal_inflation_pressure_nonincreasing"] = (
        frontier["terminal_four_quarter_inflation_deviation_change"] <= 0.0
    )
    frontier["terminal_debt_gdp_nonincreasing"] = (
        frontier["terminal_four_quarter_debt_gdp_change"] <= 0.0
    )
    frontier.to_csv(output_path, index=False)
    selected = _select_defense(frontier)
    selected.to_csv(
        OUTPUT_DIR / "sequential_policy_frontier_2026_selected.csv",
        index=False,
    )
    selected_paths = []
    for demand_fraction in SAVED_PATH_DEMAND_FRACTIONS:
        selection = selected.loc[
            selected["interest_income_domestic_demand_fraction"]
            .sub(demand_fraction)
            .abs()
            .lt(1e-9)
        ].iloc[0]
        inflation_response = float(selection["selected_fed_inflation_response"])
        name = f"selected_demand_{demand_fraction:.4f}_phi_{inflation_response:.1f}"
        result = run_sequential_crisis_simulation(
            starting.stock,
            reference,
            initial_nominal_gdp_billions_saar=starting.initial_nominal_gdp_billions_saar,
            initial_real_gdp_billions_chained_saar=(
                starting.initial_real_gdp_billions_chained_saar
            ),
            policy_rule=PolicyRule(
                regime=PolicyRegime.PRICE_STABILITY,
                inflation_response=inflation_response,
            ),
            feedback_rule=feedback_rule,
            interest_income_rule=_income_rule(demand_fraction),
            treasury_premium_basis_points=premium,
            private_credit_spread_basis_points=private_spread,
            issuance_strategy=bundle.issuance_strategy,
            scenario_name=name,
            data_vintage=bundle.cbo_vintage,
        )
        selected_paths.append(
            result.quarterly.assign(
                interest_income_domestic_demand_fraction=demand_fraction,
                fed_inflation_response=inflation_response,
                frontier_selection=selection["selection"],
            )
        )
    pd.concat(selected_paths, ignore_index=True).to_csv(
        OUTPUT_DIR / "sequential_policy_frontier_2026_selected_paths.csv",
        index=False,
    )

    config = {
        "experiment": "Finite-horizon inflation ceiling across Fed and interest responses",
        "start": str(START),
        "end": str(END),
        "treasury_premium_basis_points": PREMIUM_BASIS_POINTS,
        "treasury_premium_quarters": PREMIUM_QUARTERS,
        "private_credit_spread_basis_points": PRIVATE_CREDIT_SPREAD_BASIS_POINTS,
        "private_credit_spread_quarters": PRIVATE_CREDIT_SPREAD_QUARTERS,
        "inflation_ceiling": INFLATION_CEILING,
        "sustained_breach_quarters": SUSTAINED_BREACH_QUARTERS,
        "interest_income_domestic_demand_fractions": INTEREST_DEMAND_FRACTIONS,
        "central_benchmark_interest_demand_fraction": (
            CENTRAL_BENCHMARK_INTEREST_DEMAND_FRACTION
        ),
        "interest_recipient_share_calibration": str(HOLDER_CALIBRATION_PATH),
        "central_benchmark_spending_assumptions": {
            "domestic_private_spending_fraction": 0.25,
            "foreign_domestic_spending_fraction": 0.05,
            "federal_reserve_spending_fraction": 0.0,
        },
        "fed_inflation_responses": FED_INFLATION_RESPONSES,
        "saved_path_demand_fractions": SAVED_PATH_DEMAND_FRACTIONS,
        "feedback_rule": asdict(feedback_rule),
        "terminal_debt_target_imposed": False,
        "warnings": [
            "The grid is a conditional sensitivity frontier, not an estimated probability.",
            "Interest spending fractions and Fed response coefficients are uncalibrated.",
            "Strict defense means the simulated inflation path never exceeds four percent.",
            "A strict defense applies only through 2056Q3; terminal trends are reported.",
            "No Treasury investor-demand or auction-clearing condition is imposed.",
            "The selected row minimizes peak policy rates only within the finite saved grid.",
        ],
    }
    (CONFIG_DIR / "sequential_policy_frontier_2026.json").write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n"
    )
    print(selected.to_string(index=False))
    print("Wrote sequential policy frontier, selections, and configuration")


if __name__ == "__main__":
    main()
