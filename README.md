# HealthTech Platform

> A connected HealthTech MVP that helps patients understand their health history, helps doctors prepare for consultations, and helps hospitals act on capacity bottlenecks.

Built for a 48-hour hackathon with synthetic Azerbaijani healthcare data. This product is a clinical support and care-navigation tool — it does **not** diagnose conditions or replace clinical judgment.

## The problem

Healthcare journeys are fragmented. Patients struggle to interpret records and access appropriate care, doctors need relevant clinical context quickly, and hospitals need to turn operational bottlenecks into clear actions.

## Our solution

HealthTech brings three connected experiences into one system:

- **Patient app** — health timeline, lab comparisons, care navigation, appointment booking, insurance estimates, and consent controls.
- **Doctor panel** — consent-aware patient history, AI-generated patient briefs, structured consultation notes, and missing-information alerts.
- **Hospital command center** — bed capacity visibility, discharge blockers, priority workflows, and operational notifications.

An optional patient-safety module demonstrates a fall-risk event from a prepared room video and notifies hospital staff.

## Demo story

```text
New HbA1c result
→ trend detected
→ endocrinology recommendation
→ insurance-aware appointment booking
→ time-limited record access
→ doctor receives AI patient brief
→ consultation adds a new timeline record

Capacity risk
→ discharge blocker identified
→ doctor review task prioritized
→ task completed
→ discharge confirmed
→ bed availability recalculated
```

## Core capabilities

### Patient

- Personal medical timeline for labs, visits, medication, diagnoses, and documents
- Lab trend comparison and record-conflict warnings
- Specialist navigation without autonomous diagnosis
- Doctor search, availability, booking, rescheduling, cancellation, and queue estimate
- Mock insurance coverage and AZN payment calculation
- Category-based and time-limited record permissions
- Post-discharge health check-ins and review alerts

### Doctor

- Appointment and patient overview
- Specialty-relevant AI patient brief
- Permission-filtered medical timeline
- Consultation note drafting with doctor approval
- Missing-information prompts

### Hospital admin

- Bed occupancy and department capacity dashboard
- Expected-discharge and capacity-risk forecast
- Discharge blocker tracking
- Prioritized operational tasks with expected impact
- In-app alerts and safety-event monitoring

## Safety and privacy principles

- AI never makes a final diagnosis.
- Doctors retain final clinical authority.
- Patient consent is enforced by the backend for record access.
- All demo data is fully synthetic.
- AI output is labelled, source-aware where possible, and requires review before clinical use.

## Planned architecture

```text
Next.js + React + TypeScript + Tailwind CSS
                  │
                  ▼
             FastAPI backend
      ┌───────────┼───────────┐
      ▼           ▼           ▼
Supabase Auth  PostgreSQL  AI provider adapter
                               └─ deterministic fallback
```

The MVP uses a modular monolith: one frontend, one FastAPI backend, and one PostgreSQL database. The AI and computer-vision integrations are isolated behind provider interfaces so they can be upgraded later.

## Tech stack

| Area | Technology |
|---|---|
| Frontend | Next.js, React, TypeScript, Tailwind CSS |
| Backend | Python, FastAPI, Pydantic |
| Database & authentication | PostgreSQL, Supabase |
| AI | External LLM provider with deterministic fallback responses |
| Computer vision | Python, YOLO / pose estimation, prepared-video first |
| Charts | Recharts |
| Icons | Lucide React |
| Deployment | Vercel, Railway or Render, Supabase |

## Repository structure

```text
healthtech-platform/
├─ frontend/                 # Next.js application
├─ backend/                  # FastAPI modular monolith
│  ├─ app/
│  │  ├─ api/                # REST route groups
│  │  ├─ core/               # Settings, security, RBAC
│  │  ├─ models/             # Database models
│  │  ├─ schemas/            # Pydantic schemas
│  │  ├─ services/           # Domain and business logic
│  │  └─ ai/                 # Provider abstraction + fallbacks
├─ cv/                       # Optional patient-safety demo module
├─ docs/                     # Architecture and demo materials
└─ README.md
```

## Local development

Detailed setup instructions will be added as the frontend and backend are initialized. The final demo will support a local run mode so it remains usable if cloud services are unavailable during judging.

## Roadmap

- [x] Product definition and MVP scope
- [x] System architecture and UI/UX design
- [ ] Patient experience
- [ ] Doctor experience
- [ ] Hospital command center
- [ ] AI provider and demo fallbacks
- [ ] Patient-safety video scenario
- [ ] Cloud deployment and local demo instructions

## License

This repository is currently intended for hackathon development. License selection is pending.
