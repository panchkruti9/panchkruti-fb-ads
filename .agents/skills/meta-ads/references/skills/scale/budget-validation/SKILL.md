---
name: budget-validation
description: "Verify that the exact proposed increase fits total daily and monthly account exposure."
---

## Skill Name

Budget Validation

## Purpose

Verify that the exact proposed increase fits total daily and monthly account exposure.

## Trigger

Run only when the lifecycle orchestrator selects `budget-validation`.

## Required Inputs

Scaling Analysis result and relevant earlier evidence. Read the selected run, product, strategy and campaign target as applicable.

## Required Files

`docs/policy.md`, the effective brand policy, and the orchestrator's referenced result records. For execution or handoff, also read `README.md`.

## Tools & APIs

python -m ads budget ACCOUNT; Meta account funding and Insights.

## Instructions

1. Use the worker’s live funding enumeration and month-to-date spend in the account time zone. Count the active campaign budget once when it funds the children, and count ad set budgets when they own funding. Include all account exposure, including non-managed campaigns as aggregates.
2. Replace the target’s current budget with the proposed amount exactly once. Compare projected daily exposure and month-to-date spend plus the planned reservation for remaining days with the effective brand policy. Confirm assumptions for any lifetime or scheduled amounts. Distinguish a forecast from the configured hard spend control.
3. Record before and after totals, target, time zone, snapshot time and policy limit. A changed budget or spending scope requires fresh evidence before the proposal proceeds.

## Rules

Policy limits cannot be waived by an ordinary proposal. Apply the shared operating rules.

## Decision Logic

Block when funding is mixed, exposure cannot be bounded, data is incomplete or a limit would be exceeded. The checker evaluates the existing policy ceiling. A change to that policy follows the owner authorization process.

## Output

Check account-wide limits using live data; save the findings as a step result with dated source references.

## Output Schema

The envelope uses `status`, `summary`, `evidence`, `data` and, for a blocked or limited result, `blockers`. Required `data` keys: `account_id`, `projected_daily_minor`, `projected_monthly_minor`, `passed`. See the operator guide for types and special cases.

## Validation

Verify references, dates, scope and required fields. Reconcile contradictions. Check that conclusions follow from the evidence and list limitations before submission.

## Error Handling

Record the failed source or step and the next concrete action. Retry transient reads within provider limits. Do not retry an ambiguous write or change the approved target to bypass a failure.

## Approval

Read/analysis only; no approval or Meta mutation at this step.

## Execution Log

The orchestrator records run, step and UTC timestamp. Include source timestamps, precise decisions and blockers; store receipts via the executor.

## Next Step

Scaling Proposal. Follow the CLI's returned route.
