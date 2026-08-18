# Callout copy — editable source

Small pills that appear next to the worm's action point. **Sentence case, conversational** — these
sit close to the line and read as an aside, not a broadcast lower third.

**version: 2026.08.e**

> Design-handoff mirror. Production source of truth: `FrontEnd/static/sim-callout-copy.md`.

## How to edit

- `###` lines are tiers/categories — leave them alone, the engine matches on the id.
- `-` lines are copy variants. Add, delete, rewrite freely.
- Slots: `{NAME}` `{PTS}` `{REB}` `{AST}` `{STREAK}` `{RUN}` `{TEAM}` `{EDGE}` `{STAT}` `{DEF}` `{CATS}` `{SHOT}`
- Mid/late specials only for most tiers. **Q1–Q2** also use `earlyPts` / `earlyReb` / `earlyAst`
  and light `ambient2` / `ambient3` / `ambientBoard` lines — still subject to cadence gates.
- `gamewinner` holds 6s and is the loudest beat.

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
