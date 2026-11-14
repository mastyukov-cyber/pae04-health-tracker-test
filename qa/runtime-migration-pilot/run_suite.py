#!/usr/bin/env python3
"""Fail-closed PAE-04 browser suite for four QA levels; unchanged synthetic cases."""
from __future__ import annotations
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ENGINE, LEVEL = sys.argv[1:]
assert ENGINE in ('chromium','webkit'), ENGINE
assert LEVEL in ('STANDARD','CRITICAL','RELEASE'), LEVEL
assert os.environ.get('PAE04_SYNTHETIC_ONLY') == 'true', 'BLOCKED live-data boundary'
base=Path(__file__).resolve().parents[1]/'v0552-keyboard-polish'
assert (base/'tests'/'browser_e2e.py').is_file(), ('BLOCKED missing immutable v05.5.2 test source',base)
out=Path(__file__).resolve().parent/'reports'/ENGINE
out.mkdir(parents=True,exist_ok=True)

# Baseline v05.5.2 expected individual test counts (do not weaken).
suites={
 'STANDARD': [('keyboard_polish.py',13),('keyboard_ux.py',29),
              ('v05_ux.py',9),('mobile_geometry.py',29)],
 'CRITICAL': [('browser_e2e.py',25),('v052_features.py',14),
              ('zoom_focus.py',22),('data_safety.py',27)],
 'RELEASE': [('date_wheels.py',20)]
}
needed=['STANDARD']
if LEVEL in ('CRITICAL','RELEASE'):needed.append('CRITICAL')
if LEVEL=='RELEASE':needed.append('RELEASE')

result={'status':'FAIL','engine':ENGINE,'qa_level':LEVEL,'files':[],
        'expected':sum(n for tier in needed for _,n in suites[tier]),'passed':0}
try:
 for tier in needed:
  for name,expected in suites[tier]:
   cmd=[sys.executable,str(base/'tests'/name),ENGINE]
   print('BEGIN='+tier+' FILE='+name+' EXPECTED='+str(expected),flush=True)
   completed=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=550)
   transcript=completed.stdout or ''
   (out/(name+'.log')).write_text(transcript,encoding='utf-8')
   print(transcript[-16000:],flush=True)
   pattern=rf'RESULT=PASS ENGINE={ENGINE} CHECKS={expected}(?![0-9])'
   matched=bool(re.search(pattern,transcript))
   record={'tier':tier,'file':name,'expected':expected,
           'exit_code':completed.returncode,'pass_line_found':matched}
   result['files'].append(record)
   if completed.returncode != 0 or not matched:
    result['error']='BLOCKED_SUITES_DIVERGED_OR_FAILED:'+name
    raise RuntimeError(result['error'])
   result['passed']+=expected
 if result['passed']!=result['expected']:raise RuntimeError('BLOCKED count mismatch')
 result['status']='PASS'
except Exception as exc:
 result['error']=str(exc)
 print('RESULT=FAIL '+result['error'],flush=True)
finally:
 (out/'suite-summary.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
 print('RESULT='+result['status']+' ENGINE='+ENGINE+' LEVEL='+LEVEL+' CHECKS='+str(result['passed'])+'/'+str(result['expected']),flush=True)
sys.exit(0 if result['status']=='PASS' else 1)
