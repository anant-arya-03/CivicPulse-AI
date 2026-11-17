# Running and deploying CivicPulse

This is a working simulated product. It does not deliver government complaints or receive real email. Keep EMAIL_PROVIDER=mock and ALLOW_REAL_SUBMISSIONS=false. Do not publish demo credentials or a development server on the public internet.

## Local presentation

Run scripts/setup.ps1 once and scripts/dev.ps1 from the repository root (bash equivalents are available). Use mock AI and geocoding, EMAIL_PROVIDER=mock, ENABLE_SIMULATION=true and APP_ENV=development. Use the seeded Demo City directory. The complaint page's Demo tools explains the presentation journey. Every outgoing message still needs approval; simulated replies remain labelled.

1. Report a photo, edit suggestions, confirm a Demo City address and choose a department.
2. Review the letter and approve the simulated submission.
3. Skip ahead, approve a reminder, simulate acknowledgement and inspect Notifications.
4. Simulate a repair claim, upload an after photo, dispute it, approve the not-fixed message, then simulate another repair and confirm with a different after photo.
5. Open Settings to demonstrate persistent preferences. Privacy choices affect newly generated letters; existing text must be reviewed or regenerated explicitly.

## Hosted application

Use a dedicated host with Python 3.11+, Node 20.9+ and PostgreSQL 17. No Docker is required. Install dependencies from the repository lockfiles/environment instructions. Use a dedicated least-privilege database role and a persistent private directory for uploaded photos. Back up both PostgreSQL and photo storage, and test restoring them together.

Before starting the updated application, run from backend:

```powershell
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m alembic check
```

Build frontend with npm.cmd run build, then run npm.cmd run start. Run the backend with .venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000. Put both behind an HTTPS reverse proxy; route /api/v1 directly to FastAPI and other paths to Next.js. Enforce a 12 MB upload body limit at the reverse proxy. Keep the database and backend ports private. Use a process supervisor with automatic restart and logs; run one backend process while rate limits remain in memory.

Required production settings: APP_ENV=production, COOKIE_SECURE=true, a randomly generated SECRET_KEY of at least 32 characters, ENABLE_SIMULATION=false, ALLOW_REAL_SUBMISSIONS=false. Configure DATABASE_URL, LOCAL_STORAGE_DIR and the public HTTPS origin in CORS_ORIGINS. Secrets belong only on the host. Use mock AI until the paid provider has been validated separately. Production refuses interactive simulation tools; a presentation with time travel belongs in a separate local or access-controlled development environment.

Schedule backend/.venv/Scripts/python.exe -m app.workers.run_pending every 15 minutes with the working directory set to backend (Task Scheduler on Windows or cron on Linux). The worker drafts only. Check scheduler exit codes, failed actions, API health, disk usage and backups. Do not pass --now outside a local demo.

## Release verification and rollback

Run backend pytest and Ruff, frontend Vitest/lint/typecheck/build, then stop any test-owned servers, remove only frontend/.next and run Playwright. Browser tests create e2e-*@civicpulse.example accounts in the development database; remove only those test accounts afterwards. Never use a production database for tests. Run a manual keyboard and screen-reader check of settings, notification expansion, error announcements and the complete approval journey before public release. Automated tests do not replace a screen-reader assessment.

The M7 migration adds users.notifications_last_seen_seq. It does not remove complaint data. Back up first. To roll back M7, stop the updated processes, run alembic downgrade 4b9540dbe92f, and deploy the previous code together. Never run the new code against the old schema.

## Before real service

A real email adapter and authenticated inbound delivery, verified official contacts, live AI evaluation, shared rate limiting for multiple processes, operational monitoring, a stricter page CSP and a manual accessibility assessment remain separate release work. This prototype must not claim real delivery or guaranteed resolution. No test suite can guarantee an error-free public service.
