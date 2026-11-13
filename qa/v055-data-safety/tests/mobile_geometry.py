#!/usr/bin/env python3
"""PAE04 v05.5 mobile synthetic UI geometry checks; local loopback only."""
from pathlib import Path
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from threading import Thread
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
import sys,json,traceback
engine=sys.argv[1]
root=Path(__file__).resolve().parents[1];out=root/'reports';out.mkdir(exist_ok=True)
class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*a,**k):super().__init__(*a,directory=str(root/'site'),**k)
 def log_message(self,*a):pass
http=ThreadingHTTPServer(('127.0.0.1',0),Handler)
thread=Thread(target=http.serve_forever,daemon=True);thread.start()
result={'engine':engine,'status':'FAIL','passed':[]}
def ok(t):
 result['passed'].append(t);print('PASS '+str(len(result['passed']))+' '+t,flush=True)
def inside(a,b):return a['x']>=b['x']-3 and a['x']+a['width']<=b['x']+b['width']+3
def overlap(a,b):return a['x']<b['x']+b['width'] and a['x']+a['width']>b['x'] and a['y']<b['y']+b['height'] and a['y']+a['height']>b['y']
try:
 with sync_playwright() as p:
  browser=getattr(p,engine).launch(headless=True,args=['--no-sandbox'] if engine=='chromium' else [])
  try:
   ctx=browser.new_context(viewport={'width':390,'height':844},service_workers='allow')
   page=ctx.new_page();errors=[];external=[]
   page.on('pageerror',lambda e:errors.append(str(e)))
   page.on('request',lambda r:external.append(r.url) if urlparse(r.url).hostname not in ('127.0.0.1',None) else None)
   page.goto('http://127.0.0.1:'+str(http.server_address[1])+'/index.html')
   page.locator('#stat-pressure').wait_for()
   assert 'v05.5' in page.locator('.brand small').inner_text()
   ok('v05.5 title confirmed')
   for width in (320,375,390,430,600,740,768,820,1024):
    page.set_viewport_size({'width':width,'height':844})
    page.locator('[data-page="overview"]').click()
    cards=page.locator('.stats>.stat-card')
    assert cards.count()==3
    for v in ('0','1','10','100'):
     page.evaluate('(v)=>["stat-pressure","stat-meds","stat-intakes"].forEach(x=>document.getElementById(x).textContent=v)',v)
     nums=[page.locator('#'+x).bounding_box() for x in ('stat-pressure','stat-meds','stat-intakes')]
     assert max(n['y'] for n in nums)-min(n['y'] for n in nums)<=2,(width,v,'digits')
     caps=[cards.nth(i).locator('small').bounding_box() for i in range(3)]
     assert max(c['y'] for c in caps)-min(c['y'] for c in caps)<=2,(width,v,'captions')
     assert all(inside(nums[i],cards.nth(i).bounding_box()) for i in range(3))
    ok(str(width)+'px counters aligned 0/1/10/100')
    if width in (390,768):page.screenshot(path=str(out/f'{engine}-{width}-overview.png'))
    page.locator('[data-page="pressure"]').click()
    assert not overlap(page.locator('#pressure-title').bounding_box(),page.locator('#page-pressure .page-head .tag').bounding_box()),width
    assert inside(page.locator('#pressure-datetime').bounding_box(),page.locator('#page-pressure .panel').first.bounding_box()),width
    assert inside(page.locator('#pressure-filter').bounding_box(),page.locator('#page-pressure .panel').nth(1).bounding_box()),width
    if width<=740:
     n=page.locator('#pressure-form .form-grid').evaluate('(el)=>getComputedStyle(el).gridTemplateColumns.split(" ").length')
     assert n==1,(width,n)
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),('pressure overflow',width)
    ok(str(width)+'px pressure fields fit')
    if width in (390,768):page.screenshot(path=str(out/f'{engine}-{width}-pressure.png'))
    page.locator('[data-page="meds"]').click()
    assert page.locator('#meds-title .version-inline').count()==0
    assert page.locator('#meds-title').inner_text().strip()=='Лекарства'
    assert not overlap(page.locator('#meds-title').bounding_box(),page.locator('#page-meds .page-head .tag').bounding_box())
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),('meds overflow',width)
    ok(str(width)+'px medicine title fits')
   assert not errors,errors
   assert not external,external
   ok('no unexpected JS errors or external requests')
   result['status']='PASS'
  finally:browser.close()
except Exception as e:
 result['error']=str(e);result['trace']=traceback.format_exc();print(result['trace'],flush=True)
finally:
 http.shutdown();http.server_close();thread.join(timeout=5)
 (out/f'visual-{engine}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
 print(f"RESULT={result['status']} ENGINE={engine} CHECKS={len(result['passed'])}",flush=True)
sys.exit(0 if result['status']=='PASS' else 1)
