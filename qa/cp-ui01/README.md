# PAE-04 CP-UI01 — Apple Light Comfort Home (synthetic, detached)
Parent: CP-MED05.1 PR #15, commit c69b75e2d82a381eae4dee2b9b9f99a6dc12636a.
Scope: only new qa/cp-ui01/** and .github/workflows/pae04-cp-ui01.yml.
No modifications to main, existing PRs, published TEST, production, or medical records.

## Functions
- Today: every manually recorded right-arm pressure/pulse measurement from the local TEST database.
- Yesterday: mean systolic/diastolic values; pulse averaged only from measurements that contain a pulse. A single reading is never labelled "average".
- Medications: permanent, course, as-needed; active course visible only when it has at least one date boundary and includes today. An undated course is retained in history but not asserted active.
- Yesterday's actual intake times: shown only for permanent medications and courses active on both days; never used as a scheduled time.
- Home checkbox: explicit confirmation, creates exactly one audited synthetic intake using existing changeIntake('marked'); re-enter journal for repeating/correcting an intake. Never auto-check at midnight.
- A−/A+: five levels; local-only preference storage. Responsive controls and readable labels. No reminders.
- Daily rollover: refresh on focus, visibility and once a minute while open.

## Integrity
The detached build copies the CP-MED05.1 candidate, leaving all source assets immutable.
Unchanged IndexedDB DB_NAME/DB_VERSION, stores and v3 JSON backup schema.
No real drug catalogue is used in tests; only Учебный препарат A/B/В fixtures.
CSP is not weakened; new home.js and home.css are explicitly precached for offline.
CI runtime: Node 26, Python 3.12, Playwright 1.65.1, Chromium and WebKit.
Fail closed on unexpected source markers, output collisions and runtime mismatch.

## Known product gaps (not to conceal)
- Scheduled medication time is not in existing medication schema. UI says "Плановое время не задано". Never infer it from yesterday's actual intake.
- Drug dictionary integration remains the separate CP-MED05.1 module; official real-world catalogue requires independent sourcing and licensing review.
- This is not a final iPhone release. iPhone Safari on real hardware and backup/restore acceptance are independent release gates.
- Original UI sections outside the home retain much of their previous layout; further Apple Light Comfort styling can follow after user assessment.

## QA status
NOT YET VERIFIED at creation. Rely on live GitHub Actions logs, not this text, for PASS/FAIL.
Do not merge or publish without explicit subsequent owner approval.
