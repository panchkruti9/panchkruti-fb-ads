"""Campaign-scoped AGI accounting, separate from historical account billing."""
from datetime import date
from decimal import Decimal

from .meta import account_zone, configured, policy, require
from .state import now, parse_time, stamp


def amount(value, scale):
    result = Decimal(str(value)) * scale
    require(result.is_finite() and result >= 0 and result == result.to_integral_value(),
            "Meta campaign spend did not return valid currency units.")
    return int(result)


def read_spending(client, target, start_day=None):
    """Use exact campaign Insights; include launch-day pre-start spend in the baseline."""
    client.scope(target["id"], "campaign", target["name"])
    account = client.details()
    today = now().astimezone(account_zone(account["timezone_name"])).date()
    first = date.fromisoformat(start_day) if start_day else today
    require(first <= today, "Campaign accounting starts in the future.")
    scale = policy()["minor_per_unit"]
    rows = list(client.pages(target["id"] + "/insights", "campaign_id,date_start,date_stop,spend,impressions",
                             level="campaign", time_increment=1,
                             time_range={"since": first.isoformat(), "until": today.isoformat()}))
    days, seen = [], set()
    for row in rows:
        day = row["date_start"]
        require(row["campaign_id"] == target["id"] and day == row["date_stop"]
                and first.isoformat() <= day <= today.isoformat() and day not in seen,
                "Campaign accounting returned another scope or duplicate day.")
        seen.add(day)
        impressions = int(row.get("impressions", 0))
        require(impressions >= 0, "Invalid campaign impression count.")
        days.append({"day": day, "spend_minor": amount(row.get("spend", 0), scale), "impressions": impressions})
    month = list(client.pages(target["id"] + "/insights", "campaign_id,spend", level="campaign",
                              time_range={"since": today.replace(day=1).isoformat(), "until": today.isoformat()}))
    require(len(month) <= 1 and all(row["campaign_id"] == target["id"] for row in month),
            "Campaign month spend returned another scope.")
    return {"campaign_id": target["id"], "observed_at": stamp(), "timezone": account["timezone_name"],
            "start_day": first.isoformat(), "through_day": today.isoformat(), "month": today.strftime("%Y-%m"),
            "window_spend_minor": sum(row["spend_minor"] for row in days),
            "window_impressions": sum(row["impressions"] for row in days),
            "month_spend_minor": amount(month[0].get("spend", 0), scale) if month else 0,
            "daily": sorted(days, key=lambda row: row["day"])}


def capture_baseline(store, run, client, batch):
    entries = run.setdefault("campaign_ledger", {})
    key = batch["campaign_id"]
    existing = entries.get(key)
    journal = run.get("write_journal", {}).get((run.get("proposal") or {}).get("id"), {})
    if existing and (existing.get("launch_verified_at") or any(k.startswith("activate:") for k in journal)):
        return existing
    legacy_addition = bool(run.get("live_since") and batch.get("addition") and not existing)
    issue = None
    try:
        require(not legacy_addition, "This campaign was already managed before spend baselines were recorded; reconcile its earlier launch history.")
        reading = read_spending(client, {"id": key, "name": batch["name"]})
    except (ValueError, OSError, KeyError, TypeError) as error:
        reading = None
        issue = str(error) if isinstance(error, ValueError) else type(error).__name__
    entry = {"campaign_id": key, "name": batch["name"], "baseline": reading,
             "daily_budget_minor": batch["daily_minor"], "launch_verified_at": run.get("live_since") if legacy_addition else None,
             "first_delivery_on": None, "spent_since_start_minor": None,
             "spent_month_minor": None, "accounting_issue": issue,
             "source": "Meta campaign Insights, launch-day baseline deducted"}
    entries[key] = entry
    store.save(run, "agi_spend_baseline_saved" if reading else "agi_spend_baseline_unavailable", {
               "campaign_id": key, "start_day": reading["start_day"] if reading else None,
               "excluded_prestart_spend_minor": reading["window_spend_minor"] if reading else None,
               "detail": "Saved the campaign's pre-launch spend baseline; AGI budget clock has not started."
                         if reading else "Campaign spend baseline could not be read. Preserve unknown spend and let the agent reconcile; do not fabricate zero."})
    return entry


def mark_launched(run, receipt):
    entry = run.get("campaign_ledger", {}).get(receipt["campaign_id"])
    if entry:
        entry["launch_verified_at"] = entry.get("launch_verified_at") or receipt.get("launch_verified_at") or stamp()
        # No spend is fabricated between the baseline and verification. Read Insights next.
        entry["last_configured_status"] = "ACTIVE"
    control = receipt.get("spend_control")
    if control:
        run["account_control"] = {"spend_cap": str(control["spend_cap_minor"]),
                                  "amount_spent": str(control["amount_spent_minor"]),
                                  "observed_at": receipt.get("launch_verified_at") or stamp()}


def observe(entry, reading, daily=None):
    baseline = entry.get("baseline")
    require(baseline and reading["campaign_id"] == entry["campaign_id"]
            and reading["start_day"] == baseline["start_day"], "Campaign accounting baseline scope changed.")
    prior = entry.get("last_observed_at")
    floor = entry.get("launch_verified_at") or baseline.get("observed_at")
    if floor and parse_time(reading["observed_at"]) < parse_time(floor):
        return False
    if prior and parse_time(reading["observed_at"]) <= parse_time(prior):
        return False
    spent = reading["window_spend_minor"] - baseline["window_spend_minor"]
    month = reading["month_spend_minor"] - (baseline["month_spend_minor"] if baseline["month"] == reading["month"] else 0)
    require(spent >= 0 and month >= 0, "Meta revised campaign spend below its saved baseline; accounting needs reconciliation.")
    entry.update(spent_since_start_minor=spent, spent_month_minor=month, month=reading["month"],
                 last_observed_at=reading["observed_at"], accounting_issue=None)
    if daily is not None:
        entry["daily_budget_minor"] = daily
    if not entry.get("first_delivery_on"):
        for row in reading["daily"]:
            initial = row["day"] == baseline["start_day"]
            if (row["spend_minor"] > (baseline["window_spend_minor"] if initial else 0)
                    or row["impressions"] > (baseline["window_impressions"] if initial else 0)):
                entry.update(first_delivery_on=row["day"], first_delivery_verified_at=reading["observed_at"])
                break
    return True


def refresh(store, run, client):
    changed = False
    for entry in run.get("campaign_ledger", {}).values():
        if not entry.get("launch_verified_at"):
            continue
        try:
            require(entry.get("baseline"), "Pre-start campaign spend baseline is missing; reconcile the saved launch history before reporting usage.")
            reading = read_spending(client, {"id": entry["campaign_id"], "name": entry["name"]}, entry["baseline"]["start_day"])
            changed = observe(entry, reading) or changed
        except (ValueError, OSError, KeyError, TypeError) as error:
            entry["accounting_issue"] = str(error) if isinstance(error, ValueError) else type(error).__name__
            changed = True
    if any(entry.get("launch_verified_at") for entry in run.get("campaign_ledger", {}).values()):
        try:
            run["account_control"] = {**client.request(client.prefix, {"fields": "spend_cap,amount_spent"}),
                                      "observed_at": stamp()}
            run.pop("account_control_issue", None)
            changed = True
        except (ValueError, OSError, KeyError, TypeError) as error:
            run["account_control_issue"] = str(error) if isinstance(error, ValueError) else type(error).__name__
            changed = True
    if changed:
        totals = summary(run)
        store.save(run, "agi_spend_updated", {
            "spent_since_start_minor": totals["spent_since_start_minor"],
            "spent_month_minor": totals["spent_month_minor"],
            "first_delivery_on": totals["first_delivery_on"],
            "detail": "Updated campaign spend since verified AGI launch; excluded previous account spending."})
    return run


def summary(run):
    entries = list(run.get("campaign_ledger", {}).values())
    started = [entry for entry in entries if entry.get("launch_verified_at")]
    legacy = bool(run.get("live_since") and not started)
    complete = all(entry.get("spent_since_start_minor") is not None for entry in started) and not legacy
    zone = next((entry["baseline"]["timezone"] for entry in entries if entry.get("baseline")), "UTC")
    month = now().astimezone(account_zone(zone)).strftime("%Y-%m")
    month_complete = complete and all(entry.get("month") == month for entry in started)
    return {"started": bool(started) or legacy,
            "launch_verified_at": min((entry["launch_verified_at"] for entry in started), default=run.get("live_since")),
            "first_delivery_on": min((entry["first_delivery_on"] for entry in started if entry.get("first_delivery_on")), default=None),
            "spent_since_start_minor": sum(entry["spent_since_start_minor"] for entry in started) if complete else None,
            "spent_month_minor": sum(entry["spent_month_minor"] for entry in started) if month_complete else None,
            "month": month, "last_observed_at": min((entry.get("last_observed_at", "") for entry in started), default=None),
            "entries": entries, "legacy_baseline_missing": legacy,
            "issues": ([entry["accounting_issue"] for entry in entries if entry.get("accounting_issue")]
                       + ([run["accounting_snapshot_issue"]] if run.get("accounting_snapshot_issue") else []))}


def apply_snapshot(run, snapshot):
    """Import absolute daily totals once; repeated catch-ups never add spend twice."""
    changed = False
    with configured(run["request"].get("brand")):
        scale = policy()["minor_per_unit"]
        zone = account_zone(snapshot["account_report"]["account"].get("timezone_name", "UTC"))
        today = parse_time(snapshot["observed_at"]).astimezone(zone).date()
        month = today.strftime("%Y-%m")
        for entry in run.get("campaign_ledger", {}).values():
            campaign = snapshot.get("campaigns", {}).get(entry["campaign_id"])
            if not entry.get("launch_verified_at") or not campaign or campaign["name"] != entry["name"]:
                continue
            baseline = entry.get("baseline")
            if not baseline or baseline["start_day"] < snapshot["first_day"]:
                # A live exact-scope refresh supplies windows older than snapshot retention.
                continue
            days, seen = [], set()
            for row in campaign["daily"]["campaign"]:
                day = row["date_start"]
                require(day == row["date_stop"] and row["campaign_id"] == entry["campaign_id"] and day not in seen
                        and snapshot["first_day"] <= day <= today.isoformat(),
                        "Snapshot campaign spend has an invalid scope or duplicate day.")
                seen.add(day)
                days.append({"day": day, "spend_minor": amount(row.get("spend", 0), scale),
                             "impressions": int(row.get("impressions", 0))})
            current = [row for row in days if baseline["start_day"] <= row["day"] <= today.isoformat()]
            reading = {"campaign_id": entry["campaign_id"], "observed_at": snapshot["observed_at"],
                       "start_day": baseline["start_day"], "month": month,
                       "window_spend_minor": sum(row["spend_minor"] for row in current),
                       "month_spend_minor": sum(row["spend_minor"] for row in days if row["day"].startswith(month)),
                       "daily": sorted(current, key=lambda row: row["day"])}
            try:
                changed = observe(entry, reading) or changed
            except ValueError as error:
                entry["accounting_issue"] = str(error)
                changed = True
    return changed
