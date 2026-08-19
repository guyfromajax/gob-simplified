# Claude Code — Set Lineup: consolidated lineup table + Game view

Paste below the line into Claude Code, run from the repo root.

**Scope: the Set Lineup screen only.** Nothing else in the game changes.

**Design reference:** `Set Lineup - Timeout Read v2 Consolidated.html` in the design project. Open it and match the layout, spacing, type sizes, and color treatment. The three explainer cards below the mockup are design notes — do not port them.

**Before you write anything:** read the current Set Lineup implementation and report back which file(s) own the roster table and the right-hand rail, and what player fields are actually available to this screen. Several items below depend on data I have not verified. Where a field does not exist, **stop and ask — do not invent, derive, or approximate a value.**

---

## Why this is changing

This screen is what the user lands on during timeouts and quarter breaks, so every decision-critical value has to be readable in a few seconds.

Today: twelve static attribute columns sit between the two values that actually drive a substitution (energy and RT); the five players already in the lineup are dimmed even though their energy is the most important data on the screen; and the right rail repeats those same five players with the same values, so the screen shows the lineup twice.

The fix is hierarchy and consolidation, not new information.

---

## 1. The right-hand lineup rail goes away

The five Starting Five cards are **deleted**. Once the on-court five are grouped at the top of the roster table at full contrast (section 4), that table *is* the lineup display — slot, headshot, energy, rating, fouls, all present. The cards were a second copy of the same decision.

This also means substituting becomes one gesture inside one list instead of a cross-panel drag.

**Preserve every behavior those cards carried** — removing a player from the lineup, whatever click/drag/keyboard affordances exist, and any validation (five-player requirement, position rules). The remove control moves onto the table row (section 4). If a card carried behavior with no obvious new home, tell me rather than dropping it.

---

## 2. Third view tab: `Game`

The left panel's `Attributes | Stats` toggle becomes **`Game | Attributes | Stats`**, using the same segmented control component and styling.

- `Game` is the **default** view on this screen.
- **Attributes and Stats keep everything they currently have** — same columns, same order, same values, same formatting, same data sources. Do not add, remove, reorder, or recompute a single column in those views. They inherit only the shared changes in sections 3–5.

### Game view columns

`POS · (headshot) · PLAYER · ENG · RT · F · MIN · MO`

Only build columns whose data this screen already has. If fouls, minutes played, or player momentum are unavailable here, list which and stop.

Sortable by column as the other views are; energy sorts freshest-first on first click.

---

## 3. ENG and RT sit together, in all three views

Both move to fixed positions **immediately right of the player name**, in the order `ENG` then `RT`, ahead of every other data column. Applies to Game, Attributes, and Stats alike.

This is the crux of the redesign. These two previously clashed because they were rendered identically — two colored text values, same size, adjacent. They are now separated by **form**: energy is a bar, RT is a letter. Do not render energy as bare colored text.

### Color

**Energy bar fill — the brand green / yellow / red ramp.** Use the existing brand ramp colors; introduce no new hex values.

| Energy | Fill |
| --- | --- |
| ≥ 70% | brand green |
| 40–69% | brand yellow |
| < 40% | brand red |

**The energy number carries no hue.** The bar already encodes state twice (length and color); coloring the number is a third copy and puts a second colored glyph beside RT. Urgency comes from brightness:

| Energy | Number |
| --- | --- |
| ≥ 70% | ~55% white |
| 40–69% | ~90% white |
| < 40% | 100% white |

**RT — the game's canonical brand ramp, unchanged.** Find the existing grade→color mapping and reuse it exactly. Do not re-map grades, and do not touch RT's appearance anywhere outside this screen.

**Row edge.** A 3px rounded bar on the **leading edge of the row** (the far left of the first cell), colored by energy — brand yellow at 40–69%, brand red below 40%, **absent at 70% and above**. It flags problems only; a healthy roster shows no edges at all.

The 70 / 40 thresholds are my proposal. Confirm them against how the sim actually depletes energy — if a player never realistically drops below 40%, the bands need to move.

---

## 4. One table, on-court grouped at top

The table splits into two labeled groups: **`ON COURT` (5)**, then **`BENCH` (n)**, with a small gap between.

- The five in the lineup are **no longer dimmed.** Their energy and foul counts are the primary data on the screen; dimming them inverts the hierarchy. Full-contrast names, white slot labels, a subtle tinted row background, and the existing orange accent mark them as assigned.
- Bench players render below at normal contrast, with slightly dimmer names.
- Group headers show a small-caps label plus count. Not interactive.
- **`POS` shows the assigned slot** (PG…C) for on-court players and the player's natural/highest-rated position for the bench. Confirm assigned-slot data is available; if the lineup is only an ordered list of five without slot assignment, say so.
- **Headshots move into the table** — a small (~28px) headshot column between POS and PLAYER, on every row. Use the existing headshot component and image source. The reference file shows initials in a placeholder frame *only because the mock has no access to the images.*
- **Remove control** — the ✕ appears on hover over on-court rows only, at the end of the row. Same behavior as the current control.

Keep all existing click-to-assign and drag-to-assign behavior.

### Empty slots

If the flow ever allows fewer than five assigned players, an empty slot needs a representation — the cleanest is a placeholder row holding the slot label. Tell me how the current implementation handles this before building it; do not invent a state.

---

## 5. Momentum: pip ladder

MO becomes a compact discrete indicator, in the **table only**.

Momentum runs −5…+5 in integer steps, so the encoding must be discrete rather than a continuous fill:

- Five small pips each side of a 1px center hairline.
- Pips fill **outward from the center** — +3 fills the three pips nearest center on the right.
- **Negative (left) is brand red. Positive (right) is white.** One-sided hue, so the eye finds the decaying player without comparing two colors. **Do not use blue here** — blue belongs to RT.
- Unfilled pips are a faint track (~7.5% white), so zero momentum reads as an intact empty ladder rather than nothing.
- No numeric value displayed.

Confirm the actual momentum range before building. If it is not −5…+5, the pip count changes.

---

## 6. Header bar

Three derived reads sit in the screen's title row, centered between the `SET LINEUP` label and the view toggle: **average energy**, **count under 50%**, **count in foul trouble** — each a small label with its value.

These answer "is my current five still viable" without reading five rows. All three derive from values already in the table, but **confirm they're available together at this level before building.** If not, skip the strip and tell me.

The primary CTA in the top-right keeps its **current copy and behavior, unchanged** — the reference file's label is a placeholder, not a spec.

---

## 7. Right rail — two shot-weight charts

The rail keeps its width (~400px) and holds two charts, in this order:

1. **Playbook Shot Weights**
2. **Play Call Center Shot Weights**

Identical format: one row per position (PG / SG / SF / PF / C), each a position label, a horizontal track with a filled pill, and the percentage right-aligned.

**Preserve the existing shot-weight color scaling exactly as it is already programmed** — its ramp, thresholds, and values are already correct. Do not re-map it, do not apply the energy or RT thresholds to it, and do not treat the reference file's fill colors or percentages as authoritative; those are placeholders so the treatment is visible.

Leave the space below the two charts empty. It is reserved for functionality being added later — do not fill it.

---

## 8. Autoset Lineup

Moves **below the table on the left**, left-aligned and sized to its label, as a secondary-styled button. It reads as an action on the roster and stops competing with the primary CTA in the top-right. Behavior unchanged.

---

## 9. No scrolling

This screen must fit entirely in the viewport at any normal window size — nothing below the fold unless the user has shrunk the window themselves. The reference layout achieves this at ~710px tall via tightened row padding (~4px), 28px headshots, compressed group headers, and content-sized columns.

Table sizing rules that keep it there:

- Every column sized to its content — no column padded out to fill space.
- The **ENG column is the flexible one**: surplus width lengthens the energy bar (cap ~210px) rather than pooling as a gutter before the rail. Energy is the primary decision variable, so extra length is a gain.
- The energy bar is **left-aligned** in its cell so it sits adjacent to the name.
- No trailing spacer column.
- `Attributes` is the widest view and sets the minimum table width — it's the constraint to size against.

---

## Guardrails

- Do not invent, derive, or fake any player value. If a field is missing, stop and ask.
- Do not change the Attributes or Stats column sets, values, or formatting.
- Do not change RT's color mapping, or RT's appearance anywhere outside this screen.
- Do not change the shot-weight color scaling.
- Do not change the primary CTA's copy or behavior.
- Introduce no hex values outside the brand palette.
- Do not modify the scoreboard/context bar, Playcall Center, Game Plan, or Playbooks.
- Preserve existing keyboard, click, and drag interactions.

## Acceptance

1. `Game` is the default view: POS / headshot / PLAYER / ENG / RT / F / MIN / MO.
2. `Attributes` and `Stats` show exactly what they showed before, with ENG and RT relocated beside the name.
3. Energy is a bar on the brand green/yellow/red ramp; its number has no hue.
4. RT is visually identical to RT everywhere else in the game.
5. Row edges appear only below 70% energy, on the row's leading edge.
6. The right-hand Starting Five cards are gone, and assigning/removing/validation all still work from the table.
7. On-court five grouped at top at full contrast, with headshots and hover-✕.
8. MO is a −5…+5 pip ladder, red left / white right, table only.
9. Header bar carries the three derived reads, centered.
10. Both shot-weight charts render in the rail with their existing color scaling intact.
11. Autoset Lineup sits below the table on the left.
12. Nothing is below the fold at a normal window size, in any of the three views.
