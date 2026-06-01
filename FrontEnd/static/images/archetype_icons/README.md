# GOB Coaching Archetype Badges

Drop-in icon set for the 18 coaching archetypes. A coach's **lead archetype** (the one with the highest count in `user.archetypes`) selects the badge shown **beside their username** everywhere in GOB.

Repo location: **`FrontEnd/static/images/archetype_icons`**

## What's here

```
archetype_icons/
  archetypes.json     ← manifest: id (= DB field) → file, name, lean, color, qualifying formula
  svg/                ← 18 standalone SVGs, one per archetype (colors baked in)
    pure_offense.svg
    cerebral_offense.svg
    … (18 total)
```

**Icon `id` === the `user.archetypes.<key>` DB field name** (underscores). So the lead archetype maps straight to a file: `svg/<key>.svg`. No translation table.

## The system

Every badge is **one glyph in one lean color** — color tells you the coach's game, the glyph tells you their edge.

| Lean | Color | Meaning |
|------|-------|---------|
| Offense | `#F79420` (orange) | scoring & shooting |
| Defense | `#4E8AEC` (blue) | inside & outside defense |
| Specialist | `#E0B249` (gold) | one dominant trait family |
| Wildcard | `#A876E6` (purple) | Mr. Fundamentals & Mr. Unconventional |
| Balance | orange + blue | O / D Balance (composite: swish on a shield) |

## Usage

- **Format:** SVG on a 24×24 grid, colors **baked in** — `<img src="…">` or inline both render correctly with no extra CSS.
- **Inline (beside a username):** render at **22px** (leaderboards, account modal, account page, any username surface).
- **Explainer / hero:** render larger (**~64px**); same file, scales losslessly.
- **One badge per coach** — always their lead archetype. Never stack more than one.
- **Accessibility:** set `alt` / `aria-label` / `<title>` to the archetype `name`.

## Selecting the lead archetype

`user.archetypes` holds an integer count per archetype plus `total`. The lead archetype is the **key with the highest count** among the 18 (ignore `total`). Render `svg/<that key>.svg`. Decide a deterministic tie-breaker if two are equal (e.g. most-recently-incremented, or a fixed priority order).
