# PAE-04 CP-UI02 — iPhone home: deep synthetic visual & calendar QA

Base: CP-UI01 PR #16 / commit 6803a01ed2ec7838f7902029439ffeefa04b93e3.
No edits to PR #16, existing application, main, TEST or any personal/real medical records.

Only **new** files:
- qa/cp-ui02/tests/deep_visual_qa.py (synthetic Browser E2E; four screenshot artifacts/engine)
- .github/workflows/pae04-cp-ui02.yml (Node 26, Python 3.12, Playwright 1.65.1, Chromium & WebKit)
- this README

Assertions: fake dates Nov 14/15/16; average vs single reading; missing pulse excluded; original right-arm records; permanent, course, as-needed; ended and future courses; yesterday's actual intake time; situational historical intake hidden on home; daily rollover; new-day unchecked; font and 320px layout; IndexedDB row counts unchanged.

CI creates temporary site under qa/cp-ui02/generated-site, never touches the source. All screenshots show strictly invented educational drug labels, not actual medicine names. Screenshots and technical logs are uploaded as GitHub Actions artifacts, not Dropbox.

Acceptance: both browser suites PASS, no source/schema/backup changes. No release or merge without separate owner authorization. Real iPhone Safari device QA and official drug catalogue validation remain separate stages.