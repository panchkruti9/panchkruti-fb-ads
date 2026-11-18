---
name: scaling-eligibility
description: "Decide whether the result is strong enough to consider spending more on the same strategy."
---

## Skill Name

Scaling Eligibility

## Purpose

Decide whether the result is strong enough to consider spending more on the same strategy.

## Trigger

Run only when the lifecycle orchestrator selects `scaling-eligibility`.

## Required Inputs

Run request and current verified context. Read the selected run, product, strategy and campaign target as applicable.

## Required Files

`docs/policy.md`, the effective brand policy, and the orchestrator's referenced result records. For execution or handoff, also read `README.md`.

## Tools & APIs

Current paid-order evidence, Meta delivery, tracking and fulfilment/inventory records.

## Instructions

1. Read the current strategy criteria and two mature, comparable Meta and Shopify windows. Check target ID, tracking, attribution lag and denominator. Verify the minimum count of the selected business result and its cost at or under the strategy’s ceiling in each window. Require two nonoverlapping windows and verified contribution for the exact product and variant. In each window, product receipts after refunds and taxes must exceed verified product costs, shipping, fulfillment, fees and actual ad spend. Use the measured amounts in the business evidence. A CPA ceiling alone does not establish contribution.
2. Check that the business outcome in those windows matches the actual strategy. For a first-time buyer goal, use the confirmed first-time buyer count and its cost in both windows. Keep unknown buyer history explicit.
3. Verify availability with tracked stock or an independent current source and check fulfillment capacity and replenishment lead time. Confirm there was no material change that invalidates the comparison. Return boolean checks for business, tracking, stability, inventory and fulfillment using the keys business, tracking, stability, inventory, and fulfilment.

## Rules

verified_checks uses booleans for business, tracking, stability, inventory and fulfilment. Apply the shared operating rules.

## Decision Logic

Mark eligible only when the required checks pass. If tracking, available inventory or sample quality is uncertain, record the precise evidence needed and set a review. An eligibility pass lets Scaling Analysis explore an increase.

## Output

Determine whether an item qualifies for growth evaluation; save the findings as a step result with dated source references.

## Output Schema

The envelope uses `status`, `summary`, `evidence`, `data` and, for a blocked or limited result, `blockers`. Required `data` keys: `eligible`, `verified_checks`, `criteria`, `rationale`. See the operator guide for types and special cases.

## Validation

Verify references, dates, scope and required fields. Reconcile contradictions. Check that conclusions follow from the evidence and list limitations before submission.

## Error Handling

Record the failed source or step and the next concrete action. Retry transient reads within provider limits. Do not retry an ambiguous write or change the approved target to bypass a failure.

## Approval

Read/analysis only; no approval or Meta mutation at this step.

## Execution Log

The orchestrator records run, step and UTC timestamp. Include source timestamps, precise decisions and blockers; store receipts via the executor.

## Next Step

Scaling Analysis. Follow the CLI's returned route.
