#!/usr/bin/env python3
"""PAE-04 v05.4 synthetic only. Browser QA for read-only search and standalone SHA256 backup verification."""
from pathlib import Path
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
import json, sys, traceback
ENGINE=sys.argv[1]
if ENGINE not in ('chromium','webkit'):raise SystemExit('Unsupported engine')
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports';OUT.mkdir(exist_ok=True)
class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*a,**kw):super().__init__(*a,directory=str(ROOT/'site'),**kw)
    def log_message(self,*a):pass
http=ThreadingHTTPServer(('127.0.0.1',0),Handler)
thread=Thread(target=http.serve_forever,daemon=True);thread.start()
results={'engine':ENGINE,'status':'FAIL','checks':[]}
def ok(msg):
    results['checks'].append(msg)
    print('PASS '+str(len(results['checks']))+' '+msg,flush=True)
def read_all(page):
    return page.evaluate("async()=>await readBackupSnapshot()")
try:
  with sync_playwright() as p:
    browser=getattr(p,ENGINE).launch(headless=True,args=['--no-sandbox'] if ENGINE=='chromium' else [])
    try:
      ctx=browser.new_context(viewport={'width':390,'height':844},accept_downloads=True,service_workers='allow')
      page=ctx.new_page()
      js_errors=[];external=[]
      page.on('pageerror',lambda e:js_errors.append(str(e)))
      page.on('request',lambda q:external.append(q.url) if urlparse(q.url).hostname not in ('127.0.0.1',None) else None)
      base='http://127.0.0.1:'+str(http.server_address[1])+'/index.html'
      page.goto(base,wait_until='domcontentloaded')
      page.locator('.brand small').wait_for()
      assert 'v05.4' in page.locator('.brand small').inner_text()
      ok('v05.4 version and local synthetic build present')
      page.locator('[data-page="pressure"]').click()
      for systolic,diastolic,when,note in ((121,79,'2024-06-10T09:00','Утро'),(132,84,'2024-06-11T18:00','Вечер')):
        page.locator('#systolic').fill(str(systolic))
        page.locator('#diastolic').fill(str(diastolic))
        page.locator('#pulse').fill('70')
        page.locator('#pressure-datetime').fill(when)
        page.locator('#pressure-note').fill(note)
        page.locator('#pressure-form button[type="submit"]').click()
        expected=1 if note=='Утро' else 2
        page.locator('#pressure-list .history-row').nth(expected-1).wait_for()
        assert page.locator('#pressure-list .history-row').count()==expected
      assert len(read_all(page)['pressures'])==2
      ok('Synthetic right-arm pressure records added unchanged schema')
      before=read_all(page)
      page.locator('#pressure-search').fill('Утро')
      assert page.locator('#pressure-list .history-row').count()==1
      assert '121 / 79' in page.locator('#pressure-list').inner_text()
      assert read_all(page)==before
      ok('Pressure note search read-only')
      page.locator('#pressure-search').fill('132/84')
      assert page.locator('#pressure-list .history-row').count()==1
      assert '132 / 84' in page.locator('#pressure-list').inner_text()
      page.locator('#pressure-search').fill('несуществующий')
      assert page.locator('#pressure-list .history-row').count()==0
      assert 'измерений нет' in page.locator('#pressure-list').inner_text()
      page.locator('#pressure-search').fill('')
      assert page.locator('#pressure-list .history-row').count()==2
      ok('Pressure numeric search, empty state and clear')
      page.locator('#pressure-filter').select_option('30')
      assert page.locator('#pressure-list .history-row').count()==0
      page.locator('#pressure-filter').select_option('0')
      assert page.locator('#pressure-list .history-row').count()==2
      assert read_all(page)==before
      ok('Pressure period filter stays compatible and preserves database')
      page.locator('[data-page="meds"]').click()
      for med in ('Учебный препарат А','Учебный препарат Б'):
        page.locator('#med-name').fill(med)
        page.locator('#med-form button[type="submit"]').click()
        expected=1 if med.endswith('А') else 2
        page.locator('#med-list .med-block').nth(expected-1).wait_for()
        assert page.locator('#med-list .med-block').count()==expected
      assert len(read_all(page)['medications'])==2
      ok('Two fictional medicine entries saved in legacy format')
      before_meds=read_all(page)
      page.locator('#med-search').fill('препарат Б')
      assert page.locator('#med-list .med-block').count()==1
      assert 'Учебный препарат Б' in page.locator('#med-list').inner_text()
      assert read_all(page)==before_meds
      ok('Medicine name search is view-only')
      page.locator('#med-search').fill('неизвестный')
      assert page.locator('#med-list .med-block').count()==0
      assert 'не найдены' in page.locator('#med-list').inner_text()
      page.locator('#med-search').fill('')
      assert page.locator('#med-list .med-block').count()==2
      ok('Medicine search empty state and reset')
      page.locator('[data-page="backup"]').click()
      assert 'JSON не зашифрован' in page.locator('#page-backup').inner_text()
      assert 'не выполняет импорт' in page.locator('#page-backup').inner_text()
      ok('Backup plaintext and no-import safety notices visible')
      with page.expect_download() as dl:
        page.locator('#export-button').click()
      content=Path(dl.value.path()).read_bytes()
      exported=json.loads(content.decode('utf-8'))
      assert exported['version']==3 and sorted(exported['data'])==sorted(['pressures','medications','intakes','intakeEvents'])
      ok('Original four-store v3 export retained')
      state_before=read_all(page)
      page.locator('#verify-file').set_input_files({'name':'synthetic-backup.json','mimeType':'application/json','buffer':content})
      page.locator('#verify-result .verify-pass').wait_for()
      message=page.locator('#verify-result').inner_text()
      assert 'SHA-256 совпадает' in message and '4 учебных записей' in message
      assert read_all(page)==state_before
      assert page.locator('#import-button').is_disabled()
      ok('Downloaded file integrity PASS; no import or IndexedDB changes')
      tampered=content.replace(b'"version": 3',b'"version": 2',1)
      assert tampered!=content
      page.locator('#verify-file').set_input_files({'name':'tampered.json','mimeType':'application/json','buffer':tampered})
      page.locator('#verify-result .verify-fail').wait_for()
      assert 'SHA-256 не совпадает' in page.locator('#verify-result').inner_text()
      assert read_all(page)==state_before
      ok('Tampered file FAIL with unchanged database')
      page.locator('#verify-file').set_input_files({'name':'malformed.json','mimeType':'application/json','buffer':b'{"not":'})
      page.locator('#verify-result .verify-fail').wait_for()
      assert read_all(page)==state_before
      ok('Malformed JSON FAIL without mutations')
      page.reload(wait_until='domcontentloaded')
      page.locator('#stat-pressure').filter(has_text='2').wait_for()
      assert read_all(page)==state_before
      assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
      assert not js_errors,js_errors
      assert not external,external
      ok('Reload preserves original data, mobile no overflow, no unexpected errors/network')
      results['status']='PASS'
    finally:
      browser.close()
except Exception as e:
  results['error']=str(e)
  results['traceback']=traceback.format_exc()
  print(results['traceback'],flush=True)
finally:
  http.shutdown();http.server_close();thread.join(timeout=5)
  (OUT/f'v052-{ENGINE}.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
  print('RESULT='+results['status']+' ENGINE='+ENGINE+' CHECKS='+str(len(results['checks'])),flush=True)
sys.exit(0 if results['status']=='PASS' else 1)
