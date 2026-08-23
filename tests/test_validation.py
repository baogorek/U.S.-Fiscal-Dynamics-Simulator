from __future__ import annotations

import pytest

from debt_sim.data import load_baseline_bundle
from debt_sim.validation import run_baseline_validation


def test_pinned_treasury_reconciliation():
    bundle = load_baseline_bundle()
    stock = bundle.initial_stock
    assert stock.debt_held_by_public_billions == pytest.approx(30_277.7664202628)
    assert stock.marketable_debt_billions == pytest.approx(29_695.0023832681)
    assert stock.other_public_debt_billions == pytest.approx(582.76403699465)
    assert len(stock.cohorts) == 458


def test_cbo_baseline_validation_has_required_metrics():
    _, result, table = run_baseline_validation()
    assert result.quarterly["debt_identity_residual_billions"].abs().max() < 1e-8
    assert set(table["metric"]) >= {
        "debt_held_by_public_billions",
        "debt_held_by_public_gdp_ratio",
        "primary_deficit_billions",
        "interest_measure_billions",
        "total_deficit_billions",
    }
    primary = table[table["metric"] == "primary_deficit_billions"]
    assert primary["difference"].abs().max() < 1e-9
