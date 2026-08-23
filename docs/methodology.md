# Methodology

## Purpose and timing

The simulator is a deterministic quarterly cash-flow and debt-rollover model. Each row
is a calendar quarter ending on March 31, June 30, September 30, or December 31. Federal
fiscal year `FY y` comprises the December quarter of calendar year `y-1` and the March,
June, and September quarters of calendar year `y`.

CBO budget flows are federal-fiscal-year totals. The baseline allocates each annual flow
equally across its four fiscal quarters. CBO quarterly economic variables remain on their
reported calendar-quarter basis. No annual budget observation is silently interpreted as
a calendar-year value.

Dollar values in model output are billions of current dollars. Nominal GDP is a seasonally
adjusted annual rate; quarterly flows are not annualized. Ratios of quarterly flows to GDP
therefore multiply the quarterly flow by four.

## Nominal GDP

Let `g_t` and `pi_t` be annualized real GDP growth and GDP-price inflation. Their
quarterly equivalents are

```text
g_q,t  = (1 + g_t)^(1/4) - 1
pi_q,t = (1 + pi_t)^(1/4) - 1
```

and nominal GDP advances as

```text
NGDP_t = NGDP_(t-1) (1 + g_q,t) (1 + pi_q,t).
```

This multiplicative convention preserves the interaction between real growth and prices.
Inflation does not directly change real growth, the primary deficit, or issuance rates.
Those paths are separate scenario inputs.

## Fiscal accounting

Within a quarter:

```text
modeled total deficit_t
  = primary deficit_t + modeled debt interest cost_t

new borrowing requirement_t
  = modeled total deficit_t + other financing adjustment_t

debt held by public_t
  = debt held by public_(t-1) + new borrowing requirement_t.
```

Positive primary deficits, interest costs, and other-financing adjustments increase debt.
A sufficiently large primary surplus produces debt retirement. The implementation records
an explicit debt-identity residual on every row; it is not used as a balancing plug.

Maturing principal is different from new borrowing. It is refinanced one-for-one and
reported as both `principal_maturing` and `principal_refinanced`; it does not enter the
deficit or change total debt. Additional issuance finances the deficit and other financing.
`net_new_borrowing_requirement` can be negative in a surplus; `genuinely_new_borrowing`
is bounded at zero and the corresponding retirement is reported separately.

The model applies the period in this order:

1. index TIPS principal for the quarter's CPI inflation;
2. reset FRN rates to the current short issuance rate plus their spread;
3. accrue one quarter of interest on opening/indexed balances;
4. identify maturities and repay or refinance principal;
5. issue or retire debt for the modeled financing requirement;
6. calculate closing stocks and diagnostics.

## Security cohorts

Each cohort records instrument type, issue date, maturity date, public principal,
contractual rate, TIPS inflation index, FRN spread, and whether it was issued after the
scenario began. The initial ledger uses 458 Treasury CUSIPs outstanding on September 30,
2025.

### Bills

Bills are represented at principal value with an annual effective-yield approximation.
Quarterly financing cost is principal multiplied by one-fourth of that annual rate. This
abstracts from exact discount pricing and monthly accretion but preserves short duration
and rapid repricing.

### Fixed-rate notes and bonds

Coupon rates do not change before maturity. A market-rate shock affects only securities
issued after the shock. At maturity, the old cohort is removed and its principal is issued
into the scenario's issuance mix at current rates and tenors.

For starting notes, bonds, and TIPS, the fixed `effective_interest_rate` is the
issue-amount-weighted auction yield where Treasury reports it, otherwise the coupon. This
is a coarse approximation to coupon expense plus premium/discount amortization; coupon and
effective-rate fields remain distinct, but v0.1 does not carry a separate amortized-cost
balance.

### TIPS

TIPS have a real coupon and CPI-indexed principal. The quarterly index multiplier is

```text
index multiplier_t = 1 + quarterly CPI inflation_t.
```

The principal adjustment is recorded as `tips_inflation_compensation` and included in
`modeled_debt_interest_cost`, following federal budget treatment. It simultaneously raises
the TIPS liability, so the model does not issue the same amount a second time. Coupons are
paid on indexed principal using the real coupon. At maturity, modeled redemption cannot
fall below original par, approximating Treasury's deflation floor.

Actual Treasury index ratios use a daily interpolated, roughly three-month-lagged reference
CPI. v0.1 approximates this with a configurable one-quarter CPI lag, including for scenario
shocks. It does not model daily indexation, accrued auction inflation compensation, or tax
treatment.

### Floating Rate Notes

Treasury FRNs mature in two years and reset weekly to the most recent 13-week bill auction's
high discount rate plus a fixed spread. v0.1 resets once per quarter to the scenario's short
issuance rate plus the security's auction spread. This preserves prompt rate exposure while
matching the simulator's time step. The historical spread is joined from Treasury auction
data where available; new FRNs use the configured spread.

## Issuance

The baseline issuance mix is the September 30, 2025 public marketable composition:

| Type | Share of issuance |
| --- | ---: |
| Bills | 21.5411% |
| Notes | 51.8181% |
| Bonds | 17.2861% |
| TIPS | 7.0293% |
| FRNs | 2.3253% |

This is a transparent stock-share approximation, not a prediction of Treasury auction
policy. Default new-cohort tenors are 0.25, 7, 20, 10, and 2 years respectively. Quarterly
issuance rates are exogenous and may differ by instrument category. The same mix finances
rollovers and genuinely new borrowing unless the scenario supplies another mix.

The weighted new-issuance rate is computed from the actual issuance in the quarter. The
effective outstanding-debt rate is annualized modeled interest excluding TIPS principal
compensation divided by average interest-bearing principal for the quarter.
`share_marketable_debt_repriced_since_scenario_start` is the share of the current
marketable balance represented by post-start issuance or by FRNs that have reset since
the start; its denominator is not frozen at the opening debt stock.

## Marketable debt and debt held by the public

The detailed MSPD CUSIP file reports total outstanding amounts, not public ownership by
CUSIP. v0.1 scales each instrument class's CUSIP principals to the MSPD Table 1 amount held
by the public for that class. This preserves each class's maturity and coupon distribution.
The remaining difference between debt held by the public and modeled marketable securities
is `other_public_debt`.

At the starting date:

```text
debt held by the public       $30,277.766 billion
modeled marketable debt       $29,695.002 billion
other public debt                $582.764 billion
```

Other public debt has no modeled maturity schedule. Its interest is approximated with
CBO's projected average public-debt rate, kept in the assumption table as
`other_public_debt_interest_rate`. New borrowing and retirement occur through marketable
cohorts, leaving this remainder visible.

## Interest concepts

`modeled_debt_interest_cost` is the model's gross cost on its public Treasury cohorts:
bill discount-equivalent cost, fixed coupons, indexed TIPS coupons, TIPS principal
adjustments, and FRN interest. `cbo_net_interest_outlays` is retained separately. CBO net
interest includes interest paid on Treasury debt but offsets interest income and contains
other budget-accounting items. The validation reports the gap rather than forcing equality.

## Baseline and scenario comparison

The baseline uses CBO's February 2026 primary deficit, other-financing, real-growth,
inflation, three-month bill, and ten-year rate series. Where CBO publishes annual values,
the relevant fiscal or calendar convention is applied explicitly. The long issuance rate
uses the ten-year rate because the supplemental file does not contain a projected 20-year
rate. New TIPS use an explicit 1.75% real-rate assumption; new FRNs use the short rate plus
10 basis points.

Scenario comparisons run from the identical warmed starting stock. Difference tables use
`scenario - baseline`. Debt/GDP attribution uses an exact two-factor Shapley decomposition:
the debt contribution averages changing debt before and after changing GDP, and the GDP
contribution averages changing GDP before and after changing debt. The two contributions
sum exactly to the ratio difference; they are accounting attribution, not causal estimates.

## v0.2 inverse layer

v0.2 leaves the forward equations and cohort ledger intact. An inverse calculation changes
one bounded scenario parameter, calls the same `run_simulation` function, evaluates the
closure condition, and repeats. Scalar roots use SciPy's bounded Brent method. Inflation
solutions first scan a finite grid because strong rate pass-through can make the objective
nonmonotonic; Brent's method is then used on the first valid sign-changing interval.

Default bounds are 0% to 20% of GDP for a permanent primary-balance improvement, 0% to
1,000% for the additional cumulative price-level change, 0% to 100% for a mechanical
eligible-debt haircut, and 0 to 2,000 basis points for uniform new-yield suppression,
subject to the nominal-rate floor. Bounds are never expanded automatically. Failure returns
`No closure solution within specified bounds` plus boundary diagnostics.

### Closure targets

Let `d_0` be debt/GDP immediately before adjustment begins and `d_T` its value at the
selected endpoint.

1. **Stabilize at the starting ratio (default):** require `d_T <= d_0` and
   `d_T - d_(T-4) <= 0.001`. Thus debt/GDP may rise by no more than 0.1 percentage point
   over the final four-quarter span. The default horizon is 40 quarters.
2. **Specified endpoint ratio:** require `d_T` to be no higher than the user-supplied ratio.
   This target does not silently add the default final-year trend condition.
3. **Immediate flow stabilization:** solve the one-quarter primary-deficit share that keeps
   the next ratio approximately equal to `d_0`. It is labeled separately from multi-year
   closure.

A date start applies adjustment in that quarter after warming the ledger through the prior
quarter. A debt/GDP reference start finds the first baseline quarter-end at or above the
reference and begins adjustment in the following quarter. References are not crisis
thresholds. If one is not reached by 2056Q3, the model does not extrapolate to force a result.

### Fiscal closure

A permanent fiscal scalar `Delta PB` improves the primary balance in percentage points of
GDP. Each quarter it reduces the positive-primary-deficit input by

```text
quarterly deficit reduction_t = Delta PB * nominal GDP_t / 4.
```

Thus a 2.0% baseline primary deficit plus a 2.9-point improvement becomes approximately a
0.9% primary surplus. A linear phase-in can spread the adjustment over any positive number
of quarters. The model does not allocate the change between taxes and spending.

### Inflationary closure

The solver parameter is the **additional cumulative price-level change** relative to the
baseline price path. A constant extra quarterly multiplier is applied during a one-quarter,
one-year, or configurable multi-year episode; afterward baseline inflation resumes from the
permanently higher price level. Output includes both the additional cumulative change and
the total annualized inflation rate during the episode.

The altered inflation path advances nominal GDP in the core engine. The same extra quarterly
inflation reaches TIPS with the existing one-quarter reference-CPI lag. Nominal primary
deficits remain on their baseline dollar path by default; an optional GDP-share mode scales
them. New bill, intermediate, and long rates can respond through separate visible betas,
contemporaneously or after a chosen lag. TIPS real issuance rates are not treated as nominal
pass-through rates. Bills, FRNs, maturing fixed debt, TIPS principal, new borrowing, and
refinancing continue through the original ledger.

Inflation output uses a sequential, order-dependent accounting bridge: nominal-GDP
denominator, TIPS indexation, refinancing/rate response, and primary-deficit scaling. It is
not a structural causal decomposition. Gross principal refinanced can exceed opening debt
because bills may roll repeatedly; it is labeled gross rather than a unique survival share.

### Mechanical haircut equivalent

At the closure date, the selected fraction of eligible cohort principal is removed. Coupons
are rates applied to reduced principal, so future coupon costs and maturity refinancing fall
consistently. The default eligible set is marketable Treasury debt held by the public that is
represented by the model. Other public debt is excluded unless selected. A post-event yield
shock is optional and defaults to zero. This is a face-value equivalent, not a simulated
sovereign default or predicted loss.

### Financial-repression closure

The user supplies the inflation path. The solver subtracts one uniform number of basis points
from new nominal bill, intermediate, and long issuance rates for the selected duration, with
each rate constrained by the nominal floor. TIPS real rates are not suppressed by this
nominal-yield experiment. Output reports issuance-weighted new financing rates, average
inflation, an approximate ex-post real rate, and interest savings. A floor-bound failure is
reported as no solution.

### Mixed closure and rate stress

Mixed frontiers impose a grid for one mechanism and solve the other. Implemented pairs are
fiscal adjustment plus inflation, fiscal adjustment plus haircut, and fiscal adjustment plus
financial repression. No welfare ranking or probability is attached. The saved
fiscal/inflation research frontier uses target B—endpoint debt/GDP no higher than the starting
ratio—so the tradeoff is visible without claiming that a temporary price-level shift also
fixes the final-year structural flow.

The stress ladder adds 0, 100, 250, 500, 750, or 1,000 basis points to new-issuance rates,
runs the cohort engine, and then resolves the fiscal closure requirement. Shocks are
exogenous and carry no probability.

### Confidence-premium refinancing experiment

The pinned confidence experiment begins in 2045Q1 and imposes a 250, 500, or 1,000 basis
point premium on new Treasury issuance for 40 quarters. The premium applies to bills,
notes, bonds, and new TIPS real yields. Existing fixed-rate coupons do not change; FRNs reset
from the shocked bill rate through the ordinary cohort mechanics. The accompanying real-GDP
path is -2% annualized for four quarters, 0% for four quarters, and baseline growth
thereafter without level catch-up. Inflation, nominal primary deficits, and other financing
remain on baseline, and no default or extraordinary inflation is imposed.

For the delayed-action chart, the simulator evolves the debt stock along each stressed path
and resolves fiscal closure at the beginning of each year. Each point targets the debt ratio
inherited at that date and uses the fixed 2054Q4 endpoint plus the default final-four-quarter
stability condition. Consequently, the available closure horizon shrinks as action is
delayed. This is intentional and must be stated whenever the series is shown.
