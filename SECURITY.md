# Security Policy

## Hackathon scope

HealthTech is a public hackathon MVP using synthetic data. It is not approved for real patient information, clinical deployment, or medical-device use.

## Report a vulnerability

Do not open a public issue containing exploit details, credentials, private URLs, or personal data. Contact the repository owner privately through their GitHub profile and include only the minimum information required to reproduce the issue safely.

## Secrets

Never commit:

- database passwords or connection strings with credentials
- Supabase service-role keys
- AI API keys
- JWT signing secrets
- CV service tokens
- `.env` files
- real patient documents or private uploads

If a secret is committed, revoke or rotate it immediately. Removing it from the latest commit is not enough because Git history may retain it.

## Current security controls

- Role, patient ownership, doctor relationship, consent category, and hospital scope checks
- Demo authentication and reset disabled when `DEMO_MODE=false`
- State-transition validation for appointments, tasks, discharge, beds, and safety events
- Upload size, extension, MIME type, signature, and duplicate validation
- Server-side-only integration secrets
- Sensitive-response cache controls and baseline security headers
- Audit events for sensitive domain actions
- Deterministic AI fallback with domain mutation kept outside AI

## Production requirements

Before processing real information, replace demo authentication, add private object storage, validate PostgreSQL and row-level access design, add secret management, monitoring, backups, recovery tests, dependency scanning, penetration testing, compliance review, and clinical governance.
