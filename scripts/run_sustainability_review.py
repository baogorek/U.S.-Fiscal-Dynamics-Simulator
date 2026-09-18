"""Reproduce the no-shock sustainability review and macro-assumption challenges.

Reads the pinned data. Writes separate review artifacts; historical experiment
outputs and their coefficients are left intact. No crisis dates are fitted.
"""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path

import pandas as pd

from debt_sim.closure import ClosureTarget, solve_fiscal_adjustment
from debt_sim.crisis import (
    DebtYieldFeedbackRule,
    InterestIncomeRule,
    PrivateAbsorptionRule,
    SequentialFeedbackRule,
    run_sequential_crisis_simulation,
    summarize_crisis_path,
)
from debt_sim.data import load_baseline_bundle
from debt_sim.policy import PolicyRule
from debt_sim.scenarios import build_baseline_scenario, prepare_starting_state
from debt_sim.sustainability import constant_policy_debt_path, decompose_debt_ratio

OUTPUT = Path("data/processed")
DOCS = Path("docs")


def main() -> None:
    bundle = load_baseline_bundle()
    start = pd.Period("2026Q4", freq="Q")
    reference = build_baseline_scenario(
        bundle, start_period=start, end_period="2056Q3",
    ).quarterly_assumptions
    starting = prepare_starting_state(bundle, start)
    common = {
        "initial_nominal_gdp_billions_saar": starting.initial_nominal_gdp_billions_saar,
        "initial_real_gdp_billions_chained_saar": (
            starting.initial_real_gdp_billions_chained_saar
        ),
        "issuance_strategy": bundle.issuance_strategy,
        "data_vintage": bundle.cbo_vintage,
    }
    holder_path = Path("config/calibration/interest_recipient_shares_2026.json")
    holders = json.loads(holder_path.read_text())
    income = InterestIncomeRule(**{
        key: holders[key]
        for key in ("domestic_private_share", "foreign_share", "federal_reserve_share")
    })
    feedback = SequentialFeedbackRule()
    policy = PolicyRule()
    premium = pd.Series(0.0, index=reference.index)
    premium.iloc[:40] = 500.0
    credit = pd.Series(0.0, index=reference.index)
    credit.iloc[:8] = 200.0
    cases = {
        "no_shock": {"treasury_premium_basis_points": 0.0,
                     "private_credit_spread_basis_points": 0.0},
        "no_shock_with_debt_yields_and_capacity": {
            "treasury_premium_basis_points": 0.0,
            "private_credit_spread_basis_points": 0.0,
            "debt_yield_feedback_rule": DebtYieldFeedbackRule(),
            "private_absorption_rule": PrivateAbsorptionRule(),
        },
        "original_500bp": {},
        "smaller_100bp": {"treasury_premium_basis_points": premium / 5.0},
        "inflation_persistence_090": {
            "feedback_rule": replace(feedback, inflation_persistence=0.90),
        },
        "monetary_transmission_050": {
            "feedback_rule": replace(feedback, policy_tightening_output_semi_elasticity=0.50),
        },
        "half_interest_spending": {
            "interest_income_rule": replace(
                income, domestic_private_spending_fraction=0.125,
                foreign_domestic_spending_fraction=0.025,
            ),
        },
        "half_treasury_premium_to_private_credit": {
            "private_credit_spread_basis_points": credit + 0.5 * premium,
        },
        "combined_macro_alternative": {
            "feedback_rule": replace(
                feedback, inflation_persistence=0.90,
                policy_tightening_output_semi_elasticity=0.50,
            ),
            "private_credit_spread_basis_points": credit + 0.5 * premium,
        },
    }
    paths, summaries, configurations = [], [], {}
    for name, overrides in cases.items():
        parameters = {
            "policy_rule": policy, "feedback_rule": feedback,
            "interest_income_rule": income,
            "treasury_premium_basis_points": premium,
            "private_credit_spread_basis_points": credit,
            **overrides,
        }
        result = run_sequential_crisis_simulation(
            starting.stock, reference, **common, **parameters, scenario_name=name,
        )
        paths.append(result.quarterly.assign(scenario=name))
        summary = summarize_crisis_path(result)
        summary["terminal_output_gap"] = float(
            result.quarterly.macro_feedback_output_gap.iloc[-1]
        )
        summary["maximum_debt_identity_residual_billions"] = float(
            result.quarterly.debt_identity_residual_billions.abs().max()
        )
        summaries.append(summary)
        configurations[name] = {
            key: value.to_list() if isinstance(value, pd.Series)
            else asdict(value) if hasattr(value, "__dataclass_fields__") else value
            for key, value in parameters.items()
        }
        print(
            f"{name}: terminal inflation {summary['terminal_inflation_rate']:.2%}, "
            f"debt/GDP {summary['terminal_debt_gdp_ratio']:.2%}", flush=True,
        )
        if name == "no_shock":
            decomposition = decompose_debt_ratio(
                result.quarterly,
                initial_nominal_gdp_billions_saar=starting.initial_nominal_gdp_billions_saar,
            )
            decomposition.to_csv(OUTPUT / "sustainability_review_baseline_decomposition.csv",
                                 index=False)
            baseline = result.quarterly
    pd.concat(paths, ignore_index=True).to_csv(
        OUTPUT / "sustainability_review_macro_paths.csv", index=False,
    )
    pd.DataFrame(summaries).to_csv(OUTPUT / "sustainability_review_macro_summary.csv", index=False)

    closures = []
    closure_paths = []
    for phase in (0, 16):
        solution = solve_fiscal_adjustment(
            starting.stock, reference, **common,
            target=ClosureTarget.stabilize_at_start(max_final_four_quarter_increase=0.0),
            phase_in_quarters=phase,
            bounds=(0.0, 0.04),
        )
        if not solution.solved:
            raise RuntimeError(f"no-shock fiscal closure failed: {solution.status}")
        closures.append({
            "phase_in_quarters": phase, "adjustment_gdp_share": solution.value,
            "status": solution.status, **asdict(solution.evaluation),
            "start": str(reference.index[0]), "end": str(reference.index[-1]),
        })
        closure_paths.append(solution.result.quarterly.assign(phase_in_quarters=phase))
        print(f"No-shock fiscal improvement, phase {phase}: {solution.value:.3%}", flush=True)
    pd.DataFrame(closures).to_csv(OUTPUT / "sustainability_review_fiscal_closure.csv", index=False)
    pd.concat(closure_paths, ignore_index=True).to_csv(
        OUTPUT / "sustainability_review_fiscal_paths.csv", index=False,
    )

    constant_paths = []
    for name, deficit, rate in (
        ("stable_primary_deficit", 0.01, 0.03),
        ("larger_deficit_low_rate", 0.025, 0.03),
        ("equal_interest_growth", 0.025, 0.04),
        ("interest_above_growth", 0.025, 0.05),
    ):
        path = constant_policy_debt_path(
            initial_debt_gdp_ratio=1.0, primary_deficit_gdp_share=deficit,
            nominal_interest_rate=rate, nominal_gdp_growth=0.04, years=100,
        ).assign(scenario=name, primary_deficit_gdp_share=deficit,
                 nominal_interest_rate=rate, nominal_gdp_growth=0.04)
        constant_paths.append(path)
    pd.concat(constant_paths, ignore_index=True).to_csv(
        OUTPUT / "sustainability_review_constant_policy.csv", index=False,
    )
    plot = pd.DataFrame({
        "plot_year": [p.year + (p.quarter - 0.5) / 4 for p in reference.index],
        "baseline_debt_pct": baseline.debt_held_by_public_gdp_ratio * 100,
        "immediate_adjustment_debt_pct": (
            closure_paths[0].debt_held_by_public_gdp_ratio * 100
        ),
        "phased_adjustment_debt_pct": closure_paths[1].debt_held_by_public_gdp_ratio * 100,
    })
    plot.to_csv(DOCS / "sustainability_review_plot_data.csv", index=False)
    config = {
        "purpose": "No-shock fiscal arithmetic and challenges to unestimated macro coefficients",
        "start": str(reference.index[0]), "end": str(reference.index[-1]),
        "data_vintage": bundle.cbo_vintage,
        "holder_calibration": str(holder_path), "macro_cases": configurations,
        "closure_target": asdict(
            ClosureTarget.stabilize_at_start(max_final_four_quarter_increase=0.0)
        ),
        "constant_policy_initial_debt_gdp_ratio": 1.0,
        "constant_policy_horizon_years": 100,
        "constant_policy_cases": [
            {key: path.iloc[0][key] for key in (
                "scenario", "primary_deficit_gdp_share", "nominal_interest_rate",
                "nominal_gdp_growth",
            )} for path in constant_paths
        ],
        "warnings": [
            "Alternative macro coefficients are challenges, not empirical estimates.",
            "The no-shock reference is protected by reference-relative feedback rules.",
            "Fiscal closures hold growth, inflation, and issuance rates at reference values.",
            "Local stabilization gaps are distinct from permanent horizon-wide fiscal packages.",
            "Constant-policy paths are mathematical illustrations, not post-2056 US forecasts.",
        ],
    }
    Path("config/scenarios/sustainability_review.json").write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n",
    )


if __name__ == "__main__":
    main()
