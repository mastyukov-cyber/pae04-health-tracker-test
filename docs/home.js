'use strict';
/* PAE-04 CP-UI01. Synthetic-only home, existing DB and audit flow unchanged. */
(function () {
  if (typeof PAE04_V021_TEST_ONLY === 'undefined' || PAE04_V021_TEST_ONLY !== true) {
    throw Error('CP-UI01 is allowed only in a synthetic TEST candidate');
  }
  const FONT_KEY = 'pae04-cp-ui01-font-size-v1';
  const SCALES = [1, 1.07, 1.14, 1.22, 1.32];
  const TYPE_NAMES = {regular:'Постоянные',course:'Курсовые',asNeeded:'Ситуативные'};
  let scaleIndex=2;
  let dayLast='';
  let savingIds=new Set();
  const el=id=>document.getElementById(id);
  const element=(tag,cls,value)=>{
    const e=document.createElement(tag);
    if(cls)e.className=cls;
    if(value!==undefined)e.textContent=String(value);
    return e;
  };
  const localDate=d=>dateLocal(d);
  const priorDate=day=>{
    const parts=day.split('-').map(Number);
    return localDate(new Date(parts[0],parts[1]-1,parts[2]-1,12));
  };
  const humanDate=day=>new Intl.DateTimeFormat('ru-RU',{weekday:'long',day:'numeric',month:'long'}).format(new Date(day+'T12:00:00'));
  const activeIntake=i=>intakeStatus(i)==='active';
  function timesFor(medId,day) {
    return snapshot.intakes.filter(i=>i.medId===medId && i.date===day && activeIntake(i))
      .map(i=>i.takenAtLocal && i.takenAtLocal.startsWith(day+'T')?i.takenAtLocal.slice(11,16):null)
      .filter(Boolean).sort();
  }
  function readFont() {
    try {
      const raw=localStorage.getItem(FONT_KEY);
      if(raw!==null){
        const n=Number(raw);
        if(Number.isInteger(n)&&n>=0&&n<SCALES.length)scaleIndex=n;
      }
    } catch (_) { /* private browsing: retain working controls without persistence */ }
    applyFont();
  }
  function applyFont(){
    document.documentElement.style.setProperty('--ht-home-scale',String(SCALES[scaleIndex]));
    const indicator=el('ui01-font-label');
    if(indicator)indicator.textContent=String(scaleIndex+1)+' / '+SCALES.length;
    const less=el('ui01-font-less'),more=el('ui01-font-more');
    if(less)less.disabled=scaleIndex===0;
    if(more)more.disabled=scaleIndex===SCALES.length-1;
  }
  function adjustFont(delta){
    scaleIndex=Math.max(0,Math.min(SCALES.length-1,scaleIndex+delta));
    try{localStorage.setItem(FONT_KEY,String(scaleIndex));}catch(_){}
    applyFont();
  }
  function drawPressure(day,yday){
    const holder=el('ui01-pressure');if(!holder)return;
    holder.replaceChildren();
    const heading=element('h2','ui01-card-title','Давление сегодня');
    holder.append(heading);
    const todayRows=snapshot.pressures.filter(p=>p.dateTime.slice(0,10)===day)
      .sort((a,b)=>b.dateTime.localeCompare(a.dateTime));
    if(todayRows.length===0){
      holder.append(element('p','ui01-empty','Сегодня измерений пока нет'));
    }else{
      const list=element('div','ui01-reading-list');
      for(const p of todayRows){
        const row=element('div','ui01-reading');
        row.append(
          element('strong','ui01-bp',String(p.systolic)+' / '+String(p.diastolic)),
          element('span','ui01-reading-meta',p.dateTime.slice(11,16)+' · '+(p.pulse==null?'Пульс не указан':'Пульс '+p.pulse))
        );
        list.append(row);
      }
      holder.append(list);
    }
    const old=snapshot.pressures.filter(p=>p.dateTime.slice(0,10)===yday);
    if(old.length){
      const mean=key=>Math.round(old.reduce((a,p)=>a+p[key],0)/old.length);
      const pulses=old.filter(p=>p.pulse!==null&&Number.isFinite(p.pulse));
      const context=element('div','ui01-yesterday');
      context.append(element('span','ui01-muted',old.length===1?'Вчера · одно измерение':'Вчера · среднее за '+old.length+' измерения'));
      context.append(element('strong','ui01-yesterday-bp',String(mean('systolic'))+' / '+String(mean('diastolic'))+' мм рт. ст.'));
      if(pulses.length)context.append(element('span','ui01-muted','Пульс в среднем: '+Math.round(pulses.reduce((a,p)=>a+p.pulse,0)/pulses.length)));
      holder.append(context);
    }
    const add=element('button','primary ui01-wide-button','＋ Добавить измерение');
    add.type='button';
    add.addEventListener('click',()=>navigate('pressure'));
    holder.append(add);
  }
  function courseActive(m,day) {
    if(m.kind!=='course')return false;
    if(!m.from&&!m.to)return false; // Undated courses remain in full journal, not asserted as active.
    return (!m.from||day>=m.from)&&(!m.to||day<=m.to);
  }
  function onHomeIntake(m,button) {
    if(savingIds.has(m.id))return;
    const day=today();
    if(timesFor(m.id,day).length){navigate('meds');return;}
    if(m.kind==='course'&&!courseActive(m,day)){navigate('meds');return;}
    const time=clockLocal(new Date());
    if(!window.confirm('Подтвердить приём «'+m.name+'» сегодня в '+time+'?'))return;
    savingIds.add(m.id);button.disabled=true;
    const record={id:crypto.randomUUID(),medId:m.id,date:day,takenAtLocal:day+'T'+time,
      markedAt:new Date().toISOString(),status:'active'};
    Promise.resolve().then(()=>{
      validateIntake(record);
      return changeIntake('marked',record);
    }).then(async()=>{
      safetyNeedsNewCheck();
      await reload();
      showMessage('Приём отмечен в '+time+'. При необходимости исправьте время в журнале лекарств.');
    }).catch(err=>showMessage('Не удалось сохранить отметку: '+toError(err),'error'))
      .finally(()=>{savingIds.delete(m.id);button.disabled=false;drawHome();});
  }
  function medRow(m,day,yday){
    const row=element('div','ui01-med-row');
    const current=timesFor(m.id,day);
    const previous=(m.kind==='regular'||(m.kind==='course'&&courseActive(m,yday)))?timesFor(m.id,yday):[];
    const desc=element('div','ui01-med-description');
    desc.append(element('strong','ui01-med-name',m.name));
    if(m.dose)desc.append(element('span','ui01-personal-dose',m.dose));
    if(m.kind==='asNeeded')desc.append(element('span','ui01-muted','По необходимости'));
    if(previous.length)desc.append(element('span','ui01-yesterday-time','Вчера принято: '+previous.join(', ')));
    if(current.length)desc.append(element('span','ui01-today-time','Сегодня: '+current.join(', ')));
    const btn=element('button','ui01-check'+(current.length?' is-taken':''),current.length?'✓':'○');
    btn.type='button';
    btn.setAttribute('aria-label',current.length?'Открыть отметки приёма '+m.name:'Отметить приём сейчас: '+m.name);
    btn.setAttribute('aria-pressed',current.length?'true':'false');
    btn.addEventListener('click',()=>onHomeIntake(m,btn));
    row.append(btn,desc);
    return row;
  }
  function drawMeds(day,yday){
    const host=el('ui01-meds');if(!host)return;host.replaceChildren();
    host.append(element('h2','ui01-section-title','Лекарства сегодня'));
    let visible=0;
    for(const kind of ['regular','course','asNeeded']){
      const list=snapshot.medications.filter(m=>m.kind===kind&&(kind!=='course'||courseActive(m,day)))
        .sort((a,b)=>a.name.localeCompare(b.name,'ru'));
      if(!list.length)continue;
      visible++;
      const card=element('section','ui01-card ui01-med-group');
      const h=element('h3','ui01-group-title',TYPE_NAMES[kind]);
      card.append(h);
      for(const med of list)card.append(medRow(med,day,yday));
      host.append(card);
    }
    if(!visible)host.append(element('p','ui01-empty','На сегодня лекарств нет. Добавьте препарат в разделе «Лекарства».'));
    const note=element('p','ui01-note','○ — приём не отмечен. Это не означает, что препарат пропущен. Для повторного приёма или исправления времени откройте журнал лекарств.');
    host.append(note);
  }
  function drawHome(){
    if(!el('ui01-pressure'))return;
    const day=today(),yday=priorDate(day);
    dayLast=day;
    el('ui01-date').textContent=humanDate(day);
    drawPressure(day,yday);
    drawMeds(day,yday);
  }
  const originalOverview=renderOverview;
  renderOverview=function(){
    originalOverview();
    drawHome();
  };
  document.addEventListener('DOMContentLoaded',()=>{
    readFont();
    el('ui01-font-less').addEventListener('click',()=>adjustFont(-1));
    el('ui01-font-more').addEventListener('click',()=>adjustFont(1));
    drawHome();
    document.addEventListener('visibilitychange',()=>{if(!document.hidden)drawHome();});
    window.addEventListener('focus',drawHome);
    window.setInterval(()=>{if(today()!==dayLast)drawHome();},60000);
  });
  window.PAE04CPUI01={render:drawHome,priorDate,courseActive};
})();