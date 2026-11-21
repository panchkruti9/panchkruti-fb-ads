"""Validate skill outputs before compiling them into Meta operations."""
import re
from datetime import date
from urllib.parse import parse_qs, urlsplit

from .meta import campaign_key, child_name, destination, meta_id, minor, policy, require
from .state import REGISTRY, parse_time

PLACEMENTS = {
    "facebook_feed": ("facebook_positions", "feed", "MOBILE_FEED_STANDARD"),
    "instagram_feed": ("instagram_positions", "stream", "INSTAGRAM_STANDARD"),
    "facebook_story": ("facebook_positions", "story", "FACEBOOK_STORY_MOBILE"),
    "instagram_story": ("instagram_positions", "story", "INSTAGRAM_STORY"),
    "facebook_reels": ("facebook_positions", "facebook_reels", "FACEBOOK_REELS_MOBILE"),
    "instagram_reels": ("instagram_positions", "reels", "INSTAGRAM_REELS"),
}
VISUAL_CHECKS = ("claims", "packaging", "rights", "destination", "placement", "copy", "brand")
APPROVED_CTAS = {"SHOP_NOW", "LEARN_MORE", "ORDER_NOW"}
DEFERABLE = {"customer-research", "competitor-research", "ad-library-research",
             "creative-analysis", "audience-analysis", "performance-analysis", "business-performance",
             "campaign-analysis"}
OPS = {"HOLD", "FIX", "TEST", "REFRESH", "PAUSE", "RESUME", "RECREATE", "SCALE", "ALLOCATE", "AUDIENCE"}
DATA_TYPES = {"object": (dict,), "array": (list,), "string": (str,), "integer": (int,),
              "boolean": (bool,), "record": (dict, list, str), "object?": (dict, type(None))}


def obj(value, fields=None, *, label="object"):
    require(isinstance(value, dict), f"Expected {label}.")
    if fields is not None:
        require(set(value) == set(fields), f"{label} must have exactly: {', '.join(fields)}.")
    return value


def string(value, label="text"):
    require(isinstance(value, str) and value.strip(), f"Missing {label}.")
    return value


def seq(value, label="list", *, nonempty=False):
    require(isinstance(value, list) and (not nonempty or bool(value)), f"Invalid {label}.")
    return value


def result(step, output):
    obj(output, ("status", "summary", "evidence", "data", "blockers"))
    status = output["status"]
    require(status in {"pass", "limited", "block", "rework"}, "Unknown step result status.")
    string(output["summary"], "summary")
    evidence = seq(output["evidence"], "evidence", nonempty=status in {"pass", "limited"})
    for ref in evidence:
        obj(ref, ("source", "ref", "observed_at"))
        string(ref["source"], "source name")
        string(ref["ref"], "evidence reference")
        parse_time(ref["observed_at"])
    blockers = seq(output["blockers"], "blockers", nonempty=status != "pass")
    require(status != "pass" or not blockers, "A passing skill result cannot contain blockers.")
    for item in blockers:
        string(item, "blocker")
    data = obj(output["data"])
    if status in {"block", "rework"}:
        return output
    require(status != "limited" or step in DEFERABLE, f"{step} needs verified inputs.")
    require(set(REGISTRY[step]["fields"]) <= set(data), f"Missing required result fields for {step}.")
    for field, type_name in REGISTRY[step].get("types", {}).items():
        require(type(data[field]) in DATA_TYPES[type_name], f"{step}.{field} must be {type_name}.")
    if step == "strategy-development":
        date.fromisoformat(string(data["next_review_on"], "strategy review date"))
        criteria = obj(data.get("criteria"))
        base = {"window_days", "lag_days", "minimum_matched_orders", "maximum_cpa_minor", "recheck_hours"}
        require(base <= criteria.keys() <= base | {"learning_spend_minor", "scale_windows", "repeatability_reference"}, "Invalid review criteria.")
        if "learning_spend_minor" in criteria:
            minor(criteria["learning_spend_minor"], positive=True)
        require(type(criteria.get("scale_windows", 2)) is int and criteria.get("scale_windows", 2) in {1, 2}, "Select one or two scaling windows.")
        if criteria.get("scale_windows") == 1:
            string(criteria.get("repeatability_reference"), "dated repeatability evidence for a single-window scaling assessment")
        for field in ("window_days", "minimum_matched_orders", "recheck_hours"):
            minor(criteria[field], positive=True)
        minor(criteria["lag_days"])
        if criteria["maximum_cpa_minor"] is not None:
            minor(criteria["maximum_cpa_minor"], positive=True)
        require(criteria["window_days"] <= 30 and criteria["lag_days"] <= 30, "Unsupported review window.")
    if step == "optimization-decision":
        require(data["decision"] in OPS, "Invalid optimization decision.")
        meta_id(data["target_id"])
        string(data["rationale"], "decision rationale")
        date.fromisoformat(string(data["next_review_on"], "review date"))
    if step == "scaling-eligibility":
        checks = obj(data["verified_checks"], ("business", "tracking", "stability", "inventory", "fulfilment"))
        require(all(type(x) is bool for x in checks.values()), "Eligibility checks must be booleans.")
        require(type(data["eligible"]) is bool and data["eligible"] == all(checks.values()), "Eligibility disagrees with evidence.")
    if step == "budget-validation":
        meta_id(data["account_id"])
        minor(data["projected_daily_minor"])
        minor(data["projected_monthly_minor"])
        require(type(data["passed"]) is bool, "Budget check requires pass/fail.")
    if step == "scaling-proposal":
        meta_id(data["target_id"])
        date.fromisoformat(string(data["next_review_on"], "post-change review date"))
        require(minor(data["to_daily_minor"], positive=True) > minor(data["from_daily_minor"], positive=True),
                "Scaling must increase the approved budget.")
    return output


def audience_scope(value):
    value = obj(value, ("mode", "include", "exclude"), label="target audience")
    mode = value["mode"]
    require(mode in ("broad", "retargeting", "lookalike"), "Unknown target audience mode.")
    include, exclude = (seq(value[key], key) for key in ("include", "exclude"))
    for key in include + exclude:
        meta_id(key)
    require(len(include + exclude) == len(set(include + exclude)), "Audience inclusions and exclusions must be distinct.")
    require(bool(include) == (mode != "broad"), "Select an exact Meta audience for this mode.")
    return value


def verify_audiences(client, adsets):
    scopes = [audience_scope(aset["audience"]) for aset in adsets if "audience" in aset]
    if not any(scope["include"] or scope["exclude"] for scope in scopes):
        return
    available = {item["id"]: item for item in client.audience_inventory()}
    for scope in scopes:
        for key in scope["include"] + scope["exclude"]:
            audience = available.get(key)
            operation = (audience or {}).get("operation_status", {}).get("code")
            delivery = (audience or {}).get("delivery_status", {}).get("code")
            require(audience and audience.get("account_id") == client.account
                    and operation in {100, 200, 400, 411, 441, 450}
                    and (delivery == 200 or (delivery is None and operation == 200))
                    and not audience.get("fields_violating_integrity_policy"),
                    "A selected Meta audience is unavailable, restricted, or outside the approved account.")
            if key in scope["include"]:
                is_lookalike = audience.get("subtype") == "LOOKALIKE"
                require(is_lookalike == (scope["mode"] == "lookalike"), "Meta audience subtype differs from the plan.")


def ad_plan(run, approved_assets):
    steps = run["records"]
    validated = steps["creative-validation"]["data"]
    strategy = steps["campaign-strategy"]["data"]
    root = campaign_key(strategy["campaign_key"])
    request = run["request"]
    account = request["account_id"]
    rules = policy(request.get("brand"))
    require(strategy["account_id"] == account, "Campaign plan references a different Meta account.")
    plan = obj(validated.get("plan"))
    required_plan = {"objective", "budget_level", "daily_minor", "adsets"}
    require(required_plan <= plan.keys() <= required_plan | {"catalogue"}, "Invalid campaign plan fields.")
    if "catalogue" in plan:
        catalogue = obj(plan["catalogue"], ("product_set_id", "catalogue_id", "retailer_ids"))
        meta_id(catalogue["product_set_id"])
        meta_id(catalogue["catalogue_id"])
        seq(catalogue["retailer_ids"], "catalogue product mappings", nonempty=True)
        require(all(isinstance(key, str) and key.strip() for key in catalogue["retailer_ids"])
                and len(set(catalogue["retailer_ids"])) == len(catalogue["retailer_ids"]), "Catalogue retailer mappings must be distinct nonempty strings.")
        proof = request.get("facts", {}).get("catalogue", {})
        require(proof.get("product_id") == request["product_id"] and proof.get("variant_id") == request.get("variant_id")
                and proof.get("source") and all(proof.get(k) == v for k, v in catalogue.items()),
                "Catalogue needs verified product/variant-to-retailer mapping from connected evidence.")
    require(plan["objective"] == strategy["objective"] == "OUTCOME_SALES", "This executor supports website Sales.")
    require(plan["budget_level"] in {"campaign", "adset"}, "Select the actual funding level.")
    total = minor(plan["daily_minor"], positive=True)
    budget = obj(strategy["budget"])
    require(total == budget.get("daily_minor") and plan["budget_level"] == budget.get("level"),
            "Build funding differs from Campaign Strategy.")
    require(total <= rules["maximum_daily_minor"], "Build exceeds maximum account-wide daily allocation.")
    replacement = run.get("create_mode") in {"refresh", "test"}
    if request.get("brand") and not replacement:
        if (test_budget := request.get("test_budget_minor")) is not None:
            window = steps["strategy-development"]["data"]["criteria"]["window_days"]
            require(total * window <= test_budget, "Planned allocation exceeds the test budget over the review window.")
        if request.get("daily_budget_minor") is not None:
            require(total == request["daily_budget_minor"], "Build daily budget differs from the request.")
    if replacement:
        require(root == run["meta"].get("name"), "Creative additions must stay in the managed campaign.")
    else:
        require(root == run.get("planned_name", run["request"]["name"]), "Campaign key differs from the request.")
    assets = {item["file_id"]: item for item in seq(steps["asset-selection"]["data"]["assets"], "selected media")}
    variants = {item["name"]: item for item in seq(steps["ad-copywriting"]["data"]["variants"],
                                                  "copy variants", nonempty=True)}
    qa = {}
    for item in seq(validated["ads"], "validated ads", nonempty=True):
        checks = obj(item["checks"], VISUAL_CHECKS)
        require(all(type(value) is bool for value in checks.values()), "Per-ad checks must be booleans.")
        if not all(checks.values()):
            continue
        key = child_name(item["name"], root, ad=True)
        require(key not in qa, "Duplicate ad in QA.")
        require(seq(item["evidence"], "ad QA evidence", nonempty=True), "Ad QA needs evidence.")
        qa[key] = item
    seen, valid_sets, adset_total = set(), set(), 0
    for aset in seq(plan["adsets"], "ad sets", nonempty=True):
        required = {"name", "daily_minor", "country_codes", "placements", "existing_adset_id", "ads"}
        require(required <= obj(aset).keys() <= required | {"audience"}, "Invalid ad set plan fields.")
        approved = steps.get("audience-planning", {}).get("data", {}).get("targeting_requirements", {})
        approved = approved.get("adset_audiences", {}) if isinstance(approved, dict) else {}
        if "audience" in aset or aset["name"] in approved:
            scope = audience_scope(aset.get("audience"))
            require(approved.get(aset["name"]) == scope,
                    "Ad set audience differs from Audience Planning.")
        child_name(aset["name"], root)
        require(aset["name"] not in valid_sets, "Duplicate ad set.")
        valid_sets.add(aset["name"])
        if replacement:
            if aset["existing_adset_id"] is not None:
                meta_id(aset["existing_adset_id"])
            else:
                require(plan["budget_level"] == "campaign", "New funded ad sets need a separate verified budget transfer first.")
            require(aset["daily_minor"] == 0, "An ad addition cannot change ad set funding.")
        else:
            require(aset["existing_adset_id"] is None, "New build must create its ad sets.")
            adset_total += minor(aset["daily_minor"], positive=plan["budget_level"] == "adset")
        countries = seq(aset["country_codes"], "countries", nonempty=True)
        require(all(re.fullmatch(r"[A-Z]{2}", code) for code in countries), "Invalid country code.")
        require(set(countries) <= set(request["countries"]), "Ad set uses an unapproved market.")
        placements = seq(aset["placements"], "placements", nonempty=True)
        require(len(set(placements)) == len(placements) and set(placements) <= set(PLACEMENTS),
                "Supported placements are Facebook and Instagram Feed, Stories and Reels.")
        require(set(placements) <= set(request.get("placements", PLACEMENTS)),
                "Ad set uses a placement excluded by the brand or request.")
        for ad in seq(aset["ads"], "ads", nonempty=True):
            fields = {"name", "format", "stage", "asset_id", "poster_asset_id", "primary_text",
                      "headline", "description", "cta", "destination", "url_tags"}
            require(fields <= obj(ad).keys() <= fields | {"cards"}, "Invalid ad fields.")
            name = child_name(ad["name"], root, ad=True)
            require(name in qa and name not in seen, "Each ad must match one unique passing QA record.")
            seen.add(name)
            require(qa[name]["approved_ad"] == ad, "Ad differs from the exact creative approved by QA.")
            require(name in variants and all(ad[key] == variants[name].get(key)
                    for key in ("primary_text", "headline", "description", "cta")),
                    "Ad copy differs from the saved copywriting variant.")
            require(ad["format"] in request.get("formats", rules["formats"]) and ad["stage"] in rules["stages"],
                    "Unapproved creative type.")
            require((ad["format"] == "catalogue") == ("catalogue" in plan), "Catalogue recipe cannot mix ordinary ads in its product-set build.")
            require(name.startswith(root + "-" + ad["stage"] + "-")
                    and re.search("-" + ad["format"] + r"-v[0-9]+$", name), "Name, stage and format must agree.")
            asset = assets.get(ad["asset_id"])
            require(asset is not None and asset["stage"] == ad["stage"], "Asset not approved for this stage.")
            live = approved_assets.get(ad["asset_id"])
            require(live is not None and live["revision"] == asset["revision"] and live["stage"] == ad["stage"],
                    "Approved Drive asset was removed or changed.")
            mime = live["mime"]
            if ad["format"] == "carousel":
                from .recipes import carousel_cards
                carousel_cards(ad, assets, approved_assets)
                require(ad["asset_id"] == ad["cards"][0]["asset_id"], "Carousel primary asset must be its first card.")
                require(all(p.endswith("_feed") for p in placements), "This carousel recipe supports Feed placements.")
            require(mime in {"image/png", "image/jpeg", "video/mp4"}, "Unsupported source media.")
            if ad["format"] == "static":
                require(mime.startswith("image/"), "Static format requires image media.")
            if ad["format"] == "video":
                require(mime == "video/mp4", "Video format requires MP4 media.")
            if ad["format"] == "story":
                require(all(p.endswith("_story") for p in placements), "Story must be in Story placements.")
            if any(p.endswith("_reels") for p in placements):
                require(mime == "video/mp4", "This Reels recipe requires approved video.")
            if mime == "video/mp4":
                poster = approved_assets.get(ad["poster_asset_id"])
                selected = assets.get(ad["poster_asset_id"])
                require(poster and selected and poster["stage"] == ad["stage"] and poster["mime"].startswith("image/")
                        and poster["revision"] == selected["revision"], "Video needs a matching approved thumbnail.")
            else:
                require(ad["poster_asset_id"] is None, "Image ads do not have a video thumbnail.")
            string(ad["primary_text"], "primary text")
            string(ad["headline"], "headline")
            require(isinstance(ad["description"], str) and ad["cta"] in APPROVED_CTAS, "Invalid copy or CTA.")
            website = (request.get("brand") or {}).get("website")
            destination(ad["destination"], website)
            product_facts = steps["product-research"]["data"]["product_facts"]
            expected_url = destination(string(product_facts["url"], "verified product URL"), website)
            if website:
                require(ad["destination"] == expected_url == request["landing_page"],
                        "Ad must use the exact approved product or variant landing page.")
            actual, expected = urlsplit(ad["destination"]), urlsplit(expected_url)
            require((actual.netloc, actual.path) == (expected.netloc, expected.path) and not actual.fragment,
                    "Ad goes to a different product or contains a URL fragment.")
            tags = parse_qs(ad["url_tags"], strict_parsing=True)
            require(all(len(values) == 1 for values in tags.values()) and tags.get("utm_campaign") == [root]
                    and tags.get("utm_content") == [name] and tags.get("utm_source") == ["meta"]
                    and tags.get("utm_medium") == ["paid_social"], "Use stable Meta campaign/ad UTM values.")
    require(seen == set(qa), "Passing QA ads do not match the exact build.")
    if not replacement:
        expected = total if plan["budget_level"] == "adset" else 0
        require(adset_total == expected, "Ad set allocations disagree with selected funding level.")
    return {"name": root, **plan, "assets": {key: approved_assets[key] for key in assets
                                          if key in approved_assets}}


def targeting(aset):
    values = {"geo_locations": {"countries": aset["country_codes"]}, "publisher_platforms": []}
    for name in aset["placements"]:
        key, value, _ = PLACEMENTS[name]
        platform = key.split("_", 1)[0]
        if platform not in values["publisher_platforms"]:
            values["publisher_platforms"].append(platform)
        values.setdefault(key, []).append(value)
    if "audience" in aset:
        scope = audience_scope(aset["audience"])
        if scope["include"]:
            values["custom_audiences"] = [{"id": key} for key in scope["include"]]
            values["targeting_automation"] = {"advantage_audience": 0}
        if scope["exclude"]:
            values["excluded_custom_audiences"] = [{"id": key} for key in scope["exclude"]]
    return values
