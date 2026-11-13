from pathlib import Path
from hashlib import sha256
import json
root=Path(__file__).resolve().parent
site=root/'site';m=json.loads((root/'V051_MANIFEST.json').read_text())
expected=m['sha256']
files={str(x.relative_to(site)) for x in site.rglob('*') if x.is_file()}
assert set(expected)==files,files^set(expected)
for name,hash in expected.items():
 actual=sha256((site/name).read_bytes()).hexdigest()
 assert actual==hash,(name,actual)
html=(site/'index.html').read_text()
assert 'SAFE UX TEST v05.1' in html
assert 'class="version-inline"' not in html
assert 'class="pressure-date-field"' in html
assert "cache-v051-20261113" in (site/'sw.js').read_text()
app=(site/'app.js').read_text()
assert "const DB_NAME='PAE04_HT_STABLE_CANDIDATE_INTEGRATION_SYNTHETIC_SCHEMA1'" in app
assert "const BACKUP_VERSION=3" in app
print('RESULT=PASS VERSION=v05.1 SHA256=9/9 SYNTHETIC_ONLY=True')
