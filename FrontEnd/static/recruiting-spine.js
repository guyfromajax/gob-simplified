/**
 * Recruiting Hub — Spine (D1 / Prompt 0) shared foundation.
 *
 * Vanilla port of the approved React mockups (spine-lean.jsx / spine-phase.jsx).
 * This is the SINGLE source every later recruiting surface consumes — the hub pool,
 * the FCC Recruits tab, the FCC home/coach cards, and the Training Report callout —
 * so the lean object and phase language are identical everywhere ("build as a system").
 *
 * Exposes window.RecruitingSpine = { Lean, Phase, Anchor, rtClassForYear }.
 *
 * Reuses (does NOT fork) the existing shared helpers:
 *   - window.getRecruitRtBucketClassForYear  (js/shared/rtBucket.js)  → recruit RT colors
 *   - window.GOB_PlayerYear                    (js/shared/playerYear.js) → Year formatting
 * Pair with /css/recruiting-spine.css (tokens + component styles) and
 * /css/rt-buckets.css (.rt-low/.rt-mid/.rt-high/.rt-elite colors).
 *
 * Loaded as a classic script (no module export) for both ES-module and IIFE pages.
 */
(function (global) {
  'use strict';

  // ---- small utilities -----------------------------------------------------
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  // 3-letter team token: overlay abbrev when the franchise has one for this team,
  // else alnum slice(0,3). Routes through Common.resolveTeamAbbreviation.
  function deriveAbbr(name, teamId) {
    if (typeof global.resolveTeamAbbreviation === 'function') {
      return global.resolveTeamAbbreviation(name, teamId);
    }
    if (typeof global.deriveTeamAbbreviationFromName === 'function') {
      return global.deriveTeamAbbreviationFromName(name);
    }
    var clean = String(name || '').replace(/[^A-Za-z0-9]/g, '');
    return (clean.slice(0, 3) || '???').toUpperCase();
  }

  // Unified RT color class; the year argument remains for call-site compatibility.
  function rtClassForYear(rt, year) {
    if (typeof global.getRecruitRtBucketClassForYear === 'function') {
      return global.getRecruitRtBucketClassForYear(rt, year);
    }
    return 'rt-unknown';
  }

  // =========================================================================
  // LEAN OBJECT — the Ranked Ladder (mockup variant B)
  // =========================================================================
  var LOCK_SVG =
    '<span class="lb-lock"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4">' +
    '<rect x="5" y="11" width="14" height="10" rx="2"></rect><path d="M8 11V7a4 4 0 0 1 8 0v4"></path></svg></span>';

  var Lean = {
    ODDS: { 1: '≈8×', 2: '≈4×', 3: '≈2×' },
    deriveAbbr: deriveAbbr,

    /**
     * Normalize a backend recruit's ranked Lean object into the spine model.
     * Backend shape: recruit.Lean = { "1": team_id|"open"|null, "2": ..., "3": ... }
     * (see BackEnd/models/franchise_manager.py _build_recruit_lean).
     *
     * opts = { userTeamId, teamNameMap:{id:name}, abbrOf?:(name,id)=>str }
     * Returns { leans:[ {open:true} | {tok, you} ], yourRank, leansToUser, locked }.
     * `locked` is always false for live data (decision: capability only, no live locks —
     * the backend has no loyalty flag; the ladder can render locks but never fabricates one).
     */
    fromBackend: function (recruit, opts) {
      opts = opts || {};
      var raw = (recruit && (recruit.Lean || recruit.lean)) || {};
      var teamNameMap = opts.teamNameMap || {};
      var userId = opts.userTeamId != null ? String(opts.userTeamId) : null;
      var abbrOf = opts.abbrOf || function (name, id) { return deriveAbbr(name, id); };
      var leans = [];
      ['1', '2', '3'].forEach(function (rank) {
        var v = raw[rank];
        if (v == null) return;
        if (v === 'open') { leans.push({ open: true }); return; }
        var tid = String(v);
        var name = teamNameMap[tid] || tid;
        leans.push({ tok: abbrOf(name, tid), you: userId != null && tid === userId });
      });
      var yourIndex = leans.findIndex(function (s) { return s.you; });
      return {
        leans: leans,
        yourRank: yourIndex === -1 ? null : yourIndex + 1,
        leansToUser: yourIndex !== -1,
        locked: false
      };
    },

    /**
     * Normalize a mock SpineData recruit (leans: [{team}|{open}]) into the spine model.
     * Used only by the QA gallery so mock + real render through the identical ladder.
     */
    fromMock: function (rec, teamName, abbrFn) {
      var abbr = abbrFn || deriveAbbr;
      var leans = (rec.leans || []).map(function (s) {
        if (s.open) return { open: true };
        return { tok: abbr(s.team), you: s.team === teamName };
      });
      var yourIndex = leans.findIndex(function (s) { return s.you; });
      return {
        leans: leans,
        yourRank: yourIndex === -1 ? null : yourIndex + 1,
        leansToUser: yourIndex !== -1,
        locked: !!rec.locked
      };
    },

    /** Reduce a model to the single "standing" a row communicates. */
    analyze: function (model) {
      var leans = model.leans || [];
      if (model.locked) {
        var top = leans[0] && leans[0].tok ? leans[0].tok : '—';
        return { standing: 'locked', topRival: top };
      }
      if (model.yourRank === 1) return { standing: 'you1' };
      if (model.yourRank > 1) return { standing: 'list', rank: model.yourRank };
      if (leans.length === 0) return { standing: 'quiet' };
      if (leans.every(function (s) { return s.open; })) return { standing: 'open' };
      return { standing: 'others' };
    },

    /**
     * Ranked-ladder HTML for a normalized model. This markup is the canonical lean
     * object — reuse it verbatim on every surface (Prompt 6 requires byte-for-byte parity).
     */
    ladderHtml: function (model) {
      var leans = (model && model.leans) || [];
      if (!leans.length) {
        return '<span class="lean-b"><span class="lb-empty">No leans yet</span></span>';
      }
      var locked = !!(model && model.locked);
      var slots = leans.map(function (s, i) {
        if (s.open) {
          return '<span class="lb-slot is-open"><span class="rk">' + (i + 1) +
            '</span><span class="lb-tok">open</span></span>';
        }
        var cls = s.you ? (i === 0 ? 'is-you' : 'is-you-list') : '';
        var lock = (locked && i === 0) ? LOCK_SVG : '';
        return '<span class="lb-slot ' + cls + '">' + lock +
          '<span class="rk">' + (i + 1) + '</span>' +
          '<span class="lb-tok">' + esc(s.tok) + '</span></span>';
      });
      return '<span class="lean-b">' + slots.join('') + '</span>';
    }
  };

  // =========================================================================
  // PHASE STRIP — compact indicator + expandable season timeline (calendar-driven)
  // =========================================================================
  var PHASES = {
    passive: { dot: 'passive', nmeta: 'passive', name: 'Passive',
      sub: 'Leans come to you — win games', next: 'Invite Season opens Week 20' },
    invite: { dot: 'live', nmeta: 'live', name: 'Invite Season',
      sub: 'Invite 1 recruit per week', next: 'Signing Day is Week 35' },
    day: { dot: 'payoff', nmeta: 'payoff', name: 'Signing Day',
      sub: '50 points · binding playing-time promises', next: 'Signings post Week 36' },
    results: { dot: 'done', nmeta: 'done', name: 'Results',
      sub: 'Signings are final', next: 'Season complete' }
  };

  // Timeline segments. The 27–34 stretch is Passive mechanics, labeled "Tournament".
  var SEGS = [
    { key: 'passive', cls: 'passive', lo: 1, hi: 19, nm: 'Passive' },
    { key: 'invite', cls: 'invite', lo: 20, hi: 26, nm: 'Invite Season' },
    { key: 'passive', cls: 'passive', lo: 27, hi: 34, nm: 'Tournament' },
    { key: 'day', cls: 'day', lo: 35, hi: 35, nm: 'Signing' },
    { key: 'results', cls: 'results', lo: 36, hi: 36, nm: 'Results' }
  ];

  var CHEVRON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M6 9l6 6 6-6"></path></svg>';
  var INFO = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="12" cy="12" r="9"></circle><path d="M12 11v5M12 7.5v.5"></path></svg>';

  var Phase = {
    PHASES: PHASES,
    SEGS: SEGS,

    /** The phase is chosen by the calendar; the user never picks it. */
    forWeek: function (week) {
      var w = Number(week) || 0;
      for (var i = 0; i < SEGS.length; i++) {
        if (w >= SEGS[i].lo && w <= SEGS[i].hi) return SEGS[i].key;
      }
      return w >= 36 ? 'results' : 'passive';
    },

    /**
     * Full strip markup: the compact bar plus the (collapsed) expandable timeline as
     * ADJACENT SIBLINGS, so the CSS `.pstrip.is-open + .ptl` reveal works. Toggle via bind().
     * opts = { phase, week, inviteSent, points, open }
     */
    stripHtml: function (opts) {
      opts = opts || {};
      var phase = opts.phase || Phase.forWeek(opts.week);
      var p = PHASES[phase] || PHASES.passive;
      var week = opts.week;
      var open = !!opts.open;
      var inviteSent = opts.inviteSent || 0;
      var points = opts.points == null ? 50 : opts.points;

      var counter = '';
      if (phase === 'invite') {
        counter = '<div class="pstrip-counter"><div class="n"><b>' + inviteSent +
          '</b><i> / 7</i></div><div class="cap">Invites sent</div></div>';
      } else if (phase === 'day') {
        counter = '<div class="pstrip-counter"><div class="n"><b>' + points +
          '</b></div><div class="cap">Points left</div></div>';
      }

      var segs = SEGS.map(function (s) {
        var cur = week >= s.lo && week <= s.hi;
        var label = s.lo === s.hi ? ('WK ' + s.lo) : ('WK ' + s.lo + '–' + s.hi);
        return '<div class="ptl-seg ' + s.cls + (cur ? ' is-current' : '') + '">' +
          (cur ? '<span class="ptl-now">Now</span>' : '') +
          '<span class="wk">' + label + '</span><span class="nm">' + esc(s.nm) + '</span></div>';
      }).join('');

      // Weeks 27-34 are Passive mechanics again, but AFTER Invite Season. Asking "why
      // can't I invite yet?" there and pointing at Week 20 sends the player backwards to
      // a week already gone, so the postseason gets its own forward-looking line (the
      // FCC strip already special-cases the same stretch). Both weeks are read off SEGS
      // rather than hardcoded, so moving a segment moves the copy with it.
      var segFor = function (key) {
        for (var i = 0; i < SEGS.length; i++) { if (SEGS[i].key === key) return SEGS[i]; }
        return null;
      };
      var inviteSeg = segFor('invite');
      var daySeg = segFor('day');
      var postseason = phase === 'passive' && inviteSeg && week > inviteSeg.hi;

      var orient;
      if (postseason) {
        orient = '<strong>You\'re in the postseason.</strong> ' +
          (daySeg ? 'Signing Day is Week ' + esc(daySeg.lo) + '.' : esc(p.next) + '.');
      } else if (phase === 'passive') {
        // Both remaining branches state the milestone once, from PHASES[].next — this
        // one used to hardcode "Invites begin Week 20" and append p.next as well, so the
        // week appeared twice and the two halves could drift apart.
        orient = '<strong>Why can\'t I invite yet?</strong> It\'s Week ' + esc(week) +
          '. ' + esc(p.next) + '.';
      } else {
        orient = '<strong>You\'re in ' + esc(p.name) + '.</strong> ' + esc(p.next) + '.';
      }

      return '' +
        '<div class="pstrip' + (open ? ' is-open' : '') + '">' +
          '<div class="pstrip-status">' +
            '<span class="pstrip-phase-dot ' + p.dot + '"></span>' +
            '<span class="pstrip-wk">Week ' + esc(week) + '</span>' +
            '<span class="pstrip-meta">' +
              '<span class="pstrip-name ' + p.nmeta + '">' + esc(p.name) + '</span>' +
              '<span class="pstrip-sub">' + esc(p.sub) + '</span>' +
            '</span>' +
          '</div>' +
          '<div class="pstrip-action">' + counter +
            '<button class="pstrip-expand" type="button">' +
              (open ? 'Hide season' : 'Season') + ' ' + CHEVRON + '</button>' +
          '</div>' +
        '</div>' +
        '<div class="ptl"><div class="ptl-inner">' +
          '<div class="ptl-track">' + segs + '</div>' +
          '<div class="ptl-key">' +
            '<span><i style="background:rgba(74,144,217,.6)"></i>Passive · leans build from results</span>' +
            '<span><i style="background:rgba(52,236,39,.6)"></i>Invite Season · 7 invites</span>' +
            '<span><i style="background:rgba(247,148,32,.7)"></i>Signing Day · 50 points</span>' +
            '<span><i style="background:rgba(255,255,255,.5)"></i>Results · signed</span>' +
          '</div>' +
          '<div class="ptl-orient">' + INFO + '<span>' + orient + '</span></div>' +
          // Visit log sits BELOW the timeline: the timeline says where the season is,
          // this says what the player has spent. Supplied by the caller (the hub owns
          // the data); absent elsewhere, so other phases render the timeline alone.
          (opts.visitsHtml || '') +
        '</div></div>';
    },

    /** Wire the expand button within `container` to toggle the timeline. */
    bind: function (container) {
      if (!container) return;
      var btn = container.querySelector('.pstrip-expand');
      var strip = container.querySelector('.pstrip');
      if (!btn || !strip) return;
      btn.addEventListener('click', function () {
        var open = strip.classList.toggle('is-open');
        btn.childNodes[0].nodeValue = (open ? 'Hide season' : 'Season') + ' ';
      });
    }
  };

  // =========================================================================
  // RECRUIT POOL ANCHOR — persistent header control present in every phase/state
  // =========================================================================
  var Anchor = {
    html: function () {
      return '<button class="hub-anchor" type="button"><span class="ic">◗</span> Recruit Pool</button>';
    },

    /**
     * Bind an anchor button: dismiss any active overlay (later prompts) and scroll to the
     * pool. opts = { poolSelector, onDismiss }.
     */
    bind: function (btn, opts) {
      if (!btn) return;
      opts = opts || {};
      var sel = opts.poolSelector || '.pool-wrap';
      btn.addEventListener('click', function () {
        if (typeof opts.onDismiss === 'function') opts.onDismiss();
        var el = document.querySelector(sel);
        if (el) {
          window.scrollTo({ top: el.getBoundingClientRect().top + window.scrollY - 60, behavior: 'smooth' });
        }
      });
    }
  };

  global.RecruitingSpine = { Lean: Lean, Phase: Phase, Anchor: Anchor, rtClassForYear: rtClassForYear, esc: esc };
})(typeof window !== 'undefined' ? window : this);
