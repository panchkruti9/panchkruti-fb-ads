---
name: campaign-launch
description: Verify a paused Meta build, prepare the exact launch decision and establish its first monitoring window.
---

# Campaign Launch

Use after Campaign Build at the internal `activation-check` step. Read the saved build receipt, selected strategy, effective brand policy and [launch checks](references/checks.md).

A successful paused build proves object creation. Launch additionally needs the correct destination, usable checkout and stock, verified Purchase source, exact rendered previews and approved spend authority. Match campaign, ad set and ad IDs to the saved receipt. Verify crop, text, URL and CTA in each intended placement. A preview API response alone does not prove visual quality. Collect missing storefront or checkout evidence through the connected agent; GitHub handles Meta preview and configuration reads.

Keep brand-owned approved artwork intact when suitable. For newly written copy or generated visuals check product accuracy, ordinary benefit wording, prohibited personal assertions and misleading promises. Use actual Meta review status when returned; platform approval is not proof of business performance.

Submit the checkpoint fields returned by the lifecycle: `destination_ok`, `purchase_event_ok`, `checkout_ok`, `preview_checks`, `tracking_reference`, `spend_control_reference`. Explain the evidence behind any false value. A technical failure has a concrete recovery action; do not ask the owner to invent technical IDs or repeat an existing approval.

The next `activate` proposal identifies exact objects, settings and spend. Show that completed proposal and request the saved policy's required owner approval. Execute through the same protected Meta gateway. Reconcile partial results; never activate a replacement campaign as a workaround. Report configured status and effective delivery separately after exact readback.

On verified activation, save the first review time, account timezone, reporting lag and unchanged strategy criteria. Record the launch and next check in the readable campaign log. Continue monitoring through the orchestrator.
