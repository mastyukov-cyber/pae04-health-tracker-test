#!/usr/bin/env python3
"""CP-UI01 fail-closed static QA, Python 3.12, synthetic only."""
import json
import sys
from pathlib import Path
s=Path(sys.argv[1]).resolve()
assert s.is_dir()
html=(s/'index.html').read_text(encoding='utf-8')
app=(s/'app.js').read_text(encoding='utf-8')
home=(s/'home.js').read_text(encoding='utf-8')
css=(s/'home.css').read_text(encoding='utf-8')
sw=(s/'sw.js').read_text(encoding='utf-8')
p=json.loads((s/'CP_UI01_BUILD.json').read_text(encoding='utf-8'))
checks=[
    ('synthetic candidate only',p['status']=='synthetic_candidate_only' and p['no_medical_records'] and p['no_deployment']),
    ('no data schema changes',not p['db_schema_changed'] and not p['backup_format_changed']),
    ('home title and font controls',all(t in html for t in ['id="overview-title"','id="ui01-font-less"','id="ui01-font-more"','id="ui01-font-label"'])),
    ('today and yesterday regions',all(t in html for t in ['id="ui01-pressure"','id="ui01-meds"'])),
    ('legacy UI holders present',all(t in html for t in ['id="stat-pressure"','id="stat-meds"','id="stat-intakes"','id="overview-pressure"','id="overview-meds"'])),
    ('JS and CSS linked once',html.count('src="./home.js"')==1 and html.count('href="./home.css"')==1),
    ('five font sizes', 'const SCALES = [1, 1.07, 1.14, 1.22, 1.32]' in home),
    ('yesterday pressure and pulse',all(t in home for t in ["mean('systolic')","mean('diastolic')",'pulses.reduce'])),
    ('all three medications types',all(t in home for t in ["'regular'","'course'","'asNeeded'"])),
    ('course requires dates', 'if(!m.from&&!m.to)return false' in home),
    ('yesterday times for regular and active courses only', "m.kind==='regular'||(m.kind==='course'&&courseActive(m,yday))" in home),
    ('use original intake audit', "changeIntake('marked',record)" in home),
    ('no medicine reminders', 'Notification.requestPermission' not in home and 'setTimeout(' not in home),
    ('avoid real drug names', 'Капотен' not in home and 'Копотэн' not in home),
    ('five font controls persist', 'localStorage.setItem(FONT_KEY' in home),
    ('CSP unchanged', 'script-src &#39;unsafe-inline&#39;' not in html and 'script-src &#39;unsafe-eval&#39;' not in html),
    ('offline include home assets', all(t in sw for t in ["'./home.js'","'./home.css'"])),
    ('offline cache bumped', 'cache-cpui01-20261115' in sw),
    ('existing DB name unchanged', "const DB_NAME='PAE04_HT_STABLE_CANDIDATE_INTEGRATION_SYNTHETIC_SCHEMA1'" in app),
    ('existing DB schema unchanged', "const DB_VERSION=1" in app and "const STORE_NAMES=['pressures','medications','intakes','intakeEvents']" in app),
    ('backup v3 retained', "const BACKUP_VERSION=3" in app),
    ('med guard still wired', 'PAE04MedicationGuard' in app and (s/'med_guard.mjs').exists()),
    ('responsive mobile styles', '@media(max-width:355px)' in css and 'overflow-wrap:anywhere' in css)
]
for name,passed in checks:
    print(('PASS' if passed else 'FAIL')+' '+name)
assert all(p for _,p in checks),'CP-UI01 static gate FAIL'
print('RESULT=PASS CP_UI01_STATIC='+str(len(checks))+'/'+str(len(checks)))
