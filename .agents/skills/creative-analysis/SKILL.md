---
name: creative-analysis
description: "Determine which concepts earned a fair read, which signals changed, and what creative test would be informative next."
---

## Skill Name

Creative Analysis

## Purpose

Determine which concepts earned a fair read, which signals changed, and what creative test would be informative next.

## Trigger

Run only when the lifecycle orchestrator selects `creative-analysis`.

## Required Inputs

Business Performance Analysis result and relevant earlier evidence. Read the selected run, product, strategy and campaign target as applicable.

## Required Files

`.agents/skills/meta-ads/references/policy.md`, the effective brand policy, and the orchestrator's referenced result records. For execution or handoff, also read `README.md`.

## Tools & APIs

Ad-level Insights, creative IDs and plan history.

## Instructions

1. Join ad Insights to exact ad ID, concept, version, offer, stage, format and placement. Check spend and impression exposure per ad before comparing response and Purchase CPA. A concept with negligible delivery stays inconclusive.
2. Compare like conditions and report both spend and outcomes. A strong click rate and weak purchases can reflect a curiosity hook, a mismatch with the page, or tracking. Cross-check the destination and business evidence before recommending a new promise. A drop in response with rising frequency across comparable windows supports checking fatigue. A change in placement or audience mix offers an alternative explanation.
3. Propose a single actionable improvement or test with a specific creative element and what to hold comparable. If both angle and format differ, record the difference as a package and keep component effects unknown.

## Rules

Early noise is not fatigue. Apply the shared operating rules.

## Decision Logic

Offer a concrete next concept only when the evidence supports the shopper problem. Use more exposure or a designed test when the result is ambiguous. [Meta Blueprint creative experiments](https://www.facebookblueprint.com/student/path/219763-ab-test-conversion-brand-lift-course)

## Output

Explain differences between ad concepts and placements; save the findings as a step result with dated source references.

## Output Schema

The envelope uses `status`, `summary`, `evidence`, `data` and, for a blocked or limited result, `blockers`. Required `data` keys: `comparisons`, `fatigue`, `limitations`, `recommendations`. See the operator guide for types and special cases.

## Validation

Verify references, dates, scope and required fields. Reconcile contradictions. Check that conclusions follow from the evidence and list limitations before submission.

## Error Handling

Record the failed source or step and the next concrete action. Retry transient reads within provider limits. Do not retry an ambiguous write or change the approved target to bypass a failure.

## Approval

Read/analysis only; no approval or Meta mutation at this step.

## Execution Log

The orchestrator records run, step and UTC timestamp. Include source timestamps, precise decisions and blockers; store receipts via the executor.

## Next Step

Audience Analysis. Follow the CLI's returned route.
