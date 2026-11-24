'use strict';
/* CP-OFFLINE01. Diagnostic only: never opens or modifies IndexedDB.
   A green network dot is NOT proof that the offline app shell is installed. */
(function(){
  const CACHE='pae04-ht-stable-candidate-synthetic-schema1-cache-personal-home-v71-cachefix-20261122';
  const REQUIRED=[
    './','./index.html','./app.js','./styles.css','./home.js','./home.css',
    './med_guard.mjs','./med_matcher.mjs','./med_guard.css',
    './personal_adapter.js','./personal_profile.json','./offline_status.js'
  ];
  const status=document.getElementById('pae04-offline-status');
  if(!status)return;
  let generation=0;
  function render(ready,message){
    status.dataset.ready=ready?'true':'false';
    status.textContent=message;
  }
  async function inspect(){
    const myGeneration=++generation;
    let ready=false,caption='Офлайн-копия не готова · подключите интернет';
    try{
      if(!('serviceWorker' in navigator)||!('caches' in window)){
        caption='Safari не предоставил офлайн-хранилище';
      }else{
        const names=await caches.keys();
        if(!names.includes(CACHE)){
          caption='Офлайн-копия готовится · нужен интернет';
        }else{
          const cache=await caches.open(CACHE);
          const found=await Promise.all(REQUIRED.map(file=>cache.match(file).then(Boolean)));
          const registration=await navigator.serviceWorker.getRegistration('./');
          // Do not advertise readiness until SW controls the page.
          ready=!!registration?.active && !!navigator.serviceWorker.controller && found.every(Boolean);
          caption=ready?'Офлайн-копия готова · можно отключать интернет'
                       :'Офлайн-копия готовится · нужен интернет';
        }
      }
    }catch(_err){
      caption='Не удалось проверить офлайн-копию · оставьте интернет включённым';
    }
    if(myGeneration===generation)render(ready,caption);
  }
  render(false,'Офлайн-копия: проверяем…');
  inspect();
  if('serviceWorker' in navigator){
    navigator.serviceWorker.addEventListener('controllerchange',inspect);
    navigator.serviceWorker.ready.then(inspect).catch(inspect);
    // Register or refresh the app shell; never reads or changes IndexedDB.
    navigator.serviceWorker.register('./sw.js',{scope:'./',updateViaCache:'none'})
      .then(inspect).catch(inspect);
  }
  window.addEventListener('online',inspect);
  window.addEventListener('offline',inspect);
  // Safari can finish the install after DOMContentLoaded and ready.
  setTimeout(inspect,1500);
  setTimeout(inspect,4000);
})();
