# PAE-04 Data Safety v05.5 — synthetic-only branch

Baseline: v05.4 `aefffde27cc8bcd6d4922e724120fda4acd25c07` (QA PASS), published TEST remains v05.3 `6bb1149fc69d8232fb7a4a253475213101f7b2ad`.

## Scope implemented
- Add, delete and intake transaction success now require **fresh read-after-commit validation** (including the intake audit event). A failed post-commit check explicitly warns not to repeat writes blindly.
- Startup and on-demand **read-only local data integrity** check of four IndexedDB stores (relationships, IDs, time constraints, SHA-256 of consistent snapshot). This does NOT create or replace external backups.
- Browser storage persistence is reported read-only where supported, without requesting permission or changing settings. PWA storage cannot be guaranteed permanent.
- Backup inspection distinguishes integrity-valid JSON matching the current DB from an outdated but valid JSON. A successful download is **not** represented as verified safe external storage.
- After importing across devices, all imported records are compared with a fresh DB snapshot. Existing pre-import checkpoint, manual confirmation and conflict prevention remain intact.
- DB_NAME, DB_VERSION=1, four stores, JSON backup v3, no servers and no clinical decisions. All fixture data is fictional.

## QA
- Chromium and WebKit Playwright 1.65.0; nine SHA-256 checks, preserved browser/UX/offline/wheel/no-zoom suite.
- New QA: storage status and read-only scans; fresh readback of pressure/medication/intake + audit; valid but outdated JSON; tamper rejection; **cross-origin restore with mandatory checkpoint and confirmation**; exact data preservation across **10 reload/upgrade cycles** among v05.3, v05.4 and v05.5 at one origin.
- QA logs and screenshots contain **synthetic data only**.

## Conditions NOT yet met for live pilot
- Native iPhone Safari real-device verification and unattended/long-duration recovery tests.
- App does not automatically create an independent encrypted backup, cloud storage, or cross-device sync.
- IndexedDB data can be lost if the PWA/site data are removed or iOS evicts storage; user must keep exported copies elsewhere.
- TEST deliberately requires names beginning with «Учебный препарат» and is **not** for real medical use.
- Encryption and recovery key strategy, separate pilot origin and privacy controls are not implemented.
- Pressure deletion currently has no undo/trash; separate design review is required before real-data pilots.

**NO MERGE / NO TEST DEPLOY / NO PROD / NO MAC / NO VAULT / NO REAL PATIENT DATA.**
