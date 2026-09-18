# Start here: fiscal endgame research handoff

Updated September 18, 2026. Read this before expanding the model or rewriting the paper.

## September 18 outlook and repository checkpoint

The user asked to record the assistant's qualitative outlook and commit all pending
project work. [What I expect to happen](docs/fiscal_outlook_judgment.md) preserves the
September 16 assessment: continued borrowing, increasing pressure, and delayed,
uneven adjustment. It includes primary-source links and household consequences,
and distinguishes that judgment from the simulator's conditional results.

The checkpoint includes the previously uncommitted model extensions, configurations,
generated data, tests, and documents as well as the new outlook and navigation links.
The outlook adds no model calibration or new simulations. The separate scenario,
review, article, and untouched archive retain their roles below. The prior research
recommendations remain available; recording this outlook does not carry them out.

Checkpoint validation: all 77 tests passed, `uv run ruff check .` passed, local links
in the outlook/README/handoff resolved, and the untouched scenario archive matched
its recorded SHA-256. No simulation outputs or PDFs were regenerated for this task.

## September 7 document preservation decision

The user asked to recover the August 29 mechanism-led scenario, preserve the September 5
critique separately, and retain the new self-contained article. Do not overwrite one with
another. The original scenario is a legitimate conditional mechanism illustration; its
inflation sensitivity, assumed financing limit, and conditional recovery remain material
qualifications. Restoring it does not establish a most-likely outcome or invalidate the review.

- `docs/confidence_shock_household_scenario.tex` is the restored working scenario, with its
  narrative, figures, and original numerical results retained and targeted qualifications added.
- `docs/confidence_shock_review.tex` preserves the September 5 review, with only a companion
  note and document links/build instructions changed.
- `docs/continuing_to_borrow.tex` is the unchanged self-contained article and appendix.
- `docs/confidence_shock_household_scenario_2026-08-29.tex` is the untouched archival source.
  It contains all 1,439 lines captured before the review rewrite on September 5 at
  21:19:47.494 UTC. Recovery used the complete recorded output of
  `git status --short && cat docs/confidence_shock_household_scenario.tex`, not the older
  August 23 Git version. Its SHA-256, including the final newline, is
  `4940a6641140ce863241f39dd8146b78f3c0dbb93b4fa53570c2fb8ffe0a0b5b`.

Each source has a same-named PDF. The archive PDF is a fresh rendering of the recovered
source with the existing figure CSVs, not a recovered copy of the old PDF bytes.
The recovery makes no simulation or data changes. Preserve this separation in future edits.
Recovery checks verified the archival source byte-for-byte, preserved all five original
figures and displayed equations in the working scenario, and confirmed that the review's
analysis is unchanged. The three recovered/relocated PDFs build without warnings, document
links resolve, and hashes confirm that model code, parameters, data, and the new article
remain unchanged. No model tests or simulations were rerun for this editorial task.
The research suggestions below are prior recommendations, not authorization to expand the
model during this document-recovery task.

## At a glance

- **User's objective:** Explain what “U.S. deficit spending won't end well” actually
  means: why continued fiscal commitments become untenable, what changes, and who bears
  the consequences. A rising debt/GDP chart or an invented crisis story is insufficient.
- **User's priority:** Do not waste time on an open-ended research project that never
  answers that question. They explicitly want an honest assessment of whether further
  work can deliver an answer before spending more usage on it.
- **Current verdict:** Useful Treasury accounting and conditional stress calculations;
  no empirically identified U.S. breaking point or uniquely predicted endgame.
- **Latest advance:** A tested, illustrative model in which stable financing disappears
  as the permanent deficit rises, without an imposed debt or auction ceiling. Its
  borrowing-cost curve is unestimated. It demonstrates a mechanism, not a U.S. limit.
- **Next decision:** Can an existing published model and accessible evidence turn that
  mechanism into informative U.S. bounds and concrete conditional consequences? Assess
  this in one bounded feasibility pass before building additional machinery.
- **Prior model validation (September 5):** 77 tests passed; new Python files passed Ruff;
  the then-current research PDFs compiled without warnings. These checks validate
  implementation, not the economics; document recovery does not rerun or recalibrate models.

## What counts as an answer, and when to stop

This is not an unsolved mathematical conjecture waiting for enough computation. The
obstacles are empirical identification and future policy choices. An exact unconditional
crisis date and outcome cannot honestly be promised. An evidence-backed explanation of
the mechanisms, supportable fiscal paths, and consequences under explicit policy choices
is a realistic research product. Whether this repository can quantify those consequences
well enough remains to be established.

The next agent should deliver a short feasibility verdict with a concrete result or a
specific reason to stop. Do not simply repeat “we need expectations, general equilibrium,
and better calibration.” Do not make building a complete macroeconomic model a prerequisite
for giving the user a useful answer. Reuse published models, replication code, and estimates.

Recommended bounded next step:

1. Inspect the published **Mian–Straub–Sufi Goldilocks model and replication package**.
   Determine which financing/growth parameters can actually be identified for this U.S.
   counterfactual. Start by reproducing a published benchmark, not inventing another curve.
2. Compare the continuing scheduled-commitments fiscal path with the supported deficit
   schedule over defensible parameter ranges. Explicitly account for the possibility
   that observed borrowing rates reflect expectations of future fiscal reform.
3. Produce a decision table: which cases support continued rollover, which require an
   adjustment, and what evidence distinguishes them. For unsupported cases, explain the
   concrete fiscal, purchasing-power, or payment consequences under stated policy responses.
   Use existing cohort/closure tools where they already answer the quantitative question.
4. If the available evidence cannot narrow the cases enough to be useful, say so and
   recommend stopping model expansion. Finish with the strongest defensible explanation
   of “won't end well” and precisely identify what remains unknowable from these inputs.

Continue only if the next calculation materially narrows an uncertainty or quantifies a
meaningful consequence. Stop or narrow scope if results depend mainly on another freely
chosen demand curve, terminal target, or regime-switch threshold. More scenarios, tests,
PDFs, and roadmap checkboxes are not by themselves progress toward the user's answer.
This bounded approach is a handoff recommendation, not a user-specified time/token budget.

## Read these files first

| File | What it contains |
| --- | --- |
| [Restored main scenario](docs/confidence_shock_household_scenario.pdf) / [TeX](docs/confidence_shock_household_scenario.tex) | August 29 mechanism, hypothetical chronology, and conditional recovery, with targeted September 7 qualifications. |
| [Companion review](docs/confidence_shock_review.pdf) / [TeX](docs/confidence_shock_review.tex) | September 5 economic critique and no-shock/sensitivity calculations, preserved separately. |
| [Self-contained article](docs/continuing_to_borrow.pdf) / [TeX](docs/continuing_to_borrow.tex) | Three findings with a self-contained simulation appendix. |
| [Untouched historical scenario](docs/confidence_shock_household_scenario_2026-08-29.pdf) / [TeX](docs/confidence_shock_household_scenario_2026-08-29.tex) | Verbatim recovered August 29 source; do not edit this archive. |
| [Financing mechanism note](docs/fiscal_space_mechanism.pdf) / [TeX](docs/fiscal_space_mechanism.tex) | Separate illustrative mechanism, diagram, derivation, and missing economic decisions; 4 pages. |
| [Review findings](docs/sustainability_review.md) | Concise audit of the earlier confidence story and new numerical results. |
| [Roadmap](docs/crisis_simulator_roadmap.md) | Top section gives the latest priority. Historical checked boxes below are engineering milestones, not evidence that the research question is solved. |

The latest mechanism note is a separate follow-up to the main paper. The main paper has
not been rewritten around a calibrated version of that mechanism; none exists yet.

## Findings that must not be lost or overstated

**The old crisis date was imposed indirectly.** The earlier model added a 500-basis-point
Treasury premium for ten years, then stopped financing at a supplied multiple of reference
gross issuance. The 2039Q3 boundary under the central curve is not a discovered U.S. fiscal
limit. Gross rollover recycles principal and is not equivalent to net absorption of new debt.

**The no-shock path is protected by construction.** In `crisis.py`, incremental interest
demand and debt-yield premiums are reference-relative, and capacity is normalized to the
reference. With no initiating shock, turning on debt yields and central capacity reproduces
the baseline even as debt rises. That engine cannot independently discover baseline loss
of fiscal credibility.

**The inflation spiral is assumption-sensitive.** Keeping the 500-basis-point stress and
recipient spending unchanged, reducing unestimated quarterly inflation persistence from
0.98 to 0.90 lowers 2056 inflation from 8.04% to 2.89% (peak 3.15%). Debt still reaches
259.92% of GDP. The original ten-year Treasury premium also has no direct private-demand
effect; the separate private-credit spread lasts only two years. Holdings shares are not
empirically estimated net interest-income spending responses.

**The no-shock fiscal imbalance is concrete.** The pinned baseline ends at 172.7745%
debt/GDP in 2056Q3, with a final-four-quarter increase of 3.1342 percentage points.
Contributions are +2.20 primary deficits, +6.88 modeled interest, and -5.95 nominal GDP
growth. They use quarterly GDP denominators, not a single fiscal-year denominator.
The corresponding fiscal-year baseline ratio is about 175.06%. Modeled interest cost
differs from CBO net interest.

**Preventive adjustment is a finite-horizon calculation.** Under reference growth,
inflation, and issuance rates, a permanent primary improvement of 2.6767% of GDP starting
2026Q4 yields 86.72% debt/GDP in 2056. A four-year phase-in requires 2.7029% and ends at
91.54%. Success means terminal debt/GDP below opening 99.22% and no final-year increase;
the trend constraint binds. No fiscal multiplier is estimated. This does not prove
post-2056 stability. The older 5.48% recovery package uses a different inherited crisis
stock, macro path, horizon, and target; comparing the two does not identify the cost of delay.

**“No policy change” needs a precise counterfactual.** Pinned CBO projections continue
scheduled benefits beyond trust-fund exhaustion under baseline conventions; literal
legislative inaction does not authorize all those payments. The pinned February 2026
report projects OASI exhaustion in 2032. A payable-benefits alternative has not been
simulated. Do not conflate legal payment constraints with a bond-market crisis.

## Latest prototype: what it does and does not establish

`src/debt_sim/fiscal_space.py` defines an annual single-rate environment with nominal
growth `n`, debt/GDP `b`, and an effective borrowing rate `i(b)`. Primary deficits `d`
are shares of current GDP:

```text
F(b) = [n - i(b)] b / (1+n)
b_next - b = d - F(b)
F'(b) = [n - i(b) - b i'(b)] / (1+n)
```

Fixed points satisfy `d = F(b)`. Local stability of this scalar annual map requires
`0 < F'(b) < 2`. If `d > max F(b)`, the fixed environment has no bounded debt path.
At an interior maximum, `n - i(b) = b i'(b)`: interest can remain below growth when
the stable branch disappears. This is not a forward-looking equilibrium solver.

Illustrative inputs: growth 4%, interest 3% at 100% debt/GDP, and an interest increase
of 1 basis point per additional debt/GDP percentage point. The maximum stationary
primary deficit is 0.9615% of GDP. At deficit 0.8%, roots are 59.01% (stable) and
140.99% (unstable). At deficit 1.25%, there are no roots. **None of these is a U.S.
threshold.** The rate schedule is supplied; immediate repricing omits the Treasury
maturity ledger; growth and inflation are fixed; policy selection is absent.

Existing tools worth retaining:

- `src/debt_sim/model.py`, `debt_stock.py`, `instruments.py`: Treasury cohort accounting.
- `closure.py`: conditional fiscal, inflation, and other adjustment solvers.
- `policy.py`: partial Fed/Treasury consolidation and alternative monetary regimes.
- `sustainability.py`: exact debt-ratio decomposition and constant-policy counterexamples.
- `crisis.py`: sequential macro stress engine, subject to the limitations above.

## Sources already checked; start here instead of repeating the search

- [Mian, Straub, Sufi, AER 2025](https://www.aeaweb.org/articles?id=10.1257/aer.20220308):
  *A Goldilocks Theory of Fiscal Deficits*. The publisher links the replication package.
  The example in this repo is **not** a replication. Published results use earlier data;
  do not transplant their debt or deficit thresholds into 2026.
- [Author's July 2025 manuscript](https://atif.scholar.princeton.edu/sites/g/files/toruqf3691/files/documents/Goldilocks_AERForthcoming.pdf):
  Section 3 develops the deficit–debt schedule. This was inspected during the session.
- [Jiang et al., fiscal capacity](https://www.nber.org/papers/w29902): risk-adjusted
  valuation of fiscal backing; useful complementary approach, not a risk-free PV shortcut.
- [Blanchard 2019](https://www.aeaweb.org/articles?id=10.1257/aer.109.4.1197): sustainable
  rollover under low safe rates; fiscal feasibility differs from welfare.
- [Auclert 2019](https://www.aeaweb.org/articles?id=10.1257/aer.20160137) and
  [BIS 2026, chapter II](https://www.bis.org/publications/aer-2026/high-public-debt-shifting-financial-markets):
  interest income, valuation, and heterogeneous exposure; not estimates of our spending fraction.
- [CBO February 2026](https://www.cbo.gov/publication/62105): pinned baseline and
  scheduled/payable benefits distinction, especially appendices B and C.
- [Bhatt et al. 2026](https://www.federalreserve.gov/econres/feds/the-causal-effect-of-debt-on-interest-rates.htm):
  local expected-debt effects on rates; not a full investor-demand curve or crisis threshold.

## Reproduction and workspace cautions

From the repository root:

```bash
uv run python scripts/run_sustainability_review.py
uv run python scripts/run_fiscal_space_experiment.py
uv run pytest -q
latexmk -pdf -cd -interaction=nonstopmode -halt-on-error docs/confidence_shock_household_scenario.tex
latexmk -pdf -cd -interaction=nonstopmode -halt-on-error docs/confidence_shock_review.tex
latexmk -pdf -cd -interaction=nonstopmode -halt-on-error docs/continuing_to_borrow.tex
latexmk -pdf -cd -interaction=nonstopmode -halt-on-error docs/confidence_shock_household_scenario_2026-08-29.tex
latexmk -pdf -cd -interaction=nonstopmode -halt-on-error docs/fiscal_space_mechanism.tex
```

New outputs are `data/processed/sustainability_review_*.csv` and `fiscal_space_*.csv`.
Parameters are in `config/scenarios/sustainability_review.json` and
`fiscal_space_illustration.json`. New tests are `tests/test_sustainability.py` and
`tests/test_fiscal_space.py`. No baseline data were refreshed.

**Historical workspace note (September 5–7):** The worktree was already extensively
dirty before those sessions began. Many untracked engines, scripts, configurations,
and data files predated them and were user work. No commits were made during those
sessions; the September 18 checkpoint includes that accumulated work. Preserve it;
do not use reset, clean, or blanket checkout to tidy it. The September 5 session
added the review/diagnostic files, revised the main
scenario paper/PDF, and updated supporting documentation. September 7 restored that
scenario and relocated the review as described above. Neither operation recalibrated the earlier
macro engines or completed all items in the roadmap. Do not treat the existing app's
older narrative or `model_note.tex` as an updated statement of the review's conclusions.

The earlier pause for a usage limit prompted this handoff, not additional research
during that pause. September 18 authorized recording the outlook and committing the
workspace. Further model expansion still needs a substantive user request. Their
patience should be spent
on narrowing the answer, not on another cycle of impressive machinery and new caveats.
