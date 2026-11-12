#!/usr/bin/env python3
"""Build byte-identical PAE-04 v03 TEST resources from SHA-gated v02 + patch.
Only synthetic test assets. Fail closed before any browser starts.
"""
from pathlib import Path
from hashlib import sha256
from subprocess import run, PIPE
import base64, gzip, shutil, re, sys

ROOT=Path(__file__).resolve().parent
V02=ROOT.parent/"integration-v02-browser"/"site-v02"
V03=ROOT/"site-v03"
PATCH_FILE=ROOT/"v03.patch.gz.b64"
PATCH_SHA="e76ffbae228592fd457ed17849d4070a6a0ff341dd203ba3421ba640d1f13d17"
SOURCE_ZIP_V03_SHA="6633a51d713019e38b2094b79218b6a97ac8f230325accd4a25dc31c29a991ab"
HASHES={
 "app.js":"c86d8e6836524ee75d34e85034a2b0c12c6496f69e8e2f834c0a9c011cedebb0",
 "index.html":"c2c057ad14046a0d3f157bb42a55721f9accaf79efed59cc3e593b5d7ff361eb",
 "styles.css":"29fdc80f22147656d1450eca9b7907dadf2eb1a6ef30d299909fe1eb5a14ba0e",
 "sw.js":"2c03c6cde2d74af4c7b89c062127bd5c981a59f61979ee46545ca892d514d684",
 "manifest.webmanifest":"e48c46fe8103b6ad7015eb7e7fbe2e1756405412414dac80592b5f2b0a785d00",
 "icons/icon.svg":"377cd4fa7b4ff64ecd8d4157a9aacc67aaedcede7b39b2f4082e60a0c3b1d606",
 "icons/apple-touch-icon.png":"7e321de521f7c91a8856a66e237b98bb48d36bc89c6246ab90cc0ffb4ce6e11b",
 "icons/icon-192.png":"455b1aa541ebd7574d441d82615efd6f02d277c2ecf727077aa274fbbbe74f05",
 "icons/icon-512.png":"b5509bdf65dc021a057dac3f6db52de87a5d13d64c34cdc5f8dfc677a4e4f18b",
}
def h(x):return sha256(x).hexdigest()
try:
    assert V02.exists(),"Missing verified v02 source directory; run v02 verifier first"
    encoded=PATCH_FILE.read_text(encoding="ascii").strip()
    patch=gzip.decompress(base64.b64decode(encoded,validate=True))
    assert h(patch)==PATCH_SHA,"v03 patch checksum mismatch"
    diff_text=patch.decode("utf8")
    changed=set(re.findall(r"(?m)^\+\+\+ b/([^\r\n]+)$",diff_text))
    assert changed=={"app.js","index.html","styles.css","sw.js","manifest.webmanifest"},"unexpected patch destinations"
    assert not V03.exists(),"destination already exists: refuse overwrite"
    shutil.copytree(V02,V03)
    p=run(["patch","--batch","--fuzz=0","--no-backup-if-mismatch","-p1","-d",str(V03)],input=patch,stdout=PIPE,stderr=PIPE)
    assert p.returncode==0,"patch failed: "+p.stdout.decode(errors="replace")+" "+p.stderr.decode(errors="replace")
    actual=set(str(x.relative_to(V03)) for x in V03.rglob("*") if x.is_file())
    assert actual==set(HASHES),"extra or missing v03 assets"
    for name,expected in HASHES.items():
        assert h((V03/name).read_bytes())==expected,"v03 member differs from submitted ZIP: "+name
    assert b"INTEGRATION_SYNTHETIC_V03_CONFIRM_BUTTON_4STORE" in (V03/"app.js").read_bytes()
    print("RESULT=PASS EXACT_V03_SITE FILES=9 PATCH_SHA="+PATCH_SHA+" ORIGINAL_ZIP_SHA="+SOURCE_ZIP_V03_SHA)
except Exception as e:
    print("RESULT=BLOCKED V03_BUILD "+repr(e),file=sys.stderr)
    sys.exit(1)
