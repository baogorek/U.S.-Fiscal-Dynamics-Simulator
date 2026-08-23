"""Marketable Treasury cohort stock and quarterly rollover operations."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace

import numpy as np
import pandas as pd

from debt_sim.instruments import InstrumentType, TreasuryCohort, annual_to_quarterly_rate

DEFAULT_ISSUANCE_SHARES: dict[InstrumentType, float] = {
    InstrumentType.BILL: 0.22,
    InstrumentType.NOTE: 0.52,
    InstrumentType.BOND: 0.17,
    InstrumentType.TIPS: 0.07,
    InstrumentType.FRN: 0.02,
}

DEFAULT_TENORS_QUARTERS: dict[InstrumentType, int] = {
    InstrumentType.BILL: 1,
    InstrumentType.NOTE: 28,
    InstrumentType.BOND: 80,
    InstrumentType.TIPS: 40,
    InstrumentType.FRN: 8,
}


@dataclass(frozen=True, slots=True)
class IssuanceRates:
    """Exogenous annual rates for securities issued at a quarter end."""

    short_rate: float
    intermediate_rate: float
    long_rate: float
    tips_real_rate: float
    new_frn_spread: float = 0.001

    def __post_init__(self) -> None:
        values = (
            self.short_rate,
            self.intermediate_rate,
            self.long_rate,
            self.tips_real_rate,
            self.new_frn_spread,
        )
        if any(value < 0 for value in values[:3]):
            raise ValueError("nominal Treasury issuance rates cannot be negative in v0.1")
        if self.tips_real_rate <= -1 or self.new_frn_spread <= -1:
            raise ValueError("TIPS real rates and FRN spreads must be greater than -100%")
        if any(value > 1 for value in values[:-1]):
            raise ValueError("Treasury issuance rates above 100% are outside v0.1 bounds")

    def for_type(self, instrument_type: InstrumentType) -> float:
        return {
            InstrumentType.BILL: self.short_rate,
            InstrumentType.NOTE: self.intermediate_rate,
            InstrumentType.BOND: self.long_rate,
            InstrumentType.TIPS: self.tips_real_rate,
            InstrumentType.FRN: max(0.0, self.short_rate + self.new_frn_spread),
        }[instrument_type]


@dataclass(frozen=True, slots=True)
class IssuanceStrategy:
    """Visible assumptions governing the type and tenor of future issuance."""

    new_borrowing_shares: Mapping[InstrumentType, float] = field(
        default_factory=lambda: DEFAULT_ISSUANCE_SHARES.copy()
    )
    tenor_quarters: Mapping[InstrumentType, int] = field(
        default_factory=lambda: DEFAULT_TENORS_QUARTERS.copy()
    )
    preserve_instrument_type_on_rollover: bool = True

    def __post_init__(self) -> None:
        expected = set(InstrumentType)
        if set(self.new_borrowing_shares) != expected:
            raise ValueError("new_borrowing_shares must specify every instrument type")
        shares = np.array(list(self.new_borrowing_shares.values()), dtype=float)
        if np.any(shares < 0) or not np.isclose(shares.sum(), 1.0, atol=1e-9):
            raise ValueError("issuance shares must be nonnegative and sum to one")
        if set(self.tenor_quarters) != expected:
            raise ValueError("tenor_quarters must specify every instrument type")
        if any(int(value) <= 0 for value in self.tenor_quarters.values()):
            raise ValueError("issuance tenors must be positive")


@dataclass(frozen=True, slots=True)
class InterestAccrual:
    marketable_interest_excluding_tips_inflation_billions: float
    tips_inflation_compensation_billions: float
    frn_principal_reset_billions: float
    financing_cost_by_type_billions: Mapping[InstrumentType, float]


@dataclass(frozen=True, slots=True)
class MaturityResult:
    principal_by_type_billions: Mapping[InstrumentType, float]
    principal_maturing_billions: float
    tips_deflation_floor_cost_billions: float


@dataclass(frozen=True, slots=True)
class IssuanceResult:
    principal_issued_billions: float
    weighted_stated_issuance_rate: float


class DebtStock:
    """Mutable cohort ledger used by a single deterministic simulation run."""

    def __init__(self, cohorts: Iterable[TreasuryCohort], other_public_debt_billions: float):
        self.cohorts = list(cohorts)
        self.other_public_debt_billions = float(other_public_debt_billions)
        self._issuance_sequence = 0
        if self.other_public_debt_billions < 0:
            raise ValueError("other_public_debt_billions cannot be negative")
        if not self.cohorts:
            raise ValueError("at least one marketable Treasury cohort is required")
        ids = [cohort.cohort_id for cohort in self.cohorts]
        if len(ids) != len(set(ids)):
            raise ValueError("cohort_id values must be unique")

    def copy(self) -> DebtStock:
        clone = DebtStock(list(self.cohorts), self.other_public_debt_billions)
        clone._issuance_sequence = self._issuance_sequence
        return clone

    def reset_scenario_markers(self) -> None:
        """Treat the current stock as the inherited stock of a new scenario window."""

        self.cohorts = [
            replace(
                cohort,
                issued_since_scenario_start=False,
                repriced_since_scenario_start=False,
            )
            for cohort in self.cohorts
        ]

    @property
    def marketable_debt_billions(self) -> float:
        return sum(cohort.principal_billions for cohort in self.cohorts)

    @property
    def debt_held_by_public_billions(self) -> float:
        return self.marketable_debt_billions + self.other_public_debt_billions

    def composition_billions(self) -> dict[InstrumentType, float]:
        result = {instrument_type: 0.0 for instrument_type in InstrumentType}
        for cohort in self.cohorts:
            result[cohort.instrument_type] += cohort.principal_billions
        return result

    def accrue_quarter(
        self,
        annual_tips_reference_inflation_rate: float,
        annual_short_rate: float,
    ) -> InterestAccrual:
        """Apply TIPS indexation and FRN reset, then accrue financing cost."""

        quarterly_tips_change = annual_to_quarterly_rate(annual_tips_reference_inflation_rate)
        updated: list[TreasuryCohort] = []
        tips_adjustment = 0.0
        frn_reset_principal = 0.0
        financing_cost = 0.0
        cost_by_type: defaultdict[InstrumentType, float] = defaultdict(float)
        for cohort in self.cohorts:
            if cohort.instrument_type is InstrumentType.TIPS:
                cohort, adjustment = cohort.index_tips(quarterly_tips_change)
                tips_adjustment += adjustment
            if cohort.instrument_type is InstrumentType.FRN:
                frn_reset_principal += cohort.principal_billions
                cohort = cohort.reset_frn(annual_short_rate)
            cohort_cost = cohort.quarterly_financing_cost()
            financing_cost += cohort_cost
            cost_by_type[cohort.instrument_type] += cohort_cost
            updated.append(cohort)
        self.cohorts = updated
        return InterestAccrual(
            financing_cost,
            tips_adjustment,
            frn_reset_principal,
            {kind: cost_by_type[kind] for kind in InstrumentType},
        )

    def mature_at_end_of(self, period: pd.Period) -> MaturityResult:
        """Remove cohorts maturing by period end and compute redemption principal."""

        principal_by_type: defaultdict[InstrumentType, float] = defaultdict(float)
        remaining: list[TreasuryCohort] = []
        floor_cost = 0.0
        for cohort in self.cohorts:
            if cohort.maturity_period <= period:
                redemption = cohort.principal_billions
                if cohort.instrument_type is InstrumentType.TIPS:
                    redemption = max(redemption, cohort.redemption_floor_billions)
                    floor_cost += redemption - cohort.principal_billions
                principal_by_type[cohort.instrument_type] += redemption
            else:
                remaining.append(cohort)
        self.cohorts = remaining
        total = sum(principal_by_type.values())
        return MaturityResult(dict(principal_by_type), total, floor_cost)

    def issue_rollover(
        self,
        period: pd.Period,
        principal_by_type_billions: Mapping[InstrumentType, float],
        rates: IssuanceRates,
        strategy: IssuanceStrategy,
    ) -> IssuanceResult:
        """Refinance maturing principal without treating it as a budget deficit."""

        if strategy.preserve_instrument_type_on_rollover:
            allocation = principal_by_type_billions
        else:
            total = sum(principal_by_type_billions.values())
            allocation = {
                instrument_type: total * share
                for instrument_type, share in strategy.new_borrowing_shares.items()
            }
        return self._issue_allocation(period, allocation, rates, strategy)

    def issue_new_borrowing(
        self,
        period: pd.Period,
        amount_billions: float,
        rates: IssuanceRates,
        strategy: IssuanceStrategy,
    ) -> IssuanceResult:
        if amount_billions < 0:
            raise ValueError("issue_new_borrowing requires a nonnegative amount")
        allocation = {
            instrument_type: amount_billions * share
            for instrument_type, share in strategy.new_borrowing_shares.items()
        }
        return self._issue_allocation(period, allocation, rates, strategy)

    def _issue_allocation(
        self,
        period: pd.Period,
        allocation: Mapping[InstrumentType, float],
        rates: IssuanceRates,
        strategy: IssuanceStrategy,
    ) -> IssuanceResult:
        total = 0.0
        weighted_rate = 0.0
        for instrument_type in InstrumentType:
            principal = float(allocation.get(instrument_type, 0.0))
            if principal <= 1e-12:
                continue
            stated_rate = rates.for_type(instrument_type)
            coupon_rate = 0.0 if instrument_type is InstrumentType.BILL else stated_rate
            frn_spread = rates.new_frn_spread if instrument_type is InstrumentType.FRN else 0.0
            self._issuance_sequence += 1
            cohort = TreasuryCohort(
                cohort_id=f"sim-{period}-{instrument_type.value}-{self._issuance_sequence:06d}",
                instrument_type=instrument_type,
                issue_period=period,
                maturity_period=period + int(strategy.tenor_quarters[instrument_type]),
                principal_billions=principal,
                original_principal_billions=principal,
                coupon_rate=coupon_rate,
                effective_interest_rate=stated_rate,
                frn_spread=frn_spread,
                issued_since_scenario_start=True,
                repriced_since_scenario_start=True,
            )
            self.cohorts.append(cohort)
            total += principal
            weighted_rate += principal * stated_rate
        return IssuanceResult(total, weighted_rate / total if total else 0.0)

    def retire_debt(self, amount_billions: float) -> float:
        """Use a financing surplus to retire debt, shortest maturity first.

        Early redemption is an explicit generic-scenario convention; it is not
        a forecast of Treasury buyback operations.
        """

        if amount_billions < 0:
            raise ValueError("amount_billions must be nonnegative")
        remaining = amount_billions
        ordered = sorted(
            self.cohorts,
            key=lambda cohort: (cohort.maturity_period.ordinal, cohort.cohort_id),
        )
        updated: list[TreasuryCohort] = []
        for index, cohort in enumerate(ordered):
            if remaining <= 1e-12:
                updated.extend(ordered[index:])
                break
            reduction = min(remaining, cohort.principal_billions)
            remaining -= reduction
            balance = cohort.principal_billions - reduction
            if balance > 1e-12:
                original = cohort.original_principal_billions
                if original is not None:
                    original = max(0.0, original - reduction)
                updated.append(
                    replace(
                        cohort,
                        principal_billions=balance,
                        original_principal_billions=original,
                    )
                )
        else:
            reduction = min(remaining, self.other_public_debt_billions)
            self.other_public_debt_billions -= reduction
            remaining -= reduction
        self.cohorts = updated
        retired = amount_billions - remaining
        if remaining > 1e-9:
            raise ValueError("financing surplus exceeds all debt held by the public")
        return retired

    def average_effective_rate_excluding_tips_inflation(self) -> float:
        marketable = self.marketable_debt_billions
        if marketable <= 0:
            return 0.0
        return (
            sum(
                cohort.principal_billions * cohort.effective_interest_rate
                for cohort in self.cohorts
            )
            / marketable
        )

    def repriced_share(self) -> float:
        marketable = self.marketable_debt_billions
        if marketable <= 0:
            return 0.0
        repriced = sum(
            cohort.principal_billions
            for cohort in self.cohorts
            if cohort.repriced_since_scenario_start
        )
        return repriced / marketable
