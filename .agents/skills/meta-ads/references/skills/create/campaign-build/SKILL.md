---
name: campaign-build
description: "Build the exact validated campaign, ad sets and ads as paused Meta objects and prove what was saved."
---

## Skill Name

Campaign Build

## Purpose

Build the exact validated campaign, ad sets and ads as paused Meta objects and prove what was saved.

## Trigger

Run only when the lifecycle orchestrator selects `campaign-build`.

## Required Inputs

Creative Validation result and relevant earlier evidence. Read the selected run, product, strategy and campaign target as applicable.

## Required Files

`docs/policy.md`, the effective brand policy, and the orchestrator's referenced result records. For execution or handoff, also read `README.md`.

## Tools & APIs

Orchestrator worker, saved proposal, and operator-controlled Meta executor.

## Instructions

1. Compile the typed plan into the exact orchestrator proposal. Verify ownership, naming, hierarchy, Purchase source, supported placement, approved asset revisions, identity, URL tags and budget headroom. Confirm the applicable operator authorization before any writes.
2. For a new build create the paused campaign and ad sets and save IDs after readback. Resolve or upload approved media, handle video processing using its known ID, create the creative, and create the ad as PAUSED. For an addition use the verified existing ad set and create only the new creative and paused ad.
3. After each write read back account, parent IDs, expected configuration and configured/effective status. Record provider IDs and pending or verified state. If a response is ambiguous, first resolve whether the object exists. Resume from confirmed IDs so retries do not create duplicates.

## Rules

Only the executor can complete the step; activation uses a separate route. Apply the shared operating rules.

## Decision Logic

A paused build is complete after verified readback and a recorded receipt. Activation goes through its own check and owner approval. [Meta Marketing API campaign and creative structure](https://developers.facebook.com/documentation/ads-commerce/marketing-api)

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

Record the paused build and prepare a separate activation run when requested. Follow the CLI's returned route.
