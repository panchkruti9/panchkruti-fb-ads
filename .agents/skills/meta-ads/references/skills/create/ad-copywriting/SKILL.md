---
name: ad-copywriting
description: "Write Meta ad text that communicates the intended message, supports it with approved evidence, and leads to the right action."
---

## Skill Name

Ad Copywriting

## Purpose

Write Meta ad text that communicates the intended message, supports it with approved evidence, and leads to the right action.

## Trigger

Run only when the lifecycle orchestrator selects `ad-copywriting`.

## Required Inputs

Creative Concept result and relevant earlier evidence. Read the selected run, product, strategy and campaign target as applicable.

## Required Files

`docs/policy.md`, the effective brand policy, and the orchestrator's referenced result records. For execution or handoff, also read `README.md`.

## Tools & APIs

Product facts, concept, and shared skincare rules.

## Instructions

1. Read the concept, verified product claims, placement and destination. Put the value or product identity early enough to survive truncation. Use one verified reason to click. Write a headline understandable on its own and a description only if it adds useful information.
2. Check the implied claim of every sentence. Ingredient presence can support an ingredient statement. It cannot support a result, timeframe, comparative claim or treatment promise by itself. Use neutral product language and follow brand and Meta rules about personal attributes. Match current price, bundle terms and CTA to the page.
3. Return exact `variants` by ad name with `primary_text`, `headline`, `description` and `cta`. In `claim_evidence`, cite the product page or packaging once for ordinary product wording it supports. Identify separate sources for any stronger claim or offer.

## Rules

Remove claims that cannot be substantiated; do not edit Shopify offers. Apply the shared operating rules.

## Decision Logic

If the evidence cannot support the core premise, send the premise back to Creative Concept. If only a sentence is too strong, reduce it to what the evidence supports. Use the supported CTA enum for the intended next action. [Meta Advertising Standards](https://transparency.meta.com/policies/ad-standards/)

## Output

Write evidence-backed, placement-ready ad text; save the findings as a step result with dated source references.

## Output Schema

The envelope uses `status`, `summary`, `evidence`, `data` and, for a blocked or limited result, `blockers`. Required `data` keys: `variants`, `claim_evidence`, `ctas`. See the operator guide for types and special cases.

## Validation

Verify references, dates, scope and required fields. Reconcile contradictions. Check that conclusions follow from the evidence and list limitations before submission.

## Error Handling

Record the failed source or step and the next concrete action. Retry transient reads within provider limits. Do not retry an ambiguous write or change the approved target to bypass a failure.

## Approval

Read/analysis only; no approval or Meta mutation at this step.

## Execution Log

The orchestrator records run, step and UTC timestamp. Include source timestamps, precise decisions and blockers; store receipts via the executor.

## Next Step

Creative Asset Selection. Follow the CLI's returned route.
