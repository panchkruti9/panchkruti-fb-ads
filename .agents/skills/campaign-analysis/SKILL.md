---
name: campaign-analysis
description: "Determine whether the current campaign is meeting the current strategy and identify the most likely limiting factor."
---

## Skill Name

Campaign Analysis

## Purpose

Determine whether the current campaign is meeting the current strategy and identify the most likely limiting factor.

## Trigger

Run only when the lifecycle orchestrator selects `campaign-analysis`.

## Required Inputs

Audience Analysis result and relevant earlier evidence. Read the selected run, product, strategy and campaign target as applicable.

## Required Files

`.agents/skills/meta-ads/references/policy.md`, the effective brand policy, and the orchestrator's referenced result records. For execution or handoff, also read `README.md`.

## Tools & APIs

Current strategy and saved performance, business, creative and audience analysis.

## Instructions

Read [the practical decision guide](references/decision-guide.md) before preparing this step.

1. Read the exact strategy version and launch/change history, then line up Meta delivery, Shopify data and the approved evaluation window. Label periods affected by creative, funding, promotion, inventory or measurement changes.
2. Trace performance from eligible delivery to product visits, checkout and retained paid orders, only joining rates with valid denominators. Strong visits and falling checkout completion warrant checking fees, stock or payment before blaming creative. Rising Meta purchases with weakening Shopify matches warrants checking tags and lag before concluding actual sales rose or fell.
3. Compare actual outcomes with the original hypothesis and decision metric. Record the strongest explanation, a plausible alternative and the cheapest check that would distinguish them. Separate verified defects from broad strategy failure.

## Rules

An expired strategy must be reviewed before continuing. Apply the shared operating rules.

## Decision Logic

Hand Optimize a specific recommendation and its confidence. When the main buyer, offer or business hypothesis has failed after a mature review, state what the next strategy must reconsider.

## Output

Compare performance to strategy and business constraints; save the findings as a step result with dated source references.

## Output Schema

The envelope uses `status`, `summary`, `evidence`, `data` and, for a blocked or limited result, `blockers`. Required `data` keys: `goal_comparison`, `health`, `issues`, `recommendations`. See the operator guide for types and special cases.

## Validation

Verify references, dates, scope and required fields. Reconcile contradictions. Check that conclusions follow from the evidence and list limitations before submission.

## Error Handling

Record the failed source or step and the next concrete action. Retry transient reads within provider limits. Do not retry an ambiguous write or change the approved target to bypass a failure.

## Approval

Read/analysis only; no approval or Meta mutation at this step.

## Execution Log

The orchestrator records run, step and UTC timestamp. Include source timestamps, precise decisions and blockers; store receipts via the executor.

## Next Step

Optimization Decision. Follow the CLI's returned route.
