---
name: account-research
description: "Establish which managed objects exist, how they are configured, and what their verified history can tell the next strategy."
---

## Skill Name

Account Research

## Purpose

Establish which managed objects exist, how they are configured, and what their verified history can tell the next strategy.

## Trigger

Run only when the lifecycle orchestrator selects `account-research`.

## Required Inputs

Meta Ad Library Research result and relevant earlier evidence. Read the selected run, product, strategy and campaign target as applicable.

## Required Files

`.agents/skills/meta-ads/references/policy.md`, the effective brand policy, and the orchestrator's referenced result records. For execution or handoff, also read `README.md`.

## Tools & APIs

Meta Marketing API via meta-ads account ACCOUNT; approved read-only breakdown tools.

## Instructions

1. Verify account ID, currency, time zone and status. Read the managed `agi-` campaign → ad set → ad hierarchy from `account_report`. Verify each parent ID. Record configured and effective status separately so an active setting under a paused parent stays distinguishable from delivery.
2. Match the product using saved enrollment, known destination and naming evidence. Group prior versions and note campaign objective, funding owner, countries and event source where visible. Compare only historical Insights actually returned for the same product, market, event and attribution basis.
3. Report operating headroom and conflicts at the appropriate scope. Use verified managed objects for strategy and aggregate account-wide totals for budget. If a same-product campaign is listed but its activity or settings are uncertain, name the specific configuration or Insights read needed.

## Rules

A scoped successful empty response is distinguishable from unavailable data. Apply the shared operating rules.

## Decision Logic

A complete zero-result inventory establishes an empty managed scope. Missing permissions, pages or performance data establish a coverage gap. Route confirmed overlap and compatible prior builds to Campaign Strategy. [Meta Marketing API](https://developers.facebook.com/documentation/ads-commerce/marketing-api)

## Output

Establish an account and delivery baseline for managed items; save the findings as a step result with dated source references.

## Output Schema

The envelope uses `status`, `summary`, `evidence`, `data` and, for a blocked or limited result, `blockers`. Required `data` keys: `account_id`, `managed_objects`, `delivery`, `opportunities`. See the operator guide for types and special cases.

## Validation

Verify references, dates, scope and required fields. Reconcile contradictions. Check that conclusions follow from the evidence and list limitations before submission.

## Error Handling

Record the failed source or step and the next concrete action. Retry transient reads within provider limits. Do not retry an ambiguous write or change the approved target to bypass a failure.

## Approval

Read/analysis only; no approval or Meta mutation at this step.

## Execution Log

The orchestrator records run, step and UTC timestamp. Include source timestamps, precise decisions and blockers; store receipts via the executor.

## Next Step

Strategy Development. Follow the CLI's returned route.
