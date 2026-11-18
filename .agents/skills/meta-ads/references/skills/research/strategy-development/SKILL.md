---
name: strategy-development
description: "Create one evidence-based advertising strategy at the start of a cycle. On a later cycle, use the previous result to decide what to carry forward and what to replace."
---

## Skill Name

Strategy Development

## Purpose

Create one evidence-based advertising strategy at the start of a cycle. On a later cycle, use the previous result to decide what to carry forward and what to replace.

## Trigger

Run only when the lifecycle orchestrator selects `strategy-development`.

## Required Inputs

For a first cycle, use the five research reports and approved run requirements. For a subsequent cycle, also use the prior strategy, latest mature business and delivery evidence, and reason for the new cycle.

## Required Files

`docs/policy.md`, the effective brand policy, and the orchestrator's referenced result records. For execution or handoff, also read `README.md`.

## Tools & APIs

Stored research artifacts and verified product/account evidence.

## Instructions

Use [first-campaign decisions](../../../../../../../docs/first-campaign-decisions.md) when history is sparse. Turn the buyer hypotheses into a chosen buying reason, message, audience decision, spend allocation and a justified first review. Save the rationale and the strongest alternative in the existing output fields.

1. Write down the business result and the decision the current cycle must make. For a first run, use approved product economics and current research to choose a feasible goal. For a later cycle, read `source_data.strategy_history` for the preceding strategy version, its main hypothesis, changes made, mature Meta delivery, matched Shopify results, tracking gaps and the outcome of the last test. Name the material change that opens a new cycle.
2. Build the diagnosis before choosing a tactic. Check whether the campaign had enough delivery to evaluate the promise. When delivery is comparable and traffic still does not reach the product page, check destination loading and tracking first. When people arrive but checkout starts are weak, use product-page and customer evidence to choose between a message mismatch, unclear value and other plausible causes. When checkout starts hold up but payments fall, check shipping, payment or stock evidence. A gap between attributed purchases and Shopify matches first needs a measurement check. Use rates only where the events, scope and denominator are comparable. If sparse evidence leaves several explanations open, state which cheap check would distinguish them.
3. Rank candidate strategies by customer evidence, ability to prove the promise, plausible unit economics and how much this budget can teach. Choose one buyer situation, one promise and one primary test. A buyer situation belongs in the message even when the account cannot separately target that group. If customers repeatedly ask how the bundle fits together and the verified assets can show it, test routine clarity. If the leading objection is affordability, compare a verified value message or offer against contribution after the discount. Use competitor and Ad Library patterns as ideas, with shopper evidence and verified claims deciding whether they fit.
4. Make the strategy measurable. Define what changes, what stays comparable, the primary metric, spend available, review window, reporting lag, minimum adequate evidence and stop conditions. Calculate first-order contribution from net product revenue and retained shipping less product, fulfillment, shipping and payment costs. Account for refund effects once. Size the review window and daily plan using the brand’s spending limits and any narrower limit in the request. Subtract the desired contribution after ad spend to estimate an affordable purchase cost. For the executable ceiling, use the amount supplied in `request.review_policy` or a matching `facts.economics.target_cpa_minor` with its verified source. If neither exists, record a null ceiling and the evidence needed. Preserve supplied review policy values. Return `criteria` with integer `window_days`, `lag_days`, `minimum_matched_orders` and `recheck_hours`, and nullable integer `maximum_cpa_minor`. Use the success metric in the request. For first-time buyers, count only retained matched orders with a verified first order index. Keep unknown buyer history explicit.
5. Record what each result means before Build. If the hypothesis meets the business target with adequate evidence, preserve it and send qualified results to Scale. If the signal is promising but underexposed, continue the same strategy within its limits. If the premise is contradicted, record what was learned and create a new strategy from the remaining credible opportunities. Keep the prior version and comparison dates. When `scheduled_strategy_refresh` is true, return `cycle_action: continue` if the update can monitor the existing campaign, or `cycle_action: recreate` if the revised hypothesis needs a replacement build.

## Rules

An approval-ready strategy is not permission to write to Meta. Apply the shared operating rules.

## Decision Logic

Example with hypothetical evidence: repeated shopper questions show the set is confusing, the store can fulfill it, and the page and approved assets can prove both products and the routine. With a small budget, choose one routine-led sales test, one verified offer, and a defined purchase-cost review. If the latest evidence instead shows an unresolved checkout fault, record the fault and verify it before spending to answer a creative question. If the test later produces stable orders within target, evaluate scaling the same strategy. If mature evidence shows the routine message fails and buyers consistently ask about value, write a new value-led strategy with its own economics and review criteria. [Meta Blueprint experiment design](https://www.facebookblueprint.com/student/path/219763-ab-test-conversion-brand-lift-course) · [Randomized Facebook field experiments](https://doi.org/10.1287/mksc.2018.1135) · [Shopify sales and payments definitions](https://help.shopify.com/en/manual/reports-and-analytics/shopify-reports/report-types/default-reports/sales-report)

## Output

Convert research into a dated, reviewable ad strategy; save the findings as a step result with dated source references.

## Output Schema

The envelope uses `status`, `summary`, `evidence`, `data` and, for a blocked or limited result, `blockers`. Required `data` keys: `objective`, `funnel_allocation`, `audience_hypotheses`, `creative_directions`, `test_priorities`, `decisions`, `next_review_on`. See the operator guide for types and special cases.

Registered data fields: `objective`, `funnel_allocation`, `audience_hypotheses`, `creative_directions`, `test_priorities`, `decisions`, `next_review_on`, `criteria`.

## Validation

Check that the chosen hypothesis follows from the evidence, can be represented by approved proof and can be tested within the budget. Verify the review date and required criteria fields. For a new cycle, verify the prior version and the evidence that warrants the change.

## Error Handling

Record the failed source or step and the next concrete action. Retry transient reads within provider limits. Do not retry an ambiguous write or change the approved target to bypass a failure.

## Approval

Read/analysis only; no approval or Meta mutation at this step.

## Execution Log

The orchestrator records run, step and UTC timestamp. Include source timestamps, precise decisions and blockers; store receipts via the executor.

## Next Step

Create from the new strategy, or finish a research-only run. Follow the CLI's returned route.
