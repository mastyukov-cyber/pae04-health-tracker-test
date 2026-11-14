#!/usr/bin/env python3
"""PAE-04 v05.5.2 strict synthetic release gate. Does not read any personal data."""
from pathlib import Path
from hashlib import sha256
import json
root=Path(__file__).resolve().parent
site=root/'site'
m=json.loads((root/'V0552_MANIFEST.json').read_text(encoding='utf-8'))
expected=m['sha256']
found={str(p.relative_to(site)) for p in site.rglob('*') if p.is_file()}
assert m['version']=='v05.5.2'
assert len(expected)==9 and found==set(expected),(found^set(expected))
for path,checksum in expected.items():
 digest=sha256((site/path).read_bytes()).hexdigest()
 assert digest==checksum,(path,digest,checksum)
html=(site/'index.html').read_text(encoding='utf-8')
css=(site/'styles.css').read_text(encoding='utf-8')
app=(site/'app.js').read_text(encoding='utf-8')
sw=(site/'sw.js').read_text(encoding='utf-8')
assert 'SAFE UX TEST v05.5.2' in html
assert 'user-scalable=no' not in html and 'maximum-scale' not in html
assert 'cache-v0552-20261114' in sw
assert 'body.keyboard-editing .sidebar{display:none!important}' in css
assert 'function setupMobileKeyboardUI()' in app
assert 'id="pressure-keyboard-done"' in html
assert 'class="keyboard-done"' in html
assert 'body.note-editing #pressure-keyboard-done' in css
assert 'function navigate(page){dismissMobileKeyboard();' in app
assert "pressurePage.addEventListener('pointerdown'" in app
assert "pressurePage.addEventListener('touchstart'" in app
assert "pressurePage.addEventListener('touchmove'" in app
assert "pressurePage.addEventListener('touchend'" not in app or 'pressureSwipeStart=null' in app
assert "$('pressure-keyboard-done').addEventListener('click',dismissMobileKeyboard)" in app
assert 'function syncMobileKeyboardUI()' in app
assert 'function dismissMobileKeyboard()' in app
assert "await addRecord('pressures',p);safetyNeedsNewCheck();dismissMobileKeyboard();" in app
assert 'setupWheelPicker();setupMobileKeyboardUI();' in app
for id in ('systolic','diastolic','pulse'):
 start=html.index('id="'+id+'"')
 attrs=html[start:html.index('/>',start)]
 for token in ('type="number"','autocomplete="off"','autocorrect="off"','autocapitalize="off"','spellcheck="false"','enterkeyhint="next"'):
  if token=='type="number"':
   assert token in html[max(0,start-60):start+60],(id,token)
  else:
   assert token in attrs,(id,token)
assert "const DB_NAME='PAE04_HT_STABLE_CANDIDATE_INTEGRATION_SYNTHETIC_SCHEMA1'" in app
assert 'const DB_VERSION=1' in app
assert "const STORE_NAMES=['pressures','medications','intakes','intakeEvents']" in app
assert 'const BACKUP_VERSION=3' in app
assert 'function atomicMerge(data)' in app
assert 'function verifyRecordAfterWrite(store,record)' in app
assert 'function checkLocalIntegrity()' in app
print('RESULT=PASS VERSION=v05.5.2 FILES=9 SHA256=9/9 SCHEMA_UNCHANGED=True V3_BACKUPS=True PINCH_ZOOM=True SYNTHETIC_ONLY=True')
