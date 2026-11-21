# PAE-04 FAST LANE 14 — v05.5.1 iPhone Keyboard UX Fix (synthetic only)

Based on released and QA-approved v05.5 source commit `e50222c43190045902885ee8330bb8dbc6cf6e90`. Publish/TEST main at change start: `b032a8dccb33cb7ac6f84736cb1e6993d2b7a03c`.

## iPhone bug from user's real-device video
- Mobile sticky bottom menu lifts to the top edge of the virtual keyboard while typing pressure values.
- iOS QuickType can offer **«Автозаполнить контакт»**, including personal contact data. This originates in the operating system and cannot be absolutely disabled by the PWA.
- Form scroll and focus jump due to reduced visual viewport and the sticky navigation.

## Fix in this isolated build
1. For mobile screens <=740px, hide the sticky bottom navigation while editable controls are focused or the iOS VisualViewport is reduced by >160px; restore when the keyboard disappears. Never disable pinch zoom.
2. Set per-field `autocomplete=off`, `autocorrect=off`, `autocapitalize=off`, `spellcheck=false`, `enterkeyhint=next` on numeric BP/pulse controls. Safari may ignore autofill preferences, so no false guarantee is made.
3. Enter moves systolic -> diastolic -> pulse -> note without submitting prematurely.
4. On confirmed pressure save, explicitly blur editing focus, restore navigation and preserve the existing readback-verified IndexedDB write. Validation errors leave the form populated for correction.
5. Service Worker cache isolated as v0551. All 9 resources SHA-256 checked. No DB schema change, no backup migration, no server/cloud.

## QA
- Existing 146 browser tests/engine from v05.5 plus new focus/autofill/keyboard-hide checks on 320–740px viewports; desktop remains unmodified.
- v05.3/v05.4/v05.5 original snapshots (synthetic) used for 10 same-origin upgrades, plus v05.5.1.
- **Important**: automation cannot reproduce native iOS's QuickType "Autofill contact" suggestion, physical software keyboard or all VisualViewport animations. A real iPhone test is mandatory before accepting this fix.

## Security boundaries
No publication, TEST main change, production, Mac/RDC, Dropbox, Vault, real medical data or existing PR merges. Separate owner approval for TEST release after successful synthetic QA. Use only fabricated BP and medicine entries.
