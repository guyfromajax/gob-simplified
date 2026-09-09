## Franchise Delete System (**verified 2026-09-09**)

> Verified vs code: `_cascade_delete_franchise()` / `delete_franchise_by_id()` (`franchise_routes.py`), `collect_franchise_master_keys()` / `delete_master_keys()` (`player_image_routes.py`), `r2_images.delete_many()`, `confirmDeleteFranchise()` (`mode-select.js`), `showFranchiseGoneNotice()` (`franchise-command-center.js`).

## Overview

Hard delete of one franchise slot and everything hanging off it. There is no soft-archive — see `../projects/multi_franchises_brief.md` P7.

Two halves, deliberately split:
- **DB cascade** — synchronous and authoritative. A `200` means the franchise is really gone.
- **R2 portrait GC** — snapshotted before the wipe, executed on a background thread. Never blocks the response.

Primary files:
- `BackEnd/api/franchise_routes.py` — `_cascade_delete_franchise`, `delete_franchise_by_id`, `delete_current_franchise`
- `BackEnd/api/player_image_routes.py` — `collect_franchise_master_keys`, `delete_master_keys`, `delete_signed_masters_for_franchise`
- `BackEnd/services/r2_images.py` — `delete_many`
- `BackEnd/api/admin_routes.py` — admin reset (inline, synchronous GC)
- `FrontEnd/static/mode-select.js` — `confirmDeleteFranchise`
- `FrontEnd/static/franchise-command-center.js` — `fetchJSONWithStatus`, `showFranchiseGoneNotice`

## Endpoint Contract

| Endpoint | Case | Response |
|---|---|---|
| `DELETE /franchise/{franchise_id}` | Owned, exists | `200 {deleted: true, already_gone: false, count: 1, franchise_id}` |
| | **Does not exist (any user)** | `200 {deleted: false, already_gone: true, count: 0}` — **idempotent** |
| | Exists, owned by someone else *or* no `user_id` | `403` |
| | Malformed id | `400` |
| `DELETE /franchise/current` · `POST /franchise/delete-current` | Legacy, ≤1 franchise only | `409` when 2 exist. **Not** made idempotent — unchanged |

**Why idempotent.** Delete is retried in practice: a client that times out, or is refreshed mid-flight, has no way to know the server finished. Answering a completed delete with `404` reads to the user as a refusal on a franchise that is in fact gone. Ownership is still enforced first, so the `already_gone` branch is only reachable for an id that exists for nobody — it leaks nothing.

## Cascade Order

Order is load-bearing: the R2 key snapshot reads FPD, so it **must** run before FPD is wiped.

| Step | Collection | `franchise_id` type | Notes |
|---|---|---|---|
| 1 | *(snapshot only)* `franchise_players_data` | `str` | Collect `players/master/<player_id>.png` keys. No delete yet |
| 2 | `franchise_team_data` | `ObjectId` | |
| 3 | `franchise_players_data` | `str` | |
| 4 | `franchise_recruits_data` | `str` | |
| 5 | `games` | `str` | |
| 6 | `press_conference_sessions` | `$in [ObjectId, str]` | Wrapped — failure logged, does not block |
| 7 | `franchises` | `_id` | Last. Franchise doc is the existence marker |
| 8 | *(background thread)* R2 | — | Batched `DeleteObjects` on the step-1 snapshot |

All of 2–7 are index-backed (`db.py`: `ensure_ftd_index`, `ensure_fpd_index`, `ensure_frd_index`, `ensure_games_franchise_index`). The DB half is fast; it was never the slow part.

## R2 Portrait GC

| | Before | Now |
|---|---|---|
| Round trips | 2 per player (`head_object` + `delete_object`), serial | 1 `DeleteObjects` per **1000** keys |
| Placement | Inside the request | Background daemon thread (`img-gc-<fid8>`) |
| Effect on response | Minutes on a league-wide franchise | Not on the critical path |

**Which keys qualify.** FPD docs carrying `meta.image_id`. That is signed recruits **and** walk-ons promoted onto an active roster — `walk_on_roster_identity.py` stamps `meta.image_id` league-wide per franchise and paints a master for each, which is why the set is hundreds of keys, not a dozen. Safe to delete because signed/walk-on `player_id`s are fresh per-franchise uuids; original/universal players carry no `image_id`, so their shared masters are untouched. The shared uniform archive (`uniforms/...`, `recruits/uniform-cache/...`) is never touched.

**Accountability trade.** `delete_many` skips the `head_object` precheck, so it cannot report existed-vs-absent — it returns keys the bucket accepted. Use `r2_images.delete()` where that distinction is load-bearing. A killed process can strand a background batch; those objects are orphans nothing points at, which is the case the R2 orphan sweeper in `../projects/gob-asset-architecture.md` covers.

## Client Resolution

Every client path must end in a re-read from the server. The failure modes below all came from paths that assumed nothing had happened.

| Path | Behaviour |
|---|---|
| `200` / `404` on DELETE | Clear franchise-scoped localStorage (`FranchiseLS.clearAllForFranchise`), reload |
| Any other non-`2xx` | **Indeterminate, not known-failed.** Honest copy, then reload so the slot list is re-read. localStorage deliberately **not** cleared |
| `fetch` throws (network / user refreshed mid-delete) | Same as above — the server does not cancel with the client |
| FCC entry, `command-center/data` → `404` | `showFranchiseGoneNotice()` — full-screen panel + "Back To Home Base" |

**Why localStorage is not cleared on the indeterminate path.** `clearAllForFranchise` drops `complete_week_pending` and `eog_pgpc_snapshot`, which are week-completion resume state. Clearing them on a franchise that survived the failed delete would lose a week. Only a confirmed delete (`200`/`404`) clears.

**Why FCC needs `fetchJSONWithStatus`.** `fetchJSON` collapses every failure to `null`, and init previously did a bare `if (!topData) return;` — a deleted franchise rendered the empty shell (header `--`, every card "In Development") with no explanation. A module-level status variable would race, since init fires several un-awaited loads; the paired-return wrapper does not. `fetchJSON` delegates to it, so the ~40 existing call sites are unchanged.

## Failure Modes This Replaced

| Symptom | Cause |
|---|---|
| "Deleting franchise…" spins for minutes | Serial R2 head+delete, league-wide, inside the request |
| "Could not delete that franchise" on a franchise that *was* deleted | Client gave up (edge timeout / refresh); server finished regardless |
| Retrying the delete also failed | `404` from `verify_franchise_owned_by_user` on an already-deleted id |
| Slot card still listed after the alert | Failure path did no list refresh |
| Entering that slot → empty FCC shell | `404` swallowed by `fetchJSON`, silent `return` in init |

## Tunable Constants

| Constant | Location | Value | Effect |
|---|---|---|---|
| `chunk_size` | `r2_images.delete_many` | `1000` | Keys per `DeleteObjects` call. S3/R2 hard max is 1000 — raising it fails the request |
| `MAX_FRANCHISES_PER_USER` | `constants/multi_franchise.py` | `2` | Slot cap; `delete-current` returns `409` above 1 |
| thread name | `_cascade_delete_franchise` | `img-gc-<fid[:8]>` | Log grep handle for a stranded GC batch |
| `z-index` | `showFranchiseGoneNotice` | `1000000` | Must exceed `#page-load-overlay` (`999999`), which init's `finally` hides |

## Known Gaps

- **Not cascaded:** `training_sessions` and `eog_band_log` rows carry `franchise_id` and survive the delete. Pre-existing, diagnostic-only, out of scope for this fix.
- **Refresh paths not covered.** Only FCC *init* shows the gone-notice. `command-center/data` refetches elsewhere in `franchise-command-center.js` still fall through to `null` on a `404` — reachable only by deleting in a second tab with the FCC already open.
- **No client-side delete timeout.** Deliberate: an `AbortController` would abandon a live delete. The response is fast now, and every failure path re-reads from the server.
- `delete-current` is untouched legacy and is **not** idempotent.
