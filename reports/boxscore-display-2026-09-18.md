# Box-score position labels

**Verdict: NOT A BUG.** The `PG` / `BENCH_<id>` keys `get_box_score` produces are never shown to a player. The frontend matches box-score rows by name or player id and renders the position from the **roster** record, discarding the key. Nothing was changed, nothing committed.

Read-only investigation at `c2cf4d714`. The MIN-units question is closed per the brief and was not revisited.

## 1. Is `player.position` mutated during a game?

**No. It is never written, and it does not exist.**

- **Zero writes:** `grep -rn "\.position\s*=" BackEnd --include='*.py'` (excluding tests) returns **nothing**. No code path assigns `player.position` at any point in a game.
- **The attribute is absent entirely:** `BackEnd/models/player.py` defines `self.position_ratings` (line 79) and no `self.position`; there is no `self.pos` either. So in

  ```python
  pos = getattr(player, "position", None) or getattr(player, "pos", None) or "BENCH"   # game_manager.py:2432
  ```

  both `getattr` calls always return `None`, and **every** non-lineup player falls through to the literal `"BENCH"`. The `BENCH_<player_id[:8]>` variants are produced two lines later purely to avoid duplicate dict keys.
- **Where the `PG` / `SG` / … labels come from:** not from the player at all, but from the `team.lineup` dict keys in the loop above (`game_manager.py:2416-2424`). `get_box_score` is a snapshot of whoever occupies each lineup slot *at the moment it is called* — from the end-of-game summary path that is the final buzzer. That is why a starter who was substituted out appears as `BENCH_<id>`: not mutation, just when the snapshot is taken.
- **`BackEnd/utils/player_entry.py`:** its only `BENCH` references are `"kind": "BENCH_ENTRY"` (line 119) and a comment (line 135). That is an **animation kind** for a substitute walking on, unrelated to box-score labels. It writes no position field.

## 2. What does a player actually see?

**Not this label.** The box-score view uses it only as a lookup handle:

- `FrontEnd/static/box-score.js:369-374` finds a player's stats with `Object.entries(boxScore).find(...)` matching **`playerData.name === p.name` or the playerId**, then takes `?.[1]` — the value. The key is dropped.
- `FrontEnd/static/box-score.js:414` sets the rendered position from the roster record: `pos: p.pos || p.position || null`.
- `FrontEnd/static/box-score.js:884-888` is the only place the key is bound (`([pos, playerData])`), and it is used solely as a **fallback matcher** (`p.name === playerData.name || (p.pos === pos && p.name)`). A `BENCH_<id>` key simply never matches a roster `pos`, so name matching does the work. The key is still never displayed.
- `FrontEnd/static/js/shared/pageLoadOverlay.js:477-494` iterates `Object.keys(box)` only to index rows, and renders `row.name` plus stats (`formatPostgameStatLine`, line 450). The key is not printed.
- `FrontEnd/static/js/shared/potg.js:174-181` uses the **outer** key (team) and then `Object.values(teamPlayers)` — player keys never read.
- `gameScene.js:2249-2299` and `loadGameStats.js:471-477` likewise index by **team**, not by player position.
- The two files the brief flagged do not touch these labels at all: `simGamePresentation.js:47/528/534` is a `BENCH` chip label built from its own substitution data, and `gameScene.js:1690/3837/3844` is the `BENCH_ENTRY` animation kind.

Since the UI never shows the label, this is **not a bug**, and per the brief I stopped here: no fix was made.

## 3. Is "on the floor at the buzzer" deliberate?

**Incidental, and nothing depends on it.** The function's stated intent (`game_manager.py:2408`) is *"Get box score with all players (lineup + bench) to match team totals"* — the keys exist to be unique, which is why the collision guard appends a player-id fragment. No lineup display anywhere reads them (Q2), so the snapshot timing is not serving a second purpose. Note the same function is also called mid-game (`main.py:475` stores `start_box_score` at quarter start), where the same lineup-at-call-time rule applies.

## 4. Blast radius (had a fix been warranted)

Every consumer is key-agnostic, so the labels carry no stored data:

| consumer | how it reads the map | key used as a position? |
|---|---|---|
| `main.py:1070-1076` player-stats snapshot | copies the whole dict per team | no |
| `main.py:1151-1158` `calculate_team_stats` | sums `player_dict.values()` | no |
| `eog_attr_rules.py:31-36` `_aggregate_from_box` | iterates `.values()` | no |
| `game_summary_builder.py:34`, `api.py:1620/5730/6140`, `shared.py:2673/2945` | pass the map through into the payload | no |
| `franchise_routes.py:5602` | checks the map exists | no |
| `box-score.js` | name / playerId match; renders roster `pos` | no |
| `pageLoadOverlay.js`, `potg.js`, `gameScene.js`, `loadGameStats.js` | team-level keys; `.values()` for players | no |
| the equiv-v3 harness (`scratch_equiv3_fbdedupe.py`, probes) | reads player stats objects | no |

Season stat aggregation, awards and EOG processing all consume per-player stat **values**; none of them keys off the position label. So changing it would have been display-only — but Q2 already settles it: there is nothing player-visible to change.

## Verification

No code changed, so the references are untouched by construction and no runs were needed: played still stands at `d9a4f1517` and sim at `equiv_v3_sim_reference_9910cd6fd.json`. `git status` shows no modified tracked files; the only new file is this report.

## One correction to the previous report

`reports/boxscore-aggregates-2026-09-17.md` §4 described the label as "who is on the floor at the final buzzer". That is accurate about the observed behaviour, but the framing implied a `position` field that changes during the game. There is no such field: `Player` has no `position` or `pos` attribute, so non-lineup players always get the literal `"BENCH"`, and the positional labels are the `team.lineup` keys at call time. The §4 conclusion that drew on it — that the 32-point "bench" player was in fact a tipoff starter — is unaffected.

## Not covered

- The MIN units: closed by the brief (stored in game-seconds, converted with `Math.floor(seconds/60)` at `box-score.js:1080` and `pageLoadOverlay.js:461/482`); not revisited.
- No engine logic, constant, threshold, default or tuning was touched; no commits were made.
- The crash flags, `animator.py:1213`, the played arm, the `randint(1,6)`, the rebound path, R1 (Final Turn) and R2 (stopper) were not touched.
