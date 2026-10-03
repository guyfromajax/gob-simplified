# QA play-through — staging eye test — 2026-10-01

Covers everything that changed on `develop` **Sep 30 – Oct 1 2026**. Two audiences:
- **Part A** — Jamie's eye-test checklist (step → click → expect → colour to eyeball).
- **Part B** — a self-contained copy-paste brief for an external QA agent (Grok) on staging.
- **Part C** — offline desktop checks.

> **Use a FRESH franchise.** The old staging league is compromised — start a brand-new
> franchise and play forward; do not resume the old save.

**Staging** = the Netlify deploy of `develop` (frontend) + its Railway backend.
Fill in before running: `STAGING_URL = <paste the develop Netlify URL>`.

---

## Colour law cheat-sheet (eyeball these everywhere)

| Colour | Means | Allowed on | NOT allowed on |
|---|---|---|---|
| **Green** (`#34EC27`) | Advance / positive data | the **Advance** button; positive stat deltas | Save buttons, choice toggles, generic CTAs |
| **Orange** (`#F79420`) | **unsaved / dirty** | a Save button **only while there are unsaved changes** | anything at rest, anything already saved |
| **Navy** (`#27408E`) | **"yours"** | your team / your picks / your row | other teams, neutral chrome |
| **Neutral** (grey/white) | choice & chrome | toggles, tabs, chips, segmented controls | — |
| **Gold** (`#F0C560`) | reward / tribute | senior tribute marks, reward badges | ordinary UI |
| **Team colours** | team identity | logos, team edge borders | background washes of panels/rows |
| **Game-state** (court) | live data | RT ramp, momentum bars, has-ball/defender/AUDIBLE highlights, scoreboard pips | — (exempt; do **not** flag) |

Rule of thumb: **green = Advance only, orange = unsaved only, navy = yours.** If a colour isn't
carrying one of those meanings, it should be neutral.

---

## What changed Sep 30 – Oct 1 (so you know where to look)

- **Court (court.html):** scoreboard / start-prompt / controls + side panels on design tokens;
  **side panels now navy** (were grey), **stat toggles neutral** (were team-orange), live
  game-state colours kept as data.
- **Overlays:** game-completion, foul-out, defense-matchups, press-conference, POTG on tokens.
- **Screens on tokens + colour law:** box score, practice-squad, Set Lineup, Game Plan,
  Scouting, Playbooks / training-playbooks, player detail, program (team) select, auth pages
  (login/signup/reset), FAQ/legal, 404/maintenance, auth bar, page-load overlay, error screens,
  mode-select, community (archetypes, leaderboard, account), tutorials/FTE/Sammy.
- **Save states:** Save buttons are **neutral at rest, orange only when dirty**.
- **Team logos:** `logo_square` falls back to `logo_primary` → **0 team-art 404s**.
- **Flow / correctness:** week-1 practice-squad Submit works (confirm on top, silent disabled
  buttons); standalone training = Advance focus page + titled report; **championship / milestone
  moments are consumed on show (appear once)**; FCC shows a retryable "couldn't load" card;
  logo/standings leaders empty-state cards.
- **Dead code / tabs removed:** account-settings modal, Sammy inline ring, dev-sim popup, old
  `#standings-tab` panel (stale links remap to League › Standings), twin pages (homepage-v3,
  play-builder v1) removed with redirects.
- **Desktop:** app icon wired (icns/ico/png); splash/crash/menu on the design system, fully local.

---

## Part A — Jamie eye-test checklist

Play one franchise from creation through a conference tournament. Per step: **do** → **expect**
→ **colour**.

### 1 · Entry & auth
| Do | Expect | Colour |
|---|---|---|
| Open `STAGING_URL` | Homepage paints on dark tokens; no flash of unstyled chrome | auth bar + footer neutral; primary CTA per law |
| Sign up / log in; visit reset-password, FAQ, a legal page | All on the dark token palette; forms legible | inputs/links neutral; no stray team washes |
| Hit a bad URL (e.g. `/nope`) | Custom **404** on tokens (not a raw page) | neutral |

### 2 · New franchise → program (team) select
| Do | Expect | Colour |
|---|---|---|
| Start a **new franchise** | Mode select shows **Franchise** as the live product (Tournament / Single game are sunset) | neutral choice tiles |
| Choose your program/team (`franchise-select-team`) | Team cards with logos, no broken art | **your** selection reads **navy**; other teams neutral/team-identity only |

### 3 · Team builder
| Do | Expect | Colour |
|---|---|---|
| Build/confirm your team (`team-builder.html`) | Page on tokens; position & category chips are **choice** controls | chips **neutral**; **Continue** primary CTA — confirm it reads per law (not an off-law colour); your team identity may show navy |
| Watch the boot | No crash / blank on draft-resume | — |

### 4 · Tutorials / FTE / Sammy
| Do | Expect | Colour |
|---|---|---|
| Walk the first-time tutorials; trigger Sammy reminder | Tutorial pages + Sammy modal on tokens; Sammy ring painted from CSS (no inline ring) | neutral chrome; any "positive" callout green only if it's a positive-data/Advance beat |

### 5 · Office (Franchise Command Center)
| Do | Expect | Colour |
|---|---|---|
| Land in the Office (`franchise-command-center`) | FCC renders; **Advance** present | **Advance green**; everything else neutral/navy-for-yours |
| (If a load error is simulated) | A **"couldn't load your season"** card with **Retry**; Advance disabled with a reason | neutral error card |

### 6 · Week 1 practice-squad assignment
| Do | Expect | Colour |
|---|---|---|
| Assign the practice squad; press **Submit** | Submit works; confirm modal sits **above** the focus chrome; disabled buttons are dead (no sound, no action) | Submit neutral at rest; no green |

### 7 · Set Lineup
| Do | Expect | Colour |
|---|---|---|
| Open **Set Lineup** (`set-lineup.html`) | **Starters are empty by design**; a banner explains it | neutral |
| Press **Autoset Lineup** | Fills starters (best scorers to high-shot spots); stat columns align, no overlap | **Autoset** neutral; **Advance** green |

### 8 · Play the game
| Do | Expect | Colour |
|---|---|---|
| Pre-game: set **defense matchups** / game plan, Tip Off | Defense-matchups popup on tokens; tip-off proceeds | submit CTAs per law; **Advance/Tip Off** green |
| In-court: open the **side panels** | **Panels are navy** (`--surface-2`), not grey `#1a1a1a` | navy surfaces; team **edge border** may stay team-colour (identity) |
| Toggle the **stat toggles** (S1/S2/S3, team toggle) | Selected toggle is **neutral** (translucent white), **not team-orange** | neutral selected state |
| Watch live play | RT ramp, momentum bars, has-ball/defender/AUDIBLE highlights, scoreboard pips | these are **game-state data — do not flag** |
| End-of-game overlays: completion, POTG, foul-out, press conference | All on tokens; POTG radius correct; assigning modal neutral | positive beats green only as data/Advance |

### 9 · Box score
| Do | Expect | Colour |
|---|---|---|
| Open the **box score** (`box-score.html`) | Renders; **Back** link returns correctly; cut-player rows handled | neutral; stat deltas green only as positive data |

### 10 · Training week
| Do | Expect | Colour |
|---|---|---|
| Press **Advance** into the training week | Lands on the standalone **training page** (pip-only rows) | **Advance green** |
| Set training, press **Submit** | Submit commits; then a **titled Training Report** | Submit neutral→(orange only if it tracks dirty); report neutral |

### 11 · Game Plan / Playbooks save states
| Do | Expect | Colour |
|---|---|---|
| Open Game Plan / Playbooks; **don't** change anything | **Save is neutral** (nothing to save) | neutral |
| Change something | **Save turns orange** (dirty) | orange = unsaved |
| Press Save | Save returns to **neutral** (saved) | not orange, not green |

### 12 · League
| Do | Expect | Colour |
|---|---|---|
| Open League → Standings, Leaders | **No 404s on team logos** (square→primary fallback); standings render; empty leaders show a **shared empty-state card** (not a blank) | your team row **navy**; others team-identity only |
| Follow an old `#standings-tab` style link | Remaps to **League › Standings** (no dead tab) | — |

### 13 · Recruiting
| Do | Expect | Colour |
|---|---|---|
| Open **Recruiting** (`recruiting.html`) | Hub renders on the phase-aware spine (Bebas Neue Pro type) | your picks/leans **navy**; choice chips neutral |

### 14 · Championship moment — appears ONCE
| Do | Expect | Colour |
|---|---|---|
| Win a regular-season championship/milestone | A **title takeover** mounts once → **Go To Locker Room** | reward/tribute gold where applicable |
| Exit to Box score, navigate around, **reload** | The moment **does not re-show** (consumed on mount) | — |

### 15 · Conference tournament
| Do | Expect | Colour |
|---|---|---|
| Advance into the conference tournament | Bracket renders; play through | your team **navy** in the bracket |
| Re-win / revisit | **No repeat** of the earlier championship moment | — |

### 16 · Community / account / auth
| Do | Expect | Colour |
|---|---|---|
| Open Account, Coaching Archetypes, Archetypes Leaderboard | All on tokens; **no** account-settings modal (removed); gear opens settings directly | neutral; your rows navy |

---

## Part B — Copy-paste brief for the external QA agent (Grok)

> Paste everything between the lines. It is self-contained.

```
ROLE: You are QA-testing a web basketball-coaching sim (Franchise mode) on its STAGING build.
Frontend is a Netlify deploy; backend is Railway. Work only on staging.

STAGING_URL = <PASTE THE STAGING URL HERE>
ACCOUNT = <paste test login, or sign up a fresh account>

CRITICAL: Start a BRAND-NEW franchise and play forward. The old staging league is compromised —
do not load or resume it. If you only see an old save, create a new franchise first.

WHAT TO REPORT: For every step below, write PASS/FAIL + a screenshot. On FAIL, give the exact
URL, what you clicked, what you expected, what happened, and the browser console errors (open
DevTools). Flag any 404s in the Network tab (especially team-logo images). Note load time if a
page hangs.

COLOUR LAW (check on every screen):
- GREEN is only for the "Advance" button and positive data (e.g. a positive stat change).
  Green on a Save button, a toggle, or a generic button = FAIL.
- ORANGE means "unsaved changes" only. A Save/Submit button may be orange ONLY while there are
  unsaved edits; at rest or after saving it must be neutral (grey/white). Orange anywhere else =
  FAIL.
- NAVY (deep blue) means "this is yours" — your team, your picks, your row. Other teams must not
  be navy-washed.
- Choice controls (tabs, toggles, chips, segmented buttons) are NEUTRAL (grey/white), never a
  team colour.
- Team colours appear only as logos or thin team edge-borders, never as a background wash of a
  panel or row.
- EXCEPTION — the live game court: the shifting colours during play (energy/"RT" ramps, momentum
  bars, the gold has-ball/defender/AUDIBLE highlights, scoreboard clock/quarter pips) are DATA.
  Do NOT flag those.

STEP-BY-STEP (do them in order, one fresh franchise):

1. ENTRY/AUTH: Open STAGING_URL. Sign up / log in. Visit reset-password, an FAQ page, a legal
   page, and a bad URL (e.g. /nope). EXPECT: dark themed pages, no unstyled flashes, a custom
   404 (not a raw error). Forms and links neutral.

2. NEW FRANCHISE → TEAM SELECT: Create a new franchise. EXPECT: "Franchise" is the live mode
   (other modes are retired). Pick your program/team. EXPECT: team cards with logos (no broken
   images); YOUR pick highlights navy.

3. TEAM BUILDER: Build/confirm your team. EXPECT: page themed; position/category chips are
   NEUTRAL; the primary "Continue" button follows the colour law; no crash when the page loads
   or when resuming a draft.

4. TUTORIALS/SAMMY: Go through the first-time tutorials and the "Sammy" helper prompt. EXPECT:
   themed tutorial pages and helper modal; no broken layout.

5. OFFICE (command center): Reach the main franchise Office screen. EXPECT: it loads; the
   "Advance" button is GREEN; everything else neutral or navy-for-yours. If a load ever fails,
   EXPECT a "couldn't load your season" card with a Retry button (not a blank page).

6. WEEK-1 PRACTICE SQUAD: Assign the practice squad and press Submit. EXPECT: it submits; the
   confirmation modal appears ON TOP of the page; disabled buttons do nothing and make no sound.

7. SET LINEUP: Open Set Lineup. EXPECT: starters start EMPTY ON PURPOSE (a banner says so).
   Press "Autoset Lineup". EXPECT: starters fill in; columns line up with no overlapping text.
   "Autoset" is neutral; "Advance" is green.

8. PLAY A GAME: Set defense matchups / game plan pre-game, then Tip Off. During the game open
   the side stat panels. EXPECT: panels have a NAVY background (not grey); the stat toggles,
   when selected, are NEUTRAL (translucent white), NOT orange/team-colour. Team-colour may appear
   only as a thin edge border. Let the game finish. EXPECT: end-of-game overlays (final box /
   completion, Player of the Game, foul-out, press conference) all themed and readable.

9. BOX SCORE: Open the box score. EXPECT: it renders; the Back link returns you correctly; any
   cut players are handled without errors.

10. TRAINING WEEK: Press Advance into the training week. EXPECT: a dedicated training page.
    Set training and Submit. EXPECT: a titled Training Report afterwards. "Advance" green;
    Save/Submit neutral unless there are unsaved edits.

11. SAVE STATES: Open Game Plan and Playbooks. With NO changes, the Save button is NEUTRAL.
    Make a change → Save turns ORANGE. Press Save → it goes back to NEUTRAL. FAIL if Save is
    orange with nothing changed, or green at any time.

12. LEAGUE: Open League → Standings and Leaders. EXPECT: NO 404s on any team logos (check the
    Network tab). Standings render; if leaders are empty, a tidy "empty" card shows (not a blank
    gap). Your team's row is navy.

13. RECRUITING: Open Recruiting. EXPECT: the hub loads; your leans/picks show navy; choice chips
    neutral.

14. CHAMPIONSHIP MOMENT (appears ONCE): Win a regular-season championship/milestone. EXPECT: a
    full-screen title "takeover" appears ONE time, then a "Go To Locker Room" button. Now go to
    the Box score, click around, and RELOAD the page. EXPECT: the moment does NOT appear again.
    FAIL if it re-shows.

15. CONFERENCE TOURNAMENT: Advance into the conference tournament. EXPECT: the bracket renders;
    your team is navy. Play/revisit. EXPECT: the earlier championship moment does NOT repeat.

16. COMMUNITY/ACCOUNT: Open Account, Coaching Archetypes, and the Archetypes Leaderboard.
    EXPECT: all themed; there is NO pop-up "account settings" modal (removed) — the gear opens
    settings directly; your rows are navy.

Deliver a numbered PASS/FAIL list matching steps 1–16, each with a screenshot and any console /
network errors.
```

---

## Part C — Offline desktop app checks

| Do | Expect |
|---|---|
| Launch the packaged desktop app | Boots offline (SQLite); no remote-URL calls for shell assets |
| Check the **app icon** | Dock/taskbar/window show the GOB icon (macOS rounded with ~10% margin; Windows multi-res) — not the default Electron icon |
| Watch the **splash** | Themed splash with local fonts/logo; on an engine crash the **error screen** reads "The game engine stopped" (all local, no `http(s)`/Google-fonts references) |
| Play a game offline | Court, overlays, panels (navy), toggles (neutral) match the web build |

---

## Notes / caveats for the tester
- **Team Builder "Continue" colour** and a few chip rulings were still awaiting Jamie as of
  2026-10-01 — flag what you see rather than assuming a target.
- Some areas are **pre-shell on production** but current on staging; test staging only.
- Everything above is on `develop` (staging). Nothing here is on `main`/production.

STATUS: docs only — checklist + self-contained Grok brief for a fresh-franchise staging pass over
the Sep 30 – Oct 1 changes.
