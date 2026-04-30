# Cursor Brief — Playcall Center Redesign

## Scope
Replace the current Playcall Center markup + styles in `FrontEnd/static/court.html` with the redesigned cockpit panel from the POC. Reference file: `Playcall Center POC.html` (in this design project) — port the HTML structure, CSS, and visual treatment exactly. Do **not** port the demo `<script>` block or the placeholder headshot pattern (real player images replace it).

The redesign is a visual + structural refactor only. **All existing behavior, state management, override logic, and SFX must be preserved.**

---

## Container Constraints
- Total Playcall Center footprint: **1000px × 160px** (matches current court container).
- Three zones, left to right:
  - **Zone 1 — Overrides** (38% width): OFF row (top), DEF row (bottom).
  - **Zone 2 — Strategy dials** (32% width): Tempo, Aggression, Press/Trap.
  - **Zone 3 — Game controls** (auto width, right-aligned): Speed (disabled), Pause, Timeout.
- 1px white-5% dividers between zones.
- Subtle team-color hairline (1px) at top edge + 5% team-color gradient bleed in top 24px. Driven by `--team-rgb` CSS var.

---

## Zone 1 — Offense / Defense Overrides

### Layout
- OFF row: `[OFF label] [headshot 38px] [play name, up to 2 lines] [▲▼ stacked arrows] [✕ clear]`
- DEF row: `[DEF label] [scheme name, up to 2 lines] [▲▼ stacked arrows] [✕ clear]`
  - DEF row has **no headshot** (defense is a scheme, not a player).
- 8px horizontal gap between row elements.
- Label column auto-sized to content (no fixed width).

### Play name behavior
- Play and defense scheme names must support up to **2 lines**. Use `-webkit-line-clamp: 2` with `line-height: 1.05`. Names longer than 2 lines truncate with ellipsis.
- Example test string: `"Double Screen Three - Wing (SG)"` should wrap to 2 lines without overflow.

### Up/down arrows
- Stacked **vertically** (▲ on top, ▼ on bottom), tight against the right edge.
- 20px wide × 14px tall each, 2px gap between.
- Reads as a "scroll through plays" cycle control.

### State styling
- Default (no override): muted row, dim play name (35% white).
- **OFF "armed"** (override set, awaiting next possession): orange glow, orange border, orange-tinted "OFF" label.
- **DEF "active"** (override set, persistent until cleared): softer orange tint.
- Clear ✕ only visible when row is `.active` or `.armed`.

### Removed from previous design
- ❌ "Inside · Next possession" meta line on OFF — removed.
- ❌ "Persistent until cleared" meta line on DEF — removed.
- (State is conveyed by the orange glow alone — OFF auto-clears after possession, DEF persists. Users learn this from observation.)

---

## Zone 2 — Strategy Dials

Three stacked dial rows, each: `[label, 88px] [3-notch dial] [✕ clear]`

### Labels (full words, not abbreviations)
- `TEMPO`
- `AGGRESSION` (spelled out — this is what set the 88px column width)
- `PRESS/TRAP` (slash, no space)

### Notches (left → right) with labels rendered below each notch
- TEMPO: `FAST` · `NORMAL` · `SLOW`
- AGGRESSION: `AGGR` · `NORMAL` · `PASSIVE`
- PRESS/TRAP: `PRESS` · `TRAP` · `NONE`

Notch labels positioned 22px below the notch via `::after { content: attr(data-label); }`. This is why dial-row gap is 14px and zone padding is `10px 18px 14px` — to make room for labels.

### Visual rules
- Notch: 18px circle, 2px white-18% border, transparent fill.
- Active notch: orange fill, orange border, orange glow (`box-shadow: 0 0 12px -2px rgba(247,148,32,0.35)`).
- Active notch label: orange-tinted (`rgba(247,148,32,0.85)`).
- Track: 2px line, white-8%, no fill behind active notches. **Do not add a fill bar** — earlier iterations had one but it read as broken without a left anchor.
- All three rows show the clear ✕ when active (`.pcc-dial-row.active .pcc-clear-strategy { opacity: 1 }`).

---

## Zone 3 — Game Controls

Right-aligned flex row, 12px gap.

### Speed selector
- Vertical 3-button segmented control (▶▶▶ / ▶▶ / ▶ stacked top to bottom).
- 32px wide × 30px tall per button.
- Currently disabled — render at 35% opacity, `pointer-events: none`. (Future feature — keep markup, keep dead state.)

### Pause / Resume
- 120px × 64px primary button.
- **Neutral steel** treatment (NOT green, NOT orange):
  - Default (live game): `linear-gradient(180deg, #2a2f3a 0%, #1a1d27 100%)`, white-18% border.
  - Paused state (`.paused` class): `linear-gradient(180deg, #3a4252 0%, #232732 100%)`, white-32% border. Label swaps to "RESUME", icon swaps from `▮▮` to `▶`.
- **Why steel and not green/orange:**
  - Green is reserved for gating actions (per Styleguide.md). Pause does not advance game state, so green is wrong.
  - Orange is the save/configure action color. It's already heavily used in the panel (override states, active dials, timeout pills). Adding orange to Pause would dilute its meaning.
  - Steel keeps the action-color hierarchy clean and gives Pause a distinct tier.
- Hover: brightness +12%, border lifts to 32% white.

### Timeout
- 120px × 38px ghost button on top.
- 4-pill row directly below: each pill is `flex: 1 / height: 5px / 1px radius`, orange (`#F79420`) when available, white-10% when used.
- Pip count and used-state already wired via `.timeout-pips` / `.to-pip` markup — preserve existing class hooks if simpler than renaming. The pill row in the POC is the same data, just larger and full-width-of-button.

---

## Behavior Preservation — DO NOT BREAK

The visual refactor must keep all existing JS hooks and event listeners working. Specifically:

### Element IDs / Classes — preserve or alias
The current code (`court.html` lines 4677–4820, 5524–5540) attaches listeners to these IDs. Either keep them as-is on the new markup, or update the listeners to point at the new IDs. **Do not silently drop any listener.**

| Current ID / selector | Purpose | SFX |
|---|---|---|
| `#play-nav-up` | OFF row up arrow | `click-tiny.wav` |
| `#play-nav-down` | OFF row down arrow | `click-tiny.wav` |
| `#defense-nav-up` | DEF row up arrow | `click-tiny.wav` |
| `#defense-nav-down` | DEF row down arrow | `click-tiny.wav` |
| `.play-option` (offense card click → select) | Confirm offense play | `confirm-2.mp3` |
| `defenseCardEl` (defense card click → select) | Confirm defense scheme | `confirm-2.mp3` |
| `#clear-offense-card-x` (or wherever the OFF ✕ binds) | Clear OFF override | `x-back.mp3` |
| `#clear-defense-card-x` | Clear DEF override | `x-back.mp3` |
| `#pcc-stacks-zone .pcc-stack.tempo .pcc-stack-btn` | Tempo notch click | `confirm-2.mp3` |
| `#pcc-stacks-zone .pcc-stack.aggression .pcc-stack-btn` | Aggression notch click | `confirm-2.mp3` |
| `#pcc-stacks-zone .pcc-stack.press-trap .pcc-stack-btn` | Press/Trap notch click | `confirm-2.mp3` |
| `#clear-tempo-x` | Clear tempo override | `x-back.mp3` |
| `#clear-aggression-override-x` | Clear aggression override | `x-back.mp3` |
| `#clear-press-trap-x` | Clear press/trap override | `x-back.mp3` |
| `#pause-btn` | Pause / Resume | (none currently — see note below) |
| `#timeout-btn` | Timeout | (none currently — see note below) |
| `#game-speed-btn` | Speed selector (disabled) | n/a |

### SFX — explicit preservation list

These three SFX files **must continue to fire** on their corresponding interactions exactly as they do today. Verify post-refactor by clicking through every control and listening:

- **`/sounds/click-tiny.wav`** — fires on: `#play-nav-up`, `#play-nav-down`, `#defense-nav-up`, `#defense-nav-down`. Light "tick" for arrow paging.
- **`/sounds/confirm-2.mp3`** — fires on: any offense play option select, defense scheme card select, any tempo/aggression/press-trap notch select. Heavier "lock-in" for committing a call.
- **`/sounds/x-back.mp3`** — fires on: every clear-✕ button across OFF, DEF, tempo, aggression, press/trap. Soft "undo" for clearing an override.

The `playSound(filename)` helper at `court.html` line ~3619 is the single entry point — preserve it as-is. Every new event listener that replaces an old one must call `playSound(...)` with the same filename.

### Pause / Timeout SFX — note
The current code does **not** wire SFX to `#pause-btn` or `#timeout-btn` click handlers (we grepped — no `playSound` calls associated with them). If the team wants SFX on these going forward, suggested mapping:
- Pause → would benefit from a soft "system" tone, but **do not add new SFX as part of this refactor**. Treat that as a separate ticket.
- Timeout → same.

For this ticket, simply preserve current Pause/Timeout behavior verbatim (no SFX, just the click handlers that already exist).

### State / data flow
- `courtSetPlaycallOverride(type, value)` is the canonical override-write function — keep all calls intact.
- `currentDefenseIndex`, `selectedDefenseScheme`, `playOptions`, etc. — preserve all state variables.
- `updateDefenseCardDisplay()`, `updatePlayOptions()`, `populatePlayHeadshots()` — preserve.
- The `.timeout-pips` / `#timeout-pips` / `.to-pip` markup is consumed by timeout-state-update logic elsewhere — keep the structure even if styled to match the new pill design.

---

## CSS Variables — wire to existing theme system

The POC uses these CSS custom properties. Hook them into the existing court theming:

```css
--orange: #F79420;             /* matches Styleguide brand orange */
--orange-glow: rgba(247,148,32,0.35);
--team-rgb: <r>, <g>, <b>;     /* set per active franchise team — used for top edge tint */
--bebas: 'Bebas Neue', sans-serif;
--inter: 'Inter', sans-serif;
```

`--team-rgb` should be driven by whatever theming layer currently sets team colors on `court.html` (the fallback should be a neutral color if no franchise context).

---

## Implementation Order Suggested
1. Add new CSS to `court.html` styles (or a new partial). Keep old `#playcall-center` styles temporarily to avoid breakage during cutover.
2. Replace markup inside `#playcall-center` block. Map each old element ID/class to its new equivalent.
3. Re-bind any listeners whose target IDs changed. Verify `playSound()` calls intact.
4. Manual QA on every control:
   - OFF up/down arrows → `click-tiny.wav` fires + index advances
   - OFF play card click → `confirm-2.mp3` + override sets + orange "armed" state appears
   - OFF clear ✕ → `x-back.mp3` + override clears + row returns to default state
   - Same flow for DEF
   - Tempo/Aggression/Press-Trap notch clicks → `confirm-2.mp3` + active notch lights up
   - Each strategy clear ✕ → `x-back.mp3` + clears
   - Pause toggles label and visual state, live game state syncs
   - Timeout button + pip count updates
5. Check team-color theming hairline appears subtly on franchise pages.
6. Remove old `#playcall-center` styles once new ones confirmed working.

---

## Out of Scope for This Refactor
- New SFX on Pause/Timeout (separate ticket if desired).
- Speed selector functionality (still disabled — visual only).
- Any change to override semantics (when OFF auto-clears, when DEF clears, etc.).
- Player headshot data wiring (already in place via `populatePlayHeadshots()`).

---

## Questions for Cursor / Engineering
- The POC uses a fully new class namespace (`.pcc-row`, `.pcc-dial`, etc.) to avoid collisions with legacy `#pcc-stacks-zone` styles. Confirm whether to keep the new namespace and update listener selectors, or rename the new markup back to legacy class names to minimize JS changes. Recommendation: **keep new namespace + update selectors** — cleaner long-term.
- Confirm the team-color hook on `court.html` so `--team-rgb` can be set correctly.
