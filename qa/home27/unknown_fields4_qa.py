#!/usr/bin/env python3
"""PAE04 HOME-27: exact HOME24 site, four unknown-field cases, two actual file inputs.
SYNTHETIC ONLY; no publication, merge, or real medical records.
"""
import functools,hashlib,http.server,json,pathlib,threading,traceback,sys
from playwright.sync_api import sync_playwright

ROOT=pathlib.Path(__file__).resolve().parent.parent/"home24"
SITE=ROOT/"_staged_site"
CHECKS=[];ERRORS=[];PAGE_ERRORS=[]
def assert_check(label, condition):
    CHECKS.append({"name":label,"status":"PASS" if condition else "FAIL"})
    if not condition: raise AssertionError(label)
def canonical(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"))
def digest(v):return hashlib.sha256(canonical(v).encode("utf-8")).hexdigest()
def snapshot(page):return page.evaluate("async()=>await readBackupSnapshot()")
def upload(page,selector,value,label,expect):
    page.locator("#"+selector).set_input_files({
        "name":"HOME27_"+label+"_"+selector+".json",
        "mimeType":"application/json",
        "buffer":json.dumps(value,ensure_ascii=False,separators=(",",":")).encode()
    })
    result="#verify-result" if selector=="verify-file" else "#import-preview"
    page.wait_for_function(
        "({sel,marker})=>document.querySelector(sel)?.textContent.includes(marker)",
        arg={"sel":result,"marker":expect},timeout=15000
    )
    output=page.locator(result).inner_text()
    assert_check(label+" "+selector+" expected message",expect in output)
    return output
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*args):pass
def run():
    assert_check("staged HOME24 20 files",len([p for p in SITE.rglob("*") if p.is_file()])==20)
    server=http.server.ThreadingHTTPServer(("127.0.0.1",0),
        functools.partial(Quiet,directory=str(SITE)))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True)
            try:
                context=browser.new_context(viewport={"width":390,"height":844},
                    device_scale_factor=2,is_mobile=True,has_touch=True,
                    locale="ru-RU",service_workers="allow")
                page=context.new_page()
                page.on("pageerror",lambda e:PAGE_ERRORS.append(str(e)))
                page.goto("http://127.0.0.1:"+str(server.server_port)+"/index.html",
                    wait_until="domcontentloaded",timeout=30000)
                page.wait_for_function("""()=>typeof db!=='undefined'&&!!db&&
                    typeof parseExternalBackupJsonHOME24==='function'&&
                    typeof validateExternalBackupShape==='function'""",timeout=20000)
                assert_check("HOME24 isolated DB only",page.evaluate("DB_NAME")==
                    "PAE04_HOME24_SYNTHETIC_ISOLATED_DB_20261123")
                assert_check("no source medicine profile",
                    page.evaluate("async()=> (await (await fetch('./personal_profile.json')).json()).medicines.length")==0)
                assert_check("initial four stores empty",
                    {k:len(v) for k,v in snapshot(page).items()}==
                    {"pressures":0,"medications":0,"intakes":0,"intakeEvents":0})
                page.evaluate("""async()=>{
                    const now=new Date(),date=dateLocal(now),created=now.toISOString();
                    const p={id:'SYN_HOME27_PRESSURE_001',arm:'right',dateTime:date+'T00:01',
                      systolic:120,diastolic:80,pulse:60,note:'',createdAt:created};
                    const m={id:'SYN_HOME27_MEDICINE_001',name:'Синтетический препарат А',
                      dose:'условная единица',kind:'regular',from:null,to:null,
                      dailyIntakes:1,createdAt:created};
                    validatePressure(p);validateMed(m);
                    await addRecord('pressures',p);await addRecord('medications',m);
                    await changeIntake('marked',{id:'SYN_HOME27_INTAKE_001',
                      medId:m.id,date,takenAtLocal:date+'T00:02',
                      markedAt:created,status:'active',dailySlot:1});
                    await reload();
                    window.__home27MergeCalls=0;
                    const original=atomicMerge;
                    atomicMerge=async(...args)=>{window.__home27MergeCalls++;return original(...args)};
                }""")
                baseline=snapshot(page); baseline_sha=digest(baseline)
                assert_check("seed four stores",
                    {k:len(v) for k,v in baseline.items()}==
                    {"pressures":1,"medications":1,"intakes":1,"intakeEvents":1})
                page.locator('.nav-item[data-page="settings"]').click()
                for kind,store in [("envelope",None),("pressure","pressures"),
                                   ("intake","intakes"),("intakeEvent","intakeEvents")]:
                    obj=page.evaluate("async()=>await createBackup()")
                    if store:obj["data"][store][0]["pae04_probe_unknown"]=True
                    else:obj["pae04_probe_unknown"]=True
                    body={k:v for k,v in obj.items() if k!="sha256"}
                    obj["sha256"]=page.evaluate("async body=>await sha256(body)",body)
                    assert_check(kind+" signed SHA matches independent digest",obj["sha256"]==digest(body))
                    for selector in ("verify-file","import-file"):
                        message=upload(page,selector,obj,kind,"Неизвестное поле")
                        assert_check(kind+" "+selector+" exact field",
                            "pae04_probe_unknown" in message)
                        assert_check(kind+" "+selector+" no pending restore",
                            page.evaluate("pendingImport===null"))
                        assert_check(kind+" "+selector+" checkpoint disabled",
                            page.locator("#checkpoint-button").is_disabled())
                        assert_check(kind+" "+selector+" import disabled",
                            page.locator("#import-button").is_disabled())
                        assert_check(kind+" "+selector+" unchanged IndexedDB",
                            digest(snapshot(page))==baseline_sha)
                    page.reload(wait_until="domcontentloaded")
                    page.wait_for_function("()=>typeof db!=='undefined'&&!!db",timeout=20000)
                    page.locator('.nav-item[data-page="settings"]').click()
                    assert_check(kind+" IDB persisted after reload",
                        digest(snapshot(page))==baseline_sha)
                    assert_check(kind+" atomicMerge zero calls",
                        page.evaluate("typeof window.__home27MergeCalls==='undefined'||window.__home27MergeCalls===0"))
                for version in (1,2,3):
                    obj=page.evaluate("async()=>await createBackup()")
                    obj["version"]=version
                    if version<3:del obj["data"]["intakeEvents"]
                    body={k:v for k,v in obj.items() if k!="sha256"}
                    obj["sha256"]=page.evaluate("async body=>await sha256(body)",body)
                    assert_check("v"+str(version)+" independent SHA",obj["sha256"]==digest(body))
                    upload(page,"verify-file",obj,"v"+str(version),"PASS · SHA-256 совпадает")
                    upload(page,"import-file",obj,"v"+str(version),"Конфликтов: 0")
                    assert_check("v"+str(version)+" no automatic import",
                        page.locator("#import-button").is_disabled())
                    assert_check("v"+str(version)+" IDB unchanged",
                        digest(snapshot(page))==baseline_sha)
                assert_check("no uncaught page exceptions",PAGE_ERRORS==[])
                context.close()
                return baseline_sha
            finally:browser.close()
    finally:server.shutdown();server.server_close()
if __name__=="__main__":
    status="NOT_RUN";baseline_sha=None
    try:baseline_sha=run();status="PASS"
    except Exception as e:
        status="FAIL";ERRORS.append(type(e).__name__+": "+str(e))
        traceback.print_exc()
    report={"checkpoint":"PAE04_HOME27_UNKNOWN_FIELDS4_20261123","status":status,
      "scope":"4 unknown field cases x 2 actual file handlers, v1/v2/v3 positive, isolated four-store IndexedDB",
      "source":"HOME24 SHA-pinned staged site, CP41 validator unchanged",
      "synthetic_only":True,"browser":"GitHub Actions Chromium Playwright 1.65.1",
      "checks":CHECKS,"errors":ERRORS,"page_errors":PAGE_ERRORS,
      "baseline_sha256":baseline_sha,"security_gate":"OPEN","release":"NO_GO"}
    out=pathlib.Path(__file__).resolve().parent/"HOME27_UNKNOWN_FIELDS4_REPORT.json"
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("HOME27_RESULT "+json.dumps({"status":status,
      "pass":sum(x["status"]=="PASS" for x in CHECKS),
      "fail":sum(x["status"]=="FAIL" for x in CHECKS),"errors":ERRORS},ensure_ascii=False))
    sys.exit(0 if status=="PASS" else 1)
