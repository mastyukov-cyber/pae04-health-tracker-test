/** PAE-04 CP-MED01: name suggestions only, no medical equivalence inference. */
export function normalizeName(input) {
  return String(input ?? '').normalize('NFKC').toLocaleLowerCase('ru-RU')
    .replace(/ё/g,'е').replace(/[‐‑–—−]/g,'-')
    .replace(/[^\p{L}\p{N}]+/gu,' ').trim().replace(/\s+/g,' ');
}

/** Restricted Damerau-Levenshtein: nearby substitutions, insertions and transpositions. */
export function editDistance(a,b) {
  a = [...normalizeName(a).replaceAll(' ','')];
  b = [...normalizeName(b).replaceAll(' ','')];
  let prev2=null, prev=Array.from({length:b.length+1},(_,i)=>i);
  for(let i=1;i<=a.length;i++) {
    const curr=[i];
    for(let j=1;j<=b.length;j++) {
      let cost=a[i-1]===b[j-1]?0:1;
      let d=Math.min(prev[j]+1,curr[j-1]+1,prev[j-1]+cost);
      if(prev2 && i>1 && j>1 && a[i-1]===b[j-2] && a[i-2]===b[j-1])
        d=Math.min(d,prev2[j-2]+1);
      curr.push(d);
    }
    prev2=prev;prev=curr;
  }
  return prev[b.length];
}

function normalizeStrength(m) {
  const value=m.strength;
  return value===undefined || value===null || value==='' ? null : String(Number(value));
}
function normalizeField(s) { return normalizeName(s??''); }
/** Comparing identity needs product strength and dosage form, not only INN or brand. */
export function assessDuplicate(draft, existing) {
  const matches=[];
  for(const med of existing||[]) {
    if(normalizeName(med.name)!==normalizeName(draft.name)) continue;
    const sameStrength=normalizeStrength(med)===normalizeStrength(draft) && normalizeField(med.unit)===normalizeField(draft.unit);
    const sameForm=normalizeField(med.form)===normalizeField(draft.form);
    const sameKind=med.kind===draft.kind;
    const complete=normalizeStrength(med)!==null && normalizeStrength(draft)!==null && !!normalizeField(med.unit) && !!normalizeField(draft.unit) && !!normalizeField(med.form) && !!normalizeField(draft.form);
    let status;
    if(sameStrength && sameForm && sameKind && complete) status='possible_duplicate';
    else if(!complete) status='needs_review';
    else if(!sameStrength || !sameForm) status='different_product';
    else status='different_regimen';
    matches.push({id:med.id,name:med.name,status});
  }
  return matches;
}

/** Catalog entries: {id, name, aliases?, ingredient?, strength?, unit?, form?}.
 * Never treats matching ingredient as interchangeable medication.
 */
export function suggestNames(query, catalog=[], existing=[], limit=5) {
  const q=normalizeName(query);
  if(q.length<3) return [];
  const combined=[...existing.map(m=>({...m,origin:'existing'})),...catalog.map(m=>({...m,origin:'catalog'}))];
  const suggestions=[];
  for(const entry of combined) {
    const name=normalizeName(entry.name);
    if(!name)continue;
    const variants=[name,...(entry.aliases||[]).map(normalizeName)].filter(Boolean);
    let best=null;
    for(const variant of variants) {
      let reason=null,rank=-1;
      if(q===variant){reason='exact';rank=100;}
      else if(q.length>=4 && variant.startsWith(q)){reason='prefix';rank=75-Math.min(10,variant.length-q.length);}
      else if(q.length>=5 && variant.length>=5){
        const d=editDistance(q,variant);
        const threshold=Math.max(q.length,variant.length)>=7?2:1;
        if(d<=threshold){reason='similar';rank=60-d*10-Math.abs(q.length-variant.length);}
      }
      if(reason && (!best || rank>best.rank))best={reason,rank};
    }
    if(best)suggestions.push({id:entry.id,name:entry.name,origin:entry.origin,reason:best.reason,rank:best.rank,
      ingredient:entry.ingredient??null,strength:entry.strength??null,unit:entry.unit??'',form:entry.form??''});
  }
  // Prefer exact/existing results; never silently merge or select.
  suggestions.sort((a,b)=>b.rank-a.rank || (Number(a.origin!=='existing')-Number(b.origin!=='existing')) || a.name.localeCompare(b.name,'ru') || a.id.localeCompare(b.id,'ru'));
  return suggestions.filter((item,i,list)=>list.findIndex(other=>other.id===item.id&&other.origin===item.origin)===i).slice(0,Math.max(0,limit));
}
