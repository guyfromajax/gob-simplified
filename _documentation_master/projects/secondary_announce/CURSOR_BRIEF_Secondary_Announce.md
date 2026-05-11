# Cursor Brief — Secondary Announcement Tier

Companion to `_documentation_master/05_GP_Supporting_Systems/Announcement_System.md`.
Design reference: `Secondary Announce.html` in this project (source of truth for layout, type, color, motion).

## Goal
Introduce a **secondary** announcement tier that displays as a top-edge ribbon under the scoreboard, so non-critical announcements no longer block sprite action in center court. The primary center-court overlay is unchanged.

## Which announcements route to secondary
The following move from primary → secondary:
- **Fast Break** (start announcement)
- **Press** (start announcement)
- **Trap** (start announcement)
- **FB Outlet Pass Denied**
- **Nice Stop** (CR Fast Break defensive stop)
- **Fast Break / No Fast Break** decision announcement for the outlet passer on RR Fast Breaks
- **Slow It Down**
- **Quick Shot**
- **Final Shot**

Everything else stays on the primary center-court overlay. **AND-1 and the foul card stay primary.**

## Routing contract
- Caller decides the tier per event. Add a `tier` field to the payload passed to `window.showAnnouncementOverlay(data)`:
  - `tier: 'primary'` (default; existing behavior)
  - `tier: 'secondary'`
- `showAnnouncementOverlay(data)` branches on `data.tier`. Keep the builder functions (`showAnnouncement`, `showAndOneAnnouncement`, etc.) unchanged externally; add a `showSecondaryAnnouncement(data)` helper for clarity at call sites.

## Payload shape (secondary)
```
{
  tier: 'secondary',
  eventText: 'FB OUTLET PASS DENIED',     // headline, uppercased
  withPlayer: true | false,
  photoUrl, jersey, lastName,             // when withPlayer === true
  teamId,                                 // drives left stripe color
}
```

### Team color resolution
- If `withPlayer === true`: the player's team.
- If `withPlayer === false` (no-player events): the **offense / initiating** team.
  - Press → defense team (the team applying pressure)
  - Trap → defense team
  - Fast Break → offense team
  - Slow It Down / Quick Shot / Final Shot → offense team (team currently with the ball)
  - Nice Stop → defense team (the team that got the stop)

## DOM & mount
- Mount `#announcement-overlay-secondary` as a sibling of the existing `#announcement-overlay`, inside `#phaser-container`.
- Anchor: top edge of the court canvas, `4px` offset from the scoreboard.
- Ribbon: `64px` tall, full width of the court column with `16px` gutters left and right.
- z-index: above court sprites, below modal/foul card.

## Visual spec (see `Secondary Announce.html`)
- **Surface:** dark charcoal with the team color bleeding in from the left edge of the gradient (matches primary's vocabulary).
- **Left team stripe:** 6–8px solid team color with soft glow.
- **Headshot block:** 48×48, rounded 6px, 1px white-alpha border.
- **Jersey / last-name chip:** Bebas Neue Pro. Jersey small (11px, team color, brightness +35%); last name 18px white.
- **Headline:** **Bebas Neue Pro, italic 700, 36px** (40px in no-player state), `letter-spacing: 1.5px`, vertically centered in the ribbon (`align-self: center`, `line-height: 1`).
- **Orange `!` accent** on the trailing bang — matches primary.
- **No-player variant:** drop the headshot + chip, center the headline horizontally.

## Typography rule — applies to BOTH tiers
Use **Bebas Neue Pro** for all primary and secondary announcement headlines. The current production CSS uses Barlow Condensed; that's a divergence from the Styleguide. Migrate primary to Bebas Neue Pro in the same PR. Secondary ships on Bebas Neue Pro from day one.

## Motion
- **Entry:** slides DOWN from `translateY(-110%)` to `0`, fade in. `260ms cubic-bezier(.22,1,.36,1)` for transform, `220ms ease` for opacity. Subtle `secPulse` (scale 0.96 → 1.02 → 1.00) on the headline at `60ms` delay.
- **Exit:** slide UP + fade, same easing.
- Reduced-motion: skip transforms; fade only.

## Timing (matches primary contract)
- On-screen: **2200 ms** (overlay duration).
- Engine hold before next animation: **1000 ms** uniform. **Do not reduce below 1000 ms.**
- These come from `Announcement_System.md`; do not diverge.

## Concurrency — coexist
- Secondary and primary may be on screen **at the same time**. Secondary sits at the top edge under the scoreboard; primary sits in the center of the court. They do not visually overlap.
- Each tier manages its own visibility lifecycle independently. Don't queue across tiers.
- Within a single tier, the existing queuing behavior is preserved (only one overlay of that tier visible at a time).

## SFX
- **No SFX** for any secondary announcement in v1. Sound design will be added later.
- Primary's whistles (`whistle-1.mp3`, `whistle-3.mp3`) remain primary-only and unchanged.

## Out of scope
- `decisionPillText` / `decisionPillTone` are not used. There is no good-decision / bad-decision pill or indicator in the secondary design.
- Right-side event tag (OFFENSE / DEFENSE / FCP / HCT) is intentionally omitted — the team-color stripe carries the team signal.
- No changes to the standard (primary) announcement layout, except the typeface migration noted above.

## QA checklist
- [ ] Secondary ribbon mounts under scoreboard with 4px offset, 64px tall
- [ ] Player-present and player-absent layouts both render with vertically centered text
- [ ] Team color stripe correctly reflects the right team per the resolution table above
- [ ] Timing is 2200ms visible + 1000ms hold for both tiers
- [ ] Secondary and primary can coexist on screen without visual collision
- [ ] Reduced-motion respected
- [ ] No regression to AND-1 / foul card primary flows
- [ ] Primary headline uses Bebas Neue Pro (migration from Barlow Condensed)
- [ ] All routed events (list at top) reliably appear as secondary, not primary
