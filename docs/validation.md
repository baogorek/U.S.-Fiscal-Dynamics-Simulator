# Baseline validation

## September 2026 sustainability review

The separate review experiment reproduces the 2056Q3 no-shock ratio of 172.7745%.
Enabling the reference-relative debt-yield and central absorption rules without a shock
leaves that economic path unchanged. Across the nine new macro runs, the largest absolute
quarterly debt-identity residual is below `6e-11` billion dollars. The new debt-ratio
decomposition separately reconciles primary deficits, interest, other financing, and
nominal growth. Its final four-quarter baseline change is 3.1342 percentage points.

Tests cover a stable permanent primary deficit, linear debt growth when interest equals
growth, reconciliation of TIPS indexation and other financing, chronological input, and
the distinction between gross rollover and increases in debt. These are accounting and
implementation checks, not validation of the macro coefficients or crisis probabilities.
Full results and assumptions are linked in [the review](sustainability_review.md).

## Setup

The validation starts with Treasury's September 30, 2025 debt stock and runs quarterly
through FY2036 using CBO's February 2026 economic and budget paths. Annual simulator flows
sum the four fiscal quarters. Debt is the September-quarter closing value. The simulator's
annual debt/GDP denominator is the mean of the four quarterly nominal-GDP annual rates;
CBO's published percentage is retained as reported.

The complete machine-readable table is
`data/processed/baseline_validation_2026-02.csv`. Selected years are shown below; dollars
are billions and ratio differences are percentage points.

| FY | Metric | Simulator | CBO | Difference | Explanation |
| ---: | --- | ---: | ---: | ---: | --- |
| 2026 | Primary deficit | 813.727 | 813.727 | 0.000 | CBO path is an input |
| 2026 | Interest measure | 1,054.112 | 1,038.976 | 15.136 | Gross modeled cohort cost versus CBO net interest |
| 2026 | Total deficit | 1,867.839 | 1,852.703 | 15.136 | Inherits interest-definition gap |
| 2026 | Debt held by public | 32,215.665 | 32,095.165 | 120.500 | $105.364 initial-stock gap plus accumulated interest/timing differences |
| 2026 | Debt/GDP | 100.983% | 100.605% | 0.378 | Debt gap and annual denominator convention |
| 2031 | Primary deficit | 737.312 | 737.312 | 0.000 | CBO path is an input |
| 2031 | Interest measure | 1,566.959 | 1,548.383 | 18.576 | Gross modeled cohort cost versus CBO net interest |
| 2031 | Total deficit | 2,304.271 | 2,285.695 | 18.576 | Inherits interest-definition gap |
| 2031 | Debt held by public | 42,776.898 | 42,528.336 | 248.562 | Initial-stock and cumulative interest/timing gaps |
| 2031 | Debt/GDP | 110.213% | 109.573% | 0.640 | Debt gap and annual denominator convention |
| 2036 | Primary deficit | 971.051 | 971.051 | 0.000 | CBO path is an input |
| 2036 | Interest measure | 2,141.924 | 2,144.336 | -2.412 | Definitions differ; cohort model converges closely by this year |
| 2036 | Total deficit | 3,112.975 | 3,115.387 | -2.412 | Inherits interest-definition gap |
| 2036 | Debt held by public | 56,424.545 | 56,152.391 | 272.154 | Initial-stock and cumulative gaps |
| 2036 | Debt/GDP | 120.792% | 120.209% | 0.583 | Debt gap and annual denominator convention |

The initial Treasury stock is $30,277.766 billion; CBO's FY2025 debt value is
$30,172.402 billion. They differ by $105.364 billion because the source measures and
period conventions are not identical. v0.1 preserves the observed Treasury stock rather
than forcing it to the CBO series.

## Other financing

CBO's published other-means-of-financing series is supplied explicitly. It is
$70.060 billion in FY2026, -$36.998 billion in FY2031, and -$66.219 billion in FY2036.
It is not absorbed into the primary deficit or an unexplained residual.

## Accounting checks

Across the quarterly baseline, the largest absolute debt-identity residual is
`1.46e-11` billion, floating-point noise. Maturing principal is exactly separated from new
borrowing. Repricing is gradual: the share of the current marketable stock composed of
post-start issuance or reset FRNs is 37.8% by 2026Q3, 51.0% by 2027Q3, 75.7% by 2030Q3,
and 90.2% by 2036Q3.

## Interpretation

The comparison is close enough for v0.1's purpose without being curve-fit. The remaining
gap is informative. The model prices a simplified issuance mix and gross public Treasury
cohorts, while CBO projects net interest using richer security, cash, financing-account,
and timing detail. The model applies a coarse average interest rate to its explicit
nonmarketable public-debt remainder. No calibration constant forces these definitions to
overlap.

The final quarterly baseline ratio (2026Q3 to 2036Q3) is 119.131%, while the FY2036
validation ratio is 120.792%. The former divides September-quarter debt by September-quarter
GDP; the latter follows the stated fiscal-year average GDP convention. Both are labeled and
neither should be silently substituted for CBO's published 120.209%.

## Long-term extension check

v0.2 preserves the February 11 validation above and separately extends the forward inputs
with CBO's February 25 long-term release. The model converts annual 2037–2056 GDP levels to
quarters with a constant within-year compound growth rate chosen so that the four quarterly
SAAR levels average exactly to each published annual level. This adds no discretionary
quarterly volatility. CBO does not publish maturity-specific Treasury issuance rates in the
long-term workbook, so the final February 11 quarterly bill, intermediate, long, and TIPS
rate assumptions are held constant after 2036. Published other-means-of-financing inputs are
also unavailable after 2036 and are set to zero rather than inferred.

The extended simulator is not forced to CBO's debt levels, but it remains close in the
unshocked baseline:

| FY | Simulator debt/GDP | CBO debt/GDP | Difference |
| ---: | ---: | ---: | ---: |
| 2040 | 130.111% | 129.383% | 0.728 pp |
| 2045 | 142.308% | 141.784% | 0.524 pp |
| 2050 | 156.187% | 155.982% | 0.205 pp |
| 2056 | 175.057% | 175.076% | -0.019 pp |

FY2056 model debt is $167.467 trillion versus CBO's $167.530 trillion. The quarter-end
2056Q3 ratio is 172.775% because it divides the September stock by September-quarter GDP,
whereas the 175.057% annual validation ratio uses average FY2056 GDP. The maximum absolute
quarterly debt-identity residual through 2056Q3 is `2.91e-11` billion.
