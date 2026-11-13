#!/usr/bin/env python3
"""PAE-04 v05.5 synthetic Data Safety Gate. Never touches personal records."""
from pathlib import Path
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
import json,sys,traceback
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect

engine=sys.argv[1]
if engine not in ('chromium','webkit'):raise SystemExit('unsupported engine')
ROOT=Path(__file__).resolve().parents[1]
SITES={'v05.3':ROOT/'fixtures'/'v053',
       'v05.4':ROOT.parent/'v054-date-wheels'/'site',
       'v05.5':ROOT/'site'}
REPORTS=ROOT/'reports';REPORTS.mkdir(exist_ok=True)
state={'path':SITES['v05.5']}
class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*a,**kw):super().__init__(*a,directory=str(state['path']),**kw)
 def log_message(self,*a):pass
http=ThreadingHTTPServer(('127.0.0.1',0),Handler)
thread=Thread(target=http.serve_forever,daemon=True);thread.start()
result={'engine':engine,'passed':[],'status':'FAIL'}
def ok(msg):
 result['passed'].append(msg)
 print('PASS '+str(len(result['passed']))+' '+msg,flush=True)
def db(page):return page.evaluate('async()=>await readBackupSnapshot()')
def assert_counts(data,expected):assert [len(data[n]) for n in ['pressures','medications','intakes','intakeEvents']]==expected
def wait_count(page,id,n):
 page.locator('#'+id).get_by_text(str(n),exact=True).wait_for()
def new_server(directory):
 class Fixed(SimpleHTTPRequestHandler):
  def __init__(self,*a,**kw):super().__init__(*a,directory=str(directory),**kw)
  def log_message(self,*a):pass
 srv=ThreadingHTTPServer(('127.0.0.1',0),Fixed)
 worker=Thread(target=srv.serve_forever,daemon=True);worker.start()
 return srv,worker

receiver_server=None;receiver_thread=None
try:
 with sync_playwright() as p:
  browser=getattr(p,engine).launch(headless=True,args=['--no-sandbox'] if engine=='chromium' else [])
  try:
   ctx=browser.new_context(viewport={'width':390,'height':844},accept_downloads=True,service_workers='allow')
   page=ctx.new_page();errors=[];external=[]
   page.on('pageerror',lambda e:errors.append(str(e)))
   page.on('request',lambda q:external.append(q.url) if urlparse(q.url).hostname not in ('127.0.0.1',None) else None)
   base='http://127.0.0.1:'+str(http.server_address[1])+'/'
   page.goto(base+'index.html',wait_until='domcontentloaded')
   page.locator('.brand small').wait_for()
   assert 'v05.5' in page.locator('.brand small').inner_text()
   ok('v05.5 isolated synthetic build loads')
   page.locator('[data-page=backup]').click()
   page.locator('#safety-db-status.safety-good').wait_for()
   assert 'PASS' in page.locator('#safety-db-status').inner_text()
   assert_counts(db(page),[0,0,0,0])
   ok('First startup automatically verifies empty local DB without modifying it')
   browser_status=page.locator('#safety-browser-status')
   expect(browser_status).not_to_have_text('Статус неизвестен',timeout=10000)
   assert 'Не подтверждена' in page.locator('#safety-copy-status').inner_text()
   ok('Storage status is read-only and no false external backup assurance')
   page.locator('#safety-check').click()
   page.locator('#safety-db-status.safety-good').wait_for()
   assert_counts(db(page),[0,0,0,0])
   ok('Manual integrity scan is read-only')
   page.locator('[data-page=pressure]').click()
   page.locator('#systolic').fill('121')
   page.locator('#diastolic').fill('79')
   page.locator('#pulse').fill('70')
   page.locator('#pressure-datetime').fill('2024-06-10T09:00')
   page.locator('#pressure-form button[type=submit]').click()
   page.locator('#pressure-list .history-row').first.wait_for()
   assert_counts(db(page),[1,0,0,0])
   assert 'повторно прочитано' in page.locator('#messages').inner_text()
   ok('Pressure transaction commits and record verified by fresh IndexedDB read')
   page.locator('[data-page=backup]').click()
   assert 'повторите проверку' in page.locator('#safety-db-status').inner_text()
   assert 'не проверена' in page.locator('#safety-copy-status').inner_text()
   page.locator('#safety-check').click()
   page.locator('#safety-db-status.safety-good').wait_for()
   assert '1 записей' in page.locator('#safety-db-status').inner_text()
   ok('Mutation invalidates previous scan; new digest verifies actual DB')
   page.locator('[data-page=meds]').click()
   page.locator('#med-name').fill('Учебный препарат А')
   page.locator('#med-kind').select_option('regular')
   page.locator('#med-form button[type=submit]').click()
   page.locator('#med-list .med-block').first.wait_for()
   assert_counts(db(page),[1,1,0,0])
   ok('Medication transaction commits and record verified by fresh read')
   page.locator('#intake-date').fill('2024-06-10')
   page.locator('#med-list .med-time-controls input[type=time]').fill('08:15')
   page.locator('#med-list .intake-confirm-button').click()
   page.locator('#med-list .intake-record').first.wait_for()
   d=db(page);assert_counts(d,[1,1,1,1])
   assert d['intakeEvents'][0]['intakeId']==d['intakes'][0]['id']
   ok('Intake and audit event saved atomically and both confirmed after commit')
   page.locator('[data-page=backup]').click()
   page.locator('#safety-check').click()
   page.locator('#safety-db-status.safety-good').wait_for()
   assert '4 записей' in page.locator('#safety-db-status').inner_text()
   ok('Cross-store integrity audit validates referential links and count')
   with page.expect_download() as dl:
    page.locator('#export-button').click()
   file_bytes=Path(dl.value.path()).read_bytes()
   backup=json.loads(file_bytes.decode('utf-8'))
   assert backup['version']==3 and set(backup['data'])=={'pressures','medications','intakes','intakeEvents'}
   assert_counts(backup['data'],[1,1,1,1])
   ok('Independent v3 JSON export retains all four stores')
   page.locator('#verify-file').set_input_files({'name':'synthetic-v055.json','mimeType':'application/json','buffer':file_bytes})
   page.locator('#verify-result .verify-pass').wait_for()
   assert 'совпал с текущей базой' in page.locator('#safety-copy-status').inner_text()
   assert_counts(db(page),[1,1,1,1])
   ok('Selected backup SHA-256 passes and matches CURRENT database without import')
   page.locator('[data-page=pressure]').click()
   page.locator('#systolic').fill('129')
   page.locator('#diastolic').fill('82')
   page.locator('#pulse').fill('66')
   page.locator('#pressure-datetime').fill('2024-06-11T09:00')
   page.locator('#pressure-form button[type=submit]').click()
   page.locator('#pressure-list .history-row').nth(1).wait_for()
   assert_counts(db(page),[2,1,1,1])
   page.locator('[data-page=backup]').click()
   assert 'не проверена' in page.locator('#safety-copy-status').inner_text()
   page.locator('#verify-file').set_input_files({'name':'synthetic-old.json','mimeType':'application/json','buffer':file_bytes})
   page.locator('#verify-result .verify-pass').wait_for()
   assert 'отличается' in page.locator('#safety-copy-status').inner_text()
   ok('Older integrity-valid backup must NOT be reported as current')
   damaged=file_bytes.replace(b'"version": 3',b'"version": 2',1)
   assert damaged!=file_bytes
   page.locator('#verify-file').set_input_files({'name':'damaged.json','mimeType':'application/json','buffer':damaged})
   page.locator('#verify-result .verify-fail').wait_for()
   assert 'отклонён' in page.locator('#safety-copy-status').inner_text()
   assert_counts(db(page),[2,1,1,1])
   ok('Tampered backup blocked; local records unchanged')
   page.reload(wait_until='domcontentloaded')
   page.locator('#stat-pressure').filter(has_text='2').wait_for()
   assert_counts(db(page),[2,1,1,1])
   page.locator('[data-page=backup]').click()
   page.locator('#safety-db-status.safety-good').wait_for()
   ok('App reload preserves all rows, auto-runs integrity scan')
   receiver_server,receiver_thread=new_server(SITES['v05.5'])
   receive_url='http://127.0.0.1:'+str(receiver_server.server_address[1])+'/'
   receive_ctx=browser.new_context(viewport={'width':390,'height':844},accept_downloads=True,service_workers='allow')
   receiver=receive_ctx.new_page()
   receiver.goto(receive_url+'index.html',wait_until='domcontentloaded')
   receiver.locator('#stat-pressure').filter(has_text='0').wait_for()
   assert_counts(db(receiver),[0,0,0,0])
   ok('Separate origin simulates another device with empty local DB')
   receiver.locator('[data-page=backup]').click()
   receiver.locator('#import-file').set_input_files({'name':'migrated-backup.json','mimeType':'application/json','buffer':file_bytes})
   expect(receiver.locator('#checkpoint-button')).to_be_enabled(timeout=10000)
   with receiver.expect_download() as checkpoint:
    receiver.locator('#checkpoint-button').click()
   checkpoint_bytes=Path(checkpoint.value.path()).read_bytes()
   assert json.loads(checkpoint_bytes)['version']==3
   expect(receiver.locator('#checkpoint-ack')).to_be_enabled(timeout=10000)
   receiver.locator('#checkpoint-ack').check()
   receiver.once('dialog',lambda d:d.accept())
   receiver.locator('#import-button').click()
   expect(receiver.locator('#stat-pressure')).to_have_text('1',timeout=10000)
   restored=db(receiver)
   assert_counts(restored,[1,1,1,1])
   for store in restored:
    assert restored[store]==backup['data'][store],store
   ok('Cross-origin restore with verified SHA, pre-import checkpoint, and all records exact')
   receive_ctx.close()
   upgrade={'path':SITES['v05.5']}
   class Upgrade(SimpleHTTPRequestHandler):
    def __init__(self,*a,**kw):super().__init__(*a,directory=str(upgrade['path']),**kw)
    def log_message(self,*a):pass
    def send_head(self):
     if 'If-Modified-Since' in self.headers:del self.headers['If-Modified-Since']
     return super().send_head()
    def end_headers(self):
     self.send_header('Cache-Control','no-store, max-age=0')
     super().end_headers()
   upgrade_server=ThreadingHTTPServer(('127.0.0.1',0),Upgrade)
   upgrade_thread=Thread(target=upgrade_server.serve_forever,daemon=True)
   upgrade_thread.start()
   try:
    upctx=browser.new_context(viewport={'width':390,'height':844},service_workers='block')
    upgrade_page=upctx.new_page()
    url='http://127.0.0.1:'+str(upgrade_server.server_address[1])+'/index.html'
    upgrade_page.goto(url,wait_until='domcontentloaded')
    assert upgrade_page.url==url
    expect(upgrade_page.locator('#stat-pressure')).to_have_text('0',timeout=10000)
    upgrade_page.locator('[data-page=pressure]').click()
    upgrade_page.locator('#systolic').fill('116')
    upgrade_page.locator('#diastolic').fill('74')
    upgrade_page.locator('#pressure-datetime').fill('2024-01-09T08:30')
    upgrade_page.locator('#pressure-form button[type=submit]').click()
    expect(upgrade_page.locator('#stat-pressure')).to_have_text('1',timeout=10000)
    stable=db(upgrade_page)
    assert_counts(stable,[1,0,0,0])
    versions=['v05.3','v05.4','v05.5','v05.4','v05.3','v05.5','v05.3','v05.4','v05.5','v05.5']
    for idx,version in enumerate(versions,1):
     upgrade['path']=SITES[version]
     upgrade_page.reload(wait_until='domcontentloaded')
     upgrade_page.locator('.brand small').filter(has_text=version).wait_for()
     expect(upgrade_page.locator('#stat-pressure')).to_have_text('1',timeout=10000)
     assert db(upgrade_page)==stable,(idx,version)
     ok('Upgrade cycle '+str(idx)+'/10 version '+version+' preserves exact IndexedDB records')
    upctx.close()
   finally:
    upgrade_server.shutdown();upgrade_server.server_close();upgrade_thread.join(timeout=5)
   assert not errors,errors
   assert not external,external
   ok('No JS errors or external network calls in privacy-preserving safety QA')
   result['status']='PASS'
  finally: browser.close()
except Exception as e:
 result['error']=str(e)
 result['traceback']=traceback.format_exc()
 print(result['traceback'],flush=True)
finally:
 http.shutdown();http.server_close();thread.join(timeout=5)
 if receiver_server:
  receiver_server.shutdown();receiver_server.server_close();receiver_thread.join(timeout=5)
 (REPORTS/f'data-safety-{engine}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print('RESULT='+result['status']+' ENGINE='+engine+' CHECKS='+str(len(result['passed'])),flush=True)
sys.exit(0 if result['status']=='PASS' else 1)
