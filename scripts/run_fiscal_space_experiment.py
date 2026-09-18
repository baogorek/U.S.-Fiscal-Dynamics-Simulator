"""Illustrate stable financing, an unstable boundary, and loss of fixed points.

All parameters are illustrative. Output is deliberately labeled by years from
start, not U.S. calendar dates. No U.S. crisis probability or threshold is fitted.
"""

import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

from debt_sim.fiscal_space import LinearFinancingEnvironment


def main() -> None:
    model = LinearFinancingEnvironment()
    output = Path("data/processed")
    output.mkdir(parents=True, exist_ok=True)
    curve = pd.DataFrame([
        {"debt_gdp_pct": debt * 100,
         "steady_primary_deficit_pct": model.steady_primary_deficit(debt) * 100,
         "interest_rate_pct": model.interest_rate(debt) * 100}
        for debt in np.linspace(0, 2.2, 221)
    ])
    curve.to_csv(output / "fiscal_space_curve.csv", index=False)
    paths, points, cases = [], [], []
    for name, initial, deficit in (
        ("convergent", 1.0, 0.008),
        ("above_unstable_fixed_point", 1.6, 0.008),
        ("no_fixed_point", 1.0, 0.0125),
    ):
        path = model.simulate(
            initial_debt_gdp_ratio=initial, primary_deficit_gdp_share=deficit, years=80,
        ).assign(scenario=name)
        paths.append(path)
        fixed_points = model.fixed_points(deficit)
        points.extend({"scenario": name, **asdict(point)} for point in fixed_points)
        cases.append({
            "scenario": name, "initial_debt_gdp_ratio": initial,
            "primary_deficit_gdp_share": deficit, "fixed_point_count": len(fixed_points),
            "terminal_debt_gdp_ratio": float(path.debt_gdp_ratio.iloc[-1]),
        })
        print(name, [(p.stability, round(p.debt_gdp_ratio, 6)) for p in fixed_points])
    pd.concat(paths, ignore_index=True).to_csv(output / "fiscal_space_paths.csv", index=False)
    pd.DataFrame(points).to_csv(output / "fiscal_space_fixed_points.csv", index=False)
    pd.DataFrame(cases).to_csv(output / "fiscal_space_cases.csv", index=False)
    config = {
        "environment": asdict(model), "cases": cases, "years": 80,
        "maximum_steady_primary_deficit": model.maximum_steady_primary_deficit,
        "debt_at_maximum_deficit": model.debt_at_maximum_deficit,
        "interpretation": "Illustrative annual fixed-point diagnostic; not calibrated to the US",
        "limitations": [
            "Rates are effective rates on the whole debt stock; maturities are omitted.",
            "The affine rate schedule is supplied, not derived from investor optimization.",
            "There is no fiscal reaction, price-level adjustment, or post-break regime selection.",
            "Fixed-point stability applies to this annual map, not a forward-looking equilibrium.",
        ],
    }
    Path("config/scenarios/fiscal_space_illustration.json").write_text(
        json.dumps(config, indent=2) + "\n",
    )


if __name__ == "__main__":
    main()
