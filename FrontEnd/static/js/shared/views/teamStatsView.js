/**
 * League › Team Stats. One compact table sized to fit .main, so its single
 * header row pins under the page head. Group columns keep their shade.
 * Conference asks the server for scope=conference. Rates come from the payload.
 */

var GROUPS = [
  { name: '', shade: false, cols: [
    { key: 'team', label: 'Team', pin: true }
  ]},
  { name: '', shade: false, cols: [
    { key: 'natl_rank', label: 'Rank' }
  ]},
  { name: '', shade: false, cols: [
    { key: 'W', label: 'W' },
    { key: 'L', label: 'L' }
  ]},
  { name: '', shade: false, cols: [
    { key: 'PF', label: 'PF' },
    { key: 'PA', label: 'PA' }
  ]},
  { name: 'Shooting', shade: false, cols: [
    { key: 'FGM', label: 'FGM' },
    { key: 'FGA', label: 'FGA' },
    { key: 'FG_PCT', label: 'FG%', decimal: true }
  ]},
  { name: '3PT', shade: true, cols: [
    { key: '3PTM', label: '3PTM' },
    { key: '3PTA', label: '3PTA' },
    { key: 'TP_PCT', label: '3PT%', decimal: true }
  ]},
  { name: 'Free Throws', shade: false, cols: [
    { key: 'FTM', label: 'FTM' },
    { key: 'FTA', label: 'FTA' },
    { key: 'FT_PCT', label: 'FT%', decimal: true }
  ]},
  { name: 'Rebounding', shade: true, cols: [
    { key: 'DREB', label: 'DREB' },
    { key: 'OREB', label: 'OREB' },
    { key: 'TREB', label: 'TREB' }
  ]},
  { name: 'Other', shade: false, cols: [
    { key: 'AST', label: 'AST' },
    { key: 'F', label: 'F' },
    { key: 'TO', label: 'TO' },
    { key: 'SCR_A', label: 'SCRA' },
    { key: 'SCR_PCT', label: 'SCR%', decimal: true }
  ]},
  { name: 'Defense', shade: true, cols: [
    { key: 'STL', label: 'STL' },
    { key: 'BLK', label: 'BLK' },
    { key: 'DEF_A', label: 'DEFA' },
    { key: 'DEF_PCT', label: 'DEF%', decimal: true }
  ]}
];

// `fam` carries the family's first (`fs`) and last (`fe`) column, so the table spaces
// by stat family (Styleguide › Tables).
var LEAF = [];
GROUPS.forEach(function (group) {
  group.cols.forEach(function (col, index) {
    LEAF.push({
      key: col.key,
      label: col.label,
      pin: !!col.pin,
      shade: group.shade,
      group: group.name,
      stat: group.name !== '',
      decimal: !!col.decimal,
      fam: col.pin ? '' : (index === 0 ? ' fs' : '') + (index === group.cols.length - 1 ? ' fe' : '')
    });
  });
});

var SCOPES = [
  { id: 'conference', label: 'Conference' },
  { id: 'national', label: 'National' }
];
var SCOPE_KEY = 'gob-view-team-stats-scope';

function url(franchiseId, scope) {
  var base = window.GOBTables.apiBase('/franchise/team-stats') + '?franchise_id=' + franchiseId;
  return scope === 'conference' ? base + '&scope=conference' : base;
}

function sameId(a, b) {
  return String(a || '') !== '' && String(a) === String(b || '');
}

function num(value) {
  if (value == null || value === '') return null;
  var n = Number(value);
  return isFinite(n) ? n : null;
}

export function mount(container, ctx) {
  var tables = window.GOBTables;
  var scope = tables.readKey(SCOPE_KEY, 'national') === 'conference' ? 'conference' : 'national';
  var query = '';
  var sortKey = 'natl_rank';
  var sortDir = 1;
  var teams = [];
  var signature = '';
  var loaded = false;
  var restored = false;
  var userId = (ctx && ctx.teamId) || '';
  var franchiseId = (ctx && ctx.franchiseId) || '';

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

  function paintTools(slot) {
    slot.innerHTML = tables.segment(SCOPES, scope) + tables.searchBox('Search teams');
    slot.querySelectorAll('.stats-toggle button').forEach(function (button) {
      button.addEventListener('click', function () {
        var next = button.getAttribute('data-value');
        if (!next || next === scope) return;
        scope = next;
        tables.writeKey(SCOPE_KEY, scope);
        loaded = false;
        signature = '';
        tables.resetScroll();
        paintTools(slot);
        load();
      });
    });
    var input = slot.querySelector('input');
    if (!input) return;
    input.value = query;
    input.addEventListener('input', function () {
      query = input.value || '';
      render();
    });
  }

  function ownTools() {
    tables.registerTools('team-stats-view', paintTools);
    tables.placeTools();
  }

  function onTab() {
    if (container.classList.contains('active')) ownTools();
  }

  function valueOf(row, col) {
    if (col.key === 'team') return String(row.team || '');
    if (col.key === 'natl_rank') return num(row.natl_rank);
    var stats = row.stats || {};
    if (col.key === 'W' || col.key === 'L' || col.key === 'PF' || col.key === 'PA') {
      return num(stats[col.key] != null ? stats[col.key] : row[col.key]);
    }
    return num(stats[col.key]);
  }

  function cellText(row, col) {
    if (col.key === 'team') {
      var name = row.team || '';
      return tables.teamLink(tables.rosterHref(franchiseId, row.team_id, name, 'team-stats-view'), name, name, row.primary_color);
    }
    var value = valueOf(row, col);
    if (value == null) return col.decimal ? '—' : '';
    if (col.decimal) return tables.esc(tables.formatOneDecimal(value));
    return tables.esc(value);
  }

  function headerRow() {
    var html = '<tr>';
    LEAF.forEach(function (col) {
      var on = sortKey === col.key;
      var cls = 's' + (col.pin ? ' pin team' : '') + (col.shade ? ' gshade' : '') + col.fam
        + (on ? ' on ' + (sortDir < 0 ? 'desc' : 'asc') : '');
      html += '<th class="' + cls + '" data-sort="' + col.key + '"'
        + (col.group ? ' title="' + tables.esc(col.group) + '"' : '') + '>' + tables.esc(col.label) + '</th>';
    });
    html += '</tr>';
    return html;
  }

  function render() {
    var needle = query.trim().toLowerCase();
    var rows = teams.filter(function (row) {
      if (!needle) return true;
      return String(row.team || '').toLowerCase().indexOf(needle) !== -1;
    });
    if (sortKey) {
      var col = null;
      LEAF.forEach(function (item) { if (item.key === sortKey) col = item; });
      if (col) rows = tables.sortRows(rows, function (row) { return valueOf(row, col); }, sortDir);
    }
    var html = '<section class="gob-tcard gob-ts gob-fam"><table class="gob-tbl"><thead>'
      + headerRow() + '</thead><tbody id="teamstats-body">';
    if (!rows.length) {
      html += '<tr><td class="team" colspan="' + LEAF.length + '">No teams.</td></tr>';
    }
    rows.forEach(function (row) {
      var mine = sameId(row.team_id, userId);
      html += '<tr' + (mine ? ' class="me is-user"' : '') + '>';
      LEAF.forEach(function (col) {
        var cls = (col.pin ? 'pin team' : '') + (col.shade ? ' gshade' : '') + col.fam + (sortKey === col.key ? ' on' : '');
        html += '<td class="' + cls.trim() + '">' + cellText(row, col) + '</td>';
      });
      html += '</tr>';
    });
    html += '</tbody></table></section>';
    container.innerHTML = html;
    container.querySelectorAll('th.s').forEach(function (th) {
      th.addEventListener('click', function () {
        var key = th.getAttribute('data-sort');
        if (sortKey === key) sortDir = -sortDir;
        else { sortKey = key; sortDir = key === 'team' ? 1 : -1; }
        render();
      });
    });
    ownTools();
    restoreScroll();
  }

  function apply(payload) {
    var next = payload && Array.isArray(payload.teams) ? payload.teams : [];
    var stamp = JSON.stringify(next);
    if (loaded && stamp === signature) return;
    signature = stamp;
    teams = next;
    loaded = true;
    render();
  }

  function load() {
    var store = ctx && ctx.store;
    if (!store || typeof store.get !== 'function' || !franchiseId) {
      tables.paintError(container, 'Team stats could not be opened.', load);
      return;
    }
    if (!loaded) tables.paintSkeleton(container);
    var asked = scope;
    store.get(url(franchiseId, asked)).then(function (payload) {
      if (asked !== scope) return;
      apply(payload || { teams: [] });
    }).catch(function () {
      if (asked !== scope) return;
      loaded = false;
      tables.paintError(container, 'Team stats could not be opened.', load);
    });
  }

  function revalidate() {
    var store = ctx && ctx.store;
    if (!loaded || !store || typeof store.revalidate !== 'function' || !franchiseId) return;
    var asked = scope;
    store.revalidate(url(franchiseId, asked)).then(function (payload) {
      if (payload && asked === scope) apply(payload);
    }).catch(function () { /* keep the mounted table */ });
  }

  document.addEventListener('gob-tab-shown', onTab);
  ownTools();
  load();

  return {
    revalidate: revalidate,
    unmount: function () {
      document.removeEventListener('gob-tab-shown', onTab);
      tables.registerTools('team-stats-view', null);
    }
  };
}

export function unmount() {}
