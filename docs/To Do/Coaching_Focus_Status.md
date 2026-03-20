# Coaching focus — implementation status

**Purpose:** Per-leaf coaching focus (`training.html` radio `value`), as wired today in **`BackEnd/models/training_execution_v2.py`** (and play/defense training in the same module).  
**Prerequisite:** `parse_coaching_focus()` normalizes UI strings so `sub_option` matches these `value`s (Step 1 wiring).

**Legend**

| Status | Meaning |
|--------|--------|
| **Implemented** | Intended effects for this choice are applied in training execution (may still differ from full prose in `Training_System.md`). |
| **Partial** | Some effects exist; other doc-described effects are missing or only partially covered (called out in notes). |
| **Not implemented** | Code paths are stubs (`return False` and/or “handled separately” with no other handler); selection has no real mechanical effect beyond being stored on the report. |

**Global gap (not tied to one focus):** `momentum_score` coaching-focus amplifier is commented **TODO** (~507–509 in `training_execution_v2.py`); no focus currently applies it.

---

## Authoritarian

| # | UI label | `value` | Status | What the code actually does |
|---|----------|---------|--------|-----------------------------|
| 1 | Discipline | `authoritarian-discipline` | **Implemented** | **`_should_amplify_player_attr`:** amplifies drill gains on **BH**. **`_should_amplify_team_attr`:** amplifies **fight**, **discipline** when those team attrs receive training points (via drill multipliers → `_apply_team_training_points`). Focus multiplier: random 1.5–1.8× on qualifying gains (`_apply_player_training_points` / team apply). |
| 2 | Rebounding | `authoritarian-rebounding` | **Implemented** | Amplifies **RB** (player) and **rebound_modifier** (team), same multiplier pattern as above. |
| 3 | Execution | `authoritarian-execution` | **Implemented** (efficiency only) | **`apply_play_defense_training`:** one random **1.5–1.8×** per session scales integer **effectiveness** gains on **set plays** (`_apply_offense_play_training`) and **Man** defense (`_apply_defense_training`). Motion/zone plays get base gains only. **`_should_amplify_*`** stays `False` here—play path is separate. Momentum/cloaking are not trained by install points. |
| 4 | Teamwork | `authoritarian-teamwork` | **Implemented** (drills + install) | **Drills:** amplifies **PS**, **IQ** (`_apply_player_training_points`). **Install training:** one random **1.5–1.8×** per session on **effectiveness** gains for **`play_type == motion`** and zone defenses (`2-3`, `3-2`, `1-3-1`) — same pattern as Authoritarian / Execution for set + Man. |

---

## Systems Coach

| # | UI label | `value` | Status | What the code actually does |
|---|----------|---------|--------|-----------------------------|
| 5 | Offense | `systems-coach-offense` | **Implemented** | **`_should_amplify_team_attr`:** amplifies **offensive_efficiency** install gains. **`apply_play_defense_training`:** random **1.5–1.8×** multiplier on **offense `playPoints`** (before `_apply_offense_play_training`), so offensive play effectiveness gains scale up. Player-attr path intentionally **False** (handled via team + plays). |
| 6 | Defense | `systems-coach-defense` | **Implemented** | Same pattern: **defensive_efficiency** + **defense `playPoints`** multiplier before `_apply_defense_training`. |
| 7 | Fast Breaks | `systems-coach-fast-breaks` | **Partial** | **`_should_amplify_team_attr`:** amplifies **fb_efficiency** and **fb_opp_modifier** from team drill installs. **No** extra Systems-Coach-specific weighting of fast-break *plays* beyond the generic offense/defense play pipeline. |
| 8 | Press / Trap | `systems-coach-press-trap` | **Partial** | **`_should_amplify_team_attr`:** amplifies **pt_efficiency** and **pt_opp_modifier**. **No** focus-specific press/trap play distribution beyond generic training. |

---

## Player Maximizer

| # | UI label | `value` | Status | What the code actually does |
|---|----------|---------|--------|-----------------------------|
| 9 | Top 3 Attributes | `player-maximizer-top-3` | **Implemented** | In `_apply_player_training_points`, per player, ranks trainable anchor attrs (excl. CH, EM, MO, NG), amplifies gains to **top 3** with same focus multiplier. |
| 10 | Attributes 4–6 | `player-maximizer-attributes-4-6` | **Implemented** | Same as above for **4th–6th** highest trainable attrs. |
| 11 | Custom Attributes | `player-maximizer-custom` | **Not implemented** | **`_should_amplify_*`:** explicit TODO / `False`; no backend contract for user-selected attrs; UI exposes the radio but there is no parallel “custom list” in training execution. |
| 12 | Opportunity | `player-maximizer-opportunity` | **Not implemented** | **`_should_amplify_*`:** `False`; comment references set play / motion shot scoring “handled separately” — **no** implementation found for this `sub_option`. |

---

## Culture Builder

| # | UI label | `value` | Status | What the code actually does |
|---|----------|---------|--------|-----------------------------|
| 13 | Inspire | `culture-builder-inspire` | **Implemented** (with caveat) | **Dedicated block:** all players get **EM** and **MO** bumps `random.randint(1, 2)` each (capped 100 / 10). **`_should_amplify_team_attr`:** **team_chemistry** gains amplified. **`_should_amplify_player_attr`:** also lists EM/MO — but **EM/MO are not** in `TRAINABLE_PLAYER_ATTRS`, so drill loops never apply extra focus mult to EM/MO; the **flat block** is what implements the doc-style EM/MO bump. |
| 14 | Confidence | `culture-builder-confidence` | **Not implemented** | **`_should_amplify_*`:** `False`; comment only; no play/man-defense hook. |
| 15 | Community Engagement | `culture-builder-community` | **Partial** | **Dedicated block:** all players **EM** +1–2. Comment: crowd min/max for next home/away — **not** implemented in this module (no game-creation hook found here). |
| 16 | Teamwork | `culture-builder-teamwork` | **Partial** | **`_should_amplify_player_attr`:** **PS** only. **`_should_amplify_team_attr`:** no **team_chemistry** line for this focus (contrast **Inspire**). **Not** implemented: motion / zone defense effectiveness boosts from doc. |

---

## Summary counts

| Status | Count | Focus keys |
|--------|-------|------------|
| Implemented | **9** | discipline, rebounding, execution (set + Man), **teamwork** (motion + zone install gains + PS/IQ drills), systems offense, systems defense, player top-3, player 4–6, culture inspire* |
| Partial | **4** | systems fast breaks, systems press/trap, culture community, culture teamwork |
| Not implemented | **3** | player custom, player opportunity, culture confidence |

\*Inspire = implemented for EM/MO block + CH amplify; crowd N/A.

---

## References

- UI values: `FrontEnd/static/training.html` (coaching section).  
- Parsing: `parse_coaching_focus()` in `training_execution_v2.py`.  
- Amplifier tables: `_should_amplify_player_attr`, `_should_amplify_team_attr`; Culture special blocks in `apply_training_points`; Systems play pool: `apply_play_defense_training`.  
- Design doc: `docs/docs_1_systems/06_GMO_Supporting_Systems/Training_System.md` (may describe effects not yet built — use this status doc for code truth).

*Last reviewed against codebase in a full sweep of `training_execution_v2.py` (coaching-focus-related paths only).*
