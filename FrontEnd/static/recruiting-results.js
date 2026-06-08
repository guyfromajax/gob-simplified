(function () {
  'use strict';

  var Recruiting = window.RecruitingCommon;
  var context = Recruiting.getQueryContext();
  var params = new URLSearchParams(window.location.search);
  var weekParam = params.get('week');

  function resolveBackUrl() {
    if (context.from === 'recruiting') {
      return Recruiting.buildRecruitingUrl('recruiting.html', context, { from: 'fcc' });
    }
    return Recruiting.buildFccUrl(context);
  }

  function renderResults(data) {
    document.getElementById('results-title').textContent = 'Week ' + data.week + ' Recruiting Visits';
    var container = document.getElementById('results-container');
    container.innerHTML = '';

    (data.regions || []).forEach(function (regionBlock) {
      var regionSection = document.createElement('section');
      regionSection.className = 'recruiting-results-region';

      var heading = document.createElement('h2');
      heading.textContent = 'Region ' + regionBlock.region;
      regionSection.appendChild(heading);

      (regionBlock.conferences || []).forEach(function (conferenceBlock) {
        var conferenceHeading = document.createElement('h3');
        conferenceHeading.textContent = 'Conference ' + regionBlock.region + conferenceBlock.conference;
        regionSection.appendChild(conferenceHeading);

        var shell = document.createElement('div');
        shell.className = 'gob-data-grid-shell';
        var tableWrap = document.createElement('div');
        tableWrap.className = 'gob-data-grid-scroll scroll-x';
        var table = document.createElement('table');
        table.className = 'gob-data-grid recruiting-results-table';
        table.innerHTML = '<thead><tr><th>Team</th><th>Recruit</th><th>Home Region</th><th>Archetype</th><th>HT</th><th>WT</th><th>Pos</th><th>RT</th></tr></thead><tbody></tbody>';
        var tbody = table.querySelector('tbody');

        (conferenceBlock.teams || []).forEach(function (teamRow) {
          var tr = document.createElement('tr');
          if (teamRow.visit) {
            tr.innerHTML = [
              '<td>' + teamRow.team_name + '</td>',
              '<td>' + teamRow.visit.name + '</td>',
              '<td>' + (teamRow.visit.home_region || '--') + '</td>',
              '<td>' + (teamRow.visit.archetype || '--') + '</td>',
              '<td>' + formatHeight(teamRow.visit.height) + '</td>',
              '<td>' + (teamRow.visit.weight != null ? teamRow.visit.weight : '--') + '</td>',
              '<td>' + (teamRow.visit.pos || '--') + '</td>',
              '<td class="' + (teamRow.visit.rt != null && typeof window.getRecruitRtBucketClass === 'function' ? window.getRecruitRtBucketClass(teamRow.visit.rt) : '') + '">' + (teamRow.visit.rt != null ? teamRow.visit.rt : '--') + '</td>'
            ].join('');
          } else {
            tr.innerHTML = [
              '<td>' + teamRow.team_name + '</td>',
              '<td colspan="7" class="recruiting-no-visit">no visit</td>'
            ].join('');
          }
          tbody.appendChild(tr);
        });

        tableWrap.appendChild(table);
        shell.appendChild(tableWrap);
        regionSection.appendChild(shell);
      });

      container.appendChild(regionSection);
    });
  }

  function init() {
    if (!context.franchiseId || !context.teamId) {
      document.getElementById('results-container').innerHTML = '<p>Missing franchise context.</p>';
      return;
    }

    document.getElementById('back-btn').addEventListener('click', function () {
      window.location.href = resolveBackUrl();
    });

    var url = API_CONFIG.buildUrl('/franchise/recruiting-results') + '?franchise_id=' + encodeURIComponent(context.franchiseId);
    if (weekParam) url += '&week=' + encodeURIComponent(weekParam);

    Recruiting.fetchJSON(url)
      .then(renderResults)
      .catch(function (err) {
        console.error(err);
        document.getElementById('results-container').innerHTML = '<p>Recruiting visits are not available for this week.</p>';
      });
  }

  init();
})();
