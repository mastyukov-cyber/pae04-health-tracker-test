#!/usr/bin/env python3
"""PAE-04 v04 synthetic-only REAL browser QA. Localhost only; no live medical data."""
from pathlib import Path
from hashlib import sha256
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from urllib.request import urlopen
from urllib.parse import urlparse
from threading import Thread
from tempfile import TemporaryDirectory
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
import json, traceback,sys,os,time
SITE=Path(__file__).resolve().parents[1]/'site'
REPORT=Path(__file__).resolve().parents[1]/'reports'
REPORT.mkdir(exist_ok=True)
DB='PAE04_HT_STABLE_CANDIDATE_INTEGRATION_SYNTHETIC_SCHEMA1'
STORE=['pressures','medications','intakes','intakeEvents']
ASSETS=['','index.html','app.js','styles.css','sw.js','manifest.webmanifest','icons/icon.svg','icons/apple-touch-icon.png','icons/icon-192.png','icons/icon-512.png']
class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kw):super().__init__(*args,directory=str(SITE),**kw)
    def log_message(self,*args):pass
    def end_headers(self):
        self.send_header('Cache-Control','no-cache')
        super().end_headers()

def canonical(x):
    if isinstance(x,list):return '['+','.join(canonical(i) for i in x)+']'
    if isinstance(x,dict):return '{'+','.join(json.dumps(k,ensure_ascii=False)+':'+canonical(x[k]) for k in sorted(x))+'}'
    return json.dumps(x,ensure_ascii=False,separators=(',',':'))

def dbrows(page):
    return page.evaluate('''async(name)=>{const db=await new Promise((resolve,reject)=>{const r=indexedDB.open(name);r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error)});const names=[...db.objectStoreNames];const out={};for(const name of names){out[name]=await new Promise((resolve,reject)=>{const tx=db.transaction(name);const r=tx.objectStore(name).getAll();r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error)})}db.close();return out}''',DB)

def check_engine(p,engine,log):
    count=0
    def ok(label):
        nonlocal count
        count+=1;log.append(f'PASS {count} {label}')
    context=None;server=None;thread=None
    errors=[];outsiders=[]
    try:
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=Thread(target=server.serve_forever,daemon=True);thread.start()
        base='http://127.0.0.1:'+str(server.server_address[1])+'/'
        browser_engine=getattr(p,engine)
        context=browser_engine.launch_persistent_context(user_data_dir=str((REPORT/f'_profile_{engine}').resolve()),headless=True,accept_downloads=True,args=['--no-sandbox'] if engine=='chromium' else [],service_workers='allow',executable_path='/usr/bin/chromium' if engine=='chromium' else None)
        page=context.new_page()
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda req:outsiders.append(req.url) if urlparse(req.url).hostname not in ('127.0.0.1',None) else None)
        page.on('dialog',lambda dialog:dialog.accept())
        for asset in ASSETS:
            with urlopen(base+asset,timeout=5) as r:
                assert r.status==200,asset
        ok('10 local HTTP assets are 200, including four PNG/SVG icons')
        page.goto(base+'index.html',wait_until='domcontentloaded',timeout=30000)
        page.wait_for_function('document.querySelector("#stat-pressure")?.textContent!==undefined',timeout=15000)
        page.wait_for_function('async()=>{const r=await navigator.serviceWorker.ready;return r.active?.state==="activated"}',timeout=20000)
        ok('ServiceWorker installed and activated on real browser')
        db=dbrows(page)
        assert sorted(db)==sorted(STORE)
        assert all(not db[s] for s in STORE)
        ok('Four real IndexedDB stores created with fixed build-independent name')
        page.locator('[data-page="pressure"]').click()
        page.locator('#systolic').fill('121');page.locator('#diastolic').fill('79');page.locator('#pulse').fill('70')
        page.locator('#pressure-datetime').fill('2024-06-10T09:00')
        page.locator('#pressure-form button[type="submit"]').click()
        page.wait_for_function('document.querySelector("#stat-pressure")?.textContent==="1"')
        assert dbrows(page)['pressures'][0]['arm']=='right'
        ok('Synthetic manual right-arm pressure persisted')
        page.locator('[data-page="meds"]').click()
        page.locator('#med-name').fill('Учебный препарат А');page.locator('#med-dose').fill('Учебная дозировка')
        page.locator('#med-kind').select_option('regular');page.locator('#med-strength').fill('10');page.locator('#med-unit').select_option(label='мг');page.locator('#med-form-factor').select_option(label='таблетки')
        page.locator('#med-form button[type="submit"]').click()
        page.wait_for_function('document.querySelector("#stat-meds")?.textContent==="1"')
        page.locator('#intake-date').fill('2024-06-10')
        page.locator('#med-list .med-time-controls input[type="time"]').fill('08:15')
        page.locator('#med-list .intake-confirm-button').click()
        page.wait_for_function('document.querySelectorAll("#med-list .intake-record").length===1')
        page.locator('#med-list .med-time-controls input[type="time"]').fill('20:15')
        page.locator('#med-list .intake-confirm-button').click()
        page.wait_for_function('document.querySelectorAll("#med-list .intake-record").length===2')
        assert len(dbrows(page)['intakeEvents'])==2
        ok('Two same-day medicine intakes with distinct audit events')
        page.locator('#med-list .intake-confirm-button').click()
        page.wait_for_timeout(200)
        assert len(dbrows(page)['intakes'])==2
        ok('Same-time duplicate confirmation does not create extra record')
        page.locator('[data-page="backup"]').click()
        with page.expect_download(timeout=15000) as d:page.locator('#export-button').click()
        dl=d.value
        exported=json.loads(Path(dl.path()).read_text('utf8'))
        rawsha=exported.pop('sha256');assert sha256(canonical(exported).encode()).hexdigest()==rawsha
        exported['sha256']=rawsha
        assert exported['version']==3 and sorted(exported['data'])==sorted(STORE)
        ok('Actual browser export v3 with valid SHA-256 over all stores')
        # Restore into separate temporary profile on same origin (fresh blank IDB).
        # A fresh browser context in persistent session has isolated storage by design.
        sub=context.browser.new_context(accept_downloads=True) if context.browser else None
        # persistent contexts do not expose browser: use a separate browser process via launch.
        b=browser_engine.launch(headless=True,args=['--no-sandbox'] if engine=='chromium' else [],executable_path='/usr/bin/chromium' if engine=='chromium' else None)
        sub=b.new_context(accept_downloads=True,service_workers='allow',executable_path='/usr/bin/chromium' if engine=='chromium' else None);rest=sub.new_page()
        rest.on('dialog',lambda d:d.accept())
        rest.goto(base+'index.html',wait_until='domcontentloaded')
        rest.locator('[data-page="backup"]').click()
        filebytes=json.dumps(exported,ensure_ascii=False).encode()
        rest.locator('#import-file').set_input_files({'name':'synthetic-v3.json','mimeType':'application/json','buffer':filebytes})
        rest.wait_for_function('document.querySelector("#checkpoint-button")?.disabled===false')
        assert rest.locator('#import-button').is_disabled()
        ok('Import v3 preview requires checkpoint; cannot import directly')
        with rest.expect_download(timeout=15000) as d:rest.locator('#checkpoint-button').click()
        checkpoint=json.loads(Path(d.value.path()).read_text('utf8'))
        cp_sha=checkpoint.pop('sha256')
        assert sha256(canonical(checkpoint).encode()).hexdigest()==cp_sha
        assert all(len(checkpoint['data'][name])==0 for name in STORE)
        ok('Pre-import protective checkpoint downloads a valid consistent v3 empty snapshot')
        assert rest.locator('#import-button').is_disabled()
        rest.locator('#checkpoint-ack').check()
        assert rest.locator('#import-button').is_enabled()
        rest.locator('#import-button').click()
        rest.wait_for_function('document.querySelector("#stat-meds")?.textContent==="1"')
        restored=dbrows(rest)
        assert {k:len(v) for k,v in restored.items()}=={k:len(v) for k,v in exported['data'].items()}
        ok('Explicit checkpoint acknowledgement enables atomic restore of all four stores')
        # Corrupted file must fail closed, preserving existing records.
        bad=json.loads(json.dumps(exported));bad['data']['medications'][0]['dose']='TAMPERED'
        rest.locator('#import-file').set_input_files({'name':'corrupted.json','mimeType':'application/json','buffer':json.dumps(bad,ensure_ascii=False).encode()})
        rest.wait_for_function('document.querySelector("#import-preview")?.textContent?.includes("SHA-256")')
        assert rest.locator('#import-button').is_disabled()
        assert len(dbrows(rest)['intakes'])==2
        ok('Tampered backup rejected without altering stored intakes')
        # Checkpoint invalidated if underlying database changes after download.
        rest.locator('#import-file').set_input_files({'name':'synthetic-v3.json','mimeType':'application/json','buffer':filebytes})
        rest.wait_for_function('document.querySelector("#checkpoint-button")?.disabled===false')
        with rest.expect_download(timeout=15000):rest.locator('#checkpoint-button').click()
        rest.locator('#checkpoint-ack').check()
        rest.locator('[data-page="pressure"]').click()
        rest.locator('#systolic').fill('122');rest.locator('#diastolic').fill('78');rest.locator('#pulse').fill('70');rest.locator('#pressure-datetime').fill('2024-06-10T09:30')
        rest.locator('#pressure-form button[type="submit"]').click()
        rest.wait_for_function('document.querySelector("#stat-pressure")?.textContent==="2"')
        rest.locator('[data-page="backup"]').click()
        rest.locator('#import-button').click()
        rest.wait_for_function('document.querySelector("#messages")?.textContent?.includes("База изменилась")')
        assert rest.locator('#import-button').is_disabled()
        assert len(dbrows(rest)['pressures'])==2
        ok('Changed database after checkpoint blocks import and requires fresh checkpoint')
        assert not errors,errors
        assert not outsiders,outsiders
        ok('No page JS errors or external origin requests in primary TEST browser')
        # Browser persistence and ServiceWorker cached offline across new page.
        page.wait_for_function('Boolean(navigator.serviceWorker.controller)',timeout=15000)
        page.close()
        offline=context.new_page()
        offline.goto(base+'index.html',wait_until='domcontentloaded')
        assert len(dbrows(offline)['pressures'])==1
        ok('Reload/new tab retains synthetic data in real IndexedDB')
        if engine=='chromium':
            context.set_offline(True)
            offline.reload(wait_until='domcontentloaded',timeout=15000)
            assert len(dbrows(offline)['intakes'])==2
            context.set_offline(False)
            ok('Real Chromium network-offline SW restart preserves two intakes')
        else:
            # WebKit Playwright context.set_offline may raise unrelated internal error; test origin-down route.
            server.shutdown();server.server_close();server=None
            offline.reload(wait_until='domcontentloaded',timeout=15000)
            assert len(dbrows(offline)['intakes'])==2
            ok('WebKit origin-down cached restart preserves two intakes')
        sub.close();b.close()
        context.close();context=None
        log.append(f'RESULT=PASS ENGINE={engine} CHECKS={count} MODE=REAL_BROWSER_INDEXEDDB_AND_SW SYNTHETIC_ONLY')
        return count
    except Exception as e:
        log.append('RESULT=FAIL ENGINE='+engine+' CHECKS_BEFORE_FAILURE='+str(count)+' '+repr(e))
        log.append(traceback.format_exc())
        try:
            if 'page' in locals() and not page.is_closed():page.screenshot(path=str(REPORT/f'{engine}_fail.png'))
        except Exception:pass
        return None
    finally:
        try:
            if context:context.close()
        except Exception:pass
        if server:
            try:server.shutdown();server.server_close()
            except Exception:pass

if __name__=='__main__':
    overall=True
    with sync_playwright() as p:
        for engine in (sys.argv[1:] or ['chromium','webkit']):
            lines=[]
            got=check_engine(p,engine,lines)
            (REPORT/f'{engine}_real_browser.log').write_text('\n'.join(lines)+'\n')
            print('\n'.join(lines),flush=True)
            overall=overall and got is not None
    sys.exit(0 if overall else 1)
