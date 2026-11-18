---
name: creative-validation
description: "Decide whether the actual asset, copy, placement and destination tell the same truthful story and can be built together."
---

## Skill Name

Creative Validation

## Purpose

Decide whether the actual asset, copy, placement and destination tell the same truthful story and can be built together.

## Trigger

Run only when the lifecycle orchestrator selects `creative-validation`.

## Required Inputs

Creative Asset Selection result and relevant earlier evidence. Read the selected run, product, strategy and campaign target as applicable.

## Required Files

`docs/policy.md`, the effective brand policy, and the orchestrator's referenced result records. For execution or handoff, also read `README.md`.

## Tools & APIs

Approved media, actual placement previews, Shopify destination, Meta creative read tools.

## Instructions

1. Inspect the full ad at phone size and describe what a shopper would believe it promises. Compare this implied promise and all visible or spoken claims against approved evidence. Verify actual product packaging, brand, rights, readability and crop per placement. For video, verify the full clip or record what review is missing.
2. Open the destination and compare store, product, price and applicable offer conditions with the ad. Verify exact ad names, approved Drive revisions, supported format and URL tags. Use the website Purchase recipe and placement keys in the build contract. Check the exact requested destination, verified offer and allowed formats and placements.
3. Record an observation for each `checks` field and pair the exact `approved_ad` with its typed plan. Route copy failures to Copywriting, media failures to Asset Selection and unsupported premises to Creative Concept. Give the failed ad or asset and the change that would pass.

## Rules

Passing ads must include per-ad evidence and preserved exact fingerprints. Never pass a failed creative. Apply the shared operating rules.

## Decision Logic

If visual text promises a result the caption avoids, the visual still fails. Release to Campaign Build only where all required checks pass. The operator must review Meta’s generated preview before activation. [Meta Advertising Standards](https://transparency.meta.com/policies/ad-standards/)

## Output

Validate specific ads and their actual approved creative; save the findings as a step result with dated source references.

## Output Schema

The envelope uses `status`, `summary`, `evidence`, `data` and, for a blocked or limited result, `blockers`. Required `data` keys: `ads`, `checks`, `release_limits`. See the operator guide for types and special cases.

Registered data fields: `ads`, `checks`, `release_limits`, `plan`.

## Validation

Verify references, dates, scope and required fields. Reconcile contradictions. Check that conclusions follow from the evidence and list limitations before submission.

## Error Handling

Record the failed source or step and the next concrete action. Retry transient reads within provider limits. Do not retry an ambiguous write or change the approved target to bypass a failure.

## Approval

Read/analysis only; no approval or Meta mutation at this step.

## Execution Log

The orchestrator records run, step and UTC timestamp. Include source timestamps, precise decisions and blockers; store receipts via the executor.

## Next Step

Campaign Build. Follow the CLI's returned route.
