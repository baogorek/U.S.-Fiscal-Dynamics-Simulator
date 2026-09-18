import pandas as pd
import pytest

from debt_sim.debt_stock import DebtStock
from debt_sim.sustainability import constant_policy_debt_path, decompose_debt_ratio


def test_permanent_primary_deficit_can_have_stable_positive_debt():
    # A one-percent primary deficit is exactly financed by the growth-interest
    # advantage on debt of 104% of GDP: this is a no-crisis counterexample.
    path = constant_policy_debt_path(
        initial_debt_gdp_ratio=1.04, primary_deficit_gdp_share=0.01,
        nominal_interest_rate=0.03, nominal_gdp_growth=0.04, years=100,
    )
    assert path.debt_gdp_ratio.to_numpy() == pytest.approx([1.04] * 101)


def test_equal_interest_and_growth_produce_linear_debt_growth():
    path = constant_policy_debt_path(
        initial_debt_gdp_ratio=1.0, primary_deficit_gdp_share=0.025,
        nominal_interest_rate=0.04, nominal_gdp_growth=0.04, years=30,
    )
    assert path.debt_gdp_ratio.iloc[-1] == pytest.approx(1.75)


def test_decomposition_reconciles_indexation_and_other_financing(
    make_assumptions, make_cohort, run_small,
):
    from debt_sim.instruments import InstrumentType

    result = run_small(
        DebtStock([make_cohort(instrument_type=InstrumentType.TIPS)], 10.0),
        make_assumptions(
            periods=8, annual_real_gdp_growth_rate=0.02, annual_inflation_rate=0.03,
            annual_tips_reference_inflation_rate=0.03, primary_deficit_billions=2.0,
            other_financing_adjustment_billions=-0.25,
        ),
    )
    diagnostic = decompose_debt_ratio(
        result.quarterly, initial_nominal_gdp_billions_saar=1000.0,
    )
    assert diagnostic.decomposition_residual.abs().max() < 1e-12
    assert diagnostic.growth_contribution.lt(0).all()
    assert diagnostic.other_financing_contribution.lt(0).all()
    # A fiscal improvement equal to the local gap holds next-quarter debt/GDP
    # fixed when the inherited rates, growth, and other financing are held fixed.
    first = result.quarterly.iloc[0]
    adjustment = diagnostic.local_primary_improvement_gdp_share_annualized.iloc[0]
    adjusted_debt = (
        first.debt_held_by_public_billions
        - adjustment * first.nominal_gdp_billions_saar / 4.0
    )
    assert adjusted_debt / first.nominal_gdp_billions_saar == pytest.approx(0.11)


def test_decomposition_rejects_out_of_order_quarters():
    with pytest.raises(ValueError, match="chronological"):
        decompose_debt_ratio(
            pd.DataFrame({"quarter": ["2026Q2", "2026Q1"]}),
            initial_nominal_gdp_billions_saar=1000.0,
        )


def test_gross_rollover_does_not_increase_debt(make_assumptions, make_cohort, run_small):
    from debt_sim.instruments import InstrumentType

    assumptions = make_assumptions(
        short_issuance_rate=0.0, intermediate_issuance_rate=0.0, long_issuance_rate=0.0,
    )
    results = [
        run_small(DebtStock([cohort], 0.0), assumptions)
        for cohort in (
            make_cohort(instrument_type=InstrumentType.BILL, maturity="2026Q1", rate=0.0),
            make_cohort(maturity="2030Q1", rate=0.0),
        )
    ]
    assert results[0].quarterly.gross_treasury_issuance_billions.iloc[0] == pytest.approx(100)
    assert results[1].quarterly.gross_treasury_issuance_billions.iloc[0] == pytest.approx(0)
    for result in results:
        diagnostic = decompose_debt_ratio(
            result.quarterly, initial_nominal_gdp_billions_saar=1000.0,
        )
        assert diagnostic.debt_ratio_change.iloc[0] == pytest.approx(0)
