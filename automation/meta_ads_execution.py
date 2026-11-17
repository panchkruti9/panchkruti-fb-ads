"""Read Meta data and apply explicitly authorized, validated changes."""

import json
import os
import re
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zoneinfo import ZoneInfo

from meta_ads import (
    check_brand_budget, fingerprint, integer, meta_id, read, read_brand_limits,
    require, require_agi_name, review, save, validate,
)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Meta:
    def __init__(self, account, *, write=False):
        self.account = meta_id(account, "account ID")
        env_account = os.environ.get("META_AD_ACCOUNT_ID", "").removeprefix("act_")
        require(env_account == account, "Configure META_AD_ACCOUNT_ID to match this plan.")
        self.version = os.environ.get("META_API_VERSION", "")
        require(re.fullmatch(r"v[0-9]+\.[0-9]+", self.version), "Set META_API_VERSION explicitly.")
        self.write = write
        secret = "META_WRITE_TOKEN" if write else "META_READ_TOKEN"
        self.token = os.environ.get(secret)
        require(bool(self.token), f"Configure {secret} for this operation.")
        self.opener = build_opener(NoRedirect())

    def request(self, path, fields, *, write=False):
        require(not write or self.write, "Reporting client cannot write.")
        values = {key: json.dumps(value, separators=(",", ":")) if isinstance(value, (dict, list, bool))
                  else str(value) for key, value in fields.items()}
        query = urlencode(values)
        url = f"https://graph.facebook.com/{self.version}/{path}"
        request = Request(url if write else f"{url}?{query}", data=query.encode() if write else None,
                          headers={"Authorization": f"Bearer {self.token}",
                                   "Content-Type": "application/x-www-form-urlencoded"})
        try:
            with self.opener.open(request, timeout=30) as response:
                data = json.load(response)
        except HTTPError as error:
            raise RuntimeError(f"Meta returned HTTP {error.code} for {path}.") from error
        require(isinstance(data, dict) and "error" not in data, "Unexpected Meta response.")
        return data

    def account_details(self, currency):
        data = self.request(f"act_{self.account}", {"fields": "account_id,currency,timezone_name,account_status"})
        require(data.get("account_id") == self.account and data.get("currency") == currency,
                "Meta account or currency differs from the saved plan.")
        return data

    def month_spend(self, as_of, minor_per_unit):
        response = self.request(f"act_{self.account}/insights", {
            "fields": "spend", "level": "account",
            "time_range": {"since": as_of.replace(day=1).isoformat(), "until": as_of.isoformat()},
        })
        rows = response["data"]
        require(len(rows) <= 1 and not response.get("paging", {}).get("next"),
                "Expected one account spend total.")
        spend = Decimal(rows[0]["spend"]) * minor_per_unit if rows else Decimal(0)
        require(spend.is_finite() and spend >= 0 and spend == spend.to_integral_value(),
                "Meta account spend is invalid in the configured minor units.")
        return int(spend)

    def owned(self, object_id, fields):
        data = self.request(meta_id(object_id, "Meta object ID"), {"fields": f"id,account_id,{fields}"})
        require(data.get("id") == object_id and data.get("account_id") == self.account,
                "Meta object is outside the approved account.")
        return data

    def budget_target(self, target):
        kind_field = "objective" if target["type"] == "campaign" else "campaign_id"
        data = self.owned(target["id"], f"name,daily_budget,effective_status,{kind_field}")
        require(bool(data.get(kind_field)), "Meta budget owner type differs from the plan.")
        require_agi_name(data.get("name"), "Meta target")
        if target["type"] == "ad_set":
            parent = self.owned(data["campaign_id"], "name")
            require_agi_name(parent.get("name"), "Parent campaign")
        return data

    def verify_reporting_scope(self, target):
        edges = ("adsets", "ads") if target["type"] == "campaign" else ("ads",)
        for edge in edges:
            params = {"fields": "name", "limit": 100}
            seen = set()
            while True:
                response = self.request(f"{target['id']}/{edge}", params)
                for row in response["data"]:
                    require_agi_name(row.get("name"), "Meta reporting entity")
                paging = response.get("paging", {})
                if not paging.get("next"):
                    break
                cursor = paging.get("cursors", {}).get("after")
                require(isinstance(cursor, str) and cursor and cursor not in seen,
                        "Cannot verify all Meta entities in the reporting scope.")
                seen.add(cursor)
                params["after"] = cursor

    def verify_campaign_budget(self, target, current, new, cap):
        if target["type"] == "campaign":
            return
        campaign_id = meta_id(current["campaign_id"], "parent campaign ID")
        parent = self.owned(campaign_id, "daily_budget,lifetime_budget")
        require(not any(int(parent.get(key) or 0) for key in ("daily_budget", "lifetime_budget")),
                "The parent campaign controls funding.")
        response = self.request(f"{campaign_id}/adsets", {
            "fields": "id,status,daily_budget,lifetime_budget", "limit": 100,
        })
        require(not response.get("paging", {}).get("next"), "Cannot verify every sibling ad set budget.")
        siblings = [row for row in response["data"] if row["status"] not in {"ARCHIVED", "DELETED"}]
        require(sum(row["id"] == target["id"] for row in siblings) == 1,
                "Budget target missing from the current campaign.")
        require(all(not int(row.get("lifetime_budget") or 0) for row in siblings),
                "Cannot verify a daily cap for a campaign with lifetime-funded ad sets.")
        total = new + sum(int(row["daily_budget"]) for row in siblings if row["id"] != target["id"])
        require(total <= cap, "Combined ad set budgets exceed the approved campaign cap.")


def account_date(details):
    name = details["timezone_name"]
    return datetime.now(timezone.utc if name == "UTC" else ZoneInfo(name)).date()


def check_live_budget(plan, client, context, daily_minor, as_of):
    limits = read_brand_limits()
    require(limits is not None, "Enter the three budget limits in brand-rules.md.")
    require(plan["currency"] == "INR" and plan["minor_per_unit"] == 100,
            "The brand budget requires an INR account and rupee amounts in paise.")
    require(isinstance(context, dict) and context.get("as_of") == as_of.isoformat(),
            "Supply an account budget summary dated today in the Meta account time zone.")
    latest = {**context, "spent_minor": client.month_spend(as_of, 100)}
    return check_brand_budget(limits, latest, daily_minor, as_of.isoformat())


def live_snapshot(plan, evidence, client=None):
    require(plan.get("target") and plan.get("review"), "Set a Meta target and review criteria first.")
    client = client or Meta(plan["account_id"])
    account = client.account_details(plan["currency"])
    as_of = account_date(account)
    target = client.budget_target(plan["target"])
    require_agi_name(target.get("name"), "Meta target")
    client.verify_reporting_scope(plan["target"])
    criteria = plan["review"]
    require(criteria["result_basis"]["time_zone"] == account["timezone_name"],
            "The reporting time zone must match the Meta account.")
    today = as_of.isoformat()
    snapshot = {
        "account_id": plan["account_id"], "target": plan["target"], "currency": plan["currency"],
        "as_of": today, "time_zone": account["timezone_name"], "business_source": None,
        "target_name": target["name"],
        "meta_attribution": "Ads Manager settings for this target",
        "tracking_verified": False,
        "delivery_healthy": target.get("effective_status") == "ACTIVE" and account.get("account_status") == 1,
        "capacity_verified": False,
        "daily_budget_minor": int(target["daily_budget"]) if target.get("daily_budget") else None,
    }
    if evidence:
        for field in ("account_id", "target", "currency"):
            require(evidence.get(field) == snapshot[field], f"Business evidence has a different {field}.")
        require(bool(evidence.get("source")), "Name the business evidence source.")
        evidence_date = date.fromisoformat(evidence["as_of"])
        require(evidence_date <= as_of, "Business evidence is dated in the future.")
        if evidence_date < as_of:
            snapshot["evidence_issue"] = (
                f"Business evidence is dated {evidence_date}. Supply evidence for {today}."
            )
            evidence = {}
    if evidence:
        for field in ("business_source", "result_basis", "tracking_verified",
                      "capacity_verified", "last_budget_change"):
            if field in evidence:
                snapshot[field] = evidence[field]
        snapshot["evidence_source"] = evidence["source"]
        budget = evidence.get("account_budget")
        if (isinstance(budget, dict) and budget.get("as_of") == today
                and plan["currency"] == "INR" and plan["minor_per_unit"] == 100):
            snapshot["account_budget"] = {**budget, "spent_minor": client.month_spend(as_of, 100)}
    end = as_of - timedelta(days=1 + criteria["conversion_lag_days"])
    for name in ("current", "previous"):
        start = end - timedelta(days=criteria["days"] - 1)
        window = {"start": start.isoformat(), "end": end.isoformat()}
        data = client.request(f"{plan['target']['id']}/insights", {
            "fields": "spend,impressions,inline_link_clicks,actions",
            "time_range": {"since": window["start"], "until": window["end"]},
        })
        rows = data["data"]
        require(isinstance(rows, list) and len(rows) <= 1 and not data.get("paging", {}).get("next"),
                "Expected one aggregate Insights row per period.")
        actual = evidence.get(name, {})
        if actual:
            require(all(actual.get(k) == window[k] for k in ("start", "end")),
                    f"Business evidence for {name} covers different dates.")
        # The multiplier is account-currency configuration, not a universal cents assumption.
        multiplier = integer(plan["minor_per_unit"], "Minor units per unit", 1)
        spend = (Decimal(rows[0]["spend"]) * multiplier) if rows and "spend" in rows[0] else None
        require(spend is None or (spend.is_finite() and spend >= 0 and spend == spend.to_integral_value()),
                "Meta spend cannot be represented in the configured minor units.")
        snapshot[name] = {
            **window, "spend_minor": int(spend) if spend is not None else None,
            "results": actual.get("results"), "value_minor": actual.get("value_minor"),
            "meta": rows[0] if rows else None,
        }
        end = start - timedelta(days=1)
    return snapshot


@contextmanager
def locked_state(path):
    require(bool(path), "Specify a persistent --state file before executing.")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_suffix(path.suffix + ".lock")
    try:
        with lock.open("x"):
            pass
    except FileExistsError as error:
        raise ValueError("Execution record is locked. Check the previous run before clearing it.") from error
    try:
        yield path, read(path) if path.exists() else {}
    finally:
        lock.unlink()


def apply_budget(plan, snapshot, proposal, confirmation=None, state_path=None, client=None):
    actual = review(plan, snapshot).get("proposal")
    require(actual and actual == proposal, "Proposal does not match the saved plan and evidence.")
    old = proposal["from_daily_minor"]
    new = integer(proposal["to_daily_minor"], "Proposed daily budget", 1)
    require(new <= plan["budget"]["max_daily_minor"], "Proposal exceeds the authorized cap.")
    require((proposal["action"] == "scale" and 0 < new - old <= plan["budget"]["scale_step_minor"])
            or (proposal["action"] == "reverse" and new < old), "Invalid budget change.")
    if confirmation is None:
        return {"status": "preview", "proposal": proposal}
    require(confirmation == proposal["approval_id"], "Approval ID does not match the proposal.")
    client = client or Meta(plan["account_id"], write=True)
    account = client.account_details(plan["currency"])
    require(account["account_status"] == 1, "The Meta account is not active.")
    today = account_date(account)
    require(proposal["expires_on"] >= today.isoformat() >= snapshot["as_of"], "Proposal is stale.")
    with locked_state(state_path) as (path, records):
        approved_id = proposal["approval_id"]
        receipt = records.get(approved_id)
        current = client.budget_target(proposal["target"])
        require_agi_name(current.get("name"), "Meta target")
        client.verify_reporting_scope(proposal["target"])
        value = int(current["daily_budget"])
        if receipt:
            if receipt["status"] == "applied":
                return {**receipt, "status": "already_applied", "current_daily_minor": value}
            require(value == new, "An earlier write was unconfirmed. Reconcile it in Ads Manager before proceeding.")
        else:
            require(current.get("effective_status") == "ACTIVE" and value == old,
                    "Meta delivery or the old budget changed. Rebuild the proposal.")
            relevant = [
                item for item in records.values()
                if isinstance(item, dict) and item.get("status") in {"pending", "applied"}
                and item.get("proposal", item).get("account_id") == proposal["account_id"]
                and item.get("proposal", item).get("target") == proposal["target"]
            ]
            require(all(item["status"] == "applied" for item in relevant),
                    "Resolve the pending budget update before approving another change.")
            if relevant:
                latest = max(relevant, key=lambda item: item["applied_on"])
                recorded = snapshot.get("last_budget_change", {})
                require(recorded.get("approval_id") == latest["approval_id"]
                        and all(recorded.get(key) == latest[key] for key in
                                ("action", "applied_on", "from_daily_minor", "to_daily_minor")),
                        "Refresh the snapshot with the latest applied budget receipt.")
            client.verify_campaign_budget(proposal["target"], current, new, plan["budget"]["max_daily_minor"])
            check_live_budget(plan, client, snapshot.get("account_budget"), new, today)
            records[approved_id] = {"status": "pending", "proposal": proposal, "attempted_on": today.isoformat()}
            save(path, records)
            client.request(proposal["target"]["id"], {"daily_budget": new}, write=True)
            require(int(client.budget_target(proposal["target"])["daily_budget"]) == new,
                    "Meta has not confirmed the new budget. Reconcile before retrying.")
        result = {**proposal, "status": "applied", "applied_on": (receipt or {}).get("attempted_on", today.isoformat())}
        records[approved_id] = result
        save(path, records)
        return result


def pause_ad(plan, ad_id, ad_name, reason, confirmation=None, state_path=None, client=None):
    validate(plan)
    target = plan.get("target")
    require(target, "Save the Meta campaign or ad set target before pausing an ad.")
    meta_id(ad_id, "Ad ID")
    require_agi_name(ad_name, "Ad name")
    require(isinstance(reason, str) and reason.strip(), "Record the evidence for pausing this ad.")
    action = {"operation": "pause_ad", "account_id": plan["account_id"], "target": target,
              "ad_id": ad_id, "ad_name": ad_name, "reason": reason.strip(), "plan": fingerprint(plan)}
    approval = fingerprint(action)
    if confirmation is None:
        return {**action, "status": "preview", "approval_id": approval}
    require(confirmation == approval, "Approval ID does not match the pause preview.")
    client = client or Meta(plan["account_id"], write=True)
    account = client.account_details(plan["currency"])
    with locked_state(state_path) as (path, records):
        ad = client.owned(ad_id, "name,status,campaign_id,adset_id")
        require(ad.get("name") == ad_name, "Ad name has changed. Rebuild the preview.")
        ad_set = client.owned(ad["adset_id"], "name,campaign_id")
        campaign = client.owned(ad["campaign_id"], "name,objective")
        require_agi_name(ad_set.get("name"), "Parent ad set")
        require_agi_name(campaign.get("name"), "Parent campaign")
        parent_id = ad["campaign_id"] if target["type"] == "campaign" else ad["adset_id"]
        require(target["id"] == parent_id and ad_set["campaign_id"] == ad["campaign_id"]
                and campaign.get("objective"), "Ad is outside the saved campaign or ad set.")
        if approval in records:
            require(ad["status"] == "PAUSED", "Ad state changed or the pause is unconfirmed. Verify in Meta.")
            if records[approval]["status"] == "applied":
                return {**records[approval], "status": "already_applied"}
        elif ad["status"] == "ACTIVE":
            records[approval] = {**action, "status": "pending"}
            save(path, records)
            client.request(ad_id, {"status": "PAUSED"}, write=True)
            require(client.owned(ad_id, "status")["status"] == "PAUSED",
                    "Meta has not confirmed the pause. Verify in Meta before retrying.")
        else:
            require(ad["status"] == "PAUSED", "Ad must be active or paused.")
        result = {**action, "status": "applied", "approval_id": approval,
                  "applied_on": account_date(account).isoformat()}
        records[approval] = result
        save(path, records)
        return result


def build_operations(plan):
    require(not validate(plan), "Resolve open campaign decisions before building.")
    require(plan.get("budget") and plan.get("build"), "Set the budget cap and build settings first.")
    spec = plan["build"]
    campaign = spec["campaign"]
    require(spec["destination"] == plan["decisions"]["creative_and_copy"]["details"]["destination"],
            "Build destination differs from the creative decision.")
    destination = urlparse(spec["destination"])
    require(destination.scheme == "https" and destination.hostname and not destination.username
            and not destination.password, "Use an HTTPS destination.")
    domain = spec.get("conversion_domain", "")
    if domain:
        require(re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", domain)
                and (destination.hostname == domain or destination.hostname.endswith("." + domain)),
                "The conversion domain must match the destination.")
    cap = plan["budget"]["max_daily_minor"]
    require(set(campaign) <= {"name", "objective", "special_ad_categories", "daily_budget", "bid_strategy",
                              "is_adset_budget_sharing_enabled"},
            "Unsupported campaign settings.")
    require_agi_name(campaign.get("name"), "Campaign")
    require(campaign["objective"].strip()
            and isinstance(campaign["special_ad_categories"], list), "Specify campaign identity and ad categories.")
    campaign_payload = {**campaign, "status": "PAUSED"}
    if "daily_budget" in campaign:
        require("is_adset_budget_sharing_enabled" not in campaign, "Choose one budget level.")
    else:
        sharing = campaign.get("is_adset_budget_sharing_enabled", False)
        require(type(sharing) is bool, "Ad set budget sharing must be true or false.")
        campaign_payload["is_adset_budget_sharing_enabled"] = sharing
    operations = [("campaign", "campaigns", campaign_payload)]
    require(isinstance(spec["ad_sets"], list) and spec["ad_sets"], "Specify at least one ad set.")
    total = 0
    for index, ad_set in enumerate(spec["ad_sets"]):
        settings = ad_set["settings"]
        require(set(settings) <= {"name", "daily_budget", "targeting", "optimization_goal", "billing_event",
                                  "promoted_object", "bid_amount", "bid_strategy", "destination_type",
                                  "start_time", "end_time", "attribution_spec"}, "Unsupported ad set settings.")
        require_agi_name(settings.get("name"), "Ad set")
        require(settings["optimization_goal"].strip()
                and settings["billing_event"].strip() and settings["targeting"], "Incomplete ad set settings.")
        if settings.get("promoted_object", {}).get("pixel_id"):
            require(bool(domain), "Set the conversion domain for pixel-backed ads.")
            require(isinstance(settings.get("attribution_spec"), list) and settings["attribution_spec"],
                    "Set the attribution specification for pixel-backed ads.")
        if "daily_budget" in campaign:
            require("daily_budget" not in settings, "Choose one budget level.")
        else:
            total += integer(settings["daily_budget"], "Ad set budget", 1)
        key = f"ad_set_{index}"
        operations.append((key, "adsets", {**settings, "campaign_id": "@campaign", "status": "PAUSED"}))
        require(isinstance(ad_set["ads"], list) and ad_set["ads"], "Each ad set needs an ad.")
        for ad_index, ad in enumerate(ad_set["ads"]):
            require_agi_name(ad.get("name"), "Ad")
            creative = meta_id(ad["creative_id"], "existing creative ID")
            operations.append((f"{key}_ad_{ad_index}", "ads", {
                "name": ad["name"], "adset_id": f"@{key}", "creative": {"creative_id": creative},
                "status": "PAUSED",
                **({"conversion_domain": domain} if domain else {}),
            }))
    if "daily_budget" in campaign:
        total = integer(campaign["daily_budget"], "Campaign budget", 1)
    require(total <= cap, "Combined daily budget exceeds the approved cap.")
    return operations


def build_id(plan):
    return fingerprint({"operation": "build-paused", "plan": plan})


def creative_version(client, creative_id, destination):
    creative = client.owned(creative_id, "object_story_spec,url_tags")
    link = creative.get("object_story_spec", {}).get("link_data", {})
    cta_link = link.get("call_to_action", {}).get("value", {}).get("link")
    require(link.get("link") == destination and cta_link in {None, destination} and not link.get("child_attachments"),
            "Creative does not expose the approved single-link destination.")
    return fingerprint(creative)


def verify_targeting_audiences(client, targeting):
    for key, value in targeting.items():
        if key in {"custom_audiences", "excluded_custom_audiences",
                   "dynamic_audience_ids", "excluded_dynamic_audience_ids"}:
            for entry in value:
                audience_id = str(entry["id"] if isinstance(entry, dict) else entry)
                audience = client.owned(audience_id, "name")
                require_agi_name(audience.get("name"), "Audience")
        elif isinstance(value, dict):
            verify_targeting_audiences(client, value)
        elif key == "flexible_spec":
            for group in value:
                verify_targeting_audiences(client, group)


def build(plan, confirmation=None, state_path=None, client=None):
    operations = build_operations(plan)
    approval = build_id(plan)
    if confirmation is None:
        return {"status": "preview", "approval_id": approval, "operations": operations}
    require(confirmation == approval, "Approval ID does not match the paused plan.")
    client = client or Meta(plan["account_id"], write=True)
    account = client.account_details(plan["currency"])
    require(account["account_status"] == 1, "The Meta account is not active.")
    destination = plan["build"]["destination"]
    for _, edge, data in operations:
        if edge == "ads":
            creative_version(client, data["creative"]["creative_id"], destination)
        elif edge == "adsets":
            verify_targeting_audiences(client, data["targeting"])
    with locked_state(state_path) as (path, records):
        progress = records.setdefault(approval, {})
        for key, edge, fields in operations:
            if key in progress:
                require(progress[key]["status"] == "created",
                        f"{key} creation was unconfirmed. Reconcile in Ads Manager before resuming.")
                object_id = progress[key]["id"]
            else:
                payload = {name: progress[value[1:]]["id"] if isinstance(value, str) and value.startswith("@")
                           and name in {"campaign_id", "adset_id"} else value for name, value in fields.items()}
                progress[key] = {"status": "pending", "attempted_name": payload["name"]}
                save(path, records)
                result = client.request(f"act_{plan['account_id']}/{edge}", payload, write=True)
                object_id = meta_id(result["id"], "created object ID")
                progress[key] = {"status": "created", "id": object_id}
                save(path, records)
            expected_parent = "campaign_id" if edge == "adsets" else "adset_id" if edge == "ads" else None
            verify_fields = f"name,status,{expected_parent}" if expected_parent else "name,status"
            live = client.owned(object_id, verify_fields)
            require(live.get("status") == "PAUSED", f"{key} is not paused. Resolve in Meta before continuing.")
            require(live.get("name") == fields["name"], f"{key} name does not match the approved plan.")
            if expected_parent:
                require(live.get(expected_parent) == progress[fields[expected_parent][1:]]["id"],
                        f"{key} belongs to a different parent.")
        return {"status": "paused", "approval_id": approval, "objects": progress}


def built_ids(plan, records):
    operations = build_operations(plan)
    progress = records.get(build_id(plan), {})
    require(all(progress.get(key, {}).get("status") == "created" for key, _, _ in operations),
            "The approved paused build is incomplete.")
    ids = {key: meta_id(progress[key]["id"], f"{key} ID") for key, _, _ in operations}
    require(len(set(ids.values())) == len(ids), "The execution record repeats object IDs.")
    return operations, ids


def previews(plan, records, client=None):
    operations, ids = built_ids(plan, records)
    client = client or Meta(plan["account_id"])
    client.account_details(plan["currency"])
    links, versions = {}, {}
    for key, edge, fields in operations:
        if edge == "ads":
            ad = client.owned(ids[key], "preview_shareable_link")
            links[ids[key]] = ad.get("preview_shareable_link")
            creative_id = fields["creative"]["creative_id"]
            versions[creative_id] = creative_version(client, creative_id, plan["build"]["destination"])
    return {"build_id": build_id(plan), "preview_links": links,
            "campaign_id": ids["campaign"], "object_ids": ids, "creative_versions": versions}


def unchanged(value, approved):
    if isinstance(approved, dict):
        return isinstance(value, dict) and all(unchanged(value.get(k), v) for k, v in approved.items())
    if isinstance(approved, list):
        return isinstance(value, list) and len(value) == len(approved) and all(
            unchanged(a, b) for a, b in zip(value, approved))
    return str(value) == str(approved)


def launch(plan, qa, state_path, confirmation=None, client=None):
    require(bool(state_path), "Provide the paused build's --state file.")
    operations, ids = built_ids(plan, read(state_path))
    require(qa.get("build_id") == build_id(plan) and qa.get("object_ids") == ids,
            "QA does not identify this exact paused build.")
    checks = ("placement_previews", "destination", "tracking")
    require(all(isinstance(qa.get(key), str) and qa[key].strip() for key in checks)
            and qa.get("passed") is True, "Record passed QA and the evidence for all three checks.")
    creative_ids = {fields["creative"]["creative_id"] for _, edge, fields in operations if edge == "ads"}
    skincare = qa.get("skincare")
    require(isinstance(skincare, dict) and set(skincare) == creative_ids,
            "Record skincare QA for each exact creative ID.")
    checks = ("product_accuracy", "claims", "imagery", "rights_and_disclosures")
    for creative_id, entry in skincare.items():
        require(isinstance(entry, dict) and entry.get("passed") is True
                and all(isinstance(entry.get(key), str) and entry[key].strip() for key in checks),
                f"Record passed skincare QA and evidence for creative {creative_id}.")
    versions = qa.get("creative_versions")
    require(isinstance(versions, dict) and set(versions) == creative_ids
            and all(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) for value in versions.values()),
            "Include the creative versions from the preview.")
    approval = fingerprint({"operation": "activate", "plan": plan, "qa": qa})
    daily_minor = sum(fields.get("daily_budget", 0) for _, _, fields in operations)
    if confirmation is None:
        return {"status": "preview", "approval_id": approval, "account_id": plan["account_id"],
                "currency": plan["currency"], "objects": ids, "daily_budget_minor": daily_minor,
                "daily_budget_cap_minor": plan["budget"]["max_daily_minor"]}
    require(confirmation == approval, "Approval ID does not match this launch.")
    client = client or Meta(plan["account_id"], write=True)
    account = client.account_details(plan["currency"])
    require(account["account_status"] == 1, "The Meta account is not active.")
    with locked_state(state_path) as (path, records):
        require(built_ids(plan, records)[1] == ids, "The build record changed during review.")
        progress = records.setdefault(approval, {})
        children = {
            "adsets": {ids[key] for key, edge, _ in operations if edge == "adsets"},
            "ads": {ids[key] for key, edge, _ in operations if edge == "ads"},
        }
        for edge, expected in children.items():
            response = client.request(f"{ids['campaign']}/{edge}", {"fields": "id,status", "limit": 100})
            actual = {row["id"] for row in response["data"] if row["status"] not in {"ARCHIVED", "DELETED"}}
            require(actual == expected and not response.get("paging", {}).get("next"),
                    f"Meta {edge} differ from the approved build.")
        current = {}
        for key, edge, fields in operations:
            # Meta may normalize targeting and times. Mismatches need a new review.
            expected = {name: ids[value[1:]] if name in {"campaign_id", "adset_id"} else value
                        for name, value in fields.items() if name != "status"}
            if edge == "ads":
                expected["creative"] = {"id": expected["creative"]["creative_id"]}
            live = client.owned(ids[key], ",".join((*expected, "status", "effective_status")))
            require(unchanged(live, expected), f"{key} settings changed after approval.")
            if edge == "adsets":
                verify_targeting_audiences(client, expected["targeting"])
            if edge == "ads":
                creative_id = expected["creative"]["id"]
                require(creative_version(client, creative_id, plan["build"]["destination"]) == versions[creative_id],
                        "The Meta creative changed after review. Generate a new preview and QA.")
            current[key] = live["status"]
            allowed_status = {"PAUSED", "ACTIVE"} if key in progress else {"PAUSED"}
            require(current[key] in allowed_status, f"Unexpected status for {key}.")
            if progress.get(key) == "activated":
                require(current[key] == "ACTIVE", f"{key} changed after activation.")
        if current["campaign"] == "PAUSED":
            check_live_budget(plan, client, qa.get("account_budget"), daily_minor, account_date(account))
        # The campaign stays paused until all approved child objects are active.
        for key, _, _ in reversed(operations):
            if current[key] == "PAUSED":
                progress[key] = "pending"
                save(path, records)
                client.request(ids[key], {"status": "ACTIVE"}, write=True)
                require(client.owned(ids[key], "status").get("status") == "ACTIVE",
                        f"Meta has not confirmed activation of {key}.")
            progress[key] = "activated"
            save(path, records)
        live = client.owned(ids["campaign"], "status,effective_status")
        return {"status": "activated", "approval_id": approval,
                "campaign_id": ids["campaign"], "effective_status": live.get("effective_status")}
