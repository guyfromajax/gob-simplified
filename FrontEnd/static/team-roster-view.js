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
  
  // One table, one sort path.
  trBindToolbar();
  renderTrTable();
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
      renderTrTable();
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
    trRenderLockup(data);
    renderStartingFive();
    renderTrTable();
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
      renderTrTable();
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
    
    renderTrTable();
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

// ===================== One data surface, two switches =====================
// Replaces the four stacked tables (attributes / stats / PS attributes / PS stats) with
// a single table driven by Scope (Varsity | Practice Squad) and View (Attributes |
// Season Stats). The old render*/setup*Sorting functions targeted elements that no
// longer exist; everything below is the live path.

// The four stacked tables (roster / stats / practice roster / practice stats) collapsed
// into one Scope x View surface; their renderers and sort handlers were removed with
// them. See the TR_* block below.
const TR_STATE = { scope: 'varsity', view: 'attributes', per: 'game', sortKey: 'RT', sortDir: 'desc' };

/** Season-stat columns grouped so the table reads like a box score.
 *  Columns are REORDERED within the existing set so each group is contiguous — DEFENSE
 *  was previously split by F/TO. The set itself is unchanged.
 *  `pct: true` columns are ratios, so the Per game / Totals toggle does not touch them. */
const TR_STAT_GROUPS = [
  { label: 'SCORING',      cols: [{ k: 'PTS' }] },
  { label: 'FIELD GOALS',  cols: [{ k: 'FGM' }, { k: 'FGA' }, { k: 'FG%', pct: true }] },
  { label: '3-POINT',      cols: [{ k: '3PTM' }, { k: '3PTA' }, { k: '3PT%', pct: true }] },
  { label: 'FREE THROWS',  cols: [{ k: 'FTM' }, { k: 'FTA' }, { k: 'FT%', pct: true }] },
  { label: 'REBOUNDING',   cols: [{ k: 'DREB' }, { k: 'OREB' }, { k: 'TREB' }] },
  { label: 'PLAYMAKING',   cols: [{ k: 'AST' }] },
  { label: 'DEFENSE',      cols: [{ k: 'STL' }, { k: 'BLK' }, { k: 'DEFA' }, { k: 'DEF%', pct: true }] },
  { label: 'SCREENS',      cols: [{ k: 'SCRA' }, { k: 'SCR%', pct: true }] },
  { label: 'MISTAKES',     cols: [{ k: 'F' }, { k: 'TO' }] },
];

function trPosChipHtml(pos) {
  return '<span class="pos-chip">' + escapeTrHtml(pos || '--') + '</span>';
}

function escapeTrHtml(v) {
  return String(v == null ? '' : v)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

/** RT current -> potential lockup. Colours from the shared bucket helper. */
function trRtLockupHtml(rt, potentialRt) {
  const cls = typeof window.getRtBucketClass === 'function' ? window.getRtBucketClass(rt) : '';
  const cur = typeof formatRtDisplay === 'function' ? formatRtDisplay(rt) : (rt == null ? '--' : String(rt));
  let html = '<span class="rt-lockup"><b class="' + cls + '">' + escapeTrHtml(cur) + '</b>';
  if (potentialRt != null) {
    const pcls = typeof window.getRtBucketClass === 'function' ? window.getRtBucketClass(potentialRt) : '';
    const pot = typeof formatRtDisplay === 'function' ? formatRtDisplay(potentialRt) : String(potentialRt);
    html += '<i class="' + pcls + '">' + escapeTrHtml(pot) + '</i>';
  }
  return html + '</span>';
}

function trIdentityCellHtml(p, opts) {
  const o = opts || {};
  const nameHtml = o.link === false
    ? escapeTrHtml(p.name || '--')
    : '<a href="' + escapeTrHtml(buildPlayerDetailUrl(p._id)) + '">' + escapeTrHtml(p.name || '--') + '</a>';
  let flags = '';
  if (p.hasPlayingTimePromise) flags += '<span class="ident-flag"> (PTP)</span>';
  if (p.isGraduating) flags += '<span class="ident-flag"> (GR)</span>';
  return '<td class="c-ident"><div class="ident">' +
    '<span class="ident-jersey">' + escapeTrHtml(p.jersey == null ? '' : p.jersey) + '</span>' +
    '<span class="ident-body"><span class="ident-name">' + nameHtml + flags + '</span></span>' +
    '</div></td>';
}

function trRowsForScope() {
  return TR_STATE.scope === 'practice' ? (trainingSquadData || []) : (rosterData || []);
}

// ---------- Attributes view ----------
function trAttrHeadHtml() {
  const grouped = window.GOB_AttrTiles.groupedHeaderHtml({ key: TR_STATE.sortKey, dir: TR_STATE.sortDir });
  const th = (key, label, cls) =>
    '<th' + (cls ? ' class="' + cls + '"' : '') + ' data-tr-sort="' + key + '">' + label + '</th>';
  return '<tr>' +
    th('name', 'Player', 'c-ident') +
    '<th class="c-rt" data-tr-sort="RT">RT<span class="rt-caption">cur &rarr; pot</span></th>' +
    th('pos', 'POS') + th('year', 'YR') + th('height', 'HT') + th('weight', 'WT') +
    '<th class="attr-tiles-head">' + grouped + '</th></tr>';
}

function trAttrRowHtml(p) {
  return '<tr>' + trIdentityCellHtml(p, { link: TR_STATE.scope !== 'practice' }) +
    '<td class="c-rt">' + trRtLockupHtml(p.highestRT, p.potential_rt_ratcheted) + '</td>' +
    '<td>' + trPosChipHtml(p.pos) + '</td>' +
    '<td>' + escapeTrHtml(p.year || '--') + '</td>' +
    '<td>' + escapeTrHtml(p.height || '--') + '</td>' +
    '<td>' + escapeTrHtml(p.weight == null ? '--' : p.weight) + '</td>' +
    '<td class="attr-tiles-cell">' + window.GOB_AttrTiles.groupedTilesHtml(p.attributes || {}) + '</td>' +
    '</tr>';
}

// ---------- Season Stats view ----------
function trStatsHeadHtml() {
  let groupRow = '<tr class="tr-grouprow"><th class="c-ident" rowspan="2" data-tr-sort="name">Player</th>';
  let colRow = '<tr class="tr-colrow">';
  TR_STAT_GROUPS.forEach((g) => {
    groupRow += '<th class="tr-grp" colspan="' + g.cols.length + '">' + g.label + '</th>';
    g.cols.forEach((c, i) => {
      colRow += '<th data-tr-sort="' + c.k + '"' + (i === 0 ? ' class="tr-groupstart"' : '') + '>' +
        escapeTrHtml(c.k) + '</th>';
    });
  });
  return groupRow + '</tr>' + colRow + '</tr>';
}

function trStatValue(stats, col, gp) {
  const raw = Number(stats[col.k] != null ? stats[col.k] : 0) || 0;
  if (col.pct) return raw.toFixed(1);                      // ratios ignore the toggle
  if (TR_STATE.per === 'total' || !gp) return Math.round(raw);
  return (raw / gp).toFixed(1);
}

function trStatsRowHtml(p, statsByPid) {
  const stats = statsByPid.get(p._id) || {};
  const gp = Number(stats.GP || 0) || 0;
  let cells = '';
  TR_STAT_GROUPS.forEach((g) => {
    g.cols.forEach((c, i) => {
      cells += '<td' + (i === 0 ? ' class="tr-groupstart"' : '') + '>' + escapeTrHtml(trStatValue(stats, c, gp)) + '</td>';
    });
  });
  return '<tr>' + trIdentityCellHtml(p, { link: TR_STATE.scope !== 'practice' }) + cells + '</tr>';
}

// ---------- render + sort ----------
function trStatsByPid() {
  const m = new Map();
  (statsData || []).forEach((s) => m.set(s._id, s.stats || {}));
  return m;
}

function trSortRows(rows) {
  const key = TR_STATE.sortKey;
  const dir = TR_STATE.sortDir;
  const statsByPid = trStatsByPid();
  const tiles = window.GOB_AttrTiles;
  const val = (p) => {
    if (key === 'name') return p.name || '';
    if (key === 'pos') return p.pos || '';
    if (key === 'year') return yearSortValue(p.year);
    if (key === 'height') return p.heightRaw || 0;
    if (key === 'weight') return p.weight != null ? p.weight : -1;
    if (key === 'RT') return p.highestRT != null ? p.highestRT : -1;
    if (tiles.ATTR_KEYS.indexOf(key) !== -1) {
      const v = tiles.tileValue(p.attributes || {}, key);
      return v == null ? -1 : v;
    }
    const stats = statsByPid.get(p._id) || {};
    const gp = Number(stats.GP || 0) || 0;
    return Number(trStatValue(stats, { k: key, pct: /%$/.test(key) }, gp)) || 0;
  };
  return rows.slice().sort((a, b) => {
    const av = val(a), bv = val(b);
    if (typeof av === 'string' || typeof bv === 'string') {
      return dir === 'asc' ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
    }
    return dir === 'asc' ? av - bv : bv - av;
  });
}

function renderTrTable() {
  const head = document.getElementById('tr-head');
  const body = document.getElementById('roster-body');
  if (!head || !body) return;
  const rows = trSortRows(trRowsForScope());
  const isStats = TR_STATE.view === 'stats';
  head.innerHTML = isStats ? trStatsHeadHtml() : trAttrHeadHtml();
  if (!rows.length) {
    const span = isStats ? 1 + TR_STAT_GROUPS.reduce((n, g) => n + g.cols.length, 0) : 7;
    body.innerHTML = '<tr><td colspan="' + span + '" class="tr-empty">No players to show.</td></tr>';
  } else if (isStats) {
    const statsByPid = trStatsByPid();
    body.innerHTML = rows.map((p) => trStatsRowHtml(p, statsByPid)).join('');
  } else {
    body.innerHTML = rows.map(trAttrRowHtml).join('');
  }
  // Per game / Totals belongs to the stats view only.
  const per = document.getElementById('tr-per-track');
  if (per) per.style.display = isStats ? 'inline-flex' : 'none';
  trUpdateCounts(rows.length);
  trBindSortControls();
  if (typeof initAttributeTooltips !== 'undefined') {
    initAttributeTooltips(document.getElementById('roster-table'), ['td', 'th', '.attr-tile', '.attr-abbr']);
  }
}

function trUpdateCounts(shown) {
  const varsity = (rosterData || []).length;
  const practice = (trainingSquadData || []).length;
  document.querySelectorAll('[data-tr-count]').forEach((el) => {
    el.textContent = el.dataset.trCount === 'practice' ? practice : varsity;
  });
  const rc = document.getElementById('tr-rowcount');
  if (rc) rc.textContent = shown + (shown === 1 ? ' player' : ' players');
}

function trSortBy(key, firstDir) {
  if (TR_STATE.sortKey === key) {
    TR_STATE.sortDir = TR_STATE.sortDir === 'desc' ? 'asc' : 'desc';
  } else {
    TR_STATE.sortKey = key;
    TR_STATE.sortDir = firstDir || 'desc';
  }
  renderTrTable();
}

function trBindSortControls() {
  document.querySelectorAll('#tr-head [data-tr-sort]').forEach((th) => {
    th.style.cursor = 'pointer';
    th.addEventListener('click', () => {
      const k = th.dataset.trSort;
      trSortBy(k, (k === 'name' || k === 'pos') ? 'asc' : 'desc');
    });
  });
  document.querySelectorAll('#tr-head [data-attr-sort]').forEach((btn) => {
    btn.addEventListener('click', (e) => { e.stopPropagation(); trSortBy(btn.dataset.attrSort, 'desc'); });
  });
}

function trBindToolbar() {
  const press = (sel, attr, value) => {
    document.querySelectorAll(sel).forEach((b) =>
      b.setAttribute('aria-pressed', b.dataset[attr] === value ? 'true' : 'false'));
  };
  document.querySelectorAll('[data-tr-scope]').forEach((b) => {
    b.addEventListener('click', () => {
      TR_STATE.scope = b.dataset.trScope;
      press('[data-tr-scope]', 'trScope', TR_STATE.scope);
      renderTrTable();
    });
  });
  document.querySelectorAll('[data-tr-view]').forEach((b) => {
    b.addEventListener('click', () => {
      TR_STATE.view = b.dataset.trView;
      press('[data-tr-view]', 'trView', TR_STATE.view);
      // Default sort per view so the table opens on something meaningful.
      TR_STATE.sortKey = TR_STATE.view === 'stats' ? 'PTS' : 'RT';
      TR_STATE.sortDir = 'desc';
      renderTrTable();
    });
  });
  document.querySelectorAll('[data-tr-per]').forEach((b) => {
    b.addEventListener('click', () => {
      TR_STATE.per = b.dataset.trPer;
      press('[data-tr-per]', 'trPer', TR_STATE.per);
      renderTrTable();
    });
  });
}

/** Identity lockup: team name plus record and conference standing from the payload. */
function trRenderLockup(data) {
  const nameEl = document.getElementById('tr-team-name');
  if (nameEl) nameEl.textContent = data.team_name || data.team || teamName || '--';
  const banner = document.getElementById('team-banner-card');
  if (banner && typeof getTeamAssetPath === 'function' && (data.team_name || teamName)) {
    banner.src = getTeamAssetPath(data.team_name || teamName, 'banner_primary');
  }
  const rec = data.team_record;
  const recEl = document.getElementById('tr-record');
  const standEl = document.getElementById('tr-standing');
  const block = document.getElementById('tr-record-block');
  if (!rec) { if (block) block.style.display = 'none'; return; }
  if (block) block.style.display = '';
  if (recEl) recEl.textContent = rec.wins + '-' + rec.losses;
  if (standEl) {
    standEl.textContent = rec.conference_place
      ? rec.conference_place + (rec.conference_size ? ' of ' + rec.conference_size : '')
      : '--';
  }
}
