'use strict';
// PAE-04 CP39R-R9: single isolated Linux Chromium regression. No real data, no import/restore.
const fs=require('node:fs');
const path=require('node:path');
const http=require('node:http');
const os=require('node:os');
const crypto=require('node:crypto');
const cp=require('node:child_process');
const {chromium}=require('playwright-core');

const SOURCE_SHA='bc4de06f7536ad889dae720e1cce52c5453fdbed';
const EXPECTED_MAIN='86fafc7d55b9fde867c3dc0536fa21d89419323e';
const DB_NAME='PAE04_CYBER_CP39R_R7_SYNTHETIC_ONLY_20261122';
const ROOT=path.resolve(__dirname,'../../candidates/pae04-cp39r-r7-synthetic-build-20261122');
const SITE=path.join(ROOT,'site');
const WORK=path.join(process.env.RUNNER_TEMP||os.tmpdir(),'pae04-cp39r-r9-linux-once');
const PROFILE=path.join(WORK,'profile');
const DOWNLOADS=path.join(WORK,'downloads');
const checks=[], errors=[];
let server=null,context=null,page=null,downloadFile=null,phase='START',status='BLOCKED',httpHits=0;
const started=Date.now();
function gate(test,name,details={}){
  const yes=Boolean(test);
  checks.push({name,status:yes?'PASS':'FAIL',details});
  console.log((yes?'PASS ':'FAIL ')+name+' '+JSON.stringify(details).slice(0,200));
  if(!yes)throw Error('STOP_FIRST_'+name);
}
function command(binary,args){
  const r=cp.spawnSync(binary,args,{encoding:'utf8',timeout:8000});
  if(r.status!==0)throw Error('COMMAND_FAILED '+binary+' '+String(r.stderr).slice(0,100));
  return r.stdout.trim();
}
function canonical(value){
  if(Array.isArray(value))return '['+value.map(canonical).join(',')+']';
  if(value!==null&&typeof value==='object')return '{'+Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+canonical(value[k])).join(',')+'}';
  return JSON.stringify(value);
}
function digest(body){return crypto.createHash('sha256').update(canonical(body)).digest('hex')}
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function snapshot(){return await page.evaluate(async()=>canonical(await readBackupSnapshot()))}
async function counts(){
  return await page.evaluate(async()=>{const d=await readBackupSnapshot();return Object.fromEntries(STORE_NAMES.map(k=>[k,d[k].length]));});
}
async function awaitCount(store,count){
  await page.waitForFunction(async([k,n])=>{
    if(typeof readBackupSnapshot!=='function')return false;
    try{const d=await readBackupSnapshot();return d[k].length===n}catch{return false}
  },[store,count],{timeout:10000});
}
async function chooseFile(selector,value,filename){
  const target=selector==='#verify-file'?'#verify-result':'#import-preview';
  const prev=await page.locator(target).textContent().catch(()=> '');
  await page.locator(selector).setInputFiles({name:filename,mimeType:'application/json',buffer:Buffer.from(value,'utf8')});
  await page.waitForFunction(({target,prev})=>{
    const v=document.querySelector(target)?.textContent||'';
    return v!==prev&&(v.includes('PASS')||v.includes('FAIL')||v.includes('Ошибка:'));
  },{target,prev},{timeout:12000});
  return {
    message:(await page.locator(target).textContent()||'').slice(0,400),
    importDisabled:await page.locator('#import-button').isDisabled(),
    checkpointDisabled:await page.locator('#checkpoint-button').isDisabled(),
    persisted:await snapshot()
  };
}
async function run(){
  phase='PINNED_SOURCE';
  gate(process.env.GITHUB_REPOSITORY==='mastyukov-cyber/pae04-health-tracker-test','REPOSITORY');
  gate(process.env.GITHUB_EVENT_NAME==='pull_request'&&process.env.GITHUB_RUN_ATTEMPT==='1','ONE_SHOT_EVENT');
  gate(command('git',['rev-parse','HEAD~2'])===SOURCE_SHA,'SOURCE_PARENT_SHA',{source:SOURCE_SHA});
  gate(command('git',['rev-parse','--verify','HEAD']).length===40,'HEAD_VALID');
  const manifest=JSON.parse(fs.readFileSync(path.join(ROOT,'MANIFEST_SHA256.json'),'utf8'));
  gate(manifest.files?.length===22&&manifest.releaseGo===false&&manifest.source?.head==='0c471c1798bff2c3fbf812b81cc235b482387c20'&&manifest.destination?.base_main===EXPECTED_MAIN,'MANIFEST_PIN');
  const actual=[];
  for(const entry of fs.readdirSync(SITE,{recursive:true,withFileTypes:true})){
    if(entry.isSymbolicLink())throw Error('SYMLINK_IN_SITE');
    if(entry.isFile()){const p=path.join(entry.parentPath||entry.path,entry.name);actual.push(path.relative(SITE,p).split(path.sep).join('/'))}
  }
  gate(actual.length===22&&manifest.files.every(f=>actual.includes(f.path.slice(5))),'FILE_ALLOWLIST_22');
  for(const f of manifest.files){
    const target=path.resolve(ROOT,f.path);
    if(!target.startsWith(SITE+path.sep))throw Error('PATH_TRAVERSAL');
    const data=fs.readFileSync(target);
    if(crypto.createHash('sha256').update(data).digest('hex')!==f.sha256)throw Error('SHA_MISMATCH '+f.path);
  }
  gate(true,'SHA256_22_ASSETS',{files:22});
  const profile=JSON.parse(fs.readFileSync(path.join(SITE,'personal_profile.json'),'utf8'));
  gate(profile.medicines?.length===10&&profile.medicines.every(x=>/^Тестовый препарат \d\d$/.test(x.name))&&profile.constraints?.seed_intakes===false&&profile.constraints?.seed_pressures===false,'SYNTHETIC_PROFILE');
  const forbidden=/Эдарби|Эспиро|Липримар|Беталок|Капотен|Atomy|HemoHIM|Korean Red Ginseng|Betaloc|Turmacin|Probiotics|азилсартан|эплеренон|метопролол|аторвастатин|каптоприл/i;
  for(const f of manifest.files.filter(x=>!x.path.endsWith('.png'))){
    if(forbidden.test(fs.readFileSync(path.join(ROOT,f.path),'utf8')))throw Error('PRIVACY_BLOCK '+f.path);
  }
  gate(true,'STATIC_SYNTHETIC_PRIVACY_SCAN');
  for(const p of ['app.js','home.js','offline_status.js','personal_adapter.js','med_guard.mjs','med_matcher.mjs','sw.js'])
    command('node',['--check',path.join(SITE,p)]);
  gate(true,'NODE26_SYNTAX_7');

  phase='LOCAL_HTTP';
  if(fs.existsSync(WORK))throw Error('OUTPUT_ALREADY_EXISTS');
  fs.mkdirSync(WORK,{recursive:false});fs.mkdirSync(DOWNLOADS,{recursive:false});
  const mime={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.mjs':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.json':'application/json','.webmanifest':'application/manifest+json','.svg':'image/svg+xml','.png':'image/png','.ico':'image/x-icon'};
  server=http.createServer((req,res)=>{
    let name;
    try{name=decodeURIComponent(new URL(req.url,'http://127.0.0.1').pathname)}catch{res.writeHead(400);res.end();return}
    const target=path.resolve(SITE,'.'+(name==='/'?'/index.html':name));
    if(req.method!=='GET'||!target.startsWith(SITE+path.sep)||!fs.existsSync(target)||!fs.statSync(target).isFile()){res.writeHead(404);res.end();return}
    httpHits++;
    res.writeHead(200,{'Content-Type':mime[path.extname(target)]||'application/octet-stream','Cache-Control':'no-store'});
    fs.createReadStream(target).pipe(res);
  });
  await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve)});
  const address='http://127.0.0.1:'+server.address().port+'/index.html';

  phase='BROWSER_LAUNCH';
  const chrome=command('which',['google-chrome']);
  gate(chrome.startsWith('/')&&fs.existsSync(chrome),'CHROME_PREINSTALLED');
  context=await chromium.launchPersistentContext(PROFILE,{
    executablePath:chrome,headless:true,acceptDownloads:true,downloadsPath:DOWNLOADS,
    serviceWorkers:'allow',viewport:{width:390,height:844},
    args:['--no-proxy-server','--disable-sync','--disable-background-networking','--disable-component-update','--no-default-browser-check','--no-first-run']
  });
  await context.route('**/*',route=>{
    const u=new URL(route.request().url());
    if(u.hostname==='127.0.0.1'&&u.protocol==='http:')return route.continue();
    return route.abort('blockedbyclient');
  });
  page=await context.newPage();page.setDefaultTimeout(12000);
  phase='INTEGRATED_PWA_LOAD';
  await page.goto(address,{waitUntil:'load',timeout:20000});
  await page.waitForFunction(()=>document.readyState==='complete'&&Boolean(window.PAE04MedicationGuard),null,{timeout:12000});
  await page.waitForFunction(()=>document.querySelector('#connection-status')?.textContent?.includes('Локальная база доступна')&&typeof db!=='undefined'&&db!==null&&typeof readBackupSnapshot==='function',null,{timeout:15000});
  const dom=await page.evaluate(()=>({pressure:!!document.getElementById('pressure-form'),meds:!!document.getElementById('med-form'),verify:!!document.getElementById('verify-file'),preview:!!document.getElementById('import-file'),export:!!document.getElementById('export-button'),guard:!!window.PAE04MedicationGuard}));
  gate(Object.values(dom).every(Boolean)&&httpHits>0,'INTEGRATED_PWA_LOAD',dom);
  const empty=await counts();
  gate(Object.values(empty).every(n=>n===0)&&await page.evaluate(()=>DB_NAME)===DB_NAME,'EMPTY_ISOLATED_IDB',{empty});

  phase='PRESSURE_UI';
  await page.evaluate(()=>{
    const d=new Date(Date.now()-86400000),p=n=>String(n).padStart(2,'0');
    const day=d.getFullYear()+'-'+p(d.getMonth()+1)+'-'+p(d.getDate());
    document.getElementById('systolic').value='123';
    document.getElementById('diastolic').value='79';
    document.getElementById('pulse').value='72';
    document.getElementById('pressure-datetime').value=day+'T12:00';
    document.getElementById('pressure-note').value='SYNTHETIC_R9_ONLY';
    document.getElementById('pressure-form').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));
  });
  await awaitCount('pressures',1);
  const pressure=await page.evaluate(async()=>{const d=await readBackupSnapshot();return d.pressures[0]});
  gate(pressure?.arm==='right'&&pressure?.systolic===123&&pressure?.diastolic===79&&pressure?.pulse===72,'PRESSURE_UI_IDB',{arm:pressure?.arm});

  phase='MEDICATION_UI';
  const medAction=await page.evaluate(()=>{
    const name=document.getElementById('med-name');
    name.value='R9 Вымышленный тестовый препарат';
    name.dispatchEvent(new Event('input',{bubbles:true}));
    document.getElementById('med-dose').value='SYNTHETIC_ONLY';
    document.getElementById('med-kind').value='regular';
    document.getElementById('med-daily-target').value='2';
    const button=document.querySelector('.med-guard-confirm');
    if(!button)return {error:'CONFIRM_NOT_FOUND'};
    button.click();return {clicked:true};
  });
  if(medAction.error)throw Error(medAction.error);
  await awaitCount('medications',1);
  const med=await page.evaluate(async()=>{const d=await readBackupSnapshot();return d.medications[0]});
  gate(med?.dailyIntakes===2&&med?.kind==='regular'&&med.name.startsWith('R9 Вымышленный'),'MEDICATION_GUARD_IDB',{dailyIntakes:med?.dailyIntakes});

  phase='INTAKE_UI';
  const intakeAction=await page.evaluate(()=>{
    const d=new Date(Date.now()-86400000),p=n=>String(n).padStart(2,'0');
    const day=d.getFullYear()+'-'+p(d.getMonth()+1)+'-'+p(d.getDate());
    const date=document.getElementById('intake-date');
    date.value=day;date.dispatchEvent(new Event('change',{bubbles:true}));
    const inputs=[...document.querySelectorAll('.med-schedule-slot input[type=checkbox]')];
    const time=document.querySelector('.med-time-controls .intake-time-input');
    if(inputs.length!==2||!time)return {error:'INTAKE_CONTROLS',count:inputs.length};
    time.value='09:10';inputs[0].checked=true;
    inputs[0].dispatchEvent(new Event('change',{bubbles:true}));
    return {slots:inputs.length};
  });
  if(intakeAction.error)throw Error('INTAKE_UI '+JSON.stringify(intakeAction));
  await awaitCount('intakes',1);await awaitCount('intakeEvents',1);
  const intake=await page.evaluate(async()=>{const d=await readBackupSnapshot();return {intake:d.intakes[0],events:d.intakeEvents.length}});
  gate(intake.events===1&&intake.intake?.status==='active'&&intake.intake?.medId===med.id,'INTAKE_AUDIT_4_STORES',{events:intake.events});

  phase='RELOAD_PERSISTENCE';
  await page.reload({waitUntil:'load',timeout:18000});
  await page.waitForFunction(()=>document.querySelector('#connection-status')?.textContent?.includes('Локальная база доступна')&&typeof db!=='undefined'&&db!==null&&typeof readBackupSnapshot==='function',null,{timeout:15000});
  const persisted=await counts();
  gate(Object.values(persisted).every(x=>x===1),'PERSISTENT_IDB_4_STORES',persisted);

  phase='EXPORT_REAL_DOWNLOAD';
  const filePromise=page.waitForEvent('download',{timeout:15000});
  await page.evaluate(()=>document.getElementById('export-button').click());
  const download=await filePromise;
  downloadFile=path.join(DOWNLOADS,'R9-SYNTHETIC-EXPORTED.json');
  await download.saveAs(downloadFile);
  gate(fs.existsSync(downloadFile)&&fs.statSync(downloadFile).size>50,'REAL_BROWSER_BACKUP_DOWNLOAD',{bytes:fs.statSync(downloadFile).size});
  const backup=JSON.parse(fs.readFileSync(downloadFile,'utf8'));
  const {sha256:expected,...body}=backup;
  const countsBackup=Object.fromEntries(['pressures','medications','intakes','intakeEvents'].map(k=>[k,backup.data?.[k]?.length]));
  gate(backup.format==='pae04.healthtracker.synthetic-backup'&&backup.version===3&&expected===digest(body)&&Object.values(countsBackup).every(x=>x===1),'EXPORTED_BACKUP_SHA256_AND_COUNTS',countsBackup);

  const baseline=await snapshot(),valid=fs.readFileSync(downloadFile,'utf8');
  phase='VERIFY_VALID_EXTERNAL_JSON';
  const verified=await chooseFile('#verify-file',valid,'R9-VALID.json');
  gate(verified.message.includes('PASS · SHA-256')&&verified.persisted===baseline,'VERIFY_DOWNLOADED_JSON_UI');
  phase='PREVIEW_VALID_NO_IMPORT';
  const preview=await chooseFile('#import-file',valid,'R9-VALID.json');
  gate(preview.message.includes('Проверка SHA-256 PASS')&&!preview.checkpointDisabled&&preview.importDisabled&&preview.persisted===baseline,'PREVIEW_VALID_NO_IMPORT');

  const invalidCases=[
    ['envelope',b=>{b.syntheticUnknown='qa-canary'}],
    ['pressure',b=>{b.data.pressures[0].syntheticUnknown='qa-canary'}],
    ['intake',b=>{b.data.intakes[0].syntheticUnknown='qa-canary'}],
    ['intakeEvent',b=>{b.data.intakeEvents[0].syntheticUnknown='qa-canary'}]
  ];
  for(const [name,change] of invalidCases){
    phase='STRICT_UNKNOWN_'+name;
    const modified=structuredClone(body);change(modified);
    const invalid=JSON.stringify({...modified,sha256:digest(modified)});
    for(const [selector,label] of [['#verify-file','VERIFY'],['#import-file','PREVIEW']]){
      const selected=await chooseFile(selector,invalid,'R9-UNKNOWN-'+name+'-'+label+'.json');
      gate(selected.message.includes('Неизвестное поле резервной копии')&&selected.persisted===baseline&&(label==='VERIFY'||selected.importDisabled),'STRICT_UNKNOWN_'+name+'_'+label,{rejected:true});
    }
  }

  phase='BAD_HASH';
  const corrupted=JSON.stringify({...body,sha256:'0'.repeat(64)});
  for(const [selector,label] of [['#verify-file','VERIFY'],['#import-file','PREVIEW']]){
    const selected=await chooseFile(selector,corrupted,'R9-BAD-HASH-'+label+'.json');
    gate(selected.message.includes('SHA-256 не совпадает')&&selected.persisted===baseline&&(label==='VERIFY'||selected.importDisabled),'BAD_HASH_'+label,{rejected:true});
  }
  phase='SERVICE_WORKER_CACHE';
  const sw=await page.evaluate(async()=>{await Promise.race([navigator.serviceWorker.ready,new Promise((_,reject)=>setTimeout(()=>reject(Error('SW_TIMEOUT')),12000))]);return {controlled:!!navigator.serviceWorker.controller,keys:await caches.keys()};});
  gate(sw.controlled&&sw.keys.some(x=>x.startsWith('pae04-cyber-cp39r-r7-synthetic-isolated-cache-')),'SERVICE_WORKER_CACHE_READY',{controlled:sw.controlled,keys:sw.keys.length});

  phase='OFFLINE_RELOAD';
  await context.setOffline(true);
  await page.reload({waitUntil:'domcontentloaded',timeout:18000});
  await page.waitForFunction(()=>document.querySelector('#connection-status')?.textContent?.includes('Локальная база доступна')&&typeof db!=='undefined'&&db!==null&&typeof readBackupSnapshot==='function',null,{timeout:15000});
  const offline=await counts();
  const ok=await page.evaluate(()=>document.readyState!=='loading'&&!!document.getElementById('pressure-form')&&!!navigator.serviceWorker.controller);
  gate(ok&&Object.values(offline).every(v=>v===1),'OFFLINE_RELOAD_IDB_4_STORES',offline);

  status='PASS_INTEGRATED_LINUX_CHROMIUM_SCOPED';phase='DONE';
}
(async()=>{
  try{await run();}
  catch(e){errors.push({phase,message:String(e.stack||e).slice(0,1400)});status=String(e).includes('STOP_FIRST')?'FAIL_SCOPED':'BLOCKED_EXECUTION';}
  finally{
    if(context)try{await context.close()}catch(e){errors.push({phase:'CLEANUP',message:String(e).slice(0,180)})}
    if(server)try{server.closeAllConnections();await new Promise(resolve=>server.close(resolve))}catch(e){errors.push({phase:'CLEANUP_SERVER',message:String(e).slice(0,180)})}
    const browserChecks=checks.slice(11);
    if(status==='PASS_INTEGRATED_LINUX_CHROMIUM_SCOPED'&&(checks.length!==33||browserChecks.length!==22||browserChecks.some(x=>x.status!=='PASS'))){status='FAIL_INCOMPLETE_SCOPE';errors.push({phase:'SCOPE',message:'Expected 11 preflight and 22 browser checks'});}
    const report={checkpoint:'CP39R-R9',status,phase,source:{pr:22,sourceHead:SOURCE_SHA},counts:{tests:checks.length,passed:checks.filter(x=>x.status==='PASS').length,failed:checks.filter(x=>x.status==='FAIL').length,preflightTotal:checks.slice(0,11).length,browserTotal:browserChecks.length,browserPassed:browserChecks.filter(x=>x.status==='PASS').length},httpHits,durationSeconds:+((Date.now()-started)/1000).toFixed(2),testNames:checks.map(x=>({name:x.name,status:x.status})),errors,syntheticOnly:true,realImportPerformed:false,restorationPerformed:false,macUsed:false,artifactUploaded:false,releaseGo:false};
    console.log('PAE04_CP39R_R9_RESULT '+JSON.stringify(report));
    if(process.env.GITHUB_STEP_SUMMARY)try{fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY,'### PAE-04 CP39R-R9 — '+status+'\nTests: '+report.counts.passed+'/'+report.counts.tests+'; runtime '+report.durationSeconds+' s; PR #22 source '+SOURCE_SHA+'; release NO-GO.\n')}catch{}
    if(status!=='PASS_INTEGRATED_LINUX_CHROMIUM_SCOPED')process.exitCode=1;
  }
})();
