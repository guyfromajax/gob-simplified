# Tournament Execution System

**Location:** `BackEnd/tournament/bracket_engine.py`, `eos_tournament.py`, `bracket_logic.py`, `tournament_manager.py`  
**Status:** ✅ Bracket engine added; **EOS refactored** to use it. Tournament mode refactor (ObjectIds + engine) not yet done.  
**Scope:** 8-team single-elimination bracket flow for **Tournament mode** (standalone) and **Franchise EOS** (weeks 15–17).

---

## Overview

The Tournament Execution System runs the bracket lifecycle: **init** → **save result** → **advance** → **next game**. A shared **bracket engine** (`bracket_engine.py`) implements bracket generation, result recording, and round advancement. Tournament mode and Franchise EOS use the same logic; they differ only by **seeding** (random vs standings) and **persistence** (`tournaments` vs `franchise.eos_tournament`).

**Team identifiers:** All bracket logic uses **ObjectId strings** (hex). Use `ObjectId` only at DB boundaries.

---

## Shared Bracket Engine

**Module:** `BackEnd/tournament/bracket_engine.py`

### Functions

| Function | Purpose |
|----------|---------|
| `get_round_name(round_num)` | Maps 1 → `round1`, 2 → `round2`, 3 → `final`. |
| `generate_bracket(seed_order)` | Builds round-1 bracket from an ordered list of 8 ObjectId strings (seeds 1–8). Matchups: 1v8, 4v5, 2v7, 3v6. Returns `{round1, round2, final}`; round2/final start empty. |
| `save_game_result(bracket, round_num, matchup_index, game_id, winner_id, score?)` | Updates one matchup in `bracket` (game_id, winner, score). Mutates in place; no DB. |
| `advance_bracket(bracket, current_round, *, winners_from_matchups=True, results=None)` | Derives winners for the current round (from matchups or from `results`), builds the next round (0+1→semi 0, 2+3→semi 1; semis→final). Mutates `bracket`. Returns `(bracket, next_round, completed, champion)`. |

### Bracket Shape

- **Keys:** `round1`, `round2`, `final`.
- **Matchup:** `{home_team, away_team, game_id, winner, score}`. All team fields are ObjectId strings.

### Round Progression

1. **Round 1 (Quarterfinals):** 4 games → 4 winners.
2. **Round 2 (Semifinals):** 2 games (winners 0+1, 2+3) → 2 winners.
3. **Round 3 (Final):** 1 game → champion.

---

## Seeding

| Mode | Source | Output |
|------|--------|--------|
| **Tournament** | Random shuffle of 8 teams. | Ordered list of 8 ObjectId strings → `generate_bracket(seed_order)`. |
| **Franchise EOS** | Standings from `franchise.results` (W, PF–PA, tiebreaker). Top 8. | Same → `generate_bracket(seed_order)`. |

Seeding is mode-specific; bracket generation from `seed_order` is shared.

**EOS results must include week 14.** `initialize_eos_tournament` uses `franchise_doc.get("results", {})` to compute standings. When `complete_week` runs for week 14, it builds `existing_results` (weeks 1–13 + week 14) and sets `franchise_doc["results"] = existing_results` **before** calling `initialize_eos_tournament`, so seeding uses full regular-season results. Without that, EOS would seed from weeks 1–13 only.

---

## Persistence

| Mode | Storage | Load / Save |
|------|---------|-------------|
| **Tournament** | `tournaments` collection. Bracket in `bracket`, round in `current_round`, etc. | Routes load/save tournament doc; call engine; persist. |
| **Franchise EOS** | `franchise.eos_tournament` (embedded). Same shape. | Franchise routes load/save franchise doc; call engine; persist. |

The engine does not touch the DB. Callers read bracket/state → run engine → write back.

---

## Flow (Same for Both Modes)

1. **Init:** Produce `seed_order` (8 ObjectId strings). Call `generate_bracket(seed_order)` → initial `{round1, round2, final}`. Store in mode-specific doc with `current_round=1`, `completed=False`, `champion=None`.
2. **Play game:** User (or sim) plays a matchup. On completion, call `save_game_result(bracket, round_num, matchup_index, game_id, winner_id, score)`. Persist updated bracket.
3. **Advance:** After each result (or batch), call `advance_bracket(...)`. If the current round is complete, engine fills the next round and updates `current_round`. If final is complete, `completed=True`, `champion=winner`. Persist.
4. **Next game:** Determine user’s matchup from bracket + `current_round`; return it for play. Repeat until `completed`.

### EOS week transition (15 → 16 → 17)

- **`complete_week`** allows weeks 15–17 when `eos_tournament_active` and `eos_tournament` exist. No schedule lookup; user’s game only. Save result → advance from **in-memory** bracket (no reload). When the round advances, set `franchise.week = 14 + new_round` (15→16 for semis, 16→17 for final); otherwise keep `week` unchanged.
- **`/franchise/sim-rest-of-tournament`** sims incomplete matchups in the current round, saves results, then advances. When the round advances, it also sets `franchise.week = 14 + new_round` in the same `$set` as `eos_tournament`.

---

## Tests

| File | Coverage |
|------|----------|
| `tests/test_bracket_engine.py` | `get_round_name`, `generate_bracket` (shape, 1v8/4v5/2v7/3v6), `save_game_result`, `advance_bracket` (round1→2→3→completed, champion). |
| `tests/test_eos_bracket_engine_integration.py` | EOS init → save result → advance (round1→2→3→champion) using shared engine; mock teams, no DB. |

---

## Related

- **Merge plan:** `docs/To Do/tournament_eos_bracket_merge_plan.md` — full refactor plan (engine, EOS swap, Tournament ObjectIds).
- **EOS:** `eos_tournament.initialize_eos_tournament` (standings → seeds → `bracket_engine.generate_bracket`), `save_tournament_game_result` → `bracket_engine.save_game_result` + results append, `advance_tournament_round` → `bracket_engine.advance_bracket` (winners from matchups). **Refactor complete.** Caller sets `franchise_doc["results"] = existing_results` (including week 14) before init so seeding uses full results.
- **Tournament init:** `TournamentManager.create_tournament` (random shuffle → bracket). Will use ObjectId strings + `bracket_engine` once refactor is done.
