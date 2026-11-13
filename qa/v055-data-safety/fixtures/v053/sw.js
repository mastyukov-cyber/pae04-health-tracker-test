'use strict';
const CACHE='pae04-ht-stable-candidate-synthetic-schema1-cache-v053-20261114';
const FILES=['./','./index.html','./app.js','./styles.css','./manifest.webmanifest','./icons/icon.svg','./icons/apple-touch-icon.png','./icons/icon-192.png','./icons/icon-512.png'];
self.addEventListener('install',event=>{event.waitUntil(caches.open(CACHE).then(c=>c.addAll(FILES)).then(()=>self.skipWaiting()))});
self.addEventListener('activate',event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('pae04-ht-stable-candidate-synthetic-schema1-cache-')&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim()))});
self.addEventListener('fetch',event=>{const r=event.request;if(r.method!=='GET'||new URL(r.url).origin!==self.location.origin)return;event.respondWith(caches.match(r).then(cached=>cached||fetch(r)))});
