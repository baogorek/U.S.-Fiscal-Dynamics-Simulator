from __future__ import annotations

import pandas as pd
import pytest

from debt_sim.debt_stock import DebtStock, IssuanceStrategy
from debt_sim.instruments import InstrumentType, TreasuryCohort


@pytest.fixture
def make_cohort():
    def factory(
        *,
        instrument_type: InstrumentType = InstrumentType.NOTE,
        principal: float = 100.0,
        rate: float = 0.02,
        issue: str = "2025Q1",
        maturity: str = "2030Q1",
        cohort_id: str = "test-cohort",
        frn_spread: float = 0.0,
    ) -> TreasuryCohort:
        return TreasuryCohort(
            cohort_id=cohort_id,
            instrument_type=instrument_type,
            issue_period=pd.Period(issue, freq="Q"),
            maturity_period=pd.Period(maturity, freq="Q"),
            principal_billions=principal,
            original_principal_billions=principal,
            coupon_rate=0.0 if instrument_type is InstrumentType.BILL else max(rate, 0.0),
            effective_interest_rate=rate,
            frn_spread=frn_spread,
        )

    return factory


@pytest.fixture
def make_assumptions():
    def factory(start: str = "2026Q1", periods: int = 1, **overrides: float) -> pd.DataFrame:
        index = pd.period_range(start, periods=periods, freq="Q")
        defaults = {
            "annual_real_gdp_growth_rate": 0.0,
            "annual_inflation_rate": 0.0,
            "annual_tips_reference_inflation_rate": 0.0,
            "primary_deficit_billions": 0.0,
            "other_financing_adjustment_billions": 0.0,
            "short_issuance_rate": 0.04,
            "intermediate_issuance_rate": 0.04,
            "long_issuance_rate": 0.04,
            "tips_real_issuance_rate": 0.02,
            "new_frn_spread": 0.001,
            "other_public_debt_interest_rate": 0.0,
        }
        defaults.update(overrides)
        return pd.DataFrame(
            {key: [value] * periods for key, value in defaults.items()},
            index=index,
        )

    return factory


@pytest.fixture
def run_small():
    from debt_sim.model import run_simulation

    def runner(stock: DebtStock, assumptions: pd.DataFrame):
        return run_simulation(
            stock,
            assumptions,
            initial_nominal_gdp_billions_saar=1000.0,
            initial_real_gdp_billions_chained_saar=1000.0,
            issuance_strategy=IssuanceStrategy(),
            scenario_name="test",
            data_vintage="test",
        )

    return runner
