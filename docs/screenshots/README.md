# Product Screenshot Guide

No screenshots are committed yet. Capture real application state rather than mockups, and do not add broken image references to the root README.

## Required captures

| File name | Interface | State to show |
|---|---|---|
| `patient-home.png` | Expo Patient | Hasan's home overview with synthetic-data context |
| `patient-lab-trend.png` | Expo Patient | HbA1c longitudinal trend and cautious insight |
| `patient-booking.png` | Expo Patient | Dr. Leyla with `60 / 48 / 12 AZN` calculation |
| `doctor-patient-brief.png` | Doctor web | Consent-aware Hasan brief |
| `doctor-consultation.png` | Doctor web | AI draft and missing-information review |
| `admin-command-center.png` | Admin web | `195 / 200` capacity and operational status |
| `admin-safety.png` | Admin web | Room 204 `HIGH FALL RISK` event |

## Capture rules

- Reset the demo before capturing.
- Use only synthetic demo identities and records.
- Hide browser bookmarks, personal accounts, terminal secrets, notifications, and unrelated tabs.
- Use consistent dimensions: `1440x900` for web and a consistent portrait phone frame for mobile.
- Prefer PNG and optimize images before committing.
- Verify that no real patient data or credentials are visible.
- Add descriptive alt text when the images are added to the root README.

Suggested README layout after capture:

```markdown
| Patient | Doctor | Hospital Admin |
|---|---|---|
| ![Patient health trend](docs/screenshots/patient-lab-trend.png) | ![Consent-aware Doctor brief](docs/screenshots/doctor-patient-brief.png) | ![Hospital command center](docs/screenshots/admin-command-center.png) |
```

The automated browser surface was unavailable during Phase 14, so no fabricated screenshots were added.
