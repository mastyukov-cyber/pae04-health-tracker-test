# PAE-04 FAST LANE 16 — v05.5.2 Keyboard UX Polish (synthetic-only)

**Baseline:** QA-approved TEST v05.5.1 `c8c5aee14d6b0d746d63aa5a0e568bb277fbe658`. The published TEST main at branch creation: `fcd8914f50330158d566e56811d62a0551a48865`.
**Safety:** Draft PR only; no publication or merge; no Mac, Obsidian Vault, Dropbox, production, prescriptions or real medical data.

## Problem confirmed in iPhone recording
- v05.5.1 fixed the bottom menu overlap with the keyboard.
- Keyboard remains open when scrolling into the pressure history, occupying much of the visible screen.
- iOS may still suggest "Автозаполнить контакт" when editing the note despite autocomplete=off. That is OS-controlled, and this patch **does not claim to suppress it**.

## Scope
1. Add a 44 px-accessible "**Готово · закрыть клавиатуру**" action, shown **only while the note textarea is focused** on mobile. Pressing it does **not** submit or clear the form.
2. Dismiss the form keyboard when tapping outside the form in the pressure section (e.g., the history panel) and when scrolling toward visible history with a real upward touch gesture. Ignore gestures originating inside text inputs/textarea to preserve editing.
3. Close active keyboard focus before `navigate(page)` moves between modules.
4. Maintain v05.5.1 sticky nav hiding, app pinch zoom, pressure validation, right-arm-only entry, indexedDB DB version 1 and backup format 3. Publish isolation via separate SW cache.
5. No contact/autofill data collection, no external requests or servers, no extra notifications/permissions.

## QA
- Playwright 1.65.0 in Chromium and WebKit, nine SHA256 resources, JS syntax.
- All v05.5.1 regressions (keyboard, database/offline, medicine/search, responsive geometry, 16px focus, date wheels, Data Safety, cross-origin restore and 10 sequential same-origin version switches), plus new note Done, history tap/swipe, navigation blur, no accidental DB write, iPhone-sized viewport test.
- Test fixtures are immutable old synthetic site trees for v05.3, v05.4, v05.5, v05.5.1; v05.5.2 new site is isolated in `site/`.
- **Real iPhone keyboard test still required**. Browser emulation does not reproduce native QuickType/autofill contact UI and visual viewport animations.

## Release gates
- [ ] Both engines fully PASS, SHA-256 match, syntax PASS.
- [ ] Draft PR created, main and previous PRs unchanged.
- [ ] Explicit owner permission for TEST publication only after QA.
- [ ] Visual iPhone acceptance after deployment, using fictional records.
