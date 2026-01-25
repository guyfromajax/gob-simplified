/**
 * Shared module for rendering and sorting team stats tables
 * Used by both Tournament and Franchise modes
 * 
 * @module teamStatsTable
 */

// ✅ SS&S: Use IIFE pattern to work as both regular script and ES6 module
(function(global) {
  'use strict';
  
  /**
   * Renders team stats table with totals row
   * @param {Array} teams - Array of {team: string, stats: {...}} objects
   * @param {string} tbodyId - ID of tbody element to render into (default: 'teamstats-body')
   */
  function renderTeamStatsTable(teams, tbodyId = 'teamstats-body') {
  console.log('🔍 [DEBUG TeamStatsTable.renderTeamStatsTable] Starting with', teams.length, 'teams, tbodyId:', tbodyId);
  const tbody = document.getElementById(tbodyId);
  if (!tbody) {
    console.error('❌ [DEBUG TeamStatsTable.renderTeamStatsTable] tbody element not found:', tbodyId);
    return;
  }
  console.log('🔍 [DEBUG TeamStatsTable.renderTeamStatsTable] Found tbody element');
  tbody.innerHTML = '';
  
  // Calculate totals for all teams
  const totals = {
    W: 0, L: 0, PF: 0, PA: 0, FGM: 0, FGA: 0, "3PTM": 0, "3PTA": 0, FTM: 0, FTA: 0,
    DREB: 0, OREB: 0, TREB: 0, AST: 0, STL: 0, BLK: 0, F: 0, TO: 0,
    DEF_A: 0, DEF_S: 0, SCR_A: 0, SCR_S: 0
  };
  
  teams.forEach(t => {
    const tr = document.createElement('tr');
    const s = t.stats || {};
    
    // Accumulate totals
    totals.W += s.W || 0;
    totals.L += s.L || 0;
    totals.PF += s.PF || 0;
    totals.PA += s.PA || 0;
    totals.FGM += s.FGM || 0;
    totals.FGA += s.FGA || 0;
    totals["3PTM"] += s["3PTM"] || 0;
    totals["3PTA"] += s["3PTA"] || 0;
    totals.FTM += s.FTM || 0;
    totals.FTA += s.FTA || 0;
    totals.DREB += s.DREB || 0;
    totals.OREB += s.OREB || 0;
    totals.TREB += s.TREB || 0;
    totals.AST += s.AST || 0;
    totals.STL += s.STL || 0;
    totals.BLK += s.BLK || 0;
    totals.F += s.F || 0;
    totals.TO += s.TO || 0;
    totals.DEF_A += s.DEF_A || 0;
    totals.DEF_S += s.DEF_S || 0;
    totals.SCR_A += s.SCR_A || 0;
    totals.SCR_S += s.SCR_S || 0;
    
    // Calculate percentages
    const fgPct = s.FGA > 0 ? ((s.FGM || 0) / s.FGA * 100).toFixed(1) : '0.0';
    const threePct = s["3PTA"] > 0 ? ((s["3PTM"] || 0) / s["3PTA"] * 100).toFixed(1) : '0.0';
    const ftPct = s.FTA > 0 ? ((s.FTM || 0) / s.FTA * 100).toFixed(1) : '0.0';
    const defPct = s.DEF_A > 0 ? ((s.DEF_S || 0) / s.DEF_A * 100).toFixed(1) : '0.0';
    const scrPct = s.SCR_A > 0 ? ((s.SCR_S || 0) / s.SCR_A * 100).toFixed(1) : '0.0';
    
    tr.innerHTML = `
      <td>${t.team}</td>
      <td>${s.W || 0}</td>
      <td>${s.L || 0}</td>
      <td>${s.PF || 0}</td>
      <td>${s.PA || 0}</td>
      <td>${s.FGM || 0}</td>
      <td>${s.FGA || 0}</td>
      <td>${fgPct}%</td>
      <td>${s["3PTM"] || 0}</td>
      <td>${s["3PTA"] || 0}</td>
      <td>${threePct}%</td>
      <td>${s.FTM || 0}</td>
      <td>${s.FTA || 0}</td>
      <td>${ftPct}%</td>
      <td>${s.DREB || 0}</td>
      <td>${s.OREB || 0}</td>
      <td>${s.TREB || 0}</td>
      <td>${s.AST || 0}</td>
      <td>${s.STL || 0}</td>
      <td>${s.BLK || 0}</td>
      <td>${s.F || 0}</td>
      <td>${s.TO || 0}</td>
      <td>${s.DEF_A || 0}</td>
      <td>${defPct}%</td>
      <td>${s.SCR_A || 0}</td>
      <td>${scrPct}%</td>
    `;
    tbody.appendChild(tr);
  });
  
  // Add totals row
  const totalsTr = document.createElement('tr');
  totalsTr.className = 'totals-row';
  totalsTr.style.fontWeight = 'bold';
  totalsTr.style.pointerEvents = 'none'; // Prevent any click interactions
  
  // Calculate total percentages
  const totalFgPct = totals.FGA > 0 ? (totals.FGM / totals.FGA * 100).toFixed(1) : '0.0';
  const totalThreePct = totals["3PTA"] > 0 ? (totals["3PTM"] / totals["3PTA"] * 100).toFixed(1) : '0.0';
  const totalFtPct = totals.FTA > 0 ? (totals.FTM / totals.FTA * 100).toFixed(1) : '0.0';
  const totalDefPct = totals.DEF_A > 0 ? (totals.DEF_S / totals.DEF_A * 100).toFixed(1) : '0.0';
  const totalScrPct = totals.SCR_A > 0 ? (totals.SCR_S / totals.SCR_A * 100).toFixed(1) : '0.0';
  
  totalsTr.innerHTML = `
    <td>TOTALS</td>
    <td>${totals.W}</td>
    <td>${totals.L}</td>
    <td>${totals.PF}</td>
    <td>${totals.PA}</td>
    <td>${totals.FGM}</td>
    <td>${totals.FGA}</td>
    <td>${totalFgPct}%</td>
    <td>${totals["3PTM"]}</td>
    <td>${totals["3PTA"]}</td>
    <td>${totalThreePct}%</td>
    <td>${totals.FTM}</td>
    <td>${totals.FTA}</td>
    <td>${totalFtPct}%</td>
    <td>${totals.DREB}</td>
    <td>${totals.OREB}</td>
    <td>${totals.TREB}</td>
    <td>${totals.AST}</td>
    <td>${totals.STL}</td>
    <td>${totals.BLK}</td>
    <td>${totals.F}</td>
    <td>${totals.TO}</td>
    <td>${totals.DEF_A}</td>
    <td>${totalDefPct}%</td>
    <td>${totals.SCR_A}</td>
    <td>${totalScrPct}%</td>
  `;
  tbody.appendChild(totalsTr);
  console.log('✅ [DEBUG TeamStatsTable.renderTeamStatsTable] Rendered', teams.length, 'teams + totals row');
}

  /**
   * Sorts team stats data and re-renders table
   * @param {string} statKey - Stat key to sort by (from header data-stat attribute)
   * @param {Array} teamsData - Teams data array (will be sorted in place)
   * @param {string} tbodyId - ID of tbody element to render into (default: 'teamstats-body')
   */
  function sortTeamStats(statKey, teamsData, tbodyId = 'teamstats-body') {
  // Map display stat names to data stat keys
  const statMap = {
    'team': 'team',
    'W': 'W',
    'L': 'L',
    'PF': 'PF',
    'PA': 'PA',
    'FGM': 'FGM',
    'FGA': 'FGA',
    'FG%': 'FG%',
    '3PTM': '3PTM',
    '3PTA': '3PTA',
    '3PT%': '3PT%',
    'FTM': 'FTM',
    'FTA': 'FTA',
    'FT%': 'FT%',
    'DREB': 'DREB',
    'OREB': 'OREB',
    'TREB': 'TREB',
    'AST': 'AST',
    'STL': 'STL',
    'BLK': 'BLK',
    'F': 'F',
    'TO': 'TO',
    'DEF_A': 'DEF_A',
    'DEF%': 'DEF%',
    'SCR_A': 'SCR_A',
    'SCR%': 'SCR%'
  };
  
  const dataKey = statMap[statKey] || statKey;
  
  // Sort teams by the selected stat (descending order)
  teamsData.sort((a, b) => {
    const s1 = a.stats || {};
    const s2 = b.stats || {};
    
    let val1, val2;
    
    if (dataKey === 'team') {
      val1 = a.team || '';
      val2 = b.team || '';
      return val2.localeCompare(val1); // Reverse for descending
    } else if (dataKey === 'FG%') {
      val1 = s1.FGA > 0 ? (s1.FGM || 0) / s1.FGA : 0;
      val2 = s2.FGA > 0 ? (s2.FGM || 0) / s2.FGA : 0;
    } else if (dataKey === '3PT%') {
      val1 = s1["3PTA"] > 0 ? (s1["3PTM"] || 0) / s1["3PTA"] : 0;
      val2 = s2["3PTA"] > 0 ? (s2["3PTM"] || 0) / s2["3PTA"] : 0;
    } else if (dataKey === 'FT%') {
      val1 = s1.FTA > 0 ? (s1.FTM || 0) / s1.FTA : 0;
      val2 = s2.FTA > 0 ? (s2.FTM || 0) / s2.FTA : 0;
    } else if (dataKey === 'DEF%') {
      val1 = s1.DEF_A > 0 ? (s1.DEF_S || 0) / s1.DEF_A : 0;
      val2 = s2.DEF_A > 0 ? (s2.DEF_S || 0) / s2.DEF_A : 0;
    } else if (dataKey === 'SCR%') {
      val1 = s1.SCR_A > 0 ? (s1.SCR_S || 0) / s1.SCR_A : 0;
      val2 = s2.SCR_A > 0 ? (s2.SCR_S || 0) / s2.SCR_A : 0;
    } else {
      val1 = s1[dataKey] || 0;
      val2 = s2[dataKey] || 0;
    }
    
    return val2 - val1; // Descending order
  });
  
    // Re-render with sorted data
    renderTeamStatsTable(teamsData, tbodyId);
  }
  
  // Export for both regular script and ES6 module
  if (typeof module !== 'undefined' && module.exports) {
    // Node.js/CommonJS
    module.exports = { renderTeamStatsTable, sortTeamStats };
  } else if (typeof global !== 'undefined') {
    // Browser global
    global.TeamStatsTable = { renderTeamStatsTable, sortTeamStats };
  }
  
  // ES6 module export
  if (typeof window !== 'undefined') {
    window.TeamStatsTable = { renderTeamStatsTable, sortTeamStats };
  }
})(typeof window !== 'undefined' ? window : typeof global !== 'undefined' ? global : this);

