# Environment Configuration Streamlining Work Plan

**Created:** 2026-08-11  
**Status:** Tasks 1–10 complete; Task 11 validation complete except for live Railway database-identity log confirmation  
**Scope:** Local environment files, deployment variables, database-target resolution,
maintenance scripts, tests, backups, templates, and operational documentation.

## Objective

Make the selected runtime environment and database target explicit, consistent, and
enforceable. A missing, renamed, misplaced, or stale env file must never silently
redirect an application, test, simulation, audit, migration, or backup operation to
production.

The completed system should have:

- one documented local-development configuration;
- no production credentials stored under the repository directory;
- Railway-provided configuration for deployed environments;
- a shared database-target resolver for application and script access;
- process-level authorization for all production access;
- enforceable read-only production access;
- explicit protection for destructive operations;
- isolated test configuration;
- CI checks preventing unsafe env-loading patterns from returning.

## Incident Context

`BackEnd/db.py` previously selected `.env.local` using a path relative to the current
working directory. A script launched after changing into a scratch directory did not
find that file, fell through to `.env`, and connected to the production `gob` database.
Constructing `GameManager` then wrote `position_ratings` to 192 player documents even
though the simulation was assumed to be read-only.

Already fixed:

- `BackEnd/db.py` resolves its env path relative to the repository root.
- Production access is refused at import unless authorized per process with
  `GOB_DB_ACCESS=read` or `GOB_DB_ACCESS=write`.
- The authorization is read from a snapshot of the real process environment taken
  before dotenv loading, so a dotfile cannot grant production access.
- Tests refuse to run when the resolved database is `gob` or `gob-staging`.

Remaining systemic risks:

- `db.py` still silently falls back from a missing `.env.local` to `.env`.
- Production credentials remain in multiple ignored files under the repository.
- Approximately 114 application, test, and maintenance files load or reference env
  files independently.
- Many scripts construct `MongoClient` directly and bypass the protections in
  `BackEnd/db.py`.
- Different scripts use different file order, path resolution, variable names, and
  database-target assumptions.
- Mongo client initialization failures may silently fall back to mongomock in contexts
  where a real database was intended.
- A historical Mongo URI is committed in `.env.backup.example`. Its password has
  already been sunset, but the value must still be replaced with a placeholder.

## Current Env-File Inventory

| File | Git status | Current purpose | Current database posture | Intended disposition |
|---|---|---|---|---|
| `.env` | Ignored/untracked | General local config and service credentials | Production `gob` | Delete after migration |
| `.env.local` | Ignored/untracked | Local development | Staging | Retain; staging-only |
| `.env.production` | Ignored/untracked | Production Mongo/email config | Production `gob` | Delete after migration |
| `.env.backup` | Ignored/untracked | Production backup config | Production `gob` | Move outside repository |
| `.env.backup.example` | Tracked | Backup template | Contains historical real-looking URI | Sanitize or replace |
| `.env.railway.example` | Tracked | Railway template | Placeholder | Consolidate into `.env.example` |

The target repository state is two env files:

1. `.env.example` — tracked, sanitized documentation of supported application variables.
2. `.env.local` — ignored, local-development configuration that explicitly targets
   `gob-staging`.

An optional backup env may exist outside the repository, for example
`~/.config/gob/backup.env`, with filesystem mode `0600`.

Production configuration belongs in Railway or in the real process environment for a
single authorized maintenance command. No production env file or production credential
should live below the repository root.

---

## Task 1 — Complete the Variable and Consumer Inventory

**Status: COMPLETE — read-only audit performed 2026-08-11.** No env values or runtime
behavior were changed.

Classify every supported variable and every code path that reads configuration.

### Work

1. Enumerate variables consumed by:
   - backend application runtime;
   - frontend configuration endpoints;
   - Railway startup and health checks;
   - database scripts and migrations;
   - backup tooling;
   - image-generation and R2 tooling;
   - email tooling;
   - Sentry and diagnostic tooling;
   - tests and measurement harnesses.
2. Classify each variable as:
   - required application secret;
   - required safe configuration;
   - optional integration;
   - deployment-provided metadata;
   - script-only secret;
   - test-only setting;
   - feature flag or kill switch;
   - obsolete/unused.
3. Identify aliases that should be consolidated, including:
   - `MONGO_URI`, `MONGODB_URI`, `MONGO_URI_PROD`,
     `MONGO_URI_PRODUCTION`, and `MONGO_URI_STAGING`;
   - `ENV`, `ENVIRONMENT`, and `RAILWAY_ENVIRONMENT`;
   - production database-name aliases.
4. Produce a consumer table containing file, variable, target environment, direct or
   shared loader, and read/write capability.
5. Identify stale flags. Initial evidence indicates `GOB_DYNAMIC_HCO_MOTION` and
   `GOB_DYNAMIC_HCO_SETPLAY` are no longer runtime consumers; confirm before removal.

### Acceptance criteria

- Every variable in current env files has an owner and classification.
- Every direct dotenv loader and direct `MongoClient` call is inventoried.
- No variable is removed based only on its name or apparent age.

### Task 1 audit results

#### Scale of the configuration surface

The audit used static searches across `BackEnd/`, `scripts/`, `tests/`, `dev.py`, and
Playwright configuration. Counts overlap; a file may appear in several categories.

| Consumer type | Count | Meaning |
|---|---:|---|
| Files loading or naming dotenv/env files | 109 | Independent loaders or explicit env-file consumers |
| Files referencing environment variables | 155 | Application, scripts, tests, and tooling |
| Direct `MongoClient(...)` consumers | 85 | 76 maintenance scripts, 3 backend tests, 5 root tests, plus `BackEnd/db.py` |
| Scripts importing `BackEnd.db` | 107 | These may receive its guard, subject to import order |
| Scripts containing direct Mongo write methods | 133 | Static lower bound; imported constructors can add hidden writes |
| Scripts loading dotenv before importing `BackEnd.db` | 25 | Weakens the current “pre-dotenv” authorization guarantee |

These counts replace the initial approximate figure of 114. There are **109 explicit
env-file consumers** under the audited runtime/tooling scope and **155 files with some
environment-variable dependency**.

#### Critical architecture finding: the current production guard has two bypass classes

1. **Direct-client bypass:** 76 scripts construct `MongoClient` themselves. The
   `BackEnd/db.py` read-only collection wrapper and production authorization check do
   not protect those clients.
2. **Import-order bypass:** 25 scripts load dotenv before importing `BackEnd.db`.
   `_PRISTINE_ENV` is pristine relative to dotenv loading performed *inside* `db.py`,
   but it cannot distinguish values loaded by a caller before `db.py` is imported. A
   future dotfile containing `GOB_DB_ACCESS` could therefore be captured as though it
   came from the invoking shell.

Current env files do not contain `GOB_DB_ACCESS`, so the second issue is a latent design
gap rather than evidence of another access event. Task 5 must move authorization and
connection creation to one entry point that executes before any dotenv loader, and the
static check in Task 7 must prohibit caller-loaded authorization.

#### Current-file variable ownership

No secret values were copied into this audit.

| Current file | Variables | Classification and disposition |
|---|---|---|
| `.env` | `MONGO_URI`, `JWT_SECRET_KEY`, `ENVIRONMENT`, `IS_ALPHA`, `MAINTENANCE_MODE`, `CORS_ORIGINS` | Application runtime. Production-targeting local file; retire. |
| `.env` | `R2_ENDPOINT`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET` | Optional live R2 integration; move to environment-specific configuration. |
| `.env` | `SENDGRID_API_KEY` | Active optional password-reset integration. Keep as a supported variable, not in a production repo file. |
| `.env` | `GEMINI_API_KEY`, `SENTRY_AUTH_TOKEN` | Script/tool-only secrets; remove from application env and provide per tool/command. |
| `.env.local` | `MONGO_URI` | Local database runtime; keep but require explicit `MONGO_DB_NAME=gob-staging`. |
| `.env.local` | `RESEND_API_KEY`, `FEEDBACK_FROM_EMAIL`, `FEEDBACK_TO_EMAIL` | Active optional feedback/alpha email integration. |
| `.env.local` | `SENTRY_AUTH_TOKEN` | Script-only secret; move out of application env. |
| `.env.local` | `GOB_DYNAMIC_HCO_DEFENSE` | Active runtime kill switch; default is enabled when absent. Retain only when deliberately overriding. |
| `.env.local` | `GOB_DYNAMIC_HCO_MOTION`, `GOB_DYNAMIC_HCO_SETPLAY` | Retired. No production runtime consumer remains; references are historical tests/template comments. Remove after policy approval. |
| `.env.production` | `MONGO_URI` | Production database credential; remove from repository directory. |
| `.env.production` | `RESEND_API_KEY`, `FEEDBACK_FROM_EMAIL`, `FEEDBACK_TO_EMAIL` | Active deployment integration; belongs in Railway. |
| `.env.backup` | `MONGO_URI`, `BACKUP_OUTPUT_DIR`, `GOB_BACKUP_DISABLED` | Active backup configuration; move to an external `0600` file. |
| `.env.backup.example` | `MONGO_URI` | Tracked template containing a historical credential. Password is sunset; sanitize the committed value. |
| `.env.railway.example` | `MONGO_URI`, `JWT_SECRET_KEY`, `IS_ALPHA` plus commented options | Incomplete deployment template; consolidate into `.env.example`. |

None of the current real env files contains `MONGO_DB_NAME`. This is a safety gap:
database identity is inferred from URI paths. The target policy requires an explicit
`MONGO_DB_NAME` in local and deployed configuration and agreement with the URI path.

#### Application-runtime variable classification

| Class | Variables | Owner/current behavior |
|---|---|---|
| Database identity and authorization | `MONGO_URI`, `MONGO_DB_NAME`, `GOB_DB_ACCESS` | `BackEnd/db.py`; production access guard is not inherited by direct clients. |
| Required production authentication | `JWT_SECRET_KEY` | `BackEnd/utils/auth.py`; production raises if the development fallback is used. |
| Runtime identity aliases | `ENVIRONMENT`, `ENV`, `RAILWAY_ENVIRONMENT` | API, auth, and Team Builder leak detector use inconsistent fallback chains. Consolidate on one app-owned variable while accepting Railway metadata at the boundary. |
| Alpha/product state | `IS_ALPHA`, `MAINTENANCE_MODE` | API behavior and mutation blocking; safe configuration, not secrets. |
| Browser/API origins | `CORS_ORIGINS` | API CORS middleware; environment-specific safe configuration. |
| Authentication tuning | `JWT_EXPIRATION_HOURS`, `ALPHA_ACCESS_CODE_RATE_LIMIT_PER_HOUR` | Optional numeric overrides with defaults. |
| SendGrid password reset | `SENDGRID_API_KEY`, `RESET_EMAIL_FROM`, `RESET_LINK_BASE_URL` | Active optional integration; missing key degrades by not sending. |
| Resend feedback/alpha/reengagement | `RESEND_API_KEY`, `FEEDBACK_FROM_EMAIL`, `FEEDBACK_TO_EMAIL`, `ALPHA_EMAIL_FROM`, `ALPHA_BADGE_URL`, `SIGNUP_LINK_BASE_URL`, `GOB_MAILING_ADDRESS`, `UNSUBSCRIBE_LINK_BASE_URL`, `EMAIL_UNSUB_SECRET` | Active optional email and compliance configuration. Some values have production-looking defaults and need operational confirmation in Task 2. |
| Sentry | `SENTRY_DSN`, `SENTRY_DSN_FRONTEND` | Optional backend/frontend reporting. `SENTRY_AUTH_TOKEN` and `SENTRY_ORG` are tooling-only. |
| R2 | `R2_ENDPOINT`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET` | Optional runtime recruit image storage; lazy and degradable when absent. |
| Rate limits | `RATE_LIMIT_AUTH`, `RATE_LIMIT_SIM`, `RATE_LIMIT_SIM_TURN`, `RATE_LIMIT_GENERAL` | Optional deployment tuning with defaults. |
| CPU simulation | `FRANCHISE_CPU_SIM_USE_POOL`, `FRANCHISE_CPU_SIM_MAX_WORKERS`, `FRANCHISE_CPU_SIM_POOL_WORKERS` | Optional runtime/performance configuration. |
| EOG instrumentation | `GOB_EOG_BAND_LOG`, `GOB_EOG_BAND_LOG_FILE`, `GOB_EOG_BAND_FRANCHISES`, `GOB_EOG_BAND_TTL_DAYS` | Optional diagnostic configuration; file-path setting requires deployment review. |
| Debug/test controls | `DEBUG_SERIALIZATION`, `DISABLE_DEBUG`, `FOUL_OUT_TEST_MODE`, `FRANCHISE_START_WEEK`, `TB_LEAK_DETECTOR`, `GOB_SIM_PROFILE` | Non-production defaults or explicit diagnostic/test controls; must not enter production accidentally. |
| Reproducibility | `PYTHONHASHSEED` | Runtime/measurement determinism; deployment health reports it. |
| Deployment metadata | `PORT`, `RAILWAY_GIT_COMMIT_SHA`, `GIT_COMMIT_SHA`, `SOURCE_VERSION` | Platform/build-provided; never needed in a local secret file. |
| Playwright-only | `CI`, `BASE_URL`, `PYTHON_PATH` | Test runner configuration, not application env. |

#### Script/tool-only variable classification

| Purpose | Variables | Notes |
|---|---|---|
| Mongo aliases | `MONGO_URI`, `MONGODB_URI`, `MONGO_URI_STAGING`, `MONGO_URI_PROD`, `MONGO_URI_PRODUCTION`, `MONGO_DB_NAME`, `MONGO_DB_NAME_PRODUCTION` | Fragmented naming across scripts; replace with shared resolver + explicit target. |
| Portrait/image generation | `GEMINI_API_KEY`, `PLAYERS_COLLECTION` | Tool-only. Seven scripts consume the Gemini key. |
| Sentry issue retrieval | `SENTRY_AUTH_TOKEN`, `SENTRY_ORG` | Tool-only; not needed by the deployed application. |
| EOG measurement | `GOB_MEASUREMENT_FRANCHISE_ID`, `GOB_MEASUREMENT_TEAM`, `GOB_EOG_BAND_LOG_FILE` | Harness-specific safe identifiers/paths. |
| API diagnostics | `API_URL` | Script-specific safe configuration. |
| Simulation/repro tools | `PYTHONHASHSEED`, `GOB_SIM_PROFILE`, `FRANCHISE_CPU_SIM_USE_POOL`, `DISABLE_DEBUG` | Harness-only overrides. |

#### Alias decisions required in Task 2

1. Canonical Mongo credential variable: `MONGO_URI`.
2. Canonical database identity: `MONGO_DB_NAME`, required and validated against URI.
3. Remove script aliases after migration: `MONGODB_URI`, `MONGO_URI_PROD`,
   `MONGO_URI_PRODUCTION`, `MONGO_URI_STAGING`, and `MONGO_DB_NAME_PRODUCTION`.
4. Canonical application environment: recommend `ENVIRONMENT`; Railway metadata may be
   translated once at startup rather than consulted independently by three modules.
5. Keep `SENTRY_DSN`/`SENTRY_DSN_FRONTEND` for runtime reporting and separate them from
   the tool-only `SENTRY_AUTH_TOKEN`/`SENTRY_ORG`.
6. SendGrid and Resend are not aliases: they currently serve different active product
   paths. Do not consolidate them without a separate email-provider decision.

#### Direct-client inventory and migration groups

All direct `MongoClient` consumers were enumerated during the audit. The 76 script
consumers fall into these migration groups:

- **Production/staging dual-target and explicit production:**
  `cleanup_games_by_retention_policy.py`, `copy_gob_defenses_to_staging.py`,
  `copy_recruit_sets_staging_to_gob.py`, `copy_teams_gob_to_staging.py`,
  `delete_all_tournaments_staging.py`, `delete_gob_selected_collections.py`,
  `migrate_set_play_positions_to_target_shooter_staging.py`,
  `set_admin_user_production.py`, `sync_gob_players_from_staging_with_backup.py`,
  `sync_play_names_gob_from_staging.py`, and `upsert_teams_gob_to_staging.py`.
- **Destructive/repair/backfill writers:** add/update/delete/cleanup/migrate/reset/swap,
  recruit regeneration, play repair, ID alignment, and attribute rewrite scripts. These
  are Phase A/B even when their filenames say staging.
- **Nominally read-only audits/exports:** analysis, count, inspect, report, and export
  scripts. These remain untrusted until constructors/imports are traced for hidden
  writes, as demonstrated by `GameManager`.
- **Tests with direct clients:** backend/root tests use mongomock or test fixtures, but
  must migrate or receive an explicit static-check exception so production client
  patterns are not normalized in test code.

The reproducible inventories are:

```bash
rg -l --glob '*.py' 'MongoClient\(' BackEnd scripts tests
rg -l --glob '*.py' --glob '*.sh' --glob '*.mjs' \
  'load_dotenv|dotenv_values|source .*\.env|\.env\.local|\.env\.production|\.env\.backup' \
  BackEnd scripts tests
rg -l --glob '*.py' \
  '\.(insert_one|insert_many|update_one|update_many|replace_one|delete_one|delete_many|bulk_write|drop|rename|find_one_and_update|find_one_and_delete)\(' \
  scripts
```

Task 6 must capture the exact file list in its migration checklist as scripts are
converted. The counts above are the Task 1 baseline against which completion will be
measured.

#### Task 1 conclusion

No security-sensitive action is required from the user for Task 1. The audit confirms
that the planned shared resolver is necessary and that migration must cover both direct
clients and scripts importing `BackEnd.db`. The next work item is Task 2: agree on the
environment policy and the small number of operational choices that cannot be inferred
from code alone.

## Task 2 — Establish and Document the Environment Policy

**Status: COMPLETE — policy approved 2026-08-11.** This task records the agreed
destination; it does not yet change loaders, credentials, deployments, or env files.

Define the allowed configuration source for every execution context.

### Policy

| Context | Configuration source | Allowed database |
|---|---|---|
| Local application | Repo-root `.env.local` | `gob-staging` only |
| Unit tests | Explicit test env; normally mongomock | `gob-test` or unique scratch DB |
| Measurement harness | Explicit CLI/process environment | Named scratch DB unless explicitly authorized |
| Railway staging | Railway variables | `gob-staging` |
| Railway production | Railway variables | `gob` |
| Production diagnostic | One-command process environment | `gob`, `GOB_DB_ACCESS=read` |
| Production migration | One-command process environment | `gob`, `GOB_DB_ACCESS=write` |
| Backup job | External `0600` file or secret manager | Explicit backup target |
| R2/image tooling | One-command environment or dedicated external secret file | No implicit DB target |

### Approved policy decisions

1. **Local application database:** ordinary local development may connect only to
   `gob-staging` through the repository-root `.env.local`. Scratch databases require an
   explicit test or command configuration.
2. **Missing local configuration:** when ordinary local startup expects `.env.local`, a
   missing file is a fatal configuration error. There is no fallback to `.env`,
   production, or mongomock. Railway, CI, and commands that explicitly provide their
   complete process environment do not require `.env.local`.
3. **Canonical environment identity:** application code will use `ENVIRONMENT` with
   allowed values `development`, `test`, `staging`, and `production`.
   `RAILWAY_ENVIRONMENT` remains platform metadata translated once at the configuration
   boundary. The `ENV` alias will be retired after consumers migrate.
4. **Database identity agreement:** configured real-database contexts require both
   `MONGO_URI` and `MONGO_DB_NAME`. The URI database, `MONGO_DB_NAME`, deployment
   environment, and requested script target must agree or execution fails before a
   collection is opened.
5. **Mongomock is explicit:** mongomock is permitted only when tests or a dedicated
   test configuration select it. Missing credentials, malformed configuration, DNS
   failure, and connection failure must not silently choose mongomock.
6. **Production maintenance credentials:** no production credential will live in a
   repository file. It will be retrieved from the password manager or another approved
   source and supplied to one command together with process-level
   `GOB_DB_ACCESS=read|write`. This still permits deliberate IDE-agent production work;
   it prevents implicit production access.
7. **Script-only secrets:** `GEMINI_API_KEY`, `SENTRY_AUTH_TOKEN`, offline R2 uploader
   credentials, and similar tooling secrets will be supplied per command or through a
   dedicated external file with mode `0600`. Application runtime R2 credentials remain
   allowed in staging `.env.local` and Railway configuration.
8. **Backup configuration:** the target external path is
   `~/.config/gob/backup.env`, protected with mode `0600`. Backup tooling will require
   that explicit file and will not fall back to a repository env file.
9. **Destructive production confirmation:** production writes require both
   process-level `GOB_DB_ACCESS=write` and target-specific confirmation such as
   `--confirm-db gob`. Especially destructive interactive commands should require the
   operator to enter the database name; non-interactive operation requires an equally
   explicit command flag.

### Supporting decisions

- SendGrid and Resend remain separate supported integrations because they currently
  serve different active product paths.
- Local `.env.local` will explicitly contain `MONGO_DB_NAME=gob-staging`.
- `GOB_DYNAMIC_HCO_MOTION` and `GOB_DYNAMIC_HCO_SETPLAY` will be removed after the
  template/configuration migration because Task 1 confirmed they have no active runtime
  consumer.
- Deployment configuration remains in Railway rather than deployment env files in the
  repository.
- Tests remain prohibited from resolving to `gob` or `gob-staging`.
- Files containing credentials use Unix/macOS mode `0600` (`rw-------`): only the file
  owner may read or write them.

### Required rules

- Local `.env.local` must set both a staging URI and
  `MONGO_DB_NAME=gob-staging`.
- Production is never an implicit default.
- `GOB_DB_ACCESS` cannot be granted from a dotenv file.
- The database named by the URI, `MONGO_DB_NAME`, requested CLI target, and deployment
  identity must agree.
- Missing or ambiguous configuration fails closed.
- A requested real database must not silently become mongomock after a connection or
  configuration failure.

### Acceptance criteria

- The policy is agreed before loaders or files are removed.
- Every supported execution context has exactly one documented configuration source.

**Acceptance result:** satisfied. All nine policy decisions were approved, including
the explicit mechanism that allows authorized IDE agents to perform production writes
without retaining production credentials inside the repository.

## Task 3 — Create Sanitized Templates

**Status: COMPLETE — implemented 2026-08-11.** Only tracked templates, ignore rules,
and documentation references changed. Real ignored env files and Railway variables were
not modified.

### Work

1. Create a single tracked `.env.example` organized into:
   - required local runtime;
   - database identity;
   - authentication;
   - browser/CORS configuration;
   - email integrations;
   - monitoring;
   - R2 assets;
   - optional tuning and kill switches.
2. Use obvious placeholders only. Do not include real hosts, usernames, passwords,
   tokens, bucket names, or email recipients unless intentionally public.
3. Replace the historical URI in `.env.backup.example` with placeholders.
4. Decide whether the backup template remains as a tracked specialized template or is
   represented in operational documentation instead.
5. Consolidate and retire `.env.railway.example` after its useful comments are moved to
   `.env.example` and deployment documentation.
6. Add comments stating that `GOB_DB_ACCESS` must be supplied by the process and must
   never be placed in a dotfile.

### Acceptance criteria

- A secret scan finds no credential-like values in any tracked template.
- A new developer can construct a staging-only `.env.local` without consulting code.

**Acceptance result:** satisfied.

- Added the consolidated tracked `.env.example`, explicitly staging-oriented for local
  development and grouped by runtime owner.
- Documented that production configuration belongs in Railway and that
  `GOB_DB_ACCESS` must never be stored in dotenv.
- Included active optional SendGrid, Resend, Sentry, R2, rate-limit, CPU-simulation,
  diagnostic, and defense kill-switch variables.
- Excluded script-only credentials and retired Dynamic HCO motion/set-play flags from
  the application template.
- Replaced the historical credential in `.env.backup.example` with obvious
  placeholders and documented the future external `0600` location.
- Retired `.env.railway.example` after transferring its useful configuration guidance.
- Updated `.gitignore` to explicitly allow the two sanitized tracked templates.
- Updated `_documentation_master/ENV_VARIABLES.md` to point local setup at
  `.env.example` → `.env.local` and to prohibit a repository production env file.

## Task 4 — Harden the Application Environment Loader

**Status: COMPLETE — implemented 2026-08-11.** Application loading is hardened;
maintenance-script consolidation remains Task 5/6. Live Railway validation remains in
Task 11 because this task did not mutate or inspect Railway configuration.

Refactor `BackEnd/db.py` or a new shared environment module without changing production
deployment behavior accidentally.

### Work

1. Remove the `.env.local` → `.env` fallback.
2. Detect execution context before selecting a local file:
   - Railway uses injected variables and does not require `.env.local`.
   - CI/tests use their explicitly injected test identity.
   - an explicitly configured one-command invocation may use its process environment;
   - ordinary local startup requires repo-root `.env.local`.
3. If local `.env.local` is expected and missing, raise a clear startup error.
4. Remove the implicit fallback database name of `gob`. An absent database identity
   must fail unless the execution context explicitly selects mongomock/test mode.
5. Parse and normalize the database named in the URI.
6. Reject disagreement between the URI database and `MONGO_DB_NAME`.
7. Preserve the pre-dotenv snapshot used for `GOB_DB_ACCESS`.
8. Make mongomock selection explicit:
   - permitted for tests or an explicit local test mode;
   - not selected merely because a configured Mongo client failed to initialize.
9. Print the resolved environment, access mode, and database name at startup without
   printing the URI or credentials.

### Acceptance criteria

- Missing `.env.local` cannot reach `.env` or production.
- Railway staging and production start from injected variables only.
- URI/database mismatch fails before any collection is opened.
- A real-DB connection failure cannot silently run against mongomock.

**Acceptance result:** satisfied in code and automated tests.

- Added `BackEnd/env_config.py` as the application-runtime configuration boundary.
- Removed `.env` loading and the implicit `gob` database default from `BackEnd/db.py`.
- Ordinary local startup now requires repository-root `.env.local`.
- Real Mongo requires `ENVIRONMENT`, `MONGO_URI`, and `MONGO_DB_NAME`; URI path,
  explicit name, and environment target must agree.
- `development` and `staging` resolve only to `gob-staging`; `production` resolves only
  to `gob`; `test` cannot target either live database.
- Added explicit `GOB_DB_MODE=mongomock`. It requires `ENVIRONMENT=test` and a non-live
  database name. Mongo initialization errors now propagate instead of selecting mock.
- `GOB_DB_ACCESS` and `GOB_DB_MODE` are rejected when supplied by `.env.local`.
- Preserved process-level production read/write authorization and Railway's deployed
  write access behavior.
- Added the non-secret local identity fields `ENVIRONMENT=development` and
  `MONGO_DB_NAME=gob-staging` to the ignored `.env.local`; no credential values changed.
- Updated pytest and GitHub Actions to select mongomock explicitly.
- Added pure resolver and subprocess import tests covering missing local configuration,
  no `.env` fallback, target disagreement, explicit mock, Railway process configuration,
  production refusal/read authorization, and invalid-real-Mongo failure behavior.
- Updated `Database_System.md` and `ENV_VARIABLES.md` to describe the new behavior.

**Known boundary carried into Task 5:** scripts that load dotenv before importing
`BackEnd.db`, and scripts constructing `MongoClient` directly, are not fixed by the
application loader. They remain the next prioritized migration surface.

## Task 5 — Build One Shared Script Database Resolver

**Status: COMPLETE — implemented 2026-08-11.** The shared boundary is available and
tested. Existing maintenance scripts have not been migrated to it; that is Task 6.

Create a shared module used by all database-aware scripts.

### Required interface

The exact API should follow existing project conventions, but it must accept or resolve:

- explicit target: `gob-staging`, `gob`, or a named scratch/test database;
- explicit access intent: `read` or `write`;
- URI/process configuration;
- whether the operation is destructive;
- an optional expected collection/database marker.

### Required behavior

1. Never load `.env`, `.env.production`, or another fallback automatically.
2. Local staging may load only repo-root `.env.local`.
3. Production credentials must be present in the real process environment.
4. Require process-level `GOB_DB_ACCESS=read|write` for production.
5. Wrap or expose collections so `read` access rejects writes, including:
   - insert/update/replace/delete;
   - bulk writes;
   - drop/rename;
   - destructive database commands.
6. Validate URI database, override, and requested target before connecting.
7. Print a safe preflight summary:
   - environment;
   - database;
   - access mode;
   - destructive/non-destructive classification.
8. Production destructive operations require an additional deliberate confirmation,
   preferably a target-specific CLI flag or typed database name. Do not rely on a broad
   reusable shell-prefix approval.

### Acceptance criteria

- Scripts cannot reach production through a dotenv fallback.
- `read` mode blocks writes at the collection boundary.
- Mismatched targets fail before connection or mutation.

**Acceptance result:** satisfied by `BackEnd/script_db.py` and
`tests/test_script_db.py`.

### Implemented interface and behavior

- `connect_script_database(target=..., access=...)` requires an explicit database name
  and `read` or `write` intent.
- Production target `gob` requires an exact process-level authorization match:
  `GOB_DB_ACCESS=read` for read connections or `GOB_DB_ACCESS=write` for write
  connections.
- Production cannot use mongomock and never loads credentials from `.env.local`.
- Local staging may use repository-root `.env.local` only when complete process
  configuration was not supplied. It never reads `.env` or `.env.production`.
- Scratch/test use may explicitly select `GOB_DB_MODE=mongomock`; live database names
  are prohibited in mock mode.
- Requested target, `MONGO_DB_NAME`, URI database path, and `ENVIRONMENT` are validated
  before client construction.
- Destructive production writes require both write authorization and either matching
  `confirm_db="gob"` (the future `--confirm-db gob` CLI value) or matching interactive
  entry of the database name.
- Every successful connection prints a credential-free preflight containing only
  environment, database, access, destructive flag, mode, and safe source label.
- Read connections return guarded client, database, and collection objects. They block:
  CRUD writes, bulk writes/builders, find-and-modify operations, drops/renames,
  index/search-index changes, write aggregation stages (`$out`/`$merge`), database
  commands, database creation/drop surfaces, and client sessions that could expose an
  unguarded transactional path.
- Write connections expose the normal client/database only after configuration and
  authorization succeed.
- The client factory is injectable so all production, staging, and mismatch cases can
  be verified with mongomock without contacting live databases.

### Verification

Automated tests cover:

- target/URI/name/environment disagreement;
- refusal to fall back from missing `.env.local` to `.env`;
- production read and write authorization;
- destructive production confirmation;
- explicit mock restrictions;
- read-only CRUD, aggregation, command, database, and client enforcement;
- permitted writes through an explicit mock write connection;
- credential-free preflight output.

**Task 6 boundary:** Until individual scripts import this helper, their current direct
`MongoClient` and independent dotenv paths remain unchanged. Task 5 does not claim those
scripts are protected yet.

## Task 6 — Migrate Database Scripts in Risk Order

**Status:** PHASE A1 COMPLETE — read-only audit performed 2026-08-11. No database
script behavior was changed and no database connection was opened. Phase A2 migration
is pending the disposition decisions below.

Do not attempt a blind mechanical rewrite of all scripts at once.

### Phase A — Highest risk

Migrate first:

- deletion and cleanup scripts;
- production/staging copy and synchronization scripts;
- migrations and backfills;
- scripts that open both production and staging;
- scripts that construct `GameManager` or another object with hidden writes;
- scripts that use `.env.production` or treat `.env` as production;
- backup and restore tooling.

### Phase A1 audit results

The audit traced each script's actual collections and calls. A filename, printed
database name, or `client["gob"]` check is not a target guard: PyMongo permits selecting
any database name on any connected cluster. Safety requires validating the requested
target against the URI and process authorization at the shared connection boundary.

#### Production-capable and cross-database operations

| Script | Actual target and operation | Existing safeguards/gaps | Recommendation |
|---|---|---|---|
| `cleanup_games_by_retention_policy.py` | Reads and may delete from `games` in both `gob-staging` and `gob`; production preserves active franchise/tournament games and deletes other modes/orphans | Dry-run default and `--yes`, but targets both databases by default; independent dotenv chain and direct client | **Retain + migrate.** Require one explicit target per invocation; production deletion requires write authorization and destructive confirmation. |
| `copy_gob_defenses_to_staging.py` | Reads `gob.defenses`; replaces `gob-staging.defenses` through a temporary collection and atomic rename | Dry-run default, explicit execute, source/target DB-name checks, different-URI check, and exact verification; still bypasses shared resolver | **Retain + migrate.** This is the best existing replacement pattern. Preserve production-read/staging-write separation and exact verification. |
| `copy_recruit_sets_staging_to_gob.py` | Reads all staging recruit sets; deletes and reinserts all production recruit sets | Explicit dry-run/apply and empty-source refusal; one independently loaded URI; replacement is non-atomic and count-only verification | **Retain only if this remains the recruit-set publishing workflow; migrate + harden.** Use a temporary production collection, exact verification, atomic rename, and destructive production confirmation. |
| `copy_teams_gob_to_staging.py` | Reads all production teams; drops and reinserts staging teams | Dry-run default and separate URI/name checks; non-atomic replacement and count-only verification | **Retire in favor of `upsert_teams_gob_to_staging.py` unless exact mirroring is required.** If retained, use the verified temporary-collection pattern. |
| `upsert_teams_gob_to_staging.py` | Reads production teams; upserts each into staging and leaves staging-only documents intact | Dry-run default, separate URI/name checks; not an exact mirror | **Retain + migrate** as the normal additive team sync. |
| `clone_reference_data_to_staging.py` | Reads six production reference collections and clears/reinserts each staging counterpart | Interactive `yes`, but no dry-run, one implicit URI, non-atomic per-collection replacement, and partial completion is possible | **Retire in favor of scoped, verified synchronization tools.** If a full bootstrap is still operationally required, rebuild it as an explicit manifest-driven command using temporary collections. |
| `replace_gob_fcp_hct_from_staging.py` | Deletes/reinserts all production FCP and HCT skeletons from staging | Explicit dry-run/apply and empty inserts are allowed; one implicit URI, non-atomic, no backup or exact verification | **Consolidate into a retained universal-data publisher**, if skeleton publishing is active; otherwise retire. Do not keep as an independent unsafe replacer. |
| `replace_gob_universal_from_staging.py` | Backs up then deletes/reinserts all production teams and players from staging | Explicit dry-run/apply and local JSON backup; one implicit URI, backup stays in repo `tmp`, replacement is non-atomic, and only final counts are printed | **Consolidate with the universal-data publisher + harden.** External backup, nonempty-source check, exact verification, atomic rename, and destructive production confirmation are required. |
| `sync_gob_players_from_staging_with_backup.py` | Replaces production `players_backup`, then deletes/reinserts production `players` from staging | Explicit dry-run/apply and nonempty-source/destination checks; backup and replacement are non-atomic and count-only | **Consolidate with the universal-data publisher + harden.** It duplicates the previous script with a different backup strategy. |
| `sync_play_names_gob_from_staging.py` | Updates only matched production play `name` fields from staging | Dry-run default and scoped field updates; independent dotenv/direct client | **Retire if the one-time correction is complete; otherwise migrate as a narrowly scoped production writer.** |
| `migrate_set_play_positions_to_target_shooter_staging.py` | Updates plays and embedded play data; supports staging or production and can first copy fields staging→production | Supports dry-run, but write mode is the default; independent loaders/clients and multiple target aliases | **Retire if the schema migration is complete.** If retained for recovery, migrate and make dry-run the default with explicit target/write intent. |
| `set_admin_user_production.py` | Updates one production user's role by email | Scoped write, but no dry-run/confirmation and independent production env/client | **Retain + migrate.** This is a legitimate ongoing administrative operation; require explicit production write authorization and show the resolved user/change before confirmation. |
| `s11_provision_convergence_scratch.py` | Reads production reference data; writes or drops `gob-s11-league-convergence` | Hard-coded scratch destination, but loads `.env` before `.env.local`, direct client, and `--drop` has no confirmation | **Retain + migrate.** Production read plus scratch write; destructive confirmation applies to dropping/recloning scratch. |

#### Destructive reset, cleanup, backup, and restore operations

| Script | Actual target and operation | Existing safeguards/gaps | Recommendation |
|---|---|---|---|
| `delete_all_tournaments_staging.py` | Deletes every tournament in staging by default, but also supports production `--db gob` | Dry-run default and `--yes`; its database-name check is not a URI/cluster guard | **Retain as staging-only. Remove the production option.** A production tournament purge, if genuinely needed, should be a separately named/runbook-controlled operation. |
| `delete_gob_selected_collections.py` | Deletes every document from six production franchise/game collections | Dry-run default and `--yes`; catastrophic scope, independent production loader, ineffective DB-name guard | **Decision required; recommended retire.** Retain only if a documented production-reset capability is an intentional operational requirement. |
| `cleanup_game_collections.py` | Deletes all production tournaments, franchises, and games | Interactive typed `DELETE`; implicit `.env`, direct client, no dry-run or real target guard | **Retire.** It overlaps the broader production reset tool and has weaker controls. |
| `wipe_alpha_data.py` | Deletes users plus all game/franchise data from whichever database `BackEnd.db` resolves | Dry-run default and execute confirmation; generic name and no explicit target in CLI | **Retain + migrate** only as an explicit staging/approved production reset runbook. Its inclusion of `users` makes it materially different from ordinary cleanup. |
| `delete_all_franchises_staging.py` and `.sh` | Deletes all staging franchises, FTD, FPD, and FRD | No dry-run and Python version may fall back to an unguarded `mongosh` path; shell version loads CWD env and has no confirmation | **Replace both with one migrated staging-only command**, dry-run by default with destructive confirmation; retire the shell duplicate and fallback. |
| `delete_orphan_staging_players.py` | Computes unreferenced staging players and deletes only those IDs | Dry-run default and `--yes`; independent env/direct client | **Retain + migrate.** Scoped staging repair. |
| `reset_db.py` | Immediately deletes all teams and players from whichever DB the application resolves | No CLI, dry-run, prompt, or explicit target | **Retire immediately in Phase A2.** It is redundant and unsafe. |
| `backup_gob_staging_players.py` | Replaces staging `players_backup` using `$out` and writes backup metadata | Staging hard-code and replace opt-in; independent loader/direct client; hard-code is not URI validation | **Retain + migrate.** Treat `$out` and metadata update as staging writes; retain overwrite confirmation. |
| `eog_arm_snapshot.py` | Snapshots staging franchise state to disk; restore deletes/replaces franchise-scoped records and optionally global feed docs | Checks for `gob-staging` text in URI and validates franchise/team; restore is destructive but has no separate confirmation; imports shared app collections | **Retain + migrate.** Declare read for snapshot/verify and write for restore; explicit staging target and restore confirmation. Keep global-feed opt-in warning. |

#### Hidden-write simulation scripts

| Script | Hidden write | Recommendation |
|---|---|---|
| `simulate_100_quarters.py` | `GameManager.__init__()` calls `_update_position_ratings()`, which may update player documents before the simulation begins | **Migrate or isolate before treating it as a measurement tool.** It requires declared write access today, or `GameManager` must later receive a genuinely non-persisting construction mode. |
| `test_hco_resolution_stats.py` | Same constructor-triggered `position_ratings` persistence | **Migrate/isolate identically.** A filename beginning with `test_` does not make this read-only. |

The convergence audit itself writes only to its forced scratch database, but its
provisioner reads `gob`; both belong in Phase A because the provisioning boundary is
production-capable. Other Phase B/C scripts remain pending and will be classified as
they are migrated.

#### Phase A2 disposition decisions

Decisions recorded 2026-08-11:

1. **Recruit-set publishing remains active.** Staging `recruit_sets` must eventually
   replace production `recruit_sets`, after staging testing is complete. Migration may
   make the publisher safe now, but must not execute the production replacement as part
   of this env-streamlining work.
2. **The set-play position migration and play-name sync are complete.** Retire both
   one-time scripts.
3. **Routine lifecycle cleanup is franchise-scoped, not database-wide.** Season
   rollover deletes only `games` for the current franchise after rebuilding its FPD,
   FRD, schedule, and season state. User deletion cascades only that owned franchise's
   FTD, FPD, FRD, games, press-conference sessions, franchise document, and applicable
   signed-player R2 masters. Those paths do not need a command that wipes every user's
   production data. A separate emergency whole-production reset capability is not
   required and will be retired.

Additional decisions recorded 2026-08-11:

1. **Use additive team sync.** Production teams are upserted into staging while
   staging-only test records are preserved. Retire the exact-mirror team-copy script.
2. **Build one selectable universal-data publisher.** It must publish only collections
   explicitly selected by the operator and share authorization, backup, temporary-
   collection, exact-verification, and confirmation behavior. Selecting one collection
   such as `recruit_sets` must not publish any other collection.
3. **Retire whole-production franchise/game wipe scripts.** Routine season rollover,
   user franchise deletion, and the scoped admin cleanup path already perform targeted
   lifecycle cleanup. No emergency database-wide reset command will be retained.

All Phase A1 disposition questions are resolved. Phase A2 may proceed without further
product assumptions; publishing production data remains out of scope until separately
requested after staging validation.

### Phase A2 implementation results

**Status:** APPROVED HIGH-RISK BATCH COMPLETE — implemented 2026-08-11. Verification
used compilation, mongomock, and unit tests only. No staging or production connection
was opened, and no universal data was published.

Implemented:

- Added `scripts/publish_universal_data.py`, a selectable staging→production publisher
  for `recruit_sets`, `teams`, `players`, `fcp_skeletons`, and `hct_skeletons`.
  Selection is collection-by-collection; apply requires production write authorization,
  exact database confirmation, an external `0600` backup, nonempty staging source,
  temporary production collection, exact document verification, and atomic rename.
- Added explicit dual-target support to `BackEnd/script_db.py`: production configuration
  remains process-only while staging independently resolves from repo-root `.env.local`.
- Added a dedicated production-cluster scratch boundary. It requires production-read
  authorization, rejects `gob`/`gob-staging` as scratch targets, and requires the exact
  scratch name for destructive operations.
- Migrated the retained production→staging defense replacement and additive team sync,
  production admin-role assignment, per-target games retention cleanup, staging
  tournament/franchise/orphan cleanup, staging player backup, EOG snapshot/restore,
  staging-only alpha cleanup, and S11 scratch provisioning.
- Added `GameManager(..., persist_position_ratings=False)` for offline measurement
  callers. It preserves identical in-memory rating calculation while preventing the two
  audited simulation scripts from writing universal player ratings. Normal gameplay
  retains the default `True` behavior.

Retired as approved:

- exact-mirror or duplicate publishers: `copy_recruit_sets_staging_to_gob.py`,
  `copy_teams_gob_to_staging.py`, `clone_reference_data_to_staging.py`,
  `replace_gob_fcp_hct_from_staging.py`, `replace_gob_universal_from_staging.py`, and
  `sync_gob_players_from_staging_with_backup.py`;
- completed one-time corrections: `sync_play_names_gob_from_staging.py` and
  `migrate_set_play_positions_to_target_shooter_staging.py`;
- whole-production or unsafe duplicate reset paths: `delete_gob_selected_collections.py`,
  `cleanup_game_collections.py`, `reset_db.py`, and the shell duplicate
  `delete_all_franchises_staging.sh`.

Verification:

- 13 focused resolver/publisher/non-persisting-GameManager tests pass.
- Compilation passes for every script changed in this batch.
- The publisher regression test proves selecting `recruit_sets` replaces only that
  collection, preserves unselected production `teams`, writes the backup with mode
  `0600`, and uses no live database.
- Two unrelated pre-existing assertions in `tests/test_game_manager.py` still fail
  (`MockPlayer` missing `MIN`; expected `Lancaster` box-score key absent). The focused
  GameManager persistence test passes, so those failures were not rewritten or hidden.

Task 6 is not globally complete: 62 other scripts still construct `MongoClient`
directly. They remain queued for the Phase B writer and Phase C read-only migration
passes; this batch does not claim they are protected.

### Phase B — Ordinary writers

- staging data updates;
- roster/player/team repair scripts;
- image metadata publication;
- recruit-set and universal-data updates.

#### Phase B progress — 2026-08-11

The first unambiguous staging-only batch is migrated. No database connection was
opened. These scripts now use `BackEnd.script_db`, resolve only repo-root staging
configuration, and declare read versus write from their existing dry-run/apply flag:

- `regenerate_recruit_set_0001.py`;
- `regenerate_universal_pool.py`;
- `age_up_pool_class_years.py`;
- `edit_pool_attributes.py`;
- `recalibrate_pool_physicals.py`;
- `decap_player_attr_hundreds_gob_staging.py`;
- `rewrite_comp_player_attrs_gob_staging.py`;
- `sync_team_regions_to_gob_staging.py` (now dry-run by default; `--apply` writes);
- `rename_daniel_wilkinson_to_daniel_leverette_staging.py`;
- `rename_jett_scheller_to_jett_wood_staging.py`.

The initial batch reduced direct `MongoClient` consumers from 62 to 52.

The remaining writers cannot be safely treated as one mechanical group:

1. **Legacy schema/data migrations:** add FTE/user/subscription/scouting/play fields,
   migrate OTP/FTE/playbook/tournament/player-ID schemas, remove old skeleton steps,
   and historical one-player/play corrections. These appear one-time by design, but
   code alone cannot prove whether every deployed database received each migration.
2. **Production-capable dual writers:** team prestige, recruit regions, core team
   colors, selected player attributes/anchors, target-shooter/play-step corrections,
   and 1-3-1 defense spots currently update both `gob` and `gob-staging` in one run.
   This conflicts with the approved one-explicit-target-per-invocation policy.
3. **Operational tools:** access-code email backfill, season-advance harness, local
   player-image rename, and admin assignment have ongoing or externally visible side
   effects and need individual migration rather than retirement by filename.

Phase B pauses at this disposition boundary: deleting a legacy migration without
deployment evidence or silently changing a dual-production repair into staging-only
would require assumptions outside the code.

Disposition approved 2026-08-11:

- retain legacy migrations until deployment verification proves they can be retired;
- require exactly one `--db gob-staging` or `--db gob` target per invocation for every
  previously dual-target writer;
- consolidate staging and production admin assignment into one explicit-target tool.

Second Phase B batch:

- consolidated `set_admin_user.py` and removed the duplicate
  `set_admin_user_production.py`;
- migrated the scouting-report, user-tracking, persona-intro, FTE-v2, FTE-reset,
  alpha-OTP sent-field, sent-OTP synchronization, FTE-field, subscription/geek-points,
  and FTD-alterations migrations;
- added `scripts/db_migration_cli.py`, a thin adapter that maps legacy CLI target names
  onto the shared resolver without loading dotenv itself;
- made formerly implicit/both-target user-field migrations dry-run by default and
  require one explicit database target.

After this batch, 41 script files still construct `MongoClient`; 19 of those contain
write calls and remain in Phase B. No database was contacted during either batch.

Third Phase B batch:

- migrated the remaining direct-client writers, including player-ID conversions,
  FTD playbook migration, access-code email backfill, the staging season harness,
  retained FCP/HCT skeleton corrections, and the production-read/staging-write player
  alignment tools;
- migrated additional legacy team/player utilities that independently parsed
  `.env.local`/`.env`, including mascot/prestige/team-ID updates, TSV attribute loads,
  team repopulation/sync, player roster backfill, pool potential-factor backfill, and
  username assignment;
- every migrated mutator is dry-run/read-only by default and requires `--apply` or its
  retained explicit execute flag to obtain a write connection;
- formerly dual-target operations now open separately validated production-read and
  staging-write connections. They no longer assume both databases share one URI;
- the season-advance harness remains staging-only. Because it executes application
  routes with module-owned collections, it performs the shared staging write preflight
  before importing those routes and requires both `--db gob-staging` and `--apply`.

Offline verification after this batch:

- all Python files under `scripts/` compile;
- 26 environment, resolver, publisher, and persistence-focused tests pass;
- `git diff --check` passes;
- no live staging or production database was contacted;
- no script containing a detected Mongo mutation both constructs `MongoClient` and
  loads its own dotenv configuration. The 22 remaining direct `MongoClient`
  constructors are currently classified as Phase C read/inspection tools.

Phase B is **not yet complete**. A second inventory found 53 retained legacy scripts
that write through module-level collections imported from `BackEnd.db`. Those scripts
benefit from the hardened application resolver, but they still do not declare target
and write intent at their own CLI boundary. They remain queued for migration or
deployment-evidence retirement; they are not counted as complete merely because their
client is indirect.

#### Indirect-writer disposition audit — 2026-08-11

This was a code-and-documentation audit only. No database was contacted and no script
was deleted. The scan initially reported 53 files; `season_advance_harness.py` was a
known migrated false positive because it intentionally calls application routes after
its shared preflight. The remaining 52 divide as follows.

| Disposition | Scripts | Evidence and recommendation |
|---|---|---|
| **Retain and migrate now — operational** | `eog_measurement_season.py`, `s11_league_convergence_audit.py`, `verify_deploy.py`, `generate_alpha_otps.py`, `loader.py` | These are active measurement, deployment, OTP, or shared-loader capabilities. `loader.py` has 13 repository consumers. They need explicit target/access boundaries; they are not retirement candidates. The EOG and S11 tools also need their independent env parsing removed. |
| **Retain and migrate — production work is documented as pending** | `add_man_tight_loose_defenses.py` | `O_&_D_Plays_Collections.md` explicitly says staging is complete and production is pending. Retiring it would strand known work. Prefer folding it into one defense publisher/seeder before production execution. |
| **Retain pending deployment verification** | `migrate_to_ftd.py`, `migrate_add_user_id_to_franchises_tournaments.py`, `recruit_sets/bake_home_region.py`, `recruit_sets/normalize_recruit_years.py` | These have current or archived documentation references, but the repository cannot prove which live databases received them. Migrate their safety boundary until deployment state is verified. |
| **Consolidate defense seeders** | `init_defenses_collection.py`, `add_131_zone_defense.py`, `add_32_zone_defense.py`, `add_base_man_defense.py`, `restore_23_zone_defense.py`, plus the retained `add_man_tight_loose_defenses.py` | These overlap on the same universal collection and can overwrite or partially seed different generations of the schema. Replace them with one explicit-target, additive, idempotent defense publisher. Retire the individual scripts only after exact staging/production verification. |
| **Consolidate player/team maintenance** | `add_player_photos_to_db.py`, `add_player_position_ratings.py`, `add_team_colors.py`, `update_player_attributes_from_production.py`, `update_player_attributes_from_staging.py`, `update_player_height_weight.py`, `update_player_ids_from_players.py`, `update_staging_position_ratings.py`, `migrate_players.py` | These are overlapping content repair/import paths. Position ratings are also normally persisted by application code. Preserve any still-needed source transforms behind one explicit-target maintenance command; do not keep nine independent ambient-target writers. |
| **Consolidate recruit-set loading** | `recruit_sets/load_recruit_sets.py` plus the retained bake/normalize scripts | Loading, year normalization, and home-region baking are stages of one dataset publication workflow. Consolidate into a dry-run/validate/publish command, while preserving the currently pending transformations until deployment is verified. |
| **Deployment-evidence retirement candidates — play/skeleton migrations** | `cleanup_successful_versions.py`, `convert_motion_base_loop_to_versions.py`, `copy_successful_to_variants.py`, `create_fcp_hct_opposite_versions.py`, `create_motion_opposite_versions.py`, `create_opposite_skeletons.py`, `create_successful_versions.py`, `migrate_fcp_hct_to_version_structure.py`, `migrate_play_skeletons.py`, `migrate_play_stats_structure.py`, `migrate_plays_to_versions.py`, `migrate_skeleton_name_fields.py`, `migrate_to_reference_based_plays.py`, `rename_staging_plays_from_summary.py`, `clean_universal_plays.py` | These encode successive historical representations and several intentionally rewrite the same nested skeleton structures. No current documentation calls them an ongoing operational path. Recommended retirement after an exact schema/content verification proves both live targets already reflect the final representation. Until then, migrate rather than execute ambiently. |
| **Deployment-evidence retirement candidates — additive/removal backfills** | `add_coaching_field_to_teams.py`, `add_effectiveness_cloaking_fields.py`, `add_momentum_field_to_plays_defenses.py`, `add_player_stats_to_tournaments_and_franchises.py`, `cleanup_legacy_team_keys.py`, `migrate_foul_turnover_to_aggression_discipline.py`, `migrate_tempo_to_fast_breaks.py`, `remove_redundant_team_fields.py`, `remove_team_attributes.py`, `update_team_strategy_settings.py`, `update_teams_PFPA.py` | These are one-time schema transitions. Most have no dry-run and no external reference proving live deployment. Recommended retirement only after field-level production and staging checks; otherwise retain temporarily behind the shared boundary. |

Audit conclusions:

1. **No immediate deletions are justified by repository evidence alone.** Git age and an
   idempotent implementation do not prove a migration ran on both databases.
2. **Five operational tools can be migrated without another product decision.** The
   defense, player/team, and recruit-set families should be consolidated rather than
   mechanically migrating every duplicate.
3. **Thirty historical migration/backfill scripts require deployment evidence
   before retirement.** The safe evidence is a read-only, field/schema-specific audit
   of both `gob-staging` and `gob`; code history is insufficient.
4. **Current danger is real even after the application resolver hardening.** Forty-two
   of the 52 scripts expose no dry-run/apply flag, and four force `MONGO_DB_NAME` in
   process. Their next execution could still perform immediate bulk writes to the
   selected target.

Operational migration completed 2026-08-11:

- `generate_alpha_otps.py` now requires one explicit database. Listing/statistics are
  read-only; generating is dry-run by default and requires `--apply` to insert.
- `loader.py` no longer writes during module import. It is now an explicit-target,
  dry-run-by-default CLI and exposes a side-effect-controlled `load_teams` function.
- `eog_measurement_season.py` now requires `--db gob-staging --apply` and completes the
  shared staging-write preflight before importing application routes.
- `s11_league_convergence_audit.py` no longer reads `.env` or `.env.local`. It requires
  the exact scratch database name, `--confirm-db`, and `--apply`; the production-cluster
  scratch boundary validates the process-supplied production identity before the URI is
  retargeted to the non-live scratch database for application-route execution.
- `verify_deploy.py` keeps health verification database-free. Data/seeding checks require
  `--db gob`; they use a shared production read connection unless `--delete` explicitly
  requests write access for throwaway cleanup.

All five compile, the 26 focused environment/database tests pass, and no live database
was contacted. Defense consolidation tracing confirms universal defense documents are
catalog templates: game/season counters are copied into per-team scouting state and
updated there. Even so, the existing man-defense migration deliberately preserves any
catalog counters on update. The consolidated publisher must therefore use additive
upserts keyed by stable `defense_id`, with `game_stats`/`season_stats` set only on insert,
not a whole-collection replacement.

Consolidation progress:

- Added `scripts/publish_defenses.py`. It reads the staging catalog and additively
  upserts production by stable `defense_id`. Definition fields synchronize, while
  existing production `game_stats` and `season_stats` are preserved and those fields
  are initialized only for newly inserted defenses. Apply requires production write
  authorization, exact database confirmation, and an external `0600` backup. A
  mongomock regression test proves dry-run immutability and counter preservation.
- The six historical defense seeders remain temporarily because staging/production
  content has not yet been read and verified. They are superseded for future
  staging-to-production publication, but are not deleted on inference alone.
- Consolidated the recruit-set preparation path into
  `scripts/recruit_sets/load_recruit_sets.py`: one explicit target, dry-run default,
  optional year normalization, optional deterministic Home Region baking, validation,
  shrink protection, and publication. The standalone bake/normalize tools were also
  migrated to explicit targets while deployment verification remains outstanding.
- After this work, the mechanical indirect-writer scan falls from 52 to 46. Three of
  those are intentional application-route harnesses (`eog_measurement_season.py`,
  `s11_league_convergence_audit.py`, and `season_advance_harness.py`) that now preflight
  explicitly; six are superseded defense seeders awaiting evidence-based retirement.

Player/team maintenance consolidation completed 2026-08-11:

- Added `scripts/maintain_universal_roster.py`, one explicit-target, dry-run-first
  command for photos, ratings, roster IDs, measurements, legacy attribute profiles,
  legacy colors, and explicit-file catalog replacement.
- Destructive replacement requires `--apply`, the shared destructive-operation guard,
  exact production confirmation when applicable, and a timestamped external backup.
  Input JSON files must be named explicitly; the old broad glob behavior, which could
  mix staging and production variants, is retired.
- The nine overlapping player/team scripts now remain only as compatibility wrappers
  over the consolidated implementation. They no longer select an ambient target or
  maintain independent database behavior.
- The mechanical indirect-writer inventory consequently falls from 46 to 37. The
  remaining set consists primarily of historical schema migrations, superseded
  defense seeders, and the explicitly preflighted application-route harnesses.

Deployment-evidence audit added 2026-08-11:

- Added `scripts/audit_legacy_migrations.py`. It accepts exactly one explicit target,
  obtains an enforced read-only shared connection, and reports migration evidence as
  `PASS`, `FAIL`, `OBSOLETE`, or `UNKNOWN`. A regression test verifies that the audit
  cannot mutate its target.
- The staging run contacted `gob-staging` read-only. It made no database writes.
- Staging passes the canonical defense-ID set; play effectiveness/cloaking/momentum;
  defense effectiveness/cloaking; removal of legacy team tempo; player IDs, photos,
  and position ratings; team roster references; recruit years and Home Region; and
  franchise/tournament ownership fields.
- Two of six canonical staging defenses lack `momentum`. Code tracing identifies the
  current tight/loose man seed path as the likely source because it initializes
  effectiveness and cloaking but not momentum. This is a real catalog gap, not an env
  migration action, and has not been changed during this work.
- Universal-team `coaching`, universal-team `strategy_settings`, and stored zero PF/PA
  backfills are classified `OBSOLETE`, not failed. Current ownership puts coaching on
  users/FTD, strategy settings on FTD/tournament/game state, and standings PF/PA are
  computed from games with universal fields only an optional zero fallback. The old
  scripts should not be run merely to satisfy historical schemas.
- The FTD schema audit finds 264 malformed documents among 12,296, grouped under three
  franchise IDs. All three groups are orphaned and no active franchise group fails.
  Active staging franchise data is therefore canonical; deleting orphan documents is
  a separate data-retention decision and was not performed.
- Successive nested play/skeleton history rewrites remain `UNKNOWN`: their final state
  cannot be proven safely from field presence alone. They require an exact expected
  schema/content audit before retirement.
- Production was verified read-only on 2026-08-11 using process-supplied credentials
  and `GOB_DB_ACCESS=read`; no production credential was stored in or loaded from the
  repository. Production matches staging on every common catalog/ownership invariant,
  except that the same two of six defenses lack `momentum`. Production player catalog,
  team roster references, recruit years/Home Region, and ownership fields all pass.
  Production FTD is fully canonical (`0/6248` malformed), while nested procedural
  play/skeleton history remains `UNKNOWN` pending a migration-specific comparison.

Evidence-based disposition after the staging run:

- Player catalog, recruit normalization/Home Region, and ownership migrations have
  evidence of completion in both live targets. Their historical scripts may now be
  retired individually once no unrelated transformation remains in a given file.

Phase B evidence-based retirement and defense repair preparation:

- Removed `add_coaching_field_to_teams.py`, `update_team_strategy_settings.py`, and
  `update_teams_PFPA.py`. Both live-target audits and current ownership tracing prove
  these are obsolete architectural backfills, not pending work.
- Removed the six superseded defense seeders: `init_defenses_collection.py`,
  `add_131_zone_defense.py`, `add_32_zone_defense.py`, `add_base_man_defense.py`,
  `restore_23_zone_defense.py`, and `add_man_tight_loose_defenses.py`. Both targets
  already contain all six canonical IDs, and `publish_defenses.py` is now the single
  maintained publication path.
- Extended `publish_defenses.py` with `--repair-missing-baselines`. It targets exactly
  one database, is dry-run by default, adds only absent effectiveness/momentum/cloaking
  fields with documented zero baselines, preserves existing values and catalog
  counters, and requires explicit write authorization plus an external backup on
  apply. This replaces the only unresolved maintenance need from the retired seeders.
- The repair dry-run reported exactly two affected staging documents and only the
  `momentum` field. After review, staging was repaired with `momentum: 0` on those two
  documents. The command first wrote a `0600` recovery backup under the external
  `/Users/jamesdavies/gob-db-backups` root. The subsequent enforced read-only staging
  audit reports `0/6` missing effectiveness, momentum, or cloaking fields. Production
  was then dry-run, backed up externally, repaired through the same one-target path,
  and re-audited with process-only `GOB_DB_ACCESS=read`. It likewise reports `0/6`
  missing effectiveness, momentum, or cloaking fields; production FTD remains fully
  canonical (`0/6248` malformed).
- Removed four additional completed one-time migrations after both live-target audits:
  `add_effectiveness_cloaking_fields.py`, `migrate_tempo_to_fast_breaks.py`,
  `migrate_add_user_id_to_franchises_tournaments.py`, and `migrate_to_ftd.py`.
  Effectiveness/cloaking, tempo removal, ownership, and active FTD shape are verified
  on both targets. Staging's malformed FTD documents belong only to orphan franchise
  IDs and are a retention cleanup, not an active-schema migration.
- Security documentation now points to the read-only evidence audit instead of the
  retired ownership writer.
- Removed `add_momentum_field_to_plays_defenses.py` after the consolidated repair and
  read-only audits proved all play and defense baselines complete on both live targets.

Play/skeleton migration audit and staging cleanup:

- Added `scripts/audit_play_skeleton_migrations.py`, an explicit-target enforced
  read-only inventory of universal play variants, motion loops, FCP/HCT versions,
  legacy naming fields, archived play renames, and forbidden universal stats fields.
- Staging contains 23 plays (4 motion, 19 set). All motion base loops and all four
  variants of every set play use valid, uniquely labeled version arrays. Every set
  play has `successful`, `mid_play_change`, `contested`, and `broken`; successful is
  consistently `v0,v1`. No legacy `standard` skeleton remains.
- Staging FCP and HCT each contain one named document with `base` and `shot` variants;
  every variant uses valid labeled version arrays. No FCP `field` key or missing name
  remains. All 18 actual archived play renames are complete.
- The audit found 11 universal staging plays still carrying root `game_stats` and
  `season_stats`. This contradicted the current collection contract and the current
  play-write API, which strips those fields. Team-owned play copies remain the owner
  of mutable game and season statistics.
- Added `scripts/maintain_play_catalog.py`, a one-target, dry-run-first replacement for
  the ambient `clean_universal_plays.py`. It removes only those two root fields,
  requires an external backup on apply, and preserves every other play field.
- The staging dry run reported exactly 11 affected documents. After review, the
  cleanup wrote a full external `0600` plays backup and removed those fields. The
  subsequent read-only audit reports zero root `game_stats` and `season_stats`, with
  every skeleton and rename invariant unchanged.
- Removed the superseded `clean_universal_plays.py`. Production subsequently produced
  the same structural audit and the same exact 11-document cleanup plan. It was backed
  up externally, cleaned through the explicit production-write boundary, and re-audited:
  both root stats counts are zero and every version/name/rename invariant still matches
  staging.
- Retired the completed historical structure sequence:
  `cleanup_successful_versions.py`, `convert_motion_base_loop_to_versions.py`,
  `copy_successful_to_variants.py`, `create_fcp_hct_opposite_versions.py`,
  `create_motion_opposite_versions.py`, `create_opposite_skeletons.py`,
  `create_successful_versions.py`, `migrate_fcp_hct_to_version_structure.py`,
  `migrate_play_skeletons.py`, `migrate_plays_to_versions.py`,
  `migrate_skeleton_name_fields.py`, and `rename_staging_plays_from_summary.py`.
  Their final structural and rename invariants are present in both live targets; reruns
  could duplicate versions or rewrite current authored skeletons.
- Retired `migrate_play_stats_structure.py` and
  `migrate_to_reference_based_plays.py`. They target the former embedded
  franchise/tournament team architecture, superseded by FTD. The latter would also
  clear persisted game turns, directly contradicting current save/resume behavior.
  These are obsolete transformations, not operational maintenance tools.
- Retired the final five indirect historical writers after tracing their current
  ownership and behavior:
  `add_player_stats_to_tournaments_and_franchises.py` reset live aggregate claims and
  targeted the retired franchise-owned player map; current franchise stats live in
  FPD and tournament initialization owns its current `players` map.
  `migrate_foul_turnover_to_aggression_discipline.py` and `remove_team_attributes.py`
  targeted retired embedded franchise teams, used mutually inconsistent fight versus
  aggression paths, and the latter randomized universal values on every run.
  `remove_redundant_team_fields.py` targeted obsolete duplicate home/away blobs while
  current games intentionally keep their complete state under `teams.{team_id}`.
  `cleanup_legacy_team_keys.py` inferred IDs only from uppercase strings containing an
  underscore, which is invalid for current canonical IDs such as `XAVIEN` and could
  delete the wrong compatibility row. Current game creation and key resolution own
  canonicalization instead.
- After those retirements, no unguarded historical database writer remains. The only
  mechanical indirect-writer matches are three explicitly preflighted simulation
  harnesses plus `sim_verify/p2_rng_audit.py`; the latter is a read-only Phase C tool
  and matched only because its commentary mentions `bulk_write`.

**Phase B status: COMPLETE (2026-08-11).** Ordinary maintenance writers now use the
shared explicit-target boundary, overlapping workflows are consolidated, and retained
simulation writers preflight their target and write intent before importing
application routes. Deployment evidence from both live targets supported retirement
of the historical ambient writers. The remaining database-aware inspection/reporting
tools belong to Phase C.

### Phase C — Read-only tools

**Status: COMPLETE — implemented 2026-08-11.** Database-aware inspection, export,
measurement, and reporting scripts now use the shared explicit-target boundary or were
retired with evidence. The final scan also corrected two hidden application-DB import
paths and found no remaining independent Mongo client or database dotenv loader under
`scripts/`.

- audits and reports;
- measurement/export scripts;
- inspection and count scripts.

Read-only classification must be based on traced code, not a script name. Constructors
and imported modules may write.

#### Phase C progress — 2026-08-11

First batch migrated to the shared enforced read-only boundary:

- `count_players_by_year.py`;
- `report_gob_staging_players_by_year.py`;
- `report_gob_staging_recruit_set_years.py`;
- `review_staging_players_collection.py`;
- `inspect_franchise_roster_counts.py`.

These tools no longer parse `.env`/`.env.local`, construct `MongoClient`, change the
working directory, default silently to a live database, or accept an unchecked
positional database name. Each requires `--db gob-staging|gob`; production therefore
requires process-level `GOB_DB_ACCESS=read`. Representative staging executions passed
through the read-only proxy. The player-year report accounted for all 1,536 records,
and the franchise roster tool listed current staging franchises without mutation.

Second batch migrated:

- `export_play_skeletons.py`;
- `inspect_plays_structure.py`;
- `pull_zone_areas.py`;
- `check_duplicate_final_steps.py`.

Their Mongo access is now explicit and enforced read-only. Export destinations remain
ordinary local-file outputs and are not database writes. Across the two batches,
direct `MongoClient` consumers under `scripts/` fell from 24 to 15, and independent
`load_dotenv`/`dotenv_values` consumers fell from 11 to 7. All migrated CLIs compile,
their help/preflight parsing succeeds, and `git diff --check` passes.

Third batch migrated the current FCP/HCT/play inspection family:

- `check_opp_fields_in_skeletons.py`;
- `dump_fcp_hct_skeletons.py`;
- `list_c_midlane_shoot_set_plays.py`;
- `verify_skeleton_versions.py`.

All now require an explicit target and use the enforced read-only proxy. A staging
version report successfully inspected all 23 canonical plays. Four motion plays
correctly use `base_loop`; all 19 set plays reported their current version arrays.

The same trace identified and retired historical diagnostics rather than preserving
misleading output:

- `analyze_fcp_hct_hco_pg_opp.py` imported the full simulation engine, initializing an
  ambient application database before a protected CLI connection could be established;
  its narrower data inspection is covered by the retained opp-field tool.
- `debug_play_skeleton.py`, `validate_all_skeletons.py`, and
  `verify_play_variants.py` only understood the retired direct-steps play schema and
  would report current versioned variants as empty.
- `test_skeleton_selection.py` was a manual engine script with ambient database import,
  not an isolated test.
- `check_steal_skeletons.py` and `analyze_hco_pg_opp_issue.py` targeted the former
  `steal`/`hco` FCP/HCT variants. Current canonical documents expose `base` and `shot`;
  staging verification confirmed those historical variants do not exist.

After batch three and these evidence-based retirements, direct `MongoClient` consumers
fell to 11 and independent dotenv-library consumers to 4.

Fourth batch migrated the player/team attribute reporting family:

- `analyze_player_attrs_by_team.py`;
- `analyze_team_attribute_totals.py`;
- `audit_position_rating_sanity.py`;
- `update_total_team_attrs_doc.py`;
- `team_attr_season_dry_run.py`.

The duplicate mixed-source `total_team_attrs_report.py` was retired; the retained
reports use one explicitly selected database as their authority. The historical
`s11_authorship_drift_audit.py` was also retired: it measures the superseded offseason
shape-attractor model and its Team Builder import chain initialized the ambient
application database before a protected script connection could be established.

This batch also removed an import-time database side effect from `BackEnd.utils`.
Package-level stat-updater exports are now lazy, so importing a pure helper such as
`position_ratings` no longer imports `BackEnd.db`; the existing package API remains
available. A live staging position audit passed through the read-only boundary and
produced 1,536 roster rows plus 300 recruit rows. A one-week team-attribute dry run
also completed against staging. That harness invokes the production training engine,
which still initializes its application database client through a deeper model import,
but only after the explicit script preflight has validated the requested target and
access. It did not perform a database write.

After batch four, static `MongoClient` hits fell to five, of which one is explanatory
text in the already-preflighted `season_advance_harness.py`; four genuine direct-client
tools remain. Independent dotenv-library consumers fell to three.

Fifth batch removed those final four genuine direct-client paths:

- `export_players_for_portraits.py` now requires an explicit database and supports an
  explicit collection and output directory;
- `export_staging_unused_otps.py` is constrained to an explicit `gob-staging` target;
- `rename_player_images_by_mongo_id.py` reads names through the shared boundary while
  retaining dry-run-by-default local file renaming;
- `sync_fcp_hct_fallbacks_from_db.py` now generates fallback modules from one explicit
  source database per invocation instead of silently reading production and staging
  through one ambient credential.

No script under `scripts/` now constructs `MongoClient` directly. The sole static text
match is an explanatory comment in `season_advance_harness.py`.

A final independent-environment scan found two application-DB imports that direct-
client searches could not detect. `eog_db_sweep.py capture` now requires an explicit
target and uses the read-only proxy; its offline `compare` command remains database-
free. `send_user_reengagement_email.py` no longer loads dotenv or changes
`MONGO_DB_NAME`. Dry runs establish read access and actual sends establish write access
through the shared boundary. Email-suppression helpers now accept an injected database
for the maintenance command while lazily preserving normal application behavior.

The sole remaining dotenv-library consumer is `fetch_sentry_issue.py`, a database-free
external Sentry API tool. It belongs to script-only secret cleanup rather than the
database boundary.

### Migration procedure per script

1. State intended target(s) and access mode in the module docstring/help.
2. Replace local dotenv loading with the shared resolver.
3. Replace direct `MongoClient` construction.
4. Add explicit CLI target selection where ambiguity exists.
5. Add target/mode preflight output.
6. Add or update a test for refusal and correct target resolution.
7. Run only against a safe scratch or staging target during verification.

### Acceptance criteria

- No production-capable script retains an independent dotenv loader.
- No migrated script can silently switch targets because of CWD or missing files.
- All database writers declare write intent explicitly.

## Task 7 — Add Tests and Static Enforcement

**Status: COMPLETE — implemented 2026-08-11.** Runtime policy coverage and a
rule-specific repository scanner now run in CI. All safety tests use mongomock or pure
configuration resolution; none connects to a live database.

### Runtime tests

Cover at minimum:

1. Missing local `.env.local` fails loudly.
2. Local startup never reads `.env`.
3. URI database and `MONGO_DB_NAME` mismatch fails.
4. Requested CLI target mismatch fails.
5. Production without process-level authorization fails.
6. `GOB_DB_ACCESS=read` permits reads and blocks every supported write form.
7. `GOB_DB_ACCESS=write` is required for intended production writes.
8. Tests refuse `gob` and `gob-staging`.
9. A configured real Mongo failure does not silently select mongomock.
10. Railway-injected staging and production configurations resolve correctly without
    local files.

### Static checks

Add a CI check that rejects new instances outside approved modules of:

- `load_dotenv()`;
- manual `.env` parsing;
- direct `MongoClient(...)`;
- references to `.env.production`;
- `.env.local` → `.env` fallback loops;
- production URI literals;
- assignments of `GOB_DB_ACCESS` from a file.

Use a short explicit exception list for unavoidable tooling. Exceptions must be named
and reviewed rather than expressed as a permissive pattern.

### Acceptance criteria

- Unsafe patterns fail CI.
- The existing pytest database block-list remains active.
- Safety tests run using mongomock or a uniquely named disposable database.

**Acceptance result:** satisfied.

- Runtime tests cover missing local configuration, refusal to fall back to `.env`, URI
  and requested-target disagreement, production read/write authorization, explicit
  mongomock selection, live-database refusal in tests, invalid real-Mongo failure, and
  Railway staging and production process configuration.
- Read-only proxy tests enumerate every declared collection, database, and client
  mutator and separately cover aggregation `$out`/`$merge` and database commands.
- The application production-read proxy was brought to the same standard: the raw
  client is no longer exposed in read mode, and client/database/command/aggregation
  write surfaces are blocked in addition to collection methods.
- Added `scripts/check_env_safety.py` and a dedicated GitHub Actions step. It scans
  production source and operational scripts for dotenv loaders, manual dotenv parsing,
  direct Mongo clients, production dotenv references, local-to-generic fallback loops,
  production URI literals, and file-supplied database authorization.
- Exceptions are path- and rule-specific: the two environment boundaries may use
  `dotenv_values`, the application/shared boundaries may construct Mongo clients, and
  the database-free Sentry helper may load its external-service token pending the
  script-secret task. The two database boundaries are separately allowed to mention
  file-supplied authorization because their implementation rejects it and runtime tests
  enforce that rejection.
- Static enforcement exposed and removed lingering dotenv parsing from four Gemini
  image tools and the R2 walk-on portrait publisher. Those tools now require secrets in
  the invoking process. It also found `merge_gob_players_into_tsv.py`; that tool now
  requires an explicit database target and uses the shared read-only boundary.
- The scanner has positive repository coverage plus negative fixture tests proving each
  unsafe rule fails.

## Task 8 — Move Backup Configuration Outside the Repository

**Status: COMPLETE — local workflow retired 2026-08-11.** MongoDB Atlas Cloud Backup is
the backup authority for `MVP-Cluster`. Atlas showed 37 current snapshots, automated
hourly and daily capture, seven-day retention, and point-in-time restore. This evidence
superseded the disabled local `mongodump`/Google Drive workflow.

### Work

1. Choose an external path such as `~/.config/gob/backup.env` or a platform secret
   store.
2. Set file permissions to `0600`.
3. Update `scripts/backup-mongodb.sh` and its scheduler/launchd configuration to require
   that explicit path.
4. Make a missing backup configuration fail loudly.
5. Validate the backup target before invoking `mongodump`.
6. Confirm backup output and restore documentation without printing credentials.
7. Remove the repository-local `.env.backup` only after a successful external-config
   backup run.

### Acceptance criteria

- No production backup credential exists below the repository root.
- Scheduled and manual backups both use the external configuration successfully.

### Completion result

- Retired `scripts/backup-mongodb.sh`, its repository template, and the obsolete
  launchd/Google Drive runbook.
- Removed the ignored repository credential and the temporary external credential at
  `~/.config/gob/backup.env`; neither is needed by Atlas-managed backups.
- Removed local dump/archive/log ignore rules that existed only for the retired job.
- No launchd job was installed, so no scheduler unload was required.
- Atlas retention is currently seven days. Extending weekly/monthly retention remains
  an optional operational decision, not a prerequisite for retiring Google Drive.

## Task 9 — Remove Redundant Files After Consumer Migration

**Status: COMPLETE — implemented 2026-08-11.** Consumer tracing found and removed the
last indirect root `.env` reads before deletion. The repository now retains only the
sanitized application template `.env.example` and the ignored staging-only
`.env.local`; the latter is mode `0600`.

This task must happen late. Removing files early could cause another silent fallback in
an unmigrated script.

### Work

1. Confirm no active code reads `.env` or `.env.production`.
2. Confirm backup tooling no longer reads repository `.env.backup`.
3. Delete local `.env`.
4. Delete local `.env.production`.
5. Delete local `.env.backup` after external backup verification.
6. Confirm the Task 3 retirement of `.env.railway.example` remains complete.
7. Confirm `.env.backup.example` remains placeholder-only or retire it with the old
   repository backup workflow.
8. Retain `.env.local` as ignored staging-only local configuration.
9. Retain `.env.example` as the single tracked application template.
10. Ensure all retained secret files are mode `0600`.

### Acceptance criteria

- Repository directory contains no production credentials.
- The only application env files are `.env.example` and ignored `.env.local`.
- Git status and ignore rules match the intended policy.

**Acceptance result:** satisfied.

- Removed ignored `.env` and `.env.production` only after confirming no application,
  database script, or tooling consumer remained.
- Recruit-set image builders no longer call the retired portrait-generator `load_env`
  helper; Gemini credentials must be supplied in the invoking process.
- The Sentry helper no longer reads generic dotenv. Its API token must be supplied in
  the invoking process, allowing the final generic `.env` file to be retired.
- Task 8 removed `.env.backup`, its external copy, and the obsolete backup template.
  The previously retired Railway template remains deleted.
- `.env.local` remains ignored, staging-only, and mode `0600`. `.env.example` remains
  the sole sanitized application template.
- The script-only R2 credential was subsequently moved outside the repository by Task
  10; no live script secret remains under the worktree.
- Ignore rules for `.env`, `.env.production`, and related secret filenames remain as
  defense in depth even though those files are absent.

## Task 10 — Update Operational Documentation

**Status: COMPLETE — implemented 2026-08-11.** Operational guidance now matches the
hardened loaders and Atlas-managed backup model. The remaining repository-local R2
secret was moved to `~/.config/gob/r2.env` at mode `0600`, and all local R2 consumers
use one reviewed external-secret boundary.

Document:

- first-time local setup;
- staging-only `.env.local` requirements;
- Railway staging variables;
- Railway production variables;
- test and scratch-database invocation;
- read-only production diagnostics;
- deliberate production migrations;
- destructive-operation confirmation;
- backup configuration and restore procedure;
- script-only secrets;
- secret rotation and accidental-access response.

Update existing database documentation that currently states `.env.local` falls back to
`.env` or that missing Mongo configuration automatically uses mongomock.

### Acceptance criteria

- Documentation describes the implemented behavior, not the old loader.
- Common commands can be copied without embedding production credentials.

**Acceptance result:** satisfied.

- Added `00_Operations/Environment_Operations.md` covering first-time local setup,
  Railway staging/production identities, mongomock and scratch use, staging writers,
  production read/write commands, destructive confirmation, Atlas restore posture,
  script secrets, rotation, accidental access, and accidental database writes.
- Production command examples reference a temporary password-manager-derived shell
  variable and never embed a URI or credential.
- Added `scripts/script_secrets.py`: complete process R2 credentials win; otherwise it
  reads only external `~/.config/gob/r2.env`, rejecting symlinks, repository paths,
  unsafe permissions, placeholders, and partial process configuration.
- Migrated league/recruit uploaders, R2 inspection, retired-mover archival, and walk-on
  portrait publication to that boundary. Removed `scripts/.r2.env` after validating the
  external copy at mode `0600` without printing its values.
- The static scanner now has one narrow reviewed manual-parser exception for the shared
  external-secret module; former per-tool exceptions were removed.
- Gemini and Sentry tools use process-only credentials. Railway runtime R2 access stays
  process-injected and does not read the local external file.
- Updated the variable catalog, database system, security baseline, player-image
  runbook, and completed image-migration note.

## Task 11 — Final End-to-End Validation

Run the following as separate, observable checks:

1. Local app starts against `gob-staging` using repo-root `.env.local`.
2. Local app fails when `.env.local` is expected but absent.
3. Running from a scratch directory resolves the same repo-root policy.
4. Tests run against mongomock or `gob-test` and reject staging/production.
5. Railway staging reports `gob-staging` and expected environment identity.
6. Railway production reports `gob` and expected environment identity without a local
   file.
7. A read-only staging audit succeeds.
8. A staging writer succeeds only with explicit write intent.
9. A production read succeeds only with `GOB_DB_ACCESS=read`.
10. A production write is blocked in read mode.
11. A deliberately authorized production write reaches preflight but is tested with a
    harmless or no-op operation.
12. Backup runs from external configuration.
13. Repository and Git-history scans identify no current live credentials.
14. Static CI checks reject a sample unsafe dotenv loader and direct Mongo client.

### Validation results — 2026-08-11

| # | Result | Evidence |
|---|---|---|
| 1 | **PASS** | A real local Uvicorn startup reported the repo-root `.env.local`, `environment=development`, `database=gob-staging`, and `mode=mongo`; `GET /health` returned HTTP 200. |
| 2 | **PASS** | `tests/test_env_config.py::test_missing_local_env_fails_without_dotenv_fallback` verifies that an absent `.env.local` fails even when a legacy `.env` exists. |
| 3 | **PASS** | Resolving from `/private/tmp` still selected `/Users/jamesdavies/gob-simplified/.env.local` and `gob-staging`. |
| 4 | **PASS** | The focused environment suite uses mongomock/test identities and rejects live targets. The complete 39-test environment/security selection passed. |
| 5 | **PENDING LIVE LOG CONFIRMATION** | The public staging `/health` endpoint is healthy and reports commit `26fa4f22b006`, but the public payload intentionally does not expose database identity. Confirm the deployed startup log contains `environment=staging database=gob-staging ... source=railway-process`. Resolver tests already cover this exact Railway input. |
| 6 | **PENDING LIVE LOG CONFIRMATION** | Both the production custom domain and current Railway production domain return healthy responses, but that deployed health payload predates identity fields and exposes neither environment nor database. Confirm the deployed startup log contains `environment=production database=gob ... source=railway-process`. Resolver tests cover this exact Railway input without a local file. |
| 7 | **PASS** | `scripts/audit_legacy_migrations.py --db gob-staging` connected with read access and completed. A guarded follow-up removed three verified orphan franchise sidecar groups (264 FTD, 1,538 FPD, and 380 FRD documents; 2,182 total). The post-cleanup audit reports `malformed=0`, `active_groups=0`, and `orphan_groups=0`. |
| 8 | **PASS** | An explicit `access=write` staging connection printed its safe preflight and completed a non-mutating Mongo `ping`. Earlier Phase B staging repairs also exercised real writes through this boundary. |
| 9 | **PASS** | The operator ran the production migration audit with process-only `GOB_DB_ACCESS=read`; its preflight reported `environment=production database=gob access=read` and completed successfully. |
| 10 | **PASS** | Runtime proxy tests verify that read mode blocks every declared collection, database, and client mutator, including commands, `$out`, and `$merge`. The production authorization test also rejects write access when only read is granted. |
| 11 | **PASS** | Production write authorization and safe preflight are covered with an injected mongomock client, and the earlier deliberately authorized production defense repair exercised the real boundary. No additional production mutation was performed merely for validation. |
| 12 | **PASS — UPDATED WORKFLOW** | The local/Google Drive backup workflow was deliberately retired. Atlas Cloud Backup is active on `MVP-Cluster`: 37 observed snapshots, hourly/daily schedule, seven-day retention, and point-in-time restore. Recreating an external local backup would reverse Task 8. |
| 13 | **PASS WITH HISTORICAL NOTE** | `.env.local` and the external R2 credential file are both mode `0600`; `.env.local` is ignored; no production credential is under the repository root. Five credential-shaped lines in the tracked tree are all explicit placeholders. Git history still identifies the retired `.env.backup.example` credential artifact whose password the operator confirmed was sunset; it is not a current live credential. |
| 14 | **PASS** | `scripts/check_env_safety.py` passed. Its tests prove that sample unsafe dotenv loaders and direct `MongoClient` construction are rejected. |

The focused validation command completed with **39 passed** and the standalone static
scanner passed. `git diff --check` remains part of final handoff. The only evidence
that cannot be obtained from the public deployed endpoints is the two Railway startup
log lines in items 5 and 6; public health responses confirm availability but do not
identify their database targets.

The one-time staging cleanup is retained as
`scripts/cleanup_orphan_franchise_sidecars_staging.py`. Its target IDs and expected
counts are fixed; dry-run is the default, and execution requires the destructive
database confirmation boundary. Re-running it after the completed cleanup safely
refuses because the reviewed counts no longer match.

### Completion criteria

The project is complete only when:

- no production credential lives under the repository root;
- production is never a default or fallback target;
- all database-aware entry points use the shared target/access policy;
- read-only mode is enforced at the database operation boundary;
- tests and CI prevent regression;
- local, staging, production, backup, and maintenance workflows have each been verified.

## Execution Order Summary

1. Inventory variables and consumers.
2. Approve the environment policy.
3. Create sanitized templates.
4. Harden application loading.
5. Build the shared script resolver.
6. Migrate scripts in risk order.
7. Add runtime tests and CI enforcement.
8. Move backup configuration outside the repository.
9. Remove redundant env files.
10. Update operational documentation.
11. Perform end-to-end validation.

Do not delete or rename an env file until the consumer inventory shows that every active
reader has been migrated or deliberately retired.
