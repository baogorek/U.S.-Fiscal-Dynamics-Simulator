"""Visual narrative for the pinned 2045 confidence-premium stress experiment."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

st.set_page_config(page_title="What a Bad Ending Looks Like", layout="wide")

PROCESSED = Path("data/processed")
PATH_FILE = PROCESSED / "confidence_shock_paths_2045_2026-02-25.csv"
SUMMARY_FILE = PROCESSED / "confidence_shock_summary_2045_2026-02-25.csv"
DELAYED_FILE = (
    PROCESSED / "confidence_shock_delayed_fiscal_adjustment_2045_2026-02-25.csv"
)
SHOCK_DATE = pd.Timestamp("2045-01-01")

LABELS = {
    "unchanged_baseline": "Unchanged baseline",
    "recession_only": "Recession only",
    "rate_only_500bp": "+500 bp without recession",
    "fiscal_scare_250bp": "Fiscal scare: +250 bp",
    "serious_crisis_500bp": "Serious crisis: +500 bp",
    "loss_of_confidence_1000bp": "Loss of confidence: +1,000 bp",
}
COLORS = {
    "unchanged_baseline": "#667085",
    "recession_only": "#3478a8",
    "rate_only_500bp": "#8b5cf6",
    "fiscal_scare_250bp": "#d99b27",
    "serious_crisis_500bp": "#c83e4d",
    "loss_of_confidence_1000bp": "#6f1d1b",
}


@st.cache_data
def load_results():
    paths = pd.read_csv(PATH_FILE, parse_dates=["quarter_end"])
    summary = pd.read_csv(SUMMARY_FILE)
    delayed = pd.read_csv(DELAYED_FILE)
    delayed["closure_date"] = pd.PeriodIndex(delayed["closure_start"], freq="Q").start_time
    return paths, summary, delayed


if not all(path.exists() for path in (PATH_FILE, SUMMARY_FILE, DELAYED_FILE)):
    st.error(
        "Run `uv run python scripts/run_confidence_shock_experiment.py` to create "
        "the pinned confidence-shock outputs."
    )
    st.stop()

paths, summary, delayed = load_results()
serious_summary = summary[summary["scenario"].eq("serious_crisis_500bp")].iloc[0]
baseline_summary = summary[summary["scenario"].eq("unchanged_baseline")].iloc[0]
rate_only_summary = summary[summary["scenario"].eq("rate_only_500bp")].iloc[0]
recession_summary = summary[summary["scenario"].eq("recession_only")].iloc[0]
loss_delay = delayed[delayed["scenario"].eq("loss_of_confidence_1000bp")]
closure_delta_pp = 100 * (
    serious_summary["required_fiscal_adjustment_if_immediate_gdp_share"]
    - baseline_summary["required_fiscal_adjustment_if_immediate_gdp_share"]
)
rate_only_adjustment = rate_only_summary[
    "required_fiscal_adjustment_if_immediate_gdp_share"
]
recession_only_adjustment = recession_summary[
    "required_fiscal_adjustment_if_immediate_gdp_share"
]

st.title("This Is What “It Won’t End Well” Looks Like")
st.caption(
    "An imposed 2045 financing-premium stress—not a forecast, probability, or endogenous "
    "bond-market model. Fiscal policy, inflation, and other financing remain on baseline."
)

with st.expander("Exact scenario definition", expanded=True):
    st.markdown(
        """
- Closure state: **2045Q1**, beginning debt/GDP **138.51%**.
- Confidence premium: **+500 basis points on new Treasury issuance for 40 quarters**.
  It reaches bills, notes, bonds, new TIPS real yields, and FRNs through their bill-rate reset.
- Real growth: **−2% annualized for four quarters, 0% for four quarters, then baseline**,
  with no catch-up of the lost output level.
- Nominal primary deficits: **unchanged baseline dollar path**. Inflation: **unchanged baseline**.
- No haircut, default, extraordinary inflation, or endogenous fiscal/Federal Reserve response.
"""
    )

cards = st.columns(5)
cards[0].metric("2045 starting debt/GDP", f"{serious_summary['starting_debt_gdp_ratio']:.1%}")
cards[1].metric(
    "Immediate 10-year closure",
    f"{serious_summary['required_fiscal_adjustment_if_immediate_gdp_share']:.2%} of GDP",
    delta=f"{closure_delta_pp:.2f} pp vs baseline",
    delta_color="inverse",
)
cards[2].metric("2054 debt/GDP", f"{serious_summary['terminal_debt_gdp_ratio']:.1%}")
cards[3].metric("2054 interest/GDP", f"{serious_summary['terminal_interest_gdp_ratio']:.1%}")
cards[4].metric(
    "Extra modeled interest",
    f"${serious_summary['cumulative_additional_interest_vs_baseline_billions'] / 1000:,.1f}T",
)

st.caption(
    "The 8.69%-of-GDP result is about $2.69 trillion when applied to the simulator’s "
    "pinned 2025-sized economy. That is a scale comparison, not a literal tax estimate. "
    f"For attribution, the recession alone requires {recession_only_adjustment:.2%}; "
    f"+500 bp without the recession requires {rate_only_adjustment:.2%}."
)


def add_path_trace(fig, row, metric, scenario, *, showlegend):
    selected = paths[paths["scenario"].eq(scenario)]
    fig.add_trace(
        go.Scatter(
            x=selected["quarter_end"],
            y=100 * selected[metric],
            name=LABELS[scenario],
            legendgroup=scenario,
            showlegend=showlegend,
            mode="lines",
            line={
                "color": COLORS[scenario],
                "width": 2.6 if scenario != "unchanged_baseline" else 2,
            },
        ),
        row=row,
        col=1,
    )


subplot_titles = (
    "Debt held by the public / GDP",
    "Effective average marketable Treasury rate",
    "Modeled interest / GDP",
    "Modeled total deficit / GDP",
    "Required permanent primary-balance adjustment if action begins then",
)
figure = make_subplots(
    rows=5,
    cols=1,
    shared_xaxes=True,
    vertical_spacing=0.045,
    subplot_titles=subplot_titles,
)
for row, metric in enumerate(
    (
        "debt_held_by_public_gdp_ratio",
        "average_effective_marketable_rate_excluding_tips_inflation",
        "modeled_interest_gdp_ratio_annualized",
        "modeled_total_deficit_gdp_ratio_annualized",
    ),
    start=1,
):
    add_path_trace(figure, row, metric, "unchanged_baseline", showlegend=row == 1)
    add_path_trace(figure, row, metric, "serious_crisis_500bp", showlegend=row == 1)

for scenario in ("unchanged_baseline", "serious_crisis_500bp"):
    selected = delayed[delayed["scenario"].eq(scenario)]
    figure.add_trace(
        go.Scatter(
            x=selected["closure_date"],
            y=100 * selected["required_fiscal_adjustment_gdp_share"],
            name=LABELS[scenario],
            legendgroup=scenario,
            showlegend=False,
            mode="lines+markers",
            line={
                "color": COLORS[scenario],
                "width": 2.6 if scenario != "unchanged_baseline" else 2,
            },
        ),
        row=5,
        col=1,
    )

figure.add_vline(x=SHOCK_DATE, line_dash="dot", line_color="#111827", line_width=1.5)
figure.add_annotation(
    x=SHOCK_DATE,
    y=1.02,
    xref="x",
    yref="paper",
    text="2045Q1: +500 bp confidence premium",
    showarrow=False,
    xanchor="left",
)
figure.update_yaxes(title_text="Percent", ticksuffix="%")
figure.update_layout(
    height=1_180,
    title="Refinancing turns a rate shock into a fiscal feedback loop",
    hovermode="x unified",
    margin={"t": 100, "b": 40},
)
st.plotly_chart(figure, width="stretch")
st.caption(
    "The fiscal-adjustment panel resolves the default closure condition from each annual "
    "starting date through the fixed 2054Q4 endpoint. Its horizon therefore shrinks as action "
    "is delayed. The effective-rate measure excludes TIPS inflation compensation."
)

st.subheader("The shock reaches the debt stock progressively")
serious_post = paths[
    paths["scenario"].eq("serious_crisis_500bp")
    & paths["quarter"].map(lambda value: pd.Period(value, freq="Q") >= pd.Period("2045Q1"))
].copy()
repriced_2045 = serious_post[serious_post["quarter"].eq("2045Q4")].iloc[0][
    "share_marketable_debt_repriced_since_scenario_start"
]
serious_post["Share repriced or reset since 2045 (%)"] = 100 * serious_post[
    "share_marketable_debt_repriced_since_scenario_start"
]
st.plotly_chart(
    px.area(
        serious_post,
        x="quarter_end",
        y="Share repriced or reset since 2045 (%)",
        title="Current marketable debt issued or reset after the confidence shock",
    ),
    width="stretch",
)
st.caption(
    "This is a current-stock share, not gross refinancing. Bills can mature and reissue more "
    "than once, while inherited long fixed-rate securities retain their coupons until maturity."
)

st.subheader("How ugly the result becomes depends on the imposed premium")
comparison_names = [
    "unchanged_baseline",
    "fiscal_scare_250bp",
    "serious_crisis_500bp",
    "loss_of_confidence_1000bp",
]
left, right = st.columns(2)
with left:
    comparison = paths[paths["scenario"].isin(comparison_names)].copy()
    comparison["Scenario"] = comparison["scenario"].map(LABELS)
    comparison["Debt/GDP (%)"] = 100 * comparison["debt_held_by_public_gdp_ratio"]
    st.plotly_chart(
        px.line(
            comparison,
            x="quarter_end",
            y="Debt/GDP (%)",
            color="Scenario",
            color_discrete_map={LABELS[key]: value for key, value in COLORS.items()},
            title="Debt paths under the three confidence premiums",
        ),
        width="stretch",
    )
with right:
    comparison_delay = delayed[delayed["scenario"].isin(comparison_names)].copy()
    comparison_delay["Scenario"] = comparison_delay["scenario"].map(LABELS)
    comparison_delay["Required adjustment (% GDP)"] = 100 * comparison_delay[
        "required_fiscal_adjustment_gdp_share"
    ]
    st.plotly_chart(
        px.line(
            comparison_delay,
            x="closure_date",
            y="Required adjustment (% GDP)",
            color="Scenario",
            markers=True,
            color_discrete_map={LABELS[key]: value for key, value in COLORS.items()},
            title="Fiscal closure requirement if action is delayed",
        ),
        width="stretch",
    )
    if loss_delay["status"].eq("no_solution").any():
        first_failure = loss_delay[loss_delay["status"].eq("no_solution")].iloc[0]
        st.warning(
            f"Under +1,000 bp, waiting until {first_failure['closure_start']} produces no "
            "solution within the 20%-of-GDP fiscal bound before 2054Q4."
        )

st.subheader("+500 bp annual checkpoints")
checkpoints = serious_post[serious_post["quarter"].str.endswith("Q4")].copy()
checkpoints = checkpoints[
    checkpoints["calendar_year"].isin([2045, 2046, 2048, 2050, 2052, 2054])
]
checkpoints["Debt/GDP"] = checkpoints["debt_held_by_public_gdp_ratio"].map(
    lambda value: f"{value:.1%}"
)
checkpoints["Effective rate"] = checkpoints[
    "average_effective_marketable_rate_excluding_tips_inflation"
].map(lambda value: f"{value:.2%}")
checkpoints["Interest/GDP"] = checkpoints["modeled_interest_gdp_ratio_annualized"].map(
    lambda value: f"{value:.1%}"
)
checkpoints["Total deficit/GDP"] = checkpoints[
    "modeled_total_deficit_gdp_ratio_annualized"
].map(lambda value: f"{value:.1%}")
checkpoints["Repriced since 2045"] = checkpoints[
    "share_marketable_debt_repriced_since_scenario_start"
].map(lambda value: f"{value:.1%}")
st.dataframe(
    checkpoints[
        [
            "quarter",
            "Effective rate",
            "Interest/GDP",
            "Total deficit/GDP",
            "Debt/GDP",
            "Repriced since 2045",
        ]
    ].rename(columns={"quarter": "Quarter"}),
    hide_index=True,
    width="stretch",
)

st.subheader("What this establishes—and what it does not")
st.markdown(
    f"""
The imposed +500 bp premium does not instantly reprice the inherited stock. By the end of
2045, about **{repriced_2045:.1%}**
of current marketable debt has been issued or reset since the shock. By 2054 it is
**{serious_summary['terminal_repriced_share']:.1%}**. Over the same period, the effective
marketable rate reaches **{serious_summary['terminal_effective_marketable_rate']:.2%}**,
modeled interest reaches **{serious_summary['terminal_interest_gdp_ratio']:.1%} of GDP**,
and debt reaches **{serious_summary['terminal_debt_gdp_ratio']:.1%} of GDP**.

This establishes a conditional refinancing feedback: higher new rates raise interest
borrowing gradually; that borrowing creates additional debt issued at the stressed rates;
and delaying fiscal closure raises the required adjustment. It does **not** establish why
investors demand the premium, how probable it is, how the Federal Reserve or Congress reacts,
or whether output, inflation, issuance management, and market functioning could remain on
the imposed paths at these extreme ratios.
"""
)
