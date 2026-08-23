# Data sources and provenance

All external inputs are official machine-readable data. The pinned files run offline.
`scripts/refresh_data.py` writes immutable date-stamped raw snapshots, normalized files,
and a manifest containing URLs, query parameters, HTTP metadata, retrieval timestamps,
and SHA-256 hashes.

## Pinned vintage

| Institution | Dataset | Observation/vintage | Use |
| --- | --- | --- | --- |
| Congressional Budget Office | Ten-Year Budget Projections | February 2026 | Fiscal-year primary deficit, deficit, net interest, debt held by the public, other financing |
| Congressional Budget Office | Economic Projections | February 2026 | Quarterly nominal GDP, real GDP growth, GDP-price inflation, CPI inflation, 3-month bill rate, 10-year rate |
| Congressional Budget Office | Long-Term Budget Projections | February 25, 2026 | Fiscal-year primary deficit, net interest, debt, and GDP through 2056 |
| Congressional Budget Office | Long-Term Economic Projections | February 25, 2026 | Annual nominal/real GDP and price levels, inflation, growth, and average federal-debt rates through 2056 |
| U.S. Treasury, Fiscal Service | Monthly Statement of the Public Debt, Tables 1 and 3 | September 30, 2025 | Starting debt totals and marketable CUSIP cohorts |
| U.S. Treasury, Fiscal Service | Treasury Securities Auctions Data | Through September 30, 2025 | FRN auction spreads |

The source retrieval date is August 22, 2026. The exact pinned manifest is
`data/metadata/manifest_cbo-2026-02_treasury-2025-09-30.json`.

## Congressional Budget Office

The benchmark report is CBO's
[*The Budget and Economic Outlook: 2026 to 2036*](https://www.cbo.gov/publication/62105),
released February 11, 2026. Inputs come from CBO's
[official open-data repository](https://github.com/US-CBO/cbo-data) rather than chart
transcription:

- budget: `data/budget/ten_year_budget/annual_fy_2026-02.csv`;
- economy: `data/economic/economic_projections/quarterly_2026-02.csv`;
- the schema files alongside each dataset define variables and units.

The data-refresh script pins the full vintage-specific filenames. It does not request a
generic “latest” file.

Transformations:

- published deficit values use CBO's sign convention and are converted to positive
  borrowing requirements in model columns;
- percentages are converted to decimals;
- annual federal-budget flows are divided evenly among the four quarters of the
  corresponding fiscal year;
- quarterly economic observations retain calendar-quarter timing;
- rates remain annualized and are compounded to quarterly equivalents inside the model;
- CBO nominal GDP is a seasonally adjusted annual rate.

Processed ten-year outputs are `data/processed/cbo_baseline_fy_2026-02.csv` and
`data/processed/cbo_economy_quarterly_2026-02.csv`.

### Distinct long-term release

CBO released [*The Long-Term Budget Outlook Data: 2026 to
2056*](https://www.cbo.gov/publication/62044) on February 25, 2026. It is not silently
treated as the February 11 ten-year file. v0.2 pins these CBO open-data files:

- `data/budget/long_term_budget/annual_fy_2026-02.csv`;
- `data/economic/long_term_economic/levels_2026-02.csv`;
- `data/economic/long_term_economic/rates_2026-02.csv`.

The long-term workbook is annual. For each positive annual macro level after 2036,
the simulator solves for one constant within-year quarterly compound rate such that
the arithmetic mean of the resulting four quarterly SAAR levels equals CBO's annual
level exactly. This creates a smooth interpolation with no invented quarterly shocks.
It is applied separately to nominal GDP, real GDP, the GDP price index, and CPI-U.

The long-term file does not provide the maturity-specific 3-month and 10-year issuance
paths required by the cohort engine. The final February 11 quarterly rates are held
constant after 2036. It also does not publish CBO's other-means-of-financing series;
that flow is set to zero after FY2036. Both are visible assumptions, not fitted residuals.

The separate manifest is
`data/metadata/manifest_cbo-long-term-2026-02-25.json`. Normalized files are
`data/processed/cbo_long_term_budget_fy_2026-02-25.csv` and
`data/processed/cbo_long_term_economy_annual_2026-02-25.csv`.

## U.S. Treasury

The [Monthly Statement of the Public Debt](https://fiscaldata.treasury.gov/datasets/monthly-statement-public-debt/)
Table 1 supplies debt held by the public and public marketable amounts by instrument class.
Table 3 supplies CUSIP, issue date, maturity date, outstanding principal, and coupon/rate
for marketable securities. API filters pin `record_date=2025-09-30`.

Table 3 contains subtotal rows. Normalization retains only nine-character Treasury CUSIPs
beginning `912`, then maps Treasury descriptions to bills, notes, bonds, TIPS, and FRNs.
Because the CUSIP file reports total outstanding amounts rather than public ownership,
principals are scaled within each instrument class to Table 1's public-held totals. That
transformation is an accounting approximation and is recorded in the manifest.

[Treasury Securities Auctions Data](https://fiscaldata.treasury.gov/datasets/treasury-securities-auctions-data/)
are filtered to `floating_rate=Yes` and issue dates through the observation date. The fixed
auction spread is joined by CUSIP. Because the quarterly model resets every FRN before its
first simulated accrual, the starting effective rate is the first-quarter scenario short
rate plus that spread; an MSPD point-in-time FRN rate is not carried through the quarter.

Processed outputs are `data/processed/treasury_securities_2025-09-30.csv` and
`data/processed/initial_conditions_2025-09-30.csv`.

## Authoritative accounting references

- [TreasuryDirect's TIPS terms](https://www.treasurydirect.gov/marketable-securities/tips/)
  define CPI-U principal indexation, coupon payments on adjusted principal, and the maturity
  floor at original principal.
- [TreasuryDirect's FRN terms](https://www.treasurydirect.gov/marketable-securities/floating-rate-notes/)
  define the two-year maturity, quarterly interest payments, and weekly reset to the most
  recent 13-week bill high discount rate plus a fixed spread.
- CBO's [*Federal Net Interest Costs: A Primer*](https://www.cbo.gov/publication/56910)
  distinguishes net interest from gross Treasury security expense and explains budget
  recording for bills and TIPS.
- [*CBO Explains How It Develops the Budget Baseline*](https://www.cbo.gov/publication/59085)
  describes the agency's security-level debt-service model. The 2026 outlook separately
  explains why deficits and changes in debt can differ through other means of financing.

These references inform model conventions but are not silently converted into empirical
behavioral equations.

## CBO cross-checks reviewed but not imported

- CBO's [2026 debt-service tool](https://www.cbo.gov/publication/61912) was reviewed as a
  conceptual cross-check. Like v0.1, it leaves rates exogenous and distinguishes the
  incremental deficit before debt service from resulting interest and debt. Its effective
  marginal rate and CBO net-interest definitions are not used to calibrate the cohort model.
- [*How Changes in Economic Conditions Might Affect the Federal Budget: 2026 to
  2036*](https://www.cbo.gov/publication/62257) was reviewed but its rules of thumb are not
  applied. That analysis allows inflation and other economic variables to affect receipts,
  program outlays, and nominal interest rates. v0.1 deliberately leaves the primary deficit
  and issuance rates independent so users can isolate channels without importing a
  behavioral relationship.

## Not used as model inputs

Debt to the Penny is useful for aggregate cross-checks but is not the cohort source.
BEA, Federal Reserve, and FRED data are not needed for the pinned v0.1 baseline because
CBO supplies the economic series. No live API is called when the app or simulation starts.

The v0.1 validation remains deliberately restricted to the February 11 window through
FY2036. Appending the February 25 extension does not rewrite that regression benchmark.
