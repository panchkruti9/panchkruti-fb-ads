---
name: asset-selection
description: "Choose a specific approved asset that makes the concept’s claim visible in the intended placement."
---

## Skill Name

Creative Asset Selection

## Purpose

Choose a specific approved asset that makes the concept’s claim visible in the intended placement.

## Trigger

Run only when the lifecycle orchestrator selects `asset-selection`.

## Required Inputs

Ad Copywriting result and relevant earlier evidence. Read the selected run, product, strategy and campaign target as applicable.

## Required Files

`docs/policy.md`, the effective brand policy, and the orchestrator's referenced result records. For execution or handoff, also read `README.md`.

## Tools & APIs

Google Drive connector; fetch the configured root and returned folders directly.

## Instructions

When a Drive listing omits version or checksum, use [the connected Drive revision and original-file steps](../../../../../../../docs/contracts.md#connected-agent-steps). Verify the eligible candidates directly through the plugin and continue with the files that pass.

1. Open the configured Drive root by ID and the exact approved stage folder. Use `drive_media` and supplied previews. Check file ID, revision, approval stage and exact product. Inspect the media itself. File names and folder location do not establish what viewers see.
2. Apply pass/fail checks for authentic packaging, proof of the concept, visible claims, placement crop, contrast and readable size on a phone. For video use an approved poster for the same stage and verify all visible and spoken content. Sampled frames are partial evidence when audio or unseen sections remain.
3. Among passing options choose the one that communicates the concept fastest in the placement. Record the exact file ID, revision, stage, ad name and why it fits. If unavailable, route to a supported concept using approved media or return the exact asset requirements for production.

## Rules

Do not use Review before use assets or treat URL shape as approval. Apply the shared operating rules.

## Decision Logic

An approved folder does not establish claim support. A contents-led bundle ad needs both authentic packs identifiable. The current flow uses approved static, video and Story media and excludes catalogue output.

## Output

Choose real approved source assets by stage; save the findings as a step result with dated source references.

## Output Schema

The envelope uses `status`, `summary`, `evidence`, `data` and, for a blocked or limited result, `blockers`. Required `data` keys: `assets`, `excluded`, `placement_fit`. See the operator guide for types and special cases.

## Validation

Verify references, dates, scope and required fields. Reconcile contradictions. Check that conclusions follow from the evidence and list limitations before submission.

## Error Handling

Record the failed source or step and the next concrete action. Retry transient reads within provider limits. Do not retry an ambiguous write or change the approved target to bypass a failure.

## Approval

Read/analysis only; no approval or Meta mutation at this step.

## Execution Log

The orchestrator records run, step and UTC timestamp. Include source timestamps, precise decisions and blockers; store receipts via the executor.

## Next Step

Creative Validation. Follow the CLI's returned route.
