# Tournament vs Franchise EOS Bracket Merge Plan

**Date:** January 2025  
**Status:** ✅ Steps 1–4 done (bracket_engine, EOS refactor, Tournament refactor, Step 4 cleanup).  
**Goal:** Unify the two bespoke bracket/tournament engines (Tournament mode vs Franchise EOS) into a single shared implementation where possible.

**Related:** `Tournament_Franchise_Unification_Plan.md` (broader mode unification). This doc focuses **only** on bracket init, advance, and save-result logic.

**Motivation:** EOS has had multiple bugs (seeding from wrong source, FTD query type mismatch, infinite loop re-playing same game after a loss). Tournament mode’s bracket flow is well exercised. Unifying ensures both use the **exact same logic flow** (after seeding) and reduces EOS-specific bugs.

---

## 1. Current State: Two Bespoke Code Paths

### 1.1 Tournament Mode (Standalone)

| Concern | Location | Behavior |
|--------|----------|----------|
| **Storage** | `tournaments` collection | One doc per tournament. `bracket`, `current_round`, `completed`, `results` (list of `{round, match_index, winner, …}`). |
| **Seeding** | `TournamentManager.create_tournament()` | Random shuffle of 8 **team names** (strings). `seeds = {name: i+1}`. |
| **Bracket gen** | `TournamentManager._generate_first_round(seeds)` | 1v8, 4v5, 2v7, 3v6. Matchups use **team names** as `home_team` / `away_team`. Round keys: `round1`, `round2`, `final`. |
| **Save result** | `TournamentManager.save_game_result(round_name, matchup_index, game_id, winner_id, score)` | Updates `bracket[round][i]` (game_id, winner, score) and persists to `tournaments`. Also pushes to `tournament.results` (round, match_index, winner) from **tournament_routes** before advance. |
| **Advance** | `bracket_logic.update_bracket_from_results(tournament_id)` | Loads tournament, reads **`tournament.results`** (round + match_index), derives winners, builds next round (0+1→match0, 2+3→match1), writes to `tournaments`. Idempotent. |

**Trigger:** `POST /start-tournament` → `TournamentManager.create_tournament()`. Game results → save-result endpoint → `update_bracket_from_results`.

### 1.2 Franchise EOS (End-of-Season)

| Concern | Location | Behavior |
|--------|----------|----------|
| **Storage** | `franchise.eos_tournament` (embedded) | `bracket`, `current_round`, `completed`, `champion`, `seeds`, `results` (list). |
| **Seeding** | `eos_tournament.calculate_standings` → `generate_seeds` | Standings from **`franchise.results`** (W/L, PF–PA, tiebreaker). Seeds 1–8 = **team ObjectIds** (strings). |
| **Bracket gen** | `eos_tournament.generate_bracket(seeds, teams_collection)` | Same 1v8, 4v5, 2v7, 3v6. Matchups use **team ObjectId strings** as `home_team` / `away_team`. Same round keys. |
| **Save result** | `eos_tournament.save_tournament_game_result(franchise_doc, round_num, matchup_index, game_id, winner_id, score)` | Updates matchup in memory, appends to `eos_tournament.results`. Caller (franchise_routes) persists `franchise.eos_tournament`. |
| **Advance** | `eos_tournament.advance_tournament_round(franchise_doc, teams_collection)` | Reads **bracket matchups** (e.g. `round1[i]["winner"]`), builds next round from winners, returns updated `eos_tournament`. **Does not** use `eos_tournament.results` for advance. |

**Trigger:** Week 14 complete → `initialize_eos_tournament`. Game results → `save_tournament_game_result` → `advance_tournament_round` (in `complete_week`).

### 1.3 What’s Already Aligned

- **Bracket shape:** Both use `round1`, `round2`, `final` and matchups `{home_team, away_team, game_id, winner, score}`.
- **Round structure:** Round 1 → Round 2 (semis) → Final. Same 1v8, 4v5, 2v7, 3v6 pattern.
- **Advance logic:** Winners 0+1 → semi 0, 2+3 → semi 1; semi winners → final. Same pairing rules.

### 1.4 What Differs (Pre-Merge)

| Aspect | Tournament | EOS |
|--------|------------|-----|
| **Team identifier** | Team **names** (e.g. `"Lancaster"`) | Team **ObjectId strings** |
| **Seeding source** | Random | Standings from `franchise.results` |
| **Result storage** | `tournament.results` list (round, match_index, winner) | Winner on **matchup** + `eos_tournament.results` list |
| **Advance input** | `tournament.results` | Bracket matchup `winner` fields |
| **Persistence** | `tournaments` collection | `franchise.eos_tournament` |
| **Init** | `TournamentManager.create_tournament` | `initialize_eos_tournament` |

**Post-merge:** We unify on **ObjectId strings** for team IDs in both modes; Tournament is refactored accordingly (§8).

---

## 2. What Merging Would Entail

**Target:** After seeding (random for Tournament, standings for EOS), both modes enter the **exact same logic flow** — bracket init → save result → advance → “next game.” Only **DB sources** differ: `tournaments` vs `franchise.eos_tournament`.

### 2.1 Shared Abstraction

Introduce a **generic bracket engine** that:

1. **Initializes** a bracket from an ordered list of 8 **team identifiers** (see §8: we standardize on **ObjectId strings**).
2. **Saves a game result** for a given round and matchup index (updates matchup, optionally appends to a results list).
3. **Advances** the bracket (e.g. from matchup winners or from a results list — see §2.4).

The engine operates on an in-memory bracket (+ optional results list) and returns updates. **Persistence** is mode-specific: callers load/save from `tournaments` or `franchise.eos_tournament`.

### 2.2 Proposed Shared Module

**New / refactored module:** `BackEnd/tournament/bracket_engine.py` (or similar)

All team identifiers in bracket, results, and “next game” are **ObjectId strings** (see §8).

- **`generate_bracket(seed_order: List[str])`**  
  - `seed_order`: ordered list of 8 **ObjectId strings** (1–8).  
  - Returns `{round1, round2, final}` with matchups `{home_team, away_team, game_id, winner, score}` (all team IDs as ObjectId strings).  
  - Replaces duplicate logic in `TournamentManager._generate_first_round` and `eos_tournament.generate_bracket`.

- **`advance_bracket(bracket: dict, current_round: int, *, winners_from_matchups: bool = True)`**  
  - If `winners_from_matchups`: derive winners from `bracket[round_key]` matchups.  
  - Else: derive from `results: List[{round, match_index, winner}]` (to support tournament’s current contract during transition).  
  - Returns `(updated_bracket, next_round, completed, champion)` or similar.  
  - Replaces core logic in `bracket_logic.update_bracket_from_results` and `eos_tournament.advance_tournament_round`.

- **`save_game_result(bracket: dict, round_num: int, matchup_index: int, game_id, winner_id, score?)`**  
  - Updates the matchup in `bracket`. No DB. Callers persist.  
  - Replaces the bracket-update parts of `TournamentManager.save_game_result` and `save_tournament_game_result`.

### 2.3 Unification of Seeding

- **Tournament:** Get 8 teams (ObjectIds from DB), **random shuffle** → `seed_order`. Pass into `generate_bracket`.
- **EOS:** Compute standings from `franchise.results` → top 8 → `seed_order` = list of **ObjectId strings**. Pass into `generate_bracket`.

Seeding **source** stays mode-specific (random vs standings); **output** is always an ordered list of 8 ObjectId strings. Bracket generation from that list is shared.

### 2.4 Unification of Advance

- **EOS:** Use `winners_from_matchups=True`. Advance reads winners from bracket, runs shared `advance_bracket`, then franchise_routes writes `franchise.eos_tournament` back.
- **Tournament:** Two options:
  1. **Keep `tournament.results`**: Continue pushing `{round, match_index, winner}` on save-result. Advance uses `update_bracket_from_results` but **internally** calls shared `advance_bracket` with `winners_from_results` (or equivalent) so the pairing logic lives in one place.
  2. **Migrate to matchup-based winners**: Stop using `tournament.results` for advance; update matchup on save, then advance from matchups (like EOS). Simplifies logic but changes tournament document shape and possibly frontend expectations.

Recommendation: **Option 1** initially — reuse advance **logic** (pairing, next-round layout) via shared `advance_bracket`, while keeping tournament’s existing results list and `update_bracket_from_results` orchestration.

### 2.5 Persistence Stays Separate

- **Tournament:** `tournaments` collection. Routes load/save tournament doc, call shared engine, then persist.
- **EOS:** `franchise.eos_tournament`. `complete_week` and related franchise routes load/save franchise doc, call shared engine, then persist.

No unified storage layer required; only the **bracket + advance + save-result logic** are shared.

---

## 3. Files to Touch

### 3.1 New / Refactored

| File | Purpose |
|------|---------|
| `BackEnd/tournament/bracket_engine.py` | Shared `generate_bracket`, `advance_bracket`, `save_game_result` (bracket-only). |

### 3.2 Tournament Mode

Tournament is refactored to use **ObjectId strings** for team IDs in bracket, results, and “next game” (see §8). That adds scope: bracket, results, next-game logic, plus **ObjectId ↔ name resolution** at API/game boundaries (display, game init, roster).

| File | Changes |
|------|---------|
| `BackEnd/tournament/tournament_manager.py` | Use **ObjectId strings** for teams (not names). Seed from 8 team ObjectIds, random shuffle → `seed_order`. Use `bracket_engine.generate_bracket(seed_order)`. Replace advance logic with `bracket_engine.advance_bracket`. `save_game_result` calls shared `save_game_result` then persists. |
| `BackEnd/tournament/bracket_logic.py` | `update_bracket_from_results` operates on bracket/results with ObjectId strings. Orchestrates load → derive winners → shared `advance_bracket` → persist. |
| `BackEnd/api/tournament_routes.py` | Keep save-result → update_bracket_from_results flow. Resolve **ObjectId ↔ name** at edges (e.g. game init, roster, API responses) where rest of app expects names. Adjust APIs if TournamentManager / bracket_logic change. |

### 3.3 Franchise EOS

EOS already uses **ObjectId strings** for team IDs; no identifier migration. Refactor is mainly swapping in the shared engine.

| File | Changes |
|------|---------|
| `BackEnd/tournament/eos_tournament.py` | Use `bracket_engine.generate_bracket(seed_order)` for bracket init (seed_order = top 8 ObjectId strings from standings). Replace `advance_tournament_round` with `bracket_engine.advance_bracket` (winners from matchups). Replace bracket-update part of `save_tournament_game_result` with shared `save_game_result`. Keep EOS-specific: `calculate_standings`, `generate_seeds`, `initialize_eos_tournament` orchestration, and read/write of `franchise.eos_tournament`. |

### 3.4 Shared Helpers (Optional)

| File | Purpose |
|------|---------|
| `BackEnd/tournament/round_utils.py` or inside `bracket_engine` | Shared `get_round_name(round_num)`, round keys (`round1` / `round2` / `final`), so both paths use same constants. |

---

## 4. Implementation Order

1. **Add `bracket_engine`**  
   - Implement `generate_bracket`, `advance_bracket`, `save_game_result` with clear interfaces (team IDs, optional seed order, optional results-based advance).
2. **Refactor EOS**  
   - Swap in `bracket_engine` for bracket gen, advance, and matchup updates. Keep standings → seeds → init orchestration in `eos_tournament`. Test week 14 → 15 → 17 flow.
3. **Refactor Tournament**  
   - Switch bracket/results/next-game to **ObjectId strings** (§8); add ObjectId ↔ name resolution at API/game boundaries. Use `bracket_engine` for round1 and advance. Keep `tournament.results` contract if desired. Test full tournament flow.
4. **Optional cleanup** ✅  
   - Consolidated round-key logic: all `round_key` / `round_name` derivation now uses `bracket_engine.get_round_name(round_num)` in `tournament_routes` and `franchise_routes`. Removed inline `"final" if round == 3 else f"round{round}"` duplication.

---

## 5. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Breaking Tournament or EOS flows | Run both flows (full tournament + franchise EOS) in tests/manual QA before and after. Keep persistence and API contracts unchanged initially. |
| Tournament refactor scope (ObjectIds, resolution at edges) | Unifying on ObjectIds increases Tournament work: bracket, results, next-game, plus ObjectId ↔ name resolution at API/game boundaries. Plan for that pass explicitly. |
| Different result formats (results list vs matchup winner) | Support both advance inputs (matchups vs results) in the shared abstraction, or keep a thin adapter in `bracket_logic` that converts `results` → winners then calls shared advance. |
| Regression in standings-based EOS seeding | EOS seeding stays in `eos_tournament`; only bracket **generation** from seeds is shared. Re-run existing EOS seeding tests. |

---

## 6. Success Criteria

- **Single implementation** of 1v8, 4v5, 2v7, 3v6 bracket gen and round advance.
- **No behavior change** for users: Tournament mode and Franchise EOS behave as they do today.
- **Clear separation:** seeding and persistence remain mode-specific; bracket structure and progression are shared.
- **Tests:** Add or extend tests for `bracket_engine` (gen, advance, save) and existing tournament + EOS flows.

---

## 7. Out of Scope (For This Merge)

- Changing **storage** (tournaments vs franchise) or **API** contracts.
- **UI** (bracket display, logos, etc.); see existing unification plan for frontend.
- **Seeding rules** (random vs standings); those stay mode-specific, only the “build bracket from ordered 8” step is shared.

---

## 8. Design Decisions from Discussion

- **Team identifiers:** We **unify on ObjectId strings** (hex, e.g. `"68c98b08674d3f9b04546b2e"`) for team IDs in bracket, results, and "next game." Tournament mode is **refactored** to use them instead of team names; EOS already does. **ObjectId objects** are used **only at DB boundaries** (e.g. `teams.find({"_id": ObjectId(team_id)})`, FTD lookups). Everywhere else we store and pass strings.
- **Tournament-mode refactor scope:** Unifying on ObjectIds implies a broader Tournament refactor: bracket, results, next-game logic all use ObjectId strings; **ObjectId ↔ name resolution** happens only at edges (display, game init, roster, API). This is called out in §3.2 and §5.
- **Exact same flow, different DB sources:** After seeding (random vs standings), both modes use the **exact same** bracket init → save result → advance → "next game" flow. Only **load/save** targets differ (`tournaments` vs `franchise.eos_tournament`).

---

**Last Updated:** January 2025
