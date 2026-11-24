'use strict';
/* PAE-04 CP-OFFLINE01: immutable app shell. Never accesses IndexedDB. */
const CACHE_PREFIX='pae04-ht-stable-candidate-synthetic-schema1-cache-';
const CACHE=CACHE_PREFIX+'personal-home-v71-cachefix-20261122';
const SHELL=new URL('./index.html',self.registration.scope).href;
const FILES=[
  './','./index.html','./app.js','./styles.css','./home.js','./home.css',
  './med_guard.mjs','./med_matcher.mjs','./med_guard.css',
  './personal_adapter.js','./personal_profile.json','./offline_status.js',
  './manifest.webmanifest','./icons/icon.svg','./icons/apple-touch-icon.png',
  './icons/icon-192.png','./icons/icon-512.png'
];

self.addEventListener('install',event=>{
  event.waitUntil((async()=>{
    const cache=await caches.open(CACHE);
    await cache.addAll(FILES);
    // Never activate a partially cached release.
    for(const path of ['./','./index.html','./app.js','./home.js',
                       './med_guard.mjs','./offline_status.js']){
      if(!(await cache.match(new URL(path,self.registration.scope).href))){
        throw new Error('CP-OFFLINE01 missing app shell asset: '+path);
      }
    }
    await self.skipWaiting();
  })());
});

self.addEventListener('activate',event=>{
  // Preserve previous version caches for tabs still controlled by an older SW.
  // These caches contain only static app assets, never medicine or pressure data.
  event.waitUntil((async()=>{
    const keys=await caches.keys();
    // Keep two preceding static caches for older Safari tabs; never delete data stores.
    const prior=keys.filter(key=>key.startsWith(CACHE_PREFIX)&&key!==CACHE);
    for(const key of prior.slice(0,Math.max(0,prior.length-2)))await caches.delete(key);
    await self.clients.claim();
  })());
});

async function matchAppShell(request){
  const cache=await caches.open(CACHE);
  const hit=await cache.match(request,{ignoreSearch:request.mode==='navigate'});
  if(hit)return hit;
  // Safari may navigate with query params or with a slash rather than index.html.
  if(request.mode==='navigate')return cache.match(SHELL);
  return undefined;
}

function offlineUnavailable(){
  return new Response(
    '<!doctype html><html lang="ru"><meta charset="utf-8">'+
    '<meta name="viewport" content="width=device-width,initial-scale=1">'+
    '<title>Офлайн-копия не готова</title>'+
    '<body style="font:18px -apple-system,system-ui;padding:25px;line-height:1.5">'+
    '<h1>Офлайн-копия ещё не готова</h1>'+
    '<p>Включите интернет, откройте Health Tracker и дождитесь сообщения '+
    '«Офлайн-копия готова» в разделе «Настройки».</p>'+
    '<p>Не очищайте Safari и не удаляйте приложение: данные хранятся на устройстве.</p>'+
    '</body></html>',
    {status:503,headers:{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store'}}
  );
}

self.addEventListener('fetch',event=>{
  const request=event.request;
  const url=new URL(request.url);
  const scope=new URL(self.registration.scope);
  if(request.method!=='GET'||url.origin!==scope.origin||!url.pathname.startsWith(scope.pathname))return;
  event.respondWith((async()=>{
    try{
      const hit=await matchAppShell(request);
      if(hit)return hit;
    }catch(_cacheError){
      // WebKit can occasionally reject a Cache API operation; do not
      // propagate the rejection directly through respondWith().
    }
    try{
      return await fetch(request);
    }catch(_networkError){
      if(request.mode==='navigate'){
        try{
          const fallback=await matchAppShell(new Request(SHELL,{mode:'same-origin'}));
          if(fallback)return fallback;
        }catch(_cacheError){}
        return offlineUnavailable();
      }
      return Response.error();
    }
  })());
});
