"""Explain evidence readiness without equating missing attribution with zero demand."""
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from .meta import account_zone, policy
from .state import comparison_anchor, now, parse_time


def assess(run):
    criteria = run.get("records", {}).get("strategy-development", {}).get("data", {}).get("criteria", {})
    report = run.get("review_evidence", {})
    meta = report.get("meta", {}).get("current") or {}
    shop = report.get("shopify", {}).get("current") or {}
    result = {"state": "inconclusive", "reason": "Comparable Meta and Shopify evidence is not available.",
              "spend_minor": None, "matched_orders": None, "product_orders": None,
              "matching_coverage": None, "decision_ready": False, "next_condition": "Collect scoped reporting evidence."}
    if not report and run.get("live_since") and run.get("status") == "monitoring":
        due = run.get("next_review_at")
        pending = bool(due and parse_time(due) > now())
        result.update(state="maturing" if pending else "inconclusive",
            reason="The next purchase review is scheduled; comparable reporting will be collected when it is due." if pending else
                   "The purchase review is due; collecting the reporting evidence is the agent's next task.",
            next_condition="Collect complete post-delivery Meta and Shopify dates at the due connected-agent review, allowing for reporting lag.")
    elif not report and not run.get("live_since"):
        result.update(reason="Research and preparation are in progress; purchase performance has not been measured yet.",
                      next_condition="Complete the selected lifecycle task and verify delivery before judging purchases.")
    issue = run["request"].get("facts", {}).get("operational_issue", {})
    if issue.get("verified") is True and issue.get("target_id") == run.get("meta", {}).get("id"):
        try:
            observed = parse_time(issue["observed_at"])
            changed = run.get("last_material_change_at") or run.get("live_since")
            current = observed <= now() and (not changed or observed >= parse_time(changed))
        except (KeyError, ValueError, TypeError):
            current = False
        if current and issue.get("reference") and issue.get("kind") in {"checkout", "tracking", "availability", "spend_limit", "policy"}:
            return {**result, "state": "operational-fault", "reason": issue["kind"],
                    "next_condition": "Repair or pause the affected delivery and verify the result."}
    try:
        start, end = date.fromisoformat(meta["start"]), date.fromisoformat(meta["end"])
        if (meta["start"], meta["end"]) != (shop["start"], shop["end"]):
            return result
        rows = meta.get("rows", {}).get("campaign", [])
        if len(rows) != 1 or rows[0].get("campaign_id", run["meta"]["id"]) != run["meta"]["id"]:
            return result
        scale = policy(run["request"].get("brand"))["minor_per_unit"]
        spend = Decimal(str(rows[0]["spend"])) * scale
        if not spend.is_finite() or spend < 0:
            return result
        metric = "matched_first_time_buyers" if run["request"].get("success_metric") == "first_time_buyers" else "matched_orders"
        orders = shop[metric]
        if type(orders) is not int or orders < 0:
            return result
        product_orders = shop.get("paid_product_orders")
        result.update(spend_minor=int(spend), matched_orders=orders, product_orders=product_orders)
        matched = shop.get("matched_orders")
        if type(product_orders) is int and product_orders > 0 and type(matched) is int:
            result["matching_coverage"] = min(1.0, matched / product_orders)
        changed = comparison_anchor(run)
        if run["request"].get("brand") and (not run.get("campaign_configuration") or report.get("configuration") != run["campaign_configuration"]):
            return {**result, "reason": "Campaign settings changed or have not been verified."}
        first_delivery = run.get("campaign_ledger", {}).get(run["meta"]["id"], {}).get("first_delivery_on")
        cutoff = now().astimezone(account_zone(report.get("account_timezone", "UTC"))).date() - timedelta(days=1 + criteria["lag_days"])
        if (end > cutoff or not 1 <= (end-start).days + 1 <= criteria["window_days"] or not changed
                or start <= parse_time(changed).astimezone(account_zone(report.get("account_timezone", "UTC"))).date()
                or (first_delivery and start <= date.fromisoformat(first_delivery))):
            return {**result, "state": "maturing", "reason": "The comparable post-delivery window or reporting lag is incomplete.",
                    "next_condition": "Wait for complete comparable dates and the recorded reporting lag."}
        if shop.get("pending_journey", 0):
            return {**result, "reason": "Order journeys are still pending; missing matches are not zero sales."}
        if orders == 0 and type(product_orders) is int and product_orders > 0:
            known_returning = (metric == "matched_first_time_buyers" and shop.get("matched_orders") == product_orders
                               and shop.get("matched_returning_buyers") == product_orders
                               and shop.get("matched_buyer_history_unknown") == 0)
            if not known_returning:
                return {**result, "reason": "Product sales exist without qualified campaign matches; diagnose attribution and buyer coverage."}
        if run["request"].get("facts", {}).get("tracking", {}).get("purchase_verified") is not True:
            return {**result, "reason": "Purchase measurement is not verified."}
        minimum = criteria["minimum_matched_orders"]
        target = criteria.get("maximum_cpa_minor")
        # A learning allowance is an explicit loss bound, never an invented viable CPA.
        allowance = criteria.get("learning_spend_minor") or run["request"].get("test_budget_minor")
        exposure = target * minimum if target else allowance
        if orders >= minimum or (exposure and spend >= exposure):
            return {**result, "state": "usable-evidence", "decision_ready": True,
                    "reason": "The comparable window has qualified outcomes or reached its documented exposure bound.",
                    "next_condition": "Diagnose the constraint and choose a supported action; this is not proof of causation or profit."}
        return {**result, "state": "underexposed", "reason": "Delivery has not answered the purchase question; zero matches alone do not establish failure.",
                "next_condition": "Continue within authority or revise the explicitly bounded learning plan."}
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return result


def business_summary(run):
    assessed = assess(run)
    shop = run.get("review_evidence", {}).get("shopify", {}).get("current", {}) or {}
    metric = run["request"].get("success_metric", "paid_orders")
    meta = run.get("review_evidence", {}).get("meta", {}).get("current", {}) or {}
    rows = meta.get("rows", {}).get("campaign", [])
    attributed, action_type = None, None
    actions = rows[0].get("actions", []) if len(rows) == 1 else []
    for kind in ("offsite_conversion.fb_pixel_purchase", "purchase"):
        candidates = [a for a in actions if a.get("action_type") == kind]
        if len(candidates) == 1:
            try:
                amount = Decimal(str(candidates[0]["value"]))
                if amount.is_finite() and amount >= 0:
                    attributed, action_type = str(amount), kind
                    break
            except (KeyError, ValueError, InvalidOperation):
                pass
    cash = shop.get("product_cash", {}).get(metric, {})
    receipts = cash.get("received_less_refunds_and_tax_minor") if cash.get("unallocated_orders") == 0 else None
    economics = run["request"].get("facts", {}).get("economics", {})
    windows = [x for x in economics.get("windows", []) if (x.get("start"), x.get("end")) == (shop.get("start"), shop.get("end"))]
    costs, contribution = None, None
    scoped = (economics.get("source") and economics.get("product_id") == run["request"]["product_id"]
              and economics.get("variant_id") == run["request"].get("variant_id")
              and economics.get("campaign") == run.get("meta", {}).get("name")
              and economics.get("success_metric") == metric)
    if scoped and len(windows) == 1:
        row = windows[0]
        fields = [row.get(k) for k in ("product_cost_minor", "shipping_fulfillment_minor", "fees_minor")]
        if all(type(v) is int and v >= 0 for v in fields):
            costs = sum(fields)
            if row.get("verified_product_net_receipts_minor") is not None:
                receipts = row["verified_product_net_receipts_minor"]
            if type(receipts) is int and assessed["spend_minor"] is not None:
                contribution = receipts - costs - assessed["spend_minor"]
    return {"metric": metric, "start": shop.get("start"), "end": shop.get("end"),
            "qualified_outcomes": assessed["matched_orders"], "paid_product_orders": assessed["product_orders"],
            "matched_net_receipts_minor": receipts, "variable_costs_minor": costs,
            "contribution_after_ads_minor": contribution, "matching_coverage": assessed["matching_coverage"],
            "basis": "Qualified Shopify matched outcomes after refunds/tax and verified costs; not incremental profit.",
            "meta_attributed_purchases": attributed, "meta_purchase_action_type": action_type,
            "meta_attribution_basis": meta.get("attribution"),
            "freshness": shop.get("observed_at")}
