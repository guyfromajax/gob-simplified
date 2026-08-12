# Team Builder v2 — Work Plan & Spec

**Product:** Geeked-Out Basketball (GOB)
**Supersedes:** nothing. `team-builder-v1-spec.md` (v1.3) remains the record of what shipped.
**Spec version:** 2.0 — draft for alignment
**Status:** Phases 0, 1 and 2 **closed**. Phase 3a (banner), 3b (court) **closed**. Rescope (§4.5c) implemented. Phase 3d — `builder_set_0001` delivered, assignment and picker built at **99.2% exact match**; **pending the live uniform check** (§4.5c acceptance 28). 3c (uploads) is a post-launch fast follow.
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
| **A court generator already exists** | `scripts/generate_non_a1_courts.mjs` — **it produced 120 of the 129 courts.** Canvas 3,333 × 2,083; floor `(75,60)`→`(3258,2023)`; OOB bounds `(150,84)`→`(3183,1998)`; horizontal OOB at `y=158` / `y=1924`; centre `(1666,1042)`; lane, FT circle, three-point arc, hash, backboard, rim and overlay coordinates; JPEG quality 92. Flags: `--force`, `--team <slug>`. |
| **The 8 Conference 1 / A1 teams are excluded from it** | `bentley_truman`, `lancaster`, `four_corners`, `morristown`, `ocean_city`, `little_york`, `xavien`, `south_lancaster`. Their courts are **hand-authored reference art**, not generated. The remaining 120 were rendered from the constants above. |
| **The 120 generated courts are bit-identical to a fresh render** | Verified 2 August 2026 against `ada`: MAE 0, all 12 features Δ0. The shipped JPEGs have not drifted from the script that produced them. |
| **The constants are authoritative, not the art** | `_documentation_master/11_Design_Systems/Court_Template_Implementation_Spec.md` documents **gameplay-to-pixel anchors** — the mapping between the sim's coordinate system and the image — plus fixed court geometry, hardwood and colour distributions, logo and wordmark placement boxes, and export requirements. `docs/To Do/courts_brief.md` holds the batch design and distribution rules. |

> **Correction, 2 August 2026.** This table previously asserted *"No court generator exists — courts are hand-authored JPEGs."* That was wrong, and it was labelled verified. It sent §6.3 down a measure-and-reproduce path and cost a full Step 0 cycle aimed at the wrong artefact. `Team_Images_System.md` carries the same staleness, stating dimensions are undefined; both should be corrected.

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

#### 3.2a Mid-game resume is a separate entry point — leak found 3 August 2026

Observed in live play: a game entered normally rendered clean, then was closed mid-stream and reopened through the **mid-game resume** system. The detector then fired on two nodes:

- `<H3#home-players-header>` rendering `Concord` instead of `Alexandria`
- `<BUTTON.toggle-btn.active>` with `backgroundColor: #ec1d28` — the replaced program's core primary

**The overlay was present and unread.** The URL carried `home=Concord&home_display=Alexandria`. Identity and chrome were both on the wire exactly as §3.1a requires; the resume renderer simply built its header from `home` and never applied the overlay, and took colours from core rather than the custom palette.

**The lesson is about entry points, not surfaces.** The §3.2 sweep played a full week and passed. It never closed a game mid-stream and resumed, so an entire second entry path — one that constructs UI from persisted state rather than from a hydrated franchise payload — was never exercised. **Any path that reconstructs the game view from stored state is a distinct entry point and needs its own verification**, including resume, deep links, and a browser refresh mid-game.

**Detector note:** the DOM scanner re-fires on every mutation, so a single leak produced repeated banners in one session. It dedupes by stable node plus needle per session — a real leak is reported once, not made to feel like many.

**The leak set was never the real set.** Two nodes on a plain resume; five once an event card mounted. The extra three were player-card chrome that only exists in the DOM while a moment card is on screen. Because transient UI is only scanned while alive, **the true surface count is unknowable and node-by-node patching could never converge.**

#### 3.2b The hydration gate

Fixed by making hydration a **precondition of chrome resolution**, not a responsibility of callers:

- Resolvers own `ensureTeamBuilderVisualReady()`; first access lazily starts the payload fetch. **A warm `FranchiseLS` alone does not settle the gate** — the same localStorage-masking trap found in §6.3b, closed here before it could repeat.
- Labels and colours resolve through **one producer**. `resolveTeamBuilderDisplayName(core, urlFallback)` makes the hydrated `visual.name` authoritative and the URL a fallback only — a query parameter is user-editable and must never be an identity source.
- The sync painter has **no production call sites**. It is reachable only through async wrappers that await the gate, so a new entry point cannot render chrome without hydrating.
- The assertion is **environment-scoped**: throw in development and staging, `console.error` in production with paint proceeding. A gate that crashes a live game to prevent a cosmetic leak is the trade already rejected when the server-side detector was rescoped to observe-only.

> **The general rule: a guarantee that depends on every caller remembering is a convention, not a guarantee.** This is the third time in the project — the walk-on endpoint held only because the client didn't re-call it, and capped-mode budgets held only because tests happened to use aligned ordering. In each case the repair was to make the correct behaviour structural and the incorrect one unreachable or loud.

#### 3.2c Resume rebuilt the wrong roster — a league-wide defect Team Builder exposed

**Found 4 August 2026.** After a mid-game resume, a custom program's players rendered the *replaced* program's portraits. Two rounds of chrome and palette work changed nothing, because **chrome was never the problem** — the image key was wrong, not the colour around it.

**Root cause:** `resume_anchor.snapshot` is a deep copy of `summarize_game_state`, which carries no `franchise_id` or `mode`. The restore path replaced the root document with that snapshot wholesale, so:

```
franchise_id_for_roster = saved_franchise_id if saved_mode == "franchise" else None
```

resolved to `None`, and the GameManager rebuilt its roster from `players_collection.find({"team": team_name})` — **the core league roster**, not the franchise's.

**The portraits were the symptom. The roster was the defect.**

- A resumed quarter **simulated with core attributes**, ignoring every edit the user made. Custom players are seeded from the replaced program, so names matched and nothing looked wrong.
- `finalize_game` wrote stats against **core `player_id`s**, so a resumed game's stats missed the minted FPD documents entirely and could insert orphan rows under core ids.

**It was never Team Builder-specific.** The guard has no mod condition, so *every* franchise resuming from an anchor rebuilt from core rosters. Invisible for a normal franchise — core and franchise rosters look alike until development, injuries and roster changes diverge them. **Team Builder made it visible because a custom program's portraits differ immediately.**

**Fix, in three parts:**

1. **Merge, don't replace** — take game state from the anchor while preserving `franchise_id`, `mode`, `tournament_id` and `user_team_side` from the root document. This repairs historical saves, whose snapshots will never carry those fields.
2. **Stamp identity into new anchors** so they are self-sufficient going forward.
3. **Fail loudly** — a rebuild resolving no franchise id while the root says `mode: "franchise"` is a contradiction and raises, rather than silently loading a different roster.

> **The pattern, for the third time this project: a fallback that quietly substitutes something plausible.** The empty-defenses cache treated "no documents" as "not loaded"; the mask generator wrote a blank on failure; this loaded a different roster when context went missing. In each case the substitute was valid-looking data, which is why nothing noticed.
>
> **And the second-order lesson: Team Builder keeps surfacing general defects.** It exposed this, and the sim-perf audit exposed the empty-defenses thrash and 443 in-loop writes. A feature that makes identity visible is an unusually good detector of places where identity was being handled loosely all along.

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

**Step 3 offers two paths.** Rescoped 3 August 2026 — see §4.5c.

1. **Edit this roster** — default. All 15 pre-populated from the replaced program and editable.
2. **Import my roster (CSV)** — for users who genuinely have data.

*Keep* and *Generate* are retired.

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

### 4.5c Rescope — two paths, minted identities, universal portraits

**Rescoped 3 August 2026.** Driven by a finding in Phase 3d: portrait art comes in two incompatible forms, and that constraint reshapes the feature.

#### What forced it

The 1,536 base-league players have **flat portraits** — face and jersey painted into one finished PNG, with no mask. Recruits have **layered portraits** — a kit plus a mask, so the jersey can be recoloured for whichever program signs them.

A custom program that inherited its roster therefore inherited **unrecolourable** portraits, and its players appeared in **the replaced program's jersey and mascot wordmark**. That is a Phase-0-class identity leak in the one medium the detector cannot inspect: pixels inside an image.

Keeping the inherited faces *and* wearing the custom uniform is impossible without authoring masks for all 1,536 base players — an offline art project, not a code change.

#### The rescope

| | Before | After |
|---|---|---|
| Step 3 paths | Keep · Edit · Generate · Import | **Edit · Import** |
| A user wanting the team as-is | *Keep* path | **Play that team in normal mode** — not a mod |
| Portraits | Optional, inherited where present | **Every player gets a recolourable portrait** — assigned or picked |
| `player_id` | Inherited base-league UUID | **Minted fresh at Apply**, as signed recruits already do |
| Image sources | — | **Our assets** at launch; **uploads** as a fast follow (3c) |

#### Why this simplifies rather than shrinks

- **The shared-master corruption problem disappears.** Painting a recoloured portrait to `players/master/<player_id>.png` was unsafe because inherited players carried base-league UUIDs shared across every save. With no *Keep* path, nothing needs the shared master, so minting fresh ids removes the hazard entirely — no franchise-scoped keys, no fallback logic, no cleanup.
- **The mascot wordmark resolves for free.** Recolourable kits paint through `resolve_team_display`, so jerseys carry the custom program's colours *and* mascot.
- **Walk-ons stop being a special case.** All 15 receive portraits; none is left on the generic headshot.
- **Retiring *Keep* costs nothing real.** A user who wants a program exactly as it ships can select it in normal play. A mod that changes nothing was never the point.

#### Consequences to carry through

- **The §4.3 top-up applies universally.** Decision #4's carve-out — *Keep* is byte-identical and exempt — is retired with the path.
- **§4.5b still governs.** *Edit* seeds from the replaced program's names, height, weight, jersey and attributes; anything the user does not change is inherited. The editor remains a diff, not a form.
- **Generate is retired**, so a wholly new roster means hand-editing 15 players or importing a CSV. A real trade, accepted for fewer paths.
- **Clicking through the editor unchanged no longer reproduces the replaced program.** Attributes and names carry over, but portraits and identities are new. That is correct — the user is building a new program, not adopting an old one.
- **Verify before minting:** confirm nothing outside the franchise depends on a player's `player_id` matching the base-league UUID.

### 4.5a Roster size and walk-ons

> **The user authors all 15 — the inherited 12 plus 3 walk-ons generated when the editor opens.**

**Established, 1 August 2026:**

| Fact | Detail |
|---|---|
| Core team document | **12 players.** All 128 verified; the universal pool contains zero `Walk On` archetypes. |
| Walk-ons | **Generated at franchise init**, not stored in core. `FranchiseManager.initialize_season` calls `generate_walk_on_profile()` three times per team after cloning core FPDs. |
| Generation | `draw_position_intent` + `generate_player` on a **tier drawn per walk-on** from `WALK_ON_TIER_WEIGHTS` (Poor 65 / BelowAverage 25 / Average 8 / Good 2 — no longer 100% Poor); year drawn **directly as a roster year** from `WALK_ON_YEAR_WEIGHTS` (FR 10 / SO 40 / JR 40 / SR 10 — no JH, no advance step); `archetype: "Walk On"`, `entry_tier` = the drawn tier |
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

- **Capped mode gains nothing exploitable.** Walk-ons are mostly weak (tiered Poor 65 / BelowAverage 25 / Average 8 / Good 2 — the occasional Good is still capped), points still cannot cross a player boundary, and their budgets are fixed at generation.
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
- **This applies to both paths.** Import authors full players by definition; edit must preserve.
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
15. **Both paths end at `players` = 15**, `scholarship_players` = 12, with 3 `archetype: "Walk On"` FPDs. Verified after edit **and** import.
16. A custom program and a CPU program in the same franchise hold identical `players` / `scholarship_players` / `training_squad_players` counts at week 1 **and** after Training Camp.
17. **No orphaned FPD documents remain after Apply.** Init's three superseded walk-ons are deleted, and staging is checked for orphans left by the previous `$set` behaviour.
18. **Walk-ons are stable across wizard navigation and are not re-rollable** — leaving Roster and returning yields the same three players with the same attributes.
19. **Import of any row count other than 15 is rejected with a stated reason** — not truncated, not padded.
20. The uncapped pool and league markers are computed on **15-player franchise totals**, matching what a custom program is now authoring.
21. **A custom program created with no edits carries every inherited field forward** — names, height, weight, jersey, attributes, year, `Home Region`, development metadata — differing only in identity, colours, minted `player_id`s and portraits. Verified by diffing every field of all 15, not by spot-checking.
22. **Editing one attribute on one player changes only that value.** Every other field on that player, and every field on the other 14, is unchanged.
23. **`Home Region`, archetype, year and development metadata survive both paths.**
26. **Step 3 offers exactly two paths** (§4.5c). No *Keep* or *Generate* affordance remains in the UI or the API.
27. **Every Team Builder player has a minted `player_id`**, distinct from the base-league UUID, and **no base-league master is ever overwritten** — verified by checking `players/master/` for modifications after Apply.
28. **All 15 players render in the custom program's uniform and mascot wordmark** — verified in a live game, not in the picker preview.
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

**The renderer exists.** `generate_non_a1_courts.mjs` is a working parametric court generator producing exactly **3,333 × 2,083**. 3b is a **port and a parameterisation**, not a build:

1. Expose the five colour parameters below as inputs (they are currently distribution-driven).
2. Port the drawing from Node to **browser canvas** per §6.1 — one code path for web and a downloadable build.
3. Deliver the result to Phaser as a **blob/object URL**, never a data URI (see the constraint below).

Geometry is copied verbatim from the existing constants. Nothing is re-measured.

#### 6.3b Persistence — parameters only, and they must actually persist

> **A generated court is stored as its five parameters, never as an image.** Generation is deterministic, so the parameters are the artefact. Regeneration happens client-side on each load.

Storing the rendered image is wrong on every axis: a 3,333 × 2,083 JPEG is 1–2 MB per franchise, a data URI is the one form Phaser rejects (§6.3c), and object storage would break the offline premise §6.1 exists to protect.

**Defect found 2 August 2026.** The wizard sends `court: { hardwoodStyle, oobColor, laneColor, centreCourtColor, halfArcFillColor }`, but **the Apply request model has no `court` field, so FastAPI drops it silently.** The `team_builder` overlay persists identity and colours but not the court parameters. Regeneration then falls back to `visual.court` in **localStorage**, which survives only the creating session on the creating browser.

Two failures in one:

1. **The parameters never reach the server**, so they cannot round-trip. A reload restores defaults derived from primary and secondary.
2. **localStorage is acting as the store**, making the court per-browser rather than per-franchise. The same franchise renders differently on another device.

No error is raised at any point — the preview looks right, Apply succeeds, and the loss appears only after a reload. This is the silent-substitution pattern v1.3 §8.6 forbids, and the same shape as every other defect this phase: **the client sends something the server does not read.**

**Rule: the five court parameters are part of the Team Builder overlay and are written at Apply, exactly like the colours.** localStorage may cache; it may never be the source of truth.

**One object, one place.** The overlay lives on the franchise document (`franchises.team_builder`) and holds `primary_color`, `secondary_color`, `jersey_preset` and `court`. `resolve_team_display` reads only that field. A team's visual identity is a single object; splitting it across documents creates a second source of truth for one concept.

> **The FTD identity mirror was deleted, not repaired.** Apply also wrote `team_name` / `primary_color` / `secondary_color` onto the FTD as a denormalization for roster joins. Investigation found **nothing read them** — no query projected those fields, and the join map used core `teams.name`. The mirror was write-only, non-atomic with the overlay write, and could therefore be silently *missing* after a partial Apply, causing joins keyed on the custom name to miss while core-name joins succeeded.
>
> The first fix made it an explicit cache with overlay fallback and self-heal. The better fix was to establish what it saved: **one O(1) franchise-document read.** Nothing. So the mirror, its `$set`, its cache helper and its heal path were removed, and joins resolve the custom name directly from the overlay.
>
> **A cache earns its place by avoiding expensive work.** Reading one document is not expensive, and a cache kept because it was already there is pure surface area. Deleting the mirror removed the partial-Apply failure mode entirely rather than defending against it.

> **Testing note.** Criterion 6 cannot be judged in the creating session — localStorage masks the defect. **Reload, or open the franchise on another browser, before assessing.**

**User-exposed parameters:**

- Hardwood style — selects the `{inside}_{outside}` variant pair
- Out-of-bounds colour
- Free-throw lane colour
- **Outside-wood colour** — see the correction below
- Free-throw half-arc fill colour

> **Naming correction, 3 August 2026.** This section originally said *"centre-court colour,"* which was wrong. **There is no centre-circle fill.** The control paints the Node generator's `outsideWood` region — the full in-bounds floor first fill, covering midcourt and everything outside the three-point lobes. The `insideWood` region is the two three-point key lobes, set by the hardwood style and not separately exposed.
>
> Every sweep test passed while this was mislabelled, because the tests asserted *that a colour changed*, not *that the correct region changed*. Region-identity probes now check midcourt against outside wood and the left lobe against inside wood, and assert the lobe does **not** match outside when tones differ.

**Rename the persisted key while it is free.** The implementation carries `centreCourtColor`, retained "for the overlay contract" — but per §6.3b no such contract exists: Apply drops the `court` field, nothing persists server-side, and the only consumer is localStorage in the creating session. **No franchise has this key stored**, so renaming costs nothing today and requires a migration the moment the round-trip ships. `user_team_id` — a field carrying a display name despite its suffix — is the deferred example of what happens when this window is missed.

**Constraints:**

- Court markings — rim positions, lane geometry, OOB lines, centre line, arcs — are **fixed geometry**. The user colours them; the user never moves them. The animation system depends on exact placement.
- Output dimensions are non-negotiable.
- Defaults derive from the program's primary and secondary colours, so a user who changes nothing still gets a coherent court.

**Resolved 2 August 2026 — and then re-resolved.** No layered source (PSD/AI/SVG/FIG) exists. But a **parametric generator does**: `scripts/generate_non_a1_courts.mjs` rendered 120 of the 129 courts from explicit constants, and `Court_Template_Implementation_Spec.md` documents the gameplay-to-pixel anchors. **Geometry does not need measuring. It needs porting.**

**The acceptance bar is pixel agreement with a generated court** — one of the 120, not one of the 8 references. A port that reproduces the constants exactly will match by construction.

#### 6.3a Step 0 failed against the wrong artefact

**Result, 2 August 2026:** rendering Morristown from the `generate_non_a1_courts.mjs` constants and diffing against `morristown_court.jpg` gives **1 of 12 features** inside the ≤2px bar (the left free-throw line). Means run 5–18px.

| Feature | Expected | Measured | Δ |
|---|---|---|---|
| Centre line x | 1666 | 1666 | **0** |
| Left FT line x | 872 | 873 | 1 |
| Left lane y1 / y2 | 806 / 1271 | 807 / 1270 | 1 |
| OOB top y | 158 | 163 | 5 |
| Right FT line x | 2452 | 2459 | 7 |
| OOB bottom y | 1924 | 1914 | 10 |
| Centre circle r | 527 | 507 | 20 |
| OOB left x | 150 | 177 | 27 |
| 3pt right control x | 2213 | 2173 | 40 |
| 3pt left control x | 1112 | 1159 | 47 |
| OOB right x | 3183 | 3131 | 52 |

**The error is not noise.** Every failing feature moved **inward toward centre** while the centre line is exact — a scale mismatch about the midpoint. Layered on that, **left-side features are consistently more accurate than right-side ones** (left FT Δ1 vs right FT Δ7; left OOB Δ27 vs right OOB Δ52), the signature of geometry authored by measuring one half and mirroring it against a source that is not truly symmetric.

**Resolved: Morristown was the wrong proxy.** It is one of the **eight Conference 1 / A1 reference courts that `generate_non_a1_courts.mjs` deliberately excludes** — hand-authored art, not generated output. Step 0 diffed the constants against one of the nine courts those constants never produced.

The deltas are therefore not drift or measurement error. They are **the gap between hand-drawn reference art and the machine geometry later derived from it**, which is exactly what the inward-scaling and the left-accurate/right-inaccurate asymmetry describe.

**The constants are authoritative and the art is derived** — `Court_Template_Implementation_Spec.md` records gameplay-to-pixel anchors mapping the sim's coordinate system onto the image. Re-run Step 0 against any of the 120 generated courts; it should agree at or near zero, because those courts were rendered from the constants under test.

> **The lesson is the proxy, not the measurement.** Morristown was chosen as the reference while §2 asserted no generator existed. A wrong "established fact" produced a correct measurement of the wrong thing — and the measurement's own error pattern was what exposed it.

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

**Or: fitted assignment**, with re-roll. **This is the default** — every player is assigned automatically and the picker is an optional override.

**Assignment reuses the existing CPU portrait pipeline. Do not write a new fitting heuristic.**

| Script | Role |
|---|---|
| `scripts/classify_player_archetypes.py` | frame (Slight / Lean / Normal / Broad / Doughy), definition (Cut / Toned / Soft), skin, hair, expression — from height, weight, ST, AG and best-position RT |
| `scripts/player_ethnicity.py` | name-based race with a deterministic UUID-seeded weighted fallback |
| `scripts/players_archetypes.csv` | the committed classification of all 1,536 base players — the distribution any custom roster should resemble |

The Team Builder editor already collects every input the classifier needs, so a user-typed player is classified exactly as a CPU player was.

#### Coverage, measured 3 August 2026

The classifier produces **117** `(frame × definition × skin)` cells. `set_0001`'s 300 images cover **69**; **48 are empty**, and 21 hold a single image.

| Axis | `set_0001` | League |
|---|---|---|
| Black / white / other | 56.0 / 27.7 / 16.3 | 52.4 / 31.4 / 16.2 |
| Lean | **65.0%** | **19.3%** |
| Normal | 20.3% | 27.9% |
| Slight | 7.7% | 18.9% |
| Broad | **5.7%** | **26.7%** |
| Doughy | **1.3%** | **7.3%** |

**Skin is well covered. Frame is inverted.** Broad-Toned holds 5 images against 291 league players; Doughy-Soft holds 4 against 112; Broad-Soft holds none. **23.4% of league players sit on a zero-image triple** and can never match exactly.

**Why:** `set_0001` is a *recruit* set — seventeen and eighteen year olds, who genuinely are lean. The league is developed players who have filled out. The shortfall is structural, not a defect in either artefact, and **no relaxation rule fixes it — relaxation only redistributes scarcity.**

#### Relaxation order — corrected

> **Hold `frame`. Relax `skin` within race family first, then `definition`, and relax `frame` last.** Never fall back to a uniform random pick.

An earlier draft of this section had the opposite order — hold skin, relax frame. **The measurement disproved it.** Skin coverage tracks the league closely while frame is the scarce axis, and holding frame while relaxing skin within race family lifts coverage from 76.6% to **93.7%**. A 7'1" 264 lb player with a lean face is a more visible error than one with a neighbouring skin tone.

#### Uniqueness collides with scarcity

Blocking duplicate portraits within a roster is unenforceable in sparse cells: a roster with four Broad-Toned players faces five such images across every skin tone. **Where a cell cannot supply a unique image, frame relaxation takes precedence over the uniqueness rule** — and the fix for the underlying scarcity is §6.5a, not a cleverer matcher.

#### 6.5a Targeted extension set

**A separate set of ~150 portraits, baked into the under-served cells.** Kept separate from `set_0001` deliberately: a Lean-heavy pool is *correct* for recruits, and folding developed-player bodies into it would make incoming classes look wrong.

- **Recruit assignment continues to draw from `set_0001` only.**
- **Team Builder draws from `set_0001` ∪ the extension set.**
- Built with the existing pipeline — `generate_player_portraits.py` → `finish_portraits.py` — not a new one.
- The extension publishes the same filtered manifest subset: `build.frame`, `build.definition`, `portrait.skin`.

**Allocation, approved 3 August 2026.** Every cell with league demand ≥ 3 raised to a combined floor of 3; remainder allocated proportionally; cells below 3 league players skipped and their budget redirected to Broad-Toned. Result: exact match **76.6% → 99.2%**, with 13 league players (0.8%) left on zero-image cells — all on cells of ≤ 2 players, mostly `ambiguous` skin, where relaxation is visually harmless.

**Pilot outcome — 20 images, 12 Broad-Toned and 8 Doughy-Soft.**

- **Style coherence: passes.** On a blind unlabelled sheet mixed with `set_0001`, the new images were not distinguishable — same lighting, tank, framing and paint quality. **Restoring the original anchors rather than regenerating them is what made this possible**; they were recovered from `~/gob-portraits/` and git history at `3c11f78a1`.
- **Anatomy: partial, and anchor-limited.** Body-lock to the Broad and Doughy anchors does move neck and shoulder mass relative to Lean. But the Doughy anchor is a soft teenager, and **age language changes the face, not the mass** — prompts cannot invent bulk the anchor doesn't hold.

**Decision: teen age language across all 150.** The entire league reads late-teen and the game is college basketball — a developed-senior register would be the outlier against 1,536 existing portraits, not an improvement. The frame benefit comes from the body anchors, which apply in either register.

> **Recorded, unresolved:** frame reads weakly at a head-neck-shoulders crop, and portraits render at roughly 60–80px in the matchup popup and event cards. It is possible that Broad versus Lean is imperceptible at deployed size, in which case frame-matched assignment optimises something users cannot see and skin/hair matching matters more. A four-image comparison at render size would settle it. Not blocking; worth knowing.

Expected effect: exact match rises from **76.6%** to **99.2%**, and the collision problem in sparse cells disappears.

#### Delivered 3 August 2026

**150 / 150 baked, reconciled and published.** Frames: Broad 43 · Slight 43 · Normal 39 · Doughy 20 · Lean 5. Every cell matches the allocation exactly; zero UUID collisions with `recruit_set_0001`.

**Naming — two sequences by purpose, not one counter.**

| Logical | On disk / R2 |
|---|---|
| `recruit_set_0001` (300) | legacy `set_0001.json`; kits remain at `recruits/kit/<uuid>.png`, not migrated |
| `builder_set_0001` (150) | `builder_set_0001.allocation.json`; kits at `portrait-kits/builder_set_0001/<uuid>.png` |

Team Builder's pool is **`recruit_set_0001` ∪ `builder_set_0001`**. Recruit assignment remains `recruit_set_0001` alone (`BASE_IMAGE_SET_ID`). A single global counter was rejected: recruits would skip 0001 → 0003 with no explanation visible in the name.

**Within-cell variety needed two rebake rounds.** The first pass produced near-twins — body-lock plus similar genes — fixed with fresh genes on 15 high-similarity pairs and forced divergent hair and expression on 8 more.

> **Cosine similarity is the wrong metric here and should not be trusted as a gate.** Shared body-lock dominates it, so it keeps flagging pairs that hair and expression clearly separate on a roster. The eye is the authority; the metric is a search tool for candidates.

**Artifacts:** `builder_set_0001.manifest.json` (full genes), `builder_set_0001.published.json` (filtered subset — `build.frame`, `build.definition`, `portrait.skin` only), 450 R2 objects, `SCHEMA.md` updated for both sets.

#### 6.5b The blank-mask defect — a path used once

**Found 3 August 2026** when 2 of 15 players on a live custom roster rendered the generic silhouette. Assignment was correct; both had exact-match `builder_set_0001` ids. **Ten builder kits had shipped with empty tank masks** — eight byte-identical, two near-zero — so `make_signed_master` raised `no tank found` and no master was ever written.

**Root cause:** `ensure_sidecars_from_png` on the **`keep_teen` path** called the tank detector on an **RGBA** array. Alpha 255 inflated max − min, so shaded white fabric failed the neutrality gate and the tank came out empty. The function then **wrote that empty mask anyway**, while falling back to person-bbox for the JSON geometry — two artifacts derived from one detection, and only one of them noticed the failure. `bake_one` and the recruit bake used RGB and were unaffected, which is why `recruit_set_0001`'s 300 masks were clean.

**That path exists because of a late decision.** Choosing teen age language created a rebake route used for exactly one batch of 10 images — and all 10 were damaged. **A code path used once is a code path nobody tests.**

**Why nothing caught it earlier:**

- Reconciliation counted images; variety QC compared faces. **Both check the portrait; neither checked the mask.** The visible artifact was fine.
- Warm-paint caught the exception per player, logged it, left `image_painted` unset, and **Apply still returned success**.
- `ensure`-on-404 resolved the builder prefix correctly, found the kit, and failed on the same empty mask — **a retry that re-reads a broken input is not a fallback**, it makes a transient-looking failure permanent.

**Fixes:** tank detection forced to RGB; sidecar rebuild asserts tank pixels before writing, with no blank write and no person-bbox mask fallback; a bake gate failing any attempt under 5,000 tank pixels with a re-roll; `--rebuild-masks` / `--validate-masks` CLI; and Apply now returns `portrait_paint` counts and logs both paint failures and missing-kit skips.

**Audit result:** `recruit_set_0001` clean across all 300 (minimum ~113k tank pixels); `builder_set_0001`'s 10 rebuilt and re-uploaded; both affected masters re-painted.

> **The general rule: validate the artifact the system consumes, not the one a person looks at.** Every check in this phase examined portraits. The mask is what makes a portrait usable, and nothing looked at it until two players went missing on a live roster.

**Seed stability.** The classifier's rerolls are UUID-seeded and Team Builder `player_id`s are minted (§4.5c). **The portrait shown in the wizard must be the portrait that ships** — either mint the id when the wizard opens, or seed from something stable at that moment and carry it through Apply. This is the walk-on idempotency problem in another form: a value the user sees, then silently regenerated.

**Duplicates are blocked within a roster where the pool allows it**, and re-roll skips ids already used. Where a cell cannot supply enough distinct images, matching quality wins over uniqueness.

**Documented drift:** the decision log states a 55/35/10 race split while `RACE_WEIGHTS` in code is 60/30/10; the committed result is 52.4 / 31.4 / 16.2 after name overrides. **The code is authoritative** — correct the doc.

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
11. **A generated court renders as the live playing surface in a real game** — not a preview, not a file check.
12. **The five court parameters round-trip through the server** (§6.3b). Verified by creating a franchise, **reloading**, and confirming the chosen colours survive — then by opening the same franchise in a different browser.
13. **No court image is persisted anywhere** — not Mongo, not GridFS, not disk. Parameters only.

---

## 7. Sequencing and dependencies

| Phase | Depends on | Can start |
|---|---|---|
| **0 — Repair** | — | Immediately. Blocks everything. |
| **1 — Attributes + editor** | Phase 0 | After Phase 0 |
| **2 — Team select** | Phase 0 | Parallel with Phase 1 — independent surfaces |
| **3a — Banner** | — | **Closed** |
| **3b — Court** | — | **In progress** |
| **3d — Headshots** | Manifest subset published | **Next — moved ahead of 3c.** Stores a *selection*, not an image, so it needs no storage infrastructure at all |
| **3c — Uploads** | 3b, 3d, **and R2 upload storage** | Last. The only workstream that requires infrastructure |

**Asset storage is governed by `gob-asset-architecture.md`,** not by this plan. Its rule — *store bytes only for what a computer cannot recreate* — already applies to 3a and 3b, which persist recipes rather than renders.

**Why 3d moves ahead of 3c.** Headshot selection from `set_0001` stores an id; fitted random assignment stores a choice. Neither is an upload, so neither needs storage, normalization, cascade delete or a sweeper. 3c is the sole workstream that genuinely requires object storage, so it should be last and its prerequisite is explicit rather than implied.

**Phases 1 and 2 are genuinely independent** and can run concurrently if you want two threads. Phase 3 is one thread with internal ordering.

### 7.1 Where the asset architecture fits

`gob-asset-architecture.md` is a **standing rule plus three work items**, not a phase. The items have unrelated dependencies and should not be scheduled as a block:

| Item | Depends on | When |
|---|---|---|
| Court parameters round-trip (§6.3b) | — | **Now** — a live defect, already scoped |
| Static league assets → R2 | — | Anytime. Independent of every feature. |
| Upload storage, cascade delete, orphan sweeper | Web or online play existing | **Immediately before 3c**, and not before |

**Player imagery splits across two of these.** Headshots chosen from `set_0001` (3d) store an id and need nothing. User-uploaded player images (3c) need the full storage path. Treating "player images" as one requirement would drag infrastructure forward into a phase that doesn't need it.

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
| 4 | Players below 60 are topped up to 60 in capped mode, **on every path** | Clean rule; the alternative is an unsatisfiable minimum. Accepts that capped is near-inherited, not literally inherited. The *Keep*-path exemption was retired with the path itself (§4.5c). |
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
| 30 | **Step 3 rescoped to Edit and Import** (§4.5c) | Base-league portraits are flat and unrecolourable, so an inherited roster wore the replaced program's jersey and mascot. A user wanting a program as-is can play it in normal mode; a mod that changes nothing was never the point. |
| 31 | **Team Builder players get minted `player_id`s** | With no *Keep* path nothing needs the shared base-league master, so minting removes the overwrite hazard entirely — no franchise-scoped keys, no fallback, no cleanup. Signed recruits already do this. |
| 32 | **Every player gets a recolourable portrait** | The only faces that can wear a custom uniform are recruit-style kits. This also retires the generic-headshot walk-on case and makes the mascot wordmark correct for free. |
| 33 | **Uploads are a fast follow, not a launch requirement** | Uploads are the sole part of the feature needing infrastructure. Building R2, cascade delete and a sweeper before any real usage means guessing at requirements that usage would answer. |
| 34 | **Portraits resolve through one reference that can hold either source** | A `set_0001` id today, an uploaded object key later. Keeps uploads an added backend rather than a hunt for every place that assumed the old shape. |
| 35 | **Hold frame, relax skin first** (§6.5) | Measurement inverted the earlier assumption: skin coverage tracks the league, frame is the scarce axis. Holding frame lifts coverage 76.6% → 93.7%. |
| 36 | **Bake a ~150-image extension set rather than relax harder** (§6.5a) | 23.4% of league players sit on a zero-image cell. Relaxation redistributes scarcity; only more images remove it. The pipeline already exists. |
| 37 | **The extension set is separate from `set_0001`** | A Lean-heavy pool is correct for seventeen-year-old recruits. Folding developed-player bodies in would make incoming classes look wrong. Recruits keep drawing from `set_0001` alone. |
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
