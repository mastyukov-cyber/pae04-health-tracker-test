'use strict';
/* CP-REAL01: optional user-initiated profile seed. NO writes at boot. */
(function(){
  if(typeof PAE04_V021_TEST_ONLY!=='boolean'||!PAE04_V021_TEST_ONLY)throw Error('PERSONAL_PREVIEW_ONLY');
  const id='pae04-personal-seed-btn';
  let busy=false,profile=null;
  const element=(tag,value)=>{const e=document.createElement(tag);if(value!==undefined)e.textContent=value;return e};
  const readAll=names=>new Promise((resolve,reject)=>{
    if(typeof db==='undefined'||!db)return reject(Error('Локальная база ещё не открыта'));
    let tx;try{tx=db.transaction(names,'readonly');}catch(e){return reject(e)}
    const res={};
    for(const name of names) {
      const req=tx.objectStore(name).getAll();
      req.onsuccess=()=>{res[name]=req.result};
    }
    tx.oncomplete=()=>resolve(res);
    tx.onabort=()=>reject(tx.error||Error('Не удалось проверить локальные записи'));
  });
  function checkProfile(p){
    if(!p||p.schema!=='PAE04_PERSONAL_QA_PROFILE_V1'||p.purpose!=='PERSONAL_TEST_ONLY'||
       !Array.isArray(p.medicines)||p.medicines.length!==10||
       p.constraints?.seed_intakes!==false||p.constraints?.seed_pressures!==false)
      throw Error('Неожиданный формат персонального профиля');
    const keys=new Set(),names=new Set();
    for(const m of p.medicines){
      if(typeof m.name!=='string'||m.name.length<2||m.name.length>100||
         typeof m.dose!=='string'||m.dose.length>60||
         !['regular','course','asNeeded'].includes(m.kind)||
         keys.has(m.key)||names.has(m.name.toLocaleLowerCase('ru')))
        throw Error('Ошибочный состав персонального справочника');
      keys.add(m.key);names.add(m.name.toLocaleLowerCase('ru'));
    }
    return p;
  }
  function seedRecords(items){
    return new Promise((resolve,reject)=>{
      const stores=['pressures','medications','intakes','intakeEvents'];
      let tx;try{tx=db.transaction(stores,'readwrite');}catch(err){return reject(err)}
      let problem='Профиль не был загружен',remaining=stores.length,counts={},written=false;
      const abort=(msg)=>{problem=msg;try{tx.abort()}catch(_){}};
      tx.onabort=()=>reject(Error(problem));
      tx.onerror=()=>{};
      tx.oncomplete=()=>{if(written)resolve();else reject(Error('Запись не была подтверждена'))};
      for(const store of stores){
        const req=tx.objectStore(store).count();
        req.onsuccess=()=>{
          counts[store]=req.result;
          if(--remaining!==0)return;
          if(stores.some(name=>counts[name]!==0)){
            abort('В тестовой базе уже есть данные. Существующие карточки не изменены. Откройте чистый предпросмотр.');
            return;
          }
          try{
            for(const med of items)tx.objectStore('medications').add(med);
            written=true;
          }catch(err){abort(String(err))}
        };
        req.onerror=()=>abort('Не удалось проверить пустую базу');
      }
    });
  }
  function toRecord(m,now){
    const dose=m.category==='supplement'?'БАД · '+m.dose:m.dose;
    const record={id:crypto.randomUUID(),name:m.name,dose,kind:m.kind,
      from:m.from??null,to:m.to??null,createdAt:now};
    // Personal intake is not product strength, e.g. Betaloc ZOK 12.5 mg can
    // differ from physical tablet strength 25 mg. Do NOT infer a pill fraction.
    if(m.category==='medicine'&&m.product_strength_mg!==null&&m.product_strength_mg!==undefined)
      record.pae04v021={strength:m.product_strength_mg,unit:'мг',
        form:['таблетки','капсулы','капли','раствор','другое'].includes(m.form)?m.form:'другое'};
    validateMed(record);
    return record;
  }
  async function seed(event){
    const button=event.currentTarget;
    if(busy)return;
    if(!profile){showMessage('Справочник не загружен. Дождитесь проверки.', 'error');return}
    const names=['pressures','medications','intakes','intakeEvents'];
    try{
      const existing=await readAll(names);
      if(names.some(n=>existing[n].length!==0)){
        showMessage('Профиль можно загрузить только в полностью пустую отдельную тестовую базу. Ничего не изменено.','error');
        return;
      }
      if(!window.confirm('Добавить 10 карточек с твоими названиями и дозировками? Приёмы и давление останутся пустыми. Продолжить?'))return;
      busy=true;button.disabled=true;button.textContent='Проверяю и добавляю…';
      const now=new Date().toISOString(), records=profile.medicines.map(m=>toRecord(m,now));
      await seedRecords(records);
      const verify=await readAll(names);
      if(verify.medications.length!==10||verify.intakes.length||verify.intakeEvents.length||verify.pressures.length)
        throw Error('Повторная проверка после сохранения не прошла; проверьте журнал');
      if(typeof safetyNeedsNewCheck==='function')safetyNeedsNewCheck();
      await reload();
      showMessage('Добавлено 10 карточек. Записей о приёме и давлении нет. Проверьте дозировки перед использованием.','ok');
      button.textContent='Карточки загружены';
    }catch(err){
      showMessage('Персональный профиль не сохранён: '+(err?.message??String(err)),'error');
      button.disabled=false;button.textContent='Загрузить мои препараты';
    }finally{busy=false}
  }
  async function mount(){
    const form=document.getElementById('med-form');
    if(!form||document.getElementById(id))return;
    const panel=element('section');panel.className='pae04-profile-panel';
    panel.setAttribute('aria-label','Персональный тестовый справочник');
    const title=element('strong','Мои препараты · персональный предпросмотр');
    const note=element('p','10 настоящих названий с дозировками, включая препараты и БАДы. Приёмы и давление не загружаются.');
    const button=element('button','Проверяю справочник…');
    button.id=id;button.type='button';button.disabled=true;
    const status=element('p','Сохранение возможно только в пустой тестовой базе; существующие записи никогда не перезаписываются.');
    button.addEventListener('click',seed);
    panel.append(title,note,button,status);
    form.parentElement.insertBefore(panel,form);
    try{
      const response=await fetch('./personal_profile.json',{cache:'no-cache'});
      if(!response.ok)throw Error('Не удалось загрузить персональный справочник');
      profile=checkProfile(await response.json());
      button.textContent='Загрузить мои препараты';
      button.disabled=false;
    }catch(err){
      status.textContent='Справочник недоступен. Сохранение карточек заблокировано.';
      button.textContent='Справочник недоступен';
      showMessage('Персональный справочник: '+(err?.message??String(err)),'error');
    }
  }
  document.addEventListener('DOMContentLoaded',mount);
  window.PAE04PersonalPreview={getNameCount:()=>profile?.medicines.length??0};
})();