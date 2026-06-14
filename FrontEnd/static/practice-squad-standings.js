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

  function formatWinPct(w, l) {
    var wins = Number(w) || 0;
    var losses = Number(l) || 0;
    var total = wins + losses;
    if (total <= 0) return '.000';
    return (wins / total).toFixed(3).replace(/^0/, '');
  }

  function buildStandingsCard(titleText, rows) {
    var card = document.createElement('section');
    card.className = 'fcc-standings-card';

    var title = document.createElement('div');
    title.className = 'fcc-standings-card-title';
    title.textContent = titleText;
    card.appendChild(title);

    var headerRow = document.createElement('div');
    headerRow.className = 'fcc-standings-row fcc-standings-row-header';
    headerRow.innerHTML = [
      '<span class="fcc-standings-col-team">Team</span>',
      '<span class="fcc-standings-col-stat">W</span>',
      '<span class="fcc-standings-col-stat">L</span>',
      '<span class="fcc-standings-col-stat">Win%</span>'
    ].join('');
    card.appendChild(headerRow);

    var body = document.createElement('div');
    body.className = 'fcc-standings-card-body';

    if (!rows.length) {
      var emptyRow = document.createElement('div');
      emptyRow.className = 'fcc-standings-row';
      var emptyCell = document.createElement('span');
      emptyCell.className = 'fcc-standings-col-team';
      emptyCell.textContent = 'No data';
      emptyRow.appendChild(emptyCell);
      body.appendChild(emptyRow);
    } else {
      rows.forEach(function (r) {
        var row = document.createElement('div');
        row.className = 'fcc-standings-row';

        var teamCell = document.createElement('span');
        teamCell.className = 'fcc-standings-col-team';
        var link = document.createElement('a');
        link.href = rosterUrl(r.tid);
        link.textContent = r.name;
        teamCell.appendChild(link);
        row.appendChild(teamCell);

        var wCell = document.createElement('span');
        wCell.className = 'fcc-standings-col-stat';
        wCell.textContent = String(r.w);
        row.appendChild(wCell);

        var lCell = document.createElement('span');
        lCell.className = 'fcc-standings-col-stat';
        lCell.textContent = String(r.l);
        row.appendChild(lCell);

        var pctCell = document.createElement('span');
        pctCell.className = 'fcc-standings-col-stat';
        pctCell.textContent = formatWinPct(r.w, r.l);
        row.appendChild(pctCell);

        body.appendChild(row);
      });
    }

    card.appendChild(body);
    return card;
  }

  function renderStandings(data) {
    var root = document.getElementById('ps-standings-root');
    root.innerHTML = '';

    if (!data.initialized) {
      root.innerHTML = '<p>Practice Squad has not started yet (available after Week 1 Training Camp).</p>';
      return;
    }

    var standings = data.standings || {};
    var teams = data.teams || {};

    TIER_ORDER.forEach(function (tier) {
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

      root.appendChild(buildStandingsCard(TIER_LABELS[tier] || tier, rows));
    });
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
      if (franchiseId && typeof resolveFranchiseLockerRoomUrl === 'function') {
        back.href = resolveFranchiseLockerRoomUrl({ params: params, franchiseId: franchiseId, teamId: teamId });
        back.textContent = 'Back to Locker Room';
      } else if (franchiseId) {
        back.href = '/franchise-command-center.html?' + q();
      } else {
        back.href = '/mode-select.html';
      }
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
