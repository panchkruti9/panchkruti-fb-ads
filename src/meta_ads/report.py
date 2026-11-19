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


def describe(run):
    step, state = run["step"], run["status"]
    name = REGISTRY.get(step, {}).get("name") or step.replace("-", " ").title()
    proposal = run.get("proposal")
    public = {"monitoring": "scheduled", "blocked": "needs-attention", "execution_blocked": "needs-attention",
              "awaiting_approval": "waiting-for-approval", "paused": "completed", "stopped": "completed"}.get(state, "working")
    question = None
    if state == "monitoring":
        action, when, owner = "Compare the next complete Meta and Shopify reporting windows.", run.get("next_review_at"), "agent"
    elif state == "awaiting_approval":
        action, when, owner = f"Review the {proposal['operation']} proposal and its impact.", "After approval", "user"
        question = f"Approve the displayed {proposal['operation']} proposal?"
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
    done = f"Verified Meta {receipt['operation']}." if receipt else "Saved research and decisions are listed below."
    return {"status": public, "current_task": name, "done": done, "next_action": action,
            "when": when, "owner": owner, "question": question, "attention": run.get("blockers", [])}


def campaign_path(store, run):
    brand = (run["request"].get("brand") or {}).get("brand_id", "brand")
    return store.logs_dir / slug(brand) / (slug(run["request"]["name"]) + ".md")


def render(store, run):
    zone = account_zone("Asia/Kolkata") if (run["request"].get("brand") or {}).get("policy", {}).get("currency") == "INR" else account_zone("UTC")
    status = describe(run)
    ledger = spend_summary(run)
    if ledger["entries"] and ledger["entries"][0].get("baseline"):
        zone = account_zone(ledger["entries"][0]["baseline"]["timezone"])
    lines = ["# " + clean(run["request"].get("product_name", run["request"]["name"])), "",
             f"**Status** — {status['status']}", f"**Current task** — {status['current_task']}",
             f"**Done** — {status['done']}", f"**Next** — {status['next_action']}",
             f"**When** — {status['when']}", f"**Responsible** — {status['owner']}", ""]
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
                  f"| Next scheduled check | {local_time(run.get('next_review_at'), zone) if run.get('next_review_at') else 'Scheduled after verified launch'} |", "",
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
    if cap.get("amount_spent") is not None:
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
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def write_logs(store):
    rows = ["# Meta Ads activity", "", "Open a campaign for its decisions, results and full history.", "",
            "| Campaign | Status | AGI launch | Spend since start | Next action | When | Responsible |", "|---|---|---|---|---|---|---|"]
    for run in store.list():
        path = campaign_path(store, run)
        atomic_text(path, render(store, run))
        status = describe(run)
        ledger = spend_summary(run)
        link = path.relative_to(store.logs_dir).as_posix()
        label = run['request'].get('product_name') or run['meta'].get('name') or run['request']['name']
        rows.append(f"| [{clean(label)}]({link}) | {status['status']} | {ledger['launch_verified_at'] or 'Not started'} | {money(run, ledger['spent_since_start_minor'])} | {clean(status['next_action'])} | {clean(status['when'])} | {status['owner']} |")
    atomic_text(store.logs_dir / "activity.md", "\n".join(rows) + "\n")
