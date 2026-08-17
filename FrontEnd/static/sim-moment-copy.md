# Moment copy — editable source

This file is the source of truth for every line that appears on a card. The broadcast reads it
directly, so edits show up on reload. No code changes needed.

**version: 2026.08.b**

## How to edit

- Each `###` line is a card type. Leave those lines alone (the engine matches on the id).
- Each `-` line under it is one possible line of copy. Add, delete or rewrite freely.
- The engine picks one at random per firing, so more lines = less repetition.
- Keep lines short: **~34 characters** is the limit before the type shrinks.
- Slots get filled with live numbers: `{NAME}` `{PTS}` `{REB}` `{AST}` `{FGM}` `{FGA}` `{LAST}` `{STREAK}` `{TEAM}` `{RUN}`
- Voice: the numbers do the work. No adjectives, never claim causation.
- Note: card lines render in Bebas Neue, which is an all-caps face — write naturally, it will
  display as caps either way. (If you want true sentence case, that's a font change; ask.)

## Tag glossary

| Tag | Fires when |
|---|---|
| BUCKET | any 2-point make — the running points total |
| 3PM | a three goes in |
| PAINT | a made shot in the paint |
| BOARD | a rebound, showing the running total |
| DIME | an assist, showing the running total |
| STOCK | a steal or a block (jargon — say the word if you'd rather) |
| DOUBLE FIGURES | crossing 10 points for the first time |
| 20 / 30 | crossing 20 or 30 points |
| 10 REB | crossing 10 rebounds |
| DOUBLE-DOUBLE | 10+ in two categories |
| STREAK | 6+ straight points by one player |
| COLD | poor shooting line, stated flatly |
| FOUL | 4th or 5th foul only |
| RUN | 8+ unanswered points by one team |
| MARGIN | a team-stat tug promoted to the stage because it's deciding the game |
| CONTEXT | one of your own settings placed next to its outcome |

---

### bucket · tag BUCKET · color green
- {NAME} {PTS} PTS
- {NAME} UP TO {PTS}
- {LAST} MORE — {NAME} AT {PTS}
- {NAME} {PTS} ON {FGM}-{FGA}
- {NAME} ANSWERS · {PTS}
- THAT MAKES {PTS} FOR {NAME}
- {NAME} {PTS} AND CLIMBING

### three · tag 3PM · color green
- {NAME} FROM THREE · {PTS}
- {NAME} {PTS} PTS · 3 OF THOSE DEEP
- DEEP {NAME} — {PTS}
- {NAME} SPACES IT · {PTS} PTS
- {NAME} {FGM}-{FGA}, NOW {PTS}

### paint · tag PAINT · color green
- {NAME} INSIDE · {PTS}
- {NAME} {PTS} PTS, {REB} REB
- PAINT TOUCH — {NAME} {PTS}
- {NAME} FINISHES · {PTS} PTS

### board · tag BOARD · color blue
- {NAME} {REB} REB
- {NAME} UP TO {REB} BOARDS
- {REB} FOR {NAME}
- {NAME} {REB} REB, {PTS} PTS
- {NAME} CLEANS IT · {REB}

### dime · tag DIME · color blue
- {NAME} {AST} AST
- {NAME} UP TO {AST} DIMES
- {AST} ASSISTS FOR {NAME}
- {NAME} {AST} AST, {PTS} PTS

### stock · tag STOCK · color blue
- {NAME} TAKES IT AWAY
- {NAME} BLOCKS IT · {PTS} PTS
- BALL BACK — {NAME}
- {NAME} DISRUPTS IT

### milestone10 · tag DOUBLE FIGURES · color gold
- {NAME} REACHES 10
- {NAME} IN DOUBLE FIGURES
- 10 FOR {NAME}

### milestone20 · tag 20 · color gold
- {NAME} HITS 20
- 20 PTS · {NAME}
- {NAME} 20 ON {FGM}-{FGA}

### milestone30 · tag 30 · color gold
- {NAME} HITS 30
- 30 PTS · {NAME}

### doubleDouble · tag DOUBLE-DOUBLE · color gold
- {NAME} {PTS} AND {REB}
- {NAME} DOUBLE-DOUBLE · {PTS}/{REB}
- {NAME} {PTS} PTS, {REB} REB

### boards10 · tag 10 REB · color gold
- {NAME} 10 BOARDS
- {NAME} REACHES 10 REB

### streak · tag STREAK · color orange
- {NAME} {STREAK} STRAIGHT
- {NAME} LAST {STREAK} POINTS
- {STREAK} IN A ROW — {NAME}

### cold · tag COLD · color red
- {NAME} {FGM}-{FGA}
- {NAME} STILL {FGM} OF {FGA}
- {NAME} {PTS} PTS ON {FGA} SHOTS

### foul · tag FOUL · color red
- {NAME} PICKS UP HIS {LAST}
- {NAME} — FOUL {LAST}
- {LAST} ON {NAME}

### run · tag RUN · color orange
- {TEAM} {RUN}
- {TEAM} ON A {RUN} RUN
- {RUN} — {TEAM}

### context
<!-- format: SETTING | VALUE | STAT | NOW | your baseline | league baseline -->
- AGGRESSION | HIGH | TEAM FOULS | 11 | you avg 7.4 | league 8.1
- TEMPO | FAST | TURNOVERS | 14 | you avg 9.6 | league 11.2
- GAME PLAN | INSIDE OUT | PTS IN PAINT | 26 | you avg 30.1 | league 27.4
- TEMPO | FAST | FAST BREAK | 17 | you avg 11.0 | league 9.3
