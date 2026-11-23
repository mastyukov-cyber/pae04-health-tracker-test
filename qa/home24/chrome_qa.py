#!/usr/bin/env python3
"""One scoped Chromium HOME24 UI file-picker/IndexedDB QA, synthetic localhost ONLY."""
import hashlib,functools,http.server,json,pathlib,threading,traceback,sys
from playwright.sync_api import sync_playwright
ROOT=pathlib.Path(__file__).resolve().parent
SITE=ROOT/"_staged_site"
CHECKS=[];ERRORS=[];PAGE_ERRORS=[];BASELINE_HASH=None
def ck(label,value,want=True):
 ok=value==want
 CHECKS.append({"name":label,"status":"PASS" if ok else "FAIL"})
 if not ok:raise AssertionError(label+" got="+str(value)[:180]+" expected="+str(want)[:180])
def canonical(value):
 return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"))
def digest(value):
 return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()
def pack(data,name):
 return {"name":name+".json","mimeType":"application/json",
         "buffer":data.encode("utf-8") if isinstance(data,str) else
                   json.dumps(data,ensure_ascii=False,separators=(",",":")).encode("utf-8")}
class Quiet(http.server.SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
def snap(page):
 return page.evaluate("async()=>await readBackupSnapshot()")
def ready(page):
 page.wait_for_function("""()=>typeof db!=='undefined'&&!!db&&
    typeof PAE04StrictBackup?.checkNoDuplicateKeys==='function'&&
    typeof parseExternalBackupJsonHOME24==='function'""",timeout=20000)
def ui(page,which,raw,expect,positive=False):
 page.locator("#"+which).set_input_files(pack(raw,which+"_"+str(len(CHECKS))))
 view="#verify-result" if which=="verify-file" else "#import-preview"
 page.wait_for_function("""({id,word})=>
   document.querySelector(id)?.textContent.includes(word)""",
   arg={"id":view,"word":expect},timeout=15000)
 ck(which+" exact result "+str(len(CHECKS)),expect in page.locator(view).inner_text())
 if not positive:
  ck(which+" no import pending",page.evaluate("pendingImport===null"))
  ck(which+" checkpoint disabled",page.locator("#checkpoint-button").is_disabled())
  ck(which+" no import",page.locator("#import-button").is_disabled())
def duplicate_raw(signed,kind):
 raw=json.dumps(signed,ensure_ascii=False,separators=(",",":"))
 data=signed["data"]
 if kind=="envelope":
  old='"format":';new='"format":"pae04.healthtracker.synthetic-backup","format":'
 elif kind=="data":
  old='"data":{'
  new='"data":{"pressures":'+json.dumps(data["pressures"],ensure_ascii=False,separators=(",",":"))+','
 elif kind=="pressure":
  old='"pressures":[{';new='"pressures":[{"systolic":120,'
 elif kind=="medication":
  old='"medications":[{';new='"medications":[{"kind":"regular",'
 elif kind=="intake":
  old='"intakes":[{';new='"intakes":[{"status":"active",'
 elif kind=="intakeEvent":
  old='"intakeEvents":[{';new='"intakeEvents":[{"action":"marked",'
 elif kind=="unicode":
  old='"pressures":[{';new='"pressures":[{"\\u0073ystolic":120,'
 else:raise AssertionError("unapproved case "+kind)
 ck(kind+" unique injection anchor",raw.count(old),1)
 raw=raw.replace(old,new,1)
 ck(kind+" duplicate retains original parsed object",json.loads(raw),signed)
 ck(kind+" SHA remains mathematically valid",
    digest({k:v for k,v in json.loads(raw).items() if k!="sha256"}),signed["sha256"])
 return raw
def run():
 server=http.server.ThreadingHTTPServer(("127.0.0.1",0),
   functools.partial(Quiet,directory=str(SITE)))
 server.daemon_threads=True
 threading.Thread(target=server.serve_forever,daemon=True).start()
 try:
  with sync_playwright() as pw:
   browser=pw.chromium.launch(headless=True)
   try:
    ctx=browser.new_context(viewport={"width":390,"height":844},
       device_scale_factor=2,is_mobile=True,has_touch=True,
       locale="ru-RU",service_workers="allow",accept_downloads=True)
    page=ctx.new_page()
    page.on("pageerror",lambda e:PAGE_ERRORS.append(str(e)))
    origin="http://127.0.0.1:"+str(server.server_port)
    page.goto(origin+"/index.html",wait_until="domcontentloaded",timeout=30000)
    ready(page)
    ck("only named HOME24 database",
      page.evaluate("DB_NAME"),"PAE04_HOME24_SYNTHETIC_ISOLATED_DB_20261123")
    ck("no source personal medicine profile",
      page.evaluate("""async()=>(await(await fetch('./personal_profile.json')).json()).medicines.length"""),0)
    ck("initial isolated IDB empty",{k:len(v) for k,v in snap(page).items()},
      {"pressures":0,"medications":0,"intakes":0,"intakeEvents":0})
    page.evaluate("""async()=>{
      const now=new Date(),date=dateLocal(now),created=now.toISOString();
      const p={id:'SYN_HOME24_PRESSURE_001',arm:'right',dateTime:date+'T00:01',
       systolic:120,diastolic:80,pulse:60,note:'',createdAt:created};
      const m={id:'SYN_HOME24_MEDICINE_001',name:'Синтетический препарат А',
       dose:'условная единица',kind:'regular',from:null,to:null,
       dailyIntakes:1,createdAt:created};
      validatePressure(p);validateMed(m);
      await addRecord('pressures',p);await addRecord('medications',m);
      await changeIntake('marked',{id:'SYN_HOME24_INTAKE_001',
       medId:m.id,date,takenAtLocal:date+'T00:02',
       markedAt:created,status:'active',dailySlot:1});
      await reload();
    }""")
    baseline=snap(page)
    global BASELINE_HASH
    BASELINE_HASH=digest(baseline)
    ck("seed all four linked IDB stores",{k:len(v) for k,v in baseline.items()},
       {"pressures":1,"medications":1,"intakes":1,"intakeEvents":1})
    signed=page.evaluate("async()=>await createBackup()")
    ck("v3 SHA independently correct",digest({k:v for k,v in signed.items() if k!="sha256"}),signed["sha256"])
    ck("v3 contains CP41 fields",bool(signed["data"]["intakes"][0].get("dailySlot") and
       signed["data"]["medications"][0].get("dailyIntakes")))
    page.locator('.nav-item[data-page="settings"]').click()
    for kind in ("envelope","data","pressure","medication","intake","intakeEvent","unicode"):
     raw=duplicate_raw(signed,kind)
     before=snap(page)
     ui(page,"verify-file",raw,"DUPLICATE_JSON_KEY")
     ui(page,"import-file",raw,"DUPLICATE_JSON_KEY")
     ck(kind+" IDB byte-equivalent after both selectors",snap(page),before)
     ck(kind+" audit SHA unmodified",digest(snap(page)),BASELINE_HASH)
    # Separate SHA-tampering path remains guarded AFTER the pre-parse check.
    invalid=json.loads(json.dumps(signed))
    invalid["data"]["pressures"][0]["systolic"]=130
    ui(page,"verify-file",invalid,"SHA-256 не совпадает")
    ui(page,"import-file",invalid,"SHA-256 не совпадает")
    ck("SHA negative unchanged IDB",snap(page),baseline)
    # Missing module is fail-closed in both actual app file entrypoints.
    page.evaluate("window.PAE04StrictBackup=undefined")
    ui(page,"verify-file",signed,"Проверка безопасности JSON недоступна")
    ui(page,"import-file",signed,"Проверка безопасности JSON недоступна")
    ck("missing guard cannot write",snap(page),baseline)
    page.reload(wait_until="domcontentloaded")
    ready(page)
    page.locator('.nav-item[data-page="settings"]').click()
    # v1/v2 compatibility with extra CP41 fields; no actual restoration.
    for version in (1,2,3):
     value=json.loads(json.dumps(signed))
     value["version"]=version
     if version<3:del value["data"]["intakeEvents"]
     body={k:v for k,v in value.items() if k!="sha256"}
     value["sha256"]=page.evaluate("async body=>await sha256(body)",body)
     ck("v"+str(version)+" independently signed",value["sha256"],digest(body))
     ui(page,"verify-file",value,"PASS · SHA-256 совпадает",positive=True)
     ui(page,"import-file",value,"Конфликтов: 0",positive=True)
     ck("v"+str(version)+" preview has checkpoint option",
       not page.locator("#checkpoint-button").is_disabled())
     ck("v"+str(version)+" no automatic restore",
       page.locator("#import-button").is_disabled())
     ck("v"+str(version)+" IDB unchanged",snap(page),baseline)
    # A cached pre-parse module is required for offline readiness.
    page.wait_for_function("() => !!navigator.serviceWorker.controller",timeout=35000)
    ck("service worker confined to localhost candidate",
       page.evaluate("navigator.serviceWorker.controller.scriptURL.endsWith('/sw.js')"))
    ck("offline cached guard",page.evaluate("""async()=>{
      const c=await caches.open('pae04-home24-prep-isolated-static-v1-home24-20261123');
      return !!(await c.match('./strict_preflight.js'))}"""))
    ctx.set_offline(True)
    page.reload(wait_until="domcontentloaded")
    ready(page)
    ck("offline helper remains installed",page.evaluate(
        "typeof PAE04StrictBackup.checkNoDuplicateKeys==='function'"))
    ck("offline synthetic IDB persists",snap(page),baseline)
    ctx.set_offline(False)
    ck("no uncaught page JS errors",PAGE_ERRORS,[])
    page.screenshot(path=str(ROOT/"HOME24_CHROME_SYNTHETIC.png"),full_page=False)
    ctx.close()
   finally:browser.close()
 finally:server.shutdown();server.server_close()
if __name__=="__main__":
 status="NOT_RUN"
 try:
  run();status="PASS"
 except Exception as e:
  status="FAIL"
  ERRORS.append(type(e).__name__+": "+str(e))
  traceback.print_exc()
 report={"checkpoint":"PAE04_HOME24_CHROME_20261123","status":status,
  "source":"exact HOME24 prepared app/site SHA pins matched before run",
  "synthetic_only":True,"browser":"GitHub Actions Chromium/Playwright 1.65.1",
  "scope":"two actual file-input handlers; 7 duplicate cases; v1/v2/v3; SHA; missing module; 4-store IDB/offline",
  "checks":CHECKS,"errors":ERRORS,"page_errors":PAGE_ERRORS,
  "baseline_sha256":BASELINE_HASH,
  "security_gate":"OPEN","release":"NO_GO"}
 (ROOT/"HOME24_CHROME_REPORT.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
 print("HOME24_CHROME_QA "+json.dumps({"status":status,"pass":sum(x["status"]=="PASS" for x in CHECKS),
  "fail":sum(x["status"]=="FAIL" for x in CHECKS),"errors":ERRORS},ensure_ascii=False))
 sys.exit(0 if status=="PASS" else 1)
