(function () {
  const params = new URLSearchParams(window.location.search);
  const franchiseId = params.get('franchise_id');
  const teamId = params.get('team_id');
  const root = document.getElementById('all-brackets-root');
  const backBtn = document.getElementById('brackets-back-btn');
  const footerSchedule = document.getElementById('brackets-footer-schedule');

  function resourceQuery() {
    if (!franchiseId || !teamId) return '';
    const p = new URLSearchParams();
    p.set('franchise_id', franchiseId);
    p.set('team_id', teamId);
    if (typeof getCurrentRelativeUrl === 'function') {
      p.set('return_url', getCurrentRelativeUrl());
    } else {
      p.set('return_url', window.location.pathname + window.location.search);
    }
    return `?${p.toString()}`;
  }

  if (backBtn && franchiseId && teamId) {
    backBtn.href = resolveFranchiseLockerRoomUrl({ params, franchiseId, teamId });
  }
  if (footerSchedule && franchiseId && teamId) {
    footerSchedule.href = `/schedule.html${resourceQuery()}`;
  }

  async function fetchJSON(url) {
    const res = await fetch(url, { headers: window.API_CONFIG ? API_CONFIG.getAuthHeaders() : {} });
    if (!res.ok) throw new Error('Request failed');
    return res.json();
  }

  async function run() {
    if (!root) return;
    if (!franchiseId || !teamId) {
      root.innerHTML =
        '<p class="fcc-tournament-empty-msg">Open this page from the Franchise Command Center (missing franchise or team).</p>';
      return;
    }
    root.innerHTML = '<p class="fcc-tournament-empty-msg">Loading brackets…</p>';
    try {
      const topData = await fetchJSON(
        `${API_CONFIG.buildUrl('/franchise/command-center/data')}?franchise_id=${encodeURIComponent(franchiseId)}&profile=1`
      );
      const teamIdToNameMap = {};
      const teamIdMetaMap = {};
      try {
        const teamStatsRes = await fetchJSON(
          `${API_CONFIG.buildUrl('/franchise/team-stats')}?franchise_id=${encodeURIComponent(franchiseId)}`
        );
        (teamStatsRes?.teams || []).forEach(function (t) {
          if (t.team_id != null && t.team != null) {
            teamIdToNameMap[String(t.team_id)] = t.team;
            teamIdMetaMap[String(t.team_id)] = {
              team: t.team,
              mascot: t.mascot || '',
              conference: t.conference,
            };
          }
        });
      } catch (e) {
        console.warn('[brackets] Could not load team-stats:', e);
      }
      if (!window.FranchiseTournamentBrackets || !FranchiseTournamentBrackets.appendFranchiseBracketSections) {
        root.innerHTML = '<p class="fcc-tournament-empty-msg">Bracket UI not loaded.</p>';
        return;
      }
      FranchiseTournamentBrackets.appendFranchiseBracketSections(root, topData, {
        userTeamId: teamId,
        teamIdToNameMap,
        teamIdMetaMap,
        mode: 'all',
      });
    } catch (e) {
      console.error(e);
      root.innerHTML = '<p class="fcc-tournament-empty-msg">Could not load tournament data.</p>';
    }
  }

  run();
})();
