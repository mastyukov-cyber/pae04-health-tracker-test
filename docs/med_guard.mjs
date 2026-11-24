/** PAE-04 CP-MED02. Browser-only suggestion and duplicate guard. No persistence. */
import {normalizeName, suggestNames, assessDuplicate} from './med_matcher.mjs';
export const SYNTHETIC_CATALOG = Object.freeze([{"id":"product-edarbi-20","name":"Эдарби","aliases":["Эдарби®"],"ingredient":"азилсартана медоксомил","strength":20,"unit":"мг","form":"таблетки"},{"id":"product-espiro-25","name":"Эспиро","aliases":["Эспиро®"],"ingredient":"эплеренон","strength":25,"unit":"мг","form":"таблетки"},{"id":"product-liprimar-10","name":"Липримар","aliases":["Липримар®"],"ingredient":"аторвастатин","strength":10,"unit":"мг","form":"таблетки"},{"id":"product-betaloc-zok-25","name":"Беталок ЗОК","aliases":["Беталок® ЗОК"],"ingredient":"метопролол","strength":25,"unit":"мг","form":"таблетки"},{"id":"product-capoten-25","name":"Капотен","aliases":["Капотен®"],"ingredient":"каптоприл","strength":25,"unit":"мг","form":"таблетки"},{"id":"supplement-hemohim","name":"Atomy HemoHIM","aliases":["ХемоХИМ","HemoHIM"],"ingredient":"растительные экстракты","strength":null,"unit":"","form":"пакетики 20 мл"},{"id":"supplement-ginseng","name":"Atomy Korean Red Ginseng Jelly","aliases":["Korean Red Ginseng Jelly"],"ingredient":"красный женьшень","strength":null,"unit":"","form":"желе в саше"},{"id":"supplement-turmacin","name":"Atomy Turmacin MSM","aliases":["Turmacin MSM"],"ingredient":"MSM и селен","strength":null,"unit":"","form":"таблетки"},{"id":"supplement-omega3","name":"Atomy rTG Omega-3","aliases":["rTG Omega-3"],"ingredient":"EPA и DHA","strength":null,"unit":"","form":"капсулы"},{"id":"supplement-probiotics","name":"Atomy Probiotics 10+","aliases":["Probiotics 10+"],"ingredient":"пробиотические культуры","strength":null,"unit":"","form":"саше"}]);
export function existingProduct(m){
  const ext=m.pae04v021||{};
  return {id:m.id,name:m.name,kind:m.kind,strength:ext.strength??null,unit:ext.unit??'',form:ext.form??''};
}
export function medDraft(form){
  const raw=form.querySelector('#med-strength')?.value?.trim()||'';
  return {name:form.querySelector('#med-name')?.value?.trim()||'',kind:form.querySelector('#med-kind')?.value||'regular',
    strength:raw?Number(raw):null,unit:form.querySelector('#med-unit')?.value||'',form:form.querySelector('#med-form-factor')?.value||''};
}
export function assessEntry(draft,catalog=SYNTHETIC_CATALOG,existing=[]){
  const q=normalizeName(draft.name);
  if(!q)return {type:'block',message:'Введите название препарата.',suggestions:[]};
  const known=existing.map(existingProduct);
  const duplicates=assessDuplicate(draft,known);
  if(duplicates.some(d=>['possible_duplicate','needs_review'].includes(d.status))){
    return {type:'block',message:'Похожая карточка уже сохранена. Проверьте её в списке лекарств, прежде чем создавать новую.',suggestions:[]};
  }
  const warnings=duplicates.filter(d=>['different_product','different_regimen'].includes(d.status));
  const matches=suggestNames(draft.name,catalog,known,5);
  const exactCatalog=catalog.some(m=>normalizeName(m.name)===q);
  const exactExisting=known.some(m=>normalizeName(m.name)===q);
  if(matches.some(x=>x.reason!=='exact')&&!exactCatalog&&!exactExisting){
    return {type:'pick',message:'Название похоже на другое. Проверьте подсказки перед сохранением.',suggestions:matches};
  }
  if(warnings.length){
    return {type:'confirm',message:'Такое название уже встречается, но форма, дозировка или режим отличаются. Убедитесь, что это отдельная карточка.',suggestions:[]};
  }
  if(exactCatalog||exactExisting){return {type:'allow',message:'Название распознано. Оно не будет заменено автоматически.',suggestions:[]};}
  return {type:'confirm',message:'Название отсутствует в локальном справочнике. Проверьте написание. Сохранение вручную требует подтверждения.',suggestions:[]};
}

/** CP-MED03: read and insert under one IndexedDB readwrite transaction.
 * In separate tabs, transactions for the same object store are serialized by IndexedDB.
 * This protects against a duplicated save that bypasses a stale in-memory snapshot.
 * Does NOT merge records or determine medical interchangeability.
 */
export function saveMedicationAtomic(db, record, verifyAfterWrite){
  if(!db || typeof db.transaction!=='function' || typeof verifyAfterWrite!=='function')
    return Promise.reject(new Error('Хранилище или проверка сохранения недоступны'));
  return new Promise((resolve,reject)=>{
    let tx;
    let failure='Сохранение препарата прервано';
    try {
      tx=db.transaction(['medications'],'readwrite');
      const store=tx.objectStore('medications');
      const request=store.getAll();
      request.onsuccess=()=>{
        try{
          const existing=request.result;
          if(!Array.isArray(existing)) throw Error('Не удалось прочитать список препаратов');
          const decision=assessEntry(existingProduct(record),[],existing);
          if(decision.type==='block'||decision.type==='pick'){
            failure=decision.type==='pick'?'Появилась похожая карточка. Проверьте название и повторите подтверждение.':'Похожий препарат уже существует. Проверьте карточку в списке лекарств.';
            tx.abort();
            return;
          }
          store.add(record);
        }catch(err){
          failure=err instanceof Error?err.message:String(err);
          try{tx.abort();}catch{}
        }
      };
      request.onerror=()=>{failure='Не удалось проверить существующие препараты';try{tx.abort();}catch{}};
      tx.onabort=()=>reject(new Error(failure));
      tx.oncomplete=()=>Promise.resolve().then(()=>verifyAfterWrite('medications',record)).then(resolve,reject);
    }catch(err){reject(err);}
  });
}

function element(tag,cls,text){const el=document.createElement(tag);if(cls)el.className=cls;if(text!==undefined)el.textContent=text;return el;}
export function mount({form,nameInput,getExisting, catalog=SYNTHETIC_CATALOG}){
  if(!form||!nameInput||typeof getExisting!=='function')throw Error('CP-MED02: missing form/input/data reader');
  if(form.dataset.pae04MedGuard==='mounted')return;
  form.dataset.pae04MedGuard='mounted';
  const container=element('div','med-guard-panel');container.id='med-guard-panel';
  container.setAttribute('role','status');container.setAttribute('aria-live','polite');
  nameInput.closest('label')?.insertAdjacentElement('afterend',container);
  nameInput.setAttribute('aria-describedby',container.id);
  let approval=null;
  const draft=()=>medDraft(form);
  const fingerprint=()=>JSON.stringify(draft());
  function draw(){
    const d=draft();const decision=assessEntry(d,catalog,getExisting());
    container.replaceChildren();
    if(!d.name)return decision;
    const msg=element('p','med-guard-message',decision.message);container.append(msg);
    if(decision.type==='block')container.classList.add('is-blocked');else container.classList.remove('is-blocked');
    if(decision.type==='pick'){
      for(const suggestion of decision.suggestions){
        const btn=element('button','med-guard-option',suggestion.name+(suggestion.origin==='existing'?' · уже в списке':''));
        btn.type='button';btn.addEventListener('click',()=>{nameInput.value=suggestion.name;approval=null;nameInput.dispatchEvent(new Event('input',{bubbles:true}));nameInput.focus();});
        container.append(btn);
      }
    }
    if(decision.type==='confirm'){
      const btn=element('button','med-guard-confirm','Проверил(а), сохранить вручную');btn.type='button';
      btn.addEventListener('click',()=>{
        if(assessEntry(draft(),catalog,getExisting()).type!=='confirm')return;
        approval=fingerprint();form.requestSubmit();
      });container.append(btn);
    }
    return decision;
  }
  form.addEventListener('input',()=>{approval=null;draw();});
  form.addEventListener('change',event=>{
    // A text input emits change on blur BEFORE the clicked suggestion button receives click.
    // Replacing buttons at that moment discards the intended click; input already redraws live.
    if(event.target===nameInput)return;
    approval=null;draw();
  });
  form.addEventListener('submit',event=>{
    const decision=assessEntry(draft(),catalog,getExisting());
    if(decision.type==='allow')return;
    if(decision.type==='confirm'&&approval===fingerprint()){approval=null;return;}
    event.preventDefault();event.stopImmediatePropagation();draw();
  },true);
  draw();
}
if(typeof window!=='undefined')window.PAE04MedicationGuard={mount,saveMedicationAtomic};
