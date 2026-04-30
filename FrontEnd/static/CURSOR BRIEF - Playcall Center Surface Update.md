# Cursor Brief — Playcall Center Surface Update (Brushed Steel)

## Scope
Visual-only update to the Playcall Center container in `FrontEnd/static/court.html`. **No markup changes, no JS changes, no SFX changes.** Only the container surface and a few related visual properties.

The goal: lift the Playcall Center visually so it reads as the **action surface** (a tier above the read-only data panels like Player/Team Box Scores). The court remains the visual hero; this just makes the cockpit feel tactile rather than recessive.

Reference file: `Playcall Center POC.html` (in the design project) — the surface treatment in that file is now updated to match variant C below. Use it as the visual source of truth.

## Changes

### 1. Container surface (`#playcall-center`)
Replace the existing background, border, and add new shadows:

```css
#playcall-center {
  /* keep existing width / height / display / grid / radius / overflow */
  background: linear-gradient(180deg, #2a2f3a 0%, #20242e 50%, #262a35 100%);
  border: 1px solid rgba(255,255,255,0.16);
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.12),
    inset 0 -1px 0 rgba(0,0,0,0.5),
    0 -2px 16px -4px rgba(0,0,0,0.7),
    0 4px 12px -4px rgba(0,0,0,0.5);
}
```

### 2. Subtle vertical brushed-steel striations
Add a `::before` pseudo-element (replaces the previous `::before` if any was used for the team-color hairline — see #3):

```css
#playcall-center::before {
  content: '';
  position: absolute; inset: 0;
  background: repeating-linear-gradient(
    180deg,
    rgba(255,255,255,0.012) 0px,
    rgba(255,255,255,0.012) 1px,
    transparent 1px,
    transparent 3px
  );
  pointer-events: none;
  z-index: 1;
}
```

### 3. Move team-color hairline to its own element
The previous `::before` was the team-color hairline. Move it to a real element so the brush striations can take over `::before`. Add a single `<span class="pcc-hairline"></span>` as the **first child** inside `#playcall-center`:

```css
.pcc-hairline {
  position: absolute; top: 0; left: 0; right: 0; height: 1px;
  background: linear-gradient(to right,
    transparent 0%,
    rgba(var(--team-rgb), 0.5) 30%,
    rgba(var(--team-rgb), 0.5) 70%,
    transparent 100%);
  pointer-events: none;
  z-index: 3;
}
```

The `::after` (24px team-color top gradient bleed) stays exactly as it was — just bump its `z-index: 2`.

Add `#playcall-center > * { position: relative; z-index: 2; }` so all real content sits above the brush striations.

### 4. Inner zones — slightly stronger dividers
Bump the divider color since the panel surface is lighter now:

```css
.pcc-divider { background: rgba(255,255,255,0.08); } /* was rgba(255,255,255,0.05) */
```

### 5. OFF/DEF rows — recessed slot treatment
The override rows now sit on a lighter surface, so they need a darker recessed look:

```css
.pcc-row {
  background: rgba(0,0,0,0.25);                /* was rgba(255,255,255,0.02) */
  border-color: rgba(255,255,255,0.08);        /* was rgba(255,255,255,0.04) */
  box-shadow: inset 0 1px 0 rgba(0,0,0,0.3);   /* NEW — adds the "punched into surface" feel */
}
```

The `.armed` and `.active` orange states are unchanged.

### 6. Inactive play name color
On the lifted surface, the previous 35% white was too dim:

```css
.pcc-row:not(.active):not(.armed) .pcc-call-name {
  color: rgba(255,255,255,0.55);  /* was 0.35 */
}
```

### 7. Up/down arrows — slight bump
```css
.pcc-arrow {
  border-color: rgba(255,255,255,0.14);   /* was 0.08 */
  color: rgba(255,255,255,0.65);          /* was 0.5 */
}
```

### 8. Dial track — slight bump
```css
.pcc-dial-track {
  background: rgba(255,255,255,0.14);   /* was 0.08 */
}
```

### 9. Notch resting state — adjust for new surface
```css
.pcc-notch {
  background: #1a1d25;                     /* was #0a0c12 */
  border-color: rgba(255,255,255,0.32);    /* was 0.18 */
}
```

The `.on` orange state is unchanged.

### 10. Pause button — flip to darker treatment
The pause button must now anchor against the lifted steel surface, so it gets the *darker* color (inverse of before):

```css
.pcc-pause {
  background: linear-gradient(180deg, #14171e 0%, #0c0e13 100%);
  border-color: rgba(255,255,255,0.28);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.1), 0 4px 16px -6px rgba(0,0,0,0.8);
}
.pcc-pause:hover { filter: brightness(1.18); border-color: rgba(255,255,255,0.42); }
.pcc-pause.paused {
  background: linear-gradient(180deg, #1c2028 0%, #14171e 100%);
  border-color: rgba(255,255,255,0.42);
}
```

### 11. Timeout button — match new emphasis
```css
.pcc-timeout {
  border-color: rgba(255,255,255,0.28);   /* was 0.18 */
}
.pcc-timeout:hover {
  background: rgba(255,255,255,0.06);     /* was 0.04 */
  border-color: rgba(255,255,255,0.42);   /* was 0.32 */
}
```

### 12. Used timeout pill
```css
.pcc-pill.used {
  background: rgba(255,255,255,0.18);   /* was 0.10 */
}
```

## What Did NOT Change
- HTML structure (only added a single `.pcc-hairline` span)
- All event listeners
- All `playSound()` calls (`click-tiny.wav`, `confirm-2.mp3`, `x-back.mp3`)
- Override semantics (OFF auto-clear, DEF persistence)
- Strategy notch behavior
- Pause / Timeout JS
- The orange action color (`#F79420`) — used identically on armed/active states, dial notches, timeout pills

## Sanity Check After Implementation
1. Click through every control — every original SFX still fires.
2. Visual: the Playcall Center clearly reads as a lifted/metallic surface above the page atmosphere.
3. The orange "armed" and "active" states still pop strongly (they should pop **harder** now thanks to the darker recessed row backgrounds).
4. The Pause button reads as a deliberate, mounted-into-the-cockpit element (not floating on top).
5. Top edge: the team-color hairline + 24px gradient bleed still appears.

## If This Feels Too Strong
If on the live page the steel treatment overpowers the court (especially during high-action moments — multiple overrides armed, all dials lit), fall back to "Variant B" from the comparison file: same structure, but use these surface values instead:

```css
#playcall-center {
  background: linear-gradient(180deg, #1c2028 0%, #15181f 50%, #1a1d25 100%);
  border: 1px solid rgba(255,255,255,0.12);
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.08),
    inset 0 -1px 0 rgba(0,0,0,0.4),
    0 -2px 12px -4px rgba(0,0,0,0.6),
    0 2px 8px -4px rgba(0,0,0,0.4);
}
/* and remove the brushed-steel ::before striation block entirely */
```

Everything else stays the same.
