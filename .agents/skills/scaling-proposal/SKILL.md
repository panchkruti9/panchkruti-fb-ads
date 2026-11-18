---
name: scaling-proposal
description: "Present the exact budget change for an informed owner decision."
---

## Skill Name

Scaling Proposal

## Purpose

Present the exact budget change for an informed owner decision.

## Trigger

Run only when the lifecycle orchestrator selects `scaling-proposal`.

## Required Inputs

Budget Validation result and relevant earlier evidence. Read the selected run, product, strategy and campaign target as applicable.

## Required Files

`.agents/skills/meta-ads/references/policy.md`, the effective brand policy, and the orchestrator's referenced result records. For execution or handoff, also read `README.md`.

## Tools & APIs

Scaling analysis, passed budget validation, Shopify evidence.

## Instructions

Read [the practical decision guide](references/decision-guide.md) before preparing this step.

1. Transfer the target ID and before/after values from passed Scaling Analysis and Budget Validation without changing them. Identify which current strategy version and two mature evidence windows support the request.
2. Present matched paid retained orders, spend, cost against target, date ranges and measurement limits. Show total account impact per day and at month end. Explain the expected incremental range and the downside using the same scenario assumptions as the analysis.
3. Include the exact action, review date, rollback trigger and what the executor will verify. Bind the resulting proposal ID to the exact target and amounts so it can be approved as written.

## Rules

A changed amount or target needs a new proposal. Apply the shared operating rules.

## Decision Logic

If the evidence changes in a way that affects eligibility, amount or exposure, return to the owning analysis. The proposal is the owner’s decision document.

## Output

Create a precise decision for the owner; save the findings as a step result with dated source references.

## Output Schema

The envelope uses `status`, `summary`, `evidence`, `data` and, for a blocked or limited result, `blockers`. Required `data` keys: `target_id`, `from_daily_minor`, `to_daily_minor`, `case`, `risks`, `next_review_on`. See the operator guide for types and special cases.

## Validation

Verify references, dates, scope and required fields. Reconcile contradictions. Check that conclusions follow from the evidence and list limitations before submission.

## Error Handling

Record the failed source or step and the next concrete action. Retry transient reads within provider limits. Do not retry an ambiguous write or change the approved target to bypass a failure.

## Approval

Read/analysis only; no approval or Meta mutation at this step.

## Execution Log

The orchestrator records run, step and UTC timestamp. Include source timestamps, precise decisions and blockers; store receipts via the executor.

## Next Step

Scaling Approval. Follow the CLI's returned route.
