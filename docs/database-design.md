# Database Design

PostgreSQL 16. ORM: SQLAlchemy 2.x. Migrations: Alembic. All timestamps are
UTC `timestamptz`. Natural keys are `azure_id` (unique per entity type). All
relationships use surrogate `BIGINT` primary keys with `BIGINT` foreign keys.

## ERD (text)

```text
iterations ──< work_items >── acceptance_criteria
    │                          │
    └──────────────────────────┼───────────┐
                               │           │
                          test_story_links ┴─── test_cases >── test_scenarios
                               │               │                    │
                               │               └── test_implementations
                               │                                   │
                               └── test_defect_links ──< defects ──┘
                                                    (also links test_results)

test_runs ──< test_results >── test_implementations
                │
                └── test_defect_links

work_items ──< azure_comments
work_items ──< test_matrix_analyses
defects ──< defects (reopened events via status history)
test_cases ──< test_generation_candidates (persisted LLM output, validated)

agent_jobs, agents, notifications, report_archives,
test_execution_history (aggregated view over test_results)
```

## Tables

### azure (integration)

| Table | Purpose | Key columns |
|---|---|---|
| `iterations` | Sprint/iteration metadata | `azure_id` uq, name, path, state, start_date, finish_date |
| `work_items` | Stories/tasks/bugs/features/epics | `azure_id` uq, type, title, description, acceptance_criteria_raw, state, assigned_to, iteration_id FK, area_path, created/updated/closed_at, tags[], url, parent_azure_id, comment_count, last_synced_at |
| `azure_comments` | Work item comments (for AI analysis) | work_item_id FK, azure_comment_id uq, author, created_at, text |
| `pull_requests` | PR metadata | `azure_id` uq, title, repo, source_ref, target_ref, status, author, created/updated/closed_at, commit_count, url |
| `azure_sync_logs` | Sync audit trail | kind (work-items/pr/iterations), started/completed_at, upserted, status, error |

### test management

| Table | Purpose | Key columns |
|---|---|---|
| `test_cases` | Logical test scenario (framework-independent) | `key` uq (e.g. `TC-023`), title, description, priority, source (manual/auto), suggested_framework (api/ui/both), status |
| `test_scenarios` | Variation of a test case | test_case_id FK, name, steps JSON, status |
| `test_implementations` | Concrete automation | test_case_id FK, framework, path, name, status, content_hash |
| `acceptance_criteria` | Parsed AC of a story | work_item_id FK, text, sort_order, status (covered/not_covered) |
| `test_story_links` | Story↔AC↔TestCase | work_item_id, acceptance_criterion_id, test_case_id, coverage_status, rationale |

### execution

| Table | Purpose | Key columns |
|---|---|---|
| `test_runs` | One execution | `run_id` uq, framework, environment, branch, commit_sha, started/completed_at, duration_ms, total, passed, failed, skipped, flaky, error_count, report_location, status |
| `test_results` | One test within a run (the execution history) | `test_run_id` FK, implementation_id FK, test_case_id FK, scenario_id FK, suite, title, status, duration_ms, environment, branch, commit_sha, started/completed_at, error, stack_trace, artifacts JSON, retries, flaky |
| `test_execution_history` | **Materialized view** over test_results (per test_case aggregated) | test_case_id, last_status, first_failed_at, last_passed_commit, failure_count, pass_count, run_count, avg_duration_ms, p95_duration_ms, failure_rate, flaky |

### defects

| Table | Purpose | Key columns |
|---|---|---|
| `defects` | Bugs from Azure | `azure_id` uq, title, description, severity, state, created/resolved/closed_at, assigned_to, iteration_id FK, story work_item_id FK, url, reopened_count, is_escaped |
| `test_defect_links` | Failed test ↔ defect | test_result_id FK, test_case_id FK, defect_id FK, reason, linked_by |

### analysis / automation

| Table | Purpose | Key columns |
|---|---|---|
| `test_matrix_analyses` | Persisted LLM/heuristic analysis | work_item_id FK, coverage_pct, missing_ac_count, reused_count, new_tests_required, redundant_count, status, details JSON, model, generated_at |
| `test_generation_candidates` | Validated LLM test-case proposals awaiting approval | work_item_id FK, analysis_id FK, title, framework, content, status (proposed/approved/rejected/generated), generated_at |
| `agent_jobs` | Async jobs | type, status, trigger, params JSON, result JSON, started/completed_at, duration_ms, error, retry_count, max_retries |
| `agents` | Agent config/schedule state | name, schedule, enabled, last_run_at, last_status, run_count, last_error |

### reporting / notifications

| Table | Purpose | Key columns |
|---|---|---|
| `report_archives` | Report snapshots | sprint_name, period_start/end, generated_at, html_path, pdf_path, snapshot JSON, created_by |
| `notifications` | Outbound notification log | type, provider, subject, body, status, dedup_key, sent_at, error |

## Indexes

- `work_items(azure_id)`, `work_items(type)`, `work_items(iteration_id)`,
  `work_items(state)`
- `test_cases(key)` unique, `test_cases(status)`
- `test_results(test_run_id)`, `test_results(test_case_id, status)`,
  `test_results(started_at)` (history queries)
- `defects(azure_id)`, `defects(state)`, `defects(severity)`
- `agent_jobs(status, created_at)`
- `test_matrix_analyses(work_item_id, generated_at)`

## Data Retention

All data retained (history is the product). Report snapshots retained forever in
the archive. Notification logs pruned after 180 days (configurable).

## Conventions

- Enum-like strings are stored as `VARCHAR` with Python-side enum validation and
  DB `CHECK` constraints for the canonical statuses.
- JSON columns for flexible payloads (steps, artifacts, analysis details).
- Soft-delete flag `is_active` on `test_cases`, `test_implementations`,
  `acceptance_criteria` instead of hard deletes, to preserve history.
