# Team Builder v2 — Work Plan & Spec

**Product:** Geeked-Out Basketball (GOB)
**Supersedes:** nothing. `team-builder-v1-spec.md` (v1.3) remains the record of what shipped.
**Spec version:** 2.0 — draft for alignment
**Status:** Phase 0 **closed** — all six acceptance criteria pass. Phase 1 §4.3 measurement complete, rule confirmed. Phases 1–3 not started.
**Last updated:** 1 August 2026

---

## 0. How to use this document

Same rules as the v1 spec, which still apply to everything it covers:

- **Maintained independently of the implementation.** Not a record of what the code does — the statement of what the feature should do, against which code is checked. Do not update it from the codebase.
- **Authoritative on product behavior, UX flow, and user-facing copy.** Specified strings are the copy.
- **Silent on implementation.** No data models, no component structure.
- **Conflicts are findings, not obstacles.** Flag; do not reinterpret.

**v1.3 still governs** the slot-replacement model, the wizard skeleton, the copy deck, the import validation UX, the resolver architecture, and the scope cuts. This document changes §9 (attributes) outright, extends team-select and assets, and adds a repair phase.

**Phases run in order.** Phase 0 is a blocker; nothing else ships until it clears.

---

## 1. What changed since v1.3

| Area | v1.3 | v2 |
|---|---|---|
| **Attribute model** | Four computed conditions: team total 6,400 · top-5 cap 3,950 · ceiling 1,035 · floor 24 | Two user-chosen modes: **capped** and **uncapped**. Top-5 cap retired. |
| **Eligibility** | Computed from four conditions, frozen at Apply | **Determined by mode**, frozen at Apply |
| **Roster authoring** | CSV import only | **Inline editor** (required by capped mode) + CSV retained |
| **Team select** | Name, conference, region A–H | Adds prestige, total attributes, state-level geography, three stacking filters |
| **Geography** | Region A–H only | State-level geography **alongside** region A–H — region stays load-bearing |
| **Generated art** | Initials on a gradient | Redesigned banner; parametric court generator; user uploads |
| **Player portraits** | None | Headshot picker from `set_0001` with filters, plus fitted random assignment |

---

## 2. Established facts (v2 additions)

Verified in the repo, 1 August 2026. Treat as constraints.

| Fact | Detail |
|---|---|
| **Court dimensions** | **3,333 × 2,083**, identical across all 129 court images including `general`. `Team_Images_System.md`: *"Do not resize or re-encode — animation system depends on exact dimensions."* Any generator must hit this exactly. |
| **Banner dimensions** | 1,920 × 679 (2.83:1) for 127 teams. **`general_banner_primary.jpg` is 600 × 300 (2:1) — the wrong aspect ratio.** Card derivatives are 400 × 141. |
| **`prestige`** | Exists on team documents, integer, sampled range ~413–630. Read alongside `total_player_attrs` in `franchise_routes.py`. |
| **`total_player_attrs`** | Exists on team documents. This is the "total player attributes" for display and talent banding. |
| **`region` A–H** | Load-bearing for two systems: regional tournament phase (`franchise_tournament.py` — `region_tournaments`, `phase: "region"`) and recruiting lean via each recruit's baked `Home Region`. **Must not be repurposed.** |
| **Uniform system** | `teams/teams_uniforms.json` — per team: `base`, `zones`, `variants[]` with `body`, `trim`, `wordmark`. `Recruit_Image_System.md` locks the decision that *"a uniform is a recipe, not an image"* with templated recolor across all 128. **A custom program needs only a manifest entry.** |
| **Portrait metadata** | Exists in the recruit **baking manifest** (Artifact B): `build.frame` ∈ {Slight, Lean, Normal, Broad, Doughy}, `build.definition`, `portrait.race`, `portrait.skin`, `portrait.hair`. `SCHEMA.md` states the manifest is *"Never loaded into the game."* Phase 3 changes that for a filtered subset. |
| **Generated banner today** | `FrontEnd/static/js/shared/teamGeneratedArt.js` — 400 × 141 SVG, horizontal gradient primary→secondary, 8px accent bar, initials at 48px pinned to `x=24`, school name at 14px below. |
| **No court generator exists** | Courts are hand-authored JPEGs. `apply_team_uniforms.py` and `build_teams_uniforms.py` exist for uniforms; there is no court equivalent in the repo. |

---

## 3. Phase 0 — Repair (blocker)

**Nothing else in this plan ships until Phase 0 clears.** The v1 feature could not complete a game for a custom program. Diagnosed and fixed; acceptance still pending a live play-through.

### 3.1 Sim failure — diagnosed and fixed

`POST /api/simulate-quarter` returned 400 `game_id belongs to a different matchup` at Q1 in a Team Builder franchise. A non-overlay franchise simmed cleanly on the same build, confirming the defect was Team-Builder-specific.

**Root cause: the display resolver was being applied on the way *in* — to constructors and persistence — rather than on the way *out*.** Specifically:

| Stage | What happened |
|---|---|
| `init-game` | Rewrote `home_team`/`away_team` through the resolver before constructing `GameManager` |
| `TeamManager` | Assigned the overlay name onto `.name` when the program was custom |
| Game-doc write | Persisted `.name` and `score{}` keys as display names |
| Matchup gate | Compared the request against a cached `GameManager` whose `.name` was already display |

Both sides of the comparison could carry a resolved name, and the 400 fired whenever the two identity layers diverged for a single request.

**An earlier plumbing change had made the comparator tolerant of the mismatch.** That was the wrong repair — a tolerant gate would have let divergent names flow into game documents and score keys silently, surfacing weeks later as incorrect statistics rather than immediately as an error. The strict gate is what found this.

**Fix applied:**

- Strict gate restored; tolerant helpers removed
- `.name` stays core; `.display_name` added for the overlay; only serializers read it
- `summarize_game_state` persists core names; `score{}` keys stay core
- `init-game` no longer rewrites names before `GameManager`
- play-next emits core `home`/`away`, chrome `home_display`/`away_display`, **and** `home_id`/`away_id`; the sim payload sends identity, not chrome
- Client joins by ObjectId; ranking labels resolve at the FCC edge

Staging audit found no Team Builder franchise with display-keyed game docs, so no migration was needed.

### 3.1a The architectural rule

> **Resolve at the edge, on the way out.**
>
> The display resolver belongs in response serialization — the last step before data leaves the server. It must never touch object construction, persistence, or anything used as a key, a hash, or a comparison.

v1.3 §3.2 said *"route every display path through the resolver."* It never said *"and no identity path may touch it."* That omission is what let this through, and it is why the rule is stated here rather than left implicit.

**Corollary: keep identity comparisons strict.** A tolerant comparator hides exactly this class of defect. Strictness is the detector, not an inconvenience.

### 3.2 Resolver sweep

Confirmed miss: **mode-select, "return to franchise" container, shows the replaced CPU team's name.**

The v1 §3.2 enumeration covered 58 surfaces and all were verified — but every verification franchise was **created, inspected and deleted without a game ever being played**. Live-play surfaces were never exercised. This phase covers ground the v1 verification never reached, not work that failed.

**Scope:** re-walk the enumeration in a live franchise that plays through at least one full week, including a completed game and box score.

### 3.3 Phase 0 acceptance

1. A Team Builder franchise can sim a full game and a full week without error.
2. A franchise with no overlay is unaffected — verified, not assumed.
3. Across an entire played week — mode-select, FCC, schedule, standings, live game, box score, news — **the replaced program's name and logo appear nowhere.**
4. The §3.2 enumeration is re-verified in live play and the checklist updated with any surface it missed.
5. A written game doc shows core names in `teams[*].name` and `score{}` keys, with the overlay in `teams[*].display_name`.
6. Sending a display name as `home_team` to `simulate-quarter` is rejected with a 400.

> **Criterion 2 carries extra weight for this phase.** The fix reached into `TeamManager`, `GameManager` init, `summarize_game_state`, play-next and the client payload — all shared with non-custom play. The identity unit tests cover identity only, and the full suite was blocked by the staging DB guard. The non-mod control must be re-run **against the fixed build**, not relied on from before it.

---

## 4. Phase 1 — Attribute model and the roster editor

Replaces v1.3 §9 entirely.

### 4.1 Two modes, chosen by the user

| Mode | Budget | Reallocation | Online eligibility |
|---|---|---|---|
| **Capped** | Each player keeps **the inherited total of the player he replaces** | **Within that player only.** Points never move between players. | **Eligible** |
| **Uncapped** | One team-wide pool equal to **the largest team total in the league (7,027)** | **Freely across the whole roster** | **Not eligible** |

Both modes: every attribute is bounded **5 minimum, 99 maximum**.

**The mode determines eligibility. Eligibility is no longer computed from conditions.** This is a substantial simplification over v1.3 — the meter becomes an allocation aid rather than a compliance check.

### 4.2 Why the top-5 cap is retired

v1.3 needed a top-5 cap because a total-points budget cannot control concentration: CPU teams hold ~57% of their talent in the top five, a min-maxer reaches ~75%, and the stacked build hit 4,788 against a league max of 3,954.

**Capped mode makes stacking structurally impossible.** Points cannot move between players, so team total, top-5 sum and every per-player total are inherited from the replaced program exactly. There is nothing to cap.

**Uncapped mode is ineligible for online play by definition**, so it needs no competitive guardrail.

The cap is removed, not relaxed. Do not reintroduce it.

### 4.3 The top-up rule

The 5-per-attribute minimum implies a per-player floor of **60** (5 × 12). But inherited totals go as low as **24**, and a player holding 24 points cannot put 5 in every attribute.

**Rule: in capped mode, any inherited player below 60 is topped up to exactly 60 at Apply.**

Consequence, stated plainly: a capped roster's total will exceed the replaced program's by the sum of those shortfalls. Capped is therefore *near*-inherited, not literally inherited.

**Measured, 1 August 2026 — rule confirmed, ship as written.**

Source: `teams/all_players_with_team_names.txt`, core-12 across all 1,536 players.

| Metric | Value |
|---|---|
| Players below 60 | **13** (0.85%) |
| Teams with ≥1 below-60 player | **12 / 128** — 116 programs untouched |
| Median team top-up | **0** |
| Max single-team top-up | **36** (Concord) — ~0.6% of a median team total |
| League-wide top-up | 136 points |
| Position on roster | All 13 in the bottom 3 of a 12-man roster; 12 are last |

**The league-wide figure is not the decision metric and should not be cited as one.** A user replaces one program, so the number that governs is the worst single-team top-up: 36 points, roughly 0.6% of team total, concentrated in the 12th man. Capped remains *near*-inherited with a deviation too small to carry competitive meaning.

**Two consequences, both binding:**

1. **The top-up is surfaced, never silent.** Where an inherited total is raised, the editor states it: *"Topped up from 24 — every player needs at least 5 in each attribute."* A budget that reads 60 against an inherited 24 with no explanation is indistinguishable from a bug, and silent adjustment is the pattern v1.3 §8.6 forbids.
2. **`roster_shape_at_creation` (§4.7) records post-top-up values.** It exists so a future eligibility rule can be applied retroactively; storing the pre-top-up shape would have that rule evaluate a roster that never shipped.

### 4.4 Per-player ceilings

- **Capped: 1,035.** Retained as a belt-and-braces bound. It can never bind, since the highest inherited total is 1,034 and reallocation cannot create points.
- **Uncapped: 1,188 implicit** (99 × 12). No separate explicit ceiling.

### 4.5 The roster editor

**Capped mode requires an inline editor.** "Redistribute this player's points as you see fit" is not expressible through a CSV round-trip in any usable way. This is no longer an optional convenience — the attribute model depends on it.

Step 3 of the wizard gains a fourth path and the existing three are re-framed:

1. **Keep [replaced]'s roster** — unchanged, default, zero risk
2. **Edit this roster** — *new.* The inherited 15 in a table, editable
3. **Generate a new roster** — unchanged
4. **Import my roster (CSV)** — unchanged; retained for users who genuinely have data

**Editor requirements:**

- Opens **pre-populated with the inherited 15**. Never a blank canvas.
- Editable per player: name, height, weight, jersey number, and the twelve core attributes.
- **`CH`, `EM` and `MO` are not editable and are not shown as inputs.** They are set by the game at init (v1.3 §8.8, §2.1). Do not offer fields the game ignores.
- **A live per-player budget** in capped mode: points spent / inherited total, with over/under state.
- **A live team pool** in uncapped mode, against 7,027, with league context markers (*median program 5,567 · best program 7,027*).
- Every attribute input clamps to 5–99.
- **Reset per player** and **reset all**, returning to inherited values.

**Mode is chosen once, at Step 3 before the four roster paths, and is visible throughout.** Switching modes after editing must warn that allocations will be re-based.

### 4.6 CSV changes

- **Remove `CH`, `EM` and `MO` from the template and the optional-field list.** They are currently offered and then silently discarded — the exact silent-failure pattern v1.3 §8.6 forbids everywhere else.
- Add one line to the import screen: *"Chemistry, emotion and morale are set by the game."*
- CSV import respects the chosen mode: an imported roster is validated against capped or uncapped rules, not against the retired four conditions.

### 4.7 Persistence

Unchanged from v1.3 §9.4 in principle, updated in content. Written once at Apply, never cleared:

- `attribute_mode` — `capped` | `uncapped`
- `online_eligible` — derived from mode, frozen
- `roster_shape_at_creation` — team total, top-5 total, max single player
- `hasEverExceededBudget` — retained

Still **unread in v1 and v2**. It exists so a future eligibility rule can be applied retroactively. It will look like dead code. Do not remove it.

### 4.8 Phase 1 acceptance

1. Capped and uncapped are selectable, and the choice is visible throughout the editor.
2. In capped mode, no point can move between players — verified by attempting it.
3. In capped mode, a player's total after editing equals his inherited total, except where the §4.3 top-up applies.
4. In uncapped mode, the team pool caps at 7,027 and allocation is free across the roster.
5. Every attribute clamps to 5–99 in both modes.
6. Capped franchises persist `online_eligible: true`; uncapped persist `false`.
7. The editor opens pre-populated with the inherited 15 and never presents a blank roster.
8. `CH`, `EM`, `MO` appear nowhere in the editor or the CSV template.
9. Reset-per-player and reset-all return inherited values exactly.
10. No top-5 cap logic remains anywhere in the codebase.
11. A capped franchise on a team with a below-60 player shows the top-up notice, and `roster_shape_at_creation` reflects the topped-up totals. Test with Concord — it carries the largest top-up in the league at 36 points.

---

## 5. Phase 2 — Team select

### 5.1 Geography

**State-level geography is a new taxonomy that sits alongside `region` A–H. It does not replace it.** `region` remains load-bearing for regional tournaments and recruiting lean, and must not be repurposed or renamed.

**Geography lives at the conference level, not the team level.** All 8 teams in a conference share their conference's geography. This is a static 16-entry map, not new per-team data.

| Conference | Geography |
|---|---|
| 1 | Pennsylvania, New Jersey, Delaware |
| 2 | West Virginia, North Carolina, Virginia, Maryland |
| 3 | Massachusetts, Rhode Island, Vermont, Maine, New Hampshire, Connecticut |
| 4 | New York, East Canada, Europe |
| 5 | Michigan, Ohio, Indiana |
| 6 | Illinois, Minnesota, Wisconsin |
| 7 | Mississippi, Tennessee, Kentucky, South Carolina, Alabama |
| 8 | Florida, Georgia |
| 9 | Iowa, Kansas, Missouri |
| 10 | Nebraska, South Dakota, North Dakota, Wyoming, Montana, Central Canada |
| 11 | Oklahoma, Texas, Arkansas |
| 12 | Texas, Louisiana |
| 13 | Arizona, New Mexico, Nevada, Colorado, Utah |
| 14 | Idaho, Washington, Oregon, West Canada |
| 15 | California |
| 16 | California, Hawaii, Alaska, Asia, Australia |

**Texas appears in 11 and 12; California in 15 and 16. Both are intentional.** A geography filter on Texas returns both conferences.

**Non-US geographies in use:** East Canada, Central Canada, West Canada, Europe, Asia, Australia. This list is authoritative — it is the set that appears above. Central America is not used.

### 5.2 Card display

Each team card shows, in addition to what it shows today:

- **Conference geography** — the state list for that team's conference
- **Total player attributes**
- **Prestige**

### 5.3 Filters

Three filters: **talent**, **prestige**, **geography**. All three **stack**.

**Filter behavior — this is the specified interaction, not a suggestion:** filtered-in teams stay **active and full colour**. Filtered-out teams become **dead buttons at reduced opacity** — visible, present, not selectable. The grid never reflows and never empties.

**Talent and prestige bands.** Five percentile bands each, computed across the 128:

| Tier | Percentile |
|---|---|
| Tier 1 | 81–100 |
| Tier 2 | 61–80 |
| Tier 3 | 41–60 |
| Tier 4 | 21–40 |
| Tier 5 | 1–20 |

Talent bands rank on `total_player_attrs`; prestige bands rank on `prestige`.

Bands are contiguous and cover 1–100 with no gaps and no overlap. Percentile is a **rank across the 128 teams**, so each band holds roughly 25–26 teams.

**Geography filter** offers each geography that appears in the §5.1 map — the 50 states plus the six non-US entries — and selects every conference containing it.

### 5.4 Phase 2 acceptance

1. All 128 cards show geography, total attributes and prestige.
2. Three filters work independently and in any combination.
3. Filtered-out teams render as reduced-opacity dead buttons; the grid does not reflow or empty.
4. Selecting Texas or California returns both of their conferences.
5. `region` A–H is untouched; regional tournaments and recruiting behave identically.
6. Talent and prestige bands are contiguous (81–100 / 61–80 / 41–60 / 21–40 / 1–20) and every one of the 128 teams falls in exactly one band.

---

## 6. Phase 3 — Images

Largest phase, most design-dependent. Four independent workstreams; **3a and 3b need design sign-off before build.**

### 6.1 Architectural decision: generation and normalization happen client-side

All image generation and all upload normalization run **in the browser, on a canvas** — not on the server.

**Why:** a downloadable build has no server but still has a browser engine. Client-side canvas means one code path for web and download, works offline, and avoids a second implementation. Server-side validation may exist as a backstop but must not be load-bearing.

This applies to the banner generator, the court generator, and upload re-encoding alike.

### 6.2 — 3a. Generated banner redesign

**What's wrong today:** the generated banner is a left-to-right gradient with an 8px accent bar, initials at 48px pinned to `x=24`, and the school name at 14px underneath. Everything is small, left-aligned and floating in space.

**The reference is the `general` fallback**, which is a cropped mascot illustration zoomed so the subject bleeds off both edges. It reads as designed because **scale and crop create interest without detail** — a lesson a generated banner can borrow without any illustration.

**Direction:**

- **Oversized ghost initials.** 3–4× current size, bleeding off the left and bottom edges, ~12% opacity in the secondary colour. Depth from typography alone.
- **The full school name, centred, as the subject.** Bebas at real size. Initials read as placeholder; a wordmark reads as design.
- **Mascot name beneath**, small caps, wide letter-spacing, ~60% opacity.
- **An angled colour split** replacing the linear gradient — diagonal from primary to a darkened primary, with the secondary as a chevron edge.
- **Accent bar tied to the diagonal**, not sitting flat.

Output must match the §2 card convention (400 × 141) and the primary aspect ratio (2.83:1).

**Also fix:** `general_banner_primary.jpg` is 600 × 300 while every team banner is 1,920 × 679. The fallback is the wrong shape and will letterbox or crop wherever it appears.

> This section is direction, not a final design. Expect one or two rounds before build.

### 6.3 — 3b. Court generator

Parametric renderer, canvas, output exactly **3,333 × 2,083**.

**User-exposed parameters:**

- Hardwood style
- Out-of-bounds colour
- Free-throw lane colour
- Centre-court colour
- Free-throw half-arc fill colour

**Constraints:**

- Court markings — rim positions, lane geometry, OOB lines, centre line, arcs — are **fixed geometry**. The user colours them; the user never moves them. The animation system depends on exact placement.
- Output dimensions are non-negotiable.
- Defaults derive from the program's primary and secondary colours, so a user who changes nothing still gets a coherent court.

**Open:** the original court source (PSD/SVG/layer file) is not in the repo. If it can be found, the generator should reproduce that geometry exactly. If not, geometry must be derived by measuring an existing court — Morristown is the agreed proxy.

### 6.4 — 3c. User uploads

**Assets a user may upload:** horizontal logo, player images.

**Normalization:** read file → draw to canvas at target dimensions → re-encode → store the normalized result. The user is told approximate requirements; the app makes them exact.

**Surface constraints in the UI, above the file picker** — never only in a help doc. State the shape and rough size; do not demand exact pixel dimensions.

> Rationale: EA's TeamBuilder publishes no format spec and normalizes nothing, and it produced their worst bug class — identical PNGs failing from one editor and working from another, with users told to switch tools. Accepting generously and normalizing is the opposite posture.

**Uniforms are not uploaded.** A custom program gets an entry in `teams_uniforms.json` — `body`, `trim`, `wordmark` — and inherits the existing templated recolor. Per the locked decision, *a uniform is a recipe, not an image*. Keep the default deliberately simple: **core colour plus trim only, no other options.**

**Player images:**

- If the user uploads bespoke images for the original 12, use them.
- Every player added afterwards — recruits, walk-ons — uses the standard templated uniform painting, exactly like all 128 CPU teams.

### 6.5 — 3d. Headshot selection

For users who do **not** upload player images, two paths:

**Pick from `set_0001`**, with filters on skin tone and build.

This requires publishing a **filtered subset** of the baking manifest into the game-facing artifact: `build.frame`, `build.definition`, `portrait.skin`. `SCHEMA.md` currently states the manifest is never loaded into the game — that line needs updating to reflect the deliberate exception, not quietly contradicting.

**Or: fitted random assignment**, with re-roll.

**The random assignment must fit the player's typed height, weight and build** — matching against the **as-generated** values the user entered, not the manifest's projected mature values.

### 6.6 Phase 3 acceptance

1. The generated banner matches the approved design at both 400 × 141 and 2.83:1.
2. `general_banner_primary.jpg` is corrected to 1,920 × 679.
3. The court generator outputs exactly 3,333 × 2,083 with fixed geometry and user-set colours.
4. Court and banner generation run client-side and work with no network.
5. Uploads are normalized client-side; a user-supplied image of any reasonable size and format lands correctly.
6. Constraints appear in the UI above the file picker.
7. A custom program has a `teams_uniforms.json` entry and its recruits receive templated uniforms identical in treatment to CPU teams.
8. The headshot picker filters on skin tone and build.
9. Random assignment fits the user's typed height, weight and build, and can be re-rolled.
10. `SCHEMA.md` is updated to document the published subset.

---

## 7. Sequencing and dependencies

| Phase | Depends on | Can start |
|---|---|---|
| **0 — Repair** | — | Immediately. Blocks everything. |
| **1 — Attributes + editor** | Phase 0 | After Phase 0 |
| **2 — Team select** | Phase 0 | Parallel with Phase 1 — independent surfaces |
| **3a — Banner** | Design sign-off | Design can begin now |
| **3b — Court** | Design sign-off; court source located or geometry measured | After 3a decision on client-side rendering |
| **3c — Uploads** | 3a, 3b | After both |
| **3d — Headshots** | Manifest subset published | Parallel with 3c |

**Phases 1 and 2 are genuinely independent** and can run concurrently if you want two threads. Phase 3 is one thread with internal ordering.

---

## 8. Open items

| # | Item | Owner |
|---|---|---|
| 1 | ~~Count of players below 60 and total league-wide top-up (§4.3)~~ — **closed 1 Aug 2026, rule ships as written** | Grok, before Phase 1 |
| 2 | Original court source file — findable outside the repo? (§6.3) | Jamie |
| 3 | Banner design direction — one or two review rounds (§6.2) | Jamie + Claude |
| 4 | Trademark clearance on "Team Builder" before any marketing surface | Jamie — carried from v1.3 |
| 5 | Whether Phases 1 and 2 run concurrently or in sequence | Jamie |

---

## 9. Decision log (v2)

| # | Decision | Rationale |
|---|---|---|
| 1 | Capped/uncapped modes replace the four-condition budget | User-chosen mode is simpler than computed compliance, and capped makes stacking structurally impossible |
| 2 | Top-5 cap retired entirely | Redundant under capped (points can't move between players); unnecessary under uncapped (ineligible by definition) |
| 3 | Capped reallocation is **within a player**, uncapped is **across the roster** | The distinction is what makes capped safe for competitive play |
| 4 | Players below 60 are topped up to 60 in capped mode | Clean rule; the alternative is an unsatisfiable minimum. Accepts that capped is near-inherited, not literally inherited. **Confirmed by measurement (§4.3): 13 players, 12 teams affected, worst case 36 points (~0.6% of team total), median team unaffected.** |
| 19 | The top-up is surfaced in the editor, not applied silently | A budget reading 60 against an inherited 24 with no explanation is indistinguishable from a bug — and silent adjustment is the pattern v1.3 §8.6 forbids everywhere else |
| 20 | The §4.3 gate metric is **worst single-team top-up**, not the league-wide sum | A user replaces one program; no franchise ever experiences the league total. The original gate wording asked for the wrong number. |
| 5 | Uncapped budget = largest team total in the league (7,027) | Reads as "the best program's worth of talent" |
| 6 | Eligibility is determined by mode, not computed | Substantial simplification; the meter becomes an allocation aid |
| 7 | Inline roster editor is required, not optional | Capped mode is not expressible through CSV |
| 8 | State geography sits **alongside** region A–H | Region is load-bearing for tournaments and recruiting and must not be repurposed |
| 9 | Geography is conference-level | A static 16-entry map, not new per-team data |
| 10 | Filtered-out teams are dead buttons at reduced opacity | Grid never reflows or empties; spatial memory preserved |
| 11 | All image generation and normalization is client-side | One code path for web and downloadable; works offline |
| 12 | Court geometry is fixed; only colours are user-set | The animation system depends on exact marking placement |
| 13 | Uploads are accepted generously and normalized, not spec-enforced | EA's opposite posture produced their worst documented bug class |
| 14 | A filtered portrait-metadata subset is published game-facing | Required for headshot filtering; documented rather than done quietly |
| 15 | `CH`/`EM`/`MO` removed from the CSV template | Currently offered then silently discarded — the exact pattern v1.3 forbids |
| 16 | **Resolve at the edge, on the way out** | The resolver belongs in response serialization only. Applying it to constructors and persistence put display names on the identity path and broke the sim. |
| 17 | **Identity comparisons stay strict** | The strict matchup gate is what surfaced the leak. A tolerant comparator would have hidden it until statistics were wrong. |
| 18 | **`.name` is core, `.display_name` is the overlay** | Removing the overlay from `.name` without giving display a home just moves the leak somewhere worse. |
