---
name: creative-concept
description: "Turn one buyer question and one verified proof point into a production brief that can produce a distinct ad."
---

## Skill Name

Creative Concept

## Purpose

Turn one buyer question and one verified proof point into a production brief that can produce a distinct ad.

## Trigger

Run only when the lifecycle orchestrator selects `creative-concept`.

## Required Inputs

Audience Planning result and relevant earlier evidence. Read the selected run, product, strategy and campaign target as applicable.

## Required Files

`docs/policy.md`, the effective brand policy, and the orchestrator's referenced result records. For execution or handoff, also read `README.md`.

## Tools & APIs

Campaign strategy, funnel and audience artifacts.

## Instructions

1. Choose the shopper question from Funnel Planning and Customer Research. Write the one thing the ad must communicate and how the viewer can see it. For a contents concept, show both authentic packs. For a routine concept, show the approved sequence. For value, show what is included and verified offer terms.
2. Write the first frame or Feed thumbnail, proof moment, product visibility, overlay text, format, placement and CTA. For video or Story, specify opening, demonstration and final action. For static, make the product and message intelligible before the caption expands.
3. Choose variants that test meaningfully different messages or proof mechanisms. When testing the message, hold offer, destination and intended audience conditions comparable. A font or border change alone leaves the underlying concept the same. If approved assets cannot prove the idea, describe the missing shot or rework the concept to supported evidence.

## Rules

Start creative work after strategy; do not present previews as saved ads. Apply the shared operating rules.

## Decision Logic

Record the shopper question, message, evidence and visual plan under the exact ad name. Use the failed requirement when reworking a brief so a repeated attempt addresses the actual gap. [Meta Blueprint creative diversification](https://www.facebookblueprint.com/student/activity/707402)

## Output

Produce a brief for formats the brand can support; save the findings as a step result with dated source references.

## Output Schema

The envelope uses `status`, `summary`, `evidence`, `data` and, for a blocked or limited result, `blockers`. Required `data` keys: `concepts`, `test_variables`, `production_brief`. See the operator guide for types and special cases.

## Validation

Verify references, dates, scope and required fields. Reconcile contradictions. Check that conclusions follow from the evidence and list limitations before submission.

## Error Handling

Record the failed source or step and the next concrete action. Retry transient reads within provider limits. Do not retry an ambiguous write or change the approved target to bypass a failure.

## Approval

Read/analysis only; no approval or Meta mutation at this step.

## Execution Log

The orchestrator records run, step and UTC timestamp. Include source timestamps, precise decisions and blockers; store receipts via the executor.

## Next Step

Ad Copywriting. Follow the CLI's returned route.
