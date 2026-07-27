# Competitive UX Research — Custom Teams & League Modding in Sports Sims

**For:** Geeked-Out Basketball (browser basketball franchise sim, fixed 128-team / 16-conference league)
**Topic:** How best-in-class franchise sims let players add or customize teams with their own data
**Date:** 27 July 2026
**Scope:** UX and product patterns only. No backend design, no schemas.

**How to read this memo.** Sections 2–5 are *observed competitor behavior* — what these products actually do, with sources. Sections 6–7 are *our recommendation* — clearly separated, and none of it depends on changing the slot-replace model. Uncertainty is flagged inline as `[unverified]`, `[version-dependent]`, or `[inferred]`. A full confidence appendix is at the end.

**Products studied:** Out of the Park Baseball 24–27 · Franchise Hockey Manager 10–12 · Football Manager 24 & 26 · NBA 2K MyNBA (2K21–2K26) · EA College Football 25/26/27 TeamBuilder · legacy NCAA Football TeamBuilder (2009–2013) · College Hoops 2K8 · **Basketball GM / ZenGM** · Draft Day Sports · Eastside Hockey Manager · Pennant Chase · plus general CSV/JSON import UX from Stripe, HubSpot, Airtable, Mailchimp, Flatfile, OneSchema, NN/g and Baymard.

---

## 1. Executive summary

- **Replace-a-slot is the industry-standard model, not a compromise.** EA TeamBuilder (2009→2027, five NCAA titles and three CFB titles) and Football Manager's Create-a-Club both replace an existing program rather than expanding the league. FM's framing is the sharpest: *"This is a game mode in which you will replace an existing club with a fictional team that you will create."* Our architecture brief has independently landed on the same answer the two biggest studios in the category reached. **We should present it as a feature, not apologize for it.**

- **The replacement target is the single high-consequence decision — and every shipped product under-communicates it.** In FM, *"the facilities (also stadium capacity), reputation and finances will be inherited from the club you replace"* — and European places are listed as non-editable. In CFB you inherit rivalries, staff, My School grades and team records. EA's help documentation contains **no warning copy, no confirmation text, and no undo guidance** for the replace step. This is the single largest open lane in the category.

- **Nobody in browser basketball has shipped this.** Basketball GM is the only browser basketball sim with meaningful custom-team support, and it has no logo upload — only a `Logo URL` text field. Pennant Chase's custom leagues were still "coming soon to basketball" `[unverified — behind login]`. A polished browser create-a-team flow is genuinely unoccupied territory.

- **Cosmetics-only is the job that matters most, by a wide margin.** Every product that ships a create-a-team flow leads with identity: name, colors, logo, uniforms. EA CFB gives users **625 uniform combinations** and a stadium editor before it gives them a single roster tool. Roster import is a power-user job with a much smaller audience and vastly higher failure surface. **Recommend shipping identity first and roster import as an explicitly optional step.**

- **The best "template" is the user's own export, not a static file we author.** Basketball GM: *"You can create a league file by going to Tools > Export within a league."* HubSpot generalizes this with a **"Use as template"** button on any past successful import. Round-tripped templates are always schema-current and self-documenting; static templates go stale the first time we add a field.

- **Basketball GM's League Part Picker is the best import idea in the category and almost nobody has copied it.** After a file parses, a checkbox list appears — **"Use from selected league:"** with All/None shortcuts — letting users take *only* the teams, or only the players, from a file. It converts import from an all-or-nothing act into à-la-carte trust. This is directly applicable to our "identity without roster" partial-import requirement.

- **"God Mode" is the best-designed scope boundary in any of these products.** Basketball GM gates all destructive customization behind an opt-in flag that (a) colors every gated control purple so the mode is legible anywhere, (b) shows locked features *visible-but-disabled* with a "Show God Mode Settings" peek, and (c) charges a legible, proportionate, **non-destructive** price: permanent achievement forfeiture, tracked by a sticky flag that survives turning it back off.

- **Placeholder art is table stakes; a missing-asset empty state is a launch bug.** OOTP: *"If still no match is found, OOTP will create a basic fictional logo"* — no team is ever logo-less. EA CFB25 shipped with **zero generic stadiums**, forcing custom teams to play in rivals' branded venues; it remains one of the loudest complaints in the category. **The uncustomized path must look plain, never broken.**

- **The dominant anti-pattern across every product is silent failure.** FM: *"Couldn't load the database"* with no filename, remedy is manual bisection. FHM: team names with diacritics silently break logo matching with no diagnostic. Basketball GM: *"More detail is available in the JavaScript console."* Shopify: `"Line is invalid (No details)"`. **Naming the row, the field, the value and the fix would put us ahead of every product in this survey.**

- **Do not ship sharing, conference realignment, or league resizing in v1.** EA's conference realignment produced 17-team conferences with 6-game schedules and no upfront validator; EA's fix was to silently *delete* impossible configurations from the matrix. 2K locks conferences and divisions entirely. Every product that shipped sharing early now carries permanent moderation, hosting and server-sunset liability.

---

## 2. Competitor matrix

| Product | Entry point | Create vs. replace | Roster import | Visual assets | Mid-save edit | Sharing |
|---|---|---|---|---|---|---|
| **EA CFB 25/26/27** (TeamBuilder) | **Separate desktop-browser web app** (`ea.com/games/ea-sports-college-football/team-builder/landing`), decoupled from and released *after* the game | **Replace only.** *"choose which existing team you want your Team Builder team to replace"* — max 16 per Dynasty (32 creatable) | Optional. Binary choice at import: replace the school's roster, **or only change uniforms and field** | Custom logo upload, **5 MB total budget per team** (was 10 images × 512 KB in CFB25); recolorable generic logos; only 3 generic stadiums | Import at league creation and **at the end of each season** (CFB26+); commissioner-only, cloud Dynasty only | In-game **Create and Share → Download Center → Schools**; search by name or username; preview before download |
| **Football Manager 24** (Create-a-Club) | New Game dropdown → **"Create a club" Mode**, inside career setup | **Replace only.** *"you will replace an existing club with a fictional team that you will create."* B-teams excluded as targets | Full squad control: Add player / Create player / Load Created Player / **Auto-Fill Squad** / Clear Squad | 14 preset logos **or** custom `.png` with transparent background; kit colors, patterns, shorts, socks | ❌ Pre-career only. **No mid-save club creation exists in FM at all** | Steam Workshop (~6,237 items FM26) + sortitoutsi + FM Scout — three uncoordinated channels |
| **Football Manager 26** | Pre-Game Editor (free, **separate desktop app**) + In-Game Editor (paid DLC, $8.99) | **Create-a-Club removed in FM26**; PGE can add clubs but community norm is still "swap safely" | `.fmf`/`.xml` files dropped in an `editor data` folder; tick-box list of detected files at setup | No licensed badges shipped; `graphics/` + `config.xml` mapping filenames to internal IDs; PNG only, 180×180 (256×256 modern) | IGE edits *values* mid-save; PGE edits *structure* pre-save. Neither does the other's job | Workshop items **don't reliably reach the folder the game reads from**; no in-app browser |
| **OOTP 24–27** | Start Screen → **"New Custom Game"** → League Creation Wizard (6 steps) → **"Advanced Mode"** escape hatch. Uniquely, **"Add League" reopens the wizard mid-save** | All three: add, replace (Import Hist. Team), and a full **League Expansion Wizard** (2–10 teams, 0–60 protection slider, drag-to-protect) | **Export Rosters → hand-edit → Import Rosters.** No template ships. *"Never import roster files that are not based on an OOTP export file from the SAME league!"* | Optional always; **auto-generates a fictional logo on match failure.** PNG/JPG 150×150, filename-matched, with **team colors encoded in the filename** | Name/nickname/abbrev editable **any time incl. mid-season**; structure offseason/preseason only | No Steam Workshop; Add-Ons/Workshop Central + 8 dedicated mod sub-forums (9,045 logo threads) |
| **FHM 10–12** | Start Screen → "New Custom Game" (unbranded, undocumented wizard) | Bulk **replace** at setup — import entire real/historical leagues 1909→present into existing slots | ❌ **Export only.** Dev, verbatim: *"Sorry, you can't do what you want to do in FHM."* Custom teams can't even be saved: *"Nope. Has to be done manually each time."* | PNG into a folder; generates generic logos on failure; **era-keyed filenames** (`boston_bruins_1948-1948.png`) — best historical idea in the survey | **Structural edits gated to July 1 only.** Cross-league moves: "No." | Steam Workshop + in-app "Steamworks" installer — **but only 6 items exist**, and it installs to new games only |
| **NBA 2K MyNBA** (2K21–2K26) | Pre-league wizard (Current NBA Teams / League Expansion / Custom League) `[version-dependent — labels from a 2K24 source]`, **or** in-league `Front Office → Relocate Team` (US map with city pins) | **Genuinely adds.** League range **12–36 teams**; 2K25+ allows ±6 teams *every offseason* | 2K Share: rosters, draft classes, team designs. Rosters **do not travel with** team designs | Jersey editor supports grow/shrink/rotate/move on decals; **court editor only scales, can't customize images**. `[inferred, medium-high]` **no image upload** — preset compositor only | Relocate + full rebrand anytime; add/remove teams each offseason. **Conferences and divisions are not editable, ever** | 2K Share, browsable in-app: "hot" / "new" / "my files", search by name or gamertag, download counts |
| **Basketball GM / ZenGM** (closest analog) | New league → **"Customize"** dropdown → **"Upload league file"** / **"Enter league file URL"**; in-league **Tools → Manage Teams** | All three: Manage Teams add/remove (God Mode, phase-gated), Expansion Draft, and relocation via a **"Move"** modal | Published **JSON Schema**, a documented minimal example, and a deliberately-broken fixture file to test your error path. **League Part Picker** for partial import | **`Logo URL` + `Small Logo` text inputs. No upload anywhere in the app.** Live jersey + face preview in team colors | Manage Teams anytime; add/remove teams phase-gated with in-line consequence copy | ❌ No first-party gallery. Reddit + **GitHub raw URLs**, enabled by the "Enter league file URL" option. Zero user content stored |
| **Legacy NCAA TeamBuilder** (2009–13) | `teambuilder.easports.com`, live **6 weeks before the game** | **Replace only.** Inherited the replaced school's records + primary rival; W-L started clean | Roster editing on the web app | **Logo upload was more permissive than today's** (~256×256 primary / 128×128 secondary); post-hoc flagging, not pre-approval moderation | Import at Dynasty creation | Best sharing in the survey: filter by name/city/state/school type/author; **sort by downloads, recency, alphabetical**; private-team toggle |
| **College Hoops 2K8** | On-console **"Creation Zone"** | Create-a-team, **max 2 inserted into a legacy** | ❌ | Fixed stock logo library, **no upload, couldn't even change jersey colors** | ❌ Conference realignment was a **one-time setup gate** — *"you have to turn custom conferences on at the start"* | ❌ |

---

## 3. Findings A–G (observed behavior)

### A. Player jobs — what are people actually trying to finish?

Four jobs, and the evidence separates them cleanly by audience size:

1. **Cosmetics / identity.** Every product leads here. EA CFB's five-tab flow puts **Brand** first and **Roster** last; it offers 625 uniform combinations, a stadium editor with 8 components, and 7 custom helmet layers before it offers a single roster tool. College Hoops 2K8 shipped identity-only and was still used. This is the job with the biggest audience and the smallest failure surface.
2. **Full roster import.** Real, but power-user. OOTP explicitly scopes its import functions as *"mainly helpful to players with more technical experience."* Basketball GM's roster ecosystem runs on hand-authored JSON hosted on GitHub. FHM has no import at all and still sells.
3. **Rebuild the league map.** Smallest audience, largest blast radius. 2K refuses outright (conferences and divisions locked). EA shipped it and immediately hit mathematically-impossible schedules; their remedy was to delete configurations from the matrix rather than explain them.
4. **Share mods.** Genuinely large demand — OOTP's logo sub-forum alone has 9,045 threads; legacy NCAA TeamBuilder's FCS directory thread hit 832,000 views. But it is a *second-order* job: nobody shares before they can create, and it drags in moderation, hosting, and permanent server liability.

**Ranked for a browser basketball sim launching custom teams for the first time:**

| Rank | Job | Rationale |
|---|---|---|
| **1** | Cosmetics / identity (name, mascot, colors, logo) | Largest audience, lowest risk, fastest to a satisfying result, works with generic assets |
| **2** | Roster import — *your own program only* | The emotional core for our likely audience (a user putting their own school in), but strictly opt-in |
| **3** | Replace CPU programs (multiple slots) | Natural v1.1 extension; EA's 16-team cap shows the appetite is real |
| **4** | Share with others | v1.2+ at the earliest. Heavy ongoing cost, and every product that shipped it early regrets some part of it |
| **5** | Rebuild the league map | Explicitly out of scope. Incompatible with a fixed 128/16 structure anyway |

### B. Mental models & naming

Observed vocabulary, and how well each survives a fixed league size:

| Framing | Who uses it | Works with fixed size? |
|---|---|---|
| **"Team Builder"** | EA CFB / NCAA, 2009–2027 | ✅ Names the *act of building*, silent on league arithmetic. Most durable name in the category |
| **"Create a Club"** | Football Manager | ⚠️ Says "create," means "replace." FM has to correct it in prose immediately |
| **"League Editor" / "Manage Teams"** | OOTP, Basketball GM | ✅ Accurate, but reads as admin tooling, not as *my team* |
| **"Custom Database" / `editor data`** | Football Manager | ❌ A folder name leaking into product vocabulary. Directly implicated in the most common FM support question |
| **"Relocate Team"** | NBA 2K | ✅ Excellent when the mental model really is "this franchise moved," which for us it isn't |
| **"Expansion"** | OOTP, 2K | ❌ Actively wrong for us — it promises the league gets bigger |

**What actually reduces confusion:** every product that gets this right does it with a **noun that names the outcome plus a sentence that names the trade**, not with a cleverer feature name. EA's help text does the work: *"choose which existing team you want your Team Builder team to replace."* FM's guide does the work: *"This is a game mode in which you will replace an existing club with a fictional team that you will create."*

`[observed]` The failures cluster on framings that promise growth ("Add," "Expansion," "Create") without an adjacent sentence about what is given up. The successes pair a neutral build verb with an explicit, early, plain-language statement of the swap.

### C. Entry points & timing

**Three entry-point models exist:**

| Model | Examples | Trade-off |
|---|---|---|
| **Separate web app, syncs into the game** | EA TeamBuilder (2009→now) | Rich editing UI; but a WYSIWYG break at the boundary — logos correct on the website, *"very small and duplicated"* in-game. Also desktop-browser-only, and the site ships *after* the game |
| **Inside new-career setup** | FM Create-a-Club, OOTP wizard, Basketball GM's Customize dropdown | Highest discoverability, zero sync risk. But the edit is trapped in a flow the user only visits once |
| **Mid-save via an editor/admin surface** | OOTP editors, Basketball GM Manage Teams, 2K Front Office, FM's paid IGE | Most flexible; hardest to find. FM's paid editor is reached by right-clicking a table row or spotting a pencil glyph — its top complaint is discoverability |

**When edits lock:**

- **OOTP:** name, nickname, abbreviation, nation editable **any time, including mid-season**; league *structure* only in offseason/preseason. This split — cosmetic always, structural never mid-season — is the most sensible rule in the survey.
- **EA CFB:** CFB25 was creation-only; CFB26+ added *"At the end of each season, you'll have the option to update your program by importing new teams."*
- **FHM:** structural edits on **July 1 only**.
- **Basketball GM:** *"You can only add or remove teams during the preseason, after draft, re-signing, or free agency game phases."*
- **FM:** hard split — structure pre-career only, values mid-save only.

**Warnings for destructive changes — the actual observed inventory:**

OOTP is the only product with a real warning vocabulary, and it's all verbal, never blocking:
- *"Editing your league structure is a drastic step! Always, always, always be sure to back up your game before editing the league structure!"*
- *"Delete this league … This action cannot be reversed."*
- *"WARNING: It is not possible to undo the deletion of the alternate uniforms."*

Basketball GM's is better because it states the *simulation consequence* rather than shouting:
- *"When a team is disabled, all its players become free agents. Because of this, the best time to disable a team is right after the playoffs finish."*

**And the striking negative finding: EA's TeamBuilder import — the single most destructive action in the category — has no warning copy, no confirmation text, and no undo guidance in any documentation I could find.** `[verified absence; EA Help is silent]` Neither does NBA 2K for any MyNBA structural change. `[unverified — I found only error dialogs, never pre-action warnings]`

### D. Information architecture of the editor

**The converged step order**, across EA CFB, FM Create-a-Club, and general SaaS import flows:

| Step | EA CFB tab | FM 24 tab |
|---|---|---|
| 1. Choose what to edit | (start from existing team or scratch) | Club selection screen |
| 2. Identity | **Brand** — name, nickname, city/state, colors, mascot | **Information** |
| 3. Visuals | **Uniforms**, **Stadium** | **Logo**, **Kits** |
| 4. Context / sim properties | **Program** — playbooks, identity template, grades, pipelines, rivalries | **Facilities & Finances**, **Staff Roles** |
| 5. Roster | **Roster** — 7 archetypes + per-player editing | Squad selection screen |
| 6. Commit | Save → Submit → in-game import → pick replacement | Manager style → Confirm |

**Progressive-disclosure patterns actually observed:**

- **Preset-then-refine.** EA offers 5 helmet/jersey/pant/sock presets (625 combinations) *before* exposing the advanced layer editor. FM offers **14 preset logos** before the custom-PNG path. Basketball GM offers 5 named jersey styles. Presets mean a first-time user is never facing a blank canvas.
- **Escape hatches, not forks.** OOTP's *"at any time you can drop into Advanced Mode"* is the right instinct executed badly — there's no middle tier, so wanting two Triple-A leagues ejects you from a 5-step wizard into a 10-tab editor that makes you compute `(parent teams × draft rounds) ÷ 6`. Basketball GM's three-tier ladder (normal → God Mode → Danger Zone) is the better model.
- **Visible-but-disabled beats hidden.** Basketball GM shows God-Mode-gated settings greyed with a tooltip — *"This setting can only be changed in God Mode"* — plus a **"Show God Mode Settings"** toggle to browse before committing. Users can see the ceiling without hitting it.
- **Live preview as the trust mechanism.** Basketball GM's color pickers render a `facesjs` avatar in the team's colors and jersey style, updating live. Colors are abstract as hex and concrete as a rendered uniform.
- **Sensible defaults with escape valves.** FM's **"Auto-Fill Squad"**; EA's 7 generic roster archetypes and school identity templates (Powerhouse, Pro Factory) that seed grades. Nobody is required to fill everything in.
- **Steering users toward the safer path, in-line.** Basketball GM's Add Team panel literally argues against itself: *"An expansion draft is generally a better way to add a team."*

### E. Import / data UX — the critical section

**Template download.** The strongest observed pattern is **the template is the user's own export**:
- Basketball GM: *"You can create a league file by going to Tools > Export within a league, or by creating a custom league file."* Export presets include a **"Teams Only"** option whose description is literally *"Select only this if you want to create a new league with the same teams as this league, but without anything else copied over."*
- OOTP enforces it: the export self-documents (*"includes the list of all the fields used in the file, as well as the numeric team IDs"*), and hand-authoring from scratch is explicitly forbidden.
- HubSpot generalizes it: a **"Use as template"** button on any past successful import copies its settings and property mappings.
- Counter-position, worth weighing: **Flatfile argues templates are a cop-out** — *"this shifts burden to users rather than solving the underlying problem"* — and that a good mapping UI removes the need. Both can be true: ship the template *and* the mapping.

**Validation errors.** The category is bad at this, which is our opening.

| Product | What the user sees | Grade |
|---|---|---|
| OOTP | `error 999 // checksum incorrect` — a numeric code you look up in the manual. For roster CSV import, **no validation documented at all** | ✗ |
| FM | *"Couldn't load the database"* — no filename. Remedy is **user-performed bisection** | ✗ |
| Shopify | `"Line is invalid (No details)"` | ✗ (the canonical worst) |
| Basketball GM | Blocking errors separated from non-blocking warnings; *"You can still use this file, but these errors may cause bugs"* — but detail is pushed to devtools: *"More detail is available in the JavaScript console"* | ~ (right instinct, wrong surface) |
| HubSpot | Errors in the mapping screen, an **"Import errors"** table with `Error type` and **`Error impact`** as first-class columns, and **"Download rows with errors as file"** | ✓ (best in survey) |

Baymard's finding is the one to internalize: **98% of e-commerce sites use generic error messages; only 2% adapt per rule** — and the fix is not hard, because *"the back-end logic already knows the specific error."* Their rewrite pairs: "Invalid email" → **"This email address is missing the @ character."**

**Partial import.** Basketball GM's **League Part Picker** is the standout: after a file parses, a checkbox list headed **"Use from selected league:"** with All/None shortcuts and human-readable labels (`teams` → "Teams", `players` → "Players, including ratings and stats"), closing with *"Warning: selecting a weird combination of things may result in a partially or completely broken league."* Crucially, the *same taxonomy* appears on the export side — symmetric round-trip. EA does a cruder two-state version at import: replace the roster, **or only change uniforms and field**.

**Column mapping.** Nobody in games does this. HubSpot's mapping table columns are the reference implementation: `Column header from file` | `Preview Information` (first three rows) | `Mapped` | `Import as` | `Property`, with **"Don't import column"** in the dropdown and a global **"Don't import data in unmapped columns"** checkbox. Airtable's **"First row of CSV file is headers"** toggle degrades gracefully — unchecked, columns become "Column, 1, 2, 3" rather than erroring.

**Sample files.** Two patterns worth stealing outright:
- Basketball GM ships a **deliberately broken fixture** — *"try loading this file"*, "should show 2 errors" — so users can confirm their error path works.
- Basketball GM's minimal example shows **only the required fields**, with the note *"The only required ones are shown below. Any other fields you see in an exported or custom roster file are purely optional."* This matters because of Baymard's defensive-over-filling finding: users who hit a validation error start entering "N/A" in optional fields to avoid *"getting in trouble."* **A sample file with every field populated teaches users that every field is required.**

**What makes imports feel trustworthy vs. terrifying** — synthesized from the evidence:

| Trustworthy | Terrifying |
|---|---|
| Named progress with a phase label (*"Validating players..."*) — Basketball GM uses a real progress bar, not a spinner | A spinner, then a wall of text |
| Preview the **change set**, not the data. Airtable shows *"the number of records that will be updated, the number that won't change, and the number of new records"* | Raw row dumps |
| Errors vs. warnings separated; warnings never block | Everything blocks, or nothing is checked |
| Errors name the row, field, value and fix | `"Line is invalid (No details)"` |
| Failures come back **round-trippable** — same shape as the input, so the loop is "edit → re-upload" | A log file you read and manually cross-reference |
| Validation completes *before* anything is written | Partial writes with no rollback |
| The destructive scope is stated in the confirm, in domain language | *"Are you sure?"* |

**On undo:** this is the weakest area industry-wide. HubSpot's import tool has **no rollback** — *"if you updated existing records via an import, you will not be able to reverse the changes by deleting."* Their real rollback is a separate, permission-gated tool with a 14-day window, a **"Prepare preview"** step, and confirmation friction requiring you to **type a displayed number**. Notion sidesteps it entirely: *"Imports add rows. They don't update existing rows, so watch for duplicates."*

The crux: **almost every product can delete what it created; almost none can un-update.** `[inferred]` If our import can overwrite an existing roster, we either snapshot before commit or make the overwrite explicitly a separate, confirmed action.

### F. Visual assets

**Required vs. placeholder — the clearest split in the survey:**

- **OOTP:** optional, always. *"If still no match is found, OOTP will create a basic fictional logo."* No team is ever logo-less.
- **FHM:** generates generic logos on match failure, and FHM 10 added *"'default' versions of a number of historical team logos so teams imported to a different year that's beyond their historical range still get a logo."*
- **FM:** ships built-in default graphics; custom packs override them.
- **EA CFB:** recolorable generic logos ✓ — but **CFB25 shipped zero generic stadiums**, forcing custom teams into real schools' branded venues. User: *"I cannot stand to create a team and have to play in another team's stadium."* CFB26 added exactly three. Legacy NCAA Football 10 had generics **and** high-school stadiums at launch in 2009 — a 16-year regression, only partly undone.
- **Basketball GM:** URL text field only. `imgURLSmall ?? imgURL` fallback chain. No upload.

**Aspect ratios and file limits surfaced in the UI:**

| Product | Spec | Surfaced where |
|---|---|---|
| OOTP | PNG/JPG, **150×150**, single size (auto-resized); portraits 90×135; park photos exactly 640×480 | Manual only, not the UI. **Frozen since ~2015** while the game moved to 3D stadiums |
| FM | PNG only, 180×180 classic / 256×256 modern; icons 25×25 | Community docs only |
| Draft Day Sports | Logos **300×300**; photos 260×190; jersey icons 50×50; courts **1018×640** with a downloadable design template | Support KB |
| EA CFB 25 | 10 custom images × **512 KB each** | In-app |
| EA CFB 26/27 | **5 MB total budget per team**, unlimited images until spent | In-app. Recommended source resolution raised to 2048px |

`[verified gap]` **EA never publishes accepted file formats or pixel dimension caps** for TeamBuilder in any version — and that ambiguity is directly implicated in the "logos small and duplicated" rendering bug, where identical PNGs failed from Photoshop but worked via Adobe Express.

**Two OOTP ideas worth stealing outright:**
1. **Colors encoded in the filename** — `Augusta_GreenJackets_ffffff_00372A.png` sets logo *and* full uniform palette with zero in-game editing.
2. **Procedural fallback as a guaranteed floor** — the reason OOTP never has a broken-image empty state.

And FHM's era-keyed filenames (`boston_bruins_1948-1948.png`) resolve period-accurate art automatically — elegant, though not relevant to us.

**The single most important asset finding for us:** `[inferred, medium-high confidence]` **No browser basketball sim has an in-browser logo upload.** Basketball GM uses URL fields; Hattrick *withdrew* external hotlinking in favor of hosted upload (a direct precedent for hotlink-rot); Pennant Chase's mechanism is behind a login. Draft Day Sports has an in-app logo *creator* but it's a desktop product with no documentation of depth.

### G. Scope boundaries successful products enforce early

| Boundary | Who enforces it | How |
|---|---|---|
| **No league resizing** | EA CFB (all 8 titles, 2009–2027), FM Create-a-Club | Replace-only. League size is invariant by construction |
| **No conference realignment** | NBA 2K (all versions) | *"you can not edit divisions or conferences, they are both set."* Assignment is automatic |
| **Realignment as a one-time setup gate** | College Hoops 2K8 | *"you have to turn custom conferences on at the start"* — never a live tool |
| **Cosmetic edits always, structural edits never mid-season** | OOTP | Name/nickname/abbrev any time; structure offseason/preseason only |
| **Destructive customization behind an opt-in mode** | Basketball GM | God Mode, priced in achievements, sticky flag, purple everywhere |
| **Custom teams excluded from competitive/graded modes** | EA CFB (offline Dynasty excluded), 2K (custom teams can't be used in Play Now), Basketball GM (achievements off) | Mode-level gating |
| **CPU AI tendencies not part of team-create** | Everyone | EA exposes *school identity templates* and pipelines (sim-flavor presets), never raw AI tuning. 2K's roster AI lives in the Team Editor, separately, commissioner-only |
| **Sharing deferred or third-party** | Basketball GM (Reddit + GitHub, zero first-party hosting), OOTP (forums, no Workshop) | Never built it. Basketball GM's "Enter league file URL" option is what lets GitHub serve as the CDN |

**The instructive failure:** EA *did* ship conference realignment in CFB26, and the result was 17-team conferences producing 6-game schedules, teams meeting once every 7 years, jersey patches rendering as single-color silhouettes, and PS5 users able to realign but not protect rivalries. EA's stated remedy: *"some custom conference combinations were mathematically impossible… those edge cases have been removed from the custom conference matrix."* **They deleted the options rather than explaining the constraint** — and the hard min/max is documented nowhere.

---

## 4. Patterns worth copying

1. **The template is the user's own export.** Symmetric taxonomy on both sides of the round-trip: Basketball GM's export preset **"Teams Only"** mirrors its import **League Part Picker**. Add HubSpot's **"Use as template"** for repeat imports.
2. **The League Part Picker.** *"Use from this file: ☑ Identity ☐ Roster"* — à-la-carte trust instead of all-or-nothing, with a plain-language label per part and a closing warning about weird combinations.
3. **Preview the change set, not the data.** Airtable's "X new, Y updated, Z unchanged." Basketball GM's Move modal with a **"Rebrand team"** checkbox that swaps the preview between current and destination branding before commit. Three rows of raw data is table stakes; the impact summary is what earns trust.
4. **Errors vs. warnings, and never block on warnings** — but render the warning detail *inline*, not in devtools. HubSpot's `Error type` / `Error impact` columns plus **"Download rows with errors as file"** is the target.
5. **Adaptive error messages.** Name the row, field, value and fix. *"Row 42, 'Height': '6-4' isn't a number in inches. Use 76."* Baymard: prioritize 4–7 messages for the complex fields rather than trying to cover everything.
6. **A legible, proportionate, non-destructive price for advanced mode.** God Mode: one confirm, permanent achievement forfeiture, a sticky flag that survives switching back off, a consistent color on every gated control, and gated features **visible-but-disabled** with a peek toggle.
7. **State the simulation consequence, not just the danger.** *"When a team is disabled, all its players become free agents. Because of this, the best time to disable a team is right after the playoffs finish."* Beats *"This action cannot be reversed"* on every dimension.
8. **Preset-then-refine.** 14 preset logos or 5 jersey styles before any custom-art path. Nobody faces a blank canvas.
9. **Procedural fallback so nothing is ever missing.** Generate a logo and court from the team's colors and initials at save time. The uncustomized path looks plain, never broken.
10. **Live identity preview.** Basketball GM renders a jersey and face in the chosen colors as you pick them. Colors are abstract as hex, concrete as a rendered uniform.
11. **Ship a deliberately broken sample file** so users can verify the error path works before trusting it with real data.
12. **A named, user-invocable structural check.** FM's **"Test Nation Rules"** returns domain-language errors like *"relegated team in the bottom division has nowhere to be relegated to."* Schema validation and domain validation are different jobs; Basketball GM's own manual concedes its JSON Schema *"does not check the logical relationship between parts of the league file."*

---

## 5. Patterns to avoid

*Question H. Ranked by how much damage each one did in the wild.*

1. **Creatable ≠ usable.** EA: 32 teams creatable, 16 importable. Legacy NCAA: 120 DLC slots, 12 dynasty slots. *"It makes no sense to be allowed to create 32 Team Builders teams, but you can only download 16."* Same complaint, 15 years apart, still unresolved in July 2026.
2. **Silent failure on malformed input.** FM subfolder/zip/wrong-directory placement produces *nothing* — no warning, no "we found 0 databases (looking in: …)". FHM: diacritics in team names silently break logo matching with no diagnostic. OOTP: the game's own generated PNGs silently shadow user JPGs.
3. **File-blind error reporting.** *"Couldn't load the database"* with no filename; the community invented bisection as the debugging protocol.
4. **The uncustomized path looking broken rather than plain.** EA CFB custom teams get hardcoded sunny weather all year, no team intros or mascots, blank endzone logos in bowl games, announcers who never say the custom name, and snow effects that don't render (*"Your players act like there's snow, but nothing appears on the field"*). No EA response in thread.
5. **Identity welded to the replaced slot.** College Hoops 2K8: moving a team to a weaker conference measurably damaged recruiting, because prestige was welded to the slot. CFB26: the Championship Contender grade depends on which school you replaced. CFB: rivalry inheritance is **inverted** — *"You don't keep rivalries from the replaced team but if they have a locked opponent you do keep them"* — producing a California team playing UNC every year.
6. **Constraint discovery by trial and error.** Real arity constraints, no upfront validator, no published min/max.
7. **Custom teams disappearing across contexts.** FHM custom teams can't be saved at all — *"Nope. Has to be done manually each time."* OOTP's global `data/logos` doesn't retro-apply to existing saves. FM's Real Name Fix must be **manually reapplied after every official patch**.
8. **No undo, no pending state.** OOTP's editors have **no save button** — *"Changes take effect immediately upon selecting a value from a drop-down, or when hitting the Enter key."* Immediate commit + no undo + destructive operations is the worst combination in the survey. Tellingly, the paid third-party FM editor's *headline feature* is *"the first FM editor with a pending & undo system. Every edit you make is tracked, visible, and reversible."*
9. **Opaque, over-triggering moderation.** EA's TeamBuilder content filter rejected a Firefox logo as "personal or offensive" and a plain `111.png` number graphic. The unanswered user question: *"Is there any place that shows guidelines on what they consider offensive?"* No published criteria, no appeal path.
10. **WYSIWYG break across a boundary.** TeamBuilder logos correct on the website, *"very small and duplicated"* in-game. Users forced to author in Adobe Express to work around a first-party bug: *"We need a real fix. I am not going to be forced to create my graphics in Adobe Express lol."*
11. **Manual "save often" in a web app.** EA's own guidance is literally *"SAVE OFTEN so you do not lose your progress,"* on a desktop-browser-only tool where the Roster section *"will likely take the longest."*
12. **Hidden entry points.** FM's paid editor reached by right-clicking a table row. 2K's team-design save buried at `Front Office → Team Relocation → 2K Share Team Designs` — a 2K26 user: *"I've asked everywhere and everyone… and I've never gotten a sensible result!!!"* The identical confusion appears in 2K18 threads.
13. **Server-sunset cliffs.** Legacy TeamBuilder broke in Aug 2018 with **no announced sunset** and contradictory EA support answers; preservation fell to the community. 2K Share dies with each title's servers.

---

## 6. Recommendations for our v1

*Everything below is our recommendation, not observed competitor behavior. All of it assumes the slot-replace model, per-save overlay, and fixed 128/16 structure are fixed.*

### 6.1 Feature name

| Option | Case for | Case against |
|---|---|---|
| **"Team Builder"** ✅ **pick** | Proven across 8 titles and 17 years; names the act of building without promising league growth; already the category's default vocabulary, so it arrives pre-explained; survives expansion to multiple slots in v1.1 without renaming | Some brand adjacency to EA. `[unverified]` Worth a trademark check — it's descriptive and widely used, but confirm before it hits marketing |
| **"My Program"** | Warmest fit for the actual v1 slice (the user's own school); frames the output as a possession rather than a tool | Doesn't scale to "replace 5 CPU schools" in v1.1 without a second name |
| **"Program Editor"** | Accurate, honest, admin-flavored | Reads as tooling, not as *mine*. Lower emotional pull on a hub screen |

**Pick: "Team Builder."** Then do the work in the subtitle, exactly as EA and FM do — the name should not carry the explanation:

> **Team Builder** — Put your own program in the league. Your school takes an existing team's place; the league stays at 128.

Avoid: "Create a Team" (promises addition), "Add My School" (same), "Expansion" (actively wrong), "Custom Database" (a folder name, not a feature).

### 6.2 Primary entry point on the franchise hub

**Recommendation: one card on the post-login home, plus one persistent entry in the franchise hub — and no third path.**

- **Pre-franchise (post-login home):** a card in the "Start a franchise" area — **Team Builder · Put your own program in the league**. Positioned as a step *within* franchise creation, not a separate destination, so the user encounters it while already in a setup mindset.
- **In-franchise (franchise hub):** a persistent **Team Builder** item in the hub's management area, showing current state — "Morristown → Riverside Prep" — so users can re-open, re-import a roster, or fix a logo without starting over. This is the thing OOTP gets right and FM doesn't: *"Add League" reopens the wizard mid-save*, whereas FM has no mid-save club creation at all.

**Explicitly do not build a separate editor app or a separate URL.** EA's split is the source of its worst bug class (correct on the website, broken in-game) and its worst logistics problem (the site ships after the game). We're a browser game; our whole structural advantage here is that the editor and the sim are the same surface. Use it.

**Timing rule** (borrowed from OOTP, which has the most sensible version): **identity edits any time; roster import at preseason only.** Name, mascot, colors and logo are cosmetic overlays and should never be locked. A roster import mid-season would invalidate in-progress stats and standings, so gate it — and say why in the disabled state, don't just grey it out.

### 6.3 Wizard step list for v1

Five steps. Step 4 is skippable. The whole thing should be completable in under two minutes by someone who only wants a name and colors.

**Step 0 — Choose the slot** *(not "step 1" in the user's mind; it's framed as the premise)*
- A searchable list of all 128 programs, showing conference, name, and current record if mid-save.
- Sort/filter by conference and by region, so a user replacing a geographically-sensible school can find one.
- Selection panel shows, before commit: **"You'll replace: Morristown (Conference 7). Their schedule, conference slot, and rivalries stay with your program."**
- Primary CTA: **Choose this slot →**

**Step 1 — Identity**
- Fields: School name · Short name (for box scores) · Abbreviation (3 chars, uniqueness-validated) · Mascot · City/State.
- Live preview panel, always visible: the scoreboard bug and a standings row as they'll actually appear.
- Abbreviation is the only field with real validation. Inline, on blur: *"RIV is already used by Riverton. Try RVP."*
- Primary CTA: **Next: Colors →**

**Step 2 — Colors & look**
- Primary / secondary / accent color pickers, plus a jersey style select (5 presets, per Basketball GM).
- **Live preview updates continuously** — a jersey render, a court render, and a scoreboard bug in the chosen palette.
- **Optional logo**, clearly marked optional, with a generated placeholder shown by default so the user sees a finished-looking team before uploading anything. Upload constraints surfaced *in the UI, before the file picker* — not in a help doc: "PNG or SVG, square, up to 1 MB. Transparent background recommended."
- Primary CTA: **Next: Roster →** · Secondary: **Skip roster — use generated players**

**Step 3 — Roster (optional, and it must feel optional)**
- Three visible choices as cards, not a dropdown:
  1. **Keep Morristown's roster** — fastest, zero risk, the default
  2. **Generate a new roster** — fresh fictional players at the slot's talent level
  3. **Import my roster** — CSV or JSON
- The import path (see §6.5) is a sub-flow, not an inline field.
- Primary CTA: **Next: Review →**

**Step 4 — Review & apply**
- A **change-set summary**, not a data dump (per Airtable):
  > **Riverside Prep** replaces **Morristown** in Conference 7.
  > Identity: name, mascot, colors, logo — all set
  > Roster: 14 players imported, 1 row skipped
  > Unchanged: schedule, conference, opponents, standings to date
- The scoped-consequence line in domain language, per Basketball GM: *"Morristown will no longer appear in this franchise. Your other saves aren't affected."*
- Primary CTA: **Apply to this franchise** · Secondary: **Back**
- Post-apply confirmation with a direct link to the team page, and a persistent **Edit in Team Builder** affordance there.

**Progressive disclosure baked in:** the happy path is Slot → Identity → Colors → *skip roster* → Review. Four screens, no file handling, no failure modes. The roster import — the only genuinely risky part — is opt-in and reachable only from a step the user chose to enter.

### 6.4 Copy patterns for the replacement

The category's failure is not that replacement is confusing — it's that products announce it once, in a title, and never again at the moment of consequence. **Say it three times, escalating in specificity.**

**At the entry point (setting expectations):**
> Put your own program in the league. Your school takes an existing team's place — the league stays at 128 teams and every schedule is unchanged.

**At slot selection (naming the trade):**
> **Riverside Prep will replace Morristown.**
> You keep Morristown's spot in Conference 7, their 2026 schedule, and their rivalries. Your record starts fresh at 0–0.
> Morristown won't appear in this franchise.

**At the confirm (scoping the blast radius — this is the one every competitor omits):**
> Apply Team Builder changes?
> **Riverside Prep replaces Morristown** in Conference 7. Schedule unchanged.
> This affects **this franchise only**. Morristown is unchanged in your other saves and in any new franchise you start.
> You can edit your program's name, colors and logo at any time from the franchise hub.
> **[Apply]** [Cancel]

**On the team page afterward (persistent orientation):**
> Riverside Prep · Conference 7 · *replacing Morristown in this franchise*  **[Edit in Team Builder]**

**Three copy rules, each earned from a specific competitor failure:**
- **Name what stays, not just what changes.** EA's users are still asking what happens to the school they replaced; "schedule unchanged" preempts the question nobody thought to ask.
- **Scope the blast radius explicitly.** Per-save is our architecture's genuine advantage, and the category's most-searched confusion is *"my custom team disappeared in another save."* Say it in the confirm dialog, not in an FAQ.
- **Never use "delete," "remove," or "overwrite" for the slot.** "Replaces" and "takes the place of" are accurate and don't imply data destruction — which, per-save, is exactly right.

### 6.5 Validation UX for template import

**The flow:** Download template → upload → parse with named progress → **parts picker** → preview change set → apply → partial-success report.

**1. Template acquisition — offer both, and say which is which.**
- **Download blank template (CSV)** — headers plus 2 example rows, **with optional columns visibly left blank** (per Baymard's defensive-over-filling finding).
- **Download Morristown's current roster** — the slot's real data, pre-filled, in the same shape. This is the round-trip pattern, and for a *replace* model it's strictly better than a blank template: the user edits a file that's guaranteed valid and already the right size.
- Both buttons live on the import screen itself, above the file input — not in a help doc. Basketball GM puts the pointer inline, above the input, and that's correct.

**2. Required vs. optional, stated on the screen before upload.**
> Required: `first_name`, `last_name`, `position`, `class_year`
> Optional: `height_in`, `weight_lb`, `jersey_number`, `hometown`, `rating`
> Anything we don't recognize is ignored. Anything you leave blank, we generate.

**3. Parse with a named progress bar, not a spinner.** *"Validating roster… 14 of 15 rows."* Per Basketball GM, which names the section being validated.

**4. Column mapping — auto-detect with visible override.** Show a table: `Your column` | `First 3 rows` | `Maps to` | `Status`. Auto-map on header name; unmapped columns get a dropdown including **"Don't import this column."** Add Airtable's graceful degradation: if no header row is detected, offer a **"First row is headers"** toggle rather than erroring.

**5. Parts picker (the Basketball GM pattern, scoped to us).**
> **Use from this file:**
> ☑ Team identity (name, mascot, colors)
> ☑ Roster (15 players)

This is how we deliver "identity without roster" without inventing a second flow.

**6. Errors vs. warnings, separated and never conflated.**

| Class | Behavior | Example copy |
|---|---|---|
| **Blocking error** | Cannot proceed | *"No `last_name` column found. Your file needs `first_name` and `last_name`. [Download template]"* |
| **Row error** | Row skipped, import proceeds | *"Row 12 — `position`: 'PG/SG' isn't a position we recognize. Use one of PG, SG, SF, PF, C. This row will be skipped."* |
| **Warning** | Nothing skipped, import proceeds | *"Row 7 — `height_in` is blank. We'll generate a height."* |

Every row-level message names the **row, the field, the offending value, and the fix.** That single rule beats every game in this survey and matches HubSpot, the best non-game example.

**7. Preview the change set before commit.**
> 14 players will be added to Riverside Prep.
> 1 row will be skipped (see below).
> Morristown's current 15 players will be released to the transfer pool.
> **[Import 14 players]** [Cancel] [Download rows with errors]

That third line is the "unclear overwrite of existing roster" anti-pattern, solved by stating it.

**8. Partial success with a round-trippable error file.** *"14 players imported. 1 row skipped."* Plus **Download skipped rows** returning a file in the **same shape as the input** so the loop is edit-and-re-upload, not read-a-log. Per HubSpot, this is the load-bearing part — not the summary sentence.

**9. Empty and error states, specified:**
- **Empty (no file yet):** the two template buttons, the required/optional field list, and a one-line "or skip this — we'll generate a roster."
- **Wrong file type:** *"That's a .xlsx file. Save it as CSV (File → Save As → CSV) and try again."* Not "Invalid file."
- **Empty file:** *"That file has headers but no player rows. Add at least one player, or skip roster import."*
- **Too many rows:** *"That file has 40 players. A roster holds 15. Trim the file, or import the first 15."* — with the second option as an actual button.
- **Parse failure:** *"We couldn't read that file — it may not be a valid CSV. [Download our template] and paste your data into it."* Never "An error occurred."

### 6.6 What to cut from v1 without feeling unfinished

| Cut | Why it's safe | What makes it not feel missing |
|---|---|---|
| **Custom logo upload** | No browser basketball sim has it; OOTP proves generated logos are acceptable | Ship a **generated placeholder from colors + initials** that looks deliberate. Then add upload in v1.1 as a visible win |
| **Custom court art** | 2K's own court editor can only scale images; nobody expects this | Generate the court from team colors. It'll look better than most user uploads anyway |
| **Replacing more than one program** | EA caps at 16 of 138 and users still hit the ceiling; one is a complete story | Frame v1 explicitly as **"your program"** — a scope, not a limit. "Replace more programs" as a labeled v1.1 item |
| **Sharing / a community browser** | Permanent moderation, hosting and sunset liability. Basketball GM's ecosystem thrives with zero first-party hosting | **Export my program** as a file. Users can share it themselves on Discord — that's how Basketball GM's entire ecosystem works |
| **Conference realignment / league resizing** | Structurally incompatible; 2K refuses it outright and EA's attempt broke schedules | Never mention it as a limit. It simply isn't part of the feature's story |
| **Editing CPU AI tendencies** | Nobody bundles this into team-create | Out of frame entirely |
| **Uniform designer** | EA's 625 combinations are a AAA investment | 5 jersey style presets × 3 colors reads as a designer to a first-time user |
| **Mid-season roster import** | Invalidates in-progress stats | Gate it, and say why in the disabled state: *"Roster import is available in the preseason."* |
| **Undo of an applied import** | Genuinely hard; HubSpot and Notion both punt | Prevent instead of reverse: preview the change set, state what's released, and confirm |

### 6.7 v1.1 candidates, in priority order

1. **Logo upload** — the category's clearest unoccupied ground in browser basketball. Constraints in the UI before the picker; server-side re-encode to a normalized size to dodge EA's rendering bug class; render at final size in the preview so WYSIWYG actually holds.
2. **Replace multiple CPU programs** — EA's 16-of-138 cap tells us appetite is real. Needs a management surface listing all replacements in a save, with per-slot revert.
3. **Export my program** — a single file containing identity + roster. Cheap, and it enables organic sharing without us hosting anything (the Basketball GM strategy). Also becomes the round-trip template for repeat imports.
4. **Court and jersey customization** beyond presets.
5. **Import from a URL** — Basketball GM's *"Enter league file URL"* is what makes GitHub work as a community CDN. Costs almost nothing; unlocks a whole ecosystem.
6. **A community browser** — only after 3 and 5 prove there's content worth browsing. Moderation cost is real and permanent; EA's opaque filter rejecting a Firefox logo is the cautionary tale.

---

## 7. Open questions for design & eng

1. **Does the schedule genuinely survive a slot replace untouched?** Our copy promises "schedule unchanged" at three separate points, and it's the single most reassuring thing we say. If there's any case where it isn't literally true, the copy has to change before anything ships.
2. **What is the actual blast radius of replacing a slot mid-save?** Specifically: standings-to-date, head-to-head history, awards already given, and any in-flight recruiting or transfer state. The confirm dialog needs to enumerate this accurately, and "we'll figure it out" produces exactly EA's problem.
3. **Can a user revert a slot back to the original program?** If yes, the whole destructive-action framing softens and we can drop a lot of warning copy. If no, we need the change-set preview to carry more weight. This choice cascades through §6.4 and §6.5.
4. **Do we have a generated-logo path today?** The recommendation to cut logo upload depends entirely on generated placeholders looking deliberate rather than like a missing asset. If we don't have one, that's the first thing to build, not the last.
5. **Roster size and position rules** — exact required count, position minimums, class-year distribution. These are the domain validations that matter, and per FM's "Test Nation Rules" they need plain-English error messages, not schema errors.
6. **CSV or JSON for v1 import — pick one.** Recommendation is CSV (spreadsheet-native, the audience already has rosters in Excel, and the column-mapping pattern only makes sense for tabular data). JSON is the power-user format and can follow.
7. **What happens to a replaced program's players?** Released to a transfer pool, deleted, or retained as free agents? The answer goes verbatim into the confirm dialog, per Basketball GM's *"all its players become free agents"* pattern.
8. **Is there any competitive or leaderboard surface a modded save should be excluded from?** If yes, we adopt the God Mode pattern now — a legible, proportionate price stated up front. Retrofitting a penalty after users have built franchises is the one version of this that goes badly.

---

## Appendix: confidence & verification

**High confidence — verified against primary sources or source code:**
Basketball GM's entire UI vocabulary (verified by direct reading of the `zengm-games/zengm` source, with file paths): the six Customize dropdown options, the Manage Teams field list, the confirmed absence of any logo upload, the full League Part Picker label map, God Mode copy and the sticky `godModeInPast` flag, all import error strings, the Move modal's rebrand semantics, Export League option descriptions. EA CFB TeamBuilder: the URL, desktop-browser-only restriction, five-tab flow, 625 uniform combinations, 134 stadiums, the CFB25→26 upload-limit change, the 16-team import cap and its exact replacement wording, commissioner-only cloud-Dynasty gating. FM: the editor product split, appids and prices, `editor data` paths and the no-subfolder rule, the graphics `config.xml` schema, Workshop item counts. OOTP: all manual-sourced button labels, menu paths, wizard steps, file specs, the import error-code table, the roster import warnings verbatim. HubSpot/Airtable/Stripe/Mailchimp import flows and NN/g and Baymard guidance.

**Version-dependent — flagged inline:**
- **OOTP's official manual ends at v24; the shipping version is v27.** Logo specs, editor layouts and import flows may have changed. OOTP 27 explicitly markets UI changes but names none of these three areas.
- **FM26 removed Create-a-Club** (three independent secondary sources plus its absence from every FM26 setup walkthrough including the official one). FM Scout says it *"will return in FM27."* I could not load a primary SI URL confirming this — `community.sports-interactive.com` blocks automated fetches. **The Create-a-Club detail in the matrix is FM24 behavior**, which is the right reference for us regardless, since it's the design we're learning from.
- **EA College Football 27 has shipped or is shipping** (EA published a CFB27 Dynasty & TeamBuilder deep dive dated 4 June 2026). EA's TeamBuilder URL and help pages are **not versioned** — fetching a CFB25 doc URL now serves CFB27 content. Any undated TeamBuilder documentation may describe a different year than it appears to. School count reached 138 in CFB27.
- **NBA 2K's expansion cap model changed in 2K25** — from 6 teams total per save to 6 per offseason, repeatable, bounded by 12–36. Pre-league wizard labels are sourced to a 2K24 article and unconfirmed for 2K26.

**Unverified — do not present as fact:**
1. **NBA 2K has no custom-art upload.** This is inference from a complete absence of evidence across many sources, not a positive finding. It's also the sharpest contrast with TeamBuilder, so it's worth confirming before it appears in any external-facing material.
2. **EA's hard min/max teams-per-conference.** EA's own custom-conferences help page 404s; the only evidence is one user's 17-team failure case.
3. **What happens to a replaced school in EA's model, and whether the import is reversible.** EA Help is completely silent and no user account resolved it. Directly relevant to open question #3.
4. **FM26's missing-badge fallback treatment.** FM ships built-in defaults, so it's not an empty slot, but the actual visual is unconfirmed. Needs a screenshot.
5. **Any pre-action destructive warning copy in EA TeamBuilder or NBA 2K MyNBA.** I found only *error* dialogs, never warnings or confirms. This may genuinely not exist — which is itself the finding — but it's an argument from absence.
6. **Pennant Chase's logo input mechanism** (upload vs. URL vs. gallery, and size limits) is behind a login. It's the closest browser competitor to have shipped anything here, so it's the most decision-relevant unknown in the browser tier.
7. **The "Team Builder" name is not trademark-cleared.** It's descriptive and used widely across the category, but confirm before it reaches marketing.
8. **Draft Day Sports' in-app logo creator** is confirmed to exist by two marketing sources with zero documentation of what it does. The most interesting unknown, given it's the only in-app logo *authoring* tool in the survey.

**Method limitations:** Reddit was inaccessible throughout (403/429 at every route), so r/OOTP, r/NBA2k, r/CFB25, r/BasketballGM and r/footballmanager are entirely unexamined — the largest untapped pool for beginner-confusion evidence specifically. `forums.ootpdevelopments.com` thread bodies are registration-walled. `community.sports-interactive.com` blocks automated fetches. Complaint evidence therefore skews toward Steam, EA Forums and Operation Sports, which sample an older, more sim-focused player base than our likely audience.

---

## Sources

Selected primary references; full URLs were verified during research.

**EA College Football / TeamBuilder:** [EA Help — Team Builder](https://help.ea.com/en/articles/ea-sports-college-football/team-builder/) · [EA Help — Import team from Team Builder](https://help.ea.com/en/articles/ea-sports-college-football/import-team-from-team-builder/) · [EA — CFB25 Team Builder Deep Dive](https://www.ea.com/security/news/college-football-25-team-builder) · [EA — CFB26 Dynasty & Team Builder Deep Dive](https://www.ea.com/games/ea-sports-college-football/college-football-26/news/cfb26-campus-huddle-dynasty-deep-dive) · [EA — CFB27 Dynasty deep dive](https://www.ea.com/games/ea-sports-college-football/college-football-27/news/college-football-27-dynasty) · [Operation Sports — TeamBuilder forums](https://forums.operationsports.com/forums/forum/football/ea-sports-college-football-and-ncaa-football/ea-sports-college-football-team-builder)

**Football Manager:** [FMInside — Create a club mode](https://fminside.net/guides/basic-guides/249-create-a-club-mode-in-fm) · [FM Scout — Things Removed in FM26](https://www.fmscout.com/a-things-removed-in-fm26.html) · [sortitoutsi — Essential FM26 Info](https://sortitoutsi.net/content/74716/essential-fm26-info) · [sortitoutsi — installing editor data files](https://sortitoutsi.net/installation-instructions/4/how-to-install-fmf-and-xml-editor-data-files-in-football-manager) · [FM Scout — XML config files](https://www.fmscout.com/a-how-to-make-xml-config-files.html) · [Steam — FM26 In-Game Editor](https://store.steampowered.com/app/3551410/Football_Manager_26_InGame_Editor/)

**OOTP / FHM:** [OOTP manual — Custom Game Wizards](https://manuals.ootpdevelopments.com/index.php?man=ootp24&page=custom_game_wizards) · [League Structure Editor](https://manuals.ootpdevelopments.com/index.php?man=ootp21&page=league_structure_editor) · [Import/Export Functions](https://manuals.ootpdevelopments.com/index.php?man=ootp16&page=import_export_functions) · [Logos in Practice](https://manuals.ootpdevelopments.com/index.php?man=ootp23&page=logos-in-practice) · [Logo file naming conventions](https://manuals.ootpdevelopments.com/index.php?man=ootp17&page=logo-file-naming-conventions) · [OOTP wiki — League Expansion](https://wiki.ootpdevelopments.com/index.php?title=OOTP_Baseball:Important_Game_Concepts/Tools_Functions_and_Editors/League_Expansion) · [FHM modding sticky](https://forums.ootpdevelopments.com/showthread.php?threadid=284491)

**NBA 2K:** [2K25 MyNBA Courtside Report](https://nba.2k.com/2k25/courtside-report/mynba/) · [2K26 MyNBA Courtside Report](https://nba.2k.com/2k26/courtside-report/mynba/) · [Operation Sports — MyNBA league customization](https://forums.operationsports.com/forums/forum/basketball/nba-2k-basketball/903183-next-gen-mynba-league-customization) · [NBA2KW — MyNBA settings explained](https://nba2kw.com/nba-2k23-mynba-eras-settings-explained)

**Basketball GM / ZenGM:** [Customization manual](https://basketball-gm.com/manual/customization/) · [JSON schema page](https://basketball-gm.com/manual/customization/json-schema/) · [Minimal custom roster example](https://old.basketball-gm.com/templates/manualCustomRosters.html) · [zengm source](https://github.com/zengm-games/zengm) · [alexnoob roster repo](https://github.com/alexnoob/BasketBall-GM-Rosters)

**Import UX:** [HubSpot — Understand the import tool](https://knowledge.hubspot.com/import-and-export/understand-the-import-tool) · [HubSpot — Troubleshoot import errors](https://knowledge.hubspot.com/import-and-export/troubleshoot-import-errors) · [Airtable — CSV import extension](https://support.airtable.com/docs/csv-import-extension) · [Stripe — Data templates](https://docs.stripe.com/stripe-data/import-external-data/data-template) · [NN/g — Error message guidelines](https://www.nngroup.com/articles/error-message-guidelines/) · [NN/g — Wizards](https://www.nngroup.com/articles/wizards/) · [Baymard — Adaptive validation error messages](https://baymard.com/blog/adaptive-validation-error-messages) · [Flatfile — Optimizing CSV import experiences](https://flatfile.com/blog/optimizing-csv-import-experiences-flatfile-portal/) · [OneSchema — Building a CSV uploader](https://www.oneschema.co/blog/building-a-csv-uploader)
