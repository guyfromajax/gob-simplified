/**
 * Team › Player Stats. Wide grouped table. Rates and per-game values come
 * from GET /franchise/player-stats. This view only formats them.
 */

var GROUPS = [
  { name: '', shade: false, cols: [
    { key: 'name', label: 'Player', pin: true }
  ]},
  { name: '', shade: true, cols: [
    { key: 'GP', label: 'GP' },
    { key: 'MIN', label: 'MIN' }
  ]},
  { name: 'Scoring', shade: false, cols: [
    { key: 'PTS', label: 'PTS' },
    { key: 'FGM', label: 'FGM' },
    { key: 'FGA', label: 'FGA' },
    { key: 'fg_pct', label: 'FG%', rate: true }
  ]},
  { name: '3PT', shade: true, cols: [
    { key: '3PTM', label: '3PTM' },
    { key: '3PTA', label: '3PTA' },
    { key: 'tp_pct', label: '3PT%', rate: true }
  ]},
  { name: 'Free throws', shade: false, cols: [
    { key: 'FTM', label: 'FTM' },
    { key: 'FTA', label: 'FTA' },
    { key: 'ft_pct', label: 'FT%', rate: true }
  ]},
  { name: 'Rebounding', shade: true, cols: [
    { key: 'OREB', label: 'OREB' },
    { key: 'DREB', label: 'DREB' },
    { key: 'REB', label: 'REB' }
  ]},
  { name: 'Playmaking', shade: false, cols: [
    { key: 'AST', label: 'AST' },
    { key: 'TO', label: 'TO' }
  ]},
  { name: 'Defense', shade: true, cols: [
    { key: 'STL', label: 'STL' },
    { key: 'BLK', label: 'BLK' },
    { key: 'def_pct', label: 'DEF%', rate: true }
  ]},
  { name: '', shade: false, cols: [
    { key: 'F', label: 'F' }
  ]}
];

var LEAF = [];
GROUPS.forEach(function (group) {
  group.cols.forEach(function (col) {
    LEAF.push({
      key: col.key,
      label: col.label,
      pin: !!col.pin,
      shade: group.shade,
      rate: !!col.rate
    });
  });
});

function statsUrl(franchiseId, teamId) {
  return window.GOBTables.apiBase('/franchise/player-stats')
    + '?franchise_id=' + encodeURIComponent(franchiseId)
    + '&team_id=' + encodeURIComponent(teamId);
}

function initials(name) {
  var parts = String(name || '').trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return '';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0].charAt(0) + parts[parts.length - 1].charAt(0)).toUpperCase();
}

function portraitHtml(tables, row) {
  var letters = initials(row.name);
  var pid = row.player_id;
  var src = '';
  if (pid && window.API_CONFIG && typeof window.API_CONFIG.getPlayerImageUrl === 'function') {
    src = window.API_CONFIG.getPlayerImageUrl(pid, { size: 'card' });
  }
  if (!src) return tables.esc(letters);
  return '<img alt="" src="' + tables.esc(src) + '" data-letters="' + tables.esc(letters)
    + '" onerror="var box=this.parentNode;if(box){box.textContent=this.getAttribute(\'data-letters\')||\'\';}">';
}

function subline(row) {
  var pos = row.position && row.position !== '--' ? String(row.position) : '';
  var yr = row.year && row.year !== '--' ? String(row.year) : '';
  if (pos && yr) return pos + ' · ' + yr;
  return pos || yr;
}

export function mount(container, ctx) {
  var tables = window.GOBTables;
  var basis = 'per_game';
  var sortKey = 'PTS';
  var sortDir = -1;
  var players = [];
  var signature = '';
  var loaded = false;
  var restored = false;
  var wide = false;
  var franchiseId = (ctx && ctx.franchiseId) || '';
  var teamId = (ctx && ctx.teamId) || '';

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
    slot.innerHTML = tables.segment([
      { id: 'per_game', label: 'Per game' },
      { id: 'totals', label: 'Totals' }
    ], basis);
    slot.querySelectorAll('button').forEach(function (button) {
      button.addEventListener('click', function () {
        var next = button.getAttribute('data-value') || '';
        if (!next || next === basis) return;
        basis = next;
        slot.querySelectorAll('button').forEach(function (other) {
          other.classList.toggle('on', other === button);
        });
        render();
      });
    });
  }

  function ownTools() {
    tables.registerTools('player-stats-view', paintTools);
    tables.placeTools();
  }

  function onTab() {
    if (container.classList.contains('active')) ownTools();
  }

  function bag(row) {
    return (basis === 'totals' ? row.totals : row.per_game) || {};
  }

  function valueOf(row, col) {
    if (col.key === 'name') return String(row.name || '');
    if (col.rate) {
      var rate = row.rates ? row.rates[col.key] : null;
      return rate == null || rate === '' ? null : Number(rate);
    }
    var raw = bag(row)[col.key];
    return raw == null || raw === '' ? null : Number(raw);
  }

  function cellText(row, col) {
    var value = valueOf(row, col);
    if (col.key === 'name') {
      var name = row.name || 'Player';
      var sub = subline(row);
      return '<a class="gob-team gob-player" href="' + tables.esc(playerHref(row.player_id)) + '">'
        + '<span class="av">' + portraitHtml(tables, row) + '</span>'
        + '<span class="gob-id"><span>' + tables.esc(name) + '</span>'
        + (sub ? '<span class="sub">' + tables.esc(sub) + '</span>' : '')
        + '</span></a>';
    }
    if (value == null || !isFinite(value)) return '—';
    if (col.rate || (basis === 'per_game' && col.key !== 'GP')) {
      var text = tables.formatOneDecimal(value);
      return text === '' ? '—' : tables.esc(text);
    }
    return tables.esc(String(Math.round(value)));
  }

  function playerHref(pid) {
    var q = new URLSearchParams(window.location.search);
    q.set('tab', 'player-view');
    q.set('player_id', pid);
    q.set('origin', 'team');
    q.set('return_tab', 'player-stats-view');
    q.set('pager', 'player-stats');
    q.delete('view_team_id');
    q.delete('id');
    var text = q.toString();
    return window.location.pathname + (text ? '?' + text : '');
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
    var rows = players.slice();
    var col = null;
    LEAF.forEach(function (item) { if (item.key === sortKey) col = item; });
    if (col) rows = tables.sortRows(rows, function (row) { return valueOf(row, col); }, sortDir);
    var html = '<section class="gob-tcard"><div class="gob-scroll' + (wide ? ' gob-xs' : '') + '"><table class="gob-tbl"><thead>';
    html += '<tr class="gob-groups">';
    GROUPS.forEach(function (group, index) {
      html += '<th class="gob-g' + (index === 0 ? ' pin team' : '') + (group.shade ? ' gshade' : '')
        + '" colspan="' + group.cols.length + '">' + tables.esc(group.name) + '</th>';
    });
    html += '</tr>' + headerRow(false) + '</thead><tbody id="player-stats-body">';
    rows.forEach(function (row, index) {
      if (wide && index > 0 && index % 16 === 0) html += headerRow(true);
      html += '<tr data-pid="' + tables.esc(row.player_id) + '">';
      LEAF.forEach(function (leaf) {
        var cls = (leaf.pin ? 'pin team' : '') + (leaf.shade ? ' gshade' : '') + (sortKey === leaf.key ? ' on' : '');
        html += '<td class="' + cls.trim() + '" data-k="' + leaf.key + '">' + cellText(row, leaf) + '</td>';
      });
      html += '</tr>';
    });
    html += '</tbody></table></div></section>';
    container.innerHTML = html;
    var scroller = container.querySelector('.gob-scroll');
    var table = scroller.querySelector('table');
    var limit = scroller.clientWidth;
    var nextWide = table.scrollWidth > limit + 1;
    if (nextWide !== wide) {
      wide = nextWide;
      render();
      return;
    }
    tables.bindWide(scroller);
    container.querySelectorAll('th.s').forEach(function (th) {
      th.addEventListener('click', function () {
        var key = th.getAttribute('data-sort');
        if (sortKey === key) sortDir = -sortDir;
        else {
          sortKey = key;
          sortDir = key === 'name' ? 1 : -1;
        }
        render();
      });
    });
    var order = rows.map(function (row) { return row.player_id; });
    function openPlayer(link, event) {
      try { sessionStorage.setItem('gob-view-player-stats-order', JSON.stringify(order)); }
      catch (err) { /* the pager reads this later */ }
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button) return;
      event.preventDefault();
      if (window.GOBViews && typeof window.GOBViews.open === 'function') {
        window.GOBViews.open(link.getAttribute('href'), 'push');
      }
    }
    container.querySelectorAll('a.gob-player').forEach(function (link) {
      link.addEventListener('click', function (event) { openPlayer(link, event); });
    });
    var body = container.querySelector('tbody');
    if (body) {
      body.addEventListener('click', function (event) {
        if (event.target.closest('a')) return;
        var row = event.target.closest('tr[data-pid]');
        if (!row || !body.contains(row)) return;
        var link = row.querySelector('a.gob-player');
        if (link) link.click();
      });
    }
    ownTools();
    restoreScroll();
  }

  function apply(payload) {
    var next = payload && Array.isArray(payload.players) ? payload.players : [];
    var stamp = JSON.stringify(next);
    if (loaded && stamp === signature) return;
    signature = stamp;
    players = next;
    loaded = true;
    render();
  }

  function load() {
    var store = ctx && ctx.store;
    if (!store || typeof store.get !== 'function' || !franchiseId || !teamId) {
      tables.paintError(container, 'Player stats could not be opened.', load);
      return;
    }
    if (!loaded) tables.paintSkeleton(container);
    store.get(statsUrl(franchiseId, teamId)).then(function (payload) {
      apply(payload || { players: [] });
    }).catch(function () {
      loaded = false;
      tables.paintError(container, 'Player stats could not be opened.', load);
    });
  }

  function revalidate() {
    var store = ctx && ctx.store;
    if (!loaded || !store || typeof store.revalidate !== 'function' || !franchiseId || !teamId) return;
    store.revalidate(statsUrl(franchiseId, teamId)).then(function (payload) {
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
      tables.registerTools('player-stats-view', null);
    }
  };
}

export function unmount() {}
