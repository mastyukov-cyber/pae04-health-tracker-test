# PAE-04 CP-UX02 · Synthetic integrated candidate

**STATUS:** SOURCE_VERIFIED / SCOPED_STATIC_QA_PASS / BROWSER_NOT_RUN / RELEASE_NO-GO

Original TEST archive: 84,089 bytes SHA-256 `0abb256031187036e8d282eaedc08ffaf970e9de1cffd7cda7814cc84fb8c4cb` pinned to `12e63a63b7a76dd903b71abfd536e7dffeff11cb`.
New stored-ZIP candidate from original 17 files; changes limited to app.js, index.html, manifest.webmanifest, med_guard.mjs, offline_status.js, styles.css, sw.js.
Static/logic checks 40/40 PASS. No claims of browser QA.
Features: one medicine name field, Russian aliases HemoHIM and MSM, optional per-intake rational quantities, collapsible cancelled records, smaller QA banner. DB and backup versions remain unchanged.
**NOT RUN:** Python apply_release.py, Node 26, Safari, Chromium, offline, backup restore, iPhone. **RELEASE NO-GO.**
TEST main, Pages, Actions, production, Supabase, Vault and real medical records unchanged.
