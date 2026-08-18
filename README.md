# HealthTech Platform

A demo-ready healthcare journey for patients, doctors, and hospital operations. The app uses fully synthetic Azerbaijani-style data and is decision support only: it does not diagnose conditions or replace clinical judgment.

## What works

- Native Expo Patient app with secure demo login, five-tab navigation, safe areas, mobile charts, document/camera picking, and LAN-configurable API access
- Dedicated Next.js Doctor and Hospital Admin web panels; old patient web routes provide a clear mobile handoff
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
Expo SDK 57 / React Native / Expo Router (Patient)
Next.js 15 / React / Tailwind (Doctor + Hospital Admin)
                         |
                         v
FastAPI modular MVP (RBAC + domain APIs + deterministic engines)
          |                         |
          v                         v
Local SQLite database        Central AI adapter
for hackathon demo           live provider -> safe fallback

Separate Python CV module -> POST /cv-events
```

SQLite and header-based demo authentication are intentional current local-MVP choices. The Expo app reuses this authentication contract and stores its demo session with Expo SecureStore. Protected APIs require `X-Demo-User`; there is no implicit patient fallback. Demo authentication and reset fail closed when `DEMO_MODE=false`. Production PostgreSQL/Supabase Auth and storage remain a future infrastructure migration; the mobile app does not introduce a competing authentication system.

## Run locally

Use official CPython 3.11+ (not an MSYS Python build). Expo SDK 57 requires Node.js 22.13+; the Next.js web panels also work with that version.

Backend, from the repository root in PowerShell:

```powershell
python -m venv .venv-win
.\.venv-win\Scripts\python.exe -m pip install -r backend\requirements.txt
$env:PYTHONPATH="backend"
.\.venv-win\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Patient mobile app, in a second terminal:

```powershell
Copy-Item apps\patient-mobile\.env.example apps\patient-mobile\.env
# Edit the copied file and set EXPO_PUBLIC_API_URL to this computer's LAN IPv4 address.
cd apps\patient-mobile
npm install
npx expo start --lan
```

Scan the QR code with Expo Go. The phone and computer must be on the same network. Run `ipconfig`, use the active Wi-Fi/Ethernet IPv4 address (for example `192.168.x.x`), and set `EXPO_PUBLIC_API_URL=http://192.168.x.x:8000`. Do not use `localhost`, because on a physical phone that means the phone itself. Allow Python/Node and ports 8000/8081 through the private-network firewall if prompted.

Doctor and Hospital Admin web panels, in a third terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`. The web entry deliberately exposes Doctor/Admin roles only; legacy Patient web URLs show a mobile-app handoff. API documentation is at `http://localhost:8000/docs`.

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
$env:EXPO_PUBLIC_API_URL="http://192.168.x.x:8000"
$env:CORS_ORIGINS="http://localhost:3000,http://localhost:8081"
$env:AI_PROVIDER="mock"  # use openai only with a server-side AI_API_KEY
$env:DEMO_MODE="true"
$env:NEXT_PUBLIC_DEMO_MODE="true"
$env:EXPO_PUBLIC_DEMO_MODE="true"
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

cd ..\apps\patient-mobile
npm run typecheck
npx expo-doctor
npx expo export --platform android
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

The Expo app provides **Continue as Patient** and persists the demo patient session securely. The Next.js role switcher contains Doctor and Hospital Admin only. Direct demo API requests use the `X-Demo-User` header.

The role switcher, reset control, bundled-document shortcut, consultation notes, queue controls, and safety simulator are marked as demo tools. They are hidden by the frontend and rejected by the backend when demo mode is disabled.

## Seed and pre-flight

Create or restore the deterministic base dataset from the repository root:

```powershell
$env:PYTHONPATH="backend"
.\.venv-win\Scripts\python.exe -m app.seed
```

With the backend running, perform a read-only readiness check:

```powershell
.\.venv-win\Scripts\python.exe backend\scripts\demo_check.py
```

The check validates the database, demo identities, available slot, 200/195 bed state, Patient #104 blocker, Room 204, bundled PDF, deterministic AI fallback, and CV simulator contract.

## Reset demo data

The reset endpoint is available only while `DEMO_MODE=true`:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/demo/reset -Headers @{"X-Demo-User"="admin@demo.az"}
```

It restores Hasan's health history, Dr. Leyla, appointments and slots, consent, notifications, 195/200 occupancy, Patient #104's blocker/task, and Room 204's stable safety state.

The same action is available as **Reset Demo** in the top-level Demo Mode controls and requires confirmation. Reset is transactional, idempotent, and targets only deterministic synthetic demo records; unrelated records are preserved.

## Exact reset state

- Hasan M. has Premium Health, a Penicillin allergy, Metformin, coherent 2024–2026 history, and no active main appointment or consent.
- HbA1c is `5.4 → 5.8 → 6.3`; glucose is `89 → 96 → 108`; Vitamin D is `17 → 21 → 28`; hemoglobin is stable at `14.0 → 14.1 → 14.1`.
- The allergy conflict remains unresolved. Eight synthetic doctors exist. Dr. Leyla is an endocrinologist charging `60 AZN`; Premium Health covers `80%` (`48 AZN`), leaving `12 AZN`.
- Dr. Leyla has four available tomorrow-relative slots. Three synthetic patients are ahead, so Hasan starts at queue position `4` with an estimated `45` minute wait after booking.
- Caspian Medical Center has exactly `200` beds: `195` occupied and `5` available. Six discharges are expected, two are blocked, four are usable, twelve arrivals are expected, and the projected shortage is `3`.
- Patient #104 has a pending high-priority lab-review task; Patient #207 has a medium-priority pharmacy blocker. Room 204 is `STABLE`, with no active safety event.
- Notifications are limited to one initial patient, doctor, and admin notification. The uploadable lab PDF is available through **Upload Demo Lab**.

## Exact phone → Doctor web → Admin web demo flow

1. Reset Demo from the laptop web panel. On the phone, scan the Expo QR code and tap **Continue as Patient**.
2. On the phone, open **Health → Documents → Upload document → Use Demo Lab Report**. Review `6.3 / 108 / 28 / 14.1`, confirm it, then show the HbA1c chart, conflict, AI insight, and Endocrinology recommendation.
3. On the phone, open **Doctors**, select Dr. Leyla, choose a slot, show `60 AZN / 48 AZN covered / 12 AZN patient`, and confirm. Show queue position `4`, then grant Lab Results, Medications, Diagnoses, and Doctor Notes for `24 hours`.
4. Move to the laptop Doctor web panel. Open Hasan, show the consent-filtered brief, load demo consultation notes, generate the draft, display missing dosage/allergy-reaction warnings, and approve the consultation.
5. Switch the laptop to Hospital Admin. Resolve Patient #104's blocker, discharge, complete bed cleaning, and show `194 occupied / 6 available`. Open Patient Safety, simulate Room 204 fall risk, send a nurse, acknowledge, and resolve.

The backend integration suite executes this complete mutation/reset story twice to guard against stale slots, duplicate records, old consent, completed tasks, bed drift, notifications, and active CV events.

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
