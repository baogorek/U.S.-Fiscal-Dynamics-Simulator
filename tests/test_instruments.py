from __future__ import annotations

import pytest

from debt_sim.debt_stock import DebtStock
from debt_sim.instruments import InstrumentType


def test_frn_resets_without_waiting_for_maturity(make_cohort, make_assumptions, run_small):
    stock = DebtStock(
        [
            make_cohort(
                instrument_type=InstrumentType.FRN,
                rate=0.02,
                maturity="2028Q1",
                frn_spread=0.001,
            )
        ],
        0.0,
    )
    row = run_small(
        stock,
        make_assumptions(short_issuance_rate=0.08, primary_deficit_billions=-2.025),
    ).quarterly.iloc[0]
    assert row["frn_principal_reset_billions"] == pytest.approx(100.0)
    assert row["modeled_debt_interest_cost_billions"] == pytest.approx(2.025)
    assert row["share_marketable_debt_repriced_since_scenario_start"] == 1.0


def test_tips_inflation_adjusts_principal_and_budget_interest(
    make_cohort, make_assumptions, run_small
):
    tips_stock = DebtStock([make_cohort(instrument_type=InstrumentType.TIPS, rate=0.0)], 0.0)
    nominal_stock = DebtStock([make_cohort(instrument_type=InstrumentType.NOTE, rate=0.0)], 0.0)
    assumptions = make_assumptions(
        annual_tips_reference_inflation_rate=0.15,
        short_issuance_rate=0.0,
        intermediate_issuance_rate=0.0,
        long_issuance_rate=0.0,
        tips_real_issuance_rate=0.0,
    )
    tips = run_small(tips_stock, assumptions).quarterly.iloc[0]
    nominal = run_small(nominal_stock, assumptions).quarterly.iloc[0]
    quarterly_inflation = 1.15**0.25 - 1.0
    assert tips["tips_inflation_compensation_billions"] == pytest.approx(
        100.0 * quarterly_inflation
    )
    assert tips["tips_outstanding_billions"] == pytest.approx(100.0 * (1.0 + quarterly_inflation))
    assert nominal["nominal_fixed_rate_debt_outstanding_billions"] == pytest.approx(100.0)
    assert tips["debt_held_by_public_billions"] > nominal["debt_held_by_public_billions"]


def test_tips_deflation_floor_applies_at_maturity(make_cohort, make_assumptions, run_small):
    stock = DebtStock(
        [
            make_cohort(
                instrument_type=InstrumentType.TIPS,
                rate=0.0,
                maturity="2026Q1",
            )
        ],
        0.0,
    )
    row = run_small(
        stock,
        make_assumptions(
            annual_tips_reference_inflation_rate=-0.10,
            tips_real_issuance_rate=0.0,
        ),
    ).quarterly.iloc[0]
    assert row["tips_deflation_floor_cost_billions"] > 0
    assert row["principal_refinanced_billions"] == pytest.approx(100.0)
    assert row["debt_identity_residual_billions"] == pytest.approx(0.0, abs=1e-9)
