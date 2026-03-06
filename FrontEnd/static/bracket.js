/**
 * Shared bracket renderer for FCC (Franchise EOS Tournament) and TCC (Tournament Command Center).
 * Single source of truth for 8-team single-elimination bracket DOM.
 * Caller provides: container, bracket data (round1, round2, final), team id→name map, and options.
 */
(function (global) {
  'use strict';

  function defaultGetLogo(teamName) {
    if (typeof getTeamAssetPath === 'function') {
      return getTeamAssetPath(teamName || '', 'banner_primary');
    }
    return '/images/teams/general/general_banner_primary.jpg';
  }

  function defaultIsUserTeam() {
    return false;
  }

  /**
   * Render bracket into container. Pure DOM; no fetch, no localStorage, no side effects.
   * @param {HTMLElement} container - Element to clear and append bracket to (e.g. #bracket or #tournament-bracket-container)
   * @param {{ round1: Array, round2: Array, final: Array }} bracketData - Bracket matchups per round
   * @param {Object.<string, string>} teamIdToNameMap - Map team_id (string) -> team name (string)
   * @param {Object} [options] - Optional: results, seeds, getLogo, isUserTeam
   * @param {Array} [options.results] - TCC-style results [{ round, match_index, score, winner }]; if omitted, use matchup.score/winner
   * @param {Object.<string, number>} [options.seeds] - teamId -> seed (1-8); if omitted, derive from round1 order (1v8, 4v5, 2v7, 3v6)
   * @param {function(string): string} [options.getLogo] - teamName -> logo src
   * @param {function(string): boolean} [options.isUserTeam] - teamId or teamName -> boolean
   */
  function renderBracketShared(container, bracketData, teamIdToNameMap, options) {
    if (!container) return;
    options = options || {};
    var getLogo = options.getLogo || defaultGetLogo;
    var isUserTeam = options.isUserTeam || defaultIsUserTeam;
    var results = options.results || [];
    var seedsOption = options.seeds || null;

    var round1 = bracketData.round1 || [];
    var round2 = bracketData.round2 || [];
    var finalRound = bracketData.final || [];

    container.innerHTML = '';

    var seedMap = {};
    if (seedsOption && typeof seedsOption === 'object') {
      seedMap = seedsOption;
    } else if (round1.length >= 4) {
      seedMap[round1[0].home_team] = 1;
      seedMap[round1[0].away_team] = 8;
      seedMap[round1[1].home_team] = 4;
      seedMap[round1[1].away_team] = 5;
      seedMap[round1[2].home_team] = 2;
      seedMap[round1[2].away_team] = 7;
      seedMap[round1[3].home_team] = 3;
      seedMap[round1[3].away_team] = 6;
    }

    function getResult(round, index) {
      return results.find(function (r) { return r.round === round && r.match_index === index; }) || null;
    }

    function teamName(id) {
      if (id == null) return id;
      var s = teamIdToNameMap[String(id)];
      return s != null ? s : id;
    }

    function createTeamEntry(teamId, teamNameVal, side, score, isWinner) {
      var div = document.createElement('div');
      div.className = 'team-entry';
      if (isWinner) div.classList.add('winner');
      var label = document.createElement('span');
      label.className = 'seed-label ' + (side === 'left' ? 'seed-left' : 'seed-right');
      label.textContent = seedMap[teamId] ? '#' + seedMap[teamId] : '';
      var img = document.createElement('img');
      img.src = getLogo(teamNameVal);
      img.classList.add('team-logo', 'bracket-logo');
      if (isUserTeam(teamId) || isUserTeam(teamNameVal)) img.classList.add('user-team');
      var scoreSpan = document.createElement('span');
      scoreSpan.className = 'score';
      scoreSpan.textContent = score !== undefined && score !== null ? score : '';
      if (side === 'left') {
        div.appendChild(label);
        div.appendChild(img);
        div.appendChild(scoreSpan);
      } else {
        div.appendChild(scoreSpan);
        div.appendChild(img);
        div.appendChild(label);
      }
      return div;
    }

    function createMatchup(m, side, round, index) {
      var wrap = document.createElement('div');
      wrap.className = 'matchup-wrapper';
      var matchup = document.createElement('div');
      matchup.className = 'matchup';
      var homeId = m.home_team;
      var awayId = m.away_team;
      var homeName = teamName(homeId);
      var awayName = teamName(awayId);
      var res = getResult(round, index);
      var homeScore = res && res.score && res.score[homeName] !== undefined ? res.score[homeName] : (m.score && (m.score[homeName] != null ? m.score[homeName] : m.score[homeId]));
      var awayScore = res && res.score && res.score[awayName] !== undefined ? res.score[awayName] : (m.score && (m.score[awayName] != null ? m.score[awayName] : m.score[awayId]));
      var winner = (res && res.winner != null) ? res.winner : m.winner;
      if (side === 'center') {
        matchup.appendChild(createTeamEntry(homeId, homeName, 'left', homeScore, winner === homeId || String(winner) === String(homeId)));
        matchup.appendChild(createTeamEntry(awayId, awayName, 'right', awayScore, winner === awayId || String(winner) === String(awayId)));
      } else {
        matchup.appendChild(createTeamEntry(homeId, homeName, side, homeScore, winner === homeId || String(winner) === String(homeId)));
        matchup.appendChild(createTeamEntry(awayId, awayName, side, awayScore, winner === awayId || String(winner) === String(awayId)));
      }
      wrap.appendChild(matchup);
      return wrap;
    }

    function createPlaceholder(label) {
      var wrap = document.createElement('div');
      wrap.className = 'matchup-wrapper';
      var matchup = document.createElement('div');
      matchup.className = 'matchup';
      var placeholder = document.createElement('div');
      placeholder.className = 'placeholder';
      placeholder.textContent = label || 'TBD';
      matchup.appendChild(placeholder);
      wrap.appendChild(matchup);
      return wrap;
    }

    var leftR1 = document.createElement('div');
    leftR1.className = 'round round-1 quarterfinals';
    if (round1[0]) leftR1.appendChild(createMatchup(round1[0], 'left', 1, 0));
    var leftSpacer = document.createElement('div');
    leftSpacer.style.height = '40px';
    leftSpacer.className = 'bracket-spacer';
    leftR1.appendChild(leftSpacer);
    if (round1[1]) leftR1.appendChild(createMatchup(round1[1], 'left', 1, 1));

    var leftSemi = document.createElement('div');
    leftSemi.className = 'round round-2 semifinals';
    if (round2[0]) leftSemi.appendChild(createMatchup(round2[0], 'left', 2, 0));
    else leftSemi.appendChild(createPlaceholder('Semifinals'));

    var finalEl = document.createElement('div');
    finalEl.className = 'round round-3 final';
    if (finalRound[0]) finalEl.appendChild(createMatchup(finalRound[0], 'center', 3, 0));
    else finalEl.appendChild(createPlaceholder('Championship!'));

    var rightSemi = document.createElement('div');
    rightSemi.className = 'round round-4 semifinals';
    if (round2[1]) rightSemi.appendChild(createMatchup(round2[1], 'right', 2, 1));
    else rightSemi.appendChild(createPlaceholder('Semifinals'));

    var rightR1 = document.createElement('div');
    rightR1.className = 'round round-5 quarterfinals';
    if (round1[2]) rightR1.appendChild(createMatchup(round1[2], 'right', 1, 2));
    var rightSpacer = document.createElement('div');
    rightSpacer.style.height = '40px';
    rightSpacer.className = 'bracket-spacer';
    rightR1.appendChild(rightSpacer);
    if (round1[3]) rightR1.appendChild(createMatchup(round1[3], 'right', 1, 3));

    container.appendChild(leftR1);
    container.appendChild(leftSemi);
    container.appendChild(finalEl);
    container.appendChild(rightSemi);
    container.appendChild(rightR1);
  }

  global.renderBracketShared = renderBracketShared;
})(typeof window !== 'undefined' ? window : this);
