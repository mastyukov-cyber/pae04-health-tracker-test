#!/usr/bin/env python3
"""PAE-04 CP-UI01: detached synthetic Apple Light Comfort builder. Python 3.12."""
import argparse
import json
import re
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parent
SECTION='''<section class="page active ui01-home" id="page-overview" aria-labelledby="overview-title">
  <header class="ui01-top">
    <div><h1 class="ui01-title" id="overview-title">Сегодня</h1><span class="ui01-date" id="ui01-date"></span></div>
    <div class="ui01-font-tools" aria-label="Размер шрифта">
      <button id="ui01-font-less" type="button" aria-label="Уменьшить шрифт">А−</button>
      <span id="ui01-font-label" aria-live="polite"></span>
      <button id="ui01-font-more" type="button" aria-label="Увеличить шрифт">А+</button>
    </div>
  </header>
  <div class="ui01-card" id="ui01-pressure" aria-label="Давление сегодня"></div>
  <div id="ui01-meds" aria-label="Лекарства сегодня"></div>
  <div class="ui01-compat" hidden aria-hidden="true">
    <span id="stat-pressure">0</span><span id="stat-meds">0</span><span id="stat-intakes">0</span>
    <div id="overview-pressure"></div><div id="overview-meds"></div>
  </div>
</section>'''

def build(source:Path,target:Path):
    if target.exists():
        raise ValueError('Refuse to overwrite an existing detached candidate')
    if not source.is_dir() or source.resolve()==target.resolve():
        raise ValueError('Invalid source or destination')
    required=['index.html','app.js','styles.css','sw.js','med_guard.mjs',
              'med_matcher.mjs','med_guard.css','CP_MED05_BUILD.json']
    for name in required:
        if not (source/name).is_file():
            raise ValueError('CP-MED05 candidate required: '+name)
    meta=json.loads((source/'CP_MED05_BUILD.json').read_text(encoding='utf-8'))
    if meta.get('status')!='candidate_not_released' or meta.get('db_schema_changed') is not False or meta.get('backup_format_changed') is not False:
        raise ValueError('Unexpected CP-MED05 provenance')
    if (source/'home.js').exists() or (source/'home.css').exists():
        raise ValueError('Home extension already exists')
    html=(source/'index.html').read_text(encoding='utf-8')
    original_begin='<section class="page active" id="page-overview"'
    if html.count(original_begin)!=1:
        raise ValueError('Missing unique original overview section')
    start=html.index(original_begin)
    end=html.index('</section>',start)+len('</section>')
    original=html[start:end]
    for token in ('id="stat-pressure"','id="stat-meds"','id="stat-intakes"',
                  'id="overview-pressure"','id="overview-meds"'):
        if token not in original:
            raise ValueError('Unexpected old overview contents: '+token)
    html=html[:start]+SECTION+html[end:]
    head_marker='<link rel="stylesheet" href="./styles.css" />'
    script_marker='<script src="./app.js" defer></script>'
    if html.count(head_marker)!=1 or html.count(script_marker)!=1:
        raise ValueError('Unexpected asset anchors')
    html=html.replace(head_marker,head_marker+'\n  <link rel="stylesheet" href="./home.css" />',1)
    html=html.replace(script_marker,script_marker+'\n  <script src="./home.js" defer></script>',1)
    html=html.replace('<span>Обзор</span>','<span>Главная</span>',1)
    sw=(source/'sw.js').read_text(encoding='utf-8')
    if sw.count('cache-cpmed05-20261115')!=1:
        raise ValueError('Unexpected original offline cache version')
    sw=sw.replace('cache-cpmed05-20261115','cache-cpui01-20261115',1)
    match=re.search(r'const FILES=\[(.*?)\];',sw,re.S)
    if not match or 'home.js' in match.group(1):
        raise ValueError('Offline precache is missing or has been modified')
    sw=sw[:match.end()-2]+",'./home.js','./home.css'"+sw[match.end()-2:]
    shutil.copytree(source,target)
    (target/'index.html').write_text(html,encoding='utf-8')
    (target/'sw.js').write_text(sw,encoding='utf-8')
    shutil.copyfile(ROOT/'home.js',target/'home.js')
    shutil.copyfile(ROOT/'home.css',target/'home.css')
    (target/'CP_UI01_BUILD.json').write_text(json.dumps({
        'status':'synthetic_candidate_only','source':'CP-MED05.1 detached candidate',
        'db_schema_changed':False,'backup_format_changed':False,
        'modified':['index.html','sw.js'],'added':['home.js','home.css'],
        'no_medical_records':True,'no_deployment':True
    },ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('CP-UI01 DETACHED BUILD PASS. No source writes and no deploy.')

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--source',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args()
    build(a.source.resolve(),a.output.resolve())
