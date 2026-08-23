# U.S. Fiscal Dynamics Simulator

A transparent, deterministic quarterly model of U.S. federal debt dynamics,
Treasury refinancing, and conditional closure requirements. Version 0.2 preserves
the v0.1 forward engine and adds inverse solvers that ask what fiscal adjustment,
inflationary price-level change, mechanical debt haircut, or new-yield suppression
would be required to meet an explicit debt/GDP condition. It is not a forecast or a
crisis model.

The motivating experiment is an inflation shock. Conventional fixed-rate debt retains
its coupon until maturity, bills roll quickly, FRNs reset, and TIPS principal is indexed.
Inflation and issuance rates remain independent user assumptions so that the simulator
does not smuggle in a monetary-policy rule.

## Install

Python 3.12 or newer is required. With
[uv](https://docs.astral.sh/uv/):

```bash
uv sync --extra dev
```

The equivalent pip installation is:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
```

The checked-in processed data make the model runnable offline.

## Run

```bash
uv run pytest
uv run python scripts/run_baseline_validation.py
uv run python scripts/run_initial_experiments.py
uv run python scripts/run_v02_experiments.py
uv run python scripts/run_confidence_shock_experiment.py
uv run python scripts/run_2026_household_scenario.py
uv run python scripts/run_2036_monetary_backstop_experiment.py
uv run streamlit run app/streamlit_app.py
```

The main Streamlit page retains the v0.1 forward simulator. The multipage navigation
adds **Something Has to Give**, with four conditional closure cards, pure-mechanism
paths, an inflation/refinancing decomposition, mixed closure frontiers, the rate-shock
stress ladder, and research tables. It also includes the pinned 2045 confidence-premium
narrative, **This Is What “It Won’t End Well” Looks Like**. Custom forward controls continue to expose
inflation, real growth, primary deficits, other financing, and issuance rates
independently.

## Refresh the source data

```bash
uv run python scripts/refresh_data.py \
  --cbo-vintage 2026-02 \
  --treasury-date 2025-09-30
```

The refresh process downloads official CBO and Treasury machine-readable data, writes
date-stamped immutable raw snapshots, normalizes them, and records URLs, query
parameters, retrieval timestamps, and SHA-256 hashes in `data/metadata/`. It refuses to
overwrite an existing snapshot unless `--force` is explicitly supplied. A different
vintage should use a different vintage/date, not replace the pinned one.

The repository pins:

- CBO's February 11, 2026 budget and economic baseline (`2026-02`);
- CBO's distinct February 25, 2026 long-term budget and economic extension through 2056;
- Treasury's September 30, 2025 Monthly Statement of the Public Debt;
- Treasury auction records used to recover FRN spreads;
- retrieval date August 22, 2026.

See [data_sources.md](docs/data_sources.md) and the machine-readable
[manifest](data/metadata/manifest_cbo-2026-02_treasury-2025-09-30.json) for exact
provenance.

## Repository map

- `src/debt_sim/`: simulation, debt ledger, instruments, scenarios, data, validation;
- `app/streamlit_app.py`: analytical interface only; no model equations live here;
- `scripts/`: data refresh, validation, and reproducible experiments;
- `config/`: pinned baseline and saved scenario configurations;
- `data/raw/`, `data/processed/`, `data/metadata/`: reproducible data layers;
- `tests/`: accounting and economic-behavior tests;
- `docs/`: methodology, sources, assumptions, validation, limitations, and findings.

The external literature and terminology checks used for v0.2 are recorded in
[literature.md](docs/literature.md).

For a plain-language household interpretation of a confidence shock beginning in
2026, see [What a Treasury Confidence Shock Would Mean for the Middle Class](docs/confidence_shock_household_scenario.pdf). The worked scenario selects one closure---a
permanent wage-tax surcharge---then contrasts it with continuous deficit financing and a
model-solved monetary backstop. It includes reproducible fiscal, inflation, refinancing, and
household purchasing-power calculations. Ray Dalio and Peter Schiff appear only as popular
narrative comparisons, not as validation or model equations.

## Current scope

v0.2 includes quarterly nominal GDP, exogenous primary deficits, debt held by the public,
marketable security cohorts, nonmarketable public debt, refinancing, issuance, bills,
fixed-rate notes/bonds, TIPS, FRNs, scenario comparison, closure targets, bounded inverse
solvers, mixed frontiers, and rate stresses. A haircut is only a mechanical face-value
equivalent; financial repression is only an imposed low-new-yield path. The simulator
deliberately excludes endogenous fiscal or Federal Reserve behavior, risk premia, actual
default dynamics, exchange rates, investor behavior, stochastic shocks, welfare rankings,
and general equilibrium. The most important caveats are in
[limitations.md](docs/limitations.md).
