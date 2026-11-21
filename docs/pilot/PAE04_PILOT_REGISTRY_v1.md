# PAE-04 · Pilot Registry v1.0 (template only)

**Status: PREPARED / NO-GO FOR REAL RECORDS.** This is an anonymized coordination registry for a future three-person, voluntary PWA pilot. Do **not** store medical readings, medicine names, full names, contact details, emails, Apple IDs, backups, cookies or IP addresses in this file or GitHub issues.

## Participants (only anonymous labels)

| Tester ID | Device type | OS version | Browser / PWA mode | PWA build | Consent to pilot | Synthetic QA | Real-data GO |
|---|---|---|---|---|---|---|---|
| TESTER-01 | TBD | TBD | TBD | TBD | Pending | NOT RUN | NO-GO |
| TESTER-02 | TBD | TBD | TBD | TBD | Pending (individual) | NOT RUN | NO-GO |
| TESTER-03 | TBD | TBD | TBD | TBD | Pending (individual) | NOT RUN | NO-GO |

The owner's consent does not cover the other testers. No account sharing or cross-participant health data access.

## Bug registry (no medical values)

| Bug ID | PWA version | Device / OS | Reproduction steps (with synthetic fixtures) | Severity | Status | Verified fix / QA run |
|---|---|---|---|---|---|---|
| PAE04-MIG-001 | v02 -> v03 | Chromium/WebKit Linux | Create synthetic pressure in v02; open v03 on same origin; prior item not visible | BLOCKER | CONFIRMED | GitHub Actions #43388311474 |
| PAE04-ISO-001 | v02/v03 | Chromium/WebKit Linux | Same-origin paths can access prior IndexedDB by name | BLOCKER | CONFIRMED | GitHub Actions #43388311474 |
| PAE04-SW-001 | v02/v03 | Chromium/WebKit Linux | Inspect cache names after activating v03; browser outcomes differ | HIGH | OPEN | GitHub Actions #43388311474 |
| PAE04-VER-001 | v03 | Source audit | Manifest short name says v031 rather than v021 | MEDIUM | OPEN | Await next isolated candidate |

## Before any real-data GO (all mandatory)

- [ ] Separate-origin STABLE/BETA design and safe installation.
- [ ] Stable database namespace and tested upgrade behavior; explicit backup before any migration.
- [ ] Real iPhone Safari regular-mode **and** Home Screen offline/close/reopen/storage persistence QA (synthetic data).
- [ ] Backup export verified to exist in user's private storage; v1/v2/v3 restore, corruption and rollback verified.
- [ ] Verify no medical values in GitHub logs, analytics, network requests or crash diagnostics.
- [ ] Explain clearly that exported JSON backup is unencrypted; agree a private storage and retention procedure.
- [ ] Informed voluntary consent from each participant; independent accounts/storage.
- [ ] Owner authorizes **specific** stable build, publication and real-data pilot. Never infer approval from synthetic TEST acceptance.

## Reporting rules

Report issues with a synthetic example and a redacted screenshot. Never send real blood pressure, medicine identity, personal notes or backup exports to GitHub, Dropbox or ChatGPT without separate, specific authorization.

**Reference:** synthetic REAL-DATA READINESS diagnostic [GitHub Actions #43388311474](https://github.com/mastyukov-cyber/pae04-health-tracker-test/actions/runs/43388311474). Test success confirms blockers, **not** real-data readiness.
