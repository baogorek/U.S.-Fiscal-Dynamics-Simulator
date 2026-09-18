"""Reproduce the three runs used in The Consequences of Continuing to Borrow.

Uses pinned inputs and the existing simulator. Writes only borrowing_article_*
outputs; does not refresh data, solve fiscal adjustments, or run other scenarios.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import pandas as pd

from debt_sim.crisis import (
    InterestIncomeRule,
    SequentialFeedbackRule,
    run_sequential_crisis_simulation,
)
from debt_sim.data import load_baseline_bundle
from debt_sim.policy import PolicyRegime, PolicyRule
from debt_sim.scenarios import build_baseline_scenario, prepare_starting_state
from debt_sim.sustainability import decompose_debt_ratio

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/processed"


def main() -> None:
    bundle = load_baseline_bundle(data_root=ROOT / "data")
    scenario = build_baseline_scenario(bundle, start_period="2026Q4", end_period="2056Q3")
    reference = scenario.quarterly_assumptions
    starting = prepare_starting_state(bundle, "2026Q4")
    holder_file = ROOT / "config/calibration/interest_recipient_shares_2026.json"
    holders = json.loads(holder_file.read_text())
    income = InterestIncomeRule(
        domestic_private_share=holders["domestic_private_share"],
        foreign_share=holders["foreign_share"],
        federal_reserve_share=holders["federal_reserve_share"],
        domestic_private_spending_fraction=0.25,
        foreign_domestic_spending_fraction=0.05,
        federal_reserve_spending_fraction=0.0,
    )
    feedback = SequentialFeedbackRule(
        output_gap_persistence=0.80,
        policy_tightening_output_semi_elasticity=0.25,
        private_credit_spread_output_semi_elasticity=0.15,
        primary_deficit_output_multiplier=0.80,
        interest_income_output_multiplier=1.0,
        policy_effect_lag_quarters=2,
        fiscal_effect_lag_quarters=1,
        inflation_persistence=0.98,
        inflation_output_gap_sensitivity=0.06,
        inflation_gap_lag_quarters=2,
        automatic_stabilizer_semi_elasticity=0.45,
        primary_deficit_scales_with_nominal_gdp=True,
    )
    policy = PolicyRule(
        regime=PolicyRegime.PRICE_STABILITY,
        inflation_target=0.02,
        inflation_response=1.5,
        output_gap_response=0.5,
        reaction_smoothing=0.5,
        intermediate_policy_pass_through=0.75,
        long_policy_pass_through=0.5,
        tips_real_policy_pass_through=0.5,
        maximum_issuance_rate=0.99,
    )
    premium = pd.Series(0.0, index=reference.index)
    premium.iloc[:40] = 500.0
    private_spread = pd.Series(0.0, index=reference.index)
    private_spread.iloc[:8] = 200.0
    paths, summaries = [], []
    plot = pd.DataFrame({
        "plot_year": [p.year + (p.quarter - 0.5) / 4 for p in reference.index],
    })
    cases = [("reference", 0.98, False), ("persistent", 0.98, True), ("faster_fading", 0.90, True)]
    for name, persistence, stress in cases:
        result = run_sequential_crisis_simulation(
            starting.stock,
            reference,
            initial_nominal_gdp_billions_saar=starting.initial_nominal_gdp_billions_saar,
            initial_real_gdp_billions_chained_saar=starting.initial_real_gdp_billions_chained_saar,
            issuance_strategy=bundle.issuance_strategy,
            data_vintage=bundle.cbo_vintage,
            policy_rule=policy,
            feedback_rule=replace(feedback, inflation_persistence=persistence),
            interest_income_rule=income,
            treasury_premium_basis_points=premium if stress else 0.0,
            private_credit_spread_basis_points=private_spread if stress else 0.0,
            debt_yield_feedback_rule=None,
            private_absorption_rule=None,
            primary_balance_adjustment_gdp_share=0.0,
            scenario_name=name,
        )
        path = result.quarterly
        if path.debt_identity_residual_billions.abs().max() > 1e-7:
            raise RuntimeError(f"Debt accounting does not reconcile for {name}")
        if path.rate_bound_binding.any():
            raise RuntimeError(f"A numerical rate bound binds in {name}")
        if not np.allclose(path.primary_balance_adjustment_gdp_share, 0.0):
            raise RuntimeError(f"Unexpected fiscal adjustment in {name}")
        paths.append(path.assign(article_case=name))
        plot[f"{name}_debt_pct"] = path.debt_held_by_public_gdp_ratio.to_numpy() * 100
        plot[f"{name}_inflation_pct"] = path.annual_inflation_rate.to_numpy() * 100
        end = path.iloc[-1]
        summaries.append({
            "scenario": name,
            "inflation_persistence": persistence,
            "terminal_inflation_pct": end.annual_inflation_rate * 100,
            "peak_inflation_pct": path.annual_inflation_rate.max() * 100,
            "terminal_debt_gdp_pct": end.debt_held_by_public_gdp_ratio * 100,
            "terminal_output_gap_pct": end.macro_feedback_output_gap * 100,
            "max_accounting_residual_billions": path.debt_identity_residual_billions.abs().max(),
        })
        if name == "reference":
            decomposition = decompose_debt_ratio(
                path,
                initial_nominal_gdp_billions_saar=starting.initial_nominal_gdp_billions_saar,
            )
        print(
            f"{name}: inflation {end.annual_inflation_rate:.4%}, "
            f"debt/GDP {end.debt_held_by_public_gdp_ratio:.4%}",
            flush=True,
        )

    summary = pd.DataFrame(summaries)
    # Check the article's rounded values; these are verification checks, not fit targets.
    np.testing.assert_allclose(
        summary.terminal_inflation_pct, [2.06, 8.04, 2.89], rtol=0.0, atol=0.005,
    )
    np.testing.assert_allclose(
        summary.terminal_debt_gdp_pct, [172.77, 255.61, 259.92], rtol=0.0, atol=0.005,
    )
    if decomposition.decomposition_residual.abs().max() > 1e-10:
        raise RuntimeError("Debt-ratio decomposition does not reconcile")
    final_year = decomposition.tail(4)
    contributions = final_year[[
        "primary_contribution", "interest_contribution", "growth_contribution",
        "other_financing_contribution", "debt_ratio_change",
    ]].sum() * 100
    np.testing.assert_allclose(contributions.debt_ratio_change, 3.13, rtol=0.0, atol=0.005)

    source_files = [
        "treasury_securities_2025-09-30.csv", "initial_conditions_2025-09-30.csv",
        "cbo_baseline_fy_2026-02.csv", "cbo_economy_quarterly_2026-02.csv",
        "cbo_long_term_budget_fy_2026-02-25.csv",
        "cbo_long_term_economy_annual_2026-02-25.csv",
    ]
    hash_paths = [OUTPUT / name for name in source_files]
    hash_paths += [holder_file, Path(__file__).resolve()]
    hash_paths += sorted((ROOT / "src/debt_sim").glob("*.py"))
    metadata = {
        "title": "The Consequences of Continuing to Borrow",
        "reference_assumptions": scenario.imposed_parameters,
        "start": str(reference.index[0]),
        "end": str(reference.index[-1]),
        "opening_debt_billions": starting.stock.debt_held_by_public_billions,
        "opening_gdp_billions_saar": starting.initial_nominal_gdp_billions_saar,
        "opening_real_gdp_billions_saar": starting.initial_real_gdp_billions_chained_saar,
        "opening_debt_gdp_pct": 100 * starting.stock.debt_held_by_public_billions
        / starting.initial_nominal_gdp_billions_saar,
        "interest_income_rule": asdict(income),
        "feedback_rule_persistent_case": asdict(feedback),
        "policy_rule": asdict(policy),
        "issuance_strategy": asdict(bundle.issuance_strategy),
        "stress_treasury_premium_bp": premium.to_list(),
        "stress_private_spread_bp": private_spread.to_list(),
        "cases": [{"name": n, "rho": r, "stress": s} for n, r, s in cases],
        "final_year_contributions_percentage_points": contributions.to_dict(),
        "half_lives_years": {str(r): np.log(0.5) / np.log(r) / 4 for r in (0.98, 0.90)},
        "sha256": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in hash_paths
        },
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    pd.concat(paths, ignore_index=True).to_csv(OUTPUT / "borrowing_article_paths.csv", index=False)
    summary.to_csv(OUTPUT / "borrowing_article_summary.csv", index=False)
    decomposition.to_csv(OUTPUT / "borrowing_article_decomposition.csv", index=False)
    plot.to_csv(OUTPUT / "borrowing_article_plot_data.csv", index=False)
    reference.to_csv(OUTPUT / "borrowing_article_reference_inputs.csv", index_label="quarter")
    (OUTPUT / "borrowing_article_metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
    )
    print("Final-year contributions (percentage points):", contributions.round(4).to_dict())
    print("Article figures and accounting checks reproduced successfully.")


if __name__ == "__main__":
    main()
