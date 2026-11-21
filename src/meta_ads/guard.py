"""Meta-only spending guard for a running host or an authenticated Meta job."""
from .authority import validate
from .meta import Meta, configured, require
from .state import stamp


def check(store, run, client_factory=None):
    from .gateway import enabled, invoke
    if client_factory is None and enabled(store):
        return invoke(store, run, "guard")[0]
    rules = (run["request"].get("brand") or {}).get("policy", {})
    authority = validate(rules.get("management_authority"), rules)
    require(not run.get("proposal"), "Reconcile the current proposal before a separate guard operation.")
    require(run.get("meta", {}).get("id"), "No enrolled campaign is available for the spending guard.")
    with configured(run["request"]["brand"]):
        client = (client_factory or (lambda account: Meta(account)))(run["request"]["account_id"])
        impact = client.budget()
        observed = client.scope(run["meta"]["id"], "campaign", run["meta"]["name"])
        run["last_guard_check"] = {"at": stamp(), "spent_month_minor": impact["spent_month_minor"],
                                   "monthly_authority_minor": authority["monthly_minor"],
                                   "configured_status": observed["configured_status"]}
        store.save(run, "spending_guard_checked", run["last_guard_check"])
        if impact["spent_month_minor"] < authority["monthly_minor"] or observed["configured_status"] != "ACTIVE":
            return run
        run["safety_pause"] = {"id": run["meta"]["id"], "name": run["meta"]["name"],
                                "reason": "Verified account-month spend reached the user's standing monthly allocation."}
        run.update(step="safety-pause", status="ready")
        store.save(run, "spending_guard_triggered", run["safety_pause"])
        from .workflow import prepare, execute
        updated = prepare(store, run, client)
        if updated["status"] == "approved":
            writer = client if client.writer else Meta(run["request"]["account_id"], writer=True)
            updated = execute(store, updated["id"], lambda _account: writer)
            if updated["status"] == "monitoring" and updated.get("last_receipt", {}).get("operation") == "pause" and not updated.get("proposal"):
                from datetime import datetime, timedelta
                from .meta import account_zone
                from .state import now
                zone = account_zone(client.details()["timezone_name"])
                local = now().astimezone(zone)
                following = (local.date().replace(day=28) + timedelta(days=4)).replace(day=1)
                updated["budget_pause"] = {"month": local.strftime("%Y-%m"), "reason": "Standing monthly allocation reached."}
                updated["next_review_at"] = datetime.combine(following, datetime.min.time(), tzinfo=zone).isoformat(timespec="seconds")
                updated.setdefault("schedules", {})["performance_review_at"] = updated["next_review_at"]
                store.save(updated, "monthly_budget_review_scheduled", {"next_review_at": updated["next_review_at"]})
            return updated
        return updated
