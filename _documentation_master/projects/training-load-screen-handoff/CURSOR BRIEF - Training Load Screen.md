# CURSOR BRIEF — Training Load Screen (League News Wire)

**Source of truth for layout, type and motion:** `Training Load Screen.html` +
`training-newswire.jsx` + `training-newswire-data.js` in the design project. Open the
prototype before writing code; every number below is lifted from it.

**Replaces:** the current training load experience — the rotating archetype-voiced
highlight lines driven by `training_feed_lines.py` / `training_loading_highlights.py`,
shown through `PageLoadOverlay.show({variant:'pulse', subtitle})` +
`updatePulseSubtitle()`.

---

## 1. Objective

While a franchise training run executes (10–25s), replace the generic per-player
training highlights with rotating **national league news graphics**. Keep an
unmistakable signal that training is running in the background.

The training highlights are **not relocated** — they already live in the Training
Report and that stays their only home.

---

## 2. Scope of change

### Remove
- `training.js`: `TRAINING_CPU_HIGHLIGHT_MS`, `TRAINING_HIGHLIGHT_FALLBACK`,
  `buildRandomizedTrainingHighlightLines()`, `shuffleArrayInPlace()` (if unused
  elsewhere), and the `highlightStreamId` interval that pumps
  `updatePulseSubtitle(lines[i])`.
- `pageLoadOverlay.js`: nothing is deleted. The `pulse` variant stays exactly as-is —
  it is still used by court/FCC/post-game (`buildPostgameStatFeed`). The news wire is a
  **new variant**, not a rewrite of an existing one.
- Backend: `training_highlights` may stay on the training response (Training Report may
  use it). The load screen simply stops reading it. Confirm before removing anything
  server-side.

### Add
- `pageLoadOverlay.js`: a new `variant: 'newswire'` that renders the wire shell and owns
  the rotation. Same show/hide contract as the other variants.
- One data source for league news (see §3).

### Keep
- The green pulse bar, verbatim. Same gradient, same `pageLoadOverlayPulseBar`
  keyframes. Only the dimensions change (§6).

---

## 3. Data contract

The payload shape the UI needs is documented at the top of
`training-newswire-data.js`. Restated:

```js
{
  phase: 'preseason' | 'in_season',
  season: 1,
  week: 4,                        // week just completed (in_season)
  top10: [
    { rank, team_slug, team_name, wins, losses, conference, region }
  ],
  leaders: {
    pts | treb | ast | def_pct | stl | blk | tpm | fg_pct: [
      { rank, player_id, name, team_slug, team_name, value, display }
    ]
  },
  key_games: [
    { away_rank, away_slug, away_name, home_rank, home_slug, home_name, rank_sum }
  ],
  preseason: {
    top10:   [{ rank, team_slug, team_name, last_record, conference, region }],
    marquee: [{ week, away_rank, away_slug, away_name, home_rank, home_slug, home_name }]
  }
}
```

Rules:
- Every list is **exactly 10** entries, pre-sorted, pre-ranked. The client does no
  sorting, ranking, filtering or qualifier math.
- `display` is the **preformatted** stat string (`"63"`, `"78.6%"`). The client never
  formats a number. `value` is the raw number, for tests only.
- `key_games` is sorted by `rank_sum` ascending. Away team is the left slot, home the
  right — always.
- Qualifiers are applied **server-side**: `def_pct` requires ≥6.0 DEFA/game, `fg_pct`
  requires ≥7.0 FGA/game.
- `conference` is the integer 1–16 from `team.conference`. `region` is the letter A–H
  derived with the shipped rule `String.fromCharCode(65 + floor((conference-1)/2))`
  (`js/shared/teamPicker.js`). **Send both** — do not re-derive client-side.
- `phase` is authoritative. The client must not infer preseason from `week === 0`.
- Any key that is missing or empty **drops that graphic from the rotation**. A payload
  with only `top10` is valid and rotates one card.

### Where it comes from — recommendation
The data already exists across `/franchise/command-center/data`, `/franchise/standings`,
`/franchise/leaders`. **Build one consolidated read-only endpoint**
(`GET /franchise/league-news?franchise_id=…`) that assembles the object above.

Rationale: a load screen cannot afford a client-side fan-out to 3–4 endpoints and then
a client-side join — that is 3–4 chances to be slower than the training run it is
supposed to cover. One request, one shape, one cache key.

Do **not** bolt it onto the training-run response. It must be fetchable *before*
training starts (§4).

---

## 4. Fetch timing — the thing most likely to be got wrong

The first card must be on screen the instant the overlay appears. It must never be
preceded by a spinner or an empty frame.

```
1. User taps Submit.
2. Fire the league-news GET and the training POST *in parallel*. Do not await news.
3. Show the overlay immediately:
     - news resolved  → render card 1, start the 6s clock
     - news pending   → render header + pulse ONLY (no card frame, no skeleton rows);
                        fade card 1 in when it lands and start the clock then
     - news rejected  → fall back to PageLoadOverlay's existing `pulse` variant with
                        the team banner and the copy "Training in progress" — i.e. today's
                        overlay minus the highlight lines. Never show a broken wire.
4. Rotation is independent of training progress. It keeps cycling until hide().
```

Cache the payload for the session (it changes once per week, not once per training run).
Prefetching it on Locker Room / FCC entry is a legitimate optimisation — the load screen
should ideally never wait at all.

---

## 5. Rotation

- **Fixed order**, not shuffled:
  `top10 → key_games → pts → treb → ast → def_pct → stl → blk → tpm → fg_pct`,
  then wrap. Users typically see only 2–4 cards, so the two team-level graphics lead
  and the running order is deterministic and reviewable.
- **Preseason order:** `pre_top10 → marquee`, then wrap.
- **6000ms per card.** Single constant, one place.
- **Crossfade:** outgoing card `opacity → 0` over 260ms starting at t=5740ms; incoming
  card `opacity 0→1, translateY(6px)→0` over 340ms, `cubic-bezier(.2,.7,.3,1)`.
- **Timing sweep:** a 1px, `rgba(255,255,255,.2)` line on the card's bottom edge,
  animating `width: 0 → 100%` linearly over the 6000ms. This is the only "time
  remaining" affordance on the card and it is deliberately near-silent.
- Rotation must be **paused/cleared on `hide()`**. Clear the timers the same way
  `clearPulseFeedTimer()` does today — a leaked interval on a load overlay outlives the
  page.
- `prefers-reduced-motion: reduce` → hard cut instead of crossfade, and no sweep line.
  Rotation itself continues.

---

## 6. Chrome

**Header** (`display:flex; justify-content:space-between; align-items:center; padding:0 6px`)
- Left: `Around the League` — Bebas Neue 22px, `letter-spacing:.07em`, uppercase,
  `rgba(255,255,255,.82)`.
- Right, in order, `gap:24px`: the pulse group, then the season context.
- Season context: Inter 11px/700, `letter-spacing:.17em`, uppercase,
  `rgba(255,255,255,.36)`. In-season `Season 1 · Week 4`; preseason `Season 1 · Preseason`.

**Pulse group — header placement, compact variant**
- Bar: `96×5px`, `border-radius:999px`, track `rgba(255,255,255,.08)`,
  `box-shadow: inset 0 1px 0 rgba(255,255,255,.05)`.
- Fill: `linear-gradient(90deg, rgba(52,236,39,.35), #34EC27 48%, rgba(52,236,39,.45))`,
  `transform-origin:left center`, `animation: pageLoadOverlayPulseBar 1.2s ease-in-out infinite`
  — the existing shipped keyframes, unchanged.
- Copy: `Training in progress`, Inter 9.5px/700, `letter-spacing:.16em`, uppercase,
  `rgba(255,255,255,.46)`, 12px to the right of the bar.
- **Constraint:** the pulse group must read lighter in weight than the "Around the
  League" mark. Green is scarce in the GOB system and pulls hard; if it starts competing
  with the wordmark it belongs back under the card, not in the header.

**No footer.** The card's own sweep line carries card-level timing.

---

## 7. Card

Shell — the standard Type 1 shell treatment from `Styleguide_updated.md`, verbatim:
```css
border-radius:24px;
border:1px solid rgba(255,255,255,.09);
background:linear-gradient(160deg,rgba(255,255,255,.028) 0%,rgba(255,255,255,.014) 18%,transparent 40%),rgba(14,16,24,.96);
box-shadow:0 20px 48px rgba(0,0,0,.45), inset 0 1px 0 rgba(255,255,255,.07);
```
Plus the shell's diagonal banding on `::after`
(`repeating-linear-gradient(132deg, transparent 0 102px, rgba(255,255,255,.012) 102px 103px, transparent 103px 208px)`).
Padding `38px 46px 44px`. Overlay backdrop `#07080c`, card width
`min(1120px, 100vw - 72px)`.

Header block, every card:
- Kicker: Inter 11.5px/700, `letter-spacing:.17em`, uppercase, `rgba(255,255,255,.4)`.
- Title: Bebas Neue 60px, `line-height:.92`, `letter-spacing:.02em`, `#fff`, 28px below.

Two columns, ranks 1–5 left / 6–10 right. `grid-template-columns:1fr 1fr`; left column
`padding-right:44px`, right column `padding-left:44px` + `border-left:1px solid rgba(255,255,255,.07)`.

Rows: 76px tall, `border-top:1px solid rgba(255,255,255,.055)` (none on `:first-child`),
`:nth-child(even)` gets `background:rgba(255,255,255,.016)`. Rank numeral is Bebas Neue
26px `rgba(255,255,255,.38)`, right-aligned in a 30px column.

### Row archetypes

**Team row** — `grid: 30px 1fr auto; gap:16px` (National Top 10, Preseason Top 10)
```
1   [logo 146px]   Houston Jesuit            3-0
                   Region F · Conference 12
```
- Name: Inter 16px/600 `#fff`, ellipsis on overflow.
- Meta: Inter 12px/500, `letter-spacing:.03em`, `rgba(255,255,255,.44)`, `nowrap`.
  Literal format: `Region {region} · Conference {conference}`.
- Trailing: Inter 16px/600 `rgba(255,255,255,.72)`, `font-variant-numeric:tabular-nums`.
  In-season `W-L`; preseason the prior-season record.

**Matchup row** — `grid: 28px 1fr 20px 1fr 28px; gap:11px` (Key Games, Marquee)
```
#1  [away logo]  @  [home logo]  #7
```
- Seeds: Bebas Neue 20px `rgba(255,255,255,.5)`, centred.
- `@`: Inter 11px/700 uppercase `rgba(255,255,255,.32)`, centred.
- Logos `width:100%` of their grid column. Away left, home right, always.

**Player row** — `grid: 30px 46px 1fr auto; gap:16px` (all 8 leaderboards)
```
1   (○)   Darnell Love        63
          Xavien
```
- Headshot: 46px circle, `overflow:hidden`, `background:rgba(255,255,255,.05)`,
  `border:1px solid rgba(255,255,255,.1)`, image `object-fit:cover`.
- Name: Inter 17px/600 `#fff`, ellipsis. Team: Inter 12.5px/500 `rgba(255,255,255,.45)`.
- Stat: Bebas Neue 30px `#fff`, `letter-spacing:.02em`, right-aligned, `min-width:64px`.

### Titles and kickers

| id | Title | Kicker |
|---|---|---|
| `top10` | National Top 10 | League standings · through week {W} |
| `key_games` | Upcoming Key Games | Week {W+1} · ranked by combined national rank |
| `pts` | National Scoring Leaders | Season totals · through week {W} |
| `treb` | National Rebounding Leaders | Season totals · through week {W} |
| `ast` | National Assist Leaders | Season totals · through week {W} |
| `def_pct` | National Defense Leaders | Minimum 6.0 DEFA per game to qualify |
| `stl` | National Steal Leaders | Season totals · through week {W} |
| `blk` | National Block Leaders | Season totals · through week {W} |
| `tpm` | National 3PT Leaders | Three-pointers made · through week {W} |
| `fg_pct` | National FG% Leaders | Minimum 7.0 FGA per game to qualify |
| `pre_top10` | Preseason Top 10 | Preseason edition · projected by program rank |
| `marquee` | Marquee Matchups | Preseason edition · the season's ten biggest games |

---

## 8. Assets

**Team logo — use `banner_card.webp`, not `banner_primary.jpg`.**
```
/images/teams/{slug}/{slug}_banner_card.webp
fallback: /images/teams/general/general_banner_card.webp
```
Both files carry the identical lockup; `_card` is 400×141 / ~10KB, `_primary` is
1920×679 / ~400KB. A Top 10 card renders 10 marks and a Key Games card renders 20 — the
primary asset would put **~8MB on the wire during a load screen**, competing with the
training request it is covering. 400×141 is already ~2.7× the 146px render width, so
there is no quality argument for the larger file. (This reverses the earlier direction to
use `_primary`; flag it if `_card` is not guaranteed present for all 128 programs.)

Note `images/teams/IDA/` is uppercase on disk while the file stem stays lowercase — keep
the existing folder-case map (`{ ida: 'IDA' }`) rather than assuming folder === slug.

**Player headshot**
```
API_CONFIG.getPlayerImageUrl(player_id, { size: 'card' })
```
`onerror` → neutral silhouette: 46px circle, same border/background as the photo slot,
containing a head circle + shoulder arc at `fill: rgba(255,255,255,.24)`. The silhouette
is the loading/error state only — never the intended state.

Preload discipline: prefetch the **next** card's images during the current card's 6s
window, so a card never fades in mid-load. With 12 graphics that is at most 20 small
images ahead.

---

## 9. Empty, error and edge states

| Condition | Behaviour |
|---|---|
| News request fails / times out | Existing `pulse` variant, team banner, "Training in progress". No wire. |
| One list missing or `< 10` entries | Drop that graphic from the rotation. Never pad, never render short columns. |
| Only one graphic available | Show it, no rotation, no sweep line. |
| `phase: 'preseason'` | Preseason deck only. In-season cards are unreachable. |
| Headshot 404 | Silhouette, silently. No retry loop. |
| Team art 404 | `general_banner_card.webp`. |
| Training finishes mid-card | `hide()` immediately. Do not let the current card finish. |

---

## 10. Accessibility

- Overlay keeps today's attributes: `role="status"`, `aria-live="polite"`,
  `aria-busy="true"`, flipped on `hide()`.
- The rotating card is **`aria-hidden="true"`**. It is ambient content; announcing a new
  leaderboard every 6s to a screen reader is hostile.
- The single live announcement is the pulse copy: "Training in progress".
- Pulse bar container `aria-hidden="true"` (decorative).

---

## 11. Acceptance criteria

1. Submitting franchise training shows the wire with a card already populated — no
   spinner, no empty frame, no skeleton.
2. Cards advance every 6s in the fixed order, crossfading, with the sweep line
   completing exactly as the card changes.
3. All 10 in-season graphics render with 10 real entries and correct ranks; all 8
   leaderboards use server-formatted `display` strings.
4. `Region X · Conference N` renders under every Top 10 team name and matches
   `team.conference`.
5. The green pulse and "Training in progress" copy are visible in the header for the
   entire run and are subordinate to the wordmark.
6. Zero archetype-voiced training highlight lines appear anywhere on the load screen.
7. Killing the news endpoint degrades to today's pulse overlay with no visual breakage
   and no console errors.
8. Rotation timers are cleared on `hide()` — verify no interval survives navigation.
9. Preseason franchise shows only the two preseason graphics.
10. Nothing regresses in the `pulse` variant used by court / FCC / post-game.

---

## 12. Decisions still open

1. **Consolidated endpoint vs client fan-out.** §3 recommends one endpoint. Needs a yes.
2. **`_card` vs `_primary` team art.** §8 recommends `_card` and explains why. Needs a
   confirmation that `_card` exists for all 128 programs.
3. **Headshot size token.** Is `size: 'card'` the smallest available variant? A 46px
   circle wants ~96–128px source; if a `thumb` exists, use it and update §8.
4. **Practice Squad standings** (`/franchise/practice-squad/standings`) was listed as
   available but no graphic in the brief consumes it. Is a Practice Squad card wanted as
   an 11th graphic, or is that endpoint out of scope here?
5. **Cache scope.** Session-cached per franchise+week is the assumption. Confirm there is
   no mid-week invalidation case that would serve stale ranks.
