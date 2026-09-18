"""Illustrative fiscal fixed points with debt-dependent financing costs.

This is an annual, fully repriced, single-rate diagnostic, not the Treasury
cohort engine or an estimated U.S. demand model. Its purpose is to distinguish
loss of a stable fixed point from hitting an imposed gross-issuance ceiling.
Inflation and nominal growth are held fixed; no post-break regime is selected.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class FiscalFixedPoint:
    debt_gdp_ratio: float
    annual_transition_derivative: float
    stability: str


@dataclass(frozen=True)
class LinearFinancingEnvironment:
    """An illustrative long-run borrowing-cost schedule in decimal units.

    A slope of 0.01 means a one-percentage-point increase in debt/GDP raises
    the annual effective rate by one basis point. The intercept and slope
    must eventually be estimated jointly with growth and policy responses.
    """

    nominal_growth: float = 0.04
    anchor_interest_rate: float = 0.03
    anchor_debt_gdp_ratio: float = 1.0
    interest_slope: float = 0.01

    def __post_init__(self) -> None:
        values = (
            self.nominal_growth, self.anchor_interest_rate,
            self.anchor_debt_gdp_ratio, self.interest_slope,
        )
        if not np.isfinite(values).all():
            raise ValueError("financing assumptions must be finite")
        if self.nominal_growth <= -1 or self.intercept <= -1:
            raise ValueError("growth and rates on nonnegative debt must exceed -100 percent")
        if self.anchor_debt_gdp_ratio < 0 or self.interest_slope <= 0:
            raise ValueError("anchor debt must be nonnegative and the interest slope positive")

    @property
    def intercept(self) -> float:
        return self.anchor_interest_rate - self.interest_slope * self.anchor_debt_gdp_ratio

    def interest_rate(self, debt_gdp_ratio: float) -> float:
        return self.intercept + self.interest_slope * debt_gdp_ratio

    def steady_primary_deficit(self, debt_gdp_ratio: float) -> float:
        """Primary deficit/current GDP compatible with this fixed debt ratio."""
        return (
            (self.nominal_growth - self.interest_rate(debt_gdp_ratio))
            * debt_gdp_ratio / (1 + self.nominal_growth)
        )

    @property
    def debt_at_maximum_deficit(self) -> float:
        return max((self.nominal_growth - self.intercept) / (2 * self.interest_slope), 0)

    @property
    def maximum_steady_primary_deficit(self) -> float:
        return self.steady_primary_deficit(self.debt_at_maximum_deficit)

    def fixed_points(self, primary_deficit_gdp_share: float) -> list[FiscalFixedPoint]:
        """Nonnegative fixed points and local stability of the annual map.

        A derivative of +1 at the maximum is classified as marginal: the
        tangency is not a locally attracting fixed point from both sides.
        """
        if not np.isfinite(primary_deficit_gdp_share) or primary_deficit_gdp_share < 0:
            raise ValueError("the illustrated primary deficit must be finite and nonnegative")
        advantage = self.nominal_growth - self.intercept
        discriminant = (
            advantage**2
            - 4 * self.interest_slope * (1 + self.nominal_growth) * primary_deficit_gdp_share
        )
        if discriminant < -1e-14:
            return []
        root = np.sqrt(max(discriminant, 0))
        candidates = [(advantage - root) / (2 * self.interest_slope)]
        if root > 1e-12:
            candidates.append((advantage + root) / (2 * self.interest_slope))
        results = []
        for debt in candidates:
            if debt < -1e-12:
                continue
            debt = max(float(debt), 0)
            derivative = 1 + (2 * self.interest_slope * debt - advantage) / (
                1 + self.nominal_growth
            )
            magnitude = abs(derivative)
            stability = (
                "marginal" if np.isclose(magnitude, 1, rtol=0, atol=1e-10)
                else "stable" if magnitude < 1 else "unstable"
            )
            results.append(FiscalFixedPoint(debt, float(derivative), stability))
        return results

    def simulate(
        self, *, initial_debt_gdp_ratio: float, primary_deficit_gdp_share: float,
        years: int,
    ) -> pd.DataFrame:
        """Follow the annual map without imposing a debt or financing ceiling."""
        self.fixed_points(primary_deficit_gdp_share)  # Validate the deficit.
        if not np.isfinite(initial_debt_gdp_ratio) or initial_debt_gdp_ratio < 0:
            raise ValueError("initial debt must be finite and nonnegative")
        if isinstance(years, bool) or not isinstance(years, int) or years < 1:
            raise ValueError("years must be a positive integer")
        debt = initial_debt_gdp_ratio
        records = []
        for year in range(years + 1):
            gap = primary_deficit_gdp_share - self.steady_primary_deficit(debt)
            records.append({
                "year": year, "debt_gdp_ratio": debt,
                "interest_rate": self.interest_rate(debt),
                "next_year_debt_ratio_change": gap,
            })
            if year < years:
                debt += gap
                if not np.isfinite(debt):
                    raise ValueError("numerical overflow; this is not an economic crisis date")
        return pd.DataFrame(records)
