/**
 * Walk-On Welcome modal — season-start reveal of the walk-ons who joined the
 * user's roster.
 *
 * Season 2+ only. The server writes its payload during finish_season and clears
 * it on dismiss, so Season 1 (which never runs a rollover) can never arm it —
 * that's what keeps this out of the crowded first-time-experience flow rather
 * than a client-side season check.
 *
 * Eligibility and once-per-season persistence are server-authoritative through
 * command-center data and /franchise/walk-on-welcome-modal-seen. A season that
 * signed a full class produces no walk-ons and no payload, so nothing shows.
 *
 * Moment Modal (Styleguide §Modal System) on the shared Sammy chrome:
 * .is-wide because the roster table cannot compress to the 520px default, and
 * .is-orange because "Go To Locker Room" navigates rather than gates.
 */
(function () {
  'use strict';

  var STYLESHEET_HREF = '/css/walk-on-welcome.css';
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
    return fetch(API_CONFIG.buildUrl('/franchise/walk-on-welcome-modal-seen'), {
      method: 'PATCH',
      headers: Object.assign(
        { 'Content-Type': 'application/json' },
        API_CONFIG.getAuthHeaders ? API_CONFIG.getAuthHeaders() : {}
      ),
      body: JSON.stringify({ franchise_id: fid }),
    }).catch(function (err) {
      console.warn('[WalkOnWelcomeModal] could not persist seen state:', err);
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

  function buildBody(walkOns) {
    var wrap = document.createElement('div');

    var headline = document.createElement('p');
    headline.className = 'wow-headline';
    headline.textContent = 'Welcome to the season, Coach.';
    wrap.appendChild(headline);

    var sub = document.createElement('p');
    sub.className = 'wow-sub';
    sub.textContent = "Here are this season's walk-ons.";
    wrap.appendChild(sub);

    var tableWrap = document.createElement('div');
    tableWrap.className = 'wow-tablewrap';

    var table = document.createElement('table');
    table.className = 'wow-roster';

    var thead = document.createElement('thead');
    var headRow = document.createElement('tr');
    [
      ['Name', 'wow-name'], ['Pos', ''], ['Yr', ''], ['Ht', ''], ['Wt', 'wow-num']
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
    walkOns.forEach(function (player) {
      var row = document.createElement('tr');
      var attrs = player.attributes || {};
      cell(row, player.name || '--', 'wow-name');
      cell(row, player.pos || '--');
      cell(row, formatYear(player.year));
      cell(row, formatHeight(player.height));
      cell(row, player.weight == null ? '--' : String(player.weight), 'wow-num');
      ATTR_KEYS.forEach(function (key) {
        cell(row, String(formatAttr(attrs, key)), 'wow-num');
      });
      var rt = player.rt;
      var rtText = (rt == null || typeof formatRtDisplay !== 'function')
        ? (rt == null ? '--' : String(rt))
        : formatRtDisplay(rt);
      var rtClass = (typeof getRtBucketClass === 'function') ? getRtBucketClass(rt) : '';
      cell(row, rtText, ('wow-num ' + rtClass).trim());
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
    var payload = data && data.walk_on_welcome_modal;
    if (presented || !payload || !payload.eligible) return;
    var walkOns = payload.walk_ons || [];
    if (!walkOns.length) return;
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
        eyebrow: 'Season ' + (payload.season || ''),
        body: buildBody(walkOns),
        ctaLabel: 'Go To Locker Room',
        imageSrc: getTeamSammyImage(data.team || ''),
        modalClass: 'is-wide',
        primaryClass: 'is-orange',
        onCta: function () {
          var card = document.getElementById('home-locker-room-body');
          if (!card) return;
          var homeTab = document.querySelector('[data-tab="home-tab"]');
          if (homeTab && !document.getElementById('home-tab').classList.contains('active')) {
            homeTab.click();
          }
          card.scrollIntoView({
            behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches
              ? 'auto' : 'smooth',
            block: 'center',
          });
        },
      });
      return markSeen(fid);
    }).catch(function (err) {
      console.error('[WalkOnWelcomeModal] failed to show:', err);
    });
  }

  window.WalkOnWelcomeModal = { maybeShow: maybeShow };
})();
