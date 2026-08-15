# Configuring Azure Boards for UAT Metrics

This guide explains how to set up Azure Boards so the UAT Test Intelligence
Platform produces the metrics it was built for (coverage, UAT readiness,
velocity, regression, flakiness, defect health).

## 1. Work item model the platform expects

The platform treats work items in three roles:

| Role | Azure type (expected) | Used for |
|---|---|---|
| Story | `User Story` | Coverage, readiness, test matrix, velocity, risks |
| Bug | `Bug` (or `Issue`) | Defect metrics: MTTR, aging, severity, by-state, reopen rate |
| Everything | `Epic` / `Feature` / `Task` / `Issue` | Synced as work items / hierarchy context |

Critical: coverage, readiness, the test matrix and sprint velocity all filter on
`WorkItem.type == "User Story"` (hard-coded today). If the project process does
not have a `User Story` type, those metrics will be **empty**.

## 2. Your situation: Basic process (Epic / Issue / Task only)

Azure DevOps "Basic" process only offers **Epic**, **Issue** and **Task**. Two
ways forward:

### Option A — switch the project to Agile/Scrum (recommended)

Agile/Scrum provide `User Story` and the built-in **Acceptance Criteria** field
that the platform reads.

- Organization Settings → Boards → Process → select the project → **Change process**
  (Basic → Agile or Basic → Scrum).
- Existing Epics/Issues carry over; create new work as **User Stories**.

This is the least work and matches the platform exactly.

### Option B — configure the platform for Epic/Issue (implemented)

If you cannot change the process, the platform maps the "story" role to a
configured type and reads acceptance criteria from a configurable field:

| Setting | Default | Purpose |
|---|---|---|
| `AZURE_STORY_TYPE` | `User Story` | Type that drives coverage, readiness, matrix, velocity |
| `AZURE_DEFECT_TYPES` | `Bug,Issue` | Types ingested into the defects table on sync |
| `AZURE_ACCEPTANCE_CRITERIA_FIELD` | `Microsoft.VSTS.Common.AcceptanceCriteria` | Field parsed for criteria (one per line) |

For a Basic-process project set `AZURE_STORY_TYPE=Epic` (or `Issue`) and, unless
you add a custom AC field, define where criteria come from. Bugs tracked as
`Issue` are ingested as defects automatically — see §8.

## 3. Acceptance criteria (drives coverage)

- Put every criterion in the **Acceptance Criteria** field, **one per line**.
  The sync splits on newlines; each line becomes a tracked `AcceptanceCriterion`.
- Do not bury criteria in the Description — they are only read from the AC field
  (`Microsoft.VSTS.Common.AcceptanceCriteria`).
- A story is 100% covered when every active criterion is linked to a test case
  (see §6 for the data flow).

## 4. Sprints / iterations (drives velocity)

- Create sprint iterations in **Project Settings → Boards → Iterations**.
- Set each work item's **Iteration Path** to its sprint.
- Sprint, velocity and "current sprint" metrics key off the iteration name
  (the last segment of the iteration path).

## 5. States (drives aging & velocity)

The sync reads `System.State`, `CreatedDate` and `ClosedDate`.

- As a single user, just move items through the normal lifecycle
  (e.g. New → Active → Resolved → Closed) as you work.
- Closed dates feed cycle time / throughput; open items feed aging and readiness.

## 6. How the metrics actually flow

Azure alone does not produce the metrics — the pipeline is:

1. **Sync** — `POST /api/v1/azure/sync` pulls work items, iterations, PRs.
2. **Analyze** — matrix/intelligence agents link test cases to acceptance
   criteria and mark ACs `COVERED`/`NOT_COVERED`.
3. **Execute** — the API test framework (:5001) and Playwright framework (:6000)
   run the tests.
4. **Ingest** — results are posted back to `POST /api/v1/test-runs/ingest`.
5. **Derive** — coverage %, readiness gates, flakiness, regression and defect
   metrics are computed from the stored data.

So "something to link back to actual tests" happens at step 2: each test case
gets linked to an acceptance criterion. You do not need to maintain that linkage
by hand in Azure — it is built by the platform.

## 7. Credentials (PAT) and configuration

- Create a PAT: **avatar → Personal Access Tokens → New Token**, scope
  **Work Items → Read**. Add *Read & Write* only if you enable
  `AZURE_COMMENT_ON_ANALYSIS`.
- Put it in `.env` at the repo root (`.env` is git-ignored; `.env.example` is a
  committed template that must stay empty):

  ```bash
  AZURE_DEVOPS_ORG=<org-slug>
  AZURE_DEVOPS_PROJECT=<project-name>
  AZURE_DEVOPS_PAT=<token>
  ```

- Restart the backend (settings are read at startup), then trigger a sync:
  `POST /api/v1/azure/sync` with `Authorization: Bearer <API_TOKEN>`.

## 8. Open items / known gaps

- **Basic process lacks a built-in AC field.** If staying on Basic without a
  custom field, point `AZURE_ACCEPTANCE_CRITERIA_FIELD` at a custom field you
  add to the process (e.g. a "Acceptance Criteria" text field). Deriving
  criteria from child `Task`s is not implemented.
- **Defect state mapping.** Azure states map directly onto the defects table
  (`New`/`Active`/`Resolved`/`Closed`/`Removed`); Azure has no reopen count, so
  `reopened_count` stays 0 and is not part of Azure-fed metrics.
- **Demo data vs real sync.** Until a real sync runs, dashboards show the demo
  seed. `POST /api/v1/azure/sync` replaces demo content with ADO data.
