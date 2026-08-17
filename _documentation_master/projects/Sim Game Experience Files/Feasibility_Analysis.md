# Sim Game Presentation — Feasibility Analysis (response to C+C Prompt 1)

> ## ⚠️ HISTORICAL — pre-build document, retained for reasoning only
>
> **Written before implementation. The feature has since shipped.** Where this document
> and the code disagree, **the code is right**. Current behaviour is documented in
> [`06_Gameplay_Systems/Sim_Game_Presentation_System.md`](../../06_Gameplay_Systems/Sim_Game_Presentation_System.md);
> pacing lives in [`11_Design_Systems/Tunable_Constants.md`](../../11_Design_Systems/Tunable_Constants.md).
> This file is kept because the Q1–Q10 investigation explains *why* the architecture is
> shaped the way it is — it is not a description of what exists.
>
> **What changed between this analysis and the shipped build:**
>
> | This doc says | Shipped |
> |---|---|
> | RT bands: adopt the canonical **4-band** `rtBucket.js` map | `rtBucket.js` now runs `RT_DISPLAY_MODE = 'letter'` — **9 grades over 4 colours** (A++→F), per the Styleguide's RT Letter-Grade Scale. The badge shows a letter, not a number. Q7's colour reasoning still holds; the band count does not. |
> | Overlay mounts as a body-level fixed overlay over the court region | Correct, but **full-width** — it covers the court *and* both side panels below the scoreboard. Only the scoreboard stays live. |
> | Q9: Moments derived client-side from `turns[]`, random stub acceptable for review | **Not built at all.** No stub shipped. `.ticker` is a fixed 44px empty slot; every frame carries `ticker: null`. |
> | Chunk 0 backend: add `rt` **and** "confirm per-turn team fouls/timeouts for the scoreboard" | `rt` shipped. The team fouls/timeouts half was **missed** — the client derived team fouls by summing player `F` (which never resets per quarter) and read timeouts once from the final summary (which spoiled the end state from frame one). Both are now emitted per turn from `_append_turn()`. |
> | Chunk 4 — Moments/ticker | Skipped. Chunks 0–3, 5, 6 shipped. |
> | Design ↔ data map row `p.spot` — POTG on partial cumulative stats | Correct, with one clarification: the spotlight scores **only the ten players currently on court**, not the whole roster. |
>
> **Confirmed accurate and still load-bearing:** Q1 (DOM, not Phaser), Q2 (the `bootGame.js`
> seam — line numbers have drifted, the seam has not), Q3–Q6, Q8, Q10, and the "Assumptions"
> block, whose *"run the quarter loop to completion, then play the assembled timeline"*
> recommendation is exactly what shipped.


**Verdict: highly feasible, low backend risk.** Act 2 is a DOM overlay reusing Act 1's machinery, and the sim **already emits a real per-possession timeline** — the broadcast plays back real data, no re-simulation or synthesis. Almost every value the design needs already exists and is already streamed. There is **one** real data-plumbing gap (roster RT not in the game payload) and **three** design reconciliations to settle before building.

---

## Answers — Q1–Q10

### A. Architecture
**Q1 — Phaser scene or DOM overlay? → DOM overlay. Do NOT use Phaser.**
Act 1 (`preGameExperience.js:255` `showPreGameExperience`) is a plain DOM overlay appended to `document.body` (`.pgxp-root { position:fixed; inset:0; z-index:10002 }`), self-contained `<style>`, CSS-driven phase machine, Promise-based teardown (`root.remove()` + resolve). The `scene` param is only an audio handle. Build Act 2 identically and reuse: `preGameExperience.js` lifecycle pattern, `matchupsUiShared.js` (`buildPlayerTileHtml`, `playerImageUrl`, `POSITIONS`, `SILHOUETTE`), `gameSfx.js` audio beats, the shared `pgxp-*` style block. Rebuilding bars/worm/ticker as Phaser GameObjects would be pure cost for no benefit.

**Q2 — Where does it hook in?**
Both buttons bind `handleSimFullGame` (`bootGame.js:3217`/`:3221`); only the label + `advance_method` differ. The handler runs a per-quarter `while` loop (`:2807-2936`) POSTing `/api/simulate-quarter` with `full_sim=true`, one request per quarter, `lastSummary = res.json()` each time. On loop exit it calls `handleGameCompletion(...)` (`:2958-2967`) → `showGameCompletionPopup` (`gameCompletionPopup.js`).
**Seam: `bootGame.js:2957`** — after the loop (final `lastSummary`/`quarter` ready), before `handleGameCompletion`. Insert `await showSimGamePresentation(assembledTimeline)` there; completion popup fires unchanged afterward.

### B. Data contract
**Q3 — Timeline or only final box score? → Real per-possession timeline exists.** ✅ Better than the design assumed.
`full_sim` responses include `turns[]` (frontend summary passes `exclude_animations=False`, `shared.py:2857-2860`). Each turn (`turn_manager.py:2380-2540`) carries: running **score** (`:2388`), per-player stat **deltas** (`:2467`), **clock**/`time_remaining`/`shot_clock`/`quarter` (`game_manager.py:816-825`), on-court **lineups** (`:2385-2386`), `result_type`, `points`, `player_momentum`. ~40–80 turns/quarter → maps onto the "~45 frames/quarter" target. Cumulative per-player stats = accumulate `turns[].deltas`; running score is already absolute. **No re-sim, no client interpolation of score/stats.** One response per quarter → assemble across the 4.

**Q4 — On-court state over time? → Yes, per turn.** ✅
`turn.home_lineup`/`turn.away_lineup` = `{position: player_id}` (`serialize_lineup`, `shared.py:3756`). Foul-out swaps are reflected live (`game_manager.py:646-678`; turn also carries `fouled_out`/`foul_out_player`). **No energy/rotation auto-subs exist** — the only in-quarter lineup change is a foul-out, which is exactly the design's swap trigger. "Fixed-five + in-place swap" is fully backed by real data.

### C. Values
**Q5 — Real DEF%? → Yes, already computed + displayed.** ✅
`DEF% = round(DEF_S / DEF_A * 100)` (`scouting_utils.py:257-266`). `DEF_A`/`DEF_S` are box-score counters incremented in-engine (`shot_manager.py`), accumulate per turn via deltas. Frontend already renders `defPct` (`box-score.js:994`). Read straight off the box score.

**Q6 — Momentum for hot/cold? → Yes, per-player, already streamed.** ✅
`player.attributes["MO"]`, clamped **[-5, +5]** (`constants/momentum.py`, `player.py:189`). Stamped on every turn as `turn.player_momentum = {player_id: MO}` (`game_manager.py:869-873`) and in the per-player payload (`shared.py:2494`). flame = MO>0, snowflake = MO<0 — zero new engine work. (A frontend `moFlavor` hot/cold hook exists in `announcements.js:432` but is unpopulated; irrelevant — read `player_momentum` directly.)

**Q7 — Roster RT bands + colors? → Bands exist (4, not 5); RT is NOT in the game payload.** ⚠️ **the one real gap.**
- Roster RT = **max of `player.position_ratings` {PG..C}**, range ~0–100 (`db_utils.py:181` `_player_rt_max`). Distinct from recruiting RT.
- Canonical color map already exists (`rtBucket.js:15-22` + `rt-buckets.css`): **`0-40 red · 41-60 gold/#FFD700 · 61-80 green · 81+ blue`** (4 bands). The prototype already codes exactly this.
- **RT is absent from the in-game court player payload** (`shared.py:2489-2530` has `playerId`, `name`, `MO`, energy — no `position_ratings`/RT). It only reaches lineup-setting UIs. **→ Must add RT to the game player payload (backend) or fetch separately.**

**Q8 — Player of the Game, partial-safe? → Yes.** ✅
`_calculate_potg_summary` (`franchise_routes.py:560-698`), client mirror `potg.js:132-160` (`calculatePotgPoints`). Formula: `2*(PTS+AST+REB+STL+BLK)` + DEF% bonus (if DEF_A>10) + `+3` winning-team. All inputs are cumulative counters valid at any moment; the only final-only term is the `+3` winner bonus, which is optional and **already omitted by the client mirror**. Use `potg.js` for the traveling spotlight on partial mid-game stats.

### D. Moments
**Q9 — Play-by-play copy? → Only event banners, and NONE during full_sim.** ⚠️ net-new.
Event-typed short banners exist (`gameAnnouncements.js:50`, e.g. "STEAL!", "Rebound!") — templated labels, not prose. Critically, during `full_sim` animation generation early-returns `[]` (`main.py:938-940`), so **no announcement text is produced on the sim path**. The Moments feed must be **derived client-side from `turns[]`** (`result_type`, score swings/runs, lead changes) with a selection rule (~5–8/game). The event taxonomy (`result_type` per turn) is the scaffolding. For Prompt-1 review, a random stub against RUN/HEAT/FOUL/LEAD is acceptable.

### E. Other
**Q10 — Real portraits? → Yes.** ✅ `API_CONFIG.getPlayerImageUrl(player_id)` → Cloudflare R2, silhouette/generic fallback (`matchupsUiShared.js:103`). Sim response `players[]`/`box_score` carry the `player_id`s. Keep the silhouette only as fallback.

---

## Design ↔ data map (per-frame `st` object from `sim-presentation.js`)

| Design field | Source | Work |
|---|---|---|
| score/clock/quarter/shot | `turns[].score`, `time_remaining`, `shot_clock_remaining`, `quarter` | read |
| team fouls / timeouts (atol/htol/afoul/hfoul) | accumulate foul deltas; `teams[].timeouts`/`team_fouls` | derive/**verify per-turn** |
| worm (lead margins over time) | `turns[].score` sequence | derive |
| on-court 5 per team | `turns[].home_lineup`/`away_lineup` | read |
| p.pts/reb/ast/fouls | accumulate `turns[].deltas` | derive |
| p.def (DEF%) | accumulate `DEF_S`/`DEF_A` deltas → round | derive |
| p.rt | **NOT in payload — add to backend or fetch** | ⚠️ **gap** |
| p.hot/cold | `turns[].player_momentum` (MO ≷ 0) | read |
| p.out (fouled out) | `turn.fouled_out`/`foul_out_player` | read |
| p.sub (checked IN) | diff consecutive turns' lineups | derive |
| p.spot (TOP) | `potg.js` on partial cumulative stats | derive |
| bench chips (name/pts/reb/out) | `players[]` minus on-court + accumulated | derive |
| ticker (RUN/HEAT/FOUL/LEAD) | derive from `turns[].result_type` + swings | ⚠️ net-new |
| name/jersey/portrait | `players[]` + `player_id`→R2 | read |

**Everything is available or client-derivable except RT (one backend field) and Moments (client-side derivation).**

---

## Recommended design changes / reconciliations (decide before build)

1. **RT band count — 4 vs 5.** Brief text says 5 bands (blue→green→**gold→orange**→red); the canonical system **and your own prototype** use **4** (blue/green/gold/red at 81/61/41). **Recommend: adopt the canonical 4-band `rtBucket.js` map** for app-wide consistency and zero new mapping. (Extending to 5 is possible but diverges from every other RT surface in the app.)
2. **Moments are not real PBP.** Confirm we derive ~5–8 moments from `turns[]` (runs/lead-changes/big plays), stubbed random for the first build — not real commentary.
3. **Act 1 during the sim.** Brief step 2 wants the pre-game experience to play *while Sim Full Game sims in the background*, but `handleSimFullGame` currently **removes** `.pre-game-container` at start (`:2764`) and the pre-game overlay is the separate Q1 flow. Confirm/wire Act 1 as the during-sim cover for **Sim Full Game**; **Sim Rest of Game** (Q2+) has no Act 1 and goes straight to Act 2.

---

## Assumptions
- Playback is **client-paced** off the assembled timeline; the sim (~8–16s total across the 4 quarter requests) finishes well before the ~60–120s broadcast, so: **run the existing quarter loop to completion collecting each quarter's `turns[]`, then play the assembled full-game timeline.** (Decouples sim from playback; simplest + robust.)
- `full_sim` turns are **lighter than interactive** turns because animation generation early-returns `[]` on that path (Q9) — so the timeline feed is mostly stat/score/lineup data. **Verify actual full_sim response size**; if heavy, add a slim `turns[]` projection (backend, low-risk) — not a blocker.
- Away-left / home-right confirmed (`court.html` `#app-grid`); Act 2 mounts as a body-level fixed overlay (not nested in `#phaser-container`, which is clipped to the court cell).

---

## Implementation plan (reviewable chunks)

- **Chunk 0 — Backend (tiny, only backend change):** add roster **RT** (`_player_rt_max`) to the game player payload (`shared.py` player serialization); confirm per-turn team fouls/timeouts for the scoreboard. Draw-safe, additive.
- **Chunk 1 — Timeline assembler (client, pure fn):** walk `turns[]` (across the 4 quarter responses) → ordered array of `st` frame-states matching the `sim-presentation.js` contract (accumulate deltas, build worm, detect subs, compute DEF%, run `potg.js` for spotlight). Unit-testable in isolation.
- **Chunk 2 — Overlay shell + lifecycle:** DOM overlay mount/teardown/Promise mirroring Act 1; wire `scoreboard` + player rows + worm from the prototype renderer; reuse `pgxp-*` DNA + portraits.
- **Chunk 3 — Playback engine:** timer-driven walk through frames; pacing, quarter-break card, spotlight migration, in-place sub swaps, hot/cold.
- **Chunk 4 — Moments/ticker:** derive from `turns[]` (or random stub for review), RUN/HEAT/FOUL/LEAD selection rule + cadence.
- **Chunk 5 — Wire-in:** hook at `bootGame.js:2957`; Act 1→Act 2 chaining for Sim Full Game, straight-to-Act 2 for Sim Rest; hand off to `handleGameCompletion` unchanged.
- **Chunk 6 — States polish:** pretip/break/final, reduced-motion, 1280×720 sanity, audio beats.

**Nothing here blocks on the engine.** Only Chunk 0 touches backend, and it's one additive field.
