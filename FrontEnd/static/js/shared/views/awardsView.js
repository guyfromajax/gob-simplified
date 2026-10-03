/**
 * News › Awards. All-American teams from GET /franchise/awards.
 *
 * Weeks 1-34 it is the projection ("Projected All-Americans", rebuilt once a week and
 * frozen through the tournaments). After the National Tournament it is the final.
 * Each team is one player per position, PG to C. No season selector, no portraits. Navy
 * row is the user's team. How the teams are picked is not shown: the page has the
 * status, the player, the rating and the stat line, and the response carries no weights,
 * scores, ranks or bonus.
 *
 * Under the All-American teams, All-Conference: the same two tables for one conference
 * at a time, picked from a row of the sixteen. The user's conference is the default and
 * is cued ("Yours"). Projected weekly, final from week 27.
 */

var TEAMS = [
  { key: 'first_team', label: '1st Team All-American' },
  { key: 'second_team', label: '2nd Team All-American' },
  { key: 'third_team', label: '3rd Team All-American' }
];
var CONFERENCE_TEAMS = [
  { key: 'first_team', label: '1st Team All-Conference' },
  { key: 'second_team', label: '2nd Team All-Conference' }
];
var CONFERENCE_KEY = 'gob-view-awards-conference';

var STATS = ['PTS', 'REB', 'AST', 'STL', 'BLK', 'DEF%'];

function sameId(a, b) {
  return String(a || '') !== '' && String(a) === String(b || '');
}

function formatYear(year) {
  if (window.GOB_PlayerYear && typeof window.GOB_PlayerYear.formatDisplay === 'function') {
    return window.GOB_PlayerYear.formatDisplay(year);
  }
  return year || '--';
}

function statText(stats, key, perGame) {
  var value = stats ? stats[key] : null;
  if (value == null || value === '') return '--';
  if (key === 'DEF%') return String(value) + '%';
  if (perGame && typeof value === 'number') return value.toFixed(1);
  return String(value);
}

function hasStats(teams, keys) {
  return (keys || TEAMS).some(function (team) {
    return (teams[team.key] || []).some(function (player) {
      var stats = player.stats || {};
      return STATS.some(function (key) { return stats[key] != null && stats[key] !== ''; });
    });
  });
}

function hasField(teams, field, keys) {
  return (keys || TEAMS).some(function (team) {
    return (teams[team.key] || []).some(function (player) { return player[field] != null && player[field] !== ''; });
  });
}

/** The status line for one block: "Preseason", "After week N", … or "Final". */
function statusParts(block, esc, finalNote) {
  var status = block && block.status;
  if (status === 'final') return ['Final'];
  if (status !== 'projected') return [];
  var parts = [esc(block.label || 'Projected')];
  if (finalNote && Number(block.week) >= 26) parts.push(finalNote);
  return parts;
}

function readConference() {
  try { return sessionStorage.getItem(CONFERENCE_KEY) || ''; } catch (err) { return ''; }
}

function writeConference(value) {
  try { sessionStorage.setItem(CONFERENCE_KEY, String(value)); } catch (err) { /* ignore */ }
}

function rtCell(rating) {
  if (typeof rating !== 'number') return '<td>--</td>';
  var text = typeof window.formatRtDisplay === 'function' ? window.formatRtDisplay(rating) : String(Math.round(rating));
  var cls = typeof window.getRtBucketClass === 'function' ? window.getRtBucketClass(rating) : '';
  return '<td' + (cls ? ' class="' + cls + '"' : '') + '>' + text + '</td>';
}

/**
 * Title and the status under it: "Preseason", "After week N", "End of regular season ·
 * Not final: tournament play can still change these", or "Final".
 */
function headHtml(body, esc) {
  var status = body && body.status;
  var title = status === 'projected' ? 'Projected All-Americans' : 'All-Americans';
  var parts = statusParts(body, esc, 'Not final: tournament play can still change these');
  return '<header class="gob-awards-head"><h2>' + title + '</h2>'
    + (parts.length ? '<p>' + parts.join('<span aria-hidden="true"> \u00b7 </span>') + '</p>' : '')
    + '</header>';
}

/** All-Conference: projected until week 26 is complete, then final. */
function conferenceHeadHtml(block, esc) {
  var title = block.status === 'projected' ? 'Projected All-Conference' : 'All-Conference';
  var parts = statusParts(block, esc, '');
  return '<header class="gob-awards-head gob-awards-conf-head"><h2>' + title + '</h2>'
    + (parts.length ? '<p>' + parts.join('<span aria-hidden="true"> \u00b7 </span>') + '</p>' : '')
    + '</header>';
}

/**
 * The row of conferences. One button each, A1 to H16, the user's own marked "Yours".
 * The chosen one is `on`.
 */
function conferencePickerHtml(block, chosen, esc) {
  var labels = block.labels || {};
  var mine = String(block.conference == null ? '' : block.conference);
  var html = '<div class="gob-awards-conf-row stats-toggle" role="tablist" aria-label="Conference">';
  Object.keys(labels).sort(function (a, b) { return Number(a) - Number(b); }).forEach(function (key) {
    var yours = key === mine;
    html += '<button type="button" role="tab" data-conference="' + esc(key) + '"'
      + ' aria-selected="' + (key === chosen ? 'true' : 'false') + '"'
      + ' class="' + (key === chosen ? 'on' : '') + (yours ? ' is-yours' : '') + '"'
      + (yours ? ' title="Your conference"' : '') + '>'
      + '<span>' + esc(labels[key]) + '</span>'
      + (yours ? '<em>Yours</em>' : '')
      + '</button>';
  });
  return html + '</div>';
}

export function mount(container, ctx) {
  var tables = window.GOBTables;
  var body = null;
  var signature = '';
  var loaded = false;
  var alive = true;
  var userId = (ctx && ctx.teamId) || '';
  var franchiseId = (ctx && ctx.franchiseId) || '';

  function playerHref(player) {
    var params = new URLSearchParams(window.location.search);
    params.set('tab', 'player-view');
    params.set('player_id', player.player_id || '');
    params.set('origin', 'league');
    params.set('up', 'Awards');
    params.set('return_tab', 'awards-view');
    params.delete('story');
    params.delete('view_team_id');
    var text = params.toString();
    return window.location.pathname + (text ? '?' + text : '');
  }

  function teamHref(player) {
    var params = new URLSearchParams(window.location.search);
    params.set('tab', 'team-view');
    params.set('view_team_id', player.team_id || '');
    params.set('origin', 'league');
    params.set('up', 'Awards');
    params.set('return_tab', 'awards-view');
    params.delete('story');
    var text = params.toString();
    return window.location.pathname + (text ? '?' + text : '');
  }

  /** One team's table. `keys` says which team lists the block holds. */
  function tableHtml(players, layout) {
    var esc = tables.esc;
    var html = '<div class="gob-tcard"><table class="gob-tbl gob-awards-tbl"><colgroup>';
    if (layout.showPos) html += '<col class="c-pos">';
    html += '<col class="c-player"><col class="c-yr"><col class="c-team">';
    if (layout.showRt) html += '<col class="c-rt">';
    if (layout.showStats) STATS.forEach(function () { html += '<col class="c-stat">'; });
    html += '</colgroup><thead><tr>';
    if (layout.showPos) html += '<th class="left">Pos</th>';
    html += '<th class="left">Player</th><th class="left">Yr</th><th class="left">Team</th>';
    if (layout.showRt) html += '<th>RT</th>';
    if (layout.showStats) STATS.forEach(function (key) { html += '<th>' + esc(key) + '</th>'; });
    html += '</tr></thead><tbody>';
    if (!players.length) {
      html += '<tr><td class="left gob-awards-empty" colspan="' + layout.columns + '">No selections</td></tr>';
    }
    players.forEach(function (player) {
      var mine = sameId(player.team_id, userId);
      var stats = player.stats || {};
      var name = esc(player.name || '--');
      html += '<tr' + (mine ? ' class="me is-user"' : '') + '>';
      if (layout.showPos) html += '<td class="left gob-awards-pos">' + esc(player.position || '--') + '</td>';
      html += '<td class="left">' + (player.player_id
        ? '<a class="gob-player" href="' + esc(playerHref(player)) + '">' + name + '</a>'
        : name) + '</td>';
      html += '<td class="left">' + esc(formatYear(player.year)) + '</td>';
      html += '<td class="left">' + tables.teamLink(
        teamHref(player),
        player.team_name || '--',
        player.team_name || '',
        ''
      ) + '</td>';
      if (layout.showRt) html += rtCell(player.rating);
      if (layout.showStats) {
        STATS.forEach(function (key) {
          html += '<td>' + esc(statText(stats, key, layout.perGame)) + '</td>';
        });
      }
      html += '</tr>';
    });
    return html + '</tbody></table></div>';
  }

  // Columns follow the data: an older stored final has no position or rating, and the
  // preseason projection has no stat lines to show.
  function layoutFor(teams, keys, basis) {
    var showPos = hasField(teams, 'position', keys);
    var showRt = hasField(teams, 'rating', keys);
    var showStats = hasStats(teams, keys);
    return {
      showPos: showPos,
      showRt: showRt,
      showStats: showStats,
      perGame: basis === 'per_game',
      columns: 3 + (showPos ? 1 : 0) + (showRt ? 1 : 0) + (showStats ? STATS.length : 0)
    };
  }

  function chosenConference(block) {
    var conferences = (block && block.conferences) || {};
    var remembered = readConference();
    if (remembered && conferences[remembered]) return remembered;
    var mine = String(block && block.conference != null ? block.conference : '');
    if (mine && conferences[mine]) return mine;
    var keys = Object.keys(conferences).sort(function (a, b) { return Number(a) - Number(b); });
    return keys[0] || '';
  }

  function conferenceHtml(block) {
    var esc = tables.esc;
    if (!block || !block.conferences) return '';
    var chosen = chosenConference(block);
    var teams = block.conferences[chosen] || {};
    var layout = layoutFor(teams, CONFERENCE_TEAMS, block.stats_basis);
    var html = '<div class="gob-awards-conf" data-conference="' + esc(chosen) + '">'
      + conferenceHeadHtml(block, esc)
      + conferencePickerHtml(block, chosen, esc);
    CONFERENCE_TEAMS.forEach(function (team) {
      html += '<section><h3>' + esc(team.label) + '</h3>' + tableHtml(teams[team.key] || [], layout) + '</section>';
    });
    return html + '</div>';
  }

  function render() {
    if (!alive) return;
    var teams = (body && body.all_american_teams) || null;
    var conference = body && body.all_conference;
    var hasConference = !!(conference && conference.conferences);
    if (!teams && !hasConference) {
      container.innerHTML = '<p class="gob-news-empty gob-empty">Awards are not available yet.</p>';
      return;
    }
    var esc = tables.esc;
    var html = '<div class="gob-awards">';
    var statsShown = false;
    if (teams) {
      var layout = layoutFor(teams, TEAMS, body.stats_basis);
      statsShown = layout.showStats && layout.perGame;
      html += headHtml(body, esc);
      TEAMS.forEach(function (team) {
        html += '<section><h3>' + esc(team.label) + '</h3>' + tableHtml(teams[team.key] || [], layout) + '</section>';
      });
    }
    if (hasConference) {
      html += conferenceHtml(conference);
      var chosen = chosenConference(conference);
      var picked = layoutFor(conference.conferences[chosen] || {}, CONFERENCE_TEAMS, conference.stats_basis);
      statsShown = statsShown || (picked.showStats && picked.perGame);
    }
    if (statsShown) {
      html += '<p class="gob-awards-note">Stats are per game, regular season.</p>';
    }
    html += '</div>';
    container.innerHTML = html;
    bindLinks();
    container.querySelectorAll('.gob-awards-conf-row button').forEach(function (button) {
      button.addEventListener('click', function () {
        var next = button.getAttribute('data-conference') || '';
        if (!next || next === chosenConference(conference)) return;
        writeConference(next);
        paintConference();
      });
    });
  }

  /** Repaints the All-Conference block only, so the page stays where it is. */
  function paintConference() {
    var host = container.querySelector('.gob-awards-conf');
    var conference = body && body.all_conference;
    if (!host || !conference) return;
    var fresh = document.createElement('div');
    fresh.innerHTML = conferenceHtml(conference);
    host.replaceWith(fresh.firstChild);
    bindLinks();
    container.querySelectorAll('.gob-awards-conf-row button').forEach(function (button) {
      button.addEventListener('click', function () {
        var next = button.getAttribute('data-conference') || '';
        if (!next || next === chosenConference(conference)) return;
        writeConference(next);
        paintConference();
      });
    });
  }

  function bindLinks() {
    container.querySelectorAll('a.gob-team, a.gob-player').forEach(function (link) {
      if (link.__gobBound) return;
      link.__gobBound = true;
      link.addEventListener('click', function (event) {
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button) return;
        event.preventDefault();
        if (window.GOBViews && typeof window.GOBViews.open === 'function') {
          window.GOBViews.open(link.getAttribute('href'), 'push');
        }
      });
    });
  }

  function apply(next) {
    var stamp = JSON.stringify(next || {});
    if (loaded && stamp === signature) return;
    signature = stamp;
    body = next;
    loaded = true;
    render();
  }

  function unavailable() {
    if (!alive) return;
    loaded = true;
    body = null;
    signature = 'unavailable';
    container.innerHTML = '<p class="gob-news-empty gob-empty">Awards are not available yet.</p>';
  }

  function fail() {
    if (!alive) return;
    tables.paintError(container, 'This view could not be opened.', load);
  }

  function load() {
    var store = ctx && ctx.store;
    if (!store || typeof store.get !== 'function' || !franchiseId) {
      fail();
      return;
    }
    if (!loaded) tables.paintSkeleton(container);
    store.get(tables.apiBase('/franchise/awards') + '?franchise_id=' + encodeURIComponent(franchiseId))
      .then(function (payload) { apply(payload); })
      .catch(function (err) {
        if (err && err.status === 400) unavailable();
        else fail();
      });
  }

  function revalidate() {
    var store = ctx && ctx.store;
    if (!store || !franchiseId) return;
    store.revalidate(tables.apiBase('/franchise/awards') + '?franchise_id=' + encodeURIComponent(franchiseId))
      .then(function (payload) { if (payload) apply(payload); })
      .catch(function (err) {
        if (err && err.status === 400) unavailable();
      });
  }

  load();
  return {
    revalidate: revalidate,
    unmount: function () { alive = false; }
  };
}
