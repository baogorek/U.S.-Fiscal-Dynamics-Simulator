"""Vintage-preserving acquisition, normalization, and offline data loading."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests

from debt_sim.debt_stock import DebtStock, IssuanceStrategy
from debt_sim.instruments import InstrumentType, TreasuryCohort

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_ROOT = PROJECT_ROOT / "data"
DEFAULT_CBO_VINTAGE = "2026-02"
DEFAULT_CBO_LONG_TERM_RELEASE = "2026-02-25"
DEFAULT_TREASURY_OBSERVATION_DATE = "2025-09-30"

CBO_RAW_BASE = "https://raw.githubusercontent.com/US-CBO/cbo-data/main"
TREASURY_API_BASE = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"


@dataclass(frozen=True, slots=True)
class BaselineBundle:
    initial_stock: DebtStock
    issuance_strategy: IssuanceStrategy
    cbo_fiscal_baseline: pd.DataFrame
    cbo_quarterly_economy: pd.DataFrame
    cbo_long_term_budget: pd.DataFrame
    cbo_long_term_economic: pd.DataFrame
    initial_nominal_gdp_billions_saar: float
    initial_real_gdp_billions_chained_saar: float
    cbo_vintage: str
    treasury_observation_date: str
    metadata: dict[str, Any]


LONG_TERM_BUDGET_URL = (
    f"{CBO_RAW_BASE}/data/budget/long_term_budget/annual_fy_2026-02.csv"
)
LONG_TERM_ECONOMIC_LEVELS_URL = (
    f"{CBO_RAW_BASE}/data/economic/long_term_economic/levels_2026-02.csv"
)
LONG_TERM_ECONOMIC_RATES_URL = (
    f"{CBO_RAW_BASE}/data/economic/long_term_economic/rates_2026-02.csv"
)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write_snapshot(path: Path, payload: bytes, *, force: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        raise FileExistsError(
            f"Refusing to overwrite vintage file {path}. Use --force only deliberately."
        )
    path.write_bytes(payload)


def _download(
    session: requests.Session,
    url: str,
    params: dict[str, Any] | None = None,
) -> tuple[bytes, dict[str, str]]:
    response = session.get(url, params=params, timeout=90)
    response.raise_for_status()
    headers = {
        key: value
        for key, value in response.headers.items()
        if key.lower() in {"etag", "last-modified", "content-type", "date"}
    }
    return response.content, headers


def _as_number(value: Any) -> float | None:
    if value in (None, "", "null", "*"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_cbo_budget(payload: bytes) -> pd.DataFrame:
    raw = pd.read_csv(io.BytesIO(payload))
    pivot = raw.pivot(index="date", columns="variable", values="value")
    years = pd.Index([f"FY{year}" for year in range(2025, 2037)], name="date")
    pivot = pivot.reindex(years)
    result = pd.DataFrame(
        {
            "fiscal_year": [int(value.removeprefix("FY")) for value in pivot.index],
            # CBO represents deficits as negative budget balances. The simulator
            # uses positive values for borrowing requirements.
            "primary_deficit_billions": -pivot["proj_primary_deficit"].to_numpy(),
            "cbo_net_interest_outlays_billions": pivot["proj_outlays_net_interest"].to_numpy(),
            "total_deficit_billions": -pivot["proj_deficit_total"].to_numpy(),
            "other_financing_adjustment_billions": pivot[
                "proj_debt_change_other_financing"
            ].to_numpy(),
            "debt_held_by_public_billions": pivot["proj_debt_held_by_public"].to_numpy(),
            "debt_held_by_public_gdp_ratio": pivot["proj_debt_held_by_public_gdp_share"].to_numpy()
            / 100.0,
            "cbo_average_debt_interest_rate": pivot["proj_debt_avg_interest_rate"].to_numpy()
            / 100.0,
        }
    )
    result["end_of_fiscal_year_gdp_billions_saar"] = (
        result["debt_held_by_public_billions"] / result["debt_held_by_public_gdp_ratio"]
    )
    return result


def _normalize_cbo_economy(payload: bytes) -> pd.DataFrame:
    raw = pd.read_csv(io.BytesIO(payload))
    wanted = [
        "gdp",
        "real_gdp",
        "gdp_price_index",
        "cpiu",
        "treasury_bill_rate_3mo",
        "treasury_note_rate_10yr",
    ]
    raw = raw[raw["variable"].isin(wanted)].copy()
    pivot = raw.pivot(index="date", columns="variable", values="value").reset_index()
    pivot["quarter"] = pivot["date"].str.replace("q", "Q", regex=False)
    pivot["quarter_end"] = pd.PeriodIndex(pivot["quarter"], freq="Q").end_time.normalize()
    result = pivot.rename(
        columns={
            "gdp": "nominal_gdp_billions_saar",
            "real_gdp": "real_gdp_billions_chained_saar",
            "cpiu": "cpi_u_index",
            "treasury_bill_rate_3mo": "treasury_bill_3_month_rate",
            "treasury_note_rate_10yr": "treasury_note_10_year_rate",
        }
    )[
        [
            "quarter",
            "quarter_end",
            "nominal_gdp_billions_saar",
            "real_gdp_billions_chained_saar",
            "gdp_price_index",
            "cpi_u_index",
            "treasury_bill_3_month_rate",
            "treasury_note_10_year_rate",
        ]
    ]
    result["treasury_bill_3_month_rate"] /= 100.0
    result["treasury_note_10_year_rate"] /= 100.0
    return result.sort_values("quarter").reset_index(drop=True)


def _normalize_cbo_long_term_budget(payload: bytes) -> pd.DataFrame:
    """Normalize CBO's February 25, 2026 annual long-term budget file."""

    raw = pd.read_csv(io.BytesIO(payload))
    pivot = raw.pivot(index="date", columns="variable", values="value")
    years = pd.Index([f"FY{year}" for year in range(2026, 2057)], name="date")
    pivot = pivot.reindex(years)
    gdp = pivot["lt_gdp_trillions"].to_numpy(dtype=float) * 1000.0
    primary_share = pivot["lt_primary_deficit_gdp_share"].to_numpy(dtype=float) / 100.0
    interest_share = pivot["lt_outlays_net_interest_gdp_share"].to_numpy(dtype=float) / 100.0
    total_share = pivot["lt_deficit_total_gdp_share"].to_numpy(dtype=float) / 100.0
    debt_share = pivot["lt_debt_held_by_public_gdp_share"].to_numpy(dtype=float) / 100.0
    return pd.DataFrame(
        {
            "fiscal_year": [int(value.removeprefix("FY")) for value in pivot.index],
            # CBO uses negative values for deficits in the long-term workbook.
            "primary_deficit_billions": -primary_share * gdp,
            "cbo_net_interest_outlays_billions": interest_share * gdp,
            "total_deficit_billions": -total_share * gdp,
            "debt_held_by_public_billions": debt_share * gdp,
            "debt_held_by_public_gdp_ratio": debt_share,
            "end_of_fiscal_year_gdp_billions_saar": gdp,
        }
    )


def _normalize_cbo_long_term_economy(levels_payload: bytes, rates_payload: bytes) -> pd.DataFrame:
    """Select the annual levels and rates used by the post-2036 extension."""

    levels_raw = pd.read_csv(io.BytesIO(levels_payload))
    rates_raw = pd.read_csv(io.BytesIO(rates_payload))
    wanted_levels = {
        "nominal_gdp_level",
        "real_gdp_level",
        "gdp_price_index_level",
        "cpiu_index_level",
    }
    wanted_rates = {
        "real_gdp_growth",
        "nominal_gdp_growth",
        "gdp_price_growth",
        "cpiu_growth",
        "interest_rate_fed_debt",
    }
    levels = levels_raw[levels_raw["variable"].isin(wanted_levels)].pivot(
        index="date", columns="variable", values="value"
    )
    rates = rates_raw[rates_raw["variable"].isin(wanted_rates)].pivot(
        index="date", columns="variable", values="value"
    )
    annual = levels.join(rates, how="outer").loc[2026:2056].reset_index(names="year")
    annual["nominal_gdp_billions"] = annual.pop("nominal_gdp_level") * 1000.0
    annual["real_gdp_billions_chained"] = annual.pop("real_gdp_level") * 1000.0
    # CBO's level indexes use 1.0 in the base year; v0.1's quarterly file uses 100.
    annual["gdp_price_index"] = annual.pop("gdp_price_index_level") * 100.0
    annual["cpi_u_index"] = annual.pop("cpiu_index_level") * 100.0
    for column in wanted_rates:
        annual[column] /= 100.0
    return annual.sort_values("year").reset_index(drop=True)


CLASS_TO_TYPE = {
    "Bills Maturity Value": InstrumentType.BILL,
    "Notes": InstrumentType.NOTE,
    "Bonds": InstrumentType.BOND,
    "Inflation-Protected Securities": InstrumentType.TIPS,
    "Floating Rate Notes": InstrumentType.FRN,
}

TYPE_TO_SUMMARY_CLASS = {
    InstrumentType.BILL: "Bills",
    InstrumentType.NOTE: "Notes",
    InstrumentType.BOND: "Bonds",
    InstrumentType.TIPS: "Treasury Inflation-Protected Securities",
    InstrumentType.FRN: "Floating Rate Notes",
}


def _frn_spreads(auction_rows: list[dict[str, Any]]) -> dict[str, float]:
    spreads: dict[str, float] = {}
    for row in sorted(auction_rows, key=lambda item: item.get("issue_date") or ""):
        cusip = row.get("cusip")
        spread = _as_number(row.get("spread"))
        if cusip and spread is not None and row.get("reopening") == "No":
            spreads[cusip] = spread / 100.0
    return spreads


def _normalize_treasury(
    table1_rows: list[dict[str, Any]],
    security_rows: list[dict[str, Any]],
    auction_rows: list[dict[str, Any]],
    observation_date: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary = {
        row["security_class_desc"]: float(row["debt_held_public_mil_amt"]) / 1000.0
        for row in table1_rows
        if row["security_type_desc"] == "Marketable"
        and row["security_class_desc"] in set(TYPE_TO_SUMMARY_CLASS.values())
    }
    total_public = next(
        float(row["debt_held_public_mil_amt"]) / 1000.0
        for row in table1_rows
        if row["security_type_desc"] == "Total Public Debt Outstanding"
    )

    # MSPD includes subtotals in the same endpoint. A Treasury CUSIP here is a
    # nine-character identifier beginning with 912; selecting that pattern
    # avoids double-counting the subtotals.
    detail = [
        row
        for row in security_rows
        if row.get("security_class1_desc") in CLASS_TO_TYPE
        and isinstance(row.get("security_class2_desc"), str)
        and len(row["security_class2_desc"]) == 9
        and row["security_class2_desc"].startswith("912")
    ]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in detail:
        grouped.setdefault(row["security_class2_desc"], []).append(row)

    unscaled_by_type: dict[InstrumentType, float] = {kind: 0.0 for kind in InstrumentType}
    for rows in grouped.values():
        outstanding = next(
            (
                _as_number(row["outstanding_amt"])
                for row in rows
                if _as_number(row["outstanding_amt"]) is not None
            ),
            None,
        )
        if outstanding is not None:
            unscaled_by_type[CLASS_TO_TYPE[rows[0]["security_class1_desc"]]] += outstanding / 1000.0
    scales = {
        kind: summary[TYPE_TO_SUMMARY_CLASS[kind]] / unscaled_by_type[kind]
        for kind in InstrumentType
    }
    spreads = _frn_spreads(auction_rows)

    normalized: list[dict[str, Any]] = []
    observation_period = pd.Period(observation_date, freq="Q")
    for cusip, rows in sorted(grouped.items()):
        instrument_type = CLASS_TO_TYPE[rows[0]["security_class1_desc"]]
        maturity_date = min(row["maturity_date"] for row in rows if row["maturity_date"] != "null")
        if pd.Period(maturity_date, freq="Q") <= observation_period:
            continue
        outstanding_millions = next(
            (
                _as_number(row["outstanding_amt"])
                for row in rows
                if _as_number(row["outstanding_amt"]) is not None
            ),
            None,
        )
        if outstanding_millions is None or outstanding_millions <= 0:
            continue
        scale = scales[instrument_type]
        principal = outstanding_millions / 1000.0 * scale
        issue_amounts = np.array(
            [(_as_number(row["issued_amt"]) or 0.0) for row in rows], dtype=float
        )
        yields = np.array(
            [(_as_number(row["yield_pct"]) or np.nan) / 100.0 for row in rows],
            dtype=float,
        )
        valid_yield = np.isfinite(yields) & (issue_amounts > 0)
        coupon_candidates = [
            value / 100.0
            for row in rows
            if (value := _as_number(row["interest_rate_pct"])) is not None
        ]
        coupon = coupon_candidates[0] if coupon_candidates else 0.0
        if instrument_type is InstrumentType.FRN:
            spread = spreads.get(cusip)
            if spread is None:
                spread = next(
                    (
                        value / 100.0
                        for row in rows
                        if (value := _as_number(row["yield_pct"])) is not None
                    ),
                    0.0,
                )
            effective = 0.0  # Reset from the scenario short rate in the first quarter.
        else:
            spread = 0.0
            effective = (
                float(np.average(yields[valid_yield], weights=issue_amounts[valid_yield]))
                if valid_yield.any()
                else coupon
            )
        if instrument_type is InstrumentType.BILL:
            coupon = 0.0

        issued_total = issue_amounts.sum() / 1000.0 * scale
        original_principal = (
            min(principal, issued_total)
            if instrument_type is InstrumentType.TIPS and issued_total > 0
            else principal
        )
        normalized.append(
            {
                "cohort_id": f"mspd-{observation_date}-{cusip}",
                "cusip": cusip,
                "instrument_type": instrument_type.value,
                "issue_date": min(row["issue_date"] for row in rows if row["issue_date"] != "null"),
                "maturity_date": maturity_date,
                "principal_billions": principal,
                "original_principal_billions": original_principal,
                "coupon_rate": coupon,
                "effective_interest_rate": effective,
                "frn_spread": spread,
                "public_holding_scale_factor": scale,
            }
        )
    securities = pd.DataFrame(normalized)
    modeled_marketable = securities["principal_billions"].sum()
    other_public = total_public - modeled_marketable
    shares = securities.groupby("instrument_type")["principal_billions"].sum() / modeled_marketable
    initial = pd.DataFrame(
        [
            {
                "treasury_observation_date": observation_date,
                "debt_held_by_public_billions": total_public,
                "modeled_marketable_debt_billions": modeled_marketable,
                "other_public_debt_billions": other_public,
                **{
                    f"issuance_share_{kind.value}": float(shares[kind.value])
                    for kind in InstrumentType
                },
            }
        ]
    )
    return securities, initial


def refresh_data(
    *,
    data_root: Path = DEFAULT_DATA_ROOT,
    cbo_vintage: str = DEFAULT_CBO_VINTAGE,
    treasury_observation_date: str = DEFAULT_TREASURY_OBSERVATION_DATE,
    retrieval_date: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Download official sources, preserve raw snapshots, and normalize inputs."""

    retrieval_date = retrieval_date or date.today().isoformat()
    raw_dir = data_root / "raw" / retrieval_date
    processed_dir = data_root / "processed"
    metadata_dir = data_root / "metadata"
    session = requests.Session()
    session.headers.update({"User-Agent": "us-debt-simulator/0.1 data refresh"})

    source_specs = {
        "cbo_ten_year_budget": (
            f"{CBO_RAW_BASE}/data/budget/ten_year_budget/annual_fy_{cbo_vintage}.csv",
            None,
            f"cbo_ten_year_budget_{cbo_vintage}.csv",
        ),
        "cbo_quarterly_economy": (
            f"{CBO_RAW_BASE}/data/economic/economic_projections/quarterly_{cbo_vintage}.csv",
            None,
            f"cbo_quarterly_economy_{cbo_vintage}.csv",
        ),
        "cbo_budget_schema": (
            f"{CBO_RAW_BASE}/data/budget/ten_year_budget/schema.json",
            None,
            "cbo_ten_year_budget_schema.json",
        ),
        "cbo_economy_schema": (
            f"{CBO_RAW_BASE}/data/economic/economic_projections/schema.json",
            None,
            "cbo_economic_projections_schema.json",
        ),
        "treasury_mspd_summary": (
            f"{TREASURY_API_BASE}/v1/debt/mspd/mspd_table_1",
            {"filter": f"record_date:eq:{treasury_observation_date}", "page[size]": 5000},
            f"treasury_mspd_table1_{treasury_observation_date}.json",
        ),
        "treasury_mspd_securities": (
            f"{TREASURY_API_BASE}/v1/debt/mspd/mspd_table_3_market",
            {"filter": f"record_date:eq:{treasury_observation_date}", "page[size]": 5000},
            f"treasury_mspd_securities_{treasury_observation_date}.json",
        ),
        "treasury_frn_auctions": (
            f"{TREASURY_API_BASE}/v1/accounting/od/auctions_query",
            {
                "filter": (f"floating_rate:eq:Yes,issue_date:lte:{treasury_observation_date}"),
                "page[size]": 5000,
            },
            f"treasury_frn_auctions_through_{treasury_observation_date}.json",
        ),
    }

    payloads: dict[str, bytes] = {}
    source_metadata: dict[str, Any] = {}
    for name, (url, params, filename) in source_specs.items():
        payload, headers = _download(session, url, params)
        payloads[name] = payload
        target = raw_dir / filename
        _write_snapshot(target, payload, force=force)
        source_metadata[name] = {
            "institution": (
                "Congressional Budget Office"
                if name.startswith("cbo")
                else "U.S. Treasury, Bureau of the Fiscal Service"
            ),
            "url": url,
            "query_parameters": params,
            "raw_snapshot": str(target.relative_to(data_root.parent)),
            "sha256": _sha256(payload),
            "http_headers": headers,
        }

    cbo_budget = _normalize_cbo_budget(payloads["cbo_ten_year_budget"])
    cbo_economy = _normalize_cbo_economy(payloads["cbo_quarterly_economy"])
    table1 = json.loads(payloads["treasury_mspd_summary"])["data"]
    securities_raw = json.loads(payloads["treasury_mspd_securities"])["data"]
    auctions = json.loads(payloads["treasury_frn_auctions"])["data"]
    securities, initial = _normalize_treasury(
        table1, securities_raw, auctions, treasury_observation_date
    )

    processed = {
        f"cbo_baseline_fy_{cbo_vintage}.csv": cbo_budget.to_csv(index=False).encode(),
        f"cbo_economy_quarterly_{cbo_vintage}.csv": cbo_economy.to_csv(index=False).encode(),
        f"treasury_securities_{treasury_observation_date}.csv": securities.to_csv(
            index=False
        ).encode(),
        f"initial_conditions_{treasury_observation_date}.csv": initial.to_csv(index=False).encode(),
    }
    for filename, payload in processed.items():
        _write_snapshot(processed_dir / filename, payload, force=force)

    manifest = {
        "model_data_release": "v0.1",
        "retrieved_at_utc": datetime.now(UTC).isoformat(),
        "retrieval_date": retrieval_date,
        "cbo_vintage": cbo_vintage,
        "cbo_report_release_date": "2026-02-11",
        "treasury_observation_date": treasury_observation_date,
        "sources": source_metadata,
        "processed_files": {
            name: {"sha256": _sha256(payload)} for name, payload in processed.items()
        },
        "transformations": [
            "CBO deficit signs converted to positive borrowing requirements.",
            "CBO percentage rates converted to decimal rates.",
            "MSPD security subtotals excluded by selecting nine-character 912 CUSIPs.",
            "Security-level principal scaled by instrument class to MSPD "
            "debt-held-by-public totals.",
            "Debt held by the public outside detailed marketable cohorts retained "
            "as other_public_debt.",
        ],
    }
    manifest_name = f"manifest_cbo-{cbo_vintage}_treasury-{treasury_observation_date}.json"
    _write_snapshot(
        metadata_dir / manifest_name,
        (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode(),
        force=force,
    )
    return manifest


def refresh_long_term_data(
    *,
    data_root: Path = DEFAULT_DATA_ROOT,
    retrieval_date: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Pin and normalize the February 25, 2026 CBO long-term extension.

    This is intentionally separate from :func:`refresh_data`: the February 11
    ten-year baseline and February 25 long-term release are different source
    products even though CBO's machine-readable repository labels both 2026-02.
    """

    retrieval_date = retrieval_date or date.today().isoformat()
    raw_dir = data_root / "raw" / retrieval_date
    processed_dir = data_root / "processed"
    metadata_dir = data_root / "metadata"
    session = requests.Session()
    session.headers.update({"User-Agent": "us-debt-simulator/0.2 long-term-data refresh"})
    source_specs = {
        "cbo_long_term_budget": (
            LONG_TERM_BUDGET_URL,
            f"cbo_long_term_budget_{DEFAULT_CBO_LONG_TERM_RELEASE}.csv",
        ),
        "cbo_long_term_economic_levels": (
            LONG_TERM_ECONOMIC_LEVELS_URL,
            f"cbo_long_term_economic_levels_{DEFAULT_CBO_LONG_TERM_RELEASE}.csv",
        ),
        "cbo_long_term_economic_rates": (
            LONG_TERM_ECONOMIC_RATES_URL,
            f"cbo_long_term_economic_rates_{DEFAULT_CBO_LONG_TERM_RELEASE}.csv",
        ),
    }
    payloads: dict[str, bytes] = {}
    sources: dict[str, Any] = {}
    for name, (url, filename) in source_specs.items():
        payload, headers = _download(session, url)
        payloads[name] = payload
        target = raw_dir / filename
        _write_snapshot(target, payload, force=force)
        sources[name] = {
            "institution": "Congressional Budget Office",
            "url": url,
            "query_parameters": None,
            "raw_snapshot": str(target.relative_to(data_root.parent)),
            "sha256": _sha256(payload),
            "http_headers": headers,
        }

    budget = _normalize_cbo_long_term_budget(payloads["cbo_long_term_budget"])
    economy = _normalize_cbo_long_term_economy(
        payloads["cbo_long_term_economic_levels"],
        payloads["cbo_long_term_economic_rates"],
    )
    processed = {
        f"cbo_long_term_budget_fy_{DEFAULT_CBO_LONG_TERM_RELEASE}.csv": (
            budget.to_csv(index=False).encode()
        ),
        f"cbo_long_term_economy_annual_{DEFAULT_CBO_LONG_TERM_RELEASE}.csv": (
            economy.to_csv(index=False).encode()
        ),
    }
    for filename, payload in processed.items():
        _write_snapshot(processed_dir / filename, payload, force=force)

    manifest = {
        "model_data_release": "v0.2",
        "retrieved_at_utc": datetime.now(UTC).isoformat(),
        "retrieval_date": retrieval_date,
        "cbo_long_term_release": DEFAULT_CBO_LONG_TERM_RELEASE,
        "cbo_report_release_date": "2026-02-25",
        "cbo_ten_year_baseline_release_date": "2026-02-11",
        "sources": sources,
        "processed_files": {
            name: {"sha256": _sha256(payload)} for name, payload in processed.items()
        },
        "transformations": [
            "CBO long-term deficit shares converted from negative percentages to positive "
            "borrowing requirements in billions using CBO's fiscal-year GDP series.",
            "Annual long-term economic level indexes rescaled from 1.0 to 100.",
            "Annual percentage rates converted to decimal rates.",
            "Quarterly interpolation is performed at scenario-build time using a constant "
            "within-year compound rate calibrated to each CBO annual mean.",
            "No intra-year volatility is added.",
        ],
    }
    manifest_path = metadata_dir / (
        f"manifest_cbo-long-term-{DEFAULT_CBO_LONG_TERM_RELEASE}.json"
    )
    _write_snapshot(
        manifest_path,
        (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode(),
        force=force,
    )
    return manifest


def load_baseline_bundle(
    *,
    data_root: Path = DEFAULT_DATA_ROOT,
    cbo_vintage: str = DEFAULT_CBO_VINTAGE,
    treasury_observation_date: str = DEFAULT_TREASURY_OBSERVATION_DATE,
) -> BaselineBundle:
    """Load pinned processed data without making network requests."""

    processed = data_root / "processed"
    securities = pd.read_csv(processed / f"treasury_securities_{treasury_observation_date}.csv")
    initial = pd.read_csv(processed / f"initial_conditions_{treasury_observation_date}.csv").iloc[0]
    fiscal = pd.read_csv(processed / f"cbo_baseline_fy_{cbo_vintage}.csv")
    economy = pd.read_csv(processed / f"cbo_economy_quarterly_{cbo_vintage}.csv")
    long_term_budget = pd.read_csv(
        processed / f"cbo_long_term_budget_fy_{DEFAULT_CBO_LONG_TERM_RELEASE}.csv"
    )
    long_term_economic = pd.read_csv(
        processed / f"cbo_long_term_economy_annual_{DEFAULT_CBO_LONG_TERM_RELEASE}.csv"
    )
    manifest_path = (
        data_root
        / "metadata"
        / f"manifest_cbo-{cbo_vintage}_treasury-{treasury_observation_date}.json"
    )
    metadata = json.loads(manifest_path.read_text())
    long_term_manifest_path = (
        data_root
        / "metadata"
        / f"manifest_cbo-long-term-{DEFAULT_CBO_LONG_TERM_RELEASE}.json"
    )
    metadata["long_term_extension"] = json.loads(long_term_manifest_path.read_text())

    # Preserve the ten-year values exactly through FY2036, then append the
    # distinct February 25 long-term release. CBO does not publish other means
    # of financing in the long-term workbook, so zero is an explicit extension
    # assumption rather than a residual fitted to CBO's debt path.
    long_extension = long_term_budget[long_term_budget["fiscal_year"] > 2036].copy()
    long_extension["other_financing_adjustment_billions"] = 0.0
    rate_by_year = long_term_economic.set_index("year")["interest_rate_fed_debt"]
    long_extension["cbo_average_debt_interest_rate"] = long_extension["fiscal_year"].map(
        rate_by_year
    )
    fiscal = pd.concat([fiscal, long_extension[fiscal.columns]], ignore_index=True)

    cohorts = [
        TreasuryCohort(
            cohort_id=row.cohort_id,
            instrument_type=InstrumentType(row.instrument_type),
            issue_period=pd.Period(row.issue_date, freq="Q"),
            maturity_period=pd.Period(row.maturity_date, freq="Q"),
            principal_billions=float(row.principal_billions),
            original_principal_billions=float(row.original_principal_billions),
            coupon_rate=float(row.coupon_rate),
            effective_interest_rate=float(row.effective_interest_rate),
            frn_spread=float(row.frn_spread),
        )
        for row in securities.itertuples(index=False)
    ]
    stock = DebtStock(cohorts, float(initial["other_public_debt_billions"]))
    shares = {kind: float(initial[f"issuance_share_{kind.value}"]) for kind in InstrumentType}
    strategy = IssuanceStrategy(new_borrowing_shares=shares)

    economy_indexed = economy.set_index("quarter")
    initial_quarter = str(pd.Period(treasury_observation_date, freq="Q"))
    if initial_quarter not in economy_indexed.index:
        raise ValueError(f"CBO economy data does not contain initial quarter {initial_quarter}")
    initial_economy = economy_indexed.loc[initial_quarter]
    return BaselineBundle(
        initial_stock=stock,
        issuance_strategy=strategy,
        cbo_fiscal_baseline=fiscal,
        cbo_quarterly_economy=economy,
        cbo_long_term_budget=long_term_budget,
        cbo_long_term_economic=long_term_economic,
        initial_nominal_gdp_billions_saar=float(initial_economy["nominal_gdp_billions_saar"]),
        initial_real_gdp_billions_chained_saar=float(
            initial_economy["real_gdp_billions_chained_saar"]
        ),
        cbo_vintage=cbo_vintage,
        treasury_observation_date=treasury_observation_date,
        metadata=metadata,
    )


def refresh_cli() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--cbo-vintage", default=DEFAULT_CBO_VINTAGE)
    parser.add_argument("--treasury-observation-date", default=DEFAULT_TREASURY_OBSERVATION_DATE)
    parser.add_argument("--retrieval-date")
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--include-long-term",
        action="store_true",
        help="also pin the distinct February 25, 2026 long-term extension",
    )
    args = parser.parse_args()
    manifest = refresh_data(
        data_root=args.data_root,
        cbo_vintage=args.cbo_vintage,
        treasury_observation_date=args.treasury_observation_date,
        retrieval_date=args.retrieval_date,
        force=args.force,
    )
    print(json.dumps(manifest, indent=2))
    if args.include_long_term:
        long_term_manifest = refresh_long_term_data(
            data_root=args.data_root,
            retrieval_date=args.retrieval_date,
            force=args.force,
        )
        print(json.dumps(long_term_manifest, indent=2))


if __name__ == "__main__":
    refresh_cli()
