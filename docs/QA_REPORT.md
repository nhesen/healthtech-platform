# QA Report — FIN Login Release

Platform: `healthtech-platform` monorepo
Environment: Windows 11, PowerShell, Python 3.13, Node 22, Expo SDK 54
Scope: the myGov-style FIN login for Patient, Doctor, and Hospital Admin, plus a full regression pass.

---

## 1. Automated checks

| Suite | Command | Result |
|---|---|---|
| Backend | `$env:PYTHONPATH="backend"; python -m pytest backend\tests -q` | **44 passed** |
| CV service | `$env:PYTHONPATH="cv_service"; python -m pytest cv_service\tests -q` | **2 passed** |
| Frontend build | `cd frontend; npm run build` | **Success** — 5 routes compiled, `/login` emitted as static |
| Mobile typecheck | `cd apps/patient-mobile; npm run typecheck` | **Success** — `tsc --noEmit`, 0 errors |
| Mobile doctor | `cd apps/patient-mobile; npx expo-doctor` | **18/18 checks passed** |

The backend count went from 28 to 44: the 28 pre-existing `X-Demo-User` tests were untouched and still pass. Sixteen were added — 9 login tests, 1 end-to-end demo flow, and 6 covering the endpoints wired up while closing the README audit gaps (`backend/tests/test_readme_gaps.py`: insurance plan matrix, lab comparison, nurse-task visibility, admin-only department/recommendation/audit views, consent revocation, and reschedule-without-duplication).

> On Windows use `$env:PYTHONPATH="backend"` instead of the `PYTHONPATH=.` form shown in the README. Add `-p no:cacheprovider` when the repository sits in a OneDrive folder, otherwise pytest emits `WinError 5` cache warnings (harmless, but noisy).

---

## 2. New login tests

`backend/tests/test_auth_login.py` — 9 tests:

| Test | Asserts |
|---|---|
| `test_login_returns_demo_identity_for_every_role` | All three FIN/role pairs return 200 with the correct email, role, id, and name |
| `test_login_accepts_lowercase_fin` | `1az0001` normalises to the patient identity |
| `test_login_rejects_role_that_does_not_match_the_fin` | Patient FIN + `DOCTOR` → 401; admin FIN + `PATIENT` → 401 |
| `test_login_rejects_unknown_fin` | `9ZZ9999` → 401 |
| `test_login_validates_fin_format` | `12`, `1AZ00012`, `1AZ 001`, `1AZ-001` → 422; unknown role → 422 |
| `test_login_never_echoes_the_submitted_fin` | The FIN appears in neither the success nor the failure response body |
| `test_login_session_email_authorises_protected_endpoints` | The returned email opens `/appointments`, `/auth/me`, `/tasks`, and a doctor is still 403 on `/tasks` |
| `test_login_is_unavailable_when_demo_mode_is_disabled` | `DEMO_MODE=false` → 404 |
| `test_demo_reset_does_not_invalidate_a_logged_in_session` | `POST /demo/reset` leaves the admin session valid |

### Status-code decisions

The task asked for 401 on a bad FIN or role. A malformed FIN returns **422**, not 401, because Pydantic rejects it at the schema boundary before the handler runs. This is deliberate: it separates "you sent something that is not a FIN" from "this FIN does not exist", and it never reveals which FINs are real. Both clients map 422 to the user-facing message *"FIN 7 simvoldan ibarət olmalıdır."* and 401 to *"FIN və ya rol yanlışdır."*, so the distinction is invisible to the user while staying accurate in the API.

---

## 3. End-to-end demo flow

`backend/tests/test_demo_flow_login.py` runs all eight README demo steps, and **every role enters through `POST /auth/login`** — no hardcoded email and no role dropdown. Result: **passed**.

| Step | Verified |
|---|---|
| 1. Hasan uploads a document and confirms the extracted values | Upload returns 201, status is not `CONFIRMED` before review, review → 200, confirm → 200 with a `record_id`, and re-confirming → 409 |
| 2. HbA1c rise and endocrinology suggestion | `trend == "increasing"`, `care_navigation.suggested_specialty` contains "endocrin" |
| 3. Dr. Leyla booking: 60 AZN / 48 AZN insurance / 12 AZN patient | Exact triple asserted, then the slot books at 201 |
| 4. Consent unlocks the doctor brief | Brief is **403 before** consent and **200 after** — the ordering is asserted, not just the success |
| 5. Doctor approves the consultation note | AI draft returns 201, status walks to `IN_PROGRESS`, the approved note reaches the patient timeline |
| 6. Admin resolves blocker #104 and frees the bed | Capacity `available` increases by exactly 1 after task → discharge → cleaning |
| 7. CV fall-risk updates Room 204 | `POST /cv-events` → 201 and an unresolved Room 204 safety event appears |
| 8. Demo reset restores the start state | Capacity returns to its original value and the admin session still authenticates afterwards |

### One finding, and why it is not a bug

Step 1 initially failed my assertion `results_created >= 1`, returning `0`. Root cause: `confirm_document` (`backend/app/main.py:414`) skips a lab row when an identical `patient_id` + `metric` + `value` + `result_date` already exists, and the bundled `hasan_lab_report.pdf` repeats values already present in the seed. The deduplication is correct and worth keeping, so the assertion was corrected to check `record_id`, the `CONFIRMED` transition, and the 409 on double-confirm. No production code changed.

---

## 4. Manual verification still required

These need a browser or a physical device and were not covered by automation:

- **Web** — `/login` renders, all three FIN codes sign in, and each lands on its own panel (`/patient/health`, `/doctor/patients`, `/admin/command-center`).
- **Web route guard** — opening `/admin/tasks` with no session redirects to `/login`; opening it as a doctor shows the Azerbaijani 403 card rather than a stack trace.
- **Web logout** — clears `localStorage` and returns to `/login`; the back button does not restore the panel.
- **Mobile** — FIN `1AZ0001` opens the patient tabs; `2AZ0002`/`3AZ0003` authenticate but report that the role lives in the web panel.
- **Mobile persistence** — the session survives an app reload via SecureStore, and Profile → logout returns to the FIN screen.
- **Document upload from the browser**, which exercises the new `uploadFile` and `fetchBlob` helpers rather than the previous inline `fetch` calls.

---

## 5. Risks

- **Login rate limit is global.** `enforce_rate("login", 30, 60)` shares one bucket across all callers rather than keying per client, so 30 attempts in a minute throttle everyone. Acceptable for a three-account demo, wrong for production.
- **Session is unsigned `localStorage` / SecureStore JSON.** Anyone can hand-edit it to another demo email, exactly as the previous dropdown allowed. This is a demo-mode property of the `X-Demo-User` contract, not a new weakness, but it must not ship as real authentication.
- **The web session is client-only.** A hard refresh briefly renders "Sessiya yoxlanılır…" before the guard resolves, because `localStorage` is unavailable during server rendering.
