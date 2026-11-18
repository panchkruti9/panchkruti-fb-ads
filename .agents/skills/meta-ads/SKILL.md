---
name: meta-ads
description: Start manage ads, or handle a specific Meta Ads request. Use the brand's saved product assignments to run research, campaign creation, monitoring, optimization, and scaling through the lifecycle CLI.
---

# Meta Ads Lifecycle Orchestrator

## Start manage ads

Treat **Start manage ads** as a request to manage the full lifecycle for the saved brand's assigned products. Use `python -m ads manage --connected`. Use the saved product, market, policy and budget. Follow any narrower scope in the user's request.

Reuse existing run records. Continue through strategy, paused creation, approved launch, ongoing review, optimization, scaling and replacement when the evidence calls for it. Respect existing approvals and decisions to stop a campaign. When `next` reports an existing campaign, collect the requested Shopify product read. The lifecycle registers a verified paused draft where the account, ad destinations and assigned product variant match. Follow the returned draft-review step on the same run.

## Set up a fresh copy

Use `python -m ads init "BRAND NAME"` to create private setup files. Read the brand website, store, product title and IDs, currency, and approved media folder from the connected sources available to this agent. Match the storefront, store and ad account before saving them together. If there are multiple plausible stores, products or ad identities, ask the user to choose by name. Save technical identifiers in the setup files and leave credentials in their existing connections.

Reuse confirmed brand settings. Validate the filled setup against the shared policy before starting the workflow.

## Run the lifecycle

1. Load the user-supplied brand and product request using the [operator guide](../../../README.md) and [shared policy rules](../../../docs/policy.md). Validate scope, product and budget. Check saved runs before starting another campaign.
2. For a specific new run, use `python -m ads run REQUEST.json --brand BRAND.json --connected`. Follow `python -m ads next RUN_ID` for each due run. Handle Shopify, storefront, Drive and research work using the agent's connected tools and [connected step contract](../../../docs/contracts.md#connected-agent-steps). Send Meta operations to the Meta worker. The lifecycle selects the current skill and stores evidence. Use a separate database for simulations.
3. Build one strategy per cycle and record its hypothesis, test and review criteria. On replacement or scheduled strategy refresh, read the prior strategy and its results. Keep routine tests and scale evaluations on the current strategy.
4. Before asking for approval, run `python -m ads operator-check RUN_ID` on the intended Meta execution host. If setup is required, keep the saved proposal and report setup as the next action. Ask only for an identity or access decision the user must make. Once configured, use the exact proposal and any recorded decision. The protected operator executes authorized changes and verifies readback.

## Keep work moving and update the user

Resolve routine issues using saved evidence, the connected tools and the alternatives allowed by the selected skill. If one creative uses an unsupported claim, check the other approved assets or revise the concept around a verified product fact. Keep doing the work that can proceed when another step is waiting.

Ask the user only for a decision, required help that the agent cannot supply, or a policy-required approval. Ask one concrete question and say what the answer will unlock. Present the exact proposal and its impact for approval.

At meaningful milestones, report **Done**, **Waiting**, and **Next** in plain language. Omit empty items. Say whether the agent, a scheduled check, or the user owns the next action. Use the saved logs for diagnostics and surface technical details when the user needs them to act. Report a Meta change as done after verified readback.

## Continue on a schedule

On wake or a scheduled check, start with `python -m ads manage --connected` to import the Meta worker's encrypted snapshots and reuse the saved runs. Follow `next` for each due review. Use the eligible Meta reporting dates returned by the lifecycle and read Shopify for those same dates. One due review uses the current evidence across the missed days. Handle Shopify and Drive through their plugins. Use the protected Meta dispatcher for existing approved work only.
