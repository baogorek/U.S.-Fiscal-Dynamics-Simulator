# Crisis simulator roadmap

Document preservation update, September 7: the
[mechanism-led scenario](confidence_shock_household_scenario.pdf) has been restored,
the [economic review](confidence_shock_review.pdf) is a separate companion, and the
[self-contained article](continuing_to_borrow.pdf) remains available. The
[August 29 archive](confidence_shock_household_scenario_2026-08-29.pdf) preserves the
original. This recovery changes no models or research milestones; the roadmap below
records prior work and possible future research, not an instruction to replace the scenario.

## September 2026 change in research priority

The next economic milestone is **existence and stability of sustainable financing**,
followed by an explicit choice of monetary/fiscal continuation. The new
[mechanism note](fiscal_space_mechanism.pdf) develops an illustrative deficit–debt schedule
with stable and unstable fixed points. A permanent deficit can exceed the schedule's
maximum without any imposed auction or debt ceiling. The affine interest schedule is
still unestimated; its resulting ratios are not U.S. fiscal limits.

`scripts/run_fiscal_space_experiment.py` and `src/debt_sim/fiscal_space.py` implement
this annual diagnostic separately from the cohort engine. The milestones now are:

1. Estimate investor demand and long-run financing costs, including safe-asset services
   and beliefs about future policy. Identify intercepts and slopes together.
2. Connect those costs to investment/growth, the primary balance, and gradual repricing
   through the existing maturity ledger.
3. Check for bounded financing paths and solve alternative fiscal, monetary, and payment
   responses with investor expectations consistent with each branch.
4. Validate the mechanisms and uncertainty before assigning crisis probabilities.

Historical stress percentiles may motivate liquidity facilities, but cannot substitute
for a fiscal solvency test. A hand-set regime switch at a high debt ratio would simply
reintroduce the assumption the new diagnostic is intended to expose. The implementation
record below remains useful, but its completed boxes do not establish an endogenous or
empirically identified U.S. crisis mechanism.

## Objective

Extend the security-level Treasury accounting engine into a quarterly fiscal--monetary
stress simulator. The new layer should identify when the existing policy regime becomes
internally inconsistent, which authority reacts, and where the resulting real loss lands.
It should not infer a crisis from a particular debt/GDP threshold or treat a very large
nominal debt projection as the crisis itself.

The existing cohort ledger remains the accounting kernel. Behavioral rules sit around it
and remain replaceable, visible, and testable.

## Quarterly event order

1. Observe the inherited debt stock, inflation, output gap, market stress, and policy regime.
2. The Federal Reserve selects its policy-rate response and any market support or yield cap.
3. Treasury selects its issuance mix and any buyback operation.
4. The market clears the required issuance; the model records the shadow yield, actual yield,
   dealer absorption, and Federal Reserve purchases separately.
5. The cohort engine accrues interest, indexes TIPS, resets FRNs, refinances maturities, and
   finances the primary deficit.
6. Federal Reserve assets, reserve liabilities, reserve interest, earnings, remittances, and
   the consolidated public financing cost are updated.
7. Private credit conditions affect output, employment, tax receipts, and automatic
   stabilizers with explicit lags.
8. Stress indicators determine whether the next quarter stays in the same regime or changes.

Using the prior quarter's state for behavioral decisions avoids a hidden simultaneous-equation
solver. Any within-quarter market-clearing calculation will be separately documented.

## Work plan

### 1. Monetary and market-policy kernel

- [x] Represent a price-stability regime in which rates respond to inflation and output.
- [x] Represent market-functioning support that removes a liquidity premium without removing
  the inflation response.
- [x] Distinguish a sterilized yield cap, where reserve interest follows the shadow policy
  rate, from fiscal dominance, where both Treasury yields and reserve interest are suppressed.
- [x] Preserve shadow yields, actual issuance yields, yield suppression, and the implied
  Federal Reserve purchase requirement as separate outputs.
- [ ] Replace initial reduced-form purchase elasticity with tenor-specific demand estimates.

### 2. Consolidated Federal Reserve--Treasury accounting

- [x] Track Treasury holdings, reserve balances, interest on reserves, Federal Reserve net
  income, remittances, and deferred remittances.
- [x] Report consolidated financing cost without treating Federal Reserve purchases as debt
  cancellation.
- [ ] Add currency, reverse repos, agency securities, and operating expenses when they are
  material to a scenario.
- [ ] Pin historical H.4.1 starting values and portfolio yields in the data pipeline.

### 3. Adaptive Treasury debt management

- [x] Allow issuance shares to respond to a supplied long-yield-pressure path.
- [ ] Extend the issuance rule to auction stress and endogenous rollover exposure.
- [x] Implement liquidity-support and cash-management buybacks as gross transactions that do
  not erase the unified deficit.
- [x] Represent the announced minimum per-operation capacity and separate 10--20-year and
  20--30-year maturity buckets of the August 2026 long-end buyback expansion.
- [ ] Replace the run-rate equivalent with the exact September--November operation schedule
  when Treasury publishes it.
- [x] Report weighted maturity and the principal share due within four and eight quarters.

### 4. Treasury-market stress and market clearing

- [x] Add a reference-anchored finite private-absorption diagnostic that reports the yield
  required to place gross issuance and the first quarter a supplied capacity is exceeded.
- [x] Feed an aggregate clearing spread into issuance and stop at the first quarter when the
  supplied finite private capacity cannot place gross issuance.
- [ ] Replace an indefinitely imposed confidence premium with investor-demand curves by tenor.
- [ ] Track auction tails, bid-to-cover and dealer-takedown proxies, dealer inventory, Treasury
  volatility, repo funding, and collateral haircuts.
- [ ] Trigger market-functioning support from historical stress percentiles rather than an
  arbitrary debt threshold.
- [ ] Represent leveraged-position unwinds and finite dealer intermediation capacity.

### 5. Macro-fiscal feedback

- [x] Run debt, policy, output, and inflation in one sequential quarterly loop so stress
  interest can affect later policy decisions.
- [x] Feed the IORB operating-rate proxy, private spreads, and financial stress into the output
  gap and real growth with explicit lags.
- [x] Feed the output gap back into the primary deficit through a configurable aggregate
  automatic-stabilizer semi-elasticity.
- [x] Allocate incremental cash interest across domestic private, foreign, and Federal Reserve
  recipients and feed the spendable portion into later domestic demand.
- [x] Add an optional, reference-relative debt-yield feedback with lower, central, and upper
  mappings of a published empirical range.
- [ ] Add unemployment explicitly and separate receipts from automatic-stabilizer spending.
- [ ] Model inflation expectations, import-price effects, and central-bank credibility.
- [ ] Permit risk premiums to fall after a credible fiscal correction.
- [x] Keep every implemented behavioral elasticity configurable.
- [ ] Expose sensitivity ranges and historical estimates for each behavioral elasticity.

### 6. Household and institutional incidence

- [ ] Translate private mortgage and business-credit rates separately from capped Treasury rates.
- [ ] Track real wages, unemployment, fixed-income wealth, indexed benefits, taxes, and benefit
  reductions under explicit incidence rules.
- [ ] Add aggregate bank duration losses, capital pressure, and pension/insurer exposure.
- [ ] Report who absorbs the loss in each policy regime rather than assigning it implicitly.

### 7. Regime switching and experiments

- [ ] Implement threshold rules with hysteresis for price stability, market support, a
  sterilized cap, fiscal dominance, fiscal closure, and payment disruption.
- [ ] Run price-stability, Bessent-style maturity shift, sterilized rescue, fiscal-dominance,
  stop--go, and credible-fiscal-correction scenarios from the same starting state.
- [x] Add deterministic sensitivity sweeps across interest-income spending and Federal Reserve
  response coefficients without labeling the grid as probabilities.
- [ ] Add Monte Carlo scenario frequencies only after historical calibration; do not label
  uncalibrated frequencies as probabilities.

### 8. Validation and publication

- [ ] Back-test market plumbing against March 2020 and duration losses against the 2022--2023
  tightening episode.
- [ ] Validate policy and balance-sheet accounting against Federal Reserve releases.
- [ ] Define breakdown using observable market, financial, macroeconomic, and policy events.
- [x] Record first and first-sustained inflation-ceiling breaches without clipping inflation or
  imposing a terminal debt target.
- [ ] Update the model note and household paper only with results produced by pinned scripts.

## Initial acceptance tests

The first vertical slice is complete when it demonstrates all of the following:

- Above-target inflation raises shadow Treasury rates in the price-stability regime.
- A yield cap records the suppressed yield and the purchases required to maintain it.
- A sterilized cap pays the shadow policy rate on reserves; fiscal dominance does not.
- Federal Reserve purchases increase both Treasury holdings and reserve liabilities.
- Consolidated financing cost includes reserve interest and does not count interest paid from
  Treasury to the Federal Reserve as a cost paid to the private sector.
- The original forward engine and closure experiments continue to pass unchanged tests.

## First vertical-slice run

The initial comparison holds the previously solved 5.38-percent inflation path fixed and
changes only the policy regime. This is an engineering check of the reaction and accounting
layers, not yet a realistic macroeconomic forecast: higher policy rates do not feed back into
inflation or output, the model's GDP-price inflation is a provisional proxy for the Fed's PCE
measure, and the purchase elasticity is not calibrated.

| Regime | Average short rate | Terminal debt/GDP | Incremental Fed purchases | Consolidated financing cost |
|---|---:|---:|---:|---:|
| Price stability | 8.16% | 220.35% | none | \$106.58T |
| Market functioning | 8.09% | 219.01% | \$8.60T | \$105.54T |
| Sterilized yield cap | 3.12% | 172.09% | \$118.29T | \$103.06T |
| Fiscal dominance | 3.12% | 172.09% | \$118.29T | \$62.39T |

The comparison already exposes the missing tradeoff. Fighting inflation destroys the
low-rate debt closure. Capping Treasury rates while paying the shadow policy rate on reserves
preserves the Treasury debt path but restores much of the cost on the consolidated balance
sheet. Only the fiscal-dominance regime produces the intended negative-real-rate transfer.
The very large purchase requirement is a signal to calibrate market demand, not a finding to
publish as an estimate.

Reproduce the run with `uv run python scripts/run_policy_regime_experiment.py`. The generated
paths and summary are `data/processed/policy_regime_2036_paths.csv` and
`data/processed/policy_regime_2036_summary.csv`.

## Treasury debt-management slice

The Treasury experiment holds a ten-year, 500-basis-point confidence premium and the same
recession path fixed, then changes only debt management. The adaptive rule raises the bill
share of new borrowing from 22 percent to 42 percent. The long-end program represents four
operations in each of two maturity buckets at the announced minimum $4 billion face-value
capacity per operation. Applying that quarterly capacity for ten years is a counterfactual,
not announced policy.

| Debt-management path | Ten-year interest | Gross issuance | Terminal bill share | Share due within one year |
|---|---:|---:|---:|---:|
| Fixed issuance | $36.94T | $499.66T | 21.3% | 27.7% |
| Adaptive issuance | $36.41T | $633.56T | 32.7% | 38.6% |
| Adaptive + one-quarter long-end capacity | $36.42T | $634.34T | 32.7% | 38.6% |
| Adaptive + sustained long-end capacity | $36.50T | $648.41T | 33.9% | 39.7% |

The lower interest bill in the adaptive path is conditional on the imposed yield curve. It
comes with $134 trillion more gross issuance because short bills turn over repeatedly. The
sustained buyback path retires $1.216 trillion of face value for $676 billion at modeled
stressed market prices, but replaces the cash with bills and further shortens maturity. That
market-value exchange is not a primary-deficit reduction or an arbitrage finding.

Reproduce the run with `uv run python scripts/run_treasury_response_experiment.py`. Generated
outputs are `data/processed/treasury_response_2026_paths.csv` and
`data/processed/treasury_response_2026_summary.csv`.

## First macro-policy feedback slice

This run inherits the 5.38-percent inflation state but no longer imposes that inflation rate
for all forty quarters. IORB tightening affects output after two quarters; the output gap
affects inflation after another two-quarter lag; and an aggregate automatic stabilizer changes
the primary deficit. A separate 200-basis-point private-credit spread lasts eight quarters.

| Regime | Inflation after ten years | Inflation at or below 3% | Trough output gap | Added stabilizer deficits | Terminal debt/GDP |
|---|---:|---:|---:|---:|---:|
| Price stability | 1.99% | 12 quarters | -4.36% | $2.66T | 230.52% |
| Market functioning | 1.99% | 12 quarters | -4.36% | $2.66T | 229.12% |
| Sterilized yield cap | 1.99% | 12 quarters | -4.36% | $2.66T | 219.16% |
| Fiscal dominance | 3.12% | not reached | -1.25% | $0.72T | 195.74% |

This is closer to the real question than mechanically extrapolating debt. Price stability can
lower inflation, but doing so can create a recession, larger cyclical deficits, and higher
debt/GDP than the fixed-inflation engineering run. A sterilized cap preserves monetary
tightening through IORB even while suppressing Treasury yields. Fiscal dominance avoids most
of the contraction only by accepting higher inflation and a much larger central-bank role.

The coefficients are visible scenario assumptions, not estimates. The purchase-demand rule
also remains uncalibrated, so the very large Federal Reserve balance sheets are stress signals,
not forecasts. Reproduce the run with
`uv run python scripts/run_macro_policy_feedback_experiment.py`. Generated outputs are
`data/processed/macro_policy_feedback_2036_paths.csv` and
`data/processed/macro_policy_feedback_2036_summary.csv`.

## First sequential rate--interest--inflation slice

This experiment begins with the warmed 2026Q4 debt stock and never calls a closure solver. A
500-basis-point Treasury premium lasts forty quarters. Later Federal Reserve rates respond to
inflation generated inside the loop; the cohort ledger determines the resulting cash interest;
and a configurable portion of stress-created interest enters domestic demand after a lag. A
parallel no-shock ledger measures incremental interest in GDP-share terms, preventing a higher
scenario price level from being counted as additional real purchasing power.

| Scenario | Spendable share of incremental interest | First sustained inflation above 4% | 2056Q3 inflation | Peak policy rate | 2056Q3 debt/GDP |
|---|---:|---:|---:|---:|---:|
| No interest spending | 0.00% | none | 2.05% | 3.28% | 251.56% |
| Central spending + temporary private spread | 15.67% | 2037Q3 | 8.04% | 13.66% | 255.61% |
| High spending + temporary private spread | 31.34% | 2033Q4 | 40.93% | 78.21% | 235.59% |

The control run shows that the 500-basis-point premium by itself raises debt and interest but
does not generate inflation in this slice. The central and high-spending runs activate the
positive feedback proposed in the paper discussion: interest income supports demand, inflation
elicits higher policy rates, refinancing costs rise, and the next interest transfer becomes
larger. This is evidence that the code can represent the mechanism. It is not evidence that the
central coefficient is empirically correct. Treasury auctions still clear automatically,
inflation expectations remain reduced form, and the 99-percent issuance-rate boundary becomes
material in the most extreme run.

### Four-percent defense frontier

A second run varies the effective share of incremental cash interest entering domestic demand
and the Fed inflation-response coefficient. For each spending share, the table selects the
lowest peak policy rate among grid points that keep inflation at or below four percent. When the
grid contains no successful defense, it selects the lowest peak inflation instead.

| Interest entering demand | Selected inflation response | Four-percent ceiling defended | Peak inflation | Peak policy rate |
|---:|---:|:---:|---:|---:|
| 5.0% | 0.5 | yes | 3.42% | 4.04% |
| 8.0% | 1.0 | yes | 3.90% | 5.29% |
| 9.0% | 1.5 | yes | 3.99% | 6.40% |
| 9.5% | 3.0 | yes | 3.99% | 9.39% |
| 10.0% | 2.5 | no | 4.29% | 9.26% |
| 15.67% | 0.5 | no | 6.96% | 6.41% |

Within this uncalibrated grid, the finite-horizon ceiling boundary lies between 9.5 and 10
percent. The response is nonmonotonic near and above that boundary. More aggressive tightening
initially reduces inflation; after the fiscal-interest channel becomes large enough, further
tightening raises refinancing costs and produces a higher inflation path. Every selected path
with a positive interest-spending share ends with both inflation pressure and debt/GDP still
rising. No grid point therefore establishes a durable or convergent defense. The boundary only
describes whether inflation crosses four percent by 2056Q3 under the displayed coefficients.

### Finite private-absorption diagnostic

The reference-anchored diagnostic compares required gross issuance with private capacity at the
actual modeled yield. The central capacity rule expands absorption by five percent of reference
issuance per additional 100 basis points and caps it at 1.5 times reference issuance.

| Sequential scenario | First shortfall at actual yield | First breach of finite capacity | Peak required short-yield equivalent |
|---|---:|---:|---:|
| No interest spending | 2033Q4 | 2041Q4 | 13.60% |
| Central interest spending | 2036Q4 | none through 2056Q3 | 12.68% |
| High interest spending | 2056Q1 | 2056Q1 | 14.35% |

The diagnostic leaves the sequential path unchanged. Its required clearing yield has not yet
been fed into the next quarter, and the aggregate capacity rule has not been estimated or split
by tenor. It therefore identifies where a supplied market-capacity assumption binds without
claiming an auction-failure forecast.

### Debt-dependent yield feedback

The initial 500-basis-point premium can now be followed by a second, endogenous channel. Each
quarter's debt/GDP gap from the parallel no-shock path affects the next quarter's note, bond,
and TIPS issuance yields. The sensitivity range maps the Federal Reserve staff estimate of
1--2 basis points in the longer-run neutral rate plus 2--3 basis points in the ten-year term
premium for each percentage point of expected debt/GDP. The experiment uses a lagged realized
debt gap, so this is an explicit translation of the estimate rather than a direct application.

| Debt-yield sensitivity | 2056Q3 inflation | 2056Q3 debt/GDP | 2056Q3 long-yield addition |
|---|---:|---:|---:|
| None | 8.04% | 255.61% | 0 bp |
| Lower | 10.12% | 278.54% | 313 bp |
| Central | 11.26% | 290.47% | 464 bp |
| Upper | 12.59% | 303.80% | 645 bp |

The debt feedback magnifies the rate--interest--demand--inflation loop without introducing a
terminal debt target. It still does not calculate the yield required to clear an auction or
the nonlinear jump that a loss of market access could produce. Reproduce it with
`uv run python scripts/run_debt_yield_feedback_experiment.py`.

### Private financing-capacity boundary

The private-market-clearing experiment makes the aggregate capacity sensitivity operational.
Within each quarter, a common issuance spread rises until required gross issuance can be placed.
The run stops when issuance exceeds the supplied hard capacity multiple at every yield.

| Capacity sensitivity | Debt-yield feedback | First private financing failure | Conditional result |
|---|:---:|---:|---:|
| Tight: 1.25x maximum | no | 2034Q3 | $5.1 billion beyond capacity |
| Central: 1.50x maximum | no | 2040Q3 | $145.4 billion beyond capacity |
| Wide: 2.00x maximum | no | none through 2056Q3 | peak clearing spread 65 bp |
| Tight: 1.25x maximum | yes | 2034Q3 | $11.1 billion beyond capacity |
| Central: 1.50x maximum | yes | 2039Q3 | $37.4 billion beyond capacity |
| Wide: 2.00x maximum | yes | none through 2056Q3 | peak clearing spread 10 bp |

Debt-dependent yields partly substitute for the separate clearing spread because they already
raise note, bond, and TIPS rates. They also raise later interest costs and cause the central
hard capacity to be reached one year sooner. The boundary identifies when the supplied private
market can no longer finance the modeled path. It does not assert that Treasury then misses a
payment: Federal Reserve intervention, fiscal adjustment, forced absorption, inflationary
accommodation, and payment disruption are the next regime choices the model still needs.

Reproduce this run with `uv run python scripts/run_private_market_clearing_experiment.py`.

Reproduce the run with `uv run python scripts/run_sequential_crisis_experiment.py`. Generated
outputs are `data/processed/sequential_crisis_2026_paths.csv`,
`data/processed/sequential_crisis_2026_summary.csv`, and
`data/processed/sequential_crisis_2026_inflation_frontier.csv`. Reproduce the policy frontier
with `uv run python scripts/run_sequential_policy_frontier.py`.

## Empirical anchors

- The FOMC's longer-run inflation objective and policy framework:
  <https://www.federalreserve.gov/monetarypolicy/2026-07-mpr-statement.htm>
- Federal Reserve reserve-liability and interest-on-reserves mechanics:
  <https://www.federalreserve.gov/monetarypolicy/iorb-faqs.htm>
- Federal Reserve balance-sheet observations:
  <https://www.federalreserve.gov/releases/h41/current/>
- Treasury's August 2026 expansion of long-end liquidity-support buybacks:
  <https://home.treasury.gov/news/press-releases/sb0607>
- Dealer-capacity and leverage indicators:
  <https://www.federalreserve.gov/publications/2026-may-financial-stability-report-leverage.htm>
