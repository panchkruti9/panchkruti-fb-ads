"""Small, typed Meta recipes. Optional integrations do not gate ordinary Sales."""
from .meta import account_identity, campaign_key, destination, meta_id, require
from .plans import string


def capabilities(run):
    request = run["request"]
    formats = request.get("formats", ["static", "video", "story", "carousel"])
    result = {
        "website_purchase": {"state": "available", "recipe": "campaign-build"},
        "resume_delivery": {"state": "available", "recipe": "RESUME", "check": "Verify paused scope, Purchase source, destination and fresh funding."},
        "creative_formats": {"state": "available", "values": formats},
        "existing_audiences": {"state": "unverified", "check": "Read account audience inventory and delivery eligibility."},
        "website_audience_creation": {"state": "unverified", "recipe": "AUDIENCE", "check": "Verify dataset access and Meta audience terms."},
        "budget_redistribution": {"state": "available", "recipe": "ALLOCATE", "scope": "Enrolled campaigns for this client/account at their actual funding level; decreases first."},
        "automatic_placements": {"state": "available", "scope": "Explicit supported placement set remains the maximum allowed inventory."},
        "catalogue_sales": {"state": "unverified", "check": "Verify existing catalogue/product set, product mapping and permissions."},
        "formal_experiments": {"state": "unavailable", "alternative": "Record an exploratory comparison without claiming randomized results."},
        "customer_list_upload": {"state": "unavailable", "alternative": "Use eligible website-event or existing audiences."},
        "offline_strategy": {"state": "unavailable", "alternative": "Meta snapshots continue; connected-agent reasoning resumes on wake."},
    }
    from .state import now, parse_time
    from datetime import timedelta
    for key, observed in run.get("capability_observations", {}).items():
        if key in result:
            try:
                current = now() - parse_time(observed["observed_at"]) <= timedelta(hours=36)
            except (KeyError, TypeError, ValueError):
                current = False
            result[key].update(observed if current else {"state": "unverified", "check": "Refresh the dated account capability observation."})
    return result


def inspect_capabilities(store, run, client):
    """Optional read-only discovery through the existing Meta gateway, not client ID forms."""
    from .meta import Stop
    from .state import stamp
    data = {"account": client.details(), "audiences": [], "catalogues": [], "limitations": [], "observed_at": stamp()}
    observations = {}
    try:
        data["audiences"] = client.audience_inventory()
        observations["existing_audiences"] = {"state": "available", "observed_at": data["observed_at"],
            "check": "Inventory read succeeded; verify each selected audience's delivery eligibility before use."}
    except (Stop, KeyError, ValueError, OSError) as error:
        data["limitations"].append("Audience discovery: " + str(error))
    page = account_identity("page_id")
    if page:
        try:
            for index, catalogue in enumerate(client.pages(page + "/product_catalogs", "id,name")):
                if index >= 10:
                    data["limitations"].append("Catalogue discovery limited to ten Page catalogues.")
                    break
                record = {**catalogue, "matching_products": [], "product_sets": []}
                try:
                    for count, product in enumerate(client.pages(catalogue["id"] + "/products", "id,retailer_id,url,currency,availability")):
                        if count >= 200:
                            data["limitations"].append("Product discovery limited to 200 items per catalogue.")
                            break
                        if product.get("url") == run["request"].get("landing_page"):
                            record["matching_products"].append(product)
                    for count, product_set in enumerate(client.pages(catalogue["id"] + "/product_sets", "id,name,filter,product_count")):
                        if count >= 100:
                            data["limitations"].append("Product-set discovery limited to 100 sets per catalogue.")
                            break
                        record["product_sets"].append(product_set)
                except (Stop, KeyError, ValueError, OSError) as error:
                    record["limitation"] = str(error)
                data["catalogues"].append(record)
        except (Stop, KeyError, ValueError, OSError) as error:
            data["limitations"].append("Optional catalogue discovery: " + str(error))
    # Read access is evidence, not proof that a new write or creative type is permitted.
    run.setdefault("capability_observations", {}).update(observations)
    store.save(run, "capabilities_observed", {"observed_at": data["observed_at"], "verified_reads": list(observations),
                                               "limitations": data["limitations"]})
    return data


def audience_recipe(run, client):
    spec = run["records"]["optimization-decision"]["data"].get("audience")
    require(isinstance(spec, dict) and set(spec) == {"name", "event", "retention_days", "product_url"},
            "Website audience needs name, event, retention_days and exact product_url.")
    name = campaign_key(spec["name"])
    require(name.startswith(run["request"]["name"] + "-"), "Audience name is outside this product's managed namespace.")
    require(spec["event"] in {"PageView", "ViewContent", "AddToCart", "InitiateCheckout", "Purchase"}, "Unsupported audience event.")
    days = spec["retention_days"]
    require(type(days) is int and 1 <= days <= 180, "Website audience retention must be 1..180 days.")
    url = destination(spec["product_url"], (run["request"].get("brand") or {}).get("website"))
    require(url == run["request"].get("landing_page"), "Audience URL must match the assigned product.")
    pixel = meta_id(account_identity("pixel_id"))
    # Read permission and event source before proposing writes; no customer data is uploaded.
    source = client.request(pixel, {"fields": "id"})
    require(source.get("id") == pixel, "Cannot verify the assigned website event source.")
    rule = {"inclusions": {"operator": "or", "rules": [{
        "event_sources": [{"id": pixel, "type": "pixel"}], "retention_seconds": days * 86400,
        "filter": {"operator": "and", "filters": [
            {"field": "event", "operator": "eq", "value": spec["event"]},
            {"field": "url", "operator": "i_contains", "value": url.split("?", 1)[0]},
        ]}}]}}
    return {"name": name, "subtype": "WEBSITE", "retention_days": days, "rule": rule,
            "description": string(run["records"]["optimization-decision"]["data"]["rationale"])}


def carousel_cards(ad, selected, live):
    cards = ad.get("cards")
    require(isinstance(cards, list) and 2 <= len(cards) <= 10, "Carousel needs 2..10 ordered image cards.")
    for card in cards:
        require(isinstance(card, dict) and set(card) == {"asset_id", "headline", "description", "destination"}, "Invalid carousel card.")
        asset = selected.get(card["asset_id"])
        current = live.get(card["asset_id"])
        require(asset and current and current["mime"].startswith("image/") and asset["revision"] == current["revision"]
                and current["stage"] == ad["stage"], "Carousel card is missing, changed or in the wrong stage.")
        require(card["destination"] == ad["destination"], "All cards must use the assigned product destination.")
        string(card["headline"], "card headline")
        require(isinstance(card["description"], str), "Card description must be text.")
    return cards


def verify_catalogue(plan, client):
    if "catalogue" not in plan:
        return
    from .meta import policy
    spec = plan["catalogue"]
    product_set = client.request(spec["product_set_id"], {"fields": "id,product_catalog"})
    require(product_set.get("id") == spec["product_set_id"]
            and product_set.get("product_catalog", {}).get("id") == spec["catalogue_id"], "Catalogue product set changed.")
    sources = list(client.pages(spec["catalogue_id"] + "/external_event_sources", "id"))
    require(any(row.get("id") == account_identity("pixel_id") for row in sources), "Catalogue is not linked to the assigned Purchase source.")
    products = list(client.pages(spec["product_set_id"] + "/products", "id,retailer_id,url,currency,availability"))
    require(products and {p.get("retailer_id") for p in products} == set(spec["retailer_ids"]), "Product set includes missing or unassigned items.")
    destinations = {ad["destination"] for aset in plan["adsets"] for ad in aset["ads"]}
    require(all(p.get("url") in destinations and p.get("currency") == policy()["currency"]
                and p.get("availability") == "in stock" for p in products),
            "Catalogue product URL, currency or stock differs from the approved offer.")


def resume_recipe(run, client):
    from .execution import scope_target
    from .meta import wire_minor
    from .sources import storefront
    decision = run["records"]["optimization-decision"]["data"]
    kind, item = scope_target(run, client, decision["target_id"], ("campaign", "adset", "ad"))
    require(item["configured_status"] == "PAUSED", "Resume target is not paused.")
    tracking = run["request"].get("facts", {}).get("tracking", {})
    require(tracking.get("purchase_verified") is True and tracking.get("checkout_verified") is True
            and tracking.get("product_id") == run["request"]["product_id"]
            and (not run["request"].get("variant_id") or tracking.get("variant_id") == run["request"]["variant_id"]),
            "Verify the Purchase source and checkout before resuming delivery.")
    issue = run["request"].get("facts", {}).get("operational_issue", {})
    require(not (issue.get("verified") is True and issue.get("kind") in {"checkout", "tracking", "availability", "policy"}),
            "Resolve the recorded operational fault before resuming delivery.")
    campaign = client.scope(run["meta"]["id"], "campaign", run["meta"]["name"])
    adsets = list(client.pages(campaign["id"] + "/adsets", "id,campaign_id,configured_status,daily_budget,promoted_object"))
    selected = [a for a in adsets if a.get("configured_status") not in {"ARCHIVED", "DELETED"}
                and (kind == "campaign" or a["id"] == (item["id"] if kind == "adset" else item["adset_id"]))]
    pixel = account_identity("pixel_id")
    require(selected and all(a.get("campaign_id") == campaign["id"]
            and a.get("promoted_object", {}).get("pixel_id") == pixel
            and a.get("promoted_object", {}).get("custom_event_type") == "PURCHASE" for a in selected),
            "Paused delivery no longer uses the assigned Purchase source.")
    url = run["request"].get("landing_page") or run["records"]["product-research"]["data"]["product_facts"]["url"]
    require(storefront(url)["reachable"], "The assigned destination is unavailable.")
    selected_ids = {a["id"] for a in selected}
    for ad in client.pages(campaign["id"] + "/ads", "id,name,adset_id,campaign_id,configured_status,creative"):
        if ad.get("adset_id") not in selected_ids or ad.get("configured_status") in {"ARCHIVED", "DELETED"} or (kind == "ad" and ad["id"] != item["id"]):
            continue
        client.scope(ad["id"], "ad", run["meta"]["name"])
        creative = client.owned(ad["creative"]["id"], "object_story_spec,product_set_id")
        story = creative.get("object_story_spec", {})
        fmt = "catalogue" if creative.get("product_set_id") else "video" if story.get("video_data") else "carousel" if story.get("link_data", {}).get("child_attachments") else "static"
        client.creative(ad["creative"]["id"], url, fmt)
    if kind == "campaign":
        extra = wire_minor(item.get("daily_budget")) or sum(wire_minor(a.get("daily_budget")) for a in selected if a["configured_status"] == "ACTIVE")
    else:
        require(campaign["configured_status"] == "ACTIVE", "Resume the campaign before resuming its children.")
        if kind == "ad":
            require(selected[0]["configured_status"] == "ACTIVE", "Resume the parent ad set before its ad.")
        extra = wire_minor(item.get("daily_budget")) if kind == "adset" and not wire_minor(campaign.get("daily_budget")) else 0
    return {"id": item["id"], "name": item["name"], "kind": kind, "before": "PAUSED", "after": "ACTIVE",
            "extra_daily_minor": extra, "rationale": decision["rationale"]}
