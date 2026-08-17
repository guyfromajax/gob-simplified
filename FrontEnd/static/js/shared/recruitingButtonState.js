/**
 * Secondary hero button state — pure, so all five states are testable without a DOM.
 *
 * Reporting only: reads the Prompt 1 event log counts and the board markers, changes
 * no recruiting mechanic.
 *
 * Colour law (Styleguide): green is reserved for the GATING action. This button is
 * always skippable, so it is always amber. Recruiting only turns green when it
 * becomes #play-now itself — the week-20 no-board gate and week 35 — which is
 * updatePlayButton's job, not this function's.
 *
 *   recruitingButtonState({ week, boardSavedWeek, hasSavedBoard, counts })
 *     -> { visible, line1, line2, pulse, dead, gated }
 *
 * Loaded as a classic script (window.GOB_RecruitingButtonState) and also exported
 * for node-based unit tests.
 */
(function (global) {
  'use strict';

  var INVITE_FIRST_WEEK = 20;
  var INVITE_LAST_WEEK = 26;
  var INVITE_WEEK_COUNT = 7; // weeks 20-26 inclusive
  var WIRE_LAST_WEEK = 34;   // matches LEAN_MOVEMENT_LAST_WEEK on the backend
  var SIGNING_WEEK = 35;

  var HIDDEN = Object.freeze({
    visible: false, line1: '', line2: '', pulse: false, dead: false, gated: false,
  });

  /** "2 moved · 1 dropped you" — a count, never a bare noun. */
  function countLine(counts) {
    var moved = Math.max(0, Number((counts && counts.moved) || 0));
    var dropped = Math.max(0, Number((counts && counts.dropped) || 0));
    var parts = [];
    if (moved > 0) parts.push(moved + ' moved');
    if (dropped > 0) parts.push(dropped + ' dropped you');
    return parts.join(' · ');
  }

  function hasUnseen(counts) {
    return countLine(counts) !== '';
  }

  function state(input) {
    var opts = input || {};
    var week = Number(opts.week || 0);
    var counts = opts.counts || {};
    var boardSavedWeek = Number(opts.boardSavedWeek || 0);
    var hasSavedBoard = !!opts.hasSavedBoard;

    // Gated weeks belong to #play-now, so the secondary button stands down rather
    // than competing with the green action.
    if (week === SIGNING_WEEK) return HIDDEN;
    if (week === INVITE_FIRST_WEEK && !hasSavedBoard) return HIDDEN;

    var inviteWindow = week >= INVITE_FIRST_WEEK && week <= INVITE_LAST_WEEK;

    if (inviteWindow) {
      // Board already sent this week: still present, visibly spent.
      if (boardSavedWeek === week) {
        return {
          visible: true, line1: 'Recruiting', line2: 'Board sent',
          pulse: false, dead: true, gated: false,
        };
      }
      if (hasUnseen(counts)) {
        return {
          visible: true, line1: 'Recruiting', line2: countLine(counts),
          pulse: true, dead: false, gated: false,
        };
      }
      return {
        visible: true, line1: 'Recruiting',
        line2: 'Invite Wk ' + (week - INVITE_FIRST_WEEK + 1) + ' of ' + INVITE_WEEK_COUNT,
        pulse: false, dead: false, gated: false,
      };
    }

    // Passive weeks (1-19, 27-34): the button exists only when there is news.
    if (week >= 1 && week <= WIRE_LAST_WEEK && hasUnseen(counts)) {
      return {
        visible: true, line1: 'Recruiting', line2: countLine(counts),
        pulse: false, dead: false, gated: false,
      };
    }
    return HIDDEN;
  }

  /**
   * True when the Recruiting TAB should carry .inbox-badge. Prompted means the
   * player is being asked for something: unsent board in the invite window, or
   * unseen wire events. A spent board is not a prompt.
   */
  function isPrompted(input) {
    var result = state(input);
    if (!result.visible || result.dead) return false;
    return true;
  }

  var api = {
    recruitingButtonState: state,
    recruitingIsPrompted: isPrompted,
    recruitingCountLine: countLine,
    INVITE_FIRST_WEEK: INVITE_FIRST_WEEK,
    INVITE_LAST_WEEK: INVITE_LAST_WEEK,
    WIRE_LAST_WEEK: WIRE_LAST_WEEK,
    SIGNING_WEEK: SIGNING_WEEK,
  };

  if (global) {
    global.GOB_RecruitingButtonState = api;
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : null));
