# HealthTech Patient Mobile

Expo SDK 57, React Native, TypeScript, and Expo Router patient application. It consumes the existing FastAPI APIs and uses only Expo Go-compatible modules.

## Configure

Copy `.env.example` to `.env`, then replace the example address with the development computer's LAN IPv4 address:

```env
EXPO_PUBLIC_API_URL=http://192.168.x.x:8000
EXPO_PUBLIC_DEMO_MODE=true
```

`localhost` will not work from a physical phone. The phone and computer must be on the same network, FastAPI must listen on `0.0.0.0`, and the firewall must allow private-network access to ports 8000 and 8081.

## Run

```powershell
cd apps\patient-mobile
npm install
npx expo start --lan
```

Open Expo Go and scan the QR code. Choose **Continue as Patient**.

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
