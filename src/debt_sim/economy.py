"""Quarterly nominal-GDP accounting and calendar/fiscal-period helpers."""

from __future__ import annotations

import pandas as pd

from debt_sim.instruments import annual_to_quarterly_rate


def federal_fiscal_year(period: pd.Period) -> int:
    """Return the federal fiscal year containing a calendar quarter.

    Calendar Q4 (October through December) belongs to the following federal
    fiscal year; calendar Q1 through Q3 belong to the same-numbered fiscal year.
    """

    if not period.freqstr.startswith("Q"):
        raise ValueError("period must be quarterly")
    return period.year + 1 if period.quarter == 4 else period.year


def advance_gdp(
    prior_nominal_gdp_billions_saar: float,
    prior_real_gdp_billions_chained_saar: float,
    annual_real_growth_rate: float,
    annual_inflation_rate: float,
) -> tuple[float, float]:
    """Advance real and nominal GDP using explicit compounded quarterly rates."""

    if prior_nominal_gdp_billions_saar <= 0 or prior_real_gdp_billions_chained_saar <= 0:
        raise ValueError("initial GDP levels must be positive")
    real_quarterly = annual_to_quarterly_rate(annual_real_growth_rate)
    inflation_quarterly = annual_to_quarterly_rate(annual_inflation_rate)
    real = prior_real_gdp_billions_chained_saar * (1.0 + real_quarterly)
    nominal = prior_nominal_gdp_billions_saar * (1.0 + real_quarterly) * (1.0 + inflation_quarterly)
    return nominal, real


def annualized_flow_gdp_share(quarterly_flow_billions: float, gdp_billions_saar: float) -> float:
    """Express a quarterly flow as a share of annual-rate GDP."""

    if gdp_billions_saar <= 0:
        raise ValueError("GDP must be positive")
    return 4.0 * quarterly_flow_billions / gdp_billions_saar
