## Playbooks Page (**verified 2026-07-17**)

> Verified vs code: canonical `playbook_settings` shape + `fast_breaks` defaults (triangle 34 / rim_runner 33 / covert_release 33) and defense maps (`zone_23/zone_32/zone_131`, `man_normal/man_tight/man_loose`) match `initialize_playbook_settings`; normalization via `build_simplified_playbook_settings` (`playbook_settings_utils.py`); durable `locks` via `normalize_playbook_locks`; `slot_assignments` still present as compatibility output (not source of truth — `pc_order` is). **The canonical `playbook_settings` shape + seeded defaults are owned by `Mode_Init_System.md`; the derived likely-shot percentages are documented in the **"Likely Shot Percentages (Derived Output)"** section below.** This doc focuses on the **Playbooks page** persistence/normalization + franchise two-stage policy, and the player-facing shot-likelihood readout derived from those settings.

## Overview

The Playbooks page configures offensive and defensive weighting plus Playcall Center ordering.

**UI (redesign on `develop`):** D2-style editable tiles (3-across) under Offense / Defense tabs; enforced redistribution for Motion / Set / Man / Zone; Normalize chips for Fast Breaks / HC Traps; PCC badges derived from `pc_order` only; durable `locks`; live shot-weights via debounced `POST /api/playbooks/preview-shot-weights`; save toast `"Playbooks Saved"` (no confirm modal). Sort UI removed.

**Set Plays display order** (`compareSetPlaysForDisplay` in `common.js`):
- **While editing** on Playbooks: focus groups stay stable (`inside → attack → outside`), then `%` desc → CMD → name → API index. Tile order does not reshuffle on every % drag.
- **After Save Playbooks**, and on **read-only venues** (FCC / Set Lineup): `%` desc → focus → CMD → name → API index.

**Read-only venues (FCC playbooks summary + Set Lineup modal):** show items with `percentage > 0`, and also `percentage === 0` when the play is in `pc_order` for that side. 0% plays not on the call sheet stay hidden.

Primary frontend:
- `FrontEnd/static/playbooks.js`
- `FrontEnd/static/playbooks.html`
- `FrontEnd/static/css/playbook-tiles.css` (+ `playbook-cmd.css`, `playbooks.css`)

Primary backend:
- `BackEnd/api/gameplan_routes.py`
- `BackEnd/utils/playbook_settings_utils.py`

### CMD (effectiveness) display scale

Play CMD colors are shared across the Playbooks page, FCC playbooks summary, and Set Lineup playbooks modal:

| Band | Threshold | Class | Color |
| --- | --- | --- | --- |
| Good | ≥ 70 | `is-good` | `#4A90D9` (blue) |
| Mid | ≥ 40 | `is-mid` | `#34EC27` (green) |
| Low | < 40 | `is-low` | `#FFD700` (yellow) |

Blue ranks above green (OOTP-conditioned). Source of truth: `FrontEnd/static/css/playbook-cmd.css` + `getPlaybookCmdClass()` in `common.js`. Do not fork thresholds or hex values per screen.

## Current Identity Model

Offensive playbook persistence is now `play_id`-first, and the internal persistence model is the simplified canonical shape.

Current canonical storage shape:

```python
playbook_settings = {
    "motion": {play_id: percentage},
    "set_plays": {play_id: percentage},
    "fast_breaks": {"triangle": 34, "rim_runner": 33, "covert_release": 33},
    "hc_traps": {"standard_trap": 34, "straight_pressure": 33, "standard_diamond": 33},
    "man_defense": {defense_id: percentage},
    "zone_defense": {defense_id: percentage},
    "pc_order": {
        "offense": [play_id_1, play_id_2, ...],
        "defense": [defense_id_1, defense_id_2, ...]
    },
    "locks": {
        "motion": [play_id, ...],
        "set_plays": [play_id, ...],
        "fast_breaks": [id, ...],
        "hc_traps": [id, ...],
        "man_defense": [defense_id, ...],
        "zone_defense": [defense_id, ...],
    },
    "position_filters": {...},
    "even_distribution_all": bool,
    "_meta": {...}
}
```

Play-level metadata is stored on the team `plays` objects:
- motion plays use `motion_focus`
- set plays use `target_shooter`

### New-franchise user Playcall Center seed

Franchise initialization pre-populates `pc_order` only on the user team's FTD
row. Offense slots are, in order: `3-2 Motion`, `4-1 Motion`, `Base Post Play`,
`Movement Post Play`, `Iso`, `Pick & Roll - Entry Pass`, `Misdirection Three`,
and `Double Screen Three - Wing`. Defense slots are `Base Man`, `Deny Man`,
`Loose Man`, `2-3 Zone`, `3-2 Zone`, and `1-3-1 Zone`. CPU-team Playcall
Center orders remain empty at initialization.

The seed changes ordering only. It uses stable play/defense identity and leaves
the copied play metadata intact, so motion focus and set-play target shooter use
their catalog presets.

### Locks (durable)

`locks` marks plays exempt from enforced redistribution on the Playbooks redesign UI. They are **persisted** with `playbook_settings` (not session-only).

- Shape: per-section lists of locked ids (same id space as the percentage maps).
- Normalized by `normalize_playbook_locks()` in `playbook_settings_utils.py` (accepts lists or `{id: truthy}` dicts; resolves play names → `play_id` for motion/set).
- `GET /api/playbooks` returns `locks`.
- `POST /api/playbooks` persists `locks` from the save payload (Playbooks page includes lock toggles in the save body).
- Gameplay engines do not read locks; UI arithmetic only.

## Play Loading

`GET /api/playbooks` returns offense arrays with both:
- `name`
- `play_id`

The page uses:
- `play_id` for identity, persistence, and matching
- `name` for rendering

## Compatibility

The page and backend still tolerate old name-keyed and legacy-shaped data during rollout, but all internal persistence should normalize into the canonical shape above.

Normalization rules:
- old percentage maps keyed by play name are converted to `play_id`
- old split set-play buckets are merged into `set_plays`
- old `fast_break` maps are normalized to `fast_breaks`
- old `slot_assignments` are treated as compatibility input and normalized into `pc_order`
- old motion dropdown maps keyed by play name are normalized to `play_id` and resolved into play metadata

## Playcall Center Ordering

> This section covers only the **config side** — Playcall Center *membership + ordering* (`pc_order`) as set on the Playbooks page. The **in-game Playcall Center** tactical hub (live override UI, tempo/aggression/press-trap, defense cards) is documented in `../05_Features/Playcall_Center.md`; CPU/sim call selection is in `../05_GP_Supporting_Systems/Sim_Playcalling_System.md`.

`pc_order` is the only authoritative persistence model for Playcall Center membership and ordering. Tile PCC badges (`+ OFF` / `OFF · n`, `+ DEF` / `DEF · n`) are derived from `pc_order` index — there is no parallel checkbox selection state.

Implications:
- assigning a play from a tile badge appends to `pc_order.offense` or `pc_order.defense` (cap 8/side)
- removing a rail slot (or toggling an assigned badge) drops that id and renumbers badges live
- gameplay ordering should be restored from `pc_order` first
- `slot_assignments` may still exist as a compatibility output for older callers, but should not be treated as the source of truth

## Position Filters

Position filters currently store arrays of `play_id`.

They are still manually curated and legacy-shaped:
- `standard`
- `PG`
- `SG`
- `SF`
- `PF`
- `C`

They were updated to use stable `play_id` constants so renaming a play does not break filter membership.

## Default Seed Behavior

First-load offense percentages are seeded from a fixed starter offense set identified by `play_id`, not by play name.

That starter set still mirrors the earlier product behavior, but it is now rename-safe.

## Navigation to Play Details

Play Details navigation now prefers:
- `play_id`

and still includes:
- `play_name`

for compatibility fallback.

## Franchise Persistence Policy

Franchise mode now uses a two-stage persistence model:

- **FCC / Pregame**
  - read Playbooks from `FTD`
  - save Playbooks to `FTD`
- **Game Init**
  - copy the user team's Playbooks snapshot from `FTD` into the game doc
- **Active Gameplay**
  - read Playbooks from the game doc
  - save gameplay-scoped Playbooks changes to the game doc only

This applies to:
- offense percentages
- defense percentages
- fast break percentages
- Playcall Center ordering for offense and defense
- locks
- motion focus
- target shooter

Gameplay changes do not write back to `FTD`. FCC remains the franchise master editor.

## Likely Shot Percentages (Derived Output)

This is the **likely-shot-percentage** readout produced *from* this page's settings — a player-facing planning aid, **not** a gameplay input (the live shot engine does not read it). It answers: *based on the user's current Playbooks weighting + offensive Playcall Center assignments, how likely is each position (`PG/SG/SF/PF/C`) to be the shot-taker?* Two outputs are derived: `Playbooks` and `Playcall Center`.

> **Verified vs `playbook_weights_utils.py` (2026-07-17) — algorithm matches exactly:** 60% target / 40%-by-frequency (`_calculate_single_play_distribution`), zero-non-success → 100%, target-shooter priority (successful skeleton → team → universal, `_resolve_target_shooter`), `pos1-4`-preferred / skeleton-fallback, even Playcall split (`100/N`), floor+largest-remainder rounding (`_round_weights_to_100`), `WEIGHTS_ALGORITHM_VERSION = 1`, `NON_SUCCESS_VARIANTS=(mid_play_change, contested, broken)`, cache invalidation via `weights_cache_is_stale`. Endpoints: `GET /api/playbooks`, `POST /api/playbooks` (persists cache), `POST /api/playbooks/preview-shot-weights` (draft compute, no write). Read by 3 surfaces: Playbooks page, Set Lineup, FCC Playbooks tab.

These values are:

- derived from play definitions and user settings
- **not** influenced by player personnel
- stored as backend-derived cached values inside canonical `playbook_settings` (`position_shot_weights`)
- intended to be read by multiple pages without re-running the calculation in the frontend
- **display-only — not consumed by the gameplay shot-resolution engine**

Implementation files:

- Weight calculator: `BackEnd/utils/playbook_weights_utils.py`
- Backend route integration: `BackEnd/api/gameplan_routes.py`
- Canonical playbook settings model: `BackEnd/utils/playbook_settings_utils.py`

### Source Inputs

The calculation uses three sources:

1. `playbook_settings` — `motion`, `set_plays`, `pc_order.offense`
2. Team play metadata — `target_shooter` on set plays (`motion_focus` is **not** part of this weighting math)
3. Universal play definitions from `plays_collection` — `target_shooter`, explicit non-success shooter fields if present (`pos1`, `pos2`, `pos3`, `pos4`), `skeletons`

### Canonical Storage Location

The derived cache is stored inside canonical `playbook_settings` as:

```python
playbook_settings["position_shot_weights"] = {
    "playbooks": {"PG": int, "SG": int, "SF": int, "PF": int, "C": int},
    "playcall_center": {"PG": int, "SG": int, "SF": int, "PF": int, "C": int},
    "_meta": {
        "algorithm_version": int,
        "source_hash": str,
        "computed_at": iso_datetime,
    },
}
```

Each of `playbooks` and `playcall_center` must sum to exactly `100`.

### Per-Play Calculation Rules

Each offensive play is first converted into a per-play position distribution.

#### 1. Resolve Target Shooter

The system resolves the canonical `target_shooter` in this priority:

1. successful skeleton shooter, if one can be derived
2. team play `target_shooter`
3. universal play `target_shooter`

Successful-skeleton resolution wins any conflict.

#### 2. Ignore Success Skeletons for the Remaining 40%

The success skeletons are not used to distribute the remaining weight — the target shooter already receives the fixed success share.

#### 3. Target Shooter Gets 60%

For normal plays: `target_shooter = 60%`.

#### 4. Remaining 40% Comes from Non-Success Shooter Frequency

The remaining `40%` is distributed by frequency across non-success shooter instances.

- **Preferred source:** explicit play-definition fields `pos1`, `pos2`, `pos3`, `pos4`
- **Fallback source:** non-success skeleton variants `mid_play_change`, `contested`, `broken`

The implementation prefers explicit DB fields when they exist, and falls back to skeleton parsing when they do not.

#### 5. Zero Non-Success Shooter Case

If a play has zero non-success shooter instances: `target_shooter = 100%`.

### Set Play Position Remapping

Set-play shot weights must reflect the user's saved `target_shooter`, not just the raw builder template. The weighting system mirrors the same alias-remap model used at gameplay runtime (`target_shooter`, `pos1`, `pos2`, `pos3`, `pos4` → canonical `PG/SG/SF/PF/C`) before shooter extraction. This keeps the weights aligned with actual user settings.

### Playbooks Aggregation

`Playbooks` weights are aggregated from `motion` + `set_plays`:

- only plays with percentage `> 0` contribute
- each play contributes according to the user's saved playbook percentage (used directly — no extra normalization, since the save contract already requires the total to equal `100`)

Example: a play with derived `SG = 72%` / `PF = 20%`, weighted at `20%` in Playbooks, contributes `SG += 14.4`, `PF += 4.0`.

### Playcall Center Aggregation

`Playcall Center` weights are aggregated from `pc_order.offense`:

- only assigned offensive plays contribute
- each assigned offensive play is weighted evenly; the divisor is the actual number of assigned plays

Examples: `8 plays` => `12.5%` each; `2 plays` => `50%` each.

### Rounding Rule

Internal aggregation uses floats; stored output is integer percentages. After float aggregation, each position is floored first, then the remaining difference to `100` is distributed by largest remainder. This guarantees both `Playbooks` and `Playcall Center` totals sum to `100`.

### Refresh / Invalidation Model

The cache stays dynamic in two ways:

- **User-driven changes:** recomputed whenever the user saves Playbooks via `POST /api/playbooks` (percentage changes, Playcall Center ordering changes, set-play `target_shooter` changes).
- **Live draft preview (no save):** `POST /api/playbooks/preview-shot-weights` accepts the same body as save (`mode`, `team_id`, ids, `playbook_settings`, optional `play_updates`), runs `compute_position_shot_weights` on the draft (with in-memory play updates), and returns `{ success, position_shot_weights }` **without writing** to DB or GameManager. The Playbooks redesign page should call this on settle (slider `pointerup`, % commit, normalize) — not per `pointermove`.
- **Play-definition changes:** universal play DB changes can alter the result even if the user changes nothing. The system stores `algorithm_version` + `source_hash`; `GET /api/playbooks` recomputes a fresh result and compares cache metadata. If missing/stale, it refreshes `playbook_settings.position_shot_weights` and persists it back through canonical `playbook_settings`.

### Persistence (Franchise / Tournament / Single)

The cache follows the same persistence location as canonical `playbook_settings` (see Franchise Persistence Policy above): franchise FCC/pregame ↔ `FTD`, active franchise gameplay ↔ game-doc snapshot, tournament uses the same master-vs-game-doc split, single-game stores against the game doc. The weight cache does not introduce a separate persistence model.

### Usage Guidance

If a page needs these values, read `position_shot_weights` from the Playbooks payload (`GET /api/playbooks`) — do **not** recreate the weighting logic in the page. Any page/backend flow that derives similar shot-distribution logic independently should be audited and pointed at this shared cached output. Current scope: offense only (defensive schemes do not participate); `algorithm_version` is `1`.

## Rename Safety Status

Rename-safe:
- offense percentages
- Playcall Center ordering (`pc_order`)
- motion-focus persistence
- position filters
- most Play Details navigation

Still compatibility-based:
- some older fallback paths still accept `play_name`
- team `plays` maps may still be name-keyed in stored documents
