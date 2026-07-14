(function () {
  'use strict';

  var Recruiting = window.RecruitingCommon;
  var context = Recruiting.getQueryContext();

  function renderTeam(container, title, players) {
    var section = document.createElement('section');
    section.className = 'recruiting-results-region';
    var heading = document.createElement('h2');
    heading.textContent = title;
    section.appendChild(heading);

    var tableWrap = document.createElement('div');
    tableWrap.className = 'scroll-x';
    var table = document.createElement('table');
    table.className = 'roster-table recruiting-results-table';
    table.innerHTML = '<thead><tr><th>Player</th><th>Team</th><th>PTS</th><th>REB</th><th>AST</th><th>STL</th><th>BLK</th><th>DEF%</th></tr></thead><tbody></tbody>';
    var tbody = table.querySelector('tbody');
    var formatDefPct = function (value) {
      if (value == null || value === '') return '--';
      var numeric = Number(value);
      return Number.isFinite(numeric) ? Math.round(numeric) + '%' : String(value);
    };

    (players || []).forEach(function (player) {
      var tr = document.createElement('tr');
      var stats = player.stats || {};
      tr.innerHTML = [
        '<td>' + (player.name || '--') + '</td>',
        '<td>' + (player.team_name || '--') + '</td>',
        '<td>' + (stats.PTS != null ? stats.PTS : '--') + '</td>',
        '<td>' + (stats.REB != null ? stats.REB : '--') + '</td>',
        '<td>' + (stats.AST != null ? stats.AST : '--') + '</td>',
        '<td>' + (stats.STL != null ? stats.STL : '--') + '</td>',
        '<td>' + (stats.BLK != null ? stats.BLK : '--') + '</td>',
        '<td>' + formatDefPct(stats['DEF%']) + '</td>'
      ].join('');
      tbody.appendChild(tr);
    });

    tableWrap.appendChild(table);
    section.appendChild(tableWrap);
    container.appendChild(section);
  }

  function init() {
    if (!context.franchiseId || !context.teamId) return;
    document.getElementById('back-btn').href = Recruiting.buildFccUrl(context);
    Recruiting.fetchJSON(API_CONFIG.buildUrl('/franchise/awards') + '?franchise_id=' + encodeURIComponent(context.franchiseId))
      .then(function (data) {
        var teams = (data.all_american_teams || {});
        var container = document.getElementById('awards-container');
        container.innerHTML = '';
        renderTeam(container, '1st Team All-American', teams.first_team || []);
        renderTeam(container, '2nd Team All-American', teams.second_team || []);
        renderTeam(container, '3rd Team All-American', teams.third_team || []);
      })
      .catch(function (err) {
        console.error(err);
        document.getElementById('awards-container').innerHTML = '<p>Awards are not available yet.</p>';
      });
  }

  init();
})();
