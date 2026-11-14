# PAE-04 — Runtime Migration Pilot (synthetic only)

## Locked scope
- Source branch: `sandbox/pae04-v0552-keyboard-polish`, commit `0b42de82aa2223e1f1e395542c3ead3c6858b4ca` (**same unchanged site and tests**).
- Target pilot branch: `sandbox/pae04-runtime-migration-pilot-v01`.
- Published TEST main: `fcd8914f50330158d566e56811d62a0551a48865` (v05.5.1), **do not modify**.
- Original immutable v05.5.2 source manifest: `qa/v0552-keyboard-polish/V0552_MANIFEST.json`; 9 site SHA-256 assets and DB schema v1 unchanged; 4 stores, v3 backups.
- Original regression: GitHub Actions [43621787298](https://github.com/mastyukov-cyber/pae04-health-tracker-test/actions/runs/43621787298), SUCCESS **376/376**, run duration **111 seconds**, Python **3.12**, Playwright **1.65.0**, Node.js **not explicitly pinned**.
- Target: Node.js **26 LTS**, Python **3.12**, Playwright Python **1.65.1**, Chromium **and** WebKit kept separate.

## Four levels (pilot only)
- **FAST** — Node 26/Python 3.12 selfcheck, all 9 hashes, JS syntax, compile existing Python tests; no browser.
- **STANDARD** — FAST and mobile UI, keyboard, navigation, pressure and medication filter tests; **80/engine**.
- **CRITICAL** — STANDARD and IndexedDB/Service Worker/offline, JSON backup integrity, iOS focus/zoom and 10 same-origin upgrade cycles & protected cross-origin restore; **168/engine**.
- **RELEASE** — CRITICAL plus rolling-date UX and leap-year tests; **188/engine, 376 total**. Automatic pilot push runs RELEASE, not a shortcut.
- Both engines execute each requested browser tier. A single matrix workflow replaces redundant new pipeline definitions **only within the pilot**.
- No required legacy checks removed or weakened, no historical QA rewritten.

## Involved repository inventory (read-only)
1. `mastyukov-cyber/pae04-health-tracker-test`: published main has a one-night **13 November 2026** workflow with Node 22 and Playwright 1.56.1; it only triggers when *its own workflow* changes, and points at historic integration-v02 paths absent from current main. Classify as **historical, do not start automatically**. Current TEST Pages workflow publishes immutable v05.5.1 source. v05.5.2 QA branch uses Python 3.12, Playwright 1.65.0, Node from runner.
2. `mastyukov-cyber/health-tracker-pwa`: main Cloudflare manual-deploy workflow uses Node 24; historical integration v02 Chromium/WebKit branch uses Node 22 and Playwright 1.56.1, with successful runs 12 November 2026. No modifications in this pilot.
3. `mastyukov-cyber/pae04-pressure-demo`: main medications preview QA uses Node 24 and `@playwright/test@1.65.0`; last relevant push run 12 November 2026. Historical day-QA and viewport branches separate. No modifications in this pilot.

## Baseline vs pilot (fill from GitHub Actions)
- Baseline: **111 sec** run, **376/376** PASS, Chromium/WebKit two separate browser engines.
- Pilot: **PENDING** at creation. Artifacts will contain exact Python, Node, Playwright, Chromium and WebKit versions, test counts, timing and synthetic screenshots. A failed pin means **BLOCKED**, not a downgrade.

## Safety
No real health values, production, TEST main, Vault, Dropbox, Mac, linked secrets, Supabase, historical hashes, existing PRs or existing workflow files changed. GitHub Actions `contents:read`; no deploy privileges or billable API credentials. Data Safety tests use only synthetic fixture files.
**Do not merge**, do not publish or alter required CI automatically. Promotion across other repos requires separate owner approval and a separate review.

## Next independent checks
1. Verify GitHub Actions job statuses and exact versions from `runtime.json`, `suite-summary.json` and logs.
2. Compare durations and full 376-check parity vs baseline; distinguish wall time from per-job time.
3. Confirm commit diff limited to **new** pilot workflow, scripts, requirements and this HANDOFF.
4. Release only after separate explicit approval. Real-device iPhone keyboard QA remains independent.
