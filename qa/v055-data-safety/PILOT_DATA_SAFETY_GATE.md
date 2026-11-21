# PAE-04 — Stable Pilot / Data Safety Release Gate v1

This checklist must be PASS before anyone is instructed to use PAE-04 as their only medical record system.

- [ ] 9/9 hashes, all Chromium/WebKit old and new QA, offline and 10 upgrade cycles.
- [ ] Actual iPhone (Safari + installed PWA) preserves 4-store snapshots and the same records across ≥10 app updates and full device reboots.
- [ ] Cross-device restore from an exported v3 JSON with identical IDs, intakes and audit logs; negative and corrupt-file cases; no overwrite.
- [ ] Independently retained and verified external backup in **protected storage**; manual backup workflow documented and usable by beginners.
- [ ] Encryption / password and key recovery for any hosted storage of medical records, or clear documented local-only scope without false assurances.
- [ ] Dedicated PILOT **origin** distinct from TEST; same-origin and cross-origin migration must not be conflated.
- [ ] Ability to keep medication/pressure records recoverable after accidental user action; delete-with-undo/archive design and QA.
- [ ] Private medical data and clinical risk review; fictional-only test policy lifted only with separate explicit owner approval.
- [ ] iPhone-level review of OS storage pressure, app deletion/reinstall, browser-data removal, app offline restarts and device replacement.
- [ ] Separate owner authorization for published TEST, then PILOT, then real-data use. Do not mark this gate PASS by GitHub Actions alone.

**Current:** IN PROGRESS; synthetic browser PASS does not mean production-ready. No automatic backups.
