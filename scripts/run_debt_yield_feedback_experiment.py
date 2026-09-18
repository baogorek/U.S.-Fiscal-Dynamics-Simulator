"""Run a debt-dependent Treasury-yield sensitivity experiment.

The initial 500-basis-point premium remains a ten-year scenario shock. After
each quarter, the scenario's debt/GDP deterioration relative to the parallel
reference path can add to later Treasury yields. The coefficient range maps the
2026 FEDS estimates for longer-run neutral rates and the ten-year term premium
into the model's maturity buckets.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from debt_sim.crisis import (
    DebtYieldFeedbackRule,
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
SOURCE_URL = (
    "https://www.federalreserve.gov/econres/feds/the-causal-effect-of-debt-on-interest-rates.htm"
)
OUTPUT_DIR = Path("data/processed")
CONFIG_DIR = Path("config/scenarios")
HOLDER_CALIBRATION_PATH = Path("config/calibration/interest_recipient_shares_2026.json")
PAPER_PLOT_DATA_PATH = Path("docs/confidence_shock_central_plot_data.csv")


def _income_rule(holder_shares: dict[str, float]) -> InterestIncomeRule:
    return InterestIncomeRule(
        domestic_private_share=holder_shares["domestic_private_share"],
        foreign_share=holder_shares["foreign_share"],
        federal_reserve_share=holder_shares["federal_reserve_share"],
        domestic_private_spending_fraction=0.25,
        foreign_domestic_spending_fraction=0.05,
        federal_reserve_spending_fraction=0.0,
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    bundle = load_baseline_bundle()
    holder_calibration = json.loads(HOLDER_CALIBRATION_PATH.read_text())
    holder_shares = {
        key: float(holder_calibration[key])
        for key in ("domestic_private_share", "foreign_share", "federal_reserve_share")
    }
    starting = prepare_starting_state(bundle, START)
    reference = build_baseline_scenario(
        bundle,
        start_period=START,
        end_period=END,
    ).quarterly_assumptions

    no_premium = pd.Series(0.0, index=reference.index)
    premium = no_premium.copy()
    premium.iloc[:PREMIUM_QUARTERS] = PREMIUM_BASIS_POINTS
    private_spread = no_premium.copy()
    private_spread.iloc[:PRIVATE_CREDIT_SPREAD_QUARTERS] = PRIVATE_CREDIT_SPREAD_BASIS_POINTS
    no_private_spread = no_premium.copy()

    debt_yield_rules: dict[str, DebtYieldFeedbackRule | None] = {
        "no_feedback": None,
        "lower_estimate": DebtYieldFeedbackRule(
            intermediate_basis_points_per_debt_gdp_percentage_point=1.0,
            long_basis_points_per_debt_gdp_percentage_point=3.0,
            tips_real_basis_points_per_debt_gdp_percentage_point=1.0,
        ),
        "central_estimate": DebtYieldFeedbackRule(
            intermediate_basis_points_per_debt_gdp_percentage_point=1.5,
            long_basis_points_per_debt_gdp_percentage_point=4.0,
            tips_real_basis_points_per_debt_gdp_percentage_point=1.5,
        ),
        "upper_estimate": DebtYieldFeedbackRule(
            intermediate_basis_points_per_debt_gdp_percentage_point=2.0,
            long_basis_points_per_debt_gdp_percentage_point=5.0,
            tips_real_basis_points_per_debt_gdp_percentage_point=2.0,
        ),
    }
    scenarios = {
        "no_shock_central_debt_yield_feedback": {
            "premium": no_premium,
            "private_spread": no_private_spread,
            "debt_yield_rule": debt_yield_rules["central_estimate"],
        },
        **{
            f"stress_{name}": {
                "premium": premium,
                "private_spread": private_spread,
                "debt_yield_rule": rule,
            }
            for name, rule in debt_yield_rules.items()
        },
    }

    policy_rule = PolicyRule(regime=PolicyRegime.PRICE_STABILITY)
    feedback_rule = SequentialFeedbackRule()
    income_rule = _income_rule(holder_shares)
    results = {}
    for name, parameters in scenarios.items():
        results[name] = run_sequential_crisis_simulation(
            starting.stock,
            reference,
            initial_nominal_gdp_billions_saar=starting.initial_nominal_gdp_billions_saar,
            initial_real_gdp_billions_chained_saar=(
                starting.initial_real_gdp_billions_chained_saar
            ),
            policy_rule=policy_rule,
            feedback_rule=feedback_rule,
            debt_yield_feedback_rule=parameters["debt_yield_rule"],
            interest_income_rule=income_rule,
            treasury_premium_basis_points=parameters["premium"],
            private_credit_spread_basis_points=parameters["private_spread"],
            issuance_strategy=bundle.issuance_strategy,
            scenario_name=name,
            data_vintage=bundle.cbo_vintage,
        )

    paths = pd.concat(
        [result.quarterly.assign(scenario=name) for name, result in results.items()],
        ignore_index=True,
    )
    paths.to_csv(OUTPUT_DIR / "debt_yield_feedback_2026_paths.csv", index=False)

    central = paths.loc[paths["scenario"].eq("stress_central_estimate")].reset_index(drop=True)
    no_shock = paths.loc[paths["scenario"].eq("no_shock_central_debt_yield_feedback")].reset_index(
        drop=True
    )
    if not central["quarter"].equals(no_shock["quarter"]):
        raise ValueError("Central and no-shock quarters do not align for paper plots")
    plot_data = pd.DataFrame(
        {
            "quarter": central["quarter"].astype(str),
            "plot_year": (central["calendar_year"] + (central["calendar_quarter"] - 1) / 4),
            "treasury_premium_bp": central["treasury_premium_basis_points"],
            "private_credit_spread_bp": central["private_credit_spread_basis_points"],
            "debt_yield_long_bp": central["debt_yield_long_adjustment_basis_points"],
            "inflation_pct": 100 * central["annual_inflation_rate"],
            "reference_inflation_pct": 100 * no_shock["annual_inflation_rate"],
            "policy_rate_pct": 100 * central["policy_rate_proxy"],
            "bill_rate_pct": 100 * central["short_issuance_rate"],
            "note_rate_pct": 100 * central["intermediate_issuance_rate"],
            "long_rate_pct": 100 * central["long_issuance_rate"],
            "debt_gdp_pct": 100 * central["debt_held_by_public_gdp_ratio"],
            "interest_gdp_pct": 100 * central["modeled_interest_gdp_ratio_annualized"],
            "deficit_gdp_pct": 100 * central["modeled_total_deficit_gdp_ratio_annualized"],
            "gross_issuance_trillions": central["gross_treasury_issuance_billions"] / 1000,
            "repriced_share_pct": 100
            * central["share_marketable_debt_repriced_since_scenario_start"],
            "incremental_interest_trillions": central["incremental_cash_interest_billions"] / 1000,
            "domestic_demand_trillions": central["incremental_interest_domestic_demand_billions"]
            / 1000,
            "output_gap_pct": 100 * central["macro_feedback_output_gap"],
            "inflation_gap_pct": 100
            * (central["annual_inflation_rate"] - no_shock["annual_inflation_rate"]),
        }
    )
    plot_data.to_csv(PAPER_PLOT_DATA_PATH, index=False, float_format="%.6f")

    summary = pd.DataFrame(
        [
            summarize_crisis_path(
                result,
                inflation_ceiling=INFLATION_CEILING,
                sustained_quarters=SUSTAINED_BREACH_QUARTERS,
            )
            for result in results.values()
        ]
    )
    summary.to_csv(OUTPUT_DIR / "debt_yield_feedback_2026_summary.csv", index=False)

    config = {
        "experiment": "Lagged debt-ratio feedback into Treasury issuance yields",
        "start": str(START),
        "end": str(END),
        "initial_treasury_premium_basis_points": PREMIUM_BASIS_POINTS,
        "initial_treasury_premium_quarters": PREMIUM_QUARTERS,
        "private_credit_spread_basis_points": PRIVATE_CREDIT_SPREAD_BASIS_POINTS,
        "private_credit_spread_quarters": PRIVATE_CREDIT_SPREAD_QUARTERS,
        "inflation_ceiling": INFLATION_CEILING,
        "sustained_breach_quarters": SUSTAINED_BREACH_QUARTERS,
        "policy_rule": asdict(policy_rule),
        "feedback_rule": asdict(feedback_rule),
        "interest_income_rule": asdict(income_rule),
        "interest_recipient_share_calibration": str(HOLDER_CALIBRATION_PATH),
        "debt_yield_feedback_rules": {
            name: None if rule is None else asdict(rule) for name, rule in debt_yield_rules.items()
        },
        "empirical_source": SOURCE_URL,
        "empirical_range": {
            "longer_run_neutral_rate_basis_points_per_debt_gdp_percentage_point": [
                1.0,
                2.0,
            ],
            "ten_year_term_premium_basis_points_per_debt_gdp_percentage_point": [
                2.0,
                3.0,
            ],
        },
        "terminal_debt_target_imposed": False,
        "warnings": [
            (
                "The source estimates expected debt effects, while this experiment uses a "
                "one-quarter-lagged realized debt-ratio gap."
            ),
            "The maturity mapping is an explicit sensitivity assumption.",
            (
                "The estimated local relationship does not identify crisis nonlinearities "
                "or auction failure."
            ),
            (
                "The short Treasury rate remains tied to the Federal Reserve rule plus the "
                "exogenous stress premium."
            ),
            "Interest-recipient spending fractions remain uncalibrated.",
        ],
    }
    (CONFIG_DIR / "debt_yield_feedback_2026.json").write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n"
    )
    print(summary.to_string(index=False))
    print("Wrote debt-yield feedback paths, summary, configuration, and paper plot data")


if __name__ == "__main__":
    main()
