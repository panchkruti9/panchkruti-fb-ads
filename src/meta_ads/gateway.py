"""Encrypted, resumable Meta jobs on the repository's GitHub runner."""
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import subprocess
import time
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from .meta import Stop, canonical, fingerprint, require
from .meta_catchup import command, decrypt, encrypt, setup
from .state import ROOT, Store, stamp

TAG = "meta-jobs"
WORKFLOW = "meta-jobs.yml"
MAX_BUNDLE = 256 * 1024 * 1024
OPERATIONS = {"readiness", "account", "collect", "health", "review", "prepare", "activation",
              "budget-validation", "execute", "reconcile", "verify"}


def directory(store):
    return store.path.parent / "meta-gateway"


def enabled(store):
    return not os.environ.get("META_ADS_GITHUB_JOB") and (directory(store) / "config.json").is_file()


def settings(store):
    config = json.loads((directory(store) / "config.json").read_text(encoding="utf-8"))
    require(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", config["repo"]), "Invalid Meta job repository.")
    return config


def gh(args, *, stdin=None):
    environment = os.environ.copy()
    if not environment.get("GH_TOKEN") and "--repo" in args:
        owner = args[args.index("--repo") + 1].split("/", 1)[0]
        token = subprocess.run(["gh", "auth", "token", "--hostname", "github.com", "--user", owner],
                               capture_output=True, timeout=15)
        if token.returncode == 0:
            environment["GH_TOKEN"] = token.stdout.decode().strip()
    try:
        response = subprocess.run(["gh", *args], input=stdin, env=environment, capture_output=True, timeout=120, check=True)
    except (OSError, subprocess.SubprocessError):
        raise Stop("The GitHub Meta job request did not complete. Its private job record can be resumed.") from None
    return response.stdout


def digest(value, key):
    return hmac.new(key.encode(), canonical(value).encode(), hashlib.sha256).hexdigest()


def provision(store, repo):
    """Configure machine credentials once using the existing authenticated GitHub account."""
    require(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo), "Use owner/repository.")
    location = directory(store)
    client = location / "client"
    server = location / "server"
    setup(client)
    setup(server)
    keyfile = location / "approval.key"
    if not keyfile.exists():
        keyfile.write_text(secrets.token_hex(32), encoding="ascii")
        keyfile.chmod(0o600)
    key = keyfile.read_text(encoding="ascii")
    gh(["secret", "set", "META_JOB_DECRYPT_KEY", "--repo", repo], stdin=(server / "key.pem").read_bytes())
    gh(["secret", "set", "META_ADS_OPERATOR_KEY", "--repo", repo], stdin=key.encode())
    gh(["variable", "set", "META_JOB_CERT", "--repo", repo], stdin=(server / "cert.pem").read_bytes())
    try:
        gh(["release", "view", TAG, "--repo", repo])
    except Stop:
        gh(["release", "create", TAG, "--draft", "--title", "Encrypted Meta jobs",
            "--notes", "Encrypted job inputs and recovery checkpoints.", "--repo", repo])
    config = {"repo": repo}
    (location / "config.json").write_text(canonical(config), encoding="utf-8")
    return {"status": "configured", "repo": repo}


def operator_key(store):
    path = directory(store) / "approval.key"
    require(path.is_file(), "Run meta-ads gateway-setup once with the existing GitHub connection.")
    return path.read_text(encoding="ascii")


def job_folder(store, job_id):
    require(re.fullmatch(r"[a-f0-9]{32}", job_id), "Invalid Meta job identifier.")
    path = store.path.parent / "meta-jobs" / job_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def pack_request(store, run, operation, options):
    require(operation in OPERATIONS, "Unsupported Meta operation.")
    scope = {"run": run["id"], "revision": run["revision"], "operation": operation, "options": options}
    if operation in {"readiness", "account", "collect", "review", "verify"}:
        scope["read_window"] = int(time.time() // 300)
    job_id = fingerprint(scope)[:32]
    folder = job_folder(store, job_id)
    manifest = folder / "request.json"
    if manifest.exists():
        return job_id, json.loads(manifest.read_text(encoding="utf-8"))
    request = {"version": 1, "job_id": job_id, "operation": operation, "options": options,
               "run": run, "base_revision": run["revision"], "created_at": stamp(),
               "reply_certificate": (directory(store) / "client/cert.pem").read_text(encoding="ascii")}
    request["signature"] = digest(request, operator_key(store))
    temporary = folder / "request.zip"
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("request.json", canonical(request))
        if operation == "execute" and (run.get("proposal") or {}).get("operation") == "build":
            from .connected import media_path, read_media
            for asset in run["proposal"]["action"]["plan"]["assets"].values():
                raw = read_media(store, run, asset)
                archive.writestr("media/" + media_path(store, run, asset).name, raw)
    require(temporary.stat().st_size <= MAX_BUNDLE, "Scope this Meta job to fewer media files.")
    encrypt(temporary, folder / "request.cms", directory(store) / "server/cert.pem")
    temporary.unlink()
    manifest.write_text(canonical(request), encoding="utf-8")
    return job_id, request


def download_asset(repo, name, target):
    gh(["release", "download", TAG, "--repo", repo, "--pattern", name, "--dir", str(target), "--clobber"])
    return target / name


def submit_job(store, run, operation, options=None, *, wait_seconds=180):
    """Submit one predefined operation. A timeout leaves a resumable job on disk."""
    config = settings(store)
    job_id, request = pack_request(store, run, operation, options or {})
    folder = job_folder(store, job_id)
    result_name = job_id + "-result.cms"
    state_path = folder / "transport.json"
    assets = json.loads(gh(["release", "view", TAG, "--repo", config["repo"], "--json", "assets"]))["assets"]
    names = {item["name"] for item in assets}
    if not state_path.exists():
        name = job_id + "-request.cms"
        uploaded = folder / name
        shutil.copy2(folder / "request.cms", uploaded)
        if name not in names:
            gh(["release", "upload", TAG, str(uploaded), "--repo", config["repo"]])
        state_path.write_text(canonical({"submitted_at": stamp()}), encoding="utf-8")
    if result_name not in names:
        gh(["workflow", "run", WORKFLOW, "--repo", config["repo"], "--ref", "main",
            "-f", "job_id=" + job_id])
    until = time.monotonic() + wait_seconds
    while time.monotonic() < until:
        assets = json.loads(gh(["release", "view", TAG, "--repo", config["repo"], "--json", "assets"]))
        if any(item["name"] == result_name for item in assets["assets"]):
            encrypted = download_asset(config["repo"], result_name, folder)
            result = decrypt(encrypted, directory(store) / "client")
            signature = result.pop("signature", "")
            require(hmac.compare_digest(signature, digest(result, operator_key(store)))
                    and result["job_id"] == job_id
                    and result["request_hash"] == fingerprint(request),
                    "The Meta job receipt could not be authenticated.")
            (folder / "result.json").write_text(canonical(result), encoding="utf-8")
            return result
        time.sleep(min(8, max(0, until - time.monotonic())))
    raise Stop(f"Meta job {job_id} is queued or running. Resume the same task to collect its result.")


def import_result(store, run, result):
    remote = result["run"]
    require(remote["id"] == run["id"] and remote["request"] == run["request"], "Meta job returned another scope.")
    with store.lease("executor"):
        current = store.get(run["id"])
        applied = current.get("meta_jobs", [])
        if result["job_id"] in applied:
            return current
        require(current["revision"] == result["base_revision"], "The run changed during the Meta job. Reconcile its receipt before continuing.")
        remote["revision"] = current["revision"] + 1
        remote["meta_jobs"] = [*applied[-99:], result["job_id"]]
        with store.tx():
            cursor = store.db.execute("UPDATE runs SET rev=?,document=? WHERE id=? AND rev=?",
                                      (remote["revision"], canonical(remote), run["id"], current["revision"]))
            require(cursor.rowcount == 1, "Reload the changed run before importing the Meta job.")
            for event in result.get("events", []):
                store.db.execute("INSERT INTO events(run_id,at,kind,payload) VALUES (?,?,?,?)",
                                 (run["id"], event["at"], event["kind"], canonical(event["payload"])))
            store.log(run["id"], "meta_job_result", {"job_id": result["job_id"], "operation": result["operation"],
                                                    "status": result["status"]})
        store.refresh_logs()
    return remote


def invoke(store, run, operation, options=None):
    result = submit_job(store, run, operation, options)
    if result.get("events"):
        updated = import_result(store, run, result)
    else:
        updated = run
        if not any(event["kind"] == "meta_job_read" and event["payload"].get("job_id") == result["job_id"]
                   for event in store.events(run["id"])):
            with store.tx():
                store.log(run["id"], "meta_job_read", {"job_id": result["job_id"], "operation": operation,
                                                      "detail": f"GitHub Meta {operation}: {result['status']}"})
            store.refresh_logs()
    if result["status"] == "failed":
        raise Stop(result["error"])
    return updated, result.get("data")


def safe_extract(archive, target):
    total = 0
    for info in archive.infolist():
        total += info.file_size
        path = (target / info.filename).resolve()
        require(path.is_relative_to(target.resolve()) and not info.is_dir() and total <= MAX_BUNDLE,
                "Invalid Meta job bundle.")
        path.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(info) as source, path.open("wb") as destination:
            shutil.copyfileobj(source, destination)


def perform(store, run, operation, options):
    from .meta import Meta, configured
    from .worker import activation, collector, monitor_waiting, review_inputs
    from .workflow import execute, prepare
    from .execution import operator_setup, reconcile
    from .connected import current_media
    with configured(run["request"].get("brand")):
        client = Meta(run["request"]["account_id"])
        if operation == "readiness":
            client.details()
            writer = Meta(run["request"]["account_id"], writer=True)
            writer.details()
            ready = operator_setup(run)
            return ready
        if operation == "account":
            return {"details": client.details(), "report": client.account_report(), "budget": client.budget()}
        if operation == "collect":
            context, _ = collector(run, run["step"], None, lambda _: client, meta_only=True)
            return context
        if operation == "health":
            monitor_waiting(store, run, lambda _: client)
            return None
        if operation == "review":
            def absent(*_args, **_kwargs):
                raise Stop("Shopify windows are provided by the connected agent.")
            return review_inputs(run, client, order_reader=absent)
        if operation == "prepare":
            assets = current_media(run)["assets"] if run["step"] == "campaign-build" else None
            prepare(store, run, client, assets=assets)
            return None
        if operation == "activation":
            from .workflow import submit
            submit(store, run, activation(run, client))
            return None
        if operation == "budget-validation":
            from .worker import tick
            tick(store, run["id"])
            return None
        if operation == "execute":
            execute(store, run["id"])
            return None
        if operation == "reconcile":
            reconcile(store, run["id"], options["operation"], client, options.get("id"),
                      absent=options.get("absent", False), reference=options.get("reference"))
            return None
        if operation == "verify":
            from .meta_catchup import draft_readback
            target = run["meta"]
            require(target.get("id"), "There is no saved campaign to verify.")
            campaign = client.scope(target["id"], "campaign", target["name"])
            return {"campaign": campaign, "draft": draft_readback(client, target)}
    raise Stop("Unsupported Meta job operation.")


def run_job(job_id, location):
    """Execute on GitHub only. Checkpoints persist before each provider mutation."""
    repo = os.environ["GITHUB_REPOSITORY"]
    require(re.fullmatch(r"[a-f0-9]{32}", job_id), "Invalid Meta job identifier.")
    private = location / "server"
    private.mkdir(parents=True, exist_ok=True)
    (private / "key.pem").write_text(os.environ["META_JOB_DECRYPT_KEY"], encoding="ascii")
    (private / "cert.pem").write_text(os.environ["META_JOB_CERT"], encoding="ascii")
    encrypted = download_asset(repo, job_id + "-request.cms", location)
    # CMS decrypt is binary here because the request is a ZIP containing approved originals.
    from .meta_catchup import openssl
    raw = command([openssl(), "cms", "-decrypt", "-binary", "-inform", "DER", "-in", str(encrypted),
                   "-recip", str(private / "cert.pem"), "-inkey", str(private / "key.pem")], "Cannot decrypt Meta job.")
    require(len(raw) <= MAX_BUNDLE, "Meta job exceeds size limit.")
    import io
    extracted = location / "input"
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        safe_extract(archive, extracted)
    request = json.loads((extracted / "request.json").read_text(encoding="utf-8"))
    signature = request.pop("signature")
    key = os.environ["META_ADS_OPERATOR_KEY"]
    require(hmac.compare_digest(signature, digest(request, key)) and request["job_id"] == job_id
            and request["version"] == 1 and request["operation"] in OPERATIONS, "Invalid signed Meta job.")
    request["signature"] = signature
    request_hash = fingerprint(request)
    run = request["run"]
    require(re.fullmatch(r"[a-f0-9]{16}", run["id"]) and run["revision"] == request["base_revision"],
            "Invalid Meta job run revision.")
    require(run["request"]["account_id"] == os.environ["META_AD_ACCOUNT_ID"].removeprefix("act_"), "Meta job account mismatch.")
    store = Store(location / "lifecycle.sqlite3")
    try:
        assets = json.loads(gh(["release", "view", TAG, "--repo", repo, "--json", "assets"]))["assets"]
        if any(item["name"] == job_id + "-result.cms" for item in assets):
            return
        checkpoints = sorted(a["name"] for a in assets if re.fullmatch(job_id + r"-checkpoint-[0-9]{6}\.cms", a["name"]))
        events = []
        checkpoint_no = 0
        if checkpoints:
            previous = decrypt(download_asset(repo, checkpoints[-1], location), private)
            require(previous["request_hash"] == request_hash, "Checkpoint belongs to another job request.")
            run, events = previous["run"], previous["events"]
            checkpoint_no = int(checkpoints[-1].removesuffix(".cms").rsplit("-", 1)[1])
        store.db.execute("INSERT INTO runs VALUES (?,?,?)", (run["id"], run["revision"], canonical(run)))
        media = extracted / "media"
        if media.is_dir():
            target = location / "connected-media" / run["id"]
            target.mkdir(parents=True, exist_ok=True)
            for source in media.iterdir():
                shutil.copy2(source, target / source.name)
        original_save = store.save

        def persist(current, event, payload):
            nonlocal checkpoint_no
            original_save(current, event, payload)
            checkpoint_no += 1
            checkpoint = {"request_hash": request_hash, "run": store.get(run["id"]),
                          "events": events + store.events(run["id"])}
            plain = location / "checkpoint.json"
            plain.write_text(canonical(checkpoint), encoding="utf-8")
            output = location / f"{job_id}-checkpoint-{checkpoint_no:06d}.cms"
            encrypt(plain, output, private / "cert.pem")
            gh(["release", "upload", TAG, str(output), "--repo", repo])

        store.save = persist
        reply = {"job_id": job_id, "request_hash": request_hash, "base_revision": request["base_revision"],
                 "operation": request["operation"], "status": "verified"}
        try:
            reply["data"] = perform(store, run, request["operation"], request["options"])
        except (Stop, OSError, KeyError, ValueError, TypeError) as error:
            reply.update(status="failed", error=str(error) if isinstance(error, Stop) else f"Meta job failed ({type(error).__name__}).")
        reply["run"] = store.get(run["id"])
        if reply["run"]["status"] == "execution_blocked":
            reply.update(status="failed", error="; ".join(reply["run"].get("blockers", [])))
        reply["events"] = events + store.events(run["id"])
        reply["signature"] = digest(reply, key)
        recipient = location / "recipient.pem"
        recipient.write_text(request["reply_certificate"], encoding="ascii")
        plain = location / "result.json"
        plain.write_text(canonical(reply), encoding="utf-8")
        output = location / (job_id + "-result.cms")
        encrypt(plain, output, recipient)
        gh(["release", "upload", TAG, str(output), "--repo", repo, "--clobber"])
    finally:
        store.db.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job_id")
    args = parser.parse_args()
    try:
        with TemporaryDirectory(prefix="meta-job-") as temporary:
            run_job(args.job_id, Path(temporary))
    except Exception:
        # Job inputs and provider IDs stay in the encrypted result and private local log.
        parser.exit(2, "The Meta job could not complete. Resume the existing job and inspect its private receipt.\n")


if __name__ == "__main__":
    main()
