---
name: business-performance
description: "Measure verified Shopify business results and establish how much of the campaign can be evaluated against them."
---

## Skill Name

Business Performance Analysis

## Purpose

Measure verified Shopify business results and establish how much of the campaign can be evaluated against them.

## Trigger

Run only when the lifecycle orchestrator selects `business-performance`.

## Required Inputs

Performance Analysis result and relevant earlier evidence. Read the selected run, product, strategy and campaign target as applicable.

## Required Files

`docs/policy.md`, the effective brand policy, and the orchestrator's referenced result records. For execution or handoff, also read `README.md`.

## Tools & APIs

Shopify reporting and authorized tracking evidence.

## Instructions

1. Read both Shopify windows in `review_evidence`. Align product, dates, time zone and spend. Count only retained, paid, qualifying product orders in the matched denominator according to the current collector. Report exact last-visit Meta UTM matches, unmatched orders, pending journeys and refunds separately.
2. Compute spend ÷ retained matched orders only for aligned windows with a positive denominator. Name it as a cost per observed matched order. Compare it with Meta CPA as a different measurement. Report how many relevant Shopify orders could be matched and what portion of the result remains uncertain. A low match count can reflect missing identifiers or incomplete customer journeys.
3. Keep product net sales, whole-order revenue and contribution separate. Use the selected metric in `product_cash` for attributable carts and the exact window's verified costs. For mixed carts use verified order-line allocations. If coverage or allocated costs are missing, leave product contribution unknown and state why. For a new-buyer goal, use `matched_first_time_buyers` from the verified Shopify customer order index and report unknown buyer history explicitly.

## Rules

No inferred Shopify sales or CPA from Meta attributed conversions alone. Apply the shared operating rules.

## Decision Logic

If Meta reports purchases but Shopify matches are sparse, check UTM values, lag and how the order journey is captured before concluding the campaign lost sales. [Shopify sales and payment definitions](https://help.shopify.com/en/manual/reports-and-analytics/shopify-reports/report-types/default-reports/sales-report)

## Output

Measure actual business results independently of Meta; save the findings as a step result with dated source references.

## Output Schema

The envelope uses `status`, `summary`, `evidence`, `data` and, for a blocked or limited result, `blockers`. Required `data` keys: `shopify_current`, `shopify_previous`, `tracking`, `attribution`, `limitations`. See the operator guide for types and special cases.

## Validation

Verify references, dates, scope and required fields. Reconcile contradictions. Check that conclusions follow from the evidence and list limitations before submission.

## Error Handling

Record the failed source or step and the next concrete action. Retry transient reads within provider limits. Do not retry an ambiguous write or change the approved target to bypass a failure.

## Approval

Read/analysis only; no approval or Meta mutation at this step.

## Execution Log

The orchestrator records run, step and UTC timestamp. Include source timestamps, precise decisions and blockers; store receipts via the executor.

## Next Step

Creative Analysis. Follow the CLI's returned route.
