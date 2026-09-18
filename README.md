# U.S. Fiscal Dynamics Simulator

**Continuing this project? Read [HANDOFF.md](HANDOFF.md) first.** It records the user's
objective, current findings, and a bounded next step with criteria for stopping research.

For the current qualitative assessment, read
[What I expect to happen: delayed, uneven fiscal adjustment](docs/fiscal_outlook_judgment.md)
(September 18, 2026). It records the assistant's judgment, supporting evidence, and
expected household consequences; it is not a forecast established by the simulator.

## Read the scenario and its review together

| Document | Purpose |
| --- | --- |
| [A 500-Basis-Point Treasury Stress](docs/confidence_shock_household_scenario.pdf) ([source](docs/confidence_shock_household_scenario.tex)) | Main worked scenario: refinancing, interest income, inflation, financing stress, and a conditional recovery. Restored with targeted qualifications. |
| [Companion sustainability review](docs/confidence_shock_review.pdf) ([source](docs/confidence_shock_review.tex)) | No-shock fiscal diagnostics and challenges to the scenario's economic assumptions. |
| [The Consequences of Continuing to Borrow](docs/continuing_to_borrow.pdf) ([source](docs/continuing_to_borrow.tex)) | Self-contained overview of three findings, with equations and reproduction details in its appendix. |
| [Untouched August 29 scenario](docs/confidence_shock_household_scenario_2026-08-29.pdf) ([source](docs/confidence_shock_household_scenario_2026-08-29.tex)) | Historical edition preserved verbatim; read its claims alongside the subsequent review. |

The original mechanism-led paper and its critique are separate documents. The scenario
is a conditional worked example, not a most-likely forecast: its chronology is hypothetical,
its 2039 financing boundary depends on an unestimated capacity curve, and its inflation
result is sensitive to behavioral assumptions. The review remains worth reading without
replacing the scenario it evaluates. See the [review findings](docs/sustainability_review.md).
Archive provenance and the preservation decision are recorded in [HANDOFF.md](HANDOFF.md).
For public framing, reader order, and a suggested opening, see
[How to write up and share this work](docs/public_writeup_approach.md).

The follow-up [financing mechanism note](docs/fiscal_space_mechanism.pdf) demonstrates
how a stable debt path can disappear when borrowing costs respond to debt, without an
imposed auction ceiling. It is an illustrative fixed-point diagnostic awaiting U.S.
calibration, and specifies the missing investor behavior and policy choices.

## Simulator

A transparent, deterministic quarterly model of U.S. federal debt dynamics,
Treasury refinancing, and conditional closure requirements. The forward engine and
inverse solvers ask what fiscal adjustment, inflationary price-level change,
mechanical debt haircut, or new-yield suppression would be required to meet an
explicit debt/GDP condition. Experimental policy modules now test how the Federal
Reserve, Treasury debt management, inflation, output, and automatic stabilizers
interact. A sequential crisis experiment also feeds stress-created Treasury interest
income into later demand, inflation, and Federal Reserve rates without targeting a
terminal debt ratio. Its outputs are conditional scenario paths.

The motivating experiment is an inflation shock. Conventional fixed-rate debt retains
its coupon until maturity, bills roll quickly, FRNs reset, and TIPS principal is indexed.
The general forward engine keeps inflation and issuance rates as independent user
assumptions. Experimental feedback runs add explicit, replaceable monetary and
macro-fiscal rules around that accounting kernel.

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
uv run python scripts/run_policy_regime_experiment.py
uv run python scripts/run_treasury_response_experiment.py
uv run python scripts/run_macro_policy_feedback_experiment.py
uv run python scripts/run_sequential_crisis_experiment.py
uv run python scripts/run_sequential_policy_frontier.py
uv run python scripts/run_debt_yield_feedback_experiment.py
uv run python scripts/run_private_market_clearing_experiment.py
uv run python scripts/run_recovery_settlement_experiment.py
uv run python scripts/run_sustainability_review.py
uv run python scripts/run_fiscal_space_experiment.py
uv run streamlit run app/streamlit_app.py
```

The main Streamlit page contains the forward simulator. The multipage navigation adds
**Something Has to Give**, with four conditional closure cards, pure-mechanism
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

The staged implementation plan for endogenous policy and market feedback is in
[crisis_simulator_roadmap.md](docs/crisis_simulator_roadmap.md).

The external literature and terminology checks are recorded in
[literature.md](docs/literature.md).

For a worked refinancing stress beginning in 2026, see
[A 500-Basis-Point Treasury Stress](docs/confidence_shock_household_scenario.pdf).
The paper asks whether repeated borrowing for primary deficits and interest can continue
indefinitely. It traces refinancing through interest-recipient demand, inflation, Federal
Reserve tightening, debt-dependent yields, and a finite aggregate financing-capacity rule.
Ray Dalio and Peter Schiff motivate the opening question; the simulator identifies the
assumptions under which price stability or market absorption eventually fails.
It then carries the inherited 2039 Treasury stock through a conditional recovery in which a
four-year fiscal settlement and gradual rate normalization return debt/GDP to a declining
path by 2056.

## Current scope

The validated accounting kernel includes quarterly nominal GDP, primary deficits,
debt held by the public,
marketable security cohorts, nonmarketable public debt, refinancing, issuance, bills,
fixed-rate notes/bonds, TIPS, FRNs, scenario comparison, closure targets, bounded inverse
solvers, mixed frontiers, and rate stresses. Experimental modules add explicit Federal
Reserve regimes and balance-sheet accounting, adaptive issuance, market-value Treasury
buybacks, and lagged macro-fiscal feedback. Their behavioral coefficients are not yet
historically calibrated. The sequential vertical slice calculates stress interest,
recipient spending, output, inflation, and the next policy response quarter by quarter;
its inflation ceilings are reported as breaches rather than imposed as terminal
constraints. A reference-anchored private-absorption diagnostic reports the issuance yield
and capacity implied by supplied demand sensitivities without yet changing the simulated
yield path. An optional debt-yield rule maps a lagged deterioration relative to the parallel
reference debt/GDP path into later Treasury yields using an explicitly documented empirical
sensitivity range. An experimental private-market-clearing run raises a common issuance spread
until a supplied
aggregate absorption curve clears and terminates when issuance exceeds its finite capacity.
This boundary is conditional on an unestimated curve. A separate recovery experiment starts
from the last successful central-capacity quarter, publishes conditional post-settlement
growth, inflation, and yield paths, and solves the cohort arithmetic for the primary-balance
improvement required to stabilize debt. Political response and the probability of those
recovery assumptions remain outside the experiment. A haircut is only a mechanical face-value equivalent; financial repression is
only an imposed low-new-yield path. The simulator still excludes structural endogenous
investor demand curves, auction failure, actual default dynamics, exchange rates, bank losses,
stochastic shocks, welfare rankings, and general equilibrium. The most important caveats are in
[limitations.md](docs/limitations.md).
