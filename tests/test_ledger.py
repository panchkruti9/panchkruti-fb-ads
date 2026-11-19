"""Budget starts at verified AGI launch, independent of prior account spend."""
import unittest
from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch
from meta_ads import ledger
from meta_ads.meta import configured, Stop
from meta_ads.state import stamp,now


class LedgerTest(unittest.TestCase):
    def entry(self):
        today=now().date().isoformat()
        return {"campaign_id":"123","name":"agi-test","baseline":{
            "start_day":today,"timezone":"UTC","month":today[:7],
            "window_spend_minor":5000,"window_impressions":100,"month_spend_minor":20000},
            "launch_verified_at":stamp(),"first_delivery_on":None,
            "spent_since_start_minor":None,"spent_month_minor":None}

    def reading(self,entry,spent=6200):
        baseline=entry["baseline"]
        return {"campaign_id":"123","observed_at":stamp(),"start_day":baseline["start_day"],
            "month":baseline["month"],"window_spend_minor":spent,"month_spend_minor":21200,
            "daily":[{"day":baseline["start_day"],"spend_minor":spent,"impressions":120}]}

    def test_live_spend_reader_never_uses_account_insights_as_campaign_spend(self):
        calls=[];day=now().date().isoformat()
        class Client:
            def scope(self,object_id,kind,name):
                if object_id!="123":raise AssertionError("wrong campaign")
                return {"id":"123"}
            def details(self):return {"timezone_name":"UTC"}
            def pages(self,path,fields,**params):
                calls.append(path)
                if path!="123/insights":raise AssertionError("must not read account spend")
                if params.get("time_increment"):
                    return [{"campaign_id":"123","date_start":day,"date_stop":day,"spend":"62.00","impressions":"120"}]
                return [{"campaign_id":"123","spend":"212.00"}]
        with configured({"policy":{"minor_per_unit":100}}):
            result=ledger.read_spending(Client(),{"id":"123","name":"agi-test"})
        self.assertEqual(result["window_spend_minor"],6200)
        self.assertEqual(result["month_spend_minor"],21200)
        self.assertEqual(calls,["123/insights","123/insights"])

    def test_old_account_spend_does_not_become_agi_spend_before_launch(self):
        run={"request":{"facts":{"spend_control":{"amount_spent":"6610305"}}},"meta":{"id":"123"}}
        result=ledger.summary(run)
        self.assertFalse(result["started"])
        self.assertEqual(result["spent_since_start_minor"],0)
        self.assertIsNone(result["launch_verified_at"])

    def test_same_day_and_prior_month_spend_are_deducted_once(self):
        entry=self.entry();reading=self.reading(entry)
        self.assertTrue(ledger.observe(entry,reading))
        self.assertEqual(entry["spent_since_start_minor"],1200)
        self.assertEqual(entry["spent_month_minor"],1200)
        self.assertEqual(entry["first_delivery_on"],entry["baseline"]["start_day"])
        self.assertFalse(ledger.observe(entry,reading))
        self.assertEqual(entry["spent_since_start_minor"],1200)

    def test_new_month_does_not_deduct_previous_month_baseline(self):
        entry=self.entry();entry["baseline"]["month"]="2025-01"
        reading=self.reading(entry);reading["month"]=now().strftime("%Y-%m");reading["month_spend_minor"]=800
        ledger.observe(entry,reading)
        self.assertEqual(entry["spent_month_minor"],800)
        self.assertEqual(entry["spent_since_start_minor"],1200)

    def test_preexisting_impressions_do_not_fake_first_agi_delivery(self):
        entry=self.entry();reading=self.reading(entry,5000)
        reading["month_spend_minor"]=20000;reading["daily"][0]["impressions"]=100
        ledger.observe(entry,reading)
        self.assertIsNone(entry["first_delivery_on"])
        self.assertEqual(entry["spent_since_start_minor"],0)

    def test_replacement_keeps_previous_campaign_spend_in_run_total(self):
        old=self.entry();old.update(spent_since_start_minor=1200,spent_month_minor=1200,month=now().strftime("%Y-%m"))
        new=deepcopy(old);new.update(campaign_id="456",spent_since_start_minor=300,spent_month_minor=300)
        result=ledger.summary({"campaign_ledger":{"123":old,"456":new},"request":{}})
        self.assertEqual(result["spent_since_start_minor"],1500)
        self.assertEqual(result["spent_month_minor"],1500)

    def test_snapshots_replace_absolute_totals_without_double_counting(self):
        entry=self.entry();day=entry["baseline"]["start_day"]
        run={"request":{"brand":{"policy":{"minor_per_unit":100}}},"campaign_ledger":{"123":entry}}
        snapshot={"observed_at":stamp(),"first_day":day,"account_report":{"account":{"timezone_name":"UTC"}},
            "campaigns":{"123":{"name":"agi-test","daily":{"campaign":[{
              "campaign_id":"123","date_start":day,"date_stop":day,"spend":"62.00","impressions":"120"}]}}}}
        # This test uses a same-day monthly baseline to isolate the launch-day deduction.
        entry["baseline"]["month_spend_minor"]=5000
        self.assertTrue(ledger.apply_snapshot(run,snapshot))
        self.assertEqual(entry["spent_since_start_minor"],1200)
        self.assertFalse(ledger.apply_snapshot(run,snapshot))
        self.assertEqual(entry["spent_since_start_minor"],1200)

    def test_old_live_run_without_baseline_stays_unknown_instead_of_resetting_zero(self):
        result=ledger.summary({"request":{},"live_since":stamp()})
        self.assertTrue(result["legacy_baseline_missing"])
        self.assertIsNone(result["spent_since_start_minor"])

    def test_snapshot_from_before_launch_is_ignored(self):
        entry=self.entry();reading=self.reading(entry)
        reading["observed_at"]=(now()-timedelta(hours=1)).isoformat()
        self.assertFalse(ledger.observe(entry,reading))
        self.assertIsNone(entry["spent_since_start_minor"])
        self.assertIsNone(entry["first_delivery_on"])

    def test_partial_activation_retry_cannot_reset_saved_baseline(self):
        class Store:
            def save(self,*args):raise AssertionError("must reuse the durable baseline")
        entry=self.entry();entry["launch_verified_at"]=None
        run={"campaign_ledger":{"123":entry},"proposal":{"id":"proposal"},
             "write_journal":{"proposal":{"activate:456":{"state":"pending"}}}}
        batch={"campaign_id":"123","name":"agi-test","daily_minor":30000}
        reused=ledger.capture_baseline(Store(),run,object(),batch)
        self.assertEqual(reused["baseline"]["window_spend_minor"],5000)

    def test_late_spend_revision_does_not_erase_recorded_baseline(self):
        entry=self.entry()
        with self.assertRaises(Stop):ledger.observe(entry,self.reading(entry,4000))
        self.assertEqual(entry["baseline"]["window_spend_minor"],5000)

    def test_optional_reporting_failure_does_not_prevent_verified_launch_accounting(self):
        class Store:
            def save(self,run,event,payload):self.event=event
        store=Store();run={"proposal":{"id":"test"},"write_journal":{}}
        batch={"campaign_id":"123","name":"agi-test","daily_minor":30000}
        with patch("meta_ads.ledger.read_spending",side_effect=Stop("Temporary Insights read failure")):
            entry=ledger.capture_baseline(store,run,object(),batch)
        self.assertIsNone(entry["baseline"])
        self.assertEqual(store.event,"agi_spend_baseline_unavailable")
        ledger.mark_launched(run,{"campaign_id":"123","launch_verified_at":stamp()})
        self.assertTrue(ledger.summary({**run,"request":{}})["started"])
        self.assertIsNone(ledger.summary({**run,"request":{}})["spent_since_start_minor"])

if __name__ == "__main__":unittest.main()
