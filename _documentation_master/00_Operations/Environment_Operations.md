# Environment and Database Operations

This is the operational runbook for local development, Railway configuration,
database maintenance, script-only secrets, backups, and credential incidents. Production
release sequencing belongs to `Deploy_To_Live_System.md`; the two runbooks share the same
environment and authorization rules.

## Non-negotiable rules

- Production is never a default or fallback target.
- A real Mongo URI must include its database path, and that path must match
  `MONGO_DB_NAME`, the runtime environment, and an explicit script target.
- Local application development uses only repository-root `.env.local` and
  `gob-staging`. There is no generic `.env` or production env file.
- For ad-hoc production commands, `GOB_DB_ACCESS` is process-only. Never store it in a
  file or a persistent shell profile. Railway application runtime uses Railway platform
  identity instead and does not need this variable.
- Tests use explicit mongomock or a uniquely named disposable database; never `gob` or
  `gob-staging`.
- Never paste credentials into chat, tickets, documentation, PRs, or shell commands
  that will be retained in history.

## First-time local setup

```bash
cp .env.example .env.local
chmod 600 .env.local
```

Populate `.env.local` with staging credentials and at minimum:

```dotenv
ENVIRONMENT=development
MONGO_DB_NAME=gob-staging
MONGO_URI=mongodb+srv://<user>:<password>@<host>/gob-staging?<options>
```

The URI path must be `/gob-staging`. Local startup fails loudly when `.env.local` is
missing, malformed, names another database, or contains `GOB_DB_ACCESS` or
`GOB_DB_MODE`. It never reads `.env` and never falls back to mongomock.

## Railway environments

Railway uses injected variables only; it does not need or read a repository env file.

| Variable | Staging | Production |
|---|---|---|
| `ENVIRONMENT` | `staging` | `production` |
| `MONGO_DB_NAME` | `gob-staging` | `gob` |
| `MONGO_URI` path | `/gob-staging` | `/gob` |
| `JWT_SECRET_KEY` | staging-specific secret | different production secret |
| `GOB_DB_ACCESS` | omit | omit; Railway runtime receives deployed write access from its platform identity |
| `MAINTENANCE_MODE` | normally `false` or omitted | normally `false`; temporarily `true` only during the maintenance workflow |

Keep all other environment-specific application secrets in the corresponding Railway
environment. Startup logs safely report source, environment, database, and mode without
printing the URI. `/health` safely reports the running commit, hash seed, environment,
database name, and **resolved** database access. For Railway production, resolved access
is `write` even though the raw `GOB_DB_ACCESS` variable is absent.

Changing `MAINTENANCE_MODE` is an operational deployment action. Follow the ordered
Railway/Netlify procedure in `Deploy_To_Live_System.md`; do not toggle it independently
without completing that checklist.

## Tests and disposable databases

The standard test configuration is explicit in `tests/conftest.py` and CI:

```bash
GOB_DB_MODE=mongomock \
ENVIRONMENT=test \
MONGO_DB_NAME=gob-test \
./.venv/bin/python -m pytest
```

The test session refuses `gob` and `gob-staging`. A scratch database must have a unique,
non-live name and use a tool specifically designed for scratch targets. Production-
cluster scratch tools require production read authorization for the cluster connection,
an explicit scratch name, and exact confirmation before destructive cleanup.

## Database script operations

Every database-aware script must require an explicit target and print a safe preflight.
Inspect its exact switches first:

```bash
./.venv/bin/python scripts/<tool>.py --help
./.venv/bin/python scripts/<tool>.py --db gob-staging
```

Writers must expose explicit write intent such as `--apply`, `--commit`, or `--yes`.
Dry-run output should be reviewed before enabling that flag.

`./.venv/bin/python scripts/check_env_safety.py` is the enforcement check. A script that
it reports for direct `MongoClient` use or independent dotenv loading is not approved for
staging or production operation until it is migrated to the shared connection helper.
Do not treat a historically used script as exempt.

## Read-only production diagnostics

Retrieve the production URI from the password manager into a temporary shell variable;
do not type the value directly into the command or store it in the repository:

```bash
GOB_DB_ACCESS=read \
MONGO_URI="$PROD_MONGO_URI" \
MONGO_DB_NAME=gob \
ENVIRONMENT=production \
./.venv/bin/python scripts/audit_legacy_migrations.py --db gob
```

Read mode blocks collection, database, client, command, `$out`, and `$merge` write
surfaces. It is not merely a convention.

## Deliberate production migrations

Use write authorization only for the one reviewed command that needs it:

```bash
GOB_DB_ACCESS=write \
MONGO_URI="$PROD_MONGO_URI" \
MONGO_DB_NAME=gob \
ENVIRONMENT=production \
./.venv/bin/python scripts/<reviewed-tool>.py --db gob <explicit-write-flag>
```

Destructive tools additionally require their exact target confirmation, normally
`--confirm-db gob`. Before executing: resolve exact targets read-only, review dry-run
counts, take or confirm an Atlas snapshot, and define post-write verification. Never
generalize authorization into a persistent shell profile or dotenv file. Unset a
temporary URI afterward:

```bash
unset PROD_MONGO_URI GOB_DB_ACCESS MONGO_URI MONGO_DB_NAME ENVIRONMENT
```

## Backups and restore

MongoDB Atlas Cloud Backup is the production backup authority for `MVP-Cluster`. The
verified configuration on 2026-08-11 showed current hourly/daily snapshots, seven-day
retention, and point-in-time restore. The former local `mongodump`/Google Drive job is
retired and must not be recreated.

Review Atlas → Database → Backup regularly. A restore should normally target a new
temporary Atlas deployment or another isolated database first. Verify collection
counts and representative records before deciding on any production replacement.
Production restore is an incident operation requiring a maintenance window and an
explicit recovery plan. Use the maintenance and rollback sequence in
`Deploy_To_Live_System.md` to stop writes and keep the public application closed.

## Script-only secrets

### R2 image operations

Local R2 tools load complete process variables first. Otherwise they read only:

```text
~/.config/gob/r2.env
```

The file must be external to the repository, non-symlinked, and mode `0600`:

```bash
mkdir -p ~/.config/gob
chmod 700 ~/.config/gob
chmod 600 ~/.config/gob/r2.env
```

It contains `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT`, and `R2_BUCKET`.
Partial process configuration fails rather than mixing process and file credentials.
Railway runtime R2 integration continues to use Railway-injected variables.

### Gemini and Sentry tools

`GEMINI_API_KEY` and `SENTRY_AUTH_TOKEN` are supplied in the invoking process or via an
approved password-manager shell integration. They are not read from repository files.

## Rotation and accidental-access response

Rotate a credential immediately when it appears in terminal output shared with others,
chat, a ticket, source control, CI logs, or an untrusted file—even if the message or
commit is later deleted.

1. Revoke or rotate at the owning provider first (Atlas, Cloudflare, Sentry, Gemini,
   Resend, SendGrid, or auth-secret owner).
2. Update the approved destination: Railway, password manager, `.env.local`, or external
   mode-`0600` script file.
3. Remove the exposed local artifact without echoing its contents.
4. Search the worktree, Git history, CI logs, and collaboration systems for copies.
5. Verify staging first, then production, using safe preflight and health checks.
6. Record what was exposed, its privilege, the exposure window, rotation time, and
   verification—never the secret itself.

For an accidental database write, revoke access if necessary, stop the writer, preserve
logs, determine the exact affected documents, and choose rollback from verified evidence
or Atlas recovery. Do not attempt broad compensating writes from memory.

## Regression checks

```bash
./.venv/bin/python scripts/check_env_safety.py
./.venv/bin/python -m pytest -q tests/test_env_static_safety.py \
  tests/test_env_config.py tests/test_db_environment_integration.py \
  tests/test_script_db.py tests/test_db_read_only_proxy.py \
  tests/test_script_secrets.py
```

The CI workflow runs the static environment check on every push and pull request.
