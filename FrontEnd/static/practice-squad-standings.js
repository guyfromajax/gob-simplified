(function () {
  'use strict';

  var params = new URLSearchParams(window.location.search);
  var franchiseId = params.get('franchise_id');
  var teamId = params.get('team_id');
  var TIER_ORDER = ['1', '2', '3', '4', '5'];
  var TIER_LABELS = {
    '1': 'All-Americans',
    '2': 'All-Stars',
    '3': 'Varsity',
    '4': 'JV',
    '5': 'Squad'
  };

  function q() {
    var p = new URLSearchParams();
    if (franchiseId) p.set('franchise_id', franchiseId);
    if (teamId) p.set('team_id', teamId);
    return p.toString();
  }

  function fetchJSON(url) {
    return fetch(url, { headers: API_CONFIG.getAuthHeaders() }).then(function (res) {
      if (!res.ok) throw new Error('Request failed');
      return res.json();
    });
  }

  function currentReturnUrl() {
    return encodeURIComponent(window.location.pathname + window.location.search);
  }

  function boxScoreUrl(gameId) {
    return '/box-score.html?game_id=' + encodeURIComponent(gameId)
      + '&mode=practice_squad&' + q()
      + '&return_url=' + currentReturnUrl();
  }

  function rosterUrl(psTeamId) {
    return '/team-roster-view.html?mode=practice_squad&ps_team_id=' + encodeURIComponent(psTeamId) + '&' + q()
      + '&return_url=' + encodeURIComponent(window.location.pathname + window.location.search);
  }

  function renderStandings(data) {
    var root = document.getElementById('ps-standings-root');
    if (!data.initialized) {
      root.innerHTML = '<p>Practice Squad has not started yet (available after Week 1 Training Camp).</p>';
      return;
    }
    var standings = data.standings || {};
    var teams = data.teams || {};
    root.innerHTML = TIER_ORDER.map(function (tier) {
      var tierRows = standings[tier] || {};
      var rows = Object.keys(tierRows).map(function (tid) {
        var team = teams[tid] || {};
        var rec = tierRows[tid] || { w: 0, l: 0 };
        return {
          tid: tid,
          name: team.display_name || tid,
          w: rec.w || 0,
          l: rec.l || 0
        };
      }).sort(function (a, b) {
        if (b.w !== a.w) return b.w - a.w;
        return a.l - b.l;
      });
      var body = rows.map(function (r) {
        return '<tr><td><a class="ps-team-link" href="' + rosterUrl(r.tid) + '">' + r.name + '</a></td><td>' + r.w + '</td><td>' + r.l + '</td></tr>';
      }).join('');
      return [
        '<section class="ps-tier-block fcc-data-card"><div class="fcc-data-card-body">',
        '<h2 class="ps-tier-title">' + (TIER_LABELS[tier] || tier) + '</h2>',
        '<table class="roster-table"><thead><tr><th>Team</th><th>W</th><th>L</th></tr></thead><tbody>',
        body || '<tr><td colspan="3">No data</td></tr>',
        '</tbody></table></div></section>'
      ].join('');
    }).join('');
  }

  function renderScheduleWeek(week, games) {
    var lines = (games || []).map(function (g) {
      var text = (g.home_display || g.home_team_id) + ' vs ' + (g.away_display || g.away_team_id);
      if (g.status === 'completed' && g.game_id) {
        text = (g.home_display || g.home_team_id) + ' ' + g.home_score + ', '
          + (g.away_display || g.away_team_id) + ' ' + g.away_score;
        text += ' <a href="' + boxScoreUrl(g.game_id) + '">Box Score</a>';
      } else if (g.status === 'forfeit') {
        text += ' (forfeit)';
      }
      return '<div class="ps-schedule-game">' + text + '</div>';
    }).join('');
    return '<details class="ps-schedule-week"' + (week === currentWeek ? ' open' : '') + '><summary>Week ' + week + '</summary>' + (lines || '<div class="ps-schedule-game">No games</div>') + '</details>';
  }

  var currentWeek = 1;

  function loadScheduleWeek(week, container) {
    return fetchJSON(API_CONFIG.buildUrl('/franchise/practice-squad/schedule') + '?franchise_id=' + encodeURIComponent(franchiseId) + '&week=' + week)
      .then(function (data) {
        var el = document.createElement('div');
        el.innerHTML = renderScheduleWeek(week, data.games);
        container.appendChild(el.firstChild);
      });
  }

  function init() {
    var back = document.getElementById('back-btn');
    if (back) {
      back.href = franchiseId
        ? '/news.html?' + q()
        : '/franchise-command-center.html?' + q();
    }
    var bracketLink = document.getElementById('ps-bracket-link');
    if (bracketLink && franchiseId) {
      bracketLink.href = '/practice-squad-bracket.html?' + q();
      bracketLink.style.display = '';
    }
    if (!franchiseId) return;

    fetchJSON(API_CONFIG.buildUrl('/franchise/practice-squad/standings') + '?franchise_id=' + encodeURIComponent(franchiseId))
      .then(function (data) {
        currentWeek = data.week || 1;
        if (currentWeek >= 16) {
          var bl = document.getElementById('ps-bracket-link');
          if (bl) bl.style.display = '';
        }
        renderStandings(data);
        return fetchJSON(API_CONFIG.buildUrl('/franchise/practice-squad/schedule') + '?franchise_id=' + encodeURIComponent(franchiseId));
      })
      .then(function (meta) {
        var schedRoot = document.getElementById('ps-schedule-root');
        if (!meta.weeks || !meta.weeks.length) {
          schedRoot.innerHTML = '<p>No schedule yet.</p>';
          return;
        }
        schedRoot.innerHTML = '';
        var weeks = meta.weeks.filter(function (w) { return w >= 2 && w <= 19; });
        return weeks.reduce(function (chain, week) {
          return chain.then(function () { return loadScheduleWeek(week, schedRoot); });
        }, Promise.resolve());
      })
      .catch(function (err) {
        console.error(err);
        document.getElementById('ps-standings-root').innerHTML = '<p>Failed to load Practice Squad data.</p>';
      });
  }

  init();
})();
