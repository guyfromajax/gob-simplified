/**
 * League › Team Stats. Wide grouped table. The card scrolls sideways.
 * The header row repeats every 16 team rows. Rates come from the payload.
 */

var GROUPS = [
  { name: '', shade: false, cols: [
    { key: 'team', label: 'Team', pin: true },
    { key: 'natl_rank', label: 'Rank' },
    { key: 'W', label: 'W' },
    { key: 'L', label: 'L' },
    { key: 'PF', label: 'PF' },
    { key: 'PA', label: 'PA' }
  ]},
  { name: 'Shooting', shade: false, cols: [
    { key: 'FGM', label: 'FGM' },
    { key: 'FGA', label: 'FGA' },
    { key: 'FG_PCT', label: 'FG%' }
  ]},
  { name: '3PT', shade: true, cols: [
    { key: '3PTM', label: '3PTM' },
    { key: '3PTA', label: '3PTA' },
    { key: 'TP_PCT', label: '3PT%' }
  ]},
  { name: 'Free Throws', shade: false, cols: [
    { key: 'FTM', label: 'FTM' },
    { key: 'FTA', label: 'FTA' },
    { key: 'FT_PCT', label: 'FT%' }
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
    { key: 'SCR_PCT', label: 'SCR%' }
  ]},
  { name: 'Defense', shade: true, cols: [
    { key: 'STL', label: 'STL' },
    { key: 'BLK', label: 'BLK' },
    { key: 'DEF_A', label: 'DEFA' },
    { key: 'DEF_PCT', label: 'DEF%' }
  ]}
];

var LEAF = [];
GROUPS.forEach(function (group) {
  group.cols.forEach(function (col) {
    LEAF.push({ key: col.key, label: col.label, pin: !!col.pin, shade: group.shade, stat: group.name !== '' });
  });
});

function url(franchiseId) {
  return window.GOBTables.apiBase('/franchise/team-stats') + '?franchise_id=' + franchiseId;
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
  var query = '';
  var sortKey = '';
  var sortDir = -1;
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
    slot.innerHTML = tables.searchBox('Search teams');
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
      return tables.teamLink(tables.rosterHref(franchiseId, row.team_id, name, 'team-stats-view'), name, name);
    }
    var value = valueOf(row, col);
    if (value == null) return '';
    return tables.esc(value);
  }

  function headerRow(repeat) {
    var html = '<tr' + (repeat ? ' class="gob-rep"' : '') + '>';
    LEAF.forEach(function (col) {
      var on = sortKey === col.key;
      var cls = 's' + (col.pin ? ' pin team' : '') + (col.shade ? ' gshade' : '')
        + (on ? ' on ' + (sortDir < 0 ? 'desc' : 'asc') : '');
      html += '<th class="' + cls + '" data-sort="' + col.key + '">' + tables.esc(col.label) + '</th>';
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
    var html = '<section class="gob-tcard"><div class="gob-xs"><table class="gob-tbl"><thead>';
    html += '<tr class="gob-groups">';
    GROUPS.forEach(function (group) {
      html += '<th class="gob-g' + (group.shade ? ' gshade' : '') + '" colspan="' + group.cols.length + '">'
        + tables.esc(group.name) + '</th>';
    });
    html += '</tr>' + headerRow(false) + '</thead><tbody id="teamstats-body">';
    rows.forEach(function (row, index) {
      if (index > 0 && index % 16 === 0) html += headerRow(true);
      var mine = sameId(row.team_id, userId);
      html += '<tr' + (mine ? ' class="me is-user"' : '') + '>';
      LEAF.forEach(function (col) {
        var cls = (col.pin ? 'pin team' : '') + (col.shade ? ' gshade' : '') + (sortKey === col.key ? ' on' : '');
        html += '<td class="' + cls.trim() + '">' + cellText(row, col) + '</td>';
      });
      html += '</tr>';
    });
    html += '</tbody></table></div></section>';
    container.innerHTML = html;
    tables.bindWide(container.querySelector('.gob-xs'));
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
    store.get(url(franchiseId)).then(function (payload) {
      apply(payload || { teams: [] });
    }).catch(function () {
      loaded = false;
      tables.paintError(container, 'Team stats could not be opened.', load);
    });
  }

  function revalidate() {
    var store = ctx && ctx.store;
    if (!loaded || !store || typeof store.revalidate !== 'function' || !franchiseId) return;
    store.revalidate(url(franchiseId)).then(function (payload) {
      if (payload) apply(payload);
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
