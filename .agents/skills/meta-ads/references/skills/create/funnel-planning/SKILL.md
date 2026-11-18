---
name: funnel-planning
description: "Decide which shopper questions the campaign needs to answer before purchase and where each answer should appear."
---

## Skill Name

Funnel Planning

## Purpose

Decide which shopper questions the campaign needs to answer before purchase and where each answer should appear.

## Trigger

Run only when the lifecycle orchestrator selects `funnel-planning`.

## Required Inputs

Campaign Strategy result and relevant earlier evidence. Read the selected run, product, strategy and campaign target as applicable.

## Required Files

`docs/policy.md`, the effective brand policy, and the orchestrator's referenced result records. For execution or handoff, also read `README.md`.

## Tools & APIs

Current campaign strategy and storefront evidence.

## Instructions

1. Map Discovery, Consideration and Purchase to specific shopper questions from the strategy and research. Discovery should make the product and use case recognizable. Consideration should resolve a meaningful objection with proof. Purchase should make price, contents, terms or next action clear where they affect the decision.
2. Give each selected message a proof point, placement intent, destination, CTA and diagnostic signal. Keep the business purchase goal from Strategy Development. A consideration message can still be an ad in a Sales campaign.
3. Allocate distinct stages to separate ad sets only when separate delivery is useful, targetable and affordable. For a small test, use the message most directly tied to the current hypothesis and defer the others explicitly. Plan remarketing only with verified usable audience and account controls.

## Rules

Offer and urgency must be current and verifiable. Apply the shared operating rules.

## Decision Logic

If shoppers do not understand the bundle, prioritize a consideration message that shows the verified routine. Use a purchase-stage price message when value or terms are the stronger supported barrier. Output a message map the Creative Concept and Audience Planning skills can use.

## Output

Map Discovery, Consideration and Purchase to useful actions; save the findings as a step result with dated source references.

## Output Schema

The envelope uses `status`, `summary`, `evidence`, `data` and, for a blocked or limited result, `blockers`. Required `data` keys: `stages`, `journey`, `allocation`. See the operator guide for types and special cases.

## Validation

Verify references, dates, scope and required fields. Reconcile contradictions. Check that conclusions follow from the evidence and list limitations before submission.

## Error Handling

Record the failed source or step and the next concrete action. Retry transient reads within provider limits. Do not retry an ambiguous write or change the approved target to bypass a failure.

## Approval

Read/analysis only; no approval or Meta mutation at this step.

## Execution Log

The orchestrator records run, step and UTC timestamp. Include source timestamps, precise decisions and blockers; store receipts via the executor.

## Next Step

Audience Planning. Follow the CLI's returned route.
