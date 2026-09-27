/**
 * Team › Team Attributes. Renders the measures array from GET /franchise/team-data.
 * Missing scales and descriptions stay off the page.
 */

function showNum(value) {
  var n = Number(value);
  if (!isFinite(n)) return '';
  if (Math.abs(n - Math.round(n)) < 1e-6) return String(Math.round(n));
  return n.toFixed(3).replace(/0+$/, '').replace(/\.$/, '');
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

  function deltaChip(delta) {
    if (delta == null || delta === '') return '';
    var n = Number(delta);
    if (!isFinite(n)) return '';
    if (n > 0) return '<span class="chip up">▲ ' + tables.esc(showNum(n)) + '</span>';
    if (n < 0) return '<span class="chip down">▼ ' + tables.esc(showNum(Math.abs(n))) + '</span>';
    return '<span class="chip flat">—</span>';
  }

  function render() {
    var measures = body && Array.isArray(body.measures) ? body.measures : [];
    var families = [];
    var map = Object.create(null);
    measures.forEach(function (row) {
      var key = String(row.family || '');
      if (!map[key]) {
        map[key] = { label: row.family_label || '', rows: [] };
        families.push(map[key]);
      }
      map[key].rows.push(row);
    });
    var html = '<div class="gob-measures">';
    if (body && body.updated_after_week != null && body.updated_after_week !== '') {
      html += '<p class="gob-meta">Updated after Week ' + tables.esc(body.updated_after_week) + '</p>';
    }
    if (!families.length) {
      html += '<section class="gob-tcard"><p class="gob-meta">No team attributes.</p></section>';
    }
    families.forEach(function (family) {
      html += '<section class="gob-tcard"><header class="card-h"><h3>' + tables.esc(family.label) + '</h3></header>';
      family.rows.forEach(function (row) {
        var scale = row.scale_max == null || row.scale_max === '' ? '' : '<em>/' + tables.esc(row.scale_max) + '</em>';
        var meter = row.meter_pct == null || row.meter_pct === ''
          ? ''
          : '<span class="gob-meter"><i style="--w:' + Number(row.meter_pct) + '%"></i></span>';
        var desc = row.description ? '<span class="meta">' + tables.esc(row.description) + '</span>' : '';
        html += '<div class="gob-mrow"><span class="nm">' + tables.esc(row.label || '') + desc + '</span>'
          + '<span class="val">' + tables.esc(showNum(row.value)) + scale + '</span>'
          + meter + deltaChip(row.delta) + '</div>';
      });
      html += '</section>';
    });
    html += '</div>';
    container.innerHTML = html;
    restoreScroll();
  }

  function apply(payload) {
    var next = payload || {};
    var stamp = JSON.stringify({
      measures: next.measures || null,
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
