---
name: audience-analysis
description: "Diagnose whether the targeting and placement setup actually reached useful people under comparable conditions."
---

## Skill Name

Audience Analysis

## Purpose

Diagnose whether the targeting and placement setup actually reached useful people under comparable conditions.

## Trigger

Run only when the lifecycle orchestrator selects `audience-analysis`.

## Required Inputs

Creative Analysis result and relevant earlier evidence. Read the selected run, product, strategy and campaign target as applicable.

## Required Files

`.agents/skills/meta-ads/references/policy.md`, the effective brand policy, and the orchestrator's referenced result records. For execution or handoff, also read `README.md`.

## Tools & APIs

Ad set Insights and available authorized breakdowns.

## Instructions

Read [the practical decision guide](references/decision-guide.md) before preparing this step.

1. Join ad set results to verified geography, placements, customer controls and audience suggestions from the saved build. Compare windows with the same objective, optimization event and attribution settings. Check the current effective controls so later settings changes do not get attributed to creative.
2. Compare delivery, spend and purchase evidence at the supported grain. Treat missing conversion breakdowns as unavailable. When an ad set has little delivery, check status, restrictions, budget and eligible audience size before judging its audience.
3. Investigate concentration and overlap as hypotheses. Similar targeting can justify a closer look. Confirm overlap or relevant exclusions with authorized data before recommending consolidation or a change in controls. Avoid drawing buyer characteristics from placement or demographic reports alone.

## Rules

Respect aggregation thresholds and data limitations. Apply the shared operating rules.

## Decision Logic

Keep existing targeting when the data supports only a creative or measurement issue. Recommend an executable audience change only when a specific delivery problem and compatible control are verified. [Meta Marketing API audience and Insights guidance](https://developers.facebook.com/documentation/ads-commerce/marketing-api)

## Output

Evaluate audience delivery and overlap; save the findings as a step result with dated source references.

## Output Schema

The envelope uses `status`, `summary`, `evidence`, `data` and, for a blocked or limited result, `blockers`. Required `data` keys: `comparisons`, `overlap`, `delivery_limits`, `recommendations`. See the operator guide for types and special cases.

## Validation

Verify references, dates, scope and required fields. Reconcile contradictions. Check that conclusions follow from the evidence and list limitations before submission.

## Error Handling

Record the failed source or step and the next concrete action. Retry transient reads within provider limits. Do not retry an ambiguous write or change the approved target to bypass a failure.

## Approval

Read/analysis only; no approval or Meta mutation at this step.

## Execution Log

The orchestrator records run, step and UTC timestamp. Include source timestamps, precise decisions and blockers; store receipts via the executor.

## Next Step

Campaign Analysis. Follow the CLI's returned route.
