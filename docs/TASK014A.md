# Task 014A — Infrastructure and recovery

## Compose and configuration

Next.js proxies same-origin requests to FastAPI at http://backend:8000. Both share the application network; only the backend and migration job join PostgreSQL on its separate internal network. The DB has no published port. Application ports bind to host loopback for local review or a same-host reverse proxy. The named miracle_pg volume holds database state independently of containers. A backend restart ends in-memory Trainer games. Saved Analyzer hands, observations, training sessions and attempts belong to the owning database account.

Copy .env.example to .env. Supply a unique POSTGRES_PASSWORD and a matching DATABASE_URL using the psycopg driver, db hostname, miracle database and URL-encoded password. The database image uses its initialization variables only on first initialization of a volume. Rotate an existing database password in PostgreSQL and update clients together. Never publish rendered Compose configuration with resolved credentials.

```sh
docker compose -f compose.yaml -f compose.accounts.yaml config --quiet
docker compose -f compose.yaml -f compose.accounts.yaml build
docker compose -f compose.yaml -f compose.accounts.yaml up -d --wait
docker compose -f compose.yaml -f compose.accounts.yaml logs migrate
curl --fail http://localhost:8000/ready
curl --fail http://localhost:3000/api/profiles
docker compose -f compose.yaml -f compose.accounts.yaml down
```

Set COMPOSE_PARALLEL_LIMIT=1 on constrained laptops. Use one build or verification command at a time. Ordinary down retains the volume. Volume removal is appropriate only for disposable CI projects. Guest-only Compose uses the process health check and requires no DB.

The account overlay waits for pg_isready, then runs Alembic upgrade head as a one-shot job. Backend startup depends on successful migration. The frontend waits for backend readiness. Long-lived services use unless-stopped. A process restart does not run a new migration; apply migrations again during schema-changing deployments. Check `alembic current` against `alembic heads` in the configured backend environment. The expected revision here is 001_accounts.

Local development uses MIRACLE_ENV=development, http://localhost:3000 and COOKIE_SECURE=false. For account deployment set MIRACLE_ENV=production, COOKIE_SECURE=true, an exact HTTPS TRAINER_ORIGIN, explicit comma-separated ALLOWED_HOSTS and a credentialed PostgreSQL DATABASE_URL. Include localhost for the container readiness probe and backend for the internal proxy. GOOGLE_CLIENT_ID is supplied separately for live login. Native Next.js needs BACKEND_URL pointing to the private backend; Compose supplies it. Terminate TLS at a trusted ingress and restrict network access before exposing any service.

GET /health probes the running process. GET /ready checks the database connection and migration revision. A failed connection, missing table or incompatible revision produces HTTP 503 without returning credentials or database diagnostics. Public solver calculations remain independent of account readiness.

## Backup and recovery rehearsal

Use an isolated PG16 instance with PostgreSQL 16 client tools (createdb, dropdb, pg_dump, pg_restore) on PATH. Install the existing backend development dependencies. Set PGHOST, PGPORT, PGUSER and PGPASSWORD for the disposable cluster, then MIRACLE_DISPOSABLE_PG=yes. Run `python tools/rehearse_recovery.py` from the repository root with normal Python assertions enabled. The script creates two unique databases from template0, migrates one, starts separate backend processes against it, makes a native custom-format dump, and restores it transactionally into the second database. It compares all durable rows, including JSON payloads, owner keys and timestamps. It checks migration identity and constraints and invalidates restored logins and challenges. Both databases created by the rehearsal and the temporary dump are removed on normal completion. The operator owns cluster shutdown.

For real recovery, use restricted backup storage and libpq service/password files. Create the archive with `pg_dump -Fc -f miracle.dump --dbname=service=source`. Create a **new, isolated, empty** database from template0 and point a separate restore service definition at it. Keep application traffic disconnected. Run `pg_restore --single-transaction --exit-on-error --no-owner -d service=restore miracle.dump`. Before allowing application connections, run `psql service=restore -v ON_ERROR_STOP=1 -c "TRUNCATE logins, challenges"`. Verify both counts are zero, check the Alembic revision, verify owner relationships and compare representative records with the backup manifest. Only then configure the application to use the recovered database and verify /ready. The source stays available for rollback. Protect database dumps like the original private records.

## Verification evidence

On Windows, one disposable PostgreSQL 16.2 server was used sequentially for the rehearsal, the 13 targeted account/configuration tests and the full 350-test backend suite. The rehearsal checked fresh and outdated schemas, fresh migration, owner-isolated reads after restarting the application, native dump/restore equality and revocation before reuse. Backend coverage was 97.33%. The server was stopped after verification. CPU and peak memory were not profiled.

Docker CLI was unavailable locally. The dedicated account-infrastructure Actions job builds and starts the merged configuration, checks revision, readiness, frontend and proxy connectivity, tests database persistence after restarting the necessary services and always removes its disposable containers, network and volume. It runs separately from the solver job. Its execution on this branch requires a later push. Production ingress, live identity-provider verification and public deployment are outside this milestone.
