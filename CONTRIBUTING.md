# Contributing to DigiSolution

DigiSolution is a hackathon MVP. Keep changes focused, reproducible, and safe for a public repository containing synthetic data only.

## Before changing code

1. Read the root `README.md` and `docs/ARCHITECTURE.md`.
2. Do not commit real patient information, credentials, local databases, uploads, model weights, or generated build output.
3. Preserve the current interface boundaries: Expo for Patient, Next.js for Doctor/Admin, FastAPI for domain state, and the separate Python CV process.
4. Avoid adding infrastructure or product scope that is not needed for the issue being solved.

## Local workflow

Create a branch from `main`, make a small coherent change, and run the checks relevant to that change.

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
```

When changing migrations or demo behavior, also run:

```powershell
$env:PYTHONPATH="backend"
.\.venv-win\Scripts\python.exe -m app.migrate
.\.venv-win\Scripts\python.exe -m app.seed
.\.venv-win\Scripts\python.exe backend\scripts\demo_check.py
```

## Pull requests

- Explain the user or operational problem.
- Describe the implementation and trust-boundary impact.
- List the checks that passed.
- Include screenshots for visible UI changes.
- Identify any migration, environment, deployment, privacy, or fallback impact.
- Keep secrets and real medical data out of descriptions and screenshots.

## Documentation

Documentation must describe what the repository actually implements. Do not claim public deployment, physical-device validation, Supabase Auth/Storage, live AI, or production readiness until those states are verified.
