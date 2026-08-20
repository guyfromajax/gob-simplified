# Claude Code — Set Lineup redesign

Run from the repo root. **Scope: the Set Lineup screen only.** Nothing else in the game changes.

**Design reference:** `Set Lineup - v3 Fits.html`. Open it and match layout, spacing, type sizes, and color treatment. The stress-test bar and the three explainer cards below the mockup are design tooling — **do not port them.**

**Before writing any code:** read the current Set Lineup implementation and report back (a) which file(s) own the roster table and the right-hand rail, and (b) which of the player fields below actually exist and are reachable from this screen. Several items depend on data I have not verified. **Where a field does not exist, stop and ask — do not invent, derive, or approximate it.**

Fields the design assumes: energy, RT, fouls, minutes played, momentum, points, rebounds, assists, DEF%, assigned lineup slot, headshot.

**All numeric values, percentages, and the CTA label in the reference file are illustrative placeholders.** Only the layout, hierarchy, and color rules are the spec.

---

## Why this is changing

This screen is what the user lands on during timeouts and quarter breaks, so the read has to happen in seconds.

Today: twelve static attribute columns sit between the two values that drive a substitution (energy and RT); the five players already in the lineup are *dimmed* even though their energy is the most important data on screen; the right rail repeats those same five players with the same values, so the lineup renders twice; and several hundred pixels of empty space sit between the energy readout and the rest of the row.

---

## 1. The right-hand Starting Five rail is deleted

Once the on-court five are grouped at the top of the roster table at full contrast (§4), that table **is** the lineup display. The cards were a second copy of the same decision. Removing them also makes a substitution one gesture inside one list instead of a cross-panel drag.

**Preserve every behavior those cards carried** — removing a player, all click/drag/keyboard affordances, and any validation (five-player requirement, position rules). The remove control moves onto the table row. If a card carried behavior with no obvious new home, tell me rather than dropping it.

---

## 2. Third view tab: `Game`

`Attributes | Stats` becomes **`Game | Attributes | Stats`**, same segmented-control component and styling. **`Game` is the default** on this screen.

**Attributes and Stats keep everything they currently have** — same columns, same order, same values, same formatting, same data sources. Do not add, remove, reorder, or recompute a single column in those views. They inherit only the shared changes in §3–§5.

---

## 3. Row structure

### Game view — three segments, generous space between

`POS · headshot · PLAYER · ENG` ⟶ gap ⟶ `PTS · REB · AST · DEF%` ⟶ gap ⟶ `RT · F · MIN · MO`

Identity and readiness, then production, then rating and situation. Each gap is ~26px in the reference. The **production cluster is the flexible column** — surplus table width goes into those two gaps, so the segments keep their proportions as the window resizes. Every other column is sized to its content.

### Attributes and Stats views

`POS · headshot · PLAYER · ENG · RT ·` then that view's existing columns, unchanged. ENG and RT move to fixed positions immediately right of the name; nothing else about those views changes.

---

## 4. One table, on-court grouped at top

Two labeled groups: **`ON COURT`** then **`BENCH`**.

- The five in the lineup are **no longer dimmed.** Their energy and foul counts are the primary data on the screen; dimming them inverts the hierarchy. Full-contrast names, white slot labels, a subtle tinted row background, and the existing orange accent mark them as assigned. Bench names render slightly dimmer.
- Group headers show a small-caps label and count, and are not interactive. The ON COURT header reads `n/5`, plus an amber `N SLOTS OPEN` note when the lineup is incomplete.
- **`POS`** shows the **assigned slot** (PG…C) for on-court players, and the player's natural/highest-rated position for the bench. Confirm assigned-slot data exists; if the lineup is only an ordered list of five, say so.
- **Headshots** — a ~24px headshot column between POS and PLAYER, on every row. Use the existing headshot component and image source. The reference shows initials in a placeholder frame *only because the mock has no access to the images.*
- **Remove control** — ✕ at the end of the row, appearing on hover over on-court rows only. Same behavior as today's control.
- **Empty slots are real rows**: a dashed placeholder in the headshot column, the slot label in POS, and a quiet "Empty" hint. ON COURT is therefore always exactly five rows tall and never collapses.

Keep all existing click-to-assign and drag-to-assign behavior.

---

## 5. Color rules

The brand ramp is reused across several variables here, so each one gets its own visual channel and each channel is used once per row. This is the core of the redesign — energy and RT originally clashed because both were rendered as colored text at the same size.

**Energy — hue in the bar fill, brand green / yellow / red.** Use the existing brand ramp colors; introduce no new hex values. Energy must render as a **bar**, never as bare colored text.

| Energy | Bar fill |
| --- | --- |
| ≥ 70% | brand green |
| 40–69% | brand yellow |
| < 40% | brand red |

**The energy number carries no hue.** The bar already encodes state twice (length and color); coloring the number is a third copy. Urgency comes from brightness instead:

| Energy | Number |
| --- | --- |
| ≥ 70% | ~55% white |
| 40–69% | ~90% white |
| < 40% | 100% white |

**RT — the game's canonical brand ramp, unchanged.** Find the existing grade→color mapping and reuse it exactly. Do not re-map grades, and do not touch RT's appearance anywhere outside this screen.

**Fouls** — neutral at 0–3, brand yellow at 4, brand red at the disqualification threshold. Confirm that threshold rather than assuming 5.

**Momentum — a pip ladder, no numerals.** Momentum is a −5…+5 integer, so the encoding is discrete, not a continuous fill: five small pips each side of a 1px center hairline, filling **outward from center** (+3 fills the three pips nearest center on the right). **Negative/left is brand red; positive/right is white** — one-sided hue, so the eye finds the decaying player without comparing two colors. **Do not use blue here; blue belongs to RT.** Unfilled pips are a faint ~7.5% white track so zero momentum reads as an intact empty ladder. Confirm the range is −5…+5; if not, the pip count changes.

**Production cluster (PTS/REB/AST/DEF%) — no hue at all.** It is reference material, not signal, and must read as subordinate to everything else in the row: ~12.5px numerals at ~55% white (bench) / ~70% (on court), with ~9px labels at ~22% white. Four equal grid cells so the numerals align vertically down every row. **A player who has not played shows a single dim em-dash**, not four zeros.

**Row edge — flags problems only.** A 3px rounded bar on the row's leading edge, brand yellow at 40–69% energy, brand red below 40%, and **absent at 70% and above.** A healthy roster shows no edges at all; coloring the default state wastes the alarm channel.

The 70 / 40 thresholds are a proposal — confirm them against how the sim actually depletes energy. If a player never realistically drops below 40%, the bands need to move.

---

## 6. Header bar

Three derived reads sit in the screen's title row, centered between the `SET LINEUP` label and the view toggle: **average energy**, **count under 50%**, **count in foul trouble**. They answer "is my current five still viable" without reading five rows. Hide them when no players are assigned.

All three derive from values already in the table, but confirm they're reachable at this level before building. If not, skip the strip and tell me.

The primary CTA in the top-right keeps its **current copy and behavior, unchanged.**

---

## 7. Right rail

Width ~340px. Contents, top to bottom:

1. **Playbook Shot Weights**
2. **Play Call Center Shot Weights**
3. Action buttons, **bottom-anchored**: `Autoset Lineup` (primary-ish styling), then `Game Plan` and `Playbooks` side by side.

Both charts use one identical format: a row per position (PG/SG/SF/PF/C), each with a position label, a horizontal track with a filled pill, and the percentage right-aligned.

**Preserve the existing shot-weight color scaling exactly as already programmed** — its ramp, thresholds, and values are correct. Do not re-map it, do not apply the energy or RT thresholds to it, and do not treat the reference file's fills or percentages as authoritative.

Bottom-anchoring the buttons matters: the rail's content is short and the table's is long, so anchoring lets the leftover vertical space sit between the charts and the buttons instead of pooling as a dead pocket in the corner.

---

## 8. Nothing below the fold

This screen must fit entirely in the viewport at any normal window size, unless the user has shrunk the window themselves.

**Design against the worst case, which is an empty lineup: 5 slot placeholders + 12 bench = 17 rows** — not the 12-row full-lineup case. The reference hits ~662px at 17 rows via 28px rows, 24px headshots, and compressed group headers. Verify all three states (full / partial / empty) in all three views; `Attributes` is the widest view and sets the minimum table width.

There is roughly 130px of headroom at the worst case, so if 28px rows feel too tight in practice, row height is the first thing to spend it on.

---

## Guardrails

- Never invent, derive, or fake a player value. If a field is missing, stop and ask.
- Do not change the Attributes or Stats column sets, values, or formatting.
- Do not change RT's color mapping, or RT's appearance anywhere outside this screen.
- Do not change the shot-weight color scaling.
- Do not change the primary CTA's copy or behavior.
- Introduce no hex values outside the brand palette.
- Do not modify the scoreboard/context bar, Playcall Center, Game Plan, or Playbooks themselves.
- Preserve existing keyboard, click, and drag interactions.

## Acceptance

1. `Game` is the default view, in three spaced segments: identity+energy / production / status.
2. `Attributes` and `Stats` show exactly what they showed before, with ENG and RT relocated beside the name.
3. Energy is a bar on the brand green/yellow/red ramp; its number carries no hue.
4. RT is visually identical to RT everywhere else in the game.
5. Row edges appear only below 70% energy, on the row's leading edge.
6. The Starting Five rail is gone, and assigning / removing / validation all still work from the table.
7. On-court five grouped at top at full contrast, with headshots and a hover ✕.
8. Empty slots render as dashed rows; ON COURT is always five rows tall.
9. MO is a −5…+5 pip ladder, red left / white right, no numerals.
10. The production cluster is visibly subordinate, hue-free, vertically aligned, and shows an em-dash for players who haven't played.
11. Header bar carries the three derived reads, centered.
12. Both shot-weight charts render in the rail with their existing color scaling intact; action buttons bottom-anchored.
13. Nothing below the fold at 17 rows, in any of the three views.
