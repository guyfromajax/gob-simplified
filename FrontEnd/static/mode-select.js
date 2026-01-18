const scrimmageBtn = document.getElementById('scrimmage-btn');
const tournamentBtn = document.getElementById('tournament-btn');
const franchiseBtn = document.getElementById('franchise-btn');

if (scrimmageBtn) {
  scrimmageBtn.addEventListener('click', () => {
    window.location.href = './scrimmage-select.html';
  });
}

if (tournamentBtn) {
  tournamentBtn.addEventListener('click', () => {
    window.location.href = './tournament-select.html';
  });
}

if (franchiseBtn) {
  franchiseBtn.addEventListener('click', () => {
    window.location.href = './franchise-select-team.html';
  });
}

document.addEventListener('DOMContentLoaded', () => {
  const teamButtons = document.querySelectorAll('.team-button');
  const modeContainer = document.querySelector('.mode-container');
  const teamGrid = document.getElementById('team-grid');
  const syncTeamGridWidth = () => {
    if (modeContainer && teamGrid) {
      teamGrid.style.width = `${modeContainer.offsetWidth}px`;
    }
  };
  window.addEventListener('resize', syncTeamGridWidth);
  syncTeamGridWidth();
  const taglines = {
    'Bentley-Truman': 'Top-Shelf Talent',
    'Lancaster': 'Muscle & Defense',
    'Four Corners': 'Hustle & Attitude',
    'Ocean City': 'Sharpshooters Galore',
    'Morristown': 'Perfectly Balanced',
    'Little York': 'Wicked Smart',
    'Xavien': 'Youthful Exuberance',
    'South Lancaster': 'Us vs The World'
  };

  teamButtons.forEach(btn => {
    const team = btn.dataset.team;

    const taglineEl = btn.querySelector('.team-tagline');
    if (taglineEl && taglines[team]) {
      taglineEl.textContent = taglines[team];
    }

    btn.addEventListener('click', () => {
      // Link to team roster view page with Grid/Player view toggle
      window.location.href = `/team-roster-view.html?team_name=${encodeURIComponent(team)}&return_url=${encodeURIComponent(window.location.pathname)}`;
    });
  });

  const fallbackColor = '#ccc';
  fetch(API_CONFIG.buildUrl('/teams'))
    .then(resp => resp.json())
    .then(teamData => {
      const colorMap = {};
      teamData.forEach(t => {
        colorMap[t.name] = {
          primary: t.primary_color,
          secondary: t.secondary_color
        };
      });

      teamButtons.forEach(btn => {
        const team = btn.dataset.team;
        const taglineEl = btn.querySelector('.team-tagline');
        const colors = colorMap[team] || {};
        const bgColor = colors.primary || fallbackColor;
        const borderColor = colors.secondary || fallbackColor;
        const taglineColor = colors.primary ? '#fff' : '#000';
        btn.style.backgroundColor = bgColor;
        btn.style.borderColor = borderColor;
        if (taglineEl) taglineEl.style.color = taglineColor;
        console.log(`Tile ${team} bgColor: ${bgColor} borderColor: ${borderColor}`);
      });
    })
    .catch(() => {
      teamButtons.forEach(btn => {
        const taglineEl = btn.querySelector('.team-tagline');
        btn.style.borderColor = fallbackColor;
        btn.style.backgroundColor = fallbackColor;
        if (taglineEl) taglineEl.style.color = '#000';
        console.log(`Tile ${btn.dataset.team} bgColor: ${fallbackColor} (fallback)`);
      });
    });
});
