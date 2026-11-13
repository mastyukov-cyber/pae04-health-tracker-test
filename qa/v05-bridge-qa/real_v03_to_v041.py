#!/usr/bin/env python3
"""Synthetic-only real v03 UI -> v04.1 backup/checkpoint/import bridge acceptance."""
import json, sys, time, traceback
from pathlib import Path
from hashlib import sha256
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlsplit, unquote
from threading import Thread
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OLD_SITE = ROOT / "integration-v03-browser" / "site-v03"
NEW_SITE = ROOT / "v04-safe-upgrade" / "site"
REPORT = Path(__file__).resolve().parent / "reports"
OLD_DB = "PAE04_HealthTracker_PWA_v021_INTEGRATION_SYNTHETIC_V03_CONFIRM_BUTTON_4STORE"
NEW_DB = "PAE04_HT_STABLE_CANDIDATE_INTEGRATION_SYNTHETIC_SCHEMA1"
STORES = ["pressures", "medications", "intakes", "intakeEvents"]
MIME = {".html":"text/html; charset=utf-8",".js":"text/javascript; charset=utf-8",
        ".css":"text/css; charset=utf-8",".webmanifest":"application/manifest+json",
        ".png":"image/png",".svg":"image/svg+xml"}
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_GET(self):
        path = unquote(urlsplit(self.path).path)
        if path.startswith("/v03/"):
            root, relative = OLD_SITE, path[len("/v03/"):]
        elif path.startswith("/v041/"):
            root, relative = NEW_SITE, path[len("/v041/"):]
        else:
            self.send_error(404); return
        target = (root / (relative or "index.html")).resolve()
        if not target.is_relative_to(root.resolve()) or not target.is_file():
            self.send_error(404); return
        data=target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", MIME.get(target.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

def canonical(v):
    return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"))
def checked_archive(archive):
    assert archive["format"]=="pae04.healthtracker.synthetic-backup"
    assert archive["version"]==3
    body={k:v for k,v in archive.items() if k!="sha256"}
    assert sha256(canonical(body).encode("utf8")).hexdigest()==archive["sha256"], "backup SHA-256 mismatch"
    assert sorted(archive["data"])==sorted(STORES), "backup stores mismatch"
    return archive["data"]
def rows(page, database):
    return page.evaluate("""async({name,stores})=>{
      const db=await new Promise((resolve,reject)=>{
        const request=indexedDB.open(name);
        request.onsuccess=()=>resolve(request.result);
        request.onerror=()=>reject(request.error);
      });
      try {
        const result={};
        for(const store of stores){
          if(!db.objectStoreNames.contains(store))throw Error('Missing store: '+store);
          result[store]=await new Promise((resolve,reject)=>{
            const tx=db.transaction(store,'readonly');
            const req=tx.objectStore(store).getAll();
            req.onsuccess=()=>resolve(req.result);
            req.onerror=()=>reject(req.error);
          });
        }
        return result;
      }finally{db.close();}
    }""", {"name":database,"stores":STORES})
def normalized(d):
    return {store:sorted(d[store], key=lambda row:row["id"]) for store in STORES}
def wait(page,expr,timeout=15000):
    # Avoid page.wait_for_function string-eval: the shipped v03 CSP forbids unsafe-eval.
    deadline=time.monotonic()+timeout/1000
    while time.monotonic()<deadline:
        try:
            if page.evaluate(expr):
                return True
        except Exception:
            pass
        page.wait_for_timeout(120)
    raise AssertionError("Browser readiness timed out: "+expr)
def execute(engine,log):
    passed=0
    server=thread=browser=context=None
    evidence={}
    def ok(name):
        nonlocal passed
        passed+=1
        line=f"PASS {passed} {name}"
        log.append(line); print(line,flush=True)
    try:
        assert OLD_SITE.is_dir() and NEW_SITE.is_dir(), "SHA-gated v03/v04.1 sites not available"
        server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
        thread=Thread(target=server.serve_forever,daemon=True); thread.start()
        origin="http://127.0.0.1:"+str(server.server_address[1])
        with sync_playwright() as p:
            browser=getattr(p,engine).launch(headless=True,args=["--no-sandbox"] if engine=="chromium" else [])
            context=browser.new_context(accept_downloads=True,service_workers="allow")
            old=context.new_page()
            old.goto(origin+"/v03/index.html",wait_until="domcontentloaded")
            wait(old,"document.querySelector('#stat-pressure')?.textContent==='0'")
            old.locator('[data-page="meds"]').click()
            old.locator("#med-name").fill("Учебный препарат А")
            old.locator("#med-dose").fill("Синтетическая дозировка v03")
            old.locator("#med-strength").fill("10")
            old.locator("#med-unit").select_option(label="мг")
            old.locator("#med-form-factor").select_option(label="таблетки")
            old.locator("#med-kind").select_option("regular")
            old.locator('#med-form button[type="submit"]').click()
            wait(old,"document.querySelector('#stat-meds')?.textContent==='1'")
            ok("Actual old v03 UI creates a synthetic medication")
            old.locator("#intake-date").fill("2024-06-10")
            old.locator('#med-list .med-time-controls input[type="time"]').fill("08:15")
            old.locator("#med-list .intake-confirm-button").click()
            wait(old,"document.querySelectorAll('#med-list .intake-record').length===1")
            old.locator('#med-list .med-time-controls input[type="time"]').fill("20:15")
            old.locator("#med-list .intake-confirm-button").click()
            wait(old,"document.querySelectorAll('#med-list .intake-record').length===2")
            old.locator("#med-list .intake-record").first.locator('input[type="time"]').fill("09:10")
            old.locator("#med-list .intake-record").first.get_by_role("button",name="Изменить время").click()
            wait(old,"document.querySelector('#med-list')?.textContent?.includes('08:15 → 09:10')")
            old.locator("#med-list .intake-record").nth(1).get_by_role("button",name="Отменить отметку").click()
            wait(old,"document.querySelectorAll('#med-list .intake-record.cancelled').length===1")
            ok("Actual old UI retains two intakes and correction/cancellation events")
            old.locator('[data-page="pressure"]').click()
            old.locator("#systolic").fill("121")
            old.locator("#diastolic").fill("79")
            old.locator("#pulse").fill("70")
            old.locator("#pressure-datetime").fill("2024-06-10T09:00")
            old.locator('#pressure-form button[type="submit"]').click()
            wait(old,"document.querySelector('#stat-pressure')?.textContent==='1'")
            before=rows(old,OLD_DB)
            assert [len(before[k]) for k in STORES]==[1,1,2,4], "actual v03 DB counts mismatch"
            assert before["pressures"][0]["arm"]=="right"
            ok("Actual v03 IndexedDB has 4 complete stores with right-arm pressure")
            old.locator('[data-page="backup"]').click()
            with old.expect_download(timeout=15000) as dl:
                old.locator("#export-button").click()
            backup_bytes=Path(dl.value.path()).read_bytes()
            export=json.loads(backup_bytes)
            original=checked_archive(export)
            assert normalized(original)==normalized(before)
            evidence["v03_export_digest"]=export["sha256"]
            evidence["source_counts"]={k:len(before[k]) for k in STORES}
            ok("Actual v03 interface exports full v3 JSON with valid SHA-256")
            new=context.new_page()
            errors=[]
            new.on("pageerror",lambda e: errors.append(str(e)))
            new.goto(origin+"/v041/index.html",wait_until="domcontentloaded")
            wait(new,"document.querySelector('#stat-pressure')?.textContent==='0' && document.querySelector('#stat-meds')?.textContent==='0'")
            assert all(not x for x in rows(new,NEW_DB).values())
            assert normalized(rows(new,OLD_DB))==normalized(before)
            ok("v04.1 sees an empty new DB without deleting real v03 UI records")
            new.locator('[data-page="backup"]').click()
            new.locator("#import-file").set_input_files({"name":"v03-real-ui-synthetic-backup.json","mimeType":"application/json","buffer":backup_bytes})
            wait(new,"document.querySelector('#checkpoint-button')?.disabled===false")
            assert new.locator("#import-button").is_disabled()
            ok("v04.1 requires a protective checkpoint before v03 JSON import")
            with new.expect_download(timeout=15000) as cp:
                new.locator("#checkpoint-button").click()
            checkpoint=json.loads(Path(cp.value.path()).read_bytes())
            cp_data=checked_archive(checkpoint)
            assert all(not cp_data[k] for k in STORES), "pre-import checkpoint must be empty"
            assert new.locator("#import-button").is_disabled()
            evidence["checkpoint_digest"]=checkpoint["sha256"]
            ok("v04.1 downloads independently checked pre-import checkpoint")
            new.locator("#checkpoint-ack").check()
            assert new.locator("#import-button").is_enabled()
            new.locator("#import-button").click()
            wait(new,"document.querySelector('#stat-pressure')?.textContent==='1' && document.querySelector('#stat-meds')?.textContent==='1'")
            after=rows(new,NEW_DB)
            assert normalized(after)==normalized(original), "cross-version data mismatch"
            assert normalized(rows(new,OLD_DB))==normalized(before), "v03 records mutated"
            ok("Confirmed import preserves all original records and leaves v03 DB untouched")
            new.reload(wait_until="domcontentloaded")
            wait(new,"document.querySelector('#stat-pressure')?.textContent==='1'")
            assert normalized(rows(new,NEW_DB))==normalized(original)
            ok("v04.1 reload retains migrated synthetic data")
            new.locator('[data-page="backup"]').click()
            with new.expect_download(timeout=15000) as post:
                new.locator("#export-button").click()
            exported_new=json.loads(Path(post.value.path()).read_bytes())
            assert normalized(checked_archive(exported_new))==normalized(original)
            evidence["v041_export_digest"]=exported_new["sha256"]
            ok("v04.1 exported backup contains exact cross-version history")
            wait(new,"Boolean(navigator.serviceWorker.controller)",timeout=20000)
            cached=new.evaluate("""async()=>{
              const keys=await caches.keys();let all=[];
              for(const name of keys)all.push(...(await (await caches.open(name)).keys()).map(r=>r.url));
              return all.some(u=>u.endsWith('/v041/index.html'));
            }""")
            assert cached, "v04.1 offline cache not ready"
            server.shutdown();server.server_close();server=None
            if thread:thread.join(timeout=5)
            response=new.reload(wait_until="domcontentloaded",timeout=20000)
            assert response.from_service_worker, "v04.1 SW not serving offline page"
            assert normalized(rows(new,NEW_DB))==normalized(original)
            assert not errors, "unexpected v04.1 JavaScript errors: "+str(errors)
            ok("Offline v04.1 serves actual cross-version records after origin stopped")
            evidence["checks"]=passed
            evidence["stores"]=evidence["source_counts"]
            evidence["offline_service_worker"]=True
            context.close();context=None
            browser.close();browser=None
        log.append(f"RESULT=PASS ENGINE={engine} CHECKS={passed} REAL_V03_UI_TO_V041=True SYNTHETIC_ONLY=True")
        return {"engine":engine,"result":"PASS","evidence":evidence}
    except Exception as e:
        log.append(f"RESULT=FAIL ENGINE={engine} CHECKS={passed} ERROR={type(e).__name__}: {e}")
        log.append(traceback.format_exc())
        return {"engine":engine,"result":"FAIL","checks_completed":passed,"error":str(e),"traceback":traceback.format_exc()}
    finally:
        if context:
            try:context.close()
            except Exception:pass
        if browser:
            try:browser.close()
            except Exception:pass
        if server:
            try:server.shutdown();server.server_close()
            except Exception:pass
        if thread:
            try:thread.join(timeout=5)
            except Exception:pass

if __name__=="__main__":
    engine=sys.argv[1]
    if engine not in ("chromium","webkit"):raise SystemExit("Usage: real_v03_to_v041.py chromium|webkit")
    REPORT.mkdir(parents=True,exist_ok=True)
    log=[]
    result=execute(engine,log)
    (REPORT/f"{engine}.log").write_text("\n".join(log)+"\n",encoding="utf8")
    (REPORT/f"{engine}.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print("\n".join(log),flush=True)
    raise SystemExit(0 if result["result"]=="PASS" else 1)
