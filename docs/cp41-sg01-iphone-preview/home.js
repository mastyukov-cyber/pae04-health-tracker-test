'use strict';
/* PAE-04 CP-UI01. Synthetic-only home, existing DB and audit flow unchanged. */
(function () {
  if (typeof PAE04_V021_TEST_ONLY === 'undefined' || PAE04_V021_TEST_ONLY !== true) {
    throw Error('CP-UI01 is allowed only in a synthetic TEST candidate');
  }
  const FONT_KEY = 'pae04-cp-ui01-font-size-v1';
  const THEME_KEY = 'pae04-iphone-theme-v1';
  const COMPACT_KEY = 'pae04-iphone-compact-v1';
  const SCALES = [0.90, 0.96, 1, 1.14, 1.28];
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
  function applyDisplaySettings(){
    let theme='system',compact=true;
    try{theme=localStorage.getItem(THEME_KEY)||'system';compact=(localStorage.getItem(COMPACT_KEY)??'true')==='true';}catch(_){}
    if(!['system','light','dark'].includes(theme))theme='system';
    if(theme==='system')document.documentElement.removeAttribute('data-appearance');
    else document.documentElement.setAttribute('data-appearance',theme);
    document.documentElement.classList.toggle('compact-view',compact);
    const themeSelect=el('display-theme'),compactCheck=el('compact-view');
    if(themeSelect)themeSelect.value=theme;if(compactCheck)compactCheck.checked=compact;
  }
  function adjustFont(delta){
    scaleIndex=Math.max(0,Math.min(SCALES.length-1,scaleIndex+delta));
    try{localStorage.setItem(FONT_KEY,String(scaleIndex));}catch(_){}
    applyFont();
  }
  // HOME-V7: presentation-only projection over existing right-arm manual records.
  function v7PressureView(pressures,day){
    const rows=[...pressures].filter(p=>p&&typeof p.dateTime==='string'&&
      Number.isFinite(p.systolic)&&Number.isFinite(p.diastolic))
      .sort((a,b)=>a.dateTime.localeCompare(b.dateTime));
    const todayRows=rows.filter(p=>p.dateTime.slice(0,10)===day);
    const previous=priorDate(day),yesterday=rows.filter(p=>p.dateTime.slice(0,10)===previous);
    const mean=(records,key)=>{
      const values=records.map(p=>p[key]).filter(Number.isFinite);
      return values.length?Math.round(values.reduce((a,b)=>a+b,0)/values.length):null;
    };
    if(todayRows.length){
      return {source:'today',latest:todayRows[todayRows.length-1],
        label:'Сегодня · '+todayRows[todayRows.length-1].dateTime.slice(11,16),
        average:todayRows.length>=2?{systolic:mean(todayRows,'systolic'),
          diastolic:mean(todayRows,'diastolic'),pulse:mean(todayRows,'pulse'),
          count:todayRows.length}:null};
    }
    if(yesterday.length){
      // UX v2.3: last actual reading, not an inferred previous-day mean.
      const lastYesterday=yesterday[yesterday.length-1];
      return {source:'yesterday',latest:lastYesterday,
        label:'Вчера · '+lastYesterday.dateTime.slice(11,16),average:null};
    }
    const last=rows[rows.length-1];
    return {source:last?'older':'empty',latest:last||null,
      label:last?'Последний замер · '+humanDate(last.dateTime.slice(0,10))+' · '+last.dateTime.slice(11,16):
        'Измерений пока нет',average:null};
  }
  // Approved UX v2.3: consistent outline icons, not Unicode substitutes.
  function ux23OutlineIcon(kind){
    const paths={"regular":"<path d=\"M6 16c5 0 7-8 12-8a4 4 0 0 1 0 8c-5 0-7-8-12-8a4 4 0 1 0 0 8\"/>","course":"<rect x=\"3\" y=\"5\" width=\"18\" height=\"16\" rx=\"2\"/><path d=\"M16 3v4M8 3v4M3 10h18M8 14h.01M12 14h.01M16 14h.01M8 18h.01M12 18h.01\"/>","asNeeded":"<path d=\"m13 2-3 8h7l-6 12 1-9H5l8-11Z\"/>","activity":"<path d=\"M2 12h4l3-7 4 14 3-7h6\"/>"};
    if(!Object.prototype.hasOwnProperty.call(paths,kind))return null;
    const icon=element('span',kind==='activity'?'ux23-pulse-icon':'ui01-kind-icon kind-'+kind);
    icon.setAttribute('aria-hidden','true');
    icon.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'+paths[kind]+'</svg>';
    return icon;
  }
  function drawPressure(day){
    const holder=el('ui01-pressure');if(!holder)return;
    holder.replaceChildren();
    const title=element('h2','ui01-card-title ui01-v7-pressure-title','Последний замер');
    const icon=element('span','ui01-tonometer-icon');
    icon.innerHTML='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64" fill="none" stroke="#5486B9" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><rect x="7" y="9" width="33" height="43" rx="7"/><rect x="12" y="15" width="23" height="19" rx="3"/><path d="M17 22h12M17 27h8"/><circle cx="24" cy="43" r="3"/><path d="M40 43c11-2 7 10 14 9"/><rect x="49" y="39" width="12" height="20" rx="4"/></svg>';
    title.prepend(icon);holder.append(title);
    // Approved iPhone UX v2.3: last actual reading and today's mean are separate cards.
    const avgHost=el('ui01-pressure-average');
    if(avgHost){avgHost.replaceChildren();avgHost.hidden=true;}
    const view=v7PressureView(snapshot.pressures,day);
    if(view.latest){
      const grid=element('div','ui01-v7-pressure-grid');
      const left=element('div','ui01-v7-pressure-main');
      left.append(element('strong','ui01-v7-bp-primary',
        view.latest.systolic+' / '+view.latest.diastolic));
      left.append(element('span','ui01-v7-reading-meta',view.label));
      if(Number.isFinite(view.latest.pulse)){
        const pulse=element('span','ui01-v7-pulse','Пульс '+view.latest.pulse);
        pulse.prepend(ux23OutlineIcon('activity'));
        pulse.setAttribute('aria-label','Пульс '+view.latest.pulse+' ударов в минуту');
        left.append(pulse);
      }else left.append(element('span','ui01-v7-reading-meta','Пульс не указан'));
      grid.append(left);
      holder.append(grid);
      if(view.average && avgHost){
        const heading=element('h2','ui01-card-title ui01-average-title','Среднее за день');
        const calendar=element('span','ux23-average-icon');
        calendar.setAttribute('aria-hidden','true');
        calendar.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18M8 14h.01M12 14h.01M16 14h.01"/></svg>';
        heading.prepend(calendar);
        avgHost.append(heading);
        avgHost.append(element('strong','ui01-average-bp',
          view.average.systolic+' / '+view.average.diastolic));
        const pulse=element('div','ui01-average-pulse',
          view.average.pulse===null?'Средний пульс — не указан':'Пульс '+view.average.pulse+' уд/мин');
        if(view.average.pulse!==null)pulse.prepend(ux23OutlineIcon('activity'));
        avgHost.append(pulse);
        avgHost.append(element('span','ui01-v7-reading-meta',
          view.average.count+' замера сегодня'));
        avgHost.hidden=false;
      }
    }else{
      holder.append(element('p','ui01-empty','Измерений пока нет.'));
    }
    const add=element('button','primary ui01-wide-button','+ Добавить измерение');
    add.type='button';add.addEventListener('click',()=>{
      navigate('pressure');
      const panel=el('pressure-form')?.closest('article.panel');
      if(panel)requestAnimationFrame(()=>requestAnimationFrame(()=>{
        const top=Math.max(0,Math.round(panel.getBoundingClientRect().top+window.scrollY-12));
        window.scrollTo(0,top);
      }));
    });
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
  function medRow(m,day){
    const row=element('div','ui01-med-row');
    const current=snapshot.intakes.filter(i=>i.medId===m.id&&i.date===day&&activeIntake(i));
    const goal=m.kind==='asNeeded'?null:medDailyTarget(m);
    const desc=element('div','ui01-med-description');
    const medName=element('strong','ui01-med-name',m.name);
    desc.append(medName);
    if(goal!==null){
      const doneCount=medDailySlots(m,current).filter(Boolean).length;
      if(doneCount)medName.append(element('span','ui01-v7-done-badge',
        ' ✓ '+doneCount+'/'+goal));
    }
    if(m.dose)desc.append(element('span','ui01-personal-dose',m.dose));
    if(m.kind==='asNeeded')desc.append(element('span','ui01-muted','По необходимости'));
    if(goal===null){
      const times=current.map(i=>i.takenAtLocal?.slice(11,16)).filter(Boolean).sort();
      if(times.length)desc.append(element('span','ui01-today-time','Сегодня: '+times.join(', ')));
      const btn=element('button','ui01-check'+(current.length?' is-taken':''),current.length?'✓':'');
      btn.type='button';btn.setAttribute('aria-label',current.length?'Открыть журнал приёмов '+m.name:'Записать фактический приём '+m.name);
      btn.addEventListener('click',()=>current.length?navigate('meds'):onHomeIntake(m,btn));row.append(btn,desc);return row;
    }
    const slots=medDailySlots(m,current),checks=element('div','ui01-home-slots');
    for(let n=1;n<=goal;n++){
      const taken=slots[n-1],label=element('label','ui01-home-slot'),box=element('input');
      box.type='checkbox';box.checked=!!taken;box.setAttribute('aria-label',`${m.name}: ${medSlotLabel(goal,n)}`);
      label.append(box,element('span','',medSlotLabel(goal,n)));checks.append(label);
      box.addEventListener('change',async()=>{
        box.disabled=true;
        try{
          if(taken){if(!window.confirm(`Отменить отметку «${medSlotLabel(goal,n)}» для ${m.name}? История сохранится.`)){box.checked=true;return;}
            const stamp=new Date().toISOString();await changeIntake('cancelled',{...taken,status:'cancelled',cancelledAt:stamp,updatedAt:stamp},taken);
          }else{
            const time=clockLocal(new Date()),takenAtLocal=day+'T'+time;
            if(snapshot.intakes.some(i=>i.medId===m.id&&i.takenAtLocal===takenAtLocal&&activeIntake(i)))throw Error('В это время уже есть отметка. Уточните время в журнале лекарств.');
            const record={id:crypto.randomUUID(),medId:m.id,date:day,takenAtLocal,markedAt:new Date().toISOString(),status:'active',dailySlot:n};
            validateIntake(record);await changeIntake('marked',record);
          }
          safetyNeedsNewCheck();await reload();
        }catch(err){box.checked=!!taken;showMessage('Отметка не изменена: '+toError(err),'error');}
        finally{box.disabled=false;}
      });
    }
    const legacy=current.filter(i=>!Number.isInteger(i.dailySlot)).length;
    if(legacy)desc.append(element('span','ui01-muted',`${legacy} старых ${legacy===1?'отметка':'отметок'} без назначенного слота`));
    const actualTimes=slots.filter(Boolean).map(i=>takenTime(i)).filter(Boolean);
    if(actualTimes.length)desc.append(element('span','ui01-v7-actual-time',
      'Фактическое время: '+actualTimes.join(', ')));
    row.append(desc,checks);
    return row;
  }
  // No planned clock hours are stored: first pending is a deterministic slot order,
  // never a forecast of the actual next dose time.
  function v7Plan(day){
    const groups={},kinds=['regular','course','asNeeded'];
    let total=0,checked=0,unconfigured=0,first=null;
    for(const kind of kinds){
      const meds=snapshot.medications.filter(m=>m.kind===kind&&
        (kind!=='course'||courseActive(m,day)))
        .sort((a,b)=>a.name.localeCompare(b.name,'ru'));
      groups[kind]=meds.map(med=>{
        const current=snapshot.intakes.filter(i=>i.medId===med.id&&i.date===day&&activeIntake(i));
        const goal=kind==='asNeeded'?null:medDailyTarget(med);
        const slots=goal===null?[]:medDailySlots(med,current);
        const done=slots.filter(Boolean).length;
        if(kind!=='asNeeded'){
          if(goal===null)unconfigured++;
          else{
            total+=goal;checked+=done;
            for(let n=1;n<=goal;n++){
              if(!slots[n-1]&&!first)first={med,slot:n,goal};
            }
          }
        }
        return {med,goal,done,fullyDone:goal!==null&&goal>0&&done===goal};
      });
    }
    return {groups,total,checked,unconfigured,first};
  }
  function drawMeds(day,yday){
    const host=el('ui01-meds');if(!host)return;host.replaceChildren();
    const plan=v7Plan(day);
    const next=element('section','ui01-card ui01-v7-next');
    next.setAttribute('aria-label','Следующий неотмеченный слот');
    const remaining=Math.max(0,plan.total-plan.checked);
    const heading=plan.total?
      'Неотмеченные приёмы · осталось '+remaining+' из '+plan.total:
      'Неотмеченные приёмы';
    next.append(element('h2','ui01-card-title',heading));
    if(plan.first){
      next.append(element('strong','ui01-v7-next-name',plan.first.med.name));
      next.append(element('p','ui01-v7-next-meta',
        'Первый в списке · '+medSlotLabel(plan.first.goal,plan.first.slot)+' · плановое время не задано'));
    }else if(plan.total>0&&plan.unconfigured===0){
      next.append(element('p','ui01-v7-complete-message','✓ Все настроенные слоты отмечены'));
    }else if(plan.total===0){
      next.append(element('p','ui01-v7-next-meta','Настроенных слотов нет. Время приёма не задано.'));
    }else{
      next.append(element('p','ui01-v7-next-meta',
        'Настроенные слоты отмечены; есть препараты без расписания.'));
    }
    next.append(element('p','ui01-v7-disclaimer',
      'Порядок — по списку препаратов, а не по времени приёма. Это не рекомендация и не напоминание.'));
    host.append(next,element('h2','ui01-section-title','Лекарства сегодня'));
    let visible=0;
    for(const kind of ['regular','course','asNeeded']){
      const rows=plan.groups[kind];if(!rows.length)continue;visible++;
      const card=element('section','ui01-card ui01-med-group');
      const heading=element('h3','ui01-group-title',TYPE_NAMES[kind]);
      heading.prepend(ux23OutlineIcon(kind));
      card.append(heading);
      const pending=rows.filter(r=>!r.fullyDone),finished=rows.filter(r=>r.fullyDone);
      for(const row of pending)card.append(medRow(row.med,day));
      if(finished.length){
        // Native details keeps audited Undo controls available, but collapsed by default.
        const details=element('details','ui01-v7-finished');
        const text=finished.length===rows.length?
          '✓ Все настроенные приёмы отмечены · Показать / отменить':
          '✓ Принято: '+finished.length+' · Показать / отменить';
        details.append(element('summary','ui01-v7-finished-summary',text));
        for(const row of finished)details.append(medRow(row.med,day));
        card.append(details);
      }
      if(kind==='asNeeded'){
        card.append(element('p','ui01-v7-disclaimer',
          'Ситуативные препараты не считаются пропущенными.'));
      }
      host.append(card);
    }
    if(!visible)host.append(element('p','ui01-empty',
      'На сегодня нет постоянных и активных курсовых препаратов. Ситуативные отдельно.'));
    if(plan.total){
      host.append(element('p','ui01-note',
        'Отмечено по настроенным слотам: '+plan.checked+' из '+plan.total+
        (plan.unconfigured?' · Без расписания: '+plan.unconfigured:'')+'.'));
    }else if(plan.unconfigured){
      host.append(element('p','ui01-note',
        'У '+plan.unconfigured+' препаратов число приёмов не задано: отсутствие отметки не считается пропуском.'));
    }
  }
  function drawHome(){
    if(!el('ui01-pressure'))return;
    const day=today();
    dayLast=day;
    el('ui01-date').textContent=humanDate(day);
    drawPressure(day);
    drawMeds(day);
  }
  const originalOverview=renderOverview;
  renderOverview=function(){
    originalOverview();
    drawHome();
  };
  function setupPressurePeriods(){
    document.querySelectorAll('[data-period-target]').forEach(group=>{
      const target=el(group.dataset.periodTarget);
      if(!target)return;
      if(target.id==='pressure-list-period')target.value='all';
      const buttons=[...group.querySelectorAll('button[data-period]')];
      const sync=()=>buttons.forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.period===target.value)));
      buttons.forEach(b=>b.addEventListener('click',()=>{
        if(target.value!==b.dataset.period){
          target.value=b.dataset.period;
          target.dispatchEvent(new Event('change',{bubbles:true}));
        }
        sync();
      }));
      target.addEventListener('change',sync);
      sync();
    });
  }
  function setupMedicationSections(){
    const list=el('med-list'),history=el('intake-list'),kind=el('med-history-kind');
    const panel=list?.closest('article.panel');
    if(!list||!history||!panel||!kind)return;
    const divider=panel.querySelector('.section-divider');
    const histHead=panel.querySelector('.v05-intake-head');
    const todayHead=panel.querySelector('.panel-heading');
    if(!divider||!histHead||!todayHead)return;
    const tabs=element('div','v232-med-tabs');
    tabs.setAttribute('role','tablist');tabs.setAttribute('aria-label','Разделы лекарств');
    const todayPane=element('section','v232-med-pane'),historyPane=element('section','v232-med-pane');
    todayPane.id='v232-meds-today';historyPane.id='v232-meds-history';
    todayPane.setAttribute('role','tabpanel');historyPane.setAttribute('role','tabpanel');
    const controls=[['today','Сегодня',todayPane],['history','История приёма',historyPane]];
    for(const [key,title,pane] of controls){
      const button=element('button','v232-med-tab',title);button.type='button';
      button.dataset.medView=key;button.id='v232-tab-'+key;
      button.setAttribute('role','tab');button.setAttribute('aria-controls',pane.id);
      pane.setAttribute('aria-labelledby',button.id);
      tabs.append(button);
      button.addEventListener('click',()=>{
        for(const [v,_,p] of controls){
          const selected=v===key;p.hidden=!selected;
          tabs.querySelector('[data-med-view="'+v+'"]').setAttribute('aria-selected',String(selected));
        }
      });
    }
    const moving=[];let next=todayHead;
    while(next&&next!==divider){moving.push(next);next=next.nextElementSibling;}
    if(next!==divider||moving.length<2)return;
    for(const n of moving)todayPane.append(n);
    // Keep every original instruction and search control accessible, but out of the
    // approved compact day view until explicitly opened.
    const guidance=todayPane.querySelector(':scope > .form-hint');
    if(guidance){
      const help=element('details','ux23-meds-help');
      help.append(element('summary','ux23-meds-help-summary','Как отмечать приём'));
      guidance.replaceWith(help);help.append(guidance);todayPane.append(help);
    }
    const search=todayPane.querySelector(':scope > .compact-search');
    if(search){
      const finder=element('details','ux23-meds-search');
      finder.append(element('summary','ux23-meds-help-summary','Поиск препарата'));
      search.replaceWith(finder);finder.append(search);todayPane.append(finder);
    }
    historyPane.append(histHead,history);divider.remove();
    panel.prepend(tabs,todayPane,historyPane);
    tabs.querySelector('[data-med-view="today"]').click();
    const kindTabs=element('div','v232-med-kind-tabs');
    kindTabs.setAttribute('role','group');kindTabs.setAttribute('aria-label','Категория истории');
    const options=[['regular','Постоянные'],['course','Курсовые'],['asNeeded','Ситуативные']];
    const sync=()=>{
      kindTabs.querySelectorAll('button').forEach(button=>{
        button.setAttribute('aria-pressed',String(button.dataset.kind===kind.value));
      });
      // Tabs carry approved outline icons; retire the duplicate native type selector.
      kind.closest('label')?.classList.add('ux23-duplicate-kind-filter');
      // Permanent/course periods are fixed; only PRN has the approved 1/3-month choice.
      el('med-history-period')?.closest('label')?.classList.toggle(
        'ux23-fixed-history-period',kind.value!=='asNeeded');
    };
    for(const [value,title] of options){
      const button=element('button','v232-kind-button');button.type='button';button.dataset.kind=value;
      button.append(ux23OutlineIcon(value),document.createTextNode(title));
      button.addEventListener('click',()=>{kind.value=value;kind.dispatchEvent(new Event('change',{bubbles:true}));sync();});
      kindTabs.append(button);
    }
    kind.addEventListener('change',sync);sync();historyPane.prepend(kindTabs);
  }
  document.addEventListener('DOMContentLoaded',()=>{
    readFont();
    applyDisplaySettings();
    setupPressurePeriods();
    setupMedicationSections();
    el('display-theme').addEventListener('change',e=>{try{localStorage.setItem(THEME_KEY,e.target.value)}catch(_){}applyDisplaySettings();});
    el('compact-view').addEventListener('change',e=>{try{localStorage.setItem(COMPACT_KEY,String(e.target.checked))}catch(_){}applyDisplaySettings();});
    el('ui01-font-less').addEventListener('click',()=>adjustFont(-1));
    el('ui01-font-more').addEventListener('click',()=>adjustFont(1));
    drawHome();
    document.addEventListener('visibilitychange',()=>{if(!document.hidden)drawHome();});
    window.addEventListener('focus',drawHome);
    window.setInterval(()=>{if(today()!==dayLast)drawHome();},60000);
  });
  window.PAE04CPUI01={render:drawHome,priorDate,courseActive};
})();
