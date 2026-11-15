#!/usr/bin/env python3
"""Browser E2E of detached CP-UI01. Python 3.12 + Playwright 1.65.1."""
import datetime
import functools
import http.server
import pathlib
import sys
import threading
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

engine=sys.argv[1]
site=pathlib.Path(sys.argv[2]).resolve()
assert engine in ('chromium','webkit') and site.is_dir()
now=datetime.datetime.now(ZoneInfo('Europe/Moscow'))
day=now.date().isoformat()
yesterday=(now.date()-datetime.timedelta(days=1)).isoformat()
class Quiet(http.server.SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,directory=str(site),**kwargs)
    def log_message(self,*args): pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Quiet)
t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
url='http://127.0.0.1:'+str(server.server_port)+'/index.html'
passed=[]
errors=[]
def check(name,condition):
    assert condition,name
    passed.append(name)
    print('PASS',len(passed),name,flush=True)

def enter_pressure(page,stamp,sysval,diaval,pulse):
    page.locator('[data-page="pressure"]').click()
    page.locator('#systolic').fill(str(sysval))
    page.locator('#diastolic').fill(str(diaval))
    page.locator('#pulse').fill(str(pulse))
    page.locator('#pressure-datetime').evaluate(
        '(el,v) => {el.value=v;el.dispatchEvent(new Event("input",{bubbles:true}));}',stamp)
    page.locator('#pressure-form button[type="submit"]').click()
    page.locator('#messages').get_by_text('Измерение сохранено',exact=False).wait_for()
    page.locator('[data-page="overview"]').click()

def enter_med(page,name,kind):
    page.locator('[data-page="meds"]').click()
    page.locator('#med-name').fill(name)
    page.locator('#med-kind').select_option(kind)
    page.locator('#med-form button[type="submit"]').click()
    page.locator('#messages').get_by_text('Препарат сохранён',exact=False).wait_for()
    page.locator('[data-page="overview"]').click()

try:
    with sync_playwright() as p:
        browser=getattr(p,engine).launch(headless=True)
        context=browser.new_context(viewport={'width':390,'height':844},timezone_id='Europe/Moscow',
                                    reduced_motion='reduce')
        page=context.new_page()
        page.on('pageerror',lambda e: errors.append(str(e)))
        page.goto(url,wait_until='networkidle')
        page.locator('#ui01-date').wait_for()
        check('Home shown on synthetic PWA',page.locator('#overview-title').inner_text()=='Сегодня')
        page.locator('#ui01-pressure').get_by_text('Сегодня измерений пока нет').wait_for()
        check('No today measurement means no invented measurement',page.locator('#ui01-pressure .ui01-empty').count()==1)
        check('No empty medicine groups',page.locator('.ui01-med-group').count()==0)
        check('Large font is default on first launch',page.locator('#ui01-font-label').inner_text()=='3 / 5')
        page.locator('#ui01-font-more').click()
        page.locator('#ui01-font-more').click()
        check('Font A+ changes tier',page.locator('#ui01-font-label').inner_text()=='5 / 5')
        page.reload(wait_until='networkidle')
        check('Font setting survives restart',page.locator('#ui01-font-label').inner_text()=='5 / 5')
        enter_pressure(page,yesterday+'T09:10',126,78,71)
        page.locator('#ui01-pressure .ui01-yesterday').get_by_text('126 / 78',exact=False).wait_for()
        check('Yesterday reading shown with explicit date context',page.locator('#ui01-pressure .ui01-yesterday').count()==1)
        enter_pressure(page,day+'T10:20',132,82,75)
        check('Today and yesterday clearly separated',
              page.locator('#ui01-pressure .ui01-reading .ui01-bp').first.inner_text()=='132 / 82' and
              page.locator('#ui01-pressure .ui01-yesterday').count()==1)
        enter_med(page,'Учебный препарат А','regular')
        page.locator('.ui01-med-group').get_by_text('Постоянные').wait_for()
        check('Permanent medication shown, empty courses hidden',
              page.locator('.ui01-group-title').all_inner_texts()==['Постоянные'])
        check('No fake scheduled time',page.locator('#ui01-meds').get_by_text('Плановое время не задано').count()==1)
        page.once('dialog',lambda d:d.accept())
        page.locator('.ui01-check').first.click()
        page.locator('#ui01-meds .ui01-today-time').first.wait_for()
        check('Home medicine action logs real time via audited intake',page.locator('#ui01-meds .is-taken').count()==1)
        page.reload(wait_until='networkidle')
        check('Medicine intake survives reload',page.locator('#ui01-meds .is-taken').count()==1)
        enter_med(page,'Учебный препарат В','asNeeded')
        check('As-needed section visible when populated','Ситуативные' in page.locator('#ui01-meds').inner_text())
        check('No yesterday context for as-needed meds',
              page.locator('.ui01-med-group').last.locator('.ui01-yesterday-time').count()==0)
        for width in (320,375,390,430):
            page.set_viewport_size({'width':width,'height':844})
            bb=page.locator('#ui01-pressure').bounding_box()
            check(str(width)+'px home card inside viewport',bb is not None and bb['x']>=-2 and bb['x']+bb['width']<=width+2)
        check('No unexpected browser JS error',not errors)
        browser.close()
finally:
    server.shutdown()
print('RESULT=PASS ENGINE='+engine+' CHECKS='+str(len(passed))+'/'+str(len(passed)))
