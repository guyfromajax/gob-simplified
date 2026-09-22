/**
 * Player Development grid — the 12 active players, their training position and focus.
 *
 * ONE implementation for its two hosts: the training page (under Coaching Focus) and the
 * FCC's Training tab. They are the only two places development is editable, and a coach
 * who learns one has learned the other.
 *
 * Hosts differ in where their roster comes from, so each adapts its own payload into the
 * normalised shape below rather than this module learning two payloads:
 *
 *   { id, name, year, height, weight,
 *     attributes: { SC: 7, ... },        // 0-10 display scale or raw; passed through
 *     position_ratings: { PG: 72, ... },
 *     training_position, training_focus, resolved_training_position, resolved_training_focus }
 *
 * Row order is fixed by the caller and never re-sorted. The displayed RT follows the
 * TRAINING position, so it changes when the coach changes the position — but re-sorting on
 * that would make a row jump out from under the cursor immediately after it was used.
 */
(function () {
  'use strict';

  var ATTR_ORDER = ['SC', 'SH', 'PS', 'BH', 'ID', 'OD', 'RB', 'ST', 'AG', 'FT', 'IQ', 'ND'];

  function esc(v) {
    return String(v == null ? '' : v).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  /** Rating at the position he is COACHED at, which is what the row is about. */
  function rtAtTrainingPosition(player) {
    var dev = window.GOBDevelopmentFocus;
    var ratings = (player && player.position_ratings) || {};
    var pos = dev ? dev.positionOf(player) : null;
    var v = pos ? Number(ratings[pos]) : NaN;
    return isFinite(v) ? Math.round(v) : null;
  }

  /** Height may arrive as inches (training payload) or preformatted (roster payload). */
  function formatHeight(height) {
    if (height == null || height === '') return '--';
    var n = Number(height);
    if (!isFinite(n) || n <= 0) return String(height);
    return Math.floor(n / 12) + "'" + (n % 12) + '"';
  }

  /** Attributes may be stored raw or under anchor_ keys; prefer the anchor. */
  function attrValue(attributes, code) {
    var a = attributes || {};
    var v = a['anchor_' + code];
    if (v == null) v = a[code];
    var n = Number(v);
    return isFinite(n) ? n : null;
  }

  function hoverCardHtml(player) {
    var rows = ATTR_ORDER.map(function (code) {
      var v = attrValue(player.attributes, code);
      return '<span class="pdg-hc-attr"><b>' + esc(code) + '</b>' +
        '<i>' + (v == null ? '--' : v) + '</i></span>';
    }).join('');
    return '<span class="pdg-hc-head">' + esc(player.name) + '</span>' +
      '<span class="pdg-hc-vitals">' +
        esc(player.year || '--') + ' &middot; ' + esc(formatHeight(player.height)) +
        ' &middot; ' + esc(player.weight == null ? '--' : player.weight) + ' lb' +
      '</span>' +
      '<span class="pdg-hc-attrs">' + rows + '</span>';
  }

  /**
   * ONE hover card, fixed-position, appended to <body>.
   *
   * It used to render inside the row and flip by nth-child. Two ways that failed: the top
   * row opened upward into the panel's edge and was clipped, and the bottom row flipped
   * downward off the bottom of the page. Neither is fixable by choosing a better static
   * side — the card is inside an element that clips it. Living on <body> at position:fixed
   * removes every ancestor's overflow and stacking context from the question, and the side
   * is then chosen from the space actually available on screen.
   */
  var cardEl = null;
  var GAP = 8;
  var EDGE = 8;

  function hoverCardEl() {
    if (cardEl && cardEl.isConnected) return cardEl;
    cardEl = document.createElement('div');
    cardEl.className = 'pdg-hovercard';
    cardEl.setAttribute('role', 'tooltip');
    cardEl.hidden = true;
    document.body.appendChild(cardEl);
    return cardEl;
  }

  function showHoverCard(anchor, player) {
    var el = hoverCardEl();
    el.innerHTML = hoverCardHtml(player);
    el.hidden = false;
    // Measure only after the content is in: the card's height depends on the name wrapping.
    var a = anchor.getBoundingClientRect();
    var c = el.getBoundingClientRect();
    var vw = window.innerWidth;
    var vh = window.innerHeight;

    var above = a.top - GAP - c.height;
    var below = a.bottom + GAP;
    var top;
    if (above >= EDGE) top = above;                       // preferred: above the name
    else if (below + c.height <= vh - EDGE) top = below;   // else below it
    else top = Math.max(EDGE, vh - EDGE - c.height);       // else clamp; never off-screen

    var left = Math.min(Math.max(EDGE, a.left), vw - EDGE - c.width);
    el.style.top = Math.round(top) + 'px';
    el.style.left = Math.round(left) + 'px';
    el.classList.add('is-open');
  }

  function hideHoverCard() {
    if (!cardEl) return;
    cardEl.classList.remove('is-open');
    cardEl.hidden = true;
  }

  /** Anchored to viewport coordinates, so any scroll invalidates the position. */
  function bindHoverCard(grid, byId) {
    var open = function (e) {
      var name = e.target.closest ? e.target.closest('.pdg-name') : null;
      if (!name) return;
      var card = name.closest('.pdg-card');
      var lookup = grid._pdgById || byId;
      var player = card && lookup[String(card.dataset.pdgPlayer)];
      if (player) showHoverCard(name, player);
    };
    grid.addEventListener('mouseover', open);
    grid.addEventListener('focusin', open);
    grid.addEventListener('mouseout', function (e) {
      if (e.target.closest && e.target.closest('.pdg-name')) hideHoverCard();
    });
    grid.addEventListener('focusout', hideHoverCard);
    window.addEventListener('scroll', hideHoverCard, true);
    window.addEventListener('resize', hideHoverCard);
  }

  function cardHtml(player) {
    var dev = window.GOBDevelopmentFocus;
    var rt = rtAtTrainingPosition(player);
    return '<div class="pdg-card" data-pdg-player="' + esc(player.id) + '">' +
      '<span class="pdg-name" tabindex="0">' + esc(player.name) + '</span>' +
      '<span class="pdg-rt" data-pdg-rt>' + (rt == null ? '--' : rt) + '</span>' +
      '<span class="pdg-controls">' +
        dev.positionSelectHtml(player) + dev.focusSelectHtml(player) +
      '</span>' +
    '</div>';
  }

  function tallyHtml(players, kind) {
    var dev = window.GOBDevelopmentFocus;
    var counts = {};
    players.forEach(function (p) {
      var k = kind === 'position' ? dev.positionOf(p) : dev.focusOf(p);
      counts[k] = (counts[k] || 0) + 1;
    });
    var keys = kind === 'position'
      ? dev.POSITIONS.map(function (p) { return { k: p, label: p }; })
      : dev.FOCUSES.map(function (f) { return { k: f.value, label: f.label }; });
    return keys.map(function (o) {
      var n = counts[o.k] || 0;
      return '<span class="pdg-tally-item' + (n ? '' : ' is-zero') + '">' +
        esc(o.label) + ' <b>' + n + '</b></span>';
    }).join('');
  }

  /**
   * Render into `host`, which must contain .pdg-tally-positions, .pdg-tally-focuses and
   * .pdg-grid. `onSaved(playerId, field, value)` lets the host update its own cache.
   */
  function render(host, players, opts) {
    var dev = window.GOBDevelopmentFocus;
    if (!host || !dev) return;
    var o = opts || {};
    var rows = players || [];
    var grid = host.querySelector('.pdg-grid');
    if (!grid) return;

    grid.innerHTML = rows.length
      ? rows.map(cardHtml).join('')
      : '<div class="pdg-empty">No active players.</div>';
    paintTallies(host, rows);

    var byId = {};
    rows.forEach(function (r) { byId[String(r.id)] = r; });
    if (!grid.dataset.pdgHoverBound) {
      grid.dataset.pdgHoverBound = '1';
      bindHoverCard(grid, byId);
    } else {
      grid._pdgById = byId;
    }
    grid._pdgById = byId;

    dev.bind(grid, o.getFranchiseId || function () { return ''; }, function (playerId, field, value) {
      var row = null;
      rows.forEach(function (r) { if (String(r.id) === String(playerId)) row = r; });
      if (row) {
        row[field] = value;
        row[field === 'training_focus' ? 'resolved_training_focus' : 'resolved_training_position'] = value;
        // The row keeps its place; only the number it shows moves. Re-sorting here would
        // pull the row out from under the coach the instant he used it.
        if (field === 'training_position') {
          var cell = grid.querySelector('[data-pdg-player="' + CSS.escape(String(playerId)) + '"] [data-pdg-rt]');
          if (cell) {
            var rt = rtAtTrainingPosition(row);
            cell.textContent = rt == null ? '--' : rt;
          }
        }
      }
      paintTallies(host, rows);
      if (typeof o.onSaved === 'function') o.onSaved(playerId, field, value);
    });
  }

  function paintTallies(host, rows) {
    var pos = host.querySelector('.pdg-tally-positions');
    var foc = host.querySelector('.pdg-tally-focuses');
    if (pos) pos.innerHTML = tallyHtml(rows, 'position');
    if (foc) foc.innerHTML = tallyHtml(rows, 'focus');
  }

  window.GOBPlayerDevelopmentGrid = {
    ATTR_ORDER: ATTR_ORDER,
    render: render,
    rtAtTrainingPosition: rtAtTrainingPosition,
    formatHeight: formatHeight,
    attrValue: attrValue,
    hideHoverCard: hideHoverCard,
  };
})();
