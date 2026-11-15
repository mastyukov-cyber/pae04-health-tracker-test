#!/usr/bin/env python3
"""CP-REAL01: detached personalized iPhone PWA. Python 3.12. Never deploys."""
import argparse
import html
import json
import re
import shutil
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
ALLOWED_KINDS={"regular","course","asNeeded"}

def check_profile(profile):
    if profile.get("schema")!="PAE04_PERSONAL_QA_PROFILE_V1" or profile.get("purpose")!="PERSONAL_TEST_ONLY":
        raise ValueError("Unexpected personal test profile")
    cards=profile["medicines"]
    refs=profile["reference_catalog"]
    if len(cards)!=10 or len(refs)!=10 or len(set(c["name"] for c in cards))!=10:
        raise ValueError("Unexpected medicines or catalog")
    if not profile["constraints"]["offline"] or profile["constraints"]["seed_intakes"] or profile["constraints"]["seed_pressures"]:
        raise ValueError("Unexpected test constraints")
    for m in cards:
        if m["kind"] not in ALLOWED_KINDS or not m["name"] or len(m["dose"])>60:
            raise ValueError("Unsafe medicine profile record")
        if m["from"] and m["to"] and m["from"]>m["to"]:
            raise ValueError("Invalid dates")
    return cards,refs

def build(src:Path,dest:Path):
    if not src.is_dir() or dest.exists():
        raise ValueError("Missing source or output already exists, refusing overwrite")
    parent=json.loads((src/"CP_UI01_BUILD.json").read_text(encoding="utf8"))
    if parent["status"]!="synthetic_candidate_only" or parent["db_schema_changed"] or parent["backup_format_changed"]:
        raise ValueError("Unexpected CP-UI01 provenance")
    profile=json.loads((HERE/"personal_profile.json").read_text(encoding="utf8"))
    meds,catalog=check_profile(profile)
    source_files=["index.html","app.js","med_guard.mjs","sw.js","home.js","home.css"]
    data={x:(src/x).read_text(encoding="utf8") for x in source_files}
    if "CP-UI02: 320px high-font navigation overflow fix" not in data["home.css"]:
        raise ValueError("Missing accepted CP-UI02 narrow-screen fix")
    app=data["app.js"]
    expected="!m.name.startsWith('Учебный препарат')"
    if app.count(expected)!=1: raise ValueError("Medicine validator not at expected version")
    app=app.replace(expected,
        "(m.name.trim().length<2 || /[<>\\u0000-\\u001f]/.test(m.name))",1)
    listener="['Учебный препарат А','Учебный препарат Б','Учебный препарат В'].includes(e.target.value)"
    if app.count(listener)!=1: raise ValueError("Unexpected catalog handler")
    allowed=json.dumps([m["name"] for m in catalog],ensure_ascii=False)
    app=app.replace(listener,allowed+".includes(e.target.value)",1)
    data["app.js"]=app
    guard=data["med_guard.mjs"]
    old="""export const SYNTHETIC_CATALOG = Object.freeze([
  {id:'catalog-a',name:'Учебный препарат А'},
  {id:'catalog-b',name:'Учебный препарат Б'},
  {id:'catalog-v',name:'Учебный препарат В'}
]);"""
    if guard.count(old)!=1: raise ValueError("Unexpected medication guard source")
    refdata=[{k:v for k,v in m.items() if k in
       ("id","name","aliases","ingredient","strength","unit","form")} for m in catalog]
    guard=guard.replace(old,"export const SYNTHETIC_CATALOG = Object.freeze("+
                        json.dumps(refdata,ensure_ascii=False,separators=(",",":"))+");",1)
    guard=guard.replace("в учебном справочнике","в локальном справочнике")
    data["med_guard.mjs"]=guard
    index=data["index.html"]
    original="".join('<option value="Учебный препарат '+name+'"></option>' for name in ["А","Б","В"])
    if index.count(original)!=1: raise ValueError("Unexpected catalog datalist")
    options="".join('<option value="'+html.escape(m["name"],quote=True)+'"></option>' for m in catalog)
    index=index.replace(original,options,1)
    index=index.replace("Тестовый справочник","Справочник лекарств и добавок",1)
    index=index.replace("Например: Учебный препарат А","Например: Капотен",1)
    index=index.replace("Учебная дозировка; не заменяет назначение","Указанная дозировка (можно уточнить)",1)
    index=index.replace("Дозировка препарата / концентрация (учебная)","Дозировка препарата / концентрация",1)
    index=index.replace("PAE-04 · v0.2.1 SAFE UX TEST v05.5.2",
                        "PAE-04 · CP-REAL01 PERSONAL PREVIEW · v05.5.2",1)
    anchor='<script src="./home.js" defer></script>'
    if index.count(anchor)!=1: raise ValueError("Unexpected home script marker")
    index=index.replace(anchor,anchor+'\n  <script src="./personal_adapter.js" defer></script>',1)
    data["index.html"]=index
    home=data["home.js"]
    label="desc.append(element('strong','ui01-med-name',m.name));"
    if home.count(label)!=1: raise ValueError("Unexpected home dose label marker")
    home=home.replace(label,label+
        "\n    if(m.dose)desc.append(element('span','ui01-personal-dose',m.dose));",1)
    data["home.js"]=home
    sw=data["sw.js"]
    cache="cache-cpui01-20261115"
    if sw.count(cache)!=1 or sw.count("const FILES=[")!=1:
        raise ValueError("Unexpected offline service worker")
    sw=sw.replace(cache,"cache-cpreal01-20261115",1)
    sw=sw.replace("const FILES=[",
      "const FILES=['./personal_adapter.js','./personal_profile.json',",1)
    data["sw.js"]=sw
    data["home.css"]+="""\n/* CP-REAL01: personal test profile and dose labels, no fake intake records */
.ui01-personal-dose{color:#365a80;font-size:calc(13px * var(--ht-home-scale));line-height:1.4}
.pae04-profile-panel{background:#f4f8ff;border:1px solid #bcd1ee;border-radius:17px;
  padding:16px;margin:15px 0;line-height:1.45}
.pae04-profile-panel button{width:100%;min-height:52px;background:#286ed6;color:#fff;
  border:0;border-radius:12px;font-size:16px;font-weight:700;padding:10px}
.pae04-profile-panel button:disabled{background:#8b9ab0}
.pae04-profile-panel p{margin:7px 0;color:#41556e;font-size:14px;overflow-wrap:anywhere}
@media(max-width:355px){.pae04-profile-panel{padding:12px}}
"""
    shutil.copytree(src,dest)
    for name,body in data.items():
        (dest/name).write_text(body,encoding="utf8")
    shutil.copyfile(HERE/"personal_profile.json",dest/"personal_profile.json")
    shutil.copyfile(HERE/"personal_adapter.js",dest/"personal_adapter.js")
    (dest/"CP_REAL01_BUILD.json").write_text(json.dumps({
      "status":"personal_preview_not_published","parent":"CP-UI02 checked candidate",
      "medical_records_copied":False,"seed_intakes":False,"seed_pressures":False,
      "db_schema_changed":False,"backup_format_changed":False,"medicines":len(meds),
      "source_unchanged":True,"auto_seed":False
    },ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print("RESULT=PASS CP_REAL01_PERSONAL_CANDIDATE 10_CARDS NO_AUTO_SEED NO_DEPLOY")

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    build(a.source.resolve(),a.output.resolve())
