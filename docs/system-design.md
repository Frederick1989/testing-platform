# System Design

## 1. Monorepo Layout

```text
uat-test-intelligence/
├── docs/                          # Architecture, design, DB, API, AI, deploy, security, strategy
├── services/
│   ├── test-manager-api/          # Modular monolith backend (the "api" container)
│   │   ├── app/
│   │   │   ├── main.py            # FastAPI app factory + router registration
│   │   │   ├── config.py          # pydantic-settings, all env vars
│   │   │   ├── db.py              # engine, session factory, Base
│   │   │   ├── models.py          # SQLAlchemy models (single module, small files split below)
│   │   │   ├── models/            # models split by domain
│   │   │   ├── schemas.py         # Pydantic schemas
│   │   │   ├── api/               # routers by group (azure, test-manager, ...)
│   │   │   ├── services/          # business logic (never in routers)
│   │   │   ├── repositories/      # data access
│   │   │   ├── adapters/          # azure, llm, notifications, storage, pdf, parsers
│   │   │   ├── jobs/              # job manager, agent scheduler, workers
│   │   │   └── core/              # logging, ids, errors, auth
│   │   └── tests/
│   ├── azure-devops-adapter/      # kept as package boundary doc; deployed inside api as app.adapters.azure
│   ├── test-intelligence/         # package boundary doc; deployed inside api as app.services.intelligence
│   ├── notification-service/      # package boundary doc; deployed inside api as app.adapters.notifications
│   ├── api-test-framework/        # pytest + weather mock + runner + canonical result emitter
│   ├── web-test-framework/        # Playwright + demo webapp + runner + canonical result emitter
├── frontend/                      # React + Vite + TS + Tailwind + Recharts
├── database/
│   ├── migrations/                # Alembic
│   ├── seed/                      # deterministic demo seed
│   └── schemas/                   # ERD + SQL dumps
├── reports/{templates,generated}  # report templates and archived output
├── scripts/                       # backup, seed, dev helpers
├── docker/                        # Dockerfiles, nginx config
├── docker-compose.yml
├── .env.example
├── Makefile
└── README.md
```

**Rationale.** The six logical Python services from the spec are collapsed into a
single deployable container to stay resource-friendly on a Raspberry Pi while the
monorepo directories `azure-devops-adapter/`, `test-intelligence/` and
`notification-service/` remain as **package boundary documents** describing the
contract each package owns. Extracting them later is a packaging exercise, not a
redesign. See `docs/architecture.md` §6.

## 2. Backend layering

```text
Router (api/)        HTTP validation, auth, request-id, serialization only
   |
Service (services/)  Business logic, workflows, metrics — no HTTP, no SQL
   |
Repository (repositories/)  SQLAlchemy queries
   |
Models (models/)     ORM entities
```

Rules:
- Routers never contain business logic or raw SQL.
- Services never talk HTTP; they call repositories and adapters.
- Adapters implement protocols defined in the service layer (`azure.py`, `llm.py`,
  `notifications.py`, `storage.py`).

## 3. Configuration

`pydantic-settings`, loaded once at startup. All values overridable by env. See
`.env.example`. No secrets in code or docs.

Key groups: `APP_*`, `DATABASE_*`, `AZURE_DEVOPS_*`, `LLM_*`, `NOTIFICATIONS_*`,
`TELEGRAM_*`, `EMAIL_*`, `WHATSAPP_*`, `REPORT_*`, `SCHEDULE_*`, `STORAGE_*`.

## 4. Logging and Observability

- JSON structured logging to stdout via a `LogFilter` that injects `request_id`
  from middleware into every record.
- Middleware: request ID, request logging (method, path, status, duration),
  global exception handler that returns RFC-7807-style problem details and logs
  the error with the request/job ID.
- Every long-running operation carries `job_id` / `run_id` / `execution_id`.
- `/health` returns liveness + readiness (DB ping) and per-service status.

## 5. Job and Agent Runtime

- **JobManager**: in-process `asyncio` worker with a `QUEUED→RUNNING→COMPLETED/
  FAILED/CANCELLED` state machine persisted in `agent_jobs`. Jobs are processed
  in FIFO order with per-type concurrency limits and retries.
- **Scheduler**: APScheduler (`AsyncIOScheduler`) with deterministic cron/interval
  schedules defined by `SCHEDULE_*` env vars. Each schedule invokes an agent
  function which enqueues a job.
- Agents are plain async functions registered in an `AGENT_REGISTRY`.

## 6. Test Result Ingestion Pipeline

```text
raw framework output (pytest JUnit/JSON, Playwright JSON)
   -> parser adapter  (app.adapters.parsers)
   -> CanonicalTestResult (pydantic, validated)
   -> ingestion service: create/update test_runs + test_results,
      compute flakiness deltas, link to test cases/scenarios by key,
      emit domain events (failure, flaky, regression)
   -> notifications (deduplicated)
```

## 7. Events

An in-process event bus (`app.core.events`) publishes domain events. Notification
handlers subscribe. Event types: `test_run_completed`, `test_failed`,
`flaky_detected`, `defect_opened`, `defect_critical`, `story_blocked`,
`story_uat_ready`, `coverage_gap`, `pr_created`, `nightly_regression`.

## 8. Frontend Architecture

- React 18 + Vite + TypeScript + Tailwind CSS + Recharts.
- `react-router` with the page set from the spec.
- `src/api/client.ts` — typed fetch client; base URL from `VITE_API_BASE_URL`,
  default `/api` (proxied by nginx to `api:7000`).
- Layout: sidebar navigation, top bar, KPI cards, tables and charts from a small
  shared component library (`src/components/ui/`).
- All business metrics come from backend endpoints; the frontend never computes
  metrics.

## 9. Report Pipeline

```text
snapshot metrics for period (deterministic, from DB)
   -> render HTML from Jinja2 template (branding from REPORT_* env)
   -> HTML -> PDF (WeasyPrint engine)
   -> archive to reports/generated/<year>/<sprint-id>/  + row in report_archives
   -> frontend serves archive via /api/reports/archive/{id}
```

Reports are snapshots: archived HTML+PDF and a JSON snapshot of the period's data.
They are never regenerated from current data.

## 10. Security Architecture

See `docs/security.md`. Summary: secrets only via env; PAT never logged;
`Bearer` auth on API with configurable shared secret; demo endpoints gated by
`APP_ENV`; secret/dependency/container scanning in CI; network security via
Tailscale; sanitized HTML output.
