#!/usr/bin/env python3
"""PAE-04 v05.5.2 synthetic Keyboard Polish browser QA.

Browser mobile emulation cannot verify native iPhone QuickType/contact autofill.
All data, contacts and measurements used here are fictional.
"""
from pathlib import Path
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from threading import Thread
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect
import json,sys,traceback,re
engine=sys.argv[1]
assert engine in ('chromium','webkit')
root=Path(__file__).resolve().parents[1]
reports=root/'reports';reports.mkdir(exist_ok=True)
class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*a,**k):super().__init__(*a,directory=str(root/'site'),**k)
 def log_message(self,*a):pass
server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
worker=Thread(target=server.serve_forever,daemon=True);worker.start()
data={'engine':engine,'checks':[],'status':'FAIL'}
def ok(msg):
 data['checks'].append(msg)
 print(f'PASS {len(data["checks"])} {msg}',flush=True)
try:
 with sync_playwright() as p:
  browser=getattr(p,engine).launch(headless=True,args=['--no-sandbox'] if engine=='chromium' else [])
  try:
   ctx=browser.new_context(viewport={'width':390,'height':844},device_scale_factor=3,is_mobile=True,has_touch=True,service_workers='allow')
   page=ctx.new_page();errors=[];external=[]
   page.on('pageerror',lambda e:errors.append(str(e)))
   page.on('request',lambda r:external.append(r.url) if urlparse(r.url).hostname not in ('127.0.0.1',None) else None)
   page.goto('http://127.0.0.1:'+str(server.server_address[1])+'/index.html',wait_until='domcontentloaded')
   expect(page.locator('.brand small')).to_contain_text('v05.5.2')
   ok('New synthetic v05.5.2 loaded')
   page.locator('[data-page=pressure]').click()
   button=page.locator('#pressure-keyboard-done')
   expect(button).to_be_hidden()
   assert page.locator('#pressure-note').get_attribute('autocomplete')=='off'
   ok('Done control initially hidden and note autofill opt-out retained')
   page.locator('#pressure-note').fill('Учебная заметка — не сохранять')
   page.locator('#pressure-note').focus()
   expect(page.locator('body')).to_have_class(re.compile(r'\bnote-editing\b'),timeout=5000)
   expect(button).to_be_visible()
   assert page.locator('.sidebar').evaluate("el=>getComputedStyle(el).display")=='none'
   ok('Focused note shows accessible done control while hiding bottom navigation')
   assert button.get_attribute('type')=='button'
   assert 'без сохранения' in button.get_attribute('aria-label')
   before=page.evaluate('async()=>await readBackupSnapshot()')
   button.click()
   expect(page.locator('body')).not_to_have_class(re.compile(r'\bnote-editing\b'),timeout=5000)
   expect(button).to_be_hidden()
   assert page.locator('.sidebar').evaluate("el=>getComputedStyle(el).display")!='none'
   assert page.locator('#pressure-note').input_value()=='Учебная заметка — не сохранять'
   assert page.evaluate('async()=>await readBackupSnapshot()')==before
   ok('Done dismisses keyboard without saving or clearing the draft')
   page.locator('#pressure-note').focus()
   expect(button).to_be_visible()
   page.locator('#pressure-list').locator('xpath=..').locator('h2').click()
   expect(page.locator('body')).not_to_have_class(re.compile(r'\bnote-editing\b'),timeout=5000)
   expect(button).to_be_hidden()
   assert page.locator('#pressure-note').input_value()=='Учебная заметка — не сохранять'
   assert page.evaluate('async()=>await readBackupSnapshot()')==before
   ok('Touching history dismisses form keyboard, preserving unsaved draft')
   page.locator('#pressure-note').focus()
   expect(button).to_be_visible()
   page.evaluate("navigate('backup')")
   expect(page.locator('#page-backup')).to_be_visible()
   expect(page.locator('body')).not_to_have_class(re.compile(r'\bnote-editing\b'),timeout=5000)
   assert page.evaluate('document.activeElement.id')!='pressure-note'
   assert page.evaluate('async()=>await readBackupSnapshot()')==before
   ok('Leaving pressure section blurs keyboard without changing database')
   page.evaluate("navigate('pressure')")
   assert page.locator('#pressure-note').input_value()=='Учебная заметка — не сохранять'
   ok('Returning to form keeps unsaved note while page stays open')
   page.locator('#pressure-note').focus()
   page.evaluate("""() => {
      const form=document.querySelector('#pressure-form');
      const history=document.querySelector('#pressure-list').closest('.panel');
      history.scrollIntoView({block:'end'});
      const mk=(y)=>new Touch({identifier:11,target:form,clientX:50,clientY:y,screenX:50,screenY:y});
      form.dispatchEvent(new TouchEvent('touchstart',{bubbles:true,touches:[mk(370)],targetTouches:[mk(370)],changedTouches:[mk(370)]}));
      form.dispatchEvent(new TouchEvent('touchmove',{bubbles:true,touches:[mk(260)],targetTouches:[mk(260)],changedTouches:[mk(260)]}));
      form.dispatchEvent(new TouchEvent('touchend',{bubbles:true,touches:[],targetTouches:[],changedTouches:[mk(260)]}));
   }""")
   expect(page.locator('body')).not_to_have_class(re.compile(r'\bnote-editing\b'),timeout=5000)
   assert page.locator('#pressure-note').input_value()=='Учебная заметка — не сохранять'
   ok('Synthetic upward touch scroll toward history dismisses note keyboard')
   page.locator('#pressure-search').focus()
   expect(button).to_be_hidden()
   assert 'note-editing' not in (page.locator('body').get_attribute('class') or '')
   ok('Search field does not show note-only keyboard button')
   page.evaluate('document.activeElement.blur()')
   page.locator('#systolic').fill('121')
   page.locator('#diastolic').fill('79')
   page.locator('#pulse').fill('70')
   page.locator('#pressure-note').fill('Учебное измерение')
   page.locator('#pressure-note').focus()
   page.evaluate("document.querySelector('#pressure-form').requestSubmit()")
   expect(page.locator('#stat-pressure')).to_have_text('1',timeout=10000)
   expect(page.locator('body')).not_to_have_class(re.compile(r'\bnote-editing\b'),timeout=5000)
   record=page.evaluate("async()=>await readBackupSnapshot()")
   assert len(record['pressures'])==1
   assert record['pressures'][0]['systolic']==121 and record['pressures'][0]['diastolic']==79
   assert record['pressures'][0]['pulse']==70 and record['pressures'][0]['arm']=='right'
   assert record['pressures'][0]['note']=='Учебное измерение'
   ok('Verified save still works; original right-arm and all BP fields unchanged')
   assert page.locator('#pressure-note').input_value()==''
   assert page.locator('.sidebar').evaluate("el=>getComputedStyle(el).display")!='none'
   ok('Successful save resets form and restores mobile navigation')
   page.locator('[data-page=backup]').click()
   page.locator('#safety-check').click()
   expect(page.locator('#safety-db-status')).to_contain_text('PASS')
   ok('Data Safety post-save scan remains functional')
   assert not errors,errors
   assert not external,external
   ok('No JavaScript exceptions or third-party network requests')
   page.screenshot(path=str(reports/f'keyboard-polish-{engine}.png'))
   data['status']='PASS'
  finally:browser.close()
except Exception as exc:
 data['error']=str(exc);data['traceback']=traceback.format_exc()
 print(data['traceback'],flush=True)
finally:
 server.shutdown();server.server_close();worker.join(timeout=5)
 (reports/f'keyboard-polish-{engine}.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
 print(f'RESULT={data["status"]} ENGINE={engine} CHECKS={len(data["checks"])}',flush=True)
sys.exit(0 if data['status']=='PASS' else 1)
