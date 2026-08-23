from __future__ import annotations

import pytest

from debt_sim.debt_stock import DebtStock


def test_debt_identity_reconciles_with_zero_other_financing(
    make_cohort, make_assumptions, run_small
):
    stock = DebtStock([make_cohort(principal=100.0, rate=0.04)], 0.0)
    assumptions = make_assumptions(periods=8, primary_deficit_billions=3.0)
    result = run_small(stock, assumptions).quarterly
    assert result["debt_identity_residual_billions"].abs().max() < 1e-9
    assert result.iloc[-1]["debt_held_by_public_billions"] == pytest.approx(
        100.0
        + result["modeled_total_deficit_billions"].sum()
        + result["other_financing_adjustment_billions"].sum()
    )


def test_zero_primary_deficit_finances_interest_predictably(
    make_cohort, make_assumptions, run_small
):
    stock = DebtStock([make_cohort(principal=100.0, rate=0.04)], 0.0)
    result = run_small(stock, make_assumptions()).quarterly.iloc[0]
    assert result["primary_deficit_billions"] == 0.0
    assert result["modeled_debt_interest_cost_billions"] == pytest.approx(1.0)
    assert result["genuinely_new_borrowing_billions"] == pytest.approx(1.0)
    assert result["debt_held_by_public_billions"] == pytest.approx(101.0)


def test_refinancing_principal_is_not_a_deficit(make_cohort, make_assumptions, run_small):
    stock = DebtStock([make_cohort(principal=100.0, rate=0.0, maturity="2026Q1")], 0.0)
    row = run_small(
        stock,
        make_assumptions(
            intermediate_issuance_rate=0.0,
            short_issuance_rate=0.0,
            long_issuance_rate=0.0,
            tips_real_issuance_rate=0.0,
        ),
    ).quarterly.iloc[0]
    assert row["principal_maturing_billions"] == pytest.approx(100.0)
    assert row["principal_refinanced_billions"] == pytest.approx(100.0)
    assert row["genuinely_new_borrowing_billions"] == pytest.approx(0.0)
    assert row["modeled_total_deficit_billions"] == pytest.approx(0.0)
    assert row["debt_held_by_public_billions"] == pytest.approx(100.0)


def test_other_financing_is_explicit_in_debt_change(make_cohort, make_assumptions, run_small):
    stock = DebtStock([make_cohort(rate=0.0)], 0.0)
    row = run_small(
        stock,
        make_assumptions(primary_deficit_billions=2.0, other_financing_adjustment_billions=3.0),
    ).quarterly.iloc[0]
    assert row["modeled_total_deficit_billions"] == pytest.approx(2.0)
    assert row["debt_held_by_public_billions"] == pytest.approx(105.0)


def test_primary_surplus_reports_retirement_not_negative_new_borrowing(
    make_cohort, make_assumptions, run_small
):
    stock = DebtStock([make_cohort(principal=100.0, rate=0.0)], 0.0)
    row = run_small(
        stock,
        make_assumptions(primary_deficit_billions=-4.0),
    ).quarterly.iloc[0]
    assert row["net_new_borrowing_requirement_billions"] == pytest.approx(-4.0)
    assert row["genuinely_new_borrowing_billions"] == pytest.approx(0.0)
    assert row["debt_repayment_billions"] == pytest.approx(4.0)
    assert row["debt_held_by_public_billions"] == pytest.approx(96.0)


def test_quarterly_output_exposes_required_semantic_distinctions(
    make_cohort, make_assumptions, run_small
):
    stock = DebtStock([make_cohort()], 10.0)
    columns = set(run_small(stock, make_assumptions()).quarterly.columns)
    assert {
        "quarter",
        "calendar_year",
        "fiscal_year",
        "nominal_gdp_billions_saar",
        "primary_deficit_billions",
        "modeled_debt_interest_cost_billions",
        "modeled_total_deficit_billions",
        "other_financing_adjustment_billions",
        "debt_held_by_public_billions",
        "marketable_debt_billions",
        "other_public_debt_billions",
        "principal_maturing_billions",
        "principal_refinanced_billions",
        "net_new_borrowing_requirement_billions",
        "genuinely_new_borrowing_billions",
        "average_new_issuance_stated_rate",
        "share_marketable_debt_repriced_since_scenario_start",
    } <= columns
