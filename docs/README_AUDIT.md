# README Compliance Audit

Every feature promised in the root `README.md` and `apps/patient-mobile/README.md` was traced from the UI down to the backend endpoint that serves it. Where a promise was unmet, **the code was completed** rather than the README weakened. Line references point at the state *after* the fixes.

Legend: ✅ present and wired · ⚠️ partially wired (now fixed) · ❌ absent

---

## Patient (mobile)

| Feature | Before | After | UI | Backend |
|---|---|---|---|---|
| Longitudinal timeline and overview | ⚠️ | ✅ | `app/(tabs)/index.tsx:16`, `app/health/timeline.tsx:11` | `GET /patients/{id}/overview`, `GET /patients/{id}/timeline` |
| Lab trends and comparison | ⚠️ | ✅ | `app/health/labs.tsx:13`, `app/health/lab/[id].tsx:15` | `GET /patients/{id}/trends`, `/lab-results`, `/lab-comparison` |
| PDF / PNG / JPEG upload | ✅ | ✅ | `app/documents/upload.tsx:18-20` | `POST /documents/upload` |
| Review before confirmation | ⚠️ | ✅ | `app/documents/upload.tsx`, `app/documents/[id].tsx` | `PATCH /documents/{id}/review`, `POST /documents/{id}/confirm` |
| AI explanation and specialty suggestion | ⚠️ | ✅ | `app/(tabs)/health.tsx:17`, `app/health/lab/[id].tsx` | `GET /ai/lab-explanation/{id}`, `care_navigation` from `/trends` |
| Doctor search, availability, booking | ⚠️ | ✅ | `app/(tabs)/doctors.tsx`, `app/doctors/[id].tsx`, `app/appointments/booking.tsx` | `GET /doctors`, `/availability`, `POST /appointments`, `PATCH /appointments/{id}/reschedule` |
| Insurance calculation in AZN | ⚠️ | ✅ | `app/insurance/index.tsx:12`, `app/doctors/[id].tsx` | `GET /insurance/estimate`, **new** `GET /insurance/plan` |
| Time-limited consent and revocation | ⚠️ | ✅ | `app/permissions/index.tsx:16` | `POST /consents`, `GET /consents`, `POST /consents/{id}/revoke` |
| Queue position | ✅ | ✅ | `app/(tabs)/appointments.tsx:17`, `app/appointments/[id].tsx` | `GET /appointments/{id}/queue` |
| Post-discharge check-in | ✅ | ✅ | `app/post-discharge/index.tsx:14` | `GET`/`POST /post-discharge/{id}` |
| Notifications | ✅ | ✅ | `app/notifications/index.tsx:13` | `GET /notifications`, `PATCH .../read`, `read-all` |

### What was fixed

- **Consent revocation** was the clearest broken promise: `POST /consents/{consent_id}/revoke` existed but no screen called it, so a patient could grant access and never withdraw it. Each active consent card now has a **Revoke Access** button. The doctor name and specialty on that screen also came from a hardcoded `"Dr. Leyla Mammadova"` string and are now read from `GET /doctors/{doctorId}`.
- **Lab comparison** — `GET /patients/{id}/lab-comparison` was never called. The lab detail screen now requests the comparison across the metric's full history window and renders the backend's own `change`, `direction`, and `explanation` instead of recomputing them in the UI.
- **Specialty suggestion** — the backend already returned `care_navigation.suggested_specialty` with a `reason` on `/trends`, and the UI discarded it in favour of a generic "Find Specialist" button. It is now shown on the Health tab. The record-conflict card also displayed fixed prose while ignoring `conflicts[0].message`; it now shows the backend message.
- **Reschedule was actively wrong**, not just missing: the button opened the booking flow, which called `POST /appointments` and created a *second* appointment. It now carries a `rescheduleId` through the doctor profile into booking and calls `PATCH /appointments/{id}/reschedule`, so the existing appointment moves instead of duplicating.
- **Review before confirmation** worked only inside the upload session. Leaving the screen lost the in-memory extraction, and re-uploading hit the 409 duplicate-hash guard, so a pending document became impossible to confirm. `app/documents/[id].tsx` is now editable whenever the status is not `CONFIRMED`.
- **Insurance coverage matrix** was a hardcoded table (Cardiology 80%, MRI 50%, Dentistry 0%) presented as plan data, and the doctor profile hardcoded `"80% Endocrinology coverage"`. A new `GET /insurance/plan` endpoint returns the real `insurance_coverage` rows for the patient's plan, and both screens now render backend values.
- **Home screen** hardcoded `"Good evening, Hasan"` and a fixed `"Stable"` status. The name comes from `/overview` and the status is derived from the backend's conflicts and trend directions.

---

## Doctor (web)

| Feature | Before | After | UI | Backend |
|---|---|---|---|---|
| Daily patients, appointments, alerts | ✅ | ✅ | `app/page.tsx`, `app/[role]/[section]/page.tsx` | `GET /appointments`, `GET /notifications` |
| Appointment + consent gated access | ✅ | ✅ | `[section]/page.tsx` (`Consultations.open`) | `doctor_patient_access`, `GET /doctors/patients/{id}/brief` |
| Patient brief **and timeline** | ⚠️ | ✅ | `[section]/page.tsx` (`Consultations`) | `GET /patients/{id}/timeline` |
| Consultation workspace + reviewable AI draft | ✅ | ✅ | `[section]/page.tsx` (`Consultations`) | `POST /consultations` |
| Missing-information warnings | ✅ | ✅ | `[section]/page.tsx` (`draft.missing_information`) | `POST /consultations` |
| No timeline entry without clinician approval | ✅ | ✅ | `generate` vs `complete` | `POST /consultations` writes the record only when `complete:true` |

The only gap was the **timeline**: the README promises "patient brief + timeline", but the doctor workspace showed only the brief summary. It now loads `/patients/patient_hasan/timeline` alongside the brief, and clears it when consent is missing so a 403 never leaks records.

---

## Hospital Admin (web)

| Feature | Before | After | UI | Backend |
|---|---|---|---|---|
| Command center + 200-bed view | ✅ | ✅ | `[section]/page.tsx` (`admin/command-center`) | `GET /hospitals/{id}/capacity` |
| Department status | ❌ | ✅ | **new** `admin/departments` section and nav link | `GET /hospitals/{id}/departments` |
| Bed and patient-flow status | ✅ | ✅ | `admin/beds`, `admin/flow` | `GET .../beds`, `GET .../flow` |
| Discharge blockers + prioritized tasks | ✅ | ✅ | `admin/tasks` (`Tasks`) | `GET /tasks`, `PATCH /tasks/{id}`, `POST /tasks/{id}/complete` |
| Capacity forecast **+ recommendations** | ⚠️ | ✅ | **new** `Analytics` component | `GET .../forecast`, `GET .../recommendations` |
| Room 204 safety alert | ✅ | ✅ | `admin/safety` (`Safety`) | `GET /safety/events`, `POST /cv-events`, `POST /cv/analyze` |
| Nurse task / ack / resolve / **audit** | ⚠️ | ✅ | `Safety` now renders nurse tasks and the audit trail | `GET /audit`, `POST .../send-nurse`, `PATCH .../acknowledge`, `.../resolve` |

The **200-bed claim is real**: `backend/app/demo_seed.py:215-223` seeds beds 1–200, and the new department test asserts the per-department totals sum to exactly 200.

### What was fixed

- **Departments** — `GET /hospitals/{id}/departments` existed and returned per-department bed totals, but nothing reached it. Added an `admin/departments` route plus a nav link.
- **Recommendations** — `GET /hospitals/{id}/recommendations` was unreachable. The analytics section is now a dedicated component showing the forecast and the recommendations side by side, instead of dumping only the forecast through the generic card renderer.
- **Audit trail and nurse tasks** — acknowledge/send-nurse/resolve all wrote audit rows and created `safety_tasks`, but neither was ever displayed, so the README's "nurse task / ack / resolve / audit flow" ended at a button press. `GET /audit` is now rendered as a safety audit trail. Nurse tasks had **no read endpoint at all**, so `GET /safety/events` was extended with an additive `nurse_tasks` array per event (existing fields untouched, so old tests keep passing) and the safety page lists them.

---

## Platform-wide claims

| Claim | Status | Evidence |
|---|---|---|
| `DATABASE_URL`, `DEMO_MODE`, `CORS_ORIGINS` | ✅ | `backend/.env.example`; CORS at `main.py:261-268`, `demo_enabled()` at `main.py:47` |
| AI provider adapter + deterministic fallback | ✅ | `backend/app/ai.py:77-89` — live OpenAI when `AI_PROVIDER=openai`, otherwise `MockAIProvider` |
| `POST /demo/reset` transactional and demo-scoped | ✅ | Runs inside the `db()` commit/rollback contextmanager; `reset_demo_data` is scoped to demo IDs; uploads are removed only after commit |
| Security headers | ✅ | `main.py:269-276` — nosniff, DENY, no-referrer, and `no-store` on clinical paths |
| Upload validation (extension / MIME / size / signature) | ✅ | `POST /documents/upload` with `documents.ALLOWED`; covered by `test_security_phase10.py` |
| CV events and LYING/SITTING/STANDING transitions | ✅ | `POST /cv-events`; simulator at `cv_service/run_demo.py --simulate` |

---

## Remaining known gaps (documented, not fixed)

- `GET /notifications/unread-count` has no consumer — the mobile badge counts unread items from the list it already fetched. Functionally identical, one fewer request; not worth wiring.
- `GET /privacy-history` is consumed by the web permissions section but not by the mobile app. The mobile consent screen shows active grants only.
- `GET /discharge-blockers` has no dedicated UI; blockers surface through `/tasks`, which joins `blocker_type` and is what the admin actually acts on.
- The web patient sections (`patient/appointments`, `patient/insurance`, `patient/permissions`, `patient/documents`) are reachable by URL and now genuinely functional after the login change, but only `/patient/health` is linked from the dashboard, because the README positions the patient experience in the Expo app.
- `doctor/patients` renders through the generic `Cards` component rather than the richer dashboard view. Cosmetic, same data.
