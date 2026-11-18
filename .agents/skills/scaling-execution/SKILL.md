---
name: scaling-execution
description: "Apply the exact approved increase and restart monitoring so the strategy is judged at the new spend level."
---

## Skill Name

Scaling Execution

## Purpose

Apply the exact approved increase and restart monitoring so the strategy is judged at the new spend level.

## Trigger

Run only when the lifecycle orchestrator selects `scaling-execution`.

## Required Inputs

Scaling Approval result and relevant earlier evidence. Read the selected run, product, strategy and campaign target as applicable.

## Required Files

`.agents/skills/meta-ads/references/policy.md`, the effective brand policy, and the orchestrator's referenced result records. For execution or handoff, also read `README.md`.

## Tools & APIs

Operator-controlled Meta execution and verified readback.

## Instructions

Read [the practical decision guide](references/decision-guide.md) before preparing this step.

1. Open the approved proposal and verify the exact target ID, ownership and current budget. Recheck current campaign status, delivery, funding ownership, agreement with approved baseline and account-wide headroom. Check verified monthly spend control as required by policy.
2. Record the pending update and apply only the authorized daily budget through the dispatcher. Read back budget and state. If Meta already shows the exact proposal result after an interrupted response, reconcile the recorded operation before issuing another write.
3. Save actual before and after minor currency units, time, proposal reference, readback and strategy version. Restart monitoring using a clean post-change window and existing decision thresholds. Require new comparable evidence for another scaling decision.

## Rules

Do not automate external scheduling unless the owner requests it. Apply the shared operating rules.

## Decision Logic

Report success only after readback matches the proposal. If the live baseline or limits changed, return for updated analysis. If the result at the new spend undermines the strategy, route through Optimize before deciding whether to start a new strategy cycle. [Meta Marketing API campaign management](https://developers.facebook.com/documentation/ads-commerce/marketing-api)

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

Return to Optimize monitoring using the verified receipt. Follow the CLI's returned route.
