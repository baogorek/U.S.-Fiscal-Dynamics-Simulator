"""Adaptive Treasury issuance and market-value debt buybacks."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

import pandas as pd

from debt_sim.debt_stock import DebtStock, IssuanceRates, IssuanceStrategy
from debt_sim.instruments import InstrumentType, TreasuryCohort, annual_to_quarterly_rate


@dataclass(frozen=True, slots=True)
class TreasuryIssuanceRule:
    """Shift new borrowing toward bills when long-end yields are under pressure."""

    activation_basis_points: float = 100.0
    bill_share_increase_per_100_basis_points: float = 0.05
    maximum_bill_share: float = 0.50
    minimum_note_share: float = 0.30
    minimum_bond_share: float = 0.05

    def __post_init__(self) -> None:
        if (
            min(
                self.activation_basis_points,
                self.bill_share_increase_per_100_basis_points,
                self.maximum_bill_share,
                self.minimum_note_share,
                self.minimum_bond_share,
            )
            < 0
        ):
            raise ValueError("Treasury issuance-rule parameters cannot be negative")
        if (
            max(
                self.bill_share_increase_per_100_basis_points,
                self.maximum_bill_share,
                self.minimum_note_share,
                self.minimum_bond_share,
            )
            > 1
        ):
            raise ValueError("Treasury issuance shares must be no more than one")


@dataclass(frozen=True, slots=True)
class TreasuryBuybackInstruction:
    """Reverse-auction limits and the securities eligible for purchase.

    Treasury normally announces liquidity-support capacity in par value. A cash
    limit remains available for cash-management experiments. A zero value means
    that the corresponding limit does not bind; at least one limit must be set.
    """

    cash_limit_billions: float = 0.0
    maximum_face_value_billions: float = 0.0
    minimum_remaining_quarters: int = 40
    maximum_remaining_quarters: int = 120
    eligible_instrument_types: tuple[InstrumentType, ...] = (
        InstrumentType.NOTE,
        InstrumentType.BOND,
    )
    financing_instrument: InstrumentType = InstrumentType.BILL
    selection_rule: Literal["oldest_issue_first"] = "oldest_issue_first"

    def __post_init__(self) -> None:
        if min(self.cash_limit_billions, self.maximum_face_value_billions) < 0:
            raise ValueError("buyback limits cannot be negative")
        if max(self.cash_limit_billions, self.maximum_face_value_billions) <= 0:
            raise ValueError("a buyback must specify a cash or face-value limit")
        if self.minimum_remaining_quarters < 1:
            raise ValueError("minimum remaining maturity must be positive")
        if self.maximum_remaining_quarters < self.minimum_remaining_quarters:
            raise ValueError("maximum remaining maturity cannot be below the minimum")
        if not self.eligible_instrument_types:
            raise ValueError("a buyback must specify at least one eligible instrument type")
        if any(
            instrument not in {InstrumentType.NOTE, InstrumentType.BOND}
            for instrument in self.eligible_instrument_types
        ):
            raise ValueError("the initial buyback pricer supports fixed-rate notes and bonds")
        if self.selection_rule != "oldest_issue_first":
            raise ValueError("unknown buyback selection rule")


type TreasuryBuybackPlan = Mapping[
    pd.Period,
    TreasuryBuybackInstruction | Sequence[TreasuryBuybackInstruction],
]


@dataclass(frozen=True, slots=True)
class TreasuryBuybackResult:
    cash_limit_billions: float
    maximum_face_value_billions: float
    cash_spent_billions: float
    face_value_retired_billions: float
    premium_or_discount_billions: float
    unfilled_cash_limit_billions: float
    unfilled_face_value_limit_billions: float
    weighted_price_per_dollar_face: float
    principal_retired_by_type_billions: Mapping[InstrumentType, float]


def adaptive_issuance_strategy(
    base_strategy: IssuanceStrategy,
    long_yield_pressure_basis_points: float,
    rule: TreasuryIssuanceRule | None = None,
) -> IssuanceStrategy:
    """Return a visible bill-heavy new-borrowing mix under long-rate stress."""

    rule = rule or TreasuryIssuanceRule()
    if long_yield_pressure_basis_points < 0:
        raise ValueError("long_yield_pressure_basis_points cannot be negative")
    shares = dict(base_strategy.new_borrowing_shares)
    pressure_above_trigger = max(
        long_yield_pressure_basis_points - rule.activation_basis_points,
        0.0,
    )
    requested_shift = pressure_above_trigger / 100.0 * rule.bill_share_increase_per_100_basis_points
    bill_room = max(rule.maximum_bill_share - shares[InstrumentType.BILL], 0.0)
    note_room = max(shares[InstrumentType.NOTE] - rule.minimum_note_share, 0.0)
    bond_room = max(shares[InstrumentType.BOND] - rule.minimum_bond_share, 0.0)
    shift = min(requested_shift, bill_room, note_room + bond_room)
    if shift <= 0:
        return base_strategy

    source_room = note_room + bond_room
    note_reduction = shift * note_room / source_room
    bond_reduction = shift - note_reduction
    shares[InstrumentType.BILL] += shift
    shares[InstrumentType.NOTE] -= note_reduction
    shares[InstrumentType.BOND] -= bond_reduction
    return IssuanceStrategy(
        new_borrowing_shares=shares,
        tenor_quarters=base_strategy.tenor_quarters,
        preserve_instrument_type_on_rollover=base_strategy.preserve_instrument_type_on_rollover,
    )


def build_adaptive_issuance_strategy_path(
    base_strategy: IssuanceStrategy,
    long_yield_pressure_basis_points: pd.Series,
    rule: TreasuryIssuanceRule | None = None,
) -> dict[pd.Period, IssuanceStrategy]:
    """Build one issuance strategy per quarter from an explicit pressure path."""

    if not isinstance(long_yield_pressure_basis_points.index, pd.PeriodIndex):
        raise ValueError("long-yield pressure path must use a PeriodIndex")
    return {
        period: adaptive_issuance_strategy(base_strategy, float(pressure), rule)
        for period, pressure in long_yield_pressure_basis_points.items()
    }


def fixed_rate_price_per_dollar_face(
    cohort: TreasuryCohort,
    period: pd.Period,
    annual_market_yield: float,
) -> float:
    """Price a fixed-rate cohort using quarterly coupon cash flows."""

    if cohort.instrument_type not in {InstrumentType.NOTE, InstrumentType.BOND}:
        raise ValueError("fixed-rate buyback pricing supports notes and bonds")
    if cohort.maturity_period <= period:
        raise ValueError("cannot price a matured security for buyback")
    if annual_market_yield <= -1:
        raise ValueError("annual market yield must be greater than -100%")
    remaining_quarters = cohort.maturity_period.ordinal - period.ordinal
    quarterly_yield = annual_to_quarterly_rate(annual_market_yield)
    coupon = cohort.coupon_rate / 4.0
    if abs(quarterly_yield) < 1e-12:
        return 1.0 + coupon * remaining_quarters
    discount = 1.0 + quarterly_yield
    coupon_value = coupon * (1.0 - discount ** (-remaining_quarters)) / quarterly_yield
    principal_value = discount ** (-remaining_quarters)
    return coupon_value + principal_value


def _single_instrument_strategy(
    base_strategy: IssuanceStrategy,
    instrument_type: InstrumentType,
) -> IssuanceStrategy:
    return IssuanceStrategy(
        new_borrowing_shares={
            candidate: 1.0 if candidate is instrument_type else 0.0 for candidate in InstrumentType
        },
        tenor_quarters=base_strategy.tenor_quarters,
        preserve_instrument_type_on_rollover=base_strategy.preserve_instrument_type_on_rollover,
    )


def buyback_financing_strategy(
    base_strategy: IssuanceStrategy,
    instruction: TreasuryBuybackInstruction,
) -> IssuanceStrategy:
    """Finance a buyback with the instrument selected in the instruction."""

    return _single_instrument_strategy(base_strategy, instruction.financing_instrument)


def execute_treasury_buyback(
    stock: DebtStock,
    period: pd.Period,
    instruction: TreasuryBuybackInstruction,
    rates: IssuanceRates,
) -> TreasuryBuybackResult:
    """Purchase eligible outstanding principal up to a market-value cash limit."""

    if instruction.cash_limit_billions <= 1e-12:
        cash_remaining = float("inf")
    else:
        cash_remaining = instruction.cash_limit_billions
    if instruction.maximum_face_value_billions <= 1e-12:
        face_remaining = float("inf")
    else:
        face_remaining = instruction.maximum_face_value_billions

    if min(cash_remaining, face_remaining) <= 1e-12:
        return TreasuryBuybackResult(
            cash_limit_billions=instruction.cash_limit_billions,
            maximum_face_value_billions=instruction.maximum_face_value_billions,
            cash_spent_billions=0.0,
            face_value_retired_billions=0.0,
            premium_or_discount_billions=0.0,
            unfilled_cash_limit_billions=instruction.cash_limit_billions,
            unfilled_face_value_limit_billions=instruction.maximum_face_value_billions,
            weighted_price_per_dollar_face=0.0,
            principal_retired_by_type_billions=MappingProxyType({}),
        )

    eligible = []
    for cohort in stock.cohorts:
        remaining = cohort.maturity_period.ordinal - period.ordinal
        if (
            cohort.instrument_type in instruction.eligible_instrument_types
            and cohort.issue_period < period
            and instruction.minimum_remaining_quarters
            <= remaining
            <= instruction.maximum_remaining_quarters
        ):
            eligible.append(cohort)
    eligible.sort(key=lambda cohort: (cohort.issue_period.ordinal, cohort.cohort_id))

    reductions: dict[str, float] = {}
    retired_by_type = {instrument_type: 0.0 for instrument_type in InstrumentType}
    cash_spent = 0.0
    face_retired = 0.0
    for cohort in eligible:
        market_yield = rates.for_type(cohort.instrument_type)
        price = fixed_rate_price_per_dollar_face(cohort, period, market_yield)
        affordable_face = cash_remaining / price
        face = min(cohort.principal_billions, affordable_face, face_remaining)
        if face <= 1e-12:
            continue
        cash = face * price
        reductions[cohort.cohort_id] = face
        retired_by_type[cohort.instrument_type] += face
        face_retired += face
        cash_spent += cash
        cash_remaining -= cash
        face_remaining -= face
        if min(cash_remaining, face_remaining) <= 1e-12:
            break

    stock.retire_cohort_principal(reductions)
    nonzero_by_type = {
        instrument_type: amount
        for instrument_type, amount in retired_by_type.items()
        if amount > 1e-12
    }
    return TreasuryBuybackResult(
        cash_limit_billions=instruction.cash_limit_billions,
        maximum_face_value_billions=instruction.maximum_face_value_billions,
        cash_spent_billions=cash_spent,
        face_value_retired_billions=face_retired,
        premium_or_discount_billions=cash_spent - face_retired,
        unfilled_cash_limit_billions=(
            max(instruction.cash_limit_billions - cash_spent, 0.0)
            if instruction.cash_limit_billions > 0
            else 0.0
        ),
        unfilled_face_value_limit_billions=(
            max(instruction.maximum_face_value_billions - face_retired, 0.0)
            if instruction.maximum_face_value_billions > 0
            else 0.0
        ),
        weighted_price_per_dollar_face=(cash_spent / face_retired if face_retired > 0 else 0.0),
        principal_retired_by_type_billions=MappingProxyType(nonzero_by_type),
    )
