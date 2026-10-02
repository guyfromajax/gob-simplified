/**
 * Player Development grid — the 12 active players, their training position and focus.
 *
 * ONE implementation and ONE layout for its two hosts: the weekly training page (under
 * Coaching Focus) and Prep › Player Training. Both draw the same cards, four across. They
 * are the only two places development is editable.
 *
 * Hosts differ in where their roster comes from, so each adapts its own payload into the
 * normalised shape below rather than this module learning two payloads:
 *
 *   { id, name, year, height, weight,
 *     attributes: { SC: 7, ... },        // 0-10 display scale or raw; passed through
 *     position_ratings: { PG: 72, ... },
 *     training_position, training_focus, resolved_training_position, resolved_training_focus }
 *
 * Order: by the RT the card shows (the rating at the TRAINING position), highest first,
 * reading left to right and then top to bottom; ties keep the caller's order. The order is
 * set when the grid is rendered and not while it is being edited: that RT changes when the
 * coach changes a position, and re-sorting then would move a card out from under the
 * cursor immediately after it was used. A longer roster (camp, before cuts) adds a row.
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

  /** Highest shown RT first; a card with no rating last; ties keep the caller's order. */
  function orderByRt(players) {
    return (players || []).map(function (player, index) {
      return { player: player, index: index, rt: rtAtTrainingPosition(player) };
    }).sort(function (a, b) {
      var ar = a.rt == null ? -Infinity : a.rt;
      var br = b.rt == null ? -Infinity : b.rt;
      return (br - ar) || (a.index - b.index);
    }).map(function (entry) { return entry.player; });
  }

  /** Height may arrive as inches (training payload) or preformatted (roster payload). */
  function formatHeight(height) {
    if (height == null || height === '') return '--';
    var n = Number(height);
    if (!isFinite(n) || n <= 0) return String(height);
    return Math.floor(n / 12) + "'" + (n % 12) + '"';
  }

  /** Raw attribute, preferring anchor_. The hover card displays the first digit. */
  function attrValue(attributes, code) {
    var raw = window.GOB_AttributeDisplay.rawAttr(attributes, code);
    if (raw == null || raw === '') return null;
    var n = Number(raw);
    return isFinite(n) ? n : null;
  }

  /**
   * Which attributes this player's position + focus actually develops.
   *
   * Read from the generated matrix asset (window.GOB_TRAINING_MATRIX), the same source the
   * Training by Position tutorial renders, so the card and the chart cannot disagree. The
   * threshold and the always-100 attributes are published by that asset rather than
   * decided here — see DEVELOPS_MIN in scripts/generate_training_matrix_asset.py.
   *
   * Empty list when the asset is absent; the card then simply carries no accent.
   */
  function developsFor(player) {
    var data = window.GOB_TRAINING_MATRIX;
    var dev = window.GOBDevelopmentFocus;
    if (!data || !data.develops || !dev) return [];
    var byPos = data.matrix[dev.positionOf(player)] || {};
    var focus = dev.focusOf(player);
    var profile = byPos[focus];
    if (!profile) return [];
    var locked = data.develops.locked || [];
    var usable = ATTR_ORDER.filter(function (c) { return locked.indexOf(c) === -1; });

    // A focus other than Standard is a CHOICE, so the useful answer is what that choice
    // buys: the attributes it raises above the Standard profile for the same position.
    //
    // An absolute threshold was tried first and is wrong here. For a PG it marked the same
    // four codes on Standard, Defensive AND Fundamentals, because those four clear the bar
    // in all three — so switching focus changed nothing on screen, which is the opposite of
    // what this card is for. Defensive really moves ID 25->55 and OD 70->100; that is the
    // fact worth showing.
    if (focus !== 'standard' && byPos.standard) {
      return usable.filter(function (c) { return Number(profile[c]) > Number(byPos.standard[c]); });
    }
    // Standard has no baseline to differ from, so it names where his points land best.
    return usable.filter(function (c) { return Number(profile[c]) >= data.develops.min; });
  }

  /** "adds" for a chosen focus, "develops" for Standard — the two say different things. */
  function developsVerb(player) {
    var dev = window.GOBDevelopmentFocus;
    return (dev && dev.focusOf(player) !== 'standard') ? 'adds' : 'develops';
  }

  function hoverCardHtml(player) {
    var develops = developsFor(player);
    var rows = ATTR_ORDER.map(function (code) {
      var raw = attrValue(player.attributes, code);
      var shown = window.GOB_AttributeDisplay.displayAttr(raw);
      // The accent is on the CODE, never the value. Values are ratings, and colour on a
      // rating already means how good he is. Tinting them here would put that palette
      // on a quantity that is not a value.
      var on = develops.indexOf(code) !== -1 ? ' is-develops' : '';
      return '<span class="pdg-hc-attr' + on + '"><b>' + esc(code) + '</b>' +
        '<i>' + (shown == null ? '--' : shown) + '</i></span>';
    }).join('');

    var dev = window.GOBDevelopmentFocus;
    var summary = '';
    if (develops.length && dev) {
      // Named outright, so the accent never has to be decoded to be understood.
      summary = '<span class="pdg-hc-develops">' +
        esc(dev.positionOf(player)) + ' &middot; ' + esc(dev.focusLabel(player)) + ' ' +
        developsVerb(player) + ' <b>' + develops.map(esc).join('</b> <b>') + '</b></span>';
    }

    return '<span class="pdg-hc-head">' + esc(player.name) + '</span>' +
      '<span class="pdg-hc-vitals">' +
        esc(player.year || '--') + ' &middot; ' + esc(formatHeight(player.height)) +
        ' &middot; ' + esc(player.weight == null ? '--' : player.weight) + ' lb' +
      '</span>' + summary +
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
      var card = name.closest('.pdg-card') || name.closest('tr[data-pdg-player]');
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
    var bucket = (rt != null && typeof window.getRtBucketClass === 'function') ? window.getRtBucketClass(rt) : '';
    return '<div class="pdg-card" data-pdg-player="' + esc(player.id) + '">' +
      '<span class="pdg-name" tabindex="0">' + esc(player.name) + '</span>' +
      '<span class="pdg-rt"><b data-pdg-rt class="' + esc(bucket) + '">' +
        (rt == null ? '--' : esc(formatRtDisplay(rt))) + '</b></span>' +
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
    var rows = orderByRt(players);
    var grid = host.querySelector('.pdg-grid');
    if (!grid) return;

    // One layout for both hosts: cards, four across, filled row by row. Twelve players
    // are three rows of four, and a longer camp roster adds a row.
    host.classList.remove('pdg-layout-table');
    host.classList.add('pdg-layout-cards');
    if (o.tallies) host._pdgTallies = o.tallies;
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
        var prevResolved = field === 'training_focus' ? row.resolved_training_focus : row.resolved_training_position;
        row[field] = value;
        row[field === 'training_focus' ? 'resolved_training_focus' : 'resolved_training_position'] = value;
        // The row keeps its place; only the number it shows moves. Re-sorting here would
        // pull the row out from under the coach the instant he used it.
        if (host._pdgTallies && prevResolved !== value) {
          var maps = host._pdgTallies;
          var bag = field === 'training_focus' ? maps.focuses : maps.positions;
          if (bag) {
            if (prevResolved && Object.prototype.hasOwnProperty.call(bag, prevResolved)) {
              bag[prevResolved] = Math.max(0, (bag[prevResolved] || 0) - 1);
            }
            if (value && Object.prototype.hasOwnProperty.call(bag, value)) bag[value] = (bag[value] || 0) + 1;
          }
        }
        if (field === 'training_position') {
          var cell = grid.querySelector('[data-pdg-player="' + CSS.escape(String(playerId)) + '"] [data-pdg-rt]');
          if (cell) {
            var rt = rtAtTrainingPosition(row);
            cell.textContent = rt == null ? '--' : formatRtDisplay(rt);
            if (typeof window.getRtBucketClass === 'function') {
              cell.className = rt == null ? '' : window.getRtBucketClass(rt);
            }
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
    var maps = host._pdgTallies;
    if (maps && maps.positions && maps.focuses) {
      if (pos) pos.innerHTML = serverTallyHtml(maps.positions, 'position');
      if (foc) foc.innerHTML = serverTallyHtml(maps.focuses, 'focus');
      return;
    }
    if (pos) pos.innerHTML = tallyHtml(rows, 'position');
    if (foc) foc.innerHTML = tallyHtml(rows, 'focus');
  }

  function serverTallyHtml(counts, kind) {
    var dev = window.GOBDevelopmentFocus;
    var keys = kind === 'position'
      ? dev.POSITIONS.map(function (p) { return { k: p, label: p }; })
      : dev.FOCUSES.map(function (f) { return { k: f.value, label: f.label }; });
    return keys.map(function (o) {
      var n = counts[o.k] || 0;
      return '<span class="pdg-tally-item' + (n ? '' : ' is-zero') + '">' +
        esc(o.label) + ' <b>' + n + '</b></span>';
    }).join('');
  }

  window.GOBPlayerDevelopmentGrid = {
    ATTR_ORDER: ATTR_ORDER,
    render: render,
    rtAtTrainingPosition: rtAtTrainingPosition,
    orderByRt: orderByRt,
    formatHeight: formatHeight,
    attrValue: attrValue,
    developsFor: developsFor,
    hideHoverCard: hideHoverCard,
  };
})();
