"""Readable run history generated from the lifecycle's saved evidence."""
from .meta import account_zone
from .state import parse_time


def render(store, run):
    zone = account_zone("Asia/Kolkata")
    lines = ["# " + run["request"].get("product_name", run["request"]["name"]), "",
             f"Current step — {run['step']}", f"Current status — {run['status']}", "",
             "## Skill results", "", "| Skill | Result | Saved finding |", "|---|---|---|"]
    for skill, record in run["records"].items():
        summary = record.get("summary") or ("Verified executor receipt" if record.get("data", {}).get("receipt") else "")
        lines.append(f"| {skill} | {record.get('status', 'unknown')} | {clean(summary)} |")
    lines.extend(["", "## Timeline", "", "Times below use India Standard Time.", "",
                  "| Time | Event | Detail |", "|---|---|---|"])
    for event in store.events(run["id"]):
        payload = event["payload"]
        payload = payload if isinstance(payload, dict) else {"detail": str(payload)}
        result = payload.get("result")
        result = result if isinstance(result, dict) else {}
        detail = result.get("summary") or payload.get("reason") or payload.get("reference") or payload.get("detail")
        if not detail:
            detail = " / ".join(str(payload[key]) for key in ("step", "operation", "next") if payload.get(key))
        at = parse_time(event["at"]).astimezone(zone).strftime("%d %b %Y %H:%M:%S")
        lines.append(f"| {at} | {event['kind']} | {clean(detail or '')} |")
    lines.extend(["", "## Recorded blockers", ""])
    lines.extend(["- " + clean(item) for item in run.get("blockers", [])] or ["No blockers recorded on the current step."])
    return "\n".join(lines) + "\n"


def clean(text):
    return " ".join(str(text).split()).replace("|", "\\|")
