# PAE-04 CP-REAL02 · Separate Safari preview staging

This branch was created from the approved, verified CP-REAL01 candidate `c5ba0b48af0cf6c549a832bfdbc1a590168632dc`.

## Boundaries

- **Only** this branch receives the generated static site under `docs/`.
- Does NOT configure or activate GitHub Pages. It is a staging branch until the owner explicitly selects it in GitHub **Settings → Pages → Deploy from a branch**.
- Does NOT change `main`, the published Health Tracker TEST, other PRs or FINAL.
- Uses the same CP-REAL01 builder and reference catalog already verified with 188+19 tests in each of Chromium and WebKit. No application logic changes.
- Real medicine/supplement names and stated doses are present with user authorization; there are no actual pressure readings, intake log entries, credentials or medical records.
- Generated `docs/` includes offline assets and local-only IndexedDB code, `.nojekyll`, and `robots.txt` disallowing indexing.
- The hosted page, if later enabled, will have its own origin and **separate storage**. Its IndexedDB does not migrate automatically to the existing TEST or FINAL app.
- **One-time user action to enable after staging is verified**: GitHub repository `mastyukov-cyber/pae04-health-tracker-test` → Settings → Pages → Deploy from a branch → branch `sandbox/pae04-cp-real02-safari-pages` → folder `/docs` → Save.
- Do not enter real intake/pressure history without first explicitly exporting a backup; this is a test preview and its data could be lost on rebuild or host change.

## Acceptance

Stage workflow success, validate every staged asset, then owner sets Pages for this repository and the exact HTTPS URL is tested separately in iPhone Safari. No publication is claimed before verified availability.
