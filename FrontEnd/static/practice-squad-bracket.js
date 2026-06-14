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

  function init() {
    var back = document.getElementById('back-btn');
    if (back) back.href = '/practice-squad-standings.html?' + q();
    if (!franchiseId || typeof renderBracketShared !== 'function') return;

    fetch(API_CONFIG.buildUrl('/franchise/practice-squad/brackets') + '?franchise_id=' + encodeURIComponent(franchiseId), {
      headers: API_CONFIG.getAuthHeaders()
    })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        var root = document.getElementById('ps-brackets-root');
        if (!data.initialized || !data.tournaments) {
          root.innerHTML = '<p>Tournament brackets are not available yet.</p>';
          return;
        }
        var teams = data.teams || {};
        var nameMap = {};
        Object.keys(teams).forEach(function (tid) {
          nameMap[tid] = (teams[tid] && teams[tid].display_name) || tid;
        });
        root.innerHTML = '';
        TIER_ORDER.forEach(function (tier) {
          var tstate = data.tournaments[tier];
          if (!tstate || !tstate.bracket) return;
          var section = document.createElement('section');
          section.className = 'fcc-data-card';
          section.style.marginBottom = '24px';
          var title = document.createElement('h2');
          title.textContent = TIER_LABELS[tier] || ('Tier ' + tier);
          title.style.fontFamily = "'Bebas Neue', sans-serif";
          section.appendChild(title);
          var container = document.createElement('div');
          container.className = 'bracket';
          section.appendChild(container);
          root.appendChild(section);
          renderBracketShared(container, tstate.bracket, nameMap, {});
        });
        if (data.championship && data.championship.game_id) {
          var ch = document.createElement('section');
          ch.className = 'fcc-data-card';
          ch.innerHTML = '<h2>Practice Squad Championship</h2><p>'
            + (nameMap[data.championship.home_team_id] || '')
            + ' ' + (data.championship.home_score != null ? data.championship.home_score : '')
            + ', ' + (nameMap[data.championship.away_team_id] || '')
            + ' ' + (data.championship.away_score != null ? data.championship.away_score : '')
            + ' <a href="/box-score.html?game_id=' + encodeURIComponent(data.championship.game_id)
            + '&mode=practice_squad&' + q() + '">Box Score</a></p>';
          root.appendChild(ch);
        }
      })
      .catch(function (err) {
        console.error(err);
        document.getElementById('ps-brackets-root').innerHTML = '<p>Failed to load brackets.</p>';
      });
  }

  init();
})();
