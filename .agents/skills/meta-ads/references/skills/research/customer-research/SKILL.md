---
name: customer-research
description: "Find which situations, motivations and objections matter to shoppers and can be tested in advertising."
---

## Skill Name

Customer Research

## Purpose

Find which situations, motivations and objections matter to shoppers and can be tested in advertising.

## Trigger

Run only when the lifecycle orchestrator selects `customer-research`.

## Required Inputs

Product Research result and relevant earlier evidence. Read the selected run, product, strategy and campaign target as applicable.

## Required Files

`docs/policy.md`, the effective brand policy, and the orchestrator's referenced result records. For execution or handoff, also read `README.md`.

## Tools & APIs

Shopify order/report tools and owner-approved reviews or support summaries.

## Instructions

For a new or low-data account, read [first-campaign decisions](../../../../../../../docs/first-campaign-decisions.md). Use the product and relevant public customer research to propose labelled buyer situations, motivations and objections, and continue with a testable first strategy.

1. Review aggregate `recent_order_sample` for observed purchase behavior and `owner_feedback` or verified reviews for stated reasons. Record market, product, sample size, dates and whether the comments came before or after purchase. Shopify order patterns can describe what people bought. Use direct feedback for why they say they bought.
2. Group repeated questions by the shopper’s situation and the decision they are trying to make. Record the number of independent observations and contrary examples. Keep one-off comments as weak signals. A repeated objection among support inquiries may matter without representing all shoppers.
3. Translate each relevant finding into a falsifiable proposition. Example: shoppers ask whether the two products are used together, so a verified routine explanation may improve purchase response versus a bundle-only message. Describe what data would strengthen or overturn that proposition. Use only aggregate evidence.

## Rules

No customer names, contact details or raw orders. Apply the shared operating rules.

## Decision Logic

When comments are unavailable, report limited coverage and mark inferred motivations as hypotheses. Keep the new-versus-returning split unknown unless supported by customer history. [Shopify customer reports](https://help.shopify.com/en/manual/reports-and-analytics/shopify-reports/report-types/default-reports/customers-reports)

## Output

Identify audience needs from orders and feedback; save the findings as a step result with dated source references.

## Output Schema

The envelope uses `status`, `summary`, `evidence`, `data` and, for a blocked or limited result, `blockers`. Required `data` keys: `segments`, `motivations`, `objections`, `hypotheses`, `coverage`. See the operator guide for types and special cases.

## Validation

Verify references, dates, scope and required fields. Reconcile contradictions. Check that conclusions follow from the evidence and list limitations before submission.

## Error Handling

Record the failed source or step and the next concrete action. Retry transient reads within provider limits. Do not retry an ambiguous write or change the approved target to bypass a failure.

## Approval

Read/analysis only; no approval or Meta mutation at this step.

## Execution Log

The orchestrator records run, step and UTC timestamp. Include source timestamps, precise decisions and blockers; store receipts via the executor.

## Next Step

Competitor Research. Follow the CLI's returned route.
