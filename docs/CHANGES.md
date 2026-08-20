# Changes — FIN Login and README Compliance

Two things happened in this pass: a myGov-style FIN login replaced the role dropdown across web and mobile, and every README promise that was not actually wired got completed. Details of the audit are in `README_AUDIT.md`; test results are in `QA_REPORT.md`.

---

## 1. Authentication

The backend contract did not change. `current_user()` still resolves the `X-Demo-User` header to a user row, and `require(*roles)` still guards every endpoint. What changed is where the clients get that email: previously a hardcoded constant or a dropdown, now the response from login.

**`backend/app/main.py`**
- `DEMO_FIN_DIRECTORY` — synthetic FIN → (email, role) fixtures, server-side only.
- `LoginIn` — validates a 7-character alphanumeric FIN and a known role.
- `POST /auth/login` — 404 unless `DEMO_MODE=true`; 401 when the FIN is unknown or its role does not match the selection; rate-limited; writes a `DEMO_LOGIN` audit row that records the user id and role but **never the FIN**.

**Web (`frontend/`)**
- `app/login/page.tsx` — the portal screen: FIN field, three roles, Azerbaijani labels, a DEMO badge, and the "Sintetik demo məlumatı — real dövlət xidməti deyil" disclaimer. Styled in the same blue, centred-card idiom as the mobile screen without reproducing any myGov or ASAN mark.
- `lib/session.ts` — session storage plus the role→label, role→segment, and role→landing maps used by every guard.
- `lib/api.ts` — `api`/`mutate`/`request` no longer take a role argument; they read the acting email from the session. Added `uploadFile` and `fetchBlob` so document upload and the demo-report download stop hand-rolling `fetch` with a hardcoded header.
- `components/SessionGate.tsx` — redirects to `/login` without a session, shows a 403 card when the URL segment does not match the session role, and provides the logout button and panel header.
- `app/page.tsx`, `app/[role]/[section]/page.tsx`, `app/[role]/page.tsx` — dropdown removed; roughly forty hardcoded `"doctor@demo.az"` / `"admin@demo.az"` / `"patient@demo.az"` arguments deleted.

**Mobile (`apps/patient-mobile/`)**
- `app/(auth)/login.tsx` — FIN input with the same three roles; Həkim and Xəstəxana authenticate but are told the role lives in the web panel.
- `services/session.ts` — stores the whole `DemoUser` in SecureStore (localStorage on web) behind an in-memory cache, replacing `startDemoSession()`.
- `services/api.ts` — resolves the header from the session and adds `login()`, which deliberately sends no auth header.
- `app/documents/upload.tsx` — the demo-report download was still sending a hardcoded `patient@demo.az`; it now uses the session email.
- `types/api.ts` — `DemoUser.role` widened to all three roles; the unused `DemoEmail` type removed.

## 2. README gaps closed

Backend additions:
- `GET /insurance/plan` — returns the patient's real `insurance_coverage` rows, replacing a hardcoded coverage table in the app.
- `GET /safety/events` — extended with an additive `nurse_tasks` array per event. Existing fields are unchanged, which is why the pre-existing tests still pass.

Wired up in the UI (all endpoints already existed and were simply unreachable): consent revocation, lab comparison, the `care_navigation` specialty suggestion, appointment reschedule, document review after leaving the upload screen, the doctor's patient timeline, admin departments, capacity recommendations, and the safety audit trail.

One of these was a bug rather than a gap: the mobile **Reschedule** button opened the booking flow, which called `POST /appointments` and created a duplicate appointment instead of moving the existing one.

## 3. Files needing manual testing

Automation covers the backend and both builds, but these need a browser or a device:

- `frontend/app/login/page.tsx` — all three FIN codes, and the wrong-role 401 message.
- `frontend/components/SessionGate.tsx` — visit `/admin/tasks` with no session (expect a redirect) and as a doctor (expect the 403 card).
- `apps/patient-mobile/app/(auth)/login.tsx` — FIN `1AZ0001` on a physical iPhone through Expo Go, and session persistence across an app restart.
- `apps/patient-mobile/app/documents/[id].tsx` — open a pending document and confirm it after leaving the upload screen.
- `apps/patient-mobile/app/appointments/booking.tsx` — reschedule and confirm the appointment count does not grow.
- `frontend/app/[role]/[section]/page.tsx` — browser document upload, which now goes through `uploadFile`/`fetchBlob`.

## 4. Open risks

- **The session is not real authentication.** It is unsigned JSON in `localStorage` / SecureStore, editable by hand to another demo email — exactly as the old dropdown allowed. This is a property of the demo `X-Demo-User` contract and must be replaced before any real deployment.
- **The login rate limit is global.** `enforce_rate("login", 30, 60)` uses one shared bucket rather than a per-client key, so 30 attempts in a minute throttle everyone. Fine for three demo accounts, wrong for production.
- **No server-side route protection on the web.** Guards are client-side, so a hard refresh briefly shows "Sessiya yoxlanılır…". The backend still rejects every unauthorised request, so this is a presentation issue, not an access-control one.
- **`healthtech-platform/` is a stale, untracked duplicate** of the whole project and still contains the old dropdown code. Nothing here was applied to it. It should be deleted to avoid running the wrong copy.
- **FIN codes are documented in the READMEs and shown on the login screens.** That is intentional for a demo, and they map only to synthetic data, but the pattern must not carry over to anything real.
