# PAE-04 v05.4 — Day / Month / Year wheel picker

Synthetic-only candidate, not published and not merged.

## User experience
- Primary date input is a custom scroll-snap wheel with **separate day, month, year columns**, native clock picker for pressure time, confirm/cancel, keyboard arrow and Escape support.
- Four entry points: pressure measurement datetime, intake date, course start and course end. A course boundary can be cleared.
- Retains underlying `type=date` / `type=datetime-local` fields and ISO `YYYY-MM-DD` / `YYYY-MM-DDTHH:mm` values. A wheel selection only updates the form; it **does not** write to IndexedDB until the existing explicit save/confirm flow.
- Handles leap years, varying month lengths, date clamping, and preserves all four stores, DB version 1, backup format 3, unchanged arm right.
- Year wheel range: **1900–2100**, clearly surfaced if a date lies outside that range.
- Avoids calendar UI for the new primary controls and maintains user pinch-to-zoom (no max-scale restrictions).
- A native iPhone Safari visual QA is still required: automated WebKit is not a real iOS device.

## Safety and delivery
- Entirely synthetic offline PWA; no external network, paid API, server or notifications.
- Source baseline v05.3: `74975f15904a4c99e068a31e6030e12a21bf3c21`. Separate TEST main remains on published v05.3. No production, Mac, Obsidian Vault, real records, Dropbox or medical prescriptions touched.
- QA runs in GitHub Actions Playwright 1.65.0 Chromium and WebKit with 9/9 SHA256, previous regression tests, focused date tests including leap/invalid-day/cancel/export/med-course and mobile geometry. Tests use only synthetic data.

Reminder feature with medication names recorded as specification in `REMINDERS_V056_SPEC.md`, but **not implemented in v05.4**.
