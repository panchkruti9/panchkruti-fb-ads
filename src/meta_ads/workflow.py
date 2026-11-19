"""The sole lifecycle router. Skills return artifacts, never transition state directly."""
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from .config import configured_request
from .execution import Deferred, GATES, Executor, approval_expired, campaign_configuration, expired, make_proposal
from .meta import Meta, Stop, account_zone, campaign_key, configured, meta_id, minor, policy, require
from .plans import OPS, result, string
from .state import GROUPS, REGISTRY, now, parse_time, stamp

WRITES = set(GATES) | {"scaling-execution"}
REWORK = {
    "asset-selection": {"creative-concept"},
    "creative-validation": {"creative-concept", "ad-copywriting", "asset-selection"},
    "activation-check": set(),
}


def request(data, brand=None):
    required = {"product_id", "name", "account_id", "countries", "brief"}
    if brand is None:
        require(isinstance(data, dict) and required <= set(data) <= required | {"facts", "review_policy"},
                "New product requests require --brand BRAND.json and the product request fields.")
    else:
        data = configured_request(data, brand)
    meta_id(data["product_id"])
    meta_id(data["account_id"])
    campaign_key(data["name"])
    require(isinstance(data["countries"], list) and data["countries"]
            and all(isinstance(key, str) and re.fullmatch(r"[A-Z]{2}", key) for key in data["countries"]),
            "Countries must be an explicit nonempty list of two-letter codes.")
    string(data["brief"], "campaign brief")
    require(isinstance(data.get("facts", {}), dict), "Facts must be an object.")
    require(isinstance(data.get("review_policy", {}), dict), "Review policy must be an object.")
    if brand is not None:
        review = data["review_policy"]
        require(set(review) <= {"window_days", "lag_days", "minimum_matched_orders", "recheck_hours", "maximum_cpa_minor"},
                "Review policy includes an unsupported field.")
        for key, value in review.items():
            if key == "maximum_cpa_minor" and value is None:
                continue
            minor(value, positive=key != "lag_days")
            if key in {"window_days", "lag_days"}:
                require(value <= 30, "Review and attribution windows cannot exceed 30 days.")
    return data


def group(run, name, *, start=None):
    run.update(group=name, step=start or GROUPS[name][0], status="ready", outcome=None, proposal=None, blockers=[])
    run.pop("approval", None)
    if name == "create":
        run.pop("creative_rework_history", None)


def route_creative_rework(run, step, output):
    data = output["data"]
    target = data.get("retry_step")
    require(target in REWORK.get(step, set()), "Skill cannot reroute to that step.")
    issue = string(data.get("issue"), "specific creative issue")
    assets = data.get("asset_ids", [])
    require(isinstance(assets, list) and all(isinstance(value, str) and value.strip() for value in assets),
            "Rework asset IDs must be strings.")
    signature = [step, target, " ".join(issue.casefold().split()), sorted(set(assets))]
    history = run.setdefault("creative_rework_history", [])
    repeated = any(item["signature"] == signature for item in history)
    record = {**data, "from_step": step, "blockers": output["blockers"], "signature": signature}
    if repeated:
        stop(run, ["The same creative rework issue recurred. Resolve the missing input before trying again.", issue])
        return
    history.append(record)
    current_group = GROUPS[run["group"]]
    for invalidated in current_group[current_group.index(target):]:
        old = run["records"].pop(invalidated, None)
        if old:
            run["history"].append({"step": invalidated, "record": old})
    run["step"] = target


def completed_step(run, step):
    current = GROUPS[run["group"]]
    index = current.index(step)
    require(index + 1 < len(current), f"No ordinary successor for {step}.")
    run["step"] = current[index + 1]


def hours(run):
    strategy = run["records"]["strategy-development"]["data"]
    return strategy["criteria"]["recheck_hours"]


def schedule(run, *, outcome="COMPLETE", review_date=None):
    due = now() + timedelta(hours=hours(run))
    if review_date:
        zone = account_zone(run.get("review_evidence", {}).get("account_timezone", "UTC"))
        requested = datetime.combine(date.fromisoformat(review_date), datetime.min.time(), tzinfo=zone)
        due = max(due, requested)
    run.update(group="optimize", step="performance-analysis", status="monitoring", outcome=outcome,
               next_review_at=due.isoformat(timespec="seconds"),
               proposal=None, blockers=[])
    run.pop("approval", None)


def stop(run, reasons):
    run.update(status="blocked", outcome="STOP", blockers=reasons)


def clear_groups(run, *groups, preserve=()):
    for key in list(run["records"]):
        if REGISTRY.get(key, {}).get("group") in groups and key not in preserve:
            run["history"].append({"step": key, "record": run["records"].pop(key)})


def record_strategy_cycle(run, reason):
    records = run["records"]
    strategy = records.get("strategy-development")
    if strategy:
        run.setdefault("strategy_cycles", []).append({
            "closed_at": stamp(), "reason": reason, "strategy": strategy,
            "performance_mature": performance_mature(run),
            "campaign": {key: run["meta"].get(key) for key in ("id", "name")},
            "results": {key: records[key] for key in (
                "campaign-analysis", "business-performance", "performance-analysis", "optimization-decision"
            ) if key in records},
        })


def plan_replacement(run):
    run["create_mode"] = "recreate"
    number = run.get("replacement_number", 1) + 1
    run["replacement_number"] = number
    suffix = f"-v{number:02d}"
    base = run["request"]["name"][:100 - len(suffix)].rstrip("-")
    run["planned_name"] = campaign_key(base + suffix)
    clear_groups(run, "create")


def validate_strategy(run, data):
    require(date.fromisoformat(data["next_review_on"]) >= now().date(), "Strategy review date is in the past.")
    criteria = data["criteria"]
    baseline = run["request"].get("review_policy", {})
    for key in baseline:
        require(key in criteria and baseline[key] == criteria[key], f"Strategy changed the supplied {key}.")
    if criteria["maximum_cpa_minor"] is not None and "maximum_cpa_minor" not in baseline:
        # Without an externally supplied ceiling, a strategy can track CPA, but cannot invent a viable one.
        facts = run["request"].get("facts", {})
        cap = facts.get("economics", {})
        require(isinstance(cap, dict) and cap.get("target_cpa_minor") == criteria["maximum_cpa_minor"]
                and cap.get("source"), "CPA ceiling must come from supplied verified economics.")
    if run.get("strategy_refresh") and run["request"].get("brand"):
        require(data.get("cycle_action") in ("continue", "recreate"),
                "On strategy refresh choose whether to continue or recreate the campaign.")


def measured_window(run, key):
    """Read a clean, complete window from the worker's two independent sources."""
    criteria = run["records"]["strategy-development"]["data"]["criteria"]
    request = run["request"]
    denominator = "matched_first_time_buyers" if request.get("success_metric") == "first_time_buyers" else "matched_orders"
    money_scale = policy(request.get("brand"))["minor_per_unit"]
    report = run.get("review_evidence", {})
    if request.get("brand") and report.get("configuration") != run.get("campaign_configuration"):
        return None
    if request.get("brand") and not run.get("campaign_configuration"):
        return None
    meta = report.get("meta", {}).get(key) or {}
    shop = report.get("shopify", {}).get(key) or {}
    try:
        start, end = (date.fromisoformat(meta[k]) for k in ("start", "end"))
        if (meta["start"], meta["end"]) != (shop["start"], shop["end"]):
            return None
        zone = account_zone(report.get("account_timezone", "UTC"))
        cutoff = now().astimezone(zone).date() - timedelta(days=1 + criteria["lag_days"])
        if end > cutoff or (end - start).days + 1 != criteria["window_days"]:
            return None
        changed_at = run.get("last_material_change_at") or run.get("live_since")
        if not changed_at or start <= parse_time(changed_at).astimezone(zone).date():
            return None
        rows = meta.get("rows", {}).get("campaign", [])
        orders = shop[denominator]
        if len(rows) != 1 or type(orders) is not int or orders < 0 or shop.get("pending_journey", 0):
            return None
        if rows[0].get("campaign_id", run["meta"]["id"]) != run["meta"]["id"]:
            return None
        spent = Decimal(rows[0]["spend"]) * money_scale
        if spent.is_finite() and spent > 0:
            return {"start": start, "end": end, "orders": orders, "spend": spent,
                    "cash": shop.get("product_cash", {}).get(request.get("success_metric", "paid_orders"), {})}
    except (InvalidOperation, KeyError, TypeError, ValueError):
        pass
    return None


def performance_mature(run):
    current = measured_window(run, "current")
    if not current:
        return False
    criteria = run["records"]["strategy-development"]["data"]["criteria"]
    minimum, target = criteria["minimum_matched_orders"], criteria["maximum_cpa_minor"]
    tracking = run["request"].get("facts", {}).get("tracking", {})
    return tracking.get("purchase_verified") is True and (
        current["orders"] >= minimum or bool(target and current["spend"] >= target * minimum)
        or current["orders"] == 0)


def scale_proof(run):
    """Require independent windows and positive measured product contribution after ad spend."""
    criteria = run["records"]["strategy-development"]["data"]["criteria"]
    facts = run["request"].get("facts", {})
    economics = facts.get("economics", {})
    target = criteria["maximum_cpa_minor"]
    product = run["request"]
    if (not target or facts.get("tracking", {}).get("purchase_verified") is not True
            or not economics.get("source")
            or economics.get("product_id") != product["product_id"]
            or economics.get("variant_id") != product.get("variant_id")
            or not run["meta"].get("name") or economics.get("campaign") != run["meta"]["name"]
            or economics.get("success_metric") != product.get("success_metric", "paid_orders")):
        return False
    current = measured_window(run, "current")
    previous = measured_window(run, "previous")
    return bool(current and previous and previous["end"] < current["start"]
                and all(window["orders"] >= criteria["minimum_matched_orders"]
                        and window["spend"] <= target * window["orders"]
                        and profitable_window(window, economics)
                        for window in (current, previous)))


def profitable_window(window, economics):
    evidence = economics.get("windows")
    if not isinstance(evidence, list):
        return False
    dates = (window["start"].isoformat(), window["end"].isoformat())
    candidates = [row for row in evidence if isinstance(row, dict) and (row.get("start"), row.get("end")) == dates]
    if len(candidates) != 1:
        return False
    costs = candidates[0]
    values = [costs.get(key) for key in ("product_cost_minor", "shipping_fulfillment_minor", "fees_minor")]
    if any(type(value) is not int or value < 0 for value in values):
        return False
    cash = window["cash"]
    receipts = costs.get("verified_product_net_receipts_minor")
    if receipts is None and cash.get("unallocated_orders") == 0 and cash.get("covered_orders", 0) >= window["orders"]:
        receipts = cash.get("received_less_refunds_and_tax_minor")
    return type(receipts) is int and receipts > sum(values) + window["spend"]


def verified_stop(run, target_id):
    request = run["request"]
    budget = run.get("review_evidence", {}).get("account_budget") or {}
    rules = policy(request.get("brand"))
    if target_id == run["meta"]["id"] and (
        budget.get("daily_minor", 0) > rules["maximum_daily_minor"]
        or budget.get("spent_month_minor", 0) >= rules["maximum_monthly_minor"]
    ):
        return True
    issue = request.get("facts", {}).get("operational_issue", {})
    if not (issue.get("verified") is True and issue.get("target_id") == target_id and issue.get("reference")
            and issue.get("kind") in {"checkout", "tracking", "availability", "spend_limit", "policy"}):
        return False
    try:
        observed = parse_time(issue["observed_at"])
        changed = run.get("last_material_change_at", run.get("live_since"))
        return observed <= now() and (not changed or observed >= parse_time(changed))
    except (KeyError, TypeError, ValueError):
        return False


def decision(run, data):
    choice = data["decision"]
    require(choice in OPS, "Unsupported optimization decision.")
    require(data["target_id"] == run["meta"]["id"] or choice == "PAUSE",
            "This decision must target the enrolled campaign. Only PAUSE can target one of its children.")
    if choice in {"PAUSE", "RECREATE", "TEST", "REFRESH"} and not performance_mature(run):
        if choice != "PAUSE" or not verified_stop(run, data["target_id"]):
            schedule(run, review_date=data["next_review_on"])
            run["blockers"] = ["Proposed change held until there is a complete post-change sales window with enough evidence."]
            return
    if choice == "HOLD":
        schedule(run, review_date=data["next_review_on"])
    elif choice == "SCALE":
        if not scale_proof(run):
            schedule(run, outcome="STOP")
            run["blockers"] = ["Scale needs two separate mature sales windows, verified tracking, a cost ceiling, "
                               "and positive measured product contribution in both windows."]
            return
        group(run, "scale")
        run["outcome"] = "SCALE"
    elif choice == "PAUSE":
        run["step"] = "optimization-execution"
    elif choice in {"FIX", "TEST", "REFRESH"}:
        if choice == "FIX" and data.get("fix_kind") != "creative":
            stop(run, ["Fix needs a specific destination, tracking, or account correction. Repair it and resume review."])
            run["step"] = "campaign-analysis"
            return
        run["create_mode"] = "test" if choice == "TEST" else "refresh"
        clear_groups(run, "create")
        group(run, "create")
    else:
        record_strategy_cycle(run, "replacement")
        plan_replacement(run)
        clear_groups(run, "research")
        group(run, "research")
        run["outcome"] = "RECREATE"


def submit(store, run, output):
    step = run["step"]
    require(step not in WRITES and run["status"] == "ready", "The workflow does not accept a manual write receipt.")
    result(step, output)
    if step == "strategy-development" and output["status"] == "pass":
        validate_strategy(run, output["data"])
        prior = (run.get("strategy_cycles") or [{}])[-1]
        if (run.get("strategy_refresh") and output["data"].get("cycle_action") == "recreate"
                and not prior.get("performance_mature") and prior.get("strategy")):
            record = prior["strategy"]
            run["records"][step] = {
                **record, "data": {**record["data"], "next_review_on": output["data"]["next_review_on"]}
            }
            run.pop("strategy_refresh")
            schedule(run)
            run["blockers"] = ["Replacement held until a complete sales review is available."]
            store.save(run, "strategy_replacement_deferred", {"proposed_result": output,
                       "retained_strategy_id": record["data"].get("strategy_id"), "reasons": run["blockers"]})
            return run
    if previous := run["records"].get(step):
        run["history"].append({"step": step, "record": previous})
    current = {**output, "recorded_at": stamp(), "review_number": run["review_number"]}
    run["records"][step] = current
    if output["status"] == "block":
        stop(run, output["blockers"])
    elif output["status"] == "rework":
        route_creative_rework(run, step, output)
    elif step == "strategy-development":
        run["strategy_version"] += 1
        data = current["data"]
        data["strategy_id"] = f"{run['id']}:strategy:{run['strategy_version']}"
        data["version"] = run["strategy_version"]
        data["created_at"] = current["recorded_at"]
        data["last_reviewed_at"] = current["recorded_at"]
        data["product_id"] = run["request"]["product_id"]
        data["campaign"] = run.get("planned_name", run["request"]["name"])
        data["execution_status"] = "current"
        data["research_sources"] = [ref for key in GROUPS["research"][:-1] for ref in run["records"][key]["evidence"]]
        if run.pop("strategy_refresh", False):
            if data.get("cycle_action") == "recreate":
                plan_replacement(run)
                data["campaign"] = run["planned_name"]
                group(run, "create")
                run["outcome"] = "RECREATE"
            else:
                schedule(run)
                run["next_review_at"] = stamp()
        else:
            group(run, "create")
    elif step == "activation-check":
        run["step"] = "activate"
    elif step == "existing-campaign-review":
        if output["data"]["decision"] == "check_activation":
            require(run["meta"].get("pending_batch"), "The registered draft needs verified activation checks.")
            run["step"] = "activation-check"
        elif output["data"]["decision"] == "replan":
            require(run.get("enrolled_campaign") and not run.get("proposal") and not run.get("live_since"),
                    "Use the normal optimization workflow for a campaign that has been launched.")
            record_strategy_cycle(run, "paused_draft_replan")
            plan_replacement(run)
            group(run, "research", start="strategy-development")
        else:
            run.update(status="paused", outcome="COMPLETE", blockers=[])
    elif step == "optimization-decision":
        decision(run, output["data"])
    elif step == "scaling-eligibility" and not output["data"]["eligible"]:
        schedule(run, outcome="STOP")
        run["blockers"] = [output["summary"]]
    elif step == "budget-validation" and not output["data"]["passed"]:
        schedule(run, outcome="STOP")
        run["blockers"] = [output["summary"]]
    else:
        completed_step(run, step)
    event = {"step": step, "result": current, "next": run["step"], "outcome": run["outcome"]}
    if step == "optimization-decision" and run["outcome"] == "RECREATE" and run.get("strategy_cycles"):
        event["closed_strategy_cycle"] = run["strategy_cycles"][-1]
    if step == "optimization-decision" and run["status"] == "monitoring" and run["blockers"]:
        event["decision_deferred"] = run["blockers"]
    store.save(run, "skill_result", event)
    return run


def ready_review(store, run, *, force=False):
    checked = now()
    require(run["status"] == "monitoring", "Only a monitoring campaign can start another review.")
    if not force and run["next_review_at"] and parse_time(run["next_review_at"]) > checked:
        return run
    due = date.fromisoformat(run["records"]["strategy-development"]["data"]["next_review_on"])
    refresh = due < checked.date()
    if refresh:
        record_strategy_cycle(run, "scheduled_strategy_refresh")
    clear_groups(run, "optimize", "scale")
    run["review_number"] += 1
    run.pop("review_evidence", None)
    if refresh:
        clear_groups(run, "research")
        run["strategy_refresh"] = True
        group(run, "research")
    else:
        group(run, "optimize")
    event = {"review": run["review_number"], "step": run["step"]}
    if refresh and run.get("strategy_cycles"):
        event["closed_strategy_cycle"] = run["strategy_cycles"][-1]
    store.save(run, "review_started", event)
    return run


def prepare(store, run, client, *, assets=None):
    require(run["status"] == "ready" and run["step"] in GATES, "No proposal is due.")
    if run["step"] == "scaling-approval":
        require(scale_proof(run), "Verified scale evidence is incomplete.")
    with configured(run["request"].get("brand")):
        if run["step"] == "scaling-approval" and run["request"].get("brand"):
            require(campaign_configuration(client, run["meta"]) == run.get("campaign_configuration"),
                    "Meta configuration changed after the sales review.")
        proposal = make_proposal(run, client, assets=assets)
    run.update(proposal=proposal, status="awaiting_approval", blockers=[])
    store.save(run, "proposal_ready", proposal)
    return run


def execute(store, run_id, client_factory=None):
    from .gateway import enabled, invoke
    if client_factory is None and enabled(store):
        return invoke(store, store.get(run_id), "execute")[0]
    with store.lease("executor"):
        run = store.get(run_id)
        require(run["status"] in {"approved", "execution_blocked"}, "No approved write is pending.")
        p = run["proposal"]
        try:
            with configured(run["request"].get("brand")):
                client = (client_factory or (lambda account: Meta(account, writer=True)))(p["account_id"])
                executor = Executor(store, run, client)
                op = p["operation"]
                if op == "budget" and run["request"].get("brand") and not run["write_journal"].get(p["id"]):
                    require(campaign_configuration(client, run["meta"]) == run.get("campaign_configuration"),
                            "Meta configuration changed after the scale proposal.")
                receipt = executor.build() if op == "build" else executor.activate() if op == "activate" else executor.edit()
        except Deferred as error:
            run.update(status="approved", blockers=[str(error)])
            store.save(run, "meta_processing", {"reason": str(error)})
            return run
        except (Stop, OSError, KeyError, ValueError, TypeError) as error:
            message = str(error) if isinstance(error, Stop) else f"Provider execution failed ({type(error).__name__}). Inspect the journal."
            run.update(status="execution_blocked", outcome="STOP", blockers=[message])
            store.save(run, "execution_blocked", {"proposal": p["id"], "reason": message})
            return run
        step = run["step"]
        run["records"][step] = {"status": "pass", "data": {"receipt": receipt, "proposal_id": p["id"]},
                                 "recorded_at": stamp()}
        run["last_receipt"] = {"operation": op, "at": stamp(), **receipt}
        if op == "build":
            if not receipt["addition"] and run.get("meta", {}).get("id"):
                run.setdefault("previous_campaigns", []).append(run["meta"])
            run["meta"] = {**(run["meta"] if receipt["addition"] else {}), "id": receipt["campaign_id"],
                           "name": receipt["name"], "pending_batch": receipt}
            run.update(group="create", step="activation-check", status="ready", outcome="COMPLETE",
                       proposal=None, blockers=[])
            run.pop("approval", None)
        elif op == "activate":
            from .ledger import mark_launched
            mark_launched(run, receipt)
            run["meta"].pop("pending_batch", None)
            run.setdefault("live_since", receipt.get("launch_verified_at") or stamp())
            if run.get("create_mode") == "recreate":
                run["live_since"] = stamp()
                if run.get("previous_campaigns"):
                    prior = run["previous_campaigns"][-1]
                    run["pending_retirement"] = {key: prior[key] for key in ("id", "name")}
            run["last_material_change_at"] = stamp()
            run.pop("campaign_configuration", None)
            schedule(run)
        elif op == "pause" and p["action"].get("retirement"):
            run.pop("pending_retirement", None)
            schedule(run)
        elif op == "pause" and p["action"]["kind"] == "campaign":
            run.update(status="stopped", outcome="STOP", next_review_at=None, proposal=None, blockers=[])
        else:
            run["last_material_change_at"] = stamp()
            run.pop("campaign_configuration", None)
            scaling = run["records"].get("scaling-proposal", {}).get("data", {}) if op == "budget" else {}
            schedule(run, review_date=scaling.get("next_review_on"))
        store.save(run, "execution_verified", {"operation": op, "proposal": p["id"], "receipt": receipt})
        if op == "activate":
            from .ledger import refresh
            refresh(store, run, client)
        return run


def resume(store, run_id, *, from_step=None):
    with store.lease("executor"):
        run = store.get(run_id)
        p = run.get("proposal")
        rules = policy(run["request"].get("brand"))
        aged = p and (approval_expired(run) if run.get("approval", {}).get("approved") else expired(p, rules))
        require(run["status"] == "blocked" or (run["status"] == "paused" and run["step"] == "existing-campaign-review")
                or (aged and run["status"] in
                {"awaiting_approval", "approved", "execution_blocked"}), "Run is active or has an unexpired proposal.")
        current_writes = run["write_journal"].get(p["id"], {}) if p else {}
        require(not current_writes, "Reconcile partial writes before replacing the approved proposal.")
        if run["step"] == "scaling-execution":
            run["step"] = "scaling-approval"
        if from_step:
            choices = GROUPS[run["group"]]
            current_idx = choices.index(run["step"]) if run["step"] in choices else len(choices)
            require(from_step in choices[:current_idx + 1], "Choose an earlier step within the blocked lifecycle group.")
            for step in choices[choices.index(from_step):]:
                if record := run["records"].pop(step, None):
                    run["history"].append({"step": step, "record": record})
            run["step"] = from_step
            if from_step != "safety-pause":
                run.pop("safety_pause", None)
                run.pop("safety_pause_attempted", None)
                run.pop("blocked_since", None)
        if run["step"] == "performance-analysis":
            run.pop("review_evidence", None)
        run.update(status="ready", outcome=None, proposal=None, blockers=[])
        run.pop("approval", None)
        store.save(run, "run_resumed", {"step": run["step"]})
        return run
