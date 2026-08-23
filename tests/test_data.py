from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from debt_sim.data import (
    DEFAULT_DATA_ROOT,
    _normalize_cbo_budget,
    _normalize_cbo_economy,
    _normalize_cbo_long_term_budget,
    _normalize_cbo_long_term_economy,
    _normalize_treasury,
    _write_snapshot,
)
from debt_sim.scenarios import build_extended_quarterly_economy

RAW = DEFAULT_DATA_ROOT / "raw" / "2026-08-22"


def test_pinned_raw_snapshots_reproduce_normalized_baseline_inputs():
    budget = _normalize_cbo_budget((RAW / "cbo_ten_year_budget_2026-02.csv").read_bytes())
    economy = _normalize_cbo_economy((RAW / "cbo_quarterly_economy_2026-02.csv").read_bytes())
    assert budget.loc[budget["fiscal_year"] == 2026, "primary_deficit_billions"].item() == (
        pytest.approx(813.727)
    )
    assert budget.loc[budget["fiscal_year"] == 2036, "debt_held_by_public_gdp_ratio"].item() == (
        pytest.approx(1.20209)
    )
    assert economy["quarter"].iloc[0] == "2023Q1"
    assert economy["quarter"].iloc[-1] == "2036Q4"


def test_pinned_raw_treasury_snapshots_reproduce_public_debt_reconciliation():
    table1 = json.loads((RAW / "treasury_mspd_table1_2025-09-30.json").read_bytes())["data"]
    detail = json.loads((RAW / "treasury_mspd_securities_2025-09-30.json").read_bytes())["data"]
    auctions = json.loads((RAW / "treasury_frn_auctions_through_2025-09-30.json").read_bytes())[
        "data"
    ]
    securities, initial = _normalize_treasury(table1, detail, auctions, "2025-09-30")
    assert len(securities) == 458
    assert initial["debt_held_by_public_billions"].item() == pytest.approx(30_277.7664202628)
    assert (
        initial["modeled_marketable_debt_billions"].item()
        + initial["other_public_debt_billions"].item()
    ) == pytest.approx(initial["debt_held_by_public_billions"].item())
    assert pd.Series(
        [
            initial[f"issuance_share_{kind}"].item()
            for kind in ["bill", "note", "bond", "tips", "frn"]
        ]
    ).sum() == pytest.approx(1.0)


def test_snapshot_writer_refuses_silent_vintage_overwrite(tmp_path: Path):
    target = tmp_path / "snapshot.csv"
    _write_snapshot(target, b"first", force=False)
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        _write_snapshot(target, b"second", force=False)
    assert target.read_bytes() == b"first"


def test_long_term_snapshots_reproduce_2056_values_and_smooth_quarters():
    budget = _normalize_cbo_long_term_budget(
        (RAW / "cbo_long_term_budget_2026-02-25.csv").read_bytes()
    )
    economy = _normalize_cbo_long_term_economy(
        (RAW / "cbo_long_term_economic_levels_2026-02-25.csv").read_bytes(),
        (RAW / "cbo_long_term_economic_rates_2026-02-25.csv").read_bytes(),
    )
    assert budget.loc[budget["fiscal_year"] == 2056, "debt_held_by_public_gdp_ratio"].item() == (
        pytest.approx(1.75076)
    )
    assert economy.loc[economy["year"] == 2056, "nominal_gdp_billions"].item() == (
        pytest.approx(96_521.6)
    )


def test_quarterly_long_term_interpolation_exactly_matches_annual_means():
    from debt_sim.data import load_baseline_bundle

    bundle = load_baseline_bundle()
    quarterly = build_extended_quarterly_economy(bundle)
    for year in (2037, 2045, 2056):
        periods = [pd.Period(f"{year}Q{quarter}", freq="Q") for quarter in range(1, 5)]
        annual_mean = quarterly.loc[periods, "nominal_gdp_billions_saar"].mean()
        source = bundle.cbo_long_term_economic.set_index("year").loc[
            year, "nominal_gdp_billions"
        ]
        assert annual_mean == pytest.approx(source, rel=1e-12)
