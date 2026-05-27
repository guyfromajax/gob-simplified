# `offensive_state` Hardening — Discussion Notes

**Status:** Open question / future project
**Created:** 2026-05-27
**Context:** Surfaced during the after_steal Fast Break UESS migration. The migration broke twice because the new resolver didn't set `game_state["offensive_state"]` on certain code paths (MAKE-no-foul, then MISS-no-foul). Both produced perpetual-loop bugs (BIP → FB → BIP → FB → …).

---

## What `offensive_state` is

The **canonical "what type of turn fires next" routing signal** stored on `game.game_state`. Read by the turn-dispatching machinery to choose the resolver for the upcoming turn.

| Valid values | Routes to |
|---|---|
| `"HCO"` | Half-court offense turn |
| `"HCT"` | Half-court trap setup |
| `"FCP"` | Full-court press setup |
| `"FAST_BREAK"` | Fast break turn |
| `"FREE_THROW"` | Free throw turn |
| (default fallback) `"HCO"` | Most consumers default to HCO if missing |

**Notably NOT valid:** `"OREB"`, `"DREB"`, `"BASELINE_INBOUND"`. Those transitions are handled by parallel mechanisms (see below).

---

## Architectural rule (existing, documented in code)

[`BackEnd/models/turn_manager.py:1671-1687`](../../BackEnd/models/turn_manager.py#L1671-L1687):

> Handlers (shot_manager, phase_resolution, etc.) are the source of truth for offensive_state. They explicitly set offensive_state when needed. `next_play_type` is informational only (for frontend display/logging), not for routing. **If a handler doesn't set offensive_state, that's a bug in the handler.**

In-code documentation. **Not enforced** by any contract / type / assertion.

---

## Consumers (who reads it)

| Location | Purpose |
|---|---|
| `main.py` | Timeout resume, quarter setup — sets initial state |
| `turn_manager.py:1204, 1620, 4020, 4240` | Turn dispatch / validation |
| `utils/transition_event_detector.py` | Validates transitions between turns |
| `utils/shared.py` | Shot resolution paths |
| `models/game_manager.py` | Post-turn state propagation |

---

## Parallel `pending_*` flags (the source of perceived fragmentation)

| Flag | Purpose | Why not just `offensive_state` |
|---|---|---|
| `pending_oreb` | Chains an OREB putback/kickout turn | Carries rebounder object + from_block flag, not just a type |
| `pending_dreb_fb_play_key` | DREB-after-miss FB cascade | Carries the FB play key (RR/CR/Triangle) for the cascading FB |
| `situational_force_foul_pending` | Q4/OT situational logic | Carries situational context |
| `pending_terminal_ft` | End-of-quarter FT scenarios | Carries quarter-end context |

**Pattern:** when a transition needs to **carry data** beyond just "next type is X," it gets a dedicated `pending_*` flag instead of cramming structure into `offensive_state`.

---

## Is it flawed?

**Yes, in a real but bounded way.**

| Symptom | Severity |
|---|---|
| Handler authors must remember to set `offensive_state` on every exit path. Forgetting = perpetual-loop bug (what bit us in after_steal MAKE and MISS paths) | High when it happens, but easy to diagnose |
| No type-system or runtime contract enforces "you must set offensive_state". The in-code comment is documentation, not enforcement | Moderate — the rule is informal |
| Multiple parallel signals (`offensive_state` + various `pending_*` flags) mean a developer adding a new turn type has to know which signal applies | Moderate — learnable but not obvious |
| Some legitimate transitions (OREB chain, FB cascade) require BOTH a `pending_*` flag AND a careful decision about whether to touch `offensive_state` | Moderate — got us with "do we set offensive_state for OREB? No, but we need to know not to" |

**Not a fundamental flaw** — the architecture works for the main flows. Most bugs found have been in newly-migrated edge paths, not in core flows.

---

## Hardening options (ranked by effort)

| Option | Effort | What it fixes |
|---|---|---|
| **1. Assertion / log warning** when a turn resolves without `offensive_state` being touched | Small (~few lines) | Catches missing-update bugs in logs |
| **2. Transition validator** check that the previous turn's resolver set `offensive_state` to a value consistent with `next_play_type` | Medium | Catches inconsistencies between the two routing signals |
| **3. Refactor into a single `TurnTransition` object** carrying both type and any pending data | Large | Eliminates the parallel-flag fragmentation |

**Recommendation: Option 1.** Don't refactor unless the bug surface keeps biting. The defense-in-depth assertion catches future bugs of the same shape early without architectural disruption.

---

## Known incidents (this list will grow)

| Date | Bug | Cause | Fix |
|---|---|---|---|
| 2026-05 | after_steal FB MAKE → BIP → FB → BIP → FB loop | New resolver didn't set `offensive_state` on MAKE-no-foul path; stayed at `"FAST_BREAK"` from steal | Set `offensive_state = determine_defensive_pressure_type()` (Option B from discussion) |
| 2026-05 | after_steal FB MISS no-foul: latent loop risk + no rebound chain | New resolver placeholder `next_play_type="BASELINE_INBOUND"` was wrong; `offensive_state` left at `"FAST_BREAK"`; no rebound determined | Compute bounce_spot + determine_rebounder; OREB → `pending_oreb`; DREB → `offensive_state="HCO"` + possession flip |

---

## Related code references

- `BackEnd/models/turn_manager.py:1671-1687` — the architectural rule comment block (canonical contract documentation)
- `BackEnd/models/turn_manager.py:5135-5154` — `determine_defensive_pressure_type()` (canonical helper for post-MAKE pressure type)
- `BackEnd/models/turn_manager.py:4041-4044` — OREB putback pattern (Option B reference)
- `BackEnd/engine/rim_runner_fast_break.py:862, 971, 1020, 1198, 1202, 1235` — Rim Runner's explicit `offensive_state = "HCO"` pattern
- `BackEnd/engine/after_steal_fast_break.py` — newest resolver, includes both the MAKE pressure-type set and the MISS rebound chain
