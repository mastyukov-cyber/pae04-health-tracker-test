#!/usr/bin/env python3
"""HOME26-STALE-01: one exact-published-HOME24, synthetic-only stale checkpoint QA."""
import hashlib
import http.server
import io
import json
import os
from pathlib import Path, PurePosixPath
import resource
import tarfile
import threading
import time
import traceback
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
SITE = ROOT / "_exact_published_home24"
OUT = ROOT / "HOME26_STALE01_REPORT.json"
RUN_ID = 45227631004
STORES = ("pressures", "medications", "intakes", "intakeEvents")
EXPECTED_DB = "PAE04_HOME24_SYNTHETIC_ISOLATED_DB_20261123"
CHECKS = []
PAGE_ERRORS = []
START = time.monotonic()

def check(name, condition):
    ok = bool(condition)
    CHECKS.append({"name": name, "status": "PASS" if ok else "FAIL"})
    if not ok:
        raise AssertionError("STOP_FIRST HOME26-STALE-01: " + name)

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def sha(value):
    return hashlib.sha256(value).hexdigest()

def payload_hash(value):
    return sha(canonical(value).encode("utf-8"))

def extract_exact_site():
    import zipfile
    manifest_path = ROOT / "evidence" / "manifest" / "HOME24_BUILD_MANIFEST.json"
    tar_path = ROOT / "evidence" / "pages" / "artifact.tar"
    check("immutable published manifest present", manifest_path.is_file())
    check("immutable Pages tar present", tar_path.is_file())
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    pins = manifest["files"]
    check("published manifest exactly 75 files", len(pins) == 75)
    check("published manifest sections 17/19/19/20", (
        manifest["test_root_files"], manifest["cp40_files"],
        manifest["cp41_files"], manifest["home24_files"]) == (17, 19, 19, 20))
    prefix = "home24-iphone-preview/"
    expected = {name[len(prefix):]:pin for name,pin in pins.items() if name.startswith(prefix)}
    check("HOME24 source inventory 20", len(expected) == 20)
    check("exact published app pin", expected.get("app.js") ==
          "882ea9bdf29cbc1365e639348a2b83c76c6b2d94105908203d32c6db821706e3")
    check("exact published guard pin", expected.get("strict_preflight.js") ==
          "4fcee08c000764a9665eca30359cf53e2d04cf48fd88f05cd90213304bfb3d70")
    check("exact published index pin", expected.get("index.html") ==
          "b75588597f73550a4a6aa6ae653cb14d4cea3db80e4d682af006eb8aade7a5ea")
    SITE.mkdir(parents=True, exist_ok=False)
    seen = set()
    with tarfile.open(tar_path, mode="r:*") as archive:
        for member in archive:
            name = member.name
            while name.startswith("./"):
                name = name[2:]
            p = PurePosixPath(name)
            check("safe archive path " + name, bool(name) and not p.is_absolute()
                  and ".." not in p.parts)
            if member.isdir():
                continue
            check("regular archive entry " + name, member.isfile())
            check("unique archive entry " + name, name not in seen)
            seen.add(name)
            check("manifest entry exists " + name, name in pins)
            if name.startswith(prefix):
                rel = name[len(prefix):]
                data = archive.extractfile(member).read()
                check("HOME24 sha256 " + rel, sha(data) == expected[rel])
                dst = SITE / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(data)
    check("published .nojekyll pinned to empty SHA-256", pins.get(".nojekyll") == sha(b""))
    check("Pages artifact 74 files excluding only .nojekyll", len(seen) == 74 and seen == (set(pins) - {".nojekyll"}))
    check("extracted HOME24 inventory 20", {
        p.relative_to(SITE).as_posix() for p in SITE.rglob("*") if p.is_file()
    } == set(expected))
    return expected

class Silent(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass

def native_idb(page):
    return page.evaluate("""async () => {
      const database = await new Promise((resolve,reject) => {
        const req = indexedDB.open(DB_NAME);
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error);
        req.onupgradeneeded = () => reject(Error('Unexpected database creation'));
      });
      return new Promise((resolve,reject) => {
        const stores = ['pressures','medications','intakes','intakeEvents'];
        const result = {};
        const tx = database.transaction(stores,'readonly');
        for (const name of stores) {
          const req = tx.objectStore(name).getAll();
          req.onsuccess = () => {result[name]=req.result.sort((a,b)=>a.id.localeCompare(b.id));};
        }
        tx.oncomplete = () => {database.close(); resolve(result);};
        tx.onerror = () => {database.close(); reject(tx.error);};
        tx.onabort = () => {database.close(); reject(Error('readback transaction aborted'));};
      });
    }""")

def run_one():
    pins = extract_exact_site()
    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), lambda *args, **kw: Silent(*args, directory=str(SITE), **kw))
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = "http://127.0.0.1:" + str(server.server_port)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                context = browser.new_context(viewport={"width":390,"height":844},
                    device_scale_factor=2, is_mobile=True, has_touch=True,
                    locale="ru-RU", accept_downloads=True, service_workers="allow")
                def network_guard(route):
                    if route.request.url.startswith(base + "/"):
                        route.continue_()
                    else:
                        route.abort_()
                context.route("**/*", network_guard)
                page = context.new_page()
                page.on("pageerror", lambda e: PAGE_ERRORS.append(str(e)))
                page.goto(base + "/index.html", wait_until="domcontentloaded", timeout=25000)
                page.wait_for_function("""() => typeof db !== 'undefined' && !!db &&
                  typeof readBackupSnapshot === 'function' &&
                  typeof applyImport === 'function' &&
                  typeof PAE04StrictBackup?.checkNoDuplicateKeys === 'function'""",
                  timeout=20000)
                check("running exact HOME24 isolated DB", page.evaluate("DB_NAME") == EXPECTED_DB)
                initial = native_idb(page)
                check("initial four stores empty", {k:len(v) for k,v in initial.items()}
                      == {name:0 for name in STORES})
                page.evaluate("""async () => {
                  const now=new Date(),date=dateLocal(now),created=now.toISOString();
                  const p={id:'SYN_HOME26_PRESSURE_001',arm:'right',dateTime:date+'T00:01',
                    systolic:120,diastolic:80,pulse:60,note:'',createdAt:created};
                  const m={id:'SYN_HOME26_MEDICINE_001',name:'Синтетический препарат А',
                    dose:'условная единица',kind:'regular',from:null,to:null,
                    dailyIntakes:1,createdAt:created};
                  validatePressure(p);validateMed(m);
                  await addRecord('pressures',p);await addRecord('medications',m);
                  await changeIntake('marked',{id:'SYN_HOME26_INTAKE_001',
                    medId:m.id,date,takenAtLocal:date+'T00:02',
                    markedAt:created,status:'active',dailySlot:1});
                  await reload();
                }""")
                baseline = native_idb(page)
                check("four real IDB stores seeded", {k:len(v) for k,v in baseline.items()}
                      == {name:1 for name in STORES})
                signed = page.evaluate("""async () => {
                  const snapshot=await readBackupSnapshot();
                  const now=new Date(),date=dateLocal(now),created=now.toISOString();
                  const extra={id:'SYN_HOME26_IMPORT_NEVER_001',arm:'right',
                    dateTime:date+'T00:04',systolic:125,diastolic:81,pulse:64,
                    note:'DO_NOT_IMPORT',createdAt:created};
                  validatePressure(extra);
                  snapshot.pressures.push(extra);
                  const body={format:BACKUP_FORMAT,version:BACKUP_VERSION,
                    exportedAt:created,data:snapshot};
                  return {...body,sha256:await sha256(body)};
                }""")
                check("signed synthetic backup sha256", signed["sha256"] ==
                      payload_hash({k:v for k,v in signed.items() if k != "sha256"}))
                page.locator('.nav-item[data-page="settings"]').click()
                page.locator("#import-file").set_input_files({
                    "name":"HOME26_SYNTHETIC_SIGNED_ONLY.json",
                    "mimeType":"application/json",
                    "buffer":json.dumps(signed,ensure_ascii=False).encode("utf-8")
                })
                page.wait_for_function("""() =>
                  document.querySelector('#import-preview')?.textContent.includes('Конфликтов: 0')""",
                  timeout=15000)
                check("preview exactly one fresh synthetic record",
                      "Новых: 1" in page.locator("#import-preview").inner_text())
                check("checkpoint button enabled", page.locator("#checkpoint-button").is_enabled())
                with page.expect_download(timeout=15000) as ev:
                    page.locator("#checkpoint-button").click()
                download = ev.value
                check("synthetic checkpoint offered for download",
                      download.suggested_filename.startswith("PAE04-PERSONAL-PREIMPORT-CHECKPOINT-"))
                check("checkpoint acknowledgement enabled", page.locator("#checkpoint-ack").is_enabled())
                page.locator("#checkpoint-ack").check()
                check("import ready before local change", page.locator("#import-button").is_enabled())
                checkpoint = page.evaluate("""async () => ({
                   stored:pendingImport?.checkpoint?.baselineHash,
                   actual:await sha256(await readBackupSnapshot())
                })""")
                check("original checkpoint sha256 matches", checkpoint["stored"] == checkpoint["actual"])
                page.evaluate("""async () => {
                  const now=new Date(),date=dateLocal(now);
                  const p={id:'SYN_HOME26_AFTER_CHECKPOINT_001',arm:'right',
                    dateTime:date+'T00:03',systolic:121,diastolic:79,pulse:61,
                    note:'INTENTIONAL_CHANGE_AFTER_CHECKPOINT',createdAt:now.toISOString()};
                  validatePressure(p);
                  await addRecord('pressures',p);
                  await reload();
                }""")
                expected_after_change = native_idb(page)
                check("intentional second pressure added", len(expected_after_change["pressures"]) == 2)
                check("other three stores unchanged by deliberate edit",
                      all(expected_after_change[name] == baseline[name] for name in STORES[1:]))
                check("checkpoint is now stale", page.evaluate("""async () =>
                    (await sha256(await readBackupSnapshot())) !== pendingImport.checkpoint.baselineHash"""))
                page.evaluate("""() => {
                  window.__home26_atomicMerge_calls=0;
                  window.__home26_confirm_calls=0;
                  atomicMerge=async function() {
                    window.__home26_atomicMerge_calls++;
                    throw Error('STOP_FIRST unexpected atomicMerge invocation');
                  };
                  window.confirm=function(){window.__home26_confirm_calls++;return false;};
                }""")
                check("import button still available to exercise stale branch",
                      page.locator("#import-button").is_enabled())
                page.locator("#import-button").click()
                page.wait_for_function("""() =>
                  document.querySelector('#messages')?.textContent.includes(
                    'База изменилась после защитной копии')""", timeout=15000)
                calls = page.evaluate("""() => ({
                  merge:window.__home26_atomicMerge_calls,
                  confirm:window.__home26_confirm_calls,
                  checkpoint:pendingImport?.checkpoint,
                  ackDisabled:document.querySelector('#checkpoint-ack').disabled,
                  importDisabled:document.querySelector('#import-button').disabled,
                  checkpointEnabled:!document.querySelector('#checkpoint-button').disabled
                })""")
                check("stale checkpoint visibly rejected", True)
                check("atomicMerge not called", calls["merge"] == 0)
                check("native confirm not opened", calls["confirm"] == 0)
                check("old checkpoint invalidated", calls["checkpoint"] is None)
                check("acknowledgement disabled", calls["ackDisabled"])
                check("import button disabled", calls["importDisabled"])
                check("new checkpoint may be created", calls["checkpointEnabled"])
                after = native_idb(page)
                check("all four stores unchanged after rejection",
                      after == expected_after_change)
                check("rejected import record absent",
                      not any(x["id"] == "SYN_HOME26_IMPORT_NEVER_001" for x in after["pressures"]))
                page.reload(wait_until="domcontentloaded")
                page.wait_for_function("() => typeof db !== 'undefined' && !!db", timeout=20000)
                after_reload = native_idb(page)
                check("independent native IndexedDB readback after reload unchanged",
                      after_reload == expected_after_change)
                check("four-store SHA unchanged after reload",
                      payload_hash(after_reload) == payload_hash(expected_after_change))
                check("uncaught JavaScript exceptions absent", not PAGE_ERRORS)
                return {
                    "source_home24_files":len(pins),
                    "indexeddb_four_store_counts":{k:len(v) for k,v in after_reload.items()},
                    "after_change_sha256":payload_hash(expected_after_change),
                    "after_reload_sha256":payload_hash(after_reload),
                    "atomicMerge_calls":calls["merge"],
                    "confirm_calls":calls["confirm"]
                }
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)

def main():
    report={"checkpoint":"PAE04_HOME26_STALE01_20261123",
        "status":"FAIL_CLOSED","release":"NO_GO",
        "source_run":RUN_ID,"synthetic_only":True,
        "browser":"Chromium/Playwright 1.65.1",
        "repeat_old_qa":False,"deploy":False}
    try:
        check("synthetic environment explicitly enabled",
              os.environ.get("PAE04_HOME26_SYNTHETIC_ONLY") == "ALLOW_ONCE")
        info=run_one()
        report.update(info)
        report["status"]="PASS_SCOPED"
    except Exception as exc:
        report["error"]=str(exc)
        report["trace_tail"]=traceback.format_exc(limit=5)
    finally:
        report["checks"]=CHECKS
        report["checks_pass"]=sum(x["status"]=="PASS" for x in CHECKS)
        report["checks_fail"]=sum(x["status"]=="FAIL" for x in CHECKS)
        report["duration_seconds"]=round(time.monotonic()-START,3)
        report["maxrss_kib"]=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        report["page_errors"]=PAGE_ERRORS
        OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
        print("HOME26_STALE01_RESULT "+json.dumps({
            "status":report["status"],"pass":report["checks_pass"],
            "fail":report["checks_fail"],"error":report.get("error"),
            "duration_seconds":report["duration_seconds"]},ensure_ascii=False))
    return report["status"]=="PASS_SCOPED"

if __name__=="__main__":
    raise SystemExit(0 if main() else 1)
