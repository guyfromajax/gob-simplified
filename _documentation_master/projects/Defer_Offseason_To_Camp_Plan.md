# Defer Offseason Development to Training Camp — Work Plan

**Goal.** Make Training Camp *feel* like the moment a player develops. Offseason attribute gains are currently applied at `finish_season` (week 36) and are visible before the user runs camp. Move the offseason **attribute apply** to the **Week-1 TC "Run Training"** step so the user sees offseason + camp as one combined jump at camp.

**Status.** Design agreed (this thread). Nothing implemented.

---

## Design decision — Option A (defer), not a display mask

| | Option A — defer apply to TC (CHOSEN) | Option B — apply at finish, hide display |
|---|---|---|
| Live value during offseason window | = end of Season A (67) | = developed (70), user sees masked 67 |
| Divergence between value & display | **none** — single source of truth | real; shadow snapshot + reveal flag |
| Leak risk | none | any unmasked read leaks the gain |
| SS&S | display always derived from true state | maintains a shadow state |

Option A is chosen: no mismatch window exists because the live value never diverges from what the user sees.

**The pipeline is order-dependent (load-bearing):** offseason → camp. Camp trains *on top of* the offseason profile (`SC 67 →[offseason] 70 →[camp] 72`). Deferring only moves *when* the offseason write lands; the order and the final values are byte-identical to today.

---

## Current vs target flow

```
TODAY:
  Week 36  finish_season:  season++, year advance, graduate, recruiting, OFFSEASON APPLY
  Week 1   Run Training:   camp (trains on already-developed profile)

TARGET:
  Week 36  finish_season:  season++, year advance, graduate, recruiting        (NO attr apply)
  Week 1   Run Training:   OFFSEASON APPLY  →  camp   (sequential, once)  →  reveal
```

## What moves / what stays

| Stays in `finish_season` (=new-season init, wk 36) | Moves to `/franchise/run-training/user`, **week 1 only** |
|---|---|
| `season++`, `advance_year` (`:16608/16644/16705`) | returning-player `develop_rollover` (`:16667`) |
| graduation (`_is_graduating_year`, `:16642`) | recruit JH→FR `develop_rollover` (`:16727`) |
| recruiting / signings structure | `_build_offseason_report_line` generation |
| (roster shows correct **years** immediately) | then existing camp `execute_training` (unchanged) |

Benign accepted window: after wk-36 transition and before wk-1 Run Training, players show correct **year** with **un-developed attributes** (a sophomore with freshman-end attributes). This is intended — it's what makes the camp reveal an event.

---

## Phases

**Phase 1 — Relocate the apply.**
- In `finish_season`: keep year-advance/graduation/recruiting; **remove** the two `develop_rollover` calls (returning `:16667`, recruit `:16727`) and the offseason-report build. Persist whatever inputs the deferred step needs (see Invariants).
- In `/franchise/run-training/user`: on **week 1 only**, before camp, run the offseason `develop_rollover` for every roster player (returning + newly-signed recruits), then camp, then persist.

**Phase 2 — Idempotency + determinism.**
- Guard the offseason step to fire **exactly once** per player per season (mirror the `cpu_autotrain_week` marker pattern) — re-open / retry must not double-apply.
- Seed the offseason rng deterministically per player+season so a retry reproduces the same result.

**Phase 3 — Presentation.**
- Offseason report merges into the Week-1 TC report (one combined "development" story). Keep §8: no `peak_count` / remaining peaks / `ch_seed` leak; `broke_out` stays keyed on visible RT.

**Phase 4 — CPU parity.**
- Decide whether CPU teams defer too (they auto-train wk 1 anyway). For league consistency the offseason should apply to CPU rosters at their wk-1 autotrain, same pipeline — confirm `cpu_autotrain_week` path also runs offseason-then-camp.

**Phase 5 — Rollout.** Stage on gob-staging → run one full season transition → verify reveal + values → commit/deploy.

---

## Invariants / must-not-break

1. **Pipeline order** — offseason must run before camp in the same handler; never camp-then-offseason.
2. **Values unchanged** — final Week-1 attributes must equal today's (offseason-then-camp). Poison-test, don't diff exact draws.
3. **Inputs available at TC** — the returning path uses the just-finished season's training accumulator (`_season_alloc`, quality-half; dormant but wired). Ensure it (and `entry_tier`, `potential_factor`, `development` subdoc) survive from finish_season to Week-1 Run Training.
4. **Run once** — offseason apply is idempotent per player/season.
5. **Year vs attributes decoupled** — nothing may assume attributes match the (already-advanced) year during the window.
6. **§8** — presentation exposes observable outcomes only (RT delta, breakout, position change).

## Risks / open questions

- **Does anything in the wk-36→wk-1 window need developed RT?** (offseason recruiting valuations, roster RT displays). If yes and it must reflect post-development, revisit — but current read is the window is display-only. **Verify before Phase 1.**
- **CPU timing** (Phase 4) — must not double-apply if CPU autotrain and this share code.
- **Save migration** — mid-transition franchises already past finish_season this season: one-time, define behavior (likely: already-applied, skip defer this cycle).

## Test plan

- Full-cycle: careers through a season transition land on identical Week-1 attributes vs today (offseason-then-camp).
- Idempotency: double-fire the Week-1 handler → no double-apply.
- Reveal: player attributes/RT are the Season-A-end values after finish_season and before Run Training; equal offseason+camp after.
- §8: report emits no peak/CH-derivable fields.

## Files

- `BackEnd/api/franchise_routes.py` — `finish_season` (`:16545`), `/franchise/run-training/user` (`:14788`), `_build_offseason_report_line` (`:16498`), `cpu_autotrain_week` path.
- `BackEnd/utils/player_development.py` — `develop_rollover` (unchanged; called from the new location).
