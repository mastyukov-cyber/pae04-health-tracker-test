# PAE-04 v05.2 — Journals & Backup safety (synthetic only)

Baseline: TEST v05.1 pinned to `d341fc0d7805d2dd2e2881648c3168d9f1ef07e1`.
Source remains distinct from TEST main, production and real medical data.

## Features
- Pressure journal: local view-only search by pressure value, date and note, compatible with existing 7/30 day filter.
- Medicines: local view-only search by synthetic medication name, retains intake history and tracking.
- Backups: independently verify exported local JSON files for schema and SHA-256 without importing or changing IndexedDB. It detects tampering, corruption and malformed JSON, with explicit plaintext confidentiality warning.
- Cosmetics: improve history text contrast and reduce row whitespace.
- Keep IndexedDB name/version, all four stores, v3 backup format, original import checkpoints/conflict protection; no encryption or medical advice.

QA: 9 SHA-256 site files, 25 historical browser tests + 9 v05 UX + 29 viewport geometry + 13 new behavior tests per browser (Chromium and WebKit). No Pages deployment, no writes to main or Vault.

## Known limits
JSON backups remain plaintext, SHA-256 proves integrity only. Hard max 5 MB applies to selected backup files (same as v05.1 importer). Browser local storage is not guaranteed permanent. Never enter real medical records in synthetic TEST.

No publishing or merging until owner explicitly authorizes it.
