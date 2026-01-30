/**
 * Shared module for rendering and sorting roster player stats tables.
 * Used by both Tournament and Franchise command centers (Phase 4.2).
 *
 * Expects DOM: #roster-stats-body (tbody), #roster-tab .stats-table thead .sortable with data-stat.
 *
 * @module rosterStatsRenderer
 */
(function (global) {
  'use strict';

  var statsBodyId = 'roster-stats-body';
  var statsTableSelector = '#roster-tab .stats-table';
  var rosterPlayersDataForSorting = [];

  function getPlayerName(p) {
    return (p && (p.name || (p.first_name || '') + ' ' + (p.last_name || '')).trim()) || '';
  }

  function renderRosterStatsTable(players) {
    var tbody = document.getElementById(statsBodyId);
    if (!tbody) return;

    tbody.innerHTML = '';

    if (!players || players.length === 0) return;

    (players || []).forEach(function (p) {
      var stats = (p.stats && p.stats.season) ? p.stats.season : {};
      var tpm = stats['3PTM'] || 0;
      var tpa = stats['3PTA'] || 0;
      var fgPct = stats.FGA > 0 ? ((stats.FGM || 0) / stats.FGA * 100).toFixed(1) : '0.0';
      var threePct = tpa > 0 ? (tpm / tpa * 100).toFixed(1) : '0.0';
      var ftPct = stats.FTA > 0 ? ((stats.FTM || 0) / stats.FTA * 100).toFixed(1) : '0.0';

      var tr = document.createElement('tr');
      tr.innerHTML =
        '<td>' + getPlayerName(p) + '</td>' +
        '<td>' + (stats.PTS || 0) + '</td>' +
        '<td>' + (stats.FGM || 0) + '</td>' +
        '<td>' + (stats.FGA || 0) + '</td>' +
        '<td>' + fgPct + '%</td>' +
        '<td>' + tpm + '</td>' +
        '<td>' + tpa + '</td>' +
        '<td>' + threePct + '%</td>' +
        '<td>' + (stats.FTM || 0) + '</td>' +
        '<td>' + (stats.FTA || 0) + '</td>' +
        '<td>' + ftPct + '%</td>' +
        '<td>' + (stats.DREB || 0) + '</td>' +
        '<td>' + (stats.OREB || 0) + '</td>' +
        '<td>' + (stats.TREB || (stats.DREB || 0) + (stats.OREB || 0)) + '</td>' +
        '<td>' + (stats.AST || 0) + '</td>' +
        '<td>' + (stats.STL || 0) + '</td>' +
        '<td>' + (stats.BLK || 0) + '</td>' +
        '<td>' + (stats.F || 0) + '</td>' +
        '<td>' + (stats.MIN || 0) + '</td>' +
        '<td>' + (stats.TO || 0) + '</td>';
      tbody.appendChild(tr);
    });
  }

  function sortRosterStats(statKey) {
    var statMap = {
      'name': 'name',
      'PTS': 'PTS', 'FGM': 'FGM', 'FGA': 'FGA', 'FG%': 'FG%',
      '3PTM': '3PTM', '3PTA': '3PTA', '3PT%': '3PT%',
      'FTM': 'FTM', 'FTA': 'FTA', 'FT%': 'FT%',
      'DREB': 'DREB', 'OREB': 'OREB', 'TREB': 'TREB',
      'AST': 'AST', 'STL': 'STL', 'BLK': 'BLK', 'F': 'F', 'MIN': 'MIN', 'TO': 'TO'
    };
    var dataKey = statMap[statKey] || statKey;

    rosterPlayersDataForSorting.sort(function (a, b) {
      var val1, val2;
      var statsA = (a.stats && a.stats.season) ? a.stats.season : {};
      var statsB = (b.stats && b.stats.season) ? b.stats.season : {};

      if (dataKey === 'name') {
        return getPlayerName(b).localeCompare(getPlayerName(a));
      }
      if (dataKey === 'FG%') {
        val1 = statsA.FGA > 0 ? (statsA.FGM || 0) / statsA.FGA : 0;
        val2 = statsB.FGA > 0 ? (statsB.FGM || 0) / statsB.FGA : 0;
      } else if (dataKey === '3PT%') {
        var tpaA = statsA['3PTA'] || statsA.TPA || 0;
        var tpaB = statsB['3PTA'] || statsB.TPA || 0;
        val1 = tpaA > 0 ? ((statsA['3PTM'] || statsA.TPM || 0) / tpaA) : 0;
        val2 = tpaB > 0 ? ((statsB['3PTM'] || statsB.TPM || 0) / tpaB) : 0;
      } else if (dataKey === 'FT%') {
        val1 = statsA.FTA > 0 ? (statsA.FTM || 0) / statsA.FTA : 0;
        val2 = statsB.FTA > 0 ? (statsB.FTM || 0) / statsB.FTA : 0;
      } else if (dataKey === 'TREB') {
        val1 = statsA.TREB || (statsA.DREB || 0) + (statsA.OREB || 0);
        val2 = statsB.TREB || (statsB.DREB || 0) + (statsB.OREB || 0);
      } else {
        val1 = statsA[dataKey] || 0;
        val2 = statsB[dataKey] || 0;
      }
      return val2 - val1;
    });

    renderRosterStatsTable(rosterPlayersDataForSorting);
  }

  function renderRosterStats(players) {
    if (!players || players.length === 0) {
      var tbody = document.getElementById(statsBodyId);
      if (tbody) tbody.innerHTML = '';
      return;
    }

    rosterPlayersDataForSorting = JSON.parse(JSON.stringify(players));
    renderRosterStatsTable(rosterPlayersDataForSorting);

    var statsTable = document.querySelector(statsTableSelector);
    if (statsTable) {
      var sortableHeaders = statsTable.querySelectorAll('thead .sortable');
      sortableHeaders.forEach(function (header) {
        var newHeader = header.cloneNode(true);
        header.parentNode.replaceChild(newHeader, header);
        newHeader.style.cursor = 'pointer';
        newHeader.style.userSelect = 'none';
        newHeader.addEventListener('click', function () {
          var stat = newHeader.dataset.stat;
          sortRosterStats(stat);
        });
      });
    }
  }

  var api = {
    renderRosterStats: renderRosterStats,
    renderRosterStatsTable: renderRosterStatsTable,
    sortRosterStats: sortRosterStats
  };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  } else {
    global.RosterStatsRenderer = api;
  }
})(typeof window !== 'undefined' ? window : this);
