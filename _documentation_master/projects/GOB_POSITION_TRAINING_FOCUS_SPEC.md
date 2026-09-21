# GOB Position-Based Training Focus Specification

## Objective

Extend the existing position-based training-efficiency system so that each player has a selectable training focus. A player's existing `position` continues to serve all of its current gameplay purposes. The new `training_focus` field only selects which training-efficiency profile is used for that player's position.

Every position/focus profile must total **808%** across all 12 attributes. Free Throws (`FT`), Basketball IQ (`IQ`), and Endurance (`ND`) must always remain at **100%**. The other nine attributes must therefore total **508%**.

## Canonical terminology

### Positions

- `PG` — Point Guard
- `SG` — Shooting Guard
- `SF` — Small Forward
- `PF` — Power Forward
- `C` — Center

### Training focuses

Use these stable stored values for `training_focus`:

- `standard`
- `offensive`
- `defensive`
- `athletic`
- `fundamentals`
- `rebounding`

Recommended UI labels:

- Standard
- Offensive
- Defensive
- Athletic
- Fundamentals
- Rebounding

Focus targets:

| Focus | Primary attributes |
|---|---|
| Offensive | Scoring (`SC`), Shooting (`SH`) |
| Defensive | Inside Defense (`ID`), Outside Defense (`OD`) |
| Athletic | Strength (`ST`), Agility (`AG`) |
| Fundamentals | Passing (`PS`), Ball Handling (`BH`) |
| Rebounding | Rebounding (`RB`), Strength (`ST`) |

`standard` is the current position profile. Focus profiles redistribute the same cumulative efficiency budget; they do not add development power.

## Data-model requirements

1. Inspect the player model, MongoDB documents, serializers, API schemas, creation/import paths, and frontend types to determine whether `position` already exists and how it is represented.
2. Reuse the existing canonical `position` field. Do not rename it, duplicate it, change its meaning, or disrupt any gameplay system that already consumes it.
3. Add `training_focus` to each player. Default it to `standard` for existing and newly created players unless another focus is explicitly selected.
4. Validate `training_focus` against the six canonical stored values above. Do not silently accept arbitrary strings.
5. Backfill or safely normalize existing player records so missing/null focus behaves as `standard`. Follow the repository's established migration/backfill pattern. If no migration framework exists, implement backward-compatible reads plus the least risky idempotent backfill mechanism.
6. Ensure `training_focus` survives every relevant persistence path: player creation, load/save, API serialization, franchise/season transitions, recruiting/drafting, cloning, and any test fixtures or seed data.
7. Keep the training calculation authoritative in the same layer where the current position multiplier is applied. The effective multiplier must be selected by both `position` and `training_focus`.

## Training behavior

When a user assigns a training point to an attribute or skill set, apply the percentage at:

`TRAINING_EFFICIENCY[position][training_focus][attribute]`

Preserve the existing interpretation of the percentage. For example, if the current code treats `70` as a `0.70` multiplier, continue doing so.

Do not apply both the old position multiplier and the new profile multiplier. The selected position/focus profile replaces the old position-only lookup as the single source of the multiplier.

Do not retroactively recalculate development that was already completed before a focus change.

Centralize the matrix in one canonical module/source. The training engine and tutorial must consume the same data, or share generated data from that source, so the displayed percentages cannot drift from gameplay.

## Canonical efficiency matrix

Values below are percentages.

### Point Guard (`PG`)

| Attribute | Standard | Offensive | Defensive | Athletic | Fundamentals | Rebounding |
|---|---:|---:|---:|---:|---:|---:|
| SC | 40 | 75 | 30 | 35 | 35 | 30 |
| SH | 45 | 80 | 35 | 40 | 45 | 35 |
| PS | 85 | 70 | 75 | 68 | 100 | 70 |
| BH | 100 | 85 | 90 | 85 | 100 | 85 |
| ID | 25 | 25 | 55 | 25 | 25 | 25 |
| OD | 70 | 60 | 100 | 60 | 70 | 55 |
| RB | 25 | 25 | 25 | 25 | 25 | 75 |
| ST | 35 | 25 | 25 | 70 | 35 | 70 |
| AG | 83 | 63 | 73 | 100 | 73 | 63 |
| FT | 100 | 100 | 100 | 100 | 100 | 100 |
| IQ | 100 | 100 | 100 | 100 | 100 | 100 |
| ND | 100 | 100 | 100 | 100 | 100 | 100 |
| **Total** | **808** | **808** | **808** | **808** | **808** | **808** |

### Shooting Guard (`SG`)

| Attribute | Standard | Offensive | Defensive | Athletic | Fundamentals | Rebounding |
|---|---:|---:|---:|---:|---:|---:|
| SC | 55 | 85 | 45 | 40 | 45 | 45 |
| SH | 100 | 100 | 90 | 85 | 85 | 85 |
| PS | 70 | 62 | 60 | 58 | 100 | 55 |
| BH | 70 | 63 | 60 | 55 | 100 | 55 |
| ID | 25 | 25 | 55 | 25 | 25 | 25 |
| OD | 60 | 55 | 90 | 50 | 50 | 50 |
| RB | 25 | 25 | 25 | 25 | 25 | 75 |
| ST | 35 | 30 | 25 | 70 | 25 | 70 |
| AG | 68 | 63 | 58 | 100 | 53 | 48 |
| FT | 100 | 100 | 100 | 100 | 100 | 100 |
| IQ | 100 | 100 | 100 | 100 | 100 | 100 |
| ND | 100 | 100 | 100 | 100 | 100 | 100 |
| **Total** | **808** | **808** | **808** | **808** | **808** | **808** |

### Small Forward (`SF`)

| Attribute | Standard | Offensive | Defensive | Athletic | Fundamentals | Rebounding |
|---|---:|---:|---:|---:|---:|---:|
| SC | 82 | 100 | 72 | 65 | 72 | 67 |
| SH | 64 | 90 | 54 | 49 | 54 | 49 |
| PS | 39 | 34 | 34 | 29 | 75 | 34 |
| BH | 39 | 34 | 34 | 34 | 75 | 34 |
| ID | 50 | 45 | 80 | 45 | 40 | 45 |
| OD | 91 | 81 | 100 | 81 | 81 | 81 |
| RB | 50 | 45 | 50 | 40 | 40 | 90 |
| ST | 40 | 35 | 35 | 75 | 30 | 75 |
| AG | 53 | 44 | 49 | 90 | 41 | 33 |
| FT | 100 | 100 | 100 | 100 | 100 | 100 |
| IQ | 100 | 100 | 100 | 100 | 100 | 100 |
| ND | 100 | 100 | 100 | 100 | 100 | 100 |
| **Total** | **808** | **808** | **808** | **808** | **808** | **808** |

### Power Forward (`PF`)

| Attribute | Standard | Offensive | Defensive | Athletic | Fundamentals | Rebounding |
|---|---:|---:|---:|---:|---:|---:|
| SC | 55 | 85 | 45 | 45 | 45 | 54 |
| SH | 47 | 77 | 37 | 37 | 37 | 47 |
| PS | 35 | 30 | 30 | 30 | 75 | 35 |
| BH | 25 | 25 | 25 | 25 | 65 | 25 |
| ID | 67 | 57 | 97 | 62 | 57 | 67 |
| OD | 35 | 30 | 65 | 30 | 25 | 35 |
| RB | 100 | 90 | 90 | 94 | 90 | 100 |
| ST | 99 | 89 | 89 | 100 | 89 | 100 |
| AG | 45 | 25 | 30 | 85 | 25 | 45 |
| FT | 100 | 100 | 100 | 100 | 100 | 100 |
| IQ | 100 | 100 | 100 | 100 | 100 | 100 |
| ND | 100 | 100 | 100 | 100 | 100 | 100 |
| **Total** | **808** | **808** | **808** | **808** | **808** | **808** |

### Center (`C`)

| Attribute | Standard | Offensive | Defensive | Athletic | Fundamentals | Rebounding |
|---|---:|---:|---:|---:|---:|---:|
| SC | 68 | 95 | 58 | 50 | 48 | 58 |
| SH | 40 | 70 | 30 | 25 | 25 | 35 |
| PS | 33 | 25 | 28 | 25 | 75 | 28 |
| BH | 25 | 25 | 25 | 25 | 65 | 25 |
| ID | 100 | 100 | 100 | 100 | 100 | 100 |
| OD | 40 | 25 | 80 | 28 | 25 | 37 |
| RB | 100 | 83 | 95 | 90 | 80 | 100 |
| ST | 77 | 60 | 67 | 100 | 65 | 100 |
| AG | 25 | 25 | 25 | 65 | 25 | 25 |
| FT | 100 | 100 | 100 | 100 | 100 | 100 |
| IQ | 100 | 100 | 100 | 100 | 100 | 100 |
| ND | 100 | 100 | 100 | 100 | 100 | 100 |
| **Total** | **808** | **808** | **808** | **808** | **808** | **808** |

## Tutorial: Advanced Topics layout

Update the existing Advanced Topics tutorial section that currently displays the position-efficiency table.

The user must be able to inspect the matrix in two orientations:

### View by position

Show position controls for `PG`, `SG`, `SF`, `PF`, and `C`.

Selecting a position displays that position's six profiles side by side:

`Standard | Offensive | Defensive | Athletic | Fundamentals | Rebounding`

### View by focus

Show focus controls for `Standard`, `Offensive`, `Defensive`, `Athletic`, `Fundamentals`, and `Rebounding`.

Selecting a focus displays all five positions side by side:

`PG | SG | SF | PF | C`

### Interaction and presentation requirements

1. Provide a clear view-mode control: **By Position** / **By Focus**.
2. In By Position mode, show the five position buttons and use the selected position to populate six comparison columns.
3. In By Focus mode, show the six focus buttons and use the selected focus to populate five comparison columns.
4. Default to **By Position → PG** unless the existing page has a stronger established default that should be preserved.
5. Preserve the existing visual language, responsive behavior, attribute labels, percentage formatting, fit-category colors, and accessibility conventions.
6. The active mode and selected button must be visually clear and keyboard accessible.
7. On narrow screens, preserve legibility using the project's established responsive table/card pattern or horizontal scrolling rather than shrinking text to an unreadable size.
8. Generate the displayed values from the canonical matrix. Do not maintain a second hand-copied tutorial matrix.
9. Keep or update the fit legend so its thresholds remain consistent with the current implementation.

## Player focus-selection UI

Locate the existing player training/development interface and identify the least disruptive place for the user to view and change `training_focus`.

Unless an existing product rule says otherwise:

- Display the six focus choices using the UI labels above.
- Persist the selection immediately or through the screen's established save/apply action.
- Changing focus affects future training only.
- Show the currently selected focus when a player is revisited.
- Do not allow a focus change to alter the player's `position`.

If the repository does not contain an obvious player training-focus selection surface, stop and report the best candidate locations before inventing a new navigation flow.

## Verification and tests

Add or update tests to verify:

1. All 30 position/focus profiles exist.
2. Every profile contains all 12 attributes.
3. Every profile totals exactly `808`.
4. `FT`, `IQ`, and `ND` equal `100` in every profile.
5. Missing or null `training_focus` resolves to `standard` for legacy players.
6. Invalid focus values are rejected or normalized according to existing API conventions.
7. The training engine uses the correct percentage for representative position/focus/attribute combinations.
8. The old multiplier is not applied in addition to the selected profile.
9. `training_focus` round-trips through persistence and APIs.
10. Tutorial By Position and By Focus controls render the correct columns and values.
11. Existing systems that use `position` continue to behave unchanged.

Run the repository's relevant backend and frontend test suites, type checks, linting, and builds. Report the exact commands and results.

## Implementation guardrails

- Inspect before editing; follow existing architecture and naming conventions.
- Do not create a duplicate player-position field.
- Do not repurpose `position` to store training focus.
- Do not change unrelated simulation or player-generation behavior.
- Avoid duplicating the matrix across backend and frontend when the architecture provides a shared or API-delivered source.
- If backend and frontend cannot share code directly, establish one authoritative representation and a clear generated/serialized consumer path.
- Preserve backward compatibility for existing saves and MongoDB documents.
- Keep changes scoped and document any assumptions.

## Required implementation report

At completion, report:

1. Whether `position` already existed and every important place it is used.
2. Where `training_focus` was added and how legacy players are handled.
3. Where the canonical matrix lives.
4. Where users select a player's focus.
5. How the Advanced Topics tutorial was updated.
6. Tests added or changed and their results.
7. Any unresolved migration, deployment, or product decisions.
