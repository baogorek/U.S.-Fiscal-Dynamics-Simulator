"""Construct a conditional recovery after the central 2039 financing boundary.

The causal sequential engine carries the 2026 Treasury shock through 2039Q2,
the last quarter before the central financing-capacity curve fails.
The recovery window then makes the political regime change explicit: inflation,
real growth, and new-issuance rates follow a stated normalization path, while
the cohort closure solver finds the permanent primary-balance improvement that
returns debt/GDP to its settlement-date level and leaves it falling in 2056.

The post-settlement macro and yield paths are scenario assumptions. The solved
fiscal requirement and all Treasury refinancing results come from the cohort
engine; they are not forecasts of legislation or private behavior.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

from debt_sim.closure import ClosureTarget, solve_fiscal_adjustment
from debt_sim.crisis import (
    DebtYieldFeedbackRule,
    InterestIncomeRule,
    PrivateAbsorptionRule,
    SequentialFeedbackRule,
    run_sequential_crisis_simulation,
)
from debt_sim.data import load_baseline_bundle
from debt_sim.policy import PolicyRegime, PolicyRule
from debt_sim.scenarios import build_baseline_scenario, prepare_starting_state

SHOCK_START = pd.Period("2026Q4", freq="Q")
LAST_PRE_SETTLEMENT_QUARTER = pd.Period("2039Q2", freq="Q")
RECOVERY_START = pd.Period("2039Q3", freq="Q")
RECOVERY_END = pd.Period("2056Q3", freq="Q")
PREMIUM_BASIS_POINTS = 500.0
PREMIUM_QUARTERS = 40
PRIVATE_CREDIT_SPREAD_BASIS_POINTS = 200.0
PRIVATE_CREDIT_SPREAD_QUARTERS = 8
FISCAL_PHASE_IN_QUARTERS = 16
OUTPUT_DIR = Path("data/processed")
CONFIG_DIR = Path("config/scenarios")
PAPER_PLOT_DATA_PATH = Path("docs/recovery_settlement_plot_data.csv")
HOLDER_CALIBRATION_PATH = Path(
    "config/calibration/interest_recipient_shares_2026.json"
)


def _piecewise_path(length: int, points: list[tuple[int, float]]) -> np.ndarray:
    """Linearly interpolate a fully specified annual-rate path."""

    positions = np.arange(length)
    point_positions = np.array([position for position, _ in points], dtype=float)
    point_values = np.array([value for _, value in points], dtype=float)
    return np.interp(positions, point_positions, point_values)


def _recovery_assumptions(bundle, starting_inflation: float) -> pd.DataFrame:
    assumptions = build_baseline_scenario(
        bundle,
        start_period=RECOVERY_START,
        end_period=RECOVERY_END,
    ).quarterly_assumptions.copy()
    count = len(assumptions)
    last = count - 1

    # The package is assumed to cause a short recession, preserve a moderate
    # inflation buffer while high-coupon debt rolls over, and restore inflation
    # close to (but still above) the pre-crisis norm by the end of the horizon.
    assumptions["annual_real_gdp_growth_rate"] = _piecewise_path(
        count,
        [
            (0, -0.010),
            (4, -0.010),
            (8, 0.005),
            (12, 0.020),
            (20, 0.025),
            (28, 0.020),
            (44, 0.018),
            (last, 0.017),
        ],
    )
    assumptions["annual_inflation_rate"] = _piecewise_path(
        count,
        [
            (0, starting_inflation),
            (4, 0.052),
            (12, 0.045),
            (28, 0.035),
            (44, 0.030),
            (last, 0.025),
        ],
    )
    assumptions["annual_tips_reference_inflation_rate"] = assumptions[
        "annual_inflation_rate"
    ].shift(1, fill_value=starting_inflation)

    # A credible joint settlement removes the debt-risk spiral from marginal
    # yields, but it does not return financing costs to normal overnight.
    assumptions["short_issuance_rate"] = _piecewise_path(
        count,
        [
            (0, 0.085),
            (4, 0.075),
            (8, 0.065),
            (12, 0.055),
            (20, 0.048),
            (36, 0.045),
            (last, 0.043),
        ],
    )
    assumptions["intermediate_issuance_rate"] = _piecewise_path(
        count,
        [
            (0, 0.090),
            (4, 0.080),
            (8, 0.070),
            (12, 0.060),
            (20, 0.052),
            (36, 0.050),
            (last, 0.048),
        ],
    )
    assumptions["long_issuance_rate"] = _piecewise_path(
        count,
        [
            (0, 0.090),
            (4, 0.082),
            (8, 0.072),
            (12, 0.063),
            (20, 0.056),
            (36, 0.053),
            (last, 0.051),
        ],
    )
    assumptions["tips_real_issuance_rate"] = _piecewise_path(
        count,
        [(0, 0.027), (8, 0.022), (20, 0.020), (last, 0.018)],
    )
    assumptions["other_public_debt_interest_rate"] = _piecewise_path(
        count,
        [(0, 0.080), (8, 0.065), (20, 0.052), (36, 0.048), (last, 0.045)],
    )
    return assumptions


def _period_at_extreme(path: pd.DataFrame, column: str, kind: str) -> str:
    position = path[column].idxmax() if kind == "max" else path[column].idxmin()
    return str(path.loc[position, "quarter"])


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

    starting = prepare_starting_state(bundle, SHOCK_START)
    pre_settlement_reference = build_baseline_scenario(
        bundle,
        start_period=SHOCK_START,
        end_period=LAST_PRE_SETTLEMENT_QUARTER,
    ).quarterly_assumptions
    premium = pd.Series(0.0, index=pre_settlement_reference.index)
    premium.iloc[:PREMIUM_QUARTERS] = PREMIUM_BASIS_POINTS
    private_spread = pd.Series(0.0, index=pre_settlement_reference.index)
    private_spread.iloc[:PRIVATE_CREDIT_SPREAD_QUARTERS] = (
        PRIVATE_CREDIT_SPREAD_BASIS_POINTS
    )
    policy_rule = PolicyRule(regime=PolicyRegime.PRICE_STABILITY)
    feedback_rule = SequentialFeedbackRule()
    debt_yield_rule = DebtYieldFeedbackRule()
    crisis = run_sequential_crisis_simulation(
        starting.stock,
        pre_settlement_reference,
        initial_nominal_gdp_billions_saar=starting.initial_nominal_gdp_billions_saar,
        initial_real_gdp_billions_chained_saar=(
            starting.initial_real_gdp_billions_chained_saar
        ),
        policy_rule=policy_rule,
        feedback_rule=feedback_rule,
        debt_yield_feedback_rule=debt_yield_rule,
        private_absorption_rule=PrivateAbsorptionRule(),
        interest_income_rule=income_rule,
        treasury_premium_basis_points=premium,
        private_credit_spread_basis_points=private_spread,
        issuance_strategy=bundle.issuance_strategy,
        scenario_name="crisis_to_2039_settlement",
        data_vintage=bundle.cbo_vintage,
    )
    settlement = crisis.quarterly.iloc[-1]
    inherited_stock = crisis.ending_stock.copy()
    inherited_stock.reset_scenario_markers()
    inherited_nominal_gdp = float(settlement["nominal_gdp_billions_saar"])
    inherited_real_gdp = float(settlement["real_gdp_billions_chained_saar"])
    starting_debt_ratio = float(settlement["debt_held_by_public_gdp_ratio"])

    recovery_assumptions = _recovery_assumptions(
        bundle,
        float(settlement["annual_inflation_rate"]),
    )
    solution = solve_fiscal_adjustment(
        inherited_stock,
        recovery_assumptions,
        initial_nominal_gdp_billions_saar=inherited_nominal_gdp,
        initial_real_gdp_billions_chained_saar=inherited_real_gdp,
        issuance_strategy=bundle.issuance_strategy,
        target=ClosureTarget.stabilize_at_start(),
        bounds=(0.0, 0.20),
        phase_in_quarters=FISCAL_PHASE_IN_QUARTERS,
        data_vintage=bundle.cbo_vintage,
    )
    if not solution.solved or solution.value is None:
        raise RuntimeError("the conditional recovery fiscal closure was not solved")

    recovery = solution.result.quarterly.copy()
    recovery_periods = pd.PeriodIndex(recovery["quarter"], freq="Q")
    adjustment_dollars = (
        recovery_assumptions["primary_deficit_billions"]
        - solution.assumptions["primary_deficit_billions"]
    )
    recovery["primary_balance_adjustment_billions"] = adjustment_dollars.to_numpy()
    recovery["primary_balance_adjustment_gdp_share"] = (
        4.0
        * recovery["primary_balance_adjustment_billions"]
        / recovery["nominal_gdp_billions_saar"]
    )
    recovery["short_issuance_rate"] = solution.assumptions.loc[
        recovery_periods, "short_issuance_rate"
    ].to_numpy()
    recovery["intermediate_issuance_rate"] = solution.assumptions.loc[
        recovery_periods, "intermediate_issuance_rate"
    ].to_numpy()
    recovery["long_issuance_rate"] = solution.assumptions.loc[
        recovery_periods, "long_issuance_rate"
    ].to_numpy()
    recovery["stage"] = "conditional_recovery"
    recovery.to_csv(
        OUTPUT_DIR / "recovery_settlement_2039_paths.csv",
        index=False,
    )
    no_fiscal_path = solution.baseline_result.quarterly.reset_index(drop=True)
    if not recovery["quarter"].equals(no_fiscal_path["quarter"]):
        raise ValueError("recovery and no-fiscal quarters do not align")
    pd.DataFrame(
        {
            "quarter": recovery["quarter"],
            "plot_year": (
                recovery["calendar_year"]
                + (recovery["calendar_quarter"] - 1) / 4.0
            ),
            "inflation_pct": 100.0 * recovery["annual_inflation_rate"],
            "real_growth_pct": 100.0 * recovery["annual_real_gdp_growth_rate"],
            "short_rate_pct": 100.0 * recovery["short_issuance_rate"],
            "long_rate_pct": 100.0 * recovery["long_issuance_rate"],
            "debt_gdp_pct": 100.0 * recovery["debt_held_by_public_gdp_ratio"],
            "no_fiscal_debt_gdp_pct": (
                100.0 * no_fiscal_path["debt_held_by_public_gdp_ratio"]
            ),
            "interest_gdp_pct": (
                100.0 * recovery["modeled_interest_gdp_ratio_annualized"]
            ),
            "primary_balance_gdp_pct": (
                -100.0 * recovery["primary_deficit_gdp_ratio_annualized"]
            ),
            "primary_balance_adjustment_gdp_pct": (
                100.0 * recovery["primary_balance_adjustment_gdp_share"]
            ),
        }
    ).to_csv(PAPER_PLOT_DATA_PATH, index=False, float_format="%.6f")

    ending = recovery.iloc[-1]
    baseline_ending = solution.baseline_result.quarterly.iloc[-1]
    price_factor = float(
        np.prod((1.0 + recovery["annual_inflation_rate"].to_numpy()) ** 0.25)
    )
    peak_debt_position = recovery["debt_held_by_public_gdp_ratio"].idxmax()
    peak_interest_position = recovery["modeled_interest_gdp_ratio_annualized"].idxmax()
    summary = {
        "scenario": "conditional_2039_recovery_settlement",
        "last_pre_settlement_quarter": str(LAST_PRE_SETTLEMENT_QUARTER),
        "recovery_start": str(RECOVERY_START),
        "recovery_end": str(RECOVERY_END),
        "starting_inflation_rate": float(settlement["annual_inflation_rate"]),
        "starting_debt_gdp_ratio": starting_debt_ratio,
        "starting_interest_gdp_ratio_annualized": float(
            settlement["modeled_interest_gdp_ratio_annualized"]
        ),
        "starting_policy_rate": float(settlement["policy_rate_proxy"]),
        "required_permanent_primary_balance_improvement_gdp_share": float(
            solution.value
        ),
        "fiscal_phase_in_quarters": FISCAL_PHASE_IN_QUARTERS,
        "peak_recovery_inflation_rate": float(recovery["annual_inflation_rate"].max()),
        "peak_recovery_inflation_quarter": _period_at_extreme(
            recovery, "annual_inflation_rate", "max"
        ),
        "terminal_inflation_rate": float(ending["annual_inflation_rate"]),
        "cumulative_recovery_price_level_increase": price_factor - 1.0,
        "minimum_recovery_real_growth_rate": float(
            recovery["annual_real_gdp_growth_rate"].min()
        ),
        "minimum_recovery_real_growth_quarter": _period_at_extreme(
            recovery, "annual_real_gdp_growth_rate", "min"
        ),
        "peak_recovery_debt_gdp_ratio": float(
            recovery.loc[peak_debt_position, "debt_held_by_public_gdp_ratio"]
        ),
        "peak_recovery_debt_gdp_quarter": str(
            recovery.loc[peak_debt_position, "quarter"]
        ),
        "terminal_debt_gdp_ratio": float(ending["debt_held_by_public_gdp_ratio"]),
        "terminal_four_quarter_debt_gdp_change": float(
            ending["debt_held_by_public_gdp_ratio"]
            - recovery.iloc[-5]["debt_held_by_public_gdp_ratio"]
        ),
        "peak_recovery_interest_gdp_ratio_annualized": float(
            recovery.loc[peak_interest_position, "modeled_interest_gdp_ratio_annualized"]
        ),
        "peak_recovery_interest_quarter": str(
            recovery.loc[peak_interest_position, "quarter"]
        ),
        "terminal_interest_gdp_ratio_annualized": float(
            ending["modeled_interest_gdp_ratio_annualized"]
        ),
        "terminal_primary_balance_gdp_ratio_annualized": -float(
            ending["primary_deficit_gdp_ratio_annualized"]
        ),
        "terminal_total_balance_gdp_ratio_annualized": -float(
            ending["modeled_total_deficit_gdp_ratio_annualized"]
        ),
        "terminal_average_effective_marketable_rate": float(
            ending["average_effective_marketable_rate_excluding_tips_inflation"]
        ),
        "terminal_short_issuance_rate": float(
            solution.assumptions.iloc[-1]["short_issuance_rate"]
        ),
        "terminal_long_issuance_rate": float(
            solution.assumptions.iloc[-1]["long_issuance_rate"]
        ),
        "terminal_debt_gdp_without_fiscal_settlement": float(
            baseline_ending["debt_held_by_public_gdp_ratio"]
        ),
        "debt_target_imposed": True,
    }
    pd.DataFrame([summary]).to_csv(
        OUTPUT_DIR / "recovery_settlement_2039_summary.csv",
        index=False,
    )

    config = {
        "experiment": "Conditional recovery after the central 2039 financing boundary",
        "shock_start": str(SHOCK_START),
        "last_pre_settlement_quarter": str(LAST_PRE_SETTLEMENT_QUARTER),
        "recovery_start": str(RECOVERY_START),
        "recovery_end": str(RECOVERY_END),
        "pre_settlement": {
            "treasury_premium_basis_points": PREMIUM_BASIS_POINTS,
            "treasury_premium_quarters": PREMIUM_QUARTERS,
            "private_credit_spread_basis_points": PRIVATE_CREDIT_SPREAD_BASIS_POINTS,
            "private_credit_spread_quarters": PRIVATE_CREDIT_SPREAD_QUARTERS,
            "policy_rule": asdict(policy_rule),
            "feedback_rule": asdict(feedback_rule),
            "debt_yield_feedback_rule": asdict(debt_yield_rule),
            "private_absorption_rule": asdict(PrivateAbsorptionRule()),
            "interest_income_rule": asdict(income_rule),
        },
        "recovery": {
            "target": (
                "2056Q3 debt/GDP no higher than 2039Q2 and no more than a "
                "0.1 percentage-point increase over the final four quarters"
            ),
            "fiscal_adjustment": (
                "constant share of contemporaneous GDP, phased in linearly over "
                f"{FISCAL_PHASE_IN_QUARTERS} quarters"
            ),
            "real_growth_path": "piecewise path specified in the experiment script",
            "inflation_path": "piecewise path specified in the experiment script",
            "new_issuance_rate_path": (
                "piecewise normalization path specified in the experiment script"
            ),
        },
        "warnings": [
            (
                "Post-settlement growth, inflation, and marginal Treasury rates are "
                "conditional assumptions, not outputs of the sequential feedback rule."
            ),
            (
                "The fiscal adjustment is solved to meet a declared terminal debt target; "
                "it is a required magnitude, not a forecast of legislation."
            ),
            (
                "The cohort engine endogenously calculates rollover, coupons, TIPS "
                "indexation, interest expense, gross issuance, and debt under those paths."
            ),
            (
                "Behavioral responses, distribution, bank recapitalization, investor "
                "demand, and political implementation remain outside the recovery run."
            ),
        ],
        "paper_plot_data": str(PAPER_PLOT_DATA_PATH),
    }
    (CONFIG_DIR / "recovery_settlement_2039.json").write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n"
    )
    print(pd.DataFrame([summary]).to_string(index=False))


if __name__ == "__main__":
    main()
