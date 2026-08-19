/**
 * Recruit Visit modal — the recruit visiting the user's team this invite week.
 *
 * Weeks 20-26. Visits are resolved when the player runs training
 * (`_process_weekly_recruiting_invites`), so this lands when they return to the FCC
 * from the training report. Eligibility and once-per-week persistence are
 * server-authoritative via command-center data and
 * /franchise/recruit-visit-modal-seen.
 *
 * A week with no visit produces no payload and no modal: an empty board, or the
 * user's pick losing the prestige-weighted draw, both end the week silently rather
 * than announcing nothing.
 *
 * Mirrors the Walk-On Welcome table exactly, plus one column — Region — because a
 * recruit has a home region and it decides whether he is a realistic target.
 */
(function () {
  'use strict';

  var STYLESHEET_HREF = '/css/walk-on-welcome.css';   // same chrome as the walk-on table
  // Roster-page column order (team-roster-view.js ROSTER_ATTR_KEYS).
  var ATTR_KEYS = ['SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'AG', 'ST', 'ND', 'IQ', 'FT'];

  var presented = false;
  var retryTimer = null;
  var retries = 0;
  var MAX_RETRIES = 300;

  function ensureStylesheetLoaded() {
    if (document.querySelector('link[href="' + STYLESHEET_HREF + '"]')) return;
    var link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = STYLESHEET_HREF;
    document.head.appendChild(link);
  }

  function blockerVisible() {
    return Boolean(document.querySelector(
      '.cm-overlay.is-visible,'
      + '.arch-reveal-overlay.is-visible,'
      + '.afm-overlay.is-visible,'
      + '.gob-talert-overlay,'
      + '.sammy-modal-backdrop.open,'
      + '.bn-overlay.show'
    ));
  }

  function franchiseId() {
    return window.franchiseId || new URLSearchParams(window.location.search).get('franchise_id');
  }

  function markSeen(fid) {
    if (!fid || typeof API_CONFIG === 'undefined') return Promise.resolve();
    return fetch(API_CONFIG.buildUrl('/franchise/recruit-visit-modal-seen'), {
      method: 'PATCH',
      headers: Object.assign(
        { 'Content-Type': 'application/json' },
        API_CONFIG.getAuthHeaders ? API_CONFIG.getAuthHeaders() : {}
      ),
      body: JSON.stringify({ franchise_id: fid }),
    }).catch(function (err) {
      console.warn('[RecruitVisitModal] could not persist seen state:', err);
    });
  }

  function formatHeight(inches) {
    var raw = Number(inches);
    if (!raw || Number.isNaN(raw)) return '--';
    return Math.floor(raw / 12) + "'" + (raw % 12) + '"';
  }

  // Roster page shows attributes on the 0-10 scale and prefers the anchor value.
  function formatAttr(attrs, key) {
    var raw = (attrs || {})['anchor_' + key];
    if (raw == null || raw === '') raw = (attrs || {})[key];
    if (raw == null || raw === '') return '--';
    var num = Number(raw);
    return Number.isNaN(num) ? '--' : Math.floor(num / 10);
  }

  /** Current/potential as letter grades — the pair the roster and pool already show. */
  function formatRtPair(rt, potentialRt) {
    if (typeof formatRtWithPotentialDisplay === 'function') {
      return formatRtWithPotentialDisplay(rt, potentialRt);
    }
    if (typeof formatRtDisplay === 'function') {
      return potentialRt == null
        ? formatRtDisplay(rt)
        : formatRtDisplay(rt) + '/' + formatRtDisplay(potentialRt);
    }
    return rt == null ? '--' : String(rt);
  }

  function rtBucket(rt) {
    return (typeof getRtBucketClass === 'function') ? getRtBucketClass(rt) : '';
  }

  function formatYear(year) {
    if (window.GOB_PlayerYear && typeof window.GOB_PlayerYear.formatDisplay === 'function') {
      return window.GOB_PlayerYear.formatDisplay(year);
    }
    return year || '--';
  }

  function cell(row, text, className) {
    var td = document.createElement('td');
    if (className) td.className = className;
    td.textContent = text;
    row.appendChild(td);
    return td;
  }

  function buildBody(players) {
    var wrap = document.createElement('div');

    var headline = document.createElement('p');
    headline.className = 'wow-headline';
    headline.textContent = 'Hey Coach, here is this week\u2019s invite!';
    wrap.appendChild(headline);

    var tableWrap = document.createElement('div');
    tableWrap.className = 'wow-tablewrap';

    var table = document.createElement('table');
    table.className = 'wow-roster';

    var thead = document.createElement('thead');
    var headRow = document.createElement('tr');
    [
      ['Name', 'wow-name'], ['Pos', ''], ['Yr', ''], ['Ht', ''], ['Wt', 'wow-num'], ['Rgn', '']
    ].concat(ATTR_KEYS.map(function (k) { return [k, 'wow-num']; }))
     .concat([['RT', 'wow-num']])
     .forEach(function (spec) {
       var th = document.createElement('th');
       if (spec[1]) th.className = spec[1];
       th.textContent = spec[0];
       headRow.appendChild(th);
     });
    thead.appendChild(headRow);
    table.appendChild(thead);

    var tbody = document.createElement('tbody');
    players.forEach(function (player) {
      var row = document.createElement('tr');
      var attrs = player.attributes || {};
      cell(row, player.name || '--', 'wow-name');
      cell(row, player.pos || '--');
      cell(row, formatYear(player.year));
      cell(row, formatHeight(player.height));
      cell(row, player.weight == null ? '--' : String(player.weight), 'wow-num');
      cell(row, player.region || '--');
      ATTR_KEYS.forEach(function (key) {
        cell(row, String(formatAttr(attrs, key)), 'wow-num');
      });
      cell(row, formatRtPair(player.rt, player.potential_rt),
        ('wow-num ' + rtBucket(player.rt)).trim());
      tbody.appendChild(row);
    });
    table.appendChild(tbody);

    tableWrap.appendChild(table);
    wrap.appendChild(tableWrap);
    return wrap;
  }

  function schedule(data) {
    if (retryTimer || retries >= MAX_RETRIES) return;
    retryTimer = setTimeout(function () {
      retryTimer = null;
      retries += 1;
      maybeShow(data);
    }, 1000);
  }

  function maybeShow(data) {
    var payload = data && data.recruit_visit_modal;
    if (presented || !payload || !payload.eligible) return;
    var recruit = payload.recruit;
    if (!recruit) return;
    if (blockerVisible()) {
      schedule(data);
      return;
    }

    presented = true;
    ensureStylesheetLoaded();
    var fid = franchiseId();

    Promise.all([
      import('/js/shared/sammyModal.js'),
      import('/js/shared/teamCoachAsset.js'),
    ]).then(function (loaded) {
      var showSammyModal = loaded[0].showSammyModal;
      var getTeamSammyImage = loaded[1].getTeamSammyImage;
      showSammyModal({
        eyebrow: 'Week ' + (payload.week || '') + ' \u00b7 Invite Season',
        body: buildBody([recruit]),
        ctaLabel: 'Go To Recruiting',
        imageSrc: getTeamSammyImage(data.team || ''),
        modalClass: 'is-wide',
        primaryClass: 'is-orange',
        onCta: function () {
          var tab = document.querySelector('[data-tab="recruits-tab"]');
          if (tab) tab.click();
        },
      });
      return markSeen(fid);
    }).catch(function (err) {
      console.error('[RecruitVisitModal] failed to show:', err);
    });
  }

  window.RecruitVisitModal = { maybeShow: maybeShow };
})();
