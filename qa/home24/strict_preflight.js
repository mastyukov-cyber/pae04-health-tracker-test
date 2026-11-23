/* PAE-04 HOME-23 — SYNTHETIC-only pre-parse fail-closed browser module.
 * Standalone asset: NO storage, network, DOM, migration, import, or writes.
 */
(function (root) {
  'use strict';
  const LIMIT = 5 * 1024 * 1024;
  const MAX_DEPTH = 64;
  const MAX_VALUES = 200000;
  const STORES = Object.freeze(['pressures', 'medications', 'intakes', 'intakeEvents']);
  const ALLOW = Object.freeze({
    envelope: ['format', 'version', 'exportedAt', 'data', 'sha256'],
    data: STORES,
    pressure: ['id','systolic','diastolic','pulse','dateTime','note','arm','createdAt'],
    medication: ['id','name','dose','kind','from','to','createdAt','pae04v021'],
    extension: ['strength','unit','form'],
    intake: ['id','medId','date','markedAt','takenAtLocal','updatedAt','status','cancelledAt'],
    intakeEvent: ['id','intakeId','medId','action','at','oldTakenAtLocal','newTakenAtLocal']
  });
  function reject(code, detail='') { throw new Error(code + (detail ? ':' + String(detail).slice(0,160) : '')); }
  function plain(v) { return v !== null && typeof v === 'object' && !Array.isArray(v); }
  function keys(v, allowed, label) {
    if (!plain(v)) reject('INVALID_OBJECT',label);
    for (const k of Object.keys(v)) if (!allowed.includes(k)) reject('UNKNOWN_FIELD',label+'.'+k);
  }
  function requireKeys(v, required, label) { for (const k of required) if (!Object.hasOwn(v,k)) reject('MISSING_FIELD',label+'.'+k); }
  function checkNoDuplicateKeys(raw) {
    if (typeof raw !== 'string') reject('INVALID_RAW_TYPE');
    // TextEncoder is available in supported modern Safari/iPhone/WebKit and Node 22.
    if (new TextEncoder().encode(raw).byteLength > LIMIT) reject('OVERSIZE_JSON');
    let i = 0, values = 0;
    function whitespace() { while (i < raw.length && /[ \n\t\r]/.test(raw[i])) i++; }
    function str() {
      if (raw[i] !== '"') reject('INVALID_JSON_STRING');
      const start = i++;
      let complete = false;
      while (i < raw.length) {
        const c = raw[i++];
        if (c === '\\') { i++; continue; }
        if (c === '"') { complete = true; break; }
      }
      if (!complete) reject('UNTERMINATED_JSON_STRING');
      return JSON.parse(raw.slice(start,i)); // decodes escaped/Unicode-equivalent key names
    }
    function val(depth, path) {
      if (++values > MAX_VALUES) reject('JSON_COMPLEXITY_LIMIT');
      if (depth > MAX_DEPTH) reject('JSON_DEPTH_LIMIT');
      whitespace();
      if (raw[i] === '{') {
        i++; whitespace(); const seen = new Set();
        if (raw[i] === '}') { i++; return; }
        for (;;) {
          whitespace(); const k = str();
          if (seen.has(k)) reject('DUPLICATE_JSON_KEY',path+'.'+k);
          seen.add(k); whitespace();
          if (raw[i++] !== ':') reject('INVALID_JSON_COLON');
          val(depth+1,path+'.'+k); whitespace();
          if (raw[i] === '}') { i++; return; }
          if (raw[i++] !== ',') reject('INVALID_JSON_COMMA');
        }
      }
      if (raw[i] === '[') {
        i++; whitespace();
        if (raw[i] === ']') { i++; return; }
        let n=0;
        for (;;) {
          val(depth+1,path+'['+(n++)+']'); whitespace();
          if (raw[i] === ']') { i++; return; }
          if (raw[i++] !== ',') reject('INVALID_ARRAY_COMMA');
        }
      }
      if (raw[i] === '"') { str(); return; }
      // Strict JSON.parse after this scan checks exact primitive/number grammar.
      const start=i;
      while (i<raw.length && !/[\s,}\]]/.test(raw[i])) i++;
      if (i===start) reject('INVALID_JSON_VALUE');
    }
    whitespace(); val(0,'$'); whitespace();
    if (i !== raw.length) reject('TRAILING_JSON_CONTENT');
  }
  function parseChecked(raw) {
    checkNoDuplicateKeys(raw);
    const env = JSON.parse(raw);
    keys(env, ALLOW.envelope, 'envelope');
    requireKeys(env, ALLOW.envelope, 'envelope');
    if (!Number.isInteger(env.version) || ![1,2,3].includes(env.version)) reject('INVALID_VERSION');
    if (env.format !== 'pae04.healthtracker.synthetic-backup') reject('INVALID_FORMAT');
    const dataKeys = env.version === 3 ? STORES : STORES.slice(0,3);
    keys(env.data,dataKeys,'data'); requireKeys(env.data,dataKeys,'data');
    const typeMap = {pressures:'pressure',medications:'medication',intakes:'intake',intakeEvents:'intakeEvent'};
    for (const name of dataKeys) {
      if (!Array.isArray(env.data[name])) reject('INVALID_STORE',name);
      if (env.data[name].length > 25000) reject('STORE_LIMIT',name);
      for (let j=0; j<env.data[name].length; j++) {
        const v=env.data[name][j], label=name+'['+j+']';
        keys(v,ALLOW[typeMap[name]],label);
        if (name==='medications' && Object.hasOwn(v,'pae04v021')) keys(v.pae04v021,ALLOW.extension,label+'.pae04v021');
      }
    }
    // All cryptographic, semantic, relational, historical and rollback checks
    // must still be done by the original app after this PRE-PARSE GATE.
    return env;
  }
  const api=Object.freeze({parseChecked,checkNoDuplicateKeys,ALLOW,STORES,MAX_DEPTH,LIMIT});
  root.PAE04StrictBackup=api;
  if (typeof module !== 'undefined' && module.exports) module.exports=api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
