/**
 * Team › Team Attributes. The twelve measures from GET /franchise/team-data, above
 * the shared Team Measures radar.
 *
 * The radar is franchise-command-center.js::buildTeamMeasuresRadarMarkup, called
 * here rather than reimplemented so both surfaces keep the same ±20 geometry. It
 * reads `team_attributes`; the cells read `measures[]`. Missing scales, ranks and
 * descriptions stay off the page.
 */

/**
 * PRESENTATION-ONLY layout. Four columns of paired measures, then the four that
 * have no pair. Emitted row-major, so a CSS grid of four columns puts each pair in
 * one column: Offense/Defense, the two Press/Trap measures, the two Fast Break
 * measures, Shooting/Rebounding.
 *
 * Deliberately separate from the server's family order, which groups by where a
 * measure comes from rather than by how it reads on the page.
 */
var GRID_ROWS = [
  ['offensive_efficiency', 'pt_opp_modifier', 'fb_efficiency', 'shot_threshold'],
  ['defensive_efficiency', 'pt_efficiency', 'fb_opp_modifier', 'rebound_modifier'],
  ['team_chemistry', 'fight', 'discipline', 'momentum_score']
];

function showNum(value) {
  var n = Number(value);
  if (!isFinite(n)) return '';
  if (Math.abs(n - Math.round(n)) < 1e-6) return String(Math.round(n));
  return n.toFixed(3).replace(/0+$/, '').replace(/\.$/, '');
}

/** The signed measures read with their sign, so −7 and +7 are not both "7". */
function signedNum(value) {
  var n = Number(value);
  if (!isFinite(n)) return '';
  return (n > 0 ? '+' : '') + showNum(n);
}

function url(franchiseId, teamId) {
  var base = window.GOBTables.apiBase('/franchise/team-data');
  var q = 'franchise_id=' + encodeURIComponent(franchiseId || '');
  if (teamId) q += '&team_id=' + encodeURIComponent(teamId);
  return base + '?' + q;
}

export function mount(container, ctx) {
  var tables = window.GOBTables;
  var franchiseId = (ctx && ctx.franchiseId) || '';
  var teamId = (ctx && ctx.teamId) || '';
  var body = null;
  var signature = '';
  var loaded = false;
  var restored = false;

  function restoreScroll() {
    if (restored || !tables.backForward()) return;
    restored = true;
    var nav = ctx && ctx.nav;
    if (!nav || typeof nav.restoreScroll !== 'function') return;
    requestAnimationFrame(function () {
      nav.restoreScroll();
      requestAnimationFrame(function () { nav.restoreScroll(); });
    });
  }

  function ordinal(rank) {
    var n = Math.round(Number(rank));
    var mod100 = n % 100;
    var suffix = 'th';
    if (mod100 < 11 || mod100 > 13) {
      if (n % 10 === 1) suffix = 'st';
      else if (n % 10 === 2) suffix = 'nd';
      else if (n % 10 === 3) suffix = 'rd';
    }
    return n + suffix;
  }

  function placeText(row) {
    if (row.rank == null || row.rank === '' || row.rank_of == null || row.rank_of === '') return '—';
    return ordinal(row.rank) + ' of ' + row.rank_of;
  }

  // Neutral, per the Prep v2 decision: the arrow carries the direction and the
  // luminance carries the weight. Green and red are spent elsewhere.
  function movement(delta) {
    if (delta == null || delta === '') return '<span class="mv"></span>';
    var n = Number(delta);
    if (!isFinite(n) || n === 0) return '<span class="mv"></span>';
    if (n > 0) return '<span class="mv up">▲' + showNum(n) + '</span>';
    return '<span class="mv down">▼' + showNum(Math.abs(n)) + '</span>';
  }

  /**
   * The diverging pill for a measure stored on a signed scale, otherwise the league
   * percentile bar. Only the eight −20…+20 measures have a zero to sit either side
   * of; Chemistry, Shooting, Rebounding and Momentum do not, so they keep the bar
   * they already had.
   */
  function gauge(row) {
    var scale = Number(row.signed_scale);
    // A stored 0 is a real reading at the centre line. No stored value is not.
    var stored = row.value == null || row.value === '' ? null : Number(row.value);
    if (isFinite(scale) && scale > 0) {
      if (stored == null || !isFinite(stored)) {
        return '<span class="dv is-empty" style="--v:0"><i></i></span>';
      }
      var clamped = Math.max(-scale, Math.min(scale, stored));
      return '<span class="dv' + (clamped < 0 ? ' neg' : '') + '" style="--v:'
        + (Math.abs(clamped) / scale) + '"><i></i></span>';
    }
    var ranked = row.rank != null && row.rank !== '';
    var width = ranked && row.percentile != null && row.percentile !== '' ? Number(row.percentile) : 0;
    return '<span class="gob-meter' + (ranked ? '' : ' is-empty') + '"><i style="--w:' + width + '%"></i></span>';
  }

  /** The number beside the pill: signed for the eight, `18/25` for Chemistry. */
  function valueText(row) {
    if (row.value == null || row.value === '') return '';
    if (row.key === 'team_chemistry' && row.scale_max != null && row.scale_max !== '') {
      return tables.esc(showNum(row.value)) + '<em>/' + tables.esc(row.scale_max) + '</em>';
    }
    if (row.signed_scale != null && row.signed_scale !== '') return tables.esc(signedNum(row.value));
    return '';
  }

  function cellHtml(row) {
    return '<div class="mcell" data-measure="' + tables.esc(row.key || '') + '">'
      + '<div class="mtop"><span class="nm">' + tables.esc(row.label || '') + '</span>'
      + '<span class="place">' + tables.esc(placeText(row)) + '</span></div>'
      + '<div class="mbar">' + gauge(row) + '<b>' + valueText(row) + '</b>'
      + movement(row.rank_delta) + '</div></div>';
  }

  /** Rows in grid order, then anything the server sends that the grid does not name. */
  function gridOrder(measures) {
    var byKey = Object.create(null);
    measures.forEach(function (row) {
      if (row && row.key) byKey[String(row.key)] = row;
    });
    var ordered = [];
    var placed = Object.create(null);
    GRID_ROWS.forEach(function (keys) {
      keys.forEach(function (key) {
        if (!byKey[key]) return;
        ordered.push(byKey[key]);
        placed[key] = true;
      });
    });
    measures.forEach(function (row) {
      if (row && row.key && !placed[String(row.key)]) ordered.push(row);
    });
    return ordered;
  }

  function radarHtml() {
    var attrs = body && body.team_attributes;
    if (!attrs || typeof window.buildTeamMeasuresRadarMarkup !== 'function') return '';
    try {
      return '<section class="gob-tcard mradar">' + window.buildTeamMeasuresRadarMarkup(attrs) + '</section>';
    } catch (err) {
      return '';
    }
  }

  function render() {
    var measures = body && Array.isArray(body.measures) ? body.measures : [];
    var rows = gridOrder(measures);
    var html = '<div class="gob-measures">';
    if (body && body.updated_after_week != null && body.updated_after_week !== '') {
      html += '<p class="gob-meta">Updated after Week ' + tables.esc(body.updated_after_week) + '</p>';
    }
    html += radarHtml();
    if (!rows.length) {
      html += '<section class="gob-tcard"><p class="gob-meta">No team attributes.</p></section>';
    } else {
      html += '<section class="gob-tcard"><div class="mgrid">'
        + rows.map(cellHtml).join('') + '</div></section>';
    }
    html += '</div>';
    container.innerHTML = html;
    restoreScroll();
  }

  function apply(payload) {
    var next = payload || {};
    var stamp = JSON.stringify({
      measures: next.measures || null,
      team_attributes: next.team_attributes || null,
      updated_after_week: next.updated_after_week == null ? null : next.updated_after_week
    });
    if (loaded && stamp === signature) return;
    signature = stamp;
    body = next;
    loaded = true;
    render();
  }

  function load() {
    var store = ctx && ctx.store;
    if (!store || typeof store.get !== 'function' || !franchiseId) {
      tables.paintError(container, 'Team attributes could not be opened.', load);
      return;
    }
    if (!loaded) tables.paintSkeleton(container);
    store.get(url(franchiseId, teamId)).then(function (payload) {
      apply(payload || {});
    }).catch(function () {
      loaded = false;
      tables.paintError(container, 'Team attributes could not be opened.', load);
    });
  }

  function revalidate() {
    var store = ctx && ctx.store;
    if (!loaded || !store || typeof store.revalidate !== 'function' || !franchiseId) return;
    store.revalidate(url(franchiseId, teamId)).then(function (payload) {
      if (payload) apply(payload);
    }).catch(function () { /* keep the mounted cards */ });
  }

  load();

  return {
    revalidate: revalidate,
    unmount: function () {}
  };
}

export function unmount() {}
