# Review of fiscal sustainability, September 5, 2026

The follow-up [financing mechanism note](fiscal_space_mechanism.pdf) goes beyond this
review: a separate illustrative experiment calculates stable and unstable fiscal fixed
points, and shows their disappearance as the permanent deficit rises. Its rate schedule
still needs empirical identification; it supplies a sharper economic test, not a U.S.
crisis threshold. The updated [roadmap](crisis_simulator_roadmap.md) prioritizes estimation
of financing conditions and consistent investor expectations about policy responses.

The [companion review](confidence_shock_review.pdf)
([source](confidence_shock_review.tex)) presents an economic argument, a no-shock
experiment, and challenges to the macro assumptions. It is now separate from the
[restored mechanism-led scenario](confidence_shock_household_scenario.pdf), whose
hypothetical chronology and worked recovery remain available. The
[untouched August 29 edition](confidence_shock_household_scenario_2026-08-29.pdf)
preserves the original, and a [self-contained overview](continuing_to_borrow.pdf)
explains three findings. The document reorganization changed no model parameters or
outputs; the review still retains the original stress and recovery plots in its appendix.

## Conclusions

Permanent deficits are not inherently unsustainable. In a constant-rate annual example,
3% nominal interest and 4% nominal growth support a permanent primary deficit of 1% of
GDP at steady-state debt of 104% of GDP. The example is a counterexample to inevitability,
not a claim about future U.S. borrowing costs.

The pinned no-shock baseline nevertheless has debt rising relative to income through
2056. Continued fiscal commitments cannot indefinitely outrun the growth and demand for
liabilities that support them while preserving all real payment terms. Adjustment can
involve fiscal changes, lower real creditor returns, changed payments, or sufficiently
favorable growth and financing conditions. The model does not identify which occurs.

## Findings that change the earlier interpretation

1. **No-shock instability is not identified by the crisis engine.** Interest demand and
   debt-dependent yields are reference-relative, and absorption is normalized to reference
   issuance. With no initiating shock, enabling debt-yield feedback and the central capacity
   curve reproduces the reference exactly, despite its rising debt ratio.
2. **Inflation is highly assumption-dependent.** With the same 500-basis-point stress and
   interest spending, changing quarterly inflation persistence from 0.98 to 0.90 reduces
   2056 inflation from 8.04% to 2.89%. Peak inflation becomes 3.15%, while debt/GDP reaches
   259.92%. The earlier approximately 10% spending threshold is specific to a grid that
   fixed the remaining macro coefficients.
3. **Treasury stress lacks direct private transmission in the original experiment.**
   The Treasury premium lasts ten years; the independent private spread lasts two.
   Federal financing costs feed interest income, while the premium itself does not enter
   private demand restraint. A new sensitivity passes half that premium into private
   credit. This is a challenge assumption, not a calibrated correction.
4. **Gross-issuance capacity is not a solvency estimate.** Rollover recycles principal;
   gross turnover depends on maturities. A ceiling of 1.5 times reference gross issuance
   does not identify net desired holdings, fiscal backing, or a national shortage of savings.
5. **The recovery assumes the macro recovery.** Its 5.48%-of-GDP fiscal improvement is
   computed under supplied growth, inflation, and rate paths. The calculation does not
   establish that the package would cause those paths.
6. **Literal legislative inaction differs from the fiscal baseline.** CBO's February 2026
   baseline assumes scheduled benefits continue after trust-fund exhaustion. Its payable
   benefits alternative recognizes the financing-authority constraint. See
   [CBO, appendices B and C](https://www.cbo.gov/publication/62105). The new simulations
   retain the scheduled-commitments baseline and do not simulate payable benefits.

## New quantitative results

The no-shock path ends at 172.77% debt/GDP in 2056Q3. Contributions to the final four-quarter
increase are +2.20 percentage points from primary deficits, +6.88 from modeled interest,
and -5.95 from nominal GDP growth, totaling +3.13 points. Each contribution uses its
quarter's GDP denominator. These are neither fiscal-year budget flow shares nor CBO net
interest measures.

Holding growth, inflation, and rates at their reference paths, a permanent primary-balance
improvement of 2.6767% of GDP starting in 2026Q4 produces 86.72% debt/GDP in 2056. A
four-year phase-in requires 2.7029% and ends at 91.54%. Both require debt/GDP no greater
than its opening 99.22% and no increase during the final four quarters. The trend condition
binds. These are finite-horizon accounting requirements, with no estimated fiscal multiplier
or optimal target, and do not prove post-2056 stability. They cannot be directly compared
with the 2039 recovery package as an estimate of the cost of waiting.

## Reproduction

```bash
uv run python scripts/run_sustainability_review.py
uv run pytest
cd docs
latexmk -pdf -interaction=nonstopmode -halt-on-error confidence_shock_review.tex
```

New data are `data/processed/sustainability_review_*.csv`, the new figure reads
`docs/sustainability_review_plot_data.csv`, and complete scenario choices are recorded in
`config/scenarios/sustainability_review.json`. The new module `src/debt_sim/sustainability.py`
provides exact constant-policy arithmetic and a decomposition of the existing cohort ledger.
No baseline data were refreshed.

## Economic references checked

- [Blanchard (2019)](https://www.aeaweb.org/articles?id=10.1257/aer.109.4.1197): rollover
  under low safe interest rates can be feasible; fiscal cost and welfare cost differ.
- [Auclert (2019)](https://www.aeaweb.org/articles?id=10.1257/aer.20160137): net monetary
  transmission depends on heterogeneous earnings, inflation exposure, and interest exposure.
  This does not estimate the simulator's bondholder spending fractions.
- [BIS Annual Economic Report 2026, chapter II](https://www.bis.org/publications/aer-2026/high-public-debt-shifting-financial-markets):
  interest-income effects coexist with valuation losses and fiscal-risk repricing.
- [Bhatt et al. (2026)](https://www.federalreserve.gov/econres/feds/the-causal-effect-of-debt-on-interest-rates.htm):
  local expected-debt effects on neutral rates and term premia are not crisis thresholds.
- [Andolfatto (2021)](https://www.stlouisfed.org/publications/review/2021/05/26/is-it-time-for-some-unpleasant-monetarist-arithmetic):
  monetary and fiscal regime assumptions determine the consequences of missing fiscal support.
