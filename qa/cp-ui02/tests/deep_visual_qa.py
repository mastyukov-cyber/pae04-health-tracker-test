#!/usr/bin/env python3
"""PAE-04 CP-UI02: deep synthetic Home visual QA. Target Python 3.12 + Playwright 1.65.1."""
import datetime
import functools
import http.server
import json
import pathlib
import sys
import threading
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright, expect

engine=sys.argv[1]
site=pathlib.Path(sys.argv[2]).resolve()
reports=pathlib.Path(sys.argv[3]).resolve()
assert engine in ("chromium","webkit")
assert site.is_dir() and (site/"CP_UI01_BUILD.json").is_file()
reports.mkdir(parents=True,exist_ok=True)
zone=ZoneInfo("Europe/Moscow")
start=datetime.datetime(2026,11,15,23,58,tzinfo=zone)
class Quiet(http.server.SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,directory=str(site),**kwargs)
    def log_message(self,*args): pass
httpd=http.server.ThreadingHTTPServer(("127.0.0.1",0),Quiet)
threading.Thread(target=httpd.serve_forever,daemon=True).start()
url=f"http://127.0.0.1:{httpd.server_port}/index.html"
passes=[]
browser_errors=[]
def pass_if(label,ok):
    if not ok: raise AssertionError(label)
    passes.append(label)
    print(f"PASS {len(passes):02} {label}",flush=True)
def has_txt(page,selector,txt):
    return txt in page.locator(selector).inner_text()
def counts(page):
    return page.evaluate("""async () => {
      const req=indexedDB.open('PAE04_HT_STABLE_CANDIDATE_INTEGRATION_SYNTHETIC_SCHEMA1',1);
      const db=await new Promise((ok,bad)=>{req.onsuccess=()=>ok(req.result);req.onerror=()=>bad(req.error);});
      const stores=['pressures','medications','intakes','intakeEvents'];
      const result={};
      for (const name of stores) {
        result[name]=await new Promise((ok,bad)=>{
          const tx=db.transaction(name,'readonly');const r=tx.objectStore(name).count();
          r.onsuccess=()=>ok(r.result);r.onerror=()=>bad(r.error);
        });
      }
      db.close();return result;
    }""")
def seed(page):
    return page.evaluate("""async () => {
      // Only independent fake records in this disposable browser origin.
      const name='PAE04_HT_STABLE_CANDIDATE_INTEGRATION_SYNTHETIC_SCHEMA1';
      const req=indexedDB.open(name,1);
      const db=await new Promise((ok,bad)=>{req.onsuccess=()=>ok(req.result);req.onerror=()=>bad(req.error);});
      const tx=db.transaction(['pressures','medications','intakes','intakeEvents'],'readwrite');
      const mkId=()=>crypto.randomUUID();
      const at='2026-11-15T17:00:00.000Z';
      const press=[
        ['2026-11-14T08:30',116,74,68],
        ['2026-11-14T20:30',124,82,null],
        ['2026-11-15T08:20',130,81,72]
      ];
      for (const [dateTime,systolic,diastolic,pulse] of press)
        tx.objectStore('pressures').add({id:mkId(),systolic,diastolic,pulse,dateTime,
                                        note:'',arm:'right',createdAt:at});
      const list=[
        ['a','Учебный препарат А','regular',null,null],
        ['b','Учебный препарат В','course','2026-11-14','2026-11-15'],
        ['c','Учебный препарат Г','course','2026-11-10','2026-11-14'],
        ['d','Учебный препарат Д','course','2026-11-16','2026-11-19'],
        ['e','Учебный препарат Е','asNeeded',null,null]
      ];
      const ids={};
      for(const [key,title,kind,from,to] of list){
        const id=mkId();ids[key]=id;
        tx.objectStore('medications').add({id,name:title,kind,dose:'',from,to,createdAt:at});
      }
      const intakeSet=[
        ['a','2026-11-14','08:12'],['a','2026-11-15','08:15'],
        ['b','2026-11-14','09:40'],['e','2026-11-14','16:40']
      ];
      for(const [key,date,clock] of intakeSet){
        const id=mkId(),markedAt=at,takenAtLocal=date+'T'+clock;
        tx.objectStore('intakes').add({id,medId:ids[key],date,markedAt,takenAtLocal,status:'active'});
        tx.objectStore('intakeEvents').add({
          id:mkId(),intakeId:id,medId:ids[key],action:'marked',at:markedAt,newTakenAtLocal:takenAtLocal
        });
      }
      await new Promise((ok,bad)=>{tx.oncomplete=ok;tx.onabort=()=>bad(tx.error);tx.onerror=()=>bad(tx.error)});
      db.close();return ids;
    }""")
try:
    with sync_playwright() as playwright:
        browser=getattr(playwright,engine).launch(headless=True)
        context=browser.new_context(viewport={"width":390,"height":844},timezone_id="Europe/Moscow",
                                    device_scale_factor=1,reduced_motion="reduce",
                                    color_scheme="light")
        page=context.new_page()
        page.on("pageerror",lambda e:browser_errors.append(str(e)))
        # Fake clock must be installed before first navigation.
        page.clock.install(time=start)
        page.goto(url,wait_until="networkidle")
        expect(page.locator("#ui01-date")).to_contain_text("15 ноября")
        pass_if("First launch date is Nov 15",True)
        pass_if("Initial data empty",counts(page)=={'pressures':0,'medications':0,'intakes':0,'intakeEvents':0})
        page.screenshot(path=str(reports/f"{engine}-01-empty.png"),full_page=True)
        ids=seed(page)
        pass_if("All 5 fictional medication IDs distinct",len(set(ids.values()))==5)
        page.reload(wait_until="networkidle")
        expect(page.locator(".ui01-reading .ui01-bp")).to_have_count(1)
        pass_if("Today shows the single current-day reading",page.locator(".ui01-reading .ui01-bp").inner_text()=="130 / 81")
        pass_if("Two yesterday readings averaged separately",
                has_txt(page,"#ui01-pressure .ui01-yesterday","120 / 78"))
        pass_if("Pulse average excludes missing pulse",
                has_txt(page,"#ui01-pressure .ui01-yesterday","Пульс в среднем: 68"))
        pass_if("Yesterday text labels average, not today",
                has_txt(page,"#ui01-pressure .ui01-yesterday","среднее за 2 измерения"))
        pass_if("Today medicine groups ordered",
                page.locator(".ui01-group-title").all_inner_texts()==
                ['Постоянные','Курсовые','Ситуативные'])
        pass_if("Current course visible; expired and future courses hidden",
                has_txt(page,"#ui01-meds","Учебный препарат В")
                and "Учебный препарат Г" not in page.locator("#ui01-meds").inner_text()
                and "Учебный препарат Д" not in page.locator("#ui01-meds").inner_text())
        pass_if("Yesterday's permanent intake time is correct",
                page.locator(".ui01-med-row").filter(has_text="Учебный препарат А")
                .locator(".ui01-yesterday-time").inner_text()=="Вчера принято: 08:12")
        pass_if("Yesterday's current course intake time is correct",
                page.locator(".ui01-med-row").filter(has_text="Учебный препарат В")
                .locator(".ui01-yesterday-time").inner_text()=="Вчера принято: 09:40")
        pass_if("No yesterday hint for situational meds",
                page.locator(".ui01-med-row").filter(has_text="Учебный препарат Е")
                .locator(".ui01-yesterday-time").count()==0)
        pass_if("Today permanent intake is checked, other meds unchecked",
                page.locator(".ui01-med-row").filter(has_text="Учебный препарат А")
                .locator(".ui01-check").get_attribute("aria-pressed")=="true"
                and page.locator(".ui01-med-row").filter(has_text="Учебный препарат В")
                .locator(".ui01-check").get_attribute("aria-pressed")=="false")
        before=counts(page)
        pass_if("Read-only dashboard did not mutate seeded four-store database",
                before=={"pressures":3,"medications":5,"intakes":4,"intakeEvents":4})
        page.screenshot(path=str(reports/f"{engine}-02-home-today.png"),full_page=True)
        page.locator("#ui01-font-more").click()
        page.locator("#ui01-font-more").click()
        page.set_viewport_size({"width":320,"height":780})
        expect(page.locator("#ui01-font-label")).to_have_text("5 / 5")
        pass_if("Maximum font and narrow layout available",True)
        page.screenshot(path=str(reports/f"{engine}-03-large-font-320.png"),full_page=True)
        overflow=page.evaluate("""() => ({
          viewport:innerWidth,
          document:document.documentElement.scrollWidth,
          body:document.body.scrollWidth,
          overflowing:[...document.querySelectorAll('body *')].map(e=>{
            const r=e.getBoundingClientRect();
            return {tag:e.tagName,id:e.id,cls:String(e.className).slice(0,60),
                    left:Math.round(r.left),right:Math.round(r.right),
                    width:Math.round(r.width),scroll:e.scrollWidth,client:e.clientWidth};
          }).filter(x=>x.right>innerWidth+2||x.left< -2).slice(0,16)
        })""")
        print("OVERFLOW_DIAG="+json.dumps(overflow,ensure_ascii=False),flush=True)
        pass_if("No horizontal overflow at 320px",
                overflow["document"]<=overflow["viewport"]+2)
        page.set_viewport_size({"width":390,"height":844})
        # Simulate device waking up three minutes after midnight.
        page.clock.fast_forward("03:00")
        page.evaluate("window.dispatchEvent(new Event('focus'))")
        expect(page.locator("#ui01-date")).to_contain_text("16 ноября")
        pass_if("Day rolls forward without clearing IndexedDB",counts(page)==before)
        pass_if("At new day no readings are mislabelled as today's",
                page.locator("#ui01-pressure .ui01-reading").count()==0
                and has_txt(page,"#ui01-pressure","Сегодня измерений пока нет"))
        pass_if("Single previous-day pressure is NOT falsely called average",
                has_txt(page,"#ui01-pressure .ui01-yesterday","Вчера · одно измерение")
                and has_txt(page,"#ui01-pressure .ui01-yesterday","130 / 81")
                and not has_txt(page,"#ui01-pressure .ui01-yesterday","среднее за"))
        pass_if("Course ending yesterday hidden, new course appears",
                "Учебный препарат В" not in page.locator("#ui01-meds").inner_text()
                and has_txt(page,"#ui01-meds","Учебный препарат Д"))
        pass_if("New day starts with unchecked permanent medication",
                page.locator(".ui01-med-row").filter(has_text="Учебный препарат А")
                .locator(".ui01-check").get_attribute("aria-pressed")=="false")
        pass_if("Yesterday's factual intake now refers to day 15",
                page.locator(".ui01-med-row").filter(has_text="Учебный препарат А")
                .locator(".ui01-yesterday-time").inner_text()=="Вчера принято: 08:15")
        pass_if("Course that starts today cannot display yesterday dose",
                page.locator(".ui01-med-row").filter(has_text="Учебный препарат Д")
                .locator(".ui01-yesterday-time").count()==0)
        pass_if("All historical medication cards remain in local database",
                counts(page)["medications"]==5)
        page.screenshot(path=str(reports/f"{engine}-04-new-day.png"),full_page=True)
        pass_if("No JavaScript crashes in either view",browser_errors==[])
        context.close()
        browser.close()
finally:
    httpd.shutdown()
assert len(passes)==25,(len(passes),passes)
print(f"RESULT=PASS ENGINE={engine} CP_UI02={len(passes)}/{len(passes)} SCREENSHOTS=4",flush=True)
