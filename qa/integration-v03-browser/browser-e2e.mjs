/**
 * PAE-04 / v0.2.1 Integration Test v03 (OFFLINE FIX)
 * Full Chromium + real IndexedDB + SW E2E against SHA-verified site assets.
 * Synthetic-only. No main, external network, real health records, or Mac.
 */
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {createServer} from 'node:http';
import {readFile, mkdir, writeFile} from 'node:fs/promises';
import {resolve, extname, sep, join} from 'node:path';
import {chromium,webkit} from 'playwright';

const ROOT=resolve('qa/integration-v03-browser/site-v03');
const REPORT_DIR=resolve('qa/integration-v03-browser/reports');
const DB_NAME='PAE04_HealthTracker_PWA_v021_INTEGRATION_SYNTHETIC_V03_CONFIRM_BUTTON_4STORE';
const STORE_NAMES=['pressures','medications','intakes','intakeEvents'];
const RESOURCES=['/','/index.html','/app.js','/styles.css','/manifest.webmanifest','/icons/icon.svg',
 '/icons/apple-touch-icon.png','/icons/icon-192.png','/icons/icon-512.png'];
const MIME={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8',
 '.css':'text/css; charset=utf-8','.webmanifest':'application/manifest+json',
 '.svg':'image/svg+xml','.png':'image/png'};
const FORMAT='pae04.healthtracker.synthetic-backup';
const ENGINE=process.env.PAE04_ENGINE||'chromium';
if(!['chromium','webkit'].includes(ENGINE))throw new Error('Unsupported QA browser');
let server,browser,primaryContext,primaryPage;
let pass=0;const issues=[];const milestones=[];
const watchdog=setTimeout(()=>{console.error('RESULT=FAIL WATCHDOG_180S');process.exit(124)},180000);
const mark=(label)=>{pass++;milestones.push({number:pass,label,status:'PASS'});console.log(`PASS ${pass} ${label}`);};
const canonical=value=>{
 if(Array.isArray(value))return '['+value.map(canonical).join(',')+']';
 if(value!==null&&typeof value==='object')return '{'+Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+canonical(value[k])).join(',')+'}';
 return JSON.stringify(value);
};
function signedBackup(version,data){
 const body={format:FORMAT,version,exportedAt:'2026-11-12T10:10:00.000Z',data};
 return {...body,sha256:createHash('sha256').update(canonical(body)).digest('hex')};
}
function delay(ms){return new Promise(resolve=>setTimeout(resolve,ms));}
async function httpServer(){
 return await new Promise((done,reject)=>{
  const srv=createServer(async(req,res)=>{
   try{
    if(req.method!=='GET'&&req.method!=='HEAD'){res.writeHead(405);res.end();return;}
    const url=new URL(req.url,'http://127.0.0.1');
    const relative=decodeURIComponent(url.pathname).replace(/^\/+/, '')||'index.html';
    const filename=resolve(ROOT,relative);
    if(!filename.startsWith(ROOT+sep)){res.writeHead(403);res.end();return;}
    const data=await readFile(filename);
    res.writeHead(200,{'Content-Type':MIME[extname(filename)]||'application/octet-stream',
      'Cache-Control':'no-cache','X-Content-Type-Options':'nosniff'});
    if(req.method==='HEAD')res.end();else res.end(data);
   }catch(e){res.writeHead(e.code==='ENOENT'?404:500);res.end();}
  });
  srv.once('error',reject);
  srv.listen(0,'127.0.0.1',()=>done(srv));
 });
}
async function readDB(page){
 return page.evaluate(async({DB_NAME,STORE_NAMES})=>{
  const database=await new Promise((res,rej)=>{const req=indexedDB.open(DB_NAME);req.onsuccess=()=>res(req.result);req.onerror=()=>rej(req.error);});
  try{
   const stores=Array.from(database.objectStoreNames);
   const entries={};
   for(const name of STORE_NAMES){
    entries[name]=await new Promise((res,rej)=>{
     const tx=database.transaction(name,'readonly');const req=tx.objectStore(name).getAll();
     req.onsuccess=()=>res(req.result);req.onerror=()=>rej(req.error);
    });
   }
   const indices={};
   for(const name of ['intakes','intakeEvents']){
    const tx=database.transaction(name,'readonly');indices[name]=Array.from(tx.objectStore(name).indexNames);
   }
   return {stores,entries,indices};
  } finally {database.close();}
 },{DB_NAME,STORE_NAMES});
}
async function safeCreateContext(base){
 const context=await browser.newContext({viewport:{width:390,height:844},acceptDownloads:true,serviceWorkers:'allow'});
 const page=await context.newPage();
 page.setDefaultTimeout(10000);
 page.on('dialog',d=>d.accept().catch(()=>{}));
 page.on('pageerror',e=>issues.push(`PAGEERROR ${String(e)}`));
 await page.goto(base+'/index.html',{waitUntil:'load',timeout:15000});
 await page.waitForFunction(()=>document.getElementById('stat-meds')?.textContent==='0',null,{timeout:10000});
 return {context,page};
}
async function importUI(page,backup){
 await page.locator('[data-page="backup"]').click();
 await page.locator('#import-file').setInputFiles({name:`synthetic-v${backup.version}.json`,mimeType:'application/json',
   buffer:Buffer.from(JSON.stringify(backup))});
 await page.waitForFunction(()=>document.getElementById('import-preview')?.textContent?.trim().length>0,null,{timeout:10000});
 return {text:await page.locator('#import-preview').innerText(),enabled:await page.locator('#import-button').isEnabled()};
}
async function main(){
 try{
 await mkdir(REPORT_DIR,{recursive:true});
 server=await httpServer();
 const base=`http://127.0.0.1:${server.address().port}`;
 browser=await (ENGINE==='webkit'?webkit:chromium).launch(ENGINE==='webkit'?{headless:true}:{headless:true,args:['--no-sandbox']});
 for(const path of RESOURCES){const r=await fetch(base+path);assert.equal(r.status,200,`${path}: HTTP ${r.status}`);}
 mark('HTTP 200 on all 9 original v03 Service Worker resources');
 const start=await safeCreateContext(base);
 primaryContext=start.context;primaryPage=start.page;
 const page=primaryPage;
 assert.match(await page.title(),/HEALTH TRACKER|Health Tracker/i);
 mark(`Actual v03 HTML loaded in ${ENGINE}`);
 // ServiceWorker.ready can resolve during 'activating'; require page control.
 await page.waitForFunction(async()=>{
   const registration=await navigator.serviceWorker.ready;
   return registration.active?.state==='activated'&&Boolean(navigator.serviceWorker.controller);
 },null,{timeout:20000});
 const sw=await page.evaluate(async()=>{
  const reg=await navigator.serviceWorker.ready;
  const cacheNames=await caches.keys();
  const cacheName=cacheNames.find(n=>n.includes('pae04-pwa-v021-integration-test-v03'));
  const resources=cacheName?await (await caches.open(cacheName)).keys():[];
  return {active:reg.active?.state,cacheName,keys:resources.map(x=>new URL(x.url).pathname)};
 });
 assert.equal(sw.active,'activated');assert.ok(sw.cacheName,'v03 cache not installed');
 for(const p of RESOURCES)assert.ok(sw.keys.includes(p==='/'?'/':'/'+p.replace(/^\//,'')),`missing SW cache ${p}`);
 mark('Service Worker installed, activated and caches all 9 resources');
 const initDB=await readDB(page);
 assert.deepEqual(initDB.stores.sort(),STORE_NAMES.slice().sort());
 assert.ok(initDB.indices.intakes.includes('byMedDay'));
 assert.ok(initDB.indices.intakeEvents.includes('byIntakeId'));
 mark('Real IndexedDB opens four stores and both indexes');
 await page.locator('[data-page="meds"]').click();
 await page.locator('#med-name').fill('Учебный препарат А');
 await page.locator('#med-dose').fill('Тестовая текстовая дозировка');
 await page.locator('#med-strength').fill('10');
 await page.locator('#med-unit').selectOption({label:'мг'});
 await page.locator('#med-form-factor').selectOption({label:'таблетки'});
 await page.locator('#med-kind').selectOption('regular');
 await page.locator('#med-form button[type="submit"]').click();
 await page.waitForFunction(()=>document.getElementById('stat-meds')?.textContent==='1');
 const created=(await readDB(page)).entries.medications;
 assert.equal(created.length,1);assert.equal(created[0].pae04v021?.strength,10);
 assert.equal(created[0].dose,'Тестовая текстовая дозировка');
 mark('Real UI creates only synthetic medication and preserves legacy dose');
 await page.locator('#intake-date').fill('2024-06-10');
 await page.locator('#med-list .med-time-controls input[type="time"]').fill('08:15');
 await page.locator('#med-list .intake-confirm-button').click();
 await page.waitForFunction(()=>document.querySelectorAll('#med-list .intake-record').length===1);
 const firstState=await readDB(page);const firstId=firstState.entries.intakes[0].id;
 await page.locator('#med-list .med-time-controls input[type="time"]').fill('20:15');
 await page.locator('#med-list .intake-confirm-button').click();
 await page.waitForFunction(()=>document.querySelectorAll('#med-list .intake-record').length===2);
 let current=(await readDB(page)).entries;
 assert.equal(current.intakes.length,2);assert.equal(current.intakeEvents.length,2);
 assert.notEqual(current.intakes[0].id,current.intakes[1].id);
 mark('Two independent intakes of the same medication recorded in one day');

 // New v03 UX acceptance: duplicate same-time click must not add a new intake or event.
 await page.locator('#med-list .med-time-controls input[type="time"]').fill('20:15');
 await page.locator('#med-list .intake-confirm-button').click();
 await page.waitForFunction(()=>document.querySelector('#messages .message.error')?.textContent?.includes('Приём в 20:15 уже отмечен'));
 let afterDuplicate=(await readDB(page)).entries;
 assert.equal(afterDuplicate.intakes.length,2);
 assert.equal(afterDuplicate.intakeEvents.length,2);
 assert.equal(await page.locator('#med-list .intake-confirm-button').textContent(),'✓ Подтвердить приём');
 mark('v03 button rejects repeated same-time intake and preserves audit history');
 const firstRow=page.locator('#med-list .intake-record').first();
 await firstRow.locator('input[type="time"]').fill('09:10');
 await firstRow.getByRole('button',{name:'Изменить время'}).click();
 await page.waitForFunction(()=>document.querySelector('#med-list')?.textContent?.includes('08:15 → 09:10'));
 current=(await readDB(page)).entries;
 assert.equal(current.intakeEvents.length,3);
 const modified=current.intakes.find(i=>i.id===firstId);assert.equal(modified.takenAtLocal,'2024-06-10T09:10');
 assert.equal(modified.markedAt,firstState.entries.intakes[0].markedAt);
 mark('Time correction keeps original mark and adds immutable audit event');
 await page.locator('#med-list .intake-record').nth(1).getByRole('button',{name:'Отменить отметку'}).click();
 await page.waitForFunction(()=>document.querySelectorAll('#med-list .intake-record.cancelled').length===1);
 current=(await readDB(page)).entries;
 assert.equal(current.intakes.length,2);assert.equal(current.intakeEvents.length,4);
 assert.equal(current.intakes.filter(i=>i.status==='cancelled').length,1);
 mark('Cancellation retains intake record and adds fourth audit event');
 await page.locator('[data-page="pressure"]').click();
 await page.locator('#systolic').fill('121');await page.locator('#diastolic').fill('79');
 await page.locator('#pulse').fill('70');await page.locator('#pressure-datetime').fill('2024-06-10T09:00');
 await page.locator('#pressure-form button[type="submit"]').click();
 await page.waitForFunction(()=>document.getElementById('stat-pressure')?.textContent==='1');
 const savedBefore=await readDB(page);
 assert.equal(savedBefore.entries.pressures[0].arm,'right');
 mark('Manual pressure test persists right-arm measurement');

 // New v03 mobile-layout acceptance: iPhone-sized viewport, pressure date stays in card.
 await page.setViewportSize({width:375,height:812});
 const dateRect=await page.locator('#pressure-datetime').boundingBox();
 const formRect=await page.locator('#pressure-form').boundingBox();
 assert.ok(dateRect&&formRect,'missing pressure date field or form on mobile');
 assert.ok(dateRect.x>=formRect.x-1 && dateRect.x+dateRect.width<=formRect.x+formRect.width+1,
  'pressure datetime overflows the iPhone-width form');
 await page.setViewportSize({width:1280,height:720});
 mark('v03 iPhone-width pressure date input fits within its card');
 await page.locator('[data-page="backup"]').click();
 const [download]=await Promise.all([page.waitForEvent('download'),page.locator('#export-button').click()]);
 const exported=JSON.parse(await readFile(await download.path(),'utf8'));
 assert.equal(exported.version,3);assert.equal(exported.format,FORMAT);
 const {sha256,...body}=exported;
 assert.equal(sha256,createHash('sha256').update(canonical(body)).digest('hex'));
 assert.deepEqual(Object.keys(exported.data).sort(),STORE_NAMES.slice().sort());
 mark('Actual UI downloads v3 backup with valid full-data SHA-256');
 const restore=await safeCreateContext(base);
 const v3Preview=await importUI(restore.page,exported);
 assert.ok(v3Preview.enabled,`v3 preview rejected: ${v3Preview.text}`);
 await restore.page.locator('#import-button').click();
 await restore.page.waitForFunction(()=>document.getElementById('stat-meds')?.textContent==='1');
 const restored=await readDB(restore.page);
 for(const table of STORE_NAMES){
  assert.deepEqual(restored.entries[table].sort((a,b)=>a.id.localeCompare(b.id)),
    savedBefore.entries[table].sort((a,b)=>a.id.localeCompare(b.id)),`v3 restoration mismatch in ${table}`);
 }
 mark('v3 restore writes actual data to a fresh four-store IndexedDB');
 const duplicate=await importUI(restore.page,exported);
 assert.match(duplicate.text,/Новых:\s*0/);
 assert.ok(duplicate.enabled,'idempotent re-import preview should be enabled');
 await restore.page.locator('#import-button').click();
 await restore.page.waitForFunction(()=>document.getElementById('import-preview')?.textContent?.includes('Добавлено 0'));
 const twice=await readDB(restore.page);
 for(const t of STORE_NAMES)assert.equal(twice.entries[t].length,restored.entries[t].length);
 mark('Repeated v3 import is idempotent without duplicates');
 const fakeMed={id:'synthetic-medicine-v1',name:'Учебный препарат Б',dose:'тест',kind:'regular',from:null,to:null,createdAt:'2024-06-10T09:00:00Z'};
 for(const version of [1,2]){
  const legacyIntake={id:`synthetic-intake-v${version}`,medId:fakeMed.id,date:'2024-06-10',markedAt:'2024-06-10T08:15:00Z'};
  if(version===2)legacyIntake.takenAtLocal='2024-06-10T08:15';
  const archive=signedBackup(version,{pressures:[],medications:[fakeMed],intakes:[legacyIntake]});
  const stage=await safeCreateContext(base);
  const preview=await importUI(stage.page,archive);
  assert.ok(preview.enabled,`v${version} preview rejected: ${preview.text}`);
  await stage.page.locator('#import-button').click();
  await stage.page.waitForFunction(()=>document.getElementById('stat-meds')?.textContent==='1');
  const db=await readDB(stage.page);
  assert.equal(db.entries.intakes.length,1);assert.equal(db.entries.intakeEvents.length,0);
  if(version===1)assert.equal(db.entries.intakes[0].takenAtLocal,undefined,'v1 must not invent intake time');
  else assert.equal(db.entries.intakes[0].takenAtLocal,'2024-06-10T08:15');
  await stage.context.close();
  mark(`Real browser import restores historical backup format v${version} safely`);
 }
 const tampered=structuredClone(exported);tampered.data.medications[0].dose='tampered';
 const beforeTamper=await readDB(restore.page);
 const bad=await importUI(restore.page,tampered);
 assert.equal(bad.enabled,false);
 assert.match(bad.text,/SHA-256|поврежд/i);
 const afterTamper=await readDB(restore.page);
 for(const t of STORE_NAMES)assert.deepEqual(afterTamper.entries[t],beforeTamper.entries[t]);
 mark('Damaged import rejected with all four IndexedDB stores unchanged');
 const conflicting=structuredClone(exported);conflicting.data.medications[0].dose='Другой тестовый текст';
 const {sha256:discard,...conflictBody}=conflicting;
 conflicting.sha256=createHash('sha256').update(canonical(conflictBody)).digest('hex');
 const conflict=await importUI(restore.page,conflicting);
 assert.equal(conflict.enabled,false);assert.match(conflict.text,/Конфликтов:\s*[1-9]/i);
 mark('Re-signed but conflicting record is rejected before import');
 const atomicProbe=await restore.page.evaluate(async()=>{
  // Actual app atomicMerge, not an IndexedDB mock. It must abort every write.
  const before=await getAll('pressures');
  const first=before[0];
  const extra={...first,id:'synthetic-pressure-rollback-01'};
  const badExisting={...first,note:'Конфликт теста'};
  let failed=false;
  try{await atomicMerge({pressures:[extra,badExisting],medications:[],intakes:[],intakeEvents:[]})}
  catch{failed=true}
  const after=await getAll('pressures');
  return {failed,original:before.length,now:after.length,unmodified:after.every(p=>before.some(x=>JSON.stringify(x)===JSON.stringify(p)))};
 });
 assert.equal(atomicProbe.failed,true);assert.equal(atomicProbe.now,atomicProbe.original);assert.equal(atomicProbe.unmodified,true);
 mark('Actual atomicMerge abort rolls back earlier queued IndexedDB writes');
 await restore.context.close();
 // Existing primary context has a SW and populated IndexedDB. A new tab while
 // offline must load via Cache Storage, and records must persist after reload.
 await page.waitForFunction(()=>Boolean(navigator.serviceWorker.controller),null,{timeout:15000});
 if(ENGINE==='webkit'){
   // Linux Playwright WebKit may throw an internal navigation error with
   // browserContext.setOffline(true). Test origin failure separately instead.
   await new Promise((resolve,reject)=>server.close(error=>error?reject(error):resolve()));
   server=null;
   console.log('PAE04_WEBKIT_ORIGIN_DOWN: local test server stopped; SW must serve navigation');
 }else{
   await primaryContext.setOffline(true);
 }
 await page.reload({waitUntil:'domcontentloaded',timeout:15000});
 await page.waitForFunction(()=>document.getElementById('stat-meds')?.textContent==='1');
 const offline=await readDB(page);
 assert.equal(offline.entries.intakes.length,2);assert.equal(offline.entries.intakeEvents.length,4);
 const newTab=await primaryContext.newPage();
 await newTab.goto(base+'/index.html',{waitUntil:'domcontentloaded',timeout:15000});
 await newTab.waitForFunction(()=>document.getElementById('stat-meds')?.textContent==='1');
 assert.equal((await readDB(newTab)).entries.intakes.length,2);
 await newTab.close();
 if(ENGINE!=='webkit')await primaryContext.setOffline(false);
 mark(ENGINE==='webkit'?'Origin-down SW reload and new tab keep IndexedDB stores':
   'Offline reload and new tab via SW keep all four IndexedDB data stores');
 assert.equal(issues.length,0,`Unexpected page errors: ${issues.join(' | ')}`);
 mark('No uncaught JavaScript page errors across full browser scenarios');
 console.log(`RESULT=PASS CHECKS=${pass} FAILURES=0 MODE=REAL_${ENGINE.toUpperCase()}_AND_INDEXEDDB SOURCE_ZIP_SHA=6633a51d713019e38b2094b79218b6a97ac8f230325accd4a25dc31c29a991ab`);
} catch(e){
 issues.push(e?.stack||String(e));
 console.error(`RESULT=FAIL PASSED_BEFORE_FAILURE=${pass} ${e?.stack||e}`);
 process.exitCode=1;
 try{if(primaryPage)await primaryPage.screenshot({path:join(REPORT_DIR,'failure.png'),fullPage:true,timeout:5000});}catch{}
} finally{
 await mkdir(REPORT_DIR,{recursive:true}).catch(()=>{});
 await writeFile(join(REPORT_DIR,'summary.json'),JSON.stringify({status:process.exitCode?'FAIL':'PASS',pass,issues,milestones},null,2));
 try{await primaryContext?.close();}catch{}
 try{await browser?.close();}catch{}
 if(server)await new Promise(resolve=>server.close(resolve));
 clearTimeout(watchdog);
}

}
main().catch(e=>{console.error("RESULT=FAIL OUTER",e?.stack||String(e));process.exitCode=1;clearTimeout(watchdog);});
