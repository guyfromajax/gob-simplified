# Chapter 7 PR 3 — Office weekly "Since last week" card + PR2 door-art check

Branch `app/office-weekly-card`, merged with `origin/develop` (Ch7 design handoff,
milestone-modal queue v2, repo-hygiene). Builds the `.wkc` weekly card that replaces
the Result + What moved cards in Office column 1, and closes the PR2 door-art check.

Jamie's overrides applied: **no team-colour wash** (win or loss) and **neutral ▲/▼
deltas** (no green/red). Reward gold appears **only** on the exceptional-gain marker.

---

## 0. Door-art check (PR2 follow-up) — FIXTURE, not a desktop bug

`reports/home-base-offline/populated-1280.png` showed the generic swirl banner on both
doors while the same program (Lawrence) showed real art in Top Seasons.

**Finding:** a fixture artifact, not a desktop/loopback bug.
- Door art resolves from the franchise **display name** via `nameToTeamSlug`
  (`resolveFranchiseSlotBanner` → `getSquareLogoPath` → `getTeamAssetPath(name,'banner_primary')`).
- The PR2 offline fixture seeded display names `"Lawrence Eagles"` / `"Chapel Hill Sky"`,
  whose derived slugs (`lawrence_eagles`, `chapel_hill_sky`) have no files on disk → the
  banner 404s → general fallback. Top Seasons used the server-provided `team_slug`
  (`lawrence`) and so showed real art.
- The door-art path is profile-independent (no `desktop` branch), and a real franchise's
  `user_team_id` is the canonical team name (`Lawrence` → `lawrence`, which has art). So
  real programs render their real door banners.

**Proof:** `reports/office-weekly-card/home-base-doors-1280.png` renders the offline Home
Base on the desktop/loopback path with canonical names `Lawrence` / `Chapel Hill` — both
doors show their real banners (test asserts the `<img>` src is the per-team file, not
`general_banner`, and that it actually loads). No code fix was needed; the PR2 spec's own
fixture names are the only thing that produced general art. Captured via a self-contained
test in `office-weekly-card.spec.js` (no change to the PR2 spec, which stays on develop).

## 1. Cards replaced

| Before (column 1) | After |
| --- | --- |
| `resultCard` (`.office-res`) + `whatMovedCard` (`.office-mv`) | one `sinceLastWeekCard` (`.wkc`) |
| col-2 moment-queue "This week" card (`.office-weekly`) | removed; its items fold into the `.wkc` Also row / "+N more" |

`resultCard`, `whatMovedCard`, `movedCell`, `attrChip` and the `.office-weekly` CSS block
were deleted (dead after the swap). `attrChip` became `gainChip` (the neutral `.gc` chip).

**Test files migrated to the new markup** (they asserted the old office DOM, so they had to
change with it — beyond the brief's staging list, but required for a green gate):
`office-frontend.spec.js`, `moment-queue.spec.js`, `store-client.spec.js` (`.res-hl` → `.wkc-hl`),
`t2-roster.spec.js` (`.attr-chip` → `.wkc .gn .gc`, plus a density-class wait).

## 2. Data used (all from `office_digest`, nothing recomputed)

| Element | Field |
| --- | --- |
| WIN/LOSS tag, week · round · site, Box score | `result.user_won`, `result.week`, `result.round_name`, `result.site`, `result.box_score` |
| Scoreboard (your team on top, count-up on win) | `result` sides via `userSide`/`otherSide`, `what_moved.national_rank.now` (your rank), `result.opponent_rank` |
| Headline (only when present) | `result.headline` |
| POTG / Team leader + square portrait + PTS/REB/AST | `result.leader{player_id,name,stats}`, `result.leader_role`; portrait `API_CONFIG.getPlayerImageUrl` → silhouette → initials |
| Four badges (National, Conference, Record, Streak) | `what_moved.national_rank`, `.conference_standing`, `.record`, `.streak`; delta omitted when 0/null |
| Training rows + exceptional marker + key | `what_moved.attribute_changes[]` (grouped by player), `.exceptional` (server flag) → `.gc.xg` + `.xg-key` |
| Also row + "+N more" | `office_digest.also` + `office_digest.weekly_card_items` |
| All changes → | `trainingReportHref` |
| Entrance-once + win sting | `result.result_key` (localStorage), `playSfx(STING_WIN)` |

## 3. Motion

Rides the office `.arriving`/`.calm` system. Gated **once per `result_key`** in
`localStorage` (`arrivalFor`, cached per key for the page's life so a re-render doesn't
replay; try/catch → final state if storage fails). Win: card rise, score count-up,
staggered items, badge stagger, the gold halo once. Loss: fade-in only, no count-up, no
stagger, no sound. `STING_WIN` fires at the 720ms cue on a win's **first showing only**
(independent of reduced motion — it follows the audio settings); a loss is silent.
Reduced motion → final state, no count-up, no halo (sound still follows audio settings).

## Portrait fix (from review)

The POTG/Team-leader portrait was showing clipped top-left initials and no image. `portrait()`
now: `getPlayerImageUrl(player_id)` → the shared silhouette (`getGenericHeadshotUrl`) on a
miss → centred initials only if even the silhouette is unavailable; the box is square
(`.wkc .pg2 .portrait` `display:grid; place-items:center`, UX_System §2). The card fixtures
use a real served headshot uuid, so `win-1280`/`lossgain-1280` show a real square headshot.

## Omissions / deviations

- **`gob-tokens.css` changed (intentional):** added `--dur-gain-sweep: 700ms` and
  `--delay-cue: 720ms` (the two ch7 weekly-motion tokens the card needs; they live beside
  the other motion tokens rather than being redeclared per-component).
- **Standings windowing at 1280×720:** the single `.wkc` card replaced column 1's two
  cards; the middle-column standings window lands at **3 rows (was 4)** at the smallest
  supported size. Investigated thoroughly — columns still measure identical (570px) to
  develop; standings shows all 8 at ≥1440. `office-frontend.spec.js` updated to `>= 3`
  at 1280×720 with a comment.
- **"+N more" expanded state** can push the card's footer toward the fold when three
  folded moments are open at once (a rare payload, user-initiated); the collapsed states
  (win/loss/gain/lossgain) all fit column 1 at both sizes.
- **`data-player-id`** added to training rows (`.gn`) for player identification/linking.

## Frame comparison (`frames/office-weekly.html?s=win|loss|gain|lossgain`)

| Screenshot | Differences from the frame (other than the removed wash) |
| --- | --- |
| `win-1280` | none of substance — WIN white plate, neutral card, scoreboard (you on top), headline, POTG + real square headshot, four badges, training, All changes. Deltas neutral (frame keeps green in some builds; we render t100/t60 per Jamie). |
| `loss-1280` | LOSS outline tag; both scores t87; Team leader; Also row + "+2 more". No wash, no red. |
| `gain-1280` | Exceptional-gain marker: gold diamond + ring + gold ▲ on the one chip, gold "Exceptional gain" key. Everything else neutral. |
| `lossgain-1280` | The gold marker on a loss; card otherwise the dignified loss. |
| `win-1920` | Scales up; nothing clipped; training cap 5 (only 3 movers here). |
| `also-expanded-1280` | "+N more" expanded inline with a "Show less" toggle (a Ch7-brief addition beyond the frame's single Also row). |
| `home-base-doors-1280` | (door-art proof) real door banners with canonical names. |

## Gates (UX_System §8)

- **pytest** `--ignore=tests/e2e -q`: **4123 passed, 14 skipped, 109 xfailed, 1 xpassed, 0 failed** (197s).
- **Playwright** full suite, `workers=1`, port free, `CI` unset, no other run:
  **722 passed, 3 skipped, 0 failed** of 725 (11.2 min). A first run surfaced 8 failures — 7
  `store-client.spec.js` and 1 `t2-roster.spec.js` — all from those specs asserting the old
  office markup (`.res-hl`, `.attr-chip`). Migrated to the `.wkc` structure, and the card now
  renders training/badges even when `result` is null (a week with training but no game — the
  old What-moved card did too), so training is never dropped. t2-roster also got a density-class
  wait before it measures chip font sizes (a rare init race). Re-run is clean, 0 failed.

## Self-check

Opened each screenshot:
- **Green** appears only on the top-bar "Play Next Game" advance — never on the card, the
  WIN/LOSS tag, badges, scores or deltas. **Orange:** none. **Navy:** none needed here.
- **Reward gold** appears only on the exceptional-gain marker (diamond, ring, delta) and the
  "Exceptional gain" key — asserted by computed colour `rgb(240, 197, 96)`; the WIN plate,
  badges, scores and non-xg chips are not gold.
- **No team wash:** the card background is the neutral surface on win and loss (asserted
  identical + free of the seeded team colour). The white WIN plate / outline LOSS tag carries
  the result.
- **LOSS dignified:** both teams' scores at t87 (same computed colour), ▼ deltas t60, "Team
  leader", fade only, silent.
- **Fit:** win/loss/gain/lossgain fit column 1 at 1280×720 and 1920×1080 with nothing
  clipped or below the fold.
- **Doors:** real banners render for canonical program names on the desktop path.

`git log -1` shows this commit on `app/office-weekly-card`.

STATUS: COMPLETE
