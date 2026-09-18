"""Compare fixed issuance, adaptive issuance, and long-end Treasury buybacks.

The experiment applies the same imposed 500-basis-point confidence premium and
two-year recession to every path. It then changes debt-management behavior only.
The repeated buyback path is a counterfactual run-rate experiment, not a claim
that Treasury committed to continue the August 2026 expansion for ten years.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from debt_sim.confidence import ConfidenceShock, apply_confidence_shock
from debt_sim.data import load_baseline_bundle
from debt_sim.model import SimulationResult, run_simulation
from debt_sim.scenarios import build_baseline_scenario, prepare_starting_state
from debt_sim.treasury import (
    TreasuryBuybackInstruction,
    build_adaptive_issuance_strategy_path,
)

START = pd.Period("2026Q4", freq="Q")
END = pd.Period("2036Q3", freq="Q")
CONFIDENCE_PREMIUM_BASIS_POINTS = 500.0
LONG_END_OPERATIONS_PER_BUCKET_PER_QUARTER = 4
MINIMUM_FACE_CAPACITY_PER_OPERATION_BILLIONS = 4.0
FACE_CAPACITY_PER_BUCKET_BILLIONS = (
    LONG_END_OPERATIONS_PER_BUCKET_PER_QUARTER * MINIMUM_FACE_CAPACITY_PER_OPERATION_BILLIONS
)
OUTPUT_DIR = Path("data/processed")
CONFIG_DIR = Path("config/scenarios")


def _long_end_program() -> tuple[TreasuryBuybackInstruction, ...]:
    return (
        TreasuryBuybackInstruction(
            maximum_face_value_billions=FACE_CAPACITY_PER_BUCKET_BILLIONS,
            minimum_remaining_quarters=40,
            maximum_remaining_quarters=79,
        ),
        TreasuryBuybackInstruction(
            maximum_face_value_billions=FACE_CAPACITY_PER_BUCKET_BILLIONS,
            minimum_remaining_quarters=80,
            maximum_remaining_quarters=120,
        ),
    )


def _buyback_plan(
    periods: pd.PeriodIndex,
) -> dict[pd.Period, tuple[TreasuryBuybackInstruction, ...]]:
    return {period: _long_end_program() for period in periods}


def _summary_row(name: str, result: SimulationResult) -> dict[str, float | str]:
    path = result.quarterly
    ending = path.iloc[-1]
    return {
        "scenario": name,
        "terminal_debt_gdp_ratio": float(ending["debt_held_by_public_gdp_ratio"]),
        "cumulative_interest_billions": float(ending["cumulative_modeled_interest_billions"]),
        "cumulative_gross_issuance_billions": float(path["gross_treasury_issuance_billions"].sum()),
        "cumulative_buyback_face_retired_billions": float(
            path["treasury_buyback_face_value_retired_billions"].sum()
        ),
        "cumulative_buyback_cash_spent_billions": float(
            path["treasury_buyback_cash_spent_billions"].sum()
        ),
        "cumulative_buyback_premium_or_discount_billions": float(
            path["treasury_buyback_premium_or_discount_billions"].sum()
        ),
        "cumulative_unfilled_face_capacity_billions": float(
            path["treasury_buyback_unfilled_face_value_limit_billions"].sum()
        ),
        "terminal_bill_share_of_marketable_debt": float(ending["bill_share_of_marketable_debt"]),
        "terminal_weighted_average_remaining_maturity_years": float(
            ending["weighted_average_remaining_maturity_quarters"] / 4.0
        ),
        "terminal_share_maturing_next_four_quarters": float(
            ending["share_marketable_debt_maturing_next_four_quarters"]
        ),
        "maximum_share_maturing_next_four_quarters": float(
            path["share_marketable_debt_maturing_next_four_quarters"].max()
        ),
        "maximum_absolute_debt_identity_residual_billions": float(
            path["debt_identity_residual_billions"].abs().max()
        ),
    }


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
    stressed = apply_confidence_shock(
        reference,
        ConfidenceShock(
            CONFIDENCE_PREMIUM_BASIS_POINTS,
            duration_quarters=len(reference),
        ),
    )
    pressure = pd.Series(CONFIDENCE_PREMIUM_BASIS_POINTS, index=stressed.index)
    adaptive_path = build_adaptive_issuance_strategy_path(
        bundle.issuance_strategy,
        pressure,
    )

    common = {
        "initial_nominal_gdp_billions_saar": (starting.initial_nominal_gdp_billions_saar),
        "initial_real_gdp_billions_chained_saar": (starting.initial_real_gdp_billions_chained_saar),
        "issuance_strategy": bundle.issuance_strategy,
        "data_vintage": bundle.cbo_vintage,
    }
    results = {
        "fixed_issuance": run_simulation(
            starting.stock,
            stressed,
            scenario_name="fixed_issuance",
            **common,
        ),
        "adaptive_issuance": run_simulation(
            starting.stock,
            stressed,
            issuance_strategy_path=adaptive_path,
            scenario_name="adaptive_issuance",
            **common,
        ),
        "adaptive_plus_one_quarter_long_end_capacity": run_simulation(
            starting.stock,
            stressed,
            issuance_strategy_path=adaptive_path,
            treasury_buyback_plan={START: _long_end_program()},
            scenario_name="adaptive_plus_one_quarter_long_end_capacity",
            **common,
        ),
        "adaptive_plus_sustained_long_end_capacity": run_simulation(
            starting.stock,
            stressed,
            issuance_strategy_path=adaptive_path,
            treasury_buyback_plan=_buyback_plan(stressed.index),
            scenario_name="adaptive_plus_sustained_long_end_capacity",
            **common,
        ),
    }

    paths = pd.concat(
        [result.quarterly.assign(scenario=name) for name, result in results.items()],
        ignore_index=True,
    )
    paths.to_csv(OUTPUT_DIR / "treasury_response_2026_paths.csv", index=False)
    summaries = pd.DataFrame([_summary_row(name, result) for name, result in results.items()])
    summaries.to_csv(OUTPUT_DIR / "treasury_response_2026_summary.csv", index=False)

    config = {
        "experiment": "Treasury debt-management responses to an imposed confidence premium",
        "start": str(START),
        "end": str(END),
        "confidence_premium_basis_points": CONFIDENCE_PREMIUM_BASIS_POINTS,
        "adaptive_issuance_rule": {
            "activation_basis_points": 100.0,
            "bill_share_increase_per_additional_100_basis_points": 0.05,
            "maximum_bill_share": 0.50,
        },
        "long_end_buyback_capacity": {
            "minimum_face_capacity_per_operation_billions": (
                MINIMUM_FACE_CAPACITY_PER_OPERATION_BILLIONS
            ),
            "operations_per_bucket_per_quarter": (LONG_END_OPERATIONS_PER_BUCKET_PER_QUARTER),
            "face_capacity_per_bucket_per_quarter_billions": (FACE_CAPACITY_PER_BUCKET_BILLIONS),
            "buckets_remaining_maturity_quarters": [[40, 79], [80, 120]],
            "financing_instrument": "bill",
        },
        "source": "https://home.treasury.gov/news/press-releases/sb0607",
        "frequency_source": "https://home.treasury.gov/news/press-releases/sb0212",
        "scope_warning": (
            "The one-quarter path is a run-rate capacity equivalent, not the still-unreleased "
            "September-November operation schedule. The sustained path is a ten-year "
            "counterfactual, not announced Treasury policy. Announced maximum capacity is not "
            "the same as completed purchases. Yields do not yet respond to issuance or buybacks."
        ),
    }
    (CONFIG_DIR / "treasury_response_2026.json").write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n"
    )
    print(summaries.to_string(index=False))
    print("Wrote Treasury-response paths, summary, and configuration")


if __name__ == "__main__":
    main()
