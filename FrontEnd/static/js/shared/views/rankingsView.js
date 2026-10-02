/**
 * League › Rankings, mounted inside the command center. One T1 table in the
 * Standings treatment. Reads the rankings array already on the command-center
 * payload. The payload has no previous rank, so there is no movement column.
 * Last Week links to that game's box score: the game ids come from last week's
 * GET /franchise/schedule/week, read once the table is up. Until they land, and for
 * a game with no stored id, the result is plain text.
 */

function commandCenterUrl(franchiseId) {
  var profile = '';
  try {
    if (new URLSearchParams(window.location.search).get('cc_profile') === '1') profile = '&profile=1';
  } catch (err) { /* ignore */ }
  var base = window.API_CONFIG && typeof window.API_CONFIG.buildUrl === 'function'
    ? window.API_CONFIG.buildUrl('/franchise/command-center/data')
    : '/franchise/command-center/data';
  return base + '?franchise_id=' + franchiseId + profile;
}

function sameId(a, b) {
  return String(a || '') !== '' && String(a) === String(b || '');
}

var SHOW_ALL_KEY = 'gob-view-rankings-show-all';

function readShowAll() {
  try { return sessionStorage.getItem(SHOW_ALL_KEY) === '1'; } catch (err) { return false; }
}

function writeShowAll(showAll) {
  try { sessionStorage.setItem(SHOW_ALL_KEY, showAll ? '1' : '0'); } catch (err) { /* ignore */ }
}

function backForward() {
  try {
    var nav = performance.getEntriesByType('navigation')[0];
    return !!(nav && nav.type === 'back_forward');
  } catch (err) {
    return false;
  }
}

export function mount(container, ctx) {
  var tables = window.GOBTables;
  var showAll = readShowAll();
  var rankings = [];
  var signature = '';
  var userId = (ctx && ctx.teamId) || '';
  var loaded = false;
  var restoredScroll = false;
  var gameIds = {};
  var gamesFor = '';

  function restoreScroll() {
    if (restoredScroll || !backForward()) return;
    restoredScroll = true;
    var nav = ctx && ctx.nav;
    if (!nav || typeof nav.restoreScroll !== 'function') return;
    requestAnimationFrame(function () {
      nav.restoreScroll();
      requestAnimationFrame(function () { nav.restoreScroll(); });
    });
  }

  function paintTools(slot) {
    slot.innerHTML = '<div class="stats-toggle" role="group" aria-label="Rankings shown">'
      + '<button type="button" id="rankings-toggle-top25" data-value="top25"'
      + (showAll ? '' : ' class="on"') + '>Top 25</button>'
      + '<button type="button" id="rankings-toggle-all" data-value="all"'
      + (showAll ? ' class="on"' : '') + '>All ' + tables.esc(rankings.length || 128) + '</button>'
      + '</div>';
    slot.querySelectorAll('button').forEach(function (button) {
      button.addEventListener('click', function () {
        var next = button.getAttribute('data-value') === 'all';
        if (next === showAll) return;
        showAll = next;
        writeShowAll(showAll);
        paintTools(slot);
        render();
      });
    });
  }

  function ownTools() {
    tables.registerTools('rankings-view', paintTools);
    tables.placeTools();
  }

  function onTab() {
    if (container.classList.contains('active')) ownTools();
  }

  function lastWeekCell(row) {
    var text = row.last_week || '';
    if (!text) return '';
    var result = String(row.last_week_result || '').toUpperCase();
    var tone = result === 'W' ? ' up' : (result === 'L' ? ' dn' : '');
    var mark = result ? '<span class="gob-wl' + tone + '">' + tables.esc(result) + '</span> ' : '';
    var gameId = gameIds[String(row.team_id || '')];
    if (!gameId) return mark + tables.esc(text);
    // `data-return`: GOBNav adds return_url on the click, so the box score opens as a
    // read and its Back comes here.
    return '<a class="gob-res" data-return href="' + tables.esc(boxHref(gameId)) + '">'
      + mark + tables.esc(text) + '</a>';
  }

  function boxHref(gameId) {
    return '/box-score.html?game_id=' + encodeURIComponent(gameId)
      + '&mode=franchise&franchise_id=' + encodeURIComponent((ctx && ctx.franchiseId) || '')
      + '&team_id=' + encodeURIComponent(userId);
  }

  /** Last week's games, by team: the id that turns a Last Week result into a link. */
  function loadLastWeek(week) {
    var store = ctx && ctx.store;
    var franchiseId = (ctx && ctx.franchiseId) || '';
    var previous = Number(week) - 1;
    if (!store || typeof store.get !== 'function' || !franchiseId || !(previous >= 1)) return;
    var key = franchiseId + ':' + previous;
    if (gamesFor === key) return;
    gamesFor = key;
    store.get(tables.apiBase('/franchise/schedule/week')
      + '?franchise_id=' + encodeURIComponent(franchiseId)
      + '&week=' + encodeURIComponent(previous)).then(function (body) {
      if (gamesFor !== key) return;
      var next = {};
      ((body && body.games) || []).forEach(function (game) {
        if (!game || game.status !== 'complete' || !game.game_id) return;
        [game.away, game.home].forEach(function (side) {
          if (side && side.team_id) next[String(side.team_id)] = String(game.game_id);
        });
      });
      gameIds = next;
      if (loaded && container.querySelector('#rankings-table')) render();
    }).catch(function () {
      // The results stay plain text; the next visit asks again.
      if (gamesFor === key) gamesFor = '';
    });
  }

  function render() {
    var franchiseId = (ctx && ctx.franchiseId) || '';
    var shown = showAll ? rankings : rankings.slice(0, 25);
    // Families (Styleguide › Tables): (#, Team, W, L), (PF, PA), Last Week, Next.
    var html = '<section class="gob-tcard gob-rank gob-fam"><h2>National Rankings</h2>'
      + '<table id="rankings-table" class="gob-tbl"><thead><tr>'
      + '<th class="rk fs">#</th><th class="team">Team</th><th>W</th><th class="fe">L</th>'
      + '<th class="fs">PF</th><th class="fe">PA</th>'
      + '<th class="left fs fe">Last Week</th><th class="left fs fe">Next</th>'
      + '</tr></thead><tbody id="rankings-table-body">';
    if (!shown.length) html += '<tr><td class="team" colspan="8">No rankings yet.</td></tr>';
    shown.forEach(function (row) {
      var mine = sameId(row.team_id, userId);
      var name = row.team_name || '';
      var href = tables.rosterHref(franchiseId, row.team_id || '', name, 'rankings-view');
      html += '<tr' + (mine ? ' class="me is-user"' : '') + '>'
        + '<td class="rk fs">' + tables.esc(row.natl_rank != null ? row.natl_rank : '') + '</td>'
        + '<td class="team">' + tables.teamLink(href, name, name, row.primary_color) + '</td>'
        + '<td>' + tables.esc(row.W || 0) + '</td>'
        + '<td class="fe">' + tables.esc(row.L || 0) + '</td>'
        + '<td class="fs">' + tables.esc(row.PF != null ? row.PF : '') + '</td>'
        + '<td class="fe">' + tables.esc(row.PA != null ? row.PA : '') + '</td>'
        + '<td class="left fs fe">' + lastWeekCell(row) + '</td>'
        + '<td class="left fs fe">' + tables.esc(row.next || '') + '</td>'
        + '</tr>';
    });
    html += '</tbody></table></section>';
    container.innerHTML = html;
    ownTools();
  }

  function apply(body) {
    var rows = (body && body.rankings) || [];
    var next = JSON.stringify(rows);
    var same = loaded && next === signature && !!container.querySelector('#rankings-table');
    signature = next;
    rankings = rows;
    if (body) {
      userId = body.user_team_object_id || body.user_team_id || (ctx && ctx.teamId) || userId;
    }
    if (body) loadLastWeek(body.week);
    if (same) return;
    render();
    loaded = true;
    restoreScroll();
  }

  function url() {
    return commandCenterUrl((ctx && ctx.franchiseId) || '');
  }

  function load() {
    var store = ctx && ctx.store;
    if (!store || typeof store.get !== 'function') {
      loaded = false;
      tables.paintError(container, 'Rankings could not be opened.', load);
      return;
    }
    if (!loaded) tables.paintSkeleton(container);
    store.get(url()).then(function (body) {
      apply(body);
    }).catch(function () {
      loaded = false;
      tables.paintError(container, 'Rankings could not be opened.', load);
    });
  }

  function revalidate() {
    var store = ctx && ctx.store;
    if (!loaded || !store || typeof store.revalidate !== 'function') return;
    store.revalidate(url()).then(function (body) {
      if (body) apply(body);
    }).catch(function () { /* keep the mounted table */ });
  }

  document.addEventListener('gob-tab-shown', onTab);
  ownTools();
  load();

  return {
    revalidate: revalidate,
    unmount: function () {
      document.removeEventListener('gob-tab-shown', onTab);
      tables.registerTools('rankings-view', null);
      container.innerHTML = '';
      loaded = false;
    }
  };
}

export function unmount() {}
