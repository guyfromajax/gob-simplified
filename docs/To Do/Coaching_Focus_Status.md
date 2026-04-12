# Coaching focus — implementation status

**Purpose:** Per-leaf coaching focus (`training.html` radio `value`), as wired today in **`BackEnd/models/training_execution_v2.py`** (and play/defense training in the same module). **Community Engagement** also touches **`franchise_routes`** (FTD pending) and **`home_crowd` / `api` init-game** for franchise GP only.  
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
| 1 | Discipline | `authoritarian-discipline` | **Implemented** | **`_should_amplify_player_attr`:** amplifies drill gains on **BH**. **`_should_amplify_team_attr`:** amplifies **fight**, **discipline** when those team attrs receive positive training points. Focus multiplier: random 1.5–1.8× on qualifying gains. Any Authoritarian archetype also adds a flat per-session **discipline** bonus of `0 to +1`. |
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
| 11 | Custom (modal) | `player-maximizer-custom` | **Implemented** | **Franchise:** `GET /franchise/training-points` returns `custom_focus_roster` (rows sorted by max **RT** descending, includes `position_ratings`) + `player_maximizer_ranking_attrs`. Main PM UI is **Choose Attributes** (`player-maximizer-choose-attributes`); the modal’s **Custom** mode collects **three** distinct attrs per roster player (`coaching_focus_custom_by_player` on submit). API **rejects** bare `choose-attributes` (user must tap **Assign Focus Attributes** so payload sends a real leaf). **`normalize_coaching_focus_custom_by_player`** validates; **`_apply_player_training_points`** amplifies drill gains when `attr` is in that player’s triple. **Auto-train** skips choose + custom (no payload). |
| 12 | Positional Focus | `player-maximizer-positional-focus` | **Implemented** | Highest **RT** primary (ties **PG → SG → SF → PF → C**) maps to a fixed triple: PG→PS/BH/IQ, SG→SH/OD/AG, SF→SC/ST/AG, PF→RB/ID/ST, C→SC/ID/ST. Drill gains to those attrs use the same Player Maximizer multiplier (`positional_focus_attrs_for_player` in `training_execution_v2.py`). |
| — | Choose Attributes (UI only) | `player-maximizer-choose-attributes` | **N/A** | Opens modal; not a valid training leaf on submit. |

---

## Culture Builder

| # | UI label | `value` | Status | What the code actually does |
|---|----------|---------|--------|-----------------------------|
| 13 | Inspire | `culture-builder-inspire` | **Implemented** | See **Inspire (plain summary)** below (flat EM/MO + **team_chemistry** amplify only). |
| 14 | Confidence | `culture-builder-confidence` | **Implemented** | **`_should_amplify_player_attr`:** **CH** (conditioning, film study) and **FT** (free throws) drill gains use `random.choice([1.5, 1.6, 1.7, 1.8])` after CH’s 0.5 drill coeff. See **Confidence (plain summary)** below. |
| 15 | Community Engagement | `culture-builder-community` | **Implemented** | **Training (`training_execution_v2`):** all players **EM** +1–2 (flat block). **Franchise GP only:** sets **`pending_community_engagement`** on user FTD (`franchise_routes` `run_franchise_training`). **Home crowd roll:** consumed at franchise game start (`consume_franchise_community_engagement_for_matchup` in `home_crowd.py`, called from `/api/init-game` and the new-game `simulate-quarter` path); shifts the **Home Crowd System** weight band up/down vs actual home `team_chemistry`, Upper Bonus row when applicable; **both** teams pending CE → cancel. CPU: distant template `community_engagement` sets pending on CPU FTD. Single/tournament: no training → N/A. See **Community Engagement (plain summary)** below. |
| 16 | Team Building | `culture-builder-teamwork` | **Implemented** | **Dedicated block:** **team_chemistry** `+= random.randint(1, 3)` once per training (clamped 7–25). Any Culture Builder archetype also adds flat **fight** `+= random.randint(0, 1)` once per training. Radio **`value`** unchanged for API/back-compat. No drill multipliers, no PS / motion / zone play hooks. |

### Inspire (plain summary)

**What happens automatically (not from your sliders):**  
Every player gets **+2 to +5** to **EM** and **+1 or +2** to **MO** once per training when Inspire is selected (**EM** capped at 100, **MO** at 10). These bumps **do not** use the 1.5–1.8× focus multiplier.

**What Inspire *amplifies* (1.5×–1.8×, one random roll per session):**

| Kind | Attribute | Where it comes from in training |
|------|-----------|--------------------------------|
| Team | **team_chemistry** | Any training path that adds **team** chemistry (e.g. **Scrimmages**, **Free throws** / **Film study** fractional contributions, **Breaks** at 3–5). |

**Not amplified by Inspire:** player **CH** / **FT** (those are **Confidence**); play/defense install effectiveness; EM/MO beyond the flat block above.

### Confidence (plain summary)

Amplifies **CH** and **FT** from drills (1.5×, 1.6×, 1.7×, or 1.8× per session):

| Attribute | Where it comes from |
|-----------|---------------------|
| **CH** | **Conditioning** and **Film study** (CH’s normal **0.5×** drill coefficient on the rolled step, then focus mult). |
| **FT** | **Free throws**. |

No flat EM/MO block on Confidence; no **team_chemistry** focus mult on Confidence (contrast **Inspire**).

### Community Engagement (plain summary)

**In training:** +1–2 **EM** per player (anchors updated).

**Franchise next game (home crowd weights only — not team doc chemistry):** selecting this focus sets **`pending_community_engagement`** on the user team’s FTD. At the **start** of the **next** franchise game (or after a bye, the next game that season), the home crowd factor roll uses an adjusted band per **`Home_Crowd_System.md`** (shift **up** if user is home / beneficiary is home, **down** if user is away and floor not 7–10, **Upper Bonus** row when shifting up from the 21–25 tier). Pending is **cleared** for both teams in the matchup when the game is started. If **user and CPU** both had pending CE, shifts **cancel**. Remote CPU teams can get pending from **distant training** templates with `community_engagement: true` (regenerate templates script to populate Mongo).

---

## Summary counts

Leaf options above: **16** valid training leaves (four per archetype API block) + **Choose Attributes** (UI-only placeholder).

| Status | Count | Focus keys |
|--------|-------|------------|
| Implemented | **14** | **Authoritarian (4):** discipline, rebounding, execution (set + Man), teamwork (PS/IQ drills + motion/zone install). **Systems (2):** offense, defense. **Player maximizer (4):** top-3, attributes 4–6, custom, positional focus. **Culture (4):** inspire*, confidence†, community engagement§, team building‡ |
| Partial | **2** | **Systems (2):** fast breaks, press/trap |
| Not implemented | **0** | — |

\* **Inspire** — see **Inspire (plain summary)** above.  
† **Confidence** — see **Confidence (plain summary)** above.  
§ **Community Engagement** — see **Community Engagement (plain summary)** above.  
‡ **Team Building** — `culture-builder-teamwork`; flat +1–3 **team_chemistry** plus the shared Culture Builder flat **fight** bonus (row 16).

---

## References

- UI values: `FrontEnd/static/training.html` (coaching section).  
- Parsing: `parse_coaching_focus()` in `training_execution_v2.py`.  
- **Teamwork vs Team Building:** `COACHING_FOCUS_LEAF_DISPLAY_NAME` and `coaching_focus_leaf_display_name()` document and label **`authoritarian-teamwork`** (Authoritarian **Teamwork**) vs **`culture-builder-teamwork`** (Culture **Team Building**). Training reports include optional **`leaf_display_name`** on `coaching_focus` for stable UI copy.  
- Amplifier tables: `_should_amplify_player_attr`, `_should_amplify_team_attr`; Culture special blocks in `apply_training_points`; Systems play pool: `apply_play_defense_training`.  
- Design doc: `docs/docs_1_systems/06_GMO_Supporting_Systems/Training_System.md` (may describe effects not yet built — use this status doc for code truth).  
- **Community Engagement / home crowd:** `docs/docs_1_systems/05_GP_Supporting_Systems/Home_Crowd_System.md`; implementation `BackEnd/utils/home_crowd.py`, FTD pending in `BackEnd/api/franchise_routes.py` (`run_franchise_training` + distant training), game start in `BackEnd/api/api.py`.

*Last reviewed: Community Engagement marked implemented (FTD pending + home crowd consume); amplifier sweep `training_execution_v2.py`.*
