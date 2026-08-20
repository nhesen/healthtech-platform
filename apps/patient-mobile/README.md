# DigiSolution Mobile

Expo SDK 54, React Native, TypeScript, and Expo Router application for all three demo roles — citizen, clinician, and hospital operations. It consumes the existing FastAPI APIs and uses only Expo Go-compatible modules.

SDK 54 is the newest Expo SDK available in the Apple App Store build of Expo Go, so reviewers can scan the QR code with the store version of Expo Go on a physical iPhone without sideloading or re-signing.

## Configure

Copy `.env.example` to `.env`. For the hackathon, use the public HTTPS backend; a LAN IPv4 address remains available for local development:

```env
EXPO_PUBLIC_API_URL=https://healthtech-api.onrender.com
EXPO_PUBLIC_DEMO_MODE=true
EXPO_PUBLIC_API_TIMEOUT_MS=20000
```

`localhost` will not work from a physical phone. When using a local LAN URL, the phone and computer must be on the same network, FastAPI must listen on `0.0.0.0`, and the firewall must allow private-network access to ports 8000 and 8081.

## Run

```powershell
cd apps\patient-mobile
npm install
npx expo start --lan
```

Open Expo Go and scan the QR code, then sign in on the portal screen with a demo FIN and the matching role:

| FIN | Role | Lands on |
| --- | --- | --- |
| `1AZ0001` | Vətəndaş | Citizen tabs — home, health, doctors, appointments, profile |
| `2AZ0002` | Həkim | Clinic list, alerts, profile, and the consultation workspace |
| `3AZ0003` | Xəstəxana | Command centre, tasks, safety, analytics, profile |

Each role section is gated: a stored session that does not match the section redirects to its own landing screen, and signing out returns to the portal.

### Role sections

- **Citizen** (`app/(tabs)`) — unchanged patient journey.
- **Clinician** (`app/doctor`, `app/consultation/[id]`) — clinic list with queue counts, demo queue advance, alerts with mark-as-read, and a consultation workspace holding the consent-scoped brief, timeline, AI assessment draft, and the status progression that completes the visit.
- **Hospital operations** (`app/admin`, `app/hospital`) — capacity command centre, discharge task queue with the complete → discharge → bed-cleaning chain, camera safety board with acknowledge/dispatch/resolve, capacity forecast with recommendations, plus departments, beds, patient flow, and the audit trail.

A clinician record only opens when an appointment relationship exists **and** the citizen has granted consent for that category; otherwise the workspace shows why it is closed. Book the appointment and grant consent from the citizen role first. Seeded availability slots are relative to seed time, so if every slot is in the past use **Reset demo data** on the hospital command centre.

## Verification

```powershell
npm run typecheck
npx expo-doctor
npx expo export --platform android
```

## Current limitations

- Demo authentication uses the existing backend demo identity; production Supabase Auth is not yet present in this repository.
- In-app notifications are implemented. Native push notifications are intentionally out of scope.
- Images are uploaded for backend/manual review; OCR is not performed on the phone.
- Physical-device scanning must be performed on the presentation network. Automated checks verified LAN serving and backend reachability, but cannot physically operate Expo Go on a phone.
- `npm audit` currently reports transitive advisories in Expo/Metro build tooling (`image-size` and `uuid`). The suggested forced fix downgrades Expo and is not safe; use a patched Expo SDK release when available.
