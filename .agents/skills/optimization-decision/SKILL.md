---
name: optimization-decision
description: "Choose the next action for the current strategy using a mature result or a verified operational issue."
---

## Skill Name

Optimization Decision

## Purpose

Choose the next action for the current strategy using a mature result or a verified operational issue.

## Trigger

Run only when the lifecycle orchestrator selects `optimization-decision`.

## Required Inputs

Campaign Analysis result and relevant earlier evidence. Read the selected run, product, strategy and campaign target as applicable.

## Required Files

`.agents/skills/meta-ads/references/policy.md`, the effective brand policy, and the orchestrator's referenced result records. For execution or handoff, also read `README.md`.

## Tools & APIs

Current strategy, account facts and Optimize results.

## Instructions

Read [the practical decision guide](references/decision-guide.md) before preparing this step.

1. Read Campaign Analysis, the current strategy version and recorded stop criteria. Check evidence maturity, budget exposure, exact target and recent changes. A confirmed operational or spending problem can need action before the performance window matures.
2. Pick one action: HOLD for healthy or inconclusive delivery with a dated recheck, FIX for a verified defect, TEST for a falsifiable question within the current strategy, REFRESH for supported replacement of creative, PAUSE for a verified stop condition, RECREATE when the strategy’s underlying assumptions need a new cycle, or SCALE when qualified results favor more budget on the current strategy.
3. Attach the evidence and the enrolled campaign ID, explain what made the action preferable, and set `next_review_on`. A PAUSE decision may instead target a verified ad or ad set belonging to that campaign. For creative FIX, TEST or REFRESH, identify relevant ads in the rationale. Use `fix_kind: creative` only for a specific creative correction. For RECREATE, record which prior hypothesis failed and what must be learned first.

Read the learning snapshot as a delivery signal. Hold a healthy campaign while purchase data matures, even if it is learning. Act early on verified defects or breached safety limits. Use the shared strategy knowledge to distinguish creative changes within a campaign from a replacement strategy. Explain the expected learning impact and name the first comparable review window after a material change. The script holds performance-based PAUSE, RECREATE, TEST and REFRESH until a clean, lagged window has the strategy’s minimum order count or enough actual spend relative to its verified cost target and evidence threshold. Use the latter to decide whether to investigate zero or sparse orders. An early PAUSE needs a verified operational issue on the exact target or a measured spend-limit breach. It still runs through the existing approval policy.

## Rules

Do not scale from Meta-only evidence or manually blend Shopify totals with Meta attribution. Apply the shared operating rules.

## Decision Logic

When the current strategy hits its target but the results are immature, HOLD until the evidence threshold is met. A failed creative variation can warrant REFRESH. Repeated mature failure of the underlying offer or buyer premise warrants returning to Strategy Development.

## Output

Choose one evidence-bound action for the target; save the findings as a step result with dated source references.

## Output Schema

The envelope uses `status`, `summary`, `evidence`, `data` and, for a blocked or limited result, `blockers`. Required `data` keys: `decision`, `rationale`, `target_id`, `next_review_on`. See the operator guide for types and special cases.

## Validation

Verify references, dates, scope and required fields. Reconcile contradictions. Check that conclusions follow from the evidence and list limitations before submission.

## Error Handling

Record the failed source or step and the next concrete action. Retry transient reads within provider limits. Do not retry an ambiguous write or change the approved target to bypass a failure.

## Approval

Read/analysis only; no approval or Meta mutation at this step.

## Execution Log

The orchestrator records run, step and UTC timestamp. Include source timestamps, precise decisions and blockers; store receipts via the executor.

## Next Step

Optimization Execution. Follow the CLI's returned route.
