/**
 * League › Leaders. Category boards from GET /franchise/leaders.
 * Conference / National and Per game / Totals are query params. Full list
 * replaces this history entry and shows the top 50 of one category.
 */

var CATS = ['PTS', '3PTM', 'AST', 'BLK', 'FG%', 'REB', 'STL', 'DEF%'];
var LABELS = {
  PTS: 'Points',
  '3PTM': '3-Pointers',
  AST: 'Assists',
  BLK: 'Blocks',
  'FG%': 'FG%',
  REB: 'Rebounds',
  STL: 'Steals',
  'DEF%': 'DEF%'
};
var FALLBACK_CAPTION = {
  'FG%': 'min 5 FGA per team game',
  'DEF%': 'min 6 DEF_A per team game'
};

function leadersUrl(franchiseId, viewScope, basis, limit) {
  return window.GOBTables.apiBase('/franchise/leaders')
    + '?franchise_id=' + franchiseId
    + '&view_scope=' + viewScope
    + '&basis=' + basis
    + '&limit=' + limit;
}

function sameId(a, b) {
  return String(a || '') !== '' && String(a) === String(b || '');
}

function leaderParam() {
  try { return new URLSearchParams(window.location.search).get('leader') || ''; }
  catch (err) { return ''; }
}

export function mount(container, ctx) {
  var tables = window.GOBTables;
  var viewScope = tables.readKey('gob-view-leaders-scope', 'conference');
  if (viewScope !== 'national') viewScope = 'conference';
  var basis = tables.readKey('gob-view-leaders-basis', 'per_game');
  if (basis !== 'totals') basis = 'per_game';
  var query = '';
  var expanded = leaderParam();
  var board = null;
  var full = null;
  var boardSig = '';
  var fullSig = '';
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

  function setLeader(stat) {
    var params = new URLSearchParams(window.location.search);
    if (stat) params.set('leader', stat);
    else params.delete('leader');
    var qs = params.toString();
    window.history.replaceState(window.history.state, '', window.location.pathname + (qs ? '?' + qs : ''));
    if (window.GOBNav && typeof window.GOBNav.syncCurrent === 'function') window.GOBNav.syncCurrent();
    expanded = stat || '';
    tables.resetScroll();
    if (expanded && !full) loadFull();
    else render();
  }

  function paintTools(slot) {
    slot.innerHTML = tables.segment([
      { id: 'conference', label: 'Conference' },
      { id: 'national', label: 'National' }
    ], viewScope) + tables.segment([
      { id: 'per_game', label: 'Per game' },
      { id: 'totals', label: 'Totals' }
    ], basis) + tables.searchBox('Search players');
    var toggles = slot.querySelectorAll('.stats-toggle');
    toggles[0].querySelectorAll('button').forEach(function (button) {
      button.addEventListener('click', function () {
        var next = button.getAttribute('data-value');
        if (!next || next === viewScope) return;
        viewScope = next;
        tables.writeKey('gob-view-leaders-scope', viewScope);
        board = null;
        full = null;
        loaded = false;
        tables.resetScroll();
        load();
      });
    });
    toggles[1].querySelectorAll('button').forEach(function (button) {
      button.addEventListener('click', function () {
        var next = button.getAttribute('data-value');
        if (!next || next === basis) return;
        basis = next;
        tables.writeKey('gob-view-leaders-basis', basis);
        board = null;
        full = null;
        loaded = false;
        tables.resetScroll();
        load();
      });
    });
    var input = slot.querySelector('input');
    if (input) {
      input.value = query;
      input.addEventListener('input', function () {
        query = input.value || '';
        render();
      });
    }
  }

  function ownTools() {
    tables.registerTools('leaders-view', paintTools);
    tables.placeTools();
  }

  function onTab() {
    if (container.classList.contains('active')) ownTools();
  }

  function mine(row) {
    return sameId(row.team_id, userId);
  }

  function matches(row) {
    var needle = query.trim().toLowerCase();
    if (!needle) return true;
    var blob = (String(row.name || '') + ' ' + String(row.team || '')).toLowerCase();
    return blob.indexOf(needle) !== -1;
  }

  function captionFor(stat, rows) {
    if (stat !== 'FG%' && stat !== 'DEF%') return '';
    var i;
    for (i = 0; i < rows.length; i++) {
      if (rows[i] && rows[i].qualification_caption) return rows[i].qualification_caption;
    }
    return FALLBACK_CAPTION[stat] || '';
  }

  function person(row, rank) {
    var name = row.name || '';
    var meta = [row.position, row.year, row.team].filter(Boolean).join(' · ');
    var href = tables.rosterHref(franchiseId, row.team_id, row.team || '', 'leaders-view');
    return '<span class="rk">' + rank + '</span>'
      + '<span class="nm"><span>' + tables.esc(name) + '</span>'
      + (meta ? '<span class="sub">' + (row.team_id
        ? '<a class="gob-team" data-return href="' + tables.esc(href) + '">' + tables.esc(meta) + '</a>'
        : tables.esc(meta)) + '</span>' : '')
      + '</span><span class="val">' + tables.esc(row.value) + '</span>';
  }

  function renderBoard() {
    var html = '<div class="gob-ldr">';
    CATS.forEach(function (stat) {
      var rows = ((board && board[stat]) || []).filter(matches);
      if (query.trim() && !rows.length) return;
      var hero = rows[0];
      html += '<article class="gob-ldb"><header><span>' + tables.esc(LABELS[stat] || stat) + '</span></header>';
      if (hero) {
        html += '<div class="hero' + (mine(hero) ? ' me is-user' : '') + '">' + person(hero, 1) + '</div><ol>';
        rows.slice(1, 5).forEach(function (row, index) {
          html += '<li class="' + (mine(row) ? 'me is-user' : '') + '">' + person(row, index + 2) + '</li>';
        });
        html += '</ol>';
      }
      html += '<button type="button" class="full" data-stat="' + tables.esc(stat) + '">Full list →</button>';
      var cap = captionFor(stat, (board && board[stat]) || []);
      if (cap) html += '<p class="cap">' + tables.esc(cap) + '</p>';
      html += '</article>';
    });
    html += '</div>';
    container.innerHTML = html;
    container.querySelectorAll('.full').forEach(function (button) {
      button.addEventListener('click', function () {
        setLeader(button.getAttribute('data-stat'));
      });
    });
  }

  function renderFull() {
    var stat = expanded;
    var rows = ((full && full[stat]) || []).filter(matches);
    var html = '<section class="gob-tcard gob-full"><h2>' + tables.esc(LABELS[stat] || stat)
      + '</h2><button type="button" class="gob-board">Board</button>'
      + '<table class="gob-tbl"><thead><tr><th class="left">#</th><th class="left">Player</th><th class="left">Team</th><th>Value</th></tr></thead><tbody>';
    rows.forEach(function (row, index) {
      var href = tables.rosterHref(franchiseId, row.team_id, row.team || '', 'leaders-view');
      html += '<tr' + (mine(row) ? ' class="me is-user"' : '') + '>'
        + '<td class="left">' + (index + 1) + '</td>'
        + '<td class="left">' + tables.esc(row.name || '') + '</td>'
        + '<td class="left">' + (row.team_id
          ? '<a class="gob-team" data-return href="' + tables.esc(href) + '">' + tables.esc(row.team || '') + '</a>'
          : tables.esc(row.team || '')) + '</td>'
        + '<td>' + tables.esc(row.value) + '</td></tr>';
    });
    html += '</tbody></table>';
    var cap = captionFor(stat, (full && full[stat]) || []);
    if (cap) html += '<p class="cap">' + tables.esc(cap) + '</p>';
    html += '</section>';
    container.innerHTML = html;
    var back = container.querySelector('.gob-board');
    if (back) back.addEventListener('click', function () { setLeader(''); });
  }

  function render() {
    if (expanded) renderFull();
    else renderBoard();
    ownTools();
    restoreScroll();
  }

  function applyBoard(payload) {
    var stamp = JSON.stringify(payload || {});
    if (loaded && stamp === boardSig && !expanded) return;
    boardSig = stamp;
    board = payload || {};
    loaded = true;
    if (!expanded) render();
  }

  function applyFull(payload) {
    var stamp = JSON.stringify(payload || {});
    if (stamp === fullSig && expanded) return;
    fullSig = stamp;
    full = payload || {};
    if (expanded) render();
  }

  function fail() {
    loaded = false;
    tables.paintError(container, 'Leaders could not be opened.', load);
  }

  function load() {
    var store = ctx && ctx.store;
    if (!store || typeof store.get !== 'function' || !franchiseId) {
      fail();
      return;
    }
    if (!loaded) tables.paintSkeleton(container);
    store.get(leadersUrl(franchiseId, viewScope, basis, 5)).then(function (payload) {
      applyBoard(payload || {});
      if (expanded) loadFull();
    }).catch(fail);
  }

  function loadFull() {
    var store = ctx && ctx.store;
    if (!store || typeof store.get !== 'function' || !franchiseId) return;
    store.get(leadersUrl(franchiseId, viewScope, basis, 50)).then(function (payload) {
      applyFull(payload || {});
    }).catch(fail);
  }

  function revalidate() {
    var store = ctx && ctx.store;
    if (!loaded || !store || typeof store.revalidate !== 'function' || !franchiseId) return;
    store.revalidate(leadersUrl(franchiseId, viewScope, basis, expanded ? 50 : 5)).then(function (payload) {
      if (!payload) return;
      if (expanded) applyFull(payload);
      else applyBoard(payload);
    }).catch(function () { /* keep the mounted board */ });
  }

  document.addEventListener('gob-tab-shown', onTab);
  ownTools();
  load();

  return {
    revalidate: revalidate,
    unmount: function () {
      document.removeEventListener('gob-tab-shown', onTab);
      tables.registerTools('leaders-view', null);
    }
  };
}

export function unmount() {}
