# Deployment

## 1. Target

Raspberry Pi (4/5, 64-bit OS) running Docker Engine + Compose v2. All data in
persistent Docker volumes; a container restart never destroys data.

## 2. Compose topology

| Service | Image | Ports (host→container) | Notes |
|---|---|---|---|
| `db` | postgres:16-alpine | 5432→5432 (LAN only via bind; see §5) | volume `postgres_data` |
| `api` | built from `docker/api.Dockerfile` | 7000→7000 | runs migrations + scheduler |
| `frontend` | built (Vite → nginx) | 7001→80 | serves SPA, proxies `/api`→`api:7000` |
| `weather` | api-test-framework image | 5000→5000 | mock API under test |
| `api-tests` | api-test-framework image | 5001→5001 | runner + report viewer |
| `webapp` | web-test-framework image | 8000→8000 | demo web application |
| `web-tests` | web-test-framework image | 6000→6000, 6001→6001 | runner + report viewer |

All services share one compose network `uat`. `db` is not port-mapped to the host
by default (only other containers reach it).

## 3. Persistent volumes

```text
postgres_data      # DB
reports            # HTML templates + generated snapshots
screenshots        # Playwright/pytest artifacts
videos
traces
generated_reports  # symlinked under reports/generated (kept as its own volume)
logs               # application logs
```

## 4. Environment

Copy `.env.example` → `.env`. Required for real Azure: `AZURE_DEVOPS_ORG`,
`AZURE_DEVOPS_PROJECT`, `AZURE_DEVOPS_PAT`. Everything else has safe defaults.
Demo mode: `APP_ENV=demo`.

## 5. Network security

- PostgreSQL not published to the host; if remote DB access is needed, bind to a
  Tailscale interface only (e.g. `"100.64.0.5:5432:5432"`).
- `frontend` and `api` are reachable on the Tailscale interface. Keep services
  bound to the docker bridge by default; do not add `network_mode: host`.
- No public-internet exposure unless explicitly configured.
- Optional: add `Caddy`/`nginx` TLS termination later; out of scope for v1.

## 6. Commands

```bash
make up            # build + start
make logs          # tail logs
make migrate       # run alembic migrations
make seed          # load demo dataset (demo mode)
make backup        # pg_dump + report archive tar
make restore FILE  # restore a backup
make down          # stop (keeps volumes)
```

## 7. Backup & Restore

`scripts/backup_database.sh`:
1. `pg_dump -Fc` → `backups/<timestamp>.dump`
2. tar of `reports/` and uploads/artifacts dirs → `backups/<timestamp>-artifacts.tar.gz`
3. Log entry written to `backups/backup.log`. Secrets are never included.

Restore: `scripts/restore_database.sh <file>` drops and recreates the schema
from the dump (documented, requires `APP_ENV` confirmation). See README.

## 8. Migration to larger host / cloud

- Same compose on a larger Linux box or VM.
- K8s: split backend packages into deployments; volumes → PVCs; scheduler into a
  CronJob/`Job` operator; nginx → Ingress. DB schema unchanged.

## 9. Health & observability

- `GET /health` on `api`; compose `healthcheck` for db, api, frontend.
- JSON structured logs (`LOG_FORMAT=json`); request/job IDs throughout.
- `docker compose ps` shows healthy/unhealthy state.
