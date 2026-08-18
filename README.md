# HealthTech Platform

A demo-ready healthcare journey for patients, doctors, and hospital operations. The app uses fully synthetic Azerbaijani-style data and is decision support only: it does not diagnose conditions or replace clinical judgment.

## What works

- Patient health profile, database-backed timeline, repeated lab measurements, trends, record conflicts, and deterministic specialty navigation
- Doctor directory, availability, AZN insurance estimates, booking, rescheduling, cancellation, and queue calculation
- Category-based consent with expiry/revocation, privacy history, consent-filtered doctor brief, and doctor-approved consultation records
- Post-discharge check-ins with worsening-state alerts
- 200-bed hospital command center, discharge blockers, task start/completion, discharge, cleaning, and capacity recalculation
- Central AI provider abstraction with a deterministic no-key fallback
- Fall-risk event ingestion, cooldown deduplication, notifications, nurse tasks, acknowledgement, and resolution
- Polling-based live updates for dashboards, tasks, safety events, queue data, and notifications
- PDF/JPG/PNG upload, hash deduplication, PDF text extraction, lab classification/parsing, editable review, confirmation, timeline linking, and trend updates
- Demo reset endpoint and a real synthetic lab PDF at `backend/demo_documents/hasan_lab_report.pdf`

## Architecture

```text
Next.js 15 / React / TypeScript / Tailwind
                    |
                    v
FastAPI modular MVP (RBAC + domain APIs + deterministic engines)
          |                         |
          v                         v
Local SQLite database        Central AI adapter
for hackathon demo           live provider -> safe fallback

Separate Python CV module -> POST /cv-events
```

SQLite and header-based demo authentication are intentional local-MVP choices. Protected APIs require `X-Demo-User`; there is no implicit patient fallback. Demo authentication and reset fail closed when `DEMO_MODE=false`. The domain API boundaries can be moved to PostgreSQL/Supabase Auth after the hackathon without changing the frontend workflows.

## Run locally

Use official CPython 3.11+ (not an MSYS Python build) and Node.js 20+.

Backend, from the repository root in PowerShell:

```powershell
python -m venv .venv-win
.\.venv-win\Scripts\python.exe -m pip install -r backend\requirements.txt
$env:PYTHONPATH="backend"
.\.venv-win\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Frontend, in a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`. API documentation is at `http://localhost:8000/docs`.

## Run with Docker

Start the backend and frontend from the repository root:

```powershell
docker compose up --build -d
docker compose ps
```

Open `http://localhost:3000`. Backend health is available at `http://localhost:8000/health`.

If port 3000 is already in use, choose another host port before starting:

```powershell
$env:FRONTEND_PORT="3001"
$env:CORS_ORIGINS="http://localhost:3001"
docker compose up --build -d
```

Run the optional one-shot CV simulator after the stack is healthy:

```powershell
docker compose --profile cv run --rm cv-simulator
```

Stop the application without deleting its database or uploaded-document volumes:

```powershell
docker compose down
```

To intentionally remove demo volumes as well, use `docker compose down -v`.

Optional environment variables:

```powershell
$env:NEXT_PUBLIC_API_URL="http://localhost:8000"
$env:CORS_ORIGINS="http://localhost:3000"
$env:AI_PROVIDER="mock"  # use openai only with a server-side AI_API_KEY
$env:DEMO_MODE="true"
```

Copy [.env.example](.env.example) when configuring a deployment. Never place real secrets in frontend variables or commit them. A production CV sender must configure the same `CV_SERVICE_TOKEN` on the backend and CV process; demo-mode admin headers are accepted only while `DEMO_MODE=true`.

## Tests and build

```powershell
$env:PYTHONPATH="backend"
.\.venv-win\Scripts\python.exe -m pytest backend\tests -q

$env:PYTHONPATH="cv_service"
.\.venv-win\Scripts\python.exe -m pytest cv_service\tests -q

cd frontend
npm run build
```

## CV safety demo

Start the backend, then run from the repository root:

```powershell
$env:PYTHONPATH="cv_service"
.\.venv-win\Scripts\python.exe cv_service\run_demo.py --simulate
```

The simulator performs the stabilized `LYING -> SITTING -> STANDING` transition and sends the real fall-risk event to the backend. Video/camera modes remain extension points and fail safely when no pose model is installed.

Optional real YOLO Pose video mode:

```powershell
.\.venv-win\Scripts\python.exe -m pip install -r cv_service\requirements-vision.txt
$env:PYTHONPATH="cv_service"
.\.venv-win\Scripts\python.exe cv_service\run_demo.py --video path\to\prepared-demo.mp4
```

## Demo accounts

| Role | Demo identity |
|---|---|
| Patient | `patient@demo.az` |
| Doctor | `doctor@demo.az` |
| Hospital admin | `admin@demo.az` |

The frontend role switcher sets these demo identities. Direct API requests use the `X-Demo-User` header.

## Reset demo data

The reset endpoint is available only while `DEMO_MODE=true`:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/demo/reset -Headers @{"X-Demo-User"="admin@demo.az"}
```

It restores Hasan's health history, Dr. Leyla, appointments and slots, consent, notifications, 195/200 occupancy, Patient #104's blocker/task, and Room 204's stable safety state.

## Suggested 3–5 minute demo

1. Patient: open **My Health**, show HbA1c `5.4 -> 5.8 -> 6.3`, the conflict warning, AI-safe explanation, and Endocrinology navigation.
2. Patient: open **Appointments**, select Dr. Leyla, show the insurance estimate, and book an available slot. Open **Permissions** and grant 72-hour access.
3. Doctor: switch role, open **Consultations**, select Hasan, show the consent-filtered brief, enter a final note, and approve it. Return to the patient timeline to show the saved record.
4. Patient: open **Documents**, upload `backend/demo_documents/hasan_lab_report.pdf`, edit/remove/add extracted values, then confirm and show the updated timeline/trends.
5. Admin: open **Tasks**, start/complete Patient #104's task, discharge the patient, complete cleaning, and show available capacity increase. Open **Safety**, simulate Room 204 fall risk, send a nurse, acknowledge, and resolve.

## Safety and privacy

- Patient ownership and doctor consent are enforced in backend clinical endpoints.
- Doctor clinical access requires both an appointment relationship and active, category-matching consent.
- Hospital admins can access operational data but not full patient clinical histories.
- Hospital resources, alerts, CV events, tasks, and audit views are scoped to the admin's assigned hospital.
- Appointment, task, discharge, bed-cleaning, and safety-event state transitions are validated by the backend.
- Uploads are checked by extension, MIME type, size, and file signature; internal storage paths and hashes are not returned.
- AI never controls authentication, consent, insurance math, appointments, tasks, discharge, beds, or capacity.
- Extracted document data remains untrusted until a patient reviews and confirms it.
- No real patient data or client-side API secrets are included.
