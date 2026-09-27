/**
 * Team drill-in. Formats GET /franchise/team-detail.
 * The roster card is the Roster grid, compact. Rates on that grid stay on the roster payload.
 */

import { barHtml, bindPager, bindUp, query, readPager, stampOrigin, withParams } from './detailBar.js';
import { orderLineup, rosterTableHtml } from './rosterView.js';

function siteWord(site) {
  return site === 'home' ? 'vs' : 'at';
}

function opponentHtml(tables, row, href) {
  var rank = row.opponent_natl_rank;
  var name = (rank ? '#' + rank + ' ' : '') + (row.opponent_name || '');
  var mark = tables.markHtml(row.opponent_name || '', row.opponent_primary_color);
  if (!href) return mark + '<span>' + tables.esc(name) + '</span>';
  return '<a class="gob-team" data-gob-drill href="' + tables.esc(href) + '">' + mark + '<span>' + tables.esc(name) + '</span></a>';
}

function teamHref(id, up) {
  return withParams({
    tab: 'team-view',
    view_team_id: id,
    player_id: '',
    pager: '',
    up: up || ''
  });
}

export function mount(container, ctx) {
  var tables = window.GOBTables;
  var franchiseId = (ctx && ctx.franchiseId) || '';
  var userId = (ctx && ctx.teamId) || '';
  var team = null;
  var roster = null;
  var signature = '';
  var loaded = false;
  var requestId = 0;

  function viewedId() {
    return query().get('view_team_id') || query().get('roster_team_id') || userId;
  }

  function detailUrl() {
    return tables.apiBase('/franchise/team-detail')
      + '?franchise_id=' + encodeURIComponent(franchiseId)
      + '&team_id=' + encodeURIComponent(viewedId());
  }

  function rosterUrl() {
    return tables.apiBase('/roster/' + encodeURIComponent(viewedId()))
      + '?franchise_id=' + encodeURIComponent(franchiseId);
  }

  function showSkeleton() {
    container.innerHTML = barHtml(tables, '', null)
      + '<div class="gob-view-skel" aria-hidden="true"><div class="gob-view-skel-bar"></div>'
      + '<div class="gob-view-skel-row"></div><div class="gob-view-skel-row"></div></div>';
    bindUp(container);
  }

  function showError() {
    container.innerHTML = barHtml(tables, '', null)
      + '<div class="gob-view-error" role="alert"><p>This team could not be opened.</p>'
      + '<button type="button" class="gob-view-retry">Retry</button></div>';
    bindUp(container);
    var button = container.querySelector('.gob-view-retry');
    if (button) button.addEventListener('click', load);
  }

  function playerHref(player) {
    var id = String((player && (player._id || player.player_id || player.id)) || '');
    return withParams({
      tab: 'player-view',
      player_id: id,
      pager: 'roster',
      up: (team && team.name) || 'Team',
      view_team_id: ''
    });
  }

  function scheduleRow(row, result) {
    var href = row.opponent_id ? teamHref(row.opponent_id, (team && team.name) || 'Team') : '';
    var site = siteWord(row.site);
    var html = '<div class="gob-sch"><span class="gob-sch-w">' + tables.esc(row.week == null ? '' : 'Wk ' + row.week) + '</span>'
      + '<span class="gob-sch-opp">' + tables.esc(site) + ' ' + opponentHtml(tables, row, href) + '</span>';
    if (result) {
      var letter = row.result || '';
      var score = (row.team_score == null ? '' : row.team_score) + '–' + (row.opp_score == null ? '' : row.opp_score);
      html += '<span class="gob-sch-res' + (letter === 'L' ? ' is-loss' : '') + '">'
        + tables.esc((letter ? letter + ' ' : '') + score) + '</span>';
    }
    return html + '</div>';
  }

  function nextLine(game) {
    if (!game) return '';
    var where = siteWord(game.site);
    var who = game.opponent_name || '';
    var week = game.week == null ? '' : 'Week ' + game.week;
    return ['Next', where + ' ' + who, week].filter(function (part) { return part && part.trim(); }).join(' · ');
  }

  function scoutHref(game) {
    if (!game || String(game.opponent_id || '') !== String(userId || '')) return '';
    if (!document.getElementById('coaches-tab')) return '';
    return withParams({ tab: 'coaches-tab', view_team_id: '', player_id: '', pager: '', up: (team && team.name) || 'Team' });
  }

  function render() {
    var body = team || {};
    var record = body.record || {};
    var pager = readPager(body.team_id || viewedId());
    var color = body.primary_color || '';
    var conf = [body.conference ? body.conference + ' Conference' : '', body.region ? 'Region ' + body.region : ''].filter(Boolean).join(' · ');
    var wins = record.wins == null ? '—' : record.wins;
    var losses = record.losses == null ? '—' : record.losses;
    var place = body.conference_place || '—';
    var rank = body.natl_rank == null ? '—' : '#' + body.natl_rank;
    var streak = body.streak || '—';
    var scout = scoutHref(body.next_game);
    var players = orderLineup((roster && roster.players) || []);
    var html = barHtml(tables, body.name || '', pager);
    html += '<section class="gob-hero' + (color ? '' : ' is-neutral') + '"'
      + (color ? ' style="--tc:' + tables.esc(color) + '"' : '') + '>'
      + '<div class="gob-hero-logo">' + tables.markHtml(body.name || '', color) + '</div>'
      + '<div class="gob-hero-id"><div class="gob-hero-k">' + tables.esc(conf) + '</div>'
      + '<h1 class="gob-hero-n">' + tables.esc(body.name || '') + '</h1>'
      + (nextLine(body.next_game) ? '<div class="gob-hero-bio">' + tables.esc(nextLine(body.next_game)) + '</div>' : '')
      + (scout ? '<div class="gob-hero-act"><a class="gob-scout" data-gob-drill href="' + tables.esc(scout) + '">Scout them</a></div>' : '')
      + '</div><div class="gob-hero-stats"><div class="gob-hs">'
      + '<div><b>' + tables.esc(wins + '–' + losses) + '</b><span>Record</span></div>'
      + '<div><b>' + tables.esc(rank) + '</b><span>National</span></div>'
      + '<div><b>' + tables.esc(place) + '</b><span>Conference</span></div>'
      + '<div><b>' + tables.esc(streak) + '</b><span>Streak</span></div>'
      + '</div></div></section>';
    html += '<div class="gob-dt-body"><section class="gob-tcard"><div class="card-h"><h3>Roster</h3><span class="meta">'
      + players.length + ' players</span></div>'
      + rosterTableHtml(tables, players, {
        lineup: true,
        userTeam: !!(roster && roster.is_user_team),
        compact: true,
        playerHref: playerHref
      })
      + '</section><section class="gob-tcard"><div class="card-h"><h3>Schedule</h3></div>';
    html += '<h4 class="gob-sub">Results</h4>';
    if (!(body.results || []).length) html += '<p class="gob-quiet">No results yet</p>';
    (body.results || []).forEach(function (row) { html += scheduleRow(row, true); });
    html += '<h4 class="gob-sub">Upcoming</h4>';
    if (!(body.upcoming || []).length) html += '<p class="gob-quiet">No games ahead</p>';
    (body.upcoming || []).forEach(function (row) { html += scheduleRow(row, false); });
    html += '</section></div>';
    container.innerHTML = html;
    var wide = container.querySelector('.gob-xs');
    if (wide) tables.bindWide(wide);
    bindUp(container);
    bindPager(container, function (id) {
      if (window.GOBViews && typeof window.GOBViews.open === 'function') {
        window.GOBViews.open(withParams({ tab: 'team-view', view_team_id: id }), 'replace');
      }
    });
    var order = players.map(function (player) {
      return String((player && (player._id || player.player_id || player.id)) || '');
    });
    container.querySelectorAll('a.gob-player').forEach(function (link) {
      link.addEventListener('click', function (event) {
        try { sessionStorage.setItem('gob-view-roster-order', JSON.stringify(order)); }
        catch (err) { /* pager reads it later */ }
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        if (window.GOBViews && typeof window.GOBViews.open === 'function') {
          window.GOBViews.open(link.getAttribute('href'), 'push');
        }
      });
    });
    container.querySelectorAll('a[data-gob-drill]').forEach(function (link) {
      if (link.classList.contains('gob-player')) return;
      link.addEventListener('click', function (event) {
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        if (window.GOBViews && typeof window.GOBViews.open === 'function') {
          window.GOBViews.open(link.getAttribute('href'), 'push');
        }
      });
    });
    if (typeof window.initAttributeTooltips === 'function') {
      window.initAttributeTooltips(container, ['[data-tooltip]']);
    }
  }

  function apply(detail, rosterBody) {
    var nextTeam = detail || {};
    var nextRoster = rosterBody || { players: [] };
    if (stampOrigin(String(nextTeam.team_id || '') === String(userId || ''), 'team-view')) return;
    var stamp = JSON.stringify({ team: nextTeam, roster: nextRoster, id: viewedId() });
    if (loaded && stamp === signature) return;
    signature = stamp;
    team = nextTeam;
    roster = nextRoster;
    loaded = true;
    render();
  }

  function load() {
    var store = ctx && ctx.store;
    if (!store || typeof store.get !== 'function' || !franchiseId || !viewedId()) {
      showError();
      return;
    }
    if (!loaded) showSkeleton();
    var token = ++requestId;
    Promise.all([store.get(detailUrl()), store.get(rosterUrl())]).then(function (pair) {
      if (token !== requestId) return;
      apply(pair[0] || {}, pair[1] || { players: [] });
    }).catch(function () {
      if (token !== requestId) return;
      loaded = false;
      showError();
    });
  }

  function revalidate() {
    var store = ctx && ctx.store;
    if (!viewedId() || !store) return;
    if (team && String(team.team_id || '') !== String(viewedId())) {
      loaded = false;
      signature = '';
      load();
      return;
    }
    if (!loaded || typeof store.revalidate !== 'function') {
      load();
      return;
    }
    var token = ++requestId;
    Promise.all([store.revalidate(detailUrl()), store.revalidate(rosterUrl())]).then(function (pair) {
      if (token !== requestId) return;
      apply(pair[0] || team, pair[1] || roster);
    }).catch(function () { /* keep the mounted page */ });
  }

  load();
  return { revalidate: revalidate, unmount: function () {} };
}

export function unmount() {}
