# Soundtrack System

Two background-music contexts, distinct from the gameplay SFX system in `gameSfx.js`. Both run on loop, hard-cut on start/stop (no fade), and route through their own controller (not the SFX pool) so a long track doesn't sit in a 4-deep audio pool.

## FCC / Franchise Soundtrack

A single track loops across the entire franchise-mode experience. The user can navigate among multiple franchise pages (FCC, standings, rankings, rosters, game plan, etc.) without the music stopping. Persistence across page navigations is implemented via localStorage state because each page is a separate HTML document — a hard navigation tears down the JS context and the `<audio>` element with it.

### Tracks and selection

- `scouting-track-1.mp3` (~3 min)
- `scouting-track-2.mp3` (~4 min)
- **Selection**: a 50/50 random pick happens whenever music starts from an empty state — i.e. the first franchise-mode page visit of a session, or the first visit after a kill point or boundary page wipe. The chosen track then loops continuously across all franchise-mode pages (including round trips through FCC) until killed.

### Persistence model (localStorage)

A small state object lives in localStorage:

```
{ track: <filename>, currentTime: <seconds> }
```

- Each franchise-mode page reads this state on load. If state is present, the page instantiates an `<audio>` element, seeks to `currentTime`, and resumes playback.
- Before every page unload, the page writes the current `audio.currentTime` back to state so the next page picks up cleanly.
- This produces a brief audible gap (50–300 ms) during page transitions while the new page's `<audio>` element loads. Acceptable trade-off for ambient background music; not jarring.

### Page roles

The wiring uses three explicit roles. A page is one of these.

**Opt-in resume pages** — read state on load, resume playback, write state on unload:

- `franchise-command-center.html` — same resume-from-state rule as every other franchise page; only rolls a fresh pick when state is empty. Behaves identically whether the user is arriving for the first time or returning from another franchise page.
- `standings.html`
- `rankings.html`
- `team-roster-view.html` *(crossover: silent if reached pre-franchise via `franchise-select-team.html`, since state will be empty)*
- `game-plan.html`
- `box-score.html` *(crossover: silent if reached from EOG modal, since court.html cleared state upstream)*
- `recruiting.html`
- `recruiting-results.html` *(crossover: silent if reached from `recruiting-orders.js`, since state was cleared at the Advance button upstream)*
- `training-report.html` *(crossover: silent if reached from `training.js`, since state was cleared at the Advance button upstream)*

**Boundary pages** — clear state on load (any music that "leaks in" via direct nav from a music-on page is silenced here):

- `set-lineup.html`
- `court.html`

**Explicit kill points** — click handlers clear state and stop audio before navigating:

- FCC **Play Game** Advance button
- FCC **Run Training** Advance button
- FCC **Run Recruiting** Advance button
- FCC **Exit Franchise** button

**No wiring needed** — these are post-Advance / pre-franchise pages that are silent by default. State is already cleared at the upstream Advance / Exit button, and these pages neither read nor write state.

- `training.html`, `training-playbooks.html`, `recruiting-orders.html` (post-Run Training / Run Recruiting flows)
- `franchise-select-team.html` (pre-franchise selector)

### Start, restart, and resume behavior

- **First franchise-mode page of a session** (typically FCC): no state yet, so a 50/50 random pick happens, plays from the beginning, writes state.
- **Navigating between franchise-mode pages** (any direction, including back to FCC): the destination page reads state and resumes the same track at the stored `currentTime`. Brief audible gap during nav. No re-rolls — the same track threads through the entire session for musical continuity.
- **After a kill point** (Advance / Exit Franchise): state is cleared and music stops. Any later franchise-mode page that reads state sees empty → silent. When the user eventually returns to FCC, the empty-state rule kicks in and a fresh random pick starts again.
- **After a boundary page wipe** (Set Lineup, court.html): same effect as a kill point — state cleared, next FCC visit rolls fresh.
- **Closing the browser**: state persists in localStorage. The next session's first FCC visit will resume mid-track from where the previous session left off (e.g. starts at 2:30 of scouting-track-2). If this proves disorienting in practice, a `timestamp`-based stale-state expiry or `sessionStorage` first-visit detection can be layered in later — not currently implemented.

### Loop

Each track loops continuously (`audio.loop = true`) until killed or until the page navigates away.

## Gameplay Soundtrack (court.html)

Two tracks switch dynamically based on game state. Separate from the FCC soundtrack and its persistence model — gameplay music is fully scoped to court.html.

### Tracks

- **Default — `arcade-pulse-1.mp3`** (~5 min): standard gameplay loop. Plays in Q1–Q3 and the early portion of Q4.
- **Crunch — `pixel-pulse-1.mp3`** (~30 sec): tension loop. Plays whenever the game is in late-Q4 close-and-late or in any overtime quarter.

### Switching rules

A small evaluator runs on court.html entry and after every turn, picking which track should be playing:

- Quarter > 4 (any overtime quarter, OT1+) → **Crunch**.
- Quarter == 4 AND seconds remaining `< 121` AND `|home_score - away_score| <= 6` → **Crunch**.
- Otherwise → **Default**.

The check is **reversible**: every turn re-evaluates from scratch, so a 7+ point swing during late Q4 will hard-cut back from Crunch to Default. Same-track evaluations are no-ops (don't restart, don't disturb a user pause).

Track switches are **hard cuts** (no fade) — consistent with the rest of the music system. The new track plays from `currentTime = 0`.

Constants are at the top of [musicController.js](FrontEnd/static/js/musicController.js): `GAMEPLAY_DEFAULT_TRACK`, `GAMEPLAY_CRUNCH_TRACK`, `CRUNCH_TIME_SECONDS = 121`, `CRUNCH_SCORE_DIFF = 6`.

### Start triggers

Music start is deferred until **after the Defense Matchups modal flow resolves**, with the Q1 Opening Tip carve-out preserved. Concretely:

- **Modal-tied start (default path)**: in `gameScene.js create()`, after the `await showDefenseMatchupsPopup(...)` block, `evaluateGameplayTrack()` fires with quarter + clock + score from URL params.
  - If the modal **renders** (Q1/quarter-break/timeout entry, animate=true, don't-show-again not set): the `await` blocks until the user clicks **Submit Matchups**. Music starts on submit.
  - If the modal **does not render** (don't-show-again is set, animate=false, or `shouldShowMatchupsPopup` is false): the `await` resolves immediately and music starts immediately on court.html entry.
- **Q1 Opening Tip exception**: gated by `if (!isQ1Start)`. Even after the modal submit, music does not start for the opening tip. It waits for the tip-winner SFX (`attack-shot-strong.wav`) which fires in openingTip.js, where `playGameplayTrack()` is called. Q1 opening tip always uses the Default track since score is 0–0 and clock is full.
- **Per-turn re-evaluation**: after every real turn animation, `updateScoreboard(turn)` calls `evaluateGameplayTrack` with the post-turn quarter / clock / score. This is what flips Default ↔ Crunch when conditions change. Skipped on the initial pre-turn scoreboard paint (`isInitialUpdate` flag) so it can't override the modal-tied start moment.
- **Legacy inbound / FT triggers**: the inbound-pass-reception and FT-shooter-ball-take hooks added earlier still call `playGameplayTrack()`. Under the new model, `playGameplayTrack()` is a no-op when any track is already loaded, so these can't accidentally downgrade Crunch back to Default. Kept as defensive belts-and-braces for code paths that might skip the modal-tied start.

### Pause / Resume

- The court.html **Pause** button (id `pause-btn`) pauses the gameplay music alongside tweens and clocks. Implementation: `pauseGameplayTrack()` — pauses the `<audio>` element without resetting `currentTime`.
- The same button when toggled to **Resume** resumes from the paused position. Implementation: `resumeGameplayTrack()` — calls `.play()` on the existing audio element if it's currently paused; no-op otherwise.

### Stop

- Implicit on page unload — the user navigating away from court.html (e.g. to set-lineup.html at a quarter break) tears down the JS context and the audio element with it. No explicit stop call required.

### Restart and loop

- Every fresh start (entry to court.html) plays the track from the beginning (no cross-page resume — gameplay music is fully scoped to a single court.html load).
- Continuous loop while on court.html until paused by the user or the page unloads.

## Mutual Exclusivity

FCC and gameplay music never play at the same time. Enforced by court.html being an FCC-soundtrack **boundary page**: when court.html loads, it clears the FCC localStorage state. So even if a user navigates FCC → ... → court.html directly (without going through the Play Game Advance button), the FCC track is silenced and only the gameplay track plays.

Conversely, the gameplay track is fully scoped to court.html — leaving court.html unloads the audio element. No cross-context bleed in either direction.

## Implementation Notes

- **Do not** register these files in `GAMEPLAY_SFX_FILES` / `playGameSfx`. The SFX pool allocates 4 Audio elements per file at preload, which is wasteful for multi-minute tracks. Use a dedicated music controller that owns one `<audio>` element per active track.
- **Lazy load with `preload = "none"`**: the `<audio>` element is constructed only when needed, and the browser doesn't fetch the bytes until `play()` is called. Avoids burning the page-load budget on multi-MB music files.
- **Hard cut, no fade**: start and stop are abrupt at the trigger moments. Keep the controller simple.
- **Looping**: `audio.loop = true` so the browser handles seamless looping natively (MP3s have a tiny gap at the loop point — fine for these ambient beds).
- **Volume**: 0.4 (lower than SFX 0.7 so it stays under voice/effect stingers). Tune by ear.
- **Audible gap during nav**: 50–300 ms silent gap on every page transition. Acceptable for ambient music; not jarring. The cost of using localStorage-resume instead of an SPA or iframe shell.
- **Autoplay policy**: browsers (Chrome, Safari) block audio until the user has interacted with the page. The first FCC visit after a direct URL load may have music delayed until the user clicks anything. Subsequent navigations within the same tab inherit the gesture context.
- **Mute behavior**: if/when a global mute toggle exists, the music controller should respect it.

## Hook Points

### FCC / Franchise track

- **FCC start (fresh)**: `franchise-command-center.js` init, after `hideFccLoadingOverlay()` in the `finally` block. Always starts fresh; writes state.
- **Opt-in resume on franchise pages**: standings.html, rankings.html, team-roster-view.html, game-plan.html, box-score.html, recruiting.html, recruiting-results.html, training-report.html. Each calls the shared resume helper on load.
- **Boundary state-clear on load**: set-lineup.html, court.html. Each calls the shared clear helper at the top of its page script.
- **Explicit state-clear in handlers**: FCC Play Game / Run Training / Run Recruiting / Exit Franchise button click handlers (see [franchise-command-center.js](FrontEnd/static/franchise-command-center.js)).

### Gameplay track (court.html)

- **Modal-tied start hook**: [gameScene.js](FrontEnd/static/js/phaser/gameScene.js) `create()` — `evaluateGameplayTrack({quarter, clock, homeScore, awayScore})` placed immediately after the `await showDefenseMatchupsPopup(...)` block, gated by `if (!isQ1Start)`. Uses URL params for initial state. Fires either on modal submit or immediately when the modal is skipped.
- **Per-turn re-evaluator**: [gameScene.js](FrontEnd/static/js/phaser/gameScene.js) `updateScoreboard()` — `evaluateGameplayTrack(...)` after `liveQuarter` is set and the clock/score are synced. Fires for every turn.
- **Q1 Opening Tip start**: [openingTip.js](FrontEnd/static/js/phaser/animation/openingTip.js) `animateConvergence` — `playGameplayTrack()` (no args → Default track) right after the `attack-shot-strong.wav` SFX fires. Only fires when the on-load hook was skipped.
- **Legacy inbound start (defensive)**: [turnAnimation.js](FrontEnd/static/js/phaser/animation/turnAnimation.js) at the BIP and SIP `attachBallToPlayer(scene, ballSprite, sfSprite)` lines. No-op since `playGameplayTrack` only starts when nothing is loaded.
- **Legacy FT-shooter start (defensive)**: [FreeThrowAnimationSystem.js](FrontEnd/static/js/phaser/animation/FreeThrowAnimationSystem.js) right after `attachToPlayer(shooterSprite)`. Same no-op guarantee.
- **Pause**: [gameScene.js](FrontEnd/static/js/phaser/gameScene.js) — inside the `pauseBtn` click handler's pause branch, alongside the tween/clock pause calls.
- **Resume**: same handler's resume branch, alongside the tween/clock resume calls.
- **Stop**: implicit on court.html unload — no explicit hook.
