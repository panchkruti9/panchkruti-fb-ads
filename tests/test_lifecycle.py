"""Exercise decision boundaries using temporary state and a fake Marketing API."""
import hashlib
import json
import os
import tempfile
import unittest
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from ads import connected, meta_catchup
from ads.__main__ import assigned_requests, initialize
from ads.execution import authorize, campaign_configuration, identity, reconcile, sign
from ads.meta import Stop, configured
from ads.plans import VISUAL_CHECKS
from ads.sources import shopify_window
from ads.state import GROUPS, REGISTRY, Store, now, stamp
from ads.worker import bind_live_inputs, evidence, output, review_inputs, run_due, submit_manual
from ads.workflow import decision, execute, prepare, ready_review, request, resume, scale_proof, submit

NAME = "agi-duo-unit-test"
LINK = "https://shop.test-example.com/products/duo"
IMG = {"file_id": "imagefile1234", "name": "duo.jpg", "mime": "image/jpeg",
       "revision": "1", "stage": "discovery", "bytes": 9, "md5": "synthetic"}
VIDEO = {**IMG, "file_id": "videofile1234", "name": "duo.mp4", "mime": "video/mp4"}
ENV = {"META_PAGE_ID": "11", "META_PIXEL_ID": "12", "META_INSTAGRAM_USER_ID": "13",
       "PANCHKRUTI_OPERATOR_KEY": "simulation-only-key-for-test-fixtures-123456"}


class FakeMeta:
    version = "v27.0"
    writer = True
    account = "99"
    prefix = "act_99"

    def __init__(self):
        self.remote = {}
        self.posts = []
        self.timeout = None
        self.video_state = "processing"
        self.spend_minor = 0
        self.external_daily = 0

    def details(self):
        return {"account_id": self.account, "account_status": 1, "currency": "INR", "timezone_name": "UTC"}

    def pages(self, path, fields, **params):
        parent, edge = path.split("/")
        if edge == "adimages":
            return [{"hash": "fixture-image"}]
        if edge == "previews":
            return [{"body": "<iframe>fixture</iframe>"}]
        rows = [row for row in self.remote.values() if row["edge"] == edge]
        if parent == self.prefix:
            return deepcopy(rows)
        return deepcopy([r for r in rows if r.get("campaign_id") == parent])

    def request(self, path, params, *, post=False):
        if not post:
            if path == self.prefix:
                return {"spend_cap": 3000000, "amount_spent": self.spend_minor}
            return deepcopy(self.remote[path])
        self.posts.append((path, deepcopy(params)))
        if "/" not in path:
            item = self.remote[path]
            for field, value in params.items():
                if field == "status":
                    item.update(configured_status=value, effective_status=value)
                else:
                    item[field] = value
            return {"success": True}
        _, edge = path.split("/")
        if self.timeout == "before" and edge == "campaigns":
            self.timeout = None
            raise Stop("simulated timeout before write")
        oid = str(100 + len(self.remote))
        row = {"id": oid, "account_id": self.account, "edge": edge, **deepcopy(params)}
        if "status" in row:
            row["configured_status"] = row["effective_status"] = row["status"]
        if edge == "ads":
            row["campaign_id"] = self.remote[row["adset_id"]]["campaign_id"]
            row["creative"] = {"id": row["creative"]["creative_id"]}
        self.remote[oid] = row
        if self.timeout == "after" and edge == "campaigns":
            self.timeout = None
            raise Stop("simulated timeout after write")
        return {"id": oid}

    def owned(self, object_id, fields):
        return deepcopy(self.remote[object_id])

    def scope(self, object_id, kind, name):
        edge = {"campaign": "campaigns", "adset": "adsets", "ad": "ads"}[kind]
        value = self.remote.get(object_id)
        if not value or value["edge"] != edge or not value["name"].startswith(name):
            raise Stop("outside scope")
        return deepcopy(value)

    def creative(self, creative_id, link, fmt):
        from ads.meta import fingerprint
        return fingerprint(self.remote[creative_id])

    def budget(self, *, add=0, replace=None):
        total = add + self.external_daily + sum(x.get("daily_budget", 0) for x in self.remote.values()
                                               if x.get("configured_status") == "ACTIVE")
        if replace:
            oid, before, after = replace
            if self.remote[oid]["daily_budget"] != before:
                raise Stop("starting amount changed")
            total += after - before
        projected = self.spend_minor + total * 10
        return {"daily_minor": total, "monthly_minor": projected, "spent_month_minor": self.spend_minor,
                "passed": 30000 <= total <= 150000 and projected <= 3000000}


def valid_result(step, data=None):
    defaults = {"object": {}, "array": [], "string": "fixture", "integer": 1,
                "boolean": False, "record": {}, "object?": None}
    values = {field: deepcopy(defaults[kind]) for field, kind in REGISTRY[step].get("types", {}).items()}
    values.update(data or {})
    return output(f"Fixture for {step}", values, refs=[evidence("fixture", "synthetic-run")])


class LifecycleTest(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.store = Store(Path(self.scratch.name) / "workflow.db")
        self.addCleanup(self.store.db.close)
        self.client = FakeMeta()
        self.inventory = {item["file_id"]: item for item in (IMG, VIDEO)}
        fixture_env = patch.dict(os.environ, ENV)
        fixture_env.start()
        self.addCleanup(fixture_env.stop)
        legacy = Path(self.scratch.name) / "legacy-brand.json"
        rules = {"currency": "INR", "minor_per_unit": 100, "minimum_daily_minor": 30000,
                 "maximum_daily_minor": 150000, "maximum_monthly_minor": 3000000, "approval_hours": 24,
                 "stages": {"discovery": "Discovery", "consideration": "Consideration", "purchase": "Purchase"},
                 "formats": ["static", "video", "story"]}
        legacy.write_text(json.dumps({"website_hosts": ["shop.test-example.com"], "policy": rules}), encoding="utf-8")
        fixture_policy = patch("ads.meta.LEGACY_PROFILE_FILE", legacy)
        fixture_policy.start()
        self.addCleanup(fixture_policy.stop)
        for key, value in {
            "drive_inventory": lambda: self.inventory,
            "drive_media": lambda asset: b"test",
            "upload": self.mock_upload,
            "storefront": lambda url: {"reachable": True},
        }.items():
            p = patch("ads.execution." + key, value)
            p.start()
            self.addCleanup(p.stop)
        p = patch("ads.worker.storefront", lambda url: {"reachable": True})
        p.start()
        self.addCleanup(p.stop)
        self.run = self.store.create(request({
            "product_id": "101", "name": NAME, "account_id": "99", "countries": ["IN"], "brief": "Synthetic fixture",
            "facts": {"tracking": {"purchase_verified": True, "checkout_verified": True, "reference": "event fixture",
                                   "observed_at": stamp(), "product_id": "101", "pixel_id": "12"},
                      "spend_control": {"reference": "fixture cap"}},
            "review_policy": {"maximum_cpa_minor": 10000},
        }))

    def mock_upload(self, client, asset, raw):
        if asset["mime"] != "video/mp4":
            return {"hash": "fixture-image"}
        client.remote["999"] = {"id": "999", "edge": "videos",
                                "status": {"video_status": client.video_state}}
        return {"id": "999"}

    def add(self, data=None):
        self.run = submit(self.store, self.run, valid_result(self.run["step"], data))
        return self.run

    def reach_build(self, use_video=False):
        campaign = self.run["request"]["name"]
        link = self.run["request"].get("landing_page", LINK)
        while self.run["step"] != "creative-validation":
            step = self.run["step"]
            if step == "product-research":
                self.add({"product_facts": {"url": link}})
            elif step == "strategy-development":
                self.add({"next_review_on": (now().date() + timedelta(days=20)).isoformat(),
                          "criteria": {"window_days": 5, "lag_days": 1, "minimum_matched_orders": 3,
                                       "maximum_cpa_minor": 10000, "recheck_hours": 24}})
            elif step == "campaign-strategy":
                self.add({"campaign_key": campaign, "account_id": "99", "objective": "OUTCOME_SALES",
                          "budget": {"level": "campaign", "daily_minor": 30000}})
            elif step == "ad-copywriting":
                fmt = "story" if use_video else "static"
                slug = f"{campaign}-discovery-routine-{fmt}-v01"
                variant = {"name": slug, "primary_text": "Synthetic", "headline": "Fixture", "description": "", "cta": "SHOP_NOW"}
                self.add({"variants": [variant]})
            elif step == "asset-selection":
                self.add({"assets": [IMG, VIDEO] if use_video else [IMG]})
            else:
                self.add()
        ad = {**self.run["records"]["ad-copywriting"]["data"]["variants"][0],
              "stage": "discovery", "format": "story" if use_video else "static",
              "asset_id": VIDEO["file_id"] if use_video else IMG["file_id"],
              "poster_asset_id": IMG["file_id"] if use_video else None,
              "destination": link, "url_tags": f"utm_source=meta&utm_medium=paid_social&utm_campaign={campaign}&utm_content={slug}"}
        self.add({"ads": [{"name": slug, "approved_ad": ad, "evidence": ["fixture"],
                           "checks": dict.fromkeys(VISUAL_CHECKS, True)}],
                  "plan": {"objective": "OUTCOME_SALES", "budget_level": "campaign", "daily_minor": 30000,
                           "adsets": [{"name": campaign + "-india", "daily_minor": 0, "country_codes": ["IN"],
                                       "placements": ["instagram_story"] if use_video else ["facebook_feed"],
                                       "existing_adset_id": None, "ads": [ad]}]}})
        self.run = prepare(self.store, self.run, self.client)

    def approve(self, owner=None, renew=False):
        self.run = authorize(self.store, self.run["id"], self.run["proposal"]["id"],
                             operator="fixture operator", owner=owner, reference="fixture approval", renew=renew)

    def execute(self):
        self.run = execute(self.store, self.run["id"], lambda _account: self.client)
        return self.run

    def test_configured_request_enforces_brand_scope_and_format_policy(self):
        root = Path(__file__).resolve().parents[1] / "examples"
        brand = json.loads((root / "brand-profile.json").read_text(encoding="utf-8"))
        item = json.loads((root / "product-request.json").read_text(encoding="utf-8"))
        configured = request(item, brand)
        self.assertEqual(configured["account_id"], brand["account_id"])
        self.assertEqual(configured["review_policy"]["maximum_cpa_minor"], item["target_cost_minor"])
        with self.assertRaises(Stop):
            request({**item, "landing_page": LINK}, brand)
        with self.assertRaises(Stop):
            request({**item, "formats": ["carousel"]}, brand)

    def test_fresh_copy_setup_keeps_unknowns_blank_and_preserves_saved_profile(self):
        root = Path(self.scratch.name) / "fresh"
        template = root / "examples" / "brand-profile.json"
        template.parent.mkdir(parents=True)
        template.write_bytes((Path(__file__).resolve().parents[1] / "examples" / template.name).read_bytes())
        with patch("ads.__main__.ROOT", root):
            first = initialize("Example New Brand")
            path = Path(first["brand"])
            brand = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(path.parent.parent, root / ".state")
            self.assertIsNone(brand["account_id"])
            self.assertIsNone(brand["policy"]["maximum_monthly_minor"])
            self.assertNotIn("page_id", brand)
            with self.assertRaises(Stop):
                request(json.loads(Path(first["product"]).read_text(encoding="utf-8")), brand)
            brand["website"] = "https://shop.example.com"
            path.write_text(json.dumps(brand), encoding="utf-8")
            self.assertEqual(initialize("Example New Brand"), first)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["website"], brand["website"])

    def test_manage_uses_all_assignments_and_reuses_existing_runs(self):
        examples = Path(__file__).resolve().parents[1] / "examples"
        root = Path(self.scratch.name) / "manage-copy"
        brand_dir = root / ".state" / "one-brand"
        brand_dir.mkdir(parents=True)
        (brand_dir / "brand.json").write_bytes((examples / "brand-profile.json").read_bytes())
        first = json.loads((examples / "product-request.json").read_text(encoding="utf-8"))
        second = {**first, "product_id": "200000002", "product_name": "Second product"}
        for name, data in [("first.json", first), ("second.json", second), ("unassigned.json", {})]:
            (brand_dir / name).write_text(json.dumps(data), encoding="utf-8")
        (brand_dir / "assignments.json").write_text('["first.json", "second.json"]', encoding="utf-8")
        with patch("ads.__main__.ROOT", root):
            assigned = assigned_requests()
        self.assertEqual([item["product_id"] for item in assigned], ["200000001", "200000002"])
        runs = [self.store.create(item, reuse_existing=True) for item in assigned]
        runs[0]["status"] = "stopped"
        self.store.save(runs[0], "fixture_stop", {})
        resumed = [self.store.create(item, reuse_existing=True) for item in assigned]
        self.assertEqual([item["id"] for item in resumed], [item["id"] for item in runs])
        self.assertEqual(resumed[0]["status"], "stopped")

    def test_manual_submissions_cannot_bypass_live_checks(self):
        with patch("ads.worker.collector", return_value=({}, [])):
            with self.assertRaisesRegex(Stop, "reachable Shopify product"):
                submit_manual(self.store, self.run, valid_result("product-research"))
        self.assertEqual(self.store.get(self.run["id"])["step"], "product-research")
        self.run["step"] = "activation-check"
        with self.assertRaisesRegex(Stop, "collected by the worker"):
            submit_manual(self.store, self.run, {})

    def test_connected_product_reuses_blocked_run_and_binds_plugin_evidence(self):
        examples = Path(__file__).resolve().parents[1] / "examples"
        brand = json.loads((examples / "brand-profile.json").read_text(encoding="utf-8"))
        product = json.loads((examples / "product-request.json").read_text(encoding="utf-8"))
        campaign = request(product, brand)
        run = self.store.create(campaign)
        submit(self.store, run, output("Shopify unavailable.", {}, refs=[], status="block",
                                      blockers=["Missing SHOPIFY_READ_TOKEN."]))
        run = connected.enable(self.store, self.store.get(run["id"]))
        self.assertEqual(run["status"], "ready")
        self.assertEqual(run["id"], self.store.create(campaign, reuse_existing=True)["id"])
        with patch("ads.worker.collector", side_effect=AssertionError("Direct reads were used")):
            self.assertEqual(run_due(self.store, only=run["id"])[0], run)
        task = connected.next_step(self.store, run)
        self.assertEqual(task["action"], "collect")
        self.assertEqual(set(task["sources"]), {"shopify_product"})
        capture = stamp()
        source = {"shop": {"myshopifyDomain": "other.myshopify.com"},
                  "product": {"id": f"gid://shopify/Product/{campaign['product_id']}",
                              "onlineStoreUrl": campaign["landing_page"],
                              "variants": {"nodes": [], "pageInfo": {"hasNextPage": False}}}}
        if campaign.get("variant_id"):
            source["product"]["variants"]["nodes"] = [{"id": f"gid://shopify/ProductVariant/{campaign['variant_id']}"}]
        packet = {"revision": run["revision"], "shopify_product": {
            "observed_at": capture, "pages": [{"after": None, "data": source}],
            "storefront": {"url": campaign["landing_page"], "http_status": 200, "observed_at": capture}}}
        with self.assertRaisesRegex(Stop, "different shop"):
            connected.collect_step(self.store, run["id"], packet)
        source["shop"]["myshopifyDomain"] = brand["shopify_shop"]
        collected = connected.collect_step(self.store, run["id"], packet)
        evidence = connected.next_step(self.store, collected)
        self.assertEqual(evidence["action"], "submit")
        result = valid_result("product-research", {"product_facts": {"url": campaign["landing_page"]}})
        with self.assertRaisesRegex(Stop, "current revision"):
            connected.submit_step(self.store, collected, {"revision": run["revision"], "result": result})
        final = connected.submit_step(self.store, collected, {"revision": collected["revision"], "result": result})
        self.assertEqual(final["step"], "customer-research")
        self.assertEqual(final["records"]["product-research"]["status"], "pass")
        self.assertEqual(connected.next_step(self.store, final)["sources"].keys(), {"shopify_orders"})

    def test_connected_drive_accepts_only_approved_folder_and_matching_bytes(self):
        examples = Path(__file__).resolve().parents[1] / "examples"
        brand = json.loads((examples / "brand-profile.json").read_text(encoding="utf-8"))
        product = json.loads((examples / "product-request.json").read_text(encoding="utf-8"))
        run = connected.enable(self.store, self.store.create(request(product, brand)))
        run["step"] = "asset-selection"
        self.store.save(run, "fixture_asset_selection", {})
        task = connected.next_step(self.store, run)
        root = task["sources"]["drive"]["root"].rstrip("/").split("/")[-1]
        folders = {root: []}
        discovery = None
        for stage, name in brand["policy"]["stages"].items():
            identifier = "allowedfolder_" + stage
            folders[root].append({"id": identifier, "name": name, "parents": [root],
                                  "mimeType": "application/vnd.google-apps.folder"})
            folders[identifier] = []
            if stage == "discovery":
                discovery = identifier
        original = b"plugin source bytes"
        file_id = "connectedasset123"
        item = {"id": file_id, "name": "asset.jpg", "parents": ["wrongfolder"], "mimeType": "image/jpeg",
                "version": "8", "md5Checksum": hashlib.md5(original, usedforsecurity=False).hexdigest(),
                "size": str(len(original))}
        folders[discovery].append(item)
        packet = {"revision": run["revision"], "drive": {"observed_at": stamp(), "folders": folders}}
        with self.assertRaisesRegex(Stop, "does not belong"):
            connected.collect_step(self.store, run["id"], packet)
        item["parents"] = [discovery]
        with patch("ads.sources.drive_list", side_effect=AssertionError("Direct Drive read was used")):
            run = connected.collect_step(self.store, run["id"], packet)
        asset = connected.current_media(run)["assets"][file_id]
        directory = connected.media_directory(self.store, run)
        directory.mkdir(parents=True)
        path = directory / f"{file_id}.8.bin"
        path.write_bytes(b"changed source")
        with self.assertRaisesRegex(Stop, "approved Drive revision"):
            connected.read_media(self.store, run, asset)
        path.write_bytes(original)
        self.assertEqual(connected.read_media(self.store, run, asset), original)
        opaque_head = "0B4B-current_binary_revision"
        path = directory / f"{file_id}.{opaque_head}.bin"
        path.write_bytes(original)
        item.pop("version")
        item.pop("md5Checksum")
        item["headRevisionId"] = opaque_head
        packet["revision"] = run["revision"]
        run = connected.collect_step(self.store, run["id"], packet)
        asset = connected.current_media(run)["assets"][file_id]
        self.assertEqual(asset["revision"], opaque_head)
        self.assertEqual(asset["sha256"], hashlib.sha256(original).hexdigest())
        self.assertEqual(connected.read_media(self.store, run, asset), original)

    def test_meta_catchup_counts_each_snapshot_once_and_keeps_daily_reach_separate(self):
        examples = Path(__file__).resolve().parents[1] / "examples"
        brand = json.loads((examples / "brand-profile.json").read_text(encoding="utf-8"))
        product = json.loads((examples / "product-request.json").read_text(encoding="utf-8"))
        run = connected.enable(self.store, self.store.create(request(product, brand)))
        run["meta"] = {"id": "123", "name": run["request"]["name"]}
        run["live_since"] = (now() - timedelta(days=3)).isoformat()
        self.store.save(run, "fixture_live", {})
        day = (now().date() - timedelta(days=1)).isoformat()
        previous_day = (now().date() - timedelta(days=2)).isoformat()
        row = {"campaign_id": "123", "date_start": day, "date_stop": day, "spend": "5.50",
               "impressions": "10", "reach": "4", "frequency": "2.5",
               "actions": [{"action_type": "purchase", "value": "1"}]}
        daily = [row, {**row, "date_start": previous_day, "date_stop": previous_day}]
        snapshot = {"job_id": "1000", "observed_at": stamp(), "first_day": previous_day, "last_complete_day": day,
                    "account_report": {"account": {"account_id": brand["account_id"], "currency": brand["policy"]["currency"]}},
                    "campaigns": {"123": {"name": run["meta"]["name"], "effective_status": "ACTIVE",
                                          "alerts": [], "daily": {"campaign": daily}}}}
        cache = self.store.path.parent / "meta-catchup" / "snapshots"
        cache.mkdir(parents=True)
        (cache / "1000.json").write_text(json.dumps(snapshot), encoding="utf-8")
        once = meta_catchup.record(self.store, run)
        twice = meta_catchup.record(self.store, once)
        self.assertEqual(once["revision"], twice["revision"])
        self.assertEqual(sum(event["kind"] == "meta_catchup" for event in self.store.events(run["id"])), 1)
        aggregate = meta_catchup.aggregate_daily(daily, "campaign", previous_day, day)[0]
        self.assertEqual(aggregate["spend"], "11.00")
        self.assertEqual(aggregate["actions"], [{"action_type": "purchase", "value": "2"}])
        self.assertNotIn("reach", aggregate)

    def test_campaign_strategy_rejects_existing_campaign_before_build(self):
        context = {"account_report": {"account": {"account_id": "99"}, "managed_objects": [{"name": NAME}]}}
        plan = valid_result("campaign-strategy", {"account_id": "99"})
        with self.assertRaisesRegex(Stop, "already exists"):
            bind_live_inputs(self.run, "campaign-strategy", context, plan)
        self.run["create_mode"] = "refresh"
        self.assertIs(bind_live_inputs(self.run, "campaign-strategy", context, plan), plan)

    def test_learning_status_is_optional_and_does_not_discard_sales_reports(self):
        self.reach_build()
        self.approve()
        self.execute()
        adset = next(row for row in self.client.remote.values() if row["edge"] == "adsets")
        adset["learning_stage_info"] = {"status": "LEARNING"}
        with patch("ads.worker.meta_window", return_value={"rows": {}}), patch(
                "ads.worker.shopify_window", return_value={"matched_orders": 3}):
            review = review_inputs(self.run, self.client)
            self.assertEqual(review["adset_delivery"]["adsets"][0]["learning_stage_info"]["status"], "LEARNING")
            with patch.object(self.client, "pages", side_effect=Stop("Learning field unavailable")):
                review = review_inputs(self.run, self.client)
            self.assertIn("unavailable", review["adset_delivery"])
            self.assertEqual(review["shopify"]["current"]["matched_orders"], 3)

    def test_campaign_intake_defers_publishing_ids_until_meta_readback(self):
        examples = Path(__file__).resolve().parents[1] / "examples"
        brand = json.loads((examples / "brand-profile.json").read_text(encoding="utf-8"))
        item = json.loads((examples / "product-request.json").read_text(encoding="utf-8"))
        for key in ("page_id", "pixel_id", "instagram_id"):
            brand.pop(key)
        brand["identity_reference"] = {"campaign_name": "agi-test-sales", "adset_id": "42", "ad_id": "43"}
        self.assertEqual(request(item, brand)["product_id"], item["product_id"])
        self.client.scope = lambda *_: {"adset_id": "42", "creative": {"id": "44"}}
        self.client.owned = lambda object_id, _: {
            "promoted_object": {"pixel_id": "92"}
        } if object_id == "42" else {"object_story_spec": {
            "page_id": "91", "instagram_user_id": "93", "link_data": {"link": item["landing_page"]}
        }}
        with configured(brand):
            actual = identity({"adsets": [{"placements": ["instagram_feed"]}]}, self.client)
        self.assertEqual(actual, {"page_id": "91", "pixel_id": "92", "instagram_user_id": "93"})

    def test_configured_brand_policy_applies_to_build_and_activation(self):
        root = Path(__file__).resolve().parents[1] / "examples"
        brand = json.loads((root / "brand-profile.json").read_text(encoding="utf-8"))
        item = json.loads((root / "product-request.json").read_text(encoding="utf-8"))
        brand.update(account_id="99", page_id="91", pixel_id="92")
        brand["policy"].update(maximum_daily_minor=150000, maximum_monthly_minor=3000000,
                               operators=["fixture operator"], owners=["fixture owner"])
        facts = deepcopy(self.run["request"]["facts"])
        facts["tracking"].update(product_id=item["product_id"], pixel_id="92")
        item.update(facts=facts, countries=["IN"], daily_budget_minor=30000, target_cost_minor=10000)
        self.run = self.store.create(request(item, brand))
        self.reach_build()
        self.assertEqual(self.run["proposal"]["action"]["identity"]["page_id"], "91")
        with self.assertRaises(Stop):
            authorize(self.store, self.run["id"], self.run["proposal"]["id"],
                      operator="outside policy", owner=None, reference="fixture approval")
        self.approve()
        self.execute()
        self.assertEqual(self.run["last_receipt"]["operation"], "build")
        self.launch()

    def test_recreate_worker_receives_prior_strategy_and_failed_decision(self):
        self.reach_build()
        self.approve()
        self.execute()
        self.launch()
        old_version = self.run["strategy_version"]
        self.run["last_material_change_at"] = (now() - timedelta(days=20)).isoformat()
        self.run["review_evidence"] = self.sales_evidence()
        self.run.update(status="ready", group="optimize", step="optimization-decision")
        self.run["records"]["business-performance"] = valid_result("business-performance", {
            "shopify_current": {"matched_orders": 4},
        })
        self.store.save(self.run, "fixture_review", {})
        self.add({"decision": "RECREATE", "rationale": "Test exceeded the approved cost target.",
                  "target_id": self.run["meta"]["id"], "next_review_on": now().date().isoformat()})
        self.assertEqual(self.run["group"], "research")
        self.assertNotIn("strategy-development", self.run["records"])
        captured = {}

        def agent(run, step, context, images, scratch):
            if step == "strategy-development":
                captured.update(context["strategy_history"][-1])
                return valid_result(step, {
                    "next_review_on": (now().date() + timedelta(days=10)).isoformat(),
                    "criteria": {"window_days": 5, "lag_days": 1, "minimum_matched_orders": 3,
                                 "maximum_cpa_minor": 10000, "recheck_hours": 24},
                })
            return valid_result(step)

        with patch("ads.worker.collector", return_value=({}, [])), patch(
                "ads.worker.bind_live_inputs", side_effect=lambda run, step, context, result: result):
            self.run = run_due(self.store, only=self.run["id"], max_steps=len(GROUPS["research"]),
                               agent=agent, client_factory=lambda _: self.client)[0]
        self.assertEqual(self.run["strategy_version"], old_version + 1)
        self.assertEqual(self.run["step"], "campaign-strategy")
        self.assertEqual(captured["strategy"]["data"]["version"], old_version)
        self.assertEqual(captured["results"]["business-performance"]["data"]["shopify_current"]["matched_orders"], 4)
        self.assertIn("approved cost target", captured["results"]["optimization-decision"]["data"]["rationale"])
        self.assertTrue(any(e["payload"].get("closed_strategy_cycle") for e in self.store.events(self.run["id"])))

    def launch(self):
        self.run = run_due(self.store, only=self.run["id"], client_factory=lambda _run: self.client)[0]
        self.assertEqual(self.run["proposal"]["operation"], "activate")
        self.approve(owner="fixture owner")
        self.execute()
        self.assertEqual(self.run["status"], "monitoring")

    def test_build_cannot_write_without_approval_then_activation_schedules_monitoring(self):
        self.reach_build()
        with self.assertRaises(Stop):
            self.execute()
        self.assertEqual(self.client.posts, [])
        self.approve()
        self.execute()
        self.assertEqual(self.run["last_receipt"]["operation"], "build")
        self.assertEqual({n["configured_status"] for n in self.run["last_receipt"]["objects"]}, {"PAUSED"})
        self.run = run_due(self.store, only=self.run["id"], client_factory=lambda _run: self.client)[0]
        with self.assertRaises(Stop):
            self.approve()
        self.launch()
        self.assertEqual(self.client.posts[-1], (self.run["meta"]["id"], {"status": "ACTIVE"}))
        self.assertIsNotNone(self.run["next_review_at"])
        self.assertGreater(len(self.store.events(self.run["id"])), 20)

    def test_timeout_that_created_campaign_reconciles_without_duplicate(self):
        self.reach_build()
        self.approve()
        self.client.timeout = "after"
        self.assertEqual(self.execute()["status"], "execution_blocked")
        self.execute()
        self.assertEqual(len(self.client.posts), 1)
        self.run = reconcile(self.store, self.run["id"], "campaign", self.client)
        self.execute()
        self.assertEqual(self.run["last_receipt"]["operation"], "build")
        self.assertEqual(sum(x[0].endswith("/campaigns") for x in self.client.posts), 1)

    def test_confirmed_absence_can_resume_same_approval(self):
        self.reach_build()
        self.approve()
        self.client.timeout = "before"
        self.assertEqual(self.execute()["status"], "execution_blocked")
        with self.assertRaises(Stop):
            reconcile(self.store, self.run["id"], "campaign", self.client)
        self.run = reconcile(self.store, self.run["id"], "campaign", self.client,
                             absent=True, reference="fixture investigation")
        self.execute()
        self.assertEqual(self.run["last_receipt"]["operation"], "build")
        self.assertEqual(sum(x["edge"] == "campaigns" for x in self.client.remote.values()), 1)

    def test_story_video_processing_requeues_without_reupload(self):
        self.reach_build(use_video=True)
        self.approve()
        self.assertEqual(self.execute()["status"], "approved")
        self.client.remote["999"]["status"]["video_status"] = "ready"
        self.execute()
        self.assertEqual(self.run["last_receipt"]["operation"], "build")
        self.assertEqual(self.run["last_receipt"]["ad_ids"][0]["placements"], ["instagram_story"])

    def test_scale_requires_same_approved_proposal_and_live_account_headroom(self):
        self.reach_build()
        self.approve()
        self.execute()
        self.launch()
        self.run["live_since"] = (now() - timedelta(days=20)).isoformat()
        self.run["last_material_change_at"] = self.run["live_since"]
        self.store.save(self.run, "fixture_backdated_activation", {})
        self.run = ready_review(self.store, self.run, force=True)
        for step in GROUPS["optimize"][:5]:
            self.assertEqual(self.run["step"], step)
            self.add()
        self.run["review_evidence"] = self.sales_evidence()
        self.run["request"]["facts"]["economics"] = self.realized_economics()
        self.store.save(self.run, "fixture_evidence", {})
        target = self.run["meta"]["id"]
        self.add({"decision": "SCALE", "rationale": "fixture matched economics",
                  "target_id": target, "next_review_on": now().date().isoformat()})
        self.add({"eligible": True, "verified_checks": dict.fromkeys(("business", "tracking", "stability", "inventory", "fulfilment"), True)})
        self.add({"target_id": target, "current_daily_minor": 30000, "proposed_daily_minor": 36000})
        self.add({"account_id": "99", "projected_daily_minor": 36000, "projected_monthly_minor": 360000, "passed": True})
        self.add({"target_id": target, "from_daily_minor": 30000, "to_daily_minor": 36000,
                  "case": "fixture case", "next_review_on": now().date().isoformat()})
        self.run = prepare(self.store, self.run, self.client)
        with self.assertRaises(Stop):
            self.approve()
        self.approve(owner="fixture owner")
        self.client.external_daily = 120000
        self.assertEqual(self.execute()["status"], "execution_blocked")
        self.assertEqual(self.client.remote[target]["daily_budget"], 30000)
        self.client.external_daily = 0
        self.execute()
        self.assertEqual(self.client.remote[target]["daily_budget"], 36000)
        self.assertEqual(self.run["status"], "monitoring")

    def sales_evidence(self):
        period_a = {"start": (now().date() - timedelta(days=6)).isoformat(),
                    "end": (now().date() - timedelta(days=2)).isoformat()}
        period_b = {"start": (now().date() - timedelta(days=11)).isoformat(),
                    "end": (now().date() - timedelta(days=7)).isoformat()}
        periods = {"current": period_a, "previous": period_b}
        return {
            "meta": {k: {**v, "rows": {"campaign": [{"spend": "300.00"}]}} for k, v in periods.items()},
            "shopify": {k: {**v, "matched_orders": 4, "pending_journey": 0,
                            "product_cash": {"paid_orders": {"received_less_refunds_and_tax_minor": 65000,
                                                            "covered_orders": 4, "unallocated_orders": 0}}}
                        for k, v in periods.items()},
        }

    def realized_economics(self):
        return {"product_id": "101", "campaign": NAME, "success_metric": "paid_orders", "source": "Verified ledger",
                "windows": [{key: value for key, value in period.items() if key in ("start", "end")}
                            | {"product_cost_minor": 12000, "shipping_fulfillment_minor": 3000, "fees_minor": 2000}
                            for period in self.sales_evidence()["shopify"].values()]}

    def test_scale_requires_distinct_mature_windows_and_positive_contribution(self):
        self.reach_build()
        self.run["meta"].update(id="99", name=NAME)
        self.run["last_material_change_at"] = (now() - timedelta(days=20)).isoformat()
        self.run["review_evidence"] = self.sales_evidence()
        self.assertFalse(scale_proof(self.run))
        economics = self.run["request"]["facts"]["economics"] = self.realized_economics()
        economics["windows"][0]["fees_minor"] = 21000
        self.assertFalse(scale_proof(self.run))
        economics["windows"][0]["fees_minor"] = 2000
        self.assertTrue(scale_proof(self.run))
        for source in ("meta", "shopify"):
            results = self.run["review_evidence"][source]
            results["previous"] = deepcopy(results["current"])
        self.assertFalse(scale_proof(self.run))

    def test_product_cash_subtracts_refunds_and_excludes_unallocated_mixed_carts(self):
        from datetime import timezone

        def money_bag(amount):
            return {"shopMoney": {"amount": str(amount), "currencyCode": "INR"}}

        today = now().date()
        line = {"currentQuantity": 1, "product": {"id": "gid://shopify/Product/101"}}
        single = {
            "createdAt": today.isoformat() + "T00:00:00+00:00",
            "cancelledAt": None, "test": False, "displayFinancialStatus": "PARTIALLY_REFUNDED",
            "currentTotalPriceSet": money_bag(900), "totalReceivedSet": money_bag(1000),
            "totalRefundedSet": money_bag(100), "currentTotalTaxSet": money_bag(50),
            "customerJourneySummary": {"ready": True, "customerOrderIndex": 1, "lastVisit": {
                "utmParameters": {"source": "meta", "medium": "paid_social", "campaign": NAME}
            }},
            "lineItems": {"nodes": [line], "pageInfo": {"hasNextPage": False}},
        }
        mixed = deepcopy(single)
        mixed["lineItems"]["nodes"].append({"currentQuantity": 1, "product": {"id": "gid://shopify/Product/102"}})
        with patch("ads.sources.gql", return_value={"orders": {
                "nodes": [single, mixed], "pageInfo": {"hasNextPage": False}}}):
            result = shopify_window("101", NAME, today, today, timezone.utc)
        self.assertEqual(result["matched_first_time_buyers"], 2)
        self.assertEqual(result["product_cash"]["first_time_buyers"], {
            "received_less_refunds_and_tax_minor": 85000, "covered_orders": 1, "unallocated_orders": 1
        })

    def test_early_performance_actions_wait_but_verified_fault_can_pause(self):
        self.reach_build()
        self.run["meta"]["id"] = "99"
        for action in ("PAUSE", "RECREATE", "TEST", "REFRESH"):
            candidate = deepcopy(self.run)
            decision(candidate, {"decision": action, "target_id": "99", "next_review_on": now().date().isoformat()})
            self.assertEqual(candidate["status"], "monitoring")
            self.assertTrue(candidate["blockers"])
        self.run["request"]["facts"]["operational_issue"] = {
            "kind": "checkout", "verified": True, "target_id": "99", "reference": "Verified defect fixture",
            "observed_at": stamp()
        }
        decision(self.run, {"decision": "PAUSE", "target_id": "99", "next_review_on": now().date().isoformat()})
        self.assertEqual(self.run["step"], "optimization-execution")

    def test_scheduled_refresh_does_not_replace_an_immature_strategy(self):
        self.reach_build()
        self.approve()
        self.execute()
        self.launch()
        original = self.run["records"]["strategy-development"]["data"]
        original["next_review_on"] = (now().date() - timedelta(days=1)).isoformat()
        self.store.save(self.run, "fixture_expired_strategy", {})
        self.run = ready_review(self.store, self.run, force=True)
        while self.run["step"] != "strategy-development":
            self.add()
        self.add({"criteria": original["criteria"], "cycle_action": "recreate",
                  "next_review_on": (now().date() + timedelta(days=7)).isoformat()})
        self.assertEqual(self.run["status"], "monitoring")
        self.assertEqual(self.run["records"]["strategy-development"]["data"]["strategy_id"], original["strategy_id"])
        self.assertTrue(self.run["blockers"])

    def test_newly_blocked_live_run_logs_attention_immediately(self):
        self.reach_build()
        self.approve()
        self.execute()
        self.launch()
        self.run["last_waiting_health_check"] = stamp()
        self.run["waiting_health_scope"] = ["monitoring", "performance-analysis", None]
        self.run.update(status="blocked", blockers=["Review fixture blocked"])
        self.store.save(self.run, "fixture_blocked", {})
        self.run = run_due(self.store, only=self.run["id"], client_factory=lambda _: self.client)[0]
        self.assertTrue(self.run["waiting_health"]["attention"])
        self.assertEqual(self.store.events(self.run["id"])[-1]["kind"], "live_campaign_attention")

    def test_overdue_block_queues_a_pause_without_a_meta_write(self):
        self.reach_build()
        self.approve()
        self.execute()
        self.launch()
        self.run.update(status="blocked", blockers=["Data review blocked"],
                        waiting_health_scope=["blocked", "performance-analysis", None],
                        blocked_since=(now() - timedelta(hours=3)).isoformat())
        self.store.save(self.run, "fixture_overdue", {})
        writes = len(self.client.posts)
        with patch("ads.worker.policy", return_value={"blocked_pause_after_hours": 2}):
            self.run = run_due(self.store, only=self.run["id"], client_factory=lambda _: self.client)[0]
        self.assertEqual(self.run["status"], "awaiting_approval")
        self.assertEqual(self.run["proposal"]["operation"], "pause")
        self.assertEqual(len(self.client.posts), writes)
        self.approve()
        self.execute()
        self.assertEqual(self.run["status"], "stopped")

    def test_external_budget_edit_starts_a_new_review_window(self):
        self.reach_build()
        self.approve()
        self.execute()
        self.launch()
        self.run["campaign_configuration"] = campaign_configuration(self.client, self.run["meta"])
        self.run["last_material_change_at"] = (now() - timedelta(days=20)).isoformat()
        self.run["next_review_at"] = (now() - timedelta(minutes=1)).isoformat()
        self.store.save(self.run, "fixture_configuration", {})
        self.client.remote[self.run["meta"]["id"]]["daily_budget"] += 1000
        review = self.sales_evidence()
        review["configuration"] = campaign_configuration(self.client, self.run["meta"])
        with patch("ads.worker.review_inputs", return_value=review):
            self.run = run_due(self.store, only=self.run["id"], max_steps=1,
                               agent=lambda run, step, context, images, scratch: valid_result(step),
                               client_factory=lambda _: self.client)[0]
        self.assertEqual(self.run["review_evidence"]["configuration_changed"], ["campaign"])
        self.assertEqual(self.run["campaign_configuration"], review["configuration"])
        self.assertTrue(any(e["kind"] == "campaign_configuration_changed" for e in self.store.events(self.run["id"])))

    def test_out_of_scope_country_fails_before_proposal(self):
        self.run["request"]["countries"] = ["US"]
        self.store.save(self.run, "fixture_revised_market", {})
        with self.assertRaisesRegex(Stop, "unapproved market"):
            self.reach_build()
        self.assertEqual(self.client.posts, [])

    def test_asset_mismatch_reworks_concept_and_stops_if_the_same_issue_recurs(self):
        self.run.update(group="create", step="asset-selection")
        self.store.save(self.run, "fixture_create_ready", {})
        failure = output(
            "The available asset shows only one of the two packs.",
            {"retry_step": "creative-concept", "issue": "Only one pack is visible",
             "asset_ids": [IMG["file_id"]], "correction": "Use a supported single-product role angle"},
            refs=[evidence("fixture", IMG["file_id"])], status="rework", blockers=["Missing second pack"],
        )
        self.run = submit(self.store, self.run, failure)
        self.assertEqual(self.run["step"], "creative-concept")
        self.assertEqual(self.run["creative_rework_history"][-1]["asset_ids"], [IMG["file_id"]])
        self.add()
        self.add()
        self.assertEqual(self.run["step"], "asset-selection")
        self.run = submit(self.store, self.run, failure)
        self.assertEqual(self.run["status"], "blocked")
        self.assertEqual(self.client.posts, [])

    def test_due_worker_reviews_and_holds_without_a_second_user_request(self):
        self.reach_build()
        self.approve()
        self.execute()
        self.launch()
        self.run["next_review_at"] = (now() - timedelta(minutes=1)).isoformat()
        self.store.save(self.run, "fixture_review_due", {})
        writes = len(self.client.posts)
        target = self.run["meta"]["id"]

        def agent(run, step, context, images, scratch):
            if step == "optimization-decision":
                return valid_result(step, {"decision": "HOLD", "rationale": "Insufficient mature evidence",
                                           "target_id": target, "next_review_on": now().date().isoformat()})
            return valid_result(step)

        with patch("ads.worker.review_inputs", return_value={"meta": {}, "shopify": {}}):
            self.run = run_due(self.store, only=self.run["id"], agent=agent, client_factory=lambda _: self.client)[0]
        self.assertEqual(self.run["review_number"], 1)
        self.assertEqual(self.run["records"]["optimization-decision"]["data"]["decision"], "HOLD")
        self.assertEqual(self.run["status"], "monitoring")
        self.assertEqual(len(self.client.posts), writes)

    def test_partial_build_can_be_renewed_after_its_approval_expires(self):
        self.reach_build()
        self.approve()
        self.client.timeout = "after"
        self.execute()
        approval = self.run["approval"]
        approval["at"] = (now() - timedelta(days=2)).isoformat()
        approval["signature"] = sign({key: value for key, value in approval.items() if key != "signature"})
        self.store.save(self.run, "fixture_expired_approval", {})
        self.run = reconcile(self.store, self.run["id"], "campaign", self.client)
        self.assertEqual(self.execute()["status"], "execution_blocked")
        self.approve(renew=True)
        self.execute()
        self.assertEqual(self.run["last_receipt"]["operation"], "build")
        self.assertEqual(sum(p[0].endswith("/campaigns") for p in self.client.posts), 1)


if __name__ == "__main__":
    unittest.main()
