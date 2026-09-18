# How I would write up and share this work

September 7, 2026

This is an editorial guide for presenting the work already completed. It is not a
proposal for another modeling project or a claim that we have identified the most
likely U.S. fiscal endgame.

## The recommendation

Use a short, accessible article as the public introduction. Make the restored
shock scenario the detailed worked example, and link its economic review
prominently alongside it.

The mechanism and crisis-to-recovery narrative are the most engaging parts of the
project. The review makes clear how much confidence to place in them. Both belong
in the public presentation.

The central contribution is:

> We made one proposed mechanism explicit enough to calculate—and explicit enough
> to criticize.

Do not frame the project as either “we solved the debt crisis” or “we tried and
failed.” We developed a concrete conditional scenario and learned which
conclusions survived scrutiny. That is the story to tell, without pretending it
answers every question that originally motivated the project.

## The reader's path

| Document | Role in the public presentation |
| --- | --- |
| [The Consequences of Continuing to Borrow](continuing_to_borrow.pdf) ([source](continuing_to_borrow.tex)) | Start here: an accessible article with three findings and a self-contained technical appendix. |
| [A 500-Basis-Point Treasury Stress](confidence_shock_household_scenario.pdf) ([source](confidence_shock_household_scenario.tex)) | Explore the mechanism: refinancing, interest income, inflation, financing stress, and a conditional recovery. |
| [Companion sustainability review](confidence_shock_review.pdf) ([source](confidence_shock_review.tex)) | Examine the objections: assumptions, sensitivity checks, and limits on interpretation. |

Share the qualified working scenario, not the
[untouched August 29 edition](confidence_shock_household_scenario_2026-08-29.pdf).
Keep that edition available as historical material. It should not be the default
download or be mistaken for the current assessment.

For a general audience, the short article should be the main link. For someone
specifically interested in the proposed mechanism, send the scenario and review
together. Readers should not need to navigate the repository or read our project
history to understand the argument.

## The opening I would use

Suggested title: **What Happens When Washington Keeps Borrowing?**

Suggested subtitle: *A Treasury stress test, a possible feedback loop, and what
survived a challenge to the assumptions.*

Draft opening, in the project's author's voice:

> “This won't end well” bothered me because it rarely came with an explanation.
> If the government keeps borrowing to cover its spending and the interest on
> its existing debt, what actually happens? Who experiences the consequences,
> and through what mechanism?
>
> We built a Treasury simulation to investigate one possible answer. An assumed
> rise in borrowing rates gradually increases federal interest payments as debt
> refinances. Some of that income can become spending. In the model, the resulting
> inflation pressure can prompt further rate increases, feeding back into the
> government's financing costs.
>
> We developed a concrete stress-and-recovery scenario, then challenged its
> assumptions. The fiscal burden kept growing in the cases we examined, but the
> inflationary ending proved much less robust. Here is the scenario, what it
> explains, and where the evidence stops.

The first-person motivation is useful because it explains why the question
matters. Keep the account of model development short. The article should be about
the economic question, not a chronology of our disagreements or document revisions.

## The structure of the public article

Aim for roughly 1,200–1,800 words before the technical appendix. The existing
short article can supply the body; this does not require a fourth research paper.

### 1. State the political premise

The government initially keeps financing scheduled commitments instead of
enacting a major preventive deficit-reduction package. Sustained economic pain
may eventually change what voters and politicians will accept.

That premise rules out an automatic preventive rescue. It does not prohibit
policy changes forever. Do not turn the article into a menu of tax increases or
benefit cuts, and do not turn it into a debate about MMT.

### 2. Establish the accounting without treating it as the ending

Explain the primary deficit, interest, and refinancing in plain language.
Replacing maturing principal is not itself an increase in debt; borrowing to
finance deficits and interest is.

A growing dollar debt stock does not necessarily mean a growing debt burden.
Growth and financing costs matter. Then show the no-shock reference path, where
debt nevertheless continues rising relative to GDP through 2056.

Use this to establish the pressure that needs explaining. Do not present a
rising line as evidence of a particular crisis or its date.

### 3. Explain the proposed mechanism before presenting the dramatic outcome

Walk the reader through refinancing, interest income, spending, inflation,
monetary tightening, and renewed financing costs. Explain that the model also
includes channels through which monetary tightening restrains demand.

State early that the stress adds five percentage points to Treasury issuance
rates for ten years. That shock is an input, not something the model predicts.
Distinguish the separate debt–yield feedback and assumed financing-capacity limit
from the basic interest-income loop.

Use a short excerpt or summary of the scenario's chronology to make the
consequences tangible. Label any fictional dateline or quotation where it appears,
including in screenshots or social posts. Do not rely on a disclaimer elsewhere
in the PDF to keep an isolated excerpt from being misunderstood.

### 4. Put the strongest challenge in the main text

Show the inflation-persistence sensitivity alongside the mechanism, not in a
footnote after the conclusion.

In the paired stress runs without added debt–yield feedback, changing quarterly
inflation persistence from 0.98 to 0.90 changes 2056 inflation from 8.04% to
2.89%, while debt exceeds 250% of GDP in both cases. Neither persistence
coefficient is estimated here.

This is evidence that the inflation result depends materially on a behavioral
assumption. It is not evidence that the lower-inflation outcome is more likely,
or that all possible endings are equally likely.

### 5. Explain what a recovery inherits

Bring the discussion back to concrete obligations. Falling market yields do not
rewrite fixed coupons on outstanding bonds. Expensive borrowing can leave both
more principal and elevated contractual payments.

The restored scenario's recovery illustrates that legacy. Keep its supplied
growth, inflation, and rate paths distinct from its calculated debt and financing
results. Do not claim that the modeled fiscal package has been shown to cause
the assumed recovery.

### 6. End with the findings and the unresolved judgment

The three findings are the conclusion:

- Fiscal pressure accumulates without an initiating panic in the reference path.
- More interest income does not mechanically establish an inflation spiral.
- A recovery inherits obligations accumulated during the stress.

Then state the unanswered question precisely: we have not established that this
mechanism is the most likely one to dominate U.S. fiscal developments.

Do not expand that admission into a claim that useful forecasting is impossible.
The borrowing premise alone does not select an ending, and this project did not
complete an evidence-based ranking of competing mechanisms.

## What to show and how to label it

Use the existing no-shock debt chart and the paired inflation paths. A simple
fixed-coupon example can explain the recovery legacy without another graph.
Readers who want the full sequence can follow the link to the scenario.

Keep the quantitative labels disciplined:

- Identify the fixed February 2026 CBO input vintage. Do not call it the latest
  outlook without checking and updating the analysis.
- Say when a number is an assumption, a computed conditional result, or a
  hypothetical narrative event.
- Identify inflation as annualized quarterly GDP-price inflation, not
  twelve-month consumer-price inflation.
- Preserve the debt/GDP denominator convention; end-quarter annual-rate GDP and
  fiscal-year mean GDP produce different ratios.
- Do not stitch the 8.04% inflation run, the debt–yield-feedback run, the
  finite-capacity stopping date, and the recovery into one uninterrupted forecast.
  They are distinct experiments.
- Describe the 2039 financing boundary as a result of the supplied capacity rule,
  not an estimated date when the United States runs out of buyers.

## What I would invite readers to challenge

Ask focused questions that could improve the assessment:

1. How should additional government interest income be weighed against private
   borrowing costs, saving, taxes, and bondholder valuation losses?
2. What evidence would justify the inflation persistence and monetary response
   used in the stress scenario?
3. What investor-demand model could replace the assumed gross-issuance ceiling?

Invite better mechanisms and evidence, not merely agreement that debt is
dangerous. A competing explanation can be more persuasive without establishing
its own exact crisis date.

## Before sharing

- Keep the restored scenario, companion review, and short article easy to find.
  Link to the review wherever the scenario is introduced.
- Include the relevant assumptions next to dramatic numbers and fictional events.
- Keep equations, inputs, and reproduction instructions available in the appendix
  or accompanying repository; link external factual claims to primary sources.
- Describe the simulator as a conditional stress tool, not a validated prediction
  engine. Reproducing its calculations is not the same as validating its economics.
- Preserve the untouched archive and the separate review when making future edits.

The public promise should be modest but substantive: **here is a concrete
proposed pathway, the calculations behind it, and the objections that matter.**
