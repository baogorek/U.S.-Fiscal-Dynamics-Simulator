from __future__ import annotations

import pandas as pd
import pytest

from debt_sim.debt_stock import DebtStock, IssuanceRates, IssuanceStrategy
from debt_sim.instruments import InstrumentType
from debt_sim.model import run_simulation
from debt_sim.treasury import (
    TreasuryBuybackInstruction,
    adaptive_issuance_strategy,
    build_adaptive_issuance_strategy_path,
    execute_treasury_buyback,
    fixed_rate_price_per_dollar_face,
)


def test_adaptive_issuance_shifts_only_after_trigger_and_respects_bill_cap():
    base = IssuanceStrategy()

    unchanged = adaptive_issuance_strategy(base, 100.0)
    stressed = adaptive_issuance_strategy(base, 500.0)
    capped = adaptive_issuance_strategy(base, 2_000.0)

    assert unchanged is base
    assert stressed.new_borrowing_shares[InstrumentType.BILL] == pytest.approx(0.42)
    assert stressed.new_borrowing_shares[InstrumentType.NOTE] < 0.52
    assert stressed.new_borrowing_shares[InstrumentType.BOND] < 0.17
    assert sum(stressed.new_borrowing_shares.values()) == pytest.approx(1.0)
    assert capped.new_borrowing_shares[InstrumentType.BILL] == pytest.approx(0.50)


def test_fixed_rate_buyback_price_reflects_coupon_market_yield_gap(make_cohort):
    period = pd.Period("2026Q1", freq="Q")
    low_coupon = make_cohort(issue="2020Q1", maturity="2040Q1", rate=0.02)
    high_coupon = make_cohort(issue="2020Q1", maturity="2040Q1", rate=0.08)

    assert fixed_rate_price_per_dollar_face(low_coupon, period, 0.06) < 1.0
    assert fixed_rate_price_per_dollar_face(high_coupon, period, 0.04) > 1.0


def test_buyback_uses_market_value_and_retires_selected_face_value(make_cohort):
    period = pd.Period("2026Q1", freq="Q")
    stock = DebtStock(
        [make_cohort(issue="2020Q1", maturity="2040Q1", rate=0.02)],
        0.0,
    )
    result = execute_treasury_buyback(
        stock,
        period,
        TreasuryBuybackInstruction(cash_limit_billions=50.0),
        IssuanceRates(0.06, 0.06, 0.06, 0.03),
    )

    assert result.cash_spent_billions == pytest.approx(50.0)
    assert result.face_value_retired_billions > result.cash_spent_billions
    assert result.premium_or_discount_billions < 0.0
    assert result.weighted_price_per_dollar_face < 1.0
    assert stock.marketable_debt_billions == pytest.approx(
        100.0 - result.face_value_retired_billions
    )


def test_par_value_capacity_is_distinct_from_buyback_cash_spent(make_cohort):
    period = pd.Period("2026Q1", freq="Q")
    stock = DebtStock(
        [make_cohort(issue="2020Q1", maturity="2040Q1", rate=0.02)],
        0.0,
    )
    result = execute_treasury_buyback(
        stock,
        period,
        TreasuryBuybackInstruction(maximum_face_value_billions=16.0),
        IssuanceRates(0.06, 0.06, 0.06, 0.03),
    )

    assert result.face_value_retired_billions == pytest.approx(16.0)
    assert result.cash_spent_billions < 16.0
    assert result.unfilled_face_value_limit_billions == pytest.approx(0.0)


def test_buyback_financing_is_gross_issuance_not_a_deficit(
    make_cohort,
    make_assumptions,
):
    period = pd.Period("2026Q1", freq="Q")
    stock = DebtStock(
        [make_cohort(issue="2020Q1", maturity="2040Q1", rate=0.02)],
        0.0,
    )
    assumptions = make_assumptions(
        intermediate_issuance_rate=0.06,
        short_issuance_rate=0.06,
        long_issuance_rate=0.06,
        tips_real_issuance_rate=0.03,
    )
    row = run_simulation(
        stock,
        assumptions,
        initial_nominal_gdp_billions_saar=1_000.0,
        initial_real_gdp_billions_chained_saar=1_000.0,
        issuance_strategy=IssuanceStrategy(),
        treasury_buyback_plan={period: TreasuryBuybackInstruction(cash_limit_billions=50.0)},
        scenario_name="buyback_test",
        data_vintage="test",
    ).quarterly.iloc[0]

    face_retired = row["treasury_buyback_face_value_retired_billions"]
    assert face_retired > 50.0
    assert row["treasury_buyback_financing_issuance_billions"] == pytest.approx(50.0)
    assert row["treasury_buyback_financing_instrument"] == InstrumentType.BILL.value
    assert row["genuinely_new_borrowing_billions"] == pytest.approx(0.5)
    assert row["gross_treasury_issuance_billions"] == pytest.approx(50.5)
    assert row["debt_held_by_public_billions"] == pytest.approx(100.0 + 0.5 + 50.0 - face_retired)
    assert row["debt_identity_residual_billions"] == pytest.approx(0.0, abs=1e-10)


def test_strategy_path_changes_reported_new_borrowing_mix(
    make_cohort,
    make_assumptions,
):
    assumptions = make_assumptions(periods=2, primary_deficit_billions=10.0)
    pressure = pd.Series([0.0, 500.0], index=assumptions.index)
    path = build_adaptive_issuance_strategy_path(IssuanceStrategy(), pressure)
    result = run_simulation(
        DebtStock([make_cohort(maturity="2040Q1")], 0.0),
        assumptions,
        initial_nominal_gdp_billions_saar=1_000.0,
        initial_real_gdp_billions_chained_saar=1_000.0,
        issuance_strategy=IssuanceStrategy(),
        issuance_strategy_path=path,
        scenario_name="adaptive_issuance_test",
        data_vintage="test",
    ).quarterly

    assert result.iloc[0]["new_borrowing_bill_share"] == pytest.approx(0.22)
    assert result.iloc[1]["new_borrowing_bill_share"] == pytest.approx(0.42)


def test_quarter_can_execute_separate_long_end_buyback_buckets(
    make_cohort,
    make_assumptions,
):
    period = pd.Period("2026Q1", freq="Q")
    stock = DebtStock(
        [
            make_cohort(
                cohort_id="ten-to-twenty-year",
                issue="2020Q1",
                maturity="2040Q1",
                rate=0.02,
            ),
            make_cohort(
                cohort_id="twenty-to-thirty-year",
                instrument_type=InstrumentType.BOND,
                issue="2020Q1",
                maturity="2050Q1",
                rate=0.03,
            ),
        ],
        0.0,
    )
    row = run_simulation(
        stock,
        make_assumptions(),
        initial_nominal_gdp_billions_saar=1_000.0,
        initial_real_gdp_billions_chained_saar=1_000.0,
        issuance_strategy=IssuanceStrategy(),
        treasury_buyback_plan={
            period: (
                TreasuryBuybackInstruction(
                    maximum_face_value_billions=16.0,
                    minimum_remaining_quarters=40,
                    maximum_remaining_quarters=79,
                ),
                TreasuryBuybackInstruction(
                    maximum_face_value_billions=16.0,
                    minimum_remaining_quarters=80,
                    maximum_remaining_quarters=120,
                ),
            )
        },
        scenario_name="bucket_test",
        data_vintage="test",
    ).quarterly.iloc[0]

    assert row["treasury_buyback_operation_count"] == 2
    assert row["treasury_buyback_face_value_limit_billions"] == pytest.approx(32.0)
    assert row["treasury_buyback_face_value_retired_billions"] == pytest.approx(32.0)
    assert row["treasury_buyback_notes_retired_billions"] == pytest.approx(16.0)
    assert row["treasury_buyback_bonds_retired_billions"] == pytest.approx(16.0)
    assert row["treasury_buyback_financing_issuance_billions"] == pytest.approx(
        row["treasury_buyback_cash_spent_billions"]
    )


def test_buyback_reports_unfilled_limit_when_no_security_is_eligible(make_cohort):
    period = pd.Period("2026Q1", freq="Q")
    stock = DebtStock([make_cohort(maturity="2030Q1")], 0.0)

    result = execute_treasury_buyback(
        stock,
        period,
        TreasuryBuybackInstruction(cash_limit_billions=4.0),
        IssuanceRates(0.04, 0.04, 0.04, 0.02),
    )

    assert result.cash_spent_billions == 0.0
    assert result.unfilled_cash_limit_billions == pytest.approx(4.0)
    assert stock.marketable_debt_billions == pytest.approx(100.0)
