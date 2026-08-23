from __future__ import annotations

import pytest

from debt_sim.confidence import ConfidenceShock, apply_confidence_shock


def test_confidence_shock_imposes_rates_and_recession_without_changing_fiscal_inputs(
    make_assumptions,
):
    baseline = make_assumptions(
        periods=12,
        annual_real_gdp_growth_rate=0.015,
        annual_inflation_rate=0.02,
        primary_deficit_billions=7.0,
        short_issuance_rate=0.03,
        intermediate_issuance_rate=0.04,
        long_issuance_rate=0.05,
        tips_real_issuance_rate=0.01,
    )
    stressed = apply_confidence_shock(
        baseline,
        ConfidenceShock(500.0, duration_quarters=12),
    )
    assert (stressed.iloc[:4]["annual_real_gdp_growth_rate"] == -0.02).all()
    assert (stressed.iloc[4:8]["annual_real_gdp_growth_rate"] == 0.0).all()
    assert (stressed.iloc[8:]["annual_real_gdp_growth_rate"] == 0.015).all()
    assert stressed.iloc[0]["short_issuance_rate"] == pytest.approx(0.08)
    assert stressed.iloc[0]["intermediate_issuance_rate"] == pytest.approx(0.09)
    assert stressed.iloc[0]["long_issuance_rate"] == pytest.approx(0.10)
    assert stressed.iloc[0]["tips_real_issuance_rate"] == pytest.approx(0.06)
    assert stressed["annual_inflation_rate"].equals(baseline["annual_inflation_rate"])
    assert stressed["primary_deficit_billions"].equals(baseline["primary_deficit_billions"])


def test_confidence_shock_rejects_a_duration_beyond_the_supplied_path(make_assumptions):
    with pytest.raises(ValueError, match="duration exceeds"):
        apply_confidence_shock(
            make_assumptions(periods=8),
            ConfidenceShock(500.0, duration_quarters=9),
        )
