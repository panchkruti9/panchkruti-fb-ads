"""Collect evidence through the agent's read connections, outside the Meta worker."""
import hashlib
from datetime import timedelta, timezone
import re
from urllib.parse import urlsplit

from . import enrollment, meta_catchup
from .execution import GATES
from .meta import Stop, account_zone, budget_projection, configured, destination, policy, require
from .plans import obj, result, seq
from .sources import (MAX_MEDIA_BYTES, ORDERS, PRODUCT, checked_media, drive_id, drive_inventory,
                      inspect_media, order_window, shopify_window, windows)
from .state import REGISTRY, now, parse_time, stamp
from .worker import ASSET_STEPS, bind_live_inputs, client_for, collector, review_inputs, run_due, strategy_history
from .workflow import ready_review, resume, submit

PRODUCT_STEPS = {"product-research", "scaling-eligibility"}
META_READ_STEPS = {"account-research", "campaign-strategy", "audience-planning", "scaling-analysis"}
META_WORK_STEPS = set(GATES) | {"activation-check", "budget-validation"}
MAX_EVIDENCE_AGE = timedelta(hours=1)


def enable(store, run):
    if run.get("connected"):
        return run
    require(run["request"].get("brand"), "Load the saved brand for connected-agent mode.")
    if run["status"] == "blocked" and not run.get("proposal") and not run["write_journal"]:
        reasons = " ".join(run.get("blockers", [])).lower()
        if any(name in reasons for name in ("shopify_read_token", "drive_read_token", "worker shopify read connection",
                                            "shopify_shop", "shopify_api_version", "meta_read_token")):
            run = resume(store, run["id"])
    run["connected"] = True
    store.save(run, "connected_agent_enabled", {})
    return run


def fresh(value):
    require(isinstance(value, str), "Missing connector observation time.")
    checked = parse_time(value)
    require(now() - MAX_EVIDENCE_AGE <= checked <= now() + timedelta(seconds=5),
            "Refresh the connector evidence before continuing.")


def scoped_shop(run, data):
    shop = obj(data.get("shop"), label="Shopify shop")
    require(shop.get("myshopifyDomain") == run["request"]["brand"]["shopify_shop"],
            "Shopify plugin returned a different shop.")


def shop_query(document):
    return document.replace(" {\n", " {\n  shop { myshopifyDomain }\n", 1)


def product_context(run, packet):
    request = run["request"]
    fresh(packet.get("observed_at"))
    pages = seq(packet.get("pages"), nonempty=True, label="Shopify product pages")
    require(len(pages) <= 60, "Too many Shopify product pages.")
    product, variants, after, seen = None, [], None, set()
    for index, page in enumerate(pages):
        require(page.get("after") == after, "Shopify product pages are out of sequence.")
        data = obj(page.get("data"), label="Shopify data")
        scoped_shop(run, data)
        observed = obj(data.get("product"), label="Shopify product")
        require(observed.get("id") == f"gid://shopify/Product/{request['product_id']}",
                "Shopify plugin returned a different product.")
        batch = obj(observed.get("variants"), label="Shopify variant connection")
        details = {k: v for k, v in observed.items() if k != "variants"}
        require(product is None or product == details, "Shopify product changed during pagination.")
        product = details
        variants.extend(seq(batch.get("nodes"), label="Shopify variants"))
        info = obj(batch.get("pageInfo"), label="Shopify pagination")
        require(info.get("hasNextPage") is (index < len(pages) - 1), "Shopify product listing is incomplete.")
        after = info.get("endCursor")
        require(not info["hasNextPage"] or isinstance(after, str) and after and after not in seen,
                "Shopify product pagination did not advance.")
        seen.add(after)
    variant_ids = sorted({v["id"].removeprefix("gid://shopify/ProductVariant/") for v in variants})
    if request.get("variant_id"):
        variants = [v for v in variants if v["id"] == f"gid://shopify/ProductVariant/{request['variant_id']}"]
        require(len(variants) == 1, "Shopify plugin did not return the assigned variant.")
    context = {"live_product": {**product, "variants": variants, "observed_at": packet["observed_at"]},
               "shopify_variant_ids": variant_ids}
    if run["step"] == "product-research":
        page = obj(packet.get("storefront"), label="storefront read")
        fresh(page.get("observed_at"))
        actual = urlsplit(destination(product.get("onlineStoreUrl")))
        supplied = destination(page.get("url"))
        target = urlsplit(supplied)
        require(supplied == request["landing_page"] and (target.netloc, target.path) == (actual.netloc, actual.path)
                and type(page.get("http_status")) is int and 200 <= page["http_status"] < 300,
                "The storefront read does not verify the saved Shopify product destination.")
        context["destination_read"] = {"url": supplied, "reachable": True, "observed_at": page["observed_at"]}
    return context


def periods_for(store, run, client_factory):
    if run["step"] == "customer-research":
        today = now().date()
        return timezone.utc, {"recent": (today - timedelta(days=30), today - timedelta(days=1))}
    try:
        account = client_factory(run).details()
    except (Stop, OSError):
        snapshot = meta_catchup.current_snapshot(store, run)
        if snapshot is None:
            raise
        account = snapshot["account_report"]["account"]
    return windows(run, account)


def aggregate_orders(run, packet, period, zone, campaign):
    request = run["request"]
    fresh(packet.get("observed_at"))
    _, _, expected = order_window(*period, zone)
    require(packet.get("query") == expected, "Shopify order dates differ from the requested window.")
    pages = seq(packet.get("pages"), nonempty=True, label="Shopify order pages")
    require(len(pages) <= 120, "Too many Shopify order pages.")
    page_iter = iter(pages)

    def read_page(_document, variables):
        page = next(page_iter, None)
        require(isinstance(page, dict) and page.get("after") == variables["after"],
                "Shopify order listing is incomplete or out of sequence.")
        data = obj(page.get("data"), label="Shopify order data")
        scoped_shop(run, data)
        return data

    aggregate = shopify_window(request["product_id"], campaign, *period, zone,
                               variant_id=request.get("variant_id"), order_query=read_page)
    require(next(page_iter, None) is None, "Unexpected extra Shopify order pages.")
    return {**aggregate, "observed_at": packet["observed_at"]}


def current_media(run):
    packet = obj(run.get("connected_media"), label="fresh approved Drive inventory from the connected agent")
    fresh(packet.get("observed_at"))
    return packet


def media_directory(store, run):
    require(re.fullmatch(r"[0-9a-f]{16}", run["id"]), "Invalid run identifier.")
    return store.path.parent / "connected-media" / run["id"]


def media_path(store, run, asset):
    revision = asset.get("revision")
    require(isinstance(revision, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,160}", revision), "Invalid Drive revision.")
    root = media_directory(store, run)
    path = root / f"{drive_id(asset['file_id'])}.{revision}.bin"
    require(path.resolve() == path and path.is_file(), "Download the selected Drive revision through the plugin.")
    return path


def read_media(store, run, asset):
    with media_path(store, run, asset).open("rb") as file:
        return checked_media(asset, file.read(MAX_MEDIA_BYTES + 1))


def inventory(store, run, packet):
    fresh(packet.get("observed_at"))
    listings = obj(packet.get("folders"), label="complete Drive folder listings")

    def children(folder):
        rows = seq(listings.get(folder), label=f"complete Drive folder listing for {folder}")
        require(all(folder in item.get("parents", ()) for item in rows),
                "A Drive result does not belong to the requested folder.")
        results = []
        for item in rows:
            if item.get("mimeType") not in {"image/png", "image/jpeg", "video/mp4"} or (
                    item.get("version") and item.get("md5Checksum")):
                results.append(item)
            elif head := item.get("headRevisionId"):
                try:
                    path = media_path(store, run, {"file_id": item["id"], "revision": head})
                except Stop:
                    continue
                with path.open("rb") as file:
                    raw = file.read(MAX_MEDIA_BYTES + 1)
                if len(raw) != int(item["size"]) or len(raw) > MAX_MEDIA_BYTES:
                    continue
                results.append({**item, "version": head, "md5Checksum": hashlib.md5(raw, usedforsecurity=False).hexdigest(),
                                "sha256Checksum": hashlib.sha256(raw).hexdigest()})
        return results

    return {"observed_at": packet["observed_at"], "assets": drive_inventory(children)}


def media_needed(run):
    return (run["step"] in ASSET_STEPS or GATES.get(run["step"]) == "build")


def candidate(store, run):
    snapshot = meta_catchup.current_snapshot(store, run)
    return snapshot, enrollment.match(run, snapshot)


def snapshot_account(run, snapshot, step):
    context = {"account_report": snapshot["account_report"], "meta_job_id": snapshot["job_id"]}
    if step == "campaign-strategy":
        funding = snapshot.get("funding", {})
        today = now().astimezone(account_zone(snapshot["account_report"]["account"]["timezone_name"])).date()
        require(funding.get("as_of") == today.isoformat(),
                "Refresh the Meta snapshot to read today's account-wide budget.")
        context["account_budget_before"] = budget_projection(funding, policy(run["request"]["brand"]))
    return context


def next_step(store, run, *, client_factory=client_for):
    require(run.get("connected"), "Start this run in connected-agent mode.")
    if run["status"] == "monitoring":
        run = run_due(store, only=run["id"], max_steps=1, client_factory=client_factory)[0]
    step = run["step"]
    response = {"run_id": run["id"], "step": step, "status": run["status"], "revision": run["revision"],
                "next_review_at": run["next_review_at"]}
    operator_build = (run.get("proposal") or {}).get("operation") == "build" and run["status"] == "approved"
    if run["status"] != "ready" and not operator_build:
        return response
    with configured(run["request"]["brand"]):
        if step in META_WORK_STEPS and not media_needed(run) and not operator_build:
            return {**response, "action": "meta-worker"}
        request = run["request"]
        context = run.get("connected_context", {})
        supplied = context.get("revision") == run["revision"] and context.get("step") == step
        if supplied:
            try:
                fresh(context["observed_at"])
            except Stop:
                supplied = False
        response.update(action="submit" if supplied else "collect", request=request, records=run["records"],
                        skill_path=REGISTRY.get(step, {}).get("path"), meta=run["meta"], sources={})
        if supplied:
            response["source_data"] = context["data"]
        existing = None
        if step == "campaign-strategy" and not run["meta"]:
            _, existing = candidate(store, run)
        if (step in PRODUCT_STEPS or existing) and not supplied:
            response["sources"]["shopify_product"] = {
                "query": shop_query(PRODUCT), "variables": {"id": f"gid://shopify/Product/{request['product_id']}", "after": None},
                "storefront": request["landing_page"] if step == "product-research" else None}
        if existing:
            response["sources"]["existing_campaign"] = existing["name"]
        if step in {"customer-research", "performance-analysis"} and not supplied:
            zone, periods = periods_for(store, run, client_factory)
            response["sources"]["shopify_orders"] = {
                "query": shop_query(ORDERS),
                "windows": {key: order_window(*period, zone)[2] for key, period in periods.items()}}
        if media_needed(run) or operator_build:
            if GATES.get(step) == "build":
                try:
                    current_media(run)
                except Stop:
                    pass
                else:
                    return {**response, "action": "dispatch" if operator_build else "meta-worker"}
            response["sources"]["drive"] = {
                "root": policy()["creative_root"], "stages": policy()["stages"],
                "excluded_folder": policy()["excluded_folder"], "media_directory": str(media_directory(store, run))}
        if step in META_READ_STEPS and not supplied and not existing:
            response["sources"]["meta_worker"] = True
        return response


def collect_step(store, run_id, packet, *, client_factory=client_for):
    run = store.get(run_id)
    require(run.get("connected") and packet.get("revision") == run["revision"],
            "Reload the current connected step before collecting its evidence.")
    step = run["step"]
    build = GATES.get(step) == "build" and run["status"] in {"ready", "approved"}
    require(run["status"] == "ready" or build, "The run is waiting for a decision.")
    with configured(run["request"]["brand"]):
        context = {}
        if step == "campaign-strategy" and not run["meta"]:
            snapshot, existing = candidate(store, run)
            if existing:
                product = product_context(run, obj(packet.get("shopify_product"), label="Fresh Shopify product read"))
                return enrollment.register(store, run, snapshot, existing, product["shopify_variant_ids"])
        if step == enrollment.STEP:
            snapshot, target = candidate(store, run)
            require(target and target["id"] == run["meta"]["id"], "Refresh Meta readback for the registered campaign.")
            context["paused_draft"] = enrollment.inspect(run, snapshot, target, run["enrolled_campaign"]["variant_ids"])
            context["account_report"] = snapshot["account_report"]
            context["meta_job_id"] = snapshot["job_id"]
            campaign = snapshot["campaigns"][target["id"]]
            context["delivery_history"] = {"from": snapshot["first_day"], "through": snapshot["last_complete_day"],
                                           "campaign_rows": campaign["daily"]["campaign"]}
            context["origin_evidence"] = run["request"].get("facts", {}).get("campaign_origin")
            funding = snapshot.get("funding", {})
            if funding.get("as_of"):
                context["account_budget_before"] = budget_projection(funding, policy())
        if step in PRODUCT_STEPS:
            context.update(product_context(run, obj(packet.get("shopify_product"), label="Shopify product read")))
        if step in {"customer-research", "performance-analysis"}:
            zones = obj(packet.get("shopify_orders", {}), label="Shopify order windows")
            zone, periods = periods_for(store, run, client_factory)
            require(set(zones) <= periods.keys(), "Unexpected Shopify order window.")
            campaign = run["meta"].get("name") or run.get("planned_name") or run["request"]["name"]
            reports = {key: aggregate_orders(run, evidence, periods[key], zone, campaign)
                       for key, evidence in zones.items()}
            if step == "customer-research":
                context.update(recent_order_sample=reports.get("recent"),
                               owner_feedback=run["request"].get("facts", {}).get("customer_feedback", []))
            else:
                by_period = {period: reports[key] for key, period in periods.items() if key in reports}

                def read_orders(_product, _campaign, start, end, _zone, **_kwargs):
                    require((start, end) in by_period, "Shopify order evidence is unavailable for this window.")
                    return by_period[start, end]

                try:
                    context["review_evidence"] = review_inputs(run, client_factory(run), order_reader=read_orders)
                except (Stop, OSError):
                    snapshot = meta_catchup.current_snapshot(store, run)
                    if snapshot is None:
                        raise
                    context["review_evidence"] = meta_catchup.review(snapshot, run["meta"], periods, reports)
        if step in META_READ_STEPS:
            meta = {}
            if step in {"account-research", "campaign-strategy", "audience-planning"}:
                snapshot = meta_catchup.current_snapshot(store, run)
                if snapshot:
                    try:
                        meta = snapshot_account(run, snapshot, step)
                    except Stop:
                        pass
            if not meta:
                meta, _ = collector(run, step, None, client_factory, meta_only=True)
                if step == "campaign-strategy" and "collection_error" in meta:
                    raise Stop("Refresh the GitHub Meta snapshot and sync it for current account-wide funding.")
            require("collection_error" not in meta, meta.get("collection_error", {}).get("unavailable", ""))
            context.update(meta)
        if media_needed(run):
            media = inventory(store, run, obj(packet.get("drive"), label="Drive inventory read"))
            require(media["assets"], "Read the current revisions and download eligible approved Drive originals before selection.")
            context["drive_media"] = list(media["assets"].values())
            run["connected_media"] = media
        if step == "strategy-development":
            context["strategy_history"] = strategy_history(store, run)
        if "review_evidence" not in context and "review_evidence" in run:
            context["review_evidence"] = run["review_evidence"]
        if not build:
            run["connected_context"] = {"step": step, "revision": run["revision"] + 1,
                                        "observed_at": stamp(), "data": context}
        store.save(run, "connected_evidence_collected", {"step": step, "sources": sorted(context)})
        return run


def submit_step(store, run, packet):
    step = run["step"]
    require(run.get("connected") and run["status"] == "ready" and step not in META_WORK_STEPS,
            "The connected agent can submit only a ready analysis step.")
    saved = run.get("connected_context", {})
    require(packet.get("revision") == run["revision"] == saved.get("revision") and saved.get("step") == step,
            "Collect evidence for the current revision before submitting the connected step.")
    fresh(saved["observed_at"])
    context, output = saved["data"], obj(packet.get("result"), label="connected skill result")
    with configured(run["request"]["brand"]):
        result(step, output)
        bind_live_inputs(run, step, context, output)
        if step == enrollment.STEP and output["status"] == "pass":
            choice = output["data"]["decision"]
            require(choice in {"keep_paused", "check_activation", "replan"}, "Choose a disposition for the existing paused draft.")
            require(choice == "check_activation" or output["data"]["findings"], "Record the reason for the draft decision.")
            if choice == "check_activation":
                snapshot, target = candidate(store, run)
                require(target and target["id"] == run["meta"]["id"] and snapshot["job_id"] == context["meta_job_id"],
                        "Recollect the draft review against the newest Meta snapshot.")
                run["meta"]["pending_batch"] = enrollment.prepare_adopted_batch(run, snapshot, target, output["data"])
        if step in ASSET_STEPS and output["status"] in {"pass", "limited"}:
            selected = output["data"] if step == "asset-selection" else run["records"]["asset-selection"]["data"]
            assets = current_media(run)["assets"]
            for entry in selected["assets"]:
                asset = assets.get(entry["file_id"])
                require(asset and asset["revision"] == entry["revision"] and asset["stage"] == entry["stage"],
                        "Approved Drive asset changed before validation.")
                read_media(store, run, asset)
                inspect_media(media_path(store, run, asset))
        if step == "performance-analysis":
            review = context["review_evidence"]
            configuration = review.get("configuration", {})
            if configuration and "unavailable" not in configuration and configuration != run.get("campaign_configuration"):
                old = run.get("campaign_configuration")
                run["campaign_configuration"] = configuration
                run["last_material_change_at"] = stamp()
                review["configuration_changed"] = [key for key, value in configuration.items()
                                                   if old and old.get(key) != value]
            run["review_evidence"] = review
        run.pop("connected_context")
        return submit(store, run, output)
