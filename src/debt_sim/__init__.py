"""U.S. Fiscal Dynamics Simulator public API."""

from debt_sim.closure import (
    ClosureTarget,
    InflationEpisode,
    InflationRateResponse,
    solve_financial_repression,
    solve_fiscal_adjustment,
    solve_haircut_equivalent,
    solve_inflation_closure,
)
from debt_sim.confidence import ConfidenceShock, apply_confidence_shock
from debt_sim.data import load_baseline_bundle
from debt_sim.model import SimulationResult, run_simulation
from debt_sim.scenarios import build_baseline_scenario, build_preset_scenario

__all__ = [
    "SimulationResult",
    "ClosureTarget",
    "ConfidenceShock",
    "InflationEpisode",
    "InflationRateResponse",
    "build_baseline_scenario",
    "build_preset_scenario",
    "apply_confidence_shock",
    "load_baseline_bundle",
    "run_simulation",
    "solve_financial_repression",
    "solve_fiscal_adjustment",
    "solve_haircut_equivalent",
    "solve_inflation_closure",
]

__version__ = "0.2.0"
