# Soundtrack System

Two background-music contexts, distinct from the gameplay SFX system in `gameSfx.js`. Both run on loop, hard-cut on start/stop (no fade), and route through their own controller (not the SFX pool) so a long track doesn't sit in a 4-deep audio pool.

## FCC / Franchise Soundtrack

A single track loops across the entire franchise-mode experience. The user can navigate among multiple franchise pages (FCC, standings, rankings, rosters, game plan, etc.) without the music stopping. Persistence across page navigations is implemented via localStorage state because each page is a separate HTML document — a hard navigation tears down the JS context and the `<audio>` element with it.

### Tracks and selection

- `scouting-track-1.mp3` (~3 min)
- `scouting-track-2.mp3` (~4 min)
- **Selection**: on each *fresh* FCC visit, pick one of the two tracks 50/50. That same track plays for the entire franchise-mode session until killed.

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

- `franchise-command-center.html` — *special-case*: always starts a fresh random pick (ignores any existing state), then writes new state so downstream pages can resume.
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

- **First FCC visit of a session**: random pick (50/50), play from the beginning, write state.
- **Navigating to another franchise-mode page** (e.g. FCC → Standings): page reads state, resumes the same track at the stored `currentTime`. Brief audible gap during nav.
- **Subsequent FCC visits within the same session** (e.g. Standings → FCC): FCC re-rolls a fresh random pick and starts from the beginning, overwriting state. The user gets a new musical bed every time they return to FCC.
- **After a kill point** (Advance / Exit Franchise): state is cleared. Any later franchise-mode page that reads state sees empty state → silent. When the user eventually returns to FCC, FCC's fresh-pick rule kicks in and music starts again.
- **Closing the browser**: state persists in localStorage but it's irrelevant — the next session's first FCC visit re-rolls fresh anyway.

### Loop

Each track loops continuously (`audio.loop = true`) until killed or until the page navigates away.

## Gameplay Soundtrack (court.html)

A single short track loops in the background throughout live gameplay. Separate from the FCC soundtrack and its persistence model — gameplay music is fully scoped to court.html.

### Track

- `pixel-pulse-1.mp3` (~30 sec)

### Start triggers

- **Opening Tip**: starts immediately after the SFX that fires when the ball attaches to the player who catches the opening tip (`attack-shot-strong.wav` — see Sound_Design_Update.md → Opening Tip SFX).
- **Inbound after timeout / quarter break**: starts when the inbound-pass receiver receives the inbound pass coming out of a timeout or quarter break. (No-op if music is already playing.)
- **Free Throw return**: starts when the free-throw shooter grabs the ball, if play is resuming into a free-throw turn. (No-op if music is already playing.)

### Stop

- Implicit on page unload — the user navigating away from court.html (e.g. to set-lineup.html at a quarter break) tears down the JS context and the audio element with it. No explicit stop call required.

### Restart and loop

- Every start trigger restarts the track from the beginning (no resume).
- Continuous loop while on court.html until the user navigates away.

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

- **Start (Opening Tip)**: [openingTip.js](FrontEnd/static/js/phaser/animation/openingTip.js) `animateConvergence` — right after the `attack-shot-strong.wav` SFX fires.
- **Start (Inbound)**: [turnAnimation.js](FrontEnd/static/js/phaser/animation/turnAnimation.js) — at the BIP and SIP `attachBallToPlayer(scene, ballSprite, sfSprite)` lines.
- **Start (FT shooter)**: [FreeThrowAnimationSystem.js](FrontEnd/static/js/phaser/animation/FreeThrowAnimationSystem.js) — right after `attachToPlayer(shooterSprite)`.
- **Stop**: implicit on court.html unload — no explicit hook.
