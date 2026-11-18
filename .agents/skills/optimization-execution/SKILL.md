---
name: optimization-execution
description: "Apply the authorized optimization through the lifecycle and verify the result or handoff."
---

## Skill Name

Optimization Execution

## Purpose

Apply the authorized optimization through the lifecycle and verify the result or handoff.

## Trigger

Run only when the lifecycle orchestrator selects `optimization-execution`.

## Required Inputs

Optimization Decision result and relevant earlier evidence. Read the selected run, product, strategy and campaign target as applicable.

## Required Files

`.agents/skills/meta-ads/references/policy.md`, the effective brand policy, and the orchestrator's referenced result records. For execution or handoff, also read `README.md`.

## Tools & APIs

Orchestrator proposal and operator executor; Create for revised builds.

## Instructions

1. Match the decision to the enrolled object, approved proposal, ownership, effective state and plan. Recheck relevant limits before a write. Use the shared dispatcher for authorized changes.
2. For PAUSE, write only the authorized status and read it back. For a creative FIX, TEST or REFRESH, route approved changes through Create as new paused ads on the verified target. For a defect outside the executor, record which correction and verification are needed. RECREATE is routed directly to Research by the orchestrator with the prior decision and evidence. Verify the successor separately.
3. Persist pending and verified states and actual Meta IDs. Reconcile uncertain responses before retrying. After a verified change, set the next comparable review and record the strategy version it belongs to.

## Rules

Only an executor receipt completes an applied action. Apply the shared operating rules.

## Decision Logic

Keep the current campaign state distinct from the successor plan. A replacement proposal does not establish that the original was paused. Any removal of the old campaign follows the authorized replacement procedure.

## Output

Orchestrator-generated record or a documented stop with its reason.

## Output Schema

The envelope uses `status`, `summary`, `evidence`, `data` and, for a blocked or limited result, `blockers`. Required `data` keys: `receipt`. See the operator guide for types and special cases.

## Validation

Verify references, dates, scope and required fields. Reconcile contradictions. Verify the exact proposal and official readback; a local preview is not a receipt.

## Error Handling

Record the failed source or step and the next concrete action. Retry transient reads within provider limits. Do not retry an ambiguous write or change the approved target to bypass a failure.

## Approval

All Meta writes use operator approval. Owner approval is explicit for activation and budget changes.

## Execution Log

The orchestrator records run, step and UTC timestamp. Include source timestamps, precise decisions and blockers; store receipts via the executor.

## Next Step

Return to monitoring after a verified change or follow the decision route. Follow the CLI's returned route.
