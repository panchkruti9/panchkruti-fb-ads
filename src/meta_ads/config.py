"""Validate user-supplied brand profiles and website Sales requests."""

import re
from urllib.parse import parse_qs, urlsplit

from .meta import campaign_key, destination, meta_id, minor, require
from .plans import PLACEMENTS, string

FORMATS = {"static", "video", "story", "carousel", "catalogue"}
STAGES = {"discovery", "consideration", "purchase"}
APPROVAL_ACTIONS = {"build", "activate", "budget", "pause"}
METRICS = {"paid_orders", "first_time_buyers"}


def choices(value, allowed, label, *, allow_empty=False):
    require(isinstance(value, list) and (allow_empty or value)
            and all(isinstance(item, str) and item in allowed for item in value)
            and len(value) == len(set(value)), f"Choose supported {label}.")
    return value


def profile(data):
    required = {"brand_id", "brand_name", "website", "shopify_shop", "account_id", "policy"}
    internal = {"page_id", "pixel_id", "instagram_id", "identity_reference"}
    require(isinstance(data, dict) and required <= data.keys() <= required | internal,
            "Load the brand's storefront, connected account and saved policy.")
    require(isinstance(data["brand_id"], str) and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", data["brand_id"]),
            "Use a stable lowercase brand_id.")
    string(data["brand_name"], "brand name")
    website = urlsplit(string(data["website"], "brand website"))
    require(website.scheme == "https" and website.netloc == website.hostname
            and re.fullmatch(r"(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,63}", website.netloc)
            and website.path in {"", "/"} and not website.query and not website.fragment,
            "Use the brand's HTTPS storefront origin.")
    require(isinstance(data["shopify_shop"], str)
            and re.fullmatch(r"[a-z0-9][a-z0-9-]*\.myshopify\.com", data["shopify_shop"]),
            "Use the connected Shopify Admin shop domain.")
    meta_id(data["account_id"])
    for key in ("page_id", "pixel_id", "instagram_id"):
        if data.get(key) is not None:
            meta_id(data[key])
    if "identity_reference" in data:
        ref = data["identity_reference"]
        require(isinstance(ref, dict) and set(ref) == {"campaign_name", "ad_id", "adset_id"},
                "The connected account's saved identity reference is incomplete.")
        campaign_key(ref["campaign_name"])
        meta_id(ref["ad_id"])
        meta_id(ref["adset_id"])
    rules = data["policy"]
    fields = {"currency", "minor_per_unit", "minimum_daily_minor", "maximum_daily_minor", "maximum_monthly_minor",
              "approval_hours", "creative_root", "stages", "excluded_folder", "formats", "placements",
              "claim_rules", "operators", "owners", "owner_approval_actions"}
    require(isinstance(rules, dict) and fields <= rules.keys() <= fields | {"blocked_pause_after_hours", "management_authority"},
            "Complete the required brand policy fields.")
    if rules.get("blocked_pause_after_hours") is not None:
        minor(rules["blocked_pause_after_hours"], positive=True)
    require(isinstance(rules["currency"], str) and re.fullmatch(r"[A-Z]{3}", rules["currency"]),
            "Use the Meta and Shopify account currency code.")
    require(type(rules["minor_per_unit"]) is int and rules["minor_per_unit"] in {1, 100, 1000},
            "Set the number of minor units per currency unit.")
    minimum = minor(rules["minimum_daily_minor"])
    maximum = minor(rules["maximum_daily_minor"], positive=True)
    require(minimum <= maximum <= minor(rules["maximum_monthly_minor"], positive=True),
            "Daily and monthly policy limits are inconsistent.")
    minor(rules["approval_hours"], positive=True)
    root = urlsplit(string(rules["creative_root"], "creative folder URL"))
    require(root.scheme == "https" and root.netloc == "drive.google.com"
            and re.fullmatch(r"/drive/folders/[A-Za-z0-9_-]{8,120}/?", root.path),
            "Use the direct Google Drive creative folder URL.")
    folders = rules["stages"]
    require(isinstance(folders, dict) and folders.keys() == STAGES, "Name all three approved creative folders.")
    folder_names = [string(x, "creative folder name") for x in (*folders.values(), rules["excluded_folder"])]
    require(len(set(folder_names)) == len(folder_names), "Stage and excluded folders must be distinct.")
    choices(rules["formats"], FORMATS, "formats")
    choices(rules["placements"], PLACEMENTS, "placements")
    for key in ("claim_rules", "operators", "owners"):
        require(isinstance(rules[key], list)
                and all(isinstance(x, str) and x.strip() for x in rules[key]), f"Provide policy {key}.")
    actions = choices(rules["owner_approval_actions"], APPROVAL_ACTIONS, "owner approval actions")
    require({"activate", "budget"} <= set(actions), "Legacy owner actions must preserve activation and budget protection.")
    if rules.get("management_authority"):
        from .authority import validate
        validate(rules["management_authority"], rules)
    return data


def configured_request(data, brand):
    profile(brand)
    required = {"product_id", "product_name", "landing_page", "countries", "objective", "brief"}
    optional = {"name", "variant_id", "offer", "formats", "placements", "daily_budget_minor", "success_metric",
                "target_cost_minor", "facts", "review_policy", "test_budget_minor"}
    require(isinstance(data, dict) and required <= data.keys() <= required | optional,
            "Complete the product request template and use the brand profile for account and policy fields.")
    name = string(data["product_name"], "product name")
    meta_id(data["product_id"])
    url = destination(data["landing_page"], brand["website"])
    variant = data.get("variant_id")
    query_variant = parse_qs(urlsplit(url).query).get("variant")
    if variant is not None:
        meta_id(variant)
    require(query_variant == ([variant] if variant else None), "Landing page and Shopify variant ID must agree.")
    require(data["objective"] == "website_sales", "The automated build currently supports website_sales.")
    require(data.get("success_metric", "paid_orders") in METRICS, "Choose paid_orders or first_time_buyers.")
    rules = brand["policy"]
    spend = data.get("test_budget_minor")
    if spend is not None:
        require(minor(spend, positive=True) <= rules["maximum_monthly_minor"],
                "Test budget exceeds the brand's monthly limit.")
    if data.get("daily_budget_minor") is not None:
        daily = minor(data["daily_budget_minor"], positive=True)
        require(daily <= rules["maximum_daily_minor"] and (spend is None or daily <= spend),
                "Daily budget exceeds test or policy limit.")
    if "offer" in data:
        require(isinstance(data["offer"], dict), "Offer must be an object with checked terms.")
    formats = choices(data.get("formats", rules["formats"]), set(rules["formats"]), "request formats")
    placements = choices(data.get("placements", rules["placements"]), set(rules["placements"]), "request placements")
    review = data.get("review_policy", {})
    require(isinstance(review, dict), "Review policy must be an object.")
    review = dict(review)
    if data.get("target_cost_minor") is not None:
        ceiling = minor(data["target_cost_minor"], positive=True)
        require(review.get("maximum_cpa_minor", ceiling) == ceiling, "The two cost targets disagree.")
        review["maximum_cpa_minor"] = ceiling
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:52].rstrip("-") or "product"
    campaign = campaign_key(data.get("name", f"agi-{slug}-{data['product_id']}"[:100].rstrip("-")))
    return {**data, "name": campaign, "account_id": brand["account_id"], "brand": brand, "formats": formats,
            "placements": placements, "success_metric": data.get("success_metric", "paid_orders"),
            "review_policy": review}
