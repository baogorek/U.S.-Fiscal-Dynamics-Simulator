"""Streamlit closure dashboard for v0.2."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from debt_sim.closure import (
    ClosureTarget,
    InflationEpisode,
    InflationRateResponse,
    closure_start_after_threshold,
    fiscal_inflation_frontier,
    solve_financial_repression,
    solve_fiscal_adjustment,
    solve_haircut_equivalent,
    solve_immediate_flow_primary_balance,
    solve_inflation_closure,
)
from debt_sim.data import load_baseline_bundle
from debt_sim.model import run_simulation
from debt_sim.scenarios import build_baseline_scenario, prepare_starting_state

st.set_page_config(page_title="Something Has to Give", layout="wide")
MAX_PERIOD = pd.Period("2056Q3", freq="Q")
PROCESSED = Path("data/processed")


@st.cache_resource
def get_bundle():
    return load_baseline_bundle()


@st.cache_data(show_spinner="Tracing the baseline debt path…")
def full_baseline():
    bundle = get_bundle()
    scenario = build_baseline_scenario(bundle, end_period=MAX_PERIOD)
    return run_simulation(
        bundle.initial_stock,
        scenario.quarterly_assumptions,
        initial_nominal_gdp_billions_saar=bundle.initial_nominal_gdp_billions_saar,
        initial_real_gdp_billions_chained_saar=bundle.initial_real_gdp_billions_chained_saar,
        issuance_strategy=bundle.issuance_strategy,
        scenario_name="extended_baseline",
        data_vintage=bundle.cbo_vintage,
    )


@st.cache_data(show_spinner="Solving the four conditional closure mechanisms…")
def solve_dashboard(
    start_label: str,
    end_label: str,
    target_kind: str,
    target_ratio: float | None,
    inflation_duration: int,
    response_mode: str,
    beta_short: float,
    beta_intermediate: float,
    beta_long: float,
    response_lag: int,
    inflation_upper: float,
    repression_inflation: float | None,
    repression_floor: float,
):
    bundle = get_bundle()
    start = pd.Period(start_label, freq="Q")
    end = pd.Period(end_label, freq="Q")
    state = prepare_starting_state(bundle, start)
    assumptions = build_baseline_scenario(
        bundle, start_period=start, end_period=end
    ).quarterly_assumptions
    if target_kind == "stabilize_at_start":
        target = ClosureTarget.stabilize_at_start()
    elif target_kind == "specified_ratio":
        assert target_ratio is not None
        target = ClosureTarget.specified_ratio(target_ratio)
    else:
        target = ClosureTarget.immediate_flow()

    if response_mode == "none":
        response = InflationRateResponse.no_response()
    else:
        response = InflationRateResponse(
            mode="contemporaneous" if response_lag == 0 else "delayed",
            beta_bills=beta_short,
            beta_intermediate=beta_intermediate,
            beta_long=beta_long,
            lag_quarters=response_lag,
        )
    episode = InflationEpisode(
        duration_quarters=min(inflation_duration, len(assumptions)),
        shape=(
            "immediate_price_level"
            if inflation_duration == 1
            else "one_year"
            if inflation_duration == 4
            else "multi_year"
        ),
        rate_response=response,
    )
    common = {
        "initial_nominal_gdp_billions_saar": state.initial_nominal_gdp_billions_saar,
        "initial_real_gdp_billions_chained_saar": state.initial_real_gdp_billions_chained_saar,
        "issuance_strategy": bundle.issuance_strategy,
        "target": target,
        "data_vintage": bundle.cbo_vintage,
    }
    fiscal = solve_fiscal_adjustment(state.stock, assumptions, **common)
    inflation = solve_inflation_closure(
        state.stock,
        assumptions,
        episode=episode,
        bounds=(0.0, inflation_upper),
        **common,
    )
    haircut = solve_haircut_equivalent(state.stock, assumptions, **common)

    repression_assumptions = assumptions.copy()
    if repression_inflation is not None:
        repression_assumptions["annual_inflation_rate"] = repression_inflation
        repression_assumptions["annual_tips_reference_inflation_rate"] = repression_inflation
    repression = solve_financial_repression(
        state.stock,
        repression_assumptions,
        nominal_yield_floor=repression_floor,
        **common,
    )
    flow = solve_immediate_flow_primary_balance(
        state.stock,
        assumptions,
        initial_nominal_gdp_billions_saar=state.initial_nominal_gdp_billions_saar,
        initial_real_gdp_billions_chained_saar=state.initial_real_gdp_billions_chained_saar,
        issuance_strategy=bundle.issuance_strategy,
        data_vintage=bundle.cbo_vintage,
    )
    return {
        "fiscal": fiscal,
        "inflation": inflation,
        "haircut": haircut,
        "repression": repression,
        "flow": flow,
        "episode": episode,
        "assumptions": assumptions,
        "state": state,
        "target": target,
    }


def result_text(solution, *, scale: float, suffix: str, decimals: int = 1) -> str:
    if solution.value is None:
        return "No solution within bounds"
    return f"{solution.value * scale:,.{decimals}f}{suffix}"


bundle = get_bundle()
baseline_result = full_baseline()

st.title("Something Has to Give")
st.caption(
    "Conditional arithmetic from the existing Treasury cohort engine—not a prediction, "
    "crisis threshold, policy ranking, or estimate of political behavior."
)

with st.sidebar:
    st.header("Closure definition")
    start_mode = st.radio("Closure begins by", ["Date", "Debt/GDP reference level"])
    if start_mode == "Date":
        start_year = st.selectbox("Start year", list(range(2026, 2057)), index=19)
        closure_start = pd.Period(f"{start_year}Q1", freq="Q")
        start_note = f"Action begins in {closure_start}."
    else:
        threshold_percent = st.selectbox("Debt/GDP reference level", [120, 150, 175, 200])
        closure_start = closure_start_after_threshold(
            baseline_result, threshold_percent / 100.0
        )
        start_note = (
            "Reference level is not reached in the modeled baseline."
            if closure_start is None
            else (
                f"Action begins in {closure_start}, the quarter after the baseline "
                "first reaches it."
            )
        )
    st.caption(start_note)

    target_label = st.selectbox(
        "Closure target",
        [
            "Stabilize at the starting ratio",
            "Reach a specified debt/GDP ratio",
            "Immediate flow stabilization",
        ],
    )
    target_kind = {
        "Stabilize at the starting ratio": "stabilize_at_start",
        "Reach a specified debt/GDP ratio": "specified_ratio",
        "Immediate flow stabilization": "immediate_flow",
    }[target_label]
    target_ratio = None
    if target_kind == "specified_ratio":
        target_ratio = st.number_input("Target debt/GDP (%)", 0.0, 300.0, 130.0, 1.0) / 100.0
    horizon_years = st.slider(
        "Closure horizon (years)",
        1,
        20,
        10,
        disabled=target_kind == "immediate_flow",
    )

    st.header("Inflationary closure")
    duration_years = st.select_slider(
        "Episode duration",
        options=[0.25, 1, 2, 5, 10],
        value=5,
        format_func=lambda value: (
            "Immediate price-level approximation" if value == 0.25 else f"{value:g} years"
        ),
    )
    inflation_duration = 1 if duration_years == 0.25 else int(duration_years * 4)
    response_label = st.selectbox(
        "Issuance-rate response",
        [
            "Contemporaneous pass-through",
            "Delayed pass-through",
            "No additional response",
        ],
    )
    response_mode = "none" if response_label == "No additional response" else "pass_through"
    if response_mode == "none":
        beta_short = beta_intermediate = beta_long = 0.0
        response_lag = 0
    else:
        beta_short = st.number_input("Bills beta", 0.0, 3.0, 1.0, 0.1)
        beta_intermediate = st.number_input("Intermediate beta", 0.0, 3.0, 1.0, 0.1)
        beta_long = st.number_input("Long beta", 0.0, 3.0, 1.0, 0.1)
        response_lag = (
            st.slider("Response lag (quarters)", 1, 12, 8)
            if response_label == "Delayed pass-through"
            else 0
        )
    inflation_upper = st.number_input(
        "Maximum additional cumulative price-level change (%)",
        10.0,
        10_000.0,
        1_000.0,
        50.0,
    ) / 100.0

    st.header("Financial repression")
    repression_path = st.selectbox(
        "Inflation path during repression", ["Baseline path", "Constant user rate"]
    )
    repression_inflation = None
    if repression_path == "Constant user rate":
        repression_inflation = (
            st.number_input("Annual inflation (%)", -5.0, 100.0, 4.0, 0.5) / 100.0
        )
    repression_floor = (
        st.number_input("Nominal new-yield floor (%)", 0.0, 20.0, 0.0, 0.25) / 100.0
    )

if closure_start is None:
    st.warning(
        "That reference level is not reached by 2056Q3 in this simulator baseline. "
        "It is a reference selection, not a crisis threshold."
    )
    st.stop()

closure_end = (
    closure_start
    if target_kind == "immediate_flow"
    else closure_start + horizon_years * 4 - 1
)
if closure_end > MAX_PERIOD:
    st.error(
        f"The requested horizon ends in {closure_end}, beyond the pinned 2056Q3 data. "
        "Choose an earlier start or shorter horizon; the app will not invent a post-2056 path."
    )
    st.stop()

dashboard = solve_dashboard(
    str(closure_start),
    str(closure_end),
    target_kind,
    target_ratio,
    inflation_duration,
    response_mode,
    beta_short,
    beta_intermediate,
    beta_long,
    response_lag,
    inflation_upper,
    repression_inflation,
    repression_floor,
)
fiscal = dashboard["fiscal"]
inflation = dashboard["inflation"]
haircut = dashboard["haircut"]
repression = dashboard["repression"]
episode = dashboard["episode"]

starting_ratio = dashboard["state"].stock.debt_held_by_public_billions / dashboard[
    "state"
].initial_nominal_gdp_billions_saar
target_value = dashboard["target"].resolved_ratio(starting_ratio)
st.info(
    f"Closure starts at {starting_ratio:.1%} debt/GDP in {closure_start}; target "
    f"{target_value:.1%} by {closure_end}. "
    + (
        "The default definition also limits the rise over the final four quarters "
        "to 0.1 percentage point."
        if target_kind == "stabilize_at_start"
        else "This endpoint target does not add the multi-year final-trend condition."
    )
)

cards = st.columns(4)
with cards[0]:
    st.metric(
        "Fiscal-only closure",
        result_text(fiscal, scale=100, suffix="% of GDP"),
    )
    st.caption("Permanent required primary-balance improvement; no tax/spending split is assumed.")
with cards[1]:
    st.metric(
        "Inflation-only closure",
        result_text(inflation, scale=100, suffix="% cumulative"),
    )
    st.caption(episode.rate_response.label + " Baseline nominal primary deficits are held fixed.")
with cards[2]:
    st.metric(
        "Haircut-equivalent closure",
        result_text(haircut, scale=100, suffix="% of eligible debt"),
    )
    st.caption("Marketable Treasury debt represented in the model; zero post-event yield response.")
with cards[3]:
    st.metric(
        "Financial-repression closure",
        result_text(repression, scale=1, suffix=" bp", decimals=0),
    )
    st.caption(
        "Uniform suppression of new nominal yields for "
        f"{len(dashboard['assumptions']) / 4:g} years; "
        f"{repression_path.lower()} inflation."
    )

st.warning(
    "Mathematical feasibility is not economic or political feasibility. The zero-yield-response "
    "haircut calculation materially understates the likely consequences of an actual U.S. default."
)

overview, inflation_tab, frontier_tab, research_tab, diagnostics_tab = st.tabs(
    [
        "Pure closure paths",
        "Inflation mechanics",
        "Closure frontier",
        "Research outputs",
        "Diagnostics",
    ]
)

with overview:
    paths = {"Unchanged baseline": fiscal.baseline_result.quarterly}
    for label, solution in (
        ("Fiscal closure", fiscal),
        ("Inflationary closure", inflation),
        ("Haircut equivalent", haircut),
        ("Financial repression", repression),
    ):
        suffix = " (best within bounds)" if not solution.solved else ""
        paths[label + suffix] = solution.result.quarterly
    fig = go.Figure()
    for label, frame in paths.items():
        fig.add_trace(
            go.Scatter(
                x=frame["quarter_end"],
                y=100 * frame["debt_held_by_public_gdp_ratio"],
                name=label,
            )
        )
    fig.update_layout(
        title="Debt paths under each pure closure mechanism",
        yaxis_title="Debt held by the public (% GDP)",
        hovermode="x unified",
    )
    st.plotly_chart(fig, width="stretch")

with inflation_tab:
    if inflation.value is None:
        st.error(
            "No inflationary closure solution exists within the selected price-level bound. "
            "The best sampled terminal ratio is "
            f"{inflation.evaluation.terminal_debt_gdp_ratio:.1%}."
        )
    else:
        diagnostic = inflation.diagnostics
        terminal_improvement = diagnostic[
            "terminal_debt_gdp_improvement_vs_baseline_percentage_points"
        ]
        summary = pd.DataFrame(
            {
                "Measure": [
                    "Additional cumulative price-level change",
                    "Total episode price-level increase",
                    "Equivalent total annualized inflation",
                    "Gross principal refinanced during episode",
                    "Increase in TIPS principal compensation",
                    "Cumulative interest cost relative to baseline",
                    "Debt/GDP improvement relative to baseline",
                ],
                "Value": [
                    f"{diagnostic['required_additional_cumulative_price_level_increase']:.1%}",
                    f"{diagnostic['total_episode_cumulative_price_level_increase']:.1%}",
                    f"{diagnostic['total_annualized_inflation_during_episode']:.1%}",
                    f"${diagnostic['gross_principal_refinanced_during_episode_billions']:,.0f}B",
                    f"${diagnostic['increase_in_tips_principal_compensation_billions']:,.0f}B",
                    f"${diagnostic['cumulative_interest_cost_relative_to_baseline_billions']:+,.0f}B",
                    f"{terminal_improvement:.1f} pp",
                ],
            }
        )
        st.dataframe(summary, hide_index=True, width="stretch")
        effects = pd.DataFrame(
            {
                "Channel": [
                    "Nominal-GDP denominator",
                    "TIPS indexation",
                    "Refinancing/rates",
                    "Primary-deficit scaling",
                ],
                "Percentage points": [
                    diagnostic["denominator_effect_percentage_points"],
                    diagnostic["tips_indexation_effect_percentage_points"],
                    diagnostic["refinancing_interest_effect_percentage_points"],
                    diagnostic["primary_deficit_scaling_effect_percentage_points"],
                ],
            }
        )
        st.plotly_chart(
            px.bar(
                effects,
                x="Channel",
                y="Percentage points",
                title="Order-dependent accounting bridge to terminal debt/GDP",
            ),
            width="stretch",
        )
        st.caption(
            "Inflation reduces the real burden and debt/GDP; it does not make nominal "
            "Treasury face value disappear."
        )

with frontier_tab:
    st.caption(
        "Each point solves cumulative inflation conditional on an imposed permanent "
        "primary-balance improvement. "
        "No welfare ranking or probability is attached."
    )
    if st.button("Calculate fiscal/inflation frontier"):
        with st.spinner("Running the cohort engine across the frontier…"):
            frontier = fiscal_inflation_frontier(
                dashboard["state"].stock,
                dashboard["assumptions"],
                initial_nominal_gdp_billions_saar=(
                    dashboard["state"].initial_nominal_gdp_billions_saar
                ),
                initial_real_gdp_billions_chained_saar=(
                    dashboard["state"].initial_real_gdp_billions_chained_saar
                ),
                issuance_strategy=bundle.issuance_strategy,
                fiscal_adjustments=np.linspace(0.0, min(0.10, fiscal.value or 0.10), 9),
                episode=episode,
                target=dashboard["target"],
                inflation_bounds=(0.0, inflation_upper),
                data_vintage=bundle.cbo_vintage,
            )
        plot = frontier.dropna(subset=["additional_cumulative_price_level_change"]).copy()
        plot["Primary adjustment (% GDP)"] = 100 * plot[
            "primary_balance_improvement_gdp_share"
        ]
        plot["Cumulative inflation adjustment (%)"] = 100 * plot[
            "additional_cumulative_price_level_change"
        ]
        st.plotly_chart(
            px.line(
                plot,
                x="Primary adjustment (% GDP)",
                y="Cumulative inflation adjustment (%)",
                markers=True,
                title="Fiscal closure frontier",
            ),
            width="stretch",
        )
        st.dataframe(frontier, hide_index=True, width="stretch")

with research_tab:
    requirements_path = PROCESSED / "closure_requirements_by_start_2026-02-25.csv"
    state_table_path = PROCESSED / "closure_requirements_by_debt_state_2026-02-25.csv"
    ladder_path = PROCESSED / "rate_stress_ladder_2026-02-25.csv"
    if not requirements_path.exists():
        st.info("Run `uv run python scripts/run_v02_experiments.py` to create research outputs.")
    else:
        requirements = pd.read_csv(requirements_path)
        chart_specs = [
            ("fiscal_adjustment_gdp_share", 100, "Required primary adjustment (% GDP)"),
            (
                "inflation_cumulative_price_change",
                100,
                "Required cumulative inflation adjustment (%)",
            ),
            ("haircut_fraction", 100, "Mechanical haircut equivalent (% eligible debt)"),
            ("repression_basis_points", 1, "Required yield suppression (bp)"),
        ]
        for column, scale, title in chart_specs:
            chart = requirements.dropna(subset=[column]).copy()
            chart[title] = chart[column] * scale
            st.plotly_chart(
                px.line(chart, x="closure_start", y=title, markers=True, title=title),
                width="stretch",
            )
        if state_table_path.exists():
            st.subheader("Conditional closure requirements by reachable debt state")
            st.dataframe(pd.read_csv(state_table_path), hide_index=True, width="stretch")
        if ladder_path.exists():
            ladder = pd.read_csv(ladder_path)
            ladder["Required fiscal adjustment (% GDP)"] = 100 * ladder[
                "required_fiscal_adjustment_gdp_share"
            ]
            st.plotly_chart(
                px.line(
                    ladder,
                    x="issuance_rate_shock_basis_points",
                    y="Required fiscal adjustment (% GDP)",
                    markers=True,
                    title="Rate-shock stress ladder",
                ),
                width="stretch",
            )

with diagnostics_tab:
    st.subheader("Immediate flow stabilization")
    flow = dashboard["flow"]
    st.metric(
        "Primary deficit that holds debt/GDP approximately constant next quarter",
        result_text(flow, scale=100, suffix="% of GDP"),
    )
    st.caption(
        "Negative primary-deficit values are primary surpluses. This is not the "
        "multi-year solver."
    )
    rows = []
    for label, solution in (
        ("Fiscal", fiscal),
        ("Inflation", inflation),
        ("Haircut", haircut),
        ("Repression", repression),
    ):
        rows.append(
            {
                "Mechanism": label,
                "Status": solution.status,
                "Terminal debt/GDP": solution.evaluation.terminal_debt_gdp_ratio,
                "Final 4Q change": solution.evaluation.final_four_quarter_change,
                "Target gap": solution.evaluation.binding_gap,
                "Lower bound": solution.bounds[0],
                "Upper bound": solution.bounds[1],
            }
        )
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption(
        "PWBM model-specific outer-bound estimate: approximately 210% debt/GDP—"
        "reference marker only, "
        "not a universal crisis threshold and not a hard-coded model trigger."
    )
