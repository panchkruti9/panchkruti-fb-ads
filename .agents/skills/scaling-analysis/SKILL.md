---
name: scaling-analysis
description: "Choose one bounded budget increase that the verified strategy and available headroom can support."
---

## Skill Name

Scaling Analysis

## Purpose

Choose one bounded budget increase that the verified strategy and available headroom can support.

## Trigger

Run only when the lifecycle orchestrator selects `scaling-analysis`.

## Required Inputs

Scaling Eligibility result and relevant earlier evidence. Read the selected run, product, strategy and campaign target as applicable.

## Required Files

`.agents/skills/meta-ads/references/policy.md`, the effective brand policy, and the orchestrator's referenced result records. For execution or handoff, also read `README.md`.

## Tools & APIs

Current funding and Scale eligibility evidence.

## Instructions

1. Read `current_funding`, `account_budget_before` and both matched business outcome windows. Find the actual campaign or ad set that owns the budget and read its current minor currency units amount. Identify how much daily and projected month-end capacity remains after other active commitments.
2. Compare baseline and conservative purchase-cost scenarios. Estimate extra orders as proposed extra spend ÷ scenario CPA and compare the range with inventory, fulfillment and the strategy’s CPA ceiling. A favorable historic CPA is a planning input. Treat marginal CPA after a scale as uncertain.
3. Choose one bounded increase and set the first valid review window. Specify the spend, business KPI and operational stop trigger. When downside performance would exceed the approved ceiling or capacity, reduce the proposed increment or report that there is no defensible increment.

## Rules

Use minor currency units; a proposal is not a budget change. Apply the shared operating rules.

## Decision Logic

Return the exact budget-owner ID, before and proposed minor currency units, assumptions, risks and monitoring plan. Leave the successful strategy intact through this test of additional spend.

## Output

Model a supported increase with stop conditions; save the findings as a step result with dated source references.

## Output Schema

The envelope uses `status`, `summary`, `evidence`, `data` and, for a blocked or limited result, `blockers`. Required `data` keys: `current_daily_minor`, `proposed_daily_minor`, `risks`, `monitoring_plan`. See the operator guide for types and special cases.

Registered data fields: `current_daily_minor`, `proposed_daily_minor`, `risks`, `monitoring_plan`, `target_id`.

## Validation

Verify references, dates, scope and required fields. Reconcile contradictions. Check that conclusions follow from the evidence and list limitations before submission.

## Error Handling

Record the failed source or step and the next concrete action. Retry transient reads within provider limits. Do not retry an ambiguous write or change the approved target to bypass a failure.

## Approval

Read/analysis only; no approval or Meta mutation at this step.

## Execution Log

The orchestrator records run, step and UTC timestamp. Include source timestamps, precise decisions and blockers; store receipts via the executor.

## Next Step

Budget Validation. Follow the CLI's returned route.
