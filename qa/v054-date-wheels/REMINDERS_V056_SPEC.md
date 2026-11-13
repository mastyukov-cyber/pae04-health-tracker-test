# PAE-04 — v05.6+ Optional Medication Reminders (SPEC ONLY)

Approved concept — **not implemented or enabled in v05.4**.

- Master switch off by default, with independent switches for each medication.
- Notifications **must display the medication name** (explicit owner requirement), but not the dose by default.
- Time schedule per medication. Regular/course medications only initially; as-needed medications must never receive recurring reminders without a new design decision.
- If the matching time-slot intake was marked, do not repeat the reminder for that slot; tests must verify no double notifications.
- iPhone lock-screen disclosure: medicine names may be visible to anyone who sees the device.
- User must explicitly grant notification permission; no request before enabling reminders.
- Browser PWA background notifications on iOS may require install-to-Home-Screen, HTTPS, notification permission and a Push delivery service. GitHub Pages alone cannot reliably schedule closed-app/offline notifications.
- Prefer privacy-preserving design with no names/medical schedules on an external Push server unless explicitly authorized, and test missed/not-delivered states without false promises.
- Use only fictitious medication names and synthetic scheduled pushes in QA.
- Separate implementation, security review, TEST release gate, and owner confirmation. Never modify prescriptions.

Sequence: v05.4 custom date wheels -> v05.5 final core QA -> v05.6+ opt-in reminders, after safety/design approval.
