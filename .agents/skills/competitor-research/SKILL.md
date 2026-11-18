---
name: competitor-research
description: "Identify credible ways the brand can present its offer differently from alternatives a buyer would actually consider."
---

## Skill Name

Competitor Research

## Purpose

Identify credible ways the brand can present its offer differently from alternatives a buyer would actually consider.

## Trigger

Run only when the lifecycle orchestrator selects `competitor-research`.

## Required Inputs

Customer Research result and relevant earlier evidence. Read the selected run, product, strategy and campaign target as applicable.

## Required Files

`.agents/skills/meta-ads/references/policy.md`, the effective brand policy, and the orchestrator's referenced result records. For execution or handoff, also read `README.md`.

## Tools & APIs

Public web search and competitor product pages.

## Instructions

1. Search by the shopper’s use case, destination country and product form. Include direct alternatives and relevant substitutes, such as a single product instead of a bundle. Record why each alternative belongs in the comparison. Open its product and offer pages and date the observations.
2. Compare the real bundle contents, market, price per unit where comparable, shipping and offer conditions where visible, opening promise, and visible proof. Note checkout-only terms as unverified until checked. Attribute each outcome claim to the advertiser.
3. Turn a difference into a testable opportunity only if Product Research confirms the brand can demonstrate it. For example, lead with verified routine clarity if comparable products leave the sequence unclear and Customer Research shows that confusion matters.

## Rules

Absence from a search result is not evidence of absence. Apply the shared operating rules.

## Decision Logic

Keep a market gap as a hypothesis until supported by customer or account evidence. Public prices and messaging can support differentiation. They leave demand and profitability unverified.

## Output

Find positioning opportunities grounded in observable market evidence; save the findings as a step result with dated source references.

## Output Schema

The envelope uses `status`, `summary`, `evidence`, `data` and, for a blocked or limited result, `blockers`. Required `data` keys: `competitors`, `offers`, `messaging`, `creative_patterns`, `opportunities`. See the operator guide for types and special cases.

## Validation

Verify references, dates, scope and required fields. Reconcile contradictions. Check that conclusions follow from the evidence and list limitations before submission.

## Error Handling

Record the failed source or step and the next concrete action. Retry transient reads within provider limits. Do not retry an ambiguous write or change the approved target to bypass a failure.

## Approval

Read/analysis only; no approval or Meta mutation at this step.

## Execution Log

The orchestrator records run, step and UTC timestamp. Include source timestamps, precise decisions and blockers; store receipts via the executor.

## Next Step

Meta Ad Library Research. Follow the CLI's returned route.
