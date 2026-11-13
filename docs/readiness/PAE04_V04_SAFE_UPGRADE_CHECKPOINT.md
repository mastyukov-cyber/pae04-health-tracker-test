# PAE-04 · v04 Safe Upgrade candidate · checkpoint 13.11.2026

**Status: PREPARED / LOCAL SYNTHETIC QA PASS / REAL BROWSER QA BLOCKED / REAL DATA NO-GO.**

This document registers the exact synthetic candidate built in the isolated ChatGPT sandbox. **The v04 site files are NOT committed to GitHub here, have NOT been published, and have NOT replaced the v03 or v02 builds.** Do not present this branch as deployable code until the byte-exact package is transferred and independently verified.

## Exact deliverable

- Conversation artifact: `PAE04_HealthTracker_v04_SAFE_UPGRADE_TEST.zip` (97,568 bytes)
- ZIP SHA-256: `9b2b1d697720ca85625ca6c2b85cb1f2d0e9ee6eb8c61f0fae6a508da3bde18c`
- v03→v04 unified patch SHA-256: `14f9eda87e1a80a9e8b4ddd9f0d3374670bff2e7f918440270da7527dda1c2e2`
- Nine site files; exactly five text assets changed (app.js, index.html, manifest.webmanifest, styles.css, sw.js); four icon assets byte-identical to validated v03.
- All candidate code remains **synthetic-only**, with the `Учебный препарат` name guard and local TEST DB name.

### Core candidate changes (implemented locally, not deployed)

1. Stable **candidate** DB name `PAE04_HT_STABLE_CANDIDATE_INTEGRATION_SYNTHETIC_SCHEMA1`, independent of build number; future changes would bump IndexedDB schema version without renaming the database.
2. Backup snapshot reads all four IndexedDB stores in one readonly transaction, rather than independent sequential store reads.
3. v1/v2/v3 backup preview → download a pre-import v3 checkpoint → user explicitly acknowledges downloaded file → reject changes in source DB via SHA-256 snapshot fingerprint → explicit confirmation → atomic four-store merge.
4. Reject stale overlapping import file previews, corrupted files and collisions; no destructive overwrite.
5. Version label corrected to `v0.2.1 SAFE UPGRADE TEST v04`, manifest `HT v0.2.1 v04 TEST`. Candidate-specific SW cache deletion prefix avoids purging v02/v03 caches.
6. Privacy/safety caveats shown inline: exporting JSON is plaintext, browser cannot verify physical file save, distinct *origins* required for STABLE/BETA isolation.

### Evidence and blocked checks

- Node VM tests (synthetic): **77/77 PASS per cycle, 154/154 overall**, two independent runs. Note some checkpoint assertions are structural (code-level), not end-to-end browser validation.
- ZIP integrity and patch reconstruction: **PASS** (unified patch reproduces exact nine v04 assets).
- Local real Chromium attempt: **BLOCKED** by environment network policy `net::ERR_BLOCKED_BY_ADMINISTRATOR` on localhost; no application browser scenario completed.
- Local WebKit: **BLOCKED** (Playwright bundled WebKit executable unavailable; no simulated substitutes).
- GitHub real Chromium/WebKit QA for v04: **NOT RUN**.
- iPhone Safari / installed PWA, real persistent storage, backup file physically verified: **NOT RUN**.
- No GitHub merge, Pages publish, Mac remote access, real health records, or Obsidian Vault operations.

### Gate for next step

Transfer the attached ZIP or exact patch into a new branch; verify SHA-256 of all nine rebuilt assets on Linux runner before executing real Chromium + WebKit E2E. Test checkpoint download, real IndexedDB, corrupted import, unchanged history and offline restart. Publish only after separate explicit user approval and iOS QA. Never put this candidate and actual STABLE on the same Pages origin. **No real data GO yet.**

## Verification SHA-256 of five modified files

| File | SHA-256 |
|---|---|
| app.js | `7837f6df9b82c5cb0e8a98789ba0326ba9e597c27f43154ab969b117dd9caea6` |
| index.html | `55053430f87db962cd0482e6ced92cb646dca717782d99143e891d9eb9eedcf6` |
| styles.css | `672770d0f732502ccfce33670ed167d12ba882ebc6bf50610616e6082c5fb90c` |
| sw.js | `db303798274e07d33947c748c0f3309bf813a6fd5dc7fea083f47bed872cbbd7` |
| manifest.webmanifest | `67b89a209c3e762066b2c1a55118933088810eda9a6f95db34c3dc95835a87dc` |
