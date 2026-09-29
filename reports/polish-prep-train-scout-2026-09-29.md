# UX polish batch C — Player Training + Scouting

Branch `ux/polish-prep-train-scout`, off `origin/develop`.

---

## Read this first — one thing needs your decision

**Item 1b splits cleanly in two, and only one half is blocked.** The two kinds of
"training setting" on that page persist in completely different ways:

| | How it saves today | Can it have an orange Save + toast? |
| --- | --- | --- |
| **Per-player focus / assignments** (training position, development focus) | immediately, one `POST /franchise/player/development-focus` per change | **Yes.** The route exists and persists. |
| **Weekly point allocation** (drills, installs, sessions, coaching focus) | not at all until you submit, and submitting *runs* the week | **No.** Needs a new server route. |

So the half you named explicitly in 1b — "per-player focus/assignments" — is already
editable and already persists; it just saves silently on change, with no confirmation. The
weekly allocation is the blocked half: it lives only in a sessionStorage draft until
submit, and submit consumes the week and produces the training report. An orange Save
wired to that would quietly advance the game, which is not a save.

What I did do for item 1: renamed the tab to **Player Training** and moved it last in the
Prep sub-tabs. **I did not touch either save path**, because turning today's
save-on-change into a deferred Save is a real UX tradeoff rather than a gap — see the
questions at the end of part 1a.

Everything in item 2 and all four batch A follow-ups are done.

---

## 0. Follow-ups from batch A

### 0a — Momentum removed, eleven measures

`momentum_score` is gone from the display list (`office_digest.py::_MEASURE_FAMILIES`) and
from the ranks table (`team_measure_ranks.py`). It stays in `TEAM_MEASURE_KEYS`, which
drives the weekly snapshot write — the value is still stored, just not shown or ranked.

The grid is still 4×3. The four pair columns are unchanged; the bottom row is Chemistry /
Fight / Discipline and the fourth cell is empty, with no placeholder.

One thing worth flagging in the CSS: the row-separator rule used to count back from the
end (`:nth-last-child(-n+4)`). With eleven cells the last row is three wide, so counting
back four would have taken the rule off `rebound_modifier` in the row above. It is now a
`border-top` on `:nth-child(n+5)`, which is independent of the cell count.

### 0b — Court headshots squared

The two live ones in `court.html`: the playcall reveal HUD (`.hud-headshot-container`,
70px, now `10px`) and the sim quarter log (`.sim-quarter-player-image`, 40px, now `6px`).
The dormant `.active-player-headshot` and `.audible-headshot-container` are untouched, as
is the Phaser canvas marker.

### 0c — Radar fill is neutral

Four values in `franchise-command-center.css` were blue, not one: the zero ring stroke,
the shape fill, the outline stroke and glow, and the pulse keyframe's drop-shadow. All
now white tints. Because it is the shared renderer, both callers changed together.

### 0d — One vocabulary on Prep › Scouting

`scoutingView.js` now reads **P/T Offense**, **P/T Defense**, **Fast Break**, **Fast Break
Defense**. Display labels only; the data keys are untouched. You can see all eight in
`scouting-report-lower-1280.png`.

**Other surfaces still on the old names** (not changed — say the word and I will):

| File | What it says |
| --- | --- |
| `court.html:6544` | "Press/Trap Efficiency" |
| `box-score.js:1247`, `:1262` | "Press/Trap" |
| `training-report.js:100`, `:159` | "Press/Trap", "Press/Trap Readiness" |
| `training-report.js:106` | "Press/Trap Breaks" |
| `tutorial-scouting.html:268` | old names in tutorial copy |
| `tutorial-team-attributes.html:236`, `:246` | old names in tutorial copy |
| `tutorial-training.html:253`, `:260` | old names in tutorial copy |
| `training-report.css:503` | a comment only |

The tutorials are the ones I would most want to change next, since they teach the wrong
words to a new player.

---

## 1. Player Training

### 1a — What Prep › Training shows today

**It is already the whole standalone training page.** `trainingView.js` embeds
`/training.html?embed=1` — `.training-container`, `#custom-focus-modal` and
`#auto-train-modal` — and then loads the real `/training.js` (2,164 lines). It is not a
reduced or read-only copy. See `player-training-tabs-1280.png`: Player Drills (Inside and
Outside Offense, Inside and Outside Defense, Passing, Ball Handling, Rebounding), Scheme
Installs (Offense and Defense Install, FB Offense and Defense Install, P/T Offense and
Defense Install), Full Team Sessions (Strength, Agility, Conditioning, Free Throws, Film
Study, Breaks, Scrimmages), the Playbook Training toggle, and Coaching Focus with all four
coach archetypes. Auto-Train and the tutorial button are there too.

So the comparison table is short, because there is almost nothing in the middle column:

| | Standalone `/training.html` | Prep › Training (embed) | Old FCC training tab |
| --- | --- | --- | --- |
| Drill point sliders (team-wide, 0–5) | yes | yes, same markup and same `training.js` | no |
| Scheme installs | yes | yes | no |
| Full team sessions | yes | yes | no |
| Playbook training | yes | yes | no |
| Coaching focus | yes | yes | no |
| Auto-Train | yes | yes | no |
| **Per-player position + development focus** | yes | yes | yes — and it was the *only* thing there |
| Its own submit button | `#submit-btn` | **removed on mount** | n/a, nothing to submit |
| Commit action | page's submit button | green top-bar Advance | per-player saves post on change |

Worth being precise about one thing, since the brief's wording could read either way: the
drill controls are **team-wide point allocations**, not per-player assignments. The only
genuinely per-player settings are the position and development-focus selects in the Player
Development grid. The old FCC tab had *just* those — so "like we had before" is a strictly
smaller surface than what the tab shows today, not a larger one.

The one real difference is the last two rows: `trainingView.js` does
`submit.remove()` and hands the commit to the top-bar Advance, which relabels itself
"Submit Training" (visible in the screenshot) or "Run Training Camp" in camp week via
`GOBTraining.syncAdvance()`.

**Why it reads as confusing, and it is not what the brief assumed.** Two different views
are registered on the *same* sub-tab:

```
gobViews.js:312   id: 'training-view',        subtab: 'training-view'   // the editable page
gobViews.js:320   id: 'training-report-view', subtab: 'training-view'   // the post-run report
```

`gobShell.js:425` then collapses `training-report-view` back to `training-view` for the
purposes of highlighting the tab. So one tab shows two unrelated things depending on where
you came from — the editable settings, or the report of training already run. The Office
"todo" route (`officeHome.js:444`) deliberately points at `training-report-view`. My
strong guess is that this — a tab that sometimes isn't the settings page at all — is the
"wildly confusing" part, not a missing settings page.

**The two save paths.** Per-player settings already persist. The Player Development grid
inside this page renders two selects per player — `training_position` (PG…C) and
`training_focus` (standard, offensive, defensive, athletic, fundamentals, rebounding) — and
`developmentFocus.js` posts each change straight away:

```js
// developmentFocus.js:157 binds a change listener per select, which calls:
fetch(API_CONFIG.buildUrl('/franchise/player/development-focus'), { method: 'POST', ... })
```

That route is real (`franchise_routes.py:10021`) and takes
`{ franchise_id, player_id, training_position?, training_focus? }`.

The weekly allocation does not. `training.js:1393` sets `endpoint = '/api/training'` for
single-game mode, and that route **does not exist on the server**; `BackEnd/api/` has only
`POST /api/run_training`, `/franchise/run-training`, `/franchise/run-training/user` and
`/franchise/run-training/cpu-train`. In franchise mode the submit goes to
`run-training/user` and then polls to a terminal state. Every one of those *runs* training.
The allocation itself lives in a sessionStorage draft until then.

**So, three questions for you:**

1. Should I split the two views onto their own sub-tabs, so Player Training is always the
   editable settings and the report gets its own place? That is what I think you are
   actually asking for, and it needs no new server route.
2. For the per-player settings, do you want the **orange Save + GOBToast** (deferred: edits
   collect, one Save posts them, toast confirms, and the real-edit leave check guards the
   tab), or just a **GOBToast on the existing save-on-change**? The second is a few lines
   and pure added feedback. The first is better if you want an explicit commit point, but it
   replaces a working immediate-save with a state you can lose — and the leave check only
   earns its place in that version. I did not want to pick this for you.
3. Do you want a real save-without-running endpoint for the weekly allocation? That is a
   backend change (persist `training_data` on the franchise, have `run-training` read it
   back), which is outside this brief's "stop if the server needs changing".

### A dead code path worth knowing about

The legacy FCC training panel (`#training-tab` / `#fcc-training-dev`, with its own copy of
the Player Development grid) is **unreachable**. `commandCenterTabs.js:82` canonicalises the
tab name — `training-tab` → `training-view` — *before* passing it to `onTabShow` at line
108, so the `if (tabName === 'training-tab')` branch at
`franchise-command-center.js:4482` can never be true and `renderFccTrainingTab()` never
runs. The comment there says that panel is the fallback for when
`/franchise/training-points` returns 400 after week 26; that fallback is therefore also
broken. Not in this brief's scope, and I have not touched it, but it is either dead code to
delete or a real post-week-26 gap to fix.

### 1b — Rename and reorder (done)

`gobShell.js` now reads Game Plan, Playbooks, Scouting Report, **Player Training**. The
view **id** is unchanged, deliberately: `gobAdvance.js:380` sets `tab=training-view` and
`gobShell.js:122` maps the `/training.html` browse route to the same sub-tab, so both keep
working off the id while only the label moved.

Side effect worth knowing: `gobSubtabs.js:163` defaults a section to its first tab, so
clicking Prep in the rail now lands on Game Plan rather than Training. That follows from
the order you asked for.

### 1c — The Advance flow still reaches it

Nothing server-provided needed changing. The Advance target is the view id, which I did not
touch. Verified two ways: the top bar still renders "Submit Training" on this view (in the
screenshot), and a test clicks the renamed tab and asserts `#training-view` becomes
visible.

---

## 2. Scouting Report

### Why the attribute data was not wired

Not a missing field — a **double divide**. The server already returns the 0–10 display
scale:

```python
# scouting_utils.py:212, inside compute_projected_starting_five
raw = attrs.get(f"anchor_{k}", attrs.get(k, 0))
attr_display[k] = int(float(raw)) // 10
```

The shell view then ran that through `GOB_AttributeDisplay.displayAttr`, which does
`Math.floor(n / 10)` a second time. A 75 became 7 on the server and then 0 in the browser.
Every tile in the grid read 0; only a literal 100 survived, as 1.

Proved rather than assumed, by calling the real function:

```
ATTRIBUTES AS SENT BY SERVER: {'SC': 7, 'SH': 8, 'ID': 4, ...}
raw SC 75 -> server sends 7
client divides again -> 0
```

The legacy FCC card renderer hit this exact bug and was already fixed, with a comment
saying so (`scoutingReport.js:90`). The new shell view reintroduced it. `attrTile` now
prints the value as given, matching the legacy renderer.

**The test fixture was hiding it.** `prep-scouting.spec.js` carried raw 0–99 attributes, so
the view's second divide looked correct under test and wrong in production. The fixture now
uses the 0–10 values the server really sends, with a comment saying why, and a new test
fails on either a grid of zeros or a grid of dashes.

### The team logo

`getTeamAssetPath(name, 'logo_square')` was right, but the call was unguarded. Generated
art can throw for a team that is not in the chrome snapshot yet — `gobTables.js:44` wraps
its own identical call in a try/catch with the comment "generated art can fail closed" —
and this call sits inside `paintReady`'s markup build. One throw took the entire panel to
"Unable to load scouting report" rather than costing one logo. It now has the same
try/catch, falls back to `/images/teams/general/general_logo_square.png` like the rest of
the shell, and carries an `onerror` to the same fallback. The monogram branch is gone, so
there is one behaviour across the shell instead of two.

### Section spacing

The sections were never in the element that carried the rhythm. `.pv` had
`gap: var(--dsp-24)`, but the sections live one level deeper inside `.scouting-ready`, so
that gap only ever separated the status line from the panel and the sections themselves
fell back to whatever margins they happened to have. Measuring confirmed it: the probe
found zero gaps to compare because there were no sections at that level.

The rhythm now sits on `.scouting-ready`. Two details:

- The `.gob-1920` override is gone. `--dsp-*` tokens are themselves density-scaled
  (`--dsp-24` is 24px at 1280 and 28.5px at 1920), so the old `--dsp-16` override resolved
  to 19px and gave the **wider** screen **tighter** sections than the narrow one.
- The new rule is `.scouting-ready:not([hidden])`. A bare `display: flex` on that selector
  outranks the UA rule for the `hidden` attribute and would have leaked the panel into the
  loading state.

Measured: 24 / 24 / 24 at 1280 and 29 / 29 / 29 at 1920, across all four top-level blocks.

### The blank panel on reopen

Reopening the tab keeps the mounted handle and calls `revalidate()`
(`gobViews.js:139`), which called `load()`, which called `setStatus()` — and `setStatus`
sets `readyEl.hidden = true`. So the already-rendered panel was thrown away immediately and
stayed blank for the whole async chain: three script loads, then two fetches. That is the
4–5 frames.

Now `load()` only shows the loading status when nothing has been painted yet. On a
revalidate the panel stays up, and the payload is compared against a signature of just the
fields the panel renders; an identical payload does not repaint at all. A failed refresh
behind a good panel no longer replaces it with an error either. No change to
`gobViews.js` was needed.

---

## Tests

Added to `tests/e2e/prep-scouting.spec.js` (it already had the working FCC fixture, so one
fixture stays the single source of truth):

- attribute values render, not zeros and not dashes, with the first row pinned exactly
- the opponent logo resolves to an image that actually loaded (`naturalWidth > 0` — a
  broken src still leaves an `<img>` in the DOM, so the element existing proves nothing)
- section gaps are equal within 1px at both densities, and at least 20px
- reopening produces zero blank frames, sampled every `requestAnimationFrame`, and the
  same stamped `<tbody>` comes back, proving the panel was kept rather than rebuilt
- Scouting uses the four new labels and none of the three old ones
- the Prep sub-tabs read Game Plan, Playbooks, Scouting Report, Player Training in that
  order, and clicking the renamed tab shows `#training-view`

Updated for the eleven-measure and rename changes: `polish-team.spec.js`,
`t2-roster.spec.js`, `test_team_attribute_measures.py`, `test_team_measure_ranks.py`,
`shell-1.spec.js`, `shell-1b.spec.js`, `shell-2.spec.js`, `subtabs.spec.js`.

Not added, because the feature is not built: the Player Training save / toast / persist /
leave-check tests.

## Gate

**pytest — 0 failed.** 4045 passed, 20 skipped, 109 xfailed, 1 xpassed.
One test (`test_loopback_profile.py::test_prove_pool_cli_exits_clean`) failed only under
the tool sandbox with `sqlite3.OperationalError: unable to open database file`; re-run
unsandboxed it passes 11/11.

**Full Playwright** — `--workers=1`, port 8157, CI unset, started only after `ps` showed
the other agent's run (from `gob-audit`, port 8791) had finished: **592 passed, 3 skipped,
5 failed** in 18.4m.

Four of the five were my own rename: `shell-1`, `shell-1b`, `shell-2` and `subtabs` each
pinned the literal label "Training". Updated and re-run: **42 passed**.

The fifth, `app-router.spec.js › rankings opens in place`, is **not mine**. It looks for
`#rankings-view.tab-content.active`. I verified it by stashing every one of my frontend
changes and running it again — it still fails. That is the Rankings / gobViews history work
another agent owns.

## Screenshots

`reports/polish-prep-train-scout/`

- `scouting-report-1280.png`, `-1920.png` — the opponent header with the Four Corners logo
  resolved, and the Projected Starting 5 grid reading 7 8 4 7 9 8 3 4 7 6 7 7 for Reyes
  instead of zeros. Square player badges with initials. Green only in the top-bar Advance
  and in positive data; the RT lockups carry the tier colours. Nothing clipped.
- `scouting-report-lower-1280.png`, `-1920.png` — Team Measures with all eight new labels
  (Offense, Defense, Fast Break, Fast Break Defense, P/T Defense, P/T Offense, Discipline,
  Fight) on neutral white/grey diverging pills, no blue anywhere; then the three-up play
  usage with even gaps above and between. Nothing clipped.
- `player-training-tabs-1280.png` — the Prep tabs reading Game Plan, Playbooks, Scouting
  Report, Player Training with the last one selected, and the full editable settings behind
  it. Top-bar Advance reads "Submit Training" in green. The "0/NaN points" in this shot is
  the stub, not the view: the harness does not serve `/franchise/training-points`.
- `team-attributes-1280.png` — eleven cells, neutral radar, bottom row Chemistry / Fight /
  Discipline with the fourth column empty and no placeholder.

## Self-check

- Colour law holds. Green is only the top-bar Advance and positive data; the radar and the
  measure pills are white tints; no blue outside the RT and attribute tiers; no gold.
- Square headshots: the two live court ones are squared, and the Scouting badges take their
  corner from the shared `.gob .av` atom.
- Tokens only, scoped per view. Every new rule is under `html.gob-shell #scouting-view` or
  `#team-attributes-view`. Nothing global, so no repeat of the `h3` heading leak.
- The embed bridge still works — `trainingView.js` is untouched, and only the label and
  position moved in `gobShell.js`.
- No file owned by another agent was edited. `gobViews.js` and `gobNav.js` are untouched;
  the reorder lives in `gobShell.js`.
- Other briefs' regenerated report images were restored to HEAD (120 of them across the two
  full runs); only `reports/polish-prep-train-scout/` is new.
- GOBToast and `GOBNav.warnOnLeave` were not used, because no editing was added. The
  per-player settings that already exist save on change rather than behind a Save button;
  see question 2 at the end of part 1a.

STATUS: COMPLETE
