#!/usr/bin/env python3
"""HOME-24: stage exact previously prepared candidate from SHA-pinned published CP41.
No tests and no publication. STOP_FIRST if ANY candidate SHA differs.
"""
import hashlib,json,urllib.request,pathlib
ROOT=pathlib.Path(__file__).resolve().parent
DEST=ROOT/"_staged_site"
BASE="https://mastyukov-cyber.github.io/pae04-health-tracker-test/cp41-sg01-iphone-preview/"
ORIGINAL={
"PREVIEW_PROVENANCE.json":"2578c7a1d225f369953a81a11091d570910b301aeadd49f4797f67ffb1822d32",
"app.js":"255f383826123658ec7ebdde385781a570f0df698d55c31b2e5e871c8ea085d6",
"home.css":"09893b19ca639fc43c7cfd82f95e3c75b759956f7f932db934863b1e5f78334a",
"home.js":"f455b88de7f7c8c388b20516839bcc8f1b0d5cfb204d7562dfc43f62740856b2",
"icons/apple-touch-icon.png":"7e321de521f7c91a8856a66e237b98bb48d36bc89c6246ab90cc0ffb4ce6e11b",
"icons/icon-192.png":"455b1aa541ebd7574d441d82615efd6f02d277c2ecf727077aa274fbbbe74f05",
"icons/icon-512.png":"b5509bdf65dc021a057dac3f6db52de87a5d13d64c34cdc5f8dfc677a4e4f18b",
"icons/icon.svg":"377cd4fa7b4ff64ecd8d4157a9aacc67aaedcede7b39b2f4082e60a0c3b1d606",
"index.html":"995fef930c5ce7478db14d1f1ae3f9108327f9ce5cd14309a720c87c5df599f2",
"manifest.webmanifest":"d024327ff2a516a92092931e5f9ad303744bd529f5ef2e5084316ffc4e3cdf94",
"med_guard.css":"4b606c41bfee2be98ffd90123bc55c19f00888c0c3e18ff2f618ab0e18276389",
"med_guard.mjs":"ff522082f976086884e23fdf493dbbf02416152ca10644c38cd6a3359c03c413",
"med_matcher.mjs":"216b1cdc709d29147eba923973f530ef27c89b5422859c91dac74453666ccd08",
"offline_status.js":"0eec48f511533769447b2ddb688a555f24e890ad3f2ff5754239f8e82f101cfe",
"personal_adapter.js":"38375dfb354ba4e3393b4d9c8d1fe7c18ac76f2b918ba9ac5f9e90babc334a4c",
"personal_profile.json":"4a61bf63f5d4f8100208fabd925d8b589da95934356976c55ccfae546357be88",
"robots.txt":"331ea9090db0c9f6f597bd9840fd5b171830f6e0b3ba1cb24dfa91f0c95aedc1",
"styles.css":"5c4d697d37335fb808ddd688716a93c35fbd14d11d62a79719724dfb7c8b8c2e",
"sw.js":"23508c9c7415ff57a722b856542dbff72bf2a55d908e633f1ee94a389a6d0c25"}
EXPECTED={
"app.js":"882ea9bdf29cbc1365e639348a2b83c76c6b2d94105908203d32c6db821706e3",
"index.html":"95e7a6612d59b81fcd8d3e77f6511b21d49ba6783c17968d0fad37d6e843baba",
"sw.js":"17dfe37a6e021b77b08c91bc2e663f813a11ca6cc147341058dd1b401c8eba76",
"offline_status.js":"1dba39e2a727f74e8f4d2e32e875d3b9c4ea32028d79cc1c7303346ae5fd0582",
"strict_preflight.js":"4fcee08c000764a9665eca30359cf53e2d04cf48fd88f05cd90213304bfb3d70",
"PREVIEW_PROVENANCE.json":"42f9132fd604731ae99e0818ca89e1e737cffb47363a37d2a0dd997491c9e759"}
def sha(b):return hashlib.sha256(b).hexdigest()
def fail(ok,label):
 if not ok:raise SystemExit("STOP_FIRST HOME24 "+label)
def once(s,old,new,name):
 fail(s.count(old)==1,"anchor "+name)
 return s.replace(old,new,1)
def put(name,content):
 p=DEST/name;p.parent.mkdir(exist_ok=True,parents=True);p.write_text(content,encoding="utf-8")
def modify(name,cb):
 p=DEST/name;s=p.read_text(encoding="utf-8");p.write_text(cb(s),encoding="utf-8")
def main():
 fail(not DEST.exists(),"fresh staging directory required")
 for name,pin in ORIGINAL.items():
  req=urllib.request.Request(BASE+name,headers={"User-Agent":"PAE04-HOME24-SYNTHETIC-SHA-PIN"})
  with urllib.request.urlopen(req,timeout=30) as resp:
   fail(resp.status==200,"HTTP "+name)
   data=resp.read(1000000)
  fail(sha(data)==pin,"source drift "+name)
  p=DEST/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
 fail(json.loads((DEST/"personal_profile.json").read_text())["medicines"]==[],"personal catalog")
 guard=ROOT/"strict_preflight.js"
 fail(sha(guard.read_bytes())==EXPECTED["strict_preflight.js"],"HOME23 exact original guard SHA")
 (DEST/"strict_preflight.js").write_bytes(guard.read_bytes())
 def change_app(s):
  s=once(s,
   "const DB_NAME='PAE04_CP41_SG01_SYNTHETIC_ISOLATED_DB_20261123';",
   "const DB_NAME='PAE04_HOME24_SYNTHETIC_ISOLATED_DB_20261123';","DB isolation")
  helper="""// HOME-24: apply only HOME-23 R3 duplicate-key scan; preserve CP41 validators.
// Do NOT call historical parseChecked(): its field allowlist predates CP41.
function parseExternalBackupJsonHOME24(raw){
  const scan=globalThis.PAE04StrictBackup?.checkNoDuplicateKeys;
  if(typeof scan!=='function')throw Error('Проверка безопасности JSON недоступна');
  scan(raw); // may throw DUPLICATE_JSON_KEY before JSON.parse
  return JSON.parse(raw);
}
"""
  s=once(s,"let backupVerifySequence=0;",helper+"let backupVerifySequence=0;","helper")
  old="const parsed=JSON.parse(await file.text());"
  fail(s.count(old)==2,"two file-picker inputs")
  return s.replace(old,"const parsed=parseExternalBackupJsonHOME24(await file.text());")
 modify("app.js",change_app)
 def change_html(s):
  s=once(s,"CP41-SG01 iPhone v2.3","HOME-24 iPhone v2.3 · НЕ ОПУБЛИКОВАНО","UI warning")
  return once(s,'  <script src="./app.js" defer></script>',
              '  <script src="./strict_preflight.js" defer></script>\n  <script src="./app.js" defer></script>',"HTML script order")
 modify("index.html",change_html)
 def change_sw(s):
  s=once(s,"const CACHE_PREFIX='pae04-cp41-sg01-isolated-static-';",
    "const CACHE_PREFIX='pae04-home24-prep-isolated-static-';","SW prefix")
  s=once(s,"const CACHE=CACHE_PREFIX+'v1-20261123';",
    "const CACHE=CACHE_PREFIX+'v1-home24-20261123';","SW version")
  s=once(s,"'./','./index.html','./app.js','./styles.css'",
    "'./','./index.html','./strict_preflight.js','./app.js','./styles.css'","SW resources")
  return once(s,"'./','./index.html','./app.js','./home.js'",
    "'./','./index.html','./strict_preflight.js','./app.js','./home.js'","SW required")
 modify("sw.js",change_sw)
 def change_offline(s):
  s=once(s,"pae04-cp41-sg01-isolated-static-v1-20261123",
        "pae04-home24-prep-isolated-static-v1-home24-20261123","offline cache")
  return once(s,"'./','./index.html','./app.js','./styles.css'",
          "'./','./index.html','./strict_preflight.js','./app.js','./styles.css'","offline required")
 modify("offline_status.js",change_offline)
 provenance={
 "project":"PAE-04 HEALTH TRACKER",
 "checkpoint":"HOME-24 CP41 pre-parse JSON duplicate-key guard preparation",
 "status":"PREPARED_NOT_TESTED",
 "approval":"READ_ONLY_SOURCE_AND_SANDBOX_PREPARATION_ONLY",
 "source":"EXACT published CP41 GitHub Pages Actions 45165229283",
 "cp41_source_sandbox_head":"76e144028de7701d6f7bffcdc515ab5aaf373201",
 "cp41_cyber_main":"4e5403389232801a6dd3966542e8cdeece4f32a2",
 "home23_strict_preflight_sha256":"4fcee08c000764a9665eca30359cf53e2d04cf48fd88f05cd90213304bfb3d70",
 "reuse":"checkNoDuplicateKeys() ONLY; parseChecked() NOT CALLED: legacy field allowlist conflicts with CP41",
 "synthetic_only":True,"qa_execution":"NOT_RUN","publication":"NOT_DEPLOYED",
 "release":"NO_GO","storage":"new HOME24 IndexedDB and CacheStorage names; shared origins not equivalent to security isolation"}
 put("PREVIEW_PROVENANCE.json",json.dumps(provenance,ensure_ascii=False,indent=2)+"\n")
 for name,h in EXPECTED.items():
  fail(sha((DEST/name).read_bytes())==h,"candidate SHA mismatch "+name)
 fail(len([p for p in DEST.rglob("*") if p.is_file()])==20,"candidate 20 files")
 print("HOME24_PREPARED_CANDIDATE_SHA_PINS PASS: 20/20 files; HOME23 exact guard unchanged; no deployment")
if __name__=="__main__":main()
