"""Test rate-cap and inflation experiments after a decade of rate stress.

The experiment is deliberately conditional. A 500-basis-point confidence premium
and a two-year recession begin in 2026Q4. Primary deficits remain on their nominal
CBO paths. In 2036Q4, the experiment compares continued market stress with a
rate cap that returns new-issuance rates to their baseline paths. It then uses the
v0.2 inverse solver to distinguish a five-year price-level reset from a ten-year
inflation path that also satisfies the terminal-flow stability condition.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from debt_sim.closure import (
    ClosureSolution,
    ClosureTarget,
    InflationEpisode,
    InflationRateResponse,
    solve_financial_repression,
    solve_fiscal_adjustment,
    solve_inflation_closure,
)
from debt_sim.confidence import ConfidenceShock, apply_confidence_shock
from debt_sim.data import load_baseline_bundle
from debt_sim.model import SimulationResult, run_simulation
from debt_sim.scenarios import build_baseline_scenario, prepare_starting_state

SHOCK_START = pd.Period("2026Q4", freq="Q")
PASS_THE_BUCK_END = pd.Period("2036Q3", freq="Q")
BACKSTOP_START = pd.Period("2036Q4", freq="Q")
BACKSTOP_END = pd.Period("2046Q3", freq="Q")
PREMIUM_BASIS_POINTS = 500.0
INFLATION_DURATION_QUARTERS = 20
OUTPUT_DIR = Path("data/processed")
CONFIG_DIR = Path("config/scenarios")


def _run(
    bundle,
    stock,
    assumptions: pd.DataFrame,
    nominal_gdp: float,
    real_gdp: float,
    name: str,
) -> SimulationResult:
    return run_simulation(
        stock,
        assumptions,
        initial_nominal_gdp_billions_saar=nominal_gdp,
        initial_real_gdp_billions_chained_saar=real_gdp,
        issuance_strategy=bundle.issuance_strategy,
        scenario_name=name,
        data_vintage=bundle.cbo_vintage,
    )


def _terminal_metrics(result: SimulationResult) -> dict[str, float]:
    row = result.quarterly.iloc[-1]
    ratios = result.quarterly["debt_held_by_public_gdp_ratio"]
    return {
        "terminal_debt_billions": float(row["debt_held_by_public_billions"]),
        "terminal_nominal_gdp_billions_saar": float(row["nominal_gdp_billions_saar"]),
        "terminal_debt_gdp_ratio": float(row["debt_held_by_public_gdp_ratio"]),
        "final_four_quarter_debt_gdp_change": float(ratios.iloc[-1] - ratios.iloc[-5]),
        "terminal_effective_marketable_rate": float(
            row["average_effective_marketable_rate_excluding_tips_inflation"]
        ),
        "terminal_interest_gdp_ratio": float(row["modeled_interest_gdp_ratio_annualized"]),
        "terminal_total_deficit_gdp_ratio": float(
            row["modeled_total_deficit_gdp_ratio_annualized"]
        ),
        "terminal_repriced_share": float(
            row["share_marketable_debt_repriced_since_scenario_start"]
        ),
        "cumulative_interest_billions": float(row["cumulative_modeled_interest_billions"]),
    }


def _plain_summary(
    name: str,
    result: SimulationResult,
    *,
    starting_ratio: float,
    comparison_interest_billions: float,
) -> dict[str, float | str | None]:
    metrics = _terminal_metrics(result)
    return {
        "scenario": name,
        "status": "simulation",
        "starting_debt_gdp_ratio": starting_ratio,
        "required_extra_cumulative_price_change": None,
        "additional_annualized_inflation": None,
        "total_episode_cumulative_price_change": None,
        "fixed_dollar_real_loss_vs_baseline": None,
        "required_fiscal_adjustment_gdp_share": None,
        "required_yield_suppression_basis_points": None,
        "interest_savings_vs_continued_stress_billions": (
            comparison_interest_billions - metrics["cumulative_interest_billions"]
        ),
        **metrics,
    }


def _solution_summary(
    name: str,
    solution: ClosureSolution,
    *,
    comparison_interest_billions: float,
) -> dict[str, float | str | None]:
    metrics = _terminal_metrics(solution.result)
    diagnostics = solution.diagnostics
    extra_price_change = (
        float(solution.value)
        if solution.mechanism == "Inflationary closure" and solution.value is not None
        else None
    )
    return {
        "scenario": name,
        "status": solution.status,
        "starting_debt_gdp_ratio": float(diagnostics["starting_debt_gdp_ratio"]),
        "required_extra_cumulative_price_change": extra_price_change,
        "additional_annualized_inflation": (
            float(diagnostics["additional_annualized_inflation_during_episode"])
            if extra_price_change is not None
            else None
        ),
        "total_episode_cumulative_price_change": (
            float(diagnostics["total_episode_cumulative_price_level_increase"])
            if extra_price_change is not None
            else None
        ),
        "fixed_dollar_real_loss_vs_baseline": (
            extra_price_change / (1.0 + extra_price_change)
            if extra_price_change is not None
            else None
        ),
        "required_fiscal_adjustment_gdp_share": (
            float(solution.value)
            if solution.mechanism == "Required primary-balance adjustment"
            and solution.value is not None
            else None
        ),
        "required_yield_suppression_basis_points": (
            float(solution.value)
            if solution.mechanism == "Financial-repression closure"
            and solution.value is not None
            else None
        ),
        "interest_savings_vs_continued_stress_billions": (
            comparison_interest_billions - metrics["cumulative_interest_billions"]
        ),
        **metrics,
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    bundle = load_baseline_bundle()
    starting_state = prepare_starting_state(bundle, SHOCK_START)
    pre_backstop_baseline = build_baseline_scenario(
        bundle,
        start_period=SHOCK_START,
        end_period=PASS_THE_BUCK_END,
    ).quarterly_assumptions
    pre_backstop_stress = apply_confidence_shock(
        pre_backstop_baseline,
        ConfidenceShock(
            PREMIUM_BASIS_POINTS,
            duration_quarters=len(pre_backstop_baseline),
        ),
    )
    inherited_result = _run(
        bundle,
        starting_state.stock,
        pre_backstop_stress,
        starting_state.initial_nominal_gdp_billions_saar,
        starting_state.initial_real_gdp_billions_chained_saar,
        "pass_the_buck_before_backstop",
    )
    inherited_row = inherited_result.quarterly.iloc[-1]
    inherited_stock = inherited_result.ending_stock.copy()
    inherited_stock.reset_scenario_markers()
    inherited_nominal_gdp = float(inherited_row["nominal_gdp_billions_saar"])
    inherited_real_gdp = float(inherited_row["real_gdp_billions_chained_saar"])
    inherited_ratio = inherited_stock.debt_held_by_public_billions / inherited_nominal_gdp

    post_backstop_baseline = build_baseline_scenario(
        bundle,
        start_period=BACKSTOP_START,
        end_period=BACKSTOP_END,
    ).quarterly_assumptions
    continued_stress_assumptions = apply_confidence_shock(
        post_backstop_baseline,
        ConfidenceShock(
            PREMIUM_BASIS_POINTS,
            duration_quarters=len(post_backstop_baseline),
            include_recession=False,
        ),
    )
    common = {
        "initial_nominal_gdp_billions_saar": inherited_nominal_gdp,
        "initial_real_gdp_billions_chained_saar": inherited_real_gdp,
        "issuance_strategy": bundle.issuance_strategy,
        "target": ClosureTarget.stabilize_at_start(),
        "data_vintage": bundle.cbo_vintage,
    }

    continued_stress = _run(
        bundle,
        inherited_stock,
        continued_stress_assumptions,
        inherited_nominal_gdp,
        inherited_real_gdp,
        "continued_500bp_stress",
    )
    rate_cap_only = _run(
        bundle,
        inherited_stock,
        post_backstop_baseline,
        inherited_nominal_gdp,
        inherited_real_gdp,
        "rate_cap_only",
    )
    continued_interest = float(
        continued_stress.quarterly.iloc[-1]["cumulative_modeled_interest_billions"]
    )

    inflation_fixed_nominal = solve_inflation_closure(
        inherited_stock,
        post_backstop_baseline,
        episode=InflationEpisode(
            duration_quarters=INFLATION_DURATION_QUARTERS,
            shape="multi_year",
            rate_response=InflationRateResponse.no_response(),
            primary_deficit_scales_with_gdp=False,
        ),
        bounds=(0.0, 5.0),
        **common,
    )
    inflation_scaled_deficits = solve_inflation_closure(
        inherited_stock,
        post_backstop_baseline,
        episode=InflationEpisode(
            duration_quarters=INFLATION_DURATION_QUARTERS,
            shape="multi_year",
            rate_response=InflationRateResponse.no_response(),
            primary_deficit_scales_with_gdp=True,
        ),
        bounds=(0.0, 5.0),
        **common,
    )
    endpoint_common = {key: value for key, value in common.items() if key != "target"}
    five_year_endpoint_reset = solve_inflation_closure(
        inherited_stock,
        post_backstop_baseline,
        episode=InflationEpisode(
            duration_quarters=INFLATION_DURATION_QUARTERS,
            shape="multi_year",
            rate_response=InflationRateResponse.no_response(),
            primary_deficit_scales_with_gdp=True,
        ),
        target=ClosureTarget.specified_ratio(inherited_ratio),
        bounds=(0.0, 5.0),
        **endpoint_common,
    )
    persistent_inflation_scaled_deficits = solve_inflation_closure(
        inherited_stock,
        post_backstop_baseline,
        episode=InflationEpisode(
            duration_quarters=len(post_backstop_baseline),
            shape="multi_year",
            rate_response=InflationRateResponse.no_response(),
            primary_deficit_scales_with_gdp=True,
        ),
        bounds=(0.0, 5.0),
        **common,
    )
    inflation_without_cap = solve_inflation_closure(
        inherited_stock,
        continued_stress_assumptions,
        episode=InflationEpisode(
            duration_quarters=INFLATION_DURATION_QUARTERS,
            shape="multi_year",
            rate_response=InflationRateResponse.uniform(1.0),
            primary_deficit_scales_with_gdp=True,
        ),
        bounds=(0.0, 5.0),
        **common,
    )
    fiscal_with_cap = solve_fiscal_adjustment(
        inherited_stock,
        post_backstop_baseline,
        bounds=(0.0, 0.20),
        **common,
    )
    fiscal_under_stress = solve_fiscal_adjustment(
        inherited_stock,
        continued_stress_assumptions,
        bounds=(0.0, 0.20),
        **common,
    )
    repression_under_stress = solve_financial_repression(
        inherited_stock,
        continued_stress_assumptions,
        duration_quarters=len(continued_stress_assumptions),
        nominal_yield_floor=0.0,
        bounds_basis_points=(0.0, 2_000.0),
        **common,
    )

    summary = [
        _plain_summary(
            "continued_500bp_stress",
            continued_stress,
            starting_ratio=inherited_ratio,
            comparison_interest_billions=continued_interest,
        ),
        _plain_summary(
            "rate_cap_only",
            rate_cap_only,
            starting_ratio=inherited_ratio,
            comparison_interest_billions=continued_interest,
        ),
        _solution_summary(
            "rate_cap_plus_inflation_fixed_nominal_deficits",
            inflation_fixed_nominal,
            comparison_interest_billions=continued_interest,
        ),
        _solution_summary(
            "rate_cap_plus_inflation_deficits_scale_with_gdp",
            inflation_scaled_deficits,
            comparison_interest_billions=continued_interest,
        ),
        _solution_summary(
            "rate_cap_plus_five_year_inflation_endpoint_reset",
            five_year_endpoint_reset,
            comparison_interest_billions=continued_interest,
        ),
        _solution_summary(
            "rate_cap_plus_persistent_inflation_deficits_scale_with_gdp",
            persistent_inflation_scaled_deficits,
            comparison_interest_billions=continued_interest,
        ),
        _solution_summary(
            "continued_stress_plus_inflation_and_full_pass_through",
            inflation_without_cap,
            comparison_interest_billions=continued_interest,
        ),
        _solution_summary(
            "fiscal_closure_after_rate_cap",
            fiscal_with_cap,
            comparison_interest_billions=continued_interest,
        ),
        _solution_summary(
            "fiscal_closure_under_continued_stress",
            fiscal_under_stress,
            comparison_interest_billions=continued_interest,
        ),
        _solution_summary(
            "financial_repression_under_continued_stress",
            repression_under_stress,
            comparison_interest_billions=continued_interest,
        ),
    ]
    pd.DataFrame(summary).to_csv(
        OUTPUT_DIR / "monetary_backstop_2036_summary.csv",
        index=False,
    )

    path_results = {
        "continued_500bp_stress": continued_stress,
        "rate_cap_only": rate_cap_only,
        "rate_cap_plus_inflation_fixed_nominal_deficits": inflation_fixed_nominal.result,
        "rate_cap_plus_inflation_deficits_scale_with_gdp": inflation_scaled_deficits.result,
        "rate_cap_plus_five_year_inflation_endpoint_reset": (
            five_year_endpoint_reset.result
        ),
        "rate_cap_plus_persistent_inflation_deficits_scale_with_gdp": (
            persistent_inflation_scaled_deficits.result
        ),
        "continued_stress_plus_inflation_and_full_pass_through": (
            inflation_without_cap.result
        ),
    }
    pd.concat(
        [
            inherited_result.quarterly.assign(scenario="pre_backstop_500bp_stress"),
            *[
                result.quarterly.assign(scenario=name)
                for name, result in path_results.items()
            ],
        ],
        ignore_index=True,
    ).to_csv(OUTPUT_DIR / "monetary_backstop_2036_paths.csv", index=False)

    inflation_diagnostics = []
    for name, solution in {
        "rate_cap_fixed_nominal_deficits": inflation_fixed_nominal,
        "rate_cap_deficits_scale_with_gdp": inflation_scaled_deficits,
        "rate_cap_five_year_inflation_endpoint_reset": five_year_endpoint_reset,
        "rate_cap_persistent_inflation_deficits_scale_with_gdp": (
            persistent_inflation_scaled_deficits
        ),
        "continued_stress_full_pass_through": inflation_without_cap,
    }.items():
        inflation_diagnostics.append({"scenario": name, **solution.diagnostics})
    pd.DataFrame(inflation_diagnostics).to_csv(
        OUTPUT_DIR / "monetary_backstop_2036_inflation_diagnostics.csv",
        index=False,
    )

    if not persistent_inflation_scaled_deficits.solved:
        raise RuntimeError("persistent monetary-backstop scenario unexpectedly had no solution")
    monetary_diagnostics = persistent_inflation_scaled_deficits.diagnostics
    extra_price_change = float(
        monetary_diagnostics["required_additional_cumulative_price_level_increase"]
    )
    total_price_change = float(
        monetary_diagnostics["total_episode_cumulative_price_level_increase"]
    )
    baseline_price_change = (1.0 + total_price_change) / (1.0 + extra_price_change) - 1.0
    monetary_path = persistent_inflation_scaled_deficits.result.quarterly
    issuance_weights = monetary_path["gross_treasury_issuance_billions"]
    average_new_rate = float(
        (monetary_path["average_new_issuance_stated_rate"] * issuance_weights).sum()
        / issuance_weights.sum()
    )
    total_annualized_inflation = float(
        monetary_diagnostics["total_annualized_inflation_during_episode"]
    )
    real_new_financing_rate = (
        (1.0 + average_new_rate) / (1.0 + total_annualized_inflation) - 1.0
    )
    illustrative_starting_wage = 80_000.0
    baseline_indexed_end_wage = illustrative_starting_wage * (1.0 + baseline_price_change)
    scenario_real_wage = baseline_indexed_end_wage / (1.0 + total_price_change)
    household_translation = {
        "interpretation": (
            "illustration only: the wage follows baseline prices but receives no "
            "adjustment for the additional closure inflation"
        ),
        "starting_annual_wage_dollars": illustrative_starting_wage,
        "baseline_cumulative_price_change": baseline_price_change,
        "additional_closure_cumulative_price_change": extra_price_change,
        "scenario_total_cumulative_price_change": total_price_change,
        "baseline_indexed_2046_wage_dollars": baseline_indexed_end_wage,
        "2046_wage_needed_to_preserve_2036_purchasing_power_dollars": (
            illustrative_starting_wage * (1.0 + total_price_change)
        ),
        "scenario_real_annual_wage_in_2036_dollars": scenario_real_wage,
        "annual_real_wage_loss_vs_baseline_in_2036_dollars": (
            illustrative_starting_wage - scenario_real_wage
        ),
        "monthly_real_wage_loss_vs_baseline_in_2036_dollars": (
            (illustrative_starting_wage - scenario_real_wage) / 12.0
        ),
        "real_value_of_100000_fixed_nominal_claim_in_2036_dollars": (
            100_000.0 / (1.0 + total_price_change)
        ),
        "average_new_treasury_issuance_rate": average_new_rate,
        "average_scenario_inflation_rate": total_annualized_inflation,
        "approximate_ex_post_real_new_treasury_financing_rate": real_new_financing_rate,
        "gross_principal_refinanced_billions": float(
            monetary_diagnostics["gross_principal_refinanced_during_episode_billions"]
        ),
        "increase_in_tips_principal_compensation_billions": float(
            monetary_diagnostics["increase_in_tips_principal_compensation_billions"]
        ),
    }
    pd.DataFrame([household_translation]).to_csv(
        OUTPUT_DIR / "monetary_backstop_2036_household_translation.csv",
        index=False,
    )

    config = {
        "experiment": "rate-cap and inflation paths after a decade of refinancing stress",
        "model_version": "0.2",
        "pre_backstop": {
            "start": str(SHOCK_START),
            "end": str(PASS_THE_BUCK_END),
            "confidence_premium_basis_points": PREMIUM_BASIS_POINTS,
            "primary_deficits": "unchanged nominal CBO baseline path",
            "recession": "-2% annualized for four quarters, 0% for four, then baseline",
        },
        "backstop": {
            "start": str(BACKSTOP_START),
            "end": str(BACKSTOP_END),
            "rate_cap_definition": (
                "new bill, note, bond, and TIPS issuance rates return immediately to "
                "the CBO baseline path; coupons on inherited debt remain unchanged"
            ),
            "five_year_comparison_inflation_quarters": INFLATION_DURATION_QUARTERS,
            "selected_stabilizing_inflation_quarters": len(post_backstop_baseline),
            "inflation_rate_response": "none while the rate cap is imposed",
            "primary_deficit_treatment": "constant share of scenario GDP",
            "closure_target": (
                "terminal debt/GDP no higher than its 2036Q3 inherited level and no "
                "more than a 0.1 percentage-point increase over the final four quarters"
            ),
        },
        "interpretation": (
            "conditional Treasury-cohort arithmetic; Federal Reserve implementation, "
            "investor demand, and behavioral macroeconomic responses remain outside "
            "the experiment"
        ),
    }
    (CONFIG_DIR / "monetary_backstop_2036.json").write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n"
    )

    print(pd.DataFrame(summary).to_string(index=False))


if __name__ == "__main__":
    main()
