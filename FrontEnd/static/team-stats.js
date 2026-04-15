(function () {
  'use strict';

  const params = new URLSearchParams(window.location.search);
  const franchiseId = params.get('franchise_id');
  let userTeamId = params.get('team_id');
  let userTeamName = '';
  let currentScope = 'conference';
  let teamStatsData = null;
  let resourceCache = null;
  let defaultOrderTeams = [];
  let sortColumn = 'rank';
  let sortDirection = 'asc';

  const playNowBtn = document.getElementById('play-now');
  const COLUMN_ORDER = ['team', 'rank', 'W', 'L', 'PF', 'PA', 'FGM', 'FGA', 'FG%', '3PTM', '3PTA', '3PT%', 'FTM', 'FTA', 'FT%', 'DREB', 'OREB', 'TREB', 'AST', 'F', 'TO', 'SCR_A', 'SCR%', 'STL', 'BLK', 'DEF_A', 'DEF%'];
  const COL_GROUP_START_INDEX = { 0: 1, 6: 1, 9: 1, 12: 1, 15: 1, 18: 1, 23: 1 };
  const STAT_MAP = { team: 'team', rank: 'rank', W: 'W', L: 'L', PF: 'PF', PA: 'PA', FGM: 'FGM', FGA: 'FGA', 'FG%': 'FG%', '3PTM': '3PTM', '3PTA': '3PTA', '3PT%': '3PT%', FTM: 'FTM', FTA: 'FTA', 'FT%': 'FT%', DREB: 'DREB', OREB: 'OREB', TREB: 'TREB', AST: 'AST', F: 'F', TO: 'TO', SCR_A: 'SCR_A', 'SCR%': 'SCR%', STL: 'STL', BLK: 'BLK', DEF_A: 'DEF_A', 'DEF%': 'DEF%' };

  function playSound(filename) {
    try {
      const audio = new Audio('/sounds/' + encodeURIComponent(filename));
      audio.volume = 0.7;
      audio.play().catch(function () {});
    } catch (error) {}
  }

  async function fetchJSON(url) {
    try {
      const res = await fetch(url, { headers: API_CONFIG.getAuthHeaders() });
      if (res.status === 401 || res.status === 403) {
        if (typeof AccessDenied !== 'undefined' && AccessDenied.checkAccessDenied) {
          AccessDenied.checkAccessDenied(res);
        }
        return null;
      }
      if (!res.ok) throw new Error('Request failed');
      return await res.json();
    } catch (error) {
      console.error('Failed loading', url, error);
      return null;
    }
  }

  function buildFccUrl(tabName) {
    const next = new URLSearchParams();
    if (franchiseId) next.set('franchise_id', franchiseId);
    if (userTeamId) next.set('team_id', userTeamId);
    if (tabName) next.set('tab', tabName);
    return '/franchise-command-center.html?' + next.toString();
  }

  function buildModeUrl(pathname, extraParams) {
    const next = new URLSearchParams();
    next.set('mode', 'franchise');
    if (franchiseId) next.set('franchise_id', franchiseId);
    if (userTeamId) next.set('team_id', userTeamId);
    next.set('return_url', getCurrentRelativeUrl());
    Object.keys(extraParams || {}).forEach((key) => {
      if (extraParams[key] != null && extraParams[key] !== '') next.set(key, extraParams[key]);
    });
    return pathname + '?' + next.toString();
  }

  function wireTopButtons() {
    const exitBtn = document.getElementById('exit-franchise');
    if (exitBtn) {
      exitBtn.addEventListener('click', function () {
        playSound('x-back.mp3');
        window.location.href = '/mode-select.html';
      });
    }

    if (!playNowBtn) return;
    playNowBtn.addEventListener('click', function () {
      playSound('confirm-1.mp3');
      window.location.href = buildFccUrl('home-tab');
    });
  }

  function wireTabRoutes() {
    const routes = {
      'team-stats-home-btn': buildFccUrl('home-tab'),
      'team-stats-roster-btn': buildFccUrl('roster-tab'),
      'team-stats-player-stats-btn': buildFccUrl('player-stats-tab'),
      'team-stats-game-plan-btn': buildModeUrl('/game-plan.html', { from: 'command_center' }),
      'team-stats-playbooks-btn': buildModeUrl('/playbook-report.html', { from: 'franchise-command-center' }),
      'team-stats-coaches-btn': buildFccUrl('coaches-tab'),
      'team-stats-standings-btn': buildFccUrl('standings-tab'),
      'team-stats-schedule-btn': buildFccUrl('schedule-tab'),
      'team-stats-rankings-btn': buildFccUrl('rankings-tab'),
      'team-stats-leaders-btn': buildFccUrl('awards-tab'),
      'team-stats-press-btn': buildFccUrl('press-tab'),
      'team-stats-recruits-btn': buildFccUrl('recruits-tab'),
      'team-stats-tasks-btn': buildFccUrl('tutorials-tab')
    };

    Object.entries(routes).forEach(function ([id, route]) {
      const btn = document.getElementById(id);
      if (btn) {
        btn.dataset.route = route;
        btn.addEventListener('click', function () {
          playSound('click-tiny.wav');
          window.location.href = route;
        });
      }
    });
  }

  function populateTop(data) {
    if (!data) return;
    userTeamName = data.team || userTeamName;
    if (data.user_team_id != null) userTeamId = String(data.user_team_id);
    const logo = document.getElementById('team-logo');
    const season = document.getElementById('fcc-season-label');
    if (logo) {
      logo.src = typeof getTeamAssetPath === 'function'
        ? getTeamAssetPath(data.team, 'banner_primary')
        : '/images/teams/general/general_banner_primary.jpg';
    }
    if (season) {
      season.textContent = `Season ${Number(data.current_season || 1)} / Week ${Number(data.week || 1)}`;
    }
    if (playNowBtn) {
      if (data.cut_required) playNowBtn.textContent = 'Cut Players';
      else if (Number(data.week || 1) === 35) playNowBtn.textContent = 'Recruiting';
      else if (Number(data.week || 1) >= 36) playNowBtn.textContent = 'Go To Next Season';
      else if (!data.training_completed) playNowBtn.textContent = (data.session_type || 'in-season') === 'preseason' ? 'Run Training Camp' : 'Run Training';
      else playNowBtn.textContent = 'Play Next Game';
    }
  }

  function cloneTeams(teams) {
    return (teams || []).map(function (team) {
      return { ...team, stats: { ...(team.stats || {}) } };
    });
  }

  function getNumericNationalRank(team) {
    const parsed = Number(team?.natl_rank);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
  }

  function statValue(team, statKey) {
    const stats = team.stats || {};
    if (statKey === 'team') return team.team || '';
    if (statKey === 'rank') return getNumericNationalRank(team) ?? Number.MAX_SAFE_INTEGER;
    if (statKey === 'FG%') return stats.FGA > 0 ? ((stats.FGM || 0) / stats.FGA) : 0;
    if (statKey === '3PT%') return stats['3PTA'] > 0 ? ((stats['3PTM'] || 0) / stats['3PTA']) : 0;
    if (statKey === 'FT%') return stats.FTA > 0 ? ((stats.FTM || 0) / stats.FTA) : 0;
    if (statKey === 'DEF%') return stats.DEF_A > 0 ? ((stats.DEF_S || 0) / stats.DEF_A) : 0;
    if (statKey === 'SCR%') return stats.SCR_A > 0 ? ((stats.SCR_S || 0) / stats.SCR_A) : 0;
    return Number(stats[STAT_MAP[statKey] || statKey] || 0);
  }

  function sortTeams(teams, statKey, direction) {
    return cloneTeams(teams).sort(function (a, b) {
      if (statKey === 'team') {
        const cmp = statValue(a, statKey).localeCompare(statValue(b, statKey));
        return direction === 'asc' ? cmp : -cmp;
      }
      const diff = statValue(a, statKey) - statValue(b, statKey);
      return direction === 'asc' ? diff : -diff;
    });
  }

  function renderRows(teams) {
    const tbody = document.getElementById('teamstats-body');
    if (!tbody) return;
    tbody.innerHTML = '';

    const totals = {
      W: 0, L: 0, PF: 0, PA: 0, FGM: 0, FGA: 0, '3PTM': 0, '3PTA': 0, FTM: 0, FTA: 0,
      DREB: 0, OREB: 0, TREB: 0, AST: 0, F: 0, TO: 0, STL: 0, BLK: 0, DEF_A: 0, DEF_S: 0, SCR_A: 0, SCR_S: 0
    };

    teams.forEach(function (team) {
      const stats = team.stats || {};
      const tr = document.createElement('tr');
      let html = '';
      COLUMN_ORDER.forEach(function (key, index) {
        const groupStart = COL_GROUP_START_INDEX[index] ? ' col-group-start' : '';
        if (key === 'team') {
          html += '<td class="col-group-start">' + (team.team || '') + '</td>';
          return;
        }
        if (key === 'rank') {
          html += '<td>' + (getNumericNationalRank(team) ?? '--') + '</td>';
          return;
        }
        let value;
        if (key === 'FG%') value = stats.FGA > 0 ? (((stats.FGM || 0) / stats.FGA) * 100).toFixed(1) + '%' : '0.0%';
        else if (key === '3PT%') value = stats['3PTA'] > 0 ? (((stats['3PTM'] || 0) / stats['3PTA']) * 100).toFixed(1) + '%' : '0.0%';
        else if (key === 'FT%') value = stats.FTA > 0 ? (((stats.FTM || 0) / stats.FTA) * 100).toFixed(1) + '%' : '0.0%';
        else if (key === 'DEF%') value = stats.DEF_A > 0 ? (((stats.DEF_S || 0) / stats.DEF_A) * 100).toFixed(1) + '%' : '0.0%';
        else if (key === 'SCR%') value = stats.SCR_A > 0 ? (((stats.SCR_S || 0) / stats.SCR_A) * 100).toFixed(1) + '%' : '0.0%';
        else value = stats[key] ?? 0;
        if (key in totals) totals[key] += Number(stats[key] || 0);
        if (key === 'DEF%') totals.DEF_S += Number(stats.DEF_S || 0);
        if (key === 'SCR%') totals.SCR_S += Number(stats.SCR_S || 0);
        const extraClass = key === 'W' ? ' col-w' : key === 'L' ? ' col-l' : '';
        html += '<td class="' + (groupStart + extraClass).trim() + '">' + value + '</td>';
      });
      tr.innerHTML = html;
      tbody.appendChild(tr);
    });

    const totalsTr = document.createElement('tr');
    totalsTr.className = 'totals-row';
    totalsTr.innerHTML =
      '<td class="col-group-start">TOTALS</td>' +
      '<td>--</td>' +
      '<td class="col-w">' + totals.W + '</td>' +
      '<td class="col-l">' + totals.L + '</td>' +
      '<td>' + totals.PF + '</td>' +
      '<td>' + totals.PA + '</td>' +
      '<td class="col-group-start">' + totals.FGM + '</td>' +
      '<td>' + totals.FGA + '</td>' +
      '<td>' + (totals.FGA > 0 ? ((totals.FGM / totals.FGA) * 100).toFixed(1) : '0.0') + '%</td>' +
      '<td class="col-group-start">' + totals['3PTM'] + '</td>' +
      '<td>' + totals['3PTA'] + '</td>' +
      '<td>' + (totals['3PTA'] > 0 ? ((totals['3PTM'] / totals['3PTA']) * 100).toFixed(1) : '0.0') + '%</td>' +
      '<td class="col-group-start">' + totals.FTM + '</td>' +
      '<td>' + totals.FTA + '</td>' +
      '<td>' + (totals.FTA > 0 ? ((totals.FTM / totals.FTA) * 100).toFixed(1) : '0.0') + '%</td>' +
      '<td class="col-group-start">' + totals.DREB + '</td>' +
      '<td>' + totals.OREB + '</td>' +
      '<td>' + totals.TREB + '</td>' +
      '<td class="col-group-start">' + totals.AST + '</td>' +
      '<td>' + totals.F + '</td>' +
      '<td>' + totals.TO + '</td>' +
      '<td>' + totals.SCR_A + '</td>' +
      '<td>' + (totals.SCR_A > 0 ? ((totals.SCR_S / totals.SCR_A) * 100).toFixed(1) : '0.0') + '%</td>' +
      '<td class="col-group-start">' + totals.STL + '</td>' +
      '<td>' + totals.BLK + '</td>' +
      '<td>' + totals.DEF_A + '</td>' +
      '<td>' + (totals.DEF_A > 0 ? ((totals.DEF_S / totals.DEF_A) * 100).toFixed(1) : '0.0') + '%</td>';
    tbody.appendChild(totalsTr);
  }

  function updateSortHeaders() {
    document.querySelectorAll('.fcc-team-stats-grid thead tr.col-row th.sortable').forEach(function (th) {
      const stat = th.getAttribute('data-stat');
      const arrow = th.querySelector('.sort-arrow');
      th.classList.remove('active');
      if (arrow) arrow.textContent = '';
      if (stat === sortColumn && sortDirection) {
        th.classList.add('active');
        if (arrow) arrow.textContent = sortDirection === 'desc' ? '↓' : '↑';
      }
    });
  }

  function render() {
    if (!teamStatsData || !teamStatsData.teams) return;
    defaultOrderTeams = cloneTeams(teamStatsData.teams);
    const rows = sortColumn && sortDirection ? sortTeams(defaultOrderTeams, sortColumn, sortDirection) : defaultOrderTeams;
    renderRows(rows);
    updateSortHeaders();
  }

  async function loadScope(scope) {
    const cached = resourceCache && resourceCache.get(scope);
    if (cached) return cached;
    const payload = await fetchJSON(
      API_CONFIG.buildUrl('/franchise/team-stats')
      + '?franchise_id=' + encodeURIComponent(franchiseId)
      + '&scope=' + encodeURIComponent(scope)
    );
    return resourceCache ? resourceCache.set(scope, payload) : payload;
  }

  function bindScopeButtons() {
    document.querySelectorAll('.stats-scope-btn').forEach(function (btn) {
      btn.addEventListener('click', async function () {
        const scope = btn.getAttribute('data-scope') || 'conference';
        if (scope === currentScope) return;
        currentScope = scope;
        sortColumn = 'rank';
        sortDirection = 'asc';
        document.querySelectorAll('.stats-scope-btn').forEach(function (other) {
          other.classList.toggle('active', other.getAttribute('data-scope') === currentScope);
        });
        const tbody = document.getElementById('teamstats-body');
        if (tbody) tbody.innerHTML = '<tr><td colspan="27">Loading team stats...</td></tr>';
        teamStatsData = await loadScope(currentScope);
        render();
      });
    });

    document.querySelectorAll('.fcc-team-stats-grid thead tr.col-row th.sortable').forEach(function (th) {
      th.addEventListener('click', function () {
        const stat = th.getAttribute('data-stat');
        if (sortColumn === stat) {
          if (sortDirection === 'desc') sortDirection = 'asc';
          else if (sortDirection === 'asc') {
            sortColumn = 'rank';
            sortDirection = 'asc';
          }
        } else {
          sortColumn = stat;
          sortDirection = stat === 'rank' ? 'asc' : 'desc';
        }
        render();
      });
    });
  }

  async function init() {
    if (!franchiseId) {
      const tbody = document.getElementById('teamstats-body');
      if (tbody) tbody.innerHTML = '<tr><td colspan="27">Missing franchise_id in URL.</td></tr>';
      return;
    }

    wireTopButtons();

    const topData = await fetchJSON(API_CONFIG.buildUrl('/franchise/command-center/data') + '?franchise_id=' + encodeURIComponent(franchiseId) + '&profile=1');
    if (topData) {
      populateTop(topData);
      resourceCache = window.ResourceCache.createResourceCache('fcc-team-stats', franchiseId, topData.current_season, topData.week);
    }

    wireTabRoutes();

    teamStatsData = await loadScope(currentScope);
    if (!teamStatsData) {
      const tbody = document.getElementById('teamstats-body');
      if (tbody) tbody.innerHTML = '<tr><td colspan="27">Failed to load team stats.</td></tr>';
      return;
    }
    render();
    bindScopeButtons();
  }

  window.addEventListener('DOMContentLoaded', init);
})();
