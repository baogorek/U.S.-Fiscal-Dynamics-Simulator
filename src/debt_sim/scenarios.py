"""Construction of explicit baseline, preset, and manual scenario paths."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

import pandas as pd
from scipy.optimize import brentq

from debt_sim.data import BaselineBundle
from debt_sim.debt_stock import DebtStock
from debt_sim.economy import federal_fiscal_year
from debt_sim.instruments import quarterly_to_annual_rate


@dataclass(frozen=True, slots=True)
class Scenario:
    name: str
    description: str
    quarterly_assumptions: pd.DataFrame
    imposed_parameters: dict[str, float | int | str]


@dataclass(frozen=True, slots=True)
class StartingState:
    stock: DebtStock
    initial_nominal_gdp_billions_saar: float
    initial_real_gdp_billions_chained_saar: float


PRESET_DESCRIPTIONS = {
    "baseline": (
        "February 2026 CBO macro, primary-deficit, rate, and financing paths, "
        "with documented issuance approximations."
    ),
    "inflation_no_rate_response": (
        "Temporary 10% inflation with real growth, primary deficits, and Treasury "
        "issuance rates otherwise unchanged."
    ),
    "inflation_immediate_rate_response": (
        "Temporary 10% inflation with an immediate 500 basis point shock to "
        "new-issuance and TIPS real rates."
    ),
    "inflation_delayed_rate_response": (
        "Temporary 10% inflation; the same 500 basis point rate shock begins four quarters later."
    ),
    "persistent_financial_repression": (
        "Imposed experiment: 6% inflation for three years while Treasury financing "
        "rates remain on the baseline path. This is not a forecast."
    ),
}

MAX_BASELINE_PERIOD = pd.Period("2056Q3", freq="Q")


def _constant_growth_quarters_for_annual_mean(
    prior_fourth_quarter: float, annual_mean: float
) -> list[float]:
    """Return four smooth quarterly levels whose arithmetic mean is the annual value.

    CBO publishes annual levels after the ten-year window. A single within-year
    compound rate is chosen so the four quarterly SAAR levels exactly average to
    the published annual level. This adds no quarterly volatility.
    """

    if prior_fourth_quarter <= 0 or annual_mean <= 0:
        raise ValueError("annual interpolation requires positive levels")

    def residual(multiplier: float) -> float:
        return (
            prior_fourth_quarter
            * sum(multiplier**quarter for quarter in range(1, 5))
            / 4.0
            - annual_mean
        )

    multiplier = brentq(residual, 1e-6, 10.0, xtol=1e-13, rtol=1e-13)
    return [prior_fourth_quarter * multiplier**quarter for quarter in range(1, 5)]


def build_extended_quarterly_economy(bundle: BaselineBundle) -> pd.DataFrame:
    """Append a deterministic quarterly interpolation of CBO's 2037–2056 levels."""

    economy = bundle.cbo_quarterly_economy.copy()
    economy.index = pd.PeriodIndex(economy["quarter"], freq="Q")
    if economy.index.max() >= pd.Period("2056Q4", freq="Q"):
        return economy

    annual = bundle.cbo_long_term_economic.set_index("year")
    level_mapping = {
        "nominal_gdp_billions_saar": "nominal_gdp_billions",
        "real_gdp_billions_chained_saar": "real_gdp_billions_chained",
        "gdp_price_index": "gdp_price_index",
        "cpi_u_index": "cpi_u_index",
    }
    paths: dict[str, dict[pd.Period, float]] = {column: {} for column in level_mapping}
    for output_column, annual_column in level_mapping.items():
        prior = float(economy.loc[pd.Period("2036Q4", freq="Q"), output_column])
        for year in range(2037, 2057):
            values = _constant_growth_quarters_for_annual_mean(
                prior, float(annual.loc[year, annual_column])
            )
            for quarter, value in enumerate(values, start=1):
                paths[output_column][pd.Period(f"{year}Q{quarter}", freq="Q")] = value
            prior = values[-1]

    short_rate = float(economy.iloc[-1]["treasury_bill_3_month_rate"])
    ten_year_rate = float(economy.iloc[-1]["treasury_note_10_year_rate"])
    records = []
    for period in pd.period_range("2037Q1", "2056Q4", freq="Q"):
        records.append(
            {
                "quarter": str(period),
                "quarter_end": period.end_time.normalize(),
                **{column: values[period] for column, values in paths.items()},
                # The long-term workbook does not publish maturity-specific
                # Treasury issuance rates. Holding the February 11 endpoint
                # flat is explicit and avoids manufacturing a yield curve.
                "treasury_bill_3_month_rate": short_rate,
                "treasury_note_10_year_rate": ten_year_rate,
            }
        )
    extension = pd.DataFrame.from_records(records)
    extension.index = pd.PeriodIndex(extension["quarter"], freq="Q")
    return pd.concat([economy, extension]).sort_index()


def _annualize_ratio(current: float, prior: float) -> float:
    return quarterly_to_annual_rate(current / prior - 1.0)


def build_baseline_scenario(
    bundle: BaselineBundle,
    *,
    start_period: str | pd.Period = "2025Q4",
    end_period: str | pd.Period = "2036Q3",
    tips_real_issuance_rate: float = 0.0175,
    new_frn_spread: float = 0.001,
) -> Scenario:
    """Translate CBO calendar-quarter and fiscal-year data without mixing them."""

    start = pd.Period(start_period, freq="Q")
    end = pd.Period(end_period, freq="Q")
    if end < start:
        raise ValueError("end_period must not precede start_period")
    periods = pd.period_range(start, end, freq="Q")
    if end > MAX_BASELINE_PERIOD:
        raise ValueError(f"end_period cannot exceed the pinned horizon {MAX_BASELINE_PERIOD}")
    economy = build_extended_quarterly_economy(bundle)
    required = pd.period_range(start - 2, end, freq="Q")
    if not required.isin(economy.index).all():
        missing = required[~required.isin(economy.index)]
        raise ValueError(f"CBO economy data is missing quarters: {list(missing)}")
    fiscal = bundle.cbo_fiscal_baseline.set_index("fiscal_year")

    rows: list[dict[str, float]] = []
    for period in periods:
        current = economy.loc[period]
        prior = economy.loc[period - 1]
        tips_current = economy.loc[period - 1]
        tips_prior = economy.loc[period - 2]
        fiscal_year = federal_fiscal_year(period)
        fy = fiscal.loc[fiscal_year]
        rows.append(
            {
                "annual_real_gdp_growth_rate": _annualize_ratio(
                    float(current["real_gdp_billions_chained_saar"]),
                    float(prior["real_gdp_billions_chained_saar"]),
                ),
                "annual_inflation_rate": _annualize_ratio(
                    float(current["gdp_price_index"]), float(prior["gdp_price_index"])
                ),
                # Quarterly approximation to Treasury's lagged CPI-U reference
                # index: apply the preceding quarter's CPI-U change.
                "annual_tips_reference_inflation_rate": _annualize_ratio(
                    float(tips_current["cpi_u_index"]),
                    float(tips_prior["cpi_u_index"]),
                ),
                # Annual fiscal flows are distributed evenly across their four
                # constituent calendar quarters; no monthly timing is inferred.
                "primary_deficit_billions": float(fy["primary_deficit_billions"]) / 4.0,
                "other_financing_adjustment_billions": float(
                    fy["other_financing_adjustment_billions"]
                )
                / 4.0,
                "short_issuance_rate": float(current["treasury_bill_3_month_rate"]),
                "intermediate_issuance_rate": float(current["treasury_note_10_year_rate"]),
                # CBO's public file gives 3-month and 10-year rates. v0.1 uses
                # the 10-year series for both intermediate and long issuance.
                "long_issuance_rate": float(current["treasury_note_10_year_rate"]),
                "tips_real_issuance_rate": tips_real_issuance_rate,
                "new_frn_spread": new_frn_spread,
                "other_public_debt_interest_rate": float(fy["cbo_average_debt_interest_rate"]),
            }
        )
    assumptions = pd.DataFrame(rows, index=periods)
    assumptions.index.name = "quarter"
    return Scenario(
        name="baseline",
        description=PRESET_DESCRIPTIONS["baseline"],
        quarterly_assumptions=assumptions,
        imposed_parameters={
            "cbo_vintage": bundle.cbo_vintage,
            "cbo_ten_year_release_date": "2026-02-11",
            "cbo_long_term_release_date": "2026-02-25",
            "treasury_observation_date": bundle.treasury_observation_date,
            "tips_real_issuance_rate": tips_real_issuance_rate,
            "new_frn_spread": new_frn_spread,
            "fiscal_to_quarterly_conversion": "equal nominal quarters",
            "post_2036_economic_interpolation": (
                "constant within-year compound growth calibrated to CBO annual means"
            ),
            "post_2036_treasury_rate_assumption": (
                "February 11, 2026 final quarterly 3-month and 10-year rates held constant"
            ),
            "post_2036_other_financing_assumption": "zero; not published in long-term data",
        },
    )


def prepare_starting_state(bundle: BaselineBundle, start_period: str | pd.Period) -> StartingState:
    """Warm the cohort ledger on baseline assumptions for a later scenario start."""

    from debt_sim.model import run_simulation

    start = pd.Period(start_period, freq="Q")
    first = pd.Period("2025Q4", freq="Q")
    if start < first:
        raise ValueError("the pinned 2025-09-30 Treasury stock cannot start before 2025Q4")
    if start == first:
        stock = bundle.initial_stock.copy()
        stock.reset_scenario_markers()
        return StartingState(
            stock,
            bundle.initial_nominal_gdp_billions_saar,
            bundle.initial_real_gdp_billions_chained_saar,
        )
    warmup = build_baseline_scenario(bundle, start_period=first, end_period=start - 1)
    result = run_simulation(
        bundle.initial_stock,
        warmup.quarterly_assumptions,
        initial_nominal_gdp_billions_saar=bundle.initial_nominal_gdp_billions_saar,
        initial_real_gdp_billions_chained_saar=bundle.initial_real_gdp_billions_chained_saar,
        issuance_strategy=bundle.issuance_strategy,
        scenario_name="baseline_warmup",
        data_vintage=bundle.cbo_vintage,
    )
    stock = result.ending_stock.copy()
    stock.reset_scenario_markers()
    last = result.quarterly.iloc[-1]
    return StartingState(
        stock,
        float(last["nominal_gdp_billions_saar"]),
        float(last["real_gdp_billions_chained_saar"]),
    )


def build_preset_scenario(
    bundle: BaselineBundle,
    preset: str,
    *,
    start_period: str | pd.Period = "2025Q4",
    end_period: str | pd.Period = "2036Q3",
    shock_start_period: str | pd.Period = "2027Q1",
    shock_duration_quarters: int | None = None,
    inflation_rate: float | None = None,
    rate_shock_basis_points: float | None = None,
    rate_response_lag_quarters: int | None = None,
) -> Scenario:
    """Build one of the named, imposed experiments from the CBO-like baseline."""

    if preset not in PRESET_DESCRIPTIONS:
        raise ValueError(f"unknown preset {preset!r}; choose from {sorted(PRESET_DESCRIPTIONS)}")
    baseline = build_baseline_scenario(bundle, start_period=start_period, end_period=end_period)
    if preset == "baseline":
        return baseline

    defaults = {
        "inflation_no_rate_response": (0.10, 4, 0.0, 0),
        "inflation_immediate_rate_response": (0.10, 4, 500.0, 0),
        "inflation_delayed_rate_response": (0.10, 4, 500.0, 4),
        "persistent_financial_repression": (0.06, 12, 0.0, 0),
    }
    default_inflation, default_duration, default_rate_shock, default_lag = defaults[preset]
    inflation_rate = default_inflation if inflation_rate is None else inflation_rate
    duration = default_duration if shock_duration_quarters is None else shock_duration_quarters
    rate_shock_basis_points = (
        default_rate_shock if rate_shock_basis_points is None else rate_shock_basis_points
    )
    lag = default_lag if rate_response_lag_quarters is None else rate_response_lag_quarters
    if inflation_rate <= -1 or inflation_rate > 1:
        raise ValueError("inflation_rate must be greater than -100% and no more than 100%")
    if duration <= 0 or lag < 0:
        raise ValueError("duration must be positive and lag cannot be negative")

    assumptions = baseline.quarterly_assumptions.copy()
    shock_start = pd.Period(shock_start_period, freq="Q")
    shock_periods = pd.period_range(shock_start, periods=duration, freq="Q")
    shock_periods = shock_periods.intersection(assumptions.index)
    assumptions.loc[shock_periods, "annual_inflation_rate"] = inflation_rate

    # TIPS use a lagged CPI-U reference index. In an experimental scenario the
    # imposed general inflation path is used as the CPI-U proxy one quarter later.
    tips_periods = (shock_periods + 1).intersection(assumptions.index)
    assumptions.loc[tips_periods, "annual_tips_reference_inflation_rate"] = inflation_rate

    rate_shock = rate_shock_basis_points / 10_000.0
    rate_start = shock_start + lag
    rate_periods = pd.period_range(rate_start, periods=duration, freq="Q").intersection(
        assumptions.index
    )
    for column in [
        "short_issuance_rate",
        "intermediate_issuance_rate",
        "long_issuance_rate",
        "tips_real_issuance_rate",
    ]:
        assumptions.loc[rate_periods, column] += rate_shock

    return Scenario(
        name=preset,
        description=PRESET_DESCRIPTIONS[preset],
        quarterly_assumptions=assumptions,
        imposed_parameters={
            "inflation_rate": inflation_rate,
            "inflation_shock_start": str(shock_start),
            "inflation_duration_quarters": duration,
            "rate_shock_basis_points": rate_shock_basis_points,
            "rate_response_lag_quarters": lag,
            "primary_deficit_behavior": "unchanged nominal CBO fiscal-year path",
            "real_gdp_growth_behavior": "unchanged CBO quarterly path",
        },
    )


def build_custom_scenario(
    bundle: BaselineBundle,
    *,
    start_period: str | pd.Period,
    end_period: str | pd.Period,
    shock_start_period: str | pd.Period,
    shock_duration_quarters: int,
    inflation_rate: float,
    real_growth_adjustment_percentage_points: float = 0.0,
    short_rate_shock_basis_points: float = 0.0,
    intermediate_rate_shock_basis_points: float = 0.0,
    long_rate_shock_basis_points: float = 0.0,
    tips_real_rate_shock_basis_points: float = 0.0,
    rate_response_lag_quarters: int = 0,
    rate_shock_duration_quarters: int | None = None,
) -> Scenario:
    """Construct a custom path with independently imposed macro and rate changes."""

    baseline = build_baseline_scenario(bundle, start_period=start_period, end_period=end_period)
    rate_duration = (
        shock_duration_quarters
        if rate_shock_duration_quarters is None
        else rate_shock_duration_quarters
    )
    if shock_duration_quarters <= 0 or rate_duration <= 0 or rate_response_lag_quarters < 0:
        raise ValueError("shock duration must be positive and rate lag cannot be negative")
    if inflation_rate <= -1 or inflation_rate > 1:
        raise ValueError("inflation_rate must be greater than -100% and no more than 100%")
    assumptions = baseline.quarterly_assumptions.copy()
    shock_start = pd.Period(shock_start_period, freq="Q")
    shock_periods = pd.period_range(
        shock_start, periods=shock_duration_quarters, freq="Q"
    ).intersection(assumptions.index)
    assumptions.loc[shock_periods, "annual_inflation_rate"] = inflation_rate
    assumptions.loc[shock_periods, "annual_real_gdp_growth_rate"] += (
        real_growth_adjustment_percentage_points / 100.0
    )
    assumptions.loc[
        (shock_periods + 1).intersection(assumptions.index),
        "annual_tips_reference_inflation_rate",
    ] = inflation_rate
    rate_periods = pd.period_range(
        shock_start + rate_response_lag_quarters,
        periods=rate_duration,
        freq="Q",
    ).intersection(assumptions.index)
    shocks = {
        "short_issuance_rate": short_rate_shock_basis_points,
        "intermediate_issuance_rate": intermediate_rate_shock_basis_points,
        "long_issuance_rate": long_rate_shock_basis_points,
        "tips_real_issuance_rate": tips_real_rate_shock_basis_points,
    }
    for column, basis_points in shocks.items():
        assumptions.loc[rate_periods, column] += basis_points / 10_000.0
    return Scenario(
        name="custom",
        description="User-imposed deterministic paths; no behavioral response is inferred.",
        quarterly_assumptions=assumptions,
        imposed_parameters={
            "inflation_rate": inflation_rate,
            "shock_start": str(shock_start),
            "shock_duration_quarters": shock_duration_quarters,
            "real_growth_adjustment_percentage_points": real_growth_adjustment_percentage_points,
            "short_rate_shock_basis_points": short_rate_shock_basis_points,
            "intermediate_rate_shock_basis_points": intermediate_rate_shock_basis_points,
            "long_rate_shock_basis_points": long_rate_shock_basis_points,
            "tips_real_rate_shock_basis_points": tips_real_rate_shock_basis_points,
            "rate_response_lag_quarters": rate_response_lag_quarters,
            "rate_shock_duration_quarters": rate_duration,
        },
    )


def apply_manual_primary_deficit(
    scenario: Scenario,
    bundle: BaselineBundle,
    *,
    mode: Literal["percent_gdp", "annual_nominal_billions"],
    value: float,
    initial_nominal_gdp_billions_saar: float | None = None,
) -> Scenario:
    """Replace the exogenous primary-deficit path in either supported mode."""

    assumptions = scenario.quarterly_assumptions.copy()
    if mode == "annual_nominal_billions":
        assumptions["primary_deficit_billions"] = value / 4.0
    elif mode == "percent_gdp":
        if value < -1 or value > 1:
            raise ValueError("primary deficit share must lie between -100% and 100%")
        nominal = (
            bundle.initial_nominal_gdp_billions_saar
            if initial_nominal_gdp_billions_saar is None
            else initial_nominal_gdp_billions_saar
        )
        quarterly_values = []
        for _, row in assumptions.iterrows():
            real_change = (1.0 + float(row["annual_real_gdp_growth_rate"])) ** 0.25
            price_change = (1.0 + float(row["annual_inflation_rate"])) ** 0.25
            nominal *= real_change * price_change
            quarterly_values.append(value * nominal / 4.0)
        assumptions["primary_deficit_billions"] = quarterly_values
    else:
        raise ValueError("mode must be 'percent_gdp' or 'annual_nominal_billions'")
    parameters = dict(scenario.imposed_parameters)
    parameters.update({"manual_primary_deficit_mode": mode, "manual_primary_deficit_value": value})
    return replace(
        scenario,
        name=f"{scenario.name}_manual_primary",
        quarterly_assumptions=assumptions,
        imposed_parameters=parameters,
    )


def compare_scenarios(baseline: pd.DataFrame, scenario: pd.DataFrame) -> pd.DataFrame:
    """Return aligned levels, differences, and an exact two-factor ratio decomposition."""

    left = baseline.set_index("quarter")
    right = scenario.set_index("quarter")
    common = left.index.intersection(right.index)
    left = left.loc[common]
    right = right.loc[common]
    result = pd.DataFrame(index=common)
    result["quarter_end"] = right["quarter_end"]
    for column in [
        "debt_held_by_public_gdp_ratio",
        "debt_held_by_public_billions",
        "nominal_gdp_billions_saar",
        "modeled_debt_interest_cost_billions",
        "cumulative_modeled_interest_billions",
        "average_effective_marketable_rate_excluding_tips_inflation",
    ]:
        result[f"baseline_{column}"] = left[column]
        result[f"scenario_{column}"] = right[column]
        result[f"difference_{column}"] = right[column] - left[column]

    db = left["debt_held_by_public_billions"]
    ds = right["debt_held_by_public_billions"]
    gb = left["nominal_gdp_billions_saar"]
    gs = right["nominal_gdp_billions_saar"]
    # Shapley decomposition of Ds/Gs - Db/Gb. The two contributions sum
    # exactly and do not depend on an arbitrary ordering of numerator/denominator.
    result["debt_gdp_difference_from_nominal_debt"] = 0.5 * (
        (ds / gb - db / gb) + (ds / gs - db / gs)
    )
    result["debt_gdp_difference_from_nominal_gdp"] = 0.5 * (
        (db / gs - db / gb) + (ds / gs - ds / gb)
    )
    return result.reset_index()
