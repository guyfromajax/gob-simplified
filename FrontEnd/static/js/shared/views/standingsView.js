/**
 * League › Standings. Renders the standings payload. Card order puts the
 * user's conference first; team order inside a card is the API order.
 */

var COLS = [
  { key: 'rank', label: '#' },
  { key: 'team', label: 'Team', team: true },
  { key: 'W', label: 'W' },
  { key: 'L', label: 'L' },
  { key: 'pct', label: 'PCT' },
  { key: 'PF', label: 'PF' },
  { key: 'PA', label: 'PA' },
  { key: 'differential', label: 'DIFF', diff: true },
  { key: 'streak', label: 'STRK' },
  { key: 'next', label: 'NEXT', next: true }
];

function url(franchiseId, teamId) {
  var base = window.GOBTables.apiBase('/franchise/standings');
  var q = 'franchise_id=' + franchiseId;
  if (teamId) q += '&team_id=' + teamId;
  return base + '?' + q;
}

function sameId(a, b) {
  return String(a || '') !== '' && String(a) === String(b || '');
}

function num(value) {
  var n = Number(value);
  return isFinite(n) ? n : null;
}

export function mount(container, ctx) {
  var tables = window.GOBTables;
  var query = '';
  var sortKey = '';
  var sortDir = 1;
  var body = null;
  var signature = '';
  var loaded = false;
  var restored = false;
  var userId = (ctx && ctx.teamId) || '';

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
    if (input) {
      input.value = query;
      input.addEventListener('input', function () {
        query = input.value || '';
        render();
      });
    }
  }

  function ownTools() {
    tables.registerTools('standings-view', paintTools);
    tables.placeTools();
  }

  function onTab() {
    if (container.classList.contains('active')) ownTools();
  }

  function sameConference(card, userConference, userRegion) {
    if (userConference == null || String(card.conference) !== String(userConference)) return false;
    if (!userRegion) return true;
    return String(card.region || '').toUpperCase() === String(userRegion).toUpperCase();
  }

  function groups(rows, userConference, userRegion) {
    var map = Object.create(null);
    var order = [];
    rows.forEach(function (row) {
      var key = String(row.region || '') + '|' + String(row.conference == null ? '' : row.conference);
      if (!map[key]) {
        map[key] = { region: row.region || '', conference: row.conference, rows: [] };
        order.push(key);
      }
      map[key].rows.push(row);
    });
    var cards = order.map(function (key) { return map[key]; });
    function band(card) {
      if (sameConference(card, userConference, userRegion)) return 0;
      if (userRegion && String(card.region).toUpperCase() === String(userRegion).toUpperCase()) return 1;
      return 2;
    }
    cards.sort(function (a, b) {
      var delta = band(a) - band(b);
      if (delta) return delta;
      var region = String(a.region).localeCompare(String(b.region));
      if (region) return region;
      return Number(a.conference) - Number(b.conference);
    });
    return cards;
  }

  function visibleRows(rows) {
    var needle = query.trim().toLowerCase();
    return rows.filter(function (row) {
      if (!needle) return true;
      var name = String(row.display_name || row.name || '').toLowerCase();
      return name.indexOf(needle) !== -1;
    });
  }

  function readSort(row, key) {
    if (key === 'team') return String(row.display_name || row.name || '');
    if (key === 'rank') return num(row._rank);
    if (key === 'streak') return String(row.streak || '');
    if (key === 'next') return num(row.next_week);
    return num(row[key]);
  }

  function render() {
    if (!body) return;
    var rows = Array.isArray(body.standings) ? body.standings.slice() : [];
    var userConference = body.user_conference;
    var userRegion = body.user_region || '';
    if (userConference == null) {
      rows.some(function (row) {
        if (!sameId(row.team_id, userId)) return false;
        userConference = row.conference;
        if (!userRegion) userRegion = row.region || '';
        return true;
      });
    }
    var colorById = Object.create(null);
    var colorByName = Object.create(null);
    rows.forEach(function (row) {
      if (!row || !row.primary_color) return;
      if (row.team_id) colorById[row.team_id] = row.primary_color;
      if (row.name) colorByName[row.name] = row.primary_color;
      if (row.display_name) colorByName[row.display_name] = row.primary_color;
    });
    var filtered = visibleRows(rows);
    var cards = groups(filtered, userConference, userRegion);
    var franchiseId = (ctx && ctx.franchiseId) || '';
    var linkMeta = [];
    var html = '<div class="gob-tgrid">';
    if (!cards.length) {
      html += '<p class="gob-empty">No standings.</p>';
    }
    cards.forEach(function (card) {
      card.rows.forEach(function (row, index) { row._rank = index + 1; });
      var shown = sortKey ? tables.sortRows(card.rows, function (row) { return readSort(row, sortKey); }, sortDir) : card.rows;
      var maxAbs = 0;
      shown.forEach(function (row) {
        var diff = Math.abs(Number(row.differential) || 0);
        if (diff > maxAbs) maxAbs = diff;
      });
      var yours = sameConference(card, userConference, userRegion);
      var title = String(card.region || '') + String(card.conference == null ? '' : card.conference) + ' CONFERENCE';
      html += '<section class="gob-tcard"><h2>' + tables.esc(title);
      if (yours) html += '<em>· Yours</em>';
      html += '</h2><table class="gob-tbl"><thead><tr>';
      COLS.forEach(function (col) {
        var on = sortKey === col.key;
        var cls = 's' + (col.team ? ' team' : '') + (on ? ' on ' + (sortDir < 0 ? 'desc' : 'asc') : '');
        html += '<th class="' + cls + '" data-sort="' + col.key + '">' + tables.esc(col.label) + '</th>';
      });
      html += '</tr></thead><tbody>';
      shown.forEach(function (row) {
        var mine = sameId(row.team_id, userId);
        html += '<tr' + (mine ? ' class="me is-user"' : '') + '>';
        COLS.forEach(function (col) {
          var cls = (col.team ? 'team' : '') + (sortKey === col.key ? ' on' : '');
          var cell = '';
          if (col.team) {
            var name = row.display_name || row.name || '';
            var href = tables.rosterHref(franchiseId, row.team_id, name, 'standings-view')
              + '&origin=league&pager=standings';
            cell = tables.teamLink(href, name, row.name || name, row.primary_color);
            linkMeta.push({
              ids: shown.map(function (item) { return String(item.team_id || ''); }),
              label: String(card.region || '') + String(card.conference == null ? '' : card.conference)
            });
          } else if (col.diff) {
            cell = tables.diffCell(row.differential, maxAbs);
          } else if (col.next) {
            cell = tables.nextCell(
              row.next_opponent_name,
              row.next_week,
              colorById[row.next_opponent_id] || colorByName[row.next_opponent_name] || ''
            );
          } else if (col.key === 'rank') {
            cell = tables.esc(row._rank);
          } else if (col.key === 'streak') {
            cell = tables.esc(row.streak || '');
          } else if (col.key === 'pct') {
            cell = tables.esc(tables.formatPct(row.pct));
          } else if (row[col.key] == null || row[col.key] === '') {
            cell = '';
          } else {
            cell = tables.esc(row[col.key]);
          }
          html += '<td class="' + cls + '">' + cell + '</td>';
        });
        html += '</tr>';
      });
      html += '</tbody></table></section>';
    });
    html += '</div>';
    container.innerHTML = html;
    container.querySelectorAll('a.gob-team').forEach(function (link, index) {
      link.addEventListener('click', function () {
        var meta = linkMeta[index];
        if (!meta) return;
        try { sessionStorage.setItem('gob-view-standings-order', JSON.stringify(meta)); }
        catch (err) { /* the pager reads this later */ }
      });
    });
    container.querySelectorAll('th.s').forEach(function (th) {
      th.addEventListener('click', function () {
        var key = th.getAttribute('data-sort');
        if (sortKey === key) sortDir = -sortDir;
        else { sortKey = key; sortDir = key === 'team' || key === 'streak' ? 1 : -1; }
        render();
      });
    });
    ownTools();
    restoreScroll();
  }

  function apply(next) {
    var stamp = JSON.stringify(next && next.standings || []);
    if (loaded && stamp === signature) return;
    signature = stamp;
    body = next || { standings: [] };
    loaded = true;
    render();
  }

  function load() {
    var store = ctx && ctx.store;
    var franchiseId = (ctx && ctx.franchiseId) || '';
    if (!store || typeof store.get !== 'function' || !franchiseId) {
      tables.paintError(container, 'Standings could not be opened.', load);
      return;
    }
    if (!loaded) tables.paintSkeleton(container);
    store.get(url(franchiseId, userId)).then(function (payload) {
      apply(payload || { standings: [] });
    }).catch(function () {
      loaded = false;
      tables.paintError(container, 'Standings could not be opened.', load);
    });
  }

  function revalidate() {
    var store = ctx && ctx.store;
    var franchiseId = (ctx && ctx.franchiseId) || '';
    if (!loaded || !store || typeof store.revalidate !== 'function' || !franchiseId) return;
    store.revalidate(url(franchiseId, userId)).then(function (payload) {
      if (payload) apply(payload);
    }).catch(function () { /* keep the mounted cards */ });
  }

  document.addEventListener('gob-tab-shown', onTab);
  ownTools();
  load();

  return {
    revalidate: revalidate,
    unmount: function () {
      document.removeEventListener('gob-tab-shown', onTab);
      tables.registerTools('standings-view', null);
    }
  };
}

export function unmount() {}
