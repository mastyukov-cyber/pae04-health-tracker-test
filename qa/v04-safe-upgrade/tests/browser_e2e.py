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
V03_DB='PAE04_HealthTracker_PWA_v021_INTEGRATION_SYNTHETIC_V03_CONFIRM_BUTTON_4STORE'
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

def wait_until(page, expression, timeout=15000):
    deadline = time.monotonic() + timeout / 1000
    while time.monotonic() < deadline:
        if page.evaluate(expression):
            return
        page.wait_for_timeout(100)
    raise AssertionError(f"Timed out waiting for browser condition: {expression}")

def dbrows(page,name=DB):
    return page.evaluate('''async(name)=>{const db=await new Promise((resolve,reject)=>{const r=indexedDB.open(name);r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error)});const names=[...db.objectStoreNames];const out={};for(const name of names){out[name]=await new Promise((resolve,reject)=>{const tx=db.transaction(name);const r=tx.objectStore(name).getAll();r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error)})}db.close();return out}''',name)

def check_engine(p,engine,log):
    count=0
    def ok(label):
        nonlocal count
        count+=1;log.append(f'PASS {count} {label}')
    context=None;server=None;thread=None
    errors=[];outsiders=[]
    log.append('REFERENCE_SET_OFFLINE_EMULATION=WebKit TypeError: Load failed in prior run 43420406244; separately retesting with the loopback origin stopped, without context.set_offline(True); related Playwright issue https://github.com/microsoft/playwright/issues/42775')
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
        wait_until(page, 'document.querySelector("#stat-pressure")?.textContent!==undefined',timeout=15000)
        wait_until(page, 'async()=>{const r=await navigator.serviceWorker.ready;return r.active?.state==="activated"}',timeout=20000)
        ok('ServiceWorker installed and activated on real browser')
        db=dbrows(page)
        assert sorted(db)==sorted(STORE)
        assert all(not db[s] for s in STORE)
        ok('Four real IndexedDB stores created with fixed build-independent name')
        page.locator('[data-page="pressure"]').click()
        page.locator('#systolic').fill('121');page.locator('#diastolic').fill('79');page.locator('#pulse').fill('70')
        page.locator('#pressure-datetime').fill('2024-06-10T09:00')
        page.locator('#pressure-form button[type="submit"]').click()
        wait_until(page, 'document.querySelector("#stat-pressure")?.textContent==="1"')
        assert dbrows(page)['pressures'][0]['arm']=='right'
        ok('Synthetic manual right-arm pressure persisted')
        page.locator('[data-page="meds"]').click()
        page.locator('#med-name').fill('Учебный препарат А');page.locator('#med-dose').fill('Учебная дозировка')
        page.locator('#med-kind').select_option('regular');page.locator('#med-strength').fill('10');page.locator('#med-unit').select_option(label='мг');page.locator('#med-form-factor').select_option(label='таблетки')
        page.locator('#med-form button[type="submit"]').click()
        wait_until(page, 'document.querySelector("#stat-meds")?.textContent==="1"')
        page.locator('#intake-date').fill('2024-06-10')
        page.locator('#med-list .med-time-controls input[type="time"]').fill('08:15')
        page.locator('#med-list .intake-confirm-button').click()
        wait_until(page, 'document.querySelectorAll("#med-list .intake-record").length===1')
        page.locator('#med-list .med-time-controls input[type="time"]').fill('20:15')
        page.locator('#med-list .intake-confirm-button').click()
        wait_until(page, 'document.querySelectorAll("#med-list .intake-record").length===2')
        assert len(dbrows(page)['intakeEvents'])==2
        ok('Two same-day medicine intakes with distinct audit events')
        page.locator('#med-list .intake-confirm-button').click()
        page.wait_for_timeout(200)
        assert len(dbrows(page)['intakes'])==2
        ok('Same-time duplicate confirmation does not create extra record')
        initial_intakes=dbrows(page)['intakes']
        target_intake=next(x for x in initial_intakes if x.get('takenAtLocal')=='2024-06-10T08:15')
        first_id=target_intake['id'];first_marked=target_intake['markedAt']
        first_row=page.locator('#med-list .intake-record').first
        first_row.locator('input[type="time"]').fill('09:10')
        first_row.get_by_role('button',name='Изменить время').click()
        wait_until(page, 'document.querySelector("#med-list")?.textContent?.includes("08:15 → 09:10")')
        changed=dbrows(page)
        corrected=next(x for x in changed['intakes'] if x['id']==first_id)
        assert corrected['takenAtLocal']=='2024-06-10T09:10' and corrected['markedAt']==first_marked
        assert len(changed['intakeEvents'])==3
        ok('Synthetic intake time corrected with original mark preserved and audit event added')
        page.locator('#med-list .intake-record').nth(1).get_by_role('button',name='Отменить отметку').click()
        wait_until(page, 'document.querySelectorAll("#med-list .intake-record.cancelled").length===1')
        cancelled=dbrows(page)
        assert len(cancelled['intakes'])==2 and sum(1 for x in cancelled['intakes'] if x.get('status')=='cancelled')==1
        assert len(cancelled['intakeEvents'])==4
        ok('Synthetic intake cancellation retains history and appends audit event')
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

        # Seed a filled synthetic v03-origin IndexedDB profile, then reopen the v04 app.
        upgrade=b.new_context(accept_downloads=True,service_workers='allow')
        seed=upgrade.new_page()
        seed.goto(base+'index.html',wait_until='domcontentloaded')
        wait_until(seed, 'document.querySelector("#stat-pressure")?.textContent==="0"')
        seed_rows={
            'pressures':[{'id':'v03-pressure-0001','systolic':120,'diastolic':80,'pulse':70,'dateTime':'2024-06-10T09:00','note':'Синтетическая запись v03','arm':'right','createdAt':'2024-06-10T09:00:00.000Z'}],
            'medications':[{'id':'v03-medication-01','name':'Учебный препарат v03','dose':'10 мг','kind':'regular','from':None,'to':None,'createdAt':'2024-06-10T09:00:00.000Z'}],
            'intakes':[{'id':'v03-intake-0001','medId':'v03-medication-01','date':'2024-06-10','markedAt':'2024-06-10T08:15:00.000Z','takenAtLocal':'2024-06-10T08:15'}],
            'intakeEvents':[{'id':'v03-event-0001','intakeId':'v03-intake-0001','medId':'v03-medication-01','action':'marked','at':'2024-06-10T08:15:00.000Z','newTakenAtLocal':'2024-06-10T08:15'}]
        }
        seeded=seed.evaluate('''async({name,rows})=>{const db=await new Promise((resolve,reject)=>{const r=indexedDB.open(name,1);r.onupgradeneeded=()=>{const p=r.result.createObjectStore('pressures',{keyPath:'id'});const m=r.result.createObjectStore('medications',{keyPath:'id'});const i=r.result.createObjectStore('intakes',{keyPath:'id'});i.createIndex('byMedDay',['medId','date'],{unique:false});const e=r.result.createObjectStore('intakeEvents',{keyPath:'id'});e.createIndex('byIntakeId','intakeId',{unique:false})};r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error)});await new Promise((resolve,reject)=>{const tx=db.transaction(['pressures','medications','intakes','intakeEvents'],'readwrite');for(const n of Object.keys(rows))for(const row of rows[n])tx.objectStore(n).add(row);tx.oncomplete=resolve;tx.onabort=()=>reject(tx.error)});db.close();return true}''',{'name':V03_DB,'rows':seed_rows})
        assert seeded is True
        v03_profile=dbrows(seed,V03_DB)
        assert {k:len(v) for k,v in v03_profile.items()}=={k:1 for k in STORE}
        seed.close()
        upgrade_page=upgrade.new_page()
        upgrade_page.on('dialog',lambda d:d.accept())
        upgrade_page.goto(base+'index.html',wait_until='domcontentloaded')
        wait_until(upgrade_page, 'document.querySelector("#stat-pressure")?.textContent==="0"&&document.querySelector("#stat-meds")?.textContent==="0"')
        assert all(not v for v in dbrows(upgrade_page).values())
        assert dbrows(upgrade_page,V03_DB)==v03_profile
        ok('Fresh v04 startup does not auto-migrate or hide/delete a filled synthetic v03 database')
        v03_body={'format':exported['format'],'version':3,'exportedAt':'2026-11-13T10:00:00.000Z','data':v03_profile}
        v03_backup={**v03_body,'sha256':sha256(canonical(v03_body).encode()).hexdigest()}
        upgrade_page.locator('[data-page="backup"]').click()
        upgrade_page.locator('#import-file').set_input_files({'name':'synthetic-v03-profile-backup-v3.json','mimeType':'application/json','buffer':json.dumps(v03_backup,ensure_ascii=False).encode()})
        wait_until(upgrade_page, 'document.querySelector("#checkpoint-button")?.disabled===false')
        with upgrade_page.expect_download(timeout=15000): upgrade_page.locator('#checkpoint-button').click()
        upgrade_page.locator('#checkpoint-ack').check()
        assert upgrade_page.locator('#import-button').is_enabled()
        upgrade_page.locator('#import-button').click()
        wait_until(upgrade_page, 'document.querySelector("#stat-pressure")?.textContent==="1"&&document.querySelector("#stat-meds")?.textContent==="1"')
        transferred=dbrows(upgrade_page)
        assert transferred==v03_profile and dbrows(upgrade_page,V03_DB)==v03_profile
        ok('Synthetic v03 profile safely transfers only through confirmed v3 backup; source remains unchanged')
        upgrade.close()

        sub=b.new_context(accept_downloads=True,service_workers='allow');rest=sub.new_page()
        rest.on('dialog',lambda d:d.accept())
        rest.goto(base+'index.html',wait_until='domcontentloaded')
        rest.locator('[data-page="backup"]').click()
        filebytes=json.dumps(exported,ensure_ascii=False).encode()
        rest.locator('#import-file').set_input_files({'name':'synthetic-v3.json','mimeType':'application/json','buffer':filebytes})
        wait_until(rest, 'document.querySelector("#checkpoint-button")?.disabled===false')
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
        wait_until(rest, 'document.querySelector("#stat-meds")?.textContent==="1"')
        restored=dbrows(rest)
        assert {k:len(v) for k,v in restored.items()}=={k:len(v) for k,v in exported['data'].items()}
        ok('Explicit checkpoint acknowledgement enables atomic restore of all four stores')
        # Import actual legacy v1/v2 synthetic fixture shapes into isolated browser profiles.
        for version in (1,2):
            legacy_med={'id':f'synthetic-medicine-v{version}','name':'Учебный препарат Б','dose':'Тестовая дозировка','kind':'regular','from':None,'to':None,'createdAt':'2024-06-10T09:00:00Z'}
            legacy_intake={'id':f'synthetic-intake-v{version}','medId':legacy_med['id'],'date':'2024-06-10','markedAt':'2024-06-10T08:15:00Z'}
            if version==2: legacy_intake['takenAtLocal']='2024-06-10T08:15'
            legacy_body={'format':exported['format'],'version':version,'exportedAt':'2026-11-12T10:10:00.000Z','data':{'pressures':[],'medications':[legacy_med],'intakes':[legacy_intake]}}
            legacy={**legacy_body,'sha256':sha256(canonical(legacy_body).encode()).hexdigest()}
            stage=b.new_context(accept_downloads=True,service_workers='allow')
            legacy_page=stage.new_page()
            legacy_page.on('dialog',lambda d:d.accept())
            legacy_page.goto(base+'index.html',wait_until='domcontentloaded')
            legacy_page.locator('[data-page="backup"]').click()
            legacy_bytes=json.dumps(legacy,ensure_ascii=False).encode()
            legacy_page.locator('#import-file').set_input_files({'name':f'synthetic-v{version}.json','mimeType':'application/json','buffer':legacy_bytes})
            wait_until(legacy_page, 'document.querySelector("#checkpoint-button")?.disabled===false')
            with legacy_page.expect_download(timeout=15000): legacy_page.locator('#checkpoint-button').click()
            legacy_page.locator('#checkpoint-ack').check()
            assert legacy_page.locator('#import-button').is_enabled()
            legacy_page.locator('#import-button').click()
            wait_until(legacy_page, 'document.querySelector("#stat-meds")?.textContent==="1"')
            legacy_db=dbrows(legacy_page)
            assert len(legacy_db['medications'])==1 and len(legacy_db['intakes'])==1 and len(legacy_db['intakeEvents'])==0
            if version==1: assert 'takenAtLocal' not in legacy_db['intakes'][0]
            else: assert legacy_db['intakes'][0]['takenAtLocal']=='2024-06-10T08:15'
            stage.close()
            ok(f'Real {engine} browser imports synthetic legacy v{version} after a protective checkpoint')

        # Corrupted file must fail closed, preserving existing records.
        bad=json.loads(json.dumps(exported));bad['data']['medications'][0]['dose']='TAMPERED'
        rest.locator('#import-file').set_input_files({'name':'corrupted.json','mimeType':'application/json','buffer':json.dumps(bad,ensure_ascii=False).encode()})
        wait_until(rest, 'document.querySelector("#import-preview")?.textContent?.includes("SHA-256")')
        assert rest.locator('#import-button').is_disabled()
        assert len(dbrows(rest)['intakes'])==2
        ok('Tampered backup rejected without altering stored intakes')
        before_conflict=dbrows(rest)
        conflict=json.loads(json.dumps(exported))
        conflict['data']['medications'][0]['dose']='Изменённое тестовое содержимое с тем же ID'
        conflict_body={k:v for k,v in conflict.items() if k!='sha256'}
        conflict['sha256']=sha256(canonical(conflict_body).encode()).hexdigest()
        rest.locator('#import-file').set_input_files({'name':'synthetic-same-id-conflict.json','mimeType':'application/json','buffer':json.dumps(conflict,ensure_ascii=False).encode()})
        wait_until(rest, 'document.querySelector("#import-preview")?.textContent?.includes("Конфликтов: 1")')
        assert rest.locator('#import-button').is_disabled()
        assert dbrows(rest)==before_conflict
        ok('Same-ID different-content conflict is blocked without overwriting existing data')

        rollback=rest.evaluate('''async()=>{
          const names=['pressures','medications','intakes','intakeEvents'];
          const read=async()=>{const out={};for(const name of names)out[name]=await getAll(name);return out};
          const before=await read();
          const first=before.pressures[0];
          const newPressure={...first,id:'rollback-pressure-01'};
          const conflictingPressure={...first,note:'намеренно отличающееся содержимое'};
          const newMedication={...before.medications[0],id:'rollback-medication-01',name:'Учебный препарат rollback'};
          const newIntake={...before.intakes[0],id:'rollback-intake-0001',status:'cancelled',cancelledAt:'2024-06-10T10:00:00.000Z'};
          const newEvent={...before.intakeEvents[0],id:'rollback-event-0001',intakeId:newIntake.id,action:'cancelled',at:'2024-06-10T10:00:00.000Z',oldTakenAtLocal:before.intakes[0].takenAtLocal};
          let failed=false;try{await atomicMerge({pressures:[newPressure,conflictingPressure],medications:[newMedication],intakes:[newIntake],intakeEvents:[newEvent]})}catch{failed=true}
          const after=await read();return {failed,before,after};
        }''')
        assert rollback['failed'] is True and rollback['before']==rollback['after']
        assert set(rollback['before'])==set(STORE)
        ok('Intentional IndexedDB transaction failure rolls back writes across all four stores')

        # Checkpoint invalidated if underlying database changes after download.
        rest.locator('#import-file').set_input_files({'name':'synthetic-v3.json','mimeType':'application/json','buffer':filebytes})
        wait_until(rest, 'document.querySelector("#checkpoint-button")?.disabled===false')
        with rest.expect_download(timeout=15000):rest.locator('#checkpoint-button').click()
        rest.locator('#checkpoint-ack').check()
        rest.locator('[data-page="pressure"]').click()
        rest.locator('#systolic').fill('122');rest.locator('#diastolic').fill('78');rest.locator('#pulse').fill('70');rest.locator('#pressure-datetime').fill('2024-06-10T09:30')
        rest.locator('#pressure-form button[type="submit"]').click()
        wait_until(rest, 'document.querySelector("#stat-pressure")?.textContent==="2"')
        rest.locator('[data-page="backup"]').click()
        rest.locator('#import-button').click()
        wait_until(rest, 'document.querySelector("#messages")?.textContent?.includes("База изменилась")')
        assert rest.locator('#import-button').is_disabled()
        assert len(dbrows(rest)['pressures'])==2
        ok('Changed database after checkpoint blocks import and requires fresh checkpoint')
        assert not errors,errors
        assert not outsiders,outsiders
        ok('No page JS errors or external origin requests in primary TEST browser')
        # Check cache and controlling SW, then stop only the ephemeral HTTP origin.
        wait_until(page, 'Boolean(navigator.serviceWorker.controller)',timeout=15000)
        cache_state=page.evaluate('''async()=>{const reg=await navigator.serviceWorker.ready;const cache=await caches.open('pae04-ht-stable-candidate-synthetic-schema1-cache-v04-20261113');const response=await cache.match(new URL('./index.html',location.href).href);return {controller:Boolean(navigator.serviceWorker.controller),active:reg.active?.state,cachedIndex:Boolean(response)}}''')
        assert cache_state=={'controller':True,'active':'activated','cachedIndex':True}
        page.close()
        offline=context.new_page()
        offline.goto(base+'index.html',wait_until='domcontentloaded')
        wait_until(offline, 'Boolean(navigator.serviceWorker.controller)',timeout=15000)
        before_offline=dbrows(offline)
        assert len(before_offline['pressures'])==1 and len(before_offline['intakes'])==2
        ok(f'{engine}: cached index.html exists and new page is controlled by active Service Worker')
        server.shutdown();server.server_close()
        if thread:thread.join(timeout=5)
        server=None
        response=offline.reload(wait_until='domcontentloaded',timeout=20000)
        assert response is not None and response.from_service_worker()
        assert 'HEALTH TRACKER' in offline.title().upper()
        assert dbrows(offline)==before_offline
        missing=offline.evaluate("fetch('./__uncached_v04_qa_resource__').then(()=>({ok:true}),e=>({ok:false,name:e.name}))")
        assert missing['ok'] is False
        log.append(f'OFFLINE_ORIGIN_STOPPED=PASS ENGINE={engine} reload_from_service_worker=true indexeddb_unchanged=true uncached_request_rejected=true context.set_offline_not_used')
        ok(f'Real {engine} origin-stopped offline reload uses SW cache, retains IndexedDB, and rejects uncached request')
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
