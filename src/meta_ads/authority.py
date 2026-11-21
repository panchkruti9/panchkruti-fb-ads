"""Explicit standing management authority, separate from maximum policy limits."""
from .meta import fingerprint, minor, policy, require
from .state import parse_time, stamp


def validate(value, rules):
    require(isinstance(value, dict) and set(value) == {
        "daily_minor", "monthly_minor", "reference", "approved_at"},
        "Management authority needs daily/monthly allocations and the user's dated authorization reference.")
    require(minor(value["daily_minor"], positive=True) <= rules["maximum_daily_minor"]
            and minor(value["monthly_minor"], positive=True) <= rules["maximum_monthly_minor"],
            "Management allocation exceeds policy limits.")
    require(value["daily_minor"] <= value["monthly_minor"], "Daily authority exceeds monthly authority.")
    require(isinstance(value["reference"], str) and value["reference"].strip(), "Missing user authorization reference.")
    parse_time(value["approved_at"])
    return value


def owner_required(run, proposal):
    rules = policy(run["request"].get("brand"))
    authority = rules.get("management_authority")
    if not authority:
        operation = "activate" if proposal["operation"] == "resume" else proposal["operation"]
        return operation in rules.get("owner_approval_actions", {"activate", "budget"})
    validate(authority, rules)
    if proposal["operation"] in set(rules.get("owner_approval_actions", [])) - {"activate", "budget"}:
        return True
    impact = proposal.get("impact") or {}
    if impact.get("daily_minor", 0) > authority["daily_minor"] or impact.get("monthly_minor", 0) > authority["monthly_minor"]:
        return True
    # An account-wide funding-control change is not ordinary AGI redistribution.
    if proposal.get("action", {}).get("spend_control_change"):
        return True
    return False


def grant(store, run_id, *, daily_minor, monthly_minor, reference):
    """Record a real user instruction; callers must not manufacture consent from research."""
    with store.lease("executor"):
        run = store.get(run_id)
        require(not run.get("proposal"), "Resolve the existing proposal before changing management authority.")
        require(run["request"].get("brand"), "Standing authority requires a saved brand profile.")
        rules = run["request"]["brand"]["policy"]
        value = validate({"daily_minor": daily_minor, "monthly_minor": monthly_minor,
                          "reference": reference, "approved_at": stamp()}, rules)
        before = rules.get("management_authority")
        rules["management_authority"] = value
        run["decision_contract_version"] = 2
        store.save(run, "management_authority", {"before": before, "after": value,
                    "policy_version": fingerprint(rules)})
        return run
