# Team Builder v1 — Implementation Spec

**Product:** Geeked-Out Basketball (GOB)
**Feature:** Team Builder — let a user put their own program into a new franchise
**Spec version:** 1.3
**Status:** Complete. Tasks A and B shipped; all 34 acceptance criteria verified with evidence.
**Last updated:** 27 July 2026

---

## 0. How to use this document

**This document is maintained independently of the implementation.** It is not a record of what the code does — it is the statement of what the feature is supposed to do, against which the code is checked. Do not update it from the codebase. When code and spec disagree, that is a finding to raise, not a discrepancy to erase.

**It is authoritative on product behavior, UX flow, and user-facing copy.** Where it specifies a string, that string is the copy — it has been designed against competitive research and is not placeholder text.

**It is deliberately silent on implementation.** No data models, no storage, no component structure. Those follow the patterns already in the repo.

**Two audiences now that v1 has shipped:** reviewers checking the work against §11, and whoever picks up v1.1 (logo upload, multiple slots, sharing) and needs to know why the boundaries in §10 and §12 are where they are.

---

## 0.1 Changelog — v1.2.1 → v1.3

Recorded after the fix and closeout batches landed. Nothing here is a change of intent — it is proven implementation shape being written down so it survives.

| # | Change | Why |
|---|---|---|
| 1 | **Status flipped to Complete.** Header, §11. | All 34 criteria verified with evidence, including core-immutability hashes and a localStorage-cleared art re-verify. |
| 2 | **Asset interception location recorded: `getTeamAssetPath`.** §3.3. | The same shared-producer lesson as §3.2, applied to art. One function made franchise-aware fixed 37 call sites plus 3 coach-art sites. The v1.2 text said custom overlays *bypass* `getTeamAssetPath`; they go *through* it. |
| 3 | **Server payload is the source of truth for visuals; localStorage is a cache.** §3.3, decision 26. | The first implementation read the overlay from `FranchiseLS` only, which reintroduced broken images in any fresh client — different browser, incognito, cleared storage. Recorded as a requirement so it is never "optimized" back. |
| 4 | **Terminal asset fallback must be generic, never a 404 path.** §3.3, decision 27. | Defense in depth. Even total failure of overlay resolution now degrades to plain rather than broken, which is the §1 constraint. |
| 5 | **MO = 0 at init recorded as league-wide.** §2.1. | Verified identical for imported and core-cloned players. Recorded so nobody later reads it as an import bug and "fixes" imported players into being different from everyone else. |
| 6 | **Generate-mode meter must be labeled estimated.** §9.3. | Band resampling means the figure isn't final until Apply. A meter that reads as measured when it's estimated is a small honesty gap. |
| 7 | **Three acceptance criteria added (32–34).** §11. | Covering the properties the closeout batch established. |

### Changelog — v1.2 → v1.2.1

| # | Change | Why |
|---|---|---|
| 1 | **§9.4 clarified: eligibility evaluates live in the wizard, then freezes at Apply.** Also §11 #28, decision log #25. | The v1.2 wording said only "recomputes from the current roster," which reads as season-long recomputation and was reported as an implementation failure during verification. The implementation was right and the spec was ambiguous. Eligibility constrains authored input, not simulated outcomes. |

### Changelog — v1.1 → v1.2

Driven by the §2.3 validation results and the §3.2 escalation, both of which came back after Task B began.

| # | Change | Why |
|---|---|---|
| 1 | **Fourth budget condition added: top-5 cap at 3,950.** §9.1, §9.2. | The §2.3 validation showed a total-points budget structurally cannot control concentration. CPU teams hold ~57% of their talent in the top five; a min-maxing user reaches ~75%. The stacked build hit 4,788 against a league max of 3,954. Capping the thing that decides games is more precise than constraining it indirectly. |
| 2 | **Per-player floor cut from 220 to 24.** §9.2. | 95 of 128 teams carry a player below 220. The floor was stricter than three-quarters of the league — the day-one legitimacy failure §9.2 was explicitly trying to avoid. It drops to a sanity guard against null/zero players, anchored at the observed league minimum. |
| 3 | **Governing principle stated for all four limits.** §9.2. | *No custom program may exceed what already exists in the league on any measured dimension.* Ceiling = league max player, top-5 cap = league max top-5, floor = league min player. Team total stays at P90 deliberately — see §9.2. |
| 4 | **Meter spec revised to two bars plus two checks.** §9.3. | Top-5 is the most informative number a user can see about the team they're building. It needs its own bar, with league context markers. |
| 5 | **§2.3 converted from an open query to recorded results.** §2.2, §2.3. | The query ran. Both checks failed, in opposite directions. Results are now established data. |
| 6 | **§3.2 resolver resolved to shared-producer interception.** §3.2. | Enumeration returned 58 surfaces against a threshold of 30, plus structural blockers. Escalation worked as designed. Six shared producers deliver the same coverage with a tenth of the diff and cover future screens automatically. |
| 7 | **`GET /teams` identifier renamed `id` → `object_id`.** §2.1. | Ambiguity against the `team_id` slug, in exactly the code where a wrong key produces silent no-match rather than an error. Renamed before anything consumed it. |
| 8 | **Card banner convention added.** §3.1. | Task A shipped 10.4 MB of banner art in the first viewport. Card-sized WebP derivatives take it to ~1 MB, and §3.3's generated art has to match the same convention. |
| 9 | **Taglines confirmed dropped.** §12 #22. | Data existed only for the original 8 and only as a hard-coded object. Restoring them Core-8-only would create a visible two-tier league at exactly the moment the product says all 128 are real programs. |

### Changelog — v1.0 → v1.1

| # | Change | Why |
|---|---|---|
| 1 | Work split into Task A (expand team-select to 128) and Task B (Team Builder). | Team-select listed only 8 hard-coded programs. Doing the picker first made Task B's diff smaller and let the picker ship value on its own. |
| 2 | Phase 1 investigation section replaced with established facts. | Investigation complete; its answers became constraints. |
| 3 | Franchise display resolver added as a non-optional first build item, with a wire-everything scope policy and an escalation trigger. | Names and colors are re-read from core `teams` almost everywhere. Without a resolver the feature's central promise is false. |
| 4 | Generated placeholder art added as a non-optional first build item. | `getTeamAssetPath` falls back only on an unknown asset key, not a missing file. A custom slug produces broken images. |
| 5 | Third eligibility condition added: per-player floor. | Budget and ceiling alone permitted a six-man all-star team that passed both checks. |
| 6 | Budget figures set: 6,400 / 1,035 / 220. | Team and ceiling derived from the measured distribution; floor set by judgment. *Superseded in v1.2.* |
| 7 | Corrected the budget example figures in the Review step. | v1.0 showed `1,840 / 2,200`, ~3× below real league scale. |
| 8 | "Transfer pool" copy removed. | It does not exist. |
| 9 | Class years restricted to FR/SO/JR/SR; JH and GR get no special handling. | Neither is a Team Builder concept. |
| 10 | Roster maximum set to 15. | Season-1 capacity: 12 scholarship + 3 walk-ons. |
| 11 | Abbreviation uniqueness redefined. | No league-wide abbreviation field exists. |
| 12 | Imported players must have EM/CH/MO randomized. | Excluded from the talent budget; set at season init. |
| 13 | Roster-shape metrics persisted alongside `hasEverExceededBudget`. | So a future eligibility rule can be applied retroactively. |
| 14 | Undo confirmed cut. | Generate/Import is not reversible without an explicit pre-replace snapshot. |

---

## 1. Context and fixed constraints

GOB is a browser basketball franchise sim with a **fixed 128-team, 16-conference league**. Users want to put their own program in.

| Constraint | Meaning |
|---|---|
| **League size is invariant** | Always 128 teams, always 16 conferences. Team Builder never adds a 129th team and never resizes or realigns anything. |
| **Slot replacement model** | The user's program **takes the place of** an existing program. It inherits that slot's conference, schedule, and opponents. |
| **Per-franchise overlay** | Customizations belong to a single franchise. Core `teams` and core players are never mutated. |
| **Single entry point** | Team Builder is reachable **only** from the team-select screen at the start of a new franchise. |
| **Generic assets are acceptable** | Custom art is not required. The uncustomized path must look plain and deliberate, never broken. |

This model is not a compromise — it is what EA's TeamBuilder has shipped across eight titles since 2009 and what Football Manager's Create-a-Club does. Present it confidently in the UI.

---

## 2. Established facts

### 2.1 Codebase realities

| Area | Reality |
|---|---|
| **Schedule** | Fixtures are `(away_id, home_id)` ObjectId pairs across weeks. **Opponents and week structure survive a slot replacement.** Display names resolve through the franchise resolver (§3.2). |
| **Identifiers** | `object_id` = `str(teams._id)`, the ObjectId string. **This is the resolver key and the slot key**, used by franchise schedule pairs, FTD, standings, and `user_team_object_id`. `team_id` = a slug (e.g. `BENTLEY_TRUMAN`) used by game-doc `teams{}` keys and some box-score paths. Mongo `_id` is never emitted in JSON. Never conflate them. |
| **Conference / region** | Inherited from the replaced slot via ObjectId. Unchanged. |
| **Standings** | ObjectId-keyed. A fresh 0–0 is correct. |
| **H2H history** | None carries into a new franchise. |
| **Write-time state** | At franchise creation there are **no `season_news` strings and no season game docs**. Both are written after the overlay exists, so write-time name resolution covers them. FPD `meta.team` / `user_team_id` are written at init and rewritten by Apply. *This is why v1's single-entry-point constraint matters structurally, not just for scope.* |
| **Roster size** | Season 1: **15** = 12 scholarship + 3 walk-ons. After training camp: 12 active + 3 training squad. |
| **Class years** | Canonical set: JH, Freshman, Sophomore, Junior, Senior, Graduate. JH is recruits only. GR is earned in-game. Active players are FR/SO/JR/SR. |
| **Position** | Not required for play. All players can play any position. |
| **Attributes** | 15 total. Talent sum ("core-12") = SC + SH + ID + OD + PS + BH + RB + ST + AG + ND + IQ + FT. **CH, EM and MO are excluded from talent totals** and randomized per franchise at init. |
| **Overall rating** | No separate overall. RT = max of the five position ratings. |
| **MO at init** | **`MO` is 0 for every player at season init, in every mode.** Verified identical for imported and core-cloned players (`Player.randomize_game_attributes`). CH and EM are randomized; MO is not. This is league-wide behavior, *not* an import defect — do not "fix" it for imported players only. |
| **Transfer pool** | **Does not exist.** Camp cuts move players to the training squad; week-35 release deletes the record. |
| **Abbreviations** | No league-wide abbreviation field. Recruiting fakes it with a hard-coded rival map and `slice(0,3)`. |

### 2.2 League distribution (measured, 128 teams / 1,536 players)

**Per-team core-12 totals:** min 3,561 · P25 ~5,010 · median 5,566.5 · mean 5,518 · **P90 ~6,369** · max 7,027

**Per-team top-5 sums:** min 2,282 · median 3,148 · P90 3,640 · **max 3,954**

**Per-player core-12 totals:** **min 24** · P5 140 · P10 213 · median 455.5 · mean 459.9 · P75 581.8 · top-quintile band 617–1,034 · **max 1,034**

**Per-team weakest player:** min 24 · P10 61 · median 151.5

> Team totals were measured on 12-player universal rosters, not post-init 15-player rosters with walk-ons.

### 2.3 Validation results — both checks failed

The §2.3 query ran against the v1.1 values (6,400 / 1,035 / 220). **Both checks failed, in opposite directions.** Values revised in §9.2.

**Balance check — failed.** A maximally-stacked custom roster reached a top-5 of ~4,788, against a league max of 3,954 and a P90 of 3,640. **A total-points budget cannot control concentration.** CPU teams hold roughly 57% of their talent in their top five; a min-maxing user reaches 75%. The floor was an indirect proxy for a constraint that needed to be direct.

**Legitimacy check — failed.** 95 of 128 teams carry a player below 220, and 169 of 1,534 players sit below it. The floor was stricter than three-quarters of the league on itself.

---

## 3. What shipped

### 3.1 Task A — team-select expanded to 128

`TeamPicker` (`FrontEnd/static/js/shared/teamPicker.js` + `FrontEnd/static/css/team-picker.css`), consumed by `franchise-select-team` and by Team Builder Step 0. All 128 programs, search, region and conference filters, conference grouping, lazy-loaded art. Create path unchanged (`/franchise/select-team` with `home_slot`; tutorial path preserved). `GET /teams` extended additively with `conference`, `region`, `team_id`, `object_id`.

Selection keys on `object_id`, not name.

**Card art convention:** `{slug}_banner_card.webp` — 400 px wide (~141 px tall), WebP q80. 129 cards at ~10.7 KB average, 1.35 MB total. Full `banner_primary` is for detail views only. **§3.3's generated art follows the same convention.**

Measured cold load: 128 cards rendered in 93 ms, DOMContentLoaded 161 ms, `GET /teams` 4 ms / ~22 KB.

### 3.2 Task B, first build item — the franchise display resolver

Names, colors and mascots were re-read from core `teams` almost everywhere. Without a resolver a user names their school Riverside Prep and still sees "Morristown" on the schedule — the feature not working, and §7's copy a lie.

**Coverage requirement:** a user must never see the replaced program's identity anywhere in the app. This is unconditional.

**Method: intercept at the shared producers, not at individual call sites.** The enumeration returned **58 distinct display surfaces** against the §3.2 threshold of 30, plus structural blockers, and correctly escalated. Six shared producers — `_format_team_name_map`, FCC/schedule payloads, promoted `_ftd_team_display`, TeamManager/game snapshot, `/roster`, and the §3.3 asset strategy — deliver identical coverage at a tenth of the diff.

**Why the shared layer rather than 58 call sites:**

- Coverage is the same; the policy was never about method.
- **Future screens inherit resolution automatically.** With hand-wired call sites, screen 59 silently shows the replaced program's name and nobody notices for months.
- **The risk objection is neutralized by the no-op property below.**

**Required safety property: the resolver is a pass-through no-op when a franchise carries no Team Builder overlay.** Every existing franchise and every future franchise where the user simply picks a team hits byte-identical behavior. This is what makes touching shared producers low-risk rather than high-risk, and it is not optional.

Full enumeration retained at `team-builder-resolver-enumeration.md`. It is the checklist for acceptance criterion 5.

### 3.3 Task B, second build item — generated placeholder art

A custom slug produced broken images. Generated marks are derived from the program's initials and primary/secondary colors, with jersey and court previews from the palette and the 5 jersey presets. Output matches the §3.1 card convention.

**Acceptance: there is no broken-image state anywhere in the app for a custom program.** This is what makes cutting logo upload from v1 a safe decision rather than a visible hole.

**Interception happens inside `getTeamAssetPath` — the same shared-producer pattern as §3.2.** Custom overlays go *through* the function, not around it. Making one function franchise-aware corrected 37 call sites, plus 3 coach-art sites via a companion helper. Wiring individual surfaces was the wrong instinct twice; it is the wrong instinct in general.

Two properties are requirements, not implementation details:

1. **The server payload is the source of truth for the active visual. Client storage is a warm cache and must never be required.** The first implementation read the overlay from `FranchiseLS` alone, which reintroduced broken images in any fresh client — a different browser, an incognito window, cleared or evicted storage. The visual now hydrates from the franchise payload before first paint. **Do not optimize this back into a storage read.**

2. **The terminal fallback returns generic art, never a path that 404s.** An unknown slug resolves to `general`, so even total failure of overlay resolution degrades to plain rather than broken. This is defense in depth for the §1 constraint: *the uncustomized path must look plain and deliberate, never broken.*

> Earlier documentation claimed `getTeamAssetPath` falls back to `general` for missing files, and the code did not. The code now does. The docs were right about the intent and wrong about the state; both now agree.

---

## 4. Feature name and framing

**The feature is called "Team Builder."** Do not use "Create a Team," "Add My School," "Expansion," or "Custom Database."

The name never carries the explanation. The subtitle does:

> **Team Builder** — Put your own program in the league. Your school takes an existing team's place; the league stays at 128.

---

## 5. Entry point

**One entry point. New franchise only.** On team-select, Team Builder appears as an additional path alongside picking an existing program.

- Reads as a **peer option to picking a team**, not a settings toggle or secondary link.
- Adds no friction for the majority who just want to pick a program.
- Cancelling returns to team-select with `home_slot` preserved and no state lost.
- **Franchise creation does not begin until Apply.**

**Out of scope for v1:** any mid-franchise entry point, any franchise-hub surface, any post-creation editing. No partial versions, no dead navigation.

---

## 6. The wizard

Five steps. Step 3 is skippable. **A user who only wants a name and colors finishes in under two minutes without touching a file.**

Happy path: Slot → Identity → Colors → *skip roster* → Review. Four screens, no file handling, no failure modes. Roster import is the only genuinely risky part and it is opt-in, reachable only from a step the user actively entered.

### Step 0 — Choose the slot

The premise, not "step 1." Uses the Task A `TeamPicker` with `confirmation.enabled = true`, §7.2 copy in the panel, and `object_id` as the slot key.

- All 128 programs, searchable, conference-grouped, filterable.
- Primary CTA: **Choose this slot →**

### Step 1 — Identity

School name · Short name (box scores) · Abbreviation (3 chars) · Mascot · City/State.

**Abbreviation is the only field with real validation.** No league-wide abbreviation field exists, so validate against `slice(0,3)` of all 128 team names computed on the fly. On blur, inline, naming the conflict:

> RIV is already used by Riverton. Try RVP.

Live preview visible throughout — scoreboard bug and standings row as they will actually appear.

- Primary CTA: **Next: Colors →**

### Step 2 — Colors & look

- Primary / secondary / accent pickers, plus a jersey style selector with **5 presets**.
- **Preview updates continuously** — jersey, court, scoreboard bug. Colors are abstract as hex and concrete as a rendered uniform; the preview is the trust mechanism for this step.
- **Logo is optional and visibly marked optional.** The §3.3 generated placeholder shows by default, so the user sees a finished-looking team before uploading anything.
- Primary CTA: **Next: Roster →** · Secondary: **Skip roster — use generated players**

### Step 3 — Roster (optional, and it must feel optional)

Three choices as **cards, not a dropdown**:

1. **Keep [replaced]'s roster** — fastest, zero risk. Default.
2. **Generate a new roster** — fresh fictional players at the slot's talent band.
3. **Import my roster** — CSV (§8).

The §9 budget system applies here.

- Primary CTA: **Next: Review →**

### Step 4 — Review & apply

A **change-set summary, not a data dump**:

> **Riverside Prep** replaces **Morristown** in Conference 7.
> Identity: name, mascot, colors, logo — all set
> Roster: 14 players imported, 1 row skipped
> Team total 5,910 / 6,400 · Top five 3,410 / 3,950 — eligible for online competitions
> Unchanged: schedule, conference, opponents

- Primary CTA: **Apply and start franchise** · Secondary: **Back**

---

## 7. Copy deck

Verbatim. The replacement is communicated **three times, escalating in specificity** — the category-wide failure is announcing it once in a title and never again at the moment of consequence.

Tokens: `[replaced]`, `[user]`, `[conf]`.

### 7.1 At the entry point

> Put your own program in the league. Your school takes an existing team's place — the league stays at 128 teams and every schedule is unchanged.

### 7.2 At slot selection

> **[user] will replace [replaced].**
> You keep [replaced]'s spot in [conf], their schedule, and their rivalries. Your record starts fresh at 0–0.
> [replaced] won't appear in this franchise.

### 7.3 At the confirm

The one every competitor omits. The most important dialog in the feature.

> **Apply Team Builder changes?**
>
> **[user] replaces [replaced]** in [conf]. Schedule unchanged.
>
> This affects **this franchise only**. [replaced] is unchanged in your other saves and in any new franchise you start.
>
> **[Apply]** [Cancel]

*The line about editing later is deliberately omitted — v1 has no mid-franchise editing. Do not add it.*

### 7.4 Persistent orientation

> [user] · [conf] · *replacing [replaced] in this franchise*

### 7.5 Copy rules

Apply to any string this spec does not cover:

1. **Name what stays, not just what changes.** "Schedule unchanged" preempts a question users don't know to ask.
2. **Scope the blast radius explicitly.** Per-franchise isolation is the genuine advantage, and "my custom team disappeared in another save" is the category's most-searched confusion.
3. **Never use "delete," "remove," or "overwrite" for the slot.** "Replaces" and "takes the place of" are accurate and don't imply data destruction.

---

## 8. Roster import — validation UX

Reachable only from Step 3, choice 3.

### 8.1 Template acquisition

Two buttons **on the import screen, above the file input**:

- **Download blank template (CSV)** — headers plus 2 example rows, **optional columns visibly left blank.**
- **Download [replaced]'s current roster** — the slot's real data, pre-filled, same shape.

The second is strictly better for a replacement model: the user edits a file guaranteed valid and already the right size. The template is an export, not a static file we author and let go stale.

> ⚠️ **Do not populate every optional field in the blank template.** Users who see a fully-populated sample conclude every field is required and fabricate values to avoid "getting in trouble."

### 8.2 Required vs optional, before upload

> Required: `first_name`, `last_name`, `class_year` (FR, SO, JR, or SR)
> Optional: everything else — see the template
> Anything we don't recognize is ignored. Anything you leave blank, we generate.

**`position` is NOT required.** All players can play any position. Do not require it, validate it, or error on it.

### 8.3 Parse feedback

**Named progress, not a spinner**: `Validating roster… 14 of 15 rows.`

### 8.4 Column mapping

Auto-map on header name, visible override. Table: `Your column` | `First 3 rows` | `Maps to` | `Status`.

- Unmapped columns get a dropdown including **"Don't import this column."**
- No header row detected → offer a **"First row is headers"** toggle rather than erroring.
- Accept and normalize common aliases (`FR` / `Freshman` / `1`).

### 8.5 Parts picker

> **Use from this file:**
> ☑ Team identity (name, mascot, colors)
> ☑ Roster (15 players)

Delivers "identity without roster" without a second flow. Unchecking both equals cancelling.

### 8.6 Errors vs warnings — separated, never conflated

| Class | Behavior | Example |
|---|---|---|
| **Blocking error** | Cannot proceed | `No last_name column found. Your file needs first_name and last_name. [Download template]` |
| **Row error** | Row skipped, import proceeds | `Row 12 — class_year: "Freshmen" isn't a class year we recognize. Use FR, SO, JR, or SR. This row will be skipped.` |
| **Warning** | Nothing skipped, import proceeds | `Row 7 — height_in is blank. We'll generate a height.` |

**Every row-level message names four things: the row, the field, the offending value, and the fix.** Non-negotiable, and the single largest differentiator identified in the research. No message may read like `Line is invalid (No details)` or push detail to the browser console.

**JH and GR are not Team Builder concepts and get no special handling.** A user typing either gets the standard error above, which echoes their value and lists the four valid ones.

Warnings never block. Errors never fail silently.

### 8.7 Preview the change set before commit

> 14 players will be added to [user].
> 1 row will be skipped (see below).
> [replaced]'s current players won't be part of this franchise.
>
> **[Import 14 players]** [Cancel] [Download rows with errors]

The third line solves the "unclear overwrite of existing roster" anti-pattern by stating it. **It appears only on Generate and Import — never on Keep**, where it would be meaningless and alarming. There is no transfer pool; do not imply one.

### 8.8 Writing imported players

Imported players go through the same initialization as any other franchise player. **CH, EM and MO are always randomized** — they are excluded from the talent budget and set at season init. Import must never produce null or zero intangibles.

### 8.9 Empty and error states

| State | Copy |
|---|---|
| **Empty** | Two template buttons, the required/optional list, one line of "or skip this — we'll generate a roster." |
| **Wrong file type** | `That's a .xlsx file. Save it as CSV (File → Save As → CSV) and try again.` |
| **Empty file** | `That file has headers but no player rows. Add at least one player, or skip roster import.` |
| **Too many rows** | `That file has [n] players. A roster holds 15. Trim the file, or import the first 15.` — second option as an actual button. |
| **Parse failure** | `We couldn't read that file — it may not be a valid CSV. [Download our template] and paste your data into it.` |

Never `An error occurred.` Never `Invalid file.`

---

## 9. Attribute budget and online eligibility

A user-authored roster can trivially out-class every CPU program. The budget system keeps custom franchises comparable to the base league without blocking users who don't care.

**The pattern is Basketball GM's God Mode:** an opt-in state with a legible, proportionate, **non-destructive** price. Basketball GM charges achievements. We charge online-competition eligibility. The user is never blocked and never loses work.

### 9.1 Four conditions

| Condition | Applies to | Purpose |
|---|---|---|
| **Team total** | All 15 players | Overall talent ceiling. Controls depth. |
| **Top-5 sum** | Best 5 by core-12 | **Controls concentration — the thing that decides games.** |
| **Per-player ceiling** | Any single player | No player beyond what already exists. |
| **Per-player floor** | Top 12 by talent | Sanity guard against null/zero players. |

**Why a top-5 cap and not just a bigger floor.** A total-points budget structurally cannot control concentration: CPU teams hold ~57% of their talent in the top five, a min-maxing user reaches ~75%. Under the v1.1 values a stacked roster hit a top-5 of 4,788 against a league max of 3,954 — 21% above the best team in the league, while passing every check. The floor was an indirect proxy. Cap the thing that matters directly.

**Why the floor collapsed to a guard.** At 220 it was stricter than 95 of 128 real teams. A user importing a realistic roster with a normal walk-on would be told they're ineligible for doing what three-quarters of the league already does. Anti-stacking moved to the top-5 cap; the floor now exists only to prevent degenerate players.

**Why the floor applies to the top 12, not all 15.** Walk-ons are legitimately weak. Rank by core-12 sum; the top 12 clear the floor, the bottom 3 are unconstrained. No scholarship flag needed on imported data.

### 9.2 Values

**Governing principle: no custom program may exceed what already exists in the league on any measured dimension.**

| Limit | Value | Anchor |
|---|---|---|
| **Team total** | **6,400** | P90 of per-team totals (~6,369) — *deliberately not league max* |
| **Top-5 sum** | **3,950** | League max top-5 (3,954) |
| **Per-player ceiling** | **1,035** | League max player (1,034) + 1 for integer edges |
| **Per-player floor** | **24** | League min player (24). Zero teams violate it. |

**Why team total stays at P90 while everything else sits at league max.** This asymmetry is the design, not an oversight. It creates a trade instead of an optimum:

- *Star build* — top five at 3,950, leaving 2,450 across ten players (~245 each, meaningfully thinner than a P90 CPU team's ~390)
- *Depth build* — top five around 3,000, a genuinely deep rotation

Both viable, neither dominant. Raise the total to league max and every serious player converges on the same roster.

Measure against the same core-12 sum used for prestige. **Count all 15 players against the team total** — an evenly spread 15-player roster is starless and self-punishing given RT is the max of five position ratings.

Define all four values in **one place**, easy to tune. Expect them to change after playtesting.

### 9.3 Enforcement — soft, always

**The user is never blocked.** Failing any condition marks the franchise **ineligible for online competitions** and nothing else.

**The meter, visible throughout Step 3:**

- **Two bars** — team total and top-5 — each with **league context markers**. A number like 3,950 is arbitrary alone and instantly meaningful next to the league it came from:
  - Team total: *median program 5,567 · best program 7,027*
  - Top five: *median program 3,148 · best program 3,954*
- **Two pass/fail lines** — ceiling and floor.
- **One eligibility badge** summarizing. Details expand on demand; the badge is what matters.

Rules:

- Failing a condition changes eligibility and surfaces a plain-language explanation. It does not disable Next, throw an error, or roll back an import.
- An over-limit CSV import **still imports**. Report it as a warning, not a row error — no rows are skipped for budget reasons.
- Eligibility appears in the Step 4 summary, on the franchise command centre for custom programs, and persists as a visible franchise property.
- **Generate mode must label its figures as estimated** — band resampling means they are not final until Apply. A meter that reads as measured when it is estimated is a quiet honesty gap.

Copy:

> **Over budget by 180 points.** This franchise won't be eligible for online competitions. Everything else works normally — you can keep playing, and you can trim attributes now if you want to stay eligible.

> **Your top five is 240 over the cap.** The best starting five in the league totals 3,954. This franchise won't be eligible for online competitions; everything else works normally.

### 9.4 Eligibility evaluates live in the wizard, then freezes at Apply

**During the wizard**, eligibility recomputes continuously from the roster being built. A user who fails a condition and fixes it is eligible again. This differs deliberately from God Mode's permanent forfeiture: unlike a hidden cheat, the roster values *are* the state — there is nothing concealed to punish.

**At Apply, eligibility freezes. It is never recomputed for the life of the franchise.**

This is deliberate and is the more important half of the rule. **The budget constrains authored input, not simulated outcomes.** Rosters drift constantly through normal play — camp cuts, development, week-35 releases, graduations — and a program that *develops* into a powerhouse over three seasons has done nothing the budget exists to prevent. Recomputing over the franchise lifetime would make eligibility a function of the sim rather than of what the user chose to build, and would strip eligibility from players who did nothing wrong.

> An earlier version of this section said only "eligibility recomputes from the current roster," which read as season-long recomputation and was reported as an implementation failure during verification. It was a spec ambiguity, not a bug. Set-once at Apply is correct.

**Also persist, set once on Apply and never cleared:**

- `hasEverExceededBudget` — boolean
- `roster_shape_at_creation` — **team total, top-5 total, max single player**

Unread in v1. Persisted because there is a real future exploit — build over-cap, play a season, bank the advantage, trim to eligible — and the only way to close it later is to have recorded history from the beginning. Basketball GM's `godModeInPast` is exactly this pattern. Retrofitting after users have built franchises is impossible.

> This will look like dead code in review. It is not. Do not remove it.

### 9.5 Online competitions do not exist yet

**The eligibility flag is forward-looking metadata.** Persist it and surface it. **Build no gating logic, no online-mode checks, no matchmaking integration.** Do not scaffold an online mode or add navigation to anything that does not exist.

---

## 10. v1 scope boundaries

### Cut from v1

| Cut | Why it's safe | What prevents it feeling missing |
|---|---|---|
| **Custom logo upload** | No browser basketball sim has it; generated art is proven acceptable | §3.3 generated placeholders, non-optional |
| **Custom court art** | 2K's own court editor can only scale images | Court generated from team colors |
| **Replacing more than one program** | EA caps at 16 of 138 and users still hit it; one is a complete story | Frame v1 as **"your program"** — a scope, not a limit |
| **Sharing / community browser** | Permanent moderation, hosting and server-sunset liability | Nothing. Users don't miss what was never implied. |
| **Conference realignment / league resizing** | Structurally incompatible; 2K refuses it outright and EA's attempt broke schedules | Never mention it as a limit |
| **Editing CPU AI tendencies** | No competitor bundles this into team-create | Out of frame entirely |
| **Uniform designer** | EA's 625 combinations are a AAA investment | 5 jersey presets × 3 colors reads as a designer to a first-time user |
| **Mid-franchise editing** | Explicit product decision — and structurally load-bearing, since write-time resolution depends on the overlay existing before any news or game docs | Do not hint at it in the UI |
| **Undo of an applied change** | Identity-only overlay is reversible; Generate/Import is not, since season init clones core players and randomizes intangibles | The change-set preview and confirm dialog prevent rather than reverse |
| **Core-8 marketing taglines** | Data existed only for the original 8, hard-coded, none for the other 120 | Restoring them Core-8-only would create a visible two-tier league exactly when the product says all 128 are real programs |

**No dead UI, disabled buttons, "coming soon" labels, or unreachable routes for any cut item.**

---

## 11. Acceptance criteria

### Task A

1. All 128 programs selectable from team-select, with working search, conference grouping, and filtering.
2. Existing select-team behavior preserved end to end — same create path, same franchise flow, tutorial path intact.
3. Layout and performance hold at 128 entries with art. Card art follows the §3.1 WebP convention; first-viewport transfer is ~1 MB, not ~10 MB.
4. The picker is a reusable component consumed by Team Builder Step 0 without duplication.
5. Selection keys on `object_id`, never on name.

### Task B — resolver and art

6. A custom program's name, short name, abbreviation, mascot and colors render correctly on **every** surface in the §3.2 enumeration. No surface shows the replaced program's identity.
7. The resolver is a verified no-op for franchises without an overlay — existing franchises render byte-identically.
8. No broken-image state anywhere in the app for a custom program.

### Task B — flow

9. Team Builder is reachable from team-select, and nowhere else.
10. A user can complete the flow with only a name and colors, in under two minutes, without encountering a file input.
11. Cancelling at any step returns to team-select with `home_slot` preserved and no lost state.
12. Franchise creation does not begin until Apply.
13. Each of the 5 steps has a working primary CTA and back path.

### Task B — replacement

14. Applying replaces exactly one slot, leaves league size at 128 and conference count at 16, and leaves the fixture graph unchanged.
15. Scoped to one franchise. Core `teams` and core players unmutated — verified against another save and a newly created franchise.
16. The three replacement copy moments (§7.1, §7.2, §7.3) appear with the specified strings.

### Task B — import

17. Both template downloads work and produce files that import cleanly without modification.
18. `position` is not required; a file lacking it imports without error.
19. FR/SO/JR/SR import; any other value is skipped with the standard §8.6 error. JH and GR appear nowhere in the UI.
20. Every row-level error names row, field, value, and fix.
21. A file mixing valid and invalid rows imports the valid ones and offers a round-trippable download of the skipped ones.
22. All five empty/error states in §8.9 implemented with the specified copy.
23. The parts picker allows importing identity without roster.
24. Imported players have CH, EM and MO randomized.

### Task B — budget

25. The meter — two bars with league markers, two pass/fail lines, one badge — is visible throughout Step 3 and reflects the current roster.
26. All four conditions evaluate, including top-5.
27. Failing any condition never blocks the user, never skips rows, and never rolls back an import.
28. Eligibility recomputes live; `hasEverExceededBudget` and `roster_shape_at_creation` are persisted and never cleared.
29. No online-mode logic, navigation, or scaffolding anywhere in the diff.

### Task B — assets

32. Generated art resolves correctly with client storage cleared: the visual hydrates from the franchise payload before first paint.
33. An unknown slug returns generic art, never a path that 404s.
34. Eligibility surfaces on the franchise command centre for custom programs.

### Hygiene

30. No dead UI, disabled controls, or "coming soon" affordances for any §10 cut item.
31. The diff conforms to existing repo patterns and introduces no new frameworks or state-management approaches without flagging them.

---

## 12. Decision log

| # | Decision | Rationale | Since |
|---|---|---|---|
| 1 | Feature is named "Team Builder" | 17 years of category vocabulary; arrives pre-explained. *Trademark check pending — not for marketing surfaces yet.* | v1.0 |
| 2 | Single entry point, new franchise only | Deliberate scope reduction — and structurally load-bearing (see #23) | v1.0 |
| 3 | Replacement, never addition | Fixed league structure; also the industry-standard model | v1.0 |
| 4 | Per-franchise overlay; core data never mutated | Existing architecture decision | v1.0 |
| 5 | `position` is not a required import field | All players can play any position | v1.0 |
| 6 | Soft enforcement — warn and flag, never block | God Mode pattern: legible price, no blocked path, no lost work | v1.0 |
| 7 | Eligibility recomputes live | Roster values are the state; nothing is concealed | v1.0 |
| 8 | `hasEverExceededBudget` persisted but unused | The only way to close a future exploit is to have recorded history from day one | v1.0 |
| 9 | Online eligibility is metadata only | No online mode exists yet | v1.0 |
| 10 | Logo upload cut from v1 | No browser basketball sim has it; generated placeholders are proven acceptable | v1.0 |
| 11 | Task A (128 picker) ships before Task B | Smaller reviewable diffs; independently valuable | v1.1 |
| 12 | One reusable picker serves team-select and Step 0 | Two pickers plus a refactor is a failure mode | v1.1 |
| 13 | Display resolver and generated art are non-optional, built first | Without them the central promise is false and custom teams render broken | v1.1 |
| 14 | Team total counts all 15 players | An evenly spread roster is starless and self-punishing given RT = max of position ratings | v1.1 |
| 15 | Import accepts FR/SO/JR/SR only; JH and GR are not Team Builder concepts | JH is recruits only; GR is earned in-game | v1.1 |
| 16 | No transfer pool in copy | It does not exist | v1.1 |
| 17 | Abbreviation uniqueness via `slice(0,3)` of all 128 names | No league-wide abbreviation field exists | v1.1 |
| 18 | **Resolver intercepts at shared producers, not 58 call sites** | Same coverage, a tenth of the diff, and future screens inherit resolution automatically. Made safe by the mandatory no-op property. | v1.2 |
| 19 | **Top-5 cap added as a fourth condition at 3,950** | A total-points budget structurally cannot control concentration; the stacked build reached 4,788 against a league max of 3,954 | v1.2 |
| 20 | **Floor cut to 24** | At 220 it was stricter than 95 of 128 real teams — a day-one legitimacy failure | v1.2 |
| 21 | **Team total stays at P90 while other limits sit at league max** | Deliberate asymmetry: produces a star-vs-depth trade instead of one optimal roster | v1.2 |
| 22 | **Core-8 taglines stay off** | Data existed only for 8; restoring them creates a two-tier league exactly when the product says all 128 are real | v1.2 |
| 23 | **`GET /teams` emits `object_id`, not `id`** | Ambiguity against the `team_id` slug produces silent no-match rather than errors | v1.2 |
| 24 | **Card art is 400 px WebP; full banners for detail only** | 10.4 MB in the first viewport was too heavy; generated art follows the same convention | v1.2 |
| 25 | **Eligibility evaluates live in the wizard, then freezes at Apply — never recomputed over the franchise lifetime** | The budget constrains authored input, not simulated outcomes. Rosters drift through normal play; a program that develops into a powerhouse has done nothing the budget exists to prevent. | v1.2.1 |
| 26 | **Asset resolution intercepts inside `getTeamAssetPath`; the server payload is the source of truth and client storage is a cache only** | Reading the overlay from client storage alone reintroduced broken images in any fresh client. One franchise-aware function corrected 37 call sites. | v1.3 |
| 27 | **Terminal asset fallback is generic, never a 404 path** | Defense in depth: total failure of overlay resolution degrades to plain rather than broken | v1.3 |
| 28 | **MO = 0 at init is league-wide, not import-specific** | Verified identical for imported and core-cloned players. Recorded so it is never mistaken for an import defect. | v1.3 |

---

## 13. Background

This spec derives from a competitive UX study of Out of the Park Baseball, Franchise Hockey Manager, Football Manager, NBA 2K MyNBA, EA College Football TeamBuilder, legacy NCAA TeamBuilder, College Hoops 2K8, Basketball GM/ZenGM, Draft Day Sports, and Eastside Hockey Manager, plus import-UX patterns from Stripe, HubSpot, Airtable, Flatfile, NN/g and Baymard.

The three findings most worth knowing:

- **Replacement is the industry-standard model.** EA has shipped it across eight titles since 2009. Football Manager: *"you will replace an existing club with a fictional team that you will create."* We are not doing something unusual.
- **Every shipped product under-communicates the swap.** EA's own help documentation contains no warning copy, no confirmation text, and no undo guidance for the single most destructive action in the feature. §7 is where we beat the category, and it costs nothing but care.
- **The dominant failure mode across every product is silent failure.** Football Manager says `Couldn't load the database` with no filename. Basketball GM pushes error detail to the browser console. Shopify says `Line is invalid (No details)`. §8.6 exists because of this.
