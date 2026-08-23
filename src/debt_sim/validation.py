"""CBO baseline aggregation, comparison, and reproducible validation outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from debt_sim.data import DEFAULT_CBO_VINTAGE, DEFAULT_DATA_ROOT, load_baseline_bundle
from debt_sim.model import SimulationResult, run_simulation
from debt_sim.scenarios import Scenario, build_baseline_scenario

FLOW_COLUMNS = [
    "primary_deficit_billions",
    "modeled_debt_interest_cost_billions",
    "modeled_total_deficit_billions",
    "other_financing_adjustment_billions",
]


def aggregate_fiscal_years(result: SimulationResult) -> pd.DataFrame:
    """Aggregate quarterly flows and select fiscal-year-end stock observations."""

    quarterly = result.quarterly.sort_values("quarter_end")
    flows = quarterly.groupby("fiscal_year", as_index=False)[FLOW_COLUMNS].sum()
    fiscal_gdp = quarterly.groupby("fiscal_year", as_index=False)[
        "nominal_gdp_billions_saar"
    ].mean()
    fiscal_gdp = fiscal_gdp.rename(
        columns={"nominal_gdp_billions_saar": "fiscal_year_nominal_gdp_billions"}
    )
    stocks = quarterly.groupby("fiscal_year", as_index=False).tail(1)[
        [
            "fiscal_year",
            "quarter",
            "debt_held_by_public_billions",
            "debt_held_by_public_gdp_ratio",
            "nominal_gdp_billions_saar",
            "debt_identity_residual_billions",
        ]
    ]
    stocks = stocks.rename(
        columns={"debt_held_by_public_gdp_ratio": "quarter_end_debt_held_by_public_gdp_ratio"}
    )
    result = flows.merge(stocks, on="fiscal_year", how="left").merge(
        fiscal_gdp, on="fiscal_year", how="left"
    )
    # CBO's published fiscal-year debt ratio uses fiscal-year nominal GDP,
    # which is the mean of the four seasonally adjusted annual-rate quarters.
    result["debt_held_by_public_gdp_ratio"] = (
        result["debt_held_by_public_billions"] / result["fiscal_year_nominal_gdp_billions"]
    )
    return result


METRICS = {
    "primary_deficit_billions": (
        "primary_deficit_billions",
        "primary_deficit_billions",
        "billions of dollars",
        "CBO fiscal-year primary deficits are imposed exogenously and divided "
        "into four equal nominal quarterly flows.",
    ),
    "interest_measure_billions": (
        "modeled_debt_interest_cost_billions",
        "cbo_net_interest_outlays_billions",
        "billions of dollars",
        "Simulator debt-financing cost includes marketable accruals, TIPS "
        "compensation, and a coarse other-public-debt cost; CBO net interest also "
        "nets federal interest income and includes other budget accounts.",
    ),
    "total_deficit_billions": (
        "modeled_total_deficit_billions",
        "total_deficit_billions",
        "billions of dollars",
        "Difference is primarily the intentional modeled-debt-interest versus "
        "CBO-net-interest definition gap.",
    ),
    "debt_held_by_public_billions": (
        "debt_held_by_public_billions",
        "debt_held_by_public_billions",
        "billions of dollars",
        "Simulator starts from Treasury's 2025-09-30 MSPD stock; differences then "
        "accumulate from interest definitions, security issuance assumptions, "
        "and rounding.",
    ),
    "debt_held_by_public_gdp_ratio": (
        "debt_held_by_public_gdp_ratio",
        "debt_held_by_public_gdp_ratio",
        "ratio",
        "Uses fiscal-year nominal GDP (the mean of four calendar-quarter SAAR "
        "levels), matching CBO's annual denominator; debt differences remain in "
        "the numerator.",
    ),
    "other_financing_adjustment_billions": (
        "other_financing_adjustment_billions",
        "other_financing_adjustment_billions",
        "billions of dollars",
        "CBO's published other-means-of-financing path is imposed and divided "
        "into four equal nominal quarterly flows.",
    ),
}


def build_validation_table(
    result: SimulationResult, cbo_fiscal_baseline: pd.DataFrame
) -> pd.DataFrame:
    simulator = aggregate_fiscal_years(result)
    comparison = simulator.merge(cbo_fiscal_baseline, on="fiscal_year", suffixes=("_sim", "_cbo"))
    comparison = comparison[comparison["fiscal_year"].between(2026, 2036)]
    records: list[dict[str, float | int | str]] = []
    for row in comparison.itertuples(index=False):
        row_dict = row._asdict()
        for metric, (sim_col, cbo_col, unit, explanation) in METRICS.items():
            sim_key = sim_col
            cbo_key = cbo_col
            if sim_col == cbo_col:
                sim_key = f"{sim_col}_sim"
                cbo_key = f"{cbo_col}_cbo"
            simulator_value = float(row_dict[sim_key])
            cbo_value = float(row_dict[cbo_key])
            records.append(
                {
                    "fiscal_year": int(row_dict["fiscal_year"]),
                    "metric": metric,
                    "unit": unit,
                    "simulator": simulator_value,
                    "cbo": cbo_value,
                    "difference": simulator_value - cbo_value,
                    "difference_percent_of_cbo": (
                        (simulator_value - cbo_value) / abs(cbo_value)
                        if cbo_value != 0
                        else float("nan")
                    ),
                    "explanation": explanation,
                }
            )
    return pd.DataFrame.from_records(records)


def run_baseline_validation() -> tuple[Scenario, SimulationResult, pd.DataFrame]:
    bundle = load_baseline_bundle()
    # Preserve the v0.1 February 11 ten-year validation window exactly.
    scenario = build_baseline_scenario(bundle, end_period="2036Q3")
    result = run_simulation(
        bundle.initial_stock,
        scenario.quarterly_assumptions,
        initial_nominal_gdp_billions_saar=bundle.initial_nominal_gdp_billions_saar,
        initial_real_gdp_billions_chained_saar=bundle.initial_real_gdp_billions_chained_saar,
        issuance_strategy=bundle.issuance_strategy,
        scenario_name=scenario.name,
        data_vintage=bundle.cbo_vintage,
    )
    table = build_validation_table(result, bundle.cbo_fiscal_baseline)
    return scenario, result, table


def validation_cli() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_DATA_ROOT / "processed")
    parser.add_argument("--config-dir", type=Path, default=Path("config/baseline"))
    args = parser.parse_args()
    scenario, result, table = run_baseline_validation()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.config_dir.mkdir(parents=True, exist_ok=True)
    quarterly_path = args.output_dir / f"baseline_simulation_quarterly_{DEFAULT_CBO_VINTAGE}.csv"
    validation_path = args.output_dir / f"baseline_validation_{DEFAULT_CBO_VINTAGE}.csv"
    config_path = args.config_dir / f"cbo_baseline_{DEFAULT_CBO_VINTAGE}.json"
    result.quarterly.to_csv(quarterly_path, index=False)
    table.to_csv(validation_path, index=False)
    config_path.write_text(
        json.dumps(
            {
                "scenario_name": scenario.name,
                "description": scenario.description,
                "data_vintage": DEFAULT_CBO_VINTAGE,
                "start_period": result.quarterly.iloc[0]["quarter"],
                "end_period": result.quarterly.iloc[-1]["quarter"],
                "imposed_parameters": scenario.imposed_parameters,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    print(f"Wrote {quarterly_path}")
    print(f"Wrote {validation_path}")
    print(f"Wrote {config_path}")
    max_residual = result.quarterly["debt_identity_residual_billions"].abs().max()
    print(f"Maximum quarterly debt-identity residual: {max_residual:.3e} billion dollars")


if __name__ == "__main__":
    validation_cli()
