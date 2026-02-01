# Security Baseline

**Status:** Alpha launch baseline (January 2026)  
**Related:** `docs/To Do/0_alpha_launch_plan.md` — Phase 5.2 User Data Exposure Prevention

**Implementation status:**
- ✅ Auth required on: `POST /franchise/select-team`, `POST /tournament/start`, `POST /franchise/play-next-game`, `GET /franchise/command-center/data`, `GET /tournament/command-center/data`, `GET /api/game/{game_id}`
- ✅ `user_id` stored on new franchise and tournament documents
- ✅ Ownership helpers: `verify_franchise_owned_by_user`, `verify_tournament_owned_by_user`, `verify_game_owned_by_user`
- ✅ **Strict ownership:** Documents without `user_id` are denied (403). Run `scripts/migrate_add_user_id_to_franchises_tournaments.py` to backfill.
- ✅ Frontend: 401/403 on command-center/data triggers immediate redirect (FCC and TCC)
- ✅ Logging redaction: `BackEnd.utils.log_redact`
- ⏳ TODO: Add auth + ownership to remaining franchise/tournament/game endpoints (see lists below)

---

## 1. User Data Inventory

### 1.1 Sensitive Fields Stored

| Collection/Entity | Sensitive Fields | Notes |
|-------------------|------------------|-------|
| `users` | `email`, `password` (hashed) | Auth-only; never exposed via user-data endpoints |
| `franchises` | Season progress, results, recruits | User-owned; no PII beyond user_id |
| `tournaments` | Bracket, results, teams | User-owned; no PII beyond user_id |
| `games` | Full game state, teams, players | Linked via `franchise_id` or `tournament_id` |
| `franchise_team_data` | Strategy, playbook | Keyed by `(franchise_id, team_id)` |
| `franchise_players_data` | Player evolution | Keyed by `(franchise_id, player_id)` |
| `franchise_recruits_data` | Recruit pool | Keyed by `(franchise_id, recruit_id)` |

### 1.2 Endpoints by Category

#### Auth-Required (already)
- `GET /api/auth/me` — returns user_id, email (requires `get_current_user`)

#### User-Data Endpoints (require auth + ownership)

**Franchise:**
- `POST /franchise/select-team` — creates franchise
- `POST /franchise/play-next-game`
- `POST /franchise/save-result`
- `POST /franchise/complete-week`
- `GET /franchise/command-center/data`
- `GET /franchise/standings`
- `GET /franchise/schedule`
- `GET /franchise/leaders`
- `GET /franchise/team-stats`
- `GET /franchise/team-traits`
- `GET /franchise/team-player-stats`
- `GET /franchise/recruits`
- `GET /franchise/latest-training`
- `GET /franchise/state`
- `GET /franchise/team-data`
- `GET /franchise/roster`
- `GET /franchise/scouting-report`
- `GET /franchise/training-points`
- `POST /franchise/run-training`
- `GET /franchise/training-report`
- `POST /franchise/sim-rest-of-tournament`
- `POST /franchise/sim-championship`
- `POST /franchise/finish-season`

**Tournament:**
- `POST /tournament/start`
- `POST /tournament/simulate-round`
- `POST /tournament/save-result`
- `POST /tournament/sim-remaining`
- `GET /tournament/team-stats`
- `GET /tournament/leaders`
- `GET /tournament/command-center/data`
- `GET /tournament/state`
- `GET /tournament/team-data`
- `GET /tournament/scouting-report`
- `GET /tournament/roster`
- `POST /tournament/run-training`

**Game (linked to franchise/tournament):**
- `GET /api/game/{game_id}`
- `POST /api/simulate-quarter`
- `POST /api/simulate-turn`
- `POST /api/set-playcall-override`
- `POST /api/call-timeout`
- `POST /api/save-man-defense-matchups`
- `GET /api/game/{game_id}/lineup-for-matchups`
- `POST /api/init-game`
- `GET /api/gameplan`
- `PUT /api/gameplan`
- `GET /api/playbooks`
- `POST /api/playbooks`

**Public / Non-User-Data:**
- `GET /` — root
- `GET /health`
- `GET /app-config`
- `GET /api/auth/config`
- `POST /api/auth/signup`
- `POST /api/auth/login`
- `GET /teams` — team names (shared reference data)
- `GET /roster/{team_identifier}` — roster (shared reference)
- `GET /player/{player_id}` — player (shared reference)
- `GET /games` — list (may need auth depending on implementation)

---

## 2. Auth Enforcement

### 2.1 Pattern

- **Dependency:** `get_current_user` from `BackEnd.utils.auth`
- **Usage:** `user: dict = Depends(get_current_user)` on every user-data endpoint
- **Effect:** Unauthenticated requests return `401 Unauthorized`

### 2.2 Ownership Verification

- **Helper:** `BackEnd.utils.ownership`
  - `verify_franchise_owned_by_user(franchise_id, user_id) -> dict` — returns doc or raises 403/404
  - `verify_tournament_owned_by_user(tournament_id, user_id) -> dict` — returns doc or raises 403/404
  - `verify_game_owned_by_user(game_id, user_id) -> dict` — via franchise/tournament; returns doc or raises 403/404
- **Backward compatibility:** Documents without `user_id` (pre-migration) are allowed if authenticated; ownership cannot be verified.

---

## 3. Logging Redaction

### 3.1 Redacted Fields

- `Authorization` header
- `Cookie` (if session tokens)
- `password`, `password_hash`, `hashed_password`
- `email` (when in request bodies or error context)
- JWT tokens in URLs or bodies
- Full request/response bodies in production (use DEBUG level only)

### 3.2 Implementation

- `BackEnd.utils.log_redact.redact_sensitive(data: dict) -> dict`
- Applied before `logging.info`, `logging.warning`, `logging.error` when logging request/response/exceptions

---

## 4. Database Access

### 4.1 Hardening

- DB must not be publicly reachable; only backend application servers
- DB credentials in server-side environment variables only (never in client code)
- Rotate credentials if exposed

### 4.2 Connection

- Uses `MONGODB_URI` from environment
- No default fallback in production

---

## 5. Minimal Tests

| Test | Expected |
|------|----------|
| Unauthenticated request to user-data endpoint | `401 Unauthorized` |
| Authenticated user requests another user's franchise_id | `403 Forbidden` or `404 Not Found` |
| Authenticated user requests another user's tournament_id | `403 Forbidden` or `404 Not Found` |
| Authenticated user requests another user's game_id (via franchise/tournament) | `403 Forbidden` or `404 Not Found` |

---

## 6. Schema Changes for Ownership

### 6.1 New Fields

- `franchises.user_id` (string, optional) — set on creation when auth is present
- `tournaments.user_id` (string, optional) — set on creation when auth is present
- `games` — ownership inferred via `franchise_id` or `tournament_id`; no direct `user_id` needed

### 6.2 Migration

- New franchise/tournament documents include `user_id` when created by authenticated user
- Existing documents without `user_id` remain accessible to any authenticated user (known gap; migrate when possible)
