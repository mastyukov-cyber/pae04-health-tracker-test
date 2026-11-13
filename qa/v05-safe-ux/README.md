# PAE-04 v05 SAFE UX — synthetic branch only

Base: TEST main commit 44cd127160248ea7dfeba2aaf781142a5ae4d973
Immutable v04.1 application snapshot: b400558fd8c8147aeda50402c7aa634bdb8d455f

Changes: readonly filters for pressure history (all / 7 days / 30 days), intake history (all / confirmed / cancelled), mobile layout, visible v05 label, new isolated Service Worker cache.
Safety invariants: same IndexedDB name/version/four stores, same backup v3 format, no remote endpoints, no production, no real medical records, no publishing, no automatic migrations, no Vault.
QA: original v04 browser script copied unchanged, plus v05 synthetic mobile UX regression, Chromium and WebKit using Playwright 1.65.0. Actions never deploy to Pages.
Source icons are copied by Git blob identity, and verified byte-identical to v04.1.
Known limitations: export JSON is plaintext; browser storage is not a secure backup; this remains TEST only.
No merge/publish without a separate owner approval.
