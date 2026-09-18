from __future__ import annotations

import pandas as pd
import pytest

from debt_sim.debt_stock import DebtStock
from debt_sim.policy import (
    FedBalanceSheetState,
    PolicyRegime,
    PolicyRule,
    apply_policy_regime,
    run_policy_simulation,
)


def test_price_stability_regime_raises_shadow_rates_when_inflation_exceeds_target(
    make_assumptions,
):
    reference = make_assumptions(
        annual_inflation_rate=0.05,
        short_issuance_rate=0.03,
        intermediate_issuance_rate=0.04,
        long_issuance_rate=0.05,
        tips_real_issuance_rate=0.01,
    )
    policy = apply_policy_regime(
        reference,
        PolicyRule(
            regime=PolicyRegime.PRICE_STABILITY,
            reaction_smoothing=0.0,
        ),
    ).iloc[0]

    assert policy["policy_reaction_rate_adjustment"] == pytest.approx(0.045)
    assert policy["shadow_short_issuance_rate"] == pytest.approx(0.075)
    assert policy["shadow_intermediate_issuance_rate"] == pytest.approx(0.07375)
    assert policy["shadow_long_issuance_rate"] == pytest.approx(0.0725)
    assert policy["short_issuance_rate"] == policy["shadow_short_issuance_rate"]
    assert policy["required_fed_purchase_equivalent_gross_issuance_share"] == 0.0


def test_market_functioning_support_removes_liquidity_not_inflation_response(
    make_assumptions,
):
    reference = make_assumptions(
        annual_inflation_rate=0.05,
        short_issuance_rate=0.03,
        intermediate_issuance_rate=0.04,
        long_issuance_rate=0.05,
    )
    policy = apply_policy_regime(
        reference,
        PolicyRule(
            regime=PolicyRegime.MARKET_FUNCTIONING,
            reaction_smoothing=0.0,
            market_function_support_fraction=0.75,
        ),
        fiscal_risk_premium_basis_points=100.0,
        liquidity_premium_basis_points=200.0,
    ).iloc[0]

    assert policy["policy_reaction_rate_adjustment"] == pytest.approx(0.045)
    assert policy["shadow_short_issuance_rate"] == pytest.approx(0.105)
    assert policy["short_issuance_rate"] == pytest.approx(0.09)
    assert policy["short_yield_suppression_basis_points"] == pytest.approx(150.0)
    assert policy["required_fed_purchase_equivalent_gross_issuance_share"] == pytest.approx(0.3)


def test_sterilized_cap_and_fiscal_dominance_have_different_reserve_rates(
    make_assumptions,
):
    reference = make_assumptions(
        annual_inflation_rate=0.05,
        short_issuance_rate=0.03,
        intermediate_issuance_rate=0.04,
        long_issuance_rate=0.05,
    )
    sterilized = apply_policy_regime(
        reference,
        PolicyRule(
            regime=PolicyRegime.STERILIZED_YIELD_CAP,
            reaction_smoothing=0.0,
        ),
    ).iloc[0]
    dominance = apply_policy_regime(
        reference,
        PolicyRule(
            regime=PolicyRegime.FISCAL_DOMINANCE,
            reaction_smoothing=0.0,
        ),
    ).iloc[0]

    assert sterilized["short_issuance_rate"] == pytest.approx(0.03)
    assert dominance["short_issuance_rate"] == pytest.approx(0.03)
    assert sterilized["shadow_short_issuance_rate"] == pytest.approx(0.075)
    assert sterilized["iorb_rate"] == pytest.approx(0.075)
    assert dominance["iorb_rate"] == pytest.approx(0.03)
    assert sterilized["required_fed_purchase_equivalent_gross_issuance_share"] == pytest.approx(
        0.675
    )


def test_fed_balance_sheet_converts_purchases_to_reserves_and_tracks_deferred_remittances():
    state = FedBalanceSheetState(
        treasury_holdings_billions=50.0,
        reserve_balances_billions=40.0,
        average_treasury_yield=0.04,
    )
    quarter = state.advance(
        requested_treasury_purchases_billions=10.0,
        purchase_yield=0.03,
        iorb_rate=0.05,
        marketable_debt_billions=100.0,
    )

    assert quarter.treasury_interest_income_billions == pytest.approx(0.5)
    assert quarter.reserve_interest_expense_billions == pytest.approx(0.5)
    assert quarter.ending_state.treasury_holdings_billions == pytest.approx(60.0)
    assert quarter.ending_state.reserve_balances_billions == pytest.approx(50.0)
    assert quarter.ending_state.average_treasury_yield == pytest.approx(2.3 / 60.0)

    rollover_quarter = FedBalanceSheetState(
        treasury_holdings_billions=50.0,
        reserve_balances_billions=40.0,
        average_treasury_yield=0.02,
    ).advance(
        requested_treasury_purchases_billions=0.0,
        purchase_yield=0.06,
        iorb_rate=0.0,
        marketable_debt_billions=100.0,
        treasury_rollover_billions=10.0,
    )
    assert rollover_quarter.ending_state.treasury_holdings_billions == pytest.approx(50.0)
    assert rollover_quarter.ending_state.reserve_balances_billions == pytest.approx(40.0)
    assert rollover_quarter.ending_state.average_treasury_yield == pytest.approx(0.028)

    loss_quarter = FedBalanceSheetState(
        treasury_holdings_billions=100.0,
        reserve_balances_billions=200.0,
        average_treasury_yield=0.02,
    ).advance(
        requested_treasury_purchases_billions=0.0,
        purchase_yield=0.0,
        iorb_rate=0.04,
        marketable_debt_billions=100.0,
    )
    assert loss_quarter.net_income_billions == pytest.approx(-1.5)
    assert loss_quarter.remittance_to_treasury_billions == 0.0
    assert loss_quarter.ending_state.deferred_remittances_billions == pytest.approx(1.5)


def test_policy_simulation_exposes_consolidated_cost_of_sterilizing_a_yield_cap(
    make_cohort,
    make_assumptions,
):
    assumptions = make_assumptions(
        periods=2,
        annual_inflation_rate=0.05,
        primary_deficit_billions=10.0,
        short_issuance_rate=0.03,
        intermediate_issuance_rate=0.04,
        long_issuance_rate=0.05,
        tips_real_issuance_rate=0.01,
    )
    stock = DebtStock([make_cohort(principal=100.0, rate=0.04)], 0.0)
    common = {
        "initial_nominal_gdp_billions_saar": 1_000.0,
        "initial_real_gdp_billions_chained_saar": 1_000.0,
        "scenario_name": "test_policy",
        "data_vintage": "test",
    }
    sterilized = run_policy_simulation(
        stock,
        assumptions,
        policy_rule=PolicyRule(
            regime=PolicyRegime.STERILIZED_YIELD_CAP,
            reaction_smoothing=0.0,
        ),
        **common,
    )
    dominance = run_policy_simulation(
        stock,
        assumptions,
        policy_rule=PolicyRule(
            regime=PolicyRegime.FISCAL_DOMINANCE,
            reaction_smoothing=0.0,
        ),
        **common,
    )

    sterilized_rows = sterilized.quarterly
    dominance_rows = dominance.quarterly
    assert (sterilized_rows["fed_treasury_purchases_billions"] > 0).all()
    assert sterilized_rows.iloc[-1]["fed_reserve_balances_billions"] == pytest.approx(
        sterilized_rows["fed_treasury_purchases_billions"].sum()
    )
    assert sterilized_rows.iloc[-1]["iorb_rate"] > dominance_rows.iloc[-1]["iorb_rate"]
    assert (
        sterilized_rows.iloc[-1]["consolidated_public_financing_cost_billions"]
        > dominance_rows.iloc[-1]["consolidated_public_financing_cost_billions"]
    )


def test_policy_regime_path_can_change_during_a_simulation(make_assumptions):
    reference = make_assumptions(periods=2, annual_inflation_rate=0.05)
    regimes = pd.Series(
        [PolicyRegime.PRICE_STABILITY, PolicyRegime.FISCAL_DOMINANCE],
        index=reference.index,
    )
    policy = apply_policy_regime(
        reference,
        PolicyRule(reaction_smoothing=0.0),
        policy_regimes=regimes,
    )

    assert policy.iloc[0]["policy_regime"] == PolicyRegime.PRICE_STABILITY.value
    assert policy.iloc[1]["policy_regime"] == PolicyRegime.FISCAL_DOMINANCE.value
    assert policy.iloc[0]["short_issuance_rate"] > policy.iloc[1]["short_issuance_rate"]
