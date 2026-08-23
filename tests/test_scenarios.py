from __future__ import annotations

import pandas as pd
import pytest

from debt_sim.data import load_baseline_bundle
from debt_sim.debt_stock import DebtStock
from debt_sim.model import run_simulation, validate_assumptions
from debt_sim.scenarios import (
    apply_manual_primary_deficit,
    build_baseline_scenario,
    compare_scenarios,
)


def test_same_configuration_is_reproducible(make_cohort, make_assumptions):
    kwargs = {
        "initial_nominal_gdp_billions_saar": 1000.0,
        "initial_real_gdp_billions_chained_saar": 1000.0,
        "scenario_name": "repeat",
        "data_vintage": "fixed",
    }
    assumptions = make_assumptions(periods=6, annual_inflation_rate=0.05)
    first = run_simulation(DebtStock([make_cohort()], 0.0), assumptions, **kwargs)
    second = run_simulation(DebtStock([make_cohort()], 0.0), assumptions, **kwargs)
    pd.testing.assert_frame_equal(first.quarterly, second.quarterly, check_exact=True)


@pytest.mark.parametrize(
    ("inflation", "rate", "primary"),
    [
        (0.0, 0.0, 0.0),
        (-0.02, 0.04, 0.0),
        (0.20, 0.04, 0.0),
        (0.02, 0.50, 0.0),
        (0.02, 0.04, -5.0),
    ],
)
def test_extreme_but_valid_inputs_remain_coherent(
    inflation, rate, primary, make_cohort, make_assumptions, run_small
):
    assumptions = make_assumptions(
        periods=4,
        annual_inflation_rate=inflation,
        annual_tips_reference_inflation_rate=inflation,
        short_issuance_rate=rate,
        intermediate_issuance_rate=rate,
        long_issuance_rate=rate,
        primary_deficit_billions=primary,
    )
    result = run_small(DebtStock([make_cohort(principal=500.0, rate=0.02)], 0.0), assumptions)
    assert result.quarterly["debt_held_by_public_billions"].ge(0).all()
    assert result.quarterly["debt_identity_residual_billions"].abs().max() < 1e-8


def test_nonsensical_input_is_rejected(make_assumptions):
    bad_inflation = make_assumptions(annual_inflation_rate=-1.0)
    with pytest.raises(ValueError, match="greater than -100%"):
        validate_assumptions(bad_inflation)
    bad_rate = make_assumptions(short_issuance_rate=-0.01)
    with pytest.raises(ValueError, match="cannot be negative"):
        validate_assumptions(bad_rate)


def test_manual_primary_deficit_supports_nominal_and_gdp_share_modes():
    bundle = load_baseline_bundle()
    baseline = build_baseline_scenario(bundle, start_period="2027Q1", end_period="2027Q2")
    nominal = apply_manual_primary_deficit(
        baseline,
        bundle,
        mode="annual_nominal_billions",
        value=800.0,
    )
    share = apply_manual_primary_deficit(
        baseline,
        bundle,
        mode="percent_gdp",
        value=0.025,
    )
    assert nominal.quarterly_assumptions["primary_deficit_billions"].tolist() == [200.0, 200.0]
    assert (share.quarterly_assumptions["primary_deficit_billions"] > 0).all()
    assert share.imposed_parameters["manual_primary_deficit_mode"] == "percent_gdp"


def test_ratio_decomposition_reconciles_exactly(make_cohort, make_assumptions):
    assumptions = make_assumptions(periods=2)
    baseline = run_simulation(
        DebtStock([make_cohort(principal=100.0, rate=0.0)], 0.0),
        assumptions,
        initial_nominal_gdp_billions_saar=1000.0,
        initial_real_gdp_billions_chained_saar=1000.0,
    ).quarterly
    scenario_assumptions = assumptions.copy()
    scenario_assumptions["annual_inflation_rate"] = 0.10
    scenario_assumptions["primary_deficit_billions"] = 2.0
    scenario = run_simulation(
        DebtStock([make_cohort(principal=100.0, rate=0.0)], 0.0),
        scenario_assumptions,
        initial_nominal_gdp_billions_saar=1000.0,
        initial_real_gdp_billions_chained_saar=1000.0,
    ).quarterly
    comparison = compare_scenarios(baseline, scenario)
    attributed = (
        comparison["debt_gdp_difference_from_nominal_debt"]
        + comparison["debt_gdp_difference_from_nominal_gdp"]
    )
    pd.testing.assert_series_equal(
        attributed,
        comparison["difference_debt_held_by_public_gdp_ratio"],
        check_names=False,
        atol=1e-14,
        rtol=1e-14,
    )
