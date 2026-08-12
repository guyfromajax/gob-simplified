// Team Roster View - Displays any team's roster with attributes and season stats
// Supports both Franchise and Tournament modes

const urlParams = new URLSearchParams(window.location.search);
const mode = urlParams.get('mode'); // 'franchise' or 'tournament' or 'practice_squad'
const teamId = urlParams.get('team_id'); // Team ObjectId or name
const teamName = urlParams.get('team_name'); // Team display name
const psTeamId = urlParams.get('ps_team_id');
const franchiseId = urlParams.get('franchise_id');
const tournamentId = urlParams.get('tournament_id');
const returnTab = urlParams.get('return_tab'); // 'standings-tab' or 'schedule-tab'
const returnUrl = urlParams.get('return_url'); // Full return URL

let rosterData = [];
let trainingSquadData = [];
let statsData = [];
let projectedStartingFive = [];
let rosterSortColumn = 'RT';
let rosterSortDirection = 'desc';
let statsSortColumn = 'PTS';
let statsSortDirection = 'desc';
// True once Week 35 Recruiting Day has run — recruits join the Practice Squad section.
let practiceSquadRecruitingDone = false;

const ROSTER_ATTR_KEYS = ['SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'AG', 'ST', 'ND', 'IQ', 'FT'];

function formatYearForDisplay(year) {
  if (typeof GOB_PlayerYear !== 'undefined' && GOB_PlayerYear.formatDisplay) {
    return GOB_PlayerYear.formatDisplay(year);
  }
  if (typeof RecruitingCommon !== 'undefined' && RecruitingCommon.formatYearDisplay) {
    return RecruitingCommon.formatYearDisplay(year);
  }
  if (!year) return '--';
  if (typeof yearMap !== 'undefined') {
    const abbr = yearMap[String(year).toLowerCase()];
    if (abbr) return abbr;
  }
  const s = String(year).trim();
  return s ? s.toUpperCase() : '--';
}

function yearSortValue(year) {
  if (typeof GOB_PlayerYear !== 'undefined' && GOB_PlayerYear.getSortValue) {
    return GOB_PlayerYear.getSortValue(year);
  }
  const order = { JH: 0, Freshman: 1, Sophomore: 2, Junior: 3, Senior: 4, Graduate: 5, FR: 1, SO: 2, JR: 3, SR: 4 };
  const normalized = formatYearForDisplay(year);
  return order[normalized] != null ? order[normalized] : (order[String(year).toUpperCase()] != null ? order[String(year).toUpperCase()] : 0);
}

function getRosterReturnStorageKey() {
  return [
    'roster_return_url',
    mode || 'base',
    franchiseId || '',
    tournamentId || '',
    teamId || teamName || ''
  ].join(':');
}

function resolveRosterReturnUrl() {
  const storageKey = getRosterReturnStorageKey();
  if (returnUrl) {
    sessionStorage.setItem(storageKey, returnUrl);
    return returnUrl;
  }

  const saved = sessionStorage.getItem(storageKey);
  if (saved) return saved;

  // Fallback for direct links that didn't include return_url.
  try {
    if (document.referrer) {
      const ref = new URL(document.referrer);
      if (ref.origin === window.location.origin && !ref.pathname.includes('player-detail.html')) {
        const relativeRef = `${ref.pathname}${ref.search}`;
        sessionStorage.setItem(storageKey, relativeRef);
        return relativeRef;
      }
    }
  } catch (e) {
    // Ignore referrer parse failures and continue to mode fallback.
  }

  return null;
}

function buildPlayerDetailUrl(playerId) {
  const qs = new URLSearchParams();
  qs.set('id', playerId);
  if (mode) qs.set('mode', mode);
  if (franchiseId) qs.set('franchise_id', franchiseId);
  if (tournamentId) qs.set('tournament_id', tournamentId);
  qs.set('return_url', window.location.pathname + window.location.search);
  return `/player-detail.html?${qs.toString()}`;
}

// Attribute groupings for card back
const ATTR_GROUPS = {
  'OFFENSE': ['SC', 'SH'],
  'DEFENSE': ['ID', 'OD'],
  'SKILLS': ['PS', 'BH'],
  'DIRTY WORK': ['RB', 'ST'],
  'PHYSICAL': ['AG', 'ND'],
  'MIND': ['IQ', 'FT']
};

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
  setupBackButton();
  
  const teamBannerEl = document.getElementById('team-banner');
  if (teamName) {
    if (teamBannerEl && typeof getTeamAssetPath === 'function') {
      teamBannerEl.src = getTeamAssetPath(teamName, 'banner_primary');
      teamBannerEl.alt = `${teamName} banner`;
    }
  }
  
  // Load roster and stats
  await loadRoster();
  await loadStats();
  
  // Setup sorting
  setupRosterSorting();
  setupStatsSorting();
});

function setupBackButton() {
  const backBtn = document.getElementById('back-button');
  const resolvedReturnUrl = resolveRosterReturnUrl();
  backBtn.addEventListener('click', () => {
    if (resolvedReturnUrl) {
      window.location.href = resolvedReturnUrl;
    } else {
      // Build return URL
      let returnPath = '';
      if (mode === 'franchise' && franchiseId) {
        returnPath = `/franchise-command-center.html?franchise_id=${franchiseId}`;
        if (returnTab) {
          returnPath += `&tab=${returnTab}`;
        }
      } else if (mode === 'tournament' && tournamentId) {
        returnPath = `/tournament.html?tournament_id=${tournamentId}`;
        if (returnTab) {
          returnPath += `&tab=${returnTab}`;
        }
      } else {
        // Base mode (from mode-select) - return to mode-select
        window.location.href = '/mode-select.html';
        return;
      }
      window.location.href = returnPath;
    }
  });
}

async function loadRoster() {
  try {
    if (mode === 'practice_squad' && franchiseId && psTeamId) {
      const url = API_CONFIG.buildUrl('/franchise/practice-squad/team')
        + '?franchise_id=' + encodeURIComponent(franchiseId)
        + '&ps_team_id=' + encodeURIComponent(psTeamId);
      const headers = window.API_CONFIG ? API_CONFIG.getAuthHeaders() : {};
      const response = await fetch(url, { headers });
      if (!response.ok) throw new Error('Failed to load Practice Squad team');
      const data = await response.json();
      const team = data.team || {};
      const titleEl = document.querySelector('.section-title');
      if (titleEl) titleEl.textContent = team.display_name || 'Practice Squad';
      const teamBannerEl = document.getElementById('team-banner');
      if (teamBannerEl) teamBannerEl.style.display = 'none';

      rosterData = (data.players || []).map(p => {
        const attrs = p.attributes || {};
        const posRatings = p.position_ratings || {};
        let highestRT = -Infinity;
        let highestPos = null;
        Object.entries(posRatings).forEach(([pos, rating]) => {
          if (typeof rating === 'number' && rating > highestRT) {
            highestRT = rating;
            highestPos = pos;
          }
        });
        const heightInches = p.height || 0;
        const displayName = p.parent_team_name
          ? `${p.name} (${p.parent_team_name})`
          : p.name;
        return {
          _id: p.player_id,
          name: displayName,
          jersey: null,
          pos: highestPos || getBestPosition(posRatings).pos || '--',
          year: formatYearForDisplay(p.year),
          height: `${Math.floor(heightInches / 12)}'${heightInches % 12}"`,
          weight: p.weight || '--',
          attributes: attrs,
          position_ratings: posRatings,
          potential_rt_ratcheted: p.potential_rt_ratcheted,
          highestRT: highestRT !== -Infinity ? highestRT : null,
          highestPos: highestPos || '--',
          psStats: p.stats || {},
        };
      });
      rosterData.sort((a, b) => (b.highestRT ?? -Infinity) - (a.highestRT ?? -Infinity));
      trainingSquadData = [];
      document.getElementById('training-squad-section')?.style.setProperty('display', 'none');
      projectedStartingFive = Array.isArray(data.projected_starting_five)
        ? data.projected_starting_five
        : [];
      renderStartingFive();
      renderRoster();
      return;
    }

    // ✅ UNIFIED: Use app-level /roster/{team_name} endpoint for all modes
    if (!teamName && !teamId) {
      document.getElementById('roster-body').innerHTML = '<tr><td colspan="18">Team name required</td></tr>';
      return;
    }
    
    const rosterLookup = (mode === 'franchise' && teamId) ? teamId : (teamName || teamId);
    let url = API_CONFIG.buildUrl(`/roster/${encodeURIComponent(rosterLookup)}`);
    const params = new URLSearchParams();
    
    // Support franchise, tournament, or base mode (no mode parameter)
    if (mode === 'franchise' && franchiseId) {
      params.append('franchise_id', franchiseId);
      if (teamId) params.append('team_id', teamId);
    } else if (mode === 'tournament' && tournamentId) {
      params.append('tournament_id', tournamentId);
    }
    params.append('profile', '1');
    if (params.toString()) {
      url += `?${params.toString()}`;
    }

    // Send the auth token — the backend returns franchise-scoped data (team
    // chemistry, training_squad / Practice Squad players) only for authenticated
    // requests. Without it the response is a degraded/unauthenticated view with an
    // empty training_squad, which is why the Practice Squad section never rendered.
    const authHeaders = window.API_CONFIG ? API_CONFIG.getAuthHeaders() : {};
    const response = await fetch(url, { headers: authHeaders });
    if (!response.ok) throw new Error(`Failed to load roster: ${response.status}`);
    const data = await response.json();
    
    rosterData = (data.players || []).map(p => {
      const attrs = p.attributes || {};
      const posRatings = p.position_ratings || {};
      
      // Calculate highest RT
      let highestRT = -Infinity;
      let highestPos = null;
      Object.entries(posRatings).forEach(([pos, rating]) => {
        if (typeof rating === 'number' && rating > highestRT) {
          highestRT = rating;
          highestPos = pos;
        }
      });
      
      // Format height
      const heightInches = p.height || 0;
      const feet = Math.floor(heightInches / 12);
      const inches = heightInches % 12;
      const heightDisplay = `${feet}'${inches}"`;
      
      return {
        _id: p._id,
        name: p.name || `${p.first_name || ''} ${p.last_name || ''}`.trim(),
        jersey: p.jersey,
        pos: p.position || getBestPosition(posRatings).pos || '--',
        year: formatYearForDisplay(p.year),
        height: heightDisplay,
        heightRaw: heightInches,
        weight: p.weight || '--',
        attributes: attrs,
        position_ratings: posRatings, // Store full position ratings for player view
        potential_rt_ratcheted: p.potential_rt_ratcheted,
        highestRT: highestRT !== -Infinity ? highestRT : null,
        highestPos: highestPos || (p.position || '--'),
        photo: p.photo || null,
        hasPlayingTimePromise: !!p.has_playing_time_promise,
        isGraduating: !!p.is_graduating
      };
    });
    
    // Default sort by RT descending
    rosterData.sort((a, b) => (b.highestRT ?? -Infinity) - (a.highestRT ?? -Infinity));

    // Practice Squad players (the 3 cut players) + Recruits (added after Week 35
    // Recruiting Day). Both render in the same section below the roster, with the
    // same row shape; recruits carry their Practice Squad season stats.
    const mapPsRow = (p) => {
      const posRatings = p.position_ratings || {};
      let highestRT = -Infinity;
      Object.entries(posRatings).forEach(([, rating]) => {
        if (typeof rating === 'number' && rating > highestRT) highestRT = rating;
      });
      const heightInches = p.height || 0;
      return {
        _id: p._id,
        name: p.name || `${p.first_name || ''} ${p.last_name || ''}`.trim(),
        jersey: p.jersey,
        pos: getBestPosition(posRatings).pos || '--',
        year: formatYearForDisplay(p.year),
        height: `${Math.floor(heightInches / 12)}'${heightInches % 12}"`,
        weight: p.weight || '--',
        attributes: p.attributes || {},
        position_ratings: posRatings,
        potential_rt_ratcheted: p.potential_rt_ratcheted,
        highestRT: highestRT !== -Infinity ? highestRT : null,
        psStats: p.ps_stats || {},
        isRecruit: !!p.is_recruit,
        hasPlayingTimePromise: false,
        isGraduating: false
      };
    };
    const psPlayers = (data.training_squad || []).map(mapPsRow);
    psPlayers.sort((a, b) => (b.highestRT ?? -Infinity) - (a.highestRT ?? -Infinity));
    const psRecruits = (data.practice_squad_recruits || []).map(mapPsRow);
    psRecruits.sort((a, b) => (b.highestRT ?? -Infinity) - (a.highestRT ?? -Infinity));
    trainingSquadData = psPlayers.concat(psRecruits);
    practiceSquadRecruitingDone = !!data.practice_squad_recruiting_done;

    projectedStartingFive = (mode === 'tournament')
      ? []
      : (Array.isArray(data.projected_starting_five) ? data.projected_starting_five : []);
    renderStartingFive();
    renderRoster();
    renderTrainingSquadView();
  } catch (error) {
    console.error('Error loading roster:', error);
    document.getElementById('roster-body').innerHTML = `<tr><td colspan="18">Error loading roster: ${error.message}</td></tr>`;
  }
}

async function loadStats() {
  try {
    if (mode === 'practice_squad') {
      statsData = rosterData.map(p => ({
        _id: p._id,
        name: p.name,
        stats: p.psStats || {},
      }));
      renderStats();
      return;
    }

    // Skip stats loading if in base mode (no franchise/tournament) or
    // FTE v2 tutorial mode — tutorial users haven't played any games yet,
    // so the table would be empty + the franchise/tournament branches
    // below would bail with "Invalid mode".
    if (!mode || mode === 'tutorial') {
      const statsSection = document.getElementById('stats-section');
      if (statsSection) {
        statsSection.style.display = 'none';
      }
      return;
    }
    
    // Wait for roster to load first so we have player IDs
    if (rosterData.length === 0) {
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    
    const teamPlayerIds = rosterData.map(p => p._id);
    if (teamPlayerIds.length === 0) {
      document.getElementById('stats-body').innerHTML = '<tr><td colspan="23">No players found</td></tr>';
      return;
    }
    
    let url = '';
    if (mode === 'franchise' && franchiseId) {
      // For franchise mode, we need to resolve team_id (ObjectId) from team_name
      // First, try to get team document to resolve ObjectId
      if (teamId && teamId.match(/^[0-9a-fA-F]{24}$/)) {
        // teamId is already an ObjectId string, use it
        url = `${API_CONFIG.buildUrl('/franchise/team-player-stats')}/${encodeURIComponent(teamId)}?franchise_id=${franchiseId}&scope=season`;
      } else if (teamName) {
        // Resolve team_id from team_name by fetching team document
        try {
          const teamsResponse = await fetch(API_CONFIG.buildUrl('/teams'));
          const teams = await teamsResponse.json();
          const teamDoc = teams.find(t => t.name === teamName);
          if (teamDoc && teamDoc._id) {
            url = `${API_CONFIG.buildUrl('/franchise/team-player-stats')}/${encodeURIComponent(teamDoc._id)}?franchise_id=${franchiseId}&scope=season`;
          } else {
            // Fallback: use leaders endpoint and filter by team
            url = `${API_CONFIG.buildUrl('/franchise/leaders')}?franchise_id=${franchiseId}&scope=season`;
          }
        } catch (e) {
          // Fallback: use leaders endpoint
          url = `${API_CONFIG.buildUrl('/franchise/leaders')}?franchise_id=${franchiseId}&scope=season`;
        }
      } else {
        // Fallback: use user team endpoint
        url = `${API_CONFIG.buildUrl('/franchise/team-player-stats')}?franchise_id=${franchiseId}&scope=season`;
      }
    } else if (mode === 'tournament' && tournamentId) {
      // ✅ FIX: Tournament mode - use tournament state endpoint to get tournament document and merge stats
      // Matches Franchise mode pattern (fetch roster + tournament document, merge stats)
      url = `${API_CONFIG.buildUrl('/tournament/state')}?tournament_id=${tournamentId}`;
    } else {
      document.getElementById('stats-body').innerHTML = '<tr><td colspan="23">Invalid mode or missing IDs</td></tr>';
      return;
    }

    const statsHeaders = window.API_CONFIG ? API_CONFIG.getAuthHeaders() : {};
    const response = await fetch(url, { headers: statsHeaders });
    if (!response.ok) throw new Error(`Failed to load stats: ${response.status}`);
    const data = await response.json();

    statsData = [];
    
    if (mode === 'franchise') {
      if (url.includes('/team-player-stats/')) {
        // Direct team stats endpoint
        statsData = (data.players || []).map(p => ({
          _id: p.player_id,
          name: `${p.first_name || ''} ${p.last_name || ''}`.trim(),
          stats: p.stats || {}
        }));
      } else {
        // Leaders endpoint - need to filter by team and aggregate
        // Leaders endpoint returns stats by category, we need to extract all players
        const allPlayers = new Map();
        Object.values(data).forEach(category => {
          if (Array.isArray(category)) {
            category.forEach(player => {
              if (teamPlayerIds.includes(player._id)) {
                if (!allPlayers.has(player._id)) {
                  allPlayers.set(player._id, { _id: player._id, name: player.name, stats: {} });
                }
                const playerData = allPlayers.get(player._id);
                // Merge stats from this category
                Object.assign(playerData.stats, player.stats || {});
              }
            });
          }
        });
        statsData = Array.from(allPlayers.values());
      }
    } else if (mode === 'tournament') {
      // ✅ FIX: Tournament mode - merge stats from tournament document (matches Franchise mode pattern)
      // Tournament state endpoint returns full tournament document with players object
      const tournamentPlayers = data.players || {};
      
      // Map roster players to stats from tournament document
      statsData = teamPlayerIds.map(pid => {
        const tournamentPlayer = tournamentPlayers[pid];
        const rosterPlayer = rosterData.find(p => p._id === pid);
        
        if (tournamentPlayer && tournamentPlayer.season) {
          // Player has stats in tournament document
          return {
            _id: pid,
            name: rosterPlayer ? rosterPlayer.name : `${tournamentPlayer.meta?.first_name || ''} ${tournamentPlayer.meta?.last_name || ''}`.trim(),
            stats: tournamentPlayer.season || {}
          };
        } else {
          // Player doesn't have stats yet (team hasn't played)
          return {
            _id: pid,
            name: rosterPlayer ? rosterPlayer.name : '',
            stats: {}
          };
        }
      });
    }
    
    renderStats();
  } catch (error) {
    console.error('Error loading stats:', error);
    document.getElementById('stats-body').innerHTML = `<tr><td colspan="23">Error loading stats: ${error.message}</td></tr>`;
  }
}

function getBestPosition(positionRatings) {
  let bestPos = null;
  let bestRating = -Infinity;
  Object.entries(positionRatings || {}).forEach(([pos, rating]) => {
    if (typeof rating === 'number' && rating > bestRating) {
      bestRating = rating;
      bestPos = pos;
    }
  });
  return { pos: bestPos || '--', rating: bestRating !== -Infinity ? bestRating : null };
}

function getRawAttrValue(attrs, attr) {
  const rawVal = attrs[`anchor_${attr}`] ?? attrs[attr];
  if (rawVal == null || rawVal === '') return null;
  const num = Number(rawVal);
  return Number.isNaN(num) ? null : num;
}

function formatAttrForDisplay(attrs, attr) {
  const rawVal = getRawAttrValue(attrs, attr);
  if (rawVal == null) return '--';
  return Math.floor(rawVal / 10);
}

function getAttrSortValue(attrs, attr) {
  const rawVal = getRawAttrValue(attrs, attr);
  if (rawVal == null) return -Infinity;
  return Math.floor(rawVal / 10);
}

function renderStartingFive() {
  const section = document.getElementById('starting-five-section');
  if (!section) return;
  if (mode === 'tournament') {
    section.style.display = 'none';
    return;
  }
  const rows = projectedStartingFive || [];
  if (!rows.length || typeof renderProjectedStartingFiveCards !== 'function') {
    section.style.display = 'none';
    return;
  }
  section.style.display = '';
  renderProjectedStartingFiveCards(rows, {
    containerId: 'roster-starting-five',
    emptyClass: 'scouting-projected-empty',
  });
}

function renderRoster() {
  renderRosterInto(rosterData, 'roster-body');
}

function renderTrainingSquadView() {
  const section = document.getElementById('ts-roster-section');
  if (!section) return;
  if (!trainingSquadData || !trainingSquadData.length) {
    section.style.display = 'none';
    return;
  }
  const titleEl = document.getElementById('ps-section-title');
  if (titleEl) {
    titleEl.textContent = 'Practice Squad';
  }
  renderRosterInto(trainingSquadData, 'ts-roster-body');
  renderPracticeSquadStats();
  section.style.display = '';
}

// Practice Squad stats subsection — mirrors the Season Statistics table, fed by
// each player's ps_season_stats (regional Practice Squad games). Percentages are
// computed client-side from made/attempted, same as renderStats().
function renderPracticeSquadStats() {
  const tbody = document.getElementById('ps-stats-body');
  if (!tbody) return;
  tbody.innerHTML = '';
  trainingSquadData.forEach(p => {
    const stats = p.psStats || {};
    const tr = document.createElement('tr');

    const nameTd = document.createElement('td');
    if (p.isRecruit) {
      nameTd.textContent = p.name;
    } else {
      const nameLink = document.createElement('a');
      nameLink.href = buildPlayerDetailUrl(p._id);
      nameLink.textContent =
        typeof formatNameWithJersey === 'function' ? formatNameWithJersey(p.jersey, p.name) : p.name;
      nameLink.style.color = 'inherit';
      nameLink.style.textDecoration = 'none';
      nameLink.addEventListener('mouseenter', () => { nameLink.style.textDecoration = 'underline'; });
      nameLink.addEventListener('mouseleave', () => { nameLink.style.textDecoration = 'none'; });
      nameTd.appendChild(nameLink);
    }
    tr.appendChild(nameTd);

    const addCell = (content) => {
      const td = document.createElement('td');
      td.textContent = content;
      tr.appendChild(td);
    };

    const tpm = stats['3PTM'] || 0;
    const tpa = stats['3PTA'] || 0;
    const fgm = stats.FGM || 0;
    const fga = stats.FGA || 0;
    const ftm = stats.FTM || 0;
    const fta = stats.FTA || 0;
    const defa = stats.DEF_A || 0;
    const defs = stats.DEF_S || 0;
    const scra = stats.SCR_A || 0;
    const scrs = stats.SCR_S || 0;

    addCell(stats.PTS || 0);
    addCell(fgm);
    addCell(fga);
    addCell(fga > 0 ? ((fgm / fga) * 100).toFixed(1) : '0.0');
    addCell(tpm);
    addCell(tpa);
    addCell(tpa > 0 ? ((tpm / tpa) * 100).toFixed(1) : '0.0');
    addCell(ftm);
    addCell(fta);
    addCell(fta > 0 ? ((ftm / fta) * 100).toFixed(1) : '0.0');
    addCell(stats.DREB || 0);
    addCell(stats.OREB || 0);
    addCell(stats.TREB || stats.REB || 0);
    addCell(stats.AST || 0);
    addCell(stats.STL || 0);
    addCell(stats.BLK || 0);
    addCell(stats.F || 0);
    addCell(stats.TO || 0);
    addCell(defa);
    addCell(defa > 0 ? `${Math.round((defs / defa) * 100)}%` : '0%');
    addCell(scra);
    addCell(scra > 0 ? ((scrs / scra) * 100).toFixed(1) : '0.0');

    tbody.appendChild(tr);
  });
}

function renderRosterInto(data, tbodyId) {
  const tbody = document.getElementById(tbodyId);
  if (!tbody) return;
  tbody.innerHTML = '';

  data.forEach(p => {
    const tr = document.createElement('tr');
    const attrs = p.attributes || {};
    
    // Name with link (Practice Squad team view & recruits: plain text, no jersey/detail page)
    const nameTd = document.createElement('td');
    if (mode === 'practice_squad' || p.isRecruit) {
      nameTd.textContent = p.name;
    } else {
      const nameLink = document.createElement('a');
      nameLink.href = buildPlayerDetailUrl(p._id);
      nameLink.textContent =
        typeof formatNameWithJersey === 'function' ? formatNameWithJersey(p.jersey, p.name) : p.name;
      nameLink.style.color = 'inherit';
      nameLink.style.textDecoration = 'none';
      nameLink.addEventListener('mouseenter', () => {
        nameLink.style.textDecoration = 'underline';
      });
      nameLink.addEventListener('mouseleave', () => {
        nameLink.style.textDecoration = 'none';
      });
      nameTd.appendChild(nameLink);
    }
    if (mode !== 'practice_squad' && p.hasPlayingTimePromise) {
      const ptp = document.createElement('span');
      ptp.textContent = ' (PTP)';
      ptp.style.color = '#bb2f35';
      ptp.style.fontWeight = '700';
      nameTd.appendChild(ptp);
    }
    if (p.isGraduating) {
      const gr = document.createElement('span');
      gr.textContent = ' (GR)';
      gr.style.color = '#2f8f46';
      gr.style.fontWeight = '700';
      nameTd.appendChild(gr);
    }
    tr.appendChild(nameTd);
    
    const addCell = (content, extraClass) => {
      const td = document.createElement('td');
      td.textContent = content;
      if (extraClass) td.className = extraClass;
      tr.appendChild(td);
      return td;
    };

    addCell(p.pos);
    addCell(p.year);
    addCell(p.height);
    addCell(p.weight);
    ROSTER_ATTR_KEYS.forEach((attr) => {
      addCell(formatAttrForDisplay(attrs, attr));
    });
    // RT colored per canonical Attribute Bar Scale (see /css/rt-buckets.css).
    // Potential Rating (§Phase 4): show current/potential (e.g. C/B) when the backend
    // supplied a projected ceiling; header stays "RT", color stays by current rating.
    const _rtText = p.highestRT === null
      ? '-'
      : formatRtWithPotentialDisplay(p.highestRT, p.potential_rt_ratcheted);
    const rtCell = addCell(
      _rtText,
      typeof window.getRtBucketClass === 'function' ? window.getRtBucketClass(p.highestRT) : ''
    );
    rtCell.setAttribute('data-tooltip', 'current/potential');
    rtCell.setAttribute('title', 'current/potential');
    
    tbody.appendChild(tr);
  });
  
  // Initialize tooltips if available. Scope to the whole roster table so the
  // column headers (SC, SH, ID, OD, …) also get tooltips, not just the data
  // cells under them.
  if (typeof initAttributeTooltips !== 'undefined') {
    const rosterTable = tbody.closest('table') || tbody;
    initAttributeTooltips(rosterTable, ['td', 'th']);
  }
}

function renderStats() {
  const tbody = document.getElementById('stats-body');
  tbody.innerHTML = '';
  
  if (statsData.length === 0) {
    tbody.innerHTML = '<tr><td colspan="23">No stats available</td></tr>';
    return;
  }
  
  // Match stats to roster by player ID
  const statsMap = new Map();
  statsData.forEach(s => {
    statsMap.set(s._id, s.stats || {});
  });
  
  rosterData.forEach(p => {
    const stats = statsMap.get(p._id) || {};
    const tr = document.createElement('tr');
    
    // Name
    const nameTd = document.createElement('td');
    const nameLink = document.createElement('a');
    nameLink.href = buildPlayerDetailUrl(p._id);
    nameLink.textContent =
      typeof formatNameWithJersey === 'function' ? formatNameWithJersey(p.jersey, p.name) : p.name;
    nameLink.style.color = 'inherit';
    nameLink.style.textDecoration = 'none';
    nameLink.addEventListener('mouseenter', () => {
      nameLink.style.textDecoration = 'underline';
    });
    nameLink.addEventListener('mouseleave', () => {
      nameLink.style.textDecoration = 'none';
    });
    nameTd.appendChild(nameLink);
    if (p.hasPlayingTimePromise) {
      const ptp = document.createElement('span');
      ptp.textContent = ' (PTP)';
      ptp.style.color = '#bb2f35';
      ptp.style.fontWeight = '700';
      nameTd.appendChild(ptp);
    }
    if (p.isGraduating) {
      const gr = document.createElement('span');
      gr.textContent = ' (GR)';
      gr.style.color = '#2f8f46';
      gr.style.fontWeight = '700';
      nameTd.appendChild(gr);
    }
    tr.appendChild(nameTd);
    
    const addCell = (content) => {
      const td = document.createElement('td');
      td.textContent = content;
      tr.appendChild(td);
    };
    
    // Use 3PTM/3PTA directly (standardized field names)
    const tpm = stats['3PTM'] || 0;
    const tpa = stats['3PTA'] || 0;
    const fgm = stats.FGM || 0;
    const fga = stats.FGA || 0;
    const ftm = stats.FTM || 0;
    const fta = stats.FTA || 0;
    const defa = stats.DEF_A || 0;
    const defs = stats.DEF_S || 0;
    const scra = stats.SCR_A || 0;
    const scrs = stats.SCR_S || 0;
    
    addCell(stats.PTS || 0);
    addCell(fgm);
    addCell(fga);
    addCell(fga > 0 ? ((fgm / fga) * 100).toFixed(1) : '0.0');
    addCell(tpm);
    addCell(tpa);
    addCell(tpa > 0 ? ((tpm / tpa) * 100).toFixed(1) : '0.0');
    addCell(ftm);
    addCell(fta);
    addCell(fta > 0 ? ((ftm / fta) * 100).toFixed(1) : '0.0');
    addCell(stats.DREB || 0);
    addCell(stats.OREB || 0);
    addCell(stats.TREB || stats.REB || 0);
    addCell(stats.AST || 0);
    addCell(stats.STL || 0);
    addCell(stats.BLK || 0);
    addCell(stats.F || 0);
    addCell(stats.TO || 0);
    addCell(defa);
    addCell(defa > 0 ? `${Math.round((defs / defa) * 100)}%` : '0%');
    addCell(scra);
    addCell(scra > 0 ? ((scrs / scra) * 100).toFixed(1) : '0.0');
    
    tbody.appendChild(tr);
  });
}

function setupRosterSorting() {
  const headers = document.querySelectorAll('#roster-table thead th');
  headers.forEach(header => {
    header.style.cursor = 'pointer';
    header.addEventListener('click', () => {
      const sortKey = header.dataset.sort;
      if (sortKey === rosterSortColumn) {
        rosterSortDirection = rosterSortDirection === 'desc' ? 'asc' : 'desc';
      } else {
        rosterSortColumn = sortKey;
        rosterSortDirection = 'desc';
      }
      sortRoster();
    });
  });
}

function sortRoster() {
  rosterData.sort((a, b) => {
    let val1, val2;
    
    if (rosterSortColumn === 'name') {
      val1 = a.name || '';
      val2 = b.name || '';
      return rosterSortDirection === 'desc' ? val2.localeCompare(val1) : val1.localeCompare(val2);
    } else if (rosterSortColumn === 'RT') {
      val1 = a.highestRT ?? -Infinity;
      val2 = b.highestRT ?? -Infinity;
    } else if (rosterSortColumn === 'year') {
      val1 = yearSortValue(a.year);
      val2 = yearSortValue(b.year);
    } else if (rosterSortColumn === 'height') {
      val1 = a.heightRaw || 0;
      val2 = b.heightRaw || 0;
    } else if (rosterSortColumn === 'weight') {
      val1 = parseInt(a.weight) || 0;
      val2 = parseInt(b.weight) || 0;
    } else {
      // Attribute columns
      val1 = getAttrSortValue(a.attributes || {}, rosterSortColumn);
      val2 = getAttrSortValue(b.attributes || {}, rosterSortColumn);
    }
    
    if (rosterSortDirection === 'desc') {
      return val2 - val1;
    } else {
      return val1 - val2;
    }
  });
  
  renderRoster();
}

function setupStatsSorting() {
  const headers = document.querySelectorAll('#stats-table thead th');
  headers.forEach(header => {
    header.style.cursor = 'pointer';
    header.addEventListener('click', () => {
      const sortKey = header.dataset.sort;
      if (sortKey === statsSortColumn) {
        statsSortDirection = statsSortDirection === 'desc' ? 'asc' : 'desc';
      } else {
        statsSortColumn = sortKey;
        statsSortDirection = 'desc';
      }
      sortStats();
    });
  });
}

function sortStats() {
  // Create a combined array for sorting
  const combined = rosterData.map(p => {
    const stats = statsData.find(s => s._id === p._id)?.stats || {};
    return { player: p, stats };
  });
  
  combined.sort((a, b) => {
    let val1, val2;
    
    if (statsSortColumn === 'name') {
      val1 = a.player.name || '';
      val2 = b.player.name || '';
      return statsSortDirection === 'desc' ? val2.localeCompare(val1) : val1.localeCompare(val2);
    } else if (statsSortColumn === 'FG%') {
      const fga1 = a.stats.FGA || 0;
      const fga2 = b.stats.FGA || 0;
      val1 = fga1 > 0 ? (a.stats.FGM || 0) / fga1 : 0;
      val2 = fga2 > 0 ? (b.stats.FGM || 0) / fga2 : 0;
    } else if (statsSortColumn === '3PT%') {
      const tpa1 = a.stats['3PTA'] || 0;
      const tpa2 = b.stats['3PTA'] || 0;
      const tpm1 = a.stats['3PTM'] || 0;
      const tpm2 = b.stats['3PTM'] || 0;
      val1 = tpa1 > 0 ? tpm1 / tpa1 : 0;
      val2 = tpa2 > 0 ? tpm2 / tpa2 : 0;
    } else if (statsSortColumn === 'FT%') {
      const fta1 = a.stats.FTA || 0;
      const fta2 = b.stats.FTA || 0;
      val1 = fta1 > 0 ? (a.stats.FTM || 0) / fta1 : 0;
      val2 = fta2 > 0 ? (b.stats.FTM || 0) / fta2 : 0;
    } else if (statsSortColumn === 'DEF%') {
      const defa1 = a.stats.DEF_A || 0;
      const defa2 = b.stats.DEF_A || 0;
      val1 = defa1 > 0 ? (a.stats.DEF_S || 0) / defa1 : 0;
      val2 = defa2 > 0 ? (b.stats.DEF_S || 0) / defa2 : 0;
    } else if (statsSortColumn === 'SCR%') {
      const scra1 = a.stats.SCR_A || 0;
      const scra2 = b.stats.SCR_A || 0;
      val1 = scra1 > 0 ? (a.stats.SCR_S || 0) / scra1 : 0;
      val2 = scra2 > 0 ? (b.stats.SCR_S || 0) / scra2 : 0;
    } else {
      val1 = a.stats[statsSortColumn] || 0;
      val2 = b.stats[statsSortColumn] || 0;
    }
    
    if (statsSortDirection === 'desc') {
      return val2 - val1;
    } else {
      return val1 - val2;
    }
  });
  
  // Update rosterData order
  rosterData = combined.map(item => item.player);
  
  // Re-render both tables
  renderRoster();
  renderStats();
}
