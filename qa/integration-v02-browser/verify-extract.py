#!/usr/bin/env python3
"""PAE-04 synthetic TEST only: strict byte identity and safe extraction.
Never extract unverified archives, never read production medical data.
"""
from pathlib import Path, PurePosixPath
from hashlib import sha256
from zipfile import ZipFile
import stat
import base64
import sys

ROOT=Path(__file__).resolve().parent
SOURCE=ROOT.parent.parent / "_test_source" / "site-v02-exact.zip.b64"
OUT=ROOT / "site-v02"
ZIP_SHA="2f511cc1211e998f18c56724cff580461b759118604e98a85d8e9706dcbd403a"
FILES={
 "app.js":"861c3afb0db8b06f6e61e4e69fdeaa49b5ddf533f817a3bc37f52ed54c642845",
 "index.html":"a5d51c7b5cf4e557cc27523423b34281473882373bb72bf7b63f32f12a9c80bc",
 "styles.css":"7d1ef4179482e942412a01e06980d02c5d189a3f7ec6e3a64ca8d620145d41d4",
 "sw.js":"b2b2b53c81970512d7b6bd577dfecaffd04903d5a81f674cb9a14445a919be34",
 "manifest.webmanifest":"454d950fd021d40ec2052568ca1214bb4fe40fd80537fe46080e8bbb13242115",
 "icons/icon.svg":"377cd4fa7b4ff64ecd8d4157a9aacc67aaedcede7b39b2f4082e60a0c3b1d606",
 "icons/apple-touch-icon.png":"7e321de521f7c91a8856a66e237b98bb48d36bc89c6246ab90cc0ffb4ce6e11b",
 "icons/icon-192.png":"455b1aa541ebd7574d441d82615efd6f02d277c2ecf727077aa274fbbbe74f05",
 "icons/icon-512.png":"b5509bdf65dc021a057dac3f6db52de87a5d13d64c34cdc5f8dfc677a4e4f18b",
}
def checksum(data):
    return sha256(data).hexdigest()
try:
    b64=SOURCE.read_text(encoding="ascii").strip()
    data=base64.b64decode(b64,validate=True)
    assert checksum(data)==ZIP_SHA, "source ZIP SHA mismatch"
    import io
    with ZipFile(io.BytesIO(data)) as z:
        assert z.testzip() is None, "ZIP CRC check failed"
        names=z.namelist()
        assert len(names)==len(FILES) and set(names)==set(FILES), "unexpected archive members"
        for item in z.infolist():
            p=PurePosixPath(item.filename)
            assert not p.is_absolute() and ".." not in p.parts and len(p.parts)<=3,"unsafe path"
            assert not stat.S_ISLNK(item.external_attr>>16),"symlink"
            assert item.file_size<=800_000,"oversized member"
            assert checksum(z.read(item.filename))==FILES[item.filename],"member SHA mismatch "+item.filename
        for name in names:
            dst=OUT / name
            dst.parent.mkdir(parents=True,exist_ok=True)
            dst.write_bytes(z.read(name))
    print("RESULT=PASS BYTE_EXACT_V02 SHA256="+ZIP_SHA+" N_FILES="+str(len(FILES)))
except Exception as exc:
    print("RESULT=FAIL BLOCKED_SHA_OR_ARCHIVE "+repr(exc),file=sys.stderr)
    sys.exit(1)
