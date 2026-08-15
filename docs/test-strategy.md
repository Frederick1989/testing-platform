# Test Strategy

This document covers testing **of the platform itself**, and how the platform's
own frameworks/demo data are used to prove it end to end.

## 1. Testing pyramid

| Layer | Tool | Where | Scope |
|---|---|---|---|
| Unit | pytest | `services/test-manager-api/tests/unit` | metrics, parsing, providers, coverage math, dedup, matcher |
| Integration | pytest + real Postgres (testcontainers or compose db) | `tests/integration` | ORM + repositories + idempotent sync |
| API | FastAPI TestClient | `tests/api` | routers, auth, job flow, ingest, report endpoints |
| Contract | pytest against adapter client with recorded responses | `tests/contract` | Azure adapter mapping, PAT redaction |
| Frontend | vitest + @testing-library/react | `frontend/tests` | critical flows (matrix, coverage, reports) |
| E2E | Playwright | `frontend/tests/e2e` or `web-test-framework` | story→sync→matrix→run→results→dashboard→PDF |
| Demo E2E | `scripts/e2e_demo.sh` | CI | full happy path against compose stack |

## 2. Demo fixtures as tests

The weather demo (two stories, bugs, flaky test, sprint states, historical runs)
is deterministic and re-seedable (`/demo/seed`, `scripts/seed.sh`). It serves
both as a demo and as an end-to-end integration fixture. Assertions in CI verify
the seeded state produces expected metrics (e.g. specific coverage % and flakiness
rates), which makes regressions in the metric layer fail CI.

## 3. Key unit test targets

- `CoverageCalculator` (requirement/story/automation/execution) with edge cases:
  story with zero AC, all AC untested, blocked story.
- `UatReadinessScorer` (deterministic gates).
- `FlakinessDetector` (min runs threshold, pass/fail history).
- `DefectMetrics` (MTTR, aging, reopen rate).
- `ResultIngestor` (idempotency, dedup, event emission).
- `LLM output validation` (invalid schema → fallback, no partial writes).
- `Notification dedup/cooldown`.

## 4. Contract tests (Azure adapter)

Recorded fixtures of Azure DevOps REST responses (work items WIQL query,
iterations, PRs). The adapter maps to normalized models; tests assert field
mapping, null handling, tag parsing, and that PAT never leaks into exceptions.

## 5. CI stages

```text
lint (ruff + eslint + prettier)
  → unit tests
  → integration tests (postgres service)
  → security scan (gitleaks)
  → dependency scan (pip-audit, npm audit)
  → container build
  → container scan (trivy)
  → frontend build + vitest
  → e2e (compose stack + demo seed)
  → publish artifacts (reports, coverage, images)
```

No auto-deploy to production. Merges to main trigger the pipeline; releases are
tagged manually.

## 6. Local dev commands

```bash
make test        # backend unit+api tests
make test-front  # frontend unit tests
make lint        # ruff + eslint
make e2e         # compose up + seed + api e2e script
```

## 7. Definition of "covered"

- Story: has at least one linked test case per acceptance criterion.
- AC: has ≥1 linked test case.
- Automated: linked implementation exists.
- Executed: has ≥1 non-skipped result in the last N days.
- UAT ready: all AC covered, latest linked runs passed, no blocking defects,
  no critical open defects. Deterministic gates in `services/readiness.py`.
