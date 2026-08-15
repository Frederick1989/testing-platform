# UAT Test Intelligence Platform

An end-to-end test management intelligence platform designed for a Raspberry Pi
(and portable to any Linux host or the cloud): it ingests test results from real
test frameworks, synchronises work items from Azure DevOps, tracks UAT coverage,
identifies flaky tests and regression risks, generates snapshotted HTML/PDF
reports, and notifies on meaningful events.

![Architecture summary](docs/architecture.md)

## Repository layout

```text
docs/          # architecture, design, API spec, security, deployment, strategy
services/
  test-manager-api/    # FastAPI monolith: 6 logical services, scheduler, job worker
  weather-mock/        # API under test (:5000) with seeded defects
  api-test-framework/  # pytest runner + report viewer (:5001)
  demo-webapp/         # web app under test (:8000) with seeded UI defects
  web-test-framework/  # Playwright runner (:6000) + report viewer (:6001)
frontend/              # React + Vite + TS dashboard (:7001)
docker/                # per-service Dockerfiles + nginx config
scripts/               # backup / restore
database/              # schema & migration scripts
```

## Quick start (Docker)

```bash
cp .env.example .env
docker compose up -d --build
```

| Service | URL |
|---|---|
| Dashboard | http://localhost:7001 |
| Test Manager API (swagger) | http://localhost:7000/docs |
| Weather mock API | http://localhost:5000/docs |
| API tests (pytest) viewer | http://localhost:5001 |
| Playwright report viewer | http://localhost:6001 |
| Demo web app | http://localhost:8000 |

Seed the demo dataset (stories, acceptance criteria, defects, test runs, agents):

```bash
make seed
```

> API auth: every `/api/v1` endpoint (except `/health`) requires
> `Authorization: Bearer <API_TOKEN>` (default `dev-token`).

## Quick start (no Docker)

PostgreSQL required. Create the database, then:

```bash
cd services/test-manager-api
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/alembic upgrade head
DATABASE_URL=postgresql://uat:uat@127.0.0.1:5432/uat_test_intelligence \
  .venv/bin/uvicorn app.main:app --port 7000

cd frontend && npm install && npm run dev   # dashboard on :7001
```

Run the demo weather stack manually:

```bash
cd services/weather-mock        && .venv/bin/uvicorn app.main:app --port 5000
cd services/api-test-framework  && API_TESTS_WEATHER_URL=http://127.0.0.1:5000 \
     .venv/bin/uvicorn app.main:app --port 5001
cd services/demo-webapp         && WEATHER_URL=http://127.0.0.1:5000 node server.js
cd services/web-test-framework  && PLAYWRIGHT_BROWSERS_PATH=$PWD/.browsers \
     WEBAPP_URL=http://127.0.0.1:8000 node server.js
```

## Triggering test runs

The API test framework runs a real pytest suite (16 passing, 3 failing on the
seeded defects):

```bash
curl -X POST http://127.0.0.1:5001/execute -H 'Content-Type: application/json' \
  -d '{"environment":"qa","branch":"develop","commit_sha":"abc123"}'
```

The Playwright framework runs 5 UI tests (3 passing, 2 failing on seeded UI defects):

```bash
curl -X POST http://127.0.0.1:6000/execute -H 'Content-Type: application/json' \
  -d '{"environment":"qa","branch":"develop","commit_sha":"abc123"}'
```

Ingest the results into the platform:

```bash
curl -X POST http://127.0.0.1:7000/api/v1/test-runs/ingest \
  -H "Authorization: Bearer dev-token" -H 'Content-Type: application/json' \
  -d '{"framework":"pytest","url":"http://api-tests:5001/runs/<run_id>","environment":"qa"}'
```

## Reports & notifications

```bash
curl -X POST http://127.0.0.1:7000/api/v1/reports/generate \
  -H "Authorization: Bearer dev-token"
```

Reports are snapshotted into the archive and served from
`/api/v1/reports/archive/{id}/html` and `/pdf` (see the Dashboard → Reports page).
Email/Webhook notifications are configured via env (`EMAIL_*`, `NOTIFICATIONS_ENABLED`).

## Operations

```bash
make up            # build + start
make logs          # tail logs
make backup        # pg_dump + artifact archive -> backups/
make restore FILE=backups/<stamp>.dump
make down          # stop (keeps volumes)
```

Backups are never committed (see `.gitignore`).

## Documentation

See `docs/` — in particular `docs/architecture.md`, `docs/security.md` and
`docs/deployment.md` for deployment, and `docs/test-strategy.md` for how the
platform tests itself.
