"""Restricted Marketing API transport and readback helpers."""

import calendar
import hashlib
import json
import os
import re
import time
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

LEGACY_PROFILE_FILE = Path(__file__).resolve().parents[2] / "data/legacy-brand.json"
_brand = ContextVar("brand", default=None)


class Stop(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Stop(message)


def provider_error(error, path, token):
    """Retain actionable Graph errors without exposing credentials or raw payloads."""
    message = f"Meta returned HTTP {error.code} for {path}."
    try:
        details = json.loads(error.read(16000)).get("error", {})
        codes = [str(details[k]) for k in ("code", "error_subcode") if type(details.get(k)) is int]
        explanation = details.get("error_user_msg") or details.get("error_user_title") or details.get("message")
        if codes:
            message += " Graph code " + "/".join(codes) + "."
        if isinstance(explanation, str):
            explanation = explanation.replace(token, "[redacted]") if token else explanation
            explanation = re.sub(r"access_token=[^\s&]+|EAA[A-Za-z0-9]{40,}", "[redacted]", explanation)
            message += " " + " ".join(explanation.split())[:600]
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return message


def canonical(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def fingerprint(data):
    return hashlib.sha256(canonical(data).encode()).hexdigest()


@contextmanager
def configured(brand):
    token = _brand.set(brand)
    try:
        yield
    finally:
        _brand.reset(token)


def brand_profile():
    return _brand.get()


def legacy_profile():
    require(LEGACY_PROFILE_FILE.is_file(), "Load a saved brand profile. This copy has no legacy brand settings.")
    return json.loads(LEGACY_PROFILE_FILE.read_text(encoding="utf-8"))


def policy(brand=None):
    profile = brand if brand is not None else brand_profile()
    return (profile or legacy_profile())["policy"]


def account_identity(field):
    profile = brand_profile()
    if profile is not None:
        return profile.get(field)
    env = {"page_id": "META_PAGE_ID", "pixel_id": "META_PIXEL_ID", "instagram_id": "META_INSTAGRAM_USER_ID"}
    return os.environ.get(env[field])


def account_zone(name):
    if name == "UTC":
        return timezone.utc
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        if name in {"Asia/Kolkata", "Asia/Calcutta"}:
            return timezone(timedelta(hours=5, minutes=30), name)
        raise Stop("Install tzdata for the configured Meta account time zone.") from None


def meta_id(value):
    require(isinstance(value, str) and re.fullmatch(r"[1-9][0-9]{0,29}", value), "Expected a numeric Meta ID string.")
    return value


def minor(value, *, positive=False):
    require(type(value) is int and value >= int(positive), "Expected integer minor currency units.")
    return value


def wire_minor(value):
    if value is None:
        return 0
    require(isinstance(value, (int, str)) and re.fullmatch(r"[0-9]+", str(value)), "Invalid Meta budget field.")
    return int(value)


def budget_projection(funding, rules):
    spend = Decimal(funding["spend"]) * rules["minor_per_unit"]
    require(spend.is_finite() and spend >= 0 and spend == spend.to_integral_value(), "Invalid account spend.")
    amount = minor(funding["daily_minor"])
    remaining = minor(funding["assumed_remaining_days"], positive=True)
    projected = int(spend) + amount * remaining
    return {"as_of": funding["as_of"], "timezone": funding["timezone"], "spent_month_minor": int(spend),
            "scope": "account-wide", "account_spent_month_minor": int(spend),
            "assumed_remaining_days": remaining, "daily_minor": amount, "monthly_minor": projected,
            "passed": (rules["minimum_daily_minor"] <= amount <= rules["maximum_daily_minor"]
                       and projected <= rules["maximum_monthly_minor"])}


def campaign_key(value):
    require(isinstance(value, str) and len(value) <= 100
            and re.fullmatch(r"agi-[a-z0-9]+(?:-[a-z0-9]+)+", value), "Expected agi-<product>-<initiative>.")
    return value


def child_name(value, root, *, ad=False):
    require(isinstance(value, str) and value.startswith(root + "-") and len(value) <= 160,
            "Child name does not match its managed campaign.")
    suffix = value[len(root)+1:]
    pattern = (r"(discovery|consideration|purchase)-[a-z0-9]+(?:-[a-z0-9]+)*-(static|video|story)-v[0-9]{2,}"
               if ad else r"[a-z0-9]+(?:-[a-z0-9]+)*")
    require(re.fullmatch(pattern, suffix), "Invalid managed child name.")
    return value


def destination(value, website=None):
    require(isinstance(value, str) and value == value.strip() and not any(ch.isspace() for ch in value),
            "Expected a valid product URL.")
    url = urlparse(value)
    profile = brand_profile()
    website = website or (profile["website"] if profile else None)
    hosts = {urlparse(website).hostname} if website else set(legacy_profile()["website_hosts"])
    require(url.scheme == "https" and url.hostname in hosts and url.netloc.lower() == url.hostname
            and url.path.strip("/") and not url.fragment,
            "Expected an HTTPS product page on the configured website.")
    if not website:
        require(url.path.startswith("/products/") and len(url.path) > len("/products/"),
                "Expected a legacy Shopify product page.")
    return value


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Meta:
    def __init__(self, account, *, writer=False):
        self.account = meta_id(account)
        self.prefix = f"act_{account}"
        require(os.environ.get("META_AD_ACCOUNT_ID", "").removeprefix("act_") == account,
                "Configure the exact META_AD_ACCOUNT_ID.")
        self.version = os.environ.get("META_API_VERSION", "")
        require(re.fullmatch(r"v[0-9]+\.[0-9]+", self.version), "Set META_API_VERSION to a supported version.")
        self.writer = writer
        key = "META_WRITE_TOKEN" if writer else "META_READ_TOKEN"
        self.token = os.environ.get(key)
        require(bool(self.token), f"Missing {key}.")
        self.opener = build_opener(NoRedirect())

    def request(self, path, params, *, post=False):
        require(not post or self.writer, "Read client cannot write.")
        require(re.fullmatch(r"(?:act_)?[1-9][0-9]*(?:/[a-z_]+)?", path), "Unapproved API path.")
        values = {k: canonical(v) if isinstance(v, (dict, list, bool)) else str(v) for k, v in params.items()}
        form = urlencode(values)
        url = f"https://graph.facebook.com/{self.version}/{path}"
        req = Request(url if post else f"{url}?{form}", data=form.encode() if post else None,
                      headers={"Authorization": f"Bearer {self.token}",
                               "Content-Type": "application/x-www-form-urlencoded"})
        attempts = 1 if post else 3
        for attempt in range(attempts):
            try:
                with self.opener.open(req, timeout=30) as response:
                    if response.headers.get("X-Ad-Api-Version-Warning"):
                        raise Stop("Meta reports an API version upgrade. Verify and update the configured version.")
                    result = json.load(response)
                break
            except HTTPError as error:
                if attempt + 1 == attempts or error.code not in {429, 500, 502, 503, 504}:
                    raise Stop(provider_error(error, path, self.token)) from None
            except OSError:
                if attempt + 1 == attempts:
                    raise Stop(f"Meta request did not complete for {path}. Check write readback before resuming.") from None
            time.sleep(2 ** attempt)
        require(isinstance(result, dict) and "error" not in result, "Unexpected Meta response.")
        return result

    def pages(self, path, fields, **params):
        params = {"fields": fields, "limit": 100, **params}
        seen = set()
        for _ in range(500):
            result = self.request(path, params)
            require(isinstance(result.get("data"), list), "Missing Meta results.")
            yield from result["data"]
            paging = result.get("paging", {})
            if not paging.get("next"):
                return
            cursor = paging.get("cursors", {}).get("after")
            require(isinstance(cursor, str) and cursor and cursor not in seen, "Invalid Meta pagination.")
            seen.add(cursor)
            params["after"] = cursor
        raise Stop("Meta pagination exceeded the bound; account evidence is incomplete.")

    def details(self):
        result = self.request(self.prefix, {"fields": "account_id,currency,timezone_name,account_status"})
        require(result["account_id"] == self.account and result["currency"] == policy()["currency"],
                "Meta account or currency differs from the configured brand.")
        return result

    def owned(self, object_id, fields):
        object_id = meta_id(object_id)
        data = self.request(object_id, {"fields": "id,account_id," + fields})
        require(data.get("id") == object_id and data.get("account_id") == self.account,
                "Object outside configured account.")
        return data

    def scope(self, object_id, kind, key):
        campaign_key(key)
        if kind == "campaign":
            obj = self.owned(object_id, "name,objective,configured_status,effective_status,daily_budget,lifetime_budget")
            require(obj["name"] == key and obj.get("objective"), "Unexpected campaign name or type.")
        elif kind == "adset":
            obj = self.owned(object_id, "name,campaign_id,configured_status,effective_status,daily_budget,lifetime_budget")
            child_name(obj["name"], key)
            self.scope(obj["campaign_id"], "campaign", key)
        else:
            require(kind == "ad", "Unknown Meta object type.")
            obj = self.owned(object_id, "name,campaign_id,adset_id,configured_status,effective_status,creative")
            child_name(obj["name"], key, ad=True)
            parent = self.scope(obj["adset_id"], "adset", key)
            require(parent["campaign_id"] == obj["campaign_id"], "Incorrect ad parent hierarchy.")
        return obj

    def account_report(self):
        account = self.details()
        managed = []
        for row in self.pages(self.prefix + "/campaigns", "id,name"):
            if not isinstance(row.get("name"), str) or not row["name"].startswith("agi-"):
                continue
            try:
                key = campaign_key(row["name"])
            except Stop:
                continue
            obj = self.scope(row["id"], "campaign", key)
            obj["adsets"] = []
            for child in self.pages(f"{obj['id']}/adsets", "id,name"):
                try:
                    child_name(child["name"], key)
                except Stop:
                    continue
                adset = self.scope(child["id"], "adset", key)
                require(adset["campaign_id"] == obj["id"], "Unexpected ad set parent.")
                adset["ads"] = []
                for ad in self.pages(f"{adset['id']}/ads", "id,name"):
                    try:
                        child_name(ad["name"], key, ad=True)
                    except Stop:
                        continue
                    verified = self.scope(ad["id"], "ad", key)
                    require(verified["adset_id"] == adset["id"], "Unexpected ad parent.")
                    adset["ads"].append(verified)
                obj["adsets"].append(adset)
            managed.append(obj)
        return {"account": account, "managed_objects": managed}

    def audience_inventory(self):
        fields = ("id,account_id,name,subtype,retention_days,operation_status,delivery_status,"
                  "approximate_count_lower_bound,approximate_count_upper_bound,fields_violating_integrity_policy")
        return list(self.pages(self.prefix + "/customaudiences", fields))

    def creative(self, creative_id, link, fmt):
        item = self.owned(creative_id, "object_story_spec,url_tags,asset_feed_spec,product_set_id")
        require(not item.get("asset_feed_spec") and not item.get("product_set_id"),
                "Dynamic and catalogue creatives are excluded.")
        spec = item.get("object_story_spec", {})
        media = spec.get("link_data") or spec.get("video_data") or {}
        require(not media.get("child_attachments") and not media.get("product_set_id"),
                "Only a single approved asset is supported.")
        require(bool(spec.get("video_data")) if fmt == "video" else
                bool(spec.get("link_data")) if fmt == "static" else bool(media),
                "Meta creative does not match approved format.")
        cta_link = media.get("call_to_action", {}).get("value", {}).get("link")
        links = [url for url in (media.get("link"), cta_link) if url is not None]
        require(links and all(url == destination(link) for url in links),
                "Meta creative destination differs from the approved product link.")
        return fingerprint(item)

    def budget(self, *, replace=None, add=0):
        return budget_projection(self.funding(replace=replace, add=add), policy())

    def funding(self, *, replace=None, add=0):
        account = self.details()
        require(account["account_status"] == 1, "Meta account is not active.")
        tz = account["timezone_name"]
        zone = account_zone(tz)
        today = datetime.now(zone).date()
        amount, replaced, ids = minor(add), False, set()
        fields = "id,configured_status,daily_budget,lifetime_budget"

        def exposure(row):
            nonlocal replaced
            require(not wire_minor(row.get("lifetime_budget")), "Unbounded daily exposure from lifetime funding.")
            current = wire_minor(row.get("daily_budget"))
            if replace and row["id"] == replace[0]:
                require(not replaced and current == replace[1], "Live funding changed; prepare a new proposal.")
                replaced = True
                return replace[2]
            return current

        def active(row):
            key = meta_id(row["id"])
            require(key not in ids, "Duplicate account funding object.")
            ids.add(key)
            status = row["configured_status"]
            require(status in {"ACTIVE", "PAUSED", "DELETED", "ARCHIVED"}, "Unknown account funding status.")
            return status == "ACTIVE"

        for campaign in self.pages(self.prefix + "/campaigns", fields):
            if not active(campaign):
                continue
            loaded = exposure(campaign)
            has_campaign_budget = bool(wire_minor(campaign.get("daily_budget")))
            children = [row for row in self.pages(campaign["id"] + "/adsets", fields + ",campaign_id")
                        if active(row)]
            if has_campaign_budget:
                require(not any(wire_minor(x.get("daily_budget")) or wire_minor(x.get("lifetime_budget")) for x in children),
                        "Mixed funding levels cannot be counted safely.")
                amount += loaded
            else:
                for row in children:
                    require(row["campaign_id"] == campaign["id"], "Funding has an unexpected parent.")
                    budget = exposure(row)
                    require(budget > 0, "Missing active ad set funding.")
                    amount += budget
        require(not replace or replaced, "Active budget target was not found in account exposure.")
        response = list(self.pages(self.prefix + "/insights", "spend", level="account",
                                   time_range={"since": today.replace(day=1).isoformat(), "until": today.isoformat()}))
        require(len(response) <= 1, "Unexpected account spend response.")
        remaining = calendar.monthrange(today.year, today.month)[1] - today.day + 1
        return {"as_of": today.isoformat(), "timezone": tz,
                "spend": response[0]["spend"] if response else "0",
                "assumed_remaining_days": remaining, "daily_minor": amount}
