#!/usr/bin/env python3
"""PAE-04 v05.5 synthetic Safari focus/zoom prevention checks. No real data, localhost only."""
from pathlib import Path
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
import sys,json,traceback
engine=sys.argv[1]
if engine not in ('chromium','webkit'): raise SystemExit('Browser must be chromium or webkit')
root=Path(__file__).resolve().parents[1]
reports=root/'reports';reports.mkdir(exist_ok=True)
class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*a,**kw): super().__init__(*a,directory=str(root/'site'),**kw)
 def log_message(self,*a): pass
http=ThreadingHTTPServer(('127.0.0.1',0),Handler)
thread=Thread(target=http.serve_forever,daemon=True);thread.start()
result={'engine':engine,'status':'FAIL','passed':[]}
def ok(msg):
 result['passed'].append(msg);print(f'PASS {len(result["passed"])} {msg}',flush=True)
def inspect_visible_editable(page):
 return page.locator('input:not([type="checkbox"]):not([type="radio"]):not([type="file"]):not([type="hidden"]),select,textarea').evaluate_all("""els => els.filter(el => el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden').map(el => ({id:el.id || el.type, px:parseFloat(getComputedStyle(el).fontSize)}))""")
def check_sizes(page,width,section):
 controls=inspect_visible_editable(page)
 assert controls,(engine,width,section,'no visible controls')
 small=[x for x in controls if x['px']<15.95]
 assert not small,(engine,width,section,'sub-16px input text',small)
 assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),(engine,width,section,'horizontal overflow')
 return controls
try:
 with sync_playwright() as p:
  browser=getattr(p,engine).launch(headless=True,args=['--no-sandbox'] if engine=='chromium' else [])
  try:
   ctx=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True,device_scale_factor=3,service_workers='allow')
   page=ctx.new_page();errors=[];external=[]
   page.on('pageerror',lambda e:errors.append(str(e)))
   page.on('request',lambda r:external.append(r.url) if urlparse(r.url).hostname not in ('127.0.0.1',None) else None)
   page.goto('http://127.0.0.1:'+str(http.server_address[1])+'/index.html',wait_until='domcontentloaded')
   page.locator('.brand small').wait_for()
   assert 'v05.5' in page.locator('.brand small').inner_text()
   meta=page.locator('meta[name=viewport]').get_attribute('content').lower()
   assert 'width=device-width' in meta and 'initial-scale=1' in meta and 'viewport-fit=cover' in meta,meta
   assert 'maximum-scale' not in meta and 'user-scalable=no' not in meta and 'minimum-scale' not in meta,meta
   ok('Version v05.5 and pinch zoom remain enabled')
   for width in (320,375,390,430,600,740,768,820,1024):
    page.set_viewport_size({'width':width,'height':844})
    page.locator('[data-page="pressure"]').click()
    pressure=check_sizes(page,width,'pressure')
    for id in ('pressure-search','systolic','diastolic','pulse','pressure-datetime','pressure-note','pressure-filter'):
     c=next((x for x in pressure if x['id']==id),None)
     assert c and c['px']>=16,(width,id,c)
    page.locator('#pressure-search').fill('145')
    assert page.locator('#pressure-search').evaluate('(el)=>parseFloat(getComputedStyle(el).fontSize)')>=16
    assert page.evaluate('document.activeElement.id')=='pressure-search'
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    page.locator('#pressure-search').fill('')
    ok(str(width)+'px pressure search, numeric fields, notes, date and select >=16px')
    if width in (390,768):page.screenshot(path=str(reports/f'{engine}-{width}-pressure.png'))
    page.locator('[data-page="meds"]').click()
    meds=check_sizes(page,width,'medicines')
    for id in ('catalog-search','med-name','med-dose','med-strength','med-unit','med-form-factor','med-kind','intake-date','med-search','intake-filter'):
     c=next((x for x in meds if x['id']==id),None)
     assert c and c['px']>=16,(width,id,c)
    page.locator('#med-search').fill('Учебный')
    assert page.evaluate('document.activeElement.id')=='med-search'
    assert page.locator('#med-search').evaluate('(el)=>parseFloat(getComputedStyle(el).fontSize)')>=16
    page.locator('#med-search').fill('')
    ok(str(width)+'px medicine name/search, intake date, dropdowns >=16px')
    if width in (390,768):page.screenshot(path=str(reports/f'{engine}-{width}-medicines.png'))
   page.set_viewport_size({'width':390,'height':844})
   page.locator('#med-kind').select_option('course')
   for id in ('course-from','course-to'):
    control=page.locator('#'+id)
    assert control.is_visible()
    assert control.evaluate('(el)=>parseFloat(getComputedStyle(el).fontSize)')>=16
   ok('Course date fields >=16px without disabling user scaling')
   page.locator('#med-kind').select_option('regular')
   page.locator('#med-name').fill('Учебный препарат Zoom QA')
   page.locator('#med-form button[type=submit]').click()
   time=page.locator('#med-list .med-time-controls input[type=time]').first
   time.wait_for()
   assert time.evaluate('(el)=>parseFloat(getComputedStyle(el).fontSize)')>=16
   ok('Dynamically created intake time input >=16px')
   page.locator('[data-page="backup"]').click()
   assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
   assert not errors,errors
   assert not external,external
   ok('Backup layout fits; no JS errors or external requests')
   result['status']='PASS'
  finally: browser.close()
except Exception as e:
 result['error']=str(e);result['traceback']=traceback.format_exc();print(result['traceback'],flush=True)
finally:
 http.shutdown();http.server_close();thread.join(timeout=5)
 (reports/f'zoom-{engine}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print(f'RESULT={result["status"]} ENGINE={engine} CHECKS={len(result["passed"])}',flush=True)
sys.exit(0 if result['status']=='PASS' else 1)
