#!/usr/bin/env python3
"""CP-REAL01 strict static gate. Python 3.12; no personal history ever imported."""
import json
import sys
from pathlib import Path

site=Path(sys.argv[1]).resolve()
src=Path(__file__).resolve().parents[1]
profile=json.loads((site/"personal_profile.json").read_text(encoding="utf8"))
meta=json.loads((site/"CP_REAL01_BUILD.json").read_text(encoding="utf8"))
app=(site/"app.js").read_text(encoding="utf8")
guard=(site/"med_guard.mjs").read_text(encoding="utf8")
html=(site/"index.html").read_text(encoding="utf8")
sw=(site/"sw.js").read_text(encoding="utf8")
home=(site/"home.js").read_text(encoding="utf8")
addon=(site/"personal_adapter.js").read_text(encoding="utf8")
meds=profile["medicines"];catalog=profile["reference_catalog"]
checks=[
 ("profile schema",profile["schema"]=="PAE04_PERSONAL_QA_PROFILE_V1"),
 ("ten unique names",len(meds)==10 and len(set(x["name"] for x in meds))==10),
 ("ten local reference entries",len(catalog)==10),
 ("known heart medication doses",{
      x["name"]:x["dose"] for x in meds
    }.items() >= {"Эдарби":"20 мг","Эспиро":"25 мг",
                 "Липримар":"10 мг","Беталок ЗОК":"12,5 мг"}.items()),
 ("Capoten has no fabricated personal dose",next(x for x in meds if x["key"]=="capoten")["product_strength_mg"] is None),
 ("Capoten has 25 mg CATALOG product strength",any(x["name"]=="Капотен" and x["strength"]==25 for x in catalog)),
 ("course start Nov 13",all(x["from"]=="2026-11-13" for x in meds if x["key"] in ("turmacin","omega3"))),
 ("completed probiotic historical",next(x for x in meds if x["key"]=="probiotics")["to"]=="2026-11-13"),
 ("no intake or pressure fixtures",profile["constraints"]["seed_intakes"] is False and profile["constraints"]["seed_pressures"] is False),
 ("build remains preview only",meta["status"]=="personal_preview_not_published" and not meta["medical_records_copied"]),
 ("schema and backup unchanged",meta["db_schema_changed"] is False and meta["backup_format_changed"] is False and "const BACKUP_VERSION=3" in app),
 ("four IndexedDB stores unchanged", "['pressures','medications','intakes','intakeEvents']" in app),
 ("real medication names permitted", "!m.name.startsWith('Учебный препарат')" not in app),
 ("guard still active", "PAE04MedicationGuard" in app and "saveMedicationAtomic" in app),
 ("catalog supplies correct names", all(x["name"] in guard for x in catalog)),
 ("medicine categories kept", all(x["kind"] in ("regular","course","asNeeded") for x in meds)),
 ("manual names accepted with guard", "assessEntry" in guard and "need" in guard),
 ("offline profile & adapter", all(x in sw for x in ("'./personal_profile.json'","'./personal_adapter.js'","cache-cpreal01"))),
 ("only explicit seed", "button.addEventListener('click',seed)" in addon and "NO writes at boot" in addon),
 ("atomic serialization", "db.transaction(stores,'readwrite')" in addon and ".add(med)" in addon),
 ("refuse nonempty test DB", "counts[name]!==0" in addon and "tx.abort()" in addon),
 ("no fake schedule", "Плановое время не задано" in home),
 ("real dosing on home", "ui01-personal-dose" in home),
 ("user-facing preview identifier", "CP-REAL01 PERSONAL PREVIEW" in html),
 ("narrow navigation fix inherited", "CP-UI02: 320px high-font navigation overflow fix" in (site/"home.css").read_text(encoding="utf8")),
 ("no external APIs", all(t not in addon for t in ("localStorage.setItem(", "XMLHttpRequest(", "https://", "sendBeacon("))),
 ("no source overwrite", meta["source_unchanged"] is True),
]
for label,ok in checks:
 print(("PASS " if ok else "FAIL ")+label,flush=True)
if not all(ok for _,ok in checks):
 raise SystemExit("RESULT=FAIL CP_REAL01_STATIC")
print(f"RESULT=PASS CP_REAL01_STATIC={len(checks)}/{len(checks)}",flush=True)
