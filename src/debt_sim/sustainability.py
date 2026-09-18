"""Debt sustainability arithmetic, separate from any crisis-trigger assumption.

These diagnostics measure the primary balance needed to hold a debt ratio fixed.
They neither estimate investor demand nor select an inflation/default regime.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def constant_policy_debt_path(
    *,
    initial_debt_gdp_ratio: float,
    primary_deficit_gdp_share: float,
    nominal_interest_rate: float,
    nominal_gdp_growth: float,
    years: int,
) -> pd.DataFrame:
    """Exact annual, single-rate recursion with flows divided by current GDP.

    This deliberately simple counterexample engine has no maturity structure.
    Debt can become negative (net assets) if supplied primary surpluses are large.
    All rates and GDP shares are decimals; the interest rate applies to opening
    debt, and primary deficits are positive. Year zero is the initial stock.
    """

    values = (
        initial_debt_gdp_ratio, primary_deficit_gdp_share,
        nominal_interest_rate, nominal_gdp_growth,
    )
    if not np.isfinite(values).all():
        raise ValueError("debt arithmetic inputs must be finite")
    if min(nominal_interest_rate, nominal_gdp_growth) <= -1.0:
        raise ValueError("interest and growth rates must exceed -100 percent")
    if isinstance(years, bool) or not isinstance(years, int) or years < 1:
        raise ValueError("years must be a positive integer")
    factor = (1.0 + nominal_interest_rate) / (1.0 + nominal_gdp_growth)
    debt = initial_debt_gdp_ratio
    records = [{"year": 0, "debt_gdp_ratio": debt}]
    for year in range(1, years + 1):
        debt = factor * debt + primary_deficit_gdp_share
        if not np.isfinite(debt):
            raise ValueError("constant-policy debt path overflowed")
        records.append({"year": year, "debt_gdp_ratio": debt})
    return pd.DataFrame(records)


def decompose_debt_ratio(
    quarterly: pd.DataFrame,
    *,
    initial_nominal_gdp_billions_saar: float,
) -> pd.DataFrame:
    """Decompose each quarter's debt-ratio change using the cohort ledger.

    Quarterly contributions are shares of current annual-rate GDP. Annualized
    flow requirements multiply by four; they are local accounting requirements,
    not a permanent fiscal package or a forecast of the macro response.
    """

    if not np.isfinite(initial_nominal_gdp_billions_saar) or (
        initial_nominal_gdp_billions_saar <= 0.0
    ):
        raise ValueError("initial nominal GDP must be finite and positive")
    path = quarterly.reset_index(drop=True)
    if path.empty:
        raise ValueError("quarterly path cannot be empty")
    periods = pd.PeriodIndex(path["quarter"], freq="Q")
    if not periods.equals(pd.period_range(periods[0], periods=len(periods), freq="Q")):
        raise ValueError("quarterly path must be chronological and contiguous")
    gdp = path["nominal_gdp_billions_saar"].astype(float)
    opening = path["beginning_debt_held_by_public_billions"].astype(float)
    closing = path["debt_held_by_public_billions"].astype(float)
    primary = path["primary_deficit_billions"].astype(float)
    interest = path["modeled_debt_interest_cost_billions"].astype(float)
    other = path["other_financing_adjustment_billions"].astype(float)
    # Buybacks may exchange face value at a premium/discount. Include that
    # explicit stock-flow adjustment; never hide it in primary expenditure.
    buyback = path.get("treasury_buyback_premium_or_discount_billions", 0.0)
    other = other + buyback
    values = np.column_stack([gdp, opening, closing, primary, interest, other])
    if not np.isfinite(values).all() or (gdp <= 0.0).any():
        raise ValueError("path amounts must be finite and GDP positive")
    if not np.allclose(opening.iloc[1:], closing.iloc[:-1], rtol=1e-10, atol=1e-8):
        raise ValueError("opening debt must equal the preceding quarter's closing debt")
    prior_gdp = gdp.shift(1)
    prior_gdp.iloc[0] = initial_nominal_gdp_billions_saar
    growth = gdp / prior_gdp - 1.0
    growth_contribution = opening / gdp - opening / prior_gdp
    actual_change = closing / gdp - opening / prior_gdp
    primary_contribution = primary / gdp
    interest_contribution = interest / gdp
    other_contribution = other / gdp
    required_primary = -growth_contribution - interest_contribution - other_contribution
    return pd.DataFrame({
        "quarter": path["quarter"].astype(str),
        "debt_gdp_ratio": closing / gdp,
        "nominal_gdp_growth_quarterly": growth,
        "primary_contribution": primary_contribution,
        "interest_contribution": interest_contribution,
        "other_financing_contribution": other_contribution,
        "growth_contribution": growth_contribution,
        "debt_ratio_change": actual_change,
        "decomposition_residual": actual_change - (
            primary_contribution + interest_contribution
            + other_contribution + growth_contribution
        ),
        "stabilizing_primary_deficit_gdp_share_annualized": 4.0 * required_primary,
        "local_primary_improvement_gdp_share_annualized": (
            4.0 * (primary_contribution - required_primary)
        ),
    })
