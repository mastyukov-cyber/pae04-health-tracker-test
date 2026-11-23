#!/usr/bin/env python3
"""HOME-28 privacy-egress scoped Chromium QA. SOURCE ONLY / NOT RUN.

Only for a separately authorized GitHub Actions run against the exact SHA-pinned
HOME24 synthetic candidate. Does not read real medical records or modify app code.
"""
import functools
import hashlib
import http.server
import importlib.util
import json
import pathlib
import re
import sys
import threading
import traceback
import uuid
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent
HOME24 = HERE.parent / "home24"
SITE = HOME24 / "_staged_site"
REPORT = HERE / "HOME28_PRIVACY_EGRESS_REPORT.json"
MARKER = "SYN_PAE04_HOME28_EGRESS_" + uuid.uuid4().hex
CHECKS = []
EXTERNAL = []
LEAKS = []
WEBSOCKETS = []
PAGE_ERRORS = []
EVENT_SOURCES = []
LIMITATIONS = [
    "Chrome only; native iPhone download and system file picker NOT VERIFIED",
    "No OS-level packet capture; WebRTC and browser-internal telemetry NOT VERIFIED",
    "Service Worker script-update requests may evade Playwright route interception",
    "Static secret signatures are targeted, not a complete credential audit",
    "Only explicit HOME28 interactions are observed; no full-app coverage claim",
]
SECRET_SIGNATURES = {
    "openai-style-key": re.compile(r"\bsk-(?:proj|live|test)-[A-Za-z0-9_-]{12,}"),
    "github-access-token": re.compile(r"\b(?:ghp_|github_pat_)[A-Za-z0-9_]{12,}"),
    "private-key-block": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "supabase-service-role-assignment": re.compile(r"(?i)\bservice_role\b\s*[:=]\s*['\"][A-Za-z0-9_-]{12,}"),
}
URL_PATTERN = re.compile(r"https?://[^\s'\"<>\\)]+", re.IGNORECASE)
SOURCE_SUFFIXES = {".js", ".mjs", ".html", ".css", ".json", ".webmanifest", ".svg"}


def require(label, ok):
    CHECKS.append({"check": label, "result": "PASS" if ok else "FAIL"})
    if not ok:
        raise AssertionError(label)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def pinned_files():
    source = HOME24 / "stage_cp41.py"
    spec = importlib.util.spec_from_file_location("home28_pinned_stage_spec", source)
    if spec is None or spec.loader is None:
        raise AssertionError("missing HOME24 staging specification")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # Only declarations; module.main() is NOT called.
    pins = {**module.ORIGINAL, **module.EXPECTED}
    files = {p.relative_to(SITE).as_posix() for p in SITE.rglob("*") if p.is_file()}
    require("exact HOME24 staged file inventory", files == set(pins) and len(files) == 20)
    require("exact HOME24 SHA-256 pins", all(sha((SITE / name).read_bytes()) == pin
                                                for name, pin in pins.items()))
    profile = json.loads((SITE / "personal_profile.json").read_text(encoding="utf-8"))
    require("personal profile empty", profile.get("medicines") == [])
    return pins


def static_source_review(pins):
    secrets = []
    referenced_hosts = set()
    for name in sorted(pins):
        if pathlib.Path(name).suffix.lower() not in SOURCE_SUFFIXES:
            continue
        content = (SITE / name).read_text(encoding="utf-8")
        for signature, pattern in SECRET_SIGNATURES.items():
            if pattern.search(content):
                secrets.append({"file": name, "signature": signature})
        for match in URL_PATTERN.finditer(content):
            host = urlsplit(match.group(0).rstrip(";.,)")).hostname
            if host and host not in ("127.0.0.1", "localhost"):
                referenced_hosts.add(host.lower())
    require("no recognizable embedded secret", secrets == [])
    return {"secret_signatures": secrets,
            "external_reference_hosts": sorted(referenced_hosts),
            "external_references_require_review": bool(referenced_hosts)}


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


def run():
    pins = pinned_files()
    source_review = static_source_review(pins)
    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(Quiet, directory=str(SITE)))
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    origin = "http://127.0.0.1:" + str(server.server_port)

    def local_http(url):
        u = urlsplit(url)
        return u.scheme == "http" and u.hostname == "127.0.0.1" and u.port == server.server_port

    def inspect_request(req):
        u = urlsplit(req.url)
        if u.scheme in ("http", "https"):
            EVENT_SOURCES.append("service-worker" if req.service_worker else "page")
            if not local_http(req.url):
                EXTERNAL.append({"scheme": u.scheme, "host": u.hostname or "unknown"})
            try:
                headers = json.dumps(req.all_headers(), ensure_ascii=False)
                data = req.post_data or ""
            except Exception:
                LEAKS.append({"channel": "uninspectable-request", "kind": "REVIEW"})
                return
            if MARKER in req.url:
                LEAKS.append({"channel": "URL"})
            if MARKER in headers:
                LEAKS.append({"channel": "headers"})
            if MARKER in data:
                LEAKS.append({"channel": "body"})

    def guard_http(route):
        request = route.request
        if not local_http(request.url):
            EXTERNAL.append({"scheme": urlsplit(request.url).scheme,
                             "host": urlsplit(request.url).hostname or "unknown"})
            route.abort("blockedbyclient")
        else:
            route.continue_()

    def guard_websocket(ws):
        url = urlsplit(ws.url)
        WEBSOCKETS.append({"scheme": url.scheme, "host": url.hostname or "unknown"})
        ws.close()  # No connection to a remote WebSocket server.

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                ctx = browser.new_context(viewport={"width": 390, "height": 844},
                    device_scale_factor=2, is_mobile=True, has_touch=True,
                    locale="ru-RU", service_workers="allow", accept_downloads=False)
                ctx.on("request", inspect_request)
                ctx.route(re.compile(r"^https?://"), guard_http)
                ctx.route_web_socket(re.compile(r"^wss?://"), guard_websocket)
                page = ctx.new_page()
                page.on("pageerror", lambda e: PAGE_ERRORS.append(type(e).__name__))
                page.goto(origin + "/index.html", wait_until="domcontentloaded", timeout=30000)
                page.wait_for_function("""()=>typeof db!=='undefined'&&!!db&&
                   typeof createBackup==='function'&&typeof readBackupSnapshot==='function'""",
                   timeout=20000)
                require("isolated HOME24 database", page.evaluate("DB_NAME") ==
                        "PAE04_HOME24_SYNTHETIC_ISOLATED_DB_20261123")
                require("initially empty 4-store IndexedDB", page.evaluate("""async()=>{
                   const s=await readBackupSnapshot();return Object.values(s).every(x=>x.length===0);
                }"""))
                page.evaluate("""async marker=>{
                    const now=new Date(),date=dateLocal(now),created=now.toISOString();
                    const p={id:'SYN_HOME28_PRESSURE_001',arm:'right',dateTime:date+'T00:01',
                      systolic:120,diastolic:80,pulse:60,note:marker,createdAt:created};
                    const m={id:'SYN_HOME28_MEDICINE_001',name:'Синтетический '+marker,
                      dose:'условная единица',kind:'regular',from:null,to:null,
                      dailyIntakes:1,createdAt:created};
                    validatePressure(p);validateMed(m);
                    await addRecord('pressures',p);await addRecord('medications',m);
                    await changeIntake('marked',{id:'SYN_HOME28_INTAKE_001',
                      medId:m.id,date,takenAtLocal:date+'T00:02',
                      markedAt:created,status:'active',dailySlot:1});
                    await reload();
                }""", MARKER)
                snapshot_before = page.evaluate("async()=>await readBackupSnapshot()")
                backup = page.evaluate("async()=>await createBackup()")
                require("synthetic export API contains marker", MARKER in
                        json.dumps(backup, ensure_ascii=False))
                page.locator('.nav-item[data-page="settings"]').click()
                for selector, output, signal in [
                    ("verify-file", "#verify-result", "PASS · SHA-256 совпадает"),
                    ("import-file", "#import-preview", "Конфликтов: 0")]:
                    page.locator("#" + selector).set_input_files({
                        "name": "HOME28_SYNTHETIC_ONLY.json", "mimeType": "application/json",
                        "buffer": json.dumps(backup, ensure_ascii=False, separators=(",", ":")).encode()})
                    page.wait_for_function("""v => document.querySelector(v.sel)?.textContent.includes(v.txt)""",
                        arg={"sel": output, "txt": signal}, timeout=15000)
                require("no auto-restore after preview",
                        page.evaluate("async()=>await readBackupSnapshot()") == snapshot_before)
                page.wait_for_function("() => !!navigator.serviceWorker.controller", timeout=35000)
                require("service worker controls local site",
                        page.evaluate("navigator.serviceWorker.controller.scriptURL.endsWith('/sw.js')"))
                # Explicit synthetic probe of worker-origin request: no remote destination.
                for worker in ctx.service_workers:
                    worker.evaluate("async()=>{const r=await fetch('./index.html');return r.ok}")
                ctx.set_offline(True)
                page.reload(wait_until="domcontentloaded", timeout=30000)
                page.wait_for_function("() => typeof db !== 'undefined' && !!db", timeout=20000)
                require("offline data remains local",
                        page.evaluate("async()=>await readBackupSnapshot()") == snapshot_before)
                ctx.set_offline(False)
                page.wait_for_timeout(500)
                require("no external HTTP(S) attempts", not EXTERNAL)
                require("no marker in requests", not LEAKS)
                require("no WebSocket attempts", not WEBSOCKETS)
                require("no uncaught page errors", not PAGE_ERRORS)
                require("worker-owned network observed",
                        "service-worker" in EVENT_SOURCES)
                ctx.close()
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
    return source_review


if __name__ == "__main__":
    status = "NOT_RUN"
    static_review = None
    errors = []
    try:
        static_review = run()
        status = "PARTIAL_STATIC_REVIEW" if static_review["external_references_require_review"] else "PASS_SCOPED"
    except Exception as exc:
        status = "FAIL_CLOSED"
        errors.append(type(exc).__name__ + ": " + str(exc)[:180])
        traceback.print_exc()
    report = {"checkpoint": "PAE04_HOME28_PRIVACY_EGRESS_01",
              "status": status, "synthetic_only": True,
              "candidate": "HOME24 SHA-pinned 20-file candidate; CP41 unchanged",
              "browser": "GitHub Actions Chromium / Playwright 1.65.1",
              "checks": CHECKS, "static_review": static_review,
              "attempted_external": EXTERNAL, "marker_channel_flags": LEAKS,
              "attempted_websockets": WEBSOCKETS,
              "worker_owned_events": EVENT_SOURCES.count("service-worker"),
              "page_error_count": len(PAGE_ERRORS),
              "marker_sha256_only": sha(MARKER.encode()),
              "known_limitations": LIMITATIONS, "errors": errors,
              "security_gate": "OPEN", "release": "NO_GO"}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("HOME28_RESULT " + json.dumps({"status": status,
          "pass": sum(c["result"] == "PASS" for c in CHECKS),
          "fail": sum(c["result"] == "FAIL" for c in CHECKS),
          "errors": errors}, ensure_ascii=False))
    sys.exit(0 if status == "PASS_SCOPED" else 1)
