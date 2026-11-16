# PAE-04 CP-UX02-OFFLINE01 — isolated cache retention candidate

**Status:** SCOPED_SYNTHETIC_SW_QA_PASS / SAFARI_NOT_RUN / RELEASE_NO-GO
Parent QA commit: `e90c10d9fc88c5d581bfd50258420fa677bd80a7` · old QA ZIP Git blob `7434118c85d8fc96b6d2a8905e669106e48d114d`.
Reason: existing SW activation deleted all old app-shell caches immediately despite comment about preserving older tabs.
Change: `sw.js` and `offline_status.js` only. Cache name rotated. Keep current plus up to 2 newest previous PAE-04 caches. Unrelated caches untouched.
Synthetic service worker install/activation tests: **21/21 PASS**; 0, 1, 2 and 4 previous caches, 15 assets precached, unrelated caches, client claim.
Does NOT prove old tab compatibility in Safari; `skipWaiting` and `clients.claim` remain. Full browser/IndexedDB/restore/iPhone QA NOT RUN.
TEST main, Pages, GitHub Actions and production not changed; do not deploy without separate approval.
