'use strict';
// PAE-04 PWA v05 SAFE UX. Synthetic records only; no external endpoints, no schema changes.
// Build-independent name. TEST-only; future synthetic v05+ must keep this ID unchanged.
const DB_NAME='PAE04_HT_STABLE_CANDIDATE_INTEGRATION_SYNTHETIC_SCHEMA1';
const DB_VERSION=1;
const STORE_NAMES=['pressures','medications','intakes','intakeEvents'];
const BACKUP_FORMAT='pae04.healthtracker.synthetic-backup';
const BACKUP_VERSION=3; // v1/v2 imports normalized; new exports always v3
const KINDS={regular:'Постоянный',course:'Курсовой',asNeeded:'Ситуативный'};
const PAE04_V021_TEST_ONLY=true;
const MED_UNITS=['мг','мкг','мл','г','ЕД'];
const MED_FORMS=['таблетки','капсулы','капли','раствор','другое'];
// Structured strength is PRODUCT STRENGTH, not instruction for intake.
// Never infer it from historical free-text dose.
function validatedMedExtension(m){
  if(m.pae04v021===undefined)return null;
  const e=m.pae04v021;
  if(!e||typeof e!=='object'||Array.isArray(e)||Object.keys(e).some(k=>!['strength','unit','form'].includes(k)))throw Error('Некорректные структурированные поля препарата');
  const strength=e.strength??null,unit=e.unit??'',form=e.form??'';
  if(strength!==null&&(!(typeof strength==='number'&&Number.isFinite(strength))||strength<=0||strength>100000))throw Error('Некорректная дозировка');
  if(strength===null?unit!=='':!MED_UNITS.includes(unit))throw Error('Укажите единицу дозировки');
  if(form!==''&&!MED_FORMS.includes(form))throw Error('Некорректная форма препарата');
  return {strength,unit,form};
}
function medDescription(m){
  const e=validatedMedExtension(m);
  const label=e?.strength!==null&&e!==null?`${e.strength} ${e.unit}`:(m.dose||'Дозировка не указана');
  const form=e?.form||'Форма не указана';
  return `${label} · ${form}`;
}

let db=null;
let snapshot={pressures:[],medications:[],intakes:[],intakeEvents:[]};
let pendingImport=null;
let importPreviewSequence=0;
// A backup must be downloaded and explicitly acknowledged for each import preview.
const $=id=>document.getElementById(id);
const today=()=>dateLocal(new Date());
const dateLocal=d=>`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
const dateTimeLocal=d=>`${dateLocal(d)}T${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
const clockLocal=d=>`${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
const dateHuman=day=>validDate(day)?new Intl.DateTimeFormat('ru-RU',{day:'2-digit',month:'2-digit',year:'numeric'}).format(new Date(`${day}T12:00:00`)):day;
const takenTime=i=>i.takenAtLocal?i.takenAtLocal.slice(11,16):null;
const intakeLabel=i=>`${dateHuman(i.date)} · ${takenTime(i)||'время приёма не указано'}`;

const node=(name,cls,txt)=>{const n=document.createElement(name);if(cls)n.className=cls;if(txt!==undefined)n.textContent=txt;return n};
function showMessage(message,level='ok'){const holder=$('messages');holder.replaceChildren(node('div',`message ${level}`,message));}
function toError(e){return e instanceof Error?e.message:String(e)}

// PAE-04 v05.4 — local-only accessible scrolling day/month/year picker.
// The original ISO date and datetime inputs remain the source of truth for
// persistence and exports. Opening, scrolling and cancelling do NOT write data.
const WHEEL_MONTHS=['Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь'];
const WHEEL_TARGETS=['pressure-datetime','intake-date','course-from','course-to'];
const WHEEL_YEARS=Array.from({length:201},(_,i)=>1900+i);
const WHEEL_ROW_PX=48;
let wheelSession=null;
let wheelReturnFocus=null;
const wheelPad=n=>String(n).padStart(2,'0');
const wheelYearMonthDays=(y,m)=>new Date(y,m,0).getDate();
function wheelDisplayDate(date){
  if(!validDate(date))return'Не указана';
  const [y,m,d]=date.split('-').map(Number);
  return d+' '+WHEEL_MONTHS[m-1].toLocaleLowerCase('ru')+' '+y;
}
function updateWheelTrigger(id){
  const source=$(id),label=document.querySelector('[data-wheel-label="'+id+'"]');
  if(!source||!label)return;
  const value=source.value;
  label.textContent=id==='pressure-datetime'&&validDateTime(value)
    ?wheelDisplayDate(value.slice(0,10))+' · '+value.slice(11,16)
    :wheelDisplayDate(value);
}
function updateAllWheelTriggers(){for(const id of WHEEL_TARGETS)updateWheelTrigger(id);}
function wheelValues(which){
  if(which==='day')return Array.from({length:wheelYearMonthDays(wheelSession.year,wheelSession.month)},(_,i)=>i+1);
  if(which==='month')return Array.from({length:12},(_,i)=>i+1);
  return WHEEL_YEARS;
}
function wheelSelected(which){return wheelSession[which];}
function wheelHighlight(which){
  const scroller=$('wheel-'+which),selection=wheelSelected(which);
  for(const option of scroller.children){
    const match=Number(option.dataset.value)===selection;
    option.setAttribute('aria-selected',match?'true':'false');
    option.tabIndex=-1;
  }
}
function wheelUpdatePreview(){
  if(!wheelSession)return;
  const s=wheelSession;
  const stamp=String(s.year).padStart(4,'0')+'-'+wheelPad(s.month)+'-'+wheelPad(s.day);
  $('wheel-preview').textContent=wheelDisplayDate(stamp)+(s.id==='pressure-datetime'?' · '+$('wheel-time').value:'');
}
function wheelMakeColumn(which){
  const scroll=$('wheel-'+which),vals=wheelValues(which),frag=document.createDocumentFragment();
  scroll.replaceChildren();scroll.dataset.kind=which;
  for(const val of vals){
    const option=node('button','wheel-option',which==='month'?WHEEL_MONTHS[val-1]:String(val));
    option.type='button';option.dataset.value=String(val);option.setAttribute('role','option');
    option.addEventListener('click',()=>wheelChoose(which,val,true));
    frag.append(option);
  }
  scroll.append(frag);wheelHighlight(which);
  const index=vals.indexOf(wheelSelected(which));
  requestAnimationFrame(()=>{
    if(!wheelSession||!$('wheel-modal').contains(scroll))return;
    scroll.scrollTop=Math.max(0,index)*WHEEL_ROW_PX;
  });
}
function wheelChoose(which,val,scrollTo=false){
  if(!wheelSession)return;
  const vals=wheelValues(which);
  if(!vals.includes(val))return;
  const different=wheelSession[which]!==val;
  wheelSession[which]=val;
  if(different&&(which==='month'||which==='year')){
    wheelSession.day=Math.min(wheelSession.day,wheelYearMonthDays(wheelSession.year,wheelSession.month));
    wheelMakeColumn('day');
  }
  wheelHighlight(which);wheelUpdatePreview();
  if(scrollTo){
    $('wheel-'+which).scrollTo({top:vals.indexOf(val)*WHEEL_ROW_PX,behavior:'smooth'});
  }
}
function wheelReadScroll(which){
  if(!wheelSession)return;
  const scroll=$('wheel-'+which),vals=wheelValues(which);
  const index=Math.max(0,Math.min(vals.length-1,Math.round(scroll.scrollTop/WHEEL_ROW_PX)));
  wheelChoose(which,vals[index],false);
}
function closeWheelPicker(){
  const modal=$('wheel-modal');
  if(modal.hidden)return;
  modal.hidden=true;document.body.classList.remove('wheel-modal-open');
  if(wheelSession){
    for(const key of ['day','month','year'])clearTimeout(wheelSession['timer_'+key]);
  }
  wheelSession=null;
  if(wheelReturnFocus?.isConnected)wheelReturnFocus.focus({preventScroll:true});
  wheelReturnFocus=null;
}
function openWheelPicker(id){
  if(!WHEEL_TARGETS.includes(id))return;
  const source=$(id),timeMode=id==='pressure-datetime';
  wheelReturnFocus=document.querySelector('[data-wheel-target="'+id+'"]');
  const value=source.value,rawDay=value.slice(0,10),basis=validDate(rawDay)?rawDay:today();
  const [year,month,day]=basis.split('-').map(Number);
  if(year<1900||year>2100){showMessage('Для прокрутки доступны годы с 1900 по 2100.','warn');return;}
  wheelSession={id,year,month,day};
  $('wheel-title').textContent=id==='pressure-datetime'?'Дата и время':id==='intake-date'?'Дата приёма':id==='course-from'?'Начало курса':'Окончание курса';
  $('wheel-time-row').hidden=!timeMode;
  $('wheel-time').value=timeMode&&validDateTime(value)?value.slice(11,16):clockLocal(new Date());
  $('wheel-clear').hidden=!['course-from','course-to'].includes(id);
  $('wheel-modal').hidden=false;document.body.classList.add('wheel-modal-open');
  for(const key of ['day','month','year'])wheelMakeColumn(key);
  wheelUpdatePreview();
  $('wheel-day').focus({preventScroll:true});
}
function commitWheelDate(clear=false){
  const session=wheelSession;if(!session)return;
  const source=$(session.id);
  let next='';
  if(!clear){
    const date=String(session.year).padStart(4,'0')+'-'+wheelPad(session.month)+'-'+wheelPad(session.day);
    if(!validDate(date)){showMessage('Выбрана некорректная дата.','error');return;}
    if(session.id==='pressure-datetime'){
      const time=$('wheel-time').value;
      if(!validClock(time)){showMessage('Укажите часы и минуты.','error');return;}
      next=date+'T'+time;
      if(!validDateTime(next)){showMessage('Укажите корректные дату и время.','error');return;}
    }else next=date;
  }
  if(source.value!==next){
    source.value=next;
    source.dispatchEvent(new Event('input',{bubbles:true}));
    source.dispatchEvent(new Event('change',{bubbles:true}));
  }
  updateWheelTrigger(session.id);closeWheelPicker();
}
function setupWheelPicker(){
  for(const id of WHEEL_TARGETS){
    const target=document.querySelector('[data-wheel-target="'+id+'"]');
    if(!target||!$(id))throw Error('Отсутствует элемент выбора даты: '+id);
    target.addEventListener('click',()=>openWheelPicker(id));
    $(id).addEventListener('input',()=>updateWheelTrigger(id));
    $(id).addEventListener('change',()=>updateWheelTrigger(id));
  }
  for(const key of ['day','month','year']){
    const scroller=$('wheel-'+key);
    scroller.addEventListener('scroll',()=>{
      if(!wheelSession)return;
      clearTimeout(wheelSession['timer_'+key]);
      const current=wheelSession;
      current['timer_'+key]=setTimeout(()=>{
        if(wheelSession===current)wheelReadScroll(key);
      },105);
    },{passive:true});
    scroller.addEventListener('keydown',event=>{
      if(!wheelSession)return;
      const vals=wheelValues(key),current=wheelSelected(key);
      let next=current;
      if(event.key==='ArrowDown')next=vals[Math.min(vals.length-1,vals.indexOf(current)+1)];
      else if(event.key==='ArrowUp')next=vals[Math.max(0,vals.indexOf(current)-1)];
      else if(event.key==='Home')next=vals[0];
      else if(event.key==='End')next=vals[vals.length-1];
      else return;
      event.preventDefault();wheelChoose(key,next,true);
    });
  }
  $('wheel-cancel').addEventListener('click',closeWheelPicker);
  $('wheel-apply').addEventListener('click',()=>commitWheelDate(false));
  $('wheel-clear').addEventListener('click',()=>commitWheelDate(true));
  $('wheel-time').addEventListener('input',wheelUpdatePreview);
  $('wheel-modal').addEventListener('click',e=>{if(e.target===$('wheel-modal'))closeWheelPicker();});
  document.addEventListener('keydown',e=>{
    if(!$('wheel-modal').hidden&&e.key==='Escape'){e.preventDefault();closeWheelPicker();}
    if($('wheel-modal').hidden||e.key!=='Tab')return;
    const focusable=[...$('wheel-modal').querySelectorAll('button:not([hidden]),input:not([hidden]),[tabindex="0"]')]
      .filter(el=>!el.closest('[hidden]')&&el.getClientRects().length>0);
    if(!focusable.length)return;
    const first=focusable[0],last=focusable[focusable.length-1];
    if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}
    if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}
  });
  updateAllWheelTriggers();
}

function openDB(){return new Promise((resolve,reject)=>{
  if(!('indexedDB' in window))return reject(new Error('IndexedDB недоступна'));
  const req=indexedDB.open(DB_NAME,DB_VERSION);
  req.onupgradeneeded=()=>{
    const d=req.result;
    for(const name of STORE_NAMES){
      if(d.objectStoreNames.contains(name))continue;
      const store=d.createObjectStore(name,{keyPath:'id'});
      if(name==='intakes')store.createIndex('byMedDay',['medId','date'],{unique:false});
      if(name==='intakeEvents')store.createIndex('byIntakeId','intakeId',{unique:false});
    }
  };
  req.onsuccess=()=>resolve(req.result);
  req.onerror=()=>reject(req.error||new Error('Ошибка IndexedDB'));
  req.onblocked=()=>reject(new Error('База занята другой вкладкой'));
});}
function getAll(store){return new Promise((resolve,reject)=>{const tx=db.transaction([store],'readonly');const req=tx.objectStore(store).getAll();req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error||new Error('Ошибка чтения'));});}
function addRecord(store,record){return new Promise((resolve,reject)=>{const tx=db.transaction([store],'readwrite');tx.objectStore(store).add(record);tx.oncomplete=()=>resolve();tx.onabort=()=>reject(tx.error||new Error('Ошибка сохранения'));tx.onerror=()=>{};});}
function removeRecord(store,id){return new Promise((resolve,reject)=>{const tx=db.transaction([store],'readwrite');tx.objectStore(store).delete(id);tx.oncomplete=()=>resolve();tx.onabort=()=>reject(tx.error||new Error('Ошибка удаления'));tx.onerror=()=>{};});}
// Every intake change and its audit event are committed atomically.
function changeIntake(action,record,previous=null){return new Promise((resolve,reject)=>{
  if(!['marked','time_corrected','cancelled'].includes(action))return reject(new Error('Недопустимое действие'));
  try{validateIntake(record);}catch(e){reject(e);return;}
  const tx=db.transaction(['intakes','intakeEvents'],'readwrite');
  const store=tx.objectStore('intakes'),history=tx.objectStore('intakeEvents');
  let message='Транзакция приёма прервана';
  const abort=reason=>{message=reason;try{tx.abort();}catch{}};
  tx.oncomplete=()=>resolve();
  tx.onabort=()=>reject(new Error(message));
  const query=store.getAll();
  query.onsuccess=()=>{
    const rows=query.result,match=rows.find(i=>i.id===record.id);
    if(action==='marked'){
      if(match||previous||intakeStatus(record)!=='active'||!record.takenAtLocal){abort('Некорректная новая отметка');return;}
    }else{
      if(!match||!previous||canonical(match)!==canonical(previous)||intakeStatus(previous)!=='active'){
        abort('Конфликт исходной отметки');return;
      }
      if(action==='time_corrected'&&(intakeStatus(record)!=='active'||!record.takenAtLocal||record.takenAtLocal===previous.takenAtLocal)){
        abort('Некорректное новое время');return;
      }
      if(action==='cancelled'&&(intakeStatus(record)!=='cancelled'||!record.cancelledAt)){
        abort('Некорректная отмена');return;
      }
      if(record.id!==previous.id||record.medId!==previous.medId||record.date!==previous.date||record.markedAt!==previous.markedAt){
        abort('Запрещено менять идентификатор или дату отметки');return;
      }
    }
    if(intakeStatus(record)==='active'&&record.takenAtLocal&&rows.some(i=>i.id!==record.id&&
      i.medId===record.medId&&i.takenAtLocal===record.takenAtLocal&&intakeStatus(i)==='active')){
      abort('Такой приём с этим временем уже отмечен');return;
    }
    const event={id:crypto.randomUUID(),intakeId:record.id,medId:record.medId,action,at:new Date().toISOString()};
    if(action==='marked')event.newTakenAtLocal=record.takenAtLocal;
    if(action==='time_corrected'){
      if(previous.takenAtLocal)event.oldTakenAtLocal=previous.takenAtLocal;
      event.newTakenAtLocal=record.takenAtLocal;
    }
    if(action==='cancelled'&&previous.takenAtLocal)event.oldTakenAtLocal=previous.takenAtLocal;
    try{validateIntakeEvent(event);}catch(e){abort(e.message);return;}
    if(action==='marked')store.add(record);else store.put(record);
    history.add(event);
  };
  query.onerror=()=>abort('Не удалось проверить отметки');
});}

async function reload(){const [pressures,medications,intakes,intakeEvents]=await Promise.all(STORE_NAMES.map(getAll));snapshot={pressures,medications,intakes,intakeEvents};render();}
function navigate(page){for(const el of document.querySelectorAll('.page'))el.classList.toggle('active',el.id===`page-${page}`);for(const b of document.querySelectorAll('[data-page]')){const active=b.dataset.page===page;b.classList.toggle('active',active);b.setAttribute('aria-current',active?'page':'false')}window.scrollTo({top:0,behavior:'instant'});}
function render(){const {pressures,medications,intakes}=snapshot;$('stat-pressure').textContent=String(pressures.length);$('stat-meds').textContent=String(medications.length);$('stat-intakes').textContent=String(intakes.filter(i=>intakeStatus(i)==='active').length);renderPressure();renderMedications();renderOverview();}
function dateLabel(iso){try{return new Intl.DateTimeFormat('ru-RU',{day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'}).format(new Date(iso))}catch{return iso}}
function renderPressure(){const list=$('pressure-list');list.replaceChildren();const all=[...snapshot.pressures].sort((a,b)=>b.dateTime.localeCompare(a.dateTime));const days=Number($('pressure-filter')?.value||0);const cutoff=days?dateTimeLocal(new Date(Date.now()-days*86400000)):null;const query=($('pressure-search')?.value||'').trim().toLocaleLowerCase('ru');const sorted=all.filter(p=>(!cutoff||p.dateTime>=cutoff)&&(!query||[`${p.systolic}/${p.diastolic}`,`${p.systolic} / ${p.diastolic}`,p.dateTime,dateLabel(p.dateTime),p.note||''].some(v=>v.toLocaleLowerCase('ru').includes(query))));$('pressure-count').textContent=days?`${sorted.length} из ${all.length} записей`:`${all.length} записей`;if(!sorted.length){list.append(node('p','empty',all.length?'По заданному фильтру измерений нет.':'Пока нет измерений.'));return;}for(const p of sorted){const r=node('div','history-row'),l=node('div'),h=node('div','row-number',`${p.systolic} / ${p.diastolic}`),sub=node('div','row-subtitle',`${dateLabel(p.dateTime)} · Правая рука${p.pulse===null?'':` · Пульс ${p.pulse}`}`);l.append(h,sub);if(p.note)l.append(node('div','row-subtitle',p.note));const b=node('button','tiny-button danger','Удалить');b.type='button';b.setAttribute('aria-label',`Удалить измерение ${p.systolic}/${p.diastolic}`);b.addEventListener('click',async()=>{if(!confirm('Удалить это ТЕСТОВОЕ измерение? Действие не отменяется.'))return;try{await removeRecord('pressures',p.id);await reload();showMessage('Тестовое измерение удалено.')}catch(e){showMessage(toError(e),'error')}});r.append(l,b);list.append(r);}}
function intakeStatus(i){return i.status||'active';}
function eventsForIntake(i){return snapshot.intakeEvents.filter(e=>e.intakeId===i.id)
  .sort((a,b)=>a.at.localeCompare(b.at));}
function eventLabel(e){
  if(e.action==='marked')return 'Отмечено: '+(e.newTakenAtLocal?.slice(11)||'время не указано');
  if(e.action==='time_corrected')return 'Время: '+(e.oldTakenAtLocal?.slice(11)||'неизвестно')+' → '+e.newTakenAtLocal.slice(11);
  if(e.action==='cancelled')return 'Отменено';
  return 'Событие';
}
function isFutureIntake(t){return new Date(t).getTime()>Date.now()+60000;}
function renderMedications(){
  const list=$('med-list'),day=$('intake-date').value||today();list.replaceChildren();
  const medQuery=($('med-search')?.value||'').trim().toLocaleLowerCase('ru');const meds=[...snapshot.medications].sort((a,b)=>a.name.localeCompare(b.name,'ru')).filter(m=>m.name.toLocaleLowerCase('ru').includes(medQuery));
  if(!meds.length)list.append(node('p','empty',snapshot.medications.length?'По запросу препараты не найдены.':'Препараты ещё не добавлены.'));
  for(const med of meds){
    const wrap=node('article','med-block'),row=node('div','med-row'),desc=node('div','med-details');
    const title=node('div','row-title',med.name);
    title.prepend(node('span','med-pill','💊'));
    title.append(node('span','med-type',KINDS[med.kind]));
    let sub=medDescription(med);
    if(med.kind==='course')sub+=' · '+(med.from||'…')+' – '+(med.to||'…');
    desc.append(title,node('div','row-subtitle',sub));
    const existing=snapshot.intakes.filter(i=>i.medId===med.id&&i.date===day&&intakeStatus(i)==='active');
    desc.append(node('div','row-subtitle',`За день: ${existing.length} подтверждённых приёмов`));
    row.append(desc);
    const controls=node('div','med-time-controls'),label=node('label','intake-time-label','Время нового приёма');
    const time=node('input','intake-time-input');time.type='time';time.step=60;
    time.value=day===today()?clockLocal(new Date()):'';
    time.setAttribute('aria-label',`Время нового приёма ${med.name}`);
    label.append(time);controls.append(label);
    const confirmButton=node('button','primary intake-confirm-button','✓ Подтвердить приём');
    confirmButton.type='button';
    confirmButton.setAttribute('aria-label',`Подтвердить фактический приём ${med.name}`);
    controls.append(confirmButton);
    let submitting=false;
    confirmButton.addEventListener('click',async()=>{
      if(submitting)return; // Prevent double taps while an IndexedDB write is pending.
      submitting=true;
      confirmButton.disabled=true;
      confirmButton.textContent='Сохранение…';
      try{
        if(!validClock(time.value))throw Error('Укажите время фактического приёма');
        const chosenTime=time.value;
        const takenAtLocal=`${day}T${chosenTime}`;
        if(isFutureIntake(takenAtLocal))throw Error('Нельзя отметить будущее время');
        // Friendly immediate feedback. Atomic transaction repeats this check to prevent races.
        if(snapshot.intakes.some(i=>i.medId===med.id&&i.takenAtLocal===takenAtLocal&&intakeStatus(i)==='active')){
          throw Error(`Приём в ${chosenTime} уже отмечен. Выберите другое время.`);
        }
        const record={id:crypto.randomUUID(),medId:med.id,date:day,takenAtLocal,
          markedAt:new Date().toISOString(),status:'active'};
        validateIntake(record);
        await changeIntake('marked',record);
        await reload();
        showMessage(`✓ Приём в ${chosenTime} сохранён. История сохранена.`);
      }catch(e){showMessage(toError(e),'error');}
      finally{
        submitting=false;
        confirmButton.disabled=false;
        confirmButton.textContent='✓ Подтвердить приём';
      }
    });
    row.append(controls);wrap.append(row);
    const records=snapshot.intakes.filter(i=>i.medId===med.id&&i.date===day)
      .sort((a,b)=>(a.takenAtLocal||'').localeCompare(b.takenAtLocal||'')||a.markedAt.localeCompare(b.markedAt));
    const recList=node('div','med-record-list');
    if(!records.length)recList.append(node('p','empty','За выбранную дату приёмов нет.'));
    for(const i of records){
      const active=intakeStatus(i)==='active',item=node('div',`intake-record ${active?'':'cancelled'}`);
      const header=node('div','intake-record-head');
      header.append(node('strong','',active?'✓ '+(takenTime(i)||'Время неизвестно'):'Отменено · '+(takenTime(i)||'Время неизвестно')));
      if(active){
        const actions=node('div','intake-record-actions');
        const corrected=node('input','intake-time-input');corrected.type='time';corrected.value=takenTime(i)||'';
        corrected.setAttribute('aria-label','Уточнить время '+med.name);
        const update=node('button','tiny-button','Изменить время');update.type='button';
        update.addEventListener('click',async()=>{
          const takenAtLocal=`${i.date}T${corrected.value}`;
          if(!validClock(corrected.value)){showMessage('Укажите корректное время','warn');return;}
          if(isFutureIntake(takenAtLocal)){showMessage('Время в будущем недопустимо','warn');return;}
          if(i.takenAtLocal===takenAtLocal){showMessage('Время уже сохранено');return;}
          if(!confirm(`Изменить время ТЕСТОВОГО приёма ${med.name}?`))return;
          update.disabled=true;
          try{
            const next={...i,takenAtLocal,updatedAt:new Date().toISOString()};
            await changeIntake('time_corrected',next,i);
            await reload();showMessage('Изменение времени записано в историю.');
          }catch(e){await reload();showMessage(toError(e),'error');}
        });
        const cancel=node('button','tiny-button danger','Отменить отметку');cancel.type='button';
        cancel.addEventListener('click',async()=>{
          if(!confirm(`Отменить ТЕСТОВУЮ отметку ${med.name}? История останется.`))return;
          cancel.disabled=true;
          try{
            const stamp=new Date().toISOString();
            const next={...i,status:'cancelled',cancelledAt:stamp,updatedAt:stamp};
            await changeIntake('cancelled',next,i);
            await reload();showMessage('Отметка отменена, история сохранена.');
          }catch(e){await reload();showMessage(toError(e),'error');}
        });
        actions.append(corrected,update,cancel);header.append(actions);
      }
      item.append(header);
      const audit=eventsForIntake(i);
      if(!audit.length)item.append(node('div','row-subtitle','Исходная история изменений недоступна (старый формат).'));
      for(const event of audit)item.append(node('div','audit-event',eventLabel(event)));
      recList.append(item);
    }
    wrap.append(recList);list.append(wrap);
  }
  const history=$('intake-list');history.replaceChildren();
  const ordered=[...snapshot.intakes].sort((a,b)=>b.date.localeCompare(a.date)||
    (b.takenAtLocal||'').localeCompare(a.takenAtLocal||'')||b.markedAt.localeCompare(a.markedAt)).filter(i=>{const selected=$('intake-filter')?.value||'all';return selected==='all'||intakeStatus(i)===selected;}).slice(0,18);
  if(!ordered.length){history.append(node('p','empty','Отметок пока нет.'));return;}
  for(const i of ordered){
    const med=snapshot.medications.find(m=>m.id===i.medId);
    const row=node('div','overview-row');
    row.append(node('span','row-title',med?.name||'Учебный препарат не найден'),
      node('span','row-subtitle',`${intakeLabel(i)} · ${intakeStatus(i)==='active'?'✓':'отменено'}`));
    history.append(row);
  }
}

function renderOverview(){
  const ps=$('overview-pressure'),ms=$('overview-meds');ps.replaceChildren();ms.replaceChildren();
  const recent=[...snapshot.pressures].sort((a,b)=>b.dateTime.localeCompare(a.dateTime)).slice(0,4);
  if(!recent.length)ps.append(node('p','empty','Пока нет записей.'));
  for(const p of recent){const r=node('div','overview-row');r.append(
    node('span','row-title',`${p.systolic} / ${p.diastolic}`),node('span','row-subtitle',dateLabel(p.dateTime)));ps.append(r);}
  const day=today();
  if(!snapshot.medications.length)ms.append(node('p','empty','Пока нет препаратов.'));
  for(const med of snapshot.medications.slice(0,7)){
    const active=snapshot.intakes.filter(i=>i.medId===med.id&&i.date===day&&intakeStatus(i)==='active');
    const r=node('div','overview-row');r.append(node('span','row-title',med.name),
      node('span','row-subtitle',active.length?`✓ Отмечено: ${active.length}`:'○ Нет отметки'));
    ms.append(r);
  }
}

function validDate(s){return typeof s==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(s)&&Number.isFinite(new Date(s+'T12:00:00').getTime())&&dateLocal(new Date(s+'T12:00:00'))===s}
function validDateTime(s){return typeof s==='string'&&/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(s)&&Number.isFinite(new Date(s).getTime())&&dateTimeLocal(new Date(s))===s}
function validClock(s){return typeof s==='string'&&/^([01]\d|2[0-3]):[0-5]\d$/.test(s)}
function validBackupVersion(v){return Number.isInteger(v)&&[1,2,3].includes(v)}
function validInstant(s){return typeof s==='string'&&/^\d{4}-\d{2}-\d{2}T/.test(s)&&Number.isFinite(Date.parse(s))}
function validId(s){return typeof s==='string'&&/^[A-Za-z0-9_-]{8,100}$/.test(s)}
function validatePressure(p){if(!p||typeof p!=='object'||!validId(p.id)||p.arm!=='right'||!validDateTime(p.dateTime)||!validInstant(p.createdAt)||!Number.isInteger(p.systolic)||p.systolic<50||p.systolic>300||!Number.isInteger(p.diastolic)||p.diastolic<30||p.diastolic>200||p.systolic<=p.diastolic||!(p.pulse===null||(Number.isInteger(p.pulse)&&p.pulse>=25&&p.pulse<=250))||typeof p.note!=='string'||p.note.length>250)throw Error('Некорректная запись давления');}
function validateMed(m){
  if(!m||typeof m!=='object'||!validId(m.id)||typeof m.name!=='string'||!m.name.startsWith('Учебный препарат')||m.name.length>100||typeof m.dose!=='string'||m.dose.length>60||!Object.hasOwn(KINDS,m.kind)||!validInstant(m.createdAt)||!(m.from===null||validDate(m.from))||!(m.to===null||validDate(m.to))||(m.from&&m.to&&m.from>m.to))throw Error('Некорректная синтетическая запись препарата');
  validatedMedExtension(m);
}
function validateIntake(i){
  if(!i||typeof i!=='object'||!validId(i.id)||!validId(i.medId)||!validDate(i.date)||!validInstant(i.markedAt)||
    (i.takenAtLocal!==undefined&&(!validDateTime(i.takenAtLocal)||!i.takenAtLocal.startsWith(i.date+'T')))||
    (i.updatedAt!==undefined&&!validInstant(i.updatedAt))||
    (i.status!==undefined&&!['active','cancelled'].includes(i.status))||
    (i.cancelledAt!==undefined&&!validInstant(i.cancelledAt))||
    (intakeStatus(i)==='cancelled'&&!i.cancelledAt)||
    (intakeStatus(i)==='active'&&i.cancelledAt))throw Error('Некорректная отметка приёма');
}
function validateIntakeEvent(e){
  if(!e||typeof e!=='object'||!validId(e.id)||!validId(e.intakeId)||!validId(e.medId)||
    !['marked','time_corrected','cancelled'].includes(e.action)||!validInstant(e.at)||
    (e.oldTakenAtLocal!==undefined&&!validDateTime(e.oldTakenAtLocal))||
    (e.newTakenAtLocal!==undefined&&!validDateTime(e.newTakenAtLocal))||
    ((e.action==='marked'||e.action==='time_corrected')&&!e.newTakenAtLocal))
      throw Error('Некорректное событие журнала');
}

function canonical(value){if(Array.isArray(value))return'['+value.map(canonical).join(',')+']';if(value!==null&&typeof value==='object'){return'{'+Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+canonical(value[k])).join(',')+'}'}return JSON.stringify(value)}
async function sha256(value){if(!crypto.subtle)throw Error('SHA-256 требует HTTPS или localhost');const bytes=new TextEncoder().encode(canonical(value));const digest=await crypto.subtle.digest('SHA-256',bytes);return Array.from(new Uint8Array(digest),b=>b.toString(16).padStart(2,'0')).join('');}
function normalizedBackupData(version,data){
  if(!data||typeof data!=='object')throw Error('Отсутствует резервная копия');
  if(version<3)return {pressures:data.pressures,medications:data.medications,intakes:data.intakes,intakeEvents:[]};
  return data;
}
// Read all four stores under ONE readonly transaction: a consistent backup snapshot.
function readBackupSnapshot(){return new Promise((resolve,reject)=>{
  if(!db)return reject(new Error('База ещё не открыта'));
  const tx=db.transaction(STORE_NAMES,'readonly'),data={};
  for(const name of STORE_NAMES){
    const req=tx.objectStore(name).getAll();
    req.onsuccess=()=>{data[name]=req.result.sort((a,b)=>a.id.localeCompare(b.id));};
  }
  tx.oncomplete=()=>resolve(data);
  tx.onabort=()=>reject(tx.error||new Error('Не удалось прочитать защитную копию'));
  tx.onerror=()=>{};
});}
async function createBackup(){
  const data=await readBackupSnapshot();
  const body={format:BACKUP_FORMAT,version:BACKUP_VERSION,exportedAt:new Date().toISOString(),data};
  return {...body,sha256:await sha256(body)};
}
function validateBackupData(data,includeLocal=true){
  if(!data||typeof data!=='object'||STORE_NAMES.some(n=>!Array.isArray(data[n])))throw Error('Отсутствует необходимая таблица');
  let total=0;const ids={};
  for(const name of STORE_NAMES){
    ids[name]=new Set();total+=data[name].length;
    if(data[name].length>25000)throw Error('Слишком много записей');
    for(const r of data[name]){
      if(name==='pressures')validatePressure(r);
      if(name==='medications')validateMed(r);
      if(name==='intakes')validateIntake(r);
      if(name==='intakeEvents')validateIntakeEvent(r);
      if(ids[name].has(r.id))throw Error('Повтор ID в '+name);
      ids[name].add(r.id);
    }
  }
  if(total>50000)throw Error('Превышено допустимое количество записей');
  const meds=new Set([...(includeLocal?snapshot.medications:[]),...data.medications].map(x=>x.id));
  const intakes=new Map([...(includeLocal?snapshot.intakes:[]),...data.intakes].map(x=>[x.id,x]));
  const times=new Map();
  for(const i of [...(includeLocal?snapshot.intakes:[]),...data.intakes]){
    if(!meds.has(i.medId))throw Error('Отметка без препарата');
    if(intakeStatus(i)!=='active'||!i.takenAtLocal)continue;
    const key=i.medId+'|'+i.takenAtLocal;
    if(times.has(key)&&times.get(key)!==i.id)throw Error('Повтор активного приёма в то же время');
    times.set(key,i.id);
  }
  for(const e of data.intakeEvents){
    const intake=intakes.get(e.intakeId);
    if(!intake||intake.medId!==e.medId)throw Error('Событие без связанного приёма');
  }
  return total;
}
function prepareMerge(data){
  let fresh=0,duplicate=0,conflicts=0;
  const active=new Map(snapshot.intakes.filter(i=>intakeStatus(i)==='active'&&i.takenAtLocal)
    .map(i=>[i.medId+'|'+i.takenAtLocal,i.id]));
  for(const name of STORE_NAMES){
    const byId=new Map(snapshot[name].map(x=>[x.id,x]));
    for(const item of data[name]){
      const old=byId.get(item.id);
      if(old){if(canonical(old)===canonical(item))duplicate++;else conflicts++;}
      else if(name==='intakes'&&intakeStatus(item)==='active'&&item.takenAtLocal&&
        active.has(item.medId+'|'+item.takenAtLocal))conflicts++;
      else fresh++;
    }
  }
  return {fresh,duplicate,conflicts};
}
function atomicMerge(data){return new Promise((resolve,reject)=>{
  const tx=db.transaction(STORE_NAMES,'readwrite');let n=0,reason='Конфликт резервной копии';
  tx.oncomplete=()=>resolve(n);tx.onabort=()=>reject(new Error(reason));
  const fail=msg=>{reason=msg;try{tx.abort();}catch{}};
  const req=tx.objectStore('intakes').getAll();
  req.onsuccess=()=>{
    const existingTimes=new Map(req.result.filter(i=>intakeStatus(i)==='active'&&i.takenAtLocal)
      .map(i=>[i.medId+'|'+i.takenAtLocal,i.id]));
    for(const i of data.intakes){
      if(intakeStatus(i)==='active'&&i.takenAtLocal){
        const other=existingTimes.get(i.medId+'|'+i.takenAtLocal);
        if(other&&other!==i.id){fail('Повтор времени относительно текущей базы');return;}
      }
    }
    for(const name of STORE_NAMES){
      const store=tx.objectStore(name);
      for(const item of data[name]){
        const found=store.get(item.id);
        found.onsuccess=()=>{
          if(found.result){if(canonical(found.result)!==canonical(item))fail('Конфликт изменённой записи');}
          else{const added=store.add(item);added.onsuccess=()=>{n++};}
        };
      }
    }
  };
  req.onerror=()=>fail('Ошибка проверки текущей базы');
});}

function downloadFile(filename,blob){const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=filename;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),30000)}
async function onPressureSubmit(e){e.preventDefault();const sys=Number($('systolic').value),dia=Number($('diastolic').value),pulse=$('pulse').value.trim()?Number($('pulse').value):null,dt=$('pressure-datetime').value,note=$('pressure-note').value.trim();try{const p={id:crypto.randomUUID(),systolic:sys,diastolic:dia,pulse,dateTime:dt,note,arm:'right',createdAt:new Date().toISOString()};validatePressure(p);await addRecord('pressures',p);e.target.reset();$('pressure-datetime').value=dateTimeLocal(new Date());updateAllWheelTriggers();await reload();showMessage('Синтетическое измерение сохранено локально.')}catch(err){showMessage(toError(err),'error')}}
async function onMedSubmit(e){
  e.preventDefault();
  const p={id:crypto.randomUUID(),name:$('med-name').value.trim(),dose:$('med-dose').value.trim(),kind:$('med-kind').value,
    from:$('course-from').value||null,to:$('course-to').value||null,createdAt:new Date().toISOString()};
  if(p.kind!=='course'){p.from=null;p.to=null;}
  const raw=$('med-strength').value.trim(),strength=raw===''?null:Number(raw),unit=$('med-unit').value,form=$('med-form-factor').value;
  if(raw!==''||unit!==''||form!=='')p.pae04v021={strength,unit,form};
  try{
    validateMed(p);await addRecord('medications',p);e.target.reset();$('course-fields').hidden=true;updateAllWheelTriggers();await reload();
    showMessage('Синтетический препарат добавлен в изолированный локальный журнал v0.2.1 INTEGRATION TEST.');
  }catch(err){showMessage(toError(err),'error');}
}
async function exportBackup(){try{const backup=await createBackup();downloadFile(`PAE04-SYNTHETIC-BACKUP-${today()}.json`,new Blob([JSON.stringify(backup,null,2)],{type:'application/json'}));showMessage('Копия сформирована и передана браузеру на скачивание. Проверьте наличие файла в «Загрузках».')}catch(e){showMessage(toError(e),'error')}}
let backupVerifySequence=0;
async function verifyDownloadedBackup(e){
  const sequence=++backupVerifySequence,view=$('verify-result');
  view.replaceChildren();
  const file=e.target.files?.[0];if(!file)return;
  try{
    if(file.size>5*1024*1024)throw Error('Максимальный размер проверяемого JSON — 5 МБ');
    const parsed=JSON.parse(await file.text());if(sequence!==backupVerifySequence)return;
    if(!parsed||parsed.format!==BACKUP_FORMAT||!validBackupVersion(parsed.version)||
      !validInstant(parsed.exportedAt)||!parsed.data||
      typeof parsed.sha256!=='string'||!/^[a-f0-9]{64}$/.test(parsed.sha256))throw Error('Неверный формат копии');
    const {sha256:expected,...body}=parsed;
    if(await sha256(body)!==expected)throw Error('SHA-256 не совпадает: файл изменён или повреждён');
    if(sequence!==backupVerifySequence)return;
    const normalized=normalizedBackupData(parsed.version,parsed.data);
    const total=validateBackupData(normalized,false);
    if(sequence!==backupVerifySequence)return;
    const details=STORE_NAMES.map(name=>name+': '+normalized[name].length).join(' · ');
    view.append(node('p','verify-pass','PASS · SHA-256 совпадает · '+total+' учебных записей'),
      node('p','form-hint','Файл: '+file.name+' · '+details),
      node('p','form-hint','Файл проверен без импорта. Это не шифрование. Защитите копию от посторонних.'));
  }catch(err){if(sequence!==backupVerifySequence)return;view.append(node('p','verify-fail','FAIL · '+toError(err)));}
}
function resetImportCheckpoint(){
  $('checkpoint-button').disabled=true;
  $('checkpoint-ack').checked=false;
  $('checkpoint-ack').disabled=true;
  $('checkpoint-status').textContent='';
  $('import-button').disabled=true;
}
function syncImportReady(){
  $('import-button').disabled=!(pendingImport?.checkpoint&&$('checkpoint-ack').checked);
}
async function previewImport(e){
  const sequence=++importPreviewSequence;
  pendingImport=null;resetImportCheckpoint();
  const view=$('import-preview');view.replaceChildren();const file=e.target.files?.[0];if(!file)return;
  try{
    if(file.size>5*1024*1024)throw Error('Максимальный размер копии — 5 МБ');
    const parsed=JSON.parse(await file.text());
    if(sequence!==importPreviewSequence)return;
    if(parsed.format!==BACKUP_FORMAT||!validBackupVersion(parsed.version)||!validInstant(parsed.exportedAt)||
      !parsed.data||typeof parsed.sha256!=='string'||!/^[a-f0-9]{64}$/.test(parsed.sha256))throw Error('Неверный формат');
    const {sha256:expected,...body}=parsed;
    if(await sha256(body)!==expected)throw Error('SHA-256 не совпадает: файл повреждён');
    if(sequence!==importPreviewSequence)return;
    await reload();
    if(sequence!==importPreviewSequence)return;
    const data=normalizedBackupData(parsed.version,parsed.data);
    validateBackupData(data);const plan=prepareMerge(data);
    view.append(node('div',null,`Проверка SHA-256 PASS · Новых: ${plan.fresh} · Совпадающих: ${plan.duplicate} · Конфликтов: ${plan.conflicts}`));
    if(plan.conflicts){view.append(node('div',null,'Восстановление заблокировано из-за конфликтов.'));return;}
    if(sequence!==importPreviewSequence)return;
    pendingImport={data,version:parsed.version,hash:expected,plan,checkpoint:null};
    $('checkpoint-button').disabled=false;
  }catch(err){if(sequence!==importPreviewSequence)return;view.append(node('div',null,'Ошибка: '+toError(err)));showMessage('Проверка копии не пройдена','error');}
}
async function downloadImportCheckpoint(){
  const selected=pendingImport;
  if(!selected)return;
  $('checkpoint-button').disabled=true;
  $('checkpoint-ack').disabled=true;
  $('checkpoint-ack').checked=false;syncImportReady();
  try{
    const backup=await createBackup();
    const baselineHash=await sha256(backup.data);
    if(pendingImport!==selected)return; // file selection changed during async read
    downloadFile(`PAE04-SYNTHETIC-PREIMPORT-CHECKPOINT-${today()}.json`,new Blob([JSON.stringify(backup,null,2)],{type:'application/json'}));
    selected.checkpoint={baselineHash,backupHash:backup.sha256};
    $('checkpoint-ack').disabled=false;
    $('checkpoint-status').textContent='Копия с SHA-256 '+backup.sha256.slice(0,12)+'… передана браузеру. Проверьте, что файл действительно сохранён вне PWA, затем подтвердите ниже.';
    showMessage('Проверьте наличие защитного файла в «Загрузках». Только затем разрешите импорт.');
  }catch(err){
    if(pendingImport===selected){selected.checkpoint=null;$('checkpoint-button').disabled=false;}
    showMessage('Защитная копия не создана: '+toError(err),'error');
  }
}
async function applyImport(){
  const selected=pendingImport;
  if(!selected?.checkpoint||!$('checkpoint-ack').checked){
    showMessage('Сначала скачайте защитную копию и подтвердите её сохранение.','error');return;
  }
  const {data,version,checkpoint}=selected;
  $('import-button').disabled=true;
  try{
    const current=await readBackupSnapshot();
    if(pendingImport!==selected)return;
    const currentHash=await sha256(current);
    if(pendingImport!==selected)return;
    if(currentHash!==checkpoint.baselineHash){
      selected.checkpoint=null;resetImportCheckpoint();$('checkpoint-button').disabled=false;
      showMessage('База изменилась после защитной копии. Скачайте новую копию перед импортом.','error');return;
    }
    await reload();
    if(pendingImport!==selected)return;
    validateBackupData(data);
    const plan=prepareMerge(data);
    if(plan.conflicts)throw Error('Обнаружены конфликты, импорт остановлен');
    if(!confirm(`Импортировать ${plan.fresh} новых учебных записей из формата v${version}?\nБез удаления старых записей. Защитная копия уже сформирована.`))return;
    if(pendingImport!==selected)return;
    const count=await atomicMerge(data);
    pendingImport=null;resetImportCheckpoint();$('import-file').value='';
    $('import-preview').replaceChildren(node('div',null,`Добавлено ${count} записей; старые записи не изменены.`));
    await reload();showMessage('Учебная резервная копия импортирована.');
  }catch(e){showMessage('Импорт прерван: '+toError(e),'error');}
  finally{syncImportReady();}
}

function connectStatus(){const online=navigator.onLine,el=$('connection-status');el.replaceChildren(node('span',`status-dot ${online?'online':'offline'}`),document.createTextNode(online?'Соединение доступно':'Нет интернета · офлайн'));}
async function init(){document.querySelectorAll('[data-page]').forEach(b=>b.addEventListener('click',()=>navigate(b.dataset.page)));document.querySelectorAll('[data-go]').forEach(b=>b.addEventListener('click',()=>navigate(b.dataset.go)));window.addEventListener('online',connectStatus);window.addEventListener('offline',connectStatus);connectStatus();$('pressure-datetime').value=dateTimeLocal(new Date());$('intake-date').value=today();setupWheelPicker();$('pressure-form').addEventListener('submit',onPressureSubmit);$('med-form').addEventListener('submit',onMedSubmit);$('intake-date').addEventListener('change',renderMedications);$('pressure-filter').addEventListener('change',renderPressure);$('pressure-search').addEventListener('input',renderPressure);$('intake-filter').addEventListener('change',renderMedications);$('med-search').addEventListener('input',renderMedications);$('catalog-search').addEventListener('input',e=>{if(['Учебный препарат А','Учебный препарат Б','Учебный препарат В'].includes(e.target.value))$('med-name').value=e.target.value});$('med-kind').addEventListener('change',e=>{$('course-fields').hidden=e.target.value!=='course'});$('export-button').addEventListener('click',exportBackup);$('verify-file').addEventListener('change',verifyDownloadedBackup);$('import-file').addEventListener('change',previewImport);$('checkpoint-button').addEventListener('click',downloadImportCheckpoint);$('checkpoint-ack').addEventListener('change',syncImportReady);$('import-button').addEventListener('click',applyImport);try{db=await openDB();await reload();if('serviceWorker'in navigator){try{await navigator.serviceWorker.register('./sw.js');}catch(err){showMessage(`Локальная база работает, но офлайн-кэш не включился: ${toError(err)}`,'warn')}}}catch(e){showMessage(`Не удалось открыть локальную базу: ${toError(e)}`,'error');document.querySelectorAll('form button[type=submit],#export-button,#import-button').forEach(b=>b.disabled=true)}}
document.addEventListener('DOMContentLoaded',init);
