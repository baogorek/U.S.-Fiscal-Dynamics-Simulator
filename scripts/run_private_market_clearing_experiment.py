"""Turn the private-absorption sensitivity into a financing boundary.

Within each quarter, a common Treasury spread rises until the supplied private
absorption curve can place gross issuance. The run stops when required issuance
exceeds the curve's finite maximum at every supported yield.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from debt_sim.crisis import (
    DebtYieldFeedbackRule,
    InterestIncomeRule,
    PrivateAbsorptionRule,
    PrivateFinancingCapacityError,
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
OUTPUT_DIR = Path("data/processed")
CONFIG_DIR = Path("config/scenarios")
HOLDER_CALIBRATION_PATH = Path("config/calibration/interest_recipient_shares_2026.json")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    bundle = load_baseline_bundle()
    holder_calibration = json.loads(HOLDER_CALIBRATION_PATH.read_text())
    income_rule = InterestIncomeRule(
        domestic_private_share=float(holder_calibration["domestic_private_share"]),
        foreign_share=float(holder_calibration["foreign_share"]),
        federal_reserve_share=float(holder_calibration["federal_reserve_share"]),
        domestic_private_spending_fraction=0.25,
        foreign_domestic_spending_fraction=0.05,
        federal_reserve_spending_fraction=0.0,
    )
    starting = prepare_starting_state(bundle, START)
    reference = build_baseline_scenario(
        bundle,
        start_period=START,
        end_period=END,
    ).quarterly_assumptions
    no_premium = pd.Series(0.0, index=reference.index)
    premium = no_premium.copy()
    premium.iloc[:PREMIUM_QUARTERS] = PREMIUM_BASIS_POINTS
    no_private_spread = no_premium.copy()
    private_spread = no_premium.copy()
    private_spread.iloc[:PRIVATE_CREDIT_SPREAD_QUARTERS] = (
        PRIVATE_CREDIT_SPREAD_BASIS_POINTS
    )

    absorption_rules = {
        "tight": PrivateAbsorptionRule(
            capacity_increase_fraction_per_100_basis_points=0.025,
            maximum_capacity_multiple=1.25,
        ),
        "central": PrivateAbsorptionRule(
            capacity_increase_fraction_per_100_basis_points=0.05,
            maximum_capacity_multiple=1.50,
        ),
        "wide": PrivateAbsorptionRule(
            capacity_increase_fraction_per_100_basis_points=0.10,
            maximum_capacity_multiple=2.00,
        ),
    }
    central_debt_yield_rule = DebtYieldFeedbackRule()
    scenarios = {
        "no_shock_central_capacity": {
            "premium": no_premium,
            "private_spread": no_private_spread,
            "absorption": absorption_rules["central"],
            "debt_yield": None,
        },
        **{
            f"stress_{capacity_name}_capacity": {
                "premium": premium,
                "private_spread": private_spread,
                "absorption": absorption_rule,
                "debt_yield": None,
            }
            for capacity_name, absorption_rule in absorption_rules.items()
        },
        **{
            f"stress_{capacity_name}_capacity_with_debt_yield": {
                "premium": premium,
                "private_spread": private_spread,
                "absorption": absorption_rule,
                "debt_yield": central_debt_yield_rule,
            }
            for capacity_name, absorption_rule in absorption_rules.items()
        },
    }

    policy_rule = PolicyRule(regime=PolicyRegime.PRICE_STABILITY)
    feedback_rule = SequentialFeedbackRule()
    summaries = []
    completed_paths = []
    for name, parameters in scenarios.items():
        try:
            result = run_sequential_crisis_simulation(
                starting.stock,
                reference,
                initial_nominal_gdp_billions_saar=(
                    starting.initial_nominal_gdp_billions_saar
                ),
                initial_real_gdp_billions_chained_saar=(
                    starting.initial_real_gdp_billions_chained_saar
                ),
                policy_rule=policy_rule,
                feedback_rule=feedback_rule,
                debt_yield_feedback_rule=parameters["debt_yield"],
                private_absorption_rule=parameters["absorption"],
                interest_income_rule=income_rule,
                treasury_premium_basis_points=parameters["premium"],
                private_credit_spread_basis_points=parameters["private_spread"],
                issuance_strategy=bundle.issuance_strategy,
                scenario_name=name,
                data_vintage=bundle.cbo_vintage,
            )
        except PrivateFinancingCapacityError as error:
            summaries.append(
                {
                    "scenario": name,
                    "simulation_completed_through_2056q3": False,
                    "private_financing_capacity_failure": True,
                    "first_private_financing_capacity_failure": error.quarter,
                    "failure_reason": error.reason,
                    "required_capacity_multiple_at_failure": (
                        error.required_capacity_multiple
                    ),
                    "maximum_capacity_multiple": error.maximum_capacity_multiple,
                    "required_gross_issuance_billions_at_failure": (
                        error.required_gross_issuance_billions
                    ),
                    "maximum_capacity_billions_at_failure": error.maximum_capacity_billions,
                    "financing_shortfall_billions_at_failure": (
                        error.required_gross_issuance_billions
                        - error.maximum_capacity_billions
                    ),
                }
            )
            continue

        summary = summarize_crisis_path(result, inflation_ceiling=0.04, sustained_quarters=4)
        summary.update(
            {
                "simulation_completed_through_2056q3": True,
                "private_financing_capacity_failure": False,
                "first_private_financing_capacity_failure": "",
                "failure_reason": "",
            }
        )
        summaries.append(summary)
        completed_paths.append(result.quarterly.assign(scenario=name))

    summary_frame = pd.DataFrame(summaries)
    summary_frame.to_csv(
        OUTPUT_DIR / "private_market_clearing_2026_summary.csv",
        index=False,
    )
    if completed_paths:
        pd.concat(completed_paths, ignore_index=True).to_csv(
            OUTPUT_DIR / "private_market_clearing_2026_completed_paths.csv",
            index=False,
        )

    config = {
        "experiment": "Finite private Treasury absorption with an endogenous clearing spread",
        "start": str(START),
        "end": str(END),
        "treasury_premium_basis_points": PREMIUM_BASIS_POINTS,
        "treasury_premium_quarters": PREMIUM_QUARTERS,
        "private_credit_spread_basis_points": PRIVATE_CREDIT_SPREAD_BASIS_POINTS,
        "private_credit_spread_quarters": PRIVATE_CREDIT_SPREAD_QUARTERS,
        "policy_rule": asdict(policy_rule),
        "feedback_rule": asdict(feedback_rule),
        "central_debt_yield_feedback_rule": asdict(central_debt_yield_rule),
        "private_absorption_rules": {
            name: asdict(rule) for name, rule in absorption_rules.items()
        },
        "interest_income_rule": asdict(income_rule),
        "interest_recipient_share_calibration": str(HOLDER_CALIBRATION_PATH),
        "terminal_debt_target_imposed": False,
        "warnings": [
            "The absorption curves are transparent sensitivities, not estimated demand curves.",
            "A financing failure is conditional on the supplied hard capacity multiple.",
            "The common clearing spread is applied to all issuance types.",
            (
                "Dealer intermediation, collateral, foreign-exchange, and Federal Reserve "
                "intervention remain outside the clearing rule."
            ),
            (
                "The simulation stops at the first unplaceable financing quarter and does "
                "not model the aftermath."
            ),
        ],
    }
    (CONFIG_DIR / "private_market_clearing_2026.json").write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n"
    )
    print(summary_frame.to_string(index=False))
    print("Wrote private-market-clearing summary, completed paths, and configuration")


if __name__ == "__main__":
    main()
