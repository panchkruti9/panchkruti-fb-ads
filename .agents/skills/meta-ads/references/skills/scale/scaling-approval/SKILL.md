---
name: scaling-approval
description: "Record the owner’s decision against a specific budget proposal so the dispatcher can verify its authority."
---

## Skill Name

Scaling Approval

## Purpose

Record the owner’s decision against a specific budget proposal so the dispatcher can verify its authority.

## Trigger

Run only when the lifecycle orchestrator selects `scaling-approval`.

## Required Inputs

Scaling Proposal result and relevant earlier evidence. Read the selected run, product, strategy and campaign target as applicable.

## Required Files

`docs/policy.md`, the effective brand policy, and the orchestrator's referenced result records. For execution or handoff, also read `README.md`.

## Tools & APIs

Orchestrator approve command run by the authorized operator.

## Instructions

1. Present the exact proposal ID, budget-owning object, current and proposed amount, account exposure and business evidence. Wait for a decision from the authorized owner.
2. Record the operator, owner decision reference, timestamp and proposal ID through the orchestrator. Make clear which amount and target the decision covers. If the proposal changes in substance, submit the changed proposal for a fresh decision.
3. Before releasing the job, verify the required approval record is current and ties to the exact proposal. Rejection or absent authorization leaves the write pending or rejected according to the actual recorded decision.

## Rules

The agent does not sign or impersonate owner approval. Apply the shared operating rules.

## Decision Logic

The model must never infer consent from a previous approval or issue its own approval. Only the dispatcher releases the exact authorized action.

## Output

Orchestrator-generated record or a documented stop with its reason.

## Output Schema

The envelope uses `status`, `summary`, `evidence`, `data` and, for a blocked or limited result, `blockers`. Required `data` keys: `approval`. See the operator guide for types and special cases.

## Validation

Verify references, dates, scope and required fields. Reconcile contradictions. Verify the exact proposal and official readback; a local preview is not a receipt.

## Error Handling

Record the failed source or step and the next concrete action. Retry transient reads within provider limits. Do not retry an ambiguous write or change the approved target to bypass a failure.

## Approval

All Meta writes use operator approval. Owner approval is explicit for activation and budget changes.

## Execution Log

The orchestrator records run, step and UTC timestamp. Include source timestamps, precise decisions and blockers; store receipts via the executor.

## Next Step

Scaling Execution. Follow the CLI's returned route.
