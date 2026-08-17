// @ts-check
/**
 * recruitingButtonState() — the five secondary-button states, plus the week
 * boundaries and the gated weeks. Pure function, so no DOM and no season needed.
 *
 * Run: npx playwright test tests/e2e/recruiting-button-state.spec.js --project=chromium
 */
const { test, expect } = require('@playwright/test');
const path = require('path');

const {
  recruitingButtonState: stateOf,
  recruitingIsPrompted: isPrompted,
} = require(path.join(__dirname, '../../FrontEnd/static/js/shared/recruitingButtonState.js'));

const NONE = { moved: 0, dropped: 0 };
const EVENTS = { moved: 2, dropped: 1 };

test.describe('passive weeks (1-19, 27-34)', () => {
  test('unseen events -> amber, no pulse, count line', () => {
    for (const week of [1, 7, 19, 27, 34]) {
      const s = stateOf({ week, counts: EVENTS });
      expect(s.visible, `week ${week}`).toBe(true);
      expect(s.line1).toBe('Recruiting');
      expect(s.line2).toBe('2 moved · 1 dropped you');
      expect(s.pulse, `week ${week} must not pulse`).toBe(false);
      expect(s.dead).toBe(false);
    }
  });

  test('nothing new -> hidden', () => {
    for (const week of [1, 7, 19, 27, 34]) {
      expect(stateOf({ week, counts: NONE }).visible, `week ${week}`).toBe(false);
    }
  });

  test('count line omits a zero side rather than printing "0 dropped you"', () => {
    expect(stateOf({ week: 5, counts: { moved: 3, dropped: 0 } }).line2).toBe('3 moved');
    expect(stateOf({ week: 5, counts: { moved: 0, dropped: 2 } }).line2).toBe('2 dropped you');
  });

  test('singular counts still read as counts', () => {
    expect(stateOf({ week: 5, counts: { moved: 1, dropped: 1 } }).line2)
      .toBe('1 moved · 1 dropped you');
  });
});

test.describe('invite window (20-26)', () => {
  const base = { hasSavedBoard: true };

  test('board unsent with events pending -> amber + pulse', () => {
    const s = stateOf({ ...base, week: 21, counts: EVENTS, boardSavedWeek: 20 });
    expect(s.visible).toBe(true);
    expect(s.line2).toBe('2 moved · 1 dropped you');
    expect(s.pulse).toBe(true);
    expect(s.dead).toBe(false);
  });

  test('board unsent with no events -> Invite Wk N of 7, no pulse', () => {
    const cases = { 20: 1, 21: 2, 23: 4, 26: 7 };
    for (const [week, n] of Object.entries(cases)) {
      const s = stateOf({ ...base, week: Number(week), counts: NONE, boardSavedWeek: 0 });
      expect(s.visible, `week ${week}`).toBe(true);
      expect(s.line2, `week ${week}`).toBe(`Invite Wk ${n} of 7`);
      expect(s.pulse).toBe(false);
      expect(s.dead).toBe(false);
    }
  });

  test('board sent this week -> Board sent, is-dead, never pulsing', () => {
    const s = stateOf({ ...base, week: 22, counts: EVENTS, boardSavedWeek: 22 });
    expect(s.visible).toBe(true);
    expect(s.line2).toBe('Board sent');
    expect(s.dead).toBe(true);
    expect(s.pulse).toBe(false);
  });

  test('a board sent in a PRIOR week does not count as sent this week', () => {
    const s = stateOf({ ...base, week: 23, counts: NONE, boardSavedWeek: 22 });
    expect(s.dead).toBe(false);
    expect(s.line2).toBe('Invite Wk 4 of 7');
  });
});

test.describe('gated weeks stand down (green owns the action)', () => {
  test('week 20 with no board hides the secondary — #play-now gates instead', () => {
    expect(stateOf({ week: 20, hasSavedBoard: false, counts: EVENTS }).visible).toBe(false);
  });

  test('week 20 WITH a board keeps the secondary', () => {
    expect(stateOf({ week: 20, hasSavedBoard: true, counts: NONE }).visible).toBe(true);
  });

  test('week 35 hides the secondary', () => {
    expect(stateOf({ week: 35, hasSavedBoard: true, counts: EVENTS }).visible).toBe(false);
  });

  test('no state ever reports itself as gating', () => {
    const weeks = [1, 19, 20, 21, 26, 27, 34, 35];
    for (const week of weeks) {
      for (const counts of [NONE, EVENTS]) {
        for (const hasSavedBoard of [true, false]) {
          const s = stateOf({ week, counts, hasSavedBoard, boardSavedWeek: 0 });
          expect(s.gated, `week ${week}`).toBe(false);
        }
      }
    }
  });
});

test.describe('week boundaries', () => {
  test('19/20 and 26/27 switch behaviour on the right side', () => {
    // 19 is passive: no events -> hidden. 20 is invite: shows the invite counter.
    expect(stateOf({ week: 19, counts: NONE, hasSavedBoard: true }).visible).toBe(false);
    expect(stateOf({ week: 20, counts: NONE, hasSavedBoard: true }).line2).toBe('Invite Wk 1 of 7');
    // 26 is the last invite week; 27 is passive again.
    expect(stateOf({ week: 26, counts: NONE, hasSavedBoard: true }).line2).toBe('Invite Wk 7 of 7');
    expect(stateOf({ week: 27, counts: NONE, hasSavedBoard: true }).visible).toBe(false);
  });

  test('week 34 is the last wire week; 36+ is silent', () => {
    expect(stateOf({ week: 34, counts: EVENTS }).visible).toBe(true);
    expect(stateOf({ week: 36, counts: EVENTS }).visible).toBe(false);
    expect(stateOf({ week: 0, counts: EVENTS }).visible).toBe(false);
  });
});

test.describe('tab badge', () => {
  test('prompted when the button is live', () => {
    expect(isPrompted({ week: 7, counts: EVENTS })).toBe(true);
    expect(isPrompted({ week: 21, counts: NONE, hasSavedBoard: true, boardSavedWeek: 0 })).toBe(true);
  });

  test('not prompted when hidden or spent', () => {
    expect(isPrompted({ week: 7, counts: NONE })).toBe(false);
    expect(isPrompted({ week: 22, counts: EVENTS, hasSavedBoard: true, boardSavedWeek: 22 })).toBe(false);
    expect(isPrompted({ week: 35, counts: EVENTS, hasSavedBoard: true })).toBe(false);
  });
});

test.describe('robustness', () => {
  test('missing input does not throw', () => {
    expect(stateOf(undefined).visible).toBe(false);
    expect(stateOf({}).visible).toBe(false);
    expect(stateOf({ week: 5 }).visible).toBe(false);
  });

  test('negative or junk counts are treated as zero', () => {
    expect(stateOf({ week: 5, counts: { moved: -3, dropped: null } }).visible).toBe(false);
  });
});
