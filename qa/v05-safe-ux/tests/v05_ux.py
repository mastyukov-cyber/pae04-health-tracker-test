#!/usr/bin/env python3
"""PAE-04 v05 safe-UX synthetic E2E. Loopback only; writes temp browser profiles, never live data."""
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from threading import Thread
from playwright.sync_api import sync_playwright
from urllib.parse import urlparse
from hashlib import sha256
import json,sys,traceback
SITE=Path(__file__).resolve().parents[1]/'site'
REPORT=Path(__file__).resolve().parents[1]/'reports'
REPORT.mkdir(exist_ok=True)
engine=sys.argv[1]
if engine not in ('chromium','webkit'): raise SystemExit('Use chromium or webkit')
class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs): super().__init__(*args,directory=str(SITE),**kwargs)
    def log_message(self,*args): pass
checks=[];errors=[];outside=[];ctx=None;browser=None
def pass_check(name):
    checks.append(name);print(f'PASS {len(checks)} {name}',flush=True)
def db_data(page):
    return page.evaluate("""async()=>{const n='PAE04_HT_STABLE_CANDIDATE_INTEGRATION_SYNTHETIC_SCHEMA1';const db=await new Promise((resolve,reject)=>{const q=indexedDB.open(n);q.onsuccess=()=>resolve(q.result);q.onerror=()=>reject(q.error)});const out={};for(const s of ['pressures','medications','intakes','intakeEvents']){out[s]=await new Promise((resolve,reject)=>{const t=db.transaction(s,'readonly');const q=t.objectStore(s).getAll();q.onsuccess=()=>resolve(q.result);q.onerror=()=>reject(q.error)})}db.close();return out}""")
server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
thread=Thread(target=server.serve_forever,daemon=True);thread.start()
result={'engine':engine,'status':'FAIL','checks':0}
try:
    with sync_playwright() as p:
        browser=getattr(p,engine).launch(headless=True,args=['--no-sandbox'] if engine=='chromium' else [])
        ctx=browser.new_context(viewport={'width':390,'height':844},accept_downloads=True,service_workers='allow')
        page=ctx.new_page()
        page.on('pageerror',lambda e: errors.append(str(e)))
        page.on('request',lambda req: outside.append(req.url) if urlparse(req.url).hostname not in ('127.0.0.1',None) else None)
        page.on('dialog',lambda d:d.accept())
        url='http://127.0.0.1:'+str(server.server_address[1])+'/index.html'
        page.goto(url,wait_until='domcontentloaded')
        page.locator('header .brand').wait_for()
        assert 'v05' in page.locator('header .brand').inner_text()
        assert page.locator('nav [data-page="meds"] .nav-icon').inner_text()=='💊'
        pass_check('Visible v05 build and pill navigation')
        page.locator('[data-page="pressure"]').click()
        page.locator('#systolic').fill('121')
        page.locator('#diastolic').fill('79')
        page.locator('#pulse').fill('70')
        page.locator('#pressure-datetime').fill('2024-06-10T09:00')
        page.locator('#pressure-form button[type="submit"]').click()
        page.locator('#pressure-count').get_by_text('1 записей').wait_for()
        before=db_data(page)
        assert len(before['pressures'])==1 and before['pressures'][0]['arm']=='right'
        pass_check('Right-arm pressure saved using unchanged database schema')
        page.locator('#pressure-filter').select_option('7')
        assert '0 из 1' in page.locator('#pressure-count').inner_text()
        page.locator('#pressure-filter').select_option('30')
        assert '0 из 1' in page.locator('#pressure-count').inner_text()
        page.locator('#pressure-filter').select_option('0')
        assert '1 записей' in page.locator('#pressure-count').inner_text()
        assert db_data(page)==before
        pass_check('Pressure 7/30/all filters preserve all stored rows')
        page.locator('[data-page="meds"]').click()
        page.locator('#med-name').fill('Учебный препарат А')
        page.locator('#med-dose').fill('Вымышленная дозировка')
        page.locator('#med-kind').select_option('regular')
        page.locator('#med-form button[type="submit"]').click()
        page.locator('#intake-date').fill('2024-06-10')
        page.locator('#med-list .med-time-controls input[type="time"]').fill('08:15')
        page.locator('#med-list .intake-confirm-button').click()
        page.locator('#med-list .intake-record').first.wait_for()
        assert len(db_data(page)['intakes'])==1
        pass_check('Original medicine confirmation and audit trail unchanged')
        page.locator('#intake-filter').select_option('active')
        assert page.locator('#intake-list .overview-row').count()==1
        page.locator('#intake-filter').select_option('cancelled')
        assert page.locator('#intake-list .overview-row').count()==0
        page.locator('#intake-filter').select_option('all')
        assert page.locator('#intake-list .overview-row').count()==1
        pass_check('Medicine active/cancelled/all filters show expected rows')
        page.locator('#med-list .intake-record').first.get_by_role('button',name='Отменить отметку').click()
        page.locator('#med-list .intake-record.cancelled').wait_for()
        current=db_data(page)
        assert len(current['intakeEvents'])==2
        page.locator('#intake-filter').select_option('cancelled')
        assert page.locator('#intake-list .overview-row').count()==1
        page.locator('#intake-filter').select_option('active')
        assert page.locator('#intake-list .overview-row').count()==0
        page.locator('#intake-filter').select_option('all')
        assert db_data(page)==current
        pass_check('Cancelled medicine event visible; audit data immutable to filters')
        page.locator('[data-page="backup"]').click()
        with page.expect_download() as download: page.locator('#export-button').click()
        exported=json.loads(Path(download.value.path()).read_text(encoding='utf-8'))
        assert exported['version']==3
        assert sorted(exported['data'])==sorted(['pressures','medications','intakes','intakeEvents'])
        assert len(exported['data']['intakeEvents'])==2
        pass_check('Unchanged v3 four-store export retains cancellation history')
        page.reload(wait_until='domcontentloaded')
        page.locator('[data-page="pressure"]').click()
        assert '1 записей' in page.locator('#pressure-count').inner_text()
        assert db_data(page)==current
        assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1')
        pass_check('390px mobile width has no horizontal overflow; reload preserves data')
        assert not errors, errors
        assert not outside, outside
        pass_check('No unexpected JS exceptions or third-party network requests')
        result={'engine':engine,'status':'PASS','checks':len(checks),'records':{k:len(v) for k,v in current.items()}}
except Exception as e:
    result={'engine':engine,'status':'FAIL','checks':len(checks),'error':str(e),'trace':traceback.format_exc()}
finally:
    if ctx: ctx.close()
    if browser: browser.close()
    server.shutdown();server.server_close();thread.join(timeout=5)
    (REPORT/f'v05-{engine}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    (REPORT/f'v05-{engine}.log').write_text('\n'.join(f'PASS {i+1} {s}' for i,s in enumerate(checks))+'\nRESULT='+result['status']+'\n',encoding='utf-8')
print('RESULT='+result['status']+' ENGINE='+engine+' CHECKS='+str(len(checks)),flush=True)
if result['status']!='PASS':print(result.get('trace',''),flush=True)
raise SystemExit(0 if result['status']=='PASS' else 1)
