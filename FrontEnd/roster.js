let rosterData = null;
let currentView = sessionStorage.getItem('rosterView') || 'grid';

// Convert a numeric height (in inches) to feet-inches format
function formatHeight(raw) {
  const inches = parseInt(raw, 10);
  if (isNaN(inches)) return raw ?? '--';
  const ft = Math.floor(inches / 12);
  const inch = inches % 12;
  return `${ft}'${inch}"`;
}

async function loadRoster() {
    const team = document.getElementById("teamSelect").value;
    const container = document.getElementById("rosterContainer");
    const backendURL = window.location.origin;
    container.innerHTML = "Loading...";
  
    try {
      const res = await fetch(`${backendURL}/roster/${team}`);
      const data = await res.json();
      rosterData = data;
  
      const headers = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "AG", "ST", "ND", "IQ", "FT", "NG"];
  
      let html = `<h2>${data.team} Roster</h2><table class="roster-table"><thead><tr><th>Player</th>`;
      headers.forEach(attr => html += `<th>${attr}</th>`);
      html += `</tr></thead><tbody>`;
  
      data.players.forEach(p => {
        html += `<tr><td><a href="/static/player-detail.html?id=${p._id}">${p.name}</a></td>`;
        headers.forEach(attr => {
          let value = p.attributes[attr];
  
          if (attr === "NG") {
            value = (value ?? 0).toFixed(2);  // show 2 decimal places
          } else {
            value = Math.floor((value ?? 0) / 10);  // Convert to 0-12 scale
          }
  
          html += `<td>${value}</td>`;
        });
        html += `</tr>`;
      });
  
      html += `</tbody></table>`;
      container.innerHTML = html;
      
      // Update player view if active
      if (currentView === 'player') {
        renderPlayerView();
      }
  
    } catch (err) {
      console.error(err);
      container.innerHTML = "❌ Failed to load roster.";
    }
}

function switchView(view) {
  currentView = view;
  sessionStorage.setItem('rosterView', view);
  
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
  if (!container || !rosterData) return;
  
  container.innerHTML = '';
  
  // Sort players by their HIGHEST position rating
  const sortedPlayers = rosterData.players
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
  card.className = 'player-card';
  card.dataset.playerId = player._id;
  
  const posRatings = player.position_ratings || {};
  const highestPos = Object.entries(posRatings)
    .sort((a, b) => b[1] - a[1])[0]?.[0] || 'N/A';
  
  const attrs = player.attributes || {};
  const formatAttr = (attr) => {
    if (attr === "NG") {
      return (attrs[attr] ?? 0).toFixed(2);
    }
    return Math.floor((attrs[attr] ?? 0) / 10);
  };
  
  // Create the card inner structure
  const cardInner = document.createElement('div');
  cardInner.className = 'player-card-inner';
  
  // Create front side (simple info)
  const cardFront = document.createElement('div');
  cardFront.className = 'player-card-front';
  
  // Player headshot container
  const headshotContainer = document.createElement('div');
  headshotContainer.className = 'player-headshot-container';
  
  const headshot = document.createElement('img');
  headshot.className = 'player-headshot';
  headshot.src = `/static/images/players/${player._id}.png`;
  headshot.alt = player.name || 'Unknown';
  headshot.onerror = function() {
    this.style.display = 'none';
  };
  
  headshotContainer.appendChild(headshot);
  
  // Player info bar
  const infoBar = document.createElement('div');
  infoBar.className = 'player-info-bar';
  
  const infoLeft = document.createElement('div');
  infoLeft.className = 'player-info-left';
  
  const playerName = document.createElement('div');
  playerName.className = 'player-name';
  playerName.textContent = player.name || 'Unknown';
  
  const playerPhysical = document.createElement('div');
  playerPhysical.className = 'player-physical';
  const height = formatHeight(player.height);
  const weight = player.weight ? `${player.weight} lbs` : '--';
  playerPhysical.textContent = `${height} • ${weight}`;
  
  infoLeft.appendChild(playerName);
  infoLeft.appendChild(playerPhysical);
  
  const energyDisplay = document.createElement('div');
  energyDisplay.className = 'player-energy-display';
  energyDisplay.textContent = highestPos;
  
  infoBar.appendChild(infoLeft);
  infoBar.appendChild(energyDisplay);
  
  cardFront.appendChild(headshotContainer);
  cardFront.appendChild(infoBar);
  
  // Create back side (attributes)
  const cardBack = document.createElement('div');
  cardBack.className = 'player-card-back';
  
  // Create attribute sections
  const sections = [
    { title: 'Offensive', attrs: ['SC', 'SH', 'OD', 'PS'] },
    { title: 'Defensive', attrs: ['ID', 'BH', 'RB', 'ST'] },
    { title: 'Physical', attrs: ['AG', 'ND', 'IQ', 'FT'] },
    { title: 'Mental', attrs: ['NG'] }
  ];
  
  sections.forEach(section => {
    const sectionDiv = document.createElement('div');
    sectionDiv.className = 'attr-section';
    
    const title = document.createElement('div');
    title.className = 'attr-section-title';
    title.textContent = section.title;
    sectionDiv.appendChild(title);
    
    section.attrs.forEach(attr => {
      const attrRow = document.createElement('div');
      attrRow.className = 'attr-row';
      
      const value = formatAttr(attr);
      const rawAttr = Number(attrs[attr] ?? 0);
      const percentage = attr === 'NG' ?
        Math.min(100, Math.max(0, rawAttr * 10)) :
        Math.min(100, Math.max(0, rawAttr * 8.33));

      attrRow.style.setProperty('--attr-fill', `${percentage}%`);
      if (typeof getAttrColor === 'function') {
        const bucket = attr === 'NG' ? Math.ceil(rawAttr * 10) : Math.ceil(rawAttr / 10);
        attrRow.style.setProperty('--attr-bar-color', getAttrColor(bucket));
      }
      
      const label = document.createElement('span');
      label.className = 'attr-label';
      label.textContent = attr;
      
      const valueSpan = document.createElement('span');
      valueSpan.className = 'attr-value';
      valueSpan.textContent = value;
      
      attrRow.appendChild(label);
      attrRow.appendChild(valueSpan);
      sectionDiv.appendChild(attrRow);
    });
    
    cardBack.appendChild(sectionDiv);
  });
  
  cardInner.appendChild(cardFront);
  cardInner.appendChild(cardBack);
  card.appendChild(cardInner);
  
  // Add click handler for flipping
  card.addEventListener('click', (e) => {
    e.preventDefault();
    card.classList.toggle('flipped');
  });
  
  return card;
}

// Initialize view toggle on page load
document.addEventListener('DOMContentLoaded', () => {
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
});
  