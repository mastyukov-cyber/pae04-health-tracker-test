'use strict';
// PAE-04 PWA v05 SAFE UX. Synthetic records only; no external endpoints, no schema changes.
// Build-independent name. TEST-only; future synthetic v05+ must keep this ID unchanged.
const DB_NAME='PAE04_CYBER_CP39R_R7_SYNTHETIC_ONLY_20261122';
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

// CP-MULTI01: optional logging slots only, not dosage or time recommendations.
function medDailyTarget(m){
  if(m.dailyIntakes===undefined)return null;
  if(![1,2,3].includes(m.dailyIntakes))throw Error('Некорректное число приёмов');
  return m.dailyIntakes;
}
function medSlotLabel(goal,n){
  return goal===2?['Утро','Вечер'][n-1]:goal===3?['Утро','День','Вечер'][n-1]:'Приём';
}
function medDailySlots(m,active){
  const goal=medDailyTarget(m);if(goal===null)return [];
  const slots=Array(goal).fill(null);
  const ordered=[...active].filter(i=>i.status!=='cancelled')
    .sort((a,b)=>(a.takenAtLocal||'').localeCompare(b.takenAtLocal||'')||a.markedAt.localeCompare(b.markedAt));
  for(const i of ordered)if(Number.isInteger(i.dailySlot)&&i.dailySlot>=1&&i.dailySlot<=goal&&!slots[i.dailySlot-1])slots[i.dailySlot-1]=i;
  return slots;
}
function medDailyProgress(m,active){
  const goal=m.kind==='asNeeded'?null:medDailyTarget(m);
  if(goal===null)return {goal:null,actual:active.length,checked:null};
  return {goal,actual:active.length,checked:medDailySlots(m,active).filter(Boolean).length};
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
  return new Intl.DateTimeFormat('ru-RU',{day:'numeric',month:'long',year:'numeric'}).format(new Date(y,m-1,d,12));
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

// v05.5: do not report "saved" until IndexedDB transaction commits AND a fresh read confirms it.
function getRecordById(store,id){
  return new Promise((resolve,reject)=>{
    if(!STORE_NAMES.includes(store))return reject(new Error('Неизвестное хранилище'));
    const tx=db.transaction([store],'readonly'),req=tx.objectStore(store).get(id);
    let found;
    req.onsuccess=()=>{found=req.result};
    req.onerror=()=>reject(req.error||new Error('Ошибка чтения сохранённой записи'));
    tx.oncomplete=()=>resolve(found);
    tx.onabort=()=>reject(tx.error||new Error('Проверка после сохранения прервана'));
  });
}
async function verifyRecordAfterWrite(store,record){
  const fresh=await getRecordById(store,record.id);
  if(!fresh||canonical(fresh)!==canonical(record))
    throw Error('Не удалось подтвердить сохранение: повторно проверьте журнал перед новой попыткой');
}
async function verifyIntakeAudit(record,auditEvent){
  const [saved,event]=await Promise.all([
    getRecordById('intakes',record.id),
    getRecordById('intakeEvents',auditEvent.id)
  ]);
  if(!saved||canonical(saved)!==canonical(record)||
     !event||canonical(event)!==canonical(auditEvent))
    throw Error('Отметка могла сохраниться, но повторная проверка не пройдена. Сначала откройте журнал.');
}

function getAll(store){return new Promise((resolve,reject)=>{const tx=db.transaction([store],'readonly');const req=tx.objectStore(store).getAll();req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error||new Error('Ошибка чтения'));});}
function addRecord(store,record){return new Promise((resolve,reject)=>{const tx=db.transaction([store],'readwrite');tx.objectStore(store).add(record);tx.oncomplete=()=>{verifyRecordAfterWrite(store,record).then(resolve,reject)};tx.onabort=()=>reject(tx.error||new Error('Ошибка сохранения'));tx.onerror=()=>{};});}
function removeRecord(store,id){return new Promise((resolve,reject)=>{const tx=db.transaction([store],'readwrite');tx.objectStore(store).delete(id);tx.oncomplete=()=>{getRecordById(store,id).then(found=>{if(found!==undefined)return reject(new Error('Не удалось подтвердить удаление'));safetyNeedsNewCheck();resolve()},reject)};tx.onabort=()=>reject(tx.error||new Error('Ошибка удаления'));tx.onerror=()=>{};});}
// Every intake change and its audit event are committed atomically.
function changeIntake(action,record,previous=null){return new Promise((resolve,reject)=>{
  if(!['marked','time_corrected','cancelled'].includes(action))return reject(new Error('Недопустимое действие'));
  try{validateIntake(record);}catch(e){reject(e);return;}
  const tx=db.transaction(['intakes','intakeEvents'],'readwrite');
  const store=tx.objectStore('intakes'),history=tx.objectStore('intakeEvents');
  let message='Транзакция приёма прервана';
  const abort=reason=>{message=reason;try{tx.abort();}catch{}};
  let auditEvent=null;
  tx.oncomplete=()=>{if(!auditEvent)return reject(new Error('Нет события отметки после транзакции'));verifyIntakeAudit(record,auditEvent).then(()=>{safetyNeedsNewCheck();resolve()},reject)};
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
    if(intakeStatus(record)==='active'&&record.dailySlot!==undefined&&rows.some(i=>
      i.id!==record.id&&i.medId===record.medId&&i.date===record.date&&
      i.dailySlot===record.dailySlot&&intakeStatus(i)==='active')){
      abort('Этот номер приёма за день уже отмечен');return;
    }
    const event={id:crypto.randomUUID(),intakeId:record.id,medId:record.medId,action,at:new Date().toISOString()};
    if(action==='marked')event.newTakenAtLocal=record.takenAtLocal;
    if(action==='time_corrected'){
      if(previous.takenAtLocal)event.oldTakenAtLocal=previous.takenAtLocal;
      event.newTakenAtLocal=record.takenAtLocal;
    }
    if(action==='cancelled'&&previous.takenAtLocal)event.oldTakenAtLocal=previous.takenAtLocal;
    try{validateIntakeEvent(event);}catch(e){abort(e.message);return;}
    auditEvent=event;
    if(action==='marked')store.add(record);else store.put(record);
    history.add(event);
  };
  query.onerror=()=>abort('Не удалось проверить отметки');
});}

// Update only the journal frequency. Preserve ID, dosage and intake history.
function changeMedDailyTarget(previous,goal){
  const next={...previous};
  if(goal===null)delete next.dailyIntakes;else next.dailyIntakes=goal;
  validateMed(next);
  return new Promise((resolve,reject)=>{
    const tx=db.transaction(['medications'],'readwrite'),store=tx.objectStore('medications');
    let error='Не удалось сохранить кратность';
    tx.onabort=()=>reject(new Error(error));
    tx.oncomplete=()=>verifyRecordAfterWrite('medications',next).then(()=>{safetyNeedsNewCheck();resolve()},reject);
    const req=store.get(previous.id);
    req.onsuccess=()=>{
      if(!req.result||canonical(req.result)!==canonical(previous)){
        error='Карточка изменилась в другой вкладке';
        try{tx.abort()}catch{}return;
      }store.put(next);
    };
    req.onerror=()=>{error='Не удалось проверить карточку';try{tx.abort()}catch{}};
  });
}

async function reload(){const [pressures,medications,intakes,intakeEvents]=await Promise.all(STORE_NAMES.map(getAll));snapshot={pressures,medications,intakes,intakeEvents};render();}
function navigate(page){dismissMobileKeyboard();for(const el of document.querySelectorAll('.page'))el.classList.toggle('active',el.id===`page-${page}`);for(const b of document.querySelectorAll('[data-page]')){const active=b.dataset.page===page;b.classList.toggle('active',active);b.setAttribute('aria-current',active?'page':'false')}window.scrollTo({top:0,behavior:'instant'});}
function render(){const {pressures,medications,intakes}=snapshot;$('stat-pressure').textContent=String(pressures.length);$('stat-meds').textContent=String(medications.length);$('stat-intakes').textContent=String(intakes.filter(i=>intakeStatus(i)==='active').length);renderPressure();renderMedications();renderMedicationHistory();renderOverview();}
function dateLabel(iso){try{return new Intl.DateTimeFormat('ru-RU',{day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'}).format(new Date(iso))}catch{return iso}}
function periodCutoff(value){
 if(value==='all')return null;
 const n=new Date(),start=new Date(n.getFullYear(),n.getMonth(),n.getDate());
 if(value==='7'){start.setDate(start.getDate()-6);return dateTimeLocal(start);}
 const months=value==='30'?1:value==='90'?3:0;
 if(!months)return null;
 const t=new Date(start.getFullYear(),start.getMonth()-months,1);
 t.setDate(Math.min(start.getDate(),new Date(t.getFullYear(),t.getMonth()+1,0).getDate()));
 return dateTimeLocal(t);
}
function renderPressureChart(){
  const host=$('pressure-chart');if(!host)return;host.replaceChildren();
  const all=[...snapshot.pressures].sort((a,b)=>a.dateTime.localeCompare(b.dateTime));
  const cutoff=periodCutoff($('pressure-chart-period')?.value||'7');
  const rows=all.filter(p=>!cutoff||p.dateTime>=cutoff);
  if(!rows.length){host.append(node('p','empty',all.length?'За выбранный период измерений нет.':'График появится после первого измерения.'));return;}
  const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 720 252');svg.setAttribute('role','img');svg.setAttribute('aria-label','График давления: верхнее давление синее, нижнее зелёное, пульс красный на отдельной шкале.');
  const add=(tag,attrs={})=>{const e=document.createElementNS(ns,tag);for(const [k,v]of Object.entries(attrs))e.setAttribute(k,String(v));svg.append(e);return e;};
  const left=42,right=700,top=24,bottom=157,pulseTop=183,pulseBottom=222,n=rows.length;
  const instants=rows.map(p=>new Date(p.dateTime).getTime());
 const minTime=instants[0],maxTime=instants[n-1];
 const x=i=>n===1||maxTime===minTime?(left+right)/2:left+(right-left)*(instants[i]-minTime)/(maxTime-minTime);
  const yBP=v=>bottom-(Math.max(40,Math.min(240,v))-40)/200*(bottom-top);
  const yPulse=v=>pulseBottom-(Math.max(25,Math.min(250,v))-25)/225*(pulseBottom-pulseTop);
  const detail=node('p','pressure-point-detail','Нажмите на точку, чтобы увидеть значения и время.');detail.id='pressure-chart-detail';
  const showPoint=(p)=>{detail.textContent=`${dateLabel(p.dateTime)} · ${p.systolic}/${p.diastolic} мм рт. ст. · Пульс ${p.pulse===null?'не указан':p.pulse+' уд/мин'}`;};
  const point=(cx,cy,color,p,label)=>{const c=add('circle',{cx,cy,r:4,fill:color,tabindex:0,role:'button'});const text=`${label}: ${dateLabel(p.dateTime)}; ${p.systolic}/${p.diastolic}; пульс ${p.pulse===null?'не указан':p.pulse}`;c.setAttribute('aria-label',text);const title=document.createElementNS(ns,'title');title.textContent=text;c.append(title);c.addEventListener('click',()=>showPoint(p));c.addEventListener('focus',()=>showPoint(p));c.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();showPoint(p);}});};
  for(const value of [220,160,100,40]){const y=yBP(value);add('line',{x1:left,y1:y,x2:right,y2:y,stroke:'#e6ebf2','stroke-width':1});const t=add('text',{x:left-7,y:y+4,fill:'#758296','font-size':11,'text-anchor':'end'});t.textContent=String(value);}
  add('line',{x1:left,y1:172,x2:right,y2:172,stroke:'#cbd4e1','stroke-width':1});
  for(const value of [225,125,25]){const y=yPulse(value);const t=add('text',{x:left-7,y:y+4,fill:'#c34b55','font-size':10,'text-anchor':'end'});t.textContent=String(value);}
  const path=(key,color)=>{const pts=rows.map((p,i)=>`${i?'L':'M'}${x(i).toFixed(1)},${yBP(p[key]).toFixed(1)}`).join(' ');add('path',{d:pts,fill:'none',stroke:color,'stroke-width':3,'stroke-linecap':'round','stroke-linejoin':'round'});rows.forEach((p,i)=>point(x(i),yBP(p[key]),color,p,key==='systolic'?'Верхнее давление':'Нижнее давление'));};
  path('systolic','#3478d4');path('diastolic','#36a271');
  let pulsePath='';let pulseOpen=false;
  rows.forEach((p,i)=>{if(Number.isFinite(p.pulse)){pulsePath+=`${pulseOpen?'L':'M'}${x(i).toFixed(1)},${yPulse(p.pulse).toFixed(1)} `;pulseOpen=true;}else pulseOpen=false;});
  if(pulsePath)add('path',{d:pulsePath.trim(),fill:'none',stroke:'#dc5a62','stroke-width':2.5,'stroke-linecap':'round','stroke-linejoin':'round'});
  rows.forEach((p,i)=>{if(Number.isFinite(p.pulse))point(x(i),yPulse(p.pulse),'#dc5a62',p,'Пульс');});
  const first=new Intl.DateTimeFormat('ru-RU',{day:'2-digit',month:'short'}).format(new Date(rows[0].dateTime));
  const last=new Intl.DateTimeFormat('ru-RU',{day:'2-digit',month:'short'}).format(new Date(rows[rows.length-1].dateTime));
  const t1=add('text',{x:left,y:248,fill:'#758296','font-size':12});t1.textContent=first;
  const t2=add('text',{x:right,y:248,fill:'#758296','font-size':12,'text-anchor':'end'});t2.textContent=last;
  host.append(svg);
  const legend=node('div','pressure-legend');for(const [c,l]of [['#3478d4','Верхнее, мм рт. ст.'],['#36a271','Нижнее, мм рт. ст.'],['#dc5a62','Пульс, уд/мин · отдельная шкала']]){const item=node('span','pressure-legend-item');item.append(node('i','pressure-legend-dot'));item.querySelector('i').style.backgroundColor=c;item.append(document.createTextNode(l));legend.append(item);}host.append(legend);
  host.append(detail,node('p','form-hint',`${rows.length} измерений · пропуски пульса не соединяются нулевыми значениями.`));
}

function renderPressureSummary(){
 const host=$('v232-pressure-highlights');if(!host)return;host.replaceChildren();
 const all=[...snapshot.pressures].sort((a,b)=>b.dateTime.localeCompare(a.dateTime));
 const latest=all[0],todayRows=all.filter(p=>p.dateTime.slice(0,10)===today());
 const card=(title,value,meta,cls)=>{
  const panel=node('article','panel v232-pressure-stat '+(cls||''));
  const heading=node('h3','v232-pressure-stat-title',title);
  if(title==='Последний замер'){
   const icon=node('span','ui01-tonometer-icon');
   icon.setAttribute('aria-hidden','true');
   icon.innerHTML='<svg viewBox="0 0 64 64" aria-hidden="true"><rect x="11" y="5" width="34" height="46" rx="7"/><rect x="17" y="12" width="22" height="17" rx="2"/><path d="M20 22h4l3-5 4 9 3-4h3"/><circle cx="28" cy="40" r="3"/><path d="M45 37c13-2 17 2 13 10l-3 5"/><rect x="43" y="51" width="17" height="8" rx="3"/></svg>';
   heading.prepend(icon);
  }
  panel.append(heading,
    node('strong','v232-pressure-stat-number',value),
    node('p','v232-pressure-stat-meta',meta));host.append(panel);
 };
 if(!latest){card('Последний замер','—','Замеров пока нет');return;}
 card('Последний замер',latest.systolic+' / '+latest.diastolic,
  dateLabel(latest.dateTime)+' · '+(latest.pulse===null?'Пульс не указан':'Пульс '+latest.pulse+' уд/мин'),
  'v232-pressure-latest');
 if(todayRows.length>=2){
  const mean=k=>Math.round(todayRows.reduce((n,p)=>n+p[k],0)/todayRows.length);
  const pulses=todayRows.filter(p=>Number.isFinite(p.pulse));
  const pm=pulses.length>=2?
    ' · Средний пульс '+Math.round(pulses.reduce((n,p)=>n+p.pulse,0)/pulses.length):
    ' · Для среднего пульса недостаточно значений';
  card('Среднее за сегодня',mean('systolic')+' / '+mean('diastolic'),
    'По '+todayRows.length+' замерам'+pm,'v232-pressure-average');
 }
}
let v232PressureVisible=30,v232PressureKey='';
function renderPressure(){
  renderPressureSummary();
  renderPressureChart();
  const list=$('pressure-list');list.replaceChildren();const all=[...snapshot.pressures].sort((a,b)=>b.dateTime.localeCompare(a.dateTime));
  const cutoff=periodCutoff($('pressure-list-period')?.value||'all');const query=($('pressure-search')?.value||'').trim().toLocaleLowerCase('ru');
  const sorted=all.filter(p=>(!cutoff||p.dateTime>=cutoff)&&(!query||[`${p.systolic}/${p.diastolic}`,`${p.systolic} / ${p.diastolic}`,p.dateTime,dateLabel(p.dateTime),p.note||''].some(v=>v.toLocaleLowerCase('ru').includes(query))));
  const key=($('pressure-list-period')?.value||'all')+'|'+query;
  if(key!==v232PressureKey){v232PressureKey=key;v232PressureVisible=30;}
  $('pressure-count').textContent=`${sorted.length}${cutoff?` из ${all.length}`:''} записей`;
  if(!sorted.length){list.append(node('p','empty',all.length?'По заданному фильтру измерений нет.':'Пока нет измерений.'));return;}
  for(const p of sorted.slice(0,v232PressureVisible)){const r=node('div','history-row'),l=node('div'),h=node('div','row-number',`${p.systolic} / ${p.diastolic}`),sub=node('div','row-subtitle',`${dateLabel(p.dateTime)}${p.pulse===null?'':` · Пульс ${p.pulse}`}`);l.append(h,sub);if(p.note)l.append(node('div','row-subtitle',p.note));const b=node('button','tiny-button danger','Удалить');b.type='button';b.setAttribute('aria-label',`Удалить измерение ${p.systolic}/${p.diastolic}`);b.addEventListener('click',async()=>{if(!confirm('Удалить этот замер? Действие не отменяется.'))return;try{await removeRecord('pressures',p.id);await reload();showMessage('Замер удалён.')}catch(e){showMessage(toError(e),'error')}});const details=node('details','v232-pressure-detail');
 const summary=node('summary','v232-pressure-trigger');
 summary.append(l,node('span','v232-chevron','⌄'));
 const expanded=node('div','v232-pressure-expanded');
 expanded.append(node('p','row-subtitle','Дата и время: '+dateLabel(p.dateTime)),
  node('p','row-subtitle','Пульс: '+(p.pulse===null?'не указан':p.pulse+' уд/мин')),
  node('p','row-subtitle','Рука: правая'));
 expanded.append(b);details.append(summary,expanded);r.append(details);list.append(r);}
 if(sorted.length>v232PressureVisible){
  const more=node('button','secondary v232-load-more','Показать ещё · '+(sorted.length-v232PressureVisible));
  more.type='button';more.addEventListener('click',()=>{v232PressureVisible+=30;renderPressure();});list.append(more);
 }
}
function intakeStatus(i){return i.status||'active';}
// R10 UTC chronology: offsets must be compared as actual instants, never strings.
function eventsForIntake(i){return snapshot.intakeEvents.filter(e=>e.intakeId===i.id)
  .sort((a,b)=>{
    const ta=Date.parse(a.at),tb=Date.parse(b.at);
    if(!Number.isFinite(ta)||!Number.isFinite(tb))return String(a.id).localeCompare(String(b.id));
    return ta-tb||String(a.id).localeCompare(String(b.id));
  });}
function intakeAuditNeedsReview(events){
  return events.some((e,index)=>!Number.isFinite(Date.parse(e.at))||
    (index>0&&Date.parse(e.at)===Date.parse(events[index-1].at)));
}
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
    title.prepend(node('span','med-pill','▱'));
    title.append(node('span','med-type',KINDS[med.kind]));
    let sub=medDescription(med);
    if(med.kind==='course')sub+=' · '+(med.from||'…')+' – '+(med.to||'…');
    desc.append(title,node('div','row-subtitle',sub));
    const existing=snapshot.intakes.filter(i=>i.medId===med.id&&i.date===day&&intakeStatus(i)==='active');
    const goal=med.kind==='asNeeded'?null:medDailyTarget(med),progress=medDailyProgress(med,existing);
    desc.append(node('div','row-subtitle',goal===null?`За день: ${existing.length} подтверждённых приёмов`:`За день: ${progress.checked}/${goal} · всего фактов: ${existing.length}`));
    const frequencyLabel=node('label','med-frequency-label','Приёмов за день (учёт, не назначение)');
    const frequency=node('select','med-frequency-select');
    frequency.setAttribute('aria-label',`Кратность для ${med.name}`);
    for(const [value,name] of [['','Не задано'],['1','1 раз'],['2','2 раза'],['3','3 раза']]){
      const option=node('option',null,name);option.value=value;frequency.append(option);
    }
    frequency.value=goal===null?'':String(goal);
    frequency.addEventListener('change',async()=>{
      frequency.disabled=true;
      try{await changeMedDailyTarget(med,frequency.value===''?null:Number(frequency.value));await reload();showMessage('Кратность сохранена, прежние отметки не изменены.');}
      catch(e){await reload();showMessage(toError(e),'error')}
    });
    frequencyLabel.hidden=med.kind==='asNeeded';frequencyLabel.append(frequency);desc.append(frequencyLabel);
    row.append(desc);
    const controls=node('div','med-time-controls'),label=node('label','intake-time-label','Время нового приёма');
    const time=node('input','intake-time-input');time.type='time';time.step=60;
    time.value=day===today()?clockLocal(new Date()):'';
    time.setAttribute('aria-label',`Время нового приёма ${med.name}`);
    label.append(time);controls.append(label);
    let prnReason=null;
    if(med.kind==='asNeeded'){
      const reasonLabel=node('label','v232-prn-reason-label','Причина приёма (необязательно)');
      prnReason=node('input','v232-prn-reason-input');prnReason.type='text';
      prnReason.maxLength=160;prnReason.autocomplete='off';
      prnReason.placeholder='Можно оставить пустым';
      reasonLabel.append(prnReason);controls.append(reasonLabel);
    }
    const confirmButton=node('button','primary intake-confirm-button','✓ Подтвердить приём');
    confirmButton.type='button';
    confirmButton.setAttribute('aria-label',`Подтвердить фактический приём ${med.name}`);
    if(goal===null)controls.append(confirmButton);
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
        if(prnReason){const reason=prnReason.value.trim();if(reason)record.reason=reason;}
        validateIntake(record);
        await changeIntake('marked',record);
      safetyNeedsNewCheck();
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
    if(goal!==null){
      const schedule=node('div','med-schedule-slots');schedule.setAttribute('role','group');
      schedule.setAttribute('aria-label',`Отметки для ${med.name}`);
      const slots=medDailySlots(med,existing);
      for(let n=1;n<=goal;n++){
        const taken=slots[n-1],label=node('label','med-schedule-slot'),box=node('input');
        box.type='checkbox';box.checked=!!taken;
        box.setAttribute('aria-label',`${med.name}: ${medSlotLabel(goal,n)}, приём ${n}`);
        label.append(box,node('span',null,`${medSlotLabel(goal,n)}${taken?' · '+(takenTime(taken)||'время неизвестно'):''}`));
        schedule.append(label);
        let processing=false;
        box.addEventListener('change',async()=>{
          if(processing){box.checked=!!taken;return}
          processing=true;box.disabled=true;
          try{
            if(taken){
              if(!confirm(`Отменить отметку «${medSlotLabel(goal,n)}»? История останется.`)){box.checked=true;return}
              const stamp=new Date().toISOString();
              await changeIntake('cancelled',{...taken,status:'cancelled',cancelledAt:stamp,updatedAt:stamp},taken);
            }else{
              if(!validClock(time.value))throw Error('Укажите фактическое время');
              const takenAtLocal=`${day}T${time.value}`;
              if(isFutureIntake(takenAtLocal))throw Error('Время в будущем');
              const record={id:crypto.randomUUID(),medId:med.id,date:day,takenAtLocal,
                markedAt:new Date().toISOString(),status:'active',dailySlot:n};
              validateIntake(record);await changeIntake('marked',record);
            }
            await reload();showMessage('Отметка сохранена с фактическим временем.');
          }catch(e){await reload();showMessage(toError(e),'error')}
          finally{processing=false;box.disabled=false}
        });
      }
      wrap.append(schedule);
    }
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
          if(!confirm(`Изменить время приёма ${med.name}?`))return;
          update.disabled=true;
          try{
            const next={...i,takenAtLocal,updatedAt:new Date().toISOString()};
            await changeIntake('time_corrected',next,i);
            await reload();showMessage('Изменение времени записано в историю.');
          }catch(e){await reload();showMessage(toError(e),'error');}
        });
        const cancel=node('button','tiny-button danger','Отменить отметку');cancel.type='button';
        cancel.addEventListener('click',async()=>{
          if(!confirm(`Отменить отметку ${med.name}? История останется.`))return;
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
      if(intakeAuditNeedsReview(audit))item.append(node('div','audit-event','Проверка истории: события имеют одинаковое или некорректное время. Порядок не подтверждён.'));
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
    row.append(node('span','row-title',med?.name||'Препарат не найден'),
      node('span','row-subtitle',`${intakeLabel(i)} · ${intakeStatus(i)==='active'?'✓':'отменено'}`));
    history.append(row);
  }
}

function renderMedicationHistory(){
  const historyKindIcon=kind=>{
    const glyph={regular:'∞',course:'▦',asNeeded:'ϟ'}[kind];
    if(!glyph)return null;
    const icon=node('span',`ui01-kind-icon kind-${kind}`,glyph);
    icon.setAttribute('aria-hidden','true');
    return icon;
  };
  const host=$('intake-list');if(!host)return;host.replaceChildren();
  const kind=$('med-history-kind')?.value||'regular';
  const periodControl=$('med-history-period');
  // Approved type-specific filters: permanent 7d, courses 12 calendar months,
  // PRN 1/3 calendar months. Filters affect display only; never delete records.
  const allowed={regular:['7'],course:['365'],asNeeded:['30','90'],all:['7','30','90','365','all']}[kind]||['7'];
  if(periodControl){
    for(const option of periodControl.options)option.disabled=!allowed.includes(option.value);
    if(!allowed.includes(periodControl.value))periodControl.value=allowed[0];
  }
  const range=periodControl?.value||allowed[0];
  const now=new Date(),todayDay=dateLocal(now);
  const calendarCutoff=(months)=>{
    const d=new Date(now.getFullYear(),now.getMonth()-months,now.getDate());return dateLocal(d);
  };
  const cutoff=range==='all'?null:range==='365'?calendarCutoff(12):
    range==='90'?calendarCutoff(3):range==='30'?calendarCutoff(1):
    dateLocal(new Date(now.getFullYear(),now.getMonth(),now.getDate()-6));
  const state=$('intake-filter')?.value||'all';
  const year=String(now.getFullYear()),yearStart=year+'-01-01',yearEnd=year+'-12-31';
  const medsById=new Map(snapshot.medications.map(m=>[m.id,m]));
  const formatDay=d=>d&&/^\d{4}-\d{2}-\d{2}$/.test(d)?`${d.slice(8,10)}.${d.slice(5,7)}.${d.slice(0,4)}`:(d||'не указана');
  const addEventAudit=(item,i)=>{
    const events=eventsForIntake(i);
    if(intakeAuditNeedsReview(events))item.append(node('div','audit-event','Порядок событий не подтверждён: одинаковое или некорректное время.'));
    if(!events.length)item.append(node('div','audit-event','Старая запись: исходный журнал событий недоступен; время не подставлялось.'));
    for(const event of events)item.append(node('div','audit-event',`${new Intl.DateTimeFormat('ru-RU',{day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'}).format(new Date(event.at))} · ${eventLabel(event)}`));
  };
  if(kind==='course'){
    // One card per existing medication/course ID, including zero marked intakes.
    // A repeat course is never inferred from old intake timestamps.
    const dated=snapshot.medications.filter(m=>m.kind==='course'&&m.from&&m.to&&
      m.to>=(cutoff||'0000-01-01')&&m.from<=todayDay);
    const undated=snapshot.medications.filter(m=>m.kind==='course'&&(!m.from||!m.to));
    const withinYear=m=>m.to>=yearStart&&m.from<=yearEnd;
    const current=dated.filter(withinYear).sort((a,b)=>b.from.localeCompare(a.from));
    const previous=dated.filter(m=>!withinYear(m)).sort((a,b)=>b.from.localeCompare(a.from));
    host.append(node('p','form-hint','Курсовые · 1 год (12 календарных месяцев). Каждый курс с датами отображается даже без отметок. Отсутствие отметки не считается пропуском.'));
    const group=(title,meds,uncertain=false)=>{
      if(!meds.length)return;
      host.append(node('h4','history-group-heading',title));
      for(const med of meds){
        const details=node('details','intake-record course-history-card');
        const header=node('summary','course-history-summary');
        const glyph=historyKindIcon(med.kind);
        if(glyph)header.append(glyph);
        header.append(node('strong','',med.name));
        header.append(node('div','row-subtitle',`Начало: ${formatDay(med.from)} · окончание: ${formatDay(med.to)}`));
        if(!uncertain&&withinYear(med))header.append(node('span','history-year-badge',`Курс календарного года · ${year}`));
        details.append(header);
        if(uncertain)details.append(node('p','form-hint','Даты курса не указаны. Принадлежность к последним 12 месяцам не подтверждена; историю нужно проверить.'));
        else{
          const period=med.from>todayDay?'Даты курса ещё не наступили':med.to<todayDay?'Срок по датам завершён':'В пределах указанных дат';
          details.append(node('p','form-hint',period+' · это не подтверждает фактический приём или медицинское завершение курса.'));
        }
        const records=snapshot.intakes.filter(i=>i.medId===med.id&&(!cutoff||i.date>=cutoff)&&
          (state==='all'||intakeStatus(i)===state)).sort((a,b)=>b.date.localeCompare(a.date)||
          (b.takenAtLocal||'').localeCompare(a.takenAtLocal||''));
        const confirmed=records.filter(i=>intakeStatus(i)==='active').length;
        details.append(node('p','row-subtitle',`Подтверждённых отметок: ${confirmed}`));
        if(!records.length)details.append(node('p','empty','Отметок нет или они вне выбранного периода. Это не подтверждённый пропуск.'));
        for(const i of records){
          const entry=node('div','course-history-entry');
          entry.append(node('strong','',`${formatDay(i.date)} · ${intakeStatus(i)==='active'?'Приём подтверждён':'Отметка отменена'}`));
          if(i.takenAtLocal)entry.append(node('div','row-subtitle',`Фактическое время: ${i.takenAtLocal.slice(11)}`));
          addEventAudit(entry,i);details.append(entry);
        }
        host.append(details);
      }
    };
    group(`Курсы календарного ${year} года`,current);
    group('Другие курсы за последние 12 месяцев',previous);
    group('Даты требуют уточнения (вне подтверждённой выборки)',undated,true);
    if(!dated.length&&!undated.length)host.append(node('p','empty','Курсов за выбранный период нет.'));
    return;
  }
  const rows=[...snapshot.intakes].filter(i=>{
    const med=medsById.get(i.medId);if(!med)return false;
    const day=i.takenAtLocal?.slice(0,10)||i.date;
    // PRN history is actual active taken episodes, not cancelled plans.
    return (kind==='all'||med.kind===kind)&&(!cutoff||day>=cutoff)&&
      (kind==='asNeeded'?intakeStatus(i)==='active':state==='all'||intakeStatus(i)===state);
  }).sort((a,b)=>(b.takenAtLocal||b.date).localeCompare(a.takenAtLocal||a.date)||b.markedAt.localeCompare(a.markedAt));
  const label=kind==='regular'?'Постоянные · последние 7 дней':kind==='asNeeded'?`Ситуативные · ${range==='90'?'3 месяца':'1 месяц'} · фактические приёмы`:`История · ${rows.length} записей`;
  host.append(node('p','form-hint',label+' · отсутствие отметки не считается подтверждённым пропуском.'));
  if(!rows.length){host.append(node('p','empty','За выбранный период записей нет.'));return;}
  for(const i of rows){
    const med=medsById.get(i.medId),item=node('article',`intake-record ${intakeStatus(i)==='cancelled'?'cancelled':''}`);
    const header=node('div','intake-record-head'),main=node('div');
    const glyph=historyKindIcon(med.kind);
    if(glyph)main.append(glyph);
    main.append(node('strong','',`${med.name} · ${intakeStatus(i)==='active'?'Приём подтверждён':'Отметка отменена'}`));
    const stamp=i.takenAtLocal?dateLabel(i.takenAtLocal):`${i.date} · время неизвестно`;
    main.append(node('div','row-subtitle',`${stamp} · ${KINDS[med.kind]}`));
    if(Number.isInteger(i.dailySlot))main.append(node('div','row-subtitle',`Слот: ${medSlotLabel(medDailyTarget(med)||i.dailySlot,i.dailySlot)}`));
    if(med.kind==='asNeeded'&&typeof i.reason==='string'&&i.reason.trim())main.append(node('div','row-subtitle',`Причина: ${i.reason.trim()}`));
    header.append(main);item.append(header);addEventAudit(item,i);host.append(item);
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
    const r=node('div','overview-row'),progress=medDailyProgress(med,active);
    const summary=progress.goal===null?(active.length?`✓ Отмечено: ${active.length}`:'○ Нет отметки'):
      `Отметки: ${progress.checked}/${progress.goal} · фактов: ${progress.actual}`;
    r.append(node('span','row-title',med.name),node('span','row-subtitle',summary));
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
  if(!m||typeof m!=='object'||!validId(m.id)||typeof m.name!=='string'||(m.name.trim().length<2 || /[<>\u0000-\u001f]/.test(m.name))||m.name.length>100||typeof m.dose!=='string'||m.dose.length>60||!Object.hasOwn(KINDS,m.kind)||!validInstant(m.createdAt)||!(m.from===null||validDate(m.from))||!(m.to===null||validDate(m.to))||(m.from&&m.to&&m.from>m.to))throw Error('Некорректная запись препарата');
  validatedMedExtension(m);
  medDailyTarget(m);
}
function validateIntake(i){
  if(!i||typeof i!=='object'||!validId(i.id)||!validId(i.medId)||!validDate(i.date)||!validInstant(i.markedAt)||
    (i.takenAtLocal!==undefined&&(!validDateTime(i.takenAtLocal)||!i.takenAtLocal.startsWith(i.date+'T')))||
    (i.dailySlot!==undefined&&(!Number.isInteger(i.dailySlot)||i.dailySlot<1||i.dailySlot>3))||
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
// CP39: strict unknown-field policy for EXTERNAL backup files only.
// Local IndexedDB records and exports are not modified by this gate.
function assertKnownBackupFields(envelope){
  const allowedEnvelope=['format','version','exportedAt','data','sha256'];
  const allowedRecords={
    pressures:['id','systolic','diastolic','pulse','dateTime','note','arm','createdAt'],
    intakes:['id','medId','date','markedAt','takenAtLocal','dailySlot','updatedAt','status','cancelledAt','reason'],
    intakeEvents:['id','intakeId','medId','action','at','oldTakenAtLocal','newTakenAtLocal']
  };
  const assertFields=(record,allowed,label)=>{
    if(!record||typeof record!=='object'||Array.isArray(record))throw Error('Некорректная запись резервной копии: '+label);
    for(const key of Object.keys(record))if(!allowed.includes(key))
      throw Error('Неизвестное поле резервной копии ('+label+'): '+key);
  };
  assertFields(envelope,allowedEnvelope,'envelope');
  if(!envelope.data||typeof envelope.data!=='object'||Array.isArray(envelope.data))
    throw Error('Некорректные данные резервной копии');
  for(const [section,allowed] of Object.entries(allowedRecords)){
    const rows=envelope.data[section];
    if(section==='intakeEvents'&&(envelope.version===1||envelope.version===2)&&rows===undefined)continue;
    if(!Array.isArray(rows))throw Error('Отсутствует таблица резервной копии: '+section);
    for(const row of rows)assertFields(row,allowed,section);
  }
}

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

let safetyLastScan=null;
let verifiedExternalBackupHash=null;
function safetyWrite(id,value,cls=''){
 const el=$(id);if(!el)return;
 el.textContent=value;el.className=cls;
}
function safetyNeedsNewCheck(){
 safetyLastScan=null;verifiedExternalBackupHash=null;
 safetyWrite('safety-db-status','Записи изменились: повторите проверку','safety-warn');
 safetyWrite('safety-copy-status','После изменений новая внешняя копия не проверена','safety-warn');
}
function safetyExternalBackupVerified(expected,contentMatches){
 verifiedExternalBackupHash=contentMatches?expected:null;
 safetyWrite('safety-copy-status',
   contentMatches?'Выбранный JSON совпал с текущей базой; сохранность файла вне PWA зависит от места хранения':
     'JSON прошёл SHA-256, но отличается от текущей базы (копия может быть старой)',
   contentMatches?'safety-good':'safety-warn');
}
async function reportBrowserStorage(){
 if(!navigator.storage){safetyWrite('safety-browser-status','Браузер не сообщает статус хранилища','safety-warn');return;}
 try{
   const status=typeof navigator.storage.persisted==='function'
      ?await navigator.storage.persisted():null;
   const estimate=typeof navigator.storage.estimate==='function'
      ?await navigator.storage.estimate():null;
   const amount=estimate&&Number.isFinite(estimate.usage)?
      ' · занято примерно '+(estimate.usage/1024/1024).toFixed(2)+' МБ':'';
   safetyWrite('safety-browser-status',
     status===true?'Браузер сообщает persistent storage'+amount:
     status===false?'Нет гарантии постоянного хранения'+amount:
     'Статус браузерного хранилища недоступен'+amount,
     status===true?'safety-good':'safety-warn');
 }catch(e){safetyWrite('safety-browser-status','Не удалось прочитать статус хранения','safety-warn');}
}
async function checkLocalIntegrity(){
 const b=$('safety-check');if(b)b.disabled=true;
 safetyWrite('safety-db-status','Проверяем все четыре журнала…');
 try{
   const data=await readBackupSnapshot();
   const total=validateBackupData(data,false);
   const digest=await sha256(data);
   safetyLastScan={total,digest,at:new Date().toISOString()};
   safetyWrite('safety-db-status',
     'PASS · '+total+' записей · SHA-256 '+digest.slice(0,12)+'…','safety-good');
   return safetyLastScan;
 }catch(err){
   safetyLastScan=null;
   safetyWrite('safety-db-status','FAIL · '+toError(err),'safety-bad');
   throw err;
 }finally{if(b)b.disabled=false;}
}
function safeIntegrityCheckOnClick(){
 checkLocalIntegrity().catch(err=>showMessage(
   'Проверка локальной базы не пройдена: '+toError(err)+'. Не удаляйте данные, сохраните копию для диагностики.','error'));
}

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
  const times=new Map(),seenSlots=new Map();
  for(const i of [...(includeLocal?snapshot.intakes:[]),...data.intakes]){
    if(!meds.has(i.medId))throw Error('Отметка без препарата');
    if(intakeStatus(i)==='active'&&i.dailySlot!==undefined){
      const key=i.medId+'|'+i.date+'|'+i.dailySlot;
      if(seenSlots.has(key)&&seenSlots.get(key)!==i.id)throw Error('Повтор номера приёма в копии');
      seenSlots.set(key,i.id);
    }
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
    const existingSlots=new Map(req.result.filter(i=>intakeStatus(i)==='active'&&i.dailySlot!==undefined)
      .map(i=>[i.medId+'|'+i.date+'|'+i.dailySlot,i.id]));
    for(const i of data.intakes){
      if(intakeStatus(i)==='active'&&i.dailySlot!==undefined){
        const other=existingSlots.get(i.medId+'|'+i.date+'|'+i.dailySlot);
        if(other&&other!==i.id){fail('Повтор номера приёма относительно текущей базы');return;}
      }
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
async function onPressureSubmit(e){e.preventDefault();const sys=Number($('systolic').value),dia=Number($('diastolic').value),pulse=$('pulse').value.trim()?Number($('pulse').value):null,dt=$('pressure-datetime').value,note=$('pressure-note').value.trim();try{const p={id:crypto.randomUUID(),systolic:sys,diastolic:dia,pulse,dateTime:dt,note,arm:'right',createdAt:new Date().toISOString()};validatePressure(p);await addRecord('pressures',p);safetyNeedsNewCheck();dismissMobileKeyboard();e.target.reset();$('pressure-datetime').value=dateTimeLocal(new Date());updateAllWheelTriggers();await reload();showMessage('Измерение сохранено и повторно прочитано из локальной базы.')}catch(err){showMessage(toError(err),'error')}}
async function onMedSubmit(e){
  e.preventDefault();
  const p={id:crypto.randomUUID(),name:$('med-name').value.trim(),dose:$('med-dose').value.trim(),kind:$('med-kind').value,
    from:$('course-from').value||null,to:$('course-to').value||null,createdAt:new Date().toISOString()};
  if(p.kind!=='course'){p.from=null;p.to=null;}
  const rawTarget=$('med-daily-target').value;
  if(rawTarget!==''&&p.kind!=='asNeeded')p.dailyIntakes=Number(rawTarget);
  const raw=$('med-strength').value.trim(),strength=raw===''?null:Number(raw),unit=$('med-unit').value,form=$('med-form-factor').value;
  if(raw!==''||unit!==''||form!=='')p.pae04v021={strength,unit,form};
  try{
    validateMed(p);await window.PAE04MedicationGuard.saveMedicationAtomic(db,p,verifyRecordAfterWrite);safetyNeedsNewCheck();e.target.reset();$('course-fields').hidden=true;updateAllWheelTriggers();await reload();
    showMessage('Препарат сохранён и повторно прочитан из локальной базы.');
  }catch(err){showMessage(toError(err),'error');}
}
async function exportBackup(){try{const backup=await createBackup();downloadFile(`PAE04-PERSONAL-BACKUP-${today()}.json`,new Blob([JSON.stringify(backup,null,2)],{type:'application/json'}));showMessage('Копия сформирована и передана браузеру на скачивание. Проверьте наличие файла в «Загрузках».')}catch(e){showMessage(toError(e),'error')}}
let backupVerifySequence=0;
async function verifyDownloadedBackup(e){
  const sequence=++backupVerifySequence,view=$('verify-result');
  view.replaceChildren();
  const file=e.target.files?.[0];if(!file)return;
  verifiedExternalBackupHash=null;
  safetyWrite('safety-copy-status','Проверяем выбранный JSON…','safety-warn');
  try{
    if(file.size>5*1024*1024)throw Error('Максимальный размер проверяемого JSON — 5 МБ');
    const parsed=JSON.parse(await file.text());if(sequence!==backupVerifySequence)return;
    if(!parsed||parsed.format!==BACKUP_FORMAT||!validBackupVersion(parsed.version)||
      !validInstant(parsed.exportedAt)||!parsed.data||
      typeof parsed.sha256!=='string'||!/^[a-f0-9]{64}$/.test(parsed.sha256))throw Error('Неверный формат копии');
    const {sha256:expected,...body}=parsed;
    if(await sha256(body)!==expected)throw Error('SHA-256 не совпадает: файл изменён или повреждён');
    if(sequence!==backupVerifySequence)return;
    assertKnownBackupFields(parsed);
    const normalized=normalizedBackupData(parsed.version,parsed.data);
    const total=validateBackupData(normalized,false);
    if(sequence!==backupVerifySequence)return;
    const current=await readBackupSnapshot();
    if(sequence!==backupVerifySequence)return;
    safetyExternalBackupVerified(expected,canonical(current)===canonical(normalized));
    const details=STORE_NAMES.map(name=>name+': '+normalized[name].length).join(' · ');
    view.append(node('p','verify-pass','PASS · SHA-256 совпадает · '+total+' записей'),
      node('p','form-hint','Файл: '+file.name+' · '+details),
      node('p','form-hint','Файл проверен без импорта. Это не шифрование. Защитите копию от посторонних.'));
  }catch(err){if(sequence!==backupVerifySequence)return;safetyWrite('safety-copy-status','Выбранный JSON отклонён: актуальная внешняя копия не подтверждена','safety-bad');view.append(node('p','verify-fail','FAIL · '+toError(err)));}
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
    assertKnownBackupFields(parsed);
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
    downloadFile(`PAE04-PERSONAL-PREIMPORT-CHECKPOINT-${today()}.json`,new Blob([JSON.stringify(backup,null,2)],{type:'application/json'}));
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
    if(!confirm(`Импортировать ${plan.fresh} новых записей из формата v${version}?\nБез удаления старых записей. Защитная копия уже сформирована.`))return;
    if(pendingImport!==selected)return;
    const count=await atomicMerge(data);
    const verifyAfterImport=await readBackupSnapshot();
    for(const store of STORE_NAMES){
      const written=new Map(verifyAfterImport[store].map(x=>[x.id,x]));
      for(const item of data[store])if(canonical(written.get(item.id))!==canonical(item))
        throw Error('Импорт завершился, но проверка восстановленной записи не пройдена. Не импортируйте повторно до проверки журнала.');
    }
    safetyNeedsNewCheck();
    pendingImport=null;resetImportCheckpoint();$('import-file').value='';
    $('import-preview').replaceChildren(node('div',null,`Добавлено ${count} записей; старые записи не изменены.`));
    await reload();showMessage('Резервная копия импортирована.');
  }catch(e){showMessage('Импорт прерван: '+toError(e),'error');}
  finally{syncImportReady();}
}


// PAE-04 v05.5.1: keyboard-safe bottom navigation. The iOS software keyboard
// belongs to Safari; we never try to remove the operating-system autofill bar.
// Instead, remove our sticky nav while editable fields/keyboard are active.
const EDITABLE_MOBILE_SELECTOR='input:not([type="checkbox"]):not([type="radio"]):not([type="hidden"]):not([type="file"]):not(.wheel-source),textarea,select';
function mobileKeyboardViewportIsReduced(){
  const vv=window.visualViewport;
  return !!(vv&&window.innerWidth<=740&&
    window.innerHeight-vv.height-vv.offsetTop>160);
}
function syncMobileKeyboardUI(){
  const focused=document.activeElement;
  const editing=focused instanceof HTMLElement&&focused.matches(EDITABLE_MOBILE_SELECTOR);
  document.body.classList.toggle('keyboard-editing',editing||mobileKeyboardViewportIsReduced());
  document.body.classList.toggle('note-editing',focused?.id==='pressure-note');
}
function dismissMobileKeyboard(){
  if(document.activeElement instanceof HTMLElement)document.activeElement.blur();
  // iOS can shrink visualViewport until the keyboard close animation completes.
  syncMobileKeyboardUI();
}
function setupMobileKeyboardUI(){
  document.addEventListener('focusin',syncMobileKeyboardUI,true);
  document.addEventListener('focusout',()=>setTimeout(syncMobileKeyboardUI,50),true);
  window.addEventListener('resize',syncMobileKeyboardUI,{passive:true});
  if(window.visualViewport){
    window.visualViewport.addEventListener('resize',syncMobileKeyboardUI,{passive:true});
    window.visualViewport.addEventListener('scroll',syncMobileKeyboardUI,{passive:true});
  }
  // A tap in the history area should dismiss the old form keyboard before
  // scrolling/searching; do not change input values or save any record.
  const pressurePage=$('page-pressure');
  let pressureSwipeStart=null;
  const pressureEditing=()=>{
    const active=document.activeElement;
    return window.innerWidth<=740&&active instanceof HTMLElement&&
      active.matches(EDITABLE_MOBILE_SELECTOR)&&$('pressure-form').contains(active);
  };
  pressurePage.addEventListener('pointerdown',event=>{
    if(pressureEditing()&&!event.target.closest('#pressure-form,#pressure-keyboard-done'))dismissMobileKeyboard();
  },{passive:true});
  pressurePage.addEventListener('touchstart',event=>{
    pressureSwipeStart=null;
    if(!pressureEditing()||!event.touches.length)return;
    // Do not dismiss merely while editing/scrolling inside a textarea/input.
    if(event.target.closest('input,textarea,select,.wheel-scroll'))return;
    pressureSwipeStart={y:event.touches[0].clientY};
  },{passive:true});
  pressurePage.addEventListener('touchmove',event=>{
    if(!pressureSwipeStart||!pressureEditing()||!event.touches.length)return;
    if(pressureSwipeStart.y-event.touches[0].clientY<55)return;
    const history=$('pressure-list').closest('.panel');
    const viewportHeight=window.visualViewport?.height||window.innerHeight;
    if(history.getBoundingClientRect().top<=viewportHeight+110){
      pressureSwipeStart=null;
      dismissMobileKeyboard();
    }
  },{passive:true});
  for(const eventName of ['touchend','touchcancel']){
    pressurePage.addEventListener(eventName,()=>{pressureSwipeStart=null;},{passive:true});
  }
  $('pressure-keyboard-done').addEventListener('click',dismissMobileKeyboard);
  const nextById={systolic:'diastolic',diastolic:'pulse',pulse:'pressure-note'};
  for(const [id,nextId] of Object.entries(nextById)){
    $(id).addEventListener('keydown',event=>{
      if(event.key!=='Enter'||event.isComposing)return;
      event.preventDefault();
      $(nextId).focus({preventScroll:false});
    });
  }
  syncMobileKeyboardUI();
}

function connectStatus(state='checking'){const el=$('connection-status');const label=state==='ready'?'Локальная база доступна':state==='error'?'Локальная база недоступна':'Проверяем локальную базу';const cls=state==='ready'?'online':state==='error'?'offline':'';el.replaceChildren(node('span',`status-dot ${cls}`),document.createTextNode(label));}
async function init(){
  // Medication writes fail closed if the optional guard cannot load.
  // Pressure, history and backups remain available.
  try {
    if(!window.PAE04MedicationGuard)throw Error('Модуль проверки лекарств недоступен');
    window.PAE04MedicationGuard.mount({form:$('med-form'),nameInput:$('med-name'),getExisting:()=>snapshot.medications});
  } catch(err) {
    const medSubmit=$('med-form').querySelector('button[type=submit]');
    if(medSubmit)medSubmit.disabled=true;
    showMessage('Добавление лекарств временно заблокировано: '+toError(err),'error');
  }
document.querySelectorAll('[data-page]').forEach(b=>b.addEventListener('click',()=>navigate(b.dataset.page)));document.querySelectorAll('[data-go]').forEach(b=>b.addEventListener('click',()=>navigate(b.dataset.go)));connectStatus();$('pressure-datetime').value=dateTimeLocal(new Date());$('intake-date').value=today();setupWheelPicker();setupMobileKeyboardUI();$('pressure-form').addEventListener('submit',onPressureSubmit);$('med-form').addEventListener('submit',onMedSubmit);$('intake-date').addEventListener('change',renderMedications);$('pressure-list-period').addEventListener('change',renderPressure);$('pressure-chart-period').addEventListener('change',renderPressure);$('pressure-search').addEventListener('input',renderPressure);$('intake-filter').addEventListener('change',renderMedicationHistory);$('med-history-kind').addEventListener('change',e=>{$('med-history-period').value=({regular:'7',course:'365',asNeeded:'30',all:'all'})[e.target.value];renderMedicationHistory()});$('med-history-period').addEventListener('change',renderMedicationHistory);$('med-search').addEventListener('input',renderMedications);$('catalog-search').addEventListener('input',e=>{if(["Тестовый препарат 01","Тестовый препарат 02","Тестовый препарат 03","Тестовый препарат 04","Тестовый препарат 05","Тестовый препарат 06","Тестовый препарат 07","Тестовый препарат 08","Тестовый препарат 09","Тестовый препарат 10"].includes(e.target.value)){$('med-name').value=e.target.value;$('med-name').dispatchEvent(new Event('input',{bubbles:true}));}});$('med-kind').addEventListener('change',e=>{$('course-fields').hidden=e.target.value!=='course';const schedule=$('med-daily-target').closest('label');schedule.hidden=e.target.value==='asNeeded';if(e.target.value==='asNeeded')$('med-daily-target').value=''});$('safety-check').addEventListener('click',safeIntegrityCheckOnClick);$('export-button').addEventListener('click',exportBackup);$('verify-file').addEventListener('change',verifyDownloadedBackup);$('import-file').addEventListener('change',previewImport);$('checkpoint-button').addEventListener('click',downloadImportCheckpoint);$('checkpoint-ack').addEventListener('change',syncImportReady);$('import-button').addEventListener('click',applyImport);try{db=await openDB();await reload();connectStatus('ready');await reportBrowserStorage();try{await checkLocalIntegrity()}catch(err){showMessage('Локальная база не прошла проверку: '+toError(err),'error')}if('serviceWorker'in navigator){try{await navigator.serviceWorker.register('./sw.js');}catch(err){showMessage(`Локальная база работает, но офлайн-кэш не включился: ${toError(err)}`,'warn')}}}catch(e){connectStatus('error');showMessage(`Не удалось открыть локальную базу: ${toError(e)}`,'error');document.querySelectorAll('form button[type=submit],#export-button,#import-button').forEach(b=>b.disabled=true)}}
document.addEventListener('DOMContentLoaded',init);
