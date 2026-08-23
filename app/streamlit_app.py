"""Streamlit interface for the U.S. Fiscal Dynamics Simulator."""

from __future__ import annotations

import json
from dataclasses import replace

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from debt_sim.data import load_baseline_bundle
from debt_sim.model import run_simulation
from debt_sim.scenarios import (
    Scenario,
    apply_manual_primary_deficit,
    build_baseline_scenario,
    build_custom_scenario,
    build_preset_scenario,
    compare_scenarios,
    prepare_starting_state,
)

st.set_page_config(page_title="U.S. Fiscal Dynamics Simulator v0.2", layout="wide")


@st.cache_resource
def get_bundle():
    return load_baseline_bundle()


def run(scenario: Scenario, state, bundle):
    return run_simulation(
        state.stock,
        scenario.quarterly_assumptions,
        initial_nominal_gdp_billions_saar=state.initial_nominal_gdp_billions_saar,
        initial_real_gdp_billions_chained_saar=state.initial_real_gdp_billions_chained_saar,
        issuance_strategy=bundle.issuance_strategy,
        scenario_name=scenario.name,
        data_vintage=bundle.cbo_vintage,
    )


def comparison_figure(baseline, scenario, column, title, *, percent=False):
    fig = go.Figure()
    scale = 100.0 if percent else 1.0
    suffix = "%" if percent else ""
    fig.add_trace(
        go.Scatter(
            x=baseline["quarter_end"],
            y=baseline[column] * scale,
            name="Baseline",
            line={"color": "#4c78a8", "width": 2},
            hovertemplate=f"%{{x|%Y Q%q}}<br>%{{y:,.2f}}{suffix}<extra>Baseline</extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=scenario["quarter_end"],
            y=scenario[column] * scale,
            name="Scenario",
            line={"color": "#e45756", "width": 2},
            hovertemplate=f"%{{x|%Y Q%q}}<br>%{{y:,.2f}}{suffix}<extra>Scenario</extra>",
        )
    )
    fig.update_layout(title=title, hovermode="x unified", legend_orientation="h")
    return fig


bundle = get_bundle()

st.title("U.S. Fiscal Dynamics Simulator v0.2")
st.caption(
    "A deterministic accounting model—not a forecast. Inflation, real growth, primary deficits, "
    "and issuance rates are imposed independently; no Fed, Congressional, investor-panic, "
    "or crisis rule is inferred."
)

with st.sidebar:
    st.header("Scenario")
    st.selectbox("Baseline vintage", ["CBO February 2026"], disabled=True)
    all_periods = pd.period_range("2025Q4", "2056Q3", freq="Q")
    start_label = st.selectbox(
        "Simulation start",
        [str(period) for period in all_periods[:-1]],
        index=0,
        help=(
            "Later starts warm the Treasury cohort stock on baseline assumptions, "
            "then reset the repricing counter."
        ),
    )
    possible_ends = [str(period) for period in all_periods if period > pd.Period(start_label)]
    end_label = st.selectbox("Simulation end", possible_ends, index=len(possible_ends) - 1)
    preset_labels = {
        "Baseline": "baseline",
        "Inflation shock, rates unchanged": "inflation_no_rate_response",
        "Inflation + immediate rate response": "inflation_immediate_rate_response",
        "Inflation + delayed rate response": "inflation_delayed_rate_response",
        "Persistent financial repression": "persistent_financial_repression",
        "Custom independent paths": "custom",
    }
    preset_label = st.selectbox("Scenario preset", list(preset_labels))
    preset = preset_labels[preset_label]
    start_period = pd.Period(start_label, freq="Q")
    end_period = pd.Period(end_label, freq="Q")
    shock_options = [str(period) for period in pd.period_range(start_period, end_period, freq="Q")]
    default_shock_index = min(4, len(shock_options) - 1)
    shock_start = st.selectbox("Shock start", shock_options, index=default_shock_index)
    default_inflation = 6.0 if preset == "persistent_financial_repression" else 10.0
    inflation_percent = st.number_input(
        "Inflation during shock (%)",
        min_value=-10.0,
        max_value=100.0,
        value=default_inflation,
        step=0.5,
    )
    default_duration = 12 if preset == "persistent_financial_repression" else 4
    duration = st.slider(
        "Shock duration (quarters)",
        1,
        max(1, len(shock_options)),
        min(default_duration, len(shock_options)),
    )

    if preset == "custom":
        st.subheader("Independent changes")
        real_growth_adjustment = st.number_input(
            "Real GDP growth change (percentage points)",
            min_value=-20.0,
            max_value=20.0,
            value=0.0,
            step=0.25,
        )
        short_shock = st.number_input("Short-rate shock (bp)", -1000, 5000, 0, 25)
        intermediate_shock = st.number_input("Intermediate-rate shock (bp)", -1000, 5000, 0, 25)
        long_shock = st.number_input("Long-rate shock (bp)", -1000, 5000, 0, 25)
        tips_rate_shock = st.number_input("TIPS real-rate shock (bp)", -1000, 5000, 0, 25)
        rate_lag = st.slider("Rate-response lag (quarters)", 0, 12, 0)
        rate_duration = st.slider(
            "Rate-shock duration (quarters)",
            1,
            max(1, len(shock_options)),
            min(duration, len(shock_options)),
        )
    else:
        default_bp = (
            500
            if preset
            in {
                "inflation_immediate_rate_response",
                "inflation_delayed_rate_response",
            }
            else 0
        )
        rate_shock = st.number_input(
            "Parallel issuance-rate shock (bp)", -1000, 5000, default_bp, 25
        )
        default_lag = 4 if preset == "inflation_delayed_rate_response" else 0
        rate_lag = st.slider("Rate-response lag (quarters)", 0, 12, default_lag)

    st.subheader("Primary deficit")
    primary_mode_label = st.selectbox(
        "Primary-deficit path",
        ["CBO fiscal path", "Constant % of GDP", "Constant annual $ billions"],
    )
    primary_value = None
    if primary_mode_label == "Constant % of GDP":
        primary_value = (
            st.number_input("Primary deficit (% GDP; negative = surplus)", -25.0, 25.0, 2.5, 0.25)
            / 100.0
        )
    elif primary_mode_label == "Constant annual $ billions":
        primary_value = st.number_input(
            "Annual primary deficit ($bn; negative = surplus)",
            -5000.0,
            10_000.0,
            800.0,
            50.0,
        )

    st.subheader("Other financing")
    other_mode = st.selectbox(
        "Other-financing adjustment", ["CBO fiscal path", "Zero", "Constant annual $ billions"]
    )
    other_value = 0.0
    if other_mode == "Constant annual $ billions":
        other_value = st.number_input("Annual other financing ($bn)", -1000.0, 1000.0, 0.0, 25.0)


state = prepare_starting_state(bundle, start_period)
baseline_scenario = build_baseline_scenario(
    bundle, start_period=start_period, end_period=end_period
)
if preset == "custom":
    scenario = build_custom_scenario(
        bundle,
        start_period=start_period,
        end_period=end_period,
        shock_start_period=shock_start,
        shock_duration_quarters=duration,
        inflation_rate=inflation_percent / 100.0,
        real_growth_adjustment_percentage_points=real_growth_adjustment,
        short_rate_shock_basis_points=short_shock,
        intermediate_rate_shock_basis_points=intermediate_shock,
        long_rate_shock_basis_points=long_shock,
        tips_real_rate_shock_basis_points=tips_rate_shock,
        rate_response_lag_quarters=rate_lag,
        rate_shock_duration_quarters=rate_duration,
    )
else:
    scenario = build_preset_scenario(
        bundle,
        preset,
        start_period=start_period,
        end_period=end_period,
        shock_start_period=shock_start,
        shock_duration_quarters=duration,
        inflation_rate=inflation_percent / 100.0 if preset != "baseline" else None,
        rate_shock_basis_points=rate_shock if preset != "baseline" else None,
        rate_response_lag_quarters=rate_lag if preset != "baseline" else None,
    )

if primary_value is not None:
    scenario = apply_manual_primary_deficit(
        scenario,
        bundle,
        mode=(
            "percent_gdp"
            if primary_mode_label == "Constant % of GDP"
            else "annual_nominal_billions"
        ),
        value=primary_value,
        initial_nominal_gdp_billions_saar=state.initial_nominal_gdp_billions_saar,
    )
if other_mode == "Zero":
    scenario.quarterly_assumptions["other_financing_adjustment_billions"] = 0.0
elif other_mode == "Constant annual $ billions":
    scenario.quarterly_assumptions["other_financing_adjustment_billions"] = other_value / 4.0

with st.expander("Edit full quarterly assumption table"):
    st.caption(
        "Rates are decimals (0.10 = 10%); deficit and financing values are quarterly $ billions."
    )
    editable = scenario.quarterly_assumptions.copy()
    editable.index = editable.index.astype(str)
    edited = st.data_editor(editable, width="stretch", num_rows="fixed")
    edited.index = pd.PeriodIndex(edited.index, freq="Q")
    scenario = replace(scenario, quarterly_assumptions=edited)

baseline_result = run(baseline_scenario, state, bundle)
scenario_result = run(scenario, state, bundle)
baseline = baseline_result.quarterly
simulation = scenario_result.quarterly
comparison = compare_scenarios(baseline, simulation)
end = simulation.iloc[-1]
base_end = baseline.iloc[-1]
debt_difference_billions = (
    end["debt_held_by_public_billions"] - base_end["debt_held_by_public_billions"]
)
debt_ratio_difference_points = 100 * (
    end["debt_held_by_public_gdp_ratio"] - base_end["debt_held_by_public_gdp_ratio"]
)

st.info(scenario.description)
metrics = st.columns(6)
metrics[0].metric(
    "Debt held by public",
    f"${end['debt_held_by_public_billions'] / 1000:,.2f}T",
    f"${debt_difference_billions:+,.0f}B vs baseline",
)
metrics[1].metric(
    "Debt / GDP",
    f"{end['debt_held_by_public_gdp_ratio']:.1%}",
    f"{debt_ratio_difference_points:+.1f} pp",
)
metrics[2].metric("Primary deficit / GDP", f"{end['primary_deficit_gdp_ratio_annualized']:.1%}")
metrics[3].metric("Modeled interest / GDP", f"{end['modeled_interest_gdp_ratio_annualized']:.1%}")
metrics[4].metric(
    "Effective marketable rate",
    f"{end['average_effective_marketable_rate_excluding_tips_inflation']:.2%}",
)
metrics[5].metric(
    "Debt repriced since start",
    f"{end['share_marketable_debt_repriced_since_scenario_start']:.1%}",
)

overview, mechanisms, stock_tab, validation_tab, assumptions_tab = st.tabs(
    ["Overview", "Inflation and refinancing", "Debt stock", "Validation", "Assumptions & export"]
)

with overview:
    left, right = st.columns(2)
    left.plotly_chart(
        comparison_figure(
            baseline,
            simulation,
            "debt_held_by_public_gdp_ratio",
            "Debt held by the public / nominal GDP",
            percent=True,
        ),
        width="stretch",
    )
    right.plotly_chart(
        comparison_figure(
            baseline,
            simulation,
            "debt_held_by_public_billions",
            "Nominal debt held by the public ($bn)",
        ),
        width="stretch",
    )
    left, right = st.columns(2)
    left.plotly_chart(
        comparison_figure(
            baseline,
            simulation,
            "nominal_gdp_billions_saar",
            "Nominal GDP, seasonally adjusted annual rate ($bn)",
        ),
        width="stretch",
    )
    fiscal_flows = simulation.copy()
    fiscal_flows["Primary deficit"] = fiscal_flows["primary_deficit_gdp_ratio_annualized"] * 100
    fiscal_flows["Modeled debt interest"] = (
        fiscal_flows["modeled_interest_gdp_ratio_annualized"] * 100
    )
    flow_long = fiscal_flows.melt(
        id_vars="quarter_end",
        value_vars=["Primary deficit", "Modeled debt interest"],
        var_name="Component",
        value_name="Percent of GDP",
    )
    right.plotly_chart(
        px.line(
            flow_long,
            x="quarter_end",
            y="Percent of GDP",
            color="Component",
            title="Primary deficit and modeled interest (% GDP, annualized)",
        ),
        width="stretch",
    )

with mechanisms:
    decomposition = comparison[
        [
            "quarter_end",
            "debt_gdp_difference_from_nominal_debt",
            "debt_gdp_difference_from_nominal_gdp",
        ]
    ].rename(
        columns={
            "debt_gdp_difference_from_nominal_debt": "Nominal-debt contribution",
            "debt_gdp_difference_from_nominal_gdp": "Nominal-GDP contribution",
        }
    )
    decomp_long = decomposition.melt(
        id_vars="quarter_end", var_name="Channel", value_name="Debt/GDP difference"
    )
    decomp_long["Debt/GDP difference"] *= 100
    st.plotly_chart(
        px.area(
            decomp_long,
            x="quarter_end",
            y="Debt/GDP difference",
            color="Channel",
            title="Exact decomposition of scenario-minus-baseline debt/GDP (percentage points)",
        ),
        width="stretch",
    )
    left, right = st.columns(2)
    left.plotly_chart(
        comparison_figure(
            baseline,
            simulation,
            "average_effective_marketable_rate_excluding_tips_inflation",
            "Effective financing rate on marketable debt (ex-TIPS inflation)",
            percent=True,
        ),
        width="stretch",
    )
    reset = simulation[
        ["quarter_end", "principal_maturing_billions", "frn_principal_reset_billions"]
    ].rename(
        columns={
            "principal_maturing_billions": "Maturing principal",
            "frn_principal_reset_billions": "FRN principal resetting",
        }
    )
    reset_long = reset.melt(id_vars="quarter_end", var_name="Exposure", value_name="$ billions")
    right.plotly_chart(
        px.bar(
            reset_long,
            x="quarter_end",
            y="$ billions",
            color="Exposure",
            title="Principal maturing or resetting each quarter",
        ),
        width="stretch",
    )
    st.plotly_chart(
        comparison_figure(
            baseline,
            simulation,
            "modeled_debt_interest_cost_billions",
            "Quarterly modeled debt interest cost ($bn, including TIPS compensation)",
        ),
        width="stretch",
    )

with stock_tab:
    composition = simulation[
        [
            "quarter_end",
            "bills_outstanding_billions",
            "notes_outstanding_billions",
            "bonds_outstanding_billions",
            "tips_outstanding_billions",
            "frns_outstanding_billions",
            "other_public_debt_billions",
        ]
    ].rename(
        columns={
            "bills_outstanding_billions": "Bills",
            "notes_outstanding_billions": "Notes",
            "bonds_outstanding_billions": "Bonds",
            "tips_outstanding_billions": "TIPS",
            "frns_outstanding_billions": "FRNs",
            "other_public_debt_billions": "Other public debt",
        }
    )
    composition_long = composition.melt(
        id_vars="quarter_end", var_name="Debt component", value_name="$ billions"
    )
    st.plotly_chart(
        px.area(
            composition_long,
            x="quarter_end",
            y="$ billions",
            color="Debt component",
            title="Debt held by the public by modeled component",
        ),
        width="stretch",
    )
    st.dataframe(
        simulation[
            [
                "quarter",
                "debt_held_by_public_billions",
                "marketable_debt_billions",
                "other_public_debt_billions",
                "principal_maturing_billions",
                "principal_refinanced_billions",
                "genuinely_new_borrowing_billions",
                "gross_treasury_issuance_billions",
            ]
        ],
        width="stretch",
        hide_index=True,
    )

with validation_tab:
    validation = pd.read_csv("data/processed/baseline_validation_2026-02.csv")
    st.caption(
        "These comparisons use the full 2026–2036 baseline run. Modeled debt "
        "interest is intentionally not relabeled as CBO net interest."
    )
    summary = validation[validation["fiscal_year"].isin([2026, 2031, 2036])].copy()
    st.dataframe(summary, width="stretch", hide_index=True)
    st.markdown("See `docs/validation.md` for definitions and discrepancy explanations.")

with assumptions_tab:
    st.json(scenario.imposed_parameters)
    st.dataframe(scenario.quarterly_assumptions, width="stretch")
    config = {
        "name": scenario.name,
        "description": scenario.description,
        "cbo_vintage": bundle.cbo_vintage,
        "treasury_observation_date": bundle.treasury_observation_date,
        "start_period": start_label,
        "end_period": end_label,
        "parameters": scenario.imposed_parameters,
    }
    st.download_button(
        "Download scenario configuration",
        json.dumps(config, indent=2, sort_keys=True),
        file_name=f"{scenario.name}.json",
        mime="application/json",
    )
    st.download_button(
        "Download quarterly results",
        simulation.to_csv(index=False),
        file_name=f"{scenario.name}_quarterly.csv",
        mime="text/csv",
    )
