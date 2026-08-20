# HealthTech Hackathon Submission Package

## One-line description

HealthTech is an AI-assisted healthcare intelligence layer connecting longitudinal patient care, consent-aware clinician workflows, hospital operations, and computer-vision patient safety.

## Short description

HealthTech unifies three role-specific experiences around one authoritative backend. Patients can turn medical documents into reviewed longitudinal records, understand trends, find specialists, calculate insurance, book appointments, and control access. Doctors receive appointment-linked, consent-filtered context and reviewable AI support. Hospital teams coordinate bed capacity, discharge blockers, operational tasks, and room-level fall-risk alerts. Live AI and YOLO Pose are optional; deterministic fallbacks keep the hackathon demo reliable.

## Why it matters

The project demonstrates how fragmented care and hospital events can become an auditable loop:

```text
Insight -> Decision support -> Human action -> Updated state
```

It focuses on integration and action rather than claiming to replace clinical systems or human judgment.

## What is technically notable

- Native Expo Patient app plus separate Next.js Doctor/Admin interfaces
- Shared FastAPI domain backbone with role, relationship, consent, and hospital scoping
- Patient-reviewed medical-document extraction linked to longitudinal trends
- Backend-owned appointment, insurance, queue, discharge, and bed state
- Safety-constrained AI adapter with deterministic fallback
- Explainable YOLO Pose state machine with simulator fallback and backend event ingestion
- Versioned synthetic demo seed, one-click reset, and pre-flight readiness check
- Local SQLite plus hosted PostgreSQL/Supabase connection support
- Docker, Render, Vercel, and optional EAS configuration

## Demonstrated journey

Synthetic lab report -> reviewed CBC values -> 2025 vs 2026 comparison -> AI explanation -> hematology suggestion -> insurance estimate -> appointment -> consent -> Doctor brief -> consultation -> hospital task -> bed release -> Room 204 safety response.

## Safety and ethics

- Synthetic data only
- Decision support, not diagnosis or treatment
- No face recognition or patient identity inference
- Human approval for clinical notes and operational changes
- Category-specific consent and auditable access
- Secrets remain server-side

## Verified repository checks

- Backend test suite
- CV state-machine tests
- Next.js production build
- Expo TypeScript validation
- Expo dependency compatibility check
- Android Hermes bundle export
- Clean migration and deterministic seed
- Local Docker health, deep web routes, AI fallback, CV ingestion, and reset

Update this section with the latest command results immediately before submission.

## Links to complete before submission

| Item | Value |
|---|---|
| Repository | https://github.com/nhesen/healthtech-platform |
| Public Doctor/Admin URL | Add verified URL |
| Public API health URL | Add verified HTTPS `/health` URL |
| Demo video | Add final video URL |
| Slide deck | Add final deck URL |
| Expo build/QR instructions | Add if used |

## Team details to complete

- Hackathon/event:
- Track/category:
- Team name:
- Team members and roles:
- Contact:

These fields are intentionally blank because the repository does not contain verified team or event metadata.

## Final submission checklist

- [ ] Add event, track, team, and contact details.
- [ ] Add public web and API URLs only after they are verified.
- [ ] Confirm `/health` reports `status=ok` and `database=connected`.
- [ ] Run migrations, seed, reset, and pre-flight against the deployed database.
- [ ] Complete the main flow on a physical phone.
- [ ] Confirm Doctor and Admin deep links refresh successfully.
- [ ] Confirm the CV simulator reaches the public backend and updates Room 204.
- [ ] Confirm live AI if configured, then deliberately test fallback.
- [ ] Capture the product images listed in `docs/screenshots/README.md`.
- [ ] Record a short demo video using `docs/DEMO.md`.
- [ ] Review every screenshot and video frame for secrets or real personal data.
- [ ] Choose a license if the team intends to grant reuse rights.
- [ ] Commit and push the final passing state.

## Suggested repository topics

`healthtech`, `fastapi`, `expo`, `react-native`, `nextjs`, `typescript`, `computer-vision`, `yolo-pose`, `healthcare-ai`, `hackathon`

GitHub repository topics are currently unset and should be added manually before judging.
