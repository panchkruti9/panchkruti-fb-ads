"""Business decisions, standing authority and additional recipes with isolated provider fixtures."""
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
import json
import unittest
from unittest.mock import patch

import test_lifecycle as fixtures
from test_lifecycle import IMG, NAME, valid_result
from meta_ads.assessment import assess, business_summary, capture_learning_baseline, learning_budget, review_timing
from meta_ads.authority import owner_required, grant
from meta_ads.execution import approve_creative, verify_creative_approvals, make_proposal
from meta_ads.meta import Stop, configured
from meta_ads.plans import targeting
from meta_ads.recipes import audience_recipe, carousel_cards, verify_catalogue
from meta_ads.report import describe, render
from meta_ads.state import now, stamp
from meta_ads.workflow import decision, prepare, ready_review, schedule, scale_proof, validate_strategy


class ManagementTest(unittest.TestCase):
    setUp = fixtures.LifecycleTest.setUp
    add = fixtures.LifecycleTest.add
    reach_build = fixtures.LifecycleTest.reach_build
    mock_upload = fixtures.LifecycleTest.mock_upload
    approve = fixtures.LifecycleTest.approve
    execute = fixtures.LifecycleTest.execute
    launch = fixtures.LifecycleTest.launch
    sales_evidence = fixtures.LifecycleTest.sales_evidence
    realized_economics = fixtures.LifecycleTest.realized_economics

    def evidence_run(self):
        self.reach_build()
        self.run["meta"].update(id="99", name=NAME)
        self.run["last_material_change_at"] = (now() - timedelta(days=20)).isoformat()
        self.run["review_evidence"] = self.sales_evidence()
        return self.run

    def attach_brand(self):
        brand = json.loads((Path(__file__).resolve().parents[1] / "config/examples/brand-profile.json").read_text())
        brand.update(account_id="99", page_id="11", pixel_id="12", instagram_id="13")
        brand["website"] = "https://shop.test-example.com"
        self.run["request"]["landing_page"] = "https://shop.test-example.com/products/duo"
        brand["policy"].update(maximum_daily_minor=150000, maximum_monthly_minor=3000000,
                               operators=["fixture operator"], owners=["fixture owner"])
        self.run["request"]["brand"] = brand
        return brand

    def test_zero_orders_require_actual_exposure_and_matching_check(self):
        run = self.evidence_run()
        criteria = run["records"]["strategy-development"]["data"]["criteria"]
        criteria["maximum_cpa_minor"] = None
        shop = run["review_evidence"]["shopify"]["current"]
        shop.update(matched_orders=0, paid_product_orders=0)
        self.assertEqual(assess(run)["state"], "underexposed")
        criteria["learning_spend_minor"] = 30000
        self.assertTrue(assess(run)["decision_ready"])
        shop.update(paid_product_orders=2, unmatched_orders=2)
        self.assertEqual(assess(run)["state"], "inconclusive")
        self.assertFalse(assess(run)["decision_ready"])

    def test_first_time_buyer_unknown_is_not_zero_demand(self):
        run = self.evidence_run()
        run["request"]["success_metric"] = "first_time_buyers"
        run["review_evidence"]["shopify"]["current"].update(matched_first_time_buyers=0, paid_product_orders=4)
        self.assertFalse(assess(run)["decision_ready"])

    def test_contribution_uses_verified_costs_and_matching_basis(self):
        run = self.evidence_run()
        self.assertIsNone(business_summary(run)["contribution_after_ads_minor"])
        run["request"]["facts"]["economics"] = self.realized_economics()
        self.assertEqual(business_summary(run)["contribution_after_ads_minor"], 18000)
        run["request"]["facts"]["economics"]["windows"][0]["fees_minor"] = None
        self.assertIsNone(business_summary(run)["contribution_after_ads_minor"])

    def test_planned_challenger_does_not_declare_control_a_loser(self):
        run = self.evidence_run()
        run.pop("review_evidence")
        decision(run, {"decision": "TEST", "target_id": "99", "test_kind": "planned-challenger",
                       "exposure_plan": {"question": "Does routine demonstration answer the objection?", "comparison": "Keep offer and destination stable; record actual exposure."},
                       "next_review_on": now().date().isoformat()})
        self.assertEqual(run["step"], "campaign-strategy")
        self.assertEqual(run["create_mode"], "test")

    def test_schedule_keeps_anchor_after_a_late_check(self):
        self.reach_build()
        checked = now()
        self.run["next_review_at"] = (checked - timedelta(hours=25)).isoformat()
        with patch("meta_ads.workflow.now", return_value=checked):
            schedule(self.run)
        from meta_ads.state import parse_time
        self.assertEqual(parse_time(self.run["next_review_at"]), (checked + timedelta(hours=23)).replace(microsecond=0))

    def test_review_date_alone_preserves_strategy_and_research(self):
        self.reach_build(); self.approve(); self.execute(); self.launch()
        previous = deepcopy(self.run["records"]["strategy-development"])
        self.run["records"]["strategy-development"]["data"]["next_review_on"] = (now().date()-timedelta(days=1)).isoformat()
        product = deepcopy(self.run["records"]["product-research"])
        ready_review(self.store, self.run, force=True)
        self.assertEqual(self.run["step"], "performance-analysis")
        self.assertEqual(self.run["records"]["product-research"], product)
        self.assertEqual(self.run["strategy_version"], previous["data"]["version"])
        self.assertTrue(self.run["strategy_review_due"])

    def test_standing_authority_is_not_a_policy_ceiling(self):
        self.reach_build()
        brand = self.attach_brand()
        brand["policy"]["management_authority"] = {"daily_minor": 30000, "monthly_minor": 3000000,
                                                   "reference": "Owner instruction", "approved_at": stamp()}
        proposal = deepcopy(self.run["proposal"])
        self.assertFalse(owner_required(self.run, proposal))
        proposal["operation"] = "activate"
        self.assertFalse(owner_required(self.run, proposal))
        proposal["impact"]["daily_minor"] = 40000
        self.assertTrue(owner_required(self.run, proposal))
        proposal["operation"] = "budget"
        self.assertTrue(owner_required(self.run, proposal))

    def test_prepare_signs_routine_management_without_owner_question(self):
        self.reach_build()
        brand = self.attach_brand()
        brand["policy"]["management_authority"] = {"daily_minor": 30000, "monthly_minor": 3000000,
                                                   "reference": "Owner instruction", "approved_at": stamp()}
        self.run.update(proposal=None, status="ready")
        self.store.save(self.run, "fixture_authority", {})
        self.run = prepare(self.store, self.run, self.client)
        self.assertEqual(self.run["status"], "approved")
        self.assertIsNone(self.run["approval"]["owner"])
        self.assertIsNone(describe(self.run)["question"])

    def test_generated_creative_approval_is_bound_to_revision_bytes(self):
        self.reach_build(); self.run.update(proposal=None, status="ready")
        self.run["records"]["asset-selection"]["data"]["assets"] = deepcopy(self.run["records"]["asset-selection"]["data"]["assets"])
        self.run["records"]["asset-selection"]["data"]["assets"][0]["origin"] = "agent"
        self.store.save(self.run, "fixture_generated", {})
        asset = {**IMG, "md5": "a"*32}
        with self.assertRaises(Stop): verify_creative_approvals(self.run, {IMG["file_id"]: asset})
        self.run = approve_creative(self.store, self.run["id"], file_id=asset["file_id"], revision=asset["revision"],
                                    md5=asset["md5"], owner="fixture owner", reference="Approved the displayed preview")
        verify_creative_approvals(self.run, {IMG["file_id"]: asset})
        with self.assertRaises(Stop): verify_creative_approvals(self.run, {IMG["file_id"]: {**asset, "revision": "2"}})

    def test_allocation_prepares_decreases_first_and_cannot_increase_total(self):
        self.evidence_run()
        self.client.remote["99"] = {"id": "99", "name": NAME, "edge": "campaigns", "objective": "OUTCOME_SALES", "configured_status": "ACTIVE"}
        for oid, amount in (("51", 20000), ("52", 10000)):
            self.client.remote[oid] = {"id": oid, "name": NAME+"-"+oid, "campaign_id": "99", "edge": "adsets", "configured_status": "ACTIVE", "daily_budget": amount}
        data = {"decision": "ALLOCATE", "target_id": "99", "rationale": "Rebalance within unchanged total.",
                "changes": [{"target_id": "52", "from_daily_minor": 10000, "to_daily_minor": 15000},
                            {"target_id": "51", "from_daily_minor": 20000, "to_daily_minor": 15000}]}
        self.run["records"]["optimization-decision"] = {"data": data}
        self.run["step"] = "optimization-execution"
        p = make_proposal(self.run, self.client)
        self.assertEqual([x["id"] for x in p["action"]["changes"]], ["51", "52"])
        data["changes"][0]["to_daily_minor"] += 100
        with self.assertRaises(Stop): make_proposal(self.run, self.client)

    def test_ordered_carousel_requires_unchanged_same_stage_cards(self):
        assets = {IMG["file_id"]: IMG, "secondfile123": {**IMG, "file_id": "secondfile123"}}
        ad = {"stage": "discovery", "destination": "https://shop.test-example.com/products/duo", "cards": [
            {"asset_id": key, "headline": "Show the routine", "description": "", "destination": "https://shop.test-example.com/products/duo"} for key in assets]}
        self.assertEqual(len(carousel_cards(ad, assets, assets)), 2)
        changed = deepcopy(assets); changed["secondfile123"]["revision"] = "2"
        with self.assertRaises(Stop): carousel_cards(ad, assets, changed)

    def test_website_audience_is_product_scoped_without_customer_upload(self):
        self.run["request"]["landing_page"] = "https://shop.test-example.com/products/duo"
        self.run["records"]["optimization-decision"] = {"data": {"rationale": "Answer an objection for recent product visitors.",
            "audience": {"name": NAME+"-visitors-14d", "event": "ViewContent", "retention_days": 14, "product_url": self.run["request"]["landing_page"]}}}
        self.client.remote["12"] = {"id": "12"}
        recipe = audience_recipe(self.run, self.client)
        self.assertEqual(recipe["subtype"], "WEBSITE")
        self.assertEqual(recipe["rule"]["inclusions"]["rules"][0]["retention_seconds"], 14*86400)
        self.assertNotIn("users", recipe)

    def test_single_scaling_window_requires_more_orders_and_repeatability(self):
        run = self.evidence_run()
        run["request"]["facts"]["economics"] = self.realized_economics()
        criteria = run["records"]["strategy-development"]["data"]["criteria"]
        criteria.update(scale_windows=1, repeatability_reference="Dated daily observations in the saved report")
        self.assertFalse(scale_proof(run))
        run["review_evidence"]["shopify"]["current"]["matched_orders"] = 6
        run["request"]["facts"]["economics"]["windows"][0]["verified_product_net_receipts_minor"] = 65000
        self.assertTrue(scale_proof(run))

    def test_human_log_exposes_business_reason_and_next_condition(self):
        self.evidence_run()
        text = render(self.store, self.run)
        self.assertIn("Purchases and current decision", text)
        self.assertIn("Next decision condition", text)
        self.assertIn("Matching coverage", text)

    def test_carousel_build_and_readback_use_all_ordered_assets(self):
        self.reach_build()
        brand = self.attach_brand()
        brand["policy"]["formats"].append("carousel")
        records = self.run["records"]
        plan = records["creative-validation"]["data"]["plan"]
        ad = plan["adsets"][0]["ads"][0]
        previous_name = ad["name"]
        ad["name"] = previous_name.replace("-static-", "-carousel-")
        ad["format"] = "carousel"
        ad["url_tags"] = ad["url_tags"].replace(previous_name, ad["name"])
        second = {**IMG, "file_id": "secondfile123"}
        self.inventory[second["file_id"]] = second
        records["asset-selection"]["data"]["assets"].append(second)
        ad["cards"] = [{"asset_id": item["file_id"], "headline": "A different product detail", "description": "", "destination": ad["destination"]} for item in (IMG, second)]
        variant = records["ad-copywriting"]["data"]["variants"][0]
        variant["name"] = ad["name"]
        qa = records["creative-validation"]["data"]["ads"][0]
        qa.update(name=ad["name"], approved_ad=deepcopy(ad))
        self.run.update(proposal=None, status="ready")
        self.store.save(self.run, "fixture_carousel", {})
        self.run = prepare(self.store, self.run, self.client)
        self.approve(); self.execute()
        self.assertEqual(self.run["status"], "ready")
        creative = next(row for row in self.client.remote.values() if row.get("edge") == "adcreatives")
        cards = creative["object_story_spec"]["link_data"]["child_attachments"]
        self.assertEqual(len(cards), 2)
        self.assertFalse(creative["object_story_spec"]["link_data"]["multi_share_optimized"])

    def test_worker_receives_selected_skill_knowledge_in_prompt(self):
        from meta_ads.worker import codex_result
        self.reach_build()
        captured = {}
        step = "creative-analysis"
        def fake_process(command, **kwargs):
            captured["prompt"] = kwargs["input"]
            result = valid_result(step)
            result["data_json"] = json.dumps(result.pop("data"))
            Path(command[command.index("--output-last-message")+1]).write_text(json.dumps(result))
            return type("Result", (), {"returncode": 0})()
        with patch("meta_ads.worker.codex_command", return_value=["fixture-codex"]), patch("meta_ads.worker.subprocess.run", side_effect=fake_process):
            codex_result(self.run, step, {}, [], Path(self.scratch.name))
        self.assertIn("Selected skill knowledge (decision-guide.md)", captured["prompt"])
        self.assertIn("low-spend ad is underexposed", captured["prompt"])
        self.assertIn("The strategy contract", captured["prompt"])

    def test_clean_short_window_can_be_useful_before_target_lookback(self):
        from meta_ads.sources import windows
        run = self.evidence_run()
        run["last_material_change_at"] = (now()-timedelta(days=4)).isoformat()
        _, periods = windows(run, self.client.details())
        start, end = periods["current"]
        self.assertLess((end-start).days+1, 5)
        for source in ("meta", "shopify"):
            run["review_evidence"][source]["current"].update(start=start.isoformat(), end=end.isoformat())
        self.assertTrue(assess(run)["decision_ready"])

    def test_guard_uses_signed_pause_only_at_verified_monthly_ceiling(self):
        from meta_ads.guard import check
        run = self.evidence_run()
        brand = self.attach_brand()
        brand["policy"]["management_authority"] = {"daily_minor": 30000, "monthly_minor": 50000,
                                                   "reference": "Actual owner instruction", "approved_at": stamp()}
        self.client.remote["99"] = {"id": "99", "name": NAME, "edge": "campaigns", "objective": "OUTCOME_SALES",
                                    "configured_status": "ACTIVE", "effective_status": "ACTIVE", "daily_budget": 30000}
        run.update(status="monitoring", proposal=None)
        self.store.save(run, "fixture_guard", {})
        self.client.spend_minor = 49999
        run = check(self.store, run, lambda _account: self.client)
        self.assertFalse(self.client.posts)
        self.client.spend_minor = 50000
        run = check(self.store, run, lambda _account: self.client)
        self.assertEqual(run["status"], "monitoring")
        self.assertIn("budget_pause", run)
        self.assertEqual(self.client.posts, [("99", {"status": "PAUSED"})])
        check(self.store, run, lambda _account: self.client)
        self.assertEqual(len(self.client.posts), 1)

    def test_transfer_executes_decrease_before_increase_with_readback(self):
        from meta_ads.execution import authorize
        run = self.evidence_run()
        self.client.remote["99"] = {"id": "99", "name": NAME, "edge": "campaigns", "objective": "OUTCOME_SALES", "configured_status": "ACTIVE"}
        for oid, amount in (("51", 20000), ("52", 10000)):
            self.client.remote[oid] = {"id": oid, "name": NAME+"-"+oid, "campaign_id": "99", "edge": "adsets", "configured_status": "ACTIVE", "daily_budget": amount}
        run["records"]["optimization-decision"] = {"data": {"decision": "ALLOCATE", "target_id": "99", "rationale": "Rebalance without increasing total.",
            "changes": [{"target_id": "52", "from_daily_minor": 10000, "to_daily_minor": 15000}, {"target_id": "51", "from_daily_minor": 20000, "to_daily_minor": 15000}]}}
        run.update(step="optimization-execution", status="ready", proposal=None)
        self.store.save(run, "fixture_transfer", {})
        self.run = prepare(self.store, run, self.client)
        self.approve(); self.execute()
        self.assertEqual([p[0] for p in self.client.posts], ["51", "52"])
        self.assertEqual(self.client.budget()["daily_minor"], 30000)
        self.assertEqual(self.run["last_receipt"]["operation"], "allocation")

    def test_catalogue_rechecks_product_mapping_currency_and_event_source(self):
        plan = {"catalogue": {"catalogue_id": "81", "product_set_id": "82", "retailer_ids": ["variant-101"]},
                "adsets": [{"ads": [{"destination": "https://shop.test-example.com/products/duo"}]}]}
        class Catalogue:
            currency = "INR"
            def request(self, path, params): return {"id": "82", "product_catalog": {"id": "81"}}
            def pages(self, path, fields):
                return [{"id": "12"}] if path.endswith("external_event_sources") else [{"retailer_id": "variant-101", "url": "https://shop.test-example.com/products/duo", "currency": self.currency, "availability": "in stock"}]
        client = Catalogue()
        verify_catalogue(plan, client)
        client.currency = "USD"
        with self.assertRaises(Stop): verify_catalogue(plan, client)

    def test_new_strategy_handoff_cannot_reference_a_different_strategy(self):
        from meta_ads.workflow import submit
        self.reach_build()
        strategy = self.run["records"]["strategy-development"]["data"]
        strategy["contract_version"] = 2
        self.run.update(step="campaign-strategy", status="ready")
        with self.assertRaises(Stop): submit(self.store, self.run, valid_result("campaign-strategy", {"strategy_id": "another-strategy"}))

    def test_replacement_pauses_old_campaign_before_new_activation(self):
        self.reach_build(); self.approve(); self.execute(); self.launch()
        previous = deepcopy(self.run["meta"])
        replacement = NAME+"-v02"
        for step in ("campaign-strategy", "funnel-planning", "audience-planning", "creative-concept", "ad-copywriting", "asset-selection", "creative-validation"):
            self.run["records"][step] = json.loads(json.dumps(self.run["records"][step]).replace(NAME, replacement))
        self.run.update(create_mode="recreate", planned_name=replacement, step="campaign-build", status="ready", proposal=None)
        self.store.save(self.run, "fixture_replacement", {})
        self.run = prepare(self.store, self.run, self.client)
        self.assertEqual(self.run["proposal"]["impact"]["daily_minor"], 30000)
        self.approve(); self.execute()
        self.assertEqual(self.client.remote[previous["id"]]["configured_status"], "ACTIVE")
        observed = []
        original_request = self.client.request
        def record(path, params, **kwargs):
            value = original_request(path, params, **kwargs)
            if kwargs.get("post"): observed.append(self.client.budget()["daily_minor"])
            return value
        self.client.request = record
        self.launch()
        self.assertEqual(self.client.remote[previous["id"]]["configured_status"], "PAUSED")
        self.assertEqual(max(observed), 30000)
        self.assertNotIn("pending_retirement", self.run)

    def test_standing_routine_authorization_renews_without_new_owner_decision(self):
        from meta_ads.execution import sign
        self.reach_build()
        brand = self.attach_brand()
        brand["policy"]["management_authority"] = {"daily_minor": 30000, "monthly_minor": 3000000,
                                                   "reference": "Actual owner management instruction", "approved_at": stamp()}
        self.run.update(proposal=None, status="ready")
        self.store.save(self.run, "fixture_standing", {})
        self.run = prepare(self.store, self.run, self.client)
        a = {k: v for k, v in self.run["approval"].items() if k != "signature"}
        a["at"] = (now()-timedelta(days=2)).isoformat()
        self.run["approval"] = {**a, "signature": sign(a)}
        self.store.save(self.run, "fixture_expired_routine", {})
        self.execute()
        self.assertEqual(self.run["step"], "activation-check")
        self.assertTrue(any(e["kind"] == "management_authorization_renewed" for e in self.store.events(self.run["id"])))

    def test_grant_keeps_existing_delivery_history_and_rejects_excess(self):
        self.reach_build(); self.approve(); self.execute(); self.launch()
        run = self.run
        self.attach_brand()
        run.update(proposal=None, status="monitoring")
        self.store.save(run, "fixture_grant", {})
        updated = grant(self.store, run["id"], daily_minor=30000, monthly_minor=3000000, reference="Actual owner instruction")
        self.assertEqual(updated["campaign_ledger"], run["campaign_ledger"])
        self.assertEqual(updated["status"], "monitoring")
        self.assertEqual(updated["decision_contract_version"], 2)
        with self.assertRaises(Stop): grant(self.store, run["id"], daily_minor=150001, monthly_minor=3000000, reference="Actual owner instruction")

    def test_new_campaign_budget_adset_addition_keeps_total_funding(self):
        self.reach_build(); self.approve(); self.execute(); self.launch()
        records = self.run["records"]
        plan = records["creative-validation"]["data"]["plan"]
        ad = plan["adsets"][0]["ads"][0]
        oldname = ad["name"]
        ad["name"] = oldname[:-2]+"02"
        ad["url_tags"] = ad["url_tags"].replace(oldname, ad["name"])
        records["ad-copywriting"]["data"]["variants"][0]["name"] = ad["name"]
        records["creative-validation"]["data"]["ads"][0].update(name=ad["name"], approved_ad=deepcopy(ad))
        plan["adsets"][0]["name"] += "-challenger"
        plan["adsets"][0]["existing_adset_id"] = None
        self.run.update(create_mode="test", step="campaign-build", status="ready", proposal=None)
        self.store.save(self.run, "fixture_added_set", {})
        self.run = prepare(self.store, self.run, self.client)
        self.approve(); self.execute(); self.launch()
        self.assertEqual(self.client.budget()["daily_minor"], 30000)
        self.assertEqual(len([r for r in self.client.remote.values() if r.get("edge") == "adsets"]), 2)
        self.assertIn("last_portfolio_change_at", self.run)

    def test_transfer_between_enrolled_campaigns_has_explicit_scope(self):
        run = self.evidence_run()
        for oid, name, amount in (("99", NAME, 20000), ("98", "agi-another-managed-product", 10000)):
            self.client.remote[oid] = {"id": oid, "name": name, "edge": "campaigns", "objective": "OUTCOME_SALES", "configured_status": "ACTIVE", "daily_budget": amount}
        run["step"] = "optimization-execution"
        run["records"]["optimization-decision"] = {"data": {"decision": "ALLOCATE", "rationale": "Reallocate existing account total.",
            "changes": [{"target_id": "99", "from_daily_minor": 20000, "to_daily_minor": 15000},
                        {"target_id": "98", "from_daily_minor": 10000, "to_daily_minor": 15000}]}}
        with self.assertRaises(Stop): make_proposal(run, self.client)
        proposal = make_proposal(run, self.client, managed_scopes=[{"id": "98", "name": "agi-another-managed-product"}])
        self.assertEqual(proposal["action"]["changes"][1]["campaign_id"], "98")

    def test_known_returning_buyers_do_not_hide_zero_acquisition_results(self):
        run = self.evidence_run()
        run["request"]["success_metric"] = "first_time_buyers"
        run["review_evidence"]["shopify"]["current"].update(matched_first_time_buyers=0, paid_product_orders=4,
            matched_returning_buyers=4, matched_buyer_history_unknown=0)
        self.assertTrue(assess(run)["decision_ready"])

    def test_carousel_readback_rejects_reversed_cards(self):
        from meta_ads.execution import read_object
        expected = {"object_story_spec": {"link_data": {"child_attachments": [{"name": "First"}, {"name": "Second"}]}}}
        actual = deepcopy(expected)
        actual["object_story_spec"]["link_data"]["child_attachments"].reverse()
        self.client.remote["77"] = {"id": "77", **actual}
        with self.assertRaises(Stop): read_object(self.client, {"id": "77", "kind": "creative", "settings": expected}, None)

    def test_fresh_monthly_exposure_cannot_exceed_standing_authority(self):
        from meta_ads.execution import Executor
        brand = self.attach_brand()
        brand["policy"]["management_authority"] = {"daily_minor": 30000, "monthly_minor": 60000,
                                                   "reference": "Actual instruction", "approved_at": stamp()}
        self.client.remote["99"] = {"id": "99", "configured_status": "ACTIVE", "daily_budget": 30000}
        executor = Executor.__new__(Executor)
        executor.client, executor.run = self.client, self.run
        executor.proposal = {"impact": {"daily_minor": 30000, "monthly_minor": 300000}}
        with configured(brand), self.assertRaises(Stop): executor.budget()

    def test_resume_approved_campaign_preserves_original_agi_start(self):
        self.reach_build(); self.approve(); self.execute(); self.launch()
        self.attach_brand()
        self.run["request"]["brand"]["policy"]["management_authority"] = {"daily_minor": 30000, "monthly_minor": 3000000,
            "reference": "Actual standing instruction", "approved_at": stamp()}
        original_ledger = deepcopy(self.run["campaign_ledger"])
        target = self.run["meta"]["id"]
        for action in ("PAUSE", "RESUME"):
            self.run["records"]["optimization-decision"] = {"data": {"decision": action, "target_id": target, "rationale": "Verified operational decision within approved funding."}}
            self.run.update(step="optimization-execution", status="ready", proposal=None)
            self.store.save(self.run, "fixture_pause_resume", {})
            with patch("meta_ads.sources.storefront", return_value={"reachable": True}):
                self.run = prepare(self.store, self.run, self.client)
                self.assertEqual(self.run["status"], "approved")
                self.execute()
        self.assertEqual(self.client.remote[target]["configured_status"], "ACTIVE")
        self.assertEqual(self.run["campaign_ledger"], original_ledger)
        self.assertNotIn("management_pause", self.run)

    def test_optional_capability_failure_preserves_normal_sales(self):
        from meta_ads.recipes import inspect_capabilities, capabilities
        self.client.audience_inventory = lambda: (_ for _ in ()).throw(Stop("Optional audience read unavailable"))
        observed = inspect_capabilities(self.store, self.run, self.client)
        self.assertTrue(observed["limitations"])
        self.assertEqual(capabilities(self.run)["website_purchase"]["state"], "available")
        self.assertEqual(self.run["status"], "ready")

    def test_daily_health_check_does_not_skip_for_minor_schedule_drift(self):
        from meta_ads.worker import monitor_waiting
        self.reach_build(); self.approve(); self.execute(); self.launch()
        checked = now().replace(hour=11, minute=15, second=0, microsecond=0)
        previous = (checked-timedelta(hours=23)).isoformat()
        self.run.update(last_waiting_health_check=previous,
            waiting_health_scope=[self.run["status"], self.run["step"], None], waiting_health={"budget": {"timezone": "UTC"}})
        self.store.save(self.run, "fixture_daily_health", {})
        calls = []
        def client(_run): calls.append(True); return self.client
        with patch("meta_ads.worker.now", return_value=checked):
            monitor_waiting(self.store, self.run, client)
        self.assertEqual(len(calls), 1)
        self.assertNotEqual(self.run["last_waiting_health_check"], previous)

    def test_explicit_user_stop_is_not_reversed_by_standing_management(self):
        self.reach_build(); self.approve(); self.execute(); self.launch()
        self.attach_brand()
        self.run["request"]["brand"]["policy"]["management_authority"] = {"daily_minor": 30000, "monthly_minor": 3000000,
            "reference": "Actual instruction", "approved_at": stamp()}
        target = self.run["meta"]["id"]
        self.run["records"]["optimization-decision"] = {"data": {"decision": "PAUSE", "target_id": target,
            "rationale": "User explicitly stopped management.", "stop_management": True}}
        self.run.update(step="optimization-execution", status="ready", proposal=None)
        self.store.save(self.run, "fixture_user_stop", {})
        self.run = prepare(self.store, self.run, self.client)
        self.execute()
        self.assertEqual(self.run["status"], "stopped")
        self.assertIsNone(self.run["next_review_at"])

    def test_first_configuration_read_does_not_invent_a_material_edit(self):
        from meta_ads.worker import run_due
        self.reach_build(); self.approve(); self.execute(); self.launch()
        original = self.run["last_material_change_at"]
        self.run.pop("campaign_configuration", None)
        self.run["next_review_at"] = (now()-timedelta(minutes=1)).isoformat()
        self.store.save(self.run, "fixture_first_baseline", {})
        review = self.sales_evidence()
        review["configuration"] = {"campaign": "verified-campaign", "adsets": "verified-adsets", "ads": "verified-ads"}
        with patch("meta_ads.worker.review_inputs", return_value=review):
            self.run = run_due(self.store, only=self.run["id"], max_steps=1,
                agent=lambda *args: valid_result("performance-analysis"), client_factory=lambda _: self.client)[0]
        self.assertEqual(self.run["last_material_change_at"], original)
        self.assertEqual(self.run["campaign_configuration"], review["configuration"])
        self.assertNotIn("configuration_changed", self.run["review_evidence"])

    def test_first_connected_baseline_preserves_delivery_clock(self):
        from meta_ads.connected import submit_step
        self.reach_build()
        self.attach_brand()
        original = (now()-timedelta(days=3)).isoformat()
        self.run.update(connected=True, status="ready", step="performance-analysis", group="optimize", proposal=None,
                        last_material_change_at=original, live_since=original)
        review = self.sales_evidence()
        review["configuration"] = {"campaign": "c", "adsets": "s", "ads": "a"}
        self.store.save(self.run, "fixture_connected_baseline", {})
        self.run["connected_context"] = {"step": "performance-analysis", "revision": self.run["revision"],
                                         "observed_at": stamp(), "data": {"review_evidence": review}}
        result = submit_step(self.store, self.run, {"revision": self.run["revision"], "result": valid_result("performance-analysis")})
        self.assertEqual(result["last_material_change_at"], original)
        self.assertEqual(result["review_evidence"]["configuration_changed"], [])

    def test_purchase_exclusion_does_not_silently_use_product_page_url(self):
        self.run["request"]["landing_page"] = "https://shop.test-example.com/products/duo"
        self.run["records"]["optimization-decision"] = {"data": {"rationale": "Exclude recent store purchasers for acquisition.",
            "audience": {"name": NAME+"-purchasers-30d", "event": "Purchase", "retention_days": 30,
                         "product_url": self.run["request"]["landing_page"]}}}
        self.client.remote["12"] = {"id": "12"}
        with self.assertRaises(Stop): audience_recipe(self.run, self.client)
        self.run["records"]["optimization-decision"]["data"]["audience"]["scope"] = "all-store"
        recipe = audience_recipe(self.run, self.client)
        self.assertEqual(recipe["audience_scope"], "all-store")
        filters = recipe["rule"]["inclusions"]["rules"][0]["filter"]["filters"]
        self.assertEqual(filters, [{"field": "event", "operator": "eq", "value": "Purchase"}])

    def test_scheduled_update_explains_the_actual_strategy_route(self):
        self.run.update(status="monitoring", strategy_reconsideration={"required": True}, next_review_at=(now()+timedelta(days=1)).isoformat())
        update=describe(self.run)
        self.assertIn("buying strategy", update["next_action"])
        self.assertEqual(update["owner"], "agent")
        self.assertIsNone(update["question"])

    def learning_run(self):
        run = self.evidence_run()
        strategy = run["records"]["strategy-development"]["data"]
        strategy["criteria"].update(learning_spend_minor=60000, maximum_cpa_minor=None)
        run["campaign_ledger"] = {"99": {"campaign_id": "99", "name": NAME,
            "spent_since_start_minor": 10000, "last_observed_at": stamp()}}
        capture_learning_baseline(run, strategy)
        return run

    def test_learning_counter_includes_immature_spend_without_a_purchase_verdict(self):
        run = self.learning_run()
        run["campaign_ledger"]["99"]["spent_since_start_minor"] = 70000
        run["last_material_change_at"] = stamp()
        run["request"]["facts"]["tracking"]["purchase_verified"] = False
        result = assess(run)
        self.assertEqual(result["state"], "maturing")
        self.assertFalse(result["decision_ready"])
        self.assertTrue(result["risk_review_required"])
        self.assertEqual(result["learning_budget"]["spent_minor"], 60000)
        self.assertEqual(result["learning_budget"]["remaining_minor"], 0)
        self.assertIn("allowance now", result["next_condition"])
        self.assertEqual(learning_budget(run)["spent_minor"], 60000)

    def test_learning_bound_allows_risk_pause_but_not_replacement(self):
        run = self.learning_run()
        run["campaign_ledger"]["99"]["spent_since_start_minor"] = 70000
        run.pop("review_evidence")
        data = {"target_id": "99", "next_review_on": now().date().isoformat()}
        decision(run, {**data, "decision": "RECREATE"})
        self.assertEqual(run["status"], "monitoring")
        decision(run, {**data, "decision": "PAUSE"})
        self.assertEqual(run["step"], "optimization-execution")
        self.assertNotIn("planned_name", run)

    def test_bound_review_preempts_cadence_without_resetting_accounting(self):
        run = self.learning_run()
        run["campaign_ledger"]["99"]["spent_since_start_minor"] = 70000
        schedule(run)
        future = run["next_review_at"]
        self.store.save(run, "fixture_learning", {})
        ready_review(self.store, run)
        self.assertEqual(run["step"], "performance-analysis")
        self.assertEqual(run["status"], "ready")
        self.assertEqual(run["next_review_at"], future)
        self.assertTrue(learning_budget(run)["reached"])

    def test_missing_or_revised_learning_counter_is_not_zero(self):
        run = self.learning_run()
        entry = run["campaign_ledger"]["99"]
        entry["spent_since_start_minor"] = 9000  # Below saved baseline.
        self.assertIsNone(learning_budget(run)["spent_minor"])
        entry.update(spent_since_start_minor=90000, accounting_issue="Provider revision needs reconciliation")
        self.assertFalse(learning_budget(run)["reached"])
        entry.pop("accounting_issue")
        run["records"]["strategy-development"]["data"]["learning_baseline"]["campaign_id"] = "98"
        self.assertIsNone(learning_budget(run)["spent_minor"])

    def test_learning_baseline_comes_from_state_not_model_output(self):
        run = self.learning_run()
        strategy = run["records"]["strategy-development"]["data"]
        strategy["learning_baseline"] = {"campaign_id": "99", "spent_since_start_minor": 0}
        capture_learning_baseline(run, strategy)
        self.assertEqual(strategy["learning_baseline"]["spent_since_start_minor"], 10000)
        run["campaign_ledger"].clear()
        capture_learning_baseline(run, strategy)
        self.assertNotIn("learning_baseline", strategy)

    def test_legacy_window_exposure_is_a_scoped_lower_bound(self):
        run = self.learning_run()
        strategy = run["records"]["strategy-development"]["data"]
        strategy.pop("learning_baseline")
        strategy["created_at"] = (now()-timedelta(days=20)).isoformat()
        strategy["criteria"]["learning_spend_minor"] = 30000
        meta = run["review_evidence"]["meta"]["current"]
        meta["rows"]["campaign"][0]["campaign_id"] = "99"
        self.assertTrue(learning_budget(run)["lower_bound"])
        self.assertTrue(learning_budget(run)["reached"])
        meta["rows"]["campaign"][0]["campaign_id"] = "98"
        self.assertFalse(learning_budget(run)["reached"])
        meta["rows"]["campaign"][0]["campaign_id"] = "99"
        strategy["created_at"] = stamp()
        self.assertIsNone(learning_budget(run)["spent_minor"])

    def test_purchase_review_eligibility_uses_local_clean_day_and_lag(self):
        run = self.learning_run()
        run["last_material_change_at"] = "2026-11-21T20:00:00+00:00"  # 22 Nov in India.
        run["review_evidence"]["account_timezone"] = "Asia/Kolkata"
        run["records"]["strategy-development"]["data"]["criteria"]["lag_days"] = 2
        timing = review_timing(run)
        self.assertEqual(timing["first_clean_day"], "2026-11-23")
        self.assertEqual(timing["earliest_purchase_review_at"], "2026-11-26T00:00:00+05:30")
        run["campaign_ledger"]["99"]["first_delivery_on"] = "2026-11-24"
        self.assertEqual(review_timing(run)["first_clean_day"], "2026-11-25")

    def test_logs_show_learning_exposure_and_agent_owned_risk_review(self):
        run = self.learning_run()
        run["campaign_ledger"]["99"].update(spent_since_start_minor=70000, baseline=None,
            launch_verified_at=stamp(), month=now().strftime("%Y-%m"), spent_month_minor=70000)
        run.update(status="monitoring", next_review_at=(now()+timedelta(days=1)).isoformat())
        update = describe(run)
        self.assertEqual(update["when"], "Now")
        self.assertEqual(update["owner"], "agent")
        self.assertIsNone(update["question"])
        log = render(self.store, run)
        self.assertIn("## Bounded learning", log)
        self.assertIn("Allowance reached: agent decision required now", log)
        self.assertIn("Earliest clean purchase review", log)

    def test_launch_anchors_learning_and_additions_do_not_renew_it(self):
        self.reach_build()
        strategy = self.run["records"]["strategy-development"]["data"]
        strategy["criteria"]["learning_spend_minor"] = 60000
        self.run.update(proposal=None, status="ready")
        self.store.save(self.run, "fixture_learning_allowance", {})
        self.run = prepare(self.store, self.run, self.client)
        self.approve(); self.execute(); self.launch()
        baseline = deepcopy(self.run["records"]["strategy-development"]["data"]["learning_baseline"])
        self.assertEqual(baseline["campaign_id"], self.run["meta"]["id"])
        self.assertEqual(baseline["spent_since_start_minor"], 0)
        from meta_ads.ledger import mark_launched
        mark_launched(self.run, {"campaign_id": self.run["meta"]["id"], "launch_verified_at": stamp()})
        self.assertEqual(self.run["records"]["strategy-development"]["data"]["learning_baseline"], baseline)

    def test_risk_pause_executes_through_standing_authority_and_readback(self):
        run = self.learning_run()
        brand = self.attach_brand()
        brand["policy"]["management_authority"] = {"daily_minor": 30000, "monthly_minor": 3000000,
            "reference": "Actual management authority", "approved_at": stamp()}
        run["campaign_ledger"]["99"]["spent_since_start_minor"] = 70000
        run.pop("review_evidence")
        run["request"]["facts"]["tracking"]["purchase_verified"] = False
        self.client.remote["99"] = {"id": "99", "name": NAME, "edge": "campaigns", "objective": "OUTCOME_SALES",
            "configured_status": "ACTIVE", "effective_status": "ACTIVE", "daily_budget": 30000}
        run.update(proposal=None, status="ready", group="optimize", step="optimization-decision")
        decision_data = {"decision": "PAUSE", "target_id": "99", "rationale": "Contain the reached learning allowance; purchase measurement remains inconclusive.",
                         "next_review_on": now().date().isoformat()}
        run["records"]["optimization-decision"] = {"data": decision_data}
        decision(run, decision_data)
        self.store.save(run, "fixture_risk_pause", {})
        self.run = prepare(self.store, run, self.client)
        self.assertEqual(self.run["status"], "approved")
        self.execute()
        self.assertEqual(self.run["status"], "monitoring")
        self.assertIn("management_pause", self.run)
        self.assertEqual(self.run["last_receipt"]["operation"], "pause")
        self.assertEqual(self.client.posts, [("99", {"status": "PAUSED"})])
