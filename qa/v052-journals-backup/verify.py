from pathlib import Path
from hashlib import sha256
import json
root=Path(__file__).resolve().parent
site=root/'site'
m=json.loads((root/'V052_MANIFEST.json').read_text(encoding='utf-8'))
expected=m['sha256']
found={str(p.relative_to(site)) for p in site.rglob('*') if p.is_file()}
assert len(expected)==9 and set(expected)==found,(set(expected)^found)
for name,digest in expected.items():
    actual=sha256((site/name).read_bytes()).hexdigest()
    assert actual==digest,(name,actual,digest)
html=(site/'index.html').read_text(encoding='utf-8')
app=(site/'app.js').read_text(encoding='utf-8')
sw=(site/'sw.js').read_text(encoding='utf-8')
assert 'SAFE UX TEST v05.2' in html
assert 'id="pressure-search"' in html
assert 'id="med-search"' in html
assert 'id="verify-file"' in html
assert 'JSON не зашифрован' in html
assert "const DB_NAME='PAE04_HT_STABLE_CANDIDATE_INTEGRATION_SYNTHETIC_SCHEMA1'" in app
assert 'const DB_VERSION=1' in app
assert "const STORE_NAMES=['pressures','medications','intakes','intakeEvents']" in app
assert 'const BACKUP_VERSION=3' in app
assert 'function atomicMerge(data)' in app
assert 'verifyDownloadedBackup' in app
assert 'cache-v052-20261113' in sw
print('RESULT=PASS V05.2_SHA256=9/9 SCHEMA=UNCHANGED SYNTHETIC_ONLY=True')
