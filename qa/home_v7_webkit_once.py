#!/usr/bin/env python3
"""PAE-04 HOME-V7: one isolated Linux WebKit QA; synthetic data only."""
import hashlib
import json
import sys
import time
import urllib.request
from playwright.sync_api import sync_playwright

URL = "https://mastyukov-cyber.github.io/pae04-health-tracker-test/home-v7/"
EXPECTED_BLOB = "2859025ad28919a4956392d7431a947f1ad151e4"
EXPECTED_DB = "PAE04_HOME_V7_SYNTHETIC_ISOLATED_20261121"
CHECKS = []

def check(name, passed, details=None):
    if not passed:
        print("FAIL " + name + " " + json.dumps(details, ensure_ascii=False, default=str)[:280], flush=True)
        raise AssertionError(name)
    CHECKS.append(name)
    print("PASS " + name + " " + json.dumps(details, ensure_ascii=False, default=str)[:220], flush=True)

def get_published_blob():
    req = urllib.request.Request(URL + "home.js", headers={"User-Agent": "PAE04-Synthetic-QA/1"})
    with urllib.request.urlopen(req, timeout=16) as response:
        if response.status != 200:
            raise RuntimeError("BLOCKED_PUBLISHED_HOME_JS_HTTP_" + str(response.status))
        raw = response.read(100001)
    if not raw or len(raw) > 100000:
        raise RuntimeError("BLOCKED_PUBLISHED_HOME_JS_SIZE")
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()

def suite():
    check("PIN_PUBLISHED_HOME_JS", get_published_blob() == EXPECTED_BLOB, {"git_blob": EXPECTED_BLOB})
    with sync_playwright() as pw:
        browser = pw.webkit.launch(headless=True)
        try:
            context = browser.new_context(
                viewport={"width": 390, "height": 844},
                device_scale_factor=2,
                is_mobile=True,
                has_touch=True,
                accept_downloads=False,
                service_workers="allow",
            )
            try:
                page = context.new_page()
                page.set_default_timeout(12000)
                response = page.goto(URL, wait_until="load", timeout=35000)
                check("PUBLIC_PREVIEW_HTTP_200", response is not None and response.status == 200,
                      {"http": response.status if response else None})
                page.wait_for_function("() => typeof DB_NAME !== 'undefined' && typeof readBackupSnapshot === 'function'",
                                       timeout=15000)
                initial = page.evaluate("""async () => {
                    const d = await readBackupSnapshot();
                    return {
                        path:location.pathname, db:DB_NAME,
                        stores:Object.fromEntries(Object.entries(d).map(([k,a])=>[k,a.length])),
                        banner:!!document.querySelector('.qa-v7-banner'),
                        importDisabled:document.getElementById('import-file')?.disabled===true,
                        personalScripts:[...document.scripts].filter(x=>/personal_adapter|personal_profile/.test(x.src||'')).length,
                        guard:!!window.PAE04MedicationGuard,
                        width:innerWidth
                    };
                }""")
                check("EXACT_PREVIEW_PATH", initial["path"] == "/pae04-health-tracker-test/home-v7/",
                      {"path":initial["path"]})
                check("ISOLATED_SYNTHETIC_DB", initial["db"] == EXPECTED_DB, {"db":initial["db"]})
                check("NO_PERSONAL_PROFILE_NO_JSON_IMPORT",
                      initial["banner"] and initial["importDisabled"] and initial["personalScripts"] == 0,
                      {"banner":initial["banner"],"disabled":initial["importDisabled"],
                       "personalScripts":initial["personalScripts"]})
                expected_stores = {"pressures", "medications", "intakes", "intakeEvents"}
                check("EMPTY_FOUR_STORES_BEFORE_TEST_WRITES",
                      set(initial["stores"]) == expected_stores and all(v == 0 for v in initial["stores"].values()),
                      initial["stores"])
                check("APP_READY_WEBKIT_MOBILE",initial["guard"] and initial["width"] == 390,
                      {"guard":initial["guard"],"width":initial["width"]})

                seeded = page.evaluate("""async () => {
                    const day=today(),now=new Date().toISOString();
                    const meds=[
                        {name:'QA Бархат',kind:'regular',dailyIntakes:2},
                        {name:'QA Береза',kind:'regular',dailyIntakes:1},
                        {name:'QA Радуга',kind:'course',from:day,to:day,dailyIntakes:3},
                        {name:'QA Искра',kind:'asNeeded'}
                    ];
                    for(const m of meds){
                        m.id=crypto.randomUUID();m.dose='';m.from=m.from||null;
                        m.to=m.to||null;m.createdAt=now;validateMed(m);
                        await addRecord('medications',m);
                    }
                    for(const [s,d,stamp] of [[120,80,day+'T08:00'],[128,84,day+'T18:00']]){
                        const p={id:crypto.randomUUID(),systolic:s,diastolic:d,pulse:70,
                            dateTime:stamp,note:'QA synthetic only',arm:'right',createdAt:now};
                        validatePressure(p);await addRecord('pressures',p);
                    }
                    await reload();
                    return {meds:meds.length,pressure:2};
                }""")
                check("SYNTHETIC_TEST_SEED_ONLY",seeded == {"meds":4,"pressure":2},seeded)
                ui = page.evaluate("""() => ({
                    latest:document.querySelector('.ui01-v7-bp-primary')?.textContent,
                    mean:document.querySelector('.ui01-v7-bp-average')?.textContent,
                    groups:[...document.querySelectorAll('.ui01-med-group .ui01-group-title')].map(e=>e.textContent),
                    slots:[...document.querySelectorAll('.ui01-home-slot input[type=checkbox]')].map(e=>e.getAttribute('aria-label')),
                    next:document.querySelector('.ui01-v7-next')?.innerText,
                    viewport:innerWidth,scrollWidth:document.documentElement.scrollWidth
                })""")
                check("LATEST_AND_MEAN_PRESSURE",ui["latest"] == "128 / 84" and ui["mean"] == "124 / 82",
                      {"latest":ui["latest"],"mean":ui["mean"]})
                check("THREE_MEDICATION_GROUPS",
                      len(ui["groups"]) == 3 and all(any(t in g for g in ui["groups"]) for t in
                          ["Постоянные","Курсовые","Ситуативные"]),
                      {"groups":ui["groups"]})
                check("ONE_TWO_THREE_DAILY_SLOTS",
                      len(ui["slots"]) == 6 and
                      "QA Береза: Приём" in ui["slots"] and
                      "QA Бархат: Вечер" in ui["slots"] and
                      "QA Радуга: День" in ui["slots"],
                      {"count":len(ui["slots"])})
                check("NEXT_SLOT_WITHOUT_INVENTED_HOURS",
                      "плановое время не задано" in (ui["next"] or ""),{"next_visible":bool(ui["next"])})
                check("WEBKIT_MOBILE_NO_HORIZONTAL_SCROLL",
                      ui["viewport"] == 390 and ui["scrollWidth"] <= ui["viewport"] + 4,
                      {"width":ui["viewport"],"scroll":ui["scrollWidth"]})

                page.evaluate("""() => {
                    const box=[...document.querySelectorAll('.ui01-home-slot input[type=checkbox]')]
                        .find(e=>e.getAttribute('aria-label')==='QA Береза: Приём');
                    if(!box)throw Error('Missing synthetic one-slot checkbox');
                    box.click();
                }""")
                page.wait_for_function("""async () => {
                    const d=await readBackupSnapshot();
                    return d.intakes.length === 1 && d.intakeEvents.length === 1;
                }""",timeout=12000)
                marked = page.evaluate("""async () => {
                    const d=await readBackupSnapshot();
                    return {
                        intakes:d.intakes.length,audits:d.intakeEvents.length,
                        collapsed:[...document.querySelectorAll('details.ui01-v7-finished')]
                            .some(x=>!x.open && x.textContent.includes('QA Береза'))
                    };
                }""")
                check("REAL_WEBKIT_CHECKBOX_AUDIT_AND_COLLAPSE",
                      marked["intakes"] == 1 and marked["audits"] == 1 and marked["collapsed"], marked)
                page.reload(wait_until="load",timeout=30000)
                page.wait_for_function("() => typeof readBackupSnapshot === 'function'",timeout=15000)
                persisted=page.evaluate("""async () => {
                    const d=await readBackupSnapshot();
                    return {pressure:d.pressures.length,meds:d.medications.length,
                        intakes:d.intakes.length,events:d.intakeEvents.length};
                }""")
                check("SYNTHETIC_DB_PERSISTS_ON_RELOAD",
                      persisted == {"pressure":2,"meds":4,"intakes":1,"events":1},persisted)
                sw = page.evaluate("""async () => {
                    const regs=await navigator.serviceWorker.getRegistrations();
                    return {scopes:regs.map(r=>r.scope),caches:await caches.keys()};
                }""")
                check("ISOLATED_SERVICE_WORKER_AND_CACHE",
                      any(s.endswith("/home-v7/") for s in sw["scopes"]) and
                      any("pae04-home-v7-qa-synthetic-cache-" in c for c in sw["caches"]),
                      {"scopes":len(sw["scopes"]),"caches":len(sw["caches"])})
            finally:
                context.close()
        finally:
            browser.close()

if __name__ == "__main__":
    started=time.monotonic()
    try:
        suite()
    except Exception as exc:
        print("RESULT=FAIL WEBKIT_HOME_V7_SYNTHETIC checks_passed=" + str(len(CHECKS)) +
              " error=" + type(exc).__name__ + ":" + str(exc)[:350],flush=True)
        sys.exit(1)
    print("RESULT=PASS WEBKIT_HOME_V7_SYNTHETIC checks_passed=" + str(len(CHECKS)) +
          " seconds=" + str(round(time.monotonic()-started,2)),flush=True)
