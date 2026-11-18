---
name: product-research
description: "Establish what this exact product can sell, what the shopper will receive, and what an ad can truthfully claim."
---

## Skill Name

Product Research

## Purpose

Establish what this exact product can sell, what the shopper will receive, and what an ad can truthfully claim.

## Trigger

Run only when the lifecycle orchestrator selects `product-research`.

## Required Inputs

Run request and current verified context. Read the selected run, product, strategy and campaign target as applicable.

## Required Files

`.agents/skills/meta-ads/references/policy.md`, the effective brand policy, and the orchestrator's referenced result records. For execution or handoff, also read `README.md`.

## Tools & APIs

Shopify read connector, approved brand documents, and product page.

## Instructions

Read [the practical decision guide](references/decision-guide.md) before preparing this step.

1. Read `live_product` and `destination_read`. Match Shopify product and variant IDs to the request, then verify the customer-facing URL from `destination_read.url`, contents, sizes, price and availability for the advertised market. Record when and where each was checked. A compare-at price is price context. Confirm the actual terms before presenting a discount.
2. Read the exact product's current storefront and approved packaging. Record ordinary benefits in the same qualified language. Use additional evidence when a concept introduces a stronger or measurable result beyond the source wording.
3. Check stock tracking and inventory policy. With tracking off, zero quantity leaves availability unknown. Use verified fulfillment evidence to support an availability statement. Record missing costs, shipping or checkout evidence with the decision each gap affects.

## Rules

No claim transfers from a different product. Apply the shared operating rules.

## Decision Logic

A mismatch in ID or a missing trustworthy destination blocks this product plan. When a benefit has weak evidence, capture the narrower wording that the evidence actually supports and let Creative use that.

## Output

Establish product facts and permissible claims; save the findings as a step result with dated source references.

## Output Schema

The envelope uses `status`, `summary`, `evidence`, `data` and, for a blocked or limited result, `blockers`. Required `data` keys: `product_facts`, `approved_claims`, `restrictions`, `unknowns`. See the operator guide for types and special cases.

## Validation

Verify references, dates, scope and required fields. Reconcile contradictions. Check that conclusions follow from the evidence and list limitations before submission.

## Error Handling

Record the failed source or step and the next concrete action. Retry transient reads within provider limits. Do not retry an ambiguous write or change the approved target to bypass a failure.

## Approval

Read/analysis only; no approval or Meta mutation at this step.

## Execution Log

The orchestrator records run, step and UTC timestamp. Include source timestamps, precise decisions and blockers; store receipts via the executor.

## Next Step

Customer Research. Follow the CLI's returned route.
