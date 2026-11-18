---
name: audience-planning
description: "Turn shopper hypotheses into targetable constraints and tests the account can actually deliver."
---

## Skill Name

Audience Planning

## Purpose

Turn shopper hypotheses into targetable constraints and tests the account can actually deliver.

## Trigger

Run only when the lifecycle orchestrator selects `audience-planning`.

## Required Inputs

Funnel Planning result and relevant earlier evidence. Read the selected run, product, strategy and campaign target as applicable.

## Required Files

`docs/policy.md`, the effective brand policy, and the orchestrator's referenced result records. For execution or handoff, also read `README.md`.

## Tools & APIs

Customer research and Meta read tools.

## Instructions

Use [first-campaign decisions](../../../../../../../docs/first-campaign-decisions.md) to connect the buyer hypothesis to supported Meta delivery controls. Explain why the selected scope fits this offer and spend, and which observation would make retargeting or another prospecting test useful.

1. Separate the buyer description used to write the ad from enforceable targeting. Use the requested countries and verified shipping coverage. Decide which other controls are essential to the hypothesis, and confirm them in the current account and API recipe.
2. Inspect eligible ad set targeting and placements. For additions retain the exact ad set, countries, placements and Purchase source. For new builds, check any required custom segment, suppression or Advantage+ control as a capability in the account and executor rather than treating a suggestion as a restriction.
3. Only split audiences when their delivery can be meaningfully compared and the budget can support each. Record the source for estimated audience size or overlap if available. Similar interest descriptions or two ad sets using the same geography only flag possible overlap.
4. Use the account's saved audience inventory. Keep a broad ad set when spend or warm volume is too thin. For retargeting, select an eligible website-visit, cart or engagement audience that you can verify from its definition and exclude the applicable purchaser audience when the strategy calls for it. Consider a lookalike only when its seed and usable size are verified. Record each planned ad set scope as `targeting_requirements.adset_audiences[exact_name]` with `mode` (`broad`, `retargeting`, or `lookalike`), `include` and `exclude` arrays of saved Meta IDs.

## Rules

Do not infer sensitive traits or use personal customer exports. Apply the shared operating rules.

## Decision Logic

Keep an audience broad when the creative is the test and geography and delivery controls satisfy the strategy. If an enforceable exclusion is required and unsupported, flag the capability gap. [Meta Marketing API audience and optimization guidance](https://developers.facebook.com/documentation/ads-commerce/marketing-api)

## Output

Design testable audiences that the account can target; save the findings as a step result with dated source references.

## Output Schema

The envelope uses `status`, `summary`, `evidence`, `data` and, for a blocked or limited result, `blockers`. Required `data` keys: `audiences`, `targeting_requirements`, `overlap`, `tests`. See the operator guide for types and special cases.

## Validation

Verify references, dates, scope and required fields. Reconcile contradictions. Check that conclusions follow from the evidence and list limitations before submission.

## Error Handling

Record the failed source or step and the next concrete action. Retry transient reads within provider limits. Do not retry an ambiguous write or change the approved target to bypass a failure.

## Approval

Read/analysis only; no approval or Meta mutation at this step.

## Execution Log

The orchestrator records run, step and UTC timestamp. Include source timestamps, precise decisions and blockers; store receipts via the executor.

## Next Step

Creative Concept. Follow the CLI's returned route.
