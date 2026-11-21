"""Read-only Meta snapshots and the connected agent's private catch-up log."""
import argparse
import json
import os
import re
import shutil
import subprocess
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from .execution import campaign_configuration
from .meta import Meta, Stop, account_zone, canonical, configured, meta_id, require
from .sources import META_FIELDS
from .state import now, parse_time, stamp

WORKFLOW = "meta-catchup.yml"
ARTIFACT = "meta-catchup"
FILENAME = "meta-snapshot.cms"
LEVELS = ("campaign", "adset", "ad")
MAX_AGE = timedelta(hours=36)
ADDITIVE_FIELDS = ("spend", "impressions", "inline_link_clicks")
ACTION_FIELDS = ("actions", "action_values", "outbound_clicks")


def draft_readback(client, target):
    """Collect exact ad destinations and settings without modifying the draft."""
    campaign_id = target["id"]
    adsets = list(client.pages(f"{campaign_id}/adsets", "id,name,campaign_id,configured_status,effective_status,"
                              "daily_budget,lifetime_budget,targeting,promoted_object,optimization_goal"))
    ads = list(client.pages(f"{campaign_id}/ads", "id,name,campaign_id,adset_id,configured_status,effective_status,creative"))
    adsets = [row for row in adsets if row["configured_status"] not in {"DELETED", "ARCHIVED"}]
    ads = [row for row in ads if row["configured_status"] not in {"DELETED", "ARCHIVED"}]
    require(all(row["campaign_id"] == campaign_id for row in adsets + ads), "Draft child belongs to another campaign.")
    for ad in ads:
        ad["creative_readback"] = client.owned(ad["creative"]["id"],
                                               "object_story_spec,url_tags,asset_feed_spec,product_set_id")
    return {"adsets": adsets, "ads": ads}


def capture(client, job_id):
    account = client.request(client.prefix, {"fields": "account_id,currency,timezone_name,account_status"})
    require(account.get("account_id") == client.account, "Meta snapshot account mismatch.")
    today = now().astimezone(account_zone(account["timezone_name"])).date()
    first = today - timedelta(days=92)
    span = {"since": first.isoformat(), "until": today.isoformat()}
    with configured({"policy": {"currency": account["currency"]}}):
        report = client.account_report()
        try:
            report["audiences"] = client.audience_inventory()
        except (Stop, KeyError, TypeError, ValueError):
            report["audience_issue"] = "Meta did not return the account's saved audiences."
        try:
            funding = client.funding()
        except (Stop, KeyError, TypeError, ValueError):
            funding = {"unavailable": "Meta did not supply complete account-wide funding."}
    campaigns = {}
    for target in report["managed_objects"]:
        states = {target["configured_status"], target["effective_status"]}
        if not states.intersection({"ACTIVE", "PAUSED"}):
            continue
        children = target["adsets"]
        ids = {"campaign": {target["id"]}, "adset": {child["id"] for child in children},
               "ad": {ad["id"] for child in children for ad in child["ads"]}}
        rows = {}
        for level in LEVELS:
            daily = list(client.pages(f"{target['id']}/insights", META_FIELDS, level=level,
                                      time_range=span, time_increment=1))
            require(all(row.get("campaign_id") == target["id"] for row in daily),
                    "Insights returned an unexpected campaign.")
            rows[level] = [row for row in daily if row.get(f"{level}_id") in ids[level]]
        try:
            configuration = campaign_configuration(client, target)
        except (Stop, KeyError, TypeError, ValueError):
            configuration = {"unavailable": "Meta did not supply a complete configuration."}
        alerts = [f"Campaign delivery status is {target['effective_status']}."]
        if target["effective_status"] == "ACTIVE":
            alerts = []
            if not any(row["date_start"] == (today - timedelta(days=1)).isoformat()
                       and Decimal(row.get("spend", "0")) > 0 for row in rows["campaign"]):
                alerts.append("No spend was reported for yesterday on this active campaign.")
        campaigns[target["id"]] = {"name": target["name"], "configuration": configuration,
                                   "effective_status": target["effective_status"], "configured_status": target["configured_status"],
                                   "daily": rows, "alerts": alerts}
        if target["configured_status"] == "PAUSED":
            try:
                campaigns[target["id"]]["draft"] = draft_readback(client, target)
            except (Stop, KeyError, TypeError, ValueError):
                campaigns[target["id"]]["draft"] = {"unavailable": "Meta did not supply the complete paused draft."}
    return {"version": 1, "job_id": job_id, "observed_at": stamp(), "account_report": report,
            "first_day": first.isoformat(), "last_complete_day": (today - timedelta(days=1)).isoformat(),
            "campaigns": campaigns, "funding": funding}


def openssl():
    program = shutil.which("openssl")
    if not program and os.name == "nt":
        git = shutil.which("git")
        if git:
            candidate = Path(git).resolve().parents[1] / "usr/bin/openssl.exe"
            if candidate.is_file():
                program = str(candidate)
    require(program, "OpenSSL is required for the encrypted Meta catch-up log.")
    return program


def command(args, reason, *, seconds=60):
    try:
        parsed = subprocess.run(args, capture_output=True, check=True, timeout=seconds)
    except (OSError, subprocess.SubprocessError):
        raise Stop(reason) from None
    return parsed.stdout


def setup(directory):
    directory.mkdir(parents=True, exist_ok=True)
    key, cert = directory / "key.pem", directory / "cert.pem"
    if key.is_file() or cert.is_file():
        require(key.is_file() and cert.is_file(), "Restore the matching Meta catch-up key and certificate.")
    else:
        with TemporaryDirectory(dir=directory) as temp:
            generated = Path(temp)
            command([openssl(), "req", "-x509", "-newkey", "rsa:3072", "-nodes", "-days", "1825",
                     "-subj", "/CN=Meta catch-up recipient", "-keyout", str(generated / "key.pem"),
                     "-out", str(generated / "cert.pem")], "Could not generate the Meta catch-up key.")
            (generated / "key.pem").chmod(0o600)
            (generated / "key.pem").replace(key)
            (generated / "cert.pem").replace(cert)
    return cert


def encrypt(source, destination, certificate):
    command([openssl(), "cms", "-encrypt", "-aes-256-gcm", "-binary", "-in", str(source), "-outform", "DER",
             "-out", str(destination), str(certificate)], "Could not encrypt the Meta snapshot.")


def decrypt(source, directory):
    require(source.is_file() and source.stat().st_size <= 24_000_000, "Meta snapshot is missing or exceeds its size limit.")
    raw = command([openssl(), "cms", "-decrypt", "-binary", "-inform", "DER", "-in", str(source),
                   "-recip", str(directory / "cert.pem"), "-inkey", str(directory / "key.pem")],
                  "Could not authenticate and decrypt the Meta snapshot.")
    return json.loads(raw)


def sync(store, repo=None):
    directory = store.path.parent / "meta-catchup"
    config_path = directory / "config.json"
    if repo is None and not config_path.is_file():
        return {"status": "unconfigured", "downloaded": 0}
    repo = repo or json.loads(config_path.read_text(encoding="utf-8"))["repo"]
    require(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo), "Invalid Meta catch-up repository.")
    require((directory / "key.pem").is_file() and (directory / "cert.pem").is_file(),
            "Initialize the local Meta catch-up key before syncing.")
    today = now().date()
    records = json.loads(command(["gh", "run", "list", "--repo", repo, "--workflow", WORKFLOW, "--branch", "main",
                                  "--created", f">={today - timedelta(days=30)}", "--limit", "100",
                                  "--json", "databaseId,createdAt,conclusion,status"],
                                 "Could not read the Meta catch-up workflow runs."))
    cache = directory / "snapshots"
    cache.mkdir(exist_ok=True)
    downloaded, unavailable = 0, 0
    for job in reversed(records):
        if job["conclusion"] != "success":
            continue
        job_id = meta_id(str(job["databaseId"]))
        target = cache / f"{job_id}.json"
        if target.is_file():
            continue
        with TemporaryDirectory(dir=directory) as temp:
            try:
                command(["gh", "run", "download", job_id, "--repo", repo, "--name", ARTIFACT, "--dir", temp],
                        "The encrypted Meta snapshot could not be downloaded.")
                snapshot = decrypt(Path(temp) / FILENAME, directory)
                observed = parse_time(snapshot["observed_at"])
                require(snapshot.get("version") == 1 and snapshot.get("job_id") == job_id
                        and parse_time(job["createdAt"]) - timedelta(minutes=1) <= observed <= now() + timedelta(minutes=1),
                        "Meta snapshot does not belong to the verified Actions run.")
            except (Stop, OSError, KeyError, TypeError, ValueError):
                unavailable += 1
                continue
            temporary = Path(temp) / "snapshot.json"
            temporary.write_text(canonical(snapshot), encoding="utf-8")
            temporary.replace(target)
            downloaded += 1
    for path in cache.glob("*.json"):
        if path.stat().st_mtime < (now() - timedelta(days=31)).timestamp():
            path.unlink(missing_ok=True)
    latest = next((job for job in records if job["status"] == "completed"), {})
    return {"status": latest.get("conclusion", "waiting"), "downloaded": downloaded, "unavailable": unavailable}


def snapshots(store, run):
    directory = store.path.parent / "meta-catchup" / "snapshots"
    account = run["request"]["account_id"]
    currency = run["request"]["brand"]["policy"]["currency"]
    matches = []
    for file in directory.glob("*.json"):
        entry = json.loads(file.read_text(encoding="utf-8"))
        observed = entry["account_report"]["account"]
        if observed["account_id"] == account and observed["currency"] == currency:
            matches.append(entry)
    return sorted(matches, key=lambda entry: parse_time(entry["observed_at"]))


def record(store, run):
    if not run.get("connected") or not run.get("meta", {}).get("id"):
        return run
    target = run["meta"]
    since = run.get("meta_catchup_at") or run.get("live_since") or run["created_at"]
    unseen = []
    ledger_changed = False
    from .ledger import summary as ledger_summary
    previous_delivery = ledger_summary(run)["first_delivery_on"]
    for entry in snapshots(store, run):
        from .ledger import apply_snapshot
        try:
            ledger_changed = apply_snapshot(run, entry) or ledger_changed
        except (Stop, OSError, KeyError, TypeError, ValueError) as error:
            message = str(error) if isinstance(error, Stop) else f"Snapshot accounting needs agent reconciliation ({type(error).__name__})."
            if run.get("accounting_snapshot_issue") != message:
                run["accounting_snapshot_issue"] = message
                ledger_changed = True
        campaign = entry["campaigns"].get(target["id"])
        if campaign and campaign["name"] == target["name"] and parse_time(entry["observed_at"]) > parse_time(since):
            recent = [row for row in campaign["daily"]["campaign"] if row["date_start"] == entry["last_complete_day"]]
            unseen.append({"job_id": entry["job_id"], "at": entry["observed_at"], "status": campaign["effective_status"],
                           "dates": [entry["first_day"], entry["last_complete_day"]],
                           "yesterday": recent, "alerts": campaign["alerts"]})
            run["delivery_observation"] = {"id": target["id"], "at": entry["observed_at"],
                "configured_status": campaign.get("configured_status"), "effective_status": campaign["effective_status"]}
    if unseen or ledger_changed:
        if unseen:
            run["meta_catchup_at"] = unseen[-1]["at"]
        first_delivery = ledger_summary(run)["first_delivery_on"]
        store.save(run, "agi_delivery_started" if first_delivery and not previous_delivery else "meta_catchup", {
            "campaign_id": target["id"], "snapshots": unseen, "first_delivery_on": first_delivery,
            "detail": ("First AGI delivery observed on " + first_delivery + " (Meta account-local reporting date).")
                      if first_delivery and not previous_delivery else "Imported scheduled campaign observations."})
    return run


def current_snapshot(store, run):
    choices = snapshots(store, run)
    if choices and now() - parse_time(choices[-1]["observed_at"]) <= MAX_AGE:
        return choices[-1]


def aggregate_daily(daily, level, start, end):
    totals, days = {}, set()
    for row in daily:
        day = row["date_start"]
        require(day == row["date_stop"], "Expected individual Meta reporting days.")
        if not start <= day <= end:
            continue
        target = row[f"{level}_id"]
        require((target, day) not in days, "Duplicate Meta Insights reporting day.")
        days.add((target, day))
        group = totals.setdefault(target, {
            **{key: row[key] for key in ("campaign_id", "adset_id", "ad_id") if key in row},
            "date_start": start, "date_stop": end})
        for key in ADDITIVE_FIELDS:
            if key in row:
                group[key] = Decimal(str(group.get(key, 0))) + Decimal(row[key])
        for key in ACTION_FIELDS:
            for item in row.get(key, []):
                action = item["action_type"]
                counts = group.setdefault(key, {})
                counts[action] = counts.get(action, Decimal(0)) + Decimal(item["value"])
    for group in totals.values():
        for key in ADDITIVE_FIELDS:
            if key in group:
                group[key] = format(group[key], "f")
        for key in ACTION_FIELDS:
            if key in group:
                group[key] = [{"action_type": action, "value": format(value, "f")} for action, value in group[key].items()]
    return list(totals.values())


def review(entry, target, periods, shopify):
    campaign = entry["campaigns"].get(target["id"])
    require(campaign and campaign["name"] == target["name"], "The Meta snapshot does not cover this campaign.")
    report = {"meta": {}, "shopify": shopify, "warnings": [], "configuration": campaign["configuration"],
              "account_timezone": entry["account_report"]["account"]["timezone_name"], "meta_job_id": entry["job_id"]}
    for key, period in periods.items():
        start, end = (value.isoformat() for value in period)
        if not entry["first_day"] <= start <= end <= entry["last_complete_day"]:
            report["warnings"].append(f"Meta snapshot does not cover the {key} dates.")
            continue
        report["meta"][key] = {"start": start, "end": end, "observed_at": entry["observed_at"],
                               "rows": {level: aggregate_daily(campaign["daily"][level], level, start, end)
                                        for level in LEVELS},
                               "attribution": "Meta daily totals. Unique reach and frequency omitted for combined dates."}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("certificate", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        job = capture(Meta(os.environ.get("META_AD_ACCOUNT_ID", "").removeprefix("act_")), os.environ["GITHUB_RUN_ID"])
        with TemporaryDirectory() as temp:
            source = Path(temp) / "snapshot.json"
            source.write_text(canonical(job), encoding="utf-8")
            require(source.stat().st_size <= 23_000_000, "Meta snapshot exceeds the size limit.")
            encrypt(source, args.output, args.certificate)
    except (Stop, OSError, ValueError, TypeError, KeyError) as error:
        # Actions logs are public. Provider failure messages may contain private object IDs.
        message = str(error)
        http = re.search(r"Meta returned HTTP ([0-9]{3}) ", message)
        if http:
            parser.exit(2, f"Meta rejected the read with HTTP {http[1]}. Check the existing Meta secret and read access.\n")
        parser.exit(2, "Meta snapshot failed. Check the Meta account, API version, read secret and encryption setup.\n")


if __name__ == "__main__":
    main()
