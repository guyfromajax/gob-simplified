/**
 * Team › Schedule. Four week columns from GET /franchise/team-detail.
 * The view formats site, the W/L letter, and the next-game row. It does not
 * decide who won.
 */

var COLUMNS = [
  { label: 'Weeks 1–7', from: 1, to: 7 },
  { label: 'Weeks 8–14', from: 8, to: 14 },
  { label: 'Weeks 15–21', from: 15, to: 21 },
  { label: 'Weeks 22–26', from: 22, to: 26, eos: true }
];

var EOS_ROWS = [
  'Conference Tournaments',
  'Region Tournaments',
  'National Tournament'
];

function detailUrl(tables, franchiseId, teamId) {
  return tables.apiBase('/franchise/team-detail')
    + '?franchise_id=' + encodeURIComponent(franchiseId)
    + '&team_id=' + encodeURIComponent(teamId);
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
  var franchiseId = (ctx && ctx.franchiseId) || '';
  var teamId = (ctx && ctx.teamId) || '';
  var loaded = false;
  var restoredScroll = false;
  var signature = '';

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

  function teamHref(viewTeamId) {
    var q = new URLSearchParams(window.location.search);
    q.set('tab', 'team-view');
    q.set('view_team_id', viewTeamId);
    q.set('origin', 'team');
    q.set('return_tab', 'team-schedule-view');
    q.delete('player_id');
    q.delete('pager');
    q.delete('up');
    var text = q.toString();
    return window.location.pathname + (text ? '?' + text : '');
  }

  function boxHref(gameId) {
    return '/box-score.html?game_id=' + encodeURIComponent(gameId)
      + '&mode=franchise&franchise_id=' + encodeURIComponent(franchiseId)
      + '&team_id=' + encodeURIComponent(teamId);
  }

  function rankName(row) {
    var rank = Number(row.opponent_natl_rank);
    var name = row.opponent_name || '';
    if (isFinite(rank) && rank >= 1 && rank < 999) return '#' + rank + ' ' + name;
    return name;
  }

  function opponentCell(row) {
    var name = row.opponent_name || '';
    var record = (row.opponent_wins == null ? '0' : row.opponent_wins)
      + '-' + (row.opponent_losses == null ? '0' : row.opponent_losses);
    return '<a class="gob-team" data-gob-drill href="' + tables.esc(teamHref(row.opponent_id)) + '">'
      + tables.markHtml(name, row.opponent_primary_color)
      + '<span class="gob-id"><span title="' + tables.esc(rankName(row)) + '">' + tables.esc(rankName(row)) + '</span>'
      + '<span class="sub">' + tables.esc(record) + '</span></span></a>';
  }

  function resultCell(row) {
    if (row.kind !== 'played') return '';
    var letter = '';
    if (row.result === 'W' || row.result === 'L') {
      letter = '<span class="gob-wl ' + (row.result === 'W' ? 'up' : 'dn') + '">'
        + row.result + '</span> ';
    }
    var text = letter + tables.esc(String(row.team_score) + '-' + String(row.opp_score));
    if (!row.game_id) return text;
    return '<a class="gob-res" href="' + tables.esc(boxHref(row.game_id)) + '">' + text + '</a>';
  }

  function rowHtml(row) {
    var cls = row.kind === 'next' ? 'is-next' : (row.kind === 'open' ? 'is-open' : '');
    var site = row.kind === 'open' ? '' : (row.site === 'home' ? 'vs' : 'at');
    var opponent = row.kind === 'open' ? 'Open' : opponentCell(row);
    return '<tr' + (cls ? ' class="' + cls + '"' : '') + ' data-week="' + row.week + '">'
      + '<td class="wk">' + row.week + '</td>'
      + '<td class="site">' + site + '</td>'
      + '<td class="team">' + opponent + '</td>'
      + '<td class="res">' + resultCell(row) + '</td></tr>';
  }

  function columnHtml(column, rows) {
    var body = rows.filter(function (row) {
      return row.week >= column.from && row.week <= column.to;
    }).map(rowHtml).join('');
    if (column.eos) {
      EOS_ROWS.forEach(function (label) {
        body += '<tr class="is-eos"><td class="wk"></td><td class="team" colspan="3">'
          + tables.esc(label) + '</td></tr>';
      });
    }
    return '<section class="gob-tcard gob-schcol"><table class="gob-tbl gob-schwk">'
      + '<colgroup><col class="c-wk"><col class="c-site"><col><col class="c-res"></colgroup>'
      + '<thead><tr><th colspan="4">' + tables.esc(column.label) + '</th></tr></thead>'
      + '<tbody>' + body + '</tbody></table></section>';
  }

  function seasonRows(payload) {
    var byWeek = {};
    (payload.upcoming || []).forEach(function (row) {
      byWeek[row.week] = Object.assign({ kind: 'upcoming' }, row);
    });
    if (payload.next_game) {
      byWeek[payload.next_game.week] = Object.assign({ kind: 'next' }, payload.next_game);
    }
    (payload.results || []).forEach(function (row) {
      byWeek[row.week] = Object.assign({ kind: 'played' }, row);
    });
    var rows = [];
    var week;
    for (week = 1; week <= 26; week++) {
      rows.push(byWeek[week] || { week: week, kind: 'open' });
    }
    return rows;
  }

  function render(payload) {
    var rows = seasonRows(payload);
    container.innerHTML = '<div class="gob-schcols">'
      + COLUMNS.map(function (column) { return columnHtml(column, rows); }).join('')
      + '</div>';
    container.querySelectorAll('a[data-gob-drill]').forEach(function (link) {
      link.addEventListener('click', function (event) {
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button) return;
        event.preventDefault();
        if (window.GOBViews && typeof window.GOBViews.open === 'function') {
          window.GOBViews.open(link.getAttribute('href'), 'push');
        }
      });
    });
    restoreScroll();
  }

  function apply(payload) {
    var stamp = JSON.stringify(payload || {});
    if (loaded && stamp === signature) return;
    signature = stamp;
    loaded = true;
    render(payload || {});
  }

  function load() {
    var store = ctx && ctx.store;
    if (!store || typeof store.get !== 'function' || !franchiseId || !teamId) {
      tables.paintError(container, 'Schedule could not be opened.', load);
      return;
    }
    if (!loaded) tables.paintSkeleton(container);
    store.get(detailUrl(tables, franchiseId, teamId)).then(function (payload) {
      apply(payload || {});
    }).catch(function () {
      loaded = false;
      tables.paintError(container, 'Schedule could not be opened.', load);
    });
  }

  function revalidate() {
    var store = ctx && ctx.store;
    if (!loaded || !store || typeof store.revalidate !== 'function' || !franchiseId || !teamId) return;
    store.revalidate(detailUrl(tables, franchiseId, teamId)).then(function (payload) {
      if (payload) apply(payload);
    }).catch(function () { /* keep the mounted table */ });
  }

  function onTab(event) {
    var tab = event && event.detail && event.detail.tab;
    if (tab === 'team-schedule-view') revalidate();
  }

  document.addEventListener('gob-tab-shown', onTab);
  load();

  return {
    revalidate: revalidate,
    unmount: function () {
      document.removeEventListener('gob-tab-shown', onTab);
    }
  };
}

export function unmount() {}
