# Coaching Archetype System

Per-user tracking of a coach's **archetype mix** and **win/loss record**, surfaced as a badge, an explainer page, a one-time reveal, and leaderboards. Franchise-only (tournament mode sunset).

> **NOT the CPU concept.** This is the **USER's** coaching archetype — a classification of the
> human player's own behaviour, stored on the `users` doc. CPU teams have a separate, unrelated
> system called **identity** (a vision pair driving their strategy sliders), documented in
> [`06_Gameplay_Systems/CPU_Team_Identity_System.md`](../06_Gameplay_Systems/CPU_Team_Identity_System.md).
> The two share no code, no storage and no lifecycle. The naming split is deliberate:
> "archetype" = user, "identity" = CPU team.

## Implementation map

| Piece | Location |
|---|---|
| Schema + derived-field helpers (single source) | `BackEnd/utils/user_tracking.py` |
| Classifier (+ tests) | `BackEnd/utils/coaching_archetype.py`, `BackEnd/tests/test_coaching_archetype.py` |
| Per-quarter stash | `BackEnd/utils/archetype_tracking.py` ← `POST /api/simulate-quarter` |
| Commit (record + archetypes + lead) | `BackEnd/utils/user_game_commit.py` ← `finalize_game` |
| Signup defaults | `BackEnd/api/auth_routes.py` (`default_user_tracking`) |
| `/api/auth/me` surfacing (record, archetypes, lead_archetype, archetype_reveal_seen) | `BackEnd/api/auth_routes.py` |
| Reveal-seen flip | `PATCH /api/auth/archetype-reveal-seen` |
| Leaderboards (lead_archetype) | `BackEnd/api/leaderboard_routes.py`, `auth_routes.py` (`/api/auth/leaderboard`) |
| By-archetype leaderboard | `GET /api/leaderboard/by-archetype` → `FrontEnd/static/coaching-archetypes-leaderboard.html` |
| Shared badge component | `FrontEnd/static/js/shared/archetypeBadge.js` |
| Badge beside username | account modal (`authBarInit.js`) + leaderboards (`mode-select.js`) |
| Explainer page (4 groups) | `FrontEnd/static/coaching-archetypes.html` (manifest-driven) |
| First-archetype reveal | `FrontEnd/static/js/shared/archetypeReveal.js` (Franchise Command Center) |
| Icon + name + description manifest (**copy source of truth**) | `FrontEnd/static/images/archetype_icons/archetypes.json` |

## Classification

Each quarter the user plays/sims, classify their 5 active starters into exactly one archetype:

1. Total each of 11 attributes across the 5 starters — **SC, SH, ID, OD, PS, BH, RB, ST, AG, ND, IQ** (read `anchor_<ATTR>` if present, else `<ATTR>`, else 0).
2. **Top-3 set** = every attribute whose total ≥ the 3rd-highest total (so ties at the 3rd rank, and #1/#2 ties spilling past it, are included).
3. An archetype **qualifies** if its combo is satisfied by the top-3 set. Multiple qualify → pick one at random; exactly one → use it; none → `mr_unconventional`.

### Qualifiers (18 archetypes)

| Archetype | Qualifies when (in top-3 set) |
|---|---|
| Pure Offense | SC & SH |
| Pure Defense | ID & OD |
| O/D Balance | (SC\|SH) & (ID\|OD) |
| Rebounding King | RB & ST |
| The Intimidator | (ID\|OD) & ST |
| Mr. Fundamentals | ≥2 of (PS, BH, RB) |
| Outrun the Competition | ND & AG |
| Cerebral Offense | (SC\|SH) & IQ |
| Cerebral Defense | (ID\|OD) & IQ |
| Pure Athleticism | ≥2 of (ST, AG, ND) |
| Pure Discipline | (PS\|BH) & IQ |
| Offensive Athleticism | (SC\|SH) & (ST\|AG\|ND) |
| Defensive Athleticism | (ID\|OD) & (AG\|ND) |
| Offensive Fundamentals | (SC\|SH) & (BH\|PS) |
| Defensive Fundamentals | (ID\|OD) & (BH\|PS) |
| Offensive Rebounding | (SC\|SH) & RB |
| Defensive Rebounding | (ID\|OD) & RB |
| Mr. Unconventional | none of the above (fallback) |

Deliberate asymmetry: Offensive Athleticism allows ST/AG/ND; Defensive Athleticism only AG/ND.

## Tracking rules

- **Per quarter, every period counts** (Q1–Q4 + OT, simmed or played). The quarter's archetype is stashed on the game (`archetype_periods`, keyed by quarter) and folded into the user's counters at game completion.
- **Dedup** per `(game_id, quarter)` — refreshes / timeouts / foul-outs / mid-quarter subs don't double-count.
- **Commit once** at completion (idempotent via `finalize_game`'s franchise claims: `applied_games` per game `_id` and `applied_matchups` per franchise-week matchup — same guard that prevents double FPD stat rollup). Abandoned games count 0; CPU-vs-CPU games attribute to no one.
- **Win/loss** — each completed user game increments `record.wins` or `record.losses`; `total_games = wins + losses`; `win_rate = round(100 * wins / total_games)` (0 when no games).
- **lead_archetype** — denormalized highest-count key the UI reads for the badge. Tie-break = most recently incremented this game; `""` until the user has games.
- **Display** — archetype share = `archetypes.<key> / archetypes.total`.

**Persistence (load-bearing):** `archetype_periods` can be clobbered before `finalize` in the franchise save flow, so the commit falls back to the durable per-quarter breadcrumb `game.archetype_hook.<q>.dbg.result` when `archetype_periods` is empty. Don't remove the fallback.

## Schema (`users` doc)

- `record`: `wins, losses, total_games, win_rate, discount_wins, discount_losses` (int; `total_games` / `win_rate` derived, recomputed on every write).
- `archetypes`: the 18 keys (int) + `total` (sum of the 18).
- `lead_archetype` (str, `""` default), `archetype_reveal_seen` (bool, `false` default).

## Bulk-sim tracking (Sim Full Game / Sim Rest of Game)

Frontend sends `advance_method` on each `POST /api/simulate-quarter` (`play_quarter` / `sim_quarter` / `sim_full_game` / `sim_rest_of_game`). Backend sets sticky `games.bulk_sim_used = true` once `sim_full_game`/`sim_rest_of_game` is seen and preserves it thereafter. (Sim Quarter is sunset and never sets it.)

At commit, when `bulk_sim_used`:
- `record.discount_wins` / `discount_losses` increment (subset of wins/losses). Invariant: `discount_wins + discount_losses ≤ total_games`.
- **Geek Points policy** (`apply_bulk_sim_geek_points_policy`): bulk-sim games get the base award; fully-played games get **2× base**. Used by `maybe_award_franchise_win_geek_points` / `maybe_award_franchise_loss_geek_points`.

Ref: `Gameplay_Buttons_System.md`, `Geek_Points_System.md`, `bootGame.js`.

## Surfaces

- **Badge beside username** — account modal (`authBarInit.js`) + leaderboards (`mode-select.js`); reads `lead_archetype` (client fallback: highest archetype count).
- **Explainer** — `coaching-archetypes.html`, manifest-driven, 4 groups: Offense-First, Defense-First, Balanced, Specialist.
- **First-archetype reveal** — `archetypeReveal.js` fires once on the Franchise Command Center after the user's first non-tutorial game (gated by `archetype_reveal_seen`; the modal flips it via `PATCH /api/auth/archetype-reveal-seen`).
- **By-archetype leaderboard** — `coaching-archetypes-leaderboard.html` ← `GET /api/leaderboard/by-archetype` (top 5 per archetype by share); category headers show each archetype's definition on hover (from the manifest `description`).
- **Community highlight** — a coach's lead-archetype change posts an `archetype_evolution` row to the Community Highlights feed (see `../06_GMO_Supporting_Systems/Community_Highlights_System.md`).

**Archetype names and descriptions live once in `archetypes.json`** — the explainer, badges, and tooltips all read it. Edit copy there, not in this doc.

## Archetype Evolution modal (FCC)

When a coach's `lead_archetype` **changes** from a prior archetype (not first-time — that stays with the [first-archetype reveal](#surfaces)), the FCC shows a one-shot modal: badge of the new archetype + copy *"Hey Coach, you have evolved your coaching archetype to {name}."* Same layout/styles as the first-reveal modal (reuses the `.arch-reveal-*` CSS).

- **Detect** — the complete-week user-game block (`_complete_week_process_user_game_block`, reached via `/franchise/complete-week/phase-a`; the legacy `save_result` endpoint has the same hook) snapshots the lead archetype before `finalize_game` and compares after (`community_highlights.record_archetype_change_if_any`). On a change with a non-empty prior, it sets user field `archetype_evolution_pending = <new key>`. First-time establishment (empty prior) does **not** set it.
- **Surface / clear** — `archetype_evolution_pending` rides `/api/auth/me`; `PATCH /api/auth/archetype-evolution-seen` clears it.
- **Priority — lowest, skip permanently.** The FCC orchestrator runs it last (after championship moments resolve + tutorial-return alerts settle + a short delay) and passes `fccHasCompetingModal(topData)`. If **any** other FCC modal/prompt claims the visit — championship moments/summary, region-bye, big news (bracket/recruiting), cut-required, tutorial alerts, alpha feedback, first-archetype reveal — the modal is skipped. Either way (shown or skipped) the pending flag is consumed, so a given change is announced at most once.
- **Files** — `FrontEnd/static/js/shared/archetypeEvolutionModal.js` (`ArchetypeEvolutionModal.run`), `franchise-command-center.js` (`fccHasCompetingModal` + trigger), `BackEnd/api/auth_routes.py`, `BackEnd/utils/community_highlights.py`.
