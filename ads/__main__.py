"""Meta Ads lifecycle CLI."""
import argparse
import json
import sys
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .config import profile
from . import connected, meta_catchup
from .execution import authorize, reconcile
from .meta import Meta, Stop, configured, require
from .sources import drive_inventory, product
from .state import REGISTRY, ROOT, Store
from .worker import run_due, submit_manual
from .workflow import execute, ready_review, request, resume


def read(path):
    if path == "-":
        return json.load(sys.stdin)
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def show(run):
    proposal = run.get("proposal")
    return {key: run.get(key) for key in ("id", "revision", "group", "step", "status", "outcome", "next_review_at",
                                          "strategy_version", "blockers", "last_receipt", "waiting_health")} | {
        "product_id": run["request"]["product_id"],
        "brand_id": (run["request"].get("brand") or {}).get("brand_id"),
        "connected": bool(run.get("connected")),
        "skill_path": REGISTRY.get(run["step"], {}).get("path"),
        "campaign": {key: run["meta"].get(key) for key in ("id", "name")},
        "approval_needed": {"id": proposal["id"], "action": proposal["operation"],
                            "impact": proposal["impact"]} if proposal and run["status"] == "awaiting_approval" else None,
    }


def emit(value):
    print(json.dumps(value, indent=2, ensure_ascii=True), flush=True)


def command():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", help="Private SQLite path. Set META_ADS_STATE_DB for scheduled runs.")
    sub = parser.add_subparsers(dest="action", required=True)
    p = sub.add_parser("init", help="Prepare private, blank setup files for a new brand.")
    p.add_argument("brand", help="Short brand name for the private setup folder.")
    p = sub.add_parser("manage", help="Start or continue the full lifecycle for assigned products.")
    p.add_argument("--brand", help="Saved brand JSON. Omit when one configured brand is present.")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--now", action="store_true", help="Run due skills with the host's direct API connections.")
    mode.add_argument("--connected", action="store_true", help="Continue with the calling agent's plugins.")
    for name, help_text in (("run", "Start or enqueue one campaign request."),
                            ("validate-request", "Check the brand profile and product fields offline.")):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("file")
        p.add_argument("--brand", help="User-supplied brand and policy JSON file.")
        p.add_argument("--test-budget", help="Use this test budget in normal currency units, such as 3000.")
        if name == "run":
            mode = p.add_mutually_exclusive_group()
            mode.add_argument("--now", action="store_true", help="Run due skills with the host's direct API connections.")
            mode.add_argument("--connected", action="store_true", help="Continue with the calling agent's plugins.")
    for name in ("status", "events", "proposal", "resume", "review", "execute", "next"):
        p = sub.add_parser(name)
        p.add_argument("run_id")
        if name == "resume":
            p.add_argument("--from", dest="from_step")
    p = sub.add_parser("result")
    p.add_argument("run_id")
    p.add_argument("step")
    p = sub.add_parser("submit", help="Submit a structured read/analysis result manually.")
    p.add_argument("run_id")
    p.add_argument("step")
    p.add_argument("file")
    p.add_argument("--connected", action="store_true", help="Submit the current step as the connected agent.")
    p = sub.add_parser("collect", help="Save scoped evidence collected by the connected agent.")
    p.add_argument("run_id")
    p.add_argument("file")
    p = sub.add_parser("facts", help="Update checked owner-supplied references on a run.")
    p.add_argument("run_id")
    p.add_argument("file")
    p = sub.add_parser("approve")
    p.add_argument("run_id")
    p.add_argument("proposal_id")
    p.add_argument("--operator", required=True)
    p.add_argument("--owner")
    p.add_argument("--reference", required=True)
    p.add_argument("--reject", action="store_true")
    p.add_argument("--renew", action="store_true", help="Renew approval for the same proposal after partial execution.")
    p.add_argument("--execute", action="store_true")
    p = sub.add_parser("reconcile")
    p.add_argument("run_id")
    p.add_argument("operation")
    p.add_argument("--id")
    p.add_argument("--absent", action="store_true", help="Record independently verified non-execution.")
    p.add_argument("--reference")
    p = sub.add_parser("worker", help="Process ready or due jobs using the read-only credentials.")
    p.add_argument("--run")
    p.add_argument("--watch", action="store_true")
    p.add_argument("--interval", type=int, default=300)
    sub.add_parser("dispatch", help="Operator job. Execute queued, explicitly approved proposals.")
    sub.add_parser("list")
    sub.add_parser("meta-sync", help="Fetch completed read-only Meta snapshots from GitHub.")
    p = sub.add_parser("source", help="Probe one connected evidence source without modifying a campaign.")
    p.add_argument("source", choices=["account", "budget", "product", "drive"])
    p.add_argument("id", nargs="?")
    p.add_argument("--brand", help="Brand JSON for the configured account and evidence sources.")
    return parser.parse_args()


def initialize(brand_name):
    import re
    brand_id = re.sub(r"[^a-z0-9]+", "-", brand_name.casefold()).strip("-")
    require(brand_id and len(brand_id) <= 64, "Provide a short brand name.")
    directory = ROOT / ".state" / brand_id
    brand = read(ROOT / "examples/brand-profile.json")
    brand.update(brand_id=brand_id, brand_name=brand_name.strip(), website=None, shopify_shop=None, account_id=None)
    for field in ("page_id", "pixel_id", "instagram_id"):
        brand.pop(field, None)
    rules = brand["policy"]
    for field in ("currency", "minor_per_unit", "minimum_daily_minor", "maximum_daily_minor",
                  "maximum_monthly_minor", "creative_root"):
        rules[field] = None
    for field in ("operators", "owners", "formats", "placements"):
        rules[field] = []
    product = {"product_id": None, "product_name": None, "landing_page": None,
               "countries": [], "objective": "website_sales", "brief": None}
    directory.mkdir(parents=True, exist_ok=True)
    for name, data in (("brand.json", brand), ("product.json", product)):
        path = directory / name
        if not path.exists():
            with path.open("x", encoding="utf-8") as file:
                json.dump(data, file, indent=2, ensure_ascii=False)
                file.write("\n")
    return {"brand": str(directory / "brand.json"), "product": str(directory / "product.json")}


def assigned_requests(brand_path=None):
    if brand_path is None:
        choices = sorted((ROOT / ".state").glob("*/brand.json"))
        require(choices, "Set up a brand before starting ad management.")
        require(len(choices) == 1, "Choose which saved brand to manage.")
        brand_path = choices[0]
    path = Path(brand_path).resolve()
    brand = profile(read(path))
    assignments = path.with_name("assignments.json")
    filenames = read(assignments) if assignments.is_file() else ["product.json"]
    require(isinstance(filenames, list) and filenames
            and all(isinstance(name, str) and Path(name).name == name
                    and name.endswith(".json") and name not in {path.name, assignments.name} for name in filenames)
            and len(filenames) == len(set(filenames)), "Assign one or more distinct saved product files.")
    requests = []
    for name in filenames:
        product_path = path.with_name(name)
        require(product_path.is_file() and product_path.resolve().parent == path.parent,
                "An assigned product file is missing or outside the brand folder.")
        requests.append(request(read(product_path), brand))
    require(len({item["name"] for item in requests}) == len(requests),
            "Assigned products must have distinct campaign names.")
    return requests


def main():
    args = command()
    try:
        name = args.action
        if name == "init":
            emit(initialize(args.brand))
            return 0
        if name == "manage":
            assignments = assigned_requests(args.brand)
            store = Store(args.db)
            runs = [store.create(item, reuse_existing=True) for item in assignments]
            if args.connected:
                try:
                    caught_up = meta_catchup.sync(store)
                    if caught_up["status"] not in {"unconfigured", "success", "waiting"}:
                        print("The latest scheduled Meta read failed. Check the Meta catch-up workflow.", file=sys.stderr)
                    elif caught_up.get("unavailable"):
                        print("Some encrypted Meta snapshots could not be read.", file=sys.stderr)
                except (Stop, OSError, KeyError, ValueError):
                    print("Meta catch-up sync is unavailable. Continue with cached evidence if current.", file=sys.stderr)
                runs = [meta_catchup.record(store, connected.enable(store, run)) for run in runs]
            if args.now:
                runs = [run_due(store, only=run["id"])[0] for run in runs]
            emit([show(run) for run in runs])
            return 0
        if name == "source":
            brand = profile(read(args.brand)) if args.brand else None
            with configured(brand):
                if args.source in {"account", "budget"}:
                    account = args.id or (brand or {}).get("account_id")
                    require(not brand or brand["account_id"] == account, "Source account differs from the brand profile.")
                    client = Meta(account)
                    emit(client.account_report() if args.source == "account" else client.budget())
                elif args.source == "product":
                    emit(product(args.id))
                else:
                    emit(drive_inventory())
            return 0
        if name in {"run", "validate-request"}:
            brand = profile(read(args.brand)) if args.brand else None
            product_request = read(args.file)
            if args.test_budget is not None:
                require(brand, "Load the saved brand to use its currency for the test budget.")
                try:
                    amount = Decimal(args.test_budget) * brand["policy"]["minor_per_unit"]
                except InvalidOperation:
                    raise Stop("Enter the total test budget as a number.") from None
                require(amount.is_finite() and amount > 0 and amount == amount.to_integral_value()
                        and amount <= brand["policy"]["maximum_monthly_minor"],
                        "Enter a positive test budget within the saved monthly limit and currency precision.")
                product_request["test_budget_minor"] = int(amount)
            campaign = request(product_request, brand)
            if name == "validate-request":
                emit({"valid": True, "campaign": campaign["name"], "product_id": campaign["product_id"],
                      "brand_id": (campaign.get("brand") or {}).get("brand_id")})
                return 0
        store = Store(args.db)
        if name == "run":
            require(not args.connected or brand, "Load the saved brand for connected-agent mode.")
            run = store.create(campaign)
            if args.connected:
                run = connected.enable(store, run)
            emit(show(run))
            if args.now:
                emit(show(run_due(store, only=run["id"])[0]))
        elif name == "list":
            emit([show(r) for r in store.list()])
        elif name == "meta-sync":
            summary = meta_catchup.sync(store)
            for run in store.list():
                meta_catchup.record(store, run)
            emit(summary)
        elif name == "worker":
            require(args.interval >= 1, "Worker interval must be positive.")
            revisions = {}
            while True:
                for run in run_due(store, only=args.run):
                    if revisions.get(run["id"]) != run["revision"]:
                        emit(show(run))
                        revisions[run["id"]] = run["revision"]
                if not args.watch:
                    break
                time.sleep(args.interval)
        elif name == "dispatch":
            for run in store.list():
                if run["status"] == "approved":
                    emit(show(execute(store, run["id"])))
        else:
            run = store.get(args.run_id)
            if name == "status":
                emit(show(run))
            elif name == "next":
                emit(connected.next_step(store, run))
            elif name == "collect":
                emit(show(connected.collect_step(store, run["id"], read(args.file))))
            elif name == "events":
                emit(store.events(run["id"]))
            elif name == "result":
                emit(run["records"].get(args.step))
            elif name == "proposal":
                emit(run["proposal"])
            elif name == "resume":
                emit(show(resume(store, run["id"], from_step=args.from_step)))
            elif name == "review":
                emit(show(ready_review(store, run, force=True)))
            elif name == "submit":
                require(run["step"] == args.step, "Run has already moved beyond this result.")
                output = read(args.file)
                emit(show(connected.submit_step(store, run, output) if args.connected
                          else submit_manual(store, run, output)))
            elif name == "facts":
                values = read(args.file)
                require(isinstance(values, dict) and values, "Supply a nonempty object of verified facts.")
                with store.lease("executor"):
                    run = store.get(run["id"])
                    require(run["status"] in {"blocked", "ready", "monitoring", "paused"} and not run.get("proposal"),
                            "Resolve the current proposal before editing inputs.")
                    run["request"].setdefault("facts", {}).update(values)
                    store.save(run, "facts_updated", {"sections": sorted(values)})
                    emit(show(run))
            elif name == "approve":
                require(not (args.reject and args.execute), "A rejected proposal cannot execute.")
                updated = authorize(store, run["id"], args.proposal_id, operator=args.operator, owner=args.owner,
                                    reference=args.reference, reject=args.reject, renew=args.renew)
                emit(show(execute(store, run["id"]) if args.execute else updated))
            elif name == "execute":
                emit(show(execute(store, run["id"])))
            elif name == "reconcile":
                with configured(run["request"].get("brand")):
                    client = Meta(run["request"]["account_id"])
                    emit(show(reconcile(store, run["id"], args.operation, client, args.id,
                                        absent=args.absent, reference=args.reference)))
    except KeyboardInterrupt:
        return 130
    except (Stop, OSError, KeyError, ValueError, TypeError) as error:
        print(str(error) if isinstance(error, Stop) else f"Request failed ({type(error).__name__}). Check inputs.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
