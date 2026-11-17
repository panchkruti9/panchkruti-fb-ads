"""Validate Meta campaign plans and review performance using verified observations."""

import argparse
import hashlib
import json
import re
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path


DECISIONS = {
    "campaign_objectives": ("outcome", "objective_and_event"),
    "audience_research": ("buyer", "motivation", "barrier"),
    "customer_journey": ("message", "proof", "next_action"),
    "campaign_architecture": ("campaign_role", "budget_owner"),
    "audience_targeting": ("eligible_market", "audience_controls"),
    "ad_set_structure": ("delivery_groups", "grouping_reason"),
    "creative_and_copy": ("creative_concepts", "product_and_claim_review", "destination"),
    "budget_allocation": ("allocation_basis", "approved_limit"),
    "testing": ("hypothesis", "comparison", "metric", "stopping_rule"),
    "retargeting": ("eligibility", "message", "audience_size"),
    "optimization_and_scaling": ("minimum_evidence", "reversal_condition"),
    "tracking_and_reporting": ("event_check", "business_report"),
}

RESULT_BASIS_FIELDS = {"campaign_key", "attribution_model", "result_definition", "time_zone"}
BRAND_RULES = Path(__file__).resolve().parents[1] / "docs/meta-ads/brand-rules.md"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def require_agi_name(name, label):
    require(isinstance(name, str) and name.startswith("agi-") and name[4:].strip(),
            f"{label} name must start with agi- and include a label.")


def read(path):
    return json.loads(
        Path(path).read_text(encoding="utf-8-sig"),
        parse_constant=lambda value: require(False, f"Invalid JSON number: {value}"),
    )


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(path)


def fingerprint(data):
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def integer(value, label, minimum=0):
    require(type(value) is int and value >= minimum, f"{label} must be an integer ≥ {minimum}.")
    return value


def read_brand_limits(path=BRAND_RULES):
    fields = ("Monthly budget maximum", "Daily budget minimum", "Daily budget maximum")
    table = path.read_text(encoding="utf-8-sig")
    amounts = []
    for label in fields:
        rows = re.findall(rf"^\| {label} \| ([^|]+) \|$", table, flags=re.MULTILINE)
        require(len(rows) == 1, f"Set {label} once in brand-rules.md.")
        value = rows[0].strip()
        if value == "Pending":
            return None
        amount = value.removeprefix("₹").strip()
        require(re.fullmatch(r"[0-9][0-9,]*(?:\.[0-9]{1,2})?", amount),
                f"Enter {label} in rupees in brand-rules.md.")
        amounts.append(int(Decimal(amount.replace(",", "")) * 100))
    monthly_max, daily_min, daily_max = amounts
    require(monthly_max > 0 and daily_max > 0 and daily_min <= daily_max,
            "Check the monthly maximum and daily range in brand-rules.md.")
    return {"monthly_max": monthly_max, "daily_min": daily_min, "daily_max": daily_max}


def check_brand_budget(limits, evidence, daily_minor, as_of):
    require(limits is not None, "Enter the three budget limits in brand-rules.md.")
    require(isinstance(evidence, dict) and evidence.get("as_of") == as_of,
            "Supply an account budget summary dated today in the Meta account time zone.")
    spent = integer(evidence.get("spent_minor"), "Meta spend so far this month")
    other_min = integer(evidence.get("other_daily_min_minor"), "Other ads’ lowest daily budget")
    other_max = integer(evidence.get("other_daily_max_minor"), "Other ads’ highest daily budget", other_min)
    other_remaining = integer(evidence.get("other_remaining_minor"), "Other ads’ remaining planned spend")
    require(limits["daily_min"] <= other_min + daily_minor and other_max + daily_minor <= limits["daily_max"],
            "The combined daily budget would fall outside the brand range.")
    day = date.fromisoformat(as_of)
    remaining_days = monthrange(day.year, day.month)[1] - day.day + 1
    projected = spent + other_remaining + daily_minor * remaining_days
    require(projected <= limits["monthly_max"], "The combined plan would exceed the brand’s monthly maximum.")
    return {"daily_min_minor": other_min + daily_minor, "daily_max_minor": other_max + daily_minor,
            "projected_month_minor": projected}


def positive_decimal(value, label):
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"{label} must be a number.") from exc
    require(result.is_finite() and result > 0, f"{label} must be positive.")
    return result


def meta_id(value, label):
    require(isinstance(value, str) and re.fullmatch(r"[0-9]{1,32}", value), f"Invalid {label}.")
    return value


def validate(plan):
    require(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", plan["id"]), "Invalid plan ID.")
    require(plan["schema_version"] == 1, "Unsupported plan version.")
    meta_id(plan["account_id"], "account ID")
    require(re.fullmatch(r"[A-Z]{3}", plan["currency"]), "Use the account's ISO currency.")
    require(set(plan["decisions"]) == set(DECISIONS), "Supply exactly the 12 campaign decisions.")
    open_items = []
    for name, item in plan["decisions"].items():
        status = item["status"]
        require(status in {"decided", "deferred", "open"}, f"Invalid status for {name}.")
        require(isinstance(item["reason"], str) and item["reason"].strip(), f"Explain {name}.")
        if status == "decided":
            details = item.get("details")
            for field in DECISIONS[name]:
                require(isinstance(details, dict) and isinstance(details.get(field), str)
                        and details[field].strip(), f"{name} needs a value for {field}.")
            evidence = item.get("evidence")
            require(isinstance(evidence, list) and evidence
                    and all(isinstance(source, str) and source.strip() for source in evidence),
                    f"{name} needs a source reference.")
        if status == "deferred":
            require(isinstance(item.get("revisit"), str) and item["revisit"].strip(),
                    f"Record when to revisit {name}.")
        if status == "open" or (status == "deferred" and name not in {"retargeting", "testing"}):
            open_items.append(name)
    if plan.get("target"):
        meta_id(plan["target"]["id"], "budget target ID")
        require(plan["target"]["type"] in {"campaign", "ad_set"}, "Invalid budget owner.")
    if plan.get("budget"):
        budget = plan["budget"]
        integer(budget["max_daily_minor"], "Daily budget cap", 1)
        integer(budget["scale_step_minor"], "Scale step", 1)
        require(budget["scale_step_minor"] <= budget["max_daily_minor"], "Scale step exceeds cap.")
    if plan.get("review"):
        criteria = plan["review"]
        require(criteria["metric"] in {"cost_per_result", "result_count", "value_per_spend"},
                "Unsupported decision metric.")
        integer(criteria["minimum_results"], "Minimum results per period", 1)
        integer(criteria["days"], "Window length", 1)
        integer(criteria["conversion_lag_days"], "Conversion lag")
        integer(criteria["cooldown_days"], "Budget cooldown", criteria["days"])
        require(isinstance(criteria["metric_source"], str) and criteria["metric_source"].strip()
                and criteria["metric_source"] != "meta", "Name a business data source.")
        basis = criteria.get("result_basis")
        require(isinstance(basis, dict) and set(basis) == RESULT_BASIS_FIELDS
                and all(isinstance(value, str) and value.strip() for value in basis.values()),
                "Define the campaign filter, attribution model, result definition, and time zone.")
        require(basis["campaign_key"].strip().lower() not in {"all", "*", "storewide", "store-wide"},
                "Use a campaign-specific business filter.")
        target = positive_decimal(criteria["target"], "Primary target")
        reversal = positive_decimal(criteria["reversal_target"], "Reversal target")
        require(reversal >= target if criteria["metric"] == "cost_per_result" else reversal <= target,
                "Reversal must be at or worse than the primary target.")
    return open_items


def metric(window, name):
    count = integer(window["results"], "Business results")
    spend = integer(window["spend_minor"], "Meta spend")
    if name == "result_count":
        return Decimal(count)
    if name == "cost_per_result" and count:
        return Decimal(spend) / count
    if name == "value_per_spend" and spend:
        return Decimal(integer(window["value_minor"], "Business value")) / spend
    return None


def make_proposal(plan, snapshot, old, new, action):
    as_of = date.fromisoformat(snapshot["as_of"])
    proposal = {
        "action": action, "plan_id": plan["id"], "plan_hash": fingerprint(plan),
        "account_id": plan["account_id"], "target": plan["target"], "currency": plan["currency"],
        "from_daily_minor": old, "to_daily_minor": new,
        "snapshot_hash": fingerprint(snapshot),
        "expires_on": (as_of + timedelta(days=2)).isoformat(),
    }
    return {**proposal, "approval_id": fingerprint(proposal)}


def review(plan, snapshot):
    open_items = validate(plan)
    for field in ("account_id", "currency", "target"):
        require(snapshot[field] == plan[field], f"Snapshot {field} does not match the plan.")
    require_agi_name(snapshot.get("target_name"), "Review target")
    criteria = plan["review"]
    as_of = date.fromisoformat(snapshot["as_of"])
    current = snapshot["current"]
    previous = snapshot["previous"]
    end = as_of - timedelta(days=1 + criteria["conversion_lag_days"])
    start = end - timedelta(days=criteria["days"] - 1)
    previous_end = start - timedelta(days=1)
    previous_start = start - timedelta(days=criteria["days"])
    for window, expected_start, expected_end in ((current, start, end), (previous, previous_start, previous_end)):
        require(window["start"] == expected_start.isoformat() and window["end"] == expected_end.isoformat(),
                "Periods must be complete, adjacent, and use the configured lag.")

    def outcome(decision, reason, **extra):
        return {"plan_id": plan["id"], "as_of": as_of.isoformat(), "decision": decision,
                "reason": reason, "next_review_on": (as_of + timedelta(days=1)).isoformat(),
                "periods": {"previous": previous, "current": current}, **extra}

    if open_items:
        return outcome("investigate", f"Plan needs decisions for {', '.join(open_items)}.")
    if snapshot.get("business_source") != criteria["metric_source"] or any(
        window.get("results") is None or window.get("spend_minor") is None
        or (criteria["metric"] == "value_per_spend" and window.get("value_minor") is None)
        for window in (previous, current)
    ):
        reason = snapshot.get("evidence_issue") or "The required business outcome or spend is unavailable."
        return outcome("investigate", reason)
    if snapshot.get("tracking_verified") is not True or snapshot.get("delivery_healthy") is not True:
        return outcome("investigate", "Verify tracking and delivery before judging performance.")
    if snapshot.get("result_basis") != criteria["result_basis"] or not snapshot.get("evidence_source"):
        return outcome("investigate", "Verify the campaign filter, attribution, result definition, time zone, and evidence.")
    if any(integer(window["spend_minor"], "Meta spend") == 0 for window in (previous, current)):
        return outcome("investigate", "Verify positive campaign spend in both periods before making a budget decision.")
    target = positive_decimal(criteria["target"], "Primary target")
    counts = [integer(window["results"], "Business results") for window in (previous, current)]
    latest = snapshot.get("last_budget_change")
    if latest:
        changed = date.fromisoformat(latest["applied_on"])
        require(changed <= as_of, "Budget change cannot be in the future.")
        if start <= changed or (as_of - changed).days < criteria["cooldown_days"]:
            return outcome("hold", "Wait for a full comparison period after the budget change.")
        if latest["to_daily_minor"] != snapshot.get("daily_budget_minor"):
            return outcome("investigate", "Budget changed outside the recorded workflow.")

    if min(counts) < criteria["minimum_results"]:
        if latest and latest["action"] == "scale" and counts[1] < counts[0]:
            reversal = positive_decimal(criteria["reversal_target"], "Reversal target")
            observed = metric(current, criteria["metric"])
            if criteria["metric"] == "cost_per_result":
                breached = (observed > reversal if observed is not None
                            else current["spend_minor"] >= reversal)
            else:
                breached = observed is not None and observed < reversal
            if breached:
                return outcome(
                    "investigate",
                    "Orders fell after the last budget increase. Review a possible reversal; "
                    "result volume is below the minimum for a budget proposal.",
                )
        if criteria["metric"] == "cost_per_result" and counts[1] < criteria["minimum_results"] and (
            current["spend_minor"] >= target * criteria["minimum_results"]
        ):
            return outcome("investigate", "Spend reached the planned cost for minimum volume without enough results.")
        return outcome("hold", "Too few business results to make a budget decision.")
    before, after = (metric(window, criteria["metric"]) for window in (previous, current))
    if before is None or after is None:
        return outcome("hold", "The primary metric cannot be calculated.")
    reversal = positive_decimal(criteria["reversal_target"], "Reversal target")
    values = {"metric": criteria["metric"], "previous_value": str(before), "current_value": str(after),
              "target_value": str(target)}
    lower_is_better = criteria["metric"] == "cost_per_result"
    meets = (lambda value, threshold: value <= threshold) if lower_is_better else (
        lambda value, threshold: value >= threshold)
    old = snapshot.get("daily_budget_minor")
    if old is None:
        return outcome("investigate", "Verify the current daily budget.", **values)
    old = integer(old, "Current daily budget", 1)
    cap = plan["budget"]["max_daily_minor"]
    if old > cap:
        return outcome("investigate", "Current daily budget exceeds the approved limit.", **values)
    if latest and latest["action"] == "scale" and not meets(after, reversal):
        return outcome("propose_reverse", "The latest increase breached the reversal threshold.",
                       proposal=make_proposal(plan, snapshot, old, latest["from_daily_minor"], "reverse"), **values)
    if not all(meets(value, target) for value in (before, after)):
        return outcome("investigate", "Check where results fell short before proposing a new test.", **values)
    if criteria["metric"] == "result_count":
        return outcome("hold", "Use a cost or value target before increasing spend.", **values)
    if snapshot.get("capacity_verified") is not True:
        return outcome("hold", "Verify capacity for more volume before increasing spend.", **values)
    new = min(cap, old + plan["budget"]["scale_step_minor"])
    if new == old:
        return outcome("hold", "Budget is already at the authorized cap.", **values)
    return outcome("propose_scale", "Both periods meet target and capacity is verified.",
                   proposal=make_proposal(plan, snapshot, old, new, "scale"), **values)


def main():
    from meta_ads_execution import apply_budget, build, build_operations, launch, live_snapshot, pause_ad, previews

    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("validate", "review", "live-review", "apply-budget", "build", "previews", "launch", "pause-ad"):
        sub = commands.add_parser(command)
        sub.add_argument("plan")
        if command in {"review", "apply-budget"}:
            sub.add_argument("snapshot")
        if command == "live-review":
            sub.add_argument("--evidence")
        if command in {"build", "apply-budget", "launch", "pause-ad"}:
            sub.add_argument("--confirm", help="Exact approval ID. Omit for a preview.")
            sub.add_argument("--state", help="Persistent local execution record.")
        if command == "previews":
            sub.add_argument("--state", required=True)
        if command == "launch":
            sub.add_argument("qa", help="Saved placement, destination and tracking review.")
        if command == "apply-budget":
            sub.add_argument("proposal")
        if command == "pause-ad":
            sub.add_argument("ad_id")
            sub.add_argument("ad_name", help="Exact agi- name of the ad.")
            sub.add_argument("--reason", required=True, help="Evidence and reason for the pause.")
        sub.add_argument("--output")
    args = parser.parse_args()
    try:
        plan = read(args.plan)
        open_items = validate(plan)
        if args.command == "validate":
            ready = not open_items and bool(plan.get("budget")) and bool(plan.get("build"))
            if ready:
                build_operations(plan)
            result = {"plan_id": plan["id"], "valid": True, "open_decisions": open_items,
                      "paused_build_settings_valid": ready}
        elif args.command == "review":
            result = review(plan, read(args.snapshot))
        elif args.command == "live-review":
            snapshot = live_snapshot(plan, read(args.evidence) if args.evidence else {})
            result = review(plan, snapshot)
            if "proposal" in result:
                proposal = result["proposal"]
                try:
                    result["budget_check"] = check_brand_budget(
                        read_brand_limits(), snapshot.get("account_budget"),
                        proposal["to_daily_minor"], snapshot["as_of"])
                except ValueError as error:
                    result.pop("proposal")
                    result.update(decision="hold", reason=str(error))
            result["snapshot"] = snapshot
        elif args.command == "apply-budget":
            result = apply_budget(plan, read(args.snapshot), read(args.proposal), args.confirm, args.state)
        elif args.command == "build":
            result = build(plan, args.confirm, args.state)
        elif args.command == "previews":
            result = previews(plan, read(args.state))
        elif args.command == "pause-ad":
            result = pause_ad(plan, args.ad_id, args.ad_name, args.reason, args.confirm, args.state)
        else:
            result = launch(plan, read(args.qa), args.state, args.confirm)
        if args.output:
            save(args.output, result)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except (KeyError, TypeError, ValueError, OSError, RuntimeError) as error:
        parser.exit(1, f"Meta Ads: {error}\n")


if __name__ == "__main__":
    main()
