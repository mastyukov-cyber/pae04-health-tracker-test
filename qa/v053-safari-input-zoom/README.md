# PAE-04 FAST LANE 08 — v05.3 Safari Input Zoom Fix (synthetic only)

Source snapshot: `4bb075108e6903dd60e6dccef56b6627089336e9`. Original PWA JavaScript, IndexedDB schema, all four stores, backup JSON v3 and icons are byte-identical to v05.2.

Fix: minimum computed font size **16px** in input (except checkbox/radio/file/hidden), select and textarea, including search, pressure, medicine, intake time and date. Preserve `<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">` with pinch-to-zoom enabled. Independent Service Worker cache v05.3.

QA: nine exact SHA-256 hashes; Chromium/WebKit Playwright 1.65.0, all existing regressions plus 9 widths in mobile emulation, focus on search fields and dynamically added time inputs. Automated emulation does NOT prove native Safari's OS-level zoom behavior: user must visually accept on iPhone.

No publishing, TEST main changes, real medical data, Mac, Vault, Dropbox or production. Draft PR remains unmerged until owner approval.
