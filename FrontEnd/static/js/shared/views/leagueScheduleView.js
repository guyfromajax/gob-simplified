/**
 * League › Schedule. One national week from GET /franchise/schedule/week, as a
 * four-column grid of compact game cards. Order, scores, ranks, and which weeks
 * have games come from that payload. Only top-25 ranks are shown.
 *
 * A card's footer is the tournament round, or Final with the box score. An unplayed
 * regular-season game has nothing to say there, so it has no footer. In Region
 * Tourney R1 (week 30) the payload also lists the teams with a bye: each is a card in
 * the same style, the team over "Bye", and the week reads region by region, A to H.
 */

function weekUrl(tables, franchiseId, week) {
  var url = tables.apiBase('/franchise/schedule/week')
    + '?franchise_id=' + encodeURIComponent(franchiseId);
  if (week != null) url += '&week=' + encodeURIComponent(week);
  return url;
}

function weekFromUrl() {
  try {
    var raw = new URLSearchParams(window.location.search).get('week');
    var n = Number(raw);
    if (raw != null && raw !== '' && isFinite(n)) return n;
  } catch (err) { /* the server picks the current week */ }
  return null;
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
  var payload = null;
  var loaded = false;
  var restoredScroll = false;
  var signature = '';
  var requested = weekFromUrl();

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

  function writeWeek(week) {
    try {
      var url = new URL(window.location.href);
      url.searchParams.set('tab', 'league-schedule-view');
      url.searchParams.set('week', String(week));
      var next = url.pathname + url.search + url.hash;
      if (next === window.location.pathname + window.location.search + window.location.hash) return;
      window.history.replaceState(window.history.state, '', next);
      if (window.GOBNav && typeof window.GOBNav.syncCurrent === 'function') window.GOBNav.syncCurrent();
    } catch (err) { /* the table still shows the week */ }
  }

  function teamHref(viewTeamId) {
    var q = new URLSearchParams(window.location.search);
    q.set('tab', 'team-view');
    q.set('view_team_id', viewTeamId);
    q.set('origin', 'league');
    q.set('return_tab', 'league-schedule-view');
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

  function rankHtml(side) {
    var rank = Number(side && side.natl_rank);
    if (!isFinite(rank) || rank < 1 || rank > 25) return '';
    return '<span class="rk">' + tables.esc(rank) + '</span>';
  }

  function sideRow(side, score, won) {
    var name = (side && side.name) || 'TBD';
    var team = side && side.team_id
      ? '<a class="gob-team" data-gob-drill href="' + tables.esc(teamHref(side.team_id)) + '">'
        + tables.markHtml(name, side.primary_color) + rankHtml(side)
        + '<span class="nm">' + tables.esc(name) + '</span></a>'
      : '<span class="gob-team"><span class="nm">' + tables.esc(name) + '</span></span>';
    return '<div class="gob-gs' + (won ? ' won' : '') + '">' + team
      + '<span class="sc">' + (score == null ? '' : tables.esc(score)) + '</span></div>';
  }

  function gameCard(game) {
    var done = game.status === 'complete' && game.away_score != null && game.home_score != null;
    var away = done ? Number(game.away_score) : null;
    var home = done ? Number(game.home_score) : null;
    var context = game.tournament_context || (done ? 'Final' : '');
    var foot = '';
    if (context) {
      foot = '<span class="ctx">' + tables.esc(context) + '</span>';
      if (done && game.game_id) {
        // `data-return`: the box score opens as a read and comes back to this week.
      foot += '<a class="gob-box" data-return href="' + tables.esc(boxHref(game.game_id)) + '">Box score</a>';
      }
    }
    return '<article class="gob-game' + (game.is_user ? ' me is-user' : '') + '">'
      + sideRow(game.away, done ? game.away_score : null, done && away > home)
      + sideRow(game.home, done ? game.home_score : null, done && home > away)
      + (foot ? '<div class="gob-gf">' + foot + '</div>' : '') + '</article>';
  }

  function byeCard(bye) {
    var context = bye.tournament_context || '';
    return '<article class="gob-game gob-bye' + (bye.is_user ? ' me is-user' : '') + '">'
      + sideRow(bye.team, null, false)
      + '<div class="gob-gs gob-bye-line"><span class="nm">Bye</span></div>'
      + (context ? '<div class="gob-gf"><span class="ctx">' + tables.esc(context) + '</span></div>' : '')
      + '</article>';
  }

  /** Games, then byes, region by region. With no byes the games keep the server's order. */
  function cardsHtml(games, byes) {
    if (!byes.length) return games.map(gameCard).join('');
    var regions = Object.create(null);
    var letters = [];
    function bucket(letter) {
      var key = String(letter || '');
      if (!regions[key]) {
        regions[key] = [];
        letters.push(key);
      }
      return regions[key];
    }
    games.forEach(function (game) { bucket(game.region).push(gameCard(game)); });
    byes.forEach(function (bye) { bucket(bye.region).push(byeCard(bye)); });
    letters.sort(function (a, b) {
      if (!a || !b) return a ? -1 : (b ? 1 : 0);
      return a.localeCompare(b);
    });
    return letters.map(function (letter) { return regions[letter].join(''); }).join('');
  }

  function neighbor(dir) {
    var weeks = (payload && payload.weeks) || [];
    var here = payload ? payload.week : 0;
    var index = -1;
    var i;
    for (i = 0; i < weeks.length; i++) {
      if (weeks[i].week === here) index = i;
    }
    if (index < 0) return null;
    i = index + dir;
    while (i >= 0 && i < weeks.length) {
      if (weeks[i].enabled) return weeks[i].week;
      i += dir;
    }
    return null;
  }

  function paintTools(slot) {
    var week = payload ? payload.week : (requested || '');
    var prev = payload ? neighbor(-1) : null;
    var next = payload ? neighbor(1) : null;
    slot.innerHTML = '<div class="gob-wk" role="group" aria-label="Week">'
      + '<button type="button" data-week-step="-1"' + (prev == null ? ' disabled' : '')
      + ' aria-label="Previous week">‹</button>'
      + '<span class="gob-wk-label">Week ' + tables.esc(week) + '</span>'
      + '<button type="button" data-week-step="1"' + (next == null ? ' disabled' : '')
      + ' aria-label="Next week">›</button></div>';
    slot.querySelectorAll('button').forEach(function (button) {
      button.addEventListener('click', function () {
        var dir = Number(button.getAttribute('data-week-step'));
        var target = neighbor(dir);
        if (target == null) return;
        requested = target;
        load(false);
      });
    });
  }

  function ownTools() {
    tables.registerTools('league-schedule-view', paintTools);
    tables.placeTools();
    var slot = document.querySelector('#gob-subtabs .pg-tools[data-owner="league-schedule-view"]');
    if (slot) paintTools(slot);
  }

  function render() {
    var games = (payload && payload.games) || [];
    var byes = (payload && Array.isArray(payload.byes)) ? payload.byes : [];
    var title = payload && payload.label && payload.label.indexOf(':') >= 0
      ? payload.label.split(':').slice(1).join(':').trim()
      : '';
    var html = '<section class="gob-lsch">';
    if (title) html += '<p class="gob-sch-round">' + tables.esc(title) + '</p>';
    if (!games.length && !byes.length) {
      var empty = payload && payload.week >= 27
        ? 'No tournament matchups available yet.'
        : 'No games scheduled.';
      html += '<p class="gob-lsch-empty">' + tables.esc(empty) + '</p>';
    } else {
      html += '<div class="gob-lgrid">' + cardsHtml(games, byes) + '</div>';
    }
    html += '</section>';
    container.innerHTML = html;
    container.querySelectorAll('a[data-gob-drill]').forEach(function (link) {
      link.addEventListener('click', function (event) {
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button) return;
        event.preventDefault();
        if (window.GOBViews && typeof window.GOBViews.open === 'function') {
          window.GOBViews.open(link.getAttribute('href'), 'push');
        }
      });
    });
    ownTools();
    restoreScroll();
  }

  function apply(next) {
    var stamp = JSON.stringify(next || {});
    if (loaded && stamp === signature) {
      ownTools();
      return;
    }
    signature = stamp;
    payload = next || {};
    loaded = true;
    if (payload.week != null) writeWeek(payload.week);
    render();
  }

  function load(first) {
    var store = ctx && ctx.store;
    if (!store || typeof store.get !== 'function' || !franchiseId) {
      tables.paintError(container, 'Schedule could not be opened.', function () { load(true); });
      return;
    }
    if (first || !loaded) tables.paintSkeleton(container);
    store.get(weekUrl(tables, franchiseId, requested)).then(function (body) {
      apply(body || {});
    }).catch(function () {
      loaded = false;
      tables.paintError(container, 'Schedule could not be opened.', function () { load(true); });
    });
  }

  function revalidate() {
    var store = ctx && ctx.store;
    if (!loaded || !store || typeof store.revalidate !== 'function' || !franchiseId) return;
    store.revalidate(weekUrl(tables, franchiseId, payload && payload.week)).then(function (body) {
      if (body) apply(body);
    }).catch(function () { /* keep the mounted table */ });
  }

  function onTab(event) {
    var tab = event && event.detail && event.detail.tab;
    if (tab !== 'league-schedule-view') return;
    requested = weekFromUrl() != null ? weekFromUrl() : (payload && payload.week);
    if (!loaded) load(true);
    else revalidate();
    ownTools();
  }

  document.addEventListener('gob-tab-shown', onTab);
  ownTools();
  load(true);

  return {
    revalidate: revalidate,
    unmount: function () {
      document.removeEventListener('gob-tab-shown', onTab);
      tables.registerTools('league-schedule-view', null);
    }
  };
}

export function unmount() {}
