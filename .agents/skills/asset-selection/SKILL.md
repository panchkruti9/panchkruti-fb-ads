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

`.agents/skills/meta-ads/references/policy.md`, the effective brand policy, and the orchestrator's referenced result records. For execution or handoff, also read `README.md`.

## Tools & APIs

Google Drive connector; fetch the configured root and returned folders directly.

## Instructions

Read [the practical decision guide](references/decision-guide.md) before preparing this step.

When a Drive listing omits version or checksum, use [the connected Drive revision and original-file steps](../meta-ads/references/contracts.md#connected-agent-steps). Verify the eligible candidates directly through the plugin and continue with the files that pass.

Use `meta-ads media-preview RUN_ID` to render the saved originals as local PNGs when the Drive viewer fails. Open the returned PNG paths with the local image viewer. If a candidate is unsuitable, inspect the others and use the skill's Creative Concept rework route if none fits.

For a new creative produced for this run, follow `sources.drive.filing`. Under the saved Drive root, find or create the specified stage folder and its product subfolder using the Drive plugin. Look for the exact filename before upload. Reuse a matching file when its bytes match. If a verified original differs, use the next artwork revision in its filename. Upload the new file to the resolved parent folder ID and verify its ID, parent, and revision before using it. Reuse existing eligible artwork in place.

1. Open the configured Drive root by ID and the exact approved stage folder. Use `drive_media` and supplied previews. Check file ID, revision, approval stage and exact product. Inspect the media itself. File names and folder location do not establish what viewers see.
2. Apply pass/fail checks for authentic packaging, proof of the concept, visible claims, placement crop, contrast and readable size on a phone. For video use an approved poster for the same stage and verify all visible and spoken content. Sampled frames are partial evidence when audio or unseen sections remain.
3. Among passing options choose the one that communicates the concept fastest in the placement. Record the exact file ID, revision, stage, ad name and why it fits. If unavailable, route to a supported concept using approved media or return the exact asset requirements for production.

## Rules

Do not use Review before use assets or treat URL shape as approval. Apply the shared operating rules.

## Decision Logic

Use existing owner-approved artwork as supplied when relevant and suitable. Ordinary product-benefit wording does not require a new product-specific clinical dossier at asset selection. Flag a specific material problem such as a guarantee, misleading identity, prohibited personal assertion or actual Meta rejection. Ask for clarification only when that issue changes the usable choice; continue checking the other assets. A contents-led bundle ad needs both authentic packs identifiable. The current flow uses approved static, video and Story media and excludes catalogue output.

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
