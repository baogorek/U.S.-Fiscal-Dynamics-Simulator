# Limitations

v0.2 is an accounting, refinancing, and inverse-closure simulator. It is not a
macroeconomic forecast and does not estimate the probability, trigger, or full consequences
of a fiscal crisis. A solver result identifies what balances the modeled arithmetic under
its assumptions; it does not show that the adjustment is economically or politically viable.

## Federal Reserve consolidation

Debt held by Federal Reserve Banks is included in conventional debt held by the public,
but v0.1 does not consolidate Treasury and Federal Reserve balance sheets. It does not
model reserve remuneration, the Fed portfolio, deferred assets, remittances, or monetary
policy. Consequently, modeled Treasury interest is not a measure of consolidated public-
sector financing cost, and the model makes no claim about fiscal dominance. A future Fed
module can be added without changing the cohort ledger, but it is outside v0.1.

## Behavioral and macroeconomic omissions

- No endogenous fiscal response: taxes, program spending, and primary deficits do not
  respond unless the user changes their path.
- No endogenous monetary response: inflation and issuance rates are independent inputs.
- No investor behavior, panic, liquidity premium, term-premium model, or endogenous
  Treasury risk premium.
- No endogenous default, restructuring, auction failure, capital flight, or exchange-rate
  channel. The haircut tool only removes eligible face value mechanically.
- No general equilibrium, household/firm optimization, labor-supply response, or crowding
  out.
- No endogenous real-growth damage, recession probability, or inflation persistence.
- No stochastic shocks or Monte Carlo uncertainty.
- No political probabilities, Congressional reaction function, or crisis threshold.
- The confidence-premium experiment imposes its spread; it does not model the investor
  beliefs, market dysfunction, collateral effects, or policy news that could produce it.
- The accompanying recession has no automatic stabilizers or feedback into nominal primary
  deficits, inflation, issuance strategy, or risk premia. Its main modeled effect is through
  the real-GDP denominator.

Scenario results are conditional arithmetic, not predictions or causal estimates.

## Closure-specific omissions

- Inflationary closure is not a fiscal-dominance or fiscal-theory-of-the-price-level model.
  There are no expectations, money demand, monetary/fiscal regime switches, or equilibrium
  price-level selection.
- Rate pass-through betas are scenario inputs. The model does not estimate a Fisher relation,
  Taylor rule, term premium, or investor response.
- A mechanical haircut omits banks, money-market funds, collateral chains, Treasury-market
  liquidity, the dollar, Federal Reserve facilities, output losses, and future market access.
  Even an illustrative post-event yield shock is not a default model.
- Financial repression suppresses new modeled nominal yields but does not represent the
  capital controls, regulations, balance-sheet mandates, central-bank operations, or tax
  rules that might sustain those yields.
- The fiscal solver does not distinguish receipts from spending and contains no behavioral
  response to either.
- Mixed frontiers are accounting tradeoffs, not efficient frontiers. There is no welfare
  function, distributional analysis, desirability ordering, or probability.
- A temporary level shift can satisfy an endpoint target while debt/GDP is already rising
  again. The default closure target adds a final-year trend check precisely to expose that
  difference, but it is still only a finite-horizon condition.

## Debt and interest coverage

- Detailed cohorts cover public marketable securities after class-level reconciliation,
  not gross federal debt.
- `other_public_debt` is explicit and receives a coarse interest estimate using CBO's
  average public-debt rate, but has no modeled maturities or issuance.
- Public ownership is unavailable by CUSIP in MSPD Table 3, so v0.1 scales principals by
  instrument class. This assumes the public maturity/coupon distribution within a class
  matches the total outstanding distribution.
- The issuance mix is held fixed at starting stock shares. Treasury could change tenors,
  instrument shares, buybacks, or cash-management issuance.
- New cohorts use representative tenors rather than a full auction calendar.
- A primary surplus retires cohorts proportionally rather than through a specified debt-
  management rule.
- `modeled_debt_interest_cost` is not CBO net interest. Net interest offsets receipts and
  contains institutional and budget-accounting elements not reconstructed here.

## Instrument approximations

- Bills use an effective-yield accrual rather than exact discount cash-flow accounting.
- TIPS index quarterly with a one-quarter CPI lag, not the official daily interpolated
  reference-CPI mechanics. The deflation floor is applied at maturity, not priced as an
  embedded option.
- FRNs reset quarterly to a scenario short rate, not weekly to actual 13-week bill auction
  high discount rates.
- Coupon/interest timing is quarterly and does not reproduce exact security payment dates
  or accrued interest.
- Starting fixed-rate effective cost uses auction yield on scaled face principal and does
  not separately model issue premium/discount or amortized carrying value.
- Newly issued notes and long bonds share CBO's projected 10-year rate; the yield curve is
  therefore intentionally sparse.

## Baseline timing and data

- Fiscal-year flows are allocated evenly to quarters, while CBO economic data are calendar
  quarter. Actual receipts and outlays are seasonal.
- Quarterly nominal GDP is an annual rate, requiring a documented convention for fiscal-
  year ratios.
- The starting Treasury observation and CBO FY2025 endpoint do not exactly match.
- CBO supplemental data can be revised in a later vintage. The simulator deliberately pins
  the February 11 and February 25, 2026 releases, so a refresh is a conscious research decision.
- “Other means of financing” is taken from CBO in baseline mode but is not decomposed into
  Treasury cash-balance changes, credit-program flows, or other components.
- After 2036, CBO annual long-term levels are interpolated with constant within-year growth.
  The long-term release does not provide maturity-specific issuance rates or other means of
  financing, so final ten-year rates are held flat and other financing is set to zero.
- The data end in 2056Q3 for a complete FY2056 simulation. A 2050 or 2055 closure start
  therefore cannot receive the default 10-year horizon without inventing post-2056 inputs.

## Interpretation risk

Inflation can lower debt/GDP while nominal debt rises. That ratio change is not debt
elimination, an increase in fiscal capacity, or evidence that inflation is costless.
Distributional effects, credibility, welfare, tax-system interactions, indexed programs,
and broader economic damage are not modeled. Results must be described with the exact
inflation, rate, growth, and primary-deficit assumptions that generated them.
