# GOB Coaching Archetype Badges

Drop-in icon set for the 18 coaching archetypes. A coach's **lead archetype** (`user.lead_archetype`) selects the badge shown **beside their username** everywhere in GOB.

Repo location: **`FrontEnd/static/images/archetype_icons`**

## What's here

```
archetype_icons/
  archetypes.json     ← manifest: id (= DB field) → file, name, group, color, treatment, qualifying formula
  svg/                ← 18 standalone SVGs, one per archetype (self-contained, colors baked in)
    pure_offense.svg
    … (18 total)
```

**Icon `id` === the `user.archetypes.<key>` DB field name.** Lead archetype maps straight to a file: `svg/<key>.svg`. No translation table.

## The medallion system

Every badge shares one material — dark forged depth, glyph in its lean color. Shape carries meaning:

| Treatment | Used for | Shape |
|---|---|---|
| **hexagon** | the "face" archetypes — Intimidator + the three Fundamentals | gold/orange/blue/purple hex medallion |
| **shield** | Pure Defense | grey forged frame + dimensional blue shield |
| **standalone** | all action glyphs (offense, rebounding, athleticism, cerebral, outrun, discipline, unconventional, O/D balance) | free-standing glyph, no frame |

Color = group: **orange** Offense-First · **blue** Defense-First · **purple** Specialist · **gold** The Intimidator (alone) · O/D Balance = blue shield + orange swish.

## Usage

- **Format:** self-contained SVG (gradients/filters baked in). `<img src="…">` or inline both render correctly with no extra CSS.
- **Inline (beside a username):** render at **22px**.
- **Explainer / reveal modal:** render larger (**~64–120px**); same file, scales losslessly.
- **One badge per coach** — always their lead archetype. Never stack more than one.
- **Accessibility:** set `alt` / `aria-label` / `<title>` to the archetype `name`.

## Selecting the lead archetype

`user.archetypes` holds an integer count per archetype plus `total`. `user.lead_archetype` is the key with the highest count (tie = most recently incremented; empty when no games). Render `svg/<lead_archetype>.svg`; render nothing when empty.
