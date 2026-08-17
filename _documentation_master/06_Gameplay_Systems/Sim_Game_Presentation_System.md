# Sim Game Presentation System

> **Last Updated:** August 2026
> **Purpose:** The broadcast playback shown when the user sims their own game instead of playing it. Replaces the blank "Simulating Q1…" screen with a ~80–85s animated stat broadcast.

**Related:** [Pre-Game Experience System](./Pre_Game_XP_System.md) · [Gameplay Buttons System](./Gameplay_Buttons_System.md) · [End Of Game System](./End_Of_Game_System.md) · [UESS System](../05_UESS_System/UESS_System.md)
**Pacing constants:** [`Tunable_Constants.md` § Sim Game Experience](../11_Design_Systems/Tunable_Constants.md)
**Design history:** `projects/Sim Game Experience Files/` — historical, superseded by this doc and by the code.

---

## 1. Scope

Fires on the `.sim-full-game-button` path only — both labels, **Sim Full Game** (Q1) and **Sim Rest Of Game** (Q2+). Play Quarter is unaffected; the dormant Sim Quarter button never reaches it.

The show is two acts:

| Act | Module | Content |
|---|---|---|
| **Act 1** | `preGameExperience.js` (`displayOnly: true`) | Starting-five reveal → `Tip Off` button → veil held until the sim finishes. **Sim Full Game only.** |
| **Act 1′** | `preGameExperience.js` → `showPreppingSimCover()` | `PREPPING SIM` veil, held until the sim finishes. **Sim Rest Of Game only.** |
| **Act 2** | `simGamePresentation.js` | The broadcast. Both paths. |

Act 2 hands off to the existing `gameCompletionPopup.js` unchanged.

---

## 2. Architecture — assemble, then play

**The presentation is a pure replay over finalized data.** The full sim runs to completion first; playback starts afterward. This is deliberate and is the single most important thing to know about the system.

```
Sim button pressed
  └─ showOpaqueSimBridgeCover()          Full Game only — covers court + scoreboard instantly
  └─ while (!is_final):                  per-quarter POST /api/simulate-quarter (full_sim: true)
     └─ after Q1 response: launchAct1Cover(gid)   Act 1 mounts over the running sim
     └─ quarterSummaries.push(response)
  └─ resolveSimDone()                    releases the held veil
  └─ await act1CoverPromise / preppingCoverPromise
  └─ clearOpaqueSimBridgeCover()
  └─ buildSimTimeline(quarterSummaries)  pure transform → frames[]
  └─ showSimGamePresentation(timeline)   ~80–85s playback
  └─ handleGameCompletion(...)           existing popup, unchanged
```

Orchestration lives in `bootGame.js` → `handleSimFullGame()`. The fork is one line: `isSimFullGame = Math.max(0, quarter) < 2`.

### 2.1 Why the covers exist

The sim takes several seconds; the broadcast takes ~85. Act 1 is not decoration — it is **the thing that covers the sim wait**, and it holds its tip-off veil on a `waitForSim` promise rather than a timer, so it can never uncover early. Sim Rest Of Game has no cinematic to give, so it gets the same veil with `PREPPING SIM` copy.

The opaque `.pgxp-bridge` covers the gap between button press and Act 1 mounting (Act 1 can only launch after the Q1 response, because `/lineup-for-matchups?prefer_opening=1` needs the game set up). Every one of these is self-guarded — any failure degrades to going straight to Act 2, never to a broken screen.

### 2.2 Finalize-first invariant

The game is fully simulated and persisted before a single frame plays. The overlay reads durable data and can be abandoned at any point without affecting game state. **Nothing in the presentation path may ever write game state.**

### 2.3 What did NOT ship

Two things from the design record are worth stating so they aren't assumed:

- **No `sim_timeline` backend field.** Frames are assembled client-side from `turns[]`. The design once specced backend frame emission; it was not needed.
- **No chunked/streaming playback.** The design once specced frames streaming per quarter with the presentation lagging a fast backend. The shipped model waits for the sim, then plays. Simpler, and it cannot starve or stutter.

---

## 3. Backend contract

**One additive field was ever added for this feature.** Everything else was already emitted.

| Field | Where | Notes |
|---|---|---|
| `rt` (per player) | `shared.py` `summarize_game_state()` | Roster RT via `_player_rt_max` (max across position ratings). Display-only. |
| `home_team_fouls` / `away_team_fouls` | `game_manager.py` `_append_turn()` | Live `Team.team_fouls`. Engine-owned; **resets each quarter**. |
| `home_timeouts` / `away_timeouts` | `game_manager.py` `_append_turn()` | Live `Team.timeouts`. Starts at 4, carries the whole game. |

All three stamps are additive, consume no RNG, and are draw-preserving — seeded exact-diff must remain byte-identical across them.

Everything else the broadcast needs was already on `turns[]`: `score`, `clock`, `quarter`, `shot_clock_remaining`, `home_lineup` / `away_lineup`, per-player `deltas`, `player_momentum`, `fouled_out` / `foul_out_player`.

---

## 4. Timeline assembler

`simTimelineAssembler.js` — pure, side-effect-free, unit-testable in isolation. Input: the ordered `/api/simulate-quarter` responses. Output: `{ teams, frames, meta }`.

### 4.1 One frame per emitted turn

Not a fixed frame count. A quarter is normalized to `QUARTER_MS` regardless of how many turns it contains (§6).

### 4.2 `turns[]` is cumulative — use the last response only

The backend caches the GameManager in `ongoing_games` and `turns[]` clears only for a new Q1, so **each quarter response carries the whole game so far**. The assembler reads `allTurns` from the *final* response. Concatenating the per-quarter responses would replay Q1 four times, Q2 three times, and so on.

The earlier responses are still collected — they supply the growing player directory (bench players appear as they check in) and the per-quarter cumulative snapshots used for reconciliation.

### 4.3 UESS compliance — accumulate, then reconcile

The FE is a pure renderer ([UESS §1](../05_UESS_System/UESS_System.md)). The one place this system comes close to the line is summing per-turn `deltas` into a running per-player cumulative. The guard:

- Accumulated totals are **display state only**, never authoritative.
- At **every quarter boundary and at final**, totals are reconciled against the emitted cumulative (`summary.players[].stats`).
- On any disagreement the **emitted value wins** — display state snaps to it — and the delta is logged so silent drift surfaces.

Clean runs log `✅ [SIM-PRES] Timeline reconciliation clean across N checks`; drift logs `⚠️ … snapped N stat(s)` with a per-stat detail table.

**Nothing else is derived on the client.** Score, clock, lineups, momentum, team fouls, and timeouts are all sampled from emitted values. Team fouls in particular must never be re-derived by summing player `F`: that cannot reproduce the engine's per-quarter reset.

### 4.4 Carry-forward for helper turns

Inbound, rebound and timeout turns omit `score` and the lineups. The assembler carries forward the last known values rather than resetting — otherwise bars pulse to zero and the scoreboard blanks on those turns. The same carry-forward covers team fouls and timeouts, and doubles as backward compatibility for any game cached before those stamps existed.

### 4.5 Frame shape

```
{ phase: 'pretip' | 'live' | 'final',
  quarter,
  score: { away, home, clock, quarter, shot, atol, afoul, htol, hfoul },
  worm: [margin, …],                    // home − away, whole game
  away: [p × 5], home: [p × 5],         // by POSITIONS order, PG→C
  benchAway: [chip], benchHome: [chip],
  ticker: null,                         // moments not built — see §7
  breakSummary?, final? }

p    = { id, pos, name, jersey, rt, pts, reb, ast, def, fouls, hot, cold, out, sub, spot }
chip = { name, pts, reb, out }
```

`breakSummary` is attached retroactively to the **last frame of the quarter that just ended**, at the boundary, before the new quarter's first deltas land.

### 4.6 Sim Rest Of Game — join, don't replay

`ctx.startQuarter` gates frame emission. Earlier quarters still accumulate stats, score and worm so the join is correct (carried score, cumulative stats, full-game worm shape), but no frames are emitted for quarters the user already played. The pre-tip frame is skipped entirely on this path.

---

## 5. Act 2 renderer

`simGamePresentation.js`. Pure renderer and easer — it derives no game state.

### 5.1 Mount and footprint

`.sgp-root` is a **full-width** `position: fixed` overlay at `z-index: 2000`, spanning from the bottom of the live scoreboard to the bottom of the viewport. It covers the court **and both 280px side panels**; only the scoreboard remains visible.

Its `top` is set in JS from `document.getElementById('scoreboard').getBoundingClientRect().bottom` and re-tracked on `resize`, so the scoreboard's own height is never assumed and no row can hide beneath it.

> **Note:** this is a change from the original design, which specced a center-court region flanked by the live side panels. Full-width shipped and is the current intent.

The Phaser canvas is never touched. The overlay is a body-level sibling, not nested in `#phaser-container` (which is clipped to the court grid cell).

### 5.2 The overlay drives the real scoreboard

Act 2 does **not** re-render the scoreboard. It writes emitted values into the live DOM ids each frame: `away-score`, `home-score`, `game-clock`, `quarter`, `shot-clock`, `away-fouls`, `home-fouls`, `away-tol`, `home-tol`. Suppressible via `opts.driveScoreboard = false`.

### 5.3 Player rows

Five position pairs, PG→C, away left / home right, mirroring the pre-game convention. Each row carries:

- **Portrait** — `API_CONFIG.getPlayerImageUrl(id, { size: 'card' })`, silhouette fallback. `src` is only reset when the slot's occupant changes, so subs don't cause a reload flicker on every frame. Border tints to team colour, or red when fouled out.
- **RT badge** — canonical `rtBucket.js`: `formatRtDisplay()` for the letter, `getRtColor()` for the fill. Renders empty when RT is unknown; never guesses a band.
- **Four bars** — PTS/20, REB/10, AST/10, DEF% with an 80 threshold. Green while filling, brand blue at max, with a `currentColor` glow when maxed. Eased by a 0.5s CSS `width` transition between emitted values.
- **Status strip** — flame (`MO ≥ 4`) / snowflake (`MO ≤ −4`), `FOUL TROUBLE` at 4 fouls, `FOULED OUT` when out, plus five foul pips.
- **Tags** — `IN` on a sub's first frame; `◆ TOP` on the spotlight.

`MO_GLYPH_THRESHOLD` is 4 on the ±5 scale, matching the box-score convention (`gameScene.js:221`). MO is a **binary threshold read per frame and never interpolated.**

### 5.4 Spotlight

`◆ TOP` migrates to the highest `calculatePotgPoints()` score **among the ten players currently on the floor** — the canonical POTG formula from `potg.js`, no local mirror. On-court-only is intentional: the marker is a resting place for the eye during playback, not a game-wide award, and the real POTG is computed independently by the completion popup from the finalized document.

### 5.5 Lead worm

An SVG margin chart above the rows: home above the axis, away below, gradient-filled to the axis, dot at the current margin, and a `TIED` / `ABBR +N` label. Vertical scale is `max(6, |largest margin|)`, so blowouts and one-possession games both read.

### 5.6 Phases

| Phase | Treatment |
|---|---|
| `pretip` | `STARTING LINEUPS · TIP-OFF` label, 0-0, empty bars. Skipped on Sim Rest Of Game. |
| `live` | Normal playback. |
| break | Rows/bench/ticker blur to `blur(3px) brightness(.42)`; `END Qn` card with both scores and a top-performer line. |
| `final` | `FINAL` stamp, then dissolve → completion popup. |

### 5.7 Reduced motion

`prefers-reduced-motion: reduce` fast-forwards playback (live frames ~40ms, holds ~400ms), disables the bar transition, the spotlight pulse, the flame flicker and the fade-in, and removes the dissolve delay.

---

## 6. Pacing

Seven constants at the top of `simGamePresentation.js`, tabulated with their effects in [`Tunable_Constants.md` § Sim Game Experience](../11_Design_Systems/Tunable_Constants.md).

Per-turn hold is `QUARTER_MS ÷ turns-in-quarter`, clamped to `[FRAME_MIN_MS, FRAME_MAX_MS]`. At the observed 40–80 turns/quarter that lands around 225–450ms — inside the clamp, so the clamps are safety rails rather than active dials.

`LINEUP_CHANGE_MS` overrides the normal hold on any frame where a player carries `sub` or `out`, so foul-out swaps read. Because `out` persists for every frame a fouled-out player remains in the lineup before the swap lands, a foul-out can hold across more than one consecutive frame.

**Whole game ≈ 80–85s.**

---

## 7. Moments ticker — specced, not built

The design called for a sparse ticker (5–8 `RUN` / `HEAT` / `FOUL` / `LEAD` moments per game). It was **tabled before the first build.**

What exists today:

- Every frame carries `ticker: null`.
- `.ticker` renders as a **fixed 44px empty slot** so that adding moments later cannot reflow the layout.
- The prototype's tag/colour treatment survives at `projects/Sim Game Experience Files/sim-presentation.js` and was never ported.

Building it means deriving moments client-side from `turns[]` (`result_type`, score runs, lead changes) plus a selection rule. Note the constraint: during `full_sim` the backend's announcement generation early-returns `[]`, so **no announce text exists on the sim path** — there is nothing to render, only something to derive. Any derivation must respect UESS: classify from emitted turn facts, never invent game state.

---

## 8. Skip

A click anywhere on `.sgp-root` during playback cancels the pending frame timers, jumps to the final frame, holds `FINAL_MS`, and hands off to the completion popup.

**This is undocumented in the UI and has no affordance** — no cursor change, no label, no hint — and it contradicts the "no skip in v1" design decision. It is recorded here as current behaviour pending a decision to remove it, or to give it a visible control.

Known wrinkle: the handler clears *all* pending timers, including the finish timer it queued, so repeated clicking re-arms the hold rather than accelerating it.

---

## 9. Key files

**Frontend**

- `js/phaser/bootGame.js` — `handleSimFullGame()`, orchestration and act sequencing
- `js/phaser/utils/simTimelineAssembler.js` — `buildSimTimeline()`, turns → frames
- `js/phaser/utils/simGamePresentation.js` — `showSimGamePresentation()`, Act 2 overlay + playback + injected CSS
- `js/phaser/utils/preGameExperience.js` — Act 1 (`displayOnly`), `showPreppingSimCover()`, `showOpaqueSimBridgeCover()` / `clearOpaqueSimBridgeCover()`
- `js/phaser/utils/gameCompletionPopup.js` — the handoff target, unchanged by this system
- `js/phaser/utils/matchupsUiShared.js` — `readableTeamPresentationColor`, positions, tile DNA
- `js/phaser/utils/gameSfx.js` — pregame bed (looped through both acts, faded at Act 2 finish)
- `js/shared/potg.js` — `calculatePotgPoints()`, canonical spotlight scoring
- `js/shared/rtBucket.js` — canonical RT letter grade + colour
- `static/court.html` — host page, scoreboard markup, `#app-grid` layout constraints

**Backend**

- `models/game_manager.py` — `_append_turn()`, per-turn stamps
- `utils/shared.py` — `summarize_game_state()`, player `rt`
- `api/api.py` — `/api/simulate-quarter`

---

## 10. Acceptance criteria

- Sim Full Game: bridge → Act 1 reveal → `Tip Off` → veil holds until the sim finishes → Act 2 → completion popup. No spinner and no "Simulating Qn" text ever visible.
- Sim Rest Of Game: `PREPPING SIM` veil → Act 2 joining at the current quarter, with carried score and cumulative stats and no replay of played quarters.
- The scoreboard clock, score, quarter and shot clock track the broadcast, not the finished game.
- Team fouls reset at each quarter break; timeouts decrement when they are actually spent.
- Reconciliation logs clean; any drift snaps to the emitted value and is reported.
- Playback survives 1280×720 with no row clipped beneath the scoreboard.
- Every failure path (Act 1 fetch, assembler, presentation) degrades to the completion popup rather than a stuck screen.
- No presentation code writes game state.
