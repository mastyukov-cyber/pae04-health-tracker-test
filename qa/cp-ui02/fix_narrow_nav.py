#!/usr/bin/env python3
"""Apply a narrow-screen fix ONLY to the detached synthetic CP-UI01 site.
No source, main, DB schema, backup or live data changes.
"""
from pathlib import Path
import sys
site=Path(sys.argv[1]).resolve()
marker="/* CP-UI02: 320px high-font navigation overflow fix */"
css=site/"home.css"
meta=site/"CP_UI01_BUILD.json"
if not css.is_file() or not meta.is_file() or marker in css.read_text(encoding="utf-8"):
    raise SystemExit("BLOCKED: candidate missing or fix already applied")
text=css.read_text(encoding="utf-8")
if "body .nav-item{font-size:calc(14px * var(--ht-home-scale))}" not in text:
    raise SystemExit("BLOCKED: unexpected original navigation rule")
fix="""\n/* CP-UI02: 320px high-font navigation overflow fix */
@media(max-width:355px){
  body .sidebar{min-width:0;max-width:100%;gap:0}
  body .sidebar .nav-item{
    flex:1 1 0;min-width:0;width:0;
    padding:7px 1px;
    font-size:calc(10px * var(--ht-home-scale));
    text-align:center;white-space:normal;overflow-wrap:anywhere;
  }
  body .sidebar .nav-item span:last-child{
    max-width:100%;min-width:0;overflow-wrap:anywhere;
  }
}
"""
css.write_text(text+fix,encoding="utf-8")
print("RESULT=PASS CP_UI02_NARROW_NAV_PATCH=DETACHED_ONLY")
