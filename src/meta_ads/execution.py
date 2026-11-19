"""Plan, authorize and verify account writes."""
import hashlib
import hmac
import json
import os
import re
import uuid
from datetime import date, timedelta
from decimal import Decimal
from urllib.error import HTTPError
from urllib.request import Request

from .meta import (Stop, account_identity, brand_profile, canonical, destination, fingerprint, meta_id,
                   minor, policy, require, wire_minor)
from .plans import PLACEMENTS, ad_plan, string, targeting, verify_audiences
from .sources import drive_inventory, drive_media, storefront
from .state import now, parse_time, stamp

OWNER_ACTIONS = {"activate", "budget"}
GATES = {"campaign-build": "build", "activate": "activate", "retire": "pause",
         "optimization-execution": "pause", "scaling-approval": "budget", "safety-pause": "pause"}


class Deferred(Stop):
    """A confirmed upload needs more processing time before the next write."""


def approval_setup(run):
    """Identify missing policy assignments for the exact operation."""
    proposal = run.get("proposal") or {}
    operation = proposal.get("operation") or GATES.get(run["step"])
    if not operation:
        return []
    rules = policy(run["request"].get("brand"))
    missing = []
    if "operators" in rules and not rules["operators"]:
        missing.append("Assign an authorized operator in the saved brand policy.")
    # An empty optional owner whitelist uses the current user's recorded approval.
    # A populated whitelist remains authoritative in authorize/verify_approval.
    return missing


def operator_setup(run):
    """Report prerequisites on the host that is expected to execute the proposal."""
    missing = approval_setup(run)
    key = os.environ.get("META_ADS_OPERATOR_KEY") or os.environ.get("PANCHKRUTI_OPERATOR_KEY", "")
    if len(key) < 32:
        missing.append("Configure the approval signing key on the protected Meta worker.")
    request = run["request"]
    if os.environ.get("META_AD_ACCOUNT_ID", "").removeprefix("act_") != request["account_id"]:
        missing.append("Configure the saved ad account on the protected Meta worker.")
    version = os.environ.get("META_API_VERSION")
    if not version or (run.get("proposal") and version != run["proposal"]["api_version"]):
        missing.append("Configure the proposal's Meta API version on the protected worker.")
    if not os.environ.get("META_WRITE_TOKEN"):
        missing.append("Connect the protected worker's Meta write credential.")
    return {"status": "setup_required" if missing else "configured", "missing": missing}


def sign(value, *, key=None):
    key = key or os.environ.get("META_ADS_OPERATOR_KEY") or os.environ.get("PANCHKRUTI_OPERATOR_KEY", "")
    if not key:
        from .state import ROOT
        from pathlib import Path
        database = Path(os.environ.get("META_ADS_STATE_DB") or ROOT / "data/lifecycle.sqlite3")
        path = database.parent / "meta-gateway/approval.key"
        if path.is_file():
            key = path.read_text(encoding="ascii")
    require(len(key) >= 32, "Use the protected operator environment to authorize writes.")
    return hmac.new(key.encode(), canonical(value).encode(), hashlib.sha256).hexdigest()


def identity(plan, client):
    instagram = any(p.startswith("instagram") for a in plan["adsets"] for p in a["placements"])
    actor = {"page_id": account_identity("page_id"), "pixel_id": account_identity("pixel_id"),
             "instagram_user_id": account_identity("instagram_id") if instagram else None}
    if actor["page_id"] and actor["pixel_id"] and (not instagram or actor["instagram_user_id"]):
        return {key: meta_id(value) if value else None for key, value in actor.items()}
    reference = (brand_profile() or {}).get("identity_reference")
    require(reference, "Connect the brand's Meta advertising identity or select its Page by name before building.")
    ad = client.scope(reference["ad_id"], "ad", reference["campaign_name"])
    require(ad.get("adset_id") == reference["adset_id"], "The saved Meta reference ad set changed.")
    aset = client.owned(reference["adset_id"], "promoted_object")
    creative = client.owned(ad["creative"]["id"], "object_story_spec")
    story = creative.get("object_story_spec") or {}
    media = story.get("link_data") or story.get("video_data") or {}
    link = (media.get("call_to_action") or {}).get("value", {}).get("link") or media.get("link")
    destination(link)
    readback = {"page_id": story.get("page_id"), "pixel_id": (aset.get("promoted_object") or {}).get("pixel_id"),
                "instagram_user_id": story.get("instagram_user_id") or story.get("instagram_actor_id")}
    for key in ("page_id", "pixel_id", *(("instagram_user_id",) if instagram else ())):
        require(readback.get(key), "The connected Meta ad did not return all publishing identities. "
                "Verify its Facebook Page, Instagram account when used, and Purchase source in Meta.")
        require(not actor[key] or actor[key] == readback[key], "The connected Meta publishing identity changed.")
        actor[key] = meta_id(readback[key])
    return actor


def scope_target(run, client, object_id, kinds):
    active = run["meta"]
    for kind in kinds:
        try:
            item = client.scope(object_id, kind, active["name"])
        except Stop:
            continue
        campaign_id = item["id"] if kind == "campaign" else item.get("campaign_id")
        if campaign_id == active["id"]:
            return kind, item
    raise Stop("Target is outside the enrolled managed campaign.")


def campaign_configuration(client, target):
    campaign = client.scope(target["id"], "campaign", target["name"])
    campaign_fields = "objective,configured_status,daily_budget,lifetime_budget,bid_strategy"
    adset_fields = ("id,campaign_id,configured_status,daily_budget,lifetime_budget,bid_strategy,"
                    "targeting,promoted_object,optimization_goal,attribution_spec,start_time,end_time")
    ad_fields = "id,campaign_id,adset_id,configured_status,creative"
    settings = {"campaign": client.owned(campaign["id"], campaign_fields), "adsets": {}, "ads": {}}
    for row in client.pages(f"{campaign['id']}/adsets", adset_fields):
        require(row["campaign_id"] == campaign["id"], "Ad set configuration is outside the campaign.")
        settings["adsets"][row["id"]] = row
    for row in client.pages(f"{campaign['id']}/ads", ad_fields):
        require(row["campaign_id"] == campaign["id"] and row["adset_id"] in settings["adsets"],
                "Ad configuration is outside the campaign.")
        creative_id = row["creative"]["id"]
        creative = client.owned(creative_id, "object_story_spec,asset_feed_spec,url_tags")
        settings["ads"][row["id"]] = {**row, "creative_settings": creative}
    return {key: fingerprint(value) for key, value in settings.items()}


def hard_cap(client, impact):
    account = client.request(client.prefix, {"fields": "spend_cap,amount_spent"})
    remaining = wire_minor(account.get("spend_cap")) - wire_minor(account.get("amount_spent"))
    require(0 < remaining <= policy()["maximum_monthly_minor"] - impact["spent_month_minor"],
            "Live account spend control does not cover the remaining monthly policy limit.")


def launch_cap_change(run, client, impact):
    """Prepare a bounded account-wide change; approval is required before any write."""
    account = client.request(client.prefix, {"fields": "spend_cap,amount_spent"})
    before, spent = wire_minor(account.get("spend_cap")), wire_minor(account.get("amount_spent"))
    headroom = policy()["maximum_monthly_minor"] - impact["spent_month_minor"]
    if 0 < before - spent <= headroom:
        return None
    criteria = run["records"]["strategy-development"]["data"]["criteria"]
    days = criteria["window_days"] + criteria["lag_days"]
    allowance = min(headroom, impact["daily_minor"] * days)
    require(allowance > 0, "No authorized monthly headroom remains for launch.")
    return {"scope": "account-wide", "from_minor": before, "to_minor": spent + allowance,
            "amount_spent_minor": spent, "remaining_minor": allowance, "planning_days": days,
            "reason": "Restore bounded delivery headroom under the saved monthly policy."}


def matches(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(matches(actual.get(k), v) for k, v in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and sorted(map(canonical, actual)) == sorted(map(canonical, expected))
    if isinstance(expected, bool):
        return actual is expected
    return str(actual) == str(expected)


def read_object(client, node, status):
    expected = node["settings"]
    fields = ",".join(expected)
    if status is not None:
        fields += ",configured_status,effective_status"
    data = client.owned(node["id"], fields)
    if "targeting" in expected:
        remote = data.get("targeting") or {}
        if expected["targeting"].get("custom_audiences"):
            require(not any((remote.get("targeting_relaxation_types") or {}).values()),
                    "Meta returned expanded audience targeting. Review the ad set before proceeding.")
        for field in ("custom_audiences", "excluded_custom_audiences"):
            if field in expected["targeting"]:
                remote[field] = [{"id": str(row["id"])} for row in remote.get(field, [])]
    comparison = data
    if node.get("kind") == "creative" and isinstance(expected.get("name"), str):
        returned_name = data.get("name")
        suffix = r" \d{4}-\d{2}-\d{2}-[0-9a-f]{32}"
        if isinstance(returned_name, str) and re.fullmatch(re.escape(expected["name"]) + suffix, returned_name):
            comparison = {**data, "name": expected["name"]}
    require(matches(comparison, expected), f"Meta settings on {node['id']} differ from the proposal.")
    if status:
        require(data["configured_status"] == status, f"Expected {status} on Meta object {node['id']}.")
    return data


def matches_by_name(client, edge, name):
    return [x["id"] for x in client.pages(f"{client.prefix}/{edge}", "id,name")
            if x["name"] == name]


def previews(client, ad_ids):
    checks = {}
    for ad in ad_ids:
        for placement in ad["placements"]:
            rows = list(client.pages(f"{ad['id']}/previews", "body", ad_format=PLACEMENTS[placement][2]))
            require(rows and all(row.get("body") for row in rows),
                    f"Meta did not return a {placement} preview for {ad['id']}.")
        checks[ad["id"]] = ad["placements"]
    return checks


def verify_batch(client, batch):
    cid = batch["campaign_id"]
    if not batch["addition"]:
        expected = {n["id"] for n in batch["objects"] if n["kind"] in {"ad", "adset"}}
        actual = {x["id"] for edge in ("adsets", "ads")
                  for x in client.pages(f"{cid}/{edge}", "id,configured_status")
                  if x["configured_status"] not in {"ARCHIVED", "DELETED"}}
        require(actual == expected, "Campaign has extra or missing ad sets or ads.")
    else:
        client.scope(cid, "campaign", batch["name"])
        for item in batch["adsets"]:
            read_object(client, item, "ACTIVE")
    for obj in batch["objects"]:
        if obj["kind"] == "ad":
            version = client.creative(obj["settings"]["creative"]["id"], obj["destination"], obj["format"])
            require(version == obj["creative_version"], "The Meta creative changed after the build.")


def make_proposal(run, client, assets=None):
    operation = GATES[run["step"]]
    records = run["records"]
    if operation != "pause":
        require(date.fromisoformat(records["strategy-development"]["data"]["next_review_on"]) >= now().date(),
                "Current strategy needs review before an account write.")
    require(client.details()["account_status"] == 1, "Meta account is inactive.")
    impact = None
    if operation == "build":
        plan = ad_plan(run, drive_inventory() if assets is None else assets)
        verify_audiences(client, plan["adsets"])
        addition = run.get("create_mode") in {"test", "refresh"}
        if not addition:
            require(not matches_by_name(client, "campaigns", plan["name"]), "Campaign name exists in Meta.")
        for aset in plan["adsets"]:
            for ad in aset["ads"]:
                require(not matches_by_name(client, "ads", ad["name"]), "Ad name exists in Meta.")
        impact = client.budget(add=0 if addition else plan["daily_minor"])
        action = {"plan": plan, "identity": identity(plan, client), "addition": addition}
    elif operation == "activate":
        batch = run["meta"]["pending_batch"]
        verify_audiences(client, batch.get("audience_adsets", []))
        readiness = records["activation-check"]["data"]
        require(all(readiness.get(f) is True for f in ("destination_ok", "purchase_event_ok", "checkout_ok")),
                "Required checkout, destination, and Purchase evidence is missing.")
        string(readiness.get("tracking_reference"), "tracking reference")
        string(readiness.get("spend_control_reference"), "spending control reference")
        require(readiness["preview_checks"] == previews(client, batch["ad_ids"]), "Placement preview scope changed.")
        verify_batch(client, batch)
        for node in batch["objects"]:
            read_object(client, node, "PAUSED")
        impact = client.budget(add=0 if batch["addition"] else batch["daily_minor"])
        cap_change = launch_cap_change(run, client, impact)
        action = {"batch": batch, "readiness": readiness}
        if cap_change:
            action["spend_control_change"] = cap_change
    elif operation == "pause":
        retirement = run["step"] == "retire"
        if run["step"] == "safety-pause":
            pending = run["safety_pause"]
            kind, item = "campaign", client.scope(pending["id"], "campaign", pending["name"])
            rationale = pending["reason"]
        elif retirement:
            old = run["pending_retirement"]
            new = client.scope(run["meta"]["id"], "campaign", run["meta"]["name"])
            require(new["effective_status"] == "ACTIVE", "Replacement campaign is not delivering yet.")
            kind, item = "campaign", client.scope(old["id"], "campaign", old["name"])
            rationale = f"Replacement {new['id']} is delivering. Retire the superseded managed campaign."
        else:
            decision = records["optimization-decision"]["data"]
            require(decision["decision"] == "PAUSE", "Expected the saved pause decision.")
            kind, item = scope_target(run, client, decision["target_id"], ("ad", "adset", "campaign"))
            rationale = decision["rationale"]
        require(item["configured_status"] == "ACTIVE", "Pause target is no longer active.")
        action = {"id": item["id"], "name": item["name"], "kind": kind, "before": "ACTIVE", "after": "PAUSED",
                  "rationale": rationale, "retirement": retirement}
    else:
        data = records["scaling-proposal"]["data"]
        require(records["scaling-eligibility"]["data"]["eligible"] is True
                and records["budget-validation"]["data"]["passed"] is True, "Scale gates did not pass.")
        before, after = data["from_daily_minor"], data["to_daily_minor"]
        analysis = records["scaling-analysis"]["data"]
        require(data["target_id"] == analysis["target_id"]
                and (before, after) == (analysis["current_daily_minor"], analysis["proposed_daily_minor"])
                and minor(after, positive=True) > minor(before, positive=True), "Increase differs from analysis.")
        kind, item = scope_target(run, client, data["target_id"], ("campaign", "adset"))
        require(item["configured_status"] == "ACTIVE" and item["effective_status"] == "ACTIVE"
                and wire_minor(item["daily_budget"]) == before, "Delivery or prior budget changed.")
        impact = client.budget(replace=(item["id"], before, after))
        hard_cap(client, impact)
        action = {"id": item["id"], "name": item["name"], "kind": kind, "before": before, "after": after,
                  "business_case": data["case"], "risks": data["risks"]}
    require(impact is None or impact["passed"], "Proposed operation does not fit account-wide limits.")
    proposal = {"run_id": run["id"], "account_id": run["request"]["account_id"], "operation": operation,
                "action": action, "impact": impact, "api_version": client.version,
                "plan_revision": fingerprint({k: v for k, v in records.items() if k != "scaling-approval"}),
                "policy": fingerprint(policy()), "request_revision": fingerprint(run["request"]),
                "created_at": stamp(), "nonce": uuid.uuid4().hex}
    proposal["id"] = fingerprint(proposal)
    return proposal


def expired(proposal, rules=None):
    return now() > parse_time(proposal["created_at"]) + timedelta(hours=(rules or policy())["approval_hours"])


def proposal_id(proposal):
    return fingerprint({k: v for k, v in proposal.items() if k != "id"})


def authorize(store, run_id, proposal_ref, *, operator, owner, reference, reject=False, renew=False):
    from .gateway import enabled, operator_key
    signing_key = operator_key(store) if enabled(store) else None
    with store.lease("executor"):
        run = store.get(run_id)
        rules = policy(run["request"].get("brand"))
        p = run["proposal"]
        require(p and p["id"] == proposal_id(p) == proposal_ref, "No matching exact proposal.")
        missing = approval_setup(run)
        require(not missing, " ".join(missing))
        if renew:
            require(not reject and run["status"] in {"approved", "execution_blocked"}
                    and run["write_journal"].get(p["id"]), "Renewal is only for an approved partially executed proposal.")
            verify_approval(run, readback_only=True, signing_key=signing_key)
            require(approval_expired(run), "The current approval is still valid.")
        else:
            require(run["status"] == "awaiting_approval", "The proposal must be awaiting approval.")
            require(not expired(p, rules), "Proposal expired. Prepare a fresh one.")
        string(operator, "operator identity")
        string(reference, "decision reference")
        require("operators" not in rules or operator in rules["operators"], "Operator is outside the brand policy.")
        if p["operation"] in rules.get("owner_approval_actions", OWNER_ACTIONS) and not reject:
            string(owner, "owner identity for explicit approval")
            require(not rules.get("owners") or owner in rules["owners"], "Owner is outside the brand policy.")
        decision = {"proposal_id": proposal_ref, "operator": operator, "owner": owner,
                    "reference": reference, "at": stamp(), "approved": not reject}
        run["approval"] = {**decision, "signature": sign(decision, key=signing_key)}
        if reject:
            run.update(status="blocked", outcome="STOP", blockers=["Operator rejected this proposal."])
        else:
            run["status"] = "approved"
            if p["operation"] == "budget":
                run["step"] = "scaling-execution"
        if p["operation"] == "budget":
            run["records"]["scaling-approval"] = {"status": "pass" if not reject else "block",
                                                  "data": {"approval": decision}}
        store.save(run, "operator_renewal" if renew else "operator_decision", decision)
        return run


def approval_expired(run):
    return now() > parse_time(run["approval"]["at"]) + timedelta(
        hours=policy(run["request"].get("brand"))["approval_hours"])


def verify_approval(run, *, readback_only=False, signing_key=None):
    p, a = run["proposal"], run["approval"]
    rules = policy(run["request"].get("brand"))
    require(p["id"] == proposal_id(p), "Proposal content changed after approval.")
    require(a["approved"] is True and a["proposal_id"] == p["id"]
            and hmac.compare_digest(a["signature"], sign({k: v for k, v in a.items() if k != "signature"}, key=signing_key)),
            "Invalid approval for this proposal.")
    require("operators" not in rules or a["operator"] in rules["operators"], "Operator is outside the brand policy.")
    if p["operation"] in rules.get("owner_approval_actions", OWNER_ACTIONS):
        string(a["owner"], "owner approval")
        require(not rules.get("owners") or a["owner"] in rules["owners"], "Owner is outside the brand policy.")
    require(p["policy"] == fingerprint(rules), "Policy changed after approval.")
    require(p["request_revision"] == fingerprint(run["request"]), "Request evidence changed after approval.")
    records = {k: v for k, v in run["records"].items() if k != "scaling-approval"}
    require(p["plan_revision"] == fingerprint(records), "Input records changed after approval.")
    require(readback_only or not approval_expired(run), "Approval expired. Refresh before making another write.")
    return p


def upload(client, asset, data):
    require(client.writer and isinstance(data, bytes), "The write requires verified media bytes.")
    video = asset["mime"] == "video/mp4"
    edge, field = ("advideos", "source") if video else ("adimages", "filename")
    ext = {"image/png": "png", "image/jpeg": "jpg", "video/mp4": "mp4"}[asset["mime"]]
    boundary = uuid.uuid4().hex
    name = asset["file_id"]
    title = f"--{boundary}\r\nContent-Disposition: form-data; name=\"title\"\r\n\r\n{name}\r\n".encode()
    header = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{field}\"; filename=\"{name}.{ext}\"\r\n"
              f"Content-Type: {asset['mime']}\r\n\r\n").encode()
    body = (title if video else b"") + header + data + f"\r\n--{boundary}--\r\n".encode()
    url = f"https://graph.facebook.com/{client.version}/{client.prefix}/{edge}"
    req = Request(url, data=body, headers={"Authorization": f"Bearer {client.token}",
                                           "Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with client.opener.open(req, timeout=120) as response:
            payload = json.load(response)
    except (HTTPError, OSError, ValueError):
        raise Stop("Meta media upload was not confirmed. Reconcile before retrying.") from None
    if video:
        return {"id": meta_id(payload["id"])}
    images = list(payload["images"].values())
    require(len(images) == 1, "Expected one Meta image result.")
    return {"hash": string(images[0]["hash"], "image hash")}


class Executor:
    def __init__(self, store, run, client):
        self.store, self.run, self.client = store, run, client
        self.proposal = verify_approval(run)
        require(client.writer and client.version == self.proposal["api_version"], "Executor API version changed.")
        require(client.details()["account_status"] == 1, "Meta account is inactive.")
        self.action = self.proposal["action"]
        self.journal = run["write_journal"].setdefault(self.proposal["id"], {})

    def step(self, key, context, send, verify):
        entry = self.journal.get(key)
        if entry is None:
            require(not approval_expired(self.run), "Approval expired during execution.")
            entry = self.journal[key] = {"state": "pending", "context": context}
            self.store.save(self.run, "meta_write_pending", {"operation": key, **context})
            entry.update(state="sent", response=send())
            self.store.save(self.run, "meta_write_returned", {"operation": key, "response": entry["response"]})
        require(entry["state"] != "pending", f"Unconfirmed Meta write {key}. Reconcile it before continuing.")
        value = verify(entry["response"])
        if entry["state"] != "verified":
            entry.update(state="verified", readback=value, at=stamp())
            self.store.save(self.run, "meta_write_verified", {"operation": key, "readback": value})
        return value

    def create(self, key, kind, edge, payload, extra=None):
        client = self.client
        expected = {k: v for k, v in payload.items() if k != "status"}
        if kind == "ad":
            expected["creative"] = {"id": payload["creative"]["creative_id"]}
        status = payload.get("status")
        if kind in {"campaign", "ad"} and key not in self.journal:
            require(not matches_by_name(client, edge, payload["name"]), f"Duplicate Meta name {payload['name']}.")

        def verify(response):
            node = {"id": meta_id(response["id"]), "kind": kind, "settings": expected, **(extra or {})}
            remote = read_object(client, node, status)
            if status:
                node.update(configured_status=remote["configured_status"], effective_status=remote["effective_status"])
            return node

        return self.step(key, {"edge": edge, "kind": kind, "settings": expected, "status": status},
                         lambda: {"id": meta_id(client.request(client.prefix + "/" + edge, payload, post=True)["id"])},
                         verify)

    def media(self, asset):
        video = asset["mime"] == "video/mp4"
        def verify(response):
            if video:
                item = self.client.request(response["id"], {"fields": "id,status"})
                status = item.get("status", {}).get("video_status")
                require(item["id"] == response["id"], "Unexpected Meta video ID.")
                if status in {"processing", "uploading"}:
                    raise Deferred(f"Video {response['id']} is {status}. The operator dispatcher will read it again.")
                require(status == "ready", f"Video {response['id']} has status {status or 'unknown'}. Inspect in Meta.")
            else:
                images = self.client.pages(self.client.prefix + "/adimages", "hash", hashes=[response["hash"]])
                require(any(row["hash"] == response["hash"] for row in images), "Image missing from Meta account.")
            return response
        key = ("video:" if video else "image:") + asset["file_id"]
        raw = None
        if key not in self.journal:
            if self.run.get("connected"):
                from .connected import read_media
                raw = read_media(self.store, self.run, asset)
            else:
                raw = drive_media(asset)
        return self.step(key, {"kind": "video" if video else "image", "asset": asset},
                         lambda: upload(self.client, asset, raw), verify)

    def budget(self, *, add=0, replace=None, enforce_cap=False):
        impact = self.client.budget(replace=replace, add=add)
        require(impact["passed"] and impact["daily_minor"] <= self.proposal["impact"]["daily_minor"],
                "Current account exposure exceeds the approved daily allocation or monthly policy.")
        if enforce_cap:
            hard_cap(self.client, impact)

    def build(self):
        plan, actor, addition = (self.action[k] for k in ("plan", "identity", "addition"))
        verify_audiences(self.client, plan["adsets"])
        require(identity(plan, self.client) == actor, "Configured Meta identity changed after approval.")
        if self.run.get("connected"):
            from .connected import current_media, read_media
            live = current_media(self.run)["assets"]
        else:
            live = drive_inventory()
        ids = {k for aset in plan["adsets"] for ad in aset["ads"]
               for k in (ad["asset_id"], ad["poster_asset_id"]) if k}
        for k in ids:
            require(live.get(k) == plan["assets"][k], "An approved Drive asset changed or moved.")
            if self.run.get("connected"):
                read_media(self.store, self.run, live[k])
        self.budget(add=0 if addition else plan["daily_minor"])
        name = plan["name"]
        nodes, ads, parents = [], [], []
        if addition:
            campaign_id = self.run["meta"]["id"]
            current = self.client.scope(campaign_id, "campaign", name)
            require(current["configured_status"] == "ACTIVE", "Existing campaign is no longer active.")
        else:
            payload = {"name": name, "objective": plan["objective"], "special_ad_categories": [], "status": "PAUSED"}
            if plan["budget_level"] == "campaign":
                payload.update(daily_budget=plan["daily_minor"], bid_strategy="LOWEST_COST_WITHOUT_CAP")
            else:
                payload["is_adset_budget_sharing_enabled"] = False
            item = self.create("campaign", "campaign", "campaigns", payload)
            campaign_id = item["id"]
            nodes.append(item)
        for aset in plan["adsets"]:
            fields = {"name": aset["name"], "campaign_id": campaign_id, "targeting": targeting(aset),
                      "promoted_object": {"pixel_id": actor["pixel_id"], "custom_event_type": "PURCHASE"}}
            if addition:
                current = {"id": aset["existing_adset_id"], "kind": "adset", "settings": fields}
                read_object(self.client, current, "ACTIVE")
                adset_id = current["id"]
                parents.append(current)
            else:
                fields.update(status="PAUSED", billing_event="IMPRESSIONS", destination_type="WEBSITE",
                              optimization_goal="OFFSITE_CONVERSIONS")
                if plan["budget_level"] == "adset":
                    fields["daily_budget"] = aset["daily_minor"]
                item = self.create("adset:" + aset["name"], "adset", "adsets", fields)
                adset_id = item["id"]
                nodes.append(item)
            for ad in aset["ads"]:
                asset = plan["assets"][ad["asset_id"]]
                media = self.media(asset)
                story = {"page_id": actor["page_id"]}
                if any(p.startswith("instagram") for p in aset["placements"]):
                    story["instagram_user_id"] = actor["instagram_user_id"]
                link = ad["destination"]
                cta = {"type": ad["cta"], "value": {"link": link}}
                if asset["mime"] == "video/mp4":
                    poster = self.media(plan["assets"][ad["poster_asset_id"]])
                    story["video_data"] = {"video_id": media["id"], "image_hash": poster["hash"],
                                           "message": ad["primary_text"], "title": ad["headline"],
                                           "call_to_action": cta}
                    if ad["description"]:
                        story["video_data"]["link_description"] = ad["description"]
                else:
                    story["link_data"] = {"image_hash": media["hash"], "link": link, "message": ad["primary_text"],
                                          "name": ad["headline"], "call_to_action": cta}
                    if ad["description"]:
                        story["link_data"]["description"] = ad["description"]
                slug = ad["name"]
                creative = self.create("creative:" + slug, "creative", "adcreatives",
                                       {"name": slug, "object_story_spec": story, "url_tags": ad["url_tags"]})
                version = self.client.creative(creative["id"], link, ad["format"])
                item = self.create("ad:" + slug, "ad", "ads",
                                   {"name": slug, "status": "PAUSED", "adset_id": adset_id,
                                    "creative": {"creative_id": creative["id"]}},
                                   {"destination": link, "format": ad["format"], "creative_version": version})
                require(item["effective_status"] != "ACTIVE", "Meta ad appears to be delivering despite PAUSED.")
                nodes.append(item)
                ads.append({"id": item["id"], "placements": aset["placements"]})
        batch = {"campaign_id": campaign_id, "addition": addition, "daily_minor": plan["daily_minor"],
                 "name": name, "objects": nodes, "ad_ids": ads, "adsets": parents, "identity": actor}
        audience_adsets = [{"audience": aset["audience"]} for aset in plan["adsets"] if "audience" in aset]
        if audience_adsets:
            batch["audience_adsets"] = audience_adsets
        verify_batch(self.client, batch)
        return batch

    def update(self, key, object_id, field, before, after):
        def current():
            value = self.client.owned(object_id, field)[field]
            return wire_minor(value) if field == "daily_budget" else value

        if not self.journal.get(key):
            require(current() == before, "Meta current value differs from the approved starting value.")

        def send():
            param = "status" if field == "configured_status" else field
            self.client.request(object_id, {param: after}, post=True)
            return {"id": object_id}

        def readback(_):
            require(current() == after, f"Meta has not confirmed {field} for {object_id}.")
            return {"id": object_id, field: after}

        return self.step(key, {"kind": "update", "id": object_id, "field": field, "before": before, "after": after},
                         send, readback)

    def activate(self):
        batch = self.action["batch"]
        verify_audiences(self.client, batch.get("audience_adsets", []))
        verify_batch(self.client, batch)
        for obj in batch["objects"]:
            state = self.journal.get("activate:" + obj["id"], {}).get("state")
            read_object(self.client, obj, "ACTIVE" if state in {"sent", "verified"} else "PAUSED")
            if obj["kind"] == "ad":
                require(storefront(obj["destination"])["reachable"], "Ad destination is no longer reachable.")
        active_parent = any(n["kind"] == "campaign" and self.journal.get("activate:" + n["id"], {}).get("response")
                            for n in batch["objects"])
        change = self.action.get("spend_control_change")
        if change:
            self.budget(add=0 if batch["addition"] or active_parent else batch["daily_minor"])
            self.account_cap(change)
        self.budget(add=0 if batch["addition"] or active_parent else batch["daily_minor"], enforce_cap=True)
        for obj in sorted(batch["objects"], key=lambda n: {"ad": 0, "adset": 1, "campaign": 2}[n["kind"]]):
            oid = obj["id"]
            if obj["kind"] == "campaign" and "activate:" + oid not in self.journal:
                self.budget(add=batch["daily_minor"], enforce_cap=True)
            self.update("activate:" + oid, oid, "configured_status", "PAUSED", "ACTIVE")
        receipt = {"campaign_id": batch["campaign_id"], "objects": [
            self.client.owned(n["id"], "configured_status,effective_status") for n in batch["objects"]]}
        if change:
            receipt["spend_control"] = self.journal["account-spend-cap"]["readback"]
        return receipt

    def account_cap(self, change):
        key = "account-spend-cap"
        def read():
            return self.client.request(self.client.prefix, {"fields": "spend_cap,amount_spent"})
        current = read()
        spent = wire_minor(current.get("amount_spent"))
        require(spent >= change["amount_spent_minor"], "Account spend counter changed; refresh the launch proposal.")
        if key not in self.journal:
            require(wire_minor(current.get("spend_cap")) == change["from_minor"],
                    "Account spending limit changed; refresh the launch proposal.")
            require(0 < change["to_minor"] - spent <= change["remaining_minor"],
                    "The proposed account spending headroom is no longer valid.")
        def send():
            # Meta reads spend_cap in minor units but writes it in major currency units.
            value = format(Decimal(change["to_minor"]) / policy()["minor_per_unit"], "f")
            self.client.request(self.client.prefix, {"spend_cap": value}, post=True)
            return {"id": self.client.prefix}
        def verify(_):
            observed = read()
            require(wire_minor(observed.get("spend_cap")) == change["to_minor"],
                    "Meta has not confirmed the approved account spending limit.")
            return {"id": self.client.prefix, "spend_cap_minor": change["to_minor"],
                    "amount_spent_minor": wire_minor(observed.get("amount_spent"))}
        return self.step(key, {"kind": "account_spend_cap", "id": self.client.prefix,
                              "before": change["from_minor"], "after": change["to_minor"]}, send, verify)

    def edit(self):
        op, data = self.proposal["operation"], self.action
        scope = self.run
        if data.get("retirement"):
            live = self.run["meta"]
            require(self.client.scope(live["id"], "campaign", live["name"])["effective_status"] == "ACTIVE",
                    "Replacement campaign is no longer delivering.")
            scope = {**self.run, "meta": self.run["pending_retirement"]}
        kind, current = scope_target(scope, self.client, data["id"], (data["kind"],))
        require(kind == data["kind"] and current["name"] == data["name"], "Managed target changed.")
        field = "daily_budget" if op == "budget" else "configured_status"
        if op == "budget" and op not in self.journal:
            require(current["effective_status"] == "ACTIVE", "Target is no longer active at execution.")
            self.budget(replace=(data["id"], data["before"], data["after"]), enforce_cap=True)
        return self.update(op, data["id"], field, data["before"], data["after"])


def reconcile(store, run_id, operation, client, verified_id=None, *, absent=False, reference=None):
    # Reconciliation performs only provider reads. An absent or ambiguous result stays pending.
    with store.lease("executor"):
        run = store.get(run_id)
        require(run.get("approval"), "No operator authorization to reconcile.")
        p = verify_approval(run, readback_only=True)
        journal = run["write_journal"].get(p["id"], {})
        item = journal.get(operation)
        require(item and item["state"] == "pending", "Expected one pending operation.")
        c = item["context"]
        if absent:
            require(verified_id is None and reference, "Supply operator evidence that the request did not apply.")
            if c["kind"] == "account_spend_cap":
                value = wire_minor(client.request(client.prefix, {"fields": "spend_cap"}).get("spend_cap"))
                require(value == c["before"], "Account spending limit is no longer at its approved starting value.")
            elif c["kind"] == "update":
                value = client.owned(c["id"], c["field"])[c["field"]]
                if c["field"] == "daily_budget":
                    value = wire_minor(value)
                require(value == c["before"], "Meta is no longer at the approved starting value.")
            elif c["kind"] not in {"image", "video"}:
                require(not matches_by_name(client, c["edge"], c["settings"]["name"]),
                        "One or more matching objects exist. Reconcile the correct object instead.")
            del journal[operation]
            run["status"] = "approved"
            store.save(run, "operator_confirmed_absence",
                       {"operation": operation, "reference": reference, "context": c})
            return run
        if c["kind"] == "account_spend_cap":
            require(wire_minor(client.request(client.prefix, {"fields": "spend_cap"}).get("spend_cap")) == c["after"],
                    "Approved account spending limit is not confirmed in Meta.")
            response = {"id": client.prefix}
        elif c["kind"] == "update":
            value = client.owned(c["id"], c["field"])[c["field"]]
            if c["field"] == "daily_budget":
                value = wire_minor(value)
            require(value == c["after"], "Proposed update is not confirmed in Meta.")
            response = {"id": c["id"]}
        elif c["kind"] in {"image", "video"}:
            raise Stop("Unknown upload result requires operator investigation in the Meta asset library.")
        else:
            names = matches_by_name(client, c["edge"], c["settings"]["name"])
            require(len(names) == 1 and (verified_id is None or names[0] == verified_id),
                    "No unique matching Meta object can be reconciled.")
            read_object(client, {"id": names[0], "settings": c["settings"]}, c["status"])
            response = {"id": names[0]}
        item.update(response=response, state="sent")
        run["status"] = "approved"
        store.save(run, "meta_write_reconciled", {"operation": operation, "response": response})
        return run
