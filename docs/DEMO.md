# DigiSolution Judge Demo

## Goal

Show one connected, backend-driven story across a physical phone, Doctor web, Hospital Admin web, AI fallback, and patient-safety CV in approximately 7 minutes.

All names and records are synthetic.

## Required setup

- Backend is healthy and `/health` reports `database=connected`.
- Patient Expo app points to the same backend as the web panel.
- Doctor/Admin web is open on the presentation laptop.
- CV simulator points to that backend.
- `DEMO_MODE=true`.
- Demo data has been reset immediately before judging.

Run pre-flight:

```powershell
$env:DEMO_BACKEND_URL="http://localhost:8000"
.\.venv-win\Scripts\python.exe backend\scripts\demo_check.py
```

## Known initial state

- Patient: Hasan Nurmammadov, Premium Health, Penicillin allergy, Metformin
- Doctor: Dr. Leyla Mammadova, Endocrinology, `60 AZN`
- Insurance: `80%` covered, `48 AZN` insurer payment, `12 AZN` patient payment
- Labs: two complete blood counts, `02.09.2025` vs `10.08.2026` — WBC `10.64 → 7.38`, PLT `341 → 234`, MCV `75.3 → 76.2`, Hemoglobin `14.3 → 13.9`
- Population reference: NHANES 2021–2023 CBC, `7,593` complete panels, public domain
- Booking: no active Hasan appointment, at least one available Dr. Leyla slot
- Queue after booking: position `4`, three patients ahead, approximately `45 minutes`
- Hospital: `195 / 200` occupied, five available
- Patient #104: open lab-review blocker and pending high-priority task
- Room 204: `STABLE`, no active safety event

## Reset

Use the web **Reset Demo** control or:

```powershell
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/demo/reset" `
  -Headers @{"X-Demo-User"="admin@demo.az"}
```

## Seven-minute script

### 0:00-0:45 — Product framing

Say:

> DigiSolution is a healthcare intelligence layer connecting patient history, clinician context, hospital operations, and patient safety. It supports human decisions and actions; it does not diagnose or replace hospital systems.

Show the three interfaces: Expo Patient, Doctor web, and Hospital Admin web.

### 0:45-2:15 — Patient health and document intelligence

On the phone:

1. Continue as Hasan.
2. Open **Health -> Documents -> Upload document**.
3. Use the bundled synthetic lab report or select its PDF.
4. Show extracted WBC, Hemoglobin, PLT, and the rest of the complete blood count.
5. Emphasize that extraction is `NEEDS_REVIEW` until Hasan confirms it.
6. Confirm the values and open the CBC comparison (`02.09.2025` → `10.08.2026`).
7. Show the conflicting allergy record and the cautious AI explanation.

Key message: untrusted document text becomes patient-reviewed structured data before entering the clinical timeline.

### 2:15-3:15 — Navigation, insurance, and booking

On the phone:

1. Open **Doctors** and choose Dr. Leyla.
2. Select an available slot.
3. Show `60 AZN`, `48 AZN covered`, and `12 AZN patient payment`.
4. Confirm the appointment.
5. Open the appointment and show queue position `4` and estimated wait `45 min`.

Key message: insurance and queue values come from backend state, not hardcoded UI state.

### 3:15-4:20 — Consent-aware Doctor workspace

On the phone:

1. Grant Dr. Leyla Lab Results, Medications, Diagnoses, and Doctor Notes for 24 hours.

On the laptop Doctor panel:

2. Open Hasan's appointment and patient brief.
3. Show only the consented clinical categories.
4. Load synthetic consultation notes.
5. Generate the AI draft and show missing-information warnings.
6. Approve the final clinician-reviewed note.

Key message: AI does not bypass consent and cannot finalize the clinical record.

### 4:20-5:30 — Hospital operations

In Hospital Admin:

1. Show the Command Center at `195 / 200` occupied.
2. Open Tasks and start Patient #104's lab-review task.
3. Complete the task and resolve the blocker.
4. Discharge the patient.
5. Complete bed cleaning.
6. Show the updated capacity: `194 occupied / 6 available`.

Key message: insight leads to an explicit task, validated state transition, and measurable capacity change.

### 5:30-6:30 — Patient Safety CV

Run from the presentation laptop:

```powershell
$env:PYTHONPATH="cv_service"
$env:CV_BACKEND_URL="http://localhost:8000"
.\.venv-win\Scripts\python.exe cv_service\run_demo.py --simulate
```

In Admin Safety:

1. Show Room 204 become `HIGH FALL RISK` through backend polling.
2. Send a nurse.
3. Acknowledge the event.
4. Resolve it and show Room 204 return to `STABLE`.
5. If YOLO Pose is installed, upload a corridor photo or short video and show the `YOLO ACTIVE` badge, occupancy level, and pose transitions. If it is not installed, show `YOLO INACTIVE` and the honest 503 rather than a fake crowd count.

Key message: the CV process sends only a safety event, not identity or video data. Occupancy uploads are discarded after inference.

### 6:30-7:00 — Reliability close

Show Demo Reset and explain:

- deterministic synthetic state
- live AI with deterministic fallback
- CV video with simulator fallback
- Expo phone plus deployed HTTPS API removes LAN dependency
- backend authorization and audit events remain authoritative

## Questions judges may ask

**Does the AI diagnose?**  
No. It explains supplied data and suggests review; its output is advisory and human-reviewed.

**Can a doctor see every record?**  
No. A doctor needs an appointment relationship and active category-specific consent.

**Does CV identify the patient?**  
No. It uses pose geometry and room context only.

**Is this production-ready?**  
No. It is a tested hackathon MVP. Production identity, private object storage, compliance work, and live infrastructure validation remain explicit next steps.

## Failure-safe demo plan

| Failure | Fallback |
|---|---|
| Live AI unavailable | Set `AI_PROVIDER=mock`; deterministic output preserves the flow |
| YOLO/model unavailable | Run `--simulate` |
| Public web unavailable | Use the local Docker web on the laptop |
| Phone cannot reach laptop LAN | Point Expo to the deployed HTTPS API |
| Mutated or stale demo data | Run Demo Reset, then pre-flight |
| Expo cache issue | Run `npx expo start --clear --lan` |

## After the demo

Reset once more so mentors and judges receive the known starting state.
