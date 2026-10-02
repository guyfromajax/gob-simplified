/**
 * League › Rankings, mounted inside the command center. One T1 table in the
 * Standings treatment. Reads the rankings array already on the command-center
 * payload. The payload has no previous rank, so there is no movement column.
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
    return mark + tables.esc(text);
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
