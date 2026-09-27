/**
 * News › Awards. Week-35 All-American snapshot from GET /franchise/awards.
 * One snapshot: no season selector, no portraits. Navy row is the user's team.
 */

var TEAMS = [
  { key: 'first_team', label: '1st Team All-American' },
  { key: 'second_team', label: '2nd Team All-American' },
  { key: 'third_team', label: '3rd Team All-American' }
];

var STATS = ['PTS', 'REB', 'AST', 'STL', 'BLK', 'DEF%'];

function sameId(a, b) {
  return String(a || '') !== '' && String(a) === String(b || '');
}

function statText(stats, key) {
  var value = stats ? stats[key] : null;
  if (value == null || value === '') return '--';
  if (key === 'DEF%') return String(value) + '%';
  return String(value);
}

export function mount(container, ctx) {
  var tables = window.GOBTables;
  var body = null;
  var signature = '';
  var loaded = false;
  var alive = true;
  var userId = (ctx && ctx.teamId) || '';
  var franchiseId = (ctx && ctx.franchiseId) || '';

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

  function render() {
    if (!alive) return;
    var teams = (body && body.all_american_teams) || null;
    if (!teams) {
      container.innerHTML = '<p class="gob-news-empty">Awards are not available yet.</p>';
      return;
    }
    var html = '<div class="gob-awards">';
    TEAMS.forEach(function (team) {
      var players = teams[team.key] || [];
      html += '<section class="gob-tcard"><h3>' + tables.esc(team.label) + '</h3>';
      html += '<table class="gob-tbl"><thead><tr><th class="team">Player</th><th class="team">Team</th>';
      STATS.forEach(function (key) { html += '<th>' + tables.esc(key) + '</th>'; });
      html += '</tr></thead><tbody>';
      players.forEach(function (player) {
        var mine = sameId(player.team_id, userId);
        var stats = player.stats || {};
        html += '<tr' + (mine ? ' class="me is-user"' : '') + '>';
        html += '<td class="team">' + tables.esc(player.name || '--') + '</td>';
        html += '<td class="team">' + tables.teamLink(
          teamHref(player),
          player.team_name || '--',
          player.team_name || '',
          ''
        ) + '</td>';
        STATS.forEach(function (key) {
          html += '<td>' + tables.esc(statText(stats, key)) + '</td>';
        });
        html += '</tr>';
      });
      html += '</tbody></table></section>';
    });
    html += '</div>';
    container.innerHTML = html;
    container.querySelectorAll('a.gob-team').forEach(function (link) {
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
    container.innerHTML = '<p class="gob-news-empty">Awards are not available yet.</p>';
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
