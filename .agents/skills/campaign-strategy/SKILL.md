---
name: campaign-strategy
description: "Translate the current version of the advertising strategy into a Meta campaign structure the executor can build."
---

## Skill Name

Campaign Strategy

## Purpose

Translate the current version of the advertising strategy into a Meta campaign structure the executor can build.

## Trigger

Run only when the lifecycle orchestrator selects `campaign-strategy`.

## Required Inputs

Read the run request and `strategy-development` for the approved product, business goal, purchase-cost target, and review criteria. Use saved product and customer research for Shopify evidence. Record the dates and scope of the evidence.

## Required Files

`.agents/skills/meta-ads/references/policy.md`, the effective brand policy, and the orchestrator's referenced result records. For execution or handoff, also read `README.md`.

## Tools & APIs

Read `account_report` for managed campaigns and ad sets. Read `account_budget_before` for account-wide spending and commitments.

## Instructions

For a new or low-data account, read [first-campaign decisions](../strategy-development/references/first-campaign-decisions.md). Carry forward the chosen buyer, message, audience and review rationale. Explain what each campaign or ad set will teach at the available allocation.

1. Read the current strategy’s goal, test and review criteria. For the supported website Sales recipe, use `OUTCOME_SALES`, verify the website Purchase source is attached to the correct account and store, and capture any activation checks that remain open. Preserve the distinction between the business outcome and Meta’s delivery event.
2. Compare eligible same-product ad sets on market, destination, Purchase source, funding and business objective. Use the matching verified ad set for a creative addition, with its exact IDs and existing settings. Build a distinct campaign when a separate budget, event or delivery condition is material to the strategy.
3. Estimate test volume from comparable spend and CPA. Use the saved daily and monthly limits. If the request includes a test budget, keep daily allocation × review window within it. Use the requested daily amount when supplied and respect the allowed formats and placements. Use shared campaign funding when delivery may allocate across eligible sets. Assign separate ad set budgets where the design needs independent funding. If randomization is necessary, verify experiment and executor support. A second budget alone does not make a randomized test.
4. Return the exact naming key, account, structure, existing IDs when applicable, budget level and minor currency units amount, and the inherited success criteria. Check all active account commitments and projected cap exposure before proposing a new build.

Use Purchase for website Sales. When expected conversion volume is low, first check the event and checkout, then model how much evidence each split could produce at the proposed spend. Consolidate the plan when separate ad sets have no decision to answer. Earlier funnel events diagnose the reason sales are low. A separate optimization-event test needs its own hypothesis and supported build. Follow the purchase and learning guidance in the shared strategy knowledge.

## Rules

Do not force three separate campaigns to represent three stages. Apply the shared operating rules.

## Decision Logic

Use `planned_name` for a new build and `current_campaign_name` for additions. If that name already exists and the run is preparing a new build, record the existing campaign as the blocker. If the available setup would change the strategy's hypothesis, block with the reason and describe what Strategy Development needs to reconsider. The workflow controls the next step. [Meta Sales setup](https://www.facebookblueprint.com/student/activity/638511) · [Meta Marketing API](https://developers.facebook.com/documentation/ads-commerce/marketing-api)

## Output

Translate strategy into an executable campaign plan; save the findings as a step result with dated source references.

## Output Schema

The envelope uses `status`, `summary`, `evidence`, `data` and, for a blocked or limited result, `blockers`. Required `data` keys: `campaign_key`, `account_id`, `objective`, `structure`, `budget`, `success_criteria`. See the operator guide for types and special cases.

## Validation

Verify references, dates, scope and required fields. Reconcile contradictions. Check that conclusions follow from the evidence and list limitations before submission.

## Error Handling

Record the failed source or step and the next concrete action. Retry transient reads within provider limits. Do not retry an ambiguous write or change the approved target to bypass a failure.

## Approval

Read/analysis only; no approval or Meta mutation at this step.

## Execution Log

The orchestrator records run, step and UTC timestamp. Include source timestamps, precise decisions and blockers; store receipts via the executor.

## Next Step

Funnel Planning. Follow the CLI's returned route.
