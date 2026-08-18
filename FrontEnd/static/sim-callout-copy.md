# Callout copy — editable source

Small pills that appear next to the worm's action point. **Sentence case, conversational** — these
sit close to the line and read as an aside, not a broadcast lower third.

**version: 2026.08.d**

## How to edit

- `###` lines are tiers/categories — leave them alone, the engine matches on the id.
- `-` lines are copy variants. Add, delete, rewrite freely.
- Slots: `{NAME}` `{PTS}` `{REB}` `{AST}` `{STREAK}` `{RUN}` `{TEAM}` `{EDGE}` `{STAT}` `{DEF}` `{CATS}`
- `avatar headshot` uses the player portrait; `avatar abbr` uses a tinted tile with the team's
  three-letter abbreviation (there are no square team logos, so no logo is ever used here).
- Wrap the number in `*asterisks*` to bold it — that's the only markup.
- Keep under ~40 characters. These are asides, not headlines.
- Only **special** moments earn a callout. Routine buckets, rebounds and assists do not.

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

### fouledout · avatar headshot · red
- {NAME} fouls out
- That's five on {NAME}
