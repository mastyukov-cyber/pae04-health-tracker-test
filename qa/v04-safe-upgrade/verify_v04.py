from pathlib import Path
from hashlib import sha256
import json, sys
root = Path(__file__).resolve().parent
manifest = json.loads((root / "V04_MANIFEST.json").read_text())
site = root / "site"
failed = []
for name, expected in manifest["target_files"].items():
    actual = sha256((site / name).read_bytes()).hexdigest()
    print(f"{'PASS' if actual == expected else 'FAIL'} {name} {actual}")
    if actual != expected:
        failed.append(name)
print(f"MANIFEST_FILES={len(manifest['target_files'])} VERIFIED={len(manifest['target_files']) - len(failed)}")
sys.exit(bool(failed))
