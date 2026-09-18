from __future__ import annotations

import pytest

from debt_sim.debt_stock import DebtStock, IssuanceStrategy
from debt_sim.feedback import build_macro_feedback_path, run_macro_policy_simulation
from debt_sim.policy import PolicyRegime, PolicyRule


def test_price_stability_feedback_reduces_inflation_with_a_lag(make_assumptions):
    reference = make_assumptions(
        periods=16,
        annual_inflation_rate=0.05,
        short_issuance_rate=0.03,
        intermediate_issuance_rate=0.04,
        long_issuance_rate=0.05,
    )
    solution = build_macro_feedback_path(
        reference,
        initial_nominal_gdp_billions_saar=1_000.0,
        policy_rule=PolicyRule(
            regime=PolicyRegime.PRICE_STABILITY,
            reaction_smoothing=0.0,
        ),
    )

    assert solution.converged
    assert solution.output_gap.iloc[0] == pytest.approx(0.0)
    assert solution.output_gap.iloc[1] == pytest.approx(0.0)
    assert solution.output_gap.iloc[2] < 0.0
    assert solution.assumptions.iloc[-1]["annual_inflation_rate"] < 0.05
    assert solution.assumptions["automatic_stabilizer_primary_deficit_billions"].max() > 0.0


def test_price_stability_lowers_inflation_more_than_a_suppressed_rate_path(
    make_assumptions,
):
    reference = make_assumptions(
        periods=16,
        annual_inflation_rate=0.05,
        short_issuance_rate=0.03,
        intermediate_issuance_rate=0.04,
        long_issuance_rate=0.05,
    )
    price_stability = build_macro_feedback_path(
        reference,
        initial_nominal_gdp_billions_saar=1_000.0,
        policy_rule=PolicyRule(
            regime=PolicyRegime.PRICE_STABILITY,
            reaction_smoothing=0.0,
        ),
    )
    dominance = build_macro_feedback_path(
        reference,
        initial_nominal_gdp_billions_saar=1_000.0,
        policy_rule=PolicyRule(
            regime=PolicyRegime.FISCAL_DOMINANCE,
            reaction_smoothing=0.0,
        ),
    )

    price_stability_end = price_stability.assumptions.iloc[-1]
    dominance_end = dominance.assumptions.iloc[-1]
    assert price_stability_end["annual_inflation_rate"] < dominance_end["annual_inflation_rate"]
    assert price_stability.output_gap.min() < dominance.output_gap.min()
    assert (
        price_stability.assumptions["automatic_stabilizer_primary_deficit_billions"].sum()
        > dominance.assumptions["automatic_stabilizer_primary_deficit_billions"].sum()
    )


def test_private_credit_spread_weakens_output_even_when_treasury_rates_are_capped(
    make_assumptions,
):
    reference = make_assumptions(periods=8, annual_inflation_rate=0.02)
    solution = build_macro_feedback_path(
        reference,
        initial_nominal_gdp_billions_saar=1_000.0,
        policy_rule=PolicyRule(
            regime=PolicyRegime.FISCAL_DOMINANCE,
            reaction_smoothing=0.0,
        ),
        private_credit_spread_basis_points=300.0,
    )

    assert solution.output_gap.iloc[1] == pytest.approx(0.0)
    assert solution.output_gap.iloc[2] < 0.0
    assert (
        solution.assumptions.iloc[2]["primary_deficit_billions"]
        > reference.iloc[2]["primary_deficit_billions"]
    )


def test_macro_policy_simulation_preserves_debt_identity_and_feedback_diagnostics(
    make_cohort,
    make_assumptions,
):
    result = run_macro_policy_simulation(
        DebtStock([make_cohort(maturity="2040Q1")], 0.0),
        make_assumptions(
            periods=8,
            annual_inflation_rate=0.05,
            primary_deficit_billions=2.0,
        ),
        initial_nominal_gdp_billions_saar=1_000.0,
        initial_real_gdp_billions_chained_saar=1_000.0,
        policy_rule=PolicyRule(
            regime=PolicyRegime.PRICE_STABILITY,
            reaction_smoothing=0.0,
        ),
        issuance_strategy=IssuanceStrategy(),
        scenario_name="feedback_test",
        data_vintage="test",
    )

    assert result.quarterly["debt_identity_residual_billions"].abs().max() < 1e-9
    assert result.quarterly["macro_feedback_converged"].all()
    assert "monetary_tightening_rate_gap" in result.quarterly
    assert "reference_primary_deficit_billions" in result.quarterly
