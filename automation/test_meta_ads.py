import unittest
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from meta_ads import check_brand_budget, read, read_brand_limits, review, validate
from meta_ads_execution import Meta, apply_budget, build, launch, live_snapshot, pause_ad, previews


EXAMPLES = Path(__file__).resolve().parents[1] / "docs/meta-ads/examples"


class FakeMeta:
    def __init__(self):
        self.budget = 60000
        self.writes = []
        self.objects = {}
        self.edges = {}
        self.fail_adset = False
        self.fail_budget = False
        self.creative_message = "Example copy"
        self.target_name = "agi-example-acquisition"

    def account_details(self, currency):
        return {"account_status": 1, "timezone_name": "UTC"}

    def month_spend(self, as_of, minor_per_unit):
        return 400000

    def budget_target(self, target):
        live = self.objects.get(target["id"], {})
        return {"daily_budget": str(live.get("daily_budget", self.budget)),
                "effective_status": live.get("status", "ACTIVE"),
                "name": live.get("name", self.target_name)}

    def verify_reporting_scope(self, target):
        return Meta.verify_reporting_scope(self, target)

    def verify_campaign_budget(self, target, current, new, cap):
        pass

    def owned(self, object_id, fields):
        if object_id == "500":
            return {"object_story_spec": {"link_data": {"link": "https://example.com/offer",
                                                      "message": self.creative_message}}}
        return self.objects[object_id]

    def request(self, path, fields, *, write=False):
        if not write:
            if path.endswith(("/ads", "/adsets")):
                edge = path.split("/")[-1]
                return {"data": [{"id": key, "status": value["status"], "name": value["name"]}
                                 for key, value in self.objects.items() if self.edges[key] == edge]}
            return {"data": [{"spend": "4000.00", "impressions": "14000"}]}
        self.writes.append((path, fields))
        if path == "200" or path in self.objects:
            if path in self.objects:
                self.objects[path].update(fields)
            if "daily_budget" not in fields:
                return {"success": True}
            self.budget = fields["daily_budget"]
            if self.fail_budget:
                raise TimeoutError("Timed out after applying budget.")
            return {"success": True}
        if path.endswith("/adsets") and self.fail_adset:
            raise TimeoutError("Creation outcome unknown.")
        object_id = str(1000 + len(self.objects))
        self.objects[object_id] = dict(fields)
        self.edges[object_id] = path.split("/")[-1]
        if path.endswith("/ads"):
            self.objects[object_id]["creative"] = {"id": fields["creative"]["creative_id"]}
            self.objects[object_id]["preview_shareable_link"] = "https://example.com/ad-preview"
        return {"id": object_id}


class MetaAdsTests(unittest.TestCase):
    def setUp(self):
        self.plan = read(EXAMPLES / "campaign-plan.json")
        self.snapshot = read(EXAMPLES / "snapshot.json")
        self.client = FakeMeta()
        self.brand_limits = {"monthly_max": 4000000, "daily_min": 10000, "daily_max": 100000}
        budget_patch = patch("meta_ads_execution.read_brand_limits", return_value=self.brand_limits)
        budget_patch.start()
        self.addCleanup(budget_patch.stop)

    def test_pause_ad_writes_only_to_the_approved_ad_and_verifies_status(self):
        self.client.objects = {
            "200": {"name": "agi-example-acquisition", "objective": "OUTCOME_SALES"},
            "300": {"name": "agi-example-broad", "campaign_id": "200"},
            "400": {"name": "agi-example-demo", "campaign_id": "200", "adset_id": "300", "status": "ACTIVE"},
        }
        args = (self.plan, "400", "agi-example-demo", "Test reached its approved stopping condition.")
        preview = pause_ad(*args)
        self.assertEqual(preview["status"], "preview")
        self.assertEqual(self.client.writes, [])
        with TemporaryDirectory() as directory:
            state = Path(directory) / "state.json"
            confirmation = preview["approval_id"]
            self.client.objects["400"]["campaign_id"] = "201"
            self.client.objects["201"] = {"name": "agi-other", "objective": "OUTCOME_SALES"}
            with self.assertRaisesRegex(ValueError, "outside the saved"):
                pause_ad(*args, confirmation, state, self.client)
            self.assertEqual(self.client.writes, [])
            self.client.objects["400"]["campaign_id"] = "200"
            receipt = pause_ad(*args, confirmation, state, self.client)
            self.assertEqual(receipt["status"], "applied")
            self.assertEqual(self.client.objects["400"]["status"], "PAUSED")
            self.assertEqual(pause_ad(*args, confirmation, state, self.client)["status"], "already_applied")
            self.assertEqual(self.client.writes, [("400", {"status": "PAUSED"})])

    def account_budget(self, as_of):
        return {"as_of": as_of, "other_daily_min_minor": 0, "other_daily_max_minor": 0,
                "other_remaining_minor": 0}

    def test_brand_budget_reads_rupees_and_checks_account_projection(self):
        with TemporaryDirectory() as folder:
            brief = Path(folder) / "brand-rules.md"
            brief.write_text("| Monthly budget maximum | ₹15,000 |\n"
                             "| Daily budget minimum | ₹300 |\n"
                             "| Daily budget maximum | ₹1,000.50 |\n", encoding="utf-8")
            limits = read_brand_limits(brief)
        self.assertEqual(limits["daily_max"], 100050)
        as_of = "2026-11-21"
        context = {**self.account_budget(as_of), "spent_minor": 700000,
                   "other_daily_max_minor": 20000, "other_remaining_minor": 100000}
        self.assertEqual(check_brand_budget(limits, context, 60000, as_of)["projected_month_minor"], 1400000)
        with self.assertRaisesRegex(ValueError, "monthly maximum"):
            check_brand_budget(limits, context, 75000, as_of)
        with self.assertRaisesRegex(ValueError, "combined daily budget"):
            check_brand_budget(limits, context, 85000, as_of)

    def test_plan_requires_all_twelve_and_reason_to_defer(self):
        self.assertEqual(validate(self.plan), [])
        self.plan["decisions"]["retargeting"].pop("revisit")
        with self.assertRaisesRegex(ValueError, "revisit retargeting"):
            validate(self.plan)
        del self.plan["decisions"]["retargeting"]
        with self.assertRaisesRegex(ValueError, "12 campaign decisions"):
            validate(self.plan)

    def test_reviewed_status_without_decision_details_cannot_build(self):
        self.plan["decisions"]["audience_research"] = {"status": "decided", "reason": "Reviewed"}
        with self.assertRaisesRegex(ValueError, "audience_research needs a value for buyer"):
            build(self.plan)
        self.assertEqual(self.client.writes, [])

    def test_decision_without_evidence_cannot_increase_budget(self):
        del self.plan["decisions"]["testing"]["evidence"]
        with self.assertRaisesRegex(ValueError, "testing needs a source reference"):
            review(self.plan, self.snapshot)

    def test_build_requires_the_destination_from_the_creative_decision(self):
        self.plan["build"]["destination"] = "https://example.com/different"
        with self.assertRaisesRegex(ValueError, "destination differs from the creative decision"):
            build(self.plan)

    def test_build_requires_agi_names_at_each_level(self):
        spec = self.plan["build"]
        for level, entity in (("Campaign", spec["campaign"]),
                              ("Ad set", spec["ad_sets"][0]["settings"]),
                              ("Ad", spec["ad_sets"][0]["ads"][0])):
            with self.subTest(level=level):
                original = entity["name"]
                entity["name"] = "old-name"
                with self.assertRaisesRegex(ValueError, f"{level} name must start with agi-"):
                    build(self.plan)
                entity["name"] = original

    def test_build_rejects_a_legacy_custom_audience_before_writing(self):
        self.plan["build"]["ad_sets"][0]["settings"]["targeting"]["flexible_spec"] = [
            {"custom_audiences": [{"id": "777"}]}
        ]
        self.client.objects["777"] = {"name": "old-audience"}
        preview = build(self.plan)
        with TemporaryDirectory() as folder, self.assertRaisesRegex(ValueError, "Audience name must start with agi-"):
            build(self.plan, preview["approval_id"], Path(folder) / "state.json", self.client)
        self.assertEqual(self.client.writes, [])

    def test_review_rejects_legacy_campaigns_and_mixed_campaigns(self):
        self.snapshot["target_name"] = self.client.target_name = "legacy-campaign"
        with self.assertRaisesRegex(ValueError, "Review target name must start with agi-"):
            review(self.plan, self.snapshot)
        with self.assertRaisesRegex(ValueError, "Meta target name must start with agi-"):
            live_snapshot(self.plan, {}, self.client)
        self.client.target_name = "agi-active"
        self.client.objects["777"] = {"name": "legacy-ad", "status": "PAUSED"}
        self.client.edges["777"] = "ads"
        with self.assertRaisesRegex(ValueError, "Meta reporting entity name must start with agi-"):
            live_snapshot(self.plan, {}, self.client)

    def test_ad_set_budget_sharing_is_included_in_paused_preview(self):
        spec = self.plan["build"]
        spec["ad_sets"][0]["settings"]["daily_budget"] = spec["campaign"].pop("daily_budget")
        for fields in ({}, {"is_adset_budget_sharing_enabled": True}):
            with self.subTest(fields=fields):
                spec["campaign"].update(fields)
                payload = build(self.plan)["operations"][0][2]
                self.assertIs(payload["is_adset_budget_sharing_enabled"], bool(fields))
                self.assertEqual(payload["status"], "PAUSED")
        spec["campaign"]["is_adset_budget_sharing_enabled"] = "false"
        with self.assertRaisesRegex(ValueError, "sharing must be true or false"):
            build(self.plan)

    def test_missing_business_results_cannot_scale(self):
        self.snapshot["current"]["results"] = None
        result = review(self.plan, self.snapshot)
        self.assertEqual(result["decision"], "investigate")
        self.assertNotIn("proposal", result)

    def test_unmatched_campaign_basis_cannot_scale(self):
        for field, wrong in (("campaign_key", "store-wide"), ("attribution_model", "first click"),
                             ("result_definition", "All store orders"), ("time_zone", "Asia/Kolkata")):
            with self.subTest(field=field):
                self.snapshot["result_basis"] = {**self.plan["review"]["result_basis"], field: wrong}
                result = review(self.plan, self.snapshot)
                self.assertEqual(result["decision"], "investigate")
                self.assertNotIn("proposal", result)

    def test_zero_campaign_spend_cannot_scale(self):
        self.snapshot["current"]["spend_minor"] = 0
        self.assertEqual(review(self.plan, self.snapshot)["decision"], "investigate")

    def test_result_count_alone_cannot_scale(self):
        self.plan["review"].update(metric="result_count", target=10, reversal_target=8)
        self.assertEqual(review(self.plan, self.snapshot)["decision"], "hold")

    def test_pixel_build_requires_verified_domain_and_attribution_settings(self):
        wrong_domain = "wrong.example.net"
        self.plan["build"]["conversion_domain"] = wrong_domain
        with self.assertRaisesRegex(ValueError, "match the destination"):
            build(self.plan)
        self.plan["build"]["conversion_domain"] = "example.com"
        self.plan["build"]["ad_sets"][0]["settings"].pop("attribution_spec")
        with self.assertRaisesRegex(ValueError, "attribution specification"):
            build(self.plan)
        self.assertEqual(self.client.writes, [])

    def test_zero_results_are_known_but_insufficient(self):
        self.snapshot["current"]["results"] = 0
        self.assertEqual(review(self.plan, self.snapshot)["decision"], "hold")

    def test_low_volume_at_planned_spend_goes_to_investigation(self):
        self.snapshot["current"].update(results=0, spend_minor=500000)
        result = review(self.plan, self.snapshot)
        self.assertEqual(result["decision"], "investigate")
        self.assertNotIn("proposal", result)

    def test_reporting_client_refuses_writes_before_network_access(self):
        self.client.write = False
        with self.assertRaisesRegex(ValueError, "Reporting client cannot write"):
            Meta.request(self.client, "200", {"daily_budget": 70000}, write=True)

    def test_reversal_requires_a_full_post_change_period(self):
        self.snapshot["current"]["spend_minor"] = 900000
        self.snapshot["last_budget_change"] = {
            "action": "scale", "applied_on": "2026-11-07",
            "from_daily_minor": 50000, "to_daily_minor": 60000,
        }
        self.assertEqual(review(self.plan, self.snapshot)["decision"], "hold")
        self.snapshot["last_budget_change"]["applied_on"] = "2026-11-06"
        result = review(self.plan, self.snapshot)
        self.assertEqual(result["decision"], "propose_reverse")
        self.assertEqual(result["proposal"]["to_daily_minor"], 50000)

    def test_low_order_volume_after_scaling_flags_reversal_for_review(self):
        self.snapshot["last_budget_change"] = {
            "action": "scale", "applied_on": "2026-11-06",
            "from_daily_minor": 50000, "to_daily_minor": 60000,
        }
        for orders, spend in ((0, 70000), (2, 200000)):
            with self.subTest(orders=orders):
                self.snapshot["current"].update(results=orders, spend_minor=spend)
                result = review(self.plan, self.snapshot)
                self.assertEqual(result["decision"], "investigate")
                self.assertIn("possible reversal", result["reason"])
                self.assertNotIn("proposal", result)

        self.snapshot["current"].update(results=2, spend_minor=80000)
        self.assertEqual(review(self.plan, self.snapshot)["decision"], "hold")

    def test_mismatched_period_is_rejected(self):
        self.snapshot["current"]["end"] = "2026-11-15"
        with self.assertRaisesRegex(ValueError, "Periods must be complete"):
            review(self.plan, self.snapshot)

    def test_graph_read_without_business_evidence_does_not_fabricate_results(self):
        snapshot = live_snapshot(self.plan, {}, self.client)
        self.assertEqual(snapshot["current"]["spend_minor"], 400000)
        self.assertIsNone(snapshot["current"]["results"])
        result = review(self.plan, snapshot)
        self.assertEqual(result["decision"], "investigate")
        self.assertIn("business outcome", result["reason"])
        self.assertEqual(result["periods"]["current"]["spend_minor"], 400000)
        self.assertNotIn("proposal", result)
        self.assertEqual(self.client.writes, [])

    def test_stale_evidence_preserves_spend_and_blocks_budget_proposal(self):
        today = date.fromisoformat(live_snapshot(self.plan, {}, self.client)["as_of"])
        stale = {
            **self.snapshot,
            "source": self.snapshot["evidence_source"],
            "as_of": (today - timedelta(days=1)).isoformat(),
        }
        fresh = live_snapshot(self.plan, stale, self.client)
        result = review(self.plan, fresh)
        self.assertEqual(result["decision"], "investigate")
        self.assertIn(f"Supply evidence for {today}", result["reason"])
        self.assertEqual(result["periods"]["current"]["spend_minor"], 400000)
        self.assertIsNone(result["periods"]["current"]["results"])
        self.assertNotIn("proposal", result)

        stale["account_id"] = "999"
        with self.assertRaisesRegex(ValueError, "different account_id"):
            live_snapshot(self.plan, stale, self.client)

    def budget_proposal_today(self):
        fresh = live_snapshot(self.plan, {}, self.client)
        self.snapshot["as_of"] = fresh["as_of"]
        self.snapshot["account_budget"] = self.account_budget(fresh["as_of"])
        for name in ("current", "previous"):
            for field in ("start", "end"):
                self.snapshot[name][field] = fresh[name][field]
        return review(self.plan, self.snapshot)["proposal"]

    def test_confirmed_increase_checks_whole_account_before_writing(self):
        self.brand_limits["daily_max"] = 80000
        self.budget_proposal_today()
        self.snapshot["account_budget"]["other_daily_max_minor"] = 15000
        proposal = review(self.plan, self.snapshot)["proposal"]
        with TemporaryDirectory() as folder, self.assertRaisesRegex(ValueError, "combined daily budget"):
            apply_budget(self.plan, self.snapshot, proposal, proposal["approval_id"],
                         Path(folder) / "state.json", self.client)
        self.assertEqual(self.client.writes, [])

    def test_preview_tampering_and_stale_current_budget(self):
        proposal = self.budget_proposal_today()
        self.assertEqual(apply_budget(self.plan, self.snapshot, proposal)["status"], "preview")
        tampered = {**proposal, "to_daily_minor": 100000}
        with self.assertRaisesRegex(ValueError, "does not match"):
            apply_budget(self.plan, self.snapshot, tampered)
        self.client.budget = 65000
        with TemporaryDirectory() as folder, self.assertRaisesRegex(ValueError, "old budget changed"):
            apply_budget(self.plan, self.snapshot, proposal, proposal["approval_id"],
                         Path(folder) / "state.json", self.client)
        self.assertEqual(self.client.writes, [])

    def test_budget_timeout_is_reconciled_without_a_second_write(self):
        proposal = self.budget_proposal_today()
        self.client.fail_budget = True
        with TemporaryDirectory() as folder:
            state = Path(folder) / "state.json"
            arguments = (self.plan, self.snapshot, proposal, proposal["approval_id"], state, self.client)
            with self.assertRaises(TimeoutError):
                apply_budget(*arguments)
            self.assertEqual(apply_budget(*arguments)["status"], "applied")
            self.assertEqual(apply_budget(*arguments)["status"], "already_applied")
        self.assertEqual(len(self.client.writes), 1)

    def test_second_increase_needs_latest_receipt_and_cooldown(self):
        proposal = self.budget_proposal_today()
        with TemporaryDirectory() as folder:
            state = Path(folder) / "state.json"
            receipt = apply_budget(self.plan, self.snapshot, proposal, proposal["approval_id"], state, self.client)
            self.snapshot["daily_budget_minor"] = receipt["to_daily_minor"]
            next_proposal = review(self.plan, self.snapshot)["proposal"]
            with self.assertRaisesRegex(ValueError, "latest applied budget receipt"):
                apply_budget(self.plan, self.snapshot, next_proposal, next_proposal["approval_id"], state, self.client)
            self.snapshot["last_budget_change"] = receipt
            self.assertEqual(review(self.plan, self.snapshot)["decision"], "hold")
        self.assertEqual(len(self.client.writes), 1)

    def test_paused_build_records_objects_and_refuses_ambiguous_retry(self):
        preview = build(self.plan)
        self.assertTrue(all(fields["status"] == "PAUSED" for _, _, fields in preview["operations"]))
        with TemporaryDirectory() as folder:
            state = Path(folder) / "uncertain.json"
            args = (self.plan, preview["approval_id"], state, self.client)
            self.client.fail_adset = True
            with self.assertRaises(TimeoutError):
                build(*args)
            with self.assertRaisesRegex(ValueError, "unconfirmed"):
                build(*args)
            self.assertEqual(len(self.client.writes), 2)
            record = read(state)[preview["approval_id"]]
            self.assertEqual(record["campaign"]["status"], "created")
            self.assertEqual(record["ad_set_0"]["status"], "pending")

    def test_full_mock_lifecycle_build_review_scale_and_verify(self):
        with TemporaryDirectory() as folder:
            state = Path(folder) / "state.json"
            approval = build(self.plan)["approval_id"]
            receipt = build(self.plan, approval, state, self.client)
            self.assertEqual(len(receipt["objects"]), 3)
            self.assertEqual(build(self.plan, approval, state, self.client), receipt)
            self.assertEqual(len(self.client.writes), 3)
            rendered = previews(self.plan, read(state), self.client)
            qa = {"build_id": rendered["build_id"], "object_ids": rendered["object_ids"],
                  "creative_versions": rendered["creative_versions"],
                  "passed": True, "placement_previews": "Reviewed the preview links.",
                  "destination": "Verified the offer link.", "tracking": "Verified the purchase event.",
                  "account_budget": self.account_budget(live_snapshot(self.plan, {}, self.client)["as_of"])}
            with self.assertRaisesRegex(ValueError, "each exact creative ID"):
                launch(self.plan, qa, state)
            qa["skincare"] = {"500": {
                "passed": True, "product_accuracy": "Checked the actual label and product pack.",
                "claims": "Checked the claim evidence and the destination copy.",
                "imagery": "Reviewed the actual placement media.",
                "rights_and_disclosures": "Brand-owned media with no endorsement.",
            }}
            with self.assertRaisesRegex(ValueError, "evidence for creative 500"):
                launch(self.plan, {**qa, "skincare": {"500": {**qa["skincare"]["500"], "claims": ""}}}, state)
            self.assertEqual(len(self.client.writes), 3)
            proposed = launch(self.plan, qa, state)
            with self.assertRaisesRegex(ValueError, "exact paused build"):
                launch(self.plan, {**qa, "object_ids": {}}, state)
            self.client.creative_message = "Changed after QA"
            with self.assertRaisesRegex(ValueError, "creative changed after review"):
                launch(self.plan, qa, state, proposed["approval_id"], self.client)
            self.assertEqual(len(self.client.writes), 3)
            self.client.creative_message = "Example copy"
            self.brand_limits["monthly_max"] = 400000
            with self.assertRaisesRegex(ValueError, "monthly maximum"):
                launch(self.plan, qa, state, proposed["approval_id"], self.client)
            self.assertEqual(len(self.client.writes), 3)
            self.brand_limits["monthly_max"] = 4000000
            launched = launch(self.plan, qa, state, proposed["approval_id"], self.client)
            self.assertEqual(launched["status"], "activated")
            self.assertEqual(self.client.writes[-1], (launched["campaign_id"], {"status": "ACTIVE"}))
            self.assertEqual(launch(self.plan, qa, state, proposed["approval_id"], self.client), launched)
            self.assertEqual(len(self.client.writes), 6)
            self.plan["target"]["id"] = launched["campaign_id"]
            self.snapshot["target"] = dict(self.plan["target"])
            proposal = self.budget_proposal_today()
            self.assertEqual(proposal["to_daily_minor"], 70000)
            result = apply_budget(self.plan, self.snapshot, proposal, proposal["approval_id"], state, self.client)
            self.assertEqual(result["status"], "applied")
            self.assertEqual(self.client.budget, 70000)

    def test_build_rejects_over_budget_before_any_api_access(self):
        self.plan["build"]["campaign"]["daily_budget"] = 100000
        with self.assertRaisesRegex(ValueError, "exceeds"):
            build(self.plan)
        self.assertEqual(self.client.writes, [])

    def test_sibling_ad_set_budgets_cannot_bypass_the_campaign_cap(self):
        self.client.owned = lambda object_id, fields: {}
        self.client.request = lambda path, fields: {"data": [
            {"id": "200", "status": "ACTIVE", "daily_budget": "60000"},
            {"id": "201", "status": "PAUSED", "daily_budget": "20000"},
        ]}
        with self.assertRaisesRegex(ValueError, "Combined ad set budgets"):
            Meta.verify_campaign_budget(self.client, {"type": "ad_set", "id": "200"},
                                        {"campaign_id": "1000"}, 70000, 80000)


if __name__ == "__main__":
    unittest.main()
