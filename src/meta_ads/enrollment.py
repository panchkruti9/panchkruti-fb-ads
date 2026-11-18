"""Register a verified paused Meta draft and route it through launch review."""
from urllib.parse import parse_qs, urlsplit

from .meta import budget_projection, destination, fingerprint, minor, require, wire_minor
from .plans import PLACEMENTS, VISUAL_CHECKS


STEP = "existing-campaign-review"


def match(run, snapshot):
    if not snapshot:
        return None
    found = [item for item in snapshot["account_report"]["managed_objects"]
             if item["name"] == run.get("planned_name", run["request"]["name"])]
    require(len(found) <= 1, "More than one Meta campaign matches this assignment. Resolve the duplicate scope.")
    return found[0] if found else None


def draft(snapshot, target):
    row = snapshot["campaigns"].get(target["id"], {})
    detail = row.get("draft", {})
    require(row.get("name") == target["name"] and row.get("configuration")
            and "unavailable" not in row["configuration"] and detail.get("adsets") and detail.get("ads"),
            "Refresh the Meta snapshot to get the paused campaign, placements and ad destinations.")
    return detail


def advert_destinations(ad):
    creative = ad["creative_readback"]
    story = creative["object_story_spec"]
    media = story.get("link_data") or story.get("video_data")
    require(media and not media.get("child_attachments") and not creative.get("asset_feed_spec")
            and not creative.get("product_set_id"), "The existing ad requires a creative format review.")
    links = [url for url in (media.get("link"), (media.get("call_to_action") or {}).get("value", {}).get("link")) if url]
    require(links and len(set(links)) == 1, "Existing ad links differ or cannot be verified.")
    return links[0], "video" if story.get("video_data") else "static"


def assert_destination(run, url, variants):
    request = run["request"]
    website = request["brand"]["website"]
    expected = urlsplit(destination(request["landing_page"], website))
    actual = urlsplit(destination(url, website))
    require((actual.netloc, actual.path) == (expected.netloc, expected.path),
            "The existing campaign uses a different product page.")
    url_variant = parse_qs(actual.query, keep_blank_values=True).get("variant")
    assigned = request.get("variant_id")
    if assigned:
        require(url_variant == [assigned] or (url_variant is None and variants == [assigned]),
                "The existing ad does not identify the assigned Shopify variant.")


def inspect(run, snapshot, target, variants):
    detail = draft(snapshot, target)
    require(target["configured_status"] == target["effective_status"] == "PAUSED",
            "The matching campaign is already delivering or its paused state is unverified.")
    campaign_id = target["id"]
    adset_ids = {row["id"] for row in detail["adsets"]}
    for item in detail["adsets"] + detail["ads"]:
        require(item["campaign_id"] == campaign_id and item["configured_status"] == "PAUSED"
                and item["effective_status"] in {"PAUSED", "CAMPAIGN_PAUSED", "ADSET_PAUSED"},
                "The matching draft contains unverified or differently configured objects.")
    require(all(ad["adset_id"] in adset_ids for ad in detail["ads"]), "The matching draft has an unexpected ad parent.")
    require(target["objective"] == "OUTCOME_SALES", "The existing campaign uses a different objective.")
    for ad in detail["ads"]:
        url, _ = advert_destinations(ad)
        assert_destination(run, url, variants)
    return detail


def register(store, run, snapshot, target, variants):
    details = inspect(run, snapshot, target, variants)
    with store.lease("executor"):
        require(store.get(run["id"])["revision"] == run["revision"], "Reload the current run before registering a draft.")
        require(not run["meta"] and not run.get("proposal") and not run["write_journal"],
                "Resolve the existing run's proposal and journal before registering a draft.")
        require(all(other["id"] == run["id"] or other["request"]["account_id"] != run["request"]["account_id"]
                    or other["meta"].get("id") != target["id"] for other in store.list()),
                "This campaign is already registered on another run.")
        run["meta"] = {"id": target["id"], "name": target["name"]}
        run["enrolled_campaign"] = {"job_id": snapshot["job_id"], "observed_at": snapshot["observed_at"],
                                    "variant_ids": variants, "adsets": len(details["adsets"]), "ads": len(details["ads"])}
        run.update(step=STEP, status="ready", blockers=[])
        run.pop("connected_context", None)
        store.save(run, "paused_campaign_registered", {"campaign": run["meta"], **run["enrolled_campaign"]})
    return run


def prepare_adopted_batch(run, snapshot, target, result):
    checks = result.get("checks", {})
    require(set(checks) == set(VISUAL_CHECKS) and all(checks[name] is True for name in VISUAL_CHECKS),
            "Review the existing ads, claims, destination and placements before activation checks.")
    request = run["request"]
    rules = request["brand"]["policy"]
    adset_list = inspect(run, snapshot, target, run["enrolled_campaign"]["variant_ids"])
    campaign_id = target["id"]
    fields = ("name", "objective", "daily_budget", "lifetime_budget")
    nodes = [{"id": campaign_id, "kind": "campaign",
              "settings": {key: target[key] for key in fields if key in target}}]
    placements_by_adset = {}
    account_daily = wire_minor(target.get("daily_budget"))
    require(not wire_minor(target.get("lifetime_budget")), "Existing lifetime spending needs a separate review.")
    funding_mode = account_daily > 0
    identity = {}
    for aset in adset_list["adsets"]:
        targeting = aset["targeting"]
        require(sorted(targeting.get("geo_locations", {}).get("countries", [])) == sorted(request["countries"]),
                "Existing geographic targeting differs from the assigned markets.")
        require(aset["optimization_goal"] == "OFFSITE_CONVERSIONS"
                and aset["promoted_object"].get("custom_event_type") == "PURCHASE"
                and aset["promoted_object"].get("pixel_id"), "Existing ad set does not use a verified Purchase source.")
        pixel = aset["promoted_object"]["pixel_id"]
        saved_pixel = request["brand"].get("pixel_id") or identity.get("pixel_id")
        require(not saved_pixel or saved_pixel == pixel, "Existing ad sets use a different Purchase source.")
        identity["pixel_id"] = pixel
        channels = targeting.get("publisher_platforms", [])
        require(channels and set(channels) <= {"facebook", "instagram"},
                "Existing placement channels need review.")
        placements = set()
        for channel in channels:
            field = channel + "_positions"
            slots = targeting.get(field, [])
            mapped = {key for key, (network, slot, _) in PLACEMENTS.items() if field == network and slot in slots}
            require(slots and len(mapped) == len(set(slots)), "Existing placements are outside the supported recipe.")
            placements.update(mapped)
        require(placements <= set(request["placements"]), "Existing placements exceed the assigned policy.")
        placements_by_adset[aset["id"]] = sorted(placements)
        daily = wire_minor(aset.get("daily_budget"))
        require(not wire_minor(aset.get("lifetime_budget")) and (daily == 0 if funding_mode else daily > 0),
                "Existing budget allocation is outside the supported recipe.")
        account_daily += daily
        fields = ("name", "campaign_id", "daily_budget", "lifetime_budget", "targeting",
                  "promoted_object", "optimization_goal")
        nodes.append({"id": aset["id"], "kind": "adset", "settings": {key: aset[key] for key in fields if key in aset}})
    funded = {**snapshot["funding"], "daily_minor": snapshot["funding"]["daily_minor"] + minor(account_daily, positive=True)}
    require(budget_projection(funded, rules)["passed"], "The paused draft exceeds the saved account budget policy.")
    identifiers = []
    for ad in adset_list["ads"]:
        link, fmt = advert_destinations(ad)
        placements = placements_by_adset[ad["adset_id"]]
        require(fmt in request["formats"] and (fmt == "video" or not any(p.endswith("_reels") for p in placements)),
                "Existing creative format and placements require revision.")
        nodes.append({"id": ad["id"], "kind": "ad", "settings": {"name": ad["name"],
                      "campaign_id": campaign_id, "adset_id": ad["adset_id"], "creative": ad["creative"]},
                      "destination": link, "format": fmt, "creative_version": fingerprint(ad["creative_readback"])})
        identifiers.append({"id": ad["id"], "placements": placements})
    return {"campaign_id": campaign_id, "name": target["name"], "addition": False, "daily_minor": account_daily,
            "objects": nodes, "ad_ids": identifiers, "adsets": [], "identity": identity}
