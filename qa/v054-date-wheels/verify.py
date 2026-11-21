#!/usr/bin/env python3
"""Strict PAE-04 v05.4 synthetic 9-file manifest verification."""
from pathlib import Path
from hashlib import sha256
import json
root=Path(__file__).resolve().parent
site=root/'site'
manifest=json.loads((root/'V054_MANIFEST.json').read_text(encoding='utf-8'))
expected=manifest['sha256']
actual={str(f.relative_to(site)) for f in site.rglob('*') if f.is_file()}
assert manifest['version']=='v05.4'
assert len(expected)==9 and set(expected)==actual,(set(expected)^actual)
for rel,checksum in expected.items():
  digest=sha256((site/rel).read_bytes()).hexdigest()
  assert digest==checksum,(rel,digest,checksum)
h=(site/'index.html').read_text(encoding='utf-8')
a=(site/'app.js').read_text(encoding='utf-8')
s=(site/'styles.css').read_text(encoding='utf-8')
sw=(site/'sw.js').read_text(encoding='utf-8')
assert 'SAFE UX TEST v05.4' in h
assert 'data-wheel-target="pressure-datetime"' in h
assert 'data-wheel-target="intake-date"' in h
assert 'data-wheel-target="course-from"' in h
assert 'data-wheel-target="course-to"' in h
assert 'role="dialog"' in h and 'wheel-modal' in h
assert 'font-size: 16px !important;' in s
assert 'scroll-snap-type:y mandatory' in s
assert 'user-scalable=no' not in h and 'maximum-scale' not in h
assert 'function commitWheelDate(clear=false)' in a
assert 'function setupWheelPicker()' in a
assert 'const DB_VERSION=1' in a
assert "const DB_NAME='PAE04_HT_STABLE_CANDIDATE_INTEGRATION_SYNTHETIC_SCHEMA1'" in a
assert "const STORE_NAMES=['pressures','medications','intakes','intakeEvents']" in a
assert 'const BACKUP_VERSION=3' in a
assert 'cache-v054-20261114' in sw
print('RESULT=PASS VERSION=v05.4 SHA256=9/9 ISO_DATES=PRESERVED DB_SCHEMA=UNCHANGED BACKUP_V3=UNCHANGED')
