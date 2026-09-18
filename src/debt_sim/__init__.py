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
from debt_sim.crisis import (
    DebtYieldFeedbackRule,
    InterestIncomeRule,
    PrivateAbsorptionRule,
    PrivateFinancingCapacityError,
    SequentialCrisisResult,
    SequentialFeedbackRule,
    build_private_absorption_diagnostics,
    run_sequential_crisis_simulation,
    summarize_crisis_path,
    summarize_private_absorption,
)
from debt_sim.data import load_baseline_bundle
from debt_sim.feedback import (
    MacroFeedbackRule,
    MacroFeedbackSolution,
    MacroPolicySimulationResult,
    build_macro_feedback_path,
    run_macro_policy_simulation,
)
from debt_sim.model import SimulationResult, run_simulation
from debt_sim.policy import (
    FedBalanceSheetState,
    PolicyRegime,
    PolicyRule,
    PolicySimulationResult,
    apply_policy_regime,
    run_policy_simulation,
)
from debt_sim.scenarios import build_baseline_scenario, build_preset_scenario
from debt_sim.treasury import (
    TreasuryBuybackInstruction,
    TreasuryBuybackPlan,
    TreasuryBuybackResult,
    TreasuryIssuanceRule,
    adaptive_issuance_strategy,
    build_adaptive_issuance_strategy_path,
    execute_treasury_buyback,
    fixed_rate_price_per_dollar_face,
)

__all__ = [
    "SimulationResult",
    "ClosureTarget",
    "ConfidenceShock",
    "DebtYieldFeedbackRule",
    "FedBalanceSheetState",
    "InflationEpisode",
    "InflationRateResponse",
    "InterestIncomeRule",
    "MacroFeedbackRule",
    "MacroFeedbackSolution",
    "MacroPolicySimulationResult",
    "PolicyRegime",
    "PolicyRule",
    "PolicySimulationResult",
    "PrivateAbsorptionRule",
    "PrivateFinancingCapacityError",
    "SequentialCrisisResult",
    "SequentialFeedbackRule",
    "TreasuryBuybackInstruction",
    "TreasuryBuybackPlan",
    "TreasuryBuybackResult",
    "TreasuryIssuanceRule",
    "adaptive_issuance_strategy",
    "apply_policy_regime",
    "build_adaptive_issuance_strategy_path",
    "build_baseline_scenario",
    "build_macro_feedback_path",
    "build_private_absorption_diagnostics",
    "build_preset_scenario",
    "apply_confidence_shock",
    "load_baseline_bundle",
    "execute_treasury_buyback",
    "fixed_rate_price_per_dollar_face",
    "run_simulation",
    "run_policy_simulation",
    "run_sequential_crisis_simulation",
    "run_macro_policy_simulation",
    "solve_financial_repression",
    "solve_fiscal_adjustment",
    "solve_haircut_equivalent",
    "solve_inflation_closure",
    "summarize_crisis_path",
    "summarize_private_absorption",
]

__version__ = "0.2.0"
