# UAT Test Management Intelligence Platform — Architecture

## 1. Purpose

This document records the system architecture, the design review performed against
the product specification, the architectural decisions made, and the trade-offs
accepted. It is the authoritative reference for how the system is put together and
why.

## 2. Design Review (contradictions / ambiguities resolved)

The following points from the specification were reviewed and resolved:

| # | Topic | Issue | Resolution |
|---|-------|-------|------------|
| 1 | Service topology | Spec lists 6 Python services, each with its own container. On a Raspberry Pi this multiplies RAM/CPU overhead and forces duplicated shared code (models, config, DB sessions) across containers. | **Modular monolith backend**: one FastAPI container (`api`) containing clearly separated packages (`azure`, `intelligence`, `notifications`, `jobs`, `reporting`). Each package mirrors a logical service. The monorepo layout is preserved so packages can be extracted into separate containers later without redesign. See §6. |
| 2 | Port 5000 | Spec assigns `5000` to the API test framework *and* the API under test. | `5000` = weather mock API under test (Swagger). `5001` = API framework report/runner service. |
| 3 | `test_execution_history` | Spec lists it as a table, but the natural execution history is the set of `test_results`. A separate event table would duplicate data. | `test_results` **is** the event history. `test_execution_history` is provided as an aggregated materialized view for fast historical queries and flakiness metrics. |
| 4 | Comments/tags | Azure work items include comments; storing every comment is noisy. | Comments are stored (normalized) because the AI test-matrix analysis consumes them; they are not surfaced in the UI beyond work-item detail. |
| 5 | LLM "OpenCode-compatible provider" | Listed as a provider alongside OpenAI/Anthropic/local. | Implemented as one OpenAI-compatible chat provider (`OpenAICompatibleProvider`) configured via `LLM_BASE_URL`, which covers OpenAI, OpenCode, Ollama, LM Studio etc. |
| 6 | Notifications service | Spec lists a separate `notification-service` container. | Folded into the modular monolith as `app.notifications` behind a `NotificationProvider` protocol; can be extracted later. |
| 7 | PDF generation | HTML→PDF must be handled. | `WeasyPrint` default engine (pure Python, Pi-friendly, deterministic). Engine is pluggable (`PDF_ENGINE`), so Playwright/chromium rendering can be swapped in. |
| 8 | Coverage meaning | "Coverage" must not be code coverage only. | Requirement, story, automation and execution coverage are defined deterministically in §`coverage`. |
| 9 | AI dependence | Spec demands core workflows work without an LLM. | Every AI consumer falls back to a deterministic heuristic provider (`HeuristicLLMProvider`) when no LLM is configured. Enforced at the service layer, not the client. |
| 10 | Demo data | `/demo/run` must not be available in production. | Demo/simulation endpoints are gated behind `APP_ENV=demo|development`. |
| 11 | Azure "authoritative source" | The dashboard must keep working while offline. | Azure data is normalized into PostgreSQL; the dashboard reads the database only. Azure is the source of truth during sync; the DB is the runtime source of truth. |

## 3. Goals and Non-Goals

### Goals
- Automate test-management and reporting workflows for a UAT Lead.
- Deterministic, idempotent data pipelines (sync, metrics, reporting).
- Human-in-the-loop for everything AI-generated (tests, PRs, merges).
- Professional enterprise dashboard and PDF reporting.
- Runs on a Raspberry Pi with Docker; portable to larger Linux/cloud/K8s.
- Works without an LLM; LLM is an enhancement layer.

### Non-Goals (v1)
- No auto-merge of generated PRs.
- No S3/Azure Blob storage (interface designed, only `LocalStorage` shipped).
- No Jira/GitHub/GitLab adapters (interfaces designed, Azure only shipped).
- No OAuth/SSO (basic auth model designed; network security via Tailscale initially).

## 4. Logical Architecture

```text
Azure DevOps
   | REST API / PAT (configurable auth interface)
   v
+---------------------------------+
| app.azure  (Azure Adapter)      |
+---------------------------------+
   |                               |  triggers
   v                               v
+----------------+      +---------------------------+      +-----------------+
| PostgreSQL     |<-----| app.api (FastAPI)         |----->| LLM Provider    |
| (SQLAlchemy)   |      | routes/services/repos     |      | (pluggable)     |
+----------------+      +---------------------------+      +-----------------+
   |                      |             |
   |                      |  POST /test-runs/execute (triggers runners)
   |                      v             v
   |            +----------------+  +-------------------+
   |            | API Test       |  | Web Test          |
   |            | Framework      |  | Framework         |
   |            | (pytest 5000/  |  | (Playwright 6000/ |
   |            |  5001)         |  |  6001)            |
   |            +----------------+  +-------------------+
   |                      |             |
   |                      +----+--------+
   |                           v
   |                 Canonical Test Result
   |                 (normalized, validated)
   |                           |
   |                           v
   |                 app.intelligence
   |                 (test matrix, coverage, defects,
   |                  sprint metrics, flakiness, risks)
   |                           |
   +---------------------------+
   v
+---------------------------+      +-------------------------+
| UAT Dashboard (7001)      |      | Reports (HTML + PDF,    |
| React + Vite + Tailwind   |      | archived snapshots)     |
| + Recharts                |      +-------------------------+
+---------------------------+      +-------------------------+
                                        |  event-driven
                                        v
                                   app.notifications
                                   (Telegram/Email/Webhook/WhatsApp)
```

## 5. Key Architectural Principles

1. **Modular monolith with clean seams.** Every logical service is a package with
   a defined boundary. Extraction to separate containers requires only wiring.
2. **Interface-first integration.** `LLMProvider`, `NotificationProvider`,
   `ArtifactStorage`, `AzureClient`, `PDFEngine`, `TestResultParser` are protocols.
   The core never depends on a concrete vendor.
3. **Deterministic core.** All metrics are pure functions of persisted data.
   No AI in the metric path.
4. **Canonical internal formats.** All framework output is normalized into one
   canonical test-result schema before it touches business logic.
5. **DB is the runtime source of truth.** The dashboard, reports and metrics read
   PostgreSQL, never Azure or framework output files directly.
6. **Async jobs for everything slow.** LLM analysis, test generation, report
   generation run as tracked `AgentJob`s, never as long synchronous requests.
7. **Human approval gates.** Generated tests → branch → PR, never auto-merged.

## 6. Deployment Topology (Raspberry Pi)

```text
+------------------------------------------------------------+
| Raspberry Pi (Docker Compose)                              |
|                                                            |
|  frontend  (nginx :7001 -> static SPA, /api proxy -> api)  |
|  api       (:7000 FastAPI, runs migrations, agents, jobs)  |
|  db        (postgres:16-alpine :5432, internal only)       |
|  weather   (mock API under test :5000)                     |
|  api-tests (pytest framework :5001 report viewer)          |
|  webapp    (demo web application :8000)                    |
|  web-tests (Playwright :6000 runner, :6001 report viewer)  |
|                                                            |
|  volumes: postgres_data, reports, screenshots, videos,     |
|           traces, generated_reports                        |
+------------------------------------------------------------+
```

Containers expose only HTTP ports that need to be reachable. PostgreSQL is bound
to the internal Docker network only. Tailscale provides private remote access at
the network layer; no Tailscale logic exists in the application.

## 7. Consistency Rules

- Azure entity IDs are unique per entity type (`azure_id` + type discriminator).
- Synchronization is idempotent via natural-key upserts (`azure_id`).
- Metrics names are stable strings (`coverage.requirement`, `defects.mttr`, ...).
- Canonical statuses are enum-constrained (`PASSED`, `FAILED`, `SKIPPED`,
  `BLOCKED`, `FLAKY`, `ERROR`).
- All timestamps UTC ISO-8601.
- All service boundaries communicate in JSON with request/job/execution IDs.

## 8. Migration Path

| Target | Change |
|--------|--------|
| Larger Linux server | Same compose file, more resources. |
| Cloud VM | Same compose, add reverse proxy/TLS. |
| Kubernetes | Split backend packages into deployments; replace volumes with PVCs. |
| Cloud object storage | Implement `S3Storage` behind `ArtifactStorage`. |
| Second SCM (GitHub/GitLab/Jira) | Implement a second `ScmClient` interface. |

The database schema, canonical formats and metric definitions do not change.
