---
name: meta-ads
description: Start manage ads, or handle a specific Meta Ads request. Use the brand's saved product assignments to run research, campaign creation, monitoring, optimization, and scaling through the lifecycle CLI.
---

# Meta Ads Lifecycle Orchestrator

## Start manage ads

Treat **Start manage ads** as a request to manage the full lifecycle for all products already assigned to the saved brand. Use `python -m ads manage --now`. If there is one saved brand, use it automatically. If the user specifies a narrower job or a product, follow that request. Use the saved product, market, policy and budget. Ask only when brand scope is ambiguous or a required decision is missing.

Reuse existing run records. Continue through strategy, paused creation, approved launch, ongoing review, optimization, scaling and replacement when the evidence calls for it. Respect existing approvals and decisions to stop a campaign. If an existing Meta campaign has no registered run, report that campaign and the duplicate safeguard. Do not create another campaign to get around it.

## Set up a fresh copy

Use `python -m ads init "BRAND NAME"` to create private setup files. Read the brand website, store, product title and IDs, currency, and approved media folder from the connected sources available to this agent. Match the storefront, store and ad account before saving them together. If there are multiple plausible stores, products or ad identities, ask the user to choose by name. Save technical identifiers in the setup files and leave credentials in their existing connections.

Ask only for decisions the evidence cannot supply, such as a missing spend limit, target market, permission to use a format, or who can authorize a change. Use confirmed brand settings on later requests. A request for an existing product can be just its name or link. Infer no spending authority from an example, and treat an unverified offer or claim as unavailable. Validate the filled setup before starting the workflow.

## Run the lifecycle

1. Load the user-supplied brand and product request using the [operator guide](../../../README.md) and [shared policy rules](../../../docs/policy.md). Validate scope, product and budget. Check saved runs before starting another campaign.
2. Start with `python -m ads run REQUEST.json --brand BRAND.json --now`. Use the worker for due steps and the dispatcher for authorized proposals. The workflow selects one skill per step and stores structured evidence. Isolate simulations in a separate database.
3. Build one strategy per cycle and record its hypothesis, test and review criteria. On replacement or scheduled strategy refresh, read the prior strategy and its results. Keep routine tests and scale evaluations on the current strategy.
4. Prepare the exact proposal and present its ID, scope and impact when policy approval is due. The protected operator process executes authorized changes and verifies readback.
5. Report the outcome, evidence, Meta IDs where available and next review or exact blocker. Use `python -m ads events RUN_ID` to inspect the audit log and strategy cycle records.
