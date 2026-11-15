# PAE-04 — CP-REAL01 | Personal iPhone Preview

Status: **DRAFT, NOT DEPLOYED**. Base: CP-UI02 PR #17 at efc8682996239fa49e30445fb132028a6eb6ea9c.

Owner has explicitly authorized using their **real drug names and reported doses** in the TEST workflow. Published test material contains 10 medication/supplement names, strengths and general category — NO actual taken-at log, pressure entries, diagnosis files, credentials or medical scans. These inputs are *not new prescriptions*. In particular, the Capoten 25 mg **marketed tablet strength** is distinct from the unconfirmed personal dose; Betaloc ZOK personal amount is 12.5 mg, not inferred to equal tablet strength.

## Operation

1. Build the existing CP-MED05.1 and CP-UI01 candidate into a completely new CI directory.
2. Apply CP-UI02 confirmed 320px layout fix in that detached directory only.
3. Apply CP-REAL01 adapter to this new directory only: real catalog entries, real name validation, home dose labels, offline precache, optional "Загрузить мои препараты" button.
4. The initial browser profile is EMPTY. On explicit click, one transaction first checks all four stores are empty, then adds 10 medication records. It never writes pressures or intake history.
5. Manual new name entry still uses medication suggestion/duplicate guard and requires explicit human confirmation.
6. No change to IndexedDB schema (version 1, four stores) or v3 backup format.
7. CI runs Node 26 / Python 3.12 / Playwright 1.65.1 in Chromium and WebKit, with strict failures and screenshots.
8. NO Pages deployment, NO merge and NO transfer to iPhone yet. Release requires explicit owner approval and real Safari device QA.

## Known gaps

- Scheduled times are not modeled by v05.5.2. Real morning/evening notes are descriptive only and do not create reminders.
- Historical medication records are not imported automatically. Completed probiotics course is preserved as a historical **card**, without invented intake events.
- This QA catalog is limited to 10 selected products. Full official catalog ingestion and licensing remain separate.
- Pending evaluation: app-wide font scaling for all detailed pages and real iPhone storage/backup migration.

## Recovery

Do not merge Draft PR. Dispose of CI-generated site or separate preview origin. No modifications to main/TEST/FINAL, original PRs, Mac, Obsidian Vault, Dropbox or real IndexedDB user data.