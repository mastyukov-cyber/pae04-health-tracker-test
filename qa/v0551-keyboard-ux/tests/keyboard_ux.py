# Mobile UX: dismiss active editing keyboard before tapping the deliberately hidden bottom menu.
def nav_to(page,name):
 page.evaluate("document.activeElement.blur()")
 page.locator("body.keyboard-editing").wait_for(state="hidden",timeout=5000)
 page.locator("[data-page="+name+"]").click()

#!/usr/bin/env python3
"""PAE-04 v05.5.1 browser-simulated mobile keyboard UX QA (synthetic only).

Headless WebKit/Chromium emulate focus and visual viewport but do NOT render
native iOS contact-autofill or software keyboard. Real iPhone acceptance required.
"""
from pathlib import Path
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect
import json, traceback, sys
engine=sys.argv[1]
if engine not in ('chromium','webkit'):raise SystemExit('Unsupported engine')
root=Path(__file__).resolve().parents[1]
reports=root/'reports';reports.mkdir(exist_ok=True)
class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*a,**kw):super().__init__(*a,directory=str(root/'site'),**kw)
 def log_message(self,*a):pass
server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
worker=Thread(target=server.serve_forever,daemon=True);worker.start()
result={'engine':engine,'status':'FAIL','checks':[]}
def ok(msg):
 result['checks'].append(msg)
 print('PASS '+str(len(result['checks']))+' '+msg,flush=True)
def style(page,selector,key='display'):
 return page.locator(selector).evaluate("(el,key)=>getComputedStyle(el)[key]",key)
def focus(page,id):
 page.locator('#'+id).focus()
 expect(page.locator('#'+id)).to_be_focused()
def focus_nav_hidden(page):
 assert 'keyboard-editing' in (page.locator('body').get_attribute('class') or '')
 assert style(page,'.sidebar')=='none'
def blur(page):
 page.evaluate("document.activeElement.blur()")
 expect(page.locator('body')).not_to_have_class('keyboard-editing',timeout=5000)
 assert style(page,'.sidebar')!='none'
try:
 with sync_playwright() as p:
  browser=getattr(p,engine).launch(headless=True,args=['--no-sandbox'] if engine=='chromium' else [])
  try:
   context=browser.new_context(viewport={'width':390,'height':844},device_scale_factor=3,has_touch=True,is_mobile=True,service_workers='allow')
   page=context.new_page();errors=[];third_party=[]
   page.on('pageerror',lambda e:errors.append(str(e)))
   page.on('request',lambda q:third_party.append(q.url) if urlparse(q.url).hostname not in ('127.0.0.1',None) else None)
   url='http://127.0.0.1:'+str(server.server_address[1])+'/index.html'
   page.goto(url,wait_until='domcontentloaded')
   expect(page.locator('.brand small')).to_contain_text('v05.5.1')
   ok('Pinned version v05.5.1 loads locally')
   assert 'maximum-scale' not in page.locator('meta[name="viewport"]').get_attribute('content')
   assert 'user-scalable=no' not in page.locator('meta[name="viewport"]').get_attribute('content')
   ok('Native iOS pinch zoom remains enabled')
   nav_to(page,'pressure')
   for id in ('systolic','diastolic','pulse'):
    field=page.locator('#'+id)
    for name,value in [('autocomplete','off'),('autocorrect','off'),('autocapitalize','off'),('spellcheck','false')]:
     assert field.get_attribute(name)==value,(id,name,field.get_attribute(name))
    assert field.get_attribute('type')=='number'
    assert field.get_attribute('inputmode')=='numeric'
    assert field.get_attribute('enterkeyhint')=='next'
    ok(id+' retains validated numeric type, explicit autofill minimization and next hint')
   for width in (320,375,390,430,600,740):
    page.set_viewport_size({'width':width,'height':844})
    focus(page,'systolic')
    focus_nav_hidden(page)
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),width
    if width in (320,390):page.screenshot(path=str(reports/f'{engine}-{width}-editing.png'))
    ok(str(width)+'px mobile focus hides sticky bottom menu with no overflow')
    blur(page)
    ok(str(width)+'px blur restores original bottom menu')
   page.set_viewport_size({'width':800,'height':844})
   focus(page,'systolic')
   assert style(page,'.sidebar')!='none'
   ok('Desktop/tablet navigation is not hidden by mobile-only CSS')
   page.evaluate("document.activeElement.blur()")
   page.set_viewport_size({'width':390,'height':844})
   page.locator('#systolic').fill('121')
   focus(page,'systolic')
   page.locator('#systolic').press('Enter')
   expect(page.locator('#diastolic')).to_be_focused()
   focus_nav_hidden(page)
   ok('Enter from systolic moves to diastolic without submit')
   page.locator('#diastolic').fill('79')
   page.locator('#diastolic').press('Enter')
   expect(page.locator('#pulse')).to_be_focused()
   focus_nav_hidden(page)
   ok('Enter from diastolic moves to pulse without submit')
   page.locator('#pulse').fill('70')
   page.locator('#pulse').press('Enter')
   expect(page.locator('#pressure-note')).to_be_focused()
   focus_nav_hidden(page)
   assert 'autocomplete' in (page.locator('#pressure-note').evaluate('el=>el.outerHTML'))
   ok('Enter from pulse moves to notes; notes focus hides nav')
   page.locator('#pressure-note').fill('Учебное измерение')
   expect(page.locator('#pressure-count')).to_contain_text('0')
   page.evaluate("document.querySelector('#pressure-form').requestSubmit()")
   expect(page.locator('#pressure-count')).to_contain_text('1',timeout=10000)
   expect(page.locator('body')).not_to_have_class('keyboard-editing',timeout=10000)
   assert style(page,'.sidebar')!='none'
   assert page.evaluate("document.activeElement.id!=='pressure-note'")
   assert page.evaluate("document.activeElement.id!=='systolic'")
   ok('Verified save dismisses keyboard focus and restores nav')
   rows=page.evaluate("async()=>await readBackupSnapshot()")
   assert len(rows['pressures'])==1 and rows['pressures'][0]['arm']=='right'
   assert rows['pressures'][0]['systolic']==121 and rows['pressures'][0]['diastolic']==79
   assert rows['pressures'][0]['pulse']==70 and rows['pressures'][0]['note']=='Учебное измерение'
   ok('Actual IndexedDB record verified after save; fixed right arm and fields unchanged')
   assert page.locator('#systolic').input_value()=='' and page.locator('#diastolic').input_value()==''
   ok('Post-save form resets without losing saved measurement')
   page.locator('#pressure-search').focus()
   focus_nav_hidden(page)
   page.locator('#pressure-search').fill('121')
   expect(page.locator('#pressure-list .history-row')).to_have_count(1)
   ok('Search focus does not cause bottom nav overlap; read-only search works')
   blur(page)
   nav_to(page,'meds')
   focus(page,'med-name');focus_nav_hidden(page)
   ok('Medicine text entry gets same keyboard-safe navigation behavior')
   blur(page)
   nav_to(page,'pressure')
   page.locator('[data-wheel-target=pressure-datetime]').click()
   assert page.locator('#wheel-modal').is_visible()
   page.locator('#wheel-cancel').click()
   assert page.locator('#wheel-modal').is_hidden()
   ok('Day/month/year wheel remains available and cancellable')
   nav_to(page,'backup')
   expect(page.locator('#safety-db-status')).to_contain_text('PASS')
   ok('Local Data Safety integrity scan still succeeds')
   assert not errors,errors
   assert not third_party,third_party
   ok('No JS runtime errors or outgoing third-party requests')
   result['status']='PASS'
  finally:browser.close()
except Exception as e:
 result['error']=str(e)
 result['traceback']=traceback.format_exc()
 print(result['traceback'],flush=True)
finally:
 server.shutdown();server.server_close();worker.join(timeout=5)
 (reports/f'keyboard-ux-{engine}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print(f'RESULT={result["status"]} ENGINE={engine} CHECKS={len(result["checks"])}',flush=True)
sys.exit(0 if result['status']=='PASS' else 1)
