# Findings from v0.1 and v0.2 experiments

These are reproducible conditional model results, not forecasts. Scenario JSON is under
`config/scenarios/`; quarterly output is in
`data/processed/named_scenarios_quarterly_2026-02.csv`; summary and stress-grid outputs are
in adjacent processed files. Differences below are scenario minus the same February 2026
CBO-like baseline.

## Common setup

All scenarios start from the Treasury stock on September 30, 2025 and run through 2036Q3.
The inflation shocks begin in 2027Q1. Unless noted, CBO real growth, an exogenous nominal
primary-deficit path, CBO other financing, and the baseline issuance mix remain unchanged.
Debt/GDP changes are percentage points; dollar changes are billions.

## Finding 1: inflation changes the denominator immediately, not nominal debt

With 10% annualized inflation for four quarters and no change in issuance rates:

| Point | Debt/GDP difference | Nominal debt difference | Nominal GDP difference |
| --- | ---: | ---: | ---: |
| 2027Q1 | -1.792 pp | $0.000 | $604.425 |
| 2027Q4 | -6.780 pp | +$135.446 | +$2,588.088 |
| 2036Q3 | -7.888 pp | +$255.952 | +$3,588.572 |

The first-quarter nominal-debt difference is zero because TIPS use a one-quarter CPI lag;
the entire initial ratio movement is the GDP denominator. At the shock's end, exact
Shapley accounting attributes -7.162 points to higher nominal GDP and +0.383 points to
higher nominal debt. No nominal debt is eliminated. By 2036 the scenario has *more* debt,
equal to its additional cumulative modeled interest, despite a lower debt ratio.

Caveat: unchanged rates during a 10% inflation shock are an artificial isolation exercise.
The model makes no claim that markets or the Federal Reserve would permit it.

## Finding 2: higher new rates arrive through rollover, not instant repricing

Adding a simultaneous 500-basis-point issuance-rate increase for the same four quarters
leaves debt/GDP 5.684 points below baseline in 2027Q4, versus 6.780 points without the rate
response. By 2036Q3 the improvement narrows to 2.304 points and nominal debt is
$3,101.213 billion above baseline.

The first quarter's extra modeled interest comes from FRNs ($9.309 billion); fixed notes
and bonds add zero because no affected cohort has yet refinanced. By 2027Q2, extra bill,
note, and bond costs are $87.530 billion, $12.365 billion, and $1.162 billion respectively.
By 2028Q4, after the temporary shock has ended, remaining extra note and bond costs are
$54.797 billion and $6.818 billion. Bills respond quickly and then normalize; fixed-rate
cohorts transmit the shock more slowly and persistently.

This timing reflects the imposed constant issuance mix and representative maturities, not
a prediction of Treasury debt-management choices.

In the baseline ledger, post-start issuance plus reset FRNs represent 37.8% of the current
marketable stock by 2026Q3, 51.0% by 2027Q3, 75.7% by 2030Q3, and 90.2% by 2036Q3. Those
shares include newly borrowed securities as well as refinanced inherited principal, so
they are exposure diagnostics rather than a pure survival curve for the opening stock.

## Finding 3: delaying the rate response preserves more of the early ratio decline

When the same 500-basis-point, four-quarter rate increase starts four quarters after
inflation, the 2027Q4 debt/GDP difference remains -6.780 points—the same early result as
the no-rate-response case. By 2036Q3 it is -2.889 points, with nominal debt
$2,802.937 billion above baseline. The delayed response reduces cumulative interest versus
an immediate response because it applies to a different, later issuance window.

## Finding 4: TIPS reduce the issuer's inflation benefit

In the 10% four-quarter, no-rate-response scenario, TIPS principal compensation raises
debt by $135.446 billion by 2027Q4. A counterfactual that reclassifies the starting TIPS
stock as conventional fixed-rate notes—with all else held as closely as possible—produces
a 7.123-point debt/GDP decline instead of 6.780 points. Thus TIPS reduce the measured
2027Q4 inflation benefit by 0.343 percentage point. By 2036Q3 the reduction is 0.456 point.

This is a model counterfactual, not an estimate of what borrowing costs or issuance policy
would have been without TIPS.

## Finding 5: temporary inflation benefits persist only under the imposed rate path

A 10% four-quarter inflation shock paired with a rate increase that remains in place
through 2036 eventually loses its debt/GDP advantage:

| Permanent issuance-rate increase | First quarter above baseline again | 2036Q3 debt/GDP difference |
| ---: | --- | ---: |
| +300 bp | 2031Q4 | +13.605 pp |
| +500 bp | 2030Q2 | +30.885 pp |
| +800 bp | 2029Q2 | +62.265 pp |

These are imposed stress tests, not an estimated inflation-to-rate relationship. They show
that the refinancing mechanism can erase the initial denominator effect under sufficiently
large and persistent financing-rate assumptions.

## Finding 6: unchanged-rate stress tests scale monotonically

For four-quarter inflation shocks with baseline rates left unchanged:

| Inflation | 2027Q4 debt/GDP difference | 2036Q3 difference | 2036Q3 nominal debt difference |
| ---: | ---: | ---: | ---: |
| 5% | -2.525 pp | -2.939 pp | +$86.779 |
| 10% | -6.780 pp | -7.888 pp | +$255.952 |
| 15% | -10.668 pp | -12.407 pp | +$425.045 |
| 20% | -14.234 pp | -16.550 pp | +$594.066 |

The growing nominal-debt increments are primarily TIPS compensation and related interest.
The much larger ratio changes come from nominal GDP. The model excludes the real-economy,
fiscal, market, and political responses that make such stress scenarios costly and
unlikely to follow these isolated paths.

The temporary 10% shock does not repair the unchanged structural primary-deficit path.
Debt/GDP in the no-rate-response scenario rises from 94.717% at 2027Q4 to 111.243% at
2036Q3; it merely remains below the corresponding baseline path of 101.497% and 119.131%.
The lasting gap is largely a persistent nominal-price-level effect, not ongoing deficit
improvement.

## Finding 7: a structurally unchanged primary deficit limits improvement

A 12-quarter 6% inflation scenario with baseline financing rates lowers debt/GDP by
10.424 points at 2029Q4 and 11.797 points at 2036Q3, while nominal debt is $400.781 billion
higher at the endpoint. This is labeled “persistent financial repression” only because the
imposed inflation path stays above financing rates; the model does not generate or predict
that regime.

Primary-deficit specification matters. Calibrating both manual modes to the same
2027Q1 annual deficit of $828.681 billion, the fixed-nominal mode ends 2036Q3 7.901 points
below its comparison baseline, while a fixed 2.5%-of-GDP deficit ends only 6.507 points
below and accumulates $1,108.093 billion more nominal debt. Indexing the primary deficit
to GDP allows inflation to enlarge nominal borrowing automatically.

## What was surprising

The cleanest result is not that inflation “removes” debt—it removes none—but that the
denominator effect can remain visible for years even after TIPS compensation raises debt.
Equally important, a merely temporary rate shock does not erase that improvement by 2036
in this setup, whereas permanent rate increases do so quickly. The persistence assumption
on rates matters at least as much as the initial shock magnitude.

Those observations remain conditional on an exogenous primary deficit, unchanged real
growth, a fixed issuance mix, and no behavioral response. They should not be generalized
beyond the saved configurations.

# v0.2 closure findings

These are conditional inverse solutions, not predictions. Source tables are generated by
`scripts/run_v02_experiments.py`. Unless a finding explicitly says “endpoint target,”
closure means debt/GDP is no higher than its starting ratio at the end of the horizon and
rises no more than 0.1 percentage point over the final four-quarter span.

## Finding 8: how much does fiscal delay change the permanent adjustment?

### Question

What permanent primary-balance improvement closes the default condition when action starts
at different future dates?

### Assumptions

The baseline is CBO's February 11 ten-year path plus the February 25 long-term extension.
The adjustment begins in Q1 of the listed year, is immediate and permanent, and is bounded
between 0% and 20% of GDP. The 2030–2045 cases use 10-year horizons. The data end in 2056Q3,
so 2050 has 27 quarters and 2055 has 7; those two are not directly comparable 10-year cases.

### Result

| Start | Starting debt/GDP | Horizon | Required primary-balance improvement | First-quarter baseline primary deficit | First-quarter adjusted primary balance |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2030Q1 | 105.38% | 10 years | 2.14% of GDP | 2.07% deficit | 0.07% surplus |
| 2035Q1 | 115.64% | 10 years | 2.40% | 1.70% deficit | 0.70% surplus |
| 2040Q1 | 126.63% | 10 years | 2.67% | 1.96% deficit | 0.71% surplus |
| 2045Q1 | 138.51% | 10 years | 2.92% | 2.03% deficit | 0.89% surplus |
| 2050Q1 | 152.01% | 27 quarters | 3.02% | 2.10% deficit | 0.91% surplus |
| 2055Q1 | 167.25% | 7 quarters | 3.14% | 2.21% deficit | 0.93% surplus |

### Mechanism

The fiscal change reduces new borrowing every quarter and then lowers interest costs on the
debt that is never issued. Starting later means a larger inherited stock is already passing
through the maturity ledger, so a larger flow correction is needed.

### Sensitivity

The exact result changes with the final-trend tolerance, horizon, issuance mix, post-2036
rate assumption, and whether adjustment phases in. The truncated 2050 and 2055 horizons
should not be read as points on the same curve as the 10-year cases.

### Interpretation

Within this baseline, waiting from 2030 to 2045 raises the 10-year permanent adjustment by
about 0.79 percentage point of GDP. The result is a required primary-balance change, not a
tax increase.

### What cannot be concluded

The simulator does not show which tax or spending package could deliver the adjustment,
what it would do to output, or whether it is politically feasible.

## Finding 9: do temporary 10%, 15%, and 20% inflation episodes repair the path?

### Question

How much of a one-year inflation episode's debt/GDP effect remains after refinancing has
had five and ten years to operate?

### Assumptions

Closure-state debt/GDP is 138.51% in 2045Q1. Inflation is held at the listed total
annualized rate for four quarters, then returns to baseline. Real growth and nominal primary
deficits remain on baseline paths. Rate regimes are no additional response, one-for-one
contemporaneous pass-through, and one-for-one pass-through delayed eight quarters. Betas
apply to new bill, intermediate, and long rates. Results below are scenario minus baseline.

### Result

| Inflation | Rate response | Episode-end debt/GDP | Five-year debt/GDP | Ten-year debt/GDP | Ten-year extra interest |
| ---: | --- | ---: | ---: | ---: | ---: |
| 10% | None | -9.50 pp | -10.04 pp | -11.11 pp | +$0.945T |
| 10% | 1-for-1 now | -7.35 pp | -3.74 pp | -2.24 pp | +$9.665T |
| 10% | 1-for-1, 8-quarter lag | -9.50 pp | -4.57 pp | -0.14 pp | +$11.730T |
| 15% | None | -14.81 pp | -15.65 pp | -17.32 pp | +$1.540T |
| 15% | 1-for-1 now | -11.43 pp | -5.34 pp | -2.67 pp | +$16.600T |
| 15% | 1-for-1, 8-quarter lag | -14.81 pp | -6.82 pp | +0.62 pp | +$19.984T |
| 20% | None | -19.69 pp | -20.79 pp | -23.01 pp | +$2.134T |
| 20% | 1-for-1 now | -15.13 pp | -6.43 pp | -2.42 pp | +$24.215T |
| 20% | 1-for-1, 8-quarter lag | -19.69 pp | -8.66 pp | +1.98 pp | +$28.934T |

Debt/GDP resumes rising in absolute terms almost immediately after the episode in every
case; the first detected increase is 2046Q2. During the episode, gross refinancing is about
$81.8T because bills can roll more than once, and roughly 32%–35% of the then-current
marketable stock has repriced or reset by episode end. TIPS add about $0.485T, $0.786T, and
$1.083T of inflation compensation in the 10%, 15%, and 20% cases without rate response.

### Mechanism

The price level changes nominal GDP immediately. TIPS principal and coupons rise with a
lag. Pass-through raises new bill costs promptly, resets FRNs, and reaches fixed notes and
bonds as cohorts mature. A delayed response preserves the initial ratio drop but applies
high rates to a later and, in these simulations, larger financing window.

### Sensitivity

The result is extremely sensitive to the beta, lag, duration, and whether rates remain high
after the episode. Here the delayed one-for-one response produces a worse ten-year result
than the contemporaneous response. That is not a general theorem; it is a cohort-timing
result for this issuance path.

### Interpretation

With rates artificially unchanged, the higher price level leaves a persistent denominator
gap. With one-for-one pass-through, refinancing removes most or all of the long-run ratio
benefit. A temporary episode still does not repair the structural primary-deficit flow.

### What cannot be concluded

These experiments do not estimate how the Federal Reserve or investors would respond, the
real-output cost, fiscal indexation, expectations, or the likelihood of any inflation path.
The rates shown are high inflation, not “hyperinflation” under the conventional 50%-per-
month Cagan definition.

## Finding 10: solving for inflation exposes the target definition

### Question

What inflation episode is required when fiscal policy is unchanged?

### Assumptions

The main comparison starts in 2045Q1, runs 10 years, and uses a five-year episode. For the
endpoint-only target, 2054Q4 debt/GDP must be no higher than the 138.51% start. The default
strict target adds the final-year trend condition. The additional cumulative price-level
bound is 1,000%.

### Result

With no additional rate response, the endpoint-only target requires a 23.06% additional
cumulative price-level change. Including baseline inflation, that is 6.33% annualized over
the five-year episode. The scenario incurs $2.918T more cumulative modeled interest than
baseline. Under one-for-one contemporaneous or eight-quarter-delayed pass-through, there is
no endpoint solution within the 1,000% cumulative bound.

The stricter default target has no 2045 solution even in the no-rate-response isolation
experiment. At the 1,000% bound, terminal debt/GDP is only 27.27%, but it still rises about
0.36 percentage point over the final four-quarter span—more than the permitted 0.1 point.

At reachable debt references, endpoint-only no-rate-response requirements are 22.02%
additional cumulative inflation at the 120% state, 23.18% at 140%, and 8.67% at 160%.
The 160% case has only 16 quarters of data, so its episode covers the whole remaining
horizon and is not comparable to the two 10-year cases. One-for-one pass-through has no
bounded solution at 120% or 140%, but does solve over that short 160% window.

### Mechanism

A stock revaluation can hit an endpoint without changing the final primary-deficit flow.
The final-trend condition distinguishes those two facts. Strong rate response can also make
the inflation objective nonmonotonic: more inflation raises the denominator but can add
still more interest through refinancing.

### Sensitivity

Changing the endpoint, trend tolerance, cumulative bound, beta, lag, deficit indexation, or
episode length materially changes the answer. The no-solution result is always stated with
its finite bound.

### Interpretation

“What inflation rate fixes the debt?” has no unique answer. A well-defined conditional
answer needs a price-level quantity, duration, target, rate response, and deficit treatment.

### What cannot be concluded

The result is not fiscal dominance, a forecast of inflation, or evidence that the price
level can jump without economic and institutional consequences.

## Finding 11: TIPS make inflationary closure larger

### Question

How much does inflation-indexed debt change the solved inflation requirement?

### Assumptions

The 2045 endpoint-only target and five-year no-rate-response episode are used. The
counterfactual reclassifies TIPS principal and future TIPS issuance as fixed nominal notes
while preserving the starting maturity and financing information as closely as possible.

### Result

The required additional cumulative price-level change is 23.06% with TIPS and 19.98%
without them. TIPS raise the requirement by 3.07 percentage points, or about 15% relative
to the no-TIPS requirement.

### Mechanism

TIPS principal rises with reference CPI and coupons apply to indexed principal, offsetting
part of the nominal-GDP denominator effect.

### Sensitivity

The difference depends on the inherited TIPS share, future issuance mix, CPI lag, real
coupons, horizon, and inflation path.

### Interpretation

Inflation cannot be applied to nominal and indexed Treasury liabilities as though they were
the same instrument.

### What cannot be concluded

The counterfactual does not estimate what historical or future nominal borrowing costs
would have been if Treasury had issued no TIPS.

## Finding 12: a haircut can hit an endpoint but does not close the flow

### Question

What mechanical face-value reduction achieves the 2045 endpoint target, and how does an
illustrative post-event yield shock change it?

### Assumptions

Eligible debt is the $88.298T of modeled marketable Treasury debt held by the public at the
2045Q1 closure state. Other public debt is excluded. The horizon is 10 years and fiscal
policy is unchanged.

### Result

With no post-event yield response, the endpoint target requires a 19.86% haircut, or
$17.535T of face value. A mechanically imposed +500 bp post-event issuance-rate shock raises
the solved haircut to 45.59% ($40.257T); +1,000 bp raises it to 64.55% ($56.999T).

Under the default target, no haircut works within 0%–100%. Even removing 100% of eligible
opening debt leaves a 22.54% terminal ratio that rises 2.31 percentage points over the final
four quarters because subsequent primary deficits issue new debt.

### Mechanism

The haircut reduces principal, associated coupon expense, and future refinancing. It does
not alter the primary deficit. A yield shock makes post-event borrowing more expensive and
therefore requires a larger initial reduction to hit the same endpoint.

### Sensitivity

Eligible-debt coverage and the post-event rate path dominate the result. The zero-response
case is an isolation calculation and materially understates likely real-world consequences.

### Interpretation

This is a **mechanical face-value haircut equivalent**, not a predicted default loss.

### What cannot be concluded

The simulator says nothing about financial institutions, collateral, liquidity, the dollar,
output, monetary policy, legal priority, or future market access after an actual default.

## Finding 13: financial repression works only while rate room remains

### Question

How far below baseline must new nominal Treasury yields be held to meet the default 2045
closure condition?

### Assumptions

Baseline inflation is retained. New bill, intermediate, and long rates receive one uniform
suppression for 10 years, with a zero nominal floor. TIPS real issuance rates are unchanged.

### Result

The solved suppression is 349 basis points. Gross-issuance-weighted new financing averages
0.106% nominal against 2.005% compound-average inflation, an approximate -1.862% ex-post
real rate. Cumulative modeled interest savings are $26.212T and terminal debt/GDP is 138.51%.
The 2050 and 2055 date cases return no solution within the zero-floor bound.

### Mechanism

Lower new rates reach bills and FRNs quickly and fixed debt as it matures, reducing interest
borrowing. Unlike a one-time stock revaluation, sustained suppression can change the final
flow—but only to the extent rates can fall before the floor binds.

### Sensitivity

Requirements are not monotonic by date (368 bp in 2030, 317 bp in 2040, and 349 bp in 2045)
because inherited coupons, baseline rates, maturities, and horizon interact. The institutional
arrangements needed to produce those rates are unmodeled.

### Interpretation

The mathematical result is a conditional low-financing-rate path, not evidence that such a
regime is implementable or costless.

### What cannot be concluded

The model does not establish how repression would affect saving, banks, capital allocation,
exchange rates, inflation expectations, or output.

## Finding 14: the rate-stress ladder steepens fiscal closure sharply

### Question

How does a persistent exogenous increase in new Treasury rates change the fiscal adjustment
required from 2045?

### Assumptions

Parallel shocks apply to new issuance for the 2045Q1–2054Q4 horizon. Fiscal closure uses the
default endpoint and trend condition. No probabilities are assigned. The 210% ratio is a
PWBM model-specific reference marker only.

### Result

| Issuance-rate shock | Terminal debt/GDP without fiscal closure | Extra cumulative interest | Required fiscal improvement | First 210% crossing |
| ---: | ---: | ---: | ---: | --- |
| 0 bp | 167.25% | $0.0T | 2.92% of GDP | Not crossed |
| +100 bp | 178.08% | $9.9T | 4.11% | Not crossed |
| +250 bp | 195.91% | $26.1T | 5.77% | Not crossed |
| +500 bp | 230.51% | $57.7T | 8.26% | 2053Q3 |
| +750 bp | 272.32% | $95.8T | 10.45% | 2051Q4 |
| +1,000 bp | 322.91% | $142.0T | 12.39% | 2050Q4 |

### Mechanism

The shock enters gradually through bills, FRNs, maturities, and new borrowing. Extra
interest creates additional debt that itself must be financed, producing a transparent
interest-cost feedback without an endogenous panic rule.

### Sensitivity

The largest shocks take the model far outside ordinary U.S. experience. Results depend on
holding the shock persistent, fixed issuance shares, no fiscal response until the inverse
solver is applied, and no real-output effect.

### Interpretation

Higher refinancing rates can make the required fiscal closure several times larger even
though inherited long debt does not reprice instantly.

### What cannot be concluded

The ladder does not estimate market probabilities or assert that investors will demand any
particular spread.

## Finding 15: a mixed frontier exists, but rate pass-through matters

### Question

Which fiscal/inflation combinations hit the same endpoint near a 150% debt reference?

### Assumptions

The baseline first passes 150% in 2049Q2; adjustment starts in 2049Q3 at 150.55% and runs
through 2056Q3. Target B requires endpoint debt/GDP no higher than 150.55% and does not add
the default trend condition. Inflation lasts five years with one-for-one contemporaneous
pass-through. Nominal primary deficits remain on baseline.

### Result

Selected frontier points are:

| Permanent primary improvement | Additional cumulative price-level change |
| ---: | ---: |
| 0.00% of GDP | 79.03% |
| 0.94% | 44.57% |
| 1.88% | 20.99% |
| 2.35% | 11.50% |
| 2.82% | 3.10% |
| 3.29% | 0.00% |

At the 120% reference, the same rate assumption has no solution within the price bound for
small fiscal changes; a 1.93% fiscal improvement pairs with 33.23% cumulative inflation, a
2.32% improvement with 2.17%, and about 2.71% needs no extra inflation.

### Mechanism

Fiscal adjustment reduces the flow and future interest compounding. Inflation changes the
price level but triggers higher new yields under the imposed beta. The two channels are not
linear substitutes.

### Sensitivity

The frontier changes radically under no rate response, a lag, a different horizon, or the
stricter default final-trend target. With the strict target, temporary inflation cannot
substitute for enough fiscal flow adjustment to flatten the final year.

### Interpretation

The frontier quantifies conditional combinations without ranking them. The 150% row is the
most informative saved mixed result because several interior combinations solve cleanly.

### What cannot be concluded

The curve is not an efficient policy frontier, does not assign probabilities, and does not
measure welfare or distributional costs.

## Reachable-state research table

Under the simulator baseline, the 120%, 140%, and 160% reference states are reached; 180%
and 200% are not reached by 2056Q3. The default-condition table is:

| Reference state | Actual start | Horizon | Fiscal adjustment | Five-year inflation, beta=1 | Haircut | Repression |
| ---: | --- | ---: | ---: | --- | --- | ---: |
| 120% | 2037Q2 at 120.31% | 40q | 2.47% GDP | No bounded solution | No solution | 344 bp |
| 140% | 2045Q4 at 140.38% | 40q | 2.93% | No bounded solution | No solution | 345 bp |
| 160% | 2052Q4 at 160.20% | 16q | 3.11% | 23.05% cumulative | No solution | No solution |
| 180% | Not reached | — | — | — | — | — |
| 200% | Not reached | — | — | — | — | — |

The inflation column uses one-for-one contemporaneous pass-through; the haircut covers
modeled marketable debt and assumes zero post-event rate response; repression uses baseline
inflation and a zero nominal floor. The short 160% horizon makes that row noncomparable to
the two 10-year rows.

## Most surprising and most assumption-sensitive results

The most important conceptual result is that a stock operation can hit a low endpoint and
still fail closure because debt/GDP is already rising again. Even a 100% eligible haircut
does not satisfy the default final-year condition with the primary deficit unchanged.

The most surprising timing result is that an eight-quarter-delayed one-for-one inflation
pass-through is worse after 10 years than contemporaneous pass-through in the 15% and 20%
experiments. The delayed shock lands on a different, larger refinancing window. This is
highly assumption-sensitive and should be investigated under alternative issuance mixes.

The large interest totals under +500 to +1,000 bp stress and high-inflation pass-through are
mathematical outputs far outside the model's validated range. They are useful stress
arithmetic, but their magnitude should be treated cautiously because real growth, fiscal
policy, issuance management, inflation expectations, and market functioning remain fixed.

## Central limitation

The single most important missing element is an endogenous joint model of fiscal policy,
monetary policy, investor beliefs, and real economic activity. Without it, v0.2 can state
what each closure mechanism must do conditionally, but it cannot determine which regime
would occur, when beliefs would change, or how output and rates would respond. That is why
these findings answer “what has to give in the accounting?” more firmly than “how will this
end?”

## Finding 16: a confidence-premium shock becomes acute through refinancing

### Question

Can the cohort engine construct a concrete “bad ending” in which nothing defaults and no
extraordinary inflation occurs, but Treasury loses cheap financing?

### Assumptions

The stress begins in 2045Q1 at 138.51% debt/GDP. Nominal primary deficits, inflation, and
other financing remain on baseline. New Treasury issuance carries a 250, 500, or 1,000
basis point premium through 2054Q4. Existing fixed-rate coupons remain unchanged. Real
growth is -2% annualized for the first four quarters, 0% for the next four, and baseline
thereafter without level catch-up. No default, haircut, extraordinary inflation, or policy
response occurs. This is an imposed confidence-premium stress, not an estimated market
reaction or forecast.

### Result

| Scenario | Immediate fiscal closure | 2054 effective rate | 2054 interest/GDP | 2054 total deficit/GDP | 2054 debt/GDP | Extra cumulative interest |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Unchanged baseline | 2.92% GDP | 3.84% | 6.70% | 8.93% | 167.25% | $0.0T |
| Recession only | 3.66% | 3.84% | 7.06% | 9.41% | 176.21% | $0.0T |
| +250 bp | 6.08% | 6.23% | 13.02% | 15.37% | 206.41% | $26.145T |
| +500 bp | 8.69% | 8.65% | 20.93% | 23.28% | 242.86% | $57.699T |
| +1,000 bp | 13.01% | 13.57% | 45.08% | 47.43% | 340.22% | $141.977T |

The +500 bp adjustment is equivalent to about $2.69 trillion when its GDP share is applied
to the simulator's pinned 2025-sized economy. This is a scale comparison, not a literal tax
bill. If fiscal action under +500 bp waits, the required permanent adjustment rises from
8.69% in 2045 to 9.72% in 2047, 10.85% in 2049, 12.12% in 2051, and 13.54% in 2053. Under
+1,000 bp, waiting until 2050 produces no solution within the 20%-of-GDP fiscal bound by the
fixed 2054Q4 endpoint.

### Mechanism

At the end of the first year, 33.2% of current marketable debt has been issued or reset
since the shock. The share rises to 43.9% after two years, 67.4% after four, 84.6% after six,
and 95.9% after ten. The +500 bp premium therefore moves the effective marketable rate from
about 3.81% before the shock to 5.48% after one year and 8.65% after ten. Higher interest is
borrowed, enlarging the stock that is subsequently financed at stressed rates.

### Sensitivity

The magnitude depends heavily on the full ten-year persistence of the spread, equal shocks
to all new maturities and TIPS real yields, the recession path, fixed issuance shares,
unchanged nominal primary deficits, and the absence of any monetary, fiscal, inflation, or
growth response. The largest ratios and interest burdens are well outside the model's
historically validated range.

### Interpretation

This experiment produces the requested gradual crisis arithmetic. The shock does not cause
an instantaneous repricing of inherited long bonds. It propagates through bills, FRNs,
maturities, and deficit borrowing, and the fiscal correction needed to arrest the path gets
larger when action is postponed.

### What cannot be concluded

The model does not establish why investors would demand 500 basis points, when that would
happen, whether the premium could remain exogenous for a decade, or which emergency policy
would follow. It identifies a coherent conditional route from a financing shock to an acute
fiscal problem; it does not endogenously locate “the moment confidence breaks.”

# Worked example: when cheap Treasury financing disappears

This is the most concrete “bad ending” v0.2 can currently construct. It does not begin with
a missed payment, an auction failure, or an extraordinary inflation assumption. It begins
with one imposed change: investors require substantially more compensation to hold newly
issued Treasury debt. The model then lets the existing maturity ledger determine how that
change reaches federal interest expense.

This scenario is closely related to the risk described by CBO in [*Federal Debt and the
Risk of a Fiscal Crisis*](https://www.cbo.gov/publication/21625): confidence could weaken,
Treasury borrowing rates could rise abruptly, and restoring confidence could then require
more painful tax or spending changes than earlier action would have required. CBO also
emphasizes that the precise U.S. crisis point is unknown. The experiment below therefore
does not claim that 2045 is a predicted crisis date or that 500 basis points is an estimated
market response. It asks what follows **if** those conditions are imposed.

## How the experiment enters the model

| Scenario element | Model treatment | Important interpretation |
| --- | --- | --- |
| Starting point | 2045Q1 opening stock: $88.880T and 138.51% debt/GDP | This is the baseline state inherited from the full pre-2045 cohort simulation. |
| Confidence premium | +500 bp on new bills, notes, bonds, and TIPS real yields through 2054Q4 | It is an exogenous stress input, not an estimated risk-premium equation. |
| Existing nominal notes and bonds | Their coupons remain unchanged until maturity | Their market prices would change in reality, but their promised coupons and model face values do not. |
| Bills and FRNs | Bills refinance at stressed rates; FRNs reset from the stressed bill rate | These are the fastest transmission channels. |
| TIPS | Baseline CPI indexation continues; new real yields receive the premium | The scenario does not inflate away indexed principal. |
| Other public debt | Retains its baseline coarse interest-rate assumption | The premium is not silently applied to debt without modeled issuance or maturities. |
| Real growth | -2% annualized for four quarters, 0% for four, then baseline | There is no later catch-up of the lost output level. |
| Primary deficits | Unchanged nominal baseline dollar path | There are no automatic stabilizers, emergency spending, or endogenous austerity. |
| Inflation and other financing | Unchanged baseline paths | There is no inflationary closure or monetary financing assumption. |
| Fiscal response | None in the stress path | A separate inverse calculation measures the adjustment that would close it. |

The construction uses the original debt engine. Each quarter it accrues coupons on inherited
cohorts, resets FRNs, indexes TIPS, matures the securities due that quarter, refinances that
principal at the stressed issuance rates, and issues additional debt to finance the primary
deficit and cash interest. No debt-service amount is inserted manually.

The recession affects real and nominal GDP but, by construction, does not alter nominal
primary deficits. That isolates the denominator effect. In an actual recession, falling tax
receipts and automatic stabilizers would ordinarily change the primary balance as well, so
this is not a full cyclical budget scenario.

## What the first ten years look like

The effective-rate measure below is the average effective rate on marketable debt excluding
TIPS inflation compensation. Modeled interest/GDP includes the model's marketable interest,
TIPS compensation, maturity-floor cost, and coarse interest on other public debt. Modeled
total deficit/GDP is the primary deficit plus that modeled interest measure; it is not CBO
net interest or the unified deficit including other financing.

| Date | Effective marketable rate | Interest/GDP | Total deficit/GDP | Debt/GDP | Current debt issued or reset since shock |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2044Q4 | 3.81% | 5.49% | 7.54% | 138.51% | — |
| 2045Q4 | 5.48% | 8.04% | 10.17% | 147.79% | 33.2% |
| 2046Q4 | 6.02% | 9.26% | 11.45% | 155.76% | 43.9% |
| 2048Q4 | 7.20% | 12.11% | 14.34% | 170.27% | 67.4% |
| 2050Q4 | 8.07% | 15.17% | 17.43% | 189.89% | 84.6% |
| 2052Q4 | 8.50% | 18.16% | 20.45% | 214.43% | 93.0% |
| 2054Q4 | 8.65% | 20.93% | 23.28% | 242.86% | 95.9% |

The first year is already consequential because bills roll rapidly, FRNs reset, maturing
principal is refinanced, and new deficit borrowing occurs at the stressed rates. But the
entire stock does not jump to a rate five percentage points higher. The effective rate rises
from 3.81% before the shock to 5.48% after one year, then continues climbing as more cohorts
turn over. That gradual movement is the contribution of the maturity model.

The feedback is visible after that. Higher interest creates additional borrowing. That new
borrowing is itself issued at the stressed rates. Interest therefore becomes an increasing
part of the next period's financing need even though the primary-deficit path has not
changed. By 2054, the model has accumulated $57.699T more interest than the unchanged
baseline over the ten-year stress window.

The result is nonlinear across the stress ladder:

| Imposed premium, with recession | Immediate fiscal adjustment | 2054 interest/GDP | 2054 debt/GDP | Extra ten-year interest |
| ---: | ---: | ---: | ---: | ---: |
| +250 bp | 6.08% GDP | 13.02% | 206.41% | $26.145T |
| +500 bp | 8.69% | 20.93% | 242.86% | $57.699T |
| +1,000 bp | 13.01% | 45.08% | 340.22% | $141.977T |

Those endpoint magnitudes are far outside the range over which the simulator has been
validated. They should be read as the result of forcing every other assumption to remain in
place, not as plausible forecasts of 2054. In reality, policy, growth, inflation, issuance
strategy, or the premium itself would almost certainly change before the largest endpoints
were reached. The experiment is useful precisely because it measures the pressure forcing
one of those assumptions to break.

## What “an 8.69% adjustment” means

If policymakers acted at the beginning of 2045 and the full stressed financing path were
known, a permanent primary-balance improvement of 8.69% of GDP would satisfy the default
closure condition by 2054Q4. The unchanged baseline requires 2.92%; the recession without a
rate premium requires 3.66%; and +500 bp without the recession requires 8.26%.

Applied to the simulator's pinned 2025-sized economy, 8.69% of GDP is approximately $2.69T
per year. That conversion communicates scale only. It is not a proposed tax increase, a
specific annual appropriation cut, or a claim that a package of that headline size would
raise the primary balance one-for-one after economic feedback. The solver does not choose
between taxes and spending, phase in legislation, or model behavioral and distributional
effects.

The timing matters as much as the initial number. If the +500 bp path is allowed to run
without fiscal response, then closure is solved again using the debt stock inherited at the
beginning of each listed year and the same fixed 2054Q4 endpoint:

| Fiscal action begins | Inherited debt/GDP | Remaining horizon | Required permanent improvement |
| --- | ---: | ---: | ---: |
| 2045Q1 | 138.51% | 40 quarters | 8.69% GDP |
| 2047Q1 | 155.76% | 32 quarters | 9.72% |
| 2049Q1 | 170.27% | 24 quarters | 10.85% |
| 2051Q1 | 189.89% | 16 quarters | 12.12% |
| 2053Q1 | 214.43% | 8 quarters | 13.54% |

These are deliberately shrinking-horizon calculations, not rolling ten-year comparisons.
They answer: “If the government waits while the refinancing shock proceeds, how large must
the permanent correction be to stabilize the newly inherited ratio by the original end
date?” Under +1,000 bp, waiting until 2050 leaves no solution inside the specified 20%-of-GDP
fiscal bound by 2054Q4.

## Real-world ramifications outside the simulator

The model captures Treasury cash-flow arithmetic but not the financial system around it.
A genuine 500-basis-point fiscal-risk repricing would have consequences well beyond the
federal interest bill.

### Borrowing costs would not stop at Treasury

Treasury securities form a benchmark yield curve for many private contracts. Treasury
officials describe Treasuries as widely used collateral ([U.S. Treasury, debt-management
principles](https://home.treasury.gov/news/press-releases/jy2460)) and have noted that lower
benchmark rates can reduce borrowing costs for corporations, agencies, and mortgages
([U.S. Treasury, market-structure remarks](https://home.treasury.gov/news/press-releases/sm565)).
A sustained fiscal-risk premium would therefore put upward pressure on mortgages, business
credit, auto loans, and state and local borrowing, although private spreads would not
mechanically move one-for-one with the Treasury premium.

Those higher private financing costs could weaken residential construction, business
investment, durable-goods demand, and hiring. None of those feedbacks is in the simulation.
The imposed two-year growth shock is only a compact placeholder, not an estimate of this
broader transmission.

### Existing securities would lose market value even before their coupons changed

The cohort engine correctly keeps an inherited fixed-rate bond's coupon unchanged, but it
does not mark that bond to market. In real portfolios, a large upward yield move would lower
the price of existing fixed-rate Treasuries. Banks, insurers, pension funds, mutual funds,
foreign reserve managers, leveraged funds, and households would experience different
economic and accounting effects depending on duration, hedging, leverage, liquidity needs,
and whether they could hold the security to maturity.

This channel can matter even without credit losses. The Federal Reserve's [2025 Financial
Stability Report](https://www.federalreserve.gov/publications/files/financial-stability-report-20250425.pdf)
notes that higher rates reduce the fair value of banks' fixed-rate assets and that those
values remain rate-sensitive. Forced selling or funding withdrawals could turn valuation
losses into liquidity or solvency pressure. v0.2 contains no asset prices, capital ratios,
margin calls, hedges, depositor behavior, or fire sales, so it probably understates the
speed at which financial stress could appear even while it correctly models the slower
federal cash-interest channel.

### Treasury-market liquidity and collateral could become part of the event

FSOC describes the Treasury market as critical for federal financing, monetary-policy
implementation, safe and liquid collateral, and benchmark security pricing ([FSOC 2025
Annual Report](https://home.treasury.gov/system/files/261/FSOC2025AnnualReport.pdf)). A loss
of confidence severe enough to add 500 basis points might therefore involve more than a
smooth shift in a yield curve. Bid-ask spreads could widen, market depth could fall, dealer
balance sheets could become constrained, repo terms could tighten, and price relationships
between cash Treasuries, futures, and other instruments could become unstable.

The March 2020 episode was not a U.S. fiscal-confidence crisis, so it is not an empirical
template for this scenario. It nevertheless demonstrates that Treasury-market dysfunction
can emerge even in a flight for liquidity and can require large official interventions. The
Federal Reserve documents strained dealer intermediation, wider spreads, impaired market
depth, expanded repo operations, dealer facilities, and large Treasury purchases undertaken
to restore market functioning ([Federal Reserve retrospective](https://www.federalreserve.gov/publications/2020-november-financial-stability-report-borrowing.htm)).
The simulator assumes every auction and refinancing transaction clears at the imposed rate;
it has no concept of impaired liquidity or failed intermediation.

### The Federal Reserve would face several distinct problems

A market-functioning intervention, a monetary-policy decision, and fiscal financing support
are not the same action, even if each can involve Treasury securities. In a real stress, the
Federal Reserve might need to address repo or dealer-market dysfunction while separately
judging inflation and employment conditions. Purchases or lending that restore trading need
not eliminate a persistent fiscal-risk premium. Conversely, suppressing financing rates for
a prolonged period would move the scenario toward the simulator's financial-repression
closure mechanism and could interact with inflation expectations.

v0.2 has no Federal Reserve balance sheet, policy rule, reserve-remuneration expense,
communications, lender-of-last-resort facilities, or distinction between temporary
market-functioning purchases and sustained yield suppression. The model therefore cannot
determine whether official intervention would stop, postpone, or transform the stress.

### The recession would probably worsen the primary balance

The experiment deliberately freezes nominal primary deficits. Actual recessions ordinarily
reduce tax receipts and increase some safety-net outlays, and discretionary fiscal measures
may add further borrowing. CBO notes that fiscal crises can coincide with downturns and make
adjustment more difficult ([CBO fiscal-crisis discussion](https://www.cbo.gov/publication/21625)).
Allowing those automatic and legislative responses would generally create more near-term
financing than this experiment contains.

The opposite feedback also matters. A rapid adjustment of 8.69% of GDP, whether through
higher taxes or lower spending, would itself affect output. CBO's fiscal-policy methodology
notes that tax increases and spending cuts generally reduce aggregate demand in the short
run, while their longer-run incentive and investment effects depend on composition
([CBO methodology](https://www.cbo.gov/publication/49494)). If consolidation lowered GDP
during the stress, the initial improvement in debt/GDP would be smaller than the accounting
solver reports. Later reductions in borrowing and risk premia could work in the other
direction. Neither feedback is modeled.

### Federal budget choices would become compressed and distributional

Interest is an obligation of the federal government, but higher interest expense does not
automatically specify which other budget item changes. Congress could raise taxes, reduce
benefits or other spending, accept still more borrowing, pursue inflationary or repressive
financing, or combine them. Every choice distributes losses differently across taxpayers,
beneficiaries, federal employees and contractors, savers, debt holders, generations, and
income groups.

CBO's [analysis of waiting to stabilize debt](https://www.cbo.gov/publication/58055) finds
that delayed adjustment requires larger policy changes and that tax- and benefit-based
closures have different effects on labor supply, capital, consumption, and generations.
The simulator's 8.69% number has none of that composition. Its legitimate meaning is that
the primary balance must improve by that share under the imposed macro path—not that any
particular package is feasible or equivalent in welfare terms.

At 20.93% of GDP, the model's 2054 interest measure accounts for about 90% of the 23.28%
modeled total deficit. That does not create a legal priority rule in the model, but it
illustrates the compression of political choice: continuing to borrow the interest produces
the explosive path, while paying more of it from current resources requires very large
changes elsewhere.

### International demand and the dollar are ambiguous, not one-way predictions

Foreign investors are important Treasury holders, and the dollar's international role
supports demand for dollar-denominated safe assets. GAO notes that liquidity, depth, safety,
and the dollar's reserve role have historically supported Treasury demand, while fiscal or
policy concerns could cause some investors to seek alternatives or require higher rates
([GAO federal debt-management review](https://files.gao.gov/reports/GAO-26-107529/index.html)).

The direction of a short-run dollar response is not mechanically determined. A flight to
liquidity could strengthen the dollar and increase Treasury demand; a shock centered on U.S.
fiscal credibility could weaken demand or raise inflation and depreciation concerns. The
simulation contains neither foreign portfolios nor exchange rates and therefore makes no
claim about which channel dominates.

## How the scenario could actually close

The no-response stress path is not a plausible final equilibrium. It is a diagnostic in
which the model refuses to let anything adjust except interest expense, refinancing, and the
small imposed growth path. In real life, at least one of the following would have to occur
before or during the extreme endpoints:

- A credible fiscal package improves the primary balance, potentially reducing the premium
  but also imposing short-run and distributional costs.
- Inflation reduces the real burden of nominal debt, while TIPS, higher nominal rates,
  fiscal indexation, and economic disruption offset part of the benefit.
- Monetary or regulatory intervention holds financing rates below the stressed market path,
  shifting costs toward savers, intermediaries, or the central-bank balance sheet.
- Treasury changes its maturity and instrument mix, altering the timing but not eliminating
  the underlying financing requirement.
- A restructuring or payment disruption changes face values or timing while creating
  consequences for collateral, institutions, market access, and future yields that v0.2
  cannot calculate.
- Several mechanisms operate together.

The simulator does not choose among them. Its conclusion is narrower and more durable:
once cheap financing is removed from a large and still-rising debt stock, gradual
refinancing can convert a long-run budget imbalance into a compressed policy timetable.
The “bad ending” is not necessarily a missed coupon. It is the point at which maintaining
all previous promises and policies requires adjustments so large that the assumption of
continued inaction is no longer credible.

## Reproducibility

Run:

```bash
uv run python scripts/run_confidence_shock_experiment.py
uv run streamlit run app/streamlit_app.py
```

The pinned scenario is `config/scenarios/confidence_shock_2045.json`. Machine-readable
outputs are:

- `data/processed/confidence_shock_paths_2045_2026-02-25.csv`;
- `data/processed/confidence_shock_summary_2045_2026-02-25.csv`;
- `data/processed/confidence_shock_delayed_fiscal_adjustment_2045_2026-02-25.csv`.

The Streamlit page **This Is What “It Won't End Well” Looks Like** presents the five linked
time-series panels, the three-premium comparison, the repricing path, and annual checkpoints.
