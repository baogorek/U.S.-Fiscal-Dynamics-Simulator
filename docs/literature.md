# Literature and terminology checks

v0.2 is a transparent partial-equilibrium simulator. These sources discipline its language
and supply external comparisons; their equilibrium results are not imported as simulator
parameters.

## CBO baseline and fiscal risk

CBO's [*The Budget and Economic Outlook: 2026 to
2036*](https://www.cbo.gov/publication/62105), released February 11, supplies the ten-year
fiscal and quarterly economic baseline. [*The Long-Term Budget Outlook Data: 2026 to
2056*](https://www.cbo.gov/publication/62044), released February 25, supplies the distinct
annual extension. CBO describes a rising debt path and increased fiscal risk, not a known
date at which a crisis must occur.

CBO's [*Federal Debt and the Risk of a Fiscal
Crisis*](https://www.cbo.gov/publication/21625) is especially important for terminology: it
states that the exact point at which a U.S. fiscal crisis might occur is unknown and depends
on more than debt/GDP alone. The simulator therefore calls user values reference levels or
closure starts, never crisis thresholds, and assigns no crisis probability.

## PWBM external comparison

Penn Wharton Budget Model's [*When Does Federal Debt Reach Unsustainable Levels? Spring
2026—Onward*](https://budgetmodel.wharton.upenn.edu/p/2026-06-02-when-does-federal-debt-reach-unsustainable-levels/)
estimates an approximately 210% debt/GDP outer bound in its own stochastic general-
equilibrium model. Its reported dynamic closure comparison is roughly 15 percentage points
of broad labor-income taxation in its specified cases. Those results reflect PWBM's model,
tax base, behavior, capital flows, and healthcare scenarios. v0.2 may display 210% only as a
model-specific reference marker and does not transplant it as a trigger or calibrate its
primary-balance solver to the wage-tax result.

## Fiscal-limit research

Davig, Leeper, and Walker's [*Inflation and the Fiscal
Limit*](https://www.nber.org/papers/w16495) uses a rational-expectations model with beliefs
over the timing and composition of future policy adjustment. Inflation can revalue nominal
government liabilities in that model, but expectations and monetary/fiscal regime behavior
are essential to the equilibrium.

Leeper's [*Fiscal Limits and Monetary
Policy*](https://www.nber.org/papers/w18877) and Leeper and Walker's [*Fiscal Limits in
Advanced Economies*](https://www.nber.org/papers/w16819) emphasize that fiscal limits depend
on the capacity and willingness to adjust taxes and spending, and that unresolved fiscal
stress changes monetary-fiscal interactions. Ghosh, Kim, Mendoza, Ostry, and Qureshi's
[*Fiscal Fatigue, Fiscal Space and Debt Sustainability in Advanced
Economies*](https://www.nber.org/papers/w16782) models a fiscal reaction function, risk
premia, and an endogenous debt limit.

Those structures are deliberately absent here. v0.2 consequently uses **inflationary
closure**, not “fiscal dominance,” and reports a mechanical financing requirement rather
than a fiscal limit. It has no probability distribution over closure regimes, endogenous
risk premium, monetary reaction function, or political response.

## Hyperinflation terminology

The conventional Cagan definition begins a hyperinflation when monthly inflation exceeds
50%. The IMF review [*Modern Hyper- and High
Inflations*](https://www.imf.org/external/pubs/ft/wp/2002/wp02197.pdf) applies and discusses
that definition. Annual rates of 10%, 20%, or 50% do not meet it. The UI therefore uses
“high inflation,” “very high inflation,” or “inflationary closure” and does not label the
v0.2 experiments hyperinflation unless a generated monthly path actually crosses the
conventional threshold.

## Legitimate comparison

The literature supports three restrained conclusions used in v0.2:

- a debt path can require eventual adjustment without revealing a universal trigger date;
- several fiscal, monetary/inflation, and repudiation-equivalent mechanisms can close
  government budget arithmetic, but expectations and behavior determine their broader
  consequences;
- delayed adjustment can increase the required change, while the size and feasibility of
  that change remain model- and policy-specific.

It does not license interpreting v0.2's deterministic closure requirements as forecasts,
probabilities, welfare rankings, or estimates of the actual U.S. fiscal limit.

## Treasury-market and real-economy transmission

The confidence-premium worked example uses external sources only to interpret channels
outside the simulator. Treasury's [debt-management
principles](https://home.treasury.gov/news/press-releases/jy2460) and the [FSOC 2025 Annual
Report](https://home.treasury.gov/system/files/261/FSOC2025AnnualReport.pdf) describe the
Treasury market's roles in federal financing, benchmark pricing, collateral, and monetary
policy implementation. The Federal Reserve's [March 2020
retrospective](https://www.federalreserve.gov/publications/2020-november-financial-stability-report-borrowing.htm)
documents how dealer constraints and liquidity demand can impair Treasury-market functioning
and prompt official intervention; that event was not a fiscal-confidence crisis and is used
only as evidence about market plumbing.

The Federal Reserve's [2025 Financial Stability
Report](https://www.federalreserve.gov/publications/files/financial-stability-report-20250425.pdf)
supports the distinction between unchanged contractual coupons and falling market values of
fixed-rate assets when yields rise. CBO's [fiscal-policy
methodology](https://www.cbo.gov/publication/49494) and [analysis of delayed debt
stabilization](https://www.cbo.gov/publication/58055) support the cautions that rapid fiscal
adjustment affects demand and output, that policy composition matters, and that waiting can
increase the required change. GAO's [2026 debt-management
review](https://files.gao.gov/reports/GAO-26-107529/index.html) provides institutional context
on investor demand, Treasury borrowing costs, and the dollar's global role. None of these
effects is imported numerically into the v0.2 scenario.
