import numpy as np
import pytest

from debt_sim.fiscal_space import LinearFinancingEnvironment


def test_two_fixed_points_have_opposite_stability():
    model = LinearFinancingEnvironment()
    points = model.fixed_points(0.008)
    assert [p.stability for p in points] == ["stable", "unstable"]
    assert [p.debt_gdp_ratio for p in points] == pytest.approx([0.59012197, 1.40987803])
    for point in points:
        assert model.steady_primary_deficit(point.debt_gdp_ratio) == pytest.approx(0.008)


def test_fixed_points_merge_then_disappear_without_any_quantity_ceiling():
    model = LinearFinancingEnvironment()
    limit = model.maximum_steady_primary_deficit
    assert limit == pytest.approx(0.01 / 1.04)
    assert model.debt_at_maximum_deficit == pytest.approx(1)
    assert model.fixed_points(limit)[0].stability == "marginal"
    assert len(model.fixed_points(limit)) == 1
    assert model.fixed_points(limit + 0.001) == []
    assert all(limit + 0.001 > model.steady_primary_deficit(b) for b in np.linspace(0, 4, 101))


def test_same_deficit_converges_or_diverges_from_different_inherited_debt():
    model = LinearFinancingEnvironment()
    for initial, sign in [(1.0, -1), (1.6, 1)]:
        path = model.simulate(
            initial_debt_gdp_ratio=initial, primary_deficit_gdp_share=0.008, years=80,
        )
        assert (sign * path.next_year_debt_ratio_change > 0).all()


def test_interest_below_growth_is_not_sufficient():
    model = LinearFinancingEnvironment()
    assert model.interest_rate(1) < model.nominal_growth
    assert model.fixed_points(0.0125) == []


def test_no_positive_deficit_supported_when_rates_always_exceed_growth():
    model = LinearFinancingEnvironment(anchor_interest_rate=0.06)
    assert model.maximum_steady_primary_deficit == 0
    assert model.fixed_points(0.001) == []
