#!/usr/bin/env python3
"""Synthetic Cache Storage A/B diagnostic for unchanged PAE-04 v04 assets."""
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from threading import Thread
from tempfile import TemporaryDirectory
from importlib.metadata import version as package_version
from urllib.request import urlopen
import json, sys, time, traceback

ROOT = Path(__file__).resolve().parents[1] / "v04-safe-upgrade" / "site"
REPORT = Path(__file__).resolve().parents[1] / "reports"
DB = "PAE04_HT_STABLE_CANDIDATE_INTEGRATION_SYNTHETIC_SCHEMA1"
CACHE = "pae04-ht-stable-candidate-synthetic-schema1-cache-v04-20261113"
WORKER_FILES = [
    "/", "/index.html", "/app.js", "/styles.css", "/manifest.webmanifest",
    "/icons/icon.svg", "/icons/apple-touch-icon.png",
    "/icons/icon-192.png", "/icons/icon-512.png",
]
HTTP_ASSETS = ["", "index.html", "app.js", "styles.css", "sw.js",
               "manifest.webmanifest", "icons/icon.svg",
               "icons/apple-touch-icon.png", "icons/icon-192.png",
               "icons/icon-512.png"]

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)
    def log_message(self, *args):
        pass
    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

def wait_state(page, expression, timeout_ms=20000):
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        try:
            if page.evaluate(expression):
                return True
        except Exception:
            pass
        page.wait_for_timeout(100)
    return False

def cache_state(page):
    return page.evaluate("""async (cacheName) => {
      const registrations = await navigator.serviceWorker.getRegistrations();
      const names = await caches.keys();
      const cacheExists = names.includes(cacheName);
      const requests = cacheExists ? await (await caches.open(cacheName)).keys() : [];
      const reg = registrations.find(x => x.active?.scriptURL.endsWith('/sw.js'));
      return {
        registration: reg ? {
          installing: reg.installing?.state || null,
          waiting: reg.waiting?.state || null,
          active: reg.active?.state || null
        } : null,
        controller: Boolean(navigator.serviceWorker.controller),
        cacheNames: names,
        cacheExists,
        keys: requests.map(x => new URL(x.url).pathname).sort()
      };
    }""", CACHE)

def check_engine(playwright, engine, expected_version, log):
    failures = []
    checks = 0
    context = server = thread = None
    server_requests = []
    sw_console = []
    page_events = []
    def mark(label, passed=True, detail=None):
        nonlocal checks
        checks += 1
        state = "PASS" if passed else "FAIL"
        item = f"{state} {checks} {label}" + (f" :: {detail}" if detail else "")
        log.append(item)
        print(item, flush=True)
        if not passed:
            failures.append(label)
        return passed
    try:
        actual_version = package_version("playwright")
        if actual_version != expected_version:
            mark(f"Playwright package is {expected_version}", False, f"actual={actual_version}")
        else:
            mark(f"Playwright package version {actual_version}")

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = "http://127.0.0.1:" + str(server.server_address[1]) + "/"
        for asset in HTTP_ASSETS:
            with urlopen(base + asset, timeout=8) as response:
                server_requests.append({"path": asset or "/", "status": response.status})
                if response.status != 200:
                    raise AssertionError(f"HTTP {response.status} for {asset}")
        mark("HTTP 200 for v04 page, Service Worker, and 9 cached resources")

        browser_type = getattr(playwright, engine)
        profile = REPORT / f"profile-{engine}-pw-{expected_version}"
        context = browser_type.launch_persistent_context(
            user_data_dir=str(profile.resolve()),
            headless=True,
            accept_downloads=True,
            service_workers="allow",
            args=["--no-sandbox"] if engine == "chromium" else [],
        )
        context.on("serviceworker", lambda worker: worker.on(
            "console", lambda message: sw_console.append({
                "type": message.type, "text": message.text
            })
        ))
        page = context.new_page()
        page.on("pageerror", lambda error: page_events.append({"pageerror": str(error)}))
        page.on("console", lambda message: page_events.append({
            "console": message.type, "text": message.text
        }) if message.type == "error" else None)
        page.on("requestfailed", lambda request: page_events.append({
            "requestfailed": request.url, "failure": request.failure
        }))
        page.goto(base + "index.html", wait_until="domcontentloaded", timeout=30000)
        ua = page.evaluate("navigator.userAgent")
        controlled = wait_state(
            page,
            "Boolean(navigator.serviceWorker.controller) && "
            "navigator.serviceWorker.controller.state === 'activated'",
        )
        state_before = cache_state(page)
        mark("Service Worker installed, active, and controls page", controlled,
             json.dumps(state_before, ensure_ascii=False))
        mark("Cache Storage created with all nine v04 worker resources",
             state_before["cacheExists"] and state_before["keys"] == sorted(WORKER_FILES),
             json.dumps(state_before, ensure_ascii=False))

        online_reload_response = None
        try:
            online_reload_response = page.reload(wait_until="domcontentloaded", timeout=20000)
        except Exception as error:
            page_events.append({"online_reload_error": str(error)})
        controlled_after_reload = wait_state(
            page,
            "Boolean(navigator.serviceWorker.controller) && "
            "navigator.serviceWorker.controller.state === 'activated'",
        )
        state_after_reload = cache_state(page)
        mark("Service Worker controls reloaded page",
             controlled_after_reload,
             json.dumps(state_after_reload, ensure_ascii=False))
        mark("All nine Cache Storage resources persist after online reload",
             state_after_reload["cacheExists"] and state_after_reload["keys"] == sorted(WORKER_FILES),
             json.dumps(state_after_reload, ensure_ascii=False))

        idb_before = page.evaluate("""async (name) => {
          const db = await new Promise((resolve, reject) => {
            const req = indexedDB.open(name);
            req.onsuccess = () => resolve(req.result);
            req.onerror = () => reject(req.error);
          });
          const names = [...db.objectStoreNames].sort();
          db.close();
          return names;
        }""", DB)
        mark("Four real IndexedDB stores exist before offline reload",
             idb_before == ["intakeEvents", "intakes", "medications", "pressures"],
             json.dumps(idb_before))

        server.shutdown()
        server.server_close()
        if thread:
            thread.join(timeout=5)
        server = None

        uncached = page.evaluate("""async () => {
          try {
            const response = await fetch('./__uncached_cache_ab_probe__');
            return {rejected: response.status >= 400, status: response.status};
          } catch (error) {
            return {rejected: true, name: error.name, message: error.message};
          }
        }""")
        mark("Stopped origin rejects uncached request", uncached["rejected"],
             json.dumps(uncached, ensure_ascii=False))

        offline_response = None
        offline_error = None
        try:
            offline_response = page.reload(wait_until="domcontentloaded", timeout=20000)
        except Exception as error:
            offline_error = str(error)
        state_offline = cache_state(page)
        offline_title = ""
        offline_idb = []
        try:
            offline_title = page.title()
            offline_idb = page.evaluate("""async (name) => {
              const db = await new Promise((resolve, reject) => {
                const req = indexedDB.open(name);
                req.onsuccess = () => resolve(req.result);
                req.onerror = () => reject(req.error);
              });
              const names = [...db.objectStoreNames].sort();
              db.close();
              return names;
            }""", DB)
        except Exception as error:
            page_events.append({"post_offline_read_error": str(error)})
        sw_served = bool(offline_response and offline_response.from_service_worker)
        mark("Offline reload served from Service Worker after origin stop",
             sw_served and "HEALTH TRACKER" in offline_title.upper(),
             json.dumps({"response_from_service_worker": sw_served,
                         "reload_error": offline_error, "title": offline_title,
                         "cache": state_offline}, ensure_ascii=False))
        mark("Four IndexedDB stores remain accessible after offline reload",
             offline_idb == idb_before and idb_before == [
                 "intakeEvents", "intakes", "medications", "pressures"],
             json.dumps(offline_idb))
        mark("No page JavaScript errors", not any("pageerror" in x for x in page_events),
             json.dumps(page_events, ensure_ascii=False))

        result = {
            "engine": engine,
            "playwright": actual_version,
            "user_agent": ua,
            "http_requests": server_requests,
            "cache_before_reload": state_before,
            "cache_after_online_reload": state_after_reload,
            "cache_after_offline_reload": state_offline,
            "idb_before": idb_before,
            "idb_after_offline_reload": offline_idb,
            "uncached_request": uncached,
            "offline_response_from_service_worker": sw_served,
            "offline_reload_error": offline_error,
            "service_worker_console": sw_console,
            "page_events": page_events,
            "checks": checks,
            "failures": failures,
        }
        log.append("RESULT=" + ("PASS" if not failures else "FAIL") +
                   f" ENGINE={engine} PLAYWRIGHT={actual_version} CHECKS={checks} FAILURES={json.dumps(failures)}")
        return result
    except Exception as error:
        log.append("HARNESS_ERROR=" + repr(error))
        log.append(traceback.format_exc())
        print("HARNESS_ERROR=" + repr(error), flush=True)
        return {
            "engine": engine, "playwright": expected_version,
            "checks": checks, "failures": failures + ["harness exception"],
            "harness_error": repr(error), "traceback": traceback.format_exc(),
            "server_requests": server_requests, "service_worker_console": sw_console,
            "page_events": page_events,
        }
    finally:
        if context:
            try: context.close()
            except Exception: pass
        if server:
            try: server.shutdown(); server.server_close()
            except Exception: pass
        if thread:
            try: thread.join(timeout=5)
            except Exception: pass

if __name__ == "__main__":
    engine, expected = sys.argv[1], sys.argv[2]
    if engine not in ("chromium", "webkit") or expected not in ("1.56.0", "1.65.0"):
        raise SystemExit("usage: cache_storage_compare.py chromium|webkit 1.56.0|1.65.0")
    REPORT.mkdir(parents=True, exist_ok=True)
    lines = []
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        result = check_engine(p, engine, expected, lines)
    out = REPORT / f"cache-storage-{engine}-pw-{expected}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    (REPORT / f"cache-storage-{engine}-pw-{expected}.log").write_text("\n".join(lines) + "\n", encoding="utf8")
    print("\n".join(lines), flush=True)
    raise SystemExit(0 if result and not result.get("failures") else 1)
