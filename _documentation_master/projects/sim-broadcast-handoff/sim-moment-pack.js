/* GOB — Moment template pack. DATA, not code: versioned, swappable, no runtime generation.
   Slots: {NAME} {TEAM} {PTS} {REB} {AST} {FGM} {FGA} {LAST} {RUN} {STREAK}
   Voice rules: numbers carry the weight, no adjectives, never assert causation, max ~34 chars. */
window.MOMENT_PACK = {
  version: '2026.08.a',
  categories: {
    bucket: { tag: 'BUCKET', color: 'green', lines: [
      '{NAME} {PTS} PTS',
      '{NAME} UP TO {PTS}',
      '{LAST} MORE — {NAME} AT {PTS}',
      '{NAME} {PTS} ON {FGM}-{FGA}',
      '{NAME} ANSWERS · {PTS}',
      'THAT MAKES {PTS} FOR {NAME}',
      '{NAME} {PTS} AND CLIMBING'
    ]},
    three: { tag: '3PM', color: 'green', lines: [
      '{NAME} FROM THREE · {PTS}',
      '{NAME} {PTS} PTS · 3 OF THOSE DEEP',
      'DEEP {NAME} — {PTS}',
      '{NAME} SPACES IT · {PTS} PTS',
      '{NAME} {FGM}-{FGA}, NOW {PTS}'
    ]},
    paint: { tag: 'PAINT', color: 'green', lines: [
      '{NAME} INSIDE · {PTS}',
      '{NAME} {PTS} PTS, {REB} REB',
      'PAINT TOUCH — {NAME} {PTS}',
      '{NAME} FINISHES · {PTS} PTS'
    ]},
    board: { tag: 'BOARD', color: 'blue', lines: [
      '{NAME} {REB} REB',
      '{NAME} UP TO {REB} BOARDS',
      '{REB} FOR {NAME}',
      '{NAME} {REB} REB, {PTS} PTS',
      '{NAME} CLEANS IT · {REB}'
    ]},
    dime: { tag: 'DIME', color: 'blue', lines: [
      '{NAME} {AST} AST',
      '{NAME} UP TO {AST} DIMES',
      '{AST} ASSISTS FOR {NAME}',
      '{NAME} {AST} AST, {PTS} PTS'
    ]},
    stock: { tag: 'STOCK', color: 'blue', lines: [
      '{NAME} TAKES IT AWAY',
      '{NAME} BLOCKS IT · {PTS} PTS',
      'BALL BACK — {NAME}',
      '{NAME} DISRUPTS IT'
    ]},
    milestone10: { tag: 'DOUBLE FIGURES', color: 'gold', lines: [
      '{NAME} REACHES 10',
      '{NAME} IN DOUBLE FIGURES',
      '10 FOR {NAME}'
    ]},
    milestone20: { tag: '20', color: 'gold', lines: [
      '{NAME} HITS 20',
      '20 PTS · {NAME}',
      '{NAME} 20 ON {FGM}-{FGA}'
    ]},
    milestone30: { tag: '30', color: 'gold', lines: [
      '{NAME} HITS 30',
      '30 PTS · {NAME}'
    ]},
    doubleDouble: { tag: 'DOUBLE-DOUBLE', color: 'gold', lines: [
      '{NAME} {PTS} AND {REB}',
      '{NAME} DOUBLE-DOUBLE · {PTS}/{REB}',
      '{NAME} {PTS} PTS, {REB} REB'
    ]},
    boards10: { tag: '10 REB', color: 'gold', lines: [
      '{NAME} 10 BOARDS',
      '{NAME} REACHES 10 REB'
    ]},
    streak: { tag: 'STREAK', color: 'orange', lines: [
      '{NAME} {STREAK} STRAIGHT',
      '{NAME} LAST {STREAK} POINTS',
      '{STREAK} IN A ROW — {NAME}'
    ]},
    cold: { tag: 'COLD', color: 'red', lines: [
      '{NAME} {FGM}-{FGA}',
      '{NAME} STILL {FGM} OF {FGA}',
      '{NAME} {PTS} PTS ON {FGA} SHOTS'
    ]},
    foul: { tag: 'FOUL', color: 'red', lines: [
      '{NAME} PICKS UP HIS {LAST}',
      '{NAME} — FOUL {LAST}',
      '{LAST} ON {NAME}'
    ]},
    run: { tag: 'RUN', color: 'orange', lines: [
      '{TEAM} {RUN}',
      '{TEAM} ON A {RUN} RUN',
      '{RUN} — {TEAM}'
    ]}
  },
  /* Context cards juxtapose the coach's own setting against the outcome. No claim, no causation. */
  context: [
    { setting: 'AGGRESSION', value: 'HIGH', stat: 'TEAM FOULS', now: '11', base: 'you avg 7.4', league: 'league 8.1' },
    { setting: 'TEMPO', value: 'FAST', stat: 'TURNOVERS', now: '14', base: 'you avg 9.6', league: 'league 11.2' },
    { setting: 'GAME PLAN', value: 'INSIDE OUT', stat: 'PTS IN PAINT', now: '26', base: 'you avg 30.1', league: 'league 27.4' },
    { setting: 'TEMPO', value: 'FAST', stat: 'FAST BREAK', now: '17', base: 'you avg 11.0', league: 'league 9.3' }
  ]
};
