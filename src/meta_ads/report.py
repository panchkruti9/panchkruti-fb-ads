"""User-facing status and readable logs from committed records."""
import re
import uuid
from decimal import Decimal
from .meta import account_zone
from .state import REGISTRY, parse_time


def clean(value):
    return " ".join(str(value).split()).replace("|", "&#124;")


def slug(value):
    return re.sub(r"[^a-z0-9-]+", "-", str(value).lower()).strip("-")[:120] or "campaign"


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
    lines = ["# " + clean(run["request"].get("product_name", run["request"]["name"])), "",
             f"**Status** — {status['status']}", f"**Current task** — {status['current_task']}",
             f"**Done** — {status['done']}", f"**Next** — {status['next_action']}",
             f"**When** — {status['when']}", f"**Responsible** — {status['owner']}", ""]
    if status["attention"]:
        lines.extend(["## Needs attention", ""] + ["- " + clean(x) for x in status["attention"]] + [""])
    if status["question"]:
        lines.extend(["**Your decision** — " + status["question"], ""])
    target = run.get("meta", {})
    if target.get("id"):
        account = run["request"]["account_id"]
        lines.extend([f"[Open the saved campaign in Meta](https://adsmanager.facebook.com/adsmanager/manage/campaigns?act={account}&selected_campaign_ids={target['id']})", ""])
    lines.extend(["## Skill findings", "", "| Skill | Result | Recorded | Decision or finding |", "|---|---|---|---|"])
    for skill, record in sorted(run["records"].items(), key=lambda x: x[1].get("recorded_at", "")):
        summary = record.get("summary") or ("Verified executor receipt" if record.get("data", {}).get("receipt") else "")
        lines.append(f"| {skill} | {record.get('status', 'unknown')} | {clean(record.get('recorded_at', ''))} | {clean(summary)} |")
    lines.extend(["", "## Decisions and activity", "", f"Times use {zone}.", "",
                  "| Time | Event | Detail |", "|---|---|---|"])
    for event in store.events(run["id"]):
        payload = event["payload"]
        payload = payload if isinstance(payload, dict) else {"detail": str(payload)}
        result = payload.get("result")
        result = result if isinstance(result, dict) else {}
        detail = result.get("summary") or payload.get("reason") or payload.get("reference") or payload.get("detail")
        if not detail:
            detail = " / ".join(str(payload[key]) for key in ("step", "operation", "next", "next_action") if payload.get(key))
        at = parse_time(event["at"]).astimezone(zone).strftime("%d %b %Y %H:%M:%S")
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
            "| Campaign | Status | Current task | Next action | When | Responsible |", "|---|---|---|---|---|---|"]
    for run in store.list():
        path = campaign_path(store, run)
        atomic_text(path, render(store, run))
        status = describe(run)
        link = path.relative_to(store.logs_dir).as_posix()
        rows.append(f"| [{clean(run['request']['name'])}]({link}) | {status['status']} | {status['current_task']} | {clean(status['next_action'])} | {clean(status['when'])} | {status['owner']} |")
    atomic_text(store.logs_dir / "activity.md", "\n".join(rows) + "\n")
