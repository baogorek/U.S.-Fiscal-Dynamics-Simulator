from __future__ import annotations

from debt_sim.debt_stock import DebtStock


def test_higher_inflation_lowers_debt_gdp_through_denominator(
    make_cohort, make_assumptions, run_small
):
    stock_zero = DebtStock([make_cohort(rate=0.0)], 0.0)
    stock_high = DebtStock([make_cohort(rate=0.0)], 0.0)
    zero = run_small(stock_zero, make_assumptions()).quarterly.iloc[0]
    high = run_small(stock_high, make_assumptions(annual_inflation_rate=0.20)).quarterly.iloc[0]
    assert high["debt_held_by_public_billions"] == zero["debt_held_by_public_billions"]
    assert high["nominal_gdp_billions_saar"] > zero["nominal_gdp_billions_saar"]
    assert high["debt_held_by_public_gdp_ratio"] < zero["debt_held_by_public_gdp_ratio"]
