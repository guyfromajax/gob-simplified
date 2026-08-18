# Callout copy — editable source

Small pills that appear next to the worm's action point. **Sentence case, conversational** — these
sit close to the line and read as an aside, not a broadcast lower third.

**version: 2026.08.e**

## How to edit

- `###` lines are tiers/categories — leave them alone, the engine matches on the id.
- `-` lines are copy variants. Add, delete, rewrite freely.
- Slots: `{NAME}` `{PTS}` `{REB}` `{AST}` `{STREAK}` `{RUN}` `{TEAM}` `{EDGE}` `{STAT}` `{DEF}` `{CATS}` `{SHOT}`
- `avatar headshot` uses the player portrait; `avatar abbr` uses a tinted tile with the team's
  three-letter abbreviation (there are no square team logos, so no logo is ever used here).
- Wrap the number in `*asterisks*` to bold it — that's the only markup.
- Keep under ~40 characters. These are asides, not headlines.
- Mid/late specials only: milestones ≥20, 10 boards, DD, etc. **Q1–Q2** also fire early
  thresholds (10/5/5) and light ambient bucket/board lines — still subject to cadence gates.
- `gamewinner` is the one exception to the ~40-character rule and to the sentence-case
  rule: it is the loudest moment in the game and holds for 6s rather than 2.6s.

---

### milestone · avatar headshot · gold
- {NAME} has *{PTS}* now
- That's *{PTS}* for {NAME}
- {NAME} up to *{PTS}* points
- *{PTS}* and counting for {NAME}

### boards10 · avatar headshot · gold
- {NAME} has *{REB}* boards
- *{REB}* rebounds for {NAME}

### doubleDouble · avatar headshot · gold
- {NAME} — double-double
- Double-double for {NAME}
- {NAME} hits *{CATS}*

### earlyPts · avatar headshot · gold
- {NAME} already has *{PTS}*
- *{PTS}* early for {NAME}
- {NAME} to *{PTS}* already

### earlyReb · avatar headshot · gold
- {NAME} has *{REB}* boards already
- *{REB}* early boards for {NAME}

### earlyAst · avatar headshot · gold
- {NAME} with *{AST}* dimes already
- *{AST}* assists early for {NAME}

### ambient2 · avatar headshot · green
- {NAME} knocks down a *2*
- {NAME} — that's a *2*
- Bucket for {NAME}

### ambient3 · avatar headshot · green
- {NAME} from deep — *3*
- {NAME} knocks down a *3*
- Three for {NAME}

### ambientBoard · avatar headshot · green
- {NAME} pulls the board
- {NAME} with the rebound
- Board to {NAME}

### streak · avatar headshot · orange
- {NAME} has the last *{STREAK}*
- *{STREAK}* straight for {NAME}

### run · avatar abbr · orange
- {TEAM} on a *{RUN}* run
- *{RUN}* unanswered for {TEAM}

### advantage · avatar abbr · blue
- *+{EDGE}* {STAT} advantage
- {TEAM} up *+{EDGE}* on {STAT}

### disadvantage · avatar abbr · red
- {TEAM} — *+{EDGE}* {STAT} disadvantage
- *+{EDGE}* {STAT} disadvantage for {TEAM}

### defense · avatar headshot · blue
- {NAME} — *{DEF}%* defense
- {NAME} locking up at *{DEF}%*
- *{DEF}%* defense from {NAME}

### clutch · avatar headshot · green
- {NAME} — go-ahead bucket!
- {NAME} puts them up!
- {NAME} — what a shot!
- {NAME} ties it!
- Tied up by {NAME}!

### gamewinner · avatar headshot · gold
- {NAME} — Game Winning Shot!

### fouledout · avatar headshot · red
- {NAME} fouls out
- That's five on {NAME}
