---
name: performance-analysis
description: "Measure what Meta delivered and distinguish changes in delivery, response and attributed purchases."
---

## Skill Name

Performance Analysis

## Purpose

Measure what Meta delivered and distinguish changes in delivery, response and attributed purchases.

## Trigger

Run only when the lifecycle orchestrator selects `performance-analysis`.

## Required Inputs

Run request and current verified context. Read the selected run, product, strategy and campaign target as applicable.

## Required Files

`.agents/skills/meta-ads/references/policy.md`, the effective brand policy, and the orchestrator's referenced result records. For execution or handoff, also read `README.md`.

## Tools & APIs

Meta Marketing API Insights and authenticated account reads.

## Instructions

Read [the practical decision guide](references/decision-guide.md) before preparing this step.

1. Read campaign, ad set and ad rows in `review_evidence.meta.current` and `.previous`. Record the exact dates, account time zone, identifiers, attribution settings and returned purchase action type. Split around significant edits or mixed settings before comparing.
2. Use link clicks ÷ impressions for link CTR, spend ÷ link clicks for link CPC and spend × 1,000 ÷ impressions for CPM. Use one matching website Purchase action for Meta CPA. Leave missing denominators and unavailable breakdowns null. Compute ratios from totals at the right grain. Reach and frequency cannot be summed across rows as unique people.
3. Read the sequence: delivery and status, cost of reaching people, response to the ad, then attributed purchases. A higher CPM with stable CTR and rising CPA merits checking delivery conditions. Stable delivery with a drop in link response points to a different hypothesis. Label the hypothesis and the required corroboration.

Read the current configuration and learning information under `review_evidence.adset_delivery`. Report the learning state when returned and mark it unknown otherwise. Use `live_since` and `last_material_change_at` to identify windows that include a launch or an edit. Check `review_evidence.configuration_changed` and leave periods before the latest detected configuration change out of decisions. Record actual spend and exposure for each ad before drawing conversion conclusions.

## Rules

Meta conversions do not establish actual sales. Apply the shared operating rules.

## Decision Logic

Flag broken delivery immediately. Reserve sales-performance judgments for the strategy’s mature window. Keep Meta as a delivery and attribution report. [Meta Insights API](https://developers.facebook.com/docs/marketing-api/insights/)

## Output

Measure current and prior Meta delivery for managed targets; save the findings as a step result with dated source references.

## Output Schema

The envelope uses `status`, `summary`, `evidence`, `data` and, for a blocked or limited result, `blockers`. Required `data` keys: `meta_current`, `meta_previous`, `attribution`, `time_zone`, `anomalies`. See the operator guide for types and special cases.

## Validation

Verify references, dates, scope and required fields. Reconcile contradictions. Check that conclusions follow from the evidence and list limitations before submission.

## Error Handling

Record the failed source or step and the next concrete action. Retry transient reads within provider limits. Do not retry an ambiguous write or change the approved target to bypass a failure.

## Approval

Read/analysis only; no approval or Meta mutation at this step.

## Execution Log

The orchestrator records run, step and UTC timestamp. Include source timestamps, precise decisions and blockers; store receipts via the executor.

## Next Step

Business Performance Analysis. Follow the CLI's returned route.
