#!/usr/bin/env python3
"""PAE-04 — synthetic runtime pilot. Fail closed, never access live medical data."""
from __future__ import annotations
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parent
engine = sys.argv[1]
assert engine in ('chromium', 'webkit'), 'Only independent Chromium and WebKit'
assert sys.version_info[:2] == (3, 12), ('BLOCKED_UNSUPPORTED_PYTHON', platform.python_version())
node = subprocess.check_output(['node','--version'], text=True).strip()
assert node.startswith('v26.'), ('BLOCKED_UNSUPPORTED_NODE', node)
version = importlib.metadata.version('playwright')
assert version == '1.65.1', ('BLOCKED_UNSUPPORTED_PLAYWRIGHT', version)
assert os.getenv('PAE04_SYNTHETIC_ONLY') == 'true', 'BLOCKED live-data boundary'
with sync_playwright() as pw:
    bt = getattr(pw, engine)
    browser = bt.launch(headless=True, args=['--no-sandbox'] if engine == 'chromium' else [])
    browser_version = browser.version
    browser.close()
report = {'status':'PASS','synthetic_only':True,'node':node,
          'python':platform.python_version(),'playwright':version,
          'engine':engine,'browser_version':browser_version,
          'source':'PAE-04 v05.5.2 immutable synthetic QA'}
out = root/'reports'/engine
out.mkdir(parents=True, exist_ok=True)
(out/'runtime.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print('RUNTIME_PROBE='+json.dumps(report,sort_keys=True,ensure_ascii=False),flush=True)
