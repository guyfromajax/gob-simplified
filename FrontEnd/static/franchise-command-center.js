async function fetchJSON(url) {
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error('Request failed');
    return await res.json();
  } catch (err) {
    console.error('Failed loading', url, err);
    return null;
  }
}

let franchiseId = null;
const userTeamName = localStorage.getItem('franchise_user_team') || '';
const ATTR_HEADERS = ["SC","SH","ID","OD","PS","BH","RB","AG","ST","ND","IQ","FT"];

const teamMap = {
  "Four Corners": "FC",
  "Bentley-Truman": "BT",
  "Lancaster": "Lan",
  "Little York": "LY",
  "Morristown": "Mor",
  "Ocean City": "OC",
  "South Lancaster": "SL",
  "Xavien": "Xav",
};

const teamIdNameMap = {};

function populateTop(data) {
  if (!data) return;
  document.querySelector('.username').textContent = data.username || 'User';
  const formattedTeam = formatTeamName(data.team);
  const logoSrc = `/static/images/homepage-logos/${formattedTeam}.png`;
  document.getElementById('team-logo').src = logoSrc;
  console.log('Team logo URL:', logoSrc);

  const abbr = teamMap[formattedTeam];
  const sammyEl = document.getElementById('coach-sammy');
  const dukeEl = document.getElementById('coach-duke');
  if (abbr) {
    if (sammyEl) {
      sammyEl.src = `/static/images/coaches/${abbr}/Sammy-${abbr}.png`;
      console.log('Coach Sammy URL:', sammyEl.src);
    }
    if (dukeEl) {
      dukeEl.src = `/static/images/coaches/${abbr}/Duke-${abbr}.png`;
      console.log('Coach Duke URL:', dukeEl.src);
    }
  } else {
    if (sammyEl) sammyEl.removeAttribute('src');
    if (dukeEl) dukeEl.removeAttribute('src');
  }

  document.querySelector('.chemistry-bar').textContent = `${data.team_chemistry || 0} / 25`;
  document.getElementById('stat-offense').textContent = `Offense: ${data.offense || '--'}`;
  document.getElementById('stat-defense').textContent = `Defense: ${data.defense || '--'}`;
  document.getElementById('stat-athleticism').textContent = `Athleticism: ${data.athleticism || '--'}`;
  document.getElementById('stat-intangibles').textContent = `Intangibles: ${data.intangibles || '--'}`;
  document.getElementById('stat-prestige').textContent = `Prestige: ${data.prestige || '--'}`;
  document.getElementById('stat-rank').textContent = `Nat'l Rank: ${data.rank || '--'}`;
}

function renderStandings(data) {
  if (!data) return;
  const tbody = document.getElementById('standings-body');
  tbody.innerHTML = '';
  (data.standings || []).forEach(t => {
    teamIdNameMap[t.team_id] = t.name;
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${t.name}</td><td>${t.W}</td><td>${t.L}</td><td>${t.pct.toFixed(3)}</td><td>${t.PF}</td><td>${t.PA}</td><td>${t.next}</td>`;
    tbody.appendChild(tr);
  });
}

function renderLeaders(data) {
  if (!data) return;
  const container = document.getElementById('leaders-container');
  container.innerHTML = '';
  const categories = Object.keys(data);
  categories.forEach(cat => {
    const section = document.createElement('div');
    const h3 = document.createElement('h3');
    h3.textContent = cat;
    section.appendChild(h3);
    const div = document.createElement('div');
    div.className = 'scroll-x';
    const table = document.createElement('table');
    table.className = 'leaders-table';
    table.innerHTML = '<thead><tr><th>Rank</th><th>Player</th><th>Team</th><th>Value</th></tr></thead>';
    const body = document.createElement('tbody');
    (data[cat] || []).forEach((p, idx) => {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${idx + 1}</td><td>${p.name}</td><td>${p.team}</td><td>${p.value}</td>`;
      body.appendChild(tr);
    });
    table.appendChild(body);
    div.appendChild(table);
    section.appendChild(div);
    container.appendChild(section);
  });
}

function renderTeamStats(data) {
  if (!data) return;
  const tbody = document.getElementById('teamstats-body');
  tbody.innerHTML = '';
  data.teams.forEach(t => {
    const tr = document.createElement('tr');
    const s = t.stats || {};
    tr.innerHTML = `<td>${t.team}</td><td>${s.PTS || 0}</td><td>${s.REB || 0}</td><td>${s.AST || 0}</td><td>${s.STL || 0}</td><td>${s.BLK || 0}</td>`;
    tbody.appendChild(tr);
  });
}

function renderRecruits(data) {
  if (!data) return;
  const tbody = document.getElementById('recruits-body');
  tbody.innerHTML = '';
  
  // Process recruits to add position and rating info
  let recruits = (data.recruits || []).map(r => {
    const a = r.attributes || {};
    const ratings = r.position_ratings || {};
    const best = getBestPosition(ratings);
    
    return {
      name: r.name,
      archetype: r.archetype || '--',
      height: formatHeight(r.height),
      weight: r.weight ?? '--',
      pos: best.pos,
      rt: best.rating,
      attributes: a
    };
  });
  
  // Sort by rating (highest to lowest)
  recruits.sort((a, b) => (b.rt ?? -1) - (a.rt ?? -1));
  
  // Render sorted recruits
  recruits.forEach(r => {
    const tr = document.createElement('tr');
    const a = r.attributes;
    
    // Format attributes: 0-9 displays 0, 10-19 displays 1, 20-29 displays 2, etc.
    const formatAttr = (attr) => {
      const value = attr ?? 0;
      return Math.floor(value / 10);
    };
    
    tr.innerHTML = `<td>${r.name}</td><td>${r.archetype}</td><td>${r.height}</td><td>${r.weight}</td><td>${r.pos}</td><td>${formatAttr(a.SC)}</td><td>${formatAttr(a.SH)}</td><td>${formatAttr(a.ID)}</td><td>${formatAttr(a.OD)}</td><td>${formatAttr(a.PS)}</td><td>${formatAttr(a.BH)}</td><td>${formatAttr(a.RB)}</td><td>${formatAttr(a.AG)}</td><td>${formatAttr(a.ST)}</td><td>${formatAttr(a.ND)}</td><td>${formatAttr(a.IQ)}</td><td>${formatAttr(a.FT)}</td><td>${r.rt ?? '-'}</td>`;
    tbody.appendChild(tr);
  });
  
  // Initialize tooltips for table cells
  if (typeof initAttributeTooltips !== 'undefined') {
    initAttributeTooltips(tbody, ['td']);
  }
}

function renderTrainingResults(data) {
  const container = document.getElementById('training-results-container');
  if (!container) return;
  
  if (!data || (!data.player_logs || Object.keys(data.player_logs).length === 0)) {
    container.innerHTML = '<p>No training session completed yet.</p>';
    return;
  }
  
  container.innerHTML = '';
  
  // Add session type header
  const sessionHeader = document.createElement('h4');
  const sessionLabel = data.session_type === 'preseason' ? 'Training Camp' : 'In-Season Training';
  sessionHeader.textContent = sessionLabel + (data.week ? ` (Week ${data.week})` : '');
  sessionHeader.style.marginBottom = '15px';
  container.appendChild(sessionHeader);
  
  // Player Results
  const playerHeader = document.createElement('h5');
  playerHeader.textContent = 'Player Attribute Changes';
  playerHeader.style.marginTop = '10px';
  container.appendChild(playerHeader);
  
  const traitOrder = ['SH','SC','ID','OD','PS','BH','RB','AG','ST','ND','IQ','FT'];
  
  if (data.player_logs && typeof data.player_logs === 'object') {
    Object.entries(data.player_logs).forEach(([name, traits]) => {
      const row = document.createElement('p');
      row.style.marginBottom = '5px';
      const bold = document.createElement('strong');
      bold.textContent = name + ': ';
      row.appendChild(bold);

      const parts = traitOrder.map(attr => {
        const val = Object.hasOwnProperty.call(traits, attr) ? traits[attr] : 0;
        if (val === 0) return null;
        const sign = val > 0 ? '+' : '';
        return `${attr} ${sign}${val}`;
      }).filter(p => p !== null);

      row.appendChild(document.createTextNode(parts.join(', ')));
      container.appendChild(row);
    });
  }
  
  // Team Results
  if (data.team_log && typeof data.team_log === 'object' && Object.keys(data.team_log).length > 0) {
    const teamHeader = document.createElement('h5');
    teamHeader.textContent = 'Team Attribute Changes';
    teamHeader.style.marginTop = '20px';
    container.appendChild(teamHeader);

    Object.entries(data.team_log).forEach(([attr, delta]) => {
      const row = document.createElement('p');
      row.style.marginBottom = '5px';
      const sign = delta > 0 ? '+' : '';
      row.textContent = `${attr}: ${sign}${delta}`;
      container.appendChild(row);
    });
  }
}

function renderTeam(data) {
  console.log('renderTeam called with data:', data);
  if (!data) {
    console.log('No data provided to renderTeam');
    return;
  }
  const tbody = document.getElementById('team-body');
  if (!tbody) {
    console.log('team-body element not found');
    return;
  }
  tbody.innerHTML = '';
  console.log('Players data:', data.players);
  let players = (data.players || []).map(p => {
    try {
      const best = getBestPosition(p.position_ratings || {});
      const fullName = `${p.first_name || ''} ${p.last_name || ''}`.trim() || p.name || '';
      const player = {
        _id: p._id, // Add missing _id field for player detail links
        name: fullName,
        pos: best.pos,
        year: yearMap[p.year?.toLowerCase()] || p.year || '--',
        height: formatHeight(p.height),
        weight: p.weight ?? '--',
        attributes: p.attributes || {},
        rt: best.rating,
      };
      console.log('Mapped player:', player);
      return player;
    } catch (error) {
      console.error('Error mapping player:', p, error);
      return null;
    }
  }).filter(p => p !== null);
  players.sort((a, b) => (b.rt ?? -1) - (a.rt ?? -1));
  console.log('Sorted players:', players);
  console.log('About to render', players.length, 'players');
  players.forEach((p, index) => {
    console.log(`Rendering player ${index + 1}:`, p.name);
    const tr = document.createElement('tr');
    
    // Create player name as clickable link
    const nameTd = document.createElement("td");
    const nameLink = document.createElement("a");
    nameLink.href = `/static/player-detail.html?id=${p._id}`;
    nameLink.textContent = p.name;
    nameLink.style.color = 'inherit';
    nameLink.style.textDecoration = 'none';
    nameLink.addEventListener('mouseenter', () => {
      nameLink.style.textDecoration = 'underline';
    });
    nameLink.addEventListener('mouseleave', () => {
      nameLink.style.textDecoration = 'none';
    });
    nameTd.appendChild(nameLink);
    tr.appendChild(nameTd);
    
    // Add other columns directly as DOM elements
    const addCell = (content) => {
      const td = document.createElement('td');
      td.textContent = content;
      tr.appendChild(td);
    };
    
    addCell(p.pos);
    addCell(p.year);
    addCell(p.height);
    addCell(p.weight);
    
    ATTR_HEADERS.forEach(h => {
      const attrs = p.attributes || {};
      // Use anchor attribute (base value) as fallback, same as lineup screen
      const rawVal = attrs[`anchor_${h}`] ?? attrs[h];
      console.log(`  ${h}: anchor_${h}=${attrs[`anchor_${h}`]}, ${h}=${attrs[h]}, rawVal=${rawVal}`);
      // Convert to 0-12 scale, except NG which stays as decimal
      const displayVal = h === 'NG' 
        ? (rawVal != null ? rawVal.toFixed(2) : '--')
        : (rawVal != null ? Math.floor(rawVal / 10) : '--');
      addCell(displayVal);
    });
    addCell(p.rt ?? '-');
    
    tbody.appendChild(tr);
    console.log(`Added row for ${p.name} to table`);
  });
    console.log('Finished rendering all players. Table now has', tbody.children.length, 'rows');
  
  // Initialize tooltips for table cells
  if (typeof initAttributeTooltips !== 'undefined') {
    initAttributeTooltips(tbody, ['td']);
  }
}

function renderSchedule(data) {
  if (!data) return;
  // Schedule container is now in the schedule-tab, not standings-tab
  const container = document.getElementById('schedule-container');
  if (!container) return;
  container.innerHTML = '';
  const teamId = data.team_id;
  (data.schedule || []).forEach((weekGames, idx) => {
    const weekDiv = document.createElement('div');
    weekDiv.className = 'schedule-week';
    const h4 = document.createElement('h4');
    h4.textContent = `Week ${idx + 1}`;
    weekDiv.appendChild(h4);
    weekGames.forEach(g => {
      const gameDiv = document.createElement('div');
      gameDiv.className = 'schedule-game';
      const away = teamIdNameMap[g.away_team_id] || g.away_team_id;
      const home = teamIdNameMap[g.home_team_id] || g.home_team_id;
      let text = '';
      if (g.status === 'complete') {
        let awayStr = `${away} (${g.away_score})`;
        let homeStr = `${home} (${g.home_score})`;
        if (g.away_score > g.home_score) awayStr = `<strong>${awayStr}</strong>`;
        if (g.home_score > g.away_score) homeStr = `<strong>${homeStr}</strong>`;
        text = `${awayStr} at ${homeStr}`;
      } else {
        text = `${away} at ${home}`;
      }
      gameDiv.innerHTML = text;
      
      // Add training report link if this is user's team's game and training report exists
      if (g.is_user_team && g.has_training_report) {
        const link = document.createElement('a');
        link.href = `/static/training-report.html?mode=franchise&franchise_id=${franchiseId}&team_id=${teamId}&week=${g.week}`;
        link.textContent = ' [Training Report]';
        link.className = 'training-report-link';
        link.style.color = '#4a90e2';
        link.style.textDecoration = 'none';
        link.style.marginLeft = '8px';
        link.style.fontSize = 'calc(1em - 2px)';
        gameDiv.appendChild(link);
      }
      
      weekDiv.appendChild(gameDiv);
    });
    container.appendChild(weekDiv);
  });
}

async function init() {
  const topData = await fetchJSON(`/franchise/command-center/data?franchise_id=${franchiseId}`);
  populateTop(topData);
  
  // Update button based on training status
  updatePlayButton(topData);
  
  if (topData && topData.team) {
    // Use franchise-specific roster endpoint to get updated player attributes
    console.log('Loading franchise roster for team:', topData.team, 'franchiseId:', franchiseId);
    if (!franchiseId) {
      console.error('No franchiseId found - cannot load roster');
      return;
    }
    try {
      const rosterData = await fetchJSON(`/franchise/roster?franchise_id=${franchiseId}&team_name=${encodeURIComponent(topData.team)}`);
      console.log('Franchise roster data:', rosterData);
      if (rosterData.players && rosterData.players.length > 0) {
        console.log('First player attributes:', rosterData.players[0].attributes);
      }
      renderTeam(rosterData);
    } catch (error) {
      console.error('Failed to load franchise roster:', error);
    }
  }
  const standingsData = await fetchJSON(`/franchise/standings?franchise_id=${franchiseId}`);
  renderStandings(standingsData);
    const scheduleData = await fetchJSON(`/franchise/schedule?franchise_id=${franchiseId}`);
    renderSchedule(scheduleData);
    renderLeaders(await fetchJSON(`/franchise/leaders?franchise_id=${franchiseId}`));
    renderTeamStats(await fetchJSON('/franchise/team-stats'));
    renderRecruits(await fetchJSON(`/franchise/recruits?franchise_id=${franchiseId}`));
    renderTrainingResults(await fetchJSON(`/franchise/latest-training?franchise_id=${franchiseId}`));
    
    // Initialize tooltips for table headers
    if (typeof initAttributeTooltips !== 'undefined') {
      const teamTable = document.querySelector('#team-tab .roster-table');
      const recruitsTable = document.querySelector('#recruits-tab .roster-table');
      if (teamTable) initAttributeTooltips(teamTable, ['th']);
      if (recruitsTable) initAttributeTooltips(recruitsTable, ['th']);
    }
  }

function updatePlayButton(data) {
  const playNowBtn = document.getElementById('play-now');
  if (!data) return;
  
  const trainingCompleted = data.training_completed || false;
  const sessionType = data.session_type || 'in-season';
  
  if (!trainingCompleted) {
    playNowBtn.textContent = sessionType === 'preseason' ? 'Run Training Camp' : 'Run Training';
    playNowBtn.dataset.mode = 'training';
  } else {
    playNowBtn.textContent = 'Play Now';
    playNowBtn.dataset.mode = 'play';
  }
}

const playNowBtn = document.getElementById('play-now');
playNowBtn.disabled = true;
playNowBtn.addEventListener('click', async () => {
  const mode = playNowBtn.dataset.mode || 'play';
  
  if (mode === 'training') {
    // Navigate to training page
    const topData = await fetchJSON(`/franchise/command-center/data?franchise_id=${franchiseId}`);
    const sessionType = topData?.session_type || 'in-season';
    window.location.href = `/static/training.html?franchise_id=${franchiseId}&mode=franchise&session_type=${sessionType}`;
    return;
  }
  
  // Otherwise, play the game
  console.log('Play Now click search:', window.location.search);
  const originalText = playNowBtn.textContent;
  playNowBtn.disabled = true;
  playNowBtn.textContent = 'Loading...';
  if (!franchiseId) {
    alert('Franchise not loaded');
    playNowBtn.disabled = false;
    playNowBtn.textContent = originalText;
    return;
  }
  try {
    const res = await fetch('/franchise/play-next-game', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ franchise_id: franchiseId })
    });
    if (!res.ok) throw new Error('Simulation failed');
    const { home, away, week, home_id, away_id } = await res.json();
    if (!home || !away) throw new Error('Matchup not found');
    try {
      localStorage.setItem('franchise_week', week);
    } catch {}
    const mySide = userTeamName === home ? 'home' : (userTeamName === away ? 'away' : '');
    let url = `/static/set-lineup.html?franchise_id=${encodeURIComponent(franchiseId)}&week=${week}&home=${encodeURIComponent(home)}&away=${encodeURIComponent(away)}&home_id=${encodeURIComponent(home_id)}&away_id=${encodeURIComponent(away_id)}`;
    if (userTeamName) url += `&user_team_id=${encodeURIComponent(userTeamName)}`;
    if (mySide) url += `&my_team=${mySide}`;
    console.log('Navigating to', url);
    window.location.href = url;
  } catch (err) {
    console.error(err);
    alert('Unable to play next game');
    playNowBtn.disabled = false;
    playNowBtn.textContent = originalText;
  }
});

// Set Game Plan button (Franchise Command Center)
const setGameplanBtn = document.getElementById('set-gameplan-franchise');
if (setGameplanBtn) {
  setGameplanBtn.addEventListener('click', () => {
    if (!franchiseId || !userTeamName) {
      alert('Franchise or user team not loaded');
      return;
    }
    
    // Redirect to Game Plan screen with franchise context
    const url = `/game-plan.html?mode=franchise&franchise_id=${encodeURIComponent(franchiseId)}&user_team_id=${encodeURIComponent(userTeamName)}&from=command_center`;
    window.location.href = url;
  });
}

// Playbooks button (Franchise Command Center)
const playbooksBtn = document.getElementById('playbooks-franchise');
if (playbooksBtn) {
  playbooksBtn.addEventListener('click', () => {
    if (!franchiseId || !userTeamName) {
      alert('Franchise or user team not loaded');
      return;
    }
    
      // Build playbooks URL with franchise parameters
      const params = new URLSearchParams();
      params.set('mode', 'franchise');
      params.set('franchise_id', franchiseId);
      params.set('team_id', userTeamName); // userTeamName is the team name, backend will resolve to team_id
      params.set('from', 'franchise-command-center'); // Track navigation source
      
      window.location.href = `/static/playbooks.html?${params.toString()}`;
  });
}

window.addEventListener('DOMContentLoaded', () => {
  franchiseId = localStorage.getItem('franchiseId');
  if (franchiseId) {
    playNowBtn.disabled = false;
  }
  init();
});
