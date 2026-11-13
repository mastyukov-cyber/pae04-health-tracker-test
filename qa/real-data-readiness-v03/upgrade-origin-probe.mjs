/**
 * PAE-04 REAL-DATA READINESS: synthetic-only upgrade / origin isolation probe.
 * This is diagnostic: PASS means risks were measured, NOT that real data are safe.
 * Does not modify application code, production or public PWA.
 */
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import {resolve,extname,sep} from 'node:path';
import {chromium,webkit} from 'playwright';
const ROOT2=resolve('qa/integration-v02-browser/site-v02');
const ROOT3=resolve('qa/integration-v03-browser/site-v03');
const ENGINE=process.env.PAE04_ENGINE||'chromium';
const OLD='PAE04_HealthTracker_PWA_v021_INTEGRATION_SYNTHETIC_4STORE';
const NEW='PAE04_HealthTracker_PWA_v021_INTEGRATION_SYNTHETIC_V03_CONFIRM_BUTTON_4STORE';
const MIME={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8',
 '.css':'text/css; charset=utf-8','.webmanifest':'application/manifest+json',
 '.svg':'image/svg+xml','.png':'image/png'};
let browser,server,isolatedServer;
let checks=0;
const pass=(s)=>{checks++;console.log('PASS '+checks+' '+s)};
function makeServer(root2,root3){
 return createServer(async(req,res)=>{
  try{
    const u=new URL(req.url,'http://127.0.0.1');
    const v03=u.pathname==='/v03'||u.pathname.startsWith('/v03/');
    const rel=(v03?u.pathname.replace(/^\/v03\/?/,''):u.pathname.replace(/^\//,''))||'index.html';
    const root=v03?root3:root2;
    const target=resolve(root,rel);
    if(!target.startsWith(root+sep)){res.writeHead(403);res.end();return;}
    const data=await readFile(target);
    res.writeHead(200,{'Content-Type':MIME[extname(target)]||'application/octet-stream','Cache-Control':'no-store'});
    res.end(data);
  }catch(e){res.writeHead(404);res.end('Not found')}
 });
}
async function openServer(server){
 await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve)});
 return 'http://127.0.0.1:'+server.address().port;
}
async function readStore(page,name,store){
 return page.evaluate(({name,store})=>new Promise((resolve,reject)=>{
  const req=indexedDB.open(name);
  req.onerror=()=>reject(new Error('open '+name));
  req.onsuccess=()=>{
   const db=req.result;
   if(!db.objectStoreNames.contains(store)){db.close();reject(new Error('store missing '+store));return;}
   const tx=db.transaction(store,'readonly'),get=tx.objectStore(store).getAll();
   get.onsuccess=()=>{const v=get.result;db.close();resolve(v)};
   get.onerror=()=>{db.close();reject(new Error('read failed'))}
  };
 }),{name,store});
}
async function readyForApp(page){
 await page.waitForFunction(()=>document.getElementById('stat-pressure')?.textContent!==undefined,{timeout:15000});
}
async function main(){
 assert.ok(['chromium','webkit'].includes(ENGINE));
 browser=await {chromium,webkit}[ENGINE].launch({headless:true,args:ENGINE==='chromium'?['--no-sandbox']:[]});
 const context=await browser.newContext({serviceWorkers:'allow'});
 server=makeServer(ROOT2,ROOT3);
 const base=await openServer(server);
 const page=await context.newPage();
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base+'/index.html',{waitUntil:'domcontentloaded'});
 await readyForApp(page);
 await page.locator('#systolic').fill('121');
 await page.locator('#diastolic').fill('79');
 await page.locator('#pulse').fill('70');
 await page.locator('#pressure-datetime').fill('2024-06-10T09:00');
 await page.locator('#pressure-form button[type=submit]').click();
 await page.waitForFunction(()=>document.getElementById('stat-pressure')?.textContent==='1');
 const oldRows=await readStore(page,OLD,'pressures');
 assert.equal(oldRows.length,1);
 pass('v02 creates and persists a synthetic record in legacy TEST IndexedDB');
 await page.goto(base+'/v03/index.html',{waitUntil:'domcontentloaded'});
 await readyForApp(page);
 await page.waitForFunction(()=>document.getElementById('stat-pressure')?.textContent==='0');
 const freshRows=await readStore(page,NEW,'pressures');
 assert.equal(freshRows.length,0);
 pass('v03 does not automatically display v02 history after update on SAME origin: MIGRATION BLOCKER');
 const oldFromNewUI=await readStore(page,OLD,'pressures');
 assert.equal(oldFromNewUI.length,1);
 pass('same-origin v03 page can read old v02 IndexedDB by name: PATH NOT AN ISOLATION BOUNDARY');
 await page.waitForFunction(async()=>{
   const reg=await navigator.serviceWorker.getRegistration(location.href);
   return Boolean(reg?.active?.scriptURL?.endsWith('/v03/sw.js')&&reg.active.state==='activated');
 },null,{timeout:20000});
 const keys=await page.evaluate(()=>caches.keys());
 const oldCaches=keys.filter(k=>k.includes('integration-test-v02'));
 const newCaches=keys.filter(k=>k.includes('integration-test-v03'));
 assert.ok(newCaches.length>=1,'v03 SW cache absent');
 pass('v03 Service Worker active; observed cache keys old='+oldCaches.length+' new='+newCaches.length);
 console.log('OBSERVED_CACHE_NAMES='+JSON.stringify(keys));
 // A distinct TCP port is a distinct browser origin, even on same host.
 isolatedServer=makeServer(ROOT2,ROOT3);
 const alt=await openServer(isolatedServer);
 const altPage=await context.newPage();
 await altPage.goto(alt+'/v03/index.html',{waitUntil:'domcontentloaded'});
 await readyForApp(altPage);
 const dbs=await altPage.evaluate(async()=>{
  if(typeof indexedDB.databases!=='function')return null;
  return (await indexedDB.databases()).map(x=>x.name);
 });
 if(dbs!==null)assert.ok(!dbs.includes(OLD),'legacy DB leaked across independent origin');
 pass('separate browser origin has no inherited v02 data');
 assert.equal(errors.length,0,'uncaught page errors: '+errors.join(' | '));
 pass('no uncaught page errors in transition probe');
 console.log('RESULT=PASS CHECKS='+checks+' ENGINE='+ENGINE+' MEANING=RISKS_CONFIRMED_NOT_RELEASE_APPROVAL');
 await context.close();
}
main().catch(e=>{console.error('RESULT=FAIL '+(e.stack||e));process.exitCode=1;}).finally(async()=>{
 try{await browser?.close()}catch{}
 for(const s of [server,isolatedServer])if(s?.listening)await new Promise(resolve=>s.close(resolve));
});
