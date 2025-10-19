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
      Math.floor((p.attributes.SC ?? 0) / 10), 
      Math.floor((p.attributes.SH ?? 0) / 10), 
      Math.floor((p.attributes.ID ?? 0) / 10), 
      Math.floor((p.attributes.OD ?? 0) / 10),
      Math.floor((p.attributes.PS ?? 0) / 10), 
      Math.floor((p.attributes.BH ?? 0) / 10), 
      Math.floor((p.attributes.RB ?? 0) / 10), 
      Math.floor((p.attributes.ST ?? 0) / 10),
      Math.floor((p.attributes.AG ?? 0) / 10), 
      Math.floor((p.attributes.ND ?? 0) / 10), 
      Math.floor((p.attributes.IQ ?? 0) / 10), 
      Math.floor((p.attributes.FT ?? 0) / 10),
      (p.attributes.NG ?? 0).toFixed(2),  // NG stays as decimal
      rt
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
        console.debug('🔀 Redirecting to game-plan.html', { home: homeTeam, away: awayTeam, gameId: currentGameId });
      }
      DEBUG && console.log('[lineup] launching quarter', quarter);
      window.location.href = `/game-plan.html?${params.toString()}`;
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
  const positions = ['PG', 'SG', 'SF', 'PF', 'C'];
  
  positions.forEach(pos => {
    const container = document.querySelector(`.players-scroll[data-position="${pos}"]`);
    if (!container) return;
    
    container.innerHTML = '';
    
    // Get players for this position, sorted by rating
    const playersForPos = roster
      .map(p => {
        const posRating = (p.position_ratings || {})[pos] || -1;
        const overallRating = getRT(p);
        return { ...p, posRating, overallRating };
      })
      .sort((a, b) => {
        // Sort by position rating desc
        if (b.posRating !== a.posRating) return b.posRating - a.posRating;
        // Then by overall rating desc
        if (b.overallRating !== a.overallRating) return b.overallRating - a.overallRating;
        // Then by name asc
        return (a.name || '').localeCompare(b.name || '');
      });
    
    playersForPos.forEach(player => {
      const card = createPlayerCard(player);
      container.appendChild(card);
    });
  });
}

function createPlayerCard(player) {
  const card = document.createElement('div');
  card.className = 'player-card';
  card.dataset.playerId = player._id;
  
  // Check if selected
  const isSelected = Object.values(lineup).includes(player._id);
  if (isSelected) {
    card.classList.add('selected');
  }
  
  // Make draggable
  card.draggable = !isSelected;
  card.addEventListener('dragstart', (e) => {
    e.dataTransfer.setData('text/plain', player._id);
  });
  
  // Click to fill next slot
  card.addEventListener('click', (e) => {
    // Don't trigger on flip button or dropdown clicks
    if (e.target.closest('.flip-btn') || e.target.closest('.ratings-dropdown')) return;
    if (!isSelected) {
      fillNextSlot(player._id);
    }
  });
  
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
  
  // Headshot container
  const headshotContainer = document.createElement('div');
  headshotContainer.className = 'player-headshot-container';
  
  // Player image
  const img = document.createElement('img');
  img.className = 'player-headshot';
  img.src = player.photo || `/static/images/players/${player._id}.png`;
  img.alt = player.name;
  img.onerror = () => {
    // Fallback to white background if image fails
    img.style.display = 'none';
    headshotContainer.style.background = '#fff';
  };
  headshotContainer.appendChild(img);
  
  // Flip button
  const flipBtn = document.createElement('button');
  flipBtn.className = 'flip-btn';
  flipBtn.innerHTML = '🔁';
  flipBtn.setAttribute('aria-label', 'Flip card');
  flipBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    toggleCardFlip(player._id);
  });
  headshotContainer.appendChild(flipBtn);
  
  // Ratings dropdown
  const dropdown = createRatingsDropdown(player);
  headshotContainer.appendChild(dropdown);
  
  front.appendChild(headshotContainer);
  
  // Info bar
  const infoBar = document.createElement('div');
  infoBar.className = 'player-info-bar';
  
  const name = document.createElement('div');
  name.className = 'player-name';
  name.textContent = player.name;
  infoBar.appendChild(name);
  
  const physical = document.createElement('div');
  physical.className = 'player-physical';
  physical.textContent = `${formatHeight(player.height)} ${player.weight || '--'} lbs`;
  infoBar.appendChild(physical);
  
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
  
  const [topPos, topRating] = entries[0];
  
  // Toggle button
  const toggle = document.createElement('button');
  toggle.className = 'ratings-dropdown-toggle';
  toggle.innerHTML = `${topPos}: ${topRating} <span style="font-size: 10px;">▼</span>`;
  toggle.addEventListener('click', (e) => {
    e.stopPropagation();
    dropdown.classList.toggle('open');
    dropdownState[player._id] = dropdown.classList.contains('open');
  });
  dropdown.appendChild(toggle);
  
  // List
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
  
  // Attribute sections
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
      const rawVal = attrs[key];
      value.textContent = rawVal != null ? Math.floor(rawVal / 10) : '--';
      row.appendChild(value);
      
      section.appendChild(row);
    });
    
    back.appendChild(section);
  });
  
  return back;
}

function toggleCardFlip(playerId) {
  const card = document.querySelector(`.player-card[data-player-id="${playerId}"]`);
  if (!card) return;
  
  card.classList.toggle('flipped');
  cardFlipState[playerId] = card.classList.contains('flipped');
}

function fillNextSlot(playerId) {
  const positions = ['PG', 'SG', 'SF', 'PF', 'C'];
  
  for (const pos of positions) {
    if (!lineup[pos]) {
      assignToSlot(pos, playerId);
      return;
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
      
      // Add click handler to fill next slot
      row.addEventListener('click', (e) => {
        if (!selectedIds.includes(p._id)) {
          fillNextSlot(p._id);
        }
      });
    }
  });
};

// Make slots draggable for swapping
function setupSlotDragAndDrop() {
  const slots = document.querySelectorAll('.slot');
  
  slots.forEach(slot => {
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
      const targetPos = slot.dataset.pos;
      
      // If slot is filled, swap
      if (lineup[targetPos]) {
        const currentId = lineup[targetPos];
        
        // Find position of dragged player
        const draggedPos = Object.keys(lineup).find(pos => lineup[pos] === draggedId);
        
        if (draggedPos) {
          // Swap
          lineup[draggedPos] = currentId;
          lineup[targetPos] = draggedId;
          updateAllSlots();
        } else {
          // New assignment
          assignToSlot(targetPos, draggedId);
        }
      } else {
        assignToSlot(targetPos, draggedId);
      }
    });
    
    // Make filled slots draggable
    const observer = new MutationObserver(() => {
      if (slot.classList.contains('filled')) {
        slot.draggable = true;
        slot.addEventListener('dragstart', (e) => {
          const pos = slot.dataset.pos;
          e.dataTransfer.setData('text/plain', lineup[pos]);
        });
      } else {
        slot.draggable = false;
      }
    });
    
    observer.observe(slot, { attributes: true, attributeFilter: ['class'] });
  });
}

function updateAllSlots() {
  ['PG', 'SG', 'SF', 'PF', 'C'].forEach(pos => {
    const slot = document.querySelector(`.slot[data-pos="${pos}"]`);
    if (!slot) return;
    
    const playerId = lineup[pos];
    if (playerId && playerMap[playerId]) {
      slot.textContent = playerMap[playerId].name;
      slot.classList.add('filled');
      const removeBtn = slot.querySelector('.remove') || document.createElement('button');
      removeBtn.className = 'remove';
      removeBtn.textContent = '✕';
      removeBtn.hidden = false;
      removeBtn.onclick = (e) => {
        e.stopPropagation();
        delete lineup[pos];
        updateAllSlots();
        updatePlayButton();
        if (currentView === 'player') renderPlayerView();
      };
      if (!slot.querySelector('.remove')) slot.appendChild(removeBtn);
    } else {
      slot.textContent = pos;
      slot.classList.remove('filled');
      const removeBtn = slot.querySelector('.remove');
      if (removeBtn) removeBtn.hidden = true;
    }
  });
  
  updatePlayButton();
  if (currentView === 'player') renderPlayerView();
  if (currentView === 'grid') renderRoster();
}

document.addEventListener('DOMContentLoaded', () => {
  init();
  initViewToggle();
  setupSlotDragAndDrop();
});
