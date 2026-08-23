"""Explicit bond-market confidence-premium stress scenarios.

These helpers impose exogenous paths. They do not estimate the probability,
timing, or endogenous size of a change in Treasury financing conditions.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from debt_sim.closure import apply_parallel_rate_shock


@dataclass(frozen=True, slots=True)
class ConfidenceShock:
    """A temporary new-issuance premium with an optional imposed recession."""

    premium_basis_points: float
    duration_quarters: int = 40
    recession_first_year_real_growth: float = -0.02
    recession_second_year_real_growth: float = 0.0
    include_recession: bool = True

    def __post_init__(self) -> None:
        if self.premium_basis_points < 0:
            raise ValueError("confidence premium must be nonnegative")
        if self.duration_quarters <= 0:
            raise ValueError("confidence-premium duration must be positive")
        if min(
            self.recession_first_year_real_growth,
            self.recession_second_year_real_growth,
        ) <= -1.0:
            raise ValueError("imposed real-growth rates must be greater than -100%")


def apply_confidence_shock(
    assumptions: pd.DataFrame,
    shock: ConfidenceShock,
) -> pd.DataFrame:
    """Apply the premium and absolute annualized real-growth stress paths.

    Inflation, nominal primary deficits, other financing, and all other inputs
    remain on their supplied paths. The premium applies to new nominal bills,
    notes, and bonds and to new TIPS real rates. FRNs inherit the shocked bill
    reference rate through the existing debt engine.
    """

    if shock.duration_quarters > len(assumptions):
        raise ValueError("confidence-premium duration exceeds the supplied horizon")
    stressed = assumptions.copy()
    if shock.include_recession:
        if len(stressed) < 8:
            raise ValueError("the two-year recession path requires at least eight quarters")
        growth_column = stressed.columns.get_loc("annual_real_gdp_growth_rate")
        stressed.iloc[:4, growth_column] = shock.recession_first_year_real_growth
        stressed.iloc[4:8, growth_column] = shock.recession_second_year_real_growth
    return apply_parallel_rate_shock(
        stressed,
        shock.premium_basis_points,
        duration_quarters=shock.duration_quarters,
        include_tips_real_rate=True,
    )
