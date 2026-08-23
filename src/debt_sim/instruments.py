"""Treasury instrument definitions and interest/indexation mechanics.

Rates are stored as decimal annual rates. Principal amounts are billions of
nominal dollars. Dates are calendar-quarter periods because the simulator's
time step is quarterly even when source securities mature during a quarter.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

import pandas as pd


class InstrumentType(StrEnum):
    BILL = "bill"
    NOTE = "note"
    BOND = "bond"
    TIPS = "tips"
    FRN = "frn"


@dataclass(frozen=True, slots=True)
class TreasuryCohort:
    """A security-level observation or a homogeneous simulated issuance cohort."""

    cohort_id: str
    instrument_type: InstrumentType
    issue_period: pd.Period
    maturity_period: pd.Period
    principal_billions: float
    coupon_rate: float
    effective_interest_rate: float
    original_principal_billions: float | None = None
    frn_spread: float = 0.0
    issued_since_scenario_start: bool = False
    repriced_since_scenario_start: bool = False

    def __post_init__(self) -> None:
        if self.issue_period.freqstr.startswith("Q") is False:
            raise ValueError("issue_period must be quarterly")
        if self.maturity_period.freqstr.startswith("Q") is False:
            raise ValueError("maturity_period must be quarterly")
        if self.maturity_period < self.issue_period:
            raise ValueError("maturity_period cannot precede issue_period")
        if self.principal_billions < 0:
            raise ValueError("principal_billions cannot be negative")
        if self.original_principal_billions is not None and self.original_principal_billions < 0:
            raise ValueError("original_principal_billions cannot be negative")
        if self.coupon_rate < 0:
            raise ValueError("coupon_rate cannot be negative")
        if self.effective_interest_rate <= -1.0:
            raise ValueError("effective_interest_rate must be greater than -100%")

    @property
    def redemption_floor_billions(self) -> float:
        if self.instrument_type is not InstrumentType.TIPS:
            return self.principal_billions
        return self.original_principal_billions or self.principal_billions

    def reset_frn(self, annual_short_rate: float) -> TreasuryCohort:
        """Reset an FRN to the scenario short rate plus its fixed auction spread."""

        if self.instrument_type is not InstrumentType.FRN:
            return self
        reset_rate = max(0.0, annual_short_rate + self.frn_spread)
        return replace(
            self,
            coupon_rate=reset_rate,
            effective_interest_rate=reset_rate,
            repriced_since_scenario_start=True,
        )

    def index_tips(self, quarterly_reference_cpi_change: float) -> tuple[TreasuryCohort, float]:
        """Apply a quarterly CPI reference-index change to TIPS principal.

        Principal may fall below original par during deflation. The original-par
        guarantee is applied only at redemption, consistent with Treasury's
        security terms.
        """

        if self.instrument_type is not InstrumentType.TIPS:
            return self, 0.0
        if quarterly_reference_cpi_change <= -1.0:
            raise ValueError("quarterly TIPS reference inflation must be greater than -100%")
        adjusted = max(0.0, self.principal_billions * (1.0 + quarterly_reference_cpi_change))
        return replace(self, principal_billions=adjusted), adjusted - self.principal_billions

    def quarterly_financing_cost(self) -> float:
        """Accrue one quarter of effective financing cost.

        For bills this represents discount accrual. For coupon securities the
        effective rate is coupon plus the modeled net premium/discount
        amortization. TIPS inflation compensation is handled separately.
        """

        return self.principal_billions * self.effective_interest_rate / 4.0


def annual_to_quarterly_rate(annual_rate: float) -> float:
    """Convert an effective annual rate to a compounded quarterly rate."""

    if annual_rate <= -1.0:
        raise ValueError("annual rate must be greater than -100%")
    return (1.0 + annual_rate) ** 0.25 - 1.0


def quarterly_to_annual_rate(quarterly_rate: float) -> float:
    """Annualize a compounded quarterly rate."""

    if quarterly_rate <= -1.0:
        raise ValueError("quarterly rate must be greater than -100%")
    return (1.0 + quarterly_rate) ** 4 - 1.0
