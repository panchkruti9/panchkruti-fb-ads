"""Exercise encrypted transport, durable recovery and exact result imports."""
import io
import json
import os
import tempfile
import unittest
import zipfile
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from meta_ads import gateway
from meta_ads.meta import Stop, canonical, fingerprint
from meta_ads.state import Store, stamp
from meta_ads.workflow import request, performance_mature
from meta_ads.plans import verify_audiences
from meta_ads.meta_catchup import setup, encrypt, decrypt


class GatewayTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / "local/lifecycle.sqlite3")
        self.addCleanup(self.store.db.close)
        self.run = self.store.create(request({"product_id":"101", "name":"agi-gateway-test", "account_id":"99",
                                             "countries":["IN"], "brief":"Synthetic transport test"}))
        self.key = "synthetic-transport-approval-key-1234567890"
        base = gateway.directory(self.store)
        setup(base / "client")
        setup(base / "server")
        (base / "approval.key").write_text(self.key)
        (base / "config.json").write_text('{"repo":"example/repository"}')
        self.assets = {}

    def fake_gh(self, args, **kwargs):
        if args[:2] == ["release", "view"]:
            return json.dumps({"assets":[{"name":n} for n in self.assets]}).encode()
        if args[:2] == ["release", "download"]:
            name = args[args.index("--pattern")+1]
            folder = Path(args[args.index("--dir")+1])
            (folder/name).write_bytes(self.assets[name])
            return b""
        if args[:2] == ["release", "upload"]:
            file = Path(args[3]); self.assets[file.name] = file.read_bytes(); return b""
        raise AssertionError(args)

    def test_encrypted_job_checkpoint_resume_and_exact_once_import(self):
        self.run["status"]="execution_blocked"
        self.store.save(self.run,"fixture_prior_write_blocked",{})
        job_id, manifest = gateway.pack_request(self.store, self.run, "health", {})
        folder = gateway.job_folder(self.store,job_id)
        self.assets[job_id+"-request.cms"]=(folder/"request.cms").read_bytes()
        self.assertNotIn(b"agi-gateway-test", self.assets[job_id+"-request.cms"])
        base=gateway.directory(self.store)
        environment={"GITHUB_REPOSITORY":"example/repository", "META_AD_ACCOUNT_ID":"99",
                     "META_ADS_OPERATOR_KEY":self.key,
                     "META_JOB_CERT":(base/"server/cert.pem").read_text(),
                     "META_JOB_DECRYPT_KEY":(base/"server/key.pem").read_text()}
        def crash(store,run,operation,options):
            run["checkpoint_value"]="before-remote-write"
            store.save(run,"write_pending",{"operation":"fixture"})
            raise RuntimeError("simulate runner loss after durable checkpoint")
        with patch.dict(os.environ,environment), patch.object(gateway,"gh",self.fake_gh):
            with patch.object(gateway,"perform",crash):
                with self.assertRaises(RuntimeError):
                    gateway.run_job(job_id,self.root/"runner1")
            self.assertEqual(len([n for n in self.assets if "checkpoint" in n]),1)
            def recover(store,run,operation,options):
                self.assertEqual(run["checkpoint_value"],"before-remote-write")
                run["checkpoint_value"]="readback-verified"
                store.save(run,"write_verified",{"operation":"fixture"})
                return {"verified":True}
            with patch.object(gateway,"perform",recover):
                gateway.run_job(job_id,self.root/"runner2")
            resultpath=self.root/"result.cms";resultpath.write_bytes(self.assets[job_id+"-result.cms"])
            result=decrypt(resultpath,base/"client")
            self.assertEqual(result["status"],"verified")
            signature=result.pop("signature")
            self.assertEqual(signature,gateway.digest(result,self.key))
            updated=gateway.import_result(self.store,self.run,result)
            self.assertEqual(updated["checkpoint_value"],"readback-verified")
            events=len(self.store.events(self.run["id"]))
            replay=gateway.import_result(self.store,updated,result)
            self.assertEqual(len(self.store.events(self.run["id"])),events)
            self.assertEqual(replay["revision"],updated["revision"])
            self.assertTrue((self.store.logs_dir/"activity.md").is_file())

    def test_changed_local_revision_rejects_remote_overwrite(self):
        result={"run":deepcopy(self.run),"base_revision":self.run["revision"],"job_id":"a"*32,
                "operation":"health","status":"verified","events":[]}
        self.store.save(self.run,"local_change",{})
        with self.assertRaisesRegex(Stop,"changed during"):
            gateway.import_result(self.store,self.run,result)

    def test_activation_receipt_can_add_verified_launch_facts_but_cannot_change_product_scope(self):
        remote=deepcopy(self.run)
        remote["request"].setdefault("facts",{})["tracking"]={"purchase_verified":True}
        receipt={"run":remote,"base_revision":self.run["revision"],"job_id":"b"*32,
                 "operation":"activation","status":"verified","events":[]}
        updated=gateway.import_result(self.store,self.run,receipt)
        self.assertTrue(updated["request"]["facts"]["tracking"]["purchase_verified"])
        forged=deepcopy(receipt);forged["job_id"]="c"*32
        forged["run"]["request"]["product_id"]="999"
        with self.assertRaisesRegex(Stop,"another scope"):
            gateway.import_result(self.store,updated,forged)

    def test_prepaid_launch_uses_native_funding_without_invalid_account_limit_update(self):
        from meta_ads.execution import hard_cap, launch_cap_change
        class Client:
            prefix="act_99"
            def request(self,path,params):
                return {"is_prepay_account":True,"spend_cap":"10000","amount_spent":"10001"}
        self.assertIsNone(launch_cap_change({},Client(),{"passed":True}))
        hard_cap(Client(),{"passed":True})
        with self.assertRaises(Stop):hard_cap(Client(),{"passed":False})

    def test_bundle_cannot_escape_private_job_directory(self):
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,"w") as archive:archive.writestr("../outside.json","bad")
        with zipfile.ZipFile(io.BytesIO(buffer.getvalue())) as archive:
            with self.assertRaises(Stop):gateway.safe_extract(archive,self.root/"input")

    def test_warning_does_not_hide_deliverable_audience_but_restrictions_do(self):
        class Client:
            account="99"
            def audience_inventory(self):return [self.audience]
        client=Client()
        adsets=[{"audience":{"mode":"retargeting","include":["123"],"exclude":[]}}]
        for status in (100,200,400,411,441,450):
            client.audience={"id":"123","account_id":"99","subtype":"WEBSITE",
                             "operation_status":{"code":status},"delivery_status":{"code":200}}
            verify_audiences(client,adsets)
        for status,delivery in ((471,200),(200,300),(433,200)):
            client.audience.update(operation_status={"code":status},delivery_status={"code":delivery})
            with self.assertRaises(Stop):verify_audiences(client,adsets)

    def test_zero_orders_alone_are_not_sufficient_exposure(self):
        run={"records":{"strategy-development":{"data":{"criteria":{"minimum_matched_orders":5,
                  "maximum_cpa_minor":None}}}},"request":{"facts":{"tracking":{"purchase_verified":True}}}}
        with patch("meta_ads.workflow.measured_window",return_value={"orders":0,"spend":1000}):
            self.assertFalse(performance_mature(run))
        with patch("meta_ads.workflow.measured_window",return_value=None):
            self.assertFalse(performance_mature(run))

    def test_launch_audit_collects_other_checks_without_saved_tracking_or_pixel_permission(self):
        run={"meta":{"id":"123","name":"agi-launch-test","pending_batch":{
            "identity":{"pixel_id":"456"},"ad_ids":[{"id":"789","placements":["facebook_feed"]}]}}}
        class Client:
            prefix="act_99"
            def details(self):return {"account_status":1}
            def budget(self):return {"passed":True}
            def scope(self,*args):return {"id":"123","configured_status":"PAUSED"}
            def pages(self,*args):return [{"id":"456"}]
            def request(self,path,params):
                if path.endswith("/stats"):raise Stop("Pixel statistics permission unavailable")
                return {"account_id":"99","spend_cap":"10000","amount_spent":"0"}
        with patch("meta_ads.execution.previews",return_value={"789":["facebook_feed"]}), patch("meta_ads.meta_catchup.draft_readback",return_value={"ads":[]}):
            report=gateway.launch_audit(run,Client())
        self.assertIn("purchase_source",report["issues"])
        self.assertIn("spend_control",report["checks"])
        self.assertIn("previews",report["checks"])
        self.assertEqual(report["checks"]["campaign"]["configured_status"],"PAUSED")

if __name__ == "__main__":unittest.main()
