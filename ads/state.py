"""Persistent campaign state, current artifacts and an append-only execution log."""
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .meta import Stop, canonical, require

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = json.loads((ROOT / "ads/registry.json").read_text(encoding="utf-8"))
GROUPS = {group: [step for step, spec in REGISTRY.items() if spec["group"] == group]
          for group in ("research", "create", "optimize", "scale")}
REGISTRY["existing-campaign-review"] = {
    "path": ".agents/skills/meta-ads/references/existing-campaign-review.md", "group": "create", "gated": False,
    "fields": ["decision", "checks", "findings"],
    "types": {"decision": "string", "checks": "object", "findings": "array"},
}
REGISTRY["activation-check"] = {
    "path": "docs/activation.md", "group": "create", "gated": False,
    "fields": ["destination_ok", "purchase_event_ok", "checkout_ok", "preview_checks",
               "tracking_reference", "spend_control_reference"],
}


def now():
    return datetime.now(timezone.utc)


def stamp():
    return now().isoformat(timespec="seconds")


def parse_time(value):
    parsed = datetime.fromisoformat(value)
    require(parsed.tzinfo is not None, "Timestamp must have a time zone.")
    return parsed


class Store:
    def __init__(self, path=None):
        self.path = Path(path or os.environ.get("META_ADS_STATE_DB") or os.environ.get("PANCHKRUTI_STATE_DB")
                         or ROOT / ".state/ads.sqlite3").resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=20, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            PRAGMA journal_mode=WAL;
            PRAGMA synchronous=FULL;
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY, rev INTEGER NOT NULL, document TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
                at TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL
            );
        """)

    @contextmanager
    def tx(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self.db.rollback()
            raise
        else:
            self.db.commit()

    def log(self, run_id, kind, payload):
        self.db.execute("INSERT INTO events(run_id, at, kind, payload) VALUES (?, ?, ?, ?)",
                        (run_id, stamp(), kind, canonical(payload)))

    def create(self, request, *, reuse_existing=False):
        run_id = uuid.uuid4().hex[:16]
        run = {"id": run_id, "revision": 0, "request": request, "group": "research",
               "step": GROUPS["research"][0], "status": "ready", "outcome": None,
               "created_at": stamp(), "records": {}, "history": [], "review_number": 0,
               "next_review_at": None, "meta": {}, "proposal": None, "strategy_version": 0,
               "write_journal": {}, "next_campaign_budget": None}
        with self.tx():
            for other in self.list():
                existing = other["request"]
                if existing["account_id"] == request["account_id"] and existing["name"] == request["name"]:
                    if reuse_existing:
                        brand = existing.get("brand") or {}
                        requested_brand = request.get("brand") or {}
                        require(existing["product_id"] == request["product_id"]
                                and existing.get("variant_id") == request.get("variant_id")
                                and (brand.get("brand_id"), brand.get("shopify_shop"))
                                == (requested_brand.get("brand_id"), requested_brand.get("shopify_shop")),
                                "The saved campaign is already assigned to a different brand or product.")
                        return other
                    raise Stop(f"Campaign name already has run {other['id']}. Resume that run or use another name.")
            self.db.execute("INSERT INTO runs VALUES (?, 0, ?)", (run_id, canonical(run)))
            self.log(run_id, "request_received", request)
        return run

    def get(self, run_id):
        row = self.db.execute("SELECT document FROM runs WHERE id = ?", (run_id,)).fetchone()
        require(row is not None, "Run not found.")
        return json.loads(row["document"])

    def list(self):
        return [json.loads(row["document"]) for row in self.db.execute("SELECT document FROM runs ORDER BY rowid")]

    def save(self, run, event, payload):
        revision = run["revision"]
        run["revision"] += 1
        try:
            with self.tx():
                cursor = self.db.execute("UPDATE runs SET rev = ?, document = ? WHERE id = ? AND rev = ?",
                                         (run["revision"], canonical(run), run["id"], revision))
                require(cursor.rowcount == 1, "Run changed concurrently. Reload the current state.")
                self.log(run["id"], event, payload)
        except BaseException:
            run["revision"] = revision
            raise

    def events(self, run_id):
        self.get(run_id)
        return [{**dict(row), "payload": json.loads(row["payload"])} for row in self.db.execute(
            "SELECT sequence, at, kind, payload FROM events WHERE run_id = ? ORDER BY sequence", (run_id,))]

    @contextmanager
    def lease(self, name):
        # A separate SQLite transaction supplies a process lock which the OS releases on exit.
        require(name in {"worker", "executor"}, "Invalid lease.")
        path = self.path.with_suffix(self.path.suffix + f".{name}")
        db = sqlite3.connect(path, timeout=0, isolation_level=None)
        try:
            try:
                db.execute("BEGIN EXCLUSIVE")
            except sqlite3.OperationalError:
                raise Stop(f"Another {name} is already running against this database.") from None
            yield
        finally:
            db.close()
