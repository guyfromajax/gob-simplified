/**
 * League › Rankings, mounted inside the command center.
 * Reads the rankings array already on the command-center payload.
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
  var showAll = readShowAll();
  var rankings = [];
  var signature = '';
  var userId = (ctx && ctx.teamId) || '';
  var rootBuilt = false;
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

  function paintSkeleton() {
    var html = '<div class="gob-view-skel" aria-hidden="true"><div class="gob-view-skel-bar"></div>';
    var i;
    for (i = 0; i < 8; i++) html += '<div class="gob-view-skel-row"></div>';
    html += '</div>';
    container.innerHTML = html;
    rootBuilt = false;
  }

  function showError() {
    container.innerHTML = '<div class="gob-view-error" role="alert">'
      + '<p>Rankings could not be opened.</p>'
      + '<button type="button" class="gob-view-retry">Retry</button>'
      + '</div>';
    rootBuilt = false;
    loaded = false;
    var button = container.querySelector('.gob-view-retry');
    if (button) button.addEventListener('click', load);
  }

  function buildTeamLink(row) {
    var a = document.createElement('a');
    var franchiseId = (ctx && ctx.franchiseId) || '';
    a.href = window.GOBTables.rosterHref(franchiseId, row.team_id || '', row.team_name || '', 'rankings-view');
    a.setAttribute('data-return', '');
    a.textContent = row.team_name || '';
    a.style.color = '#4a90e2';
    a.style.textDecoration = 'none';
    return a;
  }

  function render() {
    var tbody = container.querySelector('#rankings-table-body');
    if (!tbody) return;
    tbody.innerHTML = '';
    var toShow = showAll ? rankings : rankings.slice(0, 25);
    toShow.forEach(function (row) {
      var tr = document.createElement('tr');
      if (sameId(row.team_id, userId)) tr.classList.add('is-user');

      var teamTd = document.createElement('td');
      teamTd.className = 'team-cell';
      var rankSpan = document.createElement('span');
      rankSpan.textContent = (row.natl_rank != null ? row.natl_rank : '') + '. ';
      teamTd.appendChild(rankSpan);
      var nameSpan = buildTeamLink(row);
      if (row.conference === 1) {
        nameSpan.className = 'rankings-team conference-1';
        nameSpan.style.color = row.primary_color || '#000';
        nameSpan.style.fontWeight = 'bold';
      }
      teamTd.appendChild(nameSpan);
      tr.appendChild(teamTd);

      var wlTd = document.createElement('td');
      wlTd.className = 'wl-cell';
      wlTd.textContent = (row.W || 0) + '-' + (row.L || 0);
      tr.appendChild(wlTd);

      var lastWeekTd = document.createElement('td');
      var lastWeekSpan = document.createElement('span');
      var result = (row.last_week_result || '').toUpperCase();
      if (result === 'W') lastWeekSpan.className = 'last-week-win';
      else if (result === 'L') lastWeekSpan.className = 'last-week-loss';
      else if (result === 'T') lastWeekSpan.className = 'last-week-tie';
      lastWeekSpan.textContent = row.last_week || '';
      lastWeekTd.appendChild(lastWeekSpan);
      tr.appendChild(lastWeekTd);

      var nextTd = document.createElement('td');
      nextTd.textContent = row.next || '';
      tr.appendChild(nextTd);

      tbody.appendChild(tr);
    });
  }

  function ensure() {
    if (rootBuilt && container.querySelector('#rankings-table')) return;
    container.innerHTML = ''
      + '<section class="fcc-data-card rankings-page-card">'
      + '<div class="rankings-page-card-head">'
      + '<h1 class="rankings-page-title">National Rankings</h1>'
      + '<div class="rankings-toggle-wrap">'
      + '<button type="button" id="rankings-toggle-top25" class="rankings-toggle active">Top 25</button>'
      + '<button type="button" id="rankings-toggle-all" class="rankings-toggle">All 128</button>'
      + '</div></div>'
      + '<div class="fcc-data-card-body">'
      + '<table id="rankings-table" class="leaders-table standings-conference-table rankings-results-table">'
      + '<thead><tr><th>Team</th><th>W-L</th><th>Last Week</th><th>Next</th></tr></thead>'
      + '<tbody id="rankings-table-body"></tbody>'
      + '</table></div></section>';
    rootBuilt = true;
    var top = container.querySelector('#rankings-toggle-top25');
    var all = container.querySelector('#rankings-toggle-all');
    if (top) {
      top.addEventListener('click', function () {
        showAll = false;
        writeShowAll(false);
        top.classList.add('active');
        if (all) all.classList.remove('active');
        render();
      });
    }
    if (all) {
      all.addEventListener('click', function () {
        showAll = true;
        writeShowAll(true);
        all.classList.add('active');
        if (top) top.classList.remove('active');
        render();
      });
    }
    if (showAll && all) {
      all.classList.add('active');
      if (top) top.classList.remove('active');
    }
  }

  function apply(body) {
    var rows = (body && body.rankings) || [];
    var next = JSON.stringify(rows);
    var same = loaded && rootBuilt && next === signature;
    signature = next;
    rankings = rows;
    if (body) {
      userId = body.user_team_object_id || body.user_team_id || (ctx && ctx.teamId) || userId;
    }
    if (same) return;
    ensure();
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
      showError();
      return;
    }
    if (!loaded) paintSkeleton();
    store.get(url()).then(function (body) {
      apply(body);
    }).catch(function () {
      showError();
    });
  }

  function revalidate() {
    var store = ctx && ctx.store;
    if (!loaded || !store || typeof store.revalidate !== 'function') return;
    store.revalidate(url()).then(function (body) {
      if (body) apply(body);
    }).catch(function () { /* keep the mounted table */ });
  }

  function unmount() {
    container.innerHTML = '';
    rootBuilt = false;
    loaded = false;
  }

  load();
  return { unmount: unmount, revalidate: revalidate };
}

export function unmount() {}
