from __future__ import annotations

import pytest

from debt_sim.closure import (
    ClosureTarget,
    InflationEpisode,
    InflationRateResponse,
    apply_fiscal_adjustment,
    apply_inflation_episode,
    fiscal_inflation_frontier,
    solve_financial_repression,
    solve_fiscal_adjustment,
    solve_haircut_equivalent,
    solve_inflation_closure,
)
from debt_sim.debt_stock import DebtStock, IssuanceStrategy
from debt_sim.instruments import InstrumentType
from debt_sim.model import run_simulation


def solver_kwargs(strategy: IssuanceStrategy | None = None):
    return {
        "initial_nominal_gdp_billions_saar": 1000.0,
        "initial_real_gdp_billions_chained_saar": 1000.0,
        "issuance_strategy": strategy or IssuanceStrategy(),
        "data_vintage": "synthetic",
    }


def all_bill_strategy() -> IssuanceStrategy:
    return IssuanceStrategy(
        new_borrowing_shares={
            InstrumentType.BILL: 1.0,
            InstrumentType.NOTE: 0.0,
            InstrumentType.BOND: 0.0,
            InstrumentType.TIPS: 0.0,
            InstrumentType.FRN: 0.0,
        }
    )


def test_fiscal_solver_matches_one_period_analytical_solution(
    make_cohort, make_assumptions
):
    stock = DebtStock([make_cohort(principal=100.0, rate=0.0)], 0.0)
    assumptions = make_assumptions(primary_deficit_billions=10.0)
    solution = solve_fiscal_adjustment(
        stock,
        assumptions,
        target=ClosureTarget.specified_ratio(0.10),
        **solver_kwargs(),
    )
    # 10 - adjustment * 1000 / 4 = 0, so adjustment = 4% of GDP.
    assert solution.solved
    assert solution.value == pytest.approx(0.04, abs=1e-8)
    assert solution.evaluation.terminal_debt_gdp_ratio == pytest.approx(0.10)


def test_larger_fiscal_adjustment_cannot_raise_terminal_debt_ratio(
    make_cohort, make_assumptions
):
    stock = DebtStock([make_cohort(principal=500.0, rate=0.02)], 0.0)
    assumptions = make_assumptions(periods=8, primary_deficit_billions=5.0)
    terminal = []
    for adjustment in (0.0, 0.01, 0.02, 0.03):
        adjusted = apply_fiscal_adjustment(
            assumptions,
            adjustment,
            initial_nominal_gdp_billions_saar=1000.0,
        )
        result = run_simulation(stock, adjusted, **solver_kwargs()).quarterly
        terminal.append(result.iloc[-1]["debt_held_by_public_gdp_ratio"])
    assert all(
        later <= earlier for earlier, later in zip(terminal, terminal[1:], strict=False)
    )


def test_inflation_solver_matches_pure_denominator_result(make_cohort, make_assumptions):
    stock = DebtStock([make_cohort(principal=100.0, rate=0.0)], 0.0)
    assumptions = make_assumptions()
    episode = InflationEpisode(duration_quarters=1, shape="immediate_price_level")
    solution = solve_inflation_closure(
        stock,
        assumptions,
        episode=episode,
        target=ClosureTarget.specified_ratio(0.08),
        bounds=(0.0, 1.0),
        **solver_kwargs(),
    )
    assert solution.solved
    assert solution.value == pytest.approx(0.25, abs=1e-8)
    assert solution.diagnostics["denominator_effect_percentage_points"] == pytest.approx(-2.0)


def test_tips_require_more_inflation_for_same_target(make_cohort, make_assumptions):
    assumptions = make_assumptions(periods=4)
    episode = InflationEpisode(duration_quarters=4, shape="one_year")
    nominal = DebtStock([make_cohort(principal=100.0, rate=0.0)], 0.0)
    mixed = DebtStock(
        [
            make_cohort(principal=50.0, rate=0.0, cohort_id="nominal"),
            make_cohort(
                principal=50.0,
                rate=0.0,
                instrument_type=InstrumentType.TIPS,
                cohort_id="tips",
            ),
        ],
        0.0,
    )
    target = ClosureTarget.specified_ratio(0.08)
    nominal_solution = solve_inflation_closure(
        nominal,
        assumptions,
        episode=episode,
        target=target,
        bounds=(0.0, 2.0),
        **solver_kwargs(),
    )
    tips_solution = solve_inflation_closure(
        mixed,
        assumptions,
        episode=episode,
        target=target,
        bounds=(0.0, 2.0),
        **solver_kwargs(),
    )
    assert nominal_solution.solved and tips_solution.solved
    assert tips_solution.value > nominal_solution.value


def test_rate_pass_through_makes_inflation_closure_less_favorable(
    make_cohort, make_assumptions
):
    stock = DebtStock(
        [
            make_cohort(
                principal=100.0,
                rate=0.0,
                maturity="2026Q1",
                instrument_type=InstrumentType.BILL,
            )
        ],
        0.0,
    )
    assumptions = make_assumptions(
        periods=8,
        short_issuance_rate=0.0,
        intermediate_issuance_rate=0.0,
        long_issuance_rate=0.0,
        tips_real_issuance_rate=0.0,
    )
    target = ClosureTarget.specified_ratio(0.085)
    no_response = solve_inflation_closure(
        stock,
        assumptions,
        episode=InflationEpisode(duration_quarters=4, shape="one_year"),
        target=target,
        bounds=(0.0, 2.0),
        **solver_kwargs(all_bill_strategy()),
    )
    pass_through = solve_inflation_closure(
        stock,
        assumptions,
        episode=InflationEpisode(
            duration_quarters=4,
            shape="one_year",
                rate_response=InflationRateResponse.uniform(0.5),
        ),
        target=target,
        bounds=(0.0, 2.0),
        **solver_kwargs(all_bill_strategy()),
    )
    assert no_response.solved and pass_through.solved
    assert pass_through.value > no_response.value


def test_haircut_solver_recovers_known_reduction_and_stays_in_bounds(
    make_cohort, make_assumptions
):
    stock = DebtStock([make_cohort(principal=100.0, rate=0.0)], 0.0)
    solution = solve_haircut_equivalent(
        stock,
        make_assumptions(),
        target=ClosureTarget.specified_ratio(0.08),
        **solver_kwargs(),
    )
    assert solution.solved
    assert solution.value == pytest.approx(0.20, abs=1e-8)
    assert 0.0 <= solution.value <= 1.0


def test_repression_solver_matches_predictable_interest_savings(
    make_cohort, make_assumptions
):
    stock = DebtStock(
        [
            make_cohort(
                principal=100.0,
                rate=0.04,
                maturity="2026Q1",
                instrument_type=InstrumentType.BILL,
            )
        ],
        0.0,
    )
    assumptions = make_assumptions(
        periods=2,
        primary_deficit_billions=-1.0,
        short_issuance_rate=0.04,
        intermediate_issuance_rate=0.04,
        long_issuance_rate=0.04,
        tips_real_issuance_rate=0.0,
    )
    solution = solve_financial_repression(
        stock,
        assumptions,
        target=ClosureTarget.specified_ratio(0.0995),
        bounds_basis_points=(0.0, 400.0),
        **solver_kwargs(all_bill_strategy()),
    )
    assert solution.solved
    assert solution.value == pytest.approx(200.0, abs=1e-5)
    assert solution.diagnostics["cumulative_interest_savings_vs_baseline_billions"] == (
        pytest.approx(0.5, abs=1e-6)
    )


def test_no_solution_reports_boundary_diagnostics(make_cohort, make_assumptions):
    stock = DebtStock([make_cohort(principal=100.0, rate=0.0)], 0.0)
    assumptions = make_assumptions(primary_deficit_billions=10.0)
    solution = solve_haircut_equivalent(
        stock,
        assumptions,
        target=ClosureTarget.specified_ratio(0.0),
        **solver_kwargs(),
    )
    assert solution.status == "no_solution"
    assert solution.value is None
    assert solution.boundary_evaluation.terminal_debt_gdp_ratio > 0.0


def test_every_mixed_frontier_point_meets_target(make_cohort, make_assumptions):
    stock = DebtStock([make_cohort(principal=100.0, rate=0.0)], 0.0)
    assumptions = make_assumptions(primary_deficit_billions=10.0)
    frontier = fiscal_inflation_frontier(
        stock,
        assumptions,
        fiscal_adjustments=[0.0, 0.02, 0.04],
        episode=InflationEpisode(duration_quarters=1, shape="immediate_price_level"),
        target=ClosureTarget.specified_ratio(0.10),
        inflation_bounds=(0.0, 1.0),
        **solver_kwargs(),
    )
    assert frontier["satisfies_target"].all()
    assert frontier["target_gap"].abs().max() < 1e-7


def test_inflation_episode_changes_gdp_tips_and_rates_through_existing_inputs(
    make_assumptions,
):
    assumptions = make_assumptions(periods=6)
    episode = InflationEpisode(
        duration_quarters=4,
        shape="one_year",
        rate_response=InflationRateResponse.uniform(0.5, lag_quarters=2),
    )
    shocked = apply_inflation_episode(
        assumptions,
        0.10,
        episode,
        initial_nominal_gdp_billions_saar=1000.0,
    )
    assert (shocked.iloc[:4]["annual_inflation_rate"] > 0).all()
    assert (shocked.iloc[1:5]["annual_tips_reference_inflation_rate"] > 0).all()
    assert shocked.iloc[0]["short_issuance_rate"] == assumptions.iloc[0]["short_issuance_rate"]
    assert shocked.iloc[2]["short_issuance_rate"] > assumptions.iloc[2]["short_issuance_rate"]
