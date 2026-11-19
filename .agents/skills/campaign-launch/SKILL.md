---
name: campaign-launch
description: Verify a paused Meta build, prepare the exact launch decision and establish its first monitoring window.
---

# Campaign Launch

Use after Campaign Build at the internal `activation-check` step. Read the saved build receipt, selected strategy, effective brand policy and [launch checks](references/checks.md).

A successful paused build proves object creation. Launch additionally needs the correct destination, a usable checkout, verified Purchase source, appropriate previews and approved spend authority. Match campaign, ad set and ad IDs to the saved receipt. Verify crop, text, URL and CTA in each intended placement. A preview API response alone does not prove visual quality. The launch worker first collects live evidence automatically: the selected account-owned pixel, Purchase event statistics, Purchase optimization settings, installed storefront pixel, the assigned variant's checkout navigation, previews and account spending control. Use `meta-ads gateway RUN_ID --operation launch-audit` to inspect independent Meta checks. Shopify plugin availability distinguishes an untracked zero quantity from a sold-out product. Do not request a new paid test order by default. Store-wide Purchase activity proves source activity, not an exact-product sale or verified deduplication; retain that limitation. A specific failed check is investigated before requesting user help.

Keep brand-owned approved artwork intact when suitable. For newly written copy or generated visuals check product accuracy, ordinary benefit wording, prohibited personal assertions and misleading promises. Use actual Meta review status when returned; platform approval is not proof of business performance.

Submit the checkpoint fields returned by the lifecycle: `destination_ok`, `purchase_event_ok`, `checkout_ok`, `preview_checks`, `tracking_reference`, `spend_control_reference`. Explain the evidence behind any false value. A technical failure has a concrete recovery action; do not ask the owner to invent technical IDs or repeat an existing approval.

The next `activate` proposal identifies exact objects, settings and spend. Show that completed proposal and request the saved policy's required owner approval. Execute through the same protected Meta gateway. Reconcile partial results; never activate a replacement campaign as a workaround. Report configured status and effective delivery separately after exact readback.

On verified activation, save the first review time, account timezone, reporting lag and unchanged strategy criteria. Record the launch and next check in the readable campaign log. Continue monitoring through the orchestrator.


If the account spending limit is exhausted or unsuitable, prepare the exact bounded account-wide change inside the launch proposal. Show its existing/new limit, additional allowance and campaign daily budget. Require the owner's explicit approval once for the combined proposal. Never silently raise or delete the account limit, reset the spend counter, or describe the account-wide change as applying only to this campaign. An empty owner whitelist uses the current user's recorded explicit approval; populated whitelists remain enforced.

Before activation the executor records a campaign-scoped spend baseline. Only verified activation starts the AGI budget clock. Keep first observed delivery separate, preserve the baseline on retries, and exclude pre-start or other-campaign spending. The campaign log must show these values and the next check. A temporary Insights failure records unknown spend for agent reconciliation; it does not create a new owner questionnaire or fabricate zero.
