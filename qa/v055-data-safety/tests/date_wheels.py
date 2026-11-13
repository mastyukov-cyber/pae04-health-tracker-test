#!/usr/bin/env python3
"""Synthetic-only real-browser QA: v05.5 date wheels, calendar removal, ISO persistence."""
from pathlib import Path
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import urlparse
import json, sys, traceback
from playwright.sync_api import sync_playwright
engine=sys.argv[1]
if engine not in ('chromium','webkit'):raise SystemExit('invalid engine')
root=Path(__file__).resolve().parents[1]
reports=root/'reports';reports.mkdir(exist_ok=True)
class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*a,**kw):super().__init__(*a,directory=str(root/'site'),**kw)
 def log_message(self,*a):pass
http=ThreadingHTTPServer(('127.0.0.1',0),Handler)
thread=Thread(target=http.serve_forever,daemon=True);thread.start()
r={'engine':engine,'status':'FAIL','checks':[]}
def ok(msg):
 r['checks'].append(msg);print(f'PASS {len(r["checks"])} {msg}',flush=True)
def set_wheel(page,kind,value):
 option=page.locator(f'#wheel-{kind} .wheel-option[data-value="{value}"]')
 option.click()
 assert option.get_attribute('aria-selected')=='true',(kind,value)
def get_db(page):
 return page.evaluate("async()=>await readBackupSnapshot()")
def pick(page,target):
 page.locator('[data-wheel-target="'+target+'"]').click()
 assert page.locator('#wheel-modal').is_visible()
 assert page.locator('#wheel-dialog').count()==0
try:
 with sync_playwright() as p:
  browser=getattr(p,engine).launch(headless=True,args=['--no-sandbox'] if engine=='chromium' else [])
  try:
   context=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True,device_scale_factor=3,accept_downloads=True,service_workers='allow')
   page=context.new_page();errors=[];external=[]
   page.on('pageerror',lambda e:errors.append(str(e)))
   page.on('request',lambda q:external.append(q.url) if urlparse(q.url).hostname not in ('127.0.0.1',None) else None)
   page.goto('http://127.0.0.1:'+str(http.server_address[1])+'/index.html',wait_until='domcontentloaded')
   page.locator('.brand small').wait_for()
   assert 'v05.5' in page.locator('.brand small').inner_text()
   ok('v05.5 visible on synthetic localhost')
   assert page.locator('[data-wheel-target]').count()==4
   assert page.locator('#wheel-modal').is_hidden()
   assert page.locator('#pressure-datetime').get_attribute('type')=='datetime-local'
   assert page.locator('#intake-date').get_attribute('type')=='date'
   assert 'maximum-scale' not in page.locator('meta[name=viewport]').get_attribute('content')
   ok('4 wheel triggers and preserved original ISO date input types')
   page.locator('[data-page="pressure"]').click()
   assert page.locator('#pressure-datetime').input_value()
   baseline=get_db(page)
   pick(page,'pressure-datetime')
   assert page.locator('#wheel-time').is_visible()
   assert page.locator('#wheel-day .wheel-option').count() in (28,29,30,31)
   assert page.locator('#wheel-month .wheel-option').count()==12
   assert page.locator('#wheel-year .wheel-option').count()==201
   ok('Pressure picker opens 3 scrolling wheels and separate time input')
   page.locator('#wheel-cancel').click()
   assert page.locator('#wheel-modal').is_hidden()
   assert get_db(page)==baseline
   ok('Cancel never writes to IndexedDB')
   pick(page,'pressure-datetime')
   set_wheel(page,'year',2024)
   set_wheel(page,'month',2)
   assert page.locator('#wheel-day .wheel-option').count()==29
   set_wheel(page,'day',29)
   page.locator('#wheel-time').fill('09:07')
   preview=page.locator('#wheel-preview').inner_text().lower()
   assert '29 февраля 2024' in preview,preview
   page.locator('#wheel-apply').click()
   assert page.locator('#pressure-datetime').input_value()=='2024-02-29T09:07'
   assert '29 февраля 2024' in page.locator('[data-wheel-label="pressure-datetime"]').inner_text().lower()
   assert get_db(page)==baseline
   ok('Leap date 29 Feb 2024 and time 09:07 persisted in source input only')
   page.locator('#systolic').fill('118');page.locator('#diastolic').fill('76');page.locator('#pulse').fill('68')
   page.locator('#pressure-form button[type=submit]').click()
   page.locator('#pressure-list .history-row').first.wait_for()
   stored=get_db(page)
   assert len(stored['pressures'])==1
   assert stored['pressures'][0]['dateTime']=='2024-02-29T09:07' and stored['pressures'][0]['arm']=='right'
   ok('Pressure saved with right arm and ISO local datetime unchanged')
   pick(page,'pressure-datetime')
   set_wheel(page,'year',2024)
   set_wheel(page,'month',2)
   set_wheel(page,'day',29)
   set_wheel(page,'year',2023)
   assert page.locator('#wheel-day .wheel-option').count()==28
   assert page.locator('#wheel-day .wheel-option[data-value="31"]').count()==0
   assert '28 февраля 2023' in page.locator('#wheel-preview').inner_text().lower()
   page.locator('#wheel-cancel').click()
   assert get_db(page)==stored
   ok('Switch leap year 2024 to 2023 safely clamps day 29 -> 28')
   pick(page,'pressure-datetime')
   set_wheel(page,'year',2024);set_wheel(page,'month',3);set_wheel(page,'day',31)
   set_wheel(page,'month',4)
   assert page.locator('#wheel-day .wheel-option').count()==30
   assert '30 апреля' in page.locator('#wheel-preview').inner_text().lower()
   page.locator('#wheel-cancel').click()
   ok('Switch March 31 to April clamps day to 30')
   page.locator('[data-page="meds"]').click()
   pick(page,'intake-date')
   assert page.locator('#wheel-time').is_hidden()
   set_wheel(page,'year',2024);set_wheel(page,'month',6);set_wheel(page,'day',10)
   page.locator('#wheel-apply').click()
   assert page.locator('#intake-date').input_value()=='2024-06-10'
   assert '10 июня 2024' in page.locator('[data-wheel-label="intake-date"]').inner_text().lower()
   ok('Intake date uses wheel-only day/month/year and remains ISO date')
   page.locator('#med-name').fill('Учебный препарат А')
   page.locator('#med-kind').select_option('course')
   page.locator('#course-fields').wait_for(state='visible')
   pick(page,'course-from')
   assert page.locator('#wheel-clear').is_visible()
   set_wheel(page,'year',2024);set_wheel(page,'month',6);set_wheel(page,'day',1)
   page.locator('#wheel-apply').click()
   assert page.locator('#course-from').input_value()=='2024-06-01'
   pick(page,'course-to')
   set_wheel(page,'year',2024);set_wheel(page,'month',6);set_wheel(page,'day',30)
   page.locator('#wheel-apply').click()
   assert page.locator('#course-to').input_value()=='2024-06-30'
   ok('Course start/end picked independently as ISO, no calendar')
   pick(page,'course-to')
   page.locator('#wheel-clear').click()
   assert page.locator('#course-to').input_value()==''
   pick(page,'course-to')
   set_wheel(page,'year',2024);set_wheel(page,'month',6);set_wheel(page,'day',30)
   page.locator('#wheel-apply').click()
   ok('Optional course end can be cleared then selected again')
   page.locator('#med-form button[type=submit]').click()
   page.locator('#med-list .med-block').first.wait_for()
   meds=get_db(page)['medications'];assert len(meds)==1
   assert meds[0]['from']=='2024-06-01' and meds[0]['to']=='2024-06-30'
   ok('Course medication saves original from/to fields, no schema conversion')
   page.locator('#med-list .med-time-controls input[type=time]').first.fill('08:15')
   page.locator('#med-list .intake-confirm-button').first.click()
   page.locator('#med-list .intake-record').first.wait_for()
   intake=get_db(page)['intakes']
   assert len(intake)==1 and intake[0]['date']=='2024-06-10' and intake[0]['takenAtLocal']=='2024-06-10T08:15'
   ok('Selected intake day flows to unchanged atomic audit and medicine history')
   page.locator('[data-page="backup"]').click()
   with page.expect_download() as download:page.locator('#export-button').click()
   data=json.loads(Path(download.value.path()).read_text(encoding='utf-8'))
   assert data['version']==3
   assert data['data']['pressures'][0]['dateTime']=='2024-02-29T09:07'
   assert data['data']['medications'][0]['from']=='2024-06-01'
   assert data['data']['intakes'][0]['takenAtLocal']=='2024-06-10T08:15'
   ok('Export v3 dates unchanged with all 4 legacy stores')
   page.locator('[data-page="pressure"]').click()
   for width in (320,375,390,430,768):
    page.set_viewport_size({'width':width,'height':844})
    pick(page,'pressure-datetime')
    page.locator('#wheel-modal .wheel-dialog').screenshot(path=str(reports/f'wheel-{engine}-{width}.png'))
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    dialog=page.locator('.wheel-dialog').bounding_box()
    assert dialog and dialog['x']>=-1 and dialog['x']+dialog['width']<=width+1,(width,dialog)
    assert page.locator('#wheel-day').bounding_box()['width']>30
    assert page.locator('#wheel-month').bounding_box()['width']>65
    page.locator('#wheel-cancel').click()
    ok(str(width)+'px responsive modal wheels fit iPhone/iPad viewport')
   assert not errors,errors
   assert not external,external
   ok('No JavaScript errors or third-party requests')
   r['status']='PASS'
  finally:browser.close()
except Exception as exc:
 r['error']=str(exc);r['traceback']=traceback.format_exc();print(r['traceback'],flush=True)
finally:
 http.shutdown();http.server_close();thread.join(timeout=5)
 (reports/f'date-wheels-{engine}.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
 print(f'RESULT={r["status"]} ENGINE={engine} CHECKS={len(r["checks"])}',flush=True)
sys.exit(0 if r['status']=='PASS' else 1)
