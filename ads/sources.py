"""Bounded, read-only evidence collection for the worker."""
import hashlib
import json
import os
import re
import subprocess
import time
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, build_opener

from .meta import NoRedirect, Stop, account_zone, brand_profile, canonical, destination, policy, require
from .state import stamp

PRODUCT = """query AdsProduct($id: ID!, $after: String) {
  product(id: $id) {
    id title handle status onlineStoreUrl description
    variants(first: 50, after: $after) {
      nodes { id title price compareAtPrice inventoryQuantity inventoryPolicy inventoryItem { tracked } }
      pageInfo { hasNextPage endCursor }
    }
  }
}"""
ORDERS = """query AdsOrders($query: String!, $after: String) {
  orders(first: 10, after: $after, query: $query, sortKey: CREATED_AT) {
    nodes {
      createdAt cancelledAt test displayFinancialStatus
      currentTotalPriceSet { shopMoney { amount currencyCode } }
      totalReceivedSet { shopMoney { amount currencyCode } }
      totalRefundedSet { shopMoney { amount currencyCode } }
      currentTotalTaxSet { shopMoney { amount currencyCode } }
      customerJourneySummary {
        ready customerOrderIndex lastVisit { utmParameters { source medium campaign content } }
      }
      lineItems(first: 20) {
        nodes { currentQuantity product { id } variant { id } }
        pageInfo { hasNextPage }
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}"""
META_FIELDS = ("campaign_id,adset_id,ad_id,spend,impressions,reach,frequency,inline_link_clicks,"
               "outbound_clicks,actions,action_values,date_start,date_stop")
ROOT_DRIVE = "https://www.googleapis.com/drive/v3"
OPEN = build_opener(NoRedirect())
MAX_MEDIA_BYTES = 50 * 1024 * 1024
_drive_session = None


def token(name):
    value = os.environ.get(name)
    require(bool(value), f"Missing {name} in this process.")
    return value


def fetch(url, headers, *, body=None, cap=8_000_000):
    request = Request(url, data=body, headers=headers)
    # Used for reads and token refresh. Meta write transport is separate.
    for attempt in range(3):
        try:
            with OPEN.open(request, timeout=30) as response:
                data = response.read(cap + 1)
            break
        except HTTPError as error:
            if attempt == 2 or error.code not in {429, 500, 502, 503, 504}:
                raise Stop(f"Read failed with HTTP {error.code} from {request.host}.") from None
        except OSError:
            if attempt == 2:
                raise Stop(f"Read timed out or was unavailable from {request.host}.") from None
        time.sleep(2 ** attempt)
    require(len(data) <= cap, f"Response from {request.host} exceeds the configured byte limit.")
    return data


def gql(query, variables):
    domain = token("SHOPIFY_SHOP")
    profile = brand_profile()
    require(not profile or profile["shopify_shop"] == domain, "Connected Shopify shop differs from the brand profile.")
    version = token("SHOPIFY_API_VERSION")
    require(re.fullmatch(r"[a-z0-9][a-z0-9-]*\.myshopify\.com", domain), "Use an exact myshopify.com shop domain.")
    require(re.fullmatch(r"20[0-9]{2}-(01|04|07|10)", version), "Set a stable Shopify Admin API version.")
    response = json.loads(fetch(f"https://{domain}/admin/api/{version}/graphql.json", {
        "X-Shopify-Access-Token": token("SHOPIFY_READ_TOKEN"), "Content-Type": "application/json",
    }, body=canonical({"query": query, "variables": variables}).encode()))
    require(not response.get("errors") and isinstance(response.get("data"), dict),
            "Shopify rejected the query or its access scope. Check the API version and read scopes.")
    return response["data"]


def product(product_id):
    require(re.fullmatch(r"[0-9]+", product_id), "Use the numeric Shopify product ID.")
    gid = f"gid://shopify/Product/{product_id}"
    cursor, variants = None, []
    for _ in range(60):
        info = gql(PRODUCT, {"id": gid, "after": cursor})["product"]
        require(info and info["id"] == gid, "Shopify product is inaccessible.")
        batch = info.pop("variants")
        variants.extend(batch["nodes"])
        if not batch["pageInfo"]["hasNextPage"]:
            return {**info, "variants": variants, "observed_at": stamp()}
        nxt = batch["pageInfo"]["endCursor"]
        require(nxt and nxt != cursor, "Shopify variant pagination did not advance.")
        cursor = nxt
    raise Stop("Product variant listing exceeded its page bound.")


def money(value):
    rules = policy()
    require(value["currencyCode"] == rules["currency"], "Shopify and brand policy currencies differ.")
    amount = Decimal(value["amount"]) * rules["minor_per_unit"]
    require(amount.is_finite() and amount >= 0 and amount == amount.to_integral_value(), "Invalid Shopify amount.")
    return int(amount)


def shopify_window(product_id, campaign, start, end, zone, *, variant_id=None):
    gid = f"gid://shopify/Product/{product_id}"
    variant = f"gid://shopify/ProductVariant/{variant_id}" if variant_id else None
    start_ts = datetime.combine(start, datetime.min.time(), tzinfo=zone)
    stop_ts = datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=zone)
    query = f"created_at:>='{start_ts.isoformat()}' created_at:<'{stop_ts.isoformat()}'"
    counts = dict(paid_product_orders=0, matched_orders=0, unmatched_orders=0,
                  other_campaign_orders=0, pending_journey=0, matched_refunded_orders=0,
                  matched_order_total_minor=0, matched_order_total_refunded_minor=0,
                  matched_first_time_buyers=0, matched_returning_buyers=0, matched_buyer_history_unknown=0)
    cash = {metric: {"received_less_refunds_and_tax_minor": 0, "covered_orders": 0,
                     "unallocated_orders": 0} for metric in ("paid_orders", "first_time_buyers")}
    cursor = None
    for _ in range(120):
        edge = gql(ORDERS, {"query": query, "after": cursor})["orders"]
        for order in edge["nodes"]:
            created = datetime.fromisoformat(order["createdAt"])
            require(start_ts <= created < stop_ts, "Shopify returned an order outside the requested window.")
            if order["cancelledAt"] or order["test"]:
                continue
            status = order["displayFinancialStatus"]
            if status not in {"PAID", "PARTIALLY_REFUNDED", "REFUNDED"}:
                continue
            lines = order["lineItems"]
            matching = [line for line in lines["nodes"] if (line["product"] or {}).get("id") == gid
                        and (not variant or (line.get("variant") or {}).get("id") == variant)]
            retained = any(line["currentQuantity"] > 0 for line in matching)
            require(retained or not lines["pageInfo"]["hasNextPage"],
                    "Incomplete Shopify order line list prevents accurate product matching.")
            if not matching:
                continue
            journey = order["customerJourneySummary"] or {}
            utm = ((journey.get("lastVisit") or {}).get("utmParameters") or {}) if journey.get("ready") else {}
            matched = utm.get("campaign") == campaign and utm.get("source") == "meta" and utm.get("medium") == "paid_social"
            if matched:
                counts["matched_order_total_minor"] += money(order["currentTotalPriceSet"]["shopMoney"])
                counts["matched_order_total_refunded_minor"] += money(order["totalRefundedSet"]["shopMoney"])
                counts["matched_refunded_orders"] += int(status in {"REFUNDED", "PARTIALLY_REFUNDED"})
                index = journey.get("customerOrderIndex")
                for metric in ("paid_orders", "first_time_buyers"):
                    aggregate = cash[metric]
                    if metric == "first_time_buyers" and index != 1:
                        if index is None:
                            aggregate["unallocated_orders"] += 1
                        continue
                    fields = ("totalReceivedSet", "totalRefundedSet", "currentTotalTaxSet")
                    if (lines["pageInfo"]["hasNextPage"] or len(matching) != len(lines["nodes"])
                            or any(not order.get(field, {}).get("shopMoney") for field in fields)):
                        aggregate["unallocated_orders"] += 1
                        continue
                    received, refunded, tax = (money(order[field]["shopMoney"]) for field in fields)
                    aggregate["covered_orders"] += 1
                    aggregate["received_less_refunds_and_tax_minor"] += received - refunded - tax
            if status == "REFUNDED" or not retained:
                continue
            counts["paid_product_orders"] += 1
            if matched:
                counts["matched_orders"] += 1
                index = journey.get("customerOrderIndex")
                if index == 1:
                    counts["matched_first_time_buyers"] += 1
                elif type(index) is int and index > 1:
                    counts["matched_returning_buyers"] += 1
                else:
                    counts["matched_buyer_history_unknown"] += 1
            elif utm.get("campaign"):
                counts["other_campaign_orders"] += 1
            else:
                counts["unmatched_orders"] += 1
                counts["pending_journey"] += int(not journey.get("ready"))
        if not edge["pageInfo"]["hasNextPage"]:
            return {"start": start.isoformat(), "end": end.isoformat(),
                    "time_zone": str(zone), "observed_at": stamp(), **counts,
                    "attribution": "Shopify last-visit exact Meta paid-social UTM; excludes unretained and fully refunded orders.",
                    "revenue_basis": "Whole matched order totals as of collection, not product revenue or cash receipts.",
                    "product_cash": cash}
        nxt = edge["pageInfo"]["endCursor"]
        require(nxt and nxt != cursor, "Shopify order pagination did not advance.")
        cursor = nxt
    raise Stop("Order listing exceeded its page bound. Shorten the analysis window or use an aggregate report.")


def drive_id(value):
    require(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{8,120}", value), "Invalid Drive ID.")
    return value


def drive_token():
    global _drive_session
    if not os.environ.get("DRIVE_OAUTH_REFRESH_TOKEN"):
        return token("DRIVE_READ_TOKEN")
    if _drive_session and time.monotonic() < _drive_session[1]:
        return _drive_session[0]
    body = urlencode({"grant_type": "refresh_token", "client_id": token("DRIVE_OAUTH_CLIENT_ID"),
                      "client_secret": token("DRIVE_OAUTH_CLIENT_SECRET"),
                      "refresh_token": token("DRIVE_OAUTH_REFRESH_TOKEN")}).encode()
    result = json.loads(fetch("https://oauth2.googleapis.com/token",
                              {"Content-Type": "application/x-www-form-urlencoded"}, body=body))
    require(result.get("access_token") and int(result.get("expires_in", 0)) > 60,
            "Drive did not return a usable offline access token.")
    _drive_session = result["access_token"], time.monotonic() + int(result["expires_in"]) - 60
    return _drive_session[0]


def drive_list(parent):
    parent = drive_id(parent)
    page, seen = None, set()
    for _ in range(100):
        query = {"q": f"'{parent}' in parents and trashed = false", "pageSize": 100,
                 "fields": "nextPageToken,incompleteSearch,files(id,name,mimeType,version,md5Checksum,size,parents)",
                 "supportsAllDrives": "true", "includeItemsFromAllDrives": "true"}
        if page:
            query["pageToken"] = page
        result = json.loads(fetch(f"{ROOT_DRIVE}/files?{urlencode(query)}",
                                  {"Authorization": f"Bearer {drive_token()}"}))
        require(not result.get("incompleteSearch"), "Drive returned an incomplete folder listing.")
        yield from result["files"]
        page = result.get("nextPageToken")
        if not page:
            return
        require(page not in seen, "Drive pagination repeated.")
        seen.add(page)
    raise Stop("Drive listing exceeded its page bound.")


def drive_inventory():
    config = policy()
    root = drive_id(config["creative_root"].rstrip("/").split("/")[-1])
    roots = list(drive_list(root))
    assets = {}
    for stage, folder_name in config["stages"].items():
        folders = [item for item in roots if item["name"] == folder_name and item["mimeType"] == "application/vnd.google-apps.folder"]
        require(len(folders) == 1, f"Expected one approved {folder_name} folder.")
        queue = [folders[0]["id"]]
        seen = set()
        while queue:
            folder = queue.pop()
            require(folder not in seen and len(seen) < 50, "Invalid or too large approved Drive hierarchy.")
            seen.add(folder)
            for item in drive_list(folder):
                require(folder in item["parents"], "Drive child does not belong to the queried folder.")
                mime = item["mimeType"]
                if mime == "application/vnd.google-apps.folder" and item["name"] != config["excluded_folder"]:
                    queue.append(item["id"])
                elif mime in {"image/png", "image/jpeg", "video/mp4"}:
                    require(item.get("version") and item.get("md5Checksum"), "A Drive asset is missing a verifiable revision.")
                    assets[item["id"]] = {"file_id": item["id"], "name": item["name"], "mime": mime,
                                          "revision": item["version"], "md5": item["md5Checksum"],
                                          "stage": stage, "bytes": int(item["size"])}
    return assets


def drive_media(asset):
    item = drive_id(asset["file_id"])
    raw = fetch(f"{ROOT_DRIVE}/files/{item}?alt=media&supportsAllDrives=true",
                {"Authorization": f"Bearer {drive_token()}"}, cap=MAX_MEDIA_BYTES)
    require(len(raw) == asset["bytes"] and hashlib.md5(raw, usedforsecurity=False).hexdigest() == asset["md5"],
            "Media bytes do not match the approved Drive revision.")
    return raw


def inspect_media(path):
    try:
        output = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_streams",
                                 "-show_format", "-of", "json", str(path)], capture_output=True,
                                timeout=25, check=True, encoding="utf-8")
        data = json.loads(output.stdout)
        video = data["streams"][0]
        rotate = next((entry.get("rotation") for entry in video.get("side_data_list", [])
                       if entry.get("rotation") is not None), 0)
        width, height = int(video["width"]), int(video["height"])
        if abs(int(rotate)) % 180 == 90:
            width, height = height, width
        return {"width": width, "height": height, "codec": video["codec_name"],
                "duration_seconds": data["format"].get("duration")}
    except (OSError, subprocess.SubprocessError, KeyError, ValueError, IndexError):
        raise Stop("Could not inspect the media with ffprobe.") from None


def storefront(url):
    try:
        value = destination(url)
        return {"url": value, "reachable": bool(fetch(value, {"User-Agent": "MetaAdsChecks/1.0"}, cap=2_000_000)),
                "observed_at": stamp()}
    except (Stop, ValueError):
        return {"url": url, "reachable": False, "observed_at": stamp()}


def windows(run, account):
    strategy = run["records"]["strategy-development"]["data"]
    criteria = strategy["criteria"]
    zone = account_zone(account["timezone_name"])
    last = datetime.now(zone).date() - timedelta(days=1 + criteria["lag_days"])
    number = criteria["window_days"]
    first = last - timedelta(days=number - 1)
    earlier = first - timedelta(days=number)
    return zone, {"current": (first, last), "previous": (earlier, first - timedelta(days=1))}


def meta_window(client, target, period, *, detailed=True):
    start, end = period
    campaign = client.scope(target["id"], "campaign", target["name"])
    ranges = {"since": start.isoformat(), "until": end.isoformat()}
    result = {}
    levels = ("campaign", "adset", "ad") if detailed else ("campaign",)
    for level in levels:
        rows = list(client.pages(f"{campaign['id']}/insights", META_FIELDS, level=level, time_range=ranges))
        valid = []
        for row in rows:
            key = row.get(f"{level}_id")
            require(row.get("campaign_id") == campaign["id"], "Meta Insights row is outside the campaign.")
            if level != "campaign":
                try:
                    target_item = client.scope(key, level, target["name"])
                except Stop:
                    continue
                require(target_item["campaign_id"] == campaign["id"], "Meta Insights row has the wrong campaign parent.")
            valid.append(row)
        result[level] = valid
    return {"start": ranges["since"], "end": ranges["until"], "rows": result, "observed_at": stamp(),
            "attribution": "Meta's returned attribution in the reporting account; retain action types separately."}
