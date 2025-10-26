let rosterData = null;
let currentView = sessionStorage.getItem('rosterView') || 'grid';

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
  
  card.innerHTML = `
    <div class="player-card-header">
      <h3>${player.name || 'Unknown'}</h3>
      <span class="player-position">${highestPos}</span>
    </div>
    <div class="player-card-attributes">
      <div class="attr-row">
        <span class="attr-label">SC:</span>
        <span class="attr-value">${formatAttr('SC')}</span>
        <span class="attr-label">SH:</span>
        <span class="attr-value">${formatAttr('SH')}</span>
        <span class="attr-label">ID:</span>
        <span class="attr-value">${formatAttr('ID')}</span>
      </div>
      <div class="attr-row">
        <span class="attr-label">OD:</span>
        <span class="attr-value">${formatAttr('OD')}</span>
        <span class="attr-label">PS:</span>
        <span class="attr-value">${formatAttr('PS')}</span>
        <span class="attr-label">BH:</span>
        <span class="attr-value">${formatAttr('BH')}</span>
      </div>
      <div class="attr-row">
        <span class="attr-label">RB:</span>
        <span class="attr-value">${formatAttr('RB')}</span>
        <span class="attr-label">ST:</span>
        <span class="attr-value">${formatAttr('ST')}</span>
        <span class="attr-label">AG:</span>
        <span class="attr-value">${formatAttr('AG')}</span>
      </div>
      <div class="attr-row">
        <span class="attr-label">ND:</span>
        <span class="attr-value">${formatAttr('ND')}</span>
        <span class="attr-label">IQ:</span>
        <span class="attr-value">${formatAttr('IQ')}</span>
        <span class="attr-label">FT:</span>
        <span class="attr-value">${formatAttr('FT')}</span>
      </div>
    </div>
  `;
  
  // Make card clickable to view player details
  card.style.cursor = 'pointer';
  card.addEventListener('click', () => {
    window.location.href = `/static/player-detail.html?id=${player._id}`;
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
  