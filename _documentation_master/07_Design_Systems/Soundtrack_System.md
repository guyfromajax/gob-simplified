# Soundtrack System

Two background-music contexts, distinct from the gameplay SFX system in `gameSfx.js`. Both run on loop, hard-cut on start/stop (no fade), and route through their own controller (not the SFX pool) so a long track doesn't sit in a 4-deep audio pool.

## FCC Soundtrack (Franchise Command Center)

Two tracks rotate randomly on each FCC visit.

- **Tracks**
  - `scouting-track-1.mp3` (~3 min)
  - `scouting-track-2.mp3` (~4 min)
- **Selection**: on each FCC visit, pick one of the two tracks 50/50. The other does not play that visit.
- **Start trigger**: when the user lands on `franchise-command-center.html` (FCC page load).
- **Stop trigger**: when the user clicks the **Green Action Button** that triggers any of:
  - **Play Game**
  - **Run Training**
  - **Run Recruiting**

  The button kills the music immediately.
- **Restart behavior**: each new FCC visit re-rolls the random pick and starts the chosen track from the **beginning**. No resume from prior playback position.
- **Loop**: the chosen track loops continuously until killed.

## Gameplay Soundtrack (court.html)

A single short track loops in the background throughout live gameplay.

- **Track**
  - `pixel-pulse-1.mp3` (~30 sec)
- **Start triggers**:
  - **Opening Tip**: starts immediately after the SFX that fires when the ball attaches to the player who catches the opening tip (`attack-shot-strong.wav` — see [Sound_Design_Update.md → Opening Tip SFX]).
  - **Inbound after timeout / quarter break**: starts when the inbound-pass receiver receives the inbound pass coming out of a timeout or quarter break.
  - **Free Throw return**: starts when the free-throw shooter grabs the ball, if play is resuming into a free-throw turn.
- **Stop trigger**: when the user leaves `court.html` (e.g. transitions to the set-lineup screen).
- **Restart behavior**: every start trigger restarts the track from the **beginning** (no resume).
- **Loop**: continuous loop while on `court.html` until the stop trigger fires.

## Implementation Notes

- **Do not** register these files in `GAMEPLAY_SFX_FILES` / `playGameSfx`. The SFX pool allocates 4 Audio elements per file at preload, which is wasteful for multi-minute tracks. Use a dedicated music controller that owns one `<audio>` element per active track.
- **Hard cut, no fade** — start and stop are abrupt at the trigger moments. Keep the controller simple.
- **Looping**: set `audio.loop = true` on the element so the browser handles seamless looping natively (note: MP3s have a tiny gap at the loop point — fine for these tracks since they're meant to be continuous beds).
- **Volume**: TBD — propose starting around `0.4–0.5` (lower than SFX `0.7` so it stays under voice/effect stingers). Tune by ear.
- **Mutual exclusivity**: FCC music and gameplay music never play at the same time. The FCC track is killed by the Green Action Button *before* the user reaches `court.html`, so there should be no overlap in practice; no special crossfade logic needed.
- **Mute behavior**: if/when a global mute toggle exists, the music controller should respect it.

## Hook Points (for future implementation)

- **FCC start**: `franchise-command-center.js` page-init / mount sequence.
- **FCC stop (Green Action Button)**: the click handlers for Play Game / Run Training / Run Recruiting. Each of these handlers must call the music controller's `stop()` before navigating away.
- **Gameplay start (Opening Tip)**: [openingTip.js](FrontEnd/static/js/phaser/animation/openingTip.js) `animateConvergence` — same spot where `attack-shot-strong.wav` fires after `attachBallToPlayer(scene, ballSprite, tipWinnerSprite)`. Music starts immediately after the SFX.
- **Gameplay start (Inbound after break)**: the inbound-pass-reception step in the timeout/quarter-break return flow.
- **Gameplay start (FT return)**: the moment the FT shooter takes ball ownership at the start of a free-throw turn.
- **Gameplay stop (leaving court.html)**: scene teardown / route change handler.
