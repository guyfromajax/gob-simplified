# Simple Playbooks Brief

## Objective

Overhaul the Playbooks page so it is much simpler, flatter, and easier to understand.

This phase is focused on:
- the target UI and user interaction model
- simplifying the visible configuration surface
- making Playcall Center selection and ordering clearer

This brief now includes the final **Franchise Mode** persistence model for Playbooks.

Single Game and Tournament compatibility may remain temporarily, but the implementation
and architecture in this phase are explicitly **franchise-first**.

## Franchise Persistence Contract

Franchise Mode Playbooks should follow a simple two-stage source-of-truth model:

- `franchise_team_data` (`FTD`) is the authoritative **pregame / franchise master** source
- the `game` document is the authoritative **in-game** source once a game has been initialized

### FCC / Pregame

When the user opens Playbooks from the Franchise Command Center:

- load Playbooks from `FTD`
- save Playbooks to `FTD`

This includes:
- `playbook_settings`
- team-owned `plays` play-level configuration such as:
  - `target_shooter`
  - `motion_focus`

### Game Initialization

When the user starts a franchise game:

- the game should ingest a full Playbooks snapshot from `FTD`
- that snapshot should be copied into the game doc before gameplay begins

The copied snapshot must include:
- `playbook_settings`
- team-owned `plays`

This ensures gameplay starts from exactly what the user last saved in FCC.

### Gameplay

Once the game exists:

- gameplay reads Playbooks from the game doc
- gameplay should not continue to mix reads from both the game doc and `FTD`

This is important for SS&S:
- `FTD` remains the franchise master
- the game doc remains the current game snapshot

### Halftime Editing

Playbooks editing during gameplay should be heavily restricted.

Rules:
- remove the Playbooks button from the lineup / pre-tip gameplay flow
- allow Playbooks access only at halftime, between Q2 and Q3
- at halftime, the user may edit only:
  - percentages
  - Playcall Center membership / ordering

The user may **not** edit at halftime:
- `target_shooter`
- `motion_focus`
- other structural / play-level configuration

### Halftime Persistence

Halftime Playbooks changes:

- save to the current game doc only
- do **not** save back to `FTD`

This means:
- halftime changes affect only the current game
- the next game still starts from the franchise master settings stored in `FTD`

### Postgame Behavior

After the game:

- returning to FCC should show the franchise master Playbooks settings from `FTD`
- halftime-only tactical changes from the finished game should not overwrite franchise master settings

## Top-Level Page Structure

The page should have a persistent top bar that remains visible while the user scrolls.

Top-left:
- Back button

Top-center:
- Header: `Playbook Settings`

Top-right:
- two stacked buttons
- top button: `Save Playbooks`
- bottom button: `Even Distribution - All`

The top bar should stay pinned / sticky while scrolling.

## Top-Right Buttons

### Save Playbooks

Behavior:
- dead / disabled until **all sections total 100%**
- becomes active only when every editable percentage section sums to `100`

### Even Distribution - All

Behavior:
- redistributes **all editable percentage sections** evenly across all rows in those sections
- after applying, all sections should total `100`

Confirmation modal text:
- `this will change all %s -- your previous settings will be lost`

Modal actions:
- `Cancel`
- `Save Anyway`

Modal checkbox:
- `Don't show this pop up again.`

If the user checks that box, the warning should stop appearing for future uses of the button.

## Main Page Sections

The page is composed of the following sections, in this order:

1. `Offense - Motion`
2. `Offense - Set Plays`
3. `Defense - Man`
4. `Defense - Zone`
5. `Fast Breaks`
6. `Playcall Center` ordering block

The page should feel like a clean, spreadsheet-like configuration surface rather than the current multi-panel experience.

## Offense - Motion

Each motion play appears **once only**.

Columns:
- Play Name
- `%`
- `Focus`
- `Playcall Center`
- `Effectiveness`
- `Top Scorer`

### % column

- integer input with up/down controls
- same behavior style as the current Playbooks page

### Focus column

- dropdown
- values:
  - `balanced`
  - `inside`
  - `attack`
  - `outside`

Load behavior:
- if the user has **unsaved** settings on page load, show `balanced`

### Playcall Center column

- checkbox
- boolean value (`true` / `false`)

Rules:
- a motion play can be added to Playcall Center even if its `%` is `0`
- zero-percent plays are still eligible for PCC selection

### Effectiveness column

- read-only display
- displayed as `X/100`

### Top Scorer column

- read-only display
- should show the **highest scorer this season** for that play
- format:
  - `PlayerName (Points)`

## Offense - Set Plays

Columns:
- Play Name
- `%`
- `Target Shooter`
- `Playcall Center`
- `Effectiveness`
- `Top Scorer`

### % column

- integer input with up/down controls
- same behavior style as current Playbooks

### Target Shooter column

- dropdown
- values:
  - `PG`
  - `SG`
  - `SF`
  - `PF`
  - `C`

Load behavior:
- on page load, whether settings are saved or unsaved, display that play’s current `target_shooter` value

Persistence rule:
- when the user changes target shooter, update the `target_shooter` value on that **team-owned play doc**
- do **not** change the universal play doc

### Playcall Center column

- checkbox
- boolean value

Rules:
- a set play can be added to Playcall Center even if its `%` is `0`
- zero-percent plays are still eligible for PCC selection

### Effectiveness column

- read-only display
- displayed as `X/100`

### Top Scorer column

- read-only display
- should show the **highest scorer this season** for that play
- format:
  - `PlayerName (Points)`

## Defense - Man

Rows to display:
- `Man Normal`
- `Man Pressure`
- `Man Loose`

Columns:
- Play Name
- `%`
- `Playcall Center`
- `Effectiveness`

### Man Normal

- active row
- editable like the other live sections

### Man Pressure and Man Loose

For now these should be shown as **dead rows**.

Behavior:
- all controls inactive
- user cannot edit the row
- user cannot add the row to Playcall Center

Recommended visual treatment:
- reduced row opacity
- disabled controls
- a visible `Coming Later` treatment on the row

The goal is to make it obvious these rows are intentionally unavailable, not broken.

## Defense - Zone

Rows:
- `2-3 Zone`
- `3-2 Zone`
- `1-3-1 Zone`

Columns:
- Play Name
- `%`
- `Playcall Center`
- `Effectiveness`

Behavior:
- percentage input is editable
- Playcall Center checkbox is editable
- effectiveness is read-only

## Fast Breaks

Rows:
- `Triangle`
- `Rim Runner`
- `Covert Release`

Columns for this phase:
- Play Name
- `%`

Optional read-only column:
- `Top Scorer` is **omitted for now**

Reason:
- scorer tracking for fast breaks is not yet locked for this UI
- we can add it later once that data contract is formalized

## Section Total Rules

All editable percentage sections must total `100%`.

This applies to:
- `Offense - Motion`
- `Offense - Set Plays`
- `Defense - Man`
- `Defense - Zone`
- `Fast Breaks`

Save rule:
- `Save Playbooks` is disabled until **every required section** totals `100`

Editing rule:
- users may temporarily be out of balance while editing
- the page should clearly indicate which sections are not at `100`

Active-row rule:
- only active/editable rows count toward a section total
- dead rows do **not** count toward the required `100`

## Playcall Center Selection Rules

The Playcall Center selection model is being expanded.

Previous cap:
- `6`

New cap:
- `8`

Rule:
- if the user already has `8` plays selected for the Playcall Center and they try to select another, block the action and show a popup

Popup text:
- `8 plays max can be added to the playcall center, please remove one to add another`

This should apply separately to:
- offense PCC list: max `8`
- defense PCC list: max `8`

## Playcall Center Ordering Block

At the bottom of the page, show an interactive display of the current Playcall Center settings.

Header:
- `Playcall Center`

Sub-head:
- `drag & drop to adjust the order`

Layout:
- two columns
- offense on the left
- defense on the right

Display format:

Offense
- `1. 3-2 Motion`
- `2. Wrap-Around`
- `3. Back Door Cut`

Defense
- `1. Man Normal`
- `2. 2-3 Zone`
- `3. 3-2 Zone`

Behavior:
- drag and drop within each column to adjust slot order
- ordering here controls the Playcall Center display/order used in gameplay
- the ordering block should reflect the currently checked Playcall Center rows above

Persistence rule:
- `pc_order` is the only source of truth for Playcall Center membership and ordering
- if a row is checked, it should exist in the appropriate `pc_order` list
- if a row is unchecked, it should be removed from the appropriate `pc_order` list
- do **not** persist a separate PCC membership boolean outside of `pc_order`

## UX Intent

The page should feel:
- simpler
- flatter
- easier to scan
- easier to edit quickly

The user should be able to:
- see all core playbook settings at once
- edit percentages quickly
- assign motion focus quickly
- assign set-play target shooter quickly
- choose which plays belong in Playcall Center
- reorder the Playcall Center directly without hidden slot logic

## Explicit Deferrals

Not part of this brief yet:
- final database shape
- migration strategy from the old Playbooks structure
- exact persistence contract for drag-and-drop ordering
- fast-break top-scorer display
- future activation of `Man Pressure` and `Man Loose`

## Target Data Direction

This section captures the intended simplified persistence direction for the next phase.

### FTD `playbook_settings` Target Shape

Target sub-fields:

1. `motion`
2. `set_plays`
3. `fast_breaks`
4. `man_defense`
5. `zone_defense`
6. `pc_order`
7. `_meta`

This means the current `motion_dropdowns` field should be removed in the new model.

### Team-Owned `plays` Target Shape

Per-play mutable configuration should live on the team-owned play docs in the `plays` object.

Rules:
- motion plays store `motion_focus`
- set plays store `target_shooter`

This keeps the playbook settings object focused on weighting and Playcall Center ordering, while the team-owned play docs hold per-play user customization.

### Motion Focus Persistence

The current UI concept of motion focus should **not** be pulled from universal `play_focus`.

Reason:
- motion plays generally do not use universal `play_focus` the same way set plays do
- motion focus in the new UI is a user-controlled per-team setting

Therefore:
- store motion focus on the team-owned motion play doc as `motion_focus`
- if `motion_focus == null`, the UI should display `balanced`
- selecting `balanced` in the UI should persist `null`, not the string `"balanced"`

### Set Play Target Shooter Persistence

Set-play target shooter should be pulled from the team-owned set-play doc’s `target_shooter` field.

Rule:
- editing target shooter updates the team-owned play doc only
- the universal play doc remains unchanged

### Set Play Percentage Persistence

The new playbook model should use a **single flat set-play percentage map**.

Rule:
- `set_plays` is one flat `%` map keyed by `play_id`
- it replaces the old split between:
  - `set_play_inside`
  - `set_play_attack`
  - `set_play_outside`

Runtime behavior:
- gameplay should still determine desired set-play focus from strategy settings / situational logic
- once focus is chosen, runtime should filter to set plays whose inherent `play_focus` matches that focus
- then apply the user’s `set_plays` weights only across that eligible subset

This preserves current gameplay intent while simplifying persistence and UI.

### Playcall Center Ordering Persistence

The old `slot_assignments` model should be replaced by `pc_order`.

Target shape:

```json
"pc_order": {
  "offense": [...],
  "defense": [...]
}
```

This should be modeled as two separate ordered lists:
- one for offense
- one for defense

That structure matches the new bottom-of-page drag-and-drop UI directly and is clearer than the old slot-based naming.

### Defense Identity Persistence

Defense rows should use stable defense IDs, not display names, in persistence.

Recommended IDs:
- `man_normal`
- `man_pressure`
- `man_loose`
- `zone_23`
- `zone_32`
- `zone_131`

These IDs should be used in:
- `man_defense`
- `zone_defense`
- `pc_order.defense`

Display names in the UI remain:
- `Man Normal`
- `Man Pressure`
- `Man Loose`
- `2-3 Zone`
- `3-2 Zone`
- `1-3-1 Zone`

### Fast Break Persistence

Use `fast_breaks` as the field name in the new model.

Rows should use stable IDs for persistence:
- `triangle`
- `rim_runner`
- `covert_release`

Top scorer for fast breaks remains deferred for now.

## Open Implementation Notes

These are directional notes, not yet DB decisions:
- the new page should avoid exposing old slot-assignment complexity directly
- Playcall Center membership and order should be much more obvious than the current model
- set-play target shooter editing should clearly operate on team-owned play data
- read-only performance columns should help the page feel informative, not just configurable

## Remaining Open Items

These are the only meaningful items still open after this review:
- exact `_meta` contents for the new Playbooks page
- whether the even-distribution warning suppression should live in local storage or `_meta`
- exact API response shape for the combined page payload
