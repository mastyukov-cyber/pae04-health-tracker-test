#!/usr/bin/env python3
"""CP-REAL01: actual medicine names, user-confirmed doses, fictional intake history. Python 3.12."""
import http.server
import pathlib
import sys
import threading
from playwright.sync_api import sync_playwright, expect

engine=sys.argv[1]
site=pathlib.Path(sys.argv[2]).resolve()
reports=pathlib.Path(sys.argv[3]).resolve()
assert engine in ('chromium','webkit')
assert (site/'CP_REAL01_BUILD.json').is_file()
reports.mkdir(parents=True,exist_ok=True)
class Quiet(http.server.SimpleHTTPRequestHandler):
 def __init__(self,*args,**kwargs): super().__init__(*args,directory=str(site),**kwargs)
 def log_message(self,*args): pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Quiet)
threading.Thread(target=server.serve_forever,daemon=True).start()
url=f'http://127.0.0.1:{server.server_port}/index.html'
counter=0
errors=[]
def check(name,ok):
 global counter
 if not ok: raise AssertionError(name)
 counter+=1
 print(f'PASS {counter:02d} {name}',flush=True)
def counts(page):
 return page.evaluate("""async ()=>{
   const req=indexedDB.open('PAE04_HT_STABLE_CANDIDATE_INTEGRATION_SYNTHETIC_SCHEMA1',1);
   const db=await new Promise((r,j)=>{req.onsuccess=()=>r(req.result);req.onerror=()=>j(req.error)});
   const result={};
   for(const name of ['pressures','medications','intakes','intakeEvents']){
     result[name]=await new Promise((r,j)=>{
        const req=db.transaction([name],'readonly').objectStore(name).count();
        req.onsuccess=()=>r(req.result);req.onerror=()=>j(req.error);
     });
   }
   db.close();return result;
 }""")
try:
 with sync_playwright() as p:
  browser=getattr(p,engine).launch(headless=True)
  context=browser.new_context(viewport={'width':390,'height':844},
                              timezone_id='Europe/Moscow',reduced_motion='reduce')
  page=context.new_page()
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto(url,wait_until='networkidle')
  button=page.locator('#pae04-personal-seed-btn')
  expect(button).to_be_enabled()
  check('Real-medication profile is visible but not auto-loaded',counts(page)==dict(pressures=0,medications=0,intakes=0,intakeEvents=0))
  check('Personal preview version is visible','CP-REAL01 PERSONAL PREVIEW' in page.locator('.brand').inner_text())
  page.screenshot(path=str(reports/f'{engine}-01-before-seed.png'),full_page=True)
  page.once('dialog',lambda d:d.accept())
  button.click()
  expect(page.locator('#ui01-meds')).to_contain_text('Капотен')
  result=counts(page)
  check('10 medicines saved to local empty DB',result==dict(pressures=0,medications=10,intakes=0,intakeEvents=0))
  check('Home shows three medicine types',page.locator('.ui01-group-title').all_inner_texts()==
        ['Постоянные','Курсовые','Ситуативные'])
  home=page.locator('#ui01-meds').inner_text()
  check('Four verified prescriptions in home',
        all(name in home for name in ['Эдарби','Эспиро','Липримар','Беталок ЗОК']))
  check('Personal doses displayed, no inferred Capoten dose',
        all(v in home for v in ['20 мг','25 мг','10 мг','12,5 мг','Личная дозировка не уточнена']))
  check('Completed Probiotics course does not appear on home', 'Probiotics 10+' not in home)
  check('No medicine silently marked taken',page.locator('#ui01-meds .ui01-check.is-taken').count()==0)
  page.screenshot(path=str(reports/f'{engine}-02-personal-home.png'),full_page=True)
  page.reload(wait_until='networkidle')
  check('Cards survive reload',counts(page)['medications']==10)
  page.locator('[data-page="meds"]').click()
  check('Historical probiotic card remains in medicine journal','Probiotics 10+' in page.locator('#med-list').inner_text())
  # Verify typo ("Копотэн") stays until explicit choice, not silently corrected.
  page.locator('#med-name').fill('Копотэн')
  expect(page.locator('#med-guard-panel')).to_contain_text('Капотен')
  check('Typo produces Capoten suggestion',page.locator('#med-name').input_value()=='Копотэн')
  page.locator('#med-guard-panel button').filter(has_text='Капотен').first.click()
  expect(page.locator('#med-name')).to_have_value('Капотен')
  check('Correction happens only after user chooses',True)
  # Existing profile card must not duplicate, including after user correction.
  page.locator('#med-form button[type="submit"]').click()
  page.wait_for_timeout(200)
  check('Duplicate Capoten is blocked without changing storage',counts(page)['medications']==10)
  # Repeat seed button after reload must refuse any existing data.
  button=page.locator('#pae04-personal-seed-btn')
  button.click()
  page.wait_for_timeout(200)
  check('Second personal import cannot overwrite existing cards',counts(page)['medications']==10)
  page.screenshot(path=str(reports/f'{engine}-03-typo-guard.png'),full_page=True)
  # Current browser carries no real measured pressure or intake events.
  check('No actual intake or pressure imported',
       counts(page)['pressures']==0 and counts(page)['intakes']==0 and counts(page)['intakeEvents']==0)
  # Simulate totally independent new browser/device with no data: manual real name.
  other=browser.new_context(viewport={'width':390,'height':844},timezone_id='Europe/Moscow')
  empty=other.new_page()
  empty.on('pageerror',lambda e:errors.append(str(e)))
  empty.goto(url,wait_until='networkidle')
  empty.locator('[data-page="meds"]').click()
  empty.locator('#med-name').fill('Нурофен')
  empty.locator('#med-form button[type="submit"]').click()
  confirm=empty.locator('#med-guard-panel .med-guard-confirm')
  expect(confirm).to_be_visible()
  check('Manual real medicine name requires explicit verification',counts(empty)['medications']==0)
  confirm.click()
  expect(empty.locator('#med-list')).to_contain_text('Нурофен')
  check('Manual real name saves after confirmation',counts(empty)['medications']==1)
  check('Manual entry did not import personal profile',counts(empty)['intakes']==0)
  other.close()
  page.locator('[data-page="overview"]').click()
  page.screenshot(path=str(reports/f'{engine}-04-return-home.png'),full_page=True)
  check('All screen JS errors absent',errors==[])
  browser.close()
finally:
 server.shutdown()
assert counter==19,f'Expected 19 checks, got {counter}'
print(f'RESULT=PASS ENGINE={engine} CP_REAL01={counter}/{counter} SCREENSHOTS=4')
