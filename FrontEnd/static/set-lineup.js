const urlParams = new URLSearchParams(window.location.search);
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
const isNewMatchup = !urlParams.get('game_id') || storedHome !== homeTeam || storedAway !== awayTeam;
if (isNewMatchup) {
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
    tr.draggable = true;
    tr.dataset.playerId = p._id;
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
    const cells = [
      p.name,
      bestPos,
      formatHeight(p.height),
      p.weight ?? '--',
      p.attributes.SC, p.attributes.SH, p.attributes.ID, p.attributes.OD,
      p.attributes.PS, p.attributes.BH, p.attributes.RB, p.attributes.ST,
      p.attributes.AG, p.attributes.ND, p.attributes.IQ, p.attributes.FT,
      p.attributes.NG, rt
    ];
    const classes = ['', '', 'ht', 'wt', '', '', '', '', '', '', '', '', '', '', '', '', '', 'rt'];
    cells.forEach((val, idx) => {
      const td = document.createElement('td');
      td.textContent = val ?? '--';
      if (classes[idx]) td.classList.add(classes[idx]);
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
}

function updatePlayButton() {
  const btn = document.getElementById('play-now');
  if (!btn) return;
  const filled = ['PG','SG','SF','PF','C'].every(pos => lineup[pos]);
  if (filled) {
    btn.classList.remove('disabled');
  } else {
    btn.classList.add('disabled');
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
    // Get available players (not already assigned)
    const availablePlayers = roster.filter(p => !assignedPlayers.has(p._id));
    
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
      const { player, rating } = topCandidates[randomIndex];
      
      // Assign to lineup
      lineup[pos] = player._id;
      assignedPlayers.add(player._id);
      
      // Update UI
      const slot = document.querySelector(`.slot[data-pos="${pos}"]`);
      if (slot) {
        slot.textContent = `${player.name} — ${rating}`;
        const remove = document.createElement('button');
        remove.className = 'remove';
        remove.textContent = '✕';
        remove.addEventListener('click', () => clearSlot(slot));
        slot.appendChild(remove);
        slot.classList.add('filled');
      }
    }
  });
  
  updatePlayButton();
  showToast('Lineup auto-generated!');
}

function clearSlot(slot) {
  const pos = slot.dataset.pos;
  delete lineup[pos];
  slot.textContent = pos;
  const remove = document.createElement('button');
  remove.className = 'remove';
  remove.textContent = '✕';
  remove.hidden = true;
  slot.appendChild(remove);
  slot.classList.remove('filled');
  remove.addEventListener('click', () => clearSlot(slot));
  updatePlayButton();
}

function setupSlots() {
  document.querySelectorAll('.slot').forEach(slot => {
    clearSlot(slot);
    slot.addEventListener('dragover', e => e.preventDefault());
    slot.addEventListener('drop', e => {
      e.preventDefault();
      const playerId = e.dataTransfer.getData('text/plain');
      const pos = slot.dataset.pos;
      if (lineup[pos]) {
        showToast('Slot already filled');
        return;
      }
      if (Object.values(lineup).includes(playerId)) {
        showToast('Player already used');
        return;
      }
      const player = playerMap[playerId];
      if (!player) return;
      const rating = player.position_ratings?.[pos] ?? '--';
      slot.textContent = `${player.name} — ${rating}`;
      const remove = document.createElement('button');
      remove.className = 'remove';
      remove.textContent = '✕';
      remove.addEventListener('click', () => clearSlot(slot));
      slot.appendChild(remove);
      slot.classList.add('filled');
      lineup[pos] = playerId;
      updatePlayButton();
    });
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

function setHeader() {
  const title = document.getElementById('team-title');
  if (title) {
    const periodText = periodLabel ? ` — ${periodLabel}` : '';
    title.textContent = `Set Your Lineup — ${teamName}${periodText}`;
  }
  const logo = document.getElementById('team-logo');
  if (logo) {
    logo.src = `/static/images/homepage-logos/${teamName}.png`;
    logo.alt = `${teamName} logo`;
    logo.hidden = false;
    logo.onerror = () => { logo.hidden = true; };
  }
}

async function init() {
  if (!resolveTeam()) {
    alert("Can't determine your team for this game. Please return and relaunch.");
    const btn = document.getElementById('play-now');
    if (btn) btn.classList.add('disabled');
    return;
  }
  setHeader();
  await loadRoster();
  setupSlots();
  
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
      ['PG','SG','SF','PF','C'].forEach(pos => {
        const id = lineup[pos];
        if (id) params.set(`${myTeamSide}_${pos.toLowerCase()}`, id);
      });
      if (DEBUG) {
        params.set('debug', '1');
        // optional: params.set('debug_flow', '1');
      }
      if (DEBUG) {
        console.debug('🔀 Redirecting to game-plan.html', { home: homeTeam, away: awayTeam, gameId: currentGameId });
      }
      DEBUG && console.log('[lineup] launching quarter', quarter);
      window.location.href = `/game-plan.html?${params.toString()}`;
    });
  }
}

document.addEventListener('DOMContentLoaded', init);
