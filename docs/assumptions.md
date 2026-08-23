# Assumptions register

This register separates source observations from projections and model choices. No item
below is an estimated behavioral relationship.

## Observed/current data

- The starting debt stock is the September 30, 2025 Monthly Statement of the Public Debt.
- Security type, CUSIP, issue date, maturity date, outstanding face amount, and reported
  coupon/rate come from MSPD Table 3.
- Debt held by the public and public marketable subtotals come from MSPD Table 1.
- Historical FRN fixed spreads come from Treasury Securities Auctions Data.

The CUSIP file's total outstanding amounts are scaled by instrument class to public-held
totals. Thus, the exact public ownership of an individual CUSIP is not observed.

## CBO projections

- The benchmark is the February 2026 CBO baseline, not a later vintage.
- Baseline fiscal-year primary deficits are calculated as total deficit less net interest,
  after normalizing CBO's published signs.
- Baseline other-financing adjustments are the published difference between change in debt
  held by the public and the unified deficit.
- Nominal GDP, real GDP growth, GDP-price inflation, CPI inflation, 3-month Treasury bill
  rates, and 10-year Treasury rates use the official supplemental data.
- CBO debt held by the public and net interest remain comparison series, not forced targets.

CBO's baseline is a benchmark under its methodology and law assumptions, not a forecast
that v0.1 treats as certain.

## Accounting approximations

- Annual CBO budget flows are spread evenly across four federal-fiscal-year quarters.
- GDP is an annual rate; fiscal flow ratios annualize the quarter's flow by multiplying by
  four.
- Bill discount economics are represented by an effective annual yield on principal.
- TIPS index once per quarter with a one-quarter CPI lag rather than daily interpolation.
- TIPS principal compensation is a modeled interest cost and directly increases principal;
  it is not also financed as ordinary cash interest.
- FRNs reset quarterly rather than weekly.
- `other_public_debt` has a coarse interest charge using CBO's average public-debt rate
  but no modeled maturities.
- Interest is accrued for a full quarter before quarter-end maturity processing.
- Debt retirement reduces marketable cohorts proportionally; it does not choose securities
  through active debt management.

## Baseline scenario assumptions

- Issuance shares equal the starting public marketable stock shares, held constant.
- New tenors are bills 3 months, notes 7 years, bonds 20 years, TIPS 10 years, and FRNs 2
  years.
- The CBO 3-month rate prices bills and resets FRNs.
- The CBO 10-year rate prices both new notes and bonds; this is an explicit yield-curve
  simplification.
- New TIPS use a 1.75% real coupon. This is a visible assumption, not a CBO projection.
- New FRNs use the short rate plus a 0.10 percentage-point spread.
- Inflation and rates are independent inputs. There is no Fisher equation, Taylor rule,
  Treasury risk premium, or financial-repression mechanism.

## Experimental scenario assumptions

Named scenarios change only the variables stated in their JSON files under
`config/scenarios/`. Unless stated otherwise, real growth and the CBO primary deficit path
remain unchanged. “No rate response” and “financial repression” are deliberately artificial
channel-isolation experiments, not forecasts.

Manual primary deficits may be fixed nominal quarterly amounts or annualized percentages
of GDP. In the percentage mode, a larger nominal GDP mechanically creates a larger nominal
primary deficit. Taxes and spending do not separately respond to inflation.

## Endogenous results

Debt/GDP, debt issuance, cohort rollover, interest expense, effective rates, indexed TIPS
principal, and repricing shares are calculated by the model. They are not input targets.
The CBO validation gap is also a result and is never eliminated with a hidden residual.

## v0.2 closure assumptions

- The default closure horizon is 10 years and the default target is the starting debt/GDP
  ratio plus a final-four-quarter rise no greater than 0.1 percentage point.
- A fiscal adjustment is a primary-balance improvement. Positive values reduce the model's
  positive primary deficit; they are not labeled tax increases.
- Inflation closure is parameterized by an additional cumulative price-level change. The
  default research episode lasts five years.
- Inflation and issuance rates remain independent until a scenario explicitly supplies
  bill, intermediate, and long pass-through betas and a lag.
- The saved research tables use one-for-one contemporaneous pass-through unless the column
  states otherwise. The isolation experiment uses no additional rate response.
- Inflation leaves the nominal CBO primary-deficit dollar path unchanged by default. This is
  a scenario convention, not an empirical estimate of tax or program indexation.
- The default haircut set contains modeled marketable Treasury debt held by the public.
  Other public debt is not silently haircut. The default post-event yield shock is zero.
- Financial repression means a sustained reduction in new nominal issuance rates relative
  to the supplied inflation path. It does not model legal or institutional implementation.
- New nominal rates have a zero floor in the saved experiments. If the floor binds before
  closure, the solver returns no solution.
- A 210% debt/GDP marker, when displayed, is labeled as PWBM's model-specific outer-bound
  estimate. It is never a trigger or a law of economics in this simulator.
- Mathematical solutions are not labeled feasible, safe, likely, or desirable without an
  external basis. No probabilities or social-welfare weights are assigned.
