"""User-facing status and readable logs from committed records."""
import re
import uuid
from decimal import Decimal
from .meta import account_zone
from .state import REGISTRY, parse_time
from .ledger import summary as spend_summary


def clean(value):
    return " ".join(str(value).split()).replace("|", "&#124;")


def slug(value):
    return re.sub(r"[^a-z0-9-]+", "-", str(value).lower()).strip("-")[:120] or "campaign"


def money(run, value):
    if value is None:
        return "Awaiting verified spend readback"
    rules = (run["request"].get("brand") or {}).get("policy", {})
    scale = rules.get("minor_per_unit", 100)
    decimals = {1: 0, 100: 2, 1000: 3}[scale]
    return f"{rules.get('currency', 'currency')} {Decimal(value) / scale:,.{decimals}f}"


def local_time(value, zone):
    return parse_time(value).astimezone(zone).strftime("%d %b %Y %H:%M:%S %Z") if value else "Not recorded"


def readable_when(value, zone):
    return local_time(value, zone) if isinstance(value, str) and re.match(r"^\d{4}-\d{2}-\d{2}T", value) else clean(value)


def delivery_summary(run):
    target = run.get("meta", {}).get("id")
    candidates = []
    observed = run.get("delivery_observation", {})
    if observed.get("id") == target and observed.get("at"):
        candidates.append(observed)
    health = run.get("waiting_health", {})
    if health.get("id") == target and run.get("last_waiting_health_check"):
        candidates.append({**health, "at": run["last_waiting_health_check"]})
    receipt = run.get("last_receipt", {})
    for item in receipt.get("objects", []) + ([receipt] if receipt.get("id") == target else []):
        if item.get("id") == target and receipt.get("at"):
            candidates.append({**item, "at": receipt["at"]})
    result = max(candidates, key=lambda x: parse_time(x["at"])) if candidates else {}
    return {"configured_status": result.get("configured_status"), "effective_status": result.get("effective_status"), "observed_at": result.get("at")}


def describe(run):
    step, state = run["step"], run["status"]
    name = REGISTRY.get(step, {}).get("name") or step.replace("-", " ").title()
    proposal = run.get("proposal")
    public = {"monitoring": "scheduled", "blocked": "needs-attention", "execution_blocked": "needs-attention",
              "awaiting_approval": "waiting-for-approval", "paused": "completed", "stopped": "completed"}.get(state, "working")
    question = None
    if state == "monitoring":
        action, when, owner = "Compare the next complete Meta and Shopify reporting windows.", run.get("next_review_at"), "agent"
        if run.get("budget_pause"):
            action = "Review the new monthly allocation and delivery checks before resuming approved ads."
        elif run.get("management_pause"):
            action = "Review the saved pause reason and choose the next supported strategy or resumption."
        elif run.get("strategy_reconsideration", {}).get("required") is True:
            action = "Revisit the buying strategy and bounded learning plan using the saved review and current evidence."
    elif state == "awaiting_approval":
        action, when, owner = f"Review the {proposal['operation']} proposal and its impact.", "After approval", "user"
        question = f"Approve the displayed {proposal['operation']} proposal?"
        if (run["request"].get("brand") or {}).get("policy", {}).get("management_authority"):
            from .authority import owner_required
            if not owner_required(run, proposal):
                action, when, owner, question = "Complete operator authorization under the saved management instruction.", "Now", "agent", None
                public = "working"
        change = proposal.get("action", {}).get("spend_control_change")
        if change:
            rules = (run["request"].get("brand") or {}).get("policy", {})
            scale = rules.get("minor_per_unit", 100)
            decimals = {1: 0, 100: 2, 1000: 3}[scale]
            def money(value):
                return f"{rules.get('currency', 'currency')} {Decimal(value) / scale:,.{decimals}f}"
            action = (f"Launch at {money(proposal['impact']['daily_minor'])}/day and change the account-wide spending limit "
                      f"from {money(change['from_minor'])} to {money(change['to_minor'])}, "
                      f"leaving {money(change['remaining_minor'])} additional allowance.")
            question = "Approve this exact combined launch and account-wide spending-limit proposal?"
    elif state in {"approved", "execution_blocked"}:
        action, when, owner = "Resume the exact authorized Meta operation and verify its readback.", "Now", "agent"
    elif state == "blocked":
        action, when, owner = "Resolve the recorded issue and resume the same task.", "Now", "agent"
        help_request = run.get("help_request") or {}
        if help_request.get("owner") == "user" and help_request.get("question"):
            action, when, owner = help_request["question"], "After your answer", "user"
            question = help_request["question"]
    elif state in {"paused", "stopped"}:
        action, when, owner = "The campaign is paused. Resume management when requested.", "On request", "user"
    else:
        action, when, owner = f"Complete {name.lower()} and save the result.", "Now", "agent"
    receipt = run.get("last_receipt")
    labels = {"activate": "Verified campaign activation in Meta.", "build": "Saved and verified paused ads in Meta.",
              "pause": "Verified the pause in Meta.", "resume": "Verified delivery resumption in Meta.",
              "allocation": "Verified budget redistribution.", "budget": "Verified the approved budget update.",
              "audience": "Verified the audience operation."}
    done = labels.get(receipt["operation"], "Verified the Meta operation.") if receipt else "Saved research and decisions are listed below."
    from .assessment import assess
    assessment = assess(run)
    if state == "monitoring" and assessment["risk_review_required"] and not (run.get("budget_pause") or run.get("management_pause")):
        action, when, owner = "Review the reached learning allowance and choose a bounded next action or verified pause.", "Now", "agent"
    rationale = run.get("records", {}).get("optimization-decision", {}).get("data", {}).get("rationale")
    freshness = run.get("review_evidence", {}).get("meta", {}).get("current", {}).get("observed_at")
    return {"status": public, "current_task": name, "done": done, "next_action": action,
            "when": when, "owner": owner, "question": question, "attention": run.get("blockers", []),
            "reason": rationale or assessment["reason"], "due_condition": assessment["next_condition"],
            "learning_budget": assessment["learning_budget"],
            "earliest_purchase_review_at": assessment.get("earliest_purchase_review_at"),
            "data_freshness": freshness, "evidence_state": assessment["state"], "delivery": delivery_summary(run),
            "execution_condition": "At the next available connected-agent wake after the review becomes eligible."}


def campaign_path(store, run):
    brand = (run["request"].get("brand") or {}).get("brand_id", "brand")
    return store.logs_dir / slug(brand) / (slug(run["request"]["name"]) + ".md")


def render(store, run):
    zone = account_zone(run.get("review_evidence", {}).get("account_timezone", "UTC"))
    status = describe(run)
    ledger = spend_summary(run)
    if ledger["entries"] and ledger["entries"][0].get("baseline"):
        zone = account_zone(ledger["entries"][0]["baseline"]["timezone"])
    lines = ["# " + clean(run["request"].get("product_name", run["request"]["name"])), "",
             f"**Status** — {status['status']}", f"**Current task** — {status['current_task']}",
             f"**Done** — {status['done']}", f"**Next** — {status['next_action']}",
             f"**When** — {readable_when(status['when'], zone)}", f"**Responsible** — {status['owner']}", ""]
    delivery = status["delivery"]
    lines.extend([f"**Last verified delivery** — configured {delivery['configured_status'] or 'Unknown'}, effective {delivery['effective_status'] or 'Unknown'}; observed {local_time(delivery['observed_at'], zone)}.", ""])
    from .assessment import assess, business_summary
    measured = assess(run)
    business = business_summary(run)
    current = run.get("review_evidence", {}).get("shopify", {}).get("current", {}) or {}
    contract = run.get("records", {}).get("strategy-development", {}).get("data", {}).get("decision_contract", {})
    lines.extend(["## Purchases and current decision", "",
                  f"- Evidence: {clean(measured['state'])}. {clean(status['reason'])}",
                  f"- Product paid orders: {current.get('paid_product_orders', 'Unknown')}; qualified campaign outcomes: {measured['matched_orders'] if measured['matched_orders'] is not None else 'Unknown'}.",
                  f"- Meta-attributed purchases: {business['meta_attributed_purchases'] if business['meta_attributed_purchases'] is not None else 'Unknown'} ({business['meta_purchase_action_type'] or 'action not returned'}); attribution: {clean(business['meta_attribution_basis'] or 'Not recorded')}.",
                  f"- Matching coverage: {measured['matching_coverage'] if measured['matching_coverage'] is not None else 'Unknown'}; unmatched sales are not assigned to advertising automatically.",
                  f"- Reporting last observed: {status['data_freshness'] or 'Not recorded'}.",
                  f"- Matched net receipts: {money(run, business['matched_net_receipts_minor']) if business['matched_net_receipts_minor'] is not None else 'Unknown'}; contribution after ads: {money(run, business['contribution_after_ads_minor']) if business['contribution_after_ads_minor'] is not None else 'Unknown — incomplete economics'}. This is not measured incremental profit.",
                  f"- Current buying question: {clean(contract.get('test_question', 'See saved strategy; not yet recorded in the new decision contract.'))}",
                  f"- Next decision condition: {clean(status['due_condition'])}", ""])
    learning = status["learning_budget"]
    if learning["limit_minor"] is not None:
        lines.extend(["## Bounded learning", "",
                      f"- Recorded allowance: {money(run, learning['limit_minor'])}; verified exposure: {money(run, learning['spent_minor']) if learning['spent_minor'] is not None else 'Unknown'}; remaining: {money(run, learning['remaining_minor']) if learning['remaining_minor'] is not None else 'Unknown'}.",
                      f"- Basis: {clean(learning['basis'])} Observed {local_time(learning['observed_at'], zone)}.",
                      "- Allowance reached: agent decision required now. This does not prove the ad failed." if learning['reached'] else
                      "- The allowance limits the learning question; it is not additional spending authority or a profitable CPA target.", ""])
    if status.get("earliest_purchase_review_at"):
        lines.extend([f"**Earliest clean purchase review** — {local_time(status['earliest_purchase_review_at'], zone)}. Useful exposure and verified measurement are still required; operational checks can happen sooner.", ""])
    if run.get("strategy_cycles"):
        lines.extend(["## Previous strategy learning", ""])
        for cycle in run["strategy_cycles"]:
            prior = cycle.get("strategy", {}).get("data", {})
            hypothesis = prior.get("decision_contract", {}).get("test_question") or prior.get("creative_directions", "See archived research")
            outcome = cycle.get("results", {}).get("optimization-decision", {}).get("data", {}).get("rationale", cycle.get("reason"))
            lines.append(f"- {clean(cycle.get('closed_at'))}: {clean(hypothesis)} → {clean(outcome)}")
        lines.append("")
    batch = run.get("meta", {}).get("pending_batch") or {}
    daily = batch.get("daily_minor") or run["request"].get("daily_budget_minor")
    active_entry = run.get("campaign_ledger", {}).get(run.get("meta", {}).get("id"), {})
    daily = active_entry.get("daily_budget_minor", daily)
    lines.extend(["## AGI start and campaign spending", "",
                  "| Item | Recorded value |", "|---|---|",
                  f"| AGI launch verified | {local_time(ledger['launch_verified_at'], zone) if ledger['started'] else 'Not started'} |",
                  f"| First observed delivery | {ledger['first_delivery_on'] or 'Not observed'} |",
                  f"| Spend since AGI start | {money(run, ledger['spent_since_start_minor'])} |",
                  f"| AGI campaign spend this month | {money(run, ledger['spent_month_minor'])} |",
                  f"| Configured daily budget | {money(run, daily) if daily is not None else 'Not configured'} |",
                  f"| Spend last refreshed | {local_time(ledger['last_observed_at'], zone) if ledger['started'] else local_time(run.get('prelaunch_spending', {}).get('observed_at'), zone) if run.get('prelaunch_spending') else 'Budget clock has not started'} |",
                  f"| Review eligible from | {local_time(run.get('next_review_at'), zone) if run.get('next_review_at') else 'Scheduled after verified launch'} |", "",
                  "Review eligibility is followed by the next available connected-agent wake; it is not a guarantee that a closed host runs at that exact second.", "",
                  "AGI spending uses the exact managed campaign and subtracts its pre-start baseline. Earlier account spending is shown separately. Launch verification is a timestamp; first delivery is a Meta reporting date when only daily evidence is available.", ""])
    if ledger["legacy_baseline_missing"]:
        lines.extend(["Existing launch history has no saved spend baseline. Its AGI spend remains unknown until reconciled; it is not reset to zero.", ""])
    for issue in ledger["issues"]:
        lines.append("- Accounting needs agent attention: " + clean(issue))
    if ledger["entries"]:
        lines.extend(["", "| Managed campaign | Launch verified | First delivery | Since start | Current month |", "|---|---|---|---|---|"])
        for entry in ledger["entries"]:
            month_spent = entry.get('spent_month_minor') if entry.get('month') == ledger['month'] else None
            lines.append(f"| {clean(entry['name'])} | {local_time(entry.get('launch_verified_at'), zone)} | {entry.get('first_delivery_on') or 'Not observed'} | {money(run, entry.get('spent_since_start_minor'))} | {money(run, month_spent)} |")
        lines.append("")
    cap = run.get("account_control") or run["request"].get("facts", {}).get("spend_control", {})
    billing = run.get("billing_observation") or {}
    if billing.get("is_prepay_account"):
        lines.extend(["## Meta prepaid funding — separate from AGI spending", "",
                      "- Verified funding: " + clean(billing.get("available_balance_display", "Unknown")) + ".",
                      "- Last checked: " + local_time(billing.get("observed_at"), zone) + ".",
                      "- Meta rejected the attempted account-limit change because this is a prepaid account. Funding must use its supported prepaid payment flow.",
                      "- Earlier account spending does not become this campaign's AGI spend.", ""])
    elif cap.get("amount_spent") is not None:
        counter, limit = int(cap["amount_spent"]), int(cap.get("spend_cap", 0))
        lines.extend(["## Meta account control — separate from AGI spending", "",
                      f"- Account spending-counter reading: {money(run, counter)}.",
                      f"- Account-wide spending limit: {money(run, limit) if limit else 'No account limit returned'}.",
                      f"- Last checked: {local_time(cap.get('observed_at'), zone)}.",
                      "- This counter includes other or earlier advertising; it does not become this campaign's AGI spend.", ""])
        if limit and limit <= counter:
            lines.extend(["Meta's account limit is exhausted. Starting a new AGI budget clock does not reset this platform limit. Its exact proposed change is included in the existing launch decision.", ""])
    if status["attention"]:
        lines.extend(["## Needs attention", ""] + ["- " + clean(x) for x in status["attention"]] + [""])
    if status["question"]:
        lines.extend(["**Your decision** — " + status["question"], ""])
    target = run.get("meta", {})
    if target.get("id"):
        account = run["request"]["account_id"]
        lines.extend([f"[Open the saved campaign in Meta](https://adsmanager.facebook.com/adsmanager/manage/campaigns?act={account}&selected_campaign_ids={target['id']})", ""])
    lines.extend(["## Skill findings", "", "| Skill | Result | Recorded | Decision or finding |", "|---|---|---|---|"])
    for skill, record in sorted(run["records"].items(), key=lambda x: str((x[1].get("recorded_at") or "") if isinstance(x[1], dict) else "")):
        record = record if isinstance(record, dict) else {"status": "unavailable", "summary": str(record)}
        data = record.get("data") if isinstance(record.get("data"), dict) else {}
        summary = record.get("summary") or ("Verified executor receipt" if data.get("receipt") else "")
        lines.append(f"| {skill} | {record.get('status', 'unknown')} | {clean(record.get('recorded_at', ''))} | {clean(summary)} |")
    lines.extend(["", "## Decisions and activity", "", f"Times use {zone}.", "",
                  "| Time | Event | Detail |", "|---|---|---|"])
    for event in store.events(run["id"]):
        payload = event["payload"]
        payload = payload if isinstance(payload, dict) else {"detail": str(payload)}
        result = payload.get("result")
        result = result if isinstance(result, dict) else {}
        detail = result.get("summary") or payload.get("reason") or payload.get("reference") or payload.get("detail")
        if event["kind"] == "execution_verified" and payload.get("operation") == "activate":
            detail = "AGI launch verified. Campaign accounting starts from its saved pre-launch baseline; delivery is checked separately."
        elif event["kind"] == "agi_spend_updated":
            detail = ("AGI spend since start: " + money(run, payload.get("spent_since_start_minor"))
                      + "; current month: " + money(run, payload.get("spent_month_minor")))
        if not detail:
            detail = " / ".join(str(payload[key]) for key in ("step", "operation", "next", "next_action") if payload.get(key))
        try:
            at = parse_time(event["at"]).astimezone(zone).strftime("%d %b %Y %H:%M:%S")
        except (ValueError, TypeError):
            at = clean(event.get("at", "Time unavailable"))
        lines.append(f"| {at} | {event['kind']} | {clean(detail or '')} |")
    lines.extend(["", "## Strategy history", ""])
    for cycle in run.get("strategy_cycles", []):
        lines.append("- " + clean(cycle.get("reason", "Previous cycle")) + " — " + clean(cycle.get("strategy", {}).get("summary", "")))
    return "\n".join(lines) + "\n"


def atomic_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + "." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def write_logs(store):
    rows = ["# Meta Ads activity", "", "Open a campaign for its decisions, results and full history.", "",
            "| Campaign | Status | AGI launch | Spend since start | Qualified outcomes | Contribution after ads | Next action | When | Responsible |", "|---|---|---|---|---|---|---|---|---|"]
    for run in store.list():
        path = campaign_path(store, run)
        atomic_text(path, render(store, run))
        status = describe(run)
        ledger = spend_summary(run)
        from .assessment import business_summary
        business = business_summary(run)
        link = path.relative_to(store.logs_dir).as_posix()
        label = run['request'].get('product_name') or run['meta'].get('name') or run['request']['name']
        contribution = money(run, business['contribution_after_ads_minor']) if business['contribution_after_ads_minor'] is not None else 'Unknown'
        outcomes = business['qualified_outcomes'] if business['qualified_outcomes'] is not None else 'Unknown'
        timezone = next((x["baseline"]["timezone"] for x in ledger["entries"] if x.get("baseline")), run.get("review_evidence", {}).get("account_timezone", "UTC"))
        zone = account_zone(timezone)
        launch = local_time(ledger['launch_verified_at'], zone) if ledger['launch_verified_at'] else 'Not started'
        rows.append(f"| [{clean(label)}]({link}) | {status['status']} | {launch} | {money(run, ledger['spent_since_start_minor'])} | {outcomes} | {contribution} | {clean(status['next_action'])} | {readable_when(status['when'], zone)} | {status['owner']} |")
    atomic_text(store.logs_dir / "activity.md", "\n".join(rows) + "\n")
