const urlParams = new URLSearchParams(window.location.search);
console.log('✅ set-lineup.js loaded at', new Date().toISOString());
// Append cache buster to any dynamic loads if present
(function(){
  const s = document.querySelector('script[src*="set-lineup.js"]');
  if (s && s.src.includes('__BUILD_TS__')) {
    const now = Date.now().toString();
    s.src = s.src.replace('__BUILD_TS__', now);
    console.log('🔄 Updated script src with cache buster', s.src);
  }
})();
const homeTeam = urlParams.get('home');
const awayTeam = urlParams.get('away');
const homeId = urlParams.get('home_id');
const awayId = urlParams.get('away_id');
let myTeamSide = urlParams.get('my_team');
const userTeamIdParam = urlParams.get('user_team_id');
const franchiseId = urlParams.get('franchise_id');
const weekParam = urlParams.get('week');
const tournamentId = urlParams.get('tournament_id');
const modeParam = urlParams.get('mode');
const DEBUG = urlParams.has('debug');
const quarter = parseInt(urlParams.get('quarter'), 10) || 1;
let gameId = urlParams.get('game_id') ||
  (typeof localStorage !== 'undefined' ? localStorage.getItem('game_id') : null);
const storedHome = typeof localStorage !== 'undefined' ? localStorage.getItem('game_home') : null;
const storedAway = typeof localStorage !== 'undefined' ? localStorage.getItem('game_away') : null;

// FIXED: Only clear gameId when teams actually change (new matchup)
// Don't clear it just because it's Q1 - let backend handle "Q1 but saved Q2+" detection
// This preserves the init-game flow which needs gameId to exist
const isNewMatchup = !urlParams.get('game_id') && (storedHome !== homeTeam || storedAway !== awayTeam);
if (isNewMatchup) {
  // Teams changed = definitely a new matchup, clear old gameId
  gameId = null;
  if (typeof localStorage !== 'undefined') {
    localStorage.removeItem('game_id');
    localStorage.setItem('game_home', homeTeam || '');
    localStorage.setItem('game_away', awayTeam || '');
  }
  if (typeof history !== 'undefined' && history.replaceState) {
    const clean = new URLSearchParams(urlParams);
    ['quarter', 'period', 'game_id'].forEach(k => clean.delete(k));
    const qs = clean.toString();
    history.replaceState(null, '', `${window.location.pathname}${qs ? `?${qs}` : ''}`);
  }
} else if ((quarter > 1 || urlParams.has('game_id')) &&
           typeof history !== 'undefined' && history.replaceState) {
  const clean = new URLSearchParams(urlParams);
  ['quarter', 'period', 'game_id'].forEach(k => clean.delete(k));
  const qs = clean.toString();
  history.replaceState(null, '', `${window.location.pathname}${qs ? `?${qs}` : ''}`);
}

// Re-check localStorage for gameId if we still don't have one (user navigating back during active game)
// Also check if teams match stored teams to ensure gameId is for this matchup
if (!gameId && typeof localStorage !== 'undefined') {
  const storedGameId = localStorage.getItem('game_id');
  const storedHome = localStorage.getItem('game_home');
  const storedAway = localStorage.getItem('game_away');
  // Only use stored gameId if teams match (same matchup)
  if (storedGameId && storedHome === homeTeam && storedAway === awayTeam) {
    gameId = storedGameId;
    console.log('[Lineup] Using gameId from localStorage (teams match)');
  }
}

// FIXED: Additional check - if we have a gameId but it's Q1, verify it's valid
// If user starts Q1 but saved game is Q2+, backend will handle detection via heuristic
// Frontend just needs to ensure gameId exists for init-game flow to work

console.log('[Lineup] gameId check:', {
  fromUrl: urlParams.get('game_id'),
  fromLocalStorage: typeof localStorage !== 'undefined' ? localStorage.getItem('game_id') : null,
  finalGameId: gameId,
  quarter: quarter,
  homeTeam: homeTeam,
  awayTeam: awayTeam,
  storedHome: typeof localStorage !== 'undefined' ? localStorage.getItem('game_home') : null,
  storedAway: typeof localStorage !== 'undefined' ? localStorage.getItem('game_away') : null
});

const periodLabel = urlParams.get('period') || `Q${quarter}`;
let teamName = '';

let roster = [];
const lineup = {};
const playerMap = {};

function getRT(player) {
  const ratings = Object.values(player.position_ratings || {});
  return ratings.length ? Math.max(...ratings) : -Infinity;
}

function showToast(msg) {
  const toast = document.getElementById('toast');
  if (!toast) return;
  toast.textContent = msg;
  toast.hidden = false;
  setTimeout(() => { toast.hidden = true; }, 2000);
}

async function loadRoster() {
  if (!teamName) return;
  
  // Use franchise-specific roster endpoint if in franchise mode
  let url;
  if (franchiseId) {
    url = `/franchise/roster?franchise_id=${franchiseId}&team_name=${encodeURIComponent(teamName)}`;
    console.log("Loading franchise-specific roster for lineup");
  } else {
    url = `/roster/${encodeURIComponent(teamName)}`;
    console.log("Loading standard roster for lineup");
  }
  
  const res = await fetch(url);
  if (!res.ok) return;
  const data = await res.json();
  roster = (data.players || []).map((p, idx) => ({ ...p, _idx: idx }));
  
  // If no gameId, initialize a new game (for pre-game lineup screen)
  // This creates a game document with initialized players (Emotion, Momentum)
  if (!gameId && homeTeam && awayTeam) {
    console.log("No gameId found - initializing new game for pre-game lineup");
    try {
      const mode = modeParam || 'single';
      const initRes = await fetch('/api/init-game', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          home_team: homeTeam,
          away_team: awayTeam,
          mode: mode
        })
      });
      if (initRes.ok) {
        const initData = await initRes.json();
        gameId = initData.game_id;
        console.log("✅ Initialized new game:", gameId);
        
        // Store gameId in localStorage and URL
        if (typeof localStorage !== 'undefined') {
          localStorage.setItem('game_id', gameId);
          localStorage.setItem('game_home', homeTeam);
          localStorage.setItem('game_away', awayTeam);
        }
        
        // Update URL with gameId (without page reload)
        const newParams = new URLSearchParams(window.location.search);
        newParams.set('game_id', gameId);
        if (typeof history !== 'undefined' && history.replaceState) {
          history.replaceState(null, '', `${window.location.pathname}?${newParams.toString()}`);
        }
      } else {
        console.warn("Failed to initialize game:", initRes.status, initRes.statusText);
      }
    } catch (err) {
      console.warn("Could not initialize game:", err);
    }
  }
  
  // If there's an active game, fetch current player energy levels
  // Pass quarter=1 to detect new game scenarios (Q1 request when saved game is Q2+)
  if (gameId) {
    console.log("Loading current player energy from game:", gameId);
    try {
        const gameRes = await fetch(`/api/game/${gameId}?quarter=1`);
        if (gameRes.ok) {
          const gameData = await gameRes.json();
          const gamePlayers = gameData.players || [];
          const ineligiblePlayers = gameData.ineligible_players || [];
          
          // Mark ineligible players in roster
          if (ineligiblePlayers.length > 0) {
            console.log(`Found ${ineligiblePlayers.length} ineligible players (fouled out)`);
            roster.forEach(player => {
              const playerId = player._id || player.playerId || player.player_id;
              if (playerId && ineligiblePlayers.includes(String(playerId))) {
                player.ineligible = true;
                player.fouled_out = true;
                console.log(`Marked ${player.name} as ineligible (fouled out)`);
                
                // Remove from current lineup if in lineup
                Object.keys(lineup).forEach(pos => {
                  if (lineup[pos] === playerId) {
                    console.log(`Removing ${player.name} from lineup position ${pos} (fouled out)`);
                    lineup[pos] = null;
                    const slot = document.querySelector(`.slot[data-pos="${pos}"]`);
                    if (slot) {
                      const slotContent = slot.querySelector('.slot-content');
                      if (slotContent) {
                        slotContent.innerHTML = '';
                        slotContent.classList.add('empty');
                        slot.classList.remove('filled');
                        slot.draggable = false;
                        const removeBtn = slot.querySelector('.remove-btn');
                        if (removeBtn) removeBtn.hidden = true;
                      }
                    }
                  }
                });
              }
            });
            // Re-render views to show visual indicators
            if (currentView === 'grid') {
              renderRoster();
            } else if (currentView === 'player') {
              renderPlayerView();
            }
          }
          
          console.log(`Found ${gamePlayers.length} players with energy data from game`);
          
          // Debug: Log roster player names and IDs
          console.log('[Lineup] Roster players:', roster.map(p => ({
            name: p.name,
            id: p._id || p.playerId || p.player_id
          })));
          
          // Debug: Log game player names and IDs
          console.log('[Lineup] Game players:', gamePlayers.map(gp => ({
            name: gp.name,
            id: gp._id || gp.playerId || gp.player_id,
            hasStats: !!gp.stats
          })));
        
        // Merge game data into roster (same approach as box-score.js)
        let updatedCount = 0;
        gamePlayers.forEach(gp => {
          const playerId = gp._id || gp.playerId || gp.player_id;
          if (!playerId) {
            console.warn("Game player missing ID:", gp);
            return;
          }
          
          // Try to find by ID first, then by name (same as box-score.js)
          let rosterPlayer = roster.find(p => {
            const rosterId = p._id || p.playerId || p.player_id;
            return String(rosterId) === String(playerId);
          });
          
          // Fallback to name matching if ID doesn't match
          if (!rosterPlayer && gp.name) {
            rosterPlayer = roster.find(p => p.name === gp.name);
            if (rosterPlayer) {
              console.log(`[Lineup] Matched ${gp.name} by name (ID mismatch: game=${playerId}, roster=${rosterPlayer._id || rosterPlayer.playerId || rosterPlayer.player_id})`);
            }
          }
          
          if (rosterPlayer) {
            // Energy (same as before)
            rosterPlayer.attributes = rosterPlayer.attributes || {};
            const energyValue = gp.NG ?? gp.energy ?? gp.attributes?.NG ?? 1.0;
            rosterPlayer.attributes.NG = energyValue;
            rosterPlayer.NG = energyValue;
            
            // Stats: Use EXACT same approach as box-score.js (line 203)
            // Flatten stats to player.stats (not nested under .game)
            rosterPlayer.stats = gp.stats?.game || gp.stats || {};
            
            // Attributes: EM and MO
            if (gp.attributes) {
              rosterPlayer.attributes.EM = gp.attributes.EM ?? rosterPlayer.attributes.EM ?? 50;
              rosterPlayer.attributes.MO = gp.attributes.MO ?? rosterPlayer.attributes.MO ?? 0;
              rosterPlayer.EM = rosterPlayer.attributes.EM;
              rosterPlayer.MO = rosterPlayer.attributes.MO;
            }
            
            updatedCount++;
          } else {
            // Debug: Show what we tried to match
            const rosterNames = roster.map(p => p.name).join(', ');
            console.warn(`Could not find roster player for game player: ${gp.name || 'Unknown'} (ID: ${playerId})`, {
              triedName: gp.name,
              rosterNames: rosterNames,
              rosterCount: roster.length
            });
          }
        });
        
        console.log(`Successfully updated ${updatedCount} players with game data`);
        
        // Update playerMap (same objects, just ensure references are current)
        roster.forEach(p => {
          const playerId = p._id || p.playerId || p.player_id;
          if (playerId) {
            playerMap[playerId] = p;
          }
        });
        
        // Refresh slot displays to show updated stats
        updateAllSlotDisplays();
      } else {
        console.warn(`Failed to fetch game data: ${gameRes.status} ${gameRes.statusText}`);
      }
    } catch (err) {
      console.warn("Could not load player energy from game:", err);
    }
  } else {
    console.log("No gameId found, skipping energy load (players will show default 100%)");
  }
  
  roster.sort((a, b) => {
    const diff = getRT(b) - getRT(a);
    return diff !== 0 ? diff : a._idx - b._idx;
  });
  console.log("Sorted lineup by RT descending");
  roster.forEach(p => {
    delete p._idx;
    playerMap[p._id] = p;
  });
  renderRoster();
}

function renderRoster() {
  const tbody = document.getElementById('roster-body');
  if (!tbody) return;
  tbody.innerHTML = '';
  roster.forEach(p => {
    const tr = document.createElement('tr');
    tr.draggable = !p.ineligible;  // Disable drag for ineligible players
    tr.dataset.playerId = p._id;
    if (p.ineligible) {
      tr.classList.add('ineligible');  // Add class for styling
      tr.style.opacity = '0.5';  // Shade out
      tr.style.pointerEvents = 'none';  // Disable interactions
    }
    tr.addEventListener('dragstart', e => {
      e.dataTransfer.setData('text/plain', p._id);
    });

    const posRatings = p.position_ratings || {};
    let bestPos = '--';
    let rt = '--';
    const entries = Object.entries(posRatings);
    if (entries.length) {
      const [pos, rating] = entries.reduce((a, b) => b[1] > a[1] ? b : a);
      bestPos = pos;
      rt = rating;
    }
    // Use anchor attributes (don't show energy-scaled values)
    const anchorAttrs = p.attributes || {};
    
    const cells = [
      p.name,
      bestPos,
      formatHeight(p.height),
      p.weight ?? '--',
      Math.floor((anchorAttrs.anchor_SC ?? anchorAttrs.SC ?? 0) / 10), 
      Math.floor((anchorAttrs.anchor_SH ?? anchorAttrs.SH ?? 0) / 10), 
      Math.floor((anchorAttrs.anchor_ID ?? anchorAttrs.ID ?? 0) / 10), 
      Math.floor((anchorAttrs.anchor_OD ?? anchorAttrs.OD ?? 0) / 10),
      Math.floor((anchorAttrs.anchor_PS ?? anchorAttrs.PS ?? 0) / 10), 
      Math.floor((anchorAttrs.anchor_BH ?? anchorAttrs.BH ?? 0) / 10), 
      Math.floor((anchorAttrs.anchor_RB ?? anchorAttrs.RB ?? 0) / 10), 
      Math.floor((anchorAttrs.anchor_ST ?? anchorAttrs.ST ?? 0) / 10),
      Math.floor((anchorAttrs.anchor_AG ?? anchorAttrs.AG ?? 0) / 10), 
      Math.floor((anchorAttrs.anchor_ND ?? anchorAttrs.ND ?? 0) / 10), 
      Math.floor((anchorAttrs.anchor_IQ ?? anchorAttrs.IQ ?? 0) / 10), 
      Math.floor((anchorAttrs.anchor_FT ?? anchorAttrs.FT ?? 0) / 10),
      Math.round((anchorAttrs.NG ?? 1.0) * 100),  // NG as percentage
      rt
    ];
    const classes = ['', '', 'ht', 'wt', '', '', '', '', '', '', '', '', '', '', '', '', 'ng', 'rt'];
    
    const ng = anchorAttrs.NG ?? 1.0;
    let energyBgColor;
    if (ng > 0.89) energyBgColor = '#00aa00';      // Green
    else if (ng >= 0.8) energyBgColor = '#cccc00'; // Yellow
    else if (ng >= 0.7) energyBgColor = '#ff8800'; // Orange
    else energyBgColor = '#cc0000';                // Red
    
    cells.forEach((val, idx) => {
      const td = document.createElement('td');
      
      // Make player name a clickable link
      if (idx === 0) {  // First cell is player name
        const link = document.createElement('a');
        link.href = `/static/player-detail.html?id=${p._id}`;
        link.textContent = val ?? '--';
        link.style.color = ng <= 0.89 ? '#fff' : 'inherit';
        link.style.textDecoration = 'none';
        link.style.fontWeight = ng <= 0.89 ? 'bold' : 'normal';
        link.addEventListener('mouseenter', () => {
          link.style.textDecoration = 'underline';
        });
        link.addEventListener('mouseleave', () => {
          link.style.textDecoration = 'none';
        });
        td.appendChild(link);
        
        // Apply energy-based background color to player name cell (except green)
        if (ng <= 0.89) {
          td.style.backgroundColor = energyBgColor;
        }
      } else {
      td.textContent = val ?? '--';
      }
      
      if (classes[idx]) td.classList.add(classes[idx]);
      
      // Apply energy-based background color to NG cell
      if (classes[idx] === 'ng') {
        td.style.backgroundColor = energyBgColor;
        td.style.color = '#fff';  // White text on colored background
        td.style.fontWeight = 'bold';
        td.textContent = `${val}%`;  // Add % symbol
      }
      
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
}

function updatePlayButton() {
  const playBtn = document.getElementById('play-now');
  const gameplanBtn = document.getElementById('gameplan-optional');
  
  const filled = ['PG','SG','SF','PF','C'].every(pos => lineup[pos]);
  
  if (filled) {
    // Enable play button when lineup is complete
    if (playBtn) {
      playBtn.classList.remove('disabled');
      playBtn.style.cursor = 'pointer';
    }
  } else {
    // Disable play button when lineup is incomplete
    if (playBtn) {
      playBtn.classList.add('disabled');
      playBtn.style.cursor = 'not-allowed';
    }
  }
  
  // Game Plan button is ALWAYS enabled (user can go to Game Plan anytime)
  if (gameplanBtn) {
    gameplanBtn.classList.remove('disabled');
    gameplanBtn.style.cursor = 'pointer';
    gameplanBtn.removeAttribute('disabled');
  }
}

function autosetLineup() {
  // Clear current lineup
  document.querySelectorAll('.slot').forEach(slot => clearSlot(slot));
  
  // Randomize position order
  const positions = ['PG', 'SG', 'SF', 'PF', 'C'];
  const shuffledPositions = positions.sort(() => Math.random() - 0.5);
  
  // Track which players have been assigned
  const assignedPlayers = new Set();
  
  // For each position in random order
  shuffledPositions.forEach(pos => {
    // Get available players (not already assigned AND NG >= 0.8 AND not ineligible)
    const availablePlayers = roster.filter(p => {
      const ng = p.NG ?? p.attributes?.NG ?? 1.0;
      const isIneligible = p.ineligible || p.fouled_out;
      return !assignedPlayers.has(p._id) && ng >= 0.8 && !isIneligible;
    });
    
    // Get players with ratings for this position, sorted by rating desc
    const playersWithRating = availablePlayers
      .map(p => ({
        player: p,
        rating: p.position_ratings?.[pos] ?? -Infinity
      }))
      .filter(({ rating }) => rating !== -Infinity)
      .sort((a, b) => b.rating - a.rating);
    
    // Take top 3 (or all if fewer than 3)
    const topCandidates = playersWithRating.slice(0, 3);
    
    // Randomly pick one from top candidates
    if (topCandidates.length > 0) {
      const randomIndex = Math.floor(Math.random() * topCandidates.length);
      const { player } = topCandidates[randomIndex];
      
      // Assign to lineup
      lineup[pos] = player._id;
      assignedPlayers.add(player._id);
    }
  });
  
  // Update all slot displays with correct position ratings
  updateAllSlotDisplays();
  updatePlayButton();
  // Re-attach event listeners after DOM update
  setupSlotDragAndDrop();
  showToast('Lineup auto-generated!');
}

function updateSlotDisplay(slot) {
  const pos = slot.dataset.pos;
  const playerId = lineup[pos];
  const remove = slot.querySelector('.remove');
  const slotContent = slot.querySelector('.slot-content');
  
  if (playerId && playerMap[playerId]) {
    const player = playerMap[playerId];
    const rating = player.position_ratings?.[pos] ?? '--';
    
    // Get energy (same pattern as energy - check attributes first, then fallback)
    const energy = player.attributes?.NG ?? player.NG ?? 1.0;
    const energyPercent = Math.round(energy * 100);
    
    // Get stats - handle both flat (game stats) and nested (season stats) structures
    // Game stats are already flattened at loadRoster line 211: rosterPlayer.stats = gp.stats?.game || gp.stats || {}
    // Initial roster stats are nested: stats.season.PTS (from API line 1317)
    const rawStats = player.stats || {};
    const stats = rawStats.game || rawStats.season || rawStats || {};
    
    // Get all stats with fallbacks (same pattern as energy)
    const points = stats.PTS || 0;
    const rebounds = (stats.OREB || 0) + (stats.DREB || 0) + (stats.REB || 0);
    const assists = stats.AST || 0;
    const defA = stats.DEF_A || 0;
    const defS = stats.DEF_S || 0;
    const defPct = defA > 0 ? Math.round((defS / defA) * 100) : 0;
    const fouls = stats.F || 0;
    
    // Get emotion (EM) - same pattern as energy: check attributes first, then fallback
    const em = player.attributes?.EM ?? player.EM ?? 50;
    let emoji = '😐'; // Default straight face
    if (em >= 80) emoji = '😎';        // Sunglasses
    else if (em >= 60) emoji = '😊';   // Big smile
    else if (em >= 40) emoji = '😐';   // Straight face
    else if (em >= 20) emoji = '😕';   // Slight frown
    else emoji = '😞';                 // Sad face
    
    // Get momentum (MO) - same pattern as energy: check attributes first, then fallback
    const momentum = player.attributes?.MO ?? player.MO ?? 0;
    const moValue = typeof momentum === 'number' ? momentum : 0;
    
    // Determine energy color class
    let energyClass = 'high';
    if (energyPercent < 25) energyClass = 'critical';
    else if (energyPercent < 50) energyClass = 'low';
    else if (energyPercent < 75) energyClass = 'medium';
    
    // Calculate momentum bar widths
    let leftWidth = '0%';
    let rightWidth = '0%';
    if (moValue < 0) {
      // Negative momentum: fill left side with red
      const fillPercent = Math.min(100, Math.abs(moValue) / 10 * 100); // -10 = 100%, -5 = 50%
      leftWidth = `${fillPercent}%`;
    } else if (moValue > 0) {
      // Positive momentum: fill right side with green
      const fillPercent = Math.min(100, moValue / 10 * 100); // +10 = 100%, +5 = 50%
      rightWidth = `${fillPercent}%`;
    }
    
    // Build slot content HTML
    slotContent.innerHTML = `
      <div class="player-image-container">
        <img class="player-image" src="/static/images/players/${playerId}.png" 
             onerror="this.src='/static/images/players/default.png'" alt="${player.name}">
      </div>
      <div class="player-name">${player.name}</div>
      <div class="player-rating">${rating}</div>
      <div class="player-points">${points}</div>
      <div class="player-rebounds">${rebounds}</div>
      <div class="player-assists">${assists}</div>
      <div class="player-def-pct">${defPct}%</div>
      <div class="player-emotion">${emoji}</div>
      <div class="player-momentum">
        <div class="momentum-bar-container">
          <div class="momentum-bar-left" style="width: ${leftWidth}"></div>
          <div class="momentum-bar-center"></div>
          <div class="momentum-bar-right" style="width: ${rightWidth}"></div>
        </div>
      </div>
      <div class="player-fouls">${fouls}</div>
      <div class="player-energy ${energyClass}">${energyPercent}%</div>
    `;
    
    slotContent.classList.remove('empty');
    
    // Show remove button
    if (remove) {
      remove.hidden = false;
    }
    
    slot.classList.add('filled');
    slot.draggable = true;
    slot.setAttribute('draggable', 'true');
  } else {
    // Empty slot
    slotContent.innerHTML = '';
    slotContent.classList.add('empty');
    
    if (remove) {
      remove.hidden = true;
    }
    
    slot.classList.remove('filled');
    slot.draggable = false;
    slot.setAttribute('draggable', 'false');
  }
}

function updateAllSlotDisplays() {
  document.querySelectorAll('.slot').forEach(slot => {
    updateSlotDisplay(slot);
  });
}

function clearSlot(slot) {
  const pos = slot.dataset.pos;
  delete lineup[pos];
  updateSlotDisplay(slot);
  updatePlayButton();
  
  // Re-render views to update selection state
  if (currentView === 'player') {
    renderPlayerView();
  } else {
    renderRoster();
  }
}

function setupSlots() {
  document.querySelectorAll('.slot').forEach(slot => {
    clearSlot(slot);
  });
  
  const slotsContainer = document.getElementById('slots');
  if (!slotsContainer) return;

  // Delegated dragstart on container
  slotsContainer.addEventListener('dragstart', (e) => {
    const slot = e.target.closest('.slot');
    if (!slot) return;
    const pos = slot.dataset.pos;
    const playerId = lineup[pos];
    if (playerId) {
      console.log('[DND] dragstart', { pos, playerId });
      dndLog('[DND] dragstart', { pos, playerId });
      e.dataTransfer.setData('text/plain', playerId);
      e.dataTransfer.setData('application/x-slot-pos', pos);
      e.dataTransfer.effectAllowed = 'move';
    } else {
      e.preventDefault();
    }
  });

  // Allow drops on slots
  slotsContainer.addEventListener('dragover', (e) => {
    if (e.target.closest('.slot')) {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
    }
  });

  slotsContainer.addEventListener('drop', (e) => {
    const slot = e.target.closest('.slot');
    if (!slot) return;
    e.preventDefault();

    const draggedPlayerId = e.dataTransfer.getData('text/plain');
    const dropPos = slot.dataset.pos;
    console.log('[DND] drop start', { draggedPlayerId, dropPos, lineup: { ...lineup } });
    dndLog('[DND] drop start', { draggedPlayerId, dropPos, lineup: { ...lineup } });
    if (!draggedPlayerId) return;

    // Infer source slot from lineup
    let sourcePos = null;
    for (const [p, id] of Object.entries(lineup)) {
      if (id === draggedPlayerId) { sourcePos = p; break; }
    }

    const existingAtDrop = lineup[dropPos] || null;
    console.log('[DND] resolved', { sourcePos, existingAtDrop });
    dndLog('[DND] resolved', { sourcePos, existingAtDrop });

    // Swap/move logic
    if (sourcePos && existingAtDrop) {
      lineup[sourcePos] = existingAtDrop;
    } else if (sourcePos && !existingAtDrop) {
      delete lineup[sourcePos];
    } else if (!sourcePos) {
      // Ensure uniqueness if dragged from roster
      for (const p of Object.keys(lineup)) {
        if (lineup[p] === draggedPlayerId) delete lineup[p];
      }
    }

    lineup[dropPos] = draggedPlayerId;
    console.log('[DND] drop end', { lineup: { ...lineup } });
    dndLog('[DND] drop end', { lineup: { ...lineup } });

    updateAllSlotDisplays();
    updatePlayButton();

    if (currentView === 'player') {
      renderPlayerView();
    } else {
      renderRoster();
    }
  });
}

function resolveTeam() {
  if (myTeamSide === 'home' || myTeamSide === 'away') {
    teamName = myTeamSide === 'away' ? awayTeam : homeTeam;
    return !!teamName;
  }
  const storedId = userTeamIdParam || localStorage.getItem('userTeamId') || localStorage.getItem('franchise_user_team');
  if (storedId) {
    if (storedId === homeId || storedId === homeTeam) {
      myTeamSide = 'home';
      teamName = homeTeam;
      return true;
    }
    if (storedId === awayId || storedId === awayTeam) {
      myTeamSide = 'away';
      teamName = awayTeam;
      return true;
    }
  }
  return false;
}

async function setHeader() {
  const title = document.getElementById('team-title');
  if (!title) {
    console.warn('[setHeader] team-title element not found');
    return;
  }
  
  // Determine user team and opponent team
  const userTeamName = teamName;
  const opponentTeamName = myTeamSide === 'home' ? awayTeam : homeTeam;
  
  console.log('[setHeader] Setting header:', { userTeamName, opponentTeamName, gameId });
  
  // Get scores from game data (default to 0)
  let userTeamScore = 0;
  let opponentTeamScore = 0;
  
  if (gameId) {
    try {
      const gameRes = await fetch(`/api/game/${gameId}?quarter=1`);
      if (gameRes.ok) {
        const gameData = await gameRes.json();
        const score = gameData.score || {};
        userTeamScore = score[userTeamName] || 0;
        opponentTeamScore = score[opponentTeamName] || 0;
        console.log('[setHeader] Fetched scores:', { userTeamScore, opponentTeamScore, score });
      } else {
        console.warn('[setHeader] Failed to fetch game data:', gameRes.status);
      }
    } catch (err) {
      console.warn("[setHeader] Could not fetch game scores for header:", err);
    }
  } else {
    console.log('[setHeader] No gameId, using default scores (0)');
  }
  
  // Update header format: "Set Your Lineup -- User Team Name: User Team Score -- Opponent Team Name: Opponent Team Score"
  const headerText = `Set Your Lineup — ${userTeamName}: ${userTeamScore} — ${opponentTeamName}: ${opponentTeamScore}`;
  title.textContent = headerText;
  console.log('[setHeader] Header updated to:', headerText);
  
  const logo = document.getElementById('team-logo');
  if (logo) {
    logo.src = `/static/images/homepage-logos/${teamName}.png`;
    logo.alt = `${teamName} logo`;
    logo.hidden = false;
    logo.onerror = () => { logo.hidden = true; };
  }
}

function restoreLineupFromUrl() {
  // Restore lineup from URL parameters if present
  // Ensure myTeamSide is set (should be set by resolveTeam() before this is called)
  if (!myTeamSide) {
    console.warn('[restoreLineupFromUrl] myTeamSide not set, cannot restore lineup');
    return;
  }
  
  const positions = ['PG', 'SG', 'SF', 'PF', 'C'];
  let restoredCount = 0;
  positions.forEach(pos => {
    const paramKey = `${myTeamSide}_${pos.toLowerCase()}`;
    const playerId = urlParams.get(paramKey);
    if (playerId) {
      lineup[pos] = playerId;
      restoredCount++;
      console.log(`[restoreLineupFromUrl] Restored ${pos}: ${playerId}`);
    }
  });
  console.log(`[restoreLineupFromUrl] Restored ${restoredCount} players from URL`);
}

async function init() {
  if (!resolveTeam()) {
    alert("Can't determine your team for this game. Please return and relaunch.");
    const btn = document.getElementById('play-now');
    if (btn) btn.classList.add('disabled');
    return;
  }
  
  await setHeader();
  await loadRoster();
  setupSlots(); // Setup slot event handlers (this clears slots/lineup)
  
  // Restore lineup from URL AFTER setupSlots (which clears the lineup)
  restoreLineupFromUrl();
  
  updateAllSlotDisplays(); // Display restored lineup in slots
  updatePlayButton(); // Update play button state based on restored lineup
  
  // Wire up autoset button
  const autosetBtn = document.getElementById('autoset-lineup');
  if (autosetBtn) {
    autosetBtn.addEventListener('click', autosetLineup);
  }
  
  const btn = document.getElementById('play-now');
  if (btn) {
    btn.addEventListener('click', () => {
      if (btn.classList.contains('disabled')) return;
      const currentGameId = urlParams.get('game_id') ||
        (typeof localStorage !== 'undefined' ? localStorage.getItem('game_id') : null);
      const params = new URLSearchParams();
      params.set('home', homeTeam);
      params.set('away', awayTeam);
      if (homeId) params.set('home_id', homeId);
      if (awayId) params.set('away_id', awayId);
      if (myTeamSide) params.set('my_team', myTeamSide);
      if (userTeamIdParam) params.set('user_team_id', userTeamIdParam);
      if (franchiseId) params.set('franchise_id', franchiseId);
      if (weekParam) params.set('week', weekParam);
      if (tournamentId) params.set('tournament_id', tournamentId);
      if (modeParam) params.set('mode', modeParam);
      params.set('quarter', String(quarter));
      params.set('period', periodLabel);
      if (quarter > 1 && currentGameId) params.set('game_id', currentGameId);
      
      // ✅ Preserve clock time if present (from foul out navigation)
      const clock = urlParams.get('clock');
      if (clock) params.set('clock', clock);
      
      ['PG','SG','SF','PF','C'].forEach(pos => {
        const id = lineup[pos];
        if (id) params.set(`${myTeamSide}_${pos.toLowerCase()}`, id);
      });
      
      // Carry forward start_with_inbound and starting_possession if present (from Sim to 4th Quarter)
      const startWithInbound = urlParams.get('start_with_inbound');
      const startingPossession = urlParams.get('starting_possession');
      if (startWithInbound) params.set('start_with_inbound', startWithInbound);
      if (startingPossession) params.set('starting_possession', startingPossession);
      
      if (DEBUG) {
        params.set('debug', '1');
        // optional: params.set('debug_flow', '1');
      }
      if (DEBUG) {
        console.debug('🔀 Redirecting to court.html (bypassing game plan)', { home: homeTeam, away: awayTeam, gameId: currentGameId });
      }
      DEBUG && console.log('[lineup] launching quarter', quarter);
      window.location.href = `/court.html?${params.toString()}`;
    });
  }
  
  // NEW: Optional Game Plan button (always enabled)
  const gameplanBtn = document.getElementById('gameplan-optional');
  console.log('🔍 Game Plan button found:', gameplanBtn);
  if (gameplanBtn) {
    gameplanBtn.addEventListener('click', () => {
      console.log('🎮 GAME PLAN BUTTON CLICKED! Redirecting to game-plan.html');
      const currentGameId = urlParams.get('game_id') ||
        (typeof localStorage !== 'undefined' ? localStorage.getItem('game_id') : null);
      const params = new URLSearchParams();
      params.set('home', homeTeam);
      params.set('away', awayTeam);
      if (homeId) params.set('home_id', homeId);
      if (awayId) params.set('away_id', awayId);
      if (myTeamSide) params.set('my_team', myTeamSide);
      if (userTeamIdParam) params.set('user_team_id', userTeamIdParam);
      if (franchiseId) params.set('franchise_id', franchiseId);
      if (weekParam) params.set('week', weekParam);
      if (tournamentId) params.set('tournament_id', tournamentId);
      if (modeParam) params.set('mode', modeParam);
      params.set('quarter', String(quarter));
      params.set('period', periodLabel);
      if (quarter > 1 && currentGameId) params.set('game_id', currentGameId);
      ['PG','SG','SF','PF','C'].forEach(pos => {
        const id = lineup[pos];
        if (id) params.set(`${myTeamSide}_${pos.toLowerCase()}`, id);
      });
      
      // Carry forward start_with_inbound and starting_possession if present
      const startWithInbound = urlParams.get('start_with_inbound');
      const startingPossession = urlParams.get('starting_possession');
      if (startWithInbound) params.set('start_with_inbound', startWithInbound);
      if (startingPossession) params.set('starting_possession', startingPossession);

      if (DEBUG) {
        params.set('debug', '1');
      }
      
      // Add "from=lineup" so Game Plan screen knows where user came from
      params.set('from', 'lineup');
      
      if (DEBUG) {
        console.debug('🔀 Redirecting to game-plan.html', { home: homeTeam, away: awayTeam, gameId: currentGameId });
      }
      window.location.href = `/game-plan.html?${params.toString()}`;
    });
  }

  // BOX SCORE button: go to current game's box score if available
  const boxBtn = document.getElementById('box-score-button');
  if (boxBtn) {
    boxBtn.addEventListener('click', () => {
      const currentGameId =
        urlParams.get('game_id') ||
        (typeof localStorage !== 'undefined' ? localStorage.getItem('game_id') : null);

      const params = new URLSearchParams();

      // Always pass game context so Box Score can route back to lineup if needed
      if (homeTeam) params.set('home', homeTeam);
      if (awayTeam) params.set('away', awayTeam);
      if (homeId) params.set('home_id', homeId);
      if (awayId) params.set('away_id', awayId);
      if (myTeamSide) params.set('my_team', myTeamSide);
      if (userTeamIdParam) params.set('user_team_id', userTeamIdParam);
      if (franchiseId) params.set('franchise_id', franchiseId);
      if (weekParam) params.set('week', weekParam);
      if (tournamentId) params.set('tournament_id', tournamentId);
      if (modeParam) params.set('mode', modeParam);
      params.set('quarter', String(quarter));
      params.set('period', periodLabel);

      // Carry forward inbound/possession flags if present
      const startWithInbound = urlParams.get('start_with_inbound');
      const startingPossession = urlParams.get('starting_possession');
      if (startWithInbound) params.set('start_with_inbound', startWithInbound);
      if (startingPossession) params.set('starting_possession', startingPossession);
      
      // Pass lineup params to preserve lineup when navigating back
      ['PG','SG','SF','PF','C'].forEach(pos => {
        const id = lineup[pos];
        if (id) params.set(`${myTeamSide}_${pos.toLowerCase()}`, id);
      });

      // If we have an active game, include it so Box Score shows live stats
      if (currentGameId) {
        params.set('game_id', currentGameId);
      } else {
        // Pre-game: let Box Score know to render zeroed stats
        params.set('pregame', '1');
      }

      // Mark that navigation originated from lineup so Box Score can \"Back\" here
      params.set('from', 'lineup');

      window.location.href = `/static/box-score.html?${params.toString()}`;
    });
  }
}

// ========== PLAYER VIEW IMPLEMENTATION ==========

let currentView = 'grid'; // 'grid' or 'player'
const cardFlipState = {}; // Track flip state per player ID
const dropdownState = {}; // Track dropdown open state per player ID

// Attribute groupings for card back
const ATTR_GROUPS = {
  'OFFENSE': ['SC', 'SH'],
  'DEFENSE': ['ID', 'OD'],
  'SKILLS': ['PS', 'BH'],
  'DIRTY WORK': ['RB', 'ST'],
  'PHYSICAL': ['AG', 'ND'],
  'MIND': ['IQ', 'FT']
};

function initViewToggle() {
  // Restore saved view from sessionStorage
  const savedView = sessionStorage.getItem('lineupView');
  if (savedView === 'player') {
    currentView = 'player';
  }
  
  const toggleBtns = document.querySelectorAll('.view-toggle-btn');
  toggleBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const view = btn.dataset.view;
      switchView(view);
    });
    
    // Set active state based on current view
    if (btn.dataset.view === currentView) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });
  
  // Initialize view
  switchView(currentView);
}

function switchView(view) {
  currentView = view;
  sessionStorage.setItem('lineupView', view);
  
  // Update toggle buttons
  document.querySelectorAll('.view-toggle-btn').forEach(btn => {
    if (btn.dataset.view === view) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });
  
  // Show/hide view containers
  const gridContainer = document.getElementById('roster-table-container');
  const playerContainer = document.getElementById('player-view-container');
  
  if (view === 'grid') {
    gridContainer?.classList.add('active');
    playerContainer?.classList.remove('active');
  } else {
    gridContainer?.classList.remove('active');
    playerContainer?.classList.add('active');
    renderPlayerView();
  }
}

function renderPlayerView() {
  const container = document.querySelector('.players-grid');
  if (!container) return;
  
  container.innerHTML = '';
  
  // Sort players by their HIGHEST position rating
  const sortedPlayers = roster
    .map(p => {
      const posRatings = p.position_ratings || {};
      const entries = Object.entries(posRatings);
      
      let highestPos = null;
      let highestRating = -1;
      
      if (entries.length > 0) {
        const sorted = entries.sort((a, b) => b[1] - a[1]);
        highestPos = sorted[0][0];
        highestRating = sorted[0][1];
      }
      
      return { 
        ...p, 
        highestPos,
        highestRating 
      };
    })
    .sort((a, b) => {
      // Sort by highest rating desc
      if (b.highestRating !== a.highestRating) return b.highestRating - a.highestRating;
      // Then by name asc
      return (a.name || '').localeCompare(b.name || '');
    });
  
  sortedPlayers.forEach(player => {
    const card = createPlayerCard(player);
    container.appendChild(card);
  });
}

function createPlayerCard(player) {
  const card = document.createElement('div');
  
  // Add ineligible styling for fouled-out players
  if (player.ineligible || player.fouled_out) {
    card.classList.add('ineligible');
    card.style.opacity = '0.5';
    card.style.pointerEvents = 'none';
    card.style.cursor = 'not-allowed';
  }
  card.className = 'player-card';
  card.dataset.playerId = player._id;
  
  // Check if selected
  const isSelected = Object.values(lineup).includes(player._id);
  if (isSelected) {
    card.classList.add('selected');
  }
  
  // Make draggable (only if not ineligible)
  card.draggable = !isSelected && !player.ineligible && !player.fouled_out;
  if (card.draggable) {
    card.addEventListener('dragstart', (e) => {
      e.dataTransfer.setData('text/plain', player._id);
    });
  }
  
  // Click to fill next slot (only if not ineligible)
  if (!player.ineligible && !player.fouled_out) {
    card.addEventListener('click', (e) => {
      // Don't trigger on flip button, dropdown, or headshot clicks
      if (e.target.closest('.flip-btn') || 
          e.target.closest('.ratings-dropdown') || 
          e.target.closest('.player-headshot-container')) {
        return;
      }
      if (!isSelected) {
        fillNextSlot(player._id);
      }
    });
  }
  
  const inner = document.createElement('div');
  inner.className = 'player-card-inner';
  
  // Front side
  const front = createCardFront(player);
  inner.appendChild(front);
  
  // Back side
  const back = createCardBack(player);
  inner.appendChild(back);
  
  card.appendChild(inner);
  
  return card;
}

function createCardFront(player) {
  const front = document.createElement('div');
  front.className = 'player-card-front';
  
  // Headshot container (clickable link to player detail)
  const headshotLink = document.createElement('a');
  headshotLink.href = `/static/player-detail.html?id=${player._id}`;
  headshotLink.style.display = 'block';
  headshotLink.style.textDecoration = 'none';
  
  const headshotContainer = document.createElement('div');
  headshotContainer.className = 'player-headshot-container';
  
  // Set team background image
  const teamNameNormalized = teamName.toLowerCase().replace(/\s+/g, '-');
  headshotContainer.style.backgroundImage = `url(/static/images/team-backgrounds/${teamNameNormalized}-background.png)`;
  headshotContainer.style.backgroundSize = 'cover';
  headshotContainer.style.backgroundPosition = 'center';
  
  // Add energy-based border
  const ng = player.attributes?.NG ?? 1.0;
  let borderColor;
  if (ng > 0.89) borderColor = '#00aa00';      // Green
  else if (ng >= 0.8) borderColor = '#cccc00'; // Yellow
  else if (ng >= 0.7) borderColor = '#ff8800'; // Orange
  else borderColor = '#cc0000';                // Red
  
  headshotContainer.style.border = `4px solid ${borderColor}`;
  headshotContainer.style.cursor = 'pointer';
  headshotContainer.style.transition = 'transform 0.2s ease';
  
  // Add hover effect
  headshotContainer.addEventListener('mouseenter', () => {
    headshotContainer.style.transform = 'scale(1.05)';
  });
  headshotContainer.addEventListener('mouseleave', () => {
    headshotContainer.style.transform = 'scale(1)';
  });
  
  // Player image
  const img = document.createElement('img');
  img.className = 'player-headshot';
  img.src = player.photo || `/static/images/players/${player._id}.png`;
  img.alt = player.name;
  img.onerror = () => {
    // Fallback to white background if image fails
    img.style.display = 'none';
  };
  headshotContainer.appendChild(img);
  
  // Add ineligible overlay/shade for fouled-out players
  if (player.ineligible || player.fouled_out) {
    headshotContainer.style.position = 'relative';
    
    // Add overlay shade
    const overlay = document.createElement('div');
    overlay.style.position = 'absolute';
    overlay.style.top = '0';
    overlay.style.left = '0';
    overlay.style.right = '0';
    overlay.style.bottom = '0';
    overlay.style.backgroundColor = 'rgba(0, 0, 0, 0.6)';
    overlay.style.zIndex = '10';
    overlay.style.pointerEvents = 'none';
    headshotContainer.appendChild(overlay);
    
    // Add "FOULED OUT" label
    const label = document.createElement('div');
    label.textContent = 'FOULED OUT';
    label.style.position = 'absolute';
    label.style.top = '50%';
    label.style.left = '50%';
    label.style.transform = 'translate(-50%, -50%)';
    label.style.color = '#e74c3c';
    label.style.fontWeight = 'bold';
    label.style.fontSize = '14px';
    label.style.zIndex = '11';
    label.style.pointerEvents = 'none';
    label.style.textShadow = '0 0 4px rgba(0,0,0,0.8)';
    headshotContainer.appendChild(label);
  }
  
  headshotLink.appendChild(headshotContainer);
  front.appendChild(headshotLink);
  
  // Flip button (outside the link so it doesn't navigate)
  const flipBtn = document.createElement('button');
  flipBtn.className = 'flip-btn';
  flipBtn.innerHTML = '🔁';
  flipBtn.setAttribute('aria-label', 'Flip card');
  flipBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    toggleCardFlip(player._id);
  });
  front.appendChild(flipBtn);
  
  // Ratings dropdown (outside the link)
  const dropdown = createRatingsDropdown(player);
  front.appendChild(dropdown);
  
  // Info bar
  const infoBar = document.createElement('div');
  infoBar.className = 'player-info-bar';
  
  // Left side: name and physical stats
  const leftInfo = document.createElement('div');
  leftInfo.className = 'player-info-left';
  
  const name = document.createElement('div');
  name.className = 'player-name';
  name.textContent = player.name;
  leftInfo.appendChild(name);
  
  const physical = document.createElement('div');
  physical.className = 'player-physical';
  physical.textContent = `${formatHeight(player.height)} ${player.weight || '--'} lbs`;
  leftInfo.appendChild(physical);
  
  infoBar.appendChild(leftInfo);
  
  // Right side: energy percentage
  const energyDisplay = document.createElement('div');
  energyDisplay.className = 'player-energy-display';
  const ngPercent = Math.round(ng * 100);
  energyDisplay.textContent = `${ngPercent}%`;
  energyDisplay.style.color = borderColor;  // Match border color
  energyDisplay.style.fontWeight = 'bold';
  energyDisplay.style.fontSize = '18px';
  infoBar.appendChild(energyDisplay);
  
  front.appendChild(infoBar);
  
  return front;
}

function createRatingsDropdown(player) {
  const dropdown = document.createElement('div');
  dropdown.className = 'ratings-dropdown';
  
  const posRatings = player.position_ratings || {};
  const entries = Object.entries(posRatings)
    .sort((a, b) => b[1] - a[1]); // Sort by rating desc
  
  if (entries.length === 0) return dropdown;
  
  // Use player's highest position (already calculated in renderPlayerView)
  const topPos = player.highestPos || entries[0][0];
  const topRating = player.highestRating || entries[0][1];
  
  // Toggle button - shows highest rated position
  const toggle = document.createElement('button');
  toggle.className = 'ratings-dropdown-toggle';
  toggle.innerHTML = `${topPos}: ${topRating} <span style="font-size: 10px;">▼</span>`;
  toggle.addEventListener('click', (e) => {
    e.stopPropagation();
    dropdown.classList.toggle('open');
    dropdownState[player._id] = dropdown.classList.contains('open');
  });
  dropdown.appendChild(toggle);
  
  // List - all positions sorted by rating
  const list = document.createElement('div');
  list.className = 'ratings-dropdown-list';
  
  entries.forEach(([pos, rating]) => {
    const item = document.createElement('div');
    item.className = 'ratings-dropdown-item';
    item.innerHTML = `<span>${pos}</span><span>${rating}</span>`;
    list.appendChild(item);
  });
  
  dropdown.appendChild(list);
  
  return dropdown;
}

function createCardBack(player) {
  const back = document.createElement('div');
  back.className = 'player-card-back';
  
  // Flip button (on back)
  const flipBtn = document.createElement('button');
  flipBtn.className = 'flip-btn';
  flipBtn.innerHTML = '🔁';
  flipBtn.style.position = 'absolute';
  flipBtn.style.top = '8px';
  flipBtn.style.right = '8px';
  flipBtn.setAttribute('aria-label', 'Flip card back');
  flipBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    toggleCardFlip(player._id);
  });
  back.appendChild(flipBtn);
  
  // Attribute sections - use anchor attributes (not energy-scaled)
  const attrs = player.attributes || {};
  
  Object.entries(ATTR_GROUPS).forEach(([sectionName, attrKeys]) => {
    const section = document.createElement('div');
    section.className = 'attr-section';
    
    const title = document.createElement('div');
    title.className = 'attr-section-title';
    title.textContent = sectionName;
    section.appendChild(title);
    
    attrKeys.forEach(key => {
      const row = document.createElement('div');
      row.className = 'attr-row';
      
      const label = document.createElement('span');
      label.className = 'attr-label';
      label.textContent = key;
      row.appendChild(label);
      
      const value = document.createElement('span');
      value.className = 'attr-value';
      // Use anchor attribute (base value, not energy-scaled)
      const rawVal = attrs[`anchor_${key}`] ?? attrs[key];
      const displayVal = rawVal != null ? Math.floor(rawVal / 10) : '--';
      value.textContent = displayVal;
      
      // Set gold bar fill percentage (0-10 scale, max at 100%)
      if (displayVal !== '--') {
        const fillPercentage = Math.min(displayVal * 10, 100);
        row.style.setProperty('--attr-fill', `${fillPercentage}%`);
      }
      
      row.appendChild(value);
      
      section.appendChild(row);
    });
    
    back.appendChild(section);
  });
  
  // Add NG (Energy) section at the end
  const ngSection = document.createElement('div');
  ngSection.className = 'attr-section';
  
  const ngTitle = document.createElement('div');
  ngTitle.className = 'attr-section-title';
  ngTitle.textContent = 'ENERGY';
  ngSection.appendChild(ngTitle);
  
  const ngRow = document.createElement('div');
  ngRow.className = 'attr-row';
  
  const ngLabel = document.createElement('span');
  ngLabel.className = 'attr-label';
  ngLabel.textContent = 'NG';
  ngRow.appendChild(ngLabel);
  
  const ngValue = document.createElement('span');
  ngValue.className = 'attr-value';
  const ng = attrs.NG ?? 1.0;
  const ngPercent = Math.round(ng * 100);
  ngValue.textContent = `${ngPercent}%`;
  
  // Set energy-based background color
  let bgColor;
  if (ng > 0.89) bgColor = '#00aa00';      // Green
  else if (ng >= 0.8) bgColor = '#cccc00'; // Yellow
  else if (ng >= 0.7) bgColor = '#ff8800'; // Orange
  else bgColor = '#cc0000';                // Red
  
  ngRow.style.backgroundColor = bgColor;
  ngValue.style.color = '#fff';  // White text on colored background
  ngLabel.style.color = '#fff';  // White label too
  ngValue.style.fontWeight = 'bold';
  
  // No gold bar for NG row - it has full colored background
  ngRow.style.setProperty('--attr-fill', '0%');
  
  ngRow.appendChild(ngValue);
  ngSection.appendChild(ngRow);
  back.appendChild(ngSection);
  
  return back;
}

function toggleCardFlip(playerId) {
  const card = document.querySelector(`.player-card[data-player-id="${playerId}"]`);
  if (!card) return;
  
  card.classList.toggle('flipped');
  cardFlipState[playerId] = card.classList.contains('flipped');
}

function assignToSlot(pos, playerId) {
  // Check if slot is already filled
  if (lineup[pos]) {
    showToast('Slot already filled');
    return false;
  }
  
  // Check if player is already in lineup
  if (Object.values(lineup).includes(playerId)) {
    showToast('Player already in lineup');
    return false;
  }
  
  const player = playerMap[playerId];
  if (!player) return false;
  
  // Check if player is ineligible (fouled out)
  if (player.ineligible || player.fouled_out) {
    showToast(`${player.name} has fouled out and cannot play`);
    return false;
  }
  
  // Update lineup data
  lineup[pos] = playerId;
  
  // Update all slot displays to ensure position ratings are shown correctly
  updateAllSlotDisplays();
  
  updatePlayButton();
  
  // Re-attach event listeners after DOM update
  setupSlotDragAndDrop();
  
  // Re-render views to update selection state
  if (currentView === 'player') {
    renderPlayerView();
  } else {
    renderRoster();
  }
  
  return true;
}

function fillNextSlot(playerId) {
  const player = playerMap[playerId];
  
  // Check if player is ineligible (fouled out)
  if (player && (player.ineligible || player.fouled_out)) {
    showToast(`${player.name} has fouled out and cannot play`);
    return;
  }
  
  const positions = ['PG', 'SG', 'SF', 'PF', 'C'];
  
  for (const pos of positions) {
    if (!lineup[pos]) {
      const success = assignToSlot(pos, playerId);
      if (success) return;
    }
  }
  
  showToast('All positions filled');
}

// Update renderRoster to mark selected rows
const originalRenderRoster = renderRoster;
renderRoster = function() {
  originalRenderRoster();
  
  // Mark selected rows
  const selectedIds = Object.values(lineup);
  roster.forEach(p => {
    const row = document.querySelector(`tr[data-player-id="${p._id}"]`);
    if (row) {
      if (selectedIds.includes(p._id)) {
        row.classList.add('selected');
      } else {
        row.classList.remove('selected');
      }
      
      // Add click handler to fill next slot (only if not ineligible)
      if (!p.ineligible) {
        row.addEventListener('click', (e) => {
          if (!selectedIds.includes(p._id)) {
            fillNextSlot(p._id);
          }
        });
      } else {
        // Mark ineligible rows
        row.classList.add('ineligible');
        row.style.opacity = '0.5';
        row.style.pointerEvents = 'none';
      }
    }
  });
};

// Make slots draggable for swapping
function setupSlotDragAndDrop() {
  const slots = document.querySelectorAll('.slot');
  
  slots.forEach(slot => {
    const pos = slot.dataset.pos;
    // Ensure draggable state reflects whether slot is filled
    const filled = !!lineup[pos];
    slot.draggable = filled;
    slot.setAttribute('draggable', filled ? 'true' : 'false');

    // Wire up remove button click event
    const removeBtn = slot.querySelector('.remove');
    if (removeBtn) {
      // Remove any existing listeners to prevent duplicates
      const newRemoveBtn = removeBtn.cloneNode(true);
      removeBtn.parentNode.replaceChild(newRemoveBtn, removeBtn);
      
      newRemoveBtn.addEventListener('click', (e) => {
        e.stopPropagation(); // Prevent slot click from firing
        clearSlot(slot);
      });
    }

    // Provide drag data when dragging a filled slot
    slot.addEventListener('dragstart', (e) => {
      const playerId = lineup[pos];
      if (!playerId) { e.preventDefault(); return; }
      e.dataTransfer.setData('text/plain', playerId);
      e.dataTransfer.effectAllowed = 'move';
    });
    
    slot.addEventListener('dragover', (e) => {
      e.preventDefault();
      slot.classList.add('drag-over');
    });
    
    slot.addEventListener('dragleave', () => {
      slot.classList.remove('drag-over');
    });
    
    slot.addEventListener('drop', (e) => {
      e.preventDefault();
      slot.classList.remove('drag-over');
      
      const draggedId = e.dataTransfer.getData('text/plain');
      const targetPos = pos;
      if (!draggedId) return;
      
      // If slot is filled, swap; else assign
      if (lineup[targetPos]) {
        const currentId = lineup[targetPos];
        const draggedPos = Object.keys(lineup).find(p => lineup[p] === draggedId);
        if (draggedPos) {
          lineup[draggedPos] = currentId;
          lineup[targetPos] = draggedId;
          updateAllSlots();
        } else {
          assignToSlot(targetPos, draggedId);
        }
      } else {
        assignToSlot(targetPos, draggedId);
      }
    });
  });
}

function updateAllSlots() {
  // Use the new updateAllSlotDisplays() function which handles the new HTML structure
  updateAllSlotDisplays();
  updatePlayButton();
  // Re-attach event listeners after DOM update
  setupSlotDragAndDrop();
  if (currentView === 'player') renderPlayerView();
  if (currentView === 'grid') renderRoster();
}

// D&D on-screen debug overlay
const DND_DEBUG = false;
function ensureDndOverlay() {
  if (!DND_DEBUG) return null;
  let box = document.getElementById('dnd-overlay');
  if (!box) {
    box = document.createElement('div');
    box.id = 'dnd-overlay';
    box.style.position = 'fixed';
    box.style.right = '8px';
    box.style.bottom = '8px';
    box.style.width = '360px';
    box.style.maxHeight = '40vh';
    box.style.overflowY = 'auto';
    box.style.background = 'rgba(0,0,0,0.75)';
    box.style.color = '#fff';
    box.style.font = '12px/1.4 Inter, system-ui, sans-serif';
    box.style.padding = '8px';
    box.style.borderRadius = '6px';
    box.style.zIndex = '99999';
    box.style.boxShadow = '0 2px 10px rgba(0,0,0,0.4)';
    const title = document.createElement('div');
    title.textContent = 'D&D Debug';
    title.style.fontWeight = '700';
    title.style.marginBottom = '6px';
    box.appendChild(title);
    const list = document.createElement('div');
    list.id = 'dnd-overlay-list';
    box.appendChild(list);
    document.body.appendChild(box);
  }
  return box;
}
function dndLog(label, data) {
  if (!DND_DEBUG) return;
  const box = ensureDndOverlay();
  if (!box) return;
  const list = document.getElementById('dnd-overlay-list');
  if (!list) return;
  const row = document.createElement('div');
  row.style.whiteSpace = 'pre-wrap';
  row.style.margin = '2px 0';
  const payload = data ? ` ${JSON.stringify(data)}` : '';
  row.textContent = `${label}:${payload}`;
  list.appendChild(row);
  // Keep last 20 entries
  while (list.childNodes.length > 20) list.removeChild(list.firstChild);
}

document.addEventListener('DOMContentLoaded', () => {
  init();
  initViewToggle();
  setupSlotDragAndDrop();
});
