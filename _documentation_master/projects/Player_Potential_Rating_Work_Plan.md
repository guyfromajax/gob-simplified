# Player Potential Rating — Work Plan

**Status:** Ready to implement
**Depends on:** Player Attribute Recalibration (closed, `Z-Completed/`)

## What this adds

A per-player **`potential_factor`** — a career-static scalar, uniform in ±15%, drawn independently of entry tier and of `ch_seed`. It scales the RT target the offseason event solves for, so it is a real development mechanic rather than a cosmetic label, and it is displayed to the user as a projected letter grade alongside his current one (`C+/A+`).

**Why it exists.** A clean 2× projection is a perfect read of entry tier — six tiers map to exactly six letters, so every Average player in the league would show the same grade and the display would leak a hidden variable. A per-player factor blurs the tiers: two Average recruits can show `C+` and `B`, and a high Good is indistinguishable from a low Great.

**Why it stays independent of peaks.** Peaks remain hidden and unpredictable. Visible potential and hidden peaks are orthogonal, which gives four combinations — high-projection players who never peak and disappoint, low-projection players who roll three peaks and become the story of a franchise. The magic survives precisely because it is not what is displayed.

## Decisions locked

| Decision | Value |
|---|---|
| Band | ±15%, uniform, exposed as a tunable constant |
| Distribution | Uniform, not bell-curved — busts and gems are as common as median players |
| Display | A single letter, current and potential together: `C+/A+` |
| Ratchet | If current ever exceeds potential, displayed potential becomes current |
| Visibility | Every player, always — not gated behind scouting |
| Retroactive | Yes, applied to the existing migrated pool |
| Basis | `jh_anchor × 2.0 × potential_factor`, using the **tier anchor**, not the player's own JH rating |

Letter scale (already implemented, `rt_display.rt_letter_grade`): `<30 F` · `30-39 D` · `40-49 C` · `50-59 C+` · `60-69 B` · `70-79 B+` · `80-89 A` · `90-99 A+` · `100+ A++` — the `D` band was added after this plan was first written.

Resulting projection spread:

| Tier | base | ±15% | letters spanned |
|---|---|---|---|
| Poor | 40 | 34-46 | D – C |
| Below Average | 50 | 43-58 | C – C+ |
| Average | 60 | 51-69 | C+ – B |
| Good | 70 | 60-81 | B – A |
| Great | 80 | 68-92 | B – A+ |
| Elite | 100 | 85-115 | A – A++ |

---

## Phase 1 — Generation

Draw `potential_factor` at player generation: uniform in `[1 − POTENTIAL_FACTOR_BAND, 1 + POTENTIAL_FACTOR_BAND]`, default band 0.15. Independent of `entry_tier` and of `ch_seed` — assert that independence in a test, the same way `ch_seed ⊥ entry_tier` is asserted today.

Store **top-level**, alongside `entry_tier` and `position_intent` — not inside the `development` subdoc.

Apply to every generation path: pool generation, recruit generation, walk-on generation.

Add `POTENTIAL_FACTOR_BAND` to `Tunable_Constants.md` under **Levers**, described in gameplay terms: *how much two players of the same tier can differ in projected ceiling — at 0.15, an Average recruit projects anywhere from C+ to B.*

## Phase 2 — Persistence

This is the phase that has already cost this project two days once. `potential_factor` must survive every path that `entry_tier` had to be fixed for:

- the season FRD write
- the pool → FPD carry at franchise init
- the `finish_season` forward-copy list
- `team_builder_roster._build_fpd_doc`
- the `stat_updater` finalize_game safety net

**Deterministic fallback for legacy players.** Any player without the field derives it from a hash of `player_id`, so the same player yields the same value on every read rather than re-rolling per session. Log when the fallback fires.

**Test:** a generated recruit round-trips FRD → FPD → rollover with `potential_factor` unchanged.

## Phase 3 — Wire into development ✅ SHIPPED

The offseason target became (`develop_one_offseason`, `player_development.py`):

```
_compress_rt( jh_anchor × ladder_multiple × f × potential_factor )
```

Nothing else about the event changed. `potential_factor` threads from `develop_rollover` (resolved stored-or-`player_id`) → `develop_one_offseason(..., potential_factor=)`. Default 1.0 keeps the JH-init/CPU-sim harness pf-neutral, so the four invariants (+ preserves-shape, +partA) still pass unchanged.

**Shape attractor — confirmed no desync.** `potential_factor` scales the scalar `target_rt`, hence scales `k` in `target_a = profile[a] × k`; the profile *ratios* are untouched. Same player at pf 1.0 vs 1.15: RT +7 (Average) / +11 (Elite), max attribute-share deviation **0.09–0.15%** (integer rounding). A 1.15 player reaches a higher level with the same shape.

**Ceiling — `RT_SOFT_CAP` engages; decision accepted.** Elite × 3-peak × 1.15 targets `50 × 2.6 × 1.15 = 149.5`, compressed to **137.3** (asymptote 138) — the target never reaches 149. Realistic (natural-peak) Elite population: pf moves p90 `104→108`, ≥130 rate **0.03%** (~1 in 3,000). A <2% tail of the *forced*-3-peak+top-pf cohort has *achieved* RT (recomputed from attributes) reaching ~138–150 — a pre-existing recompute-from-attributes overshoot, only slightly heavier under pf, not introduced by it. Accepted as "generational players should be exceptional." If a hard ~130 is ever wanted, the lever is lowering `RT_SOFT_CAP` or compressing achieved RT — a separate follow-up, not this phase.

**Stacked-variance (measured, senior RT p10/p50/p90, f dormant, pf live):** Poor 31/36/43 · BelowAvg 38/45/54 · Average 46/54/64 · Good 54/63/75 · Great 62/73/86 · Elite 77/91/108. Medians stay cleanly ordered; pf widens each adjacent-tier tail overlap ~2–3 RT on top of the peak-driven baseline (peaks dominate the spread). The feared "Average = F to A++" was min/max of simultaneous extremes; the realistic Average band is C–B.

## Phase 4 — Display

Projected potential is a pure function of stored fields, so it needs no history and works for any class year:

```
projection = JH_ANCHOR_BY_TIER[entry_tier] × 2.0 × potential_factor
displayed_potential = max(projection, current_RT)
```

The `max()` implements the ratchet **without a write** — it is computed at render time, so it self-corrects and cannot desynchronise from the player's actual rating.

**Surfaces — this list is exhaustive.** Potential appears on **Team Roster pages**, the **Roster tab of the Franchise Command Center**, and **all Recruiting pages and tabs**. Every other surface shows the current rating alone. Do not extend it to the wider display-sweep inventory.

The column header stays **`RT`** in all cases — no header change anywhere.

Format is `current/potential`, e.g. `C/C+`, `F/C+`, `A/A++`.

**Expose the projection as a computed field on the player payload** rather than deriving it in each view, so the formula lives in one place and front-end placement stays a presentation decision.

Front-end layout and styling are out of scope for this work — wire the data and the three surfaces above, nothing further.

**Known behaviour worth expecting:** a 3-peak player will exceed his projection, so the ratchet engages and his display converges toward `A+/A+`. That reads correctly — he has met his ceiling — but it means high performers show no headroom late in their careers. Confirm that is the intended feel before shipping.

## Phase 5 — Retroactive pool write

Write `potential_factor` to the 1,536 migrated pool players.

**Persist the value each player is ALREADY displaying — `resolve_potential_factor(player_id, None)` — NOT a fresh uniform draw.** Phase 4 ships the projected ceiling on the base-team roster pages (surface 1b), which read the pool; with no stored `potential_factor` those pages already resolve the deterministic player_id-hash value. If Phase 5 drew a *new* random factor, every pool player's displayed ceiling would silently change at backfill, and a user who scouted a team pre-franchise would see different numbers afterward. The hash fallback is verified uniform and in-band across 20,000 ids ([potential_factor tests]), so persisting it loses nothing versus a fresh draw — and it keeps the display stable across the backfill. Same `warn=False` path the read side uses.

**This is a small additive `$set`, not a re-migration.** It does not touch attributes, height, weight, year, or ratings, and it is idempotent — do not restore the backup or re-run `regenerate_universal_pool.py`. Dry-run and report the manifest before committing, same discipline as before. Verify post-write that the stored value equals what the page showed pre-write (they must be identical by construction).

**RE-ARM THE ALARM (required step, not optional).** The Phase-4 display read paths resolve `potential_factor` with `warn=False` — correct *only while the pool is un-backfilled*, when every pool row legitimately hits the fallback and a per-player warning would flood the log. Once this backfill lands, the pool carries the field, so a fallback on a pool read no longer means "expected legacy row" — it means a genuine dropped-field regression on some write path, i.e. the `entry_tier` failure with the alarm switched off. As part of this phase, **flip the display-side resolution back to warning** — either restore `warn=True` on `potential_rt_for_player`'s resolve, or narrow it to a rate-limited / once-per-id warning so a real gap surfaces without flooding. Do NOT leave `warn=False` as a permanent suppression. (Legacy *franchise* saves that predate the field may still warn on display until they lazy-backfill at rollover — acceptable, or covered by the narrowed form.) Track this as a checklist item so the suppression is provably temporary.

## Phase 6 — Validation

Short — one season plus rollover, not four. The growth model and its invariants are unchanged; what needs confirming is that the new scalar behaves.

- Senior RT by tier now spans a range rather than a point. Report p10/p50/p90 per tier and confirm the **median** still lands on 40/50/60/70/80/100.
- The ≥100 rate will move. Report it on both bases — pool and roster — since they differ by 25% and the lock is currently ambiguous about which it refers to.
- Confirm `potential_factor ⊥ entry_tier` and `⊥ ch_seed` on live data, not just in the generator.
- Confirm the four in-season and full-cycle invariants still pass.
- Report what share of players end their careers above their projection, at it, and below. If almost nobody falls short, the factor is doing less work than intended.

---

## Deliberately not in scope

**Per-attribute potential** — a player with a great shooting ceiling and a poor handle. Genuinely richer, and the kind of thing that makes scouting interesting, but it interacts with the shape attractor in ways that need designing rather than bolting on.

**Scouting-gated visibility** — showing coarser grades for unscouted players, making accurate potential a resource. Changes recruiting from a sorting exercise into a decision. Worth revisiting once the flat version has been felt in play.

**Per-rung jitter** — letting the factor vary slightly by offseason so individual years feel less mechanical. Peaks already supply the surprise; add only if development reads as too smooth.
