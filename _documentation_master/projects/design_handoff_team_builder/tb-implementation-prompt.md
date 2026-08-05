You are implementing the Team Builder feature redesign in guyfromajax/gob-simplified, branch develop.

Read design_handoff_team_builder/README.md first, in full, before writing any code. It documents seven screens with exact colors, type, spacing, copy, state and interaction behavior, plus the reasoning behind the flow's structure.

Then read _documentation_master/projects/mod-system/team-builder-v2-plan.md. The README governs presentation. That document governs behaviour, and it is not optional. Where they appear to conflict, the plan wins on rules and the README wins on rendering.

What you are building

A restructured Team Builder flow, replacing the current five-step wizard:

Program Select → Ⅰ Claim → Ⅱ Identity → [Build mode gate] → Ⅲ Roster → Review → Establish

Seven screens. The README has a section per screen.

Ground rules

1. The HTML files in design/ are design references, not production code. They are React-via-Babel prototypes. Recreate them in this repo's actual environment — vanilla JS + per-page CSS under FrontEnd/static/, following the patterns already used by franchise-select-team.html, js/shared/teamPicker.js and mode-select.js. Drop React and Babel entirely.

2. Three files ARE production code — use them as-is, do not reimplement.

js/shared/teamGeneratedArt.js (banners, jerseys, marks) — already in the repo
js/shared/teamCourtGenerator.js (courts) — already in the repo
design/tb-banner-variants.jsx — new draw functions written to drawChevronBanner's exact contract; port the four functions into teamGeneratedArt.js

An earlier prototype revision contained hand-written art generators. They disagreed with production in six documented ways and were deleted. Do not write independent art code.

3. Two production changes are required. Both are specified in the README's Production changes required section:

Four banner draw functions + a stored banner_variant on the team, defaulting to baseline
insideWoodColor on the court generator

4. Fidelity is high. Match the documented values. Where the README states a reason for a choice ("under-cap is neutral, not amber", "contain not cover", "a stepper not a slider"), the reason is load-bearing — don't optimise it away.

Behavioural rules from team-builder-v2-plan.md

These are not visible in the design files and have each already caused a production defect.

§3.1a — resolve at the edge, on the way out. The display resolver belongs in response serialization only. It must never touch object construction, persistence, or anything used as a key, hash or comparison. Applying it on the way in broke the sim.
§3.2b — chrome resolves through the hydration gate. All seven screens must resolve team identity and colour through lookupTeamChrome / ensureTeamBuilderChromeSnapshot, never from raw team data or URL parameters. Three separate rounds of identity leaks came from new entry points rendering before hydration settled.
§4.5b — the editor is a diff, not a form. Any field the user does not edit keeps its inherited value. Apply clones the inherited player document and overwrites only what changed; it does not construct a player from the payload. A zero-edit Apply once differed on 36 field paths.
§4.5b, second rule — bind by identity, never by ordinal. Budgets, edits and inherited values bind to players by identity, never by position in a query result. find() order is not roster order, and aligning to it silently wrote budgets to the wrong players.
§6.5 / §10.4 — height is final before portrait assignment. Portrait auto-assignment classifies on height, weight and attributes. A later height edit must re-run assignment for that player unless the user has explicitly picked a portrait, in which case portrait_locked preserves their choice. The README specifies both controls but not their interaction — this is the rule.
§10 — budget definitions. Height: team total, may not exceed inherited, under permitted. Year: team total, must equal inherited exactly. Attributes: per player, inherited total, points never move between players.
Traps worth knowing before you start

These each cost a debugging cycle in the prototype:

Any offset that depends on chrome height must be derived from a measurement, never hardcoded. Three separate bugs had this one cause. In production the prototype's review bar doesn't exist, so hardcoded offsets won't fail visibly in development and will be wrong in production. See Sticky offsets.
--tx3 (3.29:1) is chrome only — never body text or data. Caught five times in review. Treat it as a lint rule.
Court fields store tokens, not resolved hex. Storing hex freezes the court when the palette later changes.
RT is the position rating at a slot. There is no overall rating anywhere in this product. Don't introduce one.
Player display names must come from /teams, never derived from slugs — nameToTeamSlug is lossy for internal capitals, periods and apostrophes.
The ida asset folder is uppercase on disk (images/teams/IDA/) while its file stem is lowercase. couer_dalene has a related mismatch documented in the v1 spec — do not "fix" either stored id.
Architecture constraints
The client is a pure renderer for game rules. Position ratings are server-computed and arrive on release; the UI shows a recomputing… state and never guesses.
Running totals over server-supplied values ARE allowed and already shipped — height and year budgets are sums over values the client holds. The rule: the client may aggregate values it already holds; it may not compute values it doesn't hold. The SR=4 / JR=3 / SO=2 / FR=1 mapping comes from the server as class_rank because that is a rule, not arithmetic.
Build mode is written permanently when the program is established. There is no path to change it afterwards. The gate and the Review eligibility block both say so in those words.
Court geometry is fixed. Only the five color parameters and the hardwood style key vary.
Weight is never computed on the client. It shows the inherited value until height changes, then a short label; the figure is computed once at Apply by the backend.
Scope changes to enforce
CSV import is retired, including its backend endpoint. The flow has one roster path. It must not survive as a dormant route — a later league-wide upload feature will have different requirements and will be built fresh.
No upload control for portraits anywhere. Uploads are a committed fast follow but do not exist. A control that isn't wired is worse than an absent one.
The old five-step wizard is removed, not flagged. Do not leave both flows reachable.
Old-format team_builder_wizard_drafts rows are discarded on read, not migrated. The flow shape changed enough that a half-built wizard draft does not map cleanly onto it, and attempting a partial migration produces a program the user never authored. Detect the old shape, drop it, and surface no unfinished-program card for it — the user starts clean. Say how you detect old vs new format.
Answers to the README's open questions
Apply timing — the 2600ms SERVER_MS is a placeholder and must not ship. Instrument the real Apply and report the number. It now warm-paints 15 portrait masters, so it may be materially longer than assumed. Design the sequence around the measurement, not the placeholder.
Conference membership — use team.conference from /teams. Confirmed.
Display names — from /teams, never derived from slugs. Confirmed, and it is the same lesson that produced the Couer d'Alene and Queen's Guard defects.
Draft persistence — cheaper than the README assumes. team_builder_wizard_drafts already exists in production, built so wizard-generated walk-ons and portrait assignments stay stable across reloads. Persisting a half-built program extends something already running rather than requiring new infrastructure. Build the unfinished-program card on Program Select. Only new-format drafts populate it — see Scope changes to enforce.
Year vs potential — restore the guard, once, on the gate, where budgets are explained. Potential is fixed at generation via entry_tier and potential_factor; it does not respond to Year, height or attribute edits. A younger roster has more seasons ahead, not better players. The flow must not imply otherwise anywhere.
One edge case the design doesn't cover

The §4.3 top-up. Any player whose twelve-attribute total falls below 60 is raised to exactly 60 at Apply, because every attribute needs a minimum of 5. It affects 13 players league-wide, so it is rare — but for such a player the inspector shows 24 / 24 while the shipped player has 60. Decide whether to surface it (as the roster editor already does elsewhere: "Topped up from 24 — every player needs at least 5 in each attribute") or suppress it, and say which. Silent adjustment is the pattern this feature forbids everywhere else.

Suggested order
Claim / Program Select — the largest screen, and it grounds the league data model. It's also closest to what already ships.
Build mode gate — smallest, fully specified, no new data.
Identity studio — needs the two generator changes; do those first.
Roster — hardest. Budget arithmetic, the inspector, and the legality verdict.
Review — mostly composition over data you now have.
Establish — timing-dependent; needs the real Apply number.
Acceptance — report each explicitly, numbered, one line each

Do not mark an item passed by inspection where it can be exercised.

All seven screens render and the flow completes end to end.
Height budget enforces: over is refused, under is permitted and reads as neutral, not amber.
Year budget enforces exactly: both over and under are refused, with the shortfall or surplus stated.
Attribute budgets are per player; no point can move between players — verified by attempting it, not by reading the code.
The legality verdict is correct in both directions, and the Take me there jump selects the offending player.
Position ratings arrive from the server on release, show recomputing… while pending, and never display a guessed value.
Weight shows inherited until height changes, then the label. No weight_from_height implementation exists in frontend code.
A height edit re-runs portrait assignment unless the user picked a portrait, in which case their choice survives.
Build mode is written permanently at Establish, and both the gate and Review say so in those words.
The primary action reads Establish ⟨Program Name⟩, with a graceful fallback for long names.
Uncapped renders meters as reference readouts rather than removing them, and carries Not eligible · written permanently.
A zero-edit Apply produces a program field-for-field identical to the one it replaced, except identity, colours, minted player_ids and portraits — verified by diffing every field of all 15, not by spot-checking.
The leak detector is clean across the entire flow, including a mid-game resume afterwards. Update team-builder-identity-inventory.md with the seven new surfaces.
A non-mod franchise is unaffected — verified against the fixed build, not assumed.
The measured Apply duration is reported, and the establish sequence is built around it.
Sim Game Perf is unaffected: no new per-turn or per-frame work, no synchronous layout reads in any render loop.

Ask before deviating from a documented value. Ask before adding anything the README doesn't specify.
