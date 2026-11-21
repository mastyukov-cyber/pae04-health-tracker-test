from pathlib import Path
from hashlib import sha256
import json
root=Path(__file__).resolve().parent
site=root/'site'
m=json.loads((root/'V053_MANIFEST.json').read_text(encoding='utf-8'))
expected=m['sha256']
found={str(p.relative_to(site)) for p in site.rglob('*') if p.is_file()}
assert m['version']=='v05.3'
assert len(expected)==9 and set(expected)==found,(set(expected)^found)
for name,checksum in expected.items():
 actual=sha256((site/name).read_bytes()).hexdigest()
 assert actual==checksum,(name,actual,checksum)
html=(site/'index.html').read_text(encoding='utf-8')
css=(site/'styles.css').read_text(encoding='utf-8')
app=(site/'app.js').read_text(encoding='utf-8')
sw=(site/'sw.js').read_text(encoding='utf-8')
assert 'SAFE UX TEST v05.3' in html
assert 'width=device-width, initial-scale=1, viewport-fit=cover' in html
assert 'user-scalable=no' not in html and 'maximum-scale' not in html
assert 'font-size: 16px !important;' in css and 'input:not([type="checkbox"])' in css
assert "const DB_NAME='PAE04_HT_STABLE_CANDIDATE_INTEGRATION_SYNTHETIC_SCHEMA1'" in app
assert "const DB_VERSION=1" in app
assert "const STORE_NAMES=['pressures','medications','intakes','intakeEvents']" in app
assert "const BACKUP_VERSION=3" in app
assert 'function atomicMerge(data)' in app
assert 'cache-v053-20261114' in sw
print('RESULT=PASS VERSION=v05.3 FILES=9 SHA256=9/9 SCHEMA_UNCHANGED=True PINCH_ZOOM_ENABLED=True')
