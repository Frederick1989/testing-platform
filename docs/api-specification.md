# API Specification

Base URL: `http://<host>:7000`. All endpoints prefixed `/api/v1`. Interactive docs
at `/docs` (Swagger UI) and `/redoc`. Responses are JSON. Errors use a problem
payload: `{"error": {"code", "message", "request_id"}}`.

Auth: `Authorization: Bearer <API_TOKEN>` where `API_TOKEN` is configured via
env `API_TOKEN`. If unset, auth is disabled with a warning (small-team/Tailscale
mode). Demo endpoints additionally require `APP_ENV in {demo, development}`.

## Canonical statuses

`PASSED | FAILED | SKIPPED | BLOCKED | FLAKY | ERROR` (enum `TestStatus`).

## Endpoint groups

### health
| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/health` | Liveness + readiness (DB ping), version, uptime |

### azure
| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/azure/sync` | Full sync (work items, iterations, PRs) — async job |
| POST | `/api/v1/azure/sync/work-items` | Sync work items (idempotent upsert) |
| POST | `/api/v1/azure/sync/pull-requests` | Sync PRs |
| POST | `/api/v1/azure/sync/iterations` | Sync iterations |
| GET | `/api/v1/azure/work-items/{id}` | Work item detail |
| GET | `/api/v1/azure/work-items` | Filtered list (type, state, iteration, page) |
| GET | `/api/v1/azure/pull-requests` | PR list |

### test-manager
| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/test-manager/sync-test-matrix` | LLM/heuristic gap analysis for a story (async job) |
| POST | `/api/v1/test-manager/create-test-cases` | Generate tests → branch → run → PR (async job) |
| GET | `/api/v1/test-manager/analyses/{work_item_id}` | Latest test-matrix analysis |
| GET | `/api/v1/test-manager/stories/ready` | Stories ready for UAT sign-off |

### test-cases
| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/test-cases` | List with filters, links to stories/AC |
| POST | `/api/v1/test-cases` | Create test case (manual) |
| GET/PUT/DELETE | `/api/v1/test-cases/{key}` | Read/update/deactivate |
| POST | `/api/v1/test-cases/{key}/scenarios` | Add scenario |
| POST | `/api/v1/test-cases/{key}/implementations` | Link implementation |
| POST | `/api/v1/test-cases/link` | Link story/AC → test case |

### test-matrix
| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/test-matrix/{work_item_id}` | Full matrix: story → AC → test case → scenario → impl → latest/previous result → coverage → defects |
| GET | `/api/v1/test-matrix` | Matrix for a sprint / all stories |

### test-runs / test-results
| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/test-runs/execute` | Trigger a run in a framework (async job) |
| POST | `/api/v1/test-runs/ingest` | Ingest canonical results (used by runners) |
| GET | `/api/v1/test-runs` | List runs with filters |
| GET | `/api/v1/test-runs/{id}` | Run detail |
| GET | `/api/v1/test-runs/{id}/results` | Results of a run |
| GET | `/api/v1/test-results` | Filtered result history |
| GET | `/api/v1/test-results/{id}` | Result detail (artifacts, stack trace) |

### coverage
| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/coverage/summary` | Requirement, story, automation, execution coverage |
| GET | `/api/v1/coverage/acceptance-criteria` | AC-level coverage list |
| GET | `/api/v1/coverage/by-story` | Per-story coverage + gaps |
| GET | `/api/v1/coverage/gaps` | AC without tests, stories without execution |

### defects
| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/defects` | Filtered list |
| GET | `/api/v1/defects/summary` | Counts, aging, MTTR, reopen rate, blockers |
| GET | `/api/v1/defects/{id}` | Detail + linked tests/stories |

### reports
| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/reports/generate` | Generate HTML+PDF snapshot (async job) |
| GET | `/api/v1/reports/latest` | Latest archive entry |
| GET | `/api/v1/reports/archive` | List archived reports |
| GET | `/api/v1/reports/archive/{id}` | Archive detail |
| GET | `/api/v1/reports/archive/{id}/html` | Served HTML |
| GET | `/api/v1/reports/archive/{id}/pdf` | Served PDF |

### notifications
| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/notifications` | Recent notifications |
| POST | `/api/v1/notifications/test` | Send a test message (dev) |

### agents
| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/agents` | Registered agents + state |
| POST | `/api/v1/agents/{name}/run` | Trigger agent run now |
| PUT | `/api/v1/agents/{name}` | Enable/disable, reschedule |

### jobs
| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/jobs` | Enqueue a job (type + params) |
| GET | `/api/v1/jobs/{id}` | Job status/result |
| GET | `/api/v1/jobs` | Job list |
| POST | `/api/v1/jobs/{id}/cancel` | Cancel a queued job |

### demo (gated)
| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/demo/run` | Deterministic simulated runs `{failure_rate, flaky_rate}` |
| POST | `/api/v1/demo/seed` | Load full demo dataset |
| POST | `/api/v1/demo/reset` | Reset demo data (dev only) |

### intelligence (dashboard metric endpoints)
| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/dashboard/summary` | Everything the dashboard needs (KPIs, series, risks) |
| GET | `/api/v1/sprints` | Sprint list + delivery metrics |
| GET | `/api/v1/sprints/{id}` | Sprint detail |
| GET | `/api/v1/flaky-tests` | Flaky test list + stats |
| GET | `/api/v1/risks` | Risk list with severity |
| GET | `/api/v1/velocity` | Velocity series |

## Long-running endpoints

All slow operations (`/azure/sync*`, `/test-manager/*`, `/test-runs/execute`,
`/reports/generate`) return `202 {job_id, status}` immediately and progress on
`GET /jobs/{job_id}`. `GET /jobs/{job_id}` result is `{status, result, error,
started_at, completed_at, duration_ms}`.

## Example: sync-test-matrix

```http
POST /api/v1/test-manager/sync-test-matrix
{"work_item_id": 1234}

202 {"job_id": "job-...", "status": "QUEUED"}

GET /api/v1/jobs/job-...
{
  "status": "COMPLETED",
  "result": {
    "story_id": 1234,
    "coverage": 82,
    "missing_acceptance_criteria": 1,
    "existing_tests_reused": 4,
    "new_tests_required": 3,
    "potentially_redundant_tests": 1,
    "status": "REVIEW_REQUIRED"
  }
}
```

## Canonical test result (ingest body)

```json
{
  "test_run_id": "run-123",
  "framework": "playwright",
  "suite": "authentication",
  "environment": "qa",
  "branch": "develop",
  "commit_sha": "abc123",
  "started_at": "...", "completed_at": "...",
  "results": [
    {
      "test_case_id": "TC-001",
      "scenario_id": "SC-001",
      "title": "Login with valid credentials",
      "status": "PASSED",
      "duration_ms": 1240,
      "error": null,
      "stack_trace": null,
      "artifacts": ["/reports/screenshots/login.png"]
    }
  ]
}
```

Runners submit this to `/test-runs/ingest`. The service validates, normalizes,
persists, computes deltas and emits events.
