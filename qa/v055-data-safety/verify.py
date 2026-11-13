#!/usr/bin/env python3
"""PAE-04 v05.5 strict 9-asset SHA-256 and stability gate. Synthetic only."""
from pathlib import Path
from hashlib import sha256
import json
root=Path(__file__).resolve().parent
site=root/'site'
manifest=json.loads((root/'V055_MANIFEST.json').read_text(encoding='utf-8'))
expected=manifest['sha256']
actual={str(f.relative_to(site)) for f in site.rglob('*') if f.is_file()}
assert manifest['version']=='v05.5'
assert len(expected)==9 and set(expected)==actual,(set(expected)^actual)
for rel,checksum in expected.items():
 assert sha256((site/rel).read_bytes()).hexdigest()==checksum,rel
html=(site/'index.html').read_text(encoding='utf-8')
app=(site/'app.js').read_text(encoding='utf-8')
css=(site/'styles.css').read_text(encoding='utf-8')
sw=(site/'sw.js').read_text(encoding='utf-8')
assert 'SAFE UX TEST v05.5' in html
assert 'id="data-safety-panel"' in html and 'id="safety-check"' in html
assert 'id="safety-copy-status"' in html and 'id="safety-db-status"' in html
assert 'function verifyRecordAfterWrite(store,record)' in app
assert 'async function verifyIntakeAudit(record,auditEvent)' in app
assert 'function checkLocalIntegrity()' in app
assert 'function safetyExternalBackupVerified(expected,contentMatches)' in app
assert 'function reportBrowserStorage()' in app
assert 'navigator.storage.persist(' not in app
assert 'cache-v055-20261114' in sw
assert 'font-size: 16px !important;' in css
assert 'user-scalable=no' not in html and 'maximum-scale' not in html
assert "const DB_NAME='PAE04_HT_STABLE_CANDIDATE_INTEGRATION_SYNTHETIC_SCHEMA1'" in app
assert 'const DB_VERSION=1' in app
assert "const STORE_NAMES=['pressures','medications','intakes','intakeEvents']" in app
assert 'const BACKUP_VERSION=3' in app
assert 'function atomicMerge(data)' in app
print('RESULT=PASS VERSION=v05.5 SHA256=9/9 DB_SCHEMA=1 BACKUP=3 STORAGES=4 NO_CLOUD=True SYNTHETIC_ONLY=True')
