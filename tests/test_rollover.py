from __future__ import annotations

import pandas as pd
import pytest

from debt_sim.debt_stock import DebtStock
from debt_sim.instruments import InstrumentType


def test_fixed_rate_bond_cost_rises_only_after_refinancing(
    make_cohort, make_assumptions, run_small
):
    stock = DebtStock(
        [make_cohort(rate=0.02, maturity="2026Q1", instrument_type=InstrumentType.NOTE)],
        0.0,
    )
    assumptions = make_assumptions(periods=2, intermediate_issuance_rate=0.08)
    assumptions["primary_deficit_billions"] = [-0.5, -2.0]
    result = run_small(stock, assumptions).quarterly
    assert result.iloc[0]["modeled_debt_interest_cost_billions"] == pytest.approx(0.5)
    assert result.iloc[0]["principal_refinanced_billions"] == pytest.approx(100.0)
    assert result.iloc[1]["modeled_debt_interest_cost_billions"] == pytest.approx(2.0)


def test_rate_shock_does_not_instantly_reprice_fixed_debt(make_cohort, make_assumptions, run_small):
    stock = DebtStock([make_cohort(rate=0.02, maturity="2030Q1")], 0.0)
    row = run_small(
        stock,
        make_assumptions(intermediate_issuance_rate=0.20, primary_deficit_billions=-0.5),
    ).quarterly.iloc[0]
    assert row["modeled_debt_interest_cost_billions"] == pytest.approx(0.5)
    assert row["share_marketable_debt_repriced_since_scenario_start"] == 0.0


def test_bills_reprice_faster_than_long_bonds(make_cohort, make_assumptions, run_small):
    bill = DebtStock(
        [
            make_cohort(
                instrument_type=InstrumentType.BILL,
                rate=0.02,
                maturity="2026Q1",
            )
        ],
        0.0,
    )
    bond = DebtStock(
        [
            make_cohort(
                instrument_type=InstrumentType.BOND,
                rate=0.02,
                maturity="2040Q1",
            )
        ],
        0.0,
    )
    bill_path = make_assumptions(
        periods=2,
        short_issuance_rate=0.08,
        long_issuance_rate=0.08,
    )
    bond_path = bill_path.copy()
    bill_path["primary_deficit_billions"] = [-0.5, -2.0]
    bond_path["primary_deficit_billions"] = [-0.5, -0.5]
    bill_result = run_small(bill, bill_path).quarterly
    bond_result = run_small(bond, bond_path).quarterly
    assert bill_result.iloc[1]["modeled_debt_interest_cost_billions"] == pytest.approx(2.0)
    assert bond_result.iloc[1]["modeled_debt_interest_cost_billions"] == pytest.approx(0.5)
    assert bill_result.iloc[1]["share_marketable_debt_repriced_since_scenario_start"] == 1.0
    assert bond_result.iloc[1]["share_marketable_debt_repriced_since_scenario_start"] == 0.0


def test_fiscal_year_mapping_is_not_calendar_year_mapping():
    from debt_sim.economy import federal_fiscal_year

    assert federal_fiscal_year(pd.Period("2025Q4", freq="Q")) == 2026
    assert federal_fiscal_year(pd.Period("2026Q3", freq="Q")) == 2026
