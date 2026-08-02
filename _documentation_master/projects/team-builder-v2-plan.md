# Team Builder v2 — Work Plan & Spec

**Product:** Geeked-Out Basketball (GOB)
**Supersedes:** nothing. `team-builder-v1-spec.md` (v1.3) remains the record of what shipped.
**Spec version:** 2.0 — draft for alignment
**Status:** Phases 0, 1 and 2 **closed**. Phase 3a (banner) **closed** — "Chevron" approved and shipped. 3b (court) unblocked: no source file exists, geometry is measured from Morristown. 3c and 3d not started.
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
| **Uncapped** | One team-wide pool equal to **the largest team total in the league**, computed at runtime | **Freely across the whole roster** | **Not eligible** |

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

- **Capped: no explicit ceiling.** Dropped 1 August 2026 — reallocation cannot create points, so a ceiling can never bind. The former literal 1,035 was derived from a pre-recalibration snapshot and is exactly the class of hardcoded constant §4.4a forbids.
- **Uncapped: 1,188 implicit** (99 × 12). No separate explicit ceiling.

### 4.4a No hardcoded league constants

> **Any number derived from roster data is computed at runtime, never stored as a literal.**

The uncapped pool, the median and best league markers, and any per-player ceiling are all functions of live roster data. Attribute recalibration is an ongoing parallel workstream; a literal is a snapshot that goes silently wrong the moment that data moves — no error, just a budget that no longer means what this document says it means.

Served by `GET /franchise/team-builder/league-context` → `compute_league_attr_context(db)`, supplying `team_pool` (max), `team_median`, `team_best`.

**Decision #5 defines the pool as "the largest team total in the league." That is the definition. It is not a number.**

#### The basis is pinned to week-1 as-initialized

**Computed as:** universal-pool scholarship 12 (core-12) **+** 3 × `generate_walk_on_profile()` under `seed(team_id)`. No franchise FPD is read.

This is `max(scholarship_12 + walk_on_pad_3)` across the 128 — the maximum of the sum, not the sum of the maxima.

**Why pinned.** The first implementation read "the newest franchise with ≥64 teams at `players` ≥ 15," which made the pool depend on which save happened to be newest and how far it had progressed:

| Basis | Pool | Median |
|---|---|---|
| Newest-save pick (corrupt franchise) | 9,078 | 6,027 |
| Healthy week-1 live | 7,262 | 6,033 |
| Mid-season live (wk 19) | 6,894 | 5,753 |
| **Pinned week-1 as-initialized** | **7,485** | **6,193** |

A budget that moves with somebody else's save state is not a league constant. Seeding per `team_id` makes the walk-on component deterministic, so every user computing the pool gets the same number.

> **Separate finding, not a Team Builder defect.** The 9,078 came from franchise `6a6de652…` (South Lancaster) carrying roughly **+1,600** over a clean initialization — not walk-ons, not recalibration. Other week-1 saves scanned 7,054–7,645. Whatever produced it affects franchise creation generally and warrants its own investigation.

### 4.5 The roster editor

**Capped mode requires an inline editor.** "Redistribute this player's points as you see fit" is not expressible through a CSV round-trip in any usable way. This is no longer an optional convenience — the attribute model depends on it.

Step 3 of the wizard gains a fourth path and the existing three are re-framed:

1. **Keep [replaced]'s roster** — unchanged, default, zero risk
2. **Edit this roster** — *new.* The inherited roster in a table, editable
3. **Generate a new roster** — unchanged
4. **Import my roster (CSV)** — unchanged; retained for users who genuinely have data

**Editor requirements:**

- Opens **pre-populated with all 15** — the inherited 12 plus 3 wizard-generated walk-ons (§4.5a). Never a blank canvas.
- Editable per player: name, height, weight, jersey number, and the twelve core attributes.
- **`CH`, `EM` and `MO` are not editable and are not shown as inputs.** They are set by the game at init (v1.3 §8.8, §2.1). Do not offer fields the game ignores.
- **A live per-player budget** in capped mode: points spent / inherited total, with over/under state.
- **A live team pool** in uncapped mode, against the runtime-computed pool, with league context markers (median and best program, both computed — see §4.4a).
- **The pool meter and its markers are hidden in capped mode.** Capped has no team budget; a partially-filled bar reads as unspent headroom the user cannot actually spend.
- **An over-budget state must be visible where the user is editing**, not only on Apply. A roster editor is a dozen player cards tall; an error surfaced at the top while the user is at the bottom is the failure mode that made the franchise cap look like an infinite loop. Anchor it to the control that refuses.
- Every attribute input clamps to 5–99.
- **Reset per player** and **reset all**, returning to inherited values.

**Mode is chosen once, at the top of the editor, and is visible throughout.** Switching modes after editing must warn that allocations will be re-based.

### 4.5a Roster size and walk-ons

> **The user authors all 15 — the inherited 12 plus 3 walk-ons generated when the editor opens.**

**Established, 1 August 2026:**

| Fact | Detail |
|---|---|
| Core team document | **12 players.** All 128 verified; the universal pool contains zero `Walk On` archetypes. |
| Walk-ons | **Generated at franchise init**, not stored in core. `FranchiseManager.initialize_season` calls `generate_walk_on_profile()` three times per team after cloning core FPDs. |
| Generation | `draw_position_intent` + `generate_player(tier="Poor")`; year weights JH 60 / FR 20 / SO 10 / JR 10, advanced one year; `archetype: "Walk On"`, `entry_tier: "Poor"` |
| Season-1 shape | `players` = 15, `scholarship_players` = `players[:12]`, `training_squad_players` = `[]` |
| After Training Camp | 3 move to `training_squad_players`, leaving `players` = 12. **The user chooses which three**; it is not positional. |

**The defect this exposed.** `team_builder_apply` runs `initialize_season` first — every team reaches 15 — then `replace_slot_roster` issues `$set players: new_ids` for the edit, import and generate paths. That **deletes the init walk-ons and never regenerates them.** Only *keep* retains all 15. A user who edits a single attribute plays the season 12-deep while all 127 CPU programs carry 15. Observed live in a week-9 franchise: 127 teams at `players=12 + training_squad=3`, the custom team at `players=15` with no walk-ons ever to move.

#### The rule

- **The authored roster is 15 in both modes.** The editor opens with the inherited 12 plus 3 walk-ons and every one of the 15 is editable on the same terms.
- **The three walk-ons are generated when the editor opens**, by calling the existing `generate_walk_on_profile()` — not a parallel generator. They live in wizard state and are persisted only at Apply.
- **They are generated once and are not re-rollable.** In capped mode a walk-on's as-generated total becomes his budget; re-rolling would let a user shop for a larger one.
- **Idempotency is enforced server-side, not by frontend convention.** `POST /franchise/team-builder/wizard-walk-ons` takes `{ replaced_object_id, draft_id }`, persists to `team_builder_wizard_drafts`, and returns the same three on every call. A page refresh, a network retry or a component remount is therefore harmless.

> An earlier build satisfied this only because the client didn't re-call the endpoint. That is a convention, not a guarantee — a reload was enough to re-roll three budgets. The rule belongs where it cannot be bypassed, exactly as with the strict matchup gate in §3.1a.
- **`initialize_season` is unchanged.** It runs as it does today and gives all 128 teams their walk-ons. Apply then writes the authored 15 over that slot, replacing init's three along with the rest, and **deletes the three superseded FPD documents** so no orphans accumulate.
- **Import must supply exactly 15 rows**; anything else is rejected with a stated reason, never truncated or padded.
- **Both sides of every budget comparison are 15-player totals.** The uncapped pool, the league markers and any league context are computed on full franchise rosters, so a custom program is measured against CPU programs on the same basis.

#### Why this timing, and not the alternatives

**Not reordering `initialize_season`.** It sits on the shared path for every franchise, custom or not. Phase 0's sim failure came from altering a shared producer to serve the custom case and breaking the common one. Moving the franchise lifecycle to suit the wizard puts all franchise creation at risk to serve a minority path.

**Not excluding the slot from init generation.** A conditional inside a shared loop, with a bad failure mode: if Apply doesn't complete, that team has zero walk-ons and nothing says so — the same silent-depth class this section exists to fix.

**Generating in the wizard and overwriting at Apply** needs no lifecycle change, no exclusion flag, and no conditional in shared code. Abandoning the wizard leaves nothing behind and no team short. The cost is three throwaway player documents per custom franchise, cleaned up at Apply.

#### Consequences

- **Capped mode gains nothing exploitable.** Walk-ons are Poor-tier with low totals, points still cannot cross a player boundary, and their budgets are fixed at generation.
- **Every slot now has a real inherited total**, including 13–15. The undefined-budget problem is closed by giving those slots a budget, not by removing them from user input.
- **v1.3's floor carve-out is retired** — the rule that applied the attribute floor to the top 12 but not the bottom 3. All 15 are authored on the same terms.

### 4.5b The editor is a diff, not a form

> **Any field the user does not edit keeps its inherited value. Without exception.**

**Observed 2 August 2026:** a custom program created with no year changes came back with all 15 players as `FR`. The inherited years were discarded.

**This is not a year bug.** Year is simply the field visible enough to catch. The apply path constructs new player documents from the wizard payload instead of cloning the inherited player and overwriting only what changed — so **every field the editor does not send is reset to a default**.

The editor exposes name, height, weight, jersey number and the twelve core attributes. Everything else on a player document is therefore at risk: year, archetype, portrait and appearance data, `Home Region`, development curve, recruiting metadata, `CH` / `EM` / `MO`.

**`Home Region` is the dangerous one.** §2 records it as load-bearing for recruiting lean. Reset to a default, it would skew a custom program's recruiting for seasons before anyone connected the two.

**Rule:**

- **Apply clones the inherited player document and overwrites only the fields the editor sends.** It does not construct a player from the payload.
- **This applies to every path.** Generate and import author full players by definition; edit and keep must preserve.
- **For an imported CSV, a blank optional column means inherit** — not "use a default." v1.3 §8.6's no-silent-substitution rule already implies this; it is now stated.
- **Walk-ons are exempt only in that they have no inherited counterpart** — their wizard-generated values *are* their inherited values, and every field of them must survive Apply identically.

**Why this was missed:** every Phase 1 acceptance criterion tested a field the editor writes. None tested a field it doesn't. A form that silently defaults everything outside its own inputs looks correct from inside its own test suite.

#### The ordering defect found alongside it

The zero-edit diff surfaced **36 differing field paths**, and one was not a defaulting problem at all:

> **Capped budgets were aligned to players by position in a Mongo `find()` result rather than by identity.** `find()` order ≠ roster order, so budgets — and therefore the attributes written under them — could land on the wrong players.

**This silently violated §4.1's guarantee that points never move between players.** Not by user action, but by the system assigning a player's inherited budget to a different player. Criterion 2 passed because its tests and the live walkthrough both happened to hit aligned orderings; `find()` guarantees no such thing, and the order can change when documents are rewritten.

**Rule: budgets, edits and inherited values bind to players by identity, never by ordinal position in a query result.** This is §3.1a's lesson in another costume — an ordinal is a positional key, and positional keys are as fragile as display-name keys.

**Verification must use a deliberately shuffled order.** A test whose fixture happens to match roster order proves nothing about this class of defect.

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
11. The §4.3 top-up is proven by unit test (synthetic 24 → 60), not by a live walkthrough — recalibrated data may contain no player below 60.
12. **No league constant is a hardcoded literal** (§4.4a). The uncapped pool and league markers come from `league-context` at runtime.
13. **The editor opens with 15** — the inherited 12 plus 3 wizard-generated walk-ons — and all 15 are editable on the same terms in both modes.
15. **Every path ends at `players` = 15**, `scholarship_players` = 12, with 3 `archetype: "Walk On"` FPDs. Verified after keep, edit, import **and** generate — not only keep.
16. A custom program and a CPU program in the same franchise hold identical `players` / `scholarship_players` / `training_squad_players` counts at week 1 **and** after Training Camp.
17. **No orphaned FPD documents remain after Apply.** Init's three superseded walk-ons are deleted, and staging is checked for orphans left by the previous `$set` behaviour.
18. **Walk-ons are stable across wizard navigation and are not re-rollable** — leaving Roster and returning yields the same three players with the same attributes.
19. **Import of any row count other than 15 is rejected with a stated reason** — not truncated, not padded.
20. The uncapped pool and league markers are computed on **15-player franchise totals**, matching what a custom program is now authoring.
21. **A custom program created with no edits at all is field-for-field identical to the program it replaced**, except identity and colours — verified by diffing every field of all 12 inherited players, not by spot-checking.
22. **Editing one attribute on one player changes only that value.** Every other field on that player, and every field on the other 14, is unchanged.
23. **`Home Region`, archetype, year, portrait data and development metadata survive all four paths.**
24. A blank optional column in an imported CSV **inherits** rather than defaulting.
25. **Criterion 2 re-run against a deliberately shuffled query order.** Budgets and edits bind to the correct players when `find()` order does not match roster order.
14. The uncapped pool meter is hidden in capped mode, and an over-budget state is visible at the point of editing — not only on Apply.

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

**Approved 2 August 2026 — "Chevron."** Selected from three rendered directions (Chevron, Band, Blade), reviewed at 1× and 2× across `IDA`, `Hanson` and `South Lancaster`, and across four palettes including a deliberately unflattering one. **This is a locked design, not direction.**

#### Composition, back to front

1. **Background** — flat primary across the full card.
2. **Angled split** — a darkened primary (**primary at −16% lightness**) filling the region right of a diagonal running from roughly 38% width at the bottom edge to 75% width at the top edge. Replaces the v1 linear gradient entirely.
3. **Chevron edge** — two parallel strips in the secondary colour tracking that diagonal: a solid one at ~90% opacity, and a thinner outrider at ~35%. This is the accent, and **it follows the diagonal rather than sitting flat** — no horizontal accent bar survives from v1.
4. **Ghost initials** — the **three-letter abbreviation**, Bebas, at roughly 3.5× the v1 initials, anchored past the left edge and below the baseline so it bleeds off both. Secondary colour at **12% opacity**. Depth from typography alone; no illustration required.
5. **Wordmark** — the **full school name**, uppercase Bebas, horizontally centred, sitting above the vertical midline. The subject of the composition.
6. **Mascot name** — beneath the wordmark, Oswald light, uppercase, wide letter-spacing, ~60% opacity.

#### Rules the composition depends on

- **The wordmark shrinks to fit.** Starting size steps down until the name fits its box, floor around 40% of the starting size. This is what lets `IDA` and `South Lancaster` occupy the same frame. Long names render smaller — accepted.
- **Text colour is derived by contrast, not by a luminance threshold.** For each surface, compute the WCAG contrast ratio of **both** dark and light ink against that surface and **take the higher**. Never threshold on luminance.

> **Corrected 2 August 2026.** The first build thresholded at luminance 0.42 and put 27 of 129 programs under 4.5:1 — worst case 2.73:1 on `#ff6f61`, where black would have given 7.6:1. The threshold was selecting the *worse* ink for every mid-luminance colour. The true crossover is `(L + 0.05)² = 0.0525`, i.e. L ≈ 0.179.
>
> **Best-of-two is provably safe.** The worst possible background is one where both inks tie, and that tie occurs at **4.58:1** — above the 4.5 floor. Choosing by contrast makes the requirement unfailable for any colour, rather than something to be tuned per palette.
>
> **The guarantee requires pure `#000` and `#fff`.** A near-black such as `#14181f` carries enough luminance to erode the floor below 4.58. The ink candidates are the true extremes, not brand-tinted approximations.

**Measured result, 2 August 2026, across 128 palettes plus a pale custom program:** minimum wordmark contrast **4.736:1** (Lancaster `#d24a1b`), minimum composited mascot contrast **4.504:1** (Ocean City), zero programs under 4.5:1. Coral `#ff6f61` moved from 2.73:1 to **7.70:1** on dark ink.

> The 128 existing programs are a **test corpus, not a shipping target** — they keep their hand-authored banners. Their palettes are swept because they represent the range of colours a user can choose in the Colors step, and 27 of them would previously have produced an unreadable custom banner.

- **Contrast is measured on composited pixels, not on ink values.** The mascot line targets ~60% opacity and **rises per program until its composited contrast clears 4.5:1** (0.92 observed as the maximum). The ghost initials at 12% are **decorative and exempt**; the mascot line is **not exempt**.

> **Open, minor:** on programs pushed toward 0.92 the mascot approaches the wordmark in strength, which may flatten the type hierarchy Chevron depends on. If it reads badly, hold opacity at 60% and buy legibility with size or weight instead.
- **The abbreviation is the ghost, and it is a reliable input** — Team Builder validates it for uniqueness and length, so it is always exactly three characters. The wordmark and the ghost are therefore always different strings.

#### Still to fix

`general_banner_primary.jpg` is 600 × 300 while every team banner is 1,920 × 679. The fallback is the wrong shape and will letterbox or crop wherever it appears.

Output must match the §2 card convention (400 × 141) and the primary aspect ratio (2.83:1 at 1,920 × 679) — the same composition scaled, not re-laid-out.

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

**Resolved 2 August 2026: the original court source does not exist.** No PSD, AI, SVG or FIG anywhere in-tree or under the home directory. **Geometry is derived by measuring an existing court, with Morristown as the agreed proxy.** `extract_court_template_masks.mjs` and `build_neutral_court_master.mjs` already do measurement work keyed off Bentley-Truman and Morristown — start from those rather than measuring afresh.

Because geometry is measured rather than authored, **the acceptance bar is pixel agreement with the source court**, not visual similarity. §2 records that the animation system depends on exact marking placement; a court that looks right and is two pixels off is a failure.

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
| 2 | ~~Original court source file (§6.3)~~ — **closed 2 Aug: does not exist.** No PSD / AI / SVG / FIG in-tree or under the home directory. 3b proceeds from measured Morristown geometry. | Jamie |
| 3 | ~~Banner design direction (§6.2)~~ — **closed 2 Aug: "Chevron" approved, single round** | Jamie + Claude |
| 4 | Trademark clearance on "Team Builder" before any marketing surface | Jamie — carried from v1.3 |
| 5 | ~~Whether Phases 1 and 2 run concurrently or in sequence~~ — **closed: sequential, same agent** | Jamie |
| 6 | **Franchise `6a6de652…` (South Lancaster) carries ~+1,600 over a clean week-1 init.** Not walk-ons, not recalibration. Affects franchise creation generally, not Team Builder. | Jamie — new, 1 Aug |
| 7 | Re-run the §4.3 top-up measurement once attribute recalibration settles — informational, not a gate | Grok, after recalibration |

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
| 21 | **No league constant is stored as a literal** (§4.4a) | Attribute recalibration runs as a parallel workstream. A snapshot literal goes wrong silently — no error, just a budget that stops meaning what the spec says. |
| 22 | The capped per-player ceiling is dropped, not recalculated | Reallocation cannot create points, so it can never bind. A bound that cannot fire is a literal waiting to go stale. |
| 23 | **The user authors all 15**, including the 3 walk-ons (§4.5a) | Restores parity with all 127 CPU programs and gives slots 13–15 a real inherited total, closing the undefined-budget problem by defining it rather than by excluding those slots |
| 24 | Walk-ons are generated **in the wizard**, not by reordering `initialize_season` or excluding the slot from it | No franchise-lifecycle change, no conditional in a shared loop, and abandoning the wizard leaves no team short. Phase 0's failure came from altering a shared producer for the custom case. |
| 25 | Walk-ons are not re-rollable, **enforced server-side** | In capped mode an as-generated total becomes a budget. Frontend convention is not enforcement — a reload was enough to re-roll. |
| 26 | Budget comparisons use 15-player totals on both sides | A custom program must be measured against CPU programs on the same basis as what it authors |
| 27 | The league-context basis is **pinned to week-1 as-initialized**, seeded per `team_id` | Reading live franchise data made the pool depend on which save was newest and how far it had progressed — 6,894 to 9,078 across the same staging DB |
| 28 | **The editor is a diff, not a form** (§4.5b) | Apply must clone the inherited player and overwrite only edited fields. Constructing from the payload silently defaults every field the editor doesn't expose — 36 field paths on a zero-edit Apply. |
| 29 | **Bind by identity, never by ordinal position in a query result** (§4.5b) | Capped budgets aligned to `find()` order landed on the wrong players, silently breaking §4.1's no-points-between-players guarantee. An ordinal is a positional key; §3.1a's lesson in another costume. |
| 5 | Uncapped budget = largest team total in the league, **computed at runtime** | Reads as "the best program's worth of talent." Stored as a definition, never a literal — see §4.4a |
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
