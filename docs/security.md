# Security Model

## 1. Principles

- Secrets only in the environment / `.env` (git-ignored). Never in code, docs,
  reports, logs or containers baked at build time.
- The Azure PAT must never appear in logs. The adapter redacts it from any error
  message and never includes it in URLs it logs.
- Defense in depth: network isolation (Tailscale) + API token + input validation
  + scanning in CI.
- Least privilege: a dedicated PAT with read-only scopes for sync; a write scope
  (work items) only if Azure comments/PRs are enabled.

## 2. Secret inventory

| Secret | Env var | Usage |
|---|---|---|
| Azure PAT | `AZURE_DEVOPS_PAT` | Azure REST API |
| API token | `API_TOKEN` | Bearer auth on the API |
| LLM key | `LLM_API_KEY` | LLM provider |
| Telegram token | `TELEGRAM_BOT_TOKEN` | Notifications |
| SMTP creds | `EMAIL_USERNAME/PASSWORD` | Notifications |

`.env.example` contains only placeholders. `.gitignore` excludes `.env`,
`*.pem`, `backups/`, `reports/generated/`.

## 3. Authentication / authorization

- API: `Authorization: Bearer <API_TOKEN>`. If `API_TOKEN` is unset the API logs
  a warning and runs unauthenticated (explicit small-team/Tailscale default),
  except demo endpoints which are always gated by `APP_ENV`.
- Frontend: SPA is unauthenticated by default behind Tailscale. An optional
  `PROXY_BASIC_AUTH_USER/PASSWORD` enables basic auth at nginx for the dashboard.
- Authorization is coarse (admin = API token holder). Role model can be added
  later; interfaces are prepared.

## 4. Input validation

- Pydantic validation at every router boundary (request + response).
- Canonical test-result ingestion validates enums, sizes, and artifact paths.
- `ArtifactStorage` normalizes paths to prevent directory traversal; generated
  HTML is sanitized (escape all interpolated values; no raw user HTML).

## 5. LLM safety

- All structured output validated against Pydantic schemas (twice: provider +
  service).
- Untrusted content (work items, comments) is passed to models with a
  prompt-injection warning; LLM output is treated as data, never executed.
- No LLM output is ever rendered without escaping.

## 6. Scans (CI)

- Secret scanning: `gitleaks` on the repo.
- Dependency scanning: `pip-audit` (Python), `npm audit` (frontend), `trivy`
  for images.
- Container scanning: `trivy` on built images (also `dockle` lints).
- Pipeline is advisory: scans do not block PR merges by humans, but images are
  tagged `-unscanned` when scans are skipped.

## 7. Logging hygiene

- Structured JSON logs; fields `request_id`, `job_id`, `user`, `action`.
- Redactors: Azure PAT, API tokens, bot tokens, passwords.
- No secrets in `AgentJob.result` or error payloads (sanitize before persist).

## 8. Operational

- DB only on the internal network; backups encrypted at rest if the backup disk
  is encrypted (documented).
- Container run as non-root (`USER app`), read-only root filesystem where the
  framework allows, `no-new-privileges`.
- Image pulls pinned to digests in production compose override.
