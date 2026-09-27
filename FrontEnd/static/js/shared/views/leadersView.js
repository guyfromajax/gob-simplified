/**
 * League › Leaders. Category boards from GET /franchise/leaders.
 * Each category uses the API default (basis omitted): PTS/REB/AST per game,
 * 3PTM/BLK/STL season totals, FG% and DEF% as percentages.
 * Full list replaces this history entry and shows the top 50 of one category.
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
var PER_GAME = { PTS: 1, REB: 1, AST: 1 };
var TOTALS = { '3PTM': 1, BLK: 1, STL: 1 };
var UNITS = { PTS: 'PPG', REB: 'RPG', AST: 'APG' };

function leadersUrl(franchiseId, viewScope, limit) {
  return window.GOBTables.apiBase('/franchise/leaders')
    + '?franchise_id=' + franchiseId
    + '&view_scope=' + viewScope
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
    ], viewScope) + tables.searchBox('Search players');
    slot.querySelectorAll('.stats-toggle button').forEach(function (button) {
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

  function initials(name) {
    var parts = String(name || '').trim().split(/\s+/).filter(Boolean);
    if (!parts.length) return '';
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
    return (parts[0].charAt(0) + parts[1].charAt(0)).toUpperCase();
  }

  function abbr(name) {
    return String(name || '').replace(/[^A-Za-z0-9]/g, '').slice(0, 3).toUpperCase();
  }

  function headerMeta(stat) {
    if (PER_GAME[stat]) return 'per game';
    if (TOTALS[stat]) return 'total';
    return '';
  }

  function unit(stat) {
    if (stat === 'FG%' || stat === 'DEF%') return '%';
    return UNITS[stat] || '';
  }

  function showValue(stat, value) {
    if (value == null || value === '') return /%$/.test(stat) ? '—' : '';
    var n = Number(value);
    if (!isFinite(n)) return String(value);
    if (TOTALS[stat]) return String(Math.round(n));
    return tables.formatOneDecimal(n);
  }

  function portraitHtml(playerId, name) {
    var letters = initials(name);
    var url = '';
    if (playerId && window.API_CONFIG && typeof window.API_CONFIG.getPlayerImageUrl === 'function') {
      url = window.API_CONFIG.getPlayerImageUrl(playerId, { size: 'card' });
    }
    if (!url) return tables.esc(letters);
    return '<img alt="" src="' + tables.esc(url) + '" data-letters="' + tables.esc(letters)
      + '" onerror="var box=this.parentNode;if(box){box.textContent=this.getAttribute(\'data-letters\')||\'\';}">';
  }

  function playerHref(playerId) {
    var q = new URLSearchParams(window.location.search);
    q.set('tab', 'player-view');
    q.set('player_id', playerId || '');
    q.set('origin', 'league');
    q.set('up', 'Leaders');
    q.set('return_tab', 'leaders-view');
    q.set('pager', 'leaders');
    q.delete('view_team_id');
    var text = q.toString();
    return window.location.pathname + (text ? '?' + text : '');
  }

  function bindPlayers(order) {
    container.querySelectorAll('a.gob-player').forEach(function (link) {
      link.addEventListener('click', function (event) {
        var list = order;
        var raw = link.getAttribute('data-order');
        if (raw) {
          try { list = JSON.parse(raw); } catch (err) { list = order; }
        }
        try { sessionStorage.setItem('gob-view-leaders-order', JSON.stringify(list)); }
        catch (err) { /* the pager reads this later */ }
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        if (window.GOBViews && typeof window.GOBViews.open === 'function') {
          window.GOBViews.open(link.getAttribute('href'), 'push');
        }
      });
    });
  }

  function teamBits(row) {
    return [row.team, row.position, row.year].filter(Boolean).join(' · ');
  }

  function renderBoard() {
    var html = '<div class="gob-ldr">';
    CATS.forEach(function (stat) {
      var rows = ((board && board[stat]) || []).filter(matches);
      if (query.trim() && !rows.length) return;
      var hero = rows[0];
      var suffix = unit(stat);
      var meta = headerMeta(stat);
      html += '<article class="gob-ldb"><header class="card-h"><h3>' + tables.esc(LABELS[stat] || stat)
        + '</h3>' + (meta ? '<span class="meta">' + tables.esc(meta) + '</span>' : '') + '</header>';
      if (hero) {
        var href = tables.rosterHref(franchiseId, hero.team_id, hero.team || '', 'leaders-view') + '&origin=league';
        var who = teamBits(hero);
        var cardIds = tables.esc(JSON.stringify(rows.slice(0, 5).map(function (item) { return String(item.player_id || ''); }).filter(Boolean)));
        var heroPlayer = hero.player_id
          ? '<a class="gob-player nm" data-order="' + cardIds + '" href="' + tables.esc(playerHref(hero.player_id)) + '">' + tables.esc(hero.name || '') + '</a>'
          : '<span class="nm">' + tables.esc(hero.name || '') + '</span>';
        html += '<div class="ldb-top' + (mine(hero) ? ' me is-user' : '') + '">'
          + '<span class="av">' + portraitHtml(hero.player_id, hero.name) + '</span>'
          + '<span class="ldb-id">' + heroPlayer
          + '<span>' + (hero.team_id
            ? '<a class="gob-team" data-return href="' + tables.esc(href) + '">' + tables.esc(who) + '</a>'
            : tables.esc(who)) + '</span></span>'
          + '<span class="ldb-v">' + tables.esc(showValue(stat, hero.value))
          + (suffix ? '<em>' + tables.esc(suffix) + '</em>' : '') + '</span></div><div class="ldb-list">';
        rows.slice(1, 5).forEach(function (row, index) {
          var rowHref = tables.rosterHref(franchiseId, row.team_id, row.team || '', 'leaders-view') + '&origin=league';
          var code = abbr(row.team);
          var rowPlayer = row.player_id
            ? '<a class="gob-player nm" data-order="' + cardIds + '" href="' + tables.esc(playerHref(row.player_id)) + '">' + tables.esc(row.name || '') + '</a>'
            : '<span class="nm">' + tables.esc(row.name || '') + '</span>';
          html += '<div class="ldb-r' + (mine(row) ? ' me is-user' : '') + '"><span>' + (index + 2) + '</span>'
            + '<span class="ldb-n">' + rowPlayer
            + (code ? '<em>' + (row.team_id
              ? '<a class="gob-team" data-return href="' + tables.esc(rowHref) + '">' + tables.esc(code) + '</a>'
              : tables.esc(code)) + '</em>' : '')
            + '</span><b>' + tables.esc(showValue(stat, row.value)) + '</b></div>';
        });
        html += '</div>';
      }
      html += '<button type="button" class="full" data-stat="' + tables.esc(stat) + '">Full list →</button></article>';
    });
    html += '</div>';
    container.innerHTML = html;
    container.querySelectorAll('.full').forEach(function (button) {
      button.addEventListener('click', function () {
        setLeader(button.getAttribute('data-stat'));
      });
    });
    var order = [];
    CATS.forEach(function (stat) {
      ((board && board[stat]) || []).filter(matches).slice(0, 5).forEach(function (row) {
        if (row.player_id) order.push(String(row.player_id));
      });
    });
    bindPlayers(order);
  }

  function renderFull() {
    var stat = expanded;
    var rows = ((full && full[stat]) || []).filter(matches);
    var html = '<section class="gob-tcard gob-full"><h2>' + tables.esc(LABELS[stat] || stat)
      + '</h2><button type="button" class="gob-board">Board</button>'
      + '<table class="gob-tbl"><thead><tr><th class="left">#</th><th class="left">Player</th><th class="left">Team</th><th>Value</th></tr></thead><tbody>';
    rows.forEach(function (row, index) {
      var href = tables.rosterHref(franchiseId, row.team_id, row.team || '', 'leaders-view') + '&origin=league';
      var nameCell = row.player_id
        ? '<a class="gob-player" href="' + tables.esc(playerHref(row.player_id)) + '">' + tables.esc(row.name || '') + '</a>'
        : tables.esc(row.name || '');
      html += '<tr' + (mine(row) ? ' class="me is-user"' : '') + '>'
        + '<td class="left">' + (index + 1) + '</td>'
        + '<td class="left">' + nameCell + '</td>'
        + '<td class="left">' + (row.team_id
          ? '<a class="gob-team" data-return href="' + tables.esc(href) + '">' + tables.esc(row.team || '') + '</a>'
          : tables.esc(row.team || '')) + '</td>'
        + '<td>' + tables.esc(showValue(stat, row.value)) + '</td></tr>';
    });
    html += '</tbody></table></section>';
    container.innerHTML = html;
    var back = container.querySelector('.gob-board');
    if (back) back.addEventListener('click', function () { setLeader(''); });
    bindPlayers(rows.map(function (row) { return String(row.player_id || ''); }).filter(Boolean));
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
    store.get(leadersUrl(franchiseId, viewScope, 5)).then(function (payload) {
      applyBoard(payload || {});
      if (expanded) loadFull();
    }).catch(fail);
  }

  function loadFull() {
    var store = ctx && ctx.store;
    if (!store || typeof store.get !== 'function' || !franchiseId) return;
    store.get(leadersUrl(franchiseId, viewScope, 50)).then(function (payload) {
      applyFull(payload || {});
    }).catch(fail);
  }

  function revalidate() {
    var store = ctx && ctx.store;
    if (!loaded || !store || typeof store.revalidate !== 'function' || !franchiseId) return;
    store.revalidate(leadersUrl(franchiseId, viewScope, expanded ? 50 : 5)).then(function (payload) {
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
