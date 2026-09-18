# Limitations

v0.2 is an accounting, refinancing, and inverse-closure simulator. It is not a
macroeconomic forecast and does not estimate the probability, trigger, or full consequences
of a fiscal crisis. A solver result identifies what balances the modeled arithmetic under
its assumptions; it does not show that the adjustment is economically or politically viable.

## Federal Reserve consolidation

The general forward engine includes debt held by Federal Reserve Banks in conventional
debt held by the public and does not consolidate the two institutions. The experimental
policy layer separately tracks Treasury holdings, reserve balances, reserve remuneration,
deferred remittances, and consolidated financing cost. That balance sheet remains
incremental and omits currency, reverse repos, agency securities, and operating expenses.
The first sequential crisis experiment does not yet feed reserve interest or Federal
Reserve balance-sheet changes into aggregate demand.

## Behavioral and macroeconomic omissions

- In the general forward and closure engines, taxes, program spending, primary deficits,
  inflation, and issuance rates remain supplied paths.
- Experimental feedback engines use visible reduced-form monetary, output, inflation, and
  automatic-stabilizer rules. Their coefficients are scenario assumptions rather than
  estimates.
- No investor behavior, panic, liquidity premium, or estimated investor-demand curve. The
  sequential slice can apply a lagged, reference-relative debt-yield sensitivity, but it is
  not a structural term-premium or default-risk model.
- No endogenous default, restructuring, auction failure, capital flight, or exchange-rate
  channel. The haircut tool only removes eligible face value mechanically.
- No general equilibrium, household/firm optimization, labor-supply response, or crowding
  out.
- No structurally estimated real-growth damage, recession probability, or expectations
  process. The sequential slice uses only reduced-form output and inflation persistence.
- No stochastic shocks or Monte Carlo uncertainty.
- No political probabilities, Congressional reaction function, or crisis threshold.
- The confidence-premium experiment imposes its spread; it does not model the investor
  beliefs, market dysfunction, collateral effects, or policy news that could produce it.
- The accompanying recession has no automatic stabilizers or feedback into nominal primary
  deficits, inflation, issuance strategy, or risk premia. Its main modeled effect is through
  the real-GDP denominator.

Scenario results are conditional arithmetic, not predictions or causal estimates.

## Sequential crisis slice

The [September 2026 review](sustainability_review.md) verifies two central identification
limits. First, reference-relative interest demand, debt yields, and absorption protect the
no-shock reference by construction; the engine cannot discover baseline loss of fiscal
credibility without a disturbance or a different economic closure. Second, changing
inflation persistence from 0.98 to 0.90 removes the four-percent breach under the same
Treasury stress and spending shares. Neither the inflation frontier nor the gross-issuance
ceiling is an empirically estimated U.S. sustainability boundary. The Treasury premium
also has no direct private-demand effect in the original run; a separate two-year private
spread does not identify its ten-year transmission.

The sequential experiment closes a limited rate--interest--demand--inflation loop without
imposing debt stabilization. Important omissions remain:

- Interest-recipient shares use an approximate June/FY2026 aggregate benchmark; domestic
  and foreign spending fractions remain scenario inputs. Holdings do not migrate as debt,
  yields, or Federal Reserve purchases change.
- Incremental cash interest enters demand through a reduced-form spending fraction and
  output multiplier. Household balance sheets, wealth effects, taxes, and portfolio
  substitution are absent.
- Inflation expectations enter only through persistence. There is no separately modeled
  credibility, wage-setting, import-price, exchange-rate, or fiscal-expectations channel.
- The Federal Reserve follows a reaction rule. The model does not yet calculate the minimum
  rate required to defend a specified inflation ceiling.
- Inflation ceilings are diagnostics. The path is allowed to cross them and no policy
  change is automatically triggered by a breach.
- Private credit stress is an imposed spread. Bank lending, mortgages, business credit,
  defaults, and financial losses do not generate it endogenously.
- The default sequential runs continue to clear Treasury financing at calculated issuance
  rates. A separate private-market-clearing experiment feeds the spread required by a supplied
  aggregate absorption curve into issuance and stops when its finite capacity is exceeded.
  Tenor-specific investor and dealer demand, estimated elasticities, auction tails, collateral
  stress, and payment disruption remain outside this slice.
- The optional debt-yield feedback translates a 2026 estimate for expected debt, longer-run
  neutral rates, and the ten-year term premium into maturity-specific issuance rates. The
  source does not identify this experiment's one-quarter lag, its mapping to notes and TIPS,
  or any nonlinear crisis response. The rule therefore remains a sensitivity calculation.
- Issuance rates are bounded at 99 percent because the cohort engine supports rates only up
  to 100 percent. A binding rate bound identifies the numerical boundary of the experiment.
- A path that accelerates through 2056 demonstrates instability under the selected
  coefficients. It does not establish the date or probability of a real-world crisis.
- A private financing-capacity failure is a regime-switch boundary. Federal Reserve purchases,
  fiscal adjustment, regulatory absorption, inflationary accommodation, or payment disruption
  could follow. The sequential experiment ends at that choice; the separate recovery run
  selects one conditional continuation.

## Conditional 2039 recovery

- The recovery inherits the final successful central-capacity Treasury stock, then supplies
  real growth, inflation, and marginal issuance-rate paths through 2056. Those paths are
  transparent conditions for the calculation rather than forecasts or outputs of the
  sequential feedback rule.
- The 5.48-percent-of-GDP primary-balance improvement is solved to meet a declared endpoint
  and final-year trend condition. The target therefore determines the reported fiscal size.
- The assumed fall in marginal Treasury rates represents credibility and temporary market
  support in reduced form. Investor expectations, Federal Reserve purchases, reserve
  creation, and the exit from that support remain outside the recovery ledger.
- Real growth receives the specified one-year contraction and subsequent recovery. The
  fiscal package has no separately estimated tax, spending, labor-supply, productivity, or
  distributional effect on that path.
- The invented legislative components illustrate how a broad package might be described.
  Only their aggregate primary-balance effect enters the simulator.
- Rate normalization without the fiscal package is a controlled accounting comparison under
  the same favorable macro assumptions. Market behavior following a failed congressional
  adjustment remains unestimated.

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
