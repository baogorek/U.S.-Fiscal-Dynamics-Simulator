from __future__ import annotations

import pandas as pd
import pytest

from debt_sim.crisis import (
    DebtYieldFeedbackRule,
    InterestIncomeRule,
    PrivateAbsorptionRule,
    PrivateFinancingCapacityError,
    SequentialFeedbackRule,
    build_private_absorption_diagnostics,
    run_sequential_crisis_simulation,
    summarize_crisis_path,
    summarize_private_absorption,
)
from debt_sim.debt_stock import DebtStock, IssuanceStrategy
from debt_sim.instruments import InstrumentType
from debt_sim.policy import PolicyRule


def test_zero_stress_reproduces_parallel_reference(make_assumptions, make_cohort):
    assumptions = make_assumptions(
        periods=8,
        annual_inflation_rate=0.02,
        annual_tips_reference_inflation_rate=0.02,
        primary_deficit_billions=2.0,
        short_issuance_rate=0.03,
        intermediate_issuance_rate=0.04,
        long_issuance_rate=0.04,
    )
    assumptions["annual_inflation_rate"] = [0.02, 0.025, 0.03, 0.027, 0.024, 0.022, 0.021, 0.02]
    assumptions["annual_tips_reference_inflation_rate"] = [
        0.018,
        0.021,
        0.026,
        0.029,
        0.025,
        0.023,
        0.021,
        0.02,
    ]
    result = run_sequential_crisis_simulation(
        DebtStock([make_cohort(maturity="2030Q1")], 0.0),
        assumptions,
        initial_nominal_gdp_billions_saar=1_000.0,
        initial_real_gdp_billions_chained_saar=1_000.0,
        policy_rule=PolicyRule(reaction_smoothing=0.0),
        debt_yield_feedback_rule=DebtYieldFeedbackRule(),
        private_absorption_rule=PrivateAbsorptionRule(),
        issuance_strategy=IssuanceStrategy(),
        scenario_name="zero_stress",
        data_vintage="test",
    )

    assert result.quarterly["debt_held_by_public_billions"].to_list() == pytest.approx(
        result.reference_quarterly["debt_held_by_public_billions"].to_list()
    )
    assert result.quarterly["incremental_cash_interest_billions"].abs().max() < 1e-12
    assert not result.quarterly["terminal_debt_target_imposed"].any()
    absorption = build_private_absorption_diagnostics(result)
    absorption_summary = summarize_private_absorption(absorption)
    assert not absorption_summary["private_absorption_shortfall_occurs"]
    assert not absorption_summary["finite_private_absorption_capacity_exceeded"]
    assert (
        result.quarterly["private_absorption_market_clearing_spread_basis_points"].max()
        == pytest.approx(0.0)
    )


def test_primary_balance_adjustment_enters_debt_and_macro_feedback(
    make_assumptions,
    make_cohort,
):
    assumptions = make_assumptions(
        periods=8,
        annual_inflation_rate=0.02,
        annual_tips_reference_inflation_rate=0.02,
        primary_deficit_billions=20.0,
        short_issuance_rate=0.03,
        intermediate_issuance_rate=0.04,
        long_issuance_rate=0.04,
    )
    common = {
        "initial_nominal_gdp_billions_saar": 1_000.0,
        "initial_real_gdp_billions_chained_saar": 1_000.0,
        "policy_rule": PolicyRule(
            inflation_response=0.0,
            output_gap_response=0.0,
            reaction_smoothing=0.0,
        ),
        "feedback_rule": SequentialFeedbackRule(
            output_gap_persistence=0.0,
            policy_tightening_output_semi_elasticity=0.0,
            private_credit_spread_output_semi_elasticity=0.0,
            primary_deficit_output_multiplier=1.0,
            interest_income_output_multiplier=0.0,
            fiscal_effect_lag_quarters=1,
            inflation_persistence=0.0,
            inflation_output_gap_sensitivity=0.0,
            automatic_stabilizer_semi_elasticity=0.0,
        ),
        "interest_income_rule": InterestIncomeRule(
            domestic_private_share=1.0,
            foreign_share=0.0,
            federal_reserve_share=0.0,
            domestic_private_spending_fraction=0.0,
        ),
        "issuance_strategy": IssuanceStrategy(),
        "data_vintage": "test",
    }
    stock = DebtStock([make_cohort(maturity="2030Q1")], 0.0)
    unchanged = run_sequential_crisis_simulation(
        stock,
        assumptions,
        scenario_name="unchanged_primary_balance",
        **common,
    )
    adjusted = run_sequential_crisis_simulation(
        stock,
        assumptions,
        primary_balance_adjustment_gdp_share=0.04,
        scenario_name="adjusted_primary_balance",
        **common,
    )

    path = adjusted.quarterly
    assert path.iloc[0]["primary_balance_adjustment_gdp_share"] == pytest.approx(0.04)
    assert path.iloc[0]["primary_balance_adjustment_billions"] == pytest.approx(
        0.04 * path.iloc[0]["nominal_gdp_billions_saar"] / 4.0
    )
    assert path.iloc[1]["macro_feedback_output_gap"] < 0.0
    assert path.iloc[-1]["debt_held_by_public_billions"] < unchanged.quarterly.iloc[-1][
        "debt_held_by_public_billions"
    ]


def test_debt_deterioration_raises_later_treasury_yields(make_assumptions, make_cohort):
    assumptions = make_assumptions(
        periods=12,
        annual_inflation_rate=0.02,
        annual_tips_reference_inflation_rate=0.02,
        primary_deficit_billions=20.0,
        short_issuance_rate=0.02,
        intermediate_issuance_rate=0.03,
        long_issuance_rate=0.04,
    )
    common = {
        "initial_nominal_gdp_billions_saar": 1_000.0,
        "initial_real_gdp_billions_chained_saar": 1_000.0,
        "policy_rule": PolicyRule(
            inflation_response=0.0,
            output_gap_response=0.0,
            reaction_smoothing=0.0,
        ),
        "feedback_rule": SequentialFeedbackRule(
            policy_tightening_output_semi_elasticity=0.0,
            primary_deficit_output_multiplier=0.0,
            interest_income_output_multiplier=0.0,
            automatic_stabilizer_semi_elasticity=0.0,
        ),
        "interest_income_rule": InterestIncomeRule(
            domestic_private_share=1.0,
            foreign_share=0.0,
            federal_reserve_share=0.0,
            domestic_private_spending_fraction=0.0,
        ),
        "treasury_premium_basis_points": 500.0,
        "issuance_strategy": IssuanceStrategy(),
        "data_vintage": "test",
    }
    no_feedback = run_sequential_crisis_simulation(
        DebtStock([make_cohort(maturity="2026Q1")], 0.0),
        assumptions,
        scenario_name="no_debt_yield_feedback",
        **common,
    )
    with_feedback = run_sequential_crisis_simulation(
        DebtStock([make_cohort(maturity="2026Q1")], 0.0),
        assumptions,
        debt_yield_feedback_rule=DebtYieldFeedbackRule(signal_lag_quarters=1),
        scenario_name="with_debt_yield_feedback",
        **common,
    )

    path = with_feedback.quarterly
    assert path.iloc[0]["debt_yield_long_adjustment_basis_points"] == pytest.approx(0.0)
    assert path["debt_gdp_ratio_gap_from_reference_percentage_points"].max() > 0.0
    assert path["debt_yield_long_adjustment_basis_points"].max() > 0.0
    assert path.iloc[-1]["long_issuance_rate"] > no_feedback.quarterly.iloc[-1][
        "long_issuance_rate"
    ]


def test_private_absorption_spread_clears_then_finite_capacity_fails(
    make_assumptions,
    make_cohort,
):
    assumptions = make_assumptions(
        periods=8,
        annual_inflation_rate=0.02,
        annual_tips_reference_inflation_rate=0.02,
        primary_deficit_billions=10.0,
        short_issuance_rate=0.02,
        intermediate_issuance_rate=0.03,
        long_issuance_rate=0.04,
    )
    common = {
        "initial_nominal_gdp_billions_saar": 1_000.0,
        "initial_real_gdp_billions_chained_saar": 1_000.0,
        "policy_rule": PolicyRule(
            inflation_response=0.0,
            output_gap_response=0.0,
            reaction_smoothing=0.0,
        ),
        "feedback_rule": SequentialFeedbackRule(
            output_gap_persistence=0.0,
            policy_tightening_output_semi_elasticity=0.0,
            private_credit_spread_output_semi_elasticity=1.0,
            primary_deficit_output_multiplier=0.0,
            interest_income_output_multiplier=0.0,
            policy_effect_lag_quarters=1,
            automatic_stabilizer_semi_elasticity=0.5,
        ),
        "interest_income_rule": InterestIncomeRule(
            domestic_private_share=1.0,
            foreign_share=0.0,
            federal_reserve_share=0.0,
            domestic_private_spending_fraction=0.0,
        ),
        "private_credit_spread_basis_points": 1_000.0,
        "issuance_strategy": IssuanceStrategy(),
        "data_vintage": "test",
    }
    stock = DebtStock([make_cohort(maturity="2030Q1")], 0.0)
    clearing = run_sequential_crisis_simulation(
        stock,
        assumptions,
        private_absorption_rule=PrivateAbsorptionRule(
            capacity_increase_fraction_per_100_basis_points=0.10,
            maximum_capacity_multiple=10.0,
        ),
        scenario_name="market_clearing",
        **common,
    )
    assert (
        clearing.quarterly["private_absorption_market_clearing_spread_basis_points"].max()
        > 0.0
    )
    assert (
        clearing.quarterly["private_absorption_required_capacity_multiple"]
        <= clearing.quarterly["private_absorption_capacity_multiple_at_clearing_yield"]
        + 1e-9
    ).all()

    with pytest.raises(PrivateFinancingCapacityError) as failure:
        run_sequential_crisis_simulation(
            stock,
            assumptions,
            private_absorption_rule=PrivateAbsorptionRule(
                capacity_increase_fraction_per_100_basis_points=0.10,
                maximum_capacity_multiple=1.0,
            ),
            scenario_name="finite_capacity_failure",
            **common,
        )
    assert failure.value.quarter == "2026Q2"
    assert failure.value.required_capacity_multiple > 1.0


def test_incremental_interest_enters_demand_then_inflation(make_assumptions, make_cohort):
    assumptions = make_assumptions(
        periods=16,
        annual_inflation_rate=0.02,
        annual_tips_reference_inflation_rate=0.02,
        short_issuance_rate=0.02,
        intermediate_issuance_rate=0.02,
        long_issuance_rate=0.02,
    )
    stock = DebtStock(
        [
            make_cohort(
                instrument_type=InstrumentType.BILL,
                principal=1_000.0,
                rate=0.02,
                maturity="2026Q1",
            )
        ],
        0.0,
    )
    common = {
        "initial_nominal_gdp_billions_saar": 1_000.0,
        "initial_real_gdp_billions_chained_saar": 1_000.0,
        "policy_rule": PolicyRule(reaction_smoothing=0.0),
        "feedback_rule": SequentialFeedbackRule(
            automatic_stabilizer_semi_elasticity=0.0,
            primary_deficit_output_multiplier=0.0,
        ),
        "treasury_premium_basis_points": 500.0,
        "issuance_strategy": IssuanceStrategy(),
        "data_vintage": "test",
    }
    no_spending = run_sequential_crisis_simulation(
        stock,
        assumptions,
        interest_income_rule=InterestIncomeRule(
            domestic_private_share=1.0,
            foreign_share=0.0,
            federal_reserve_share=0.0,
            domestic_private_spending_fraction=0.0,
        ),
        scenario_name="no_interest_spending",
        **common,
    )
    full_spending = run_sequential_crisis_simulation(
        stock,
        assumptions,
        interest_income_rule=InterestIncomeRule(
            domestic_private_share=1.0,
            foreign_share=0.0,
            federal_reserve_share=0.0,
            domestic_private_spending_fraction=1.0,
        ),
        scenario_name="full_interest_spending",
        **common,
    )

    assert full_spending.quarterly["incremental_cash_interest_billions"].max() > 0.0
    assert full_spending.quarterly["macro_feedback_output_gap"].max() > 0.0
    assert (
        full_spending.quarterly["annual_inflation_rate"].max()
        > no_spending.quarterly["annual_inflation_rate"].max()
    )
    assert (
        full_spending.quarterly["policy_rate_proxy"].max()
        > no_spending.quarterly["policy_rate_proxy"].max()
    )
    absorption = build_private_absorption_diagnostics(
        full_spending,
        PrivateAbsorptionRule(maximum_capacity_multiple=1.0),
    )
    assert summarize_private_absorption(absorption)["finite_private_absorption_capacity_exceeded"]


def test_inflation_is_recorded_above_twenty_percent_without_clipping(
    make_assumptions,
    make_cohort,
):
    assumptions = make_assumptions(
        periods=6,
        annual_inflation_rate=0.02,
        annual_tips_reference_inflation_rate=0.02,
    )
    supply_pressure = pd.Series(0.0, index=assumptions.index)
    supply_pressure.iloc[1:] = 0.30
    result = run_sequential_crisis_simulation(
        DebtStock([make_cohort(maturity="2030Q1")], 0.0),
        assumptions,
        initial_nominal_gdp_billions_saar=1_000.0,
        initial_real_gdp_billions_chained_saar=1_000.0,
        policy_rule=PolicyRule(
            inflation_response=0.0,
            output_gap_response=0.0,
            reaction_smoothing=0.0,
        ),
        feedback_rule=SequentialFeedbackRule(
            policy_tightening_output_semi_elasticity=0.0,
            automatic_stabilizer_semi_elasticity=0.0,
        ),
        supply_inflation_pressure_rate=supply_pressure,
        issuance_strategy=IssuanceStrategy(),
        scenario_name="unclipped_inflation",
        data_vintage="test",
    )

    assert result.quarterly["annual_inflation_rate"].max() > 0.20
    summary = summarize_crisis_path(result, inflation_ceiling=0.04, sustained_quarters=2)
    assert summary["inflation_ceiling_breached"]
    assert summary["inflation_ceiling_breached_sustained"]
    assert summary["first_sustained_inflation_ceiling_breach"] == "2026Q2"
