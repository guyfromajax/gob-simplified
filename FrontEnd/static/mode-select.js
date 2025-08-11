const scrimmageBtn = document.getElementById('scrimmage-btn');
const tournamentBtn = document.getElementById('tournament-btn');
const franchiseBtn = document.getElementById('franchise-btn');

if (scrimmageBtn) {
  scrimmageBtn.addEventListener('click', () => {
    window.location.href = './index.html';
  });
}

if (tournamentBtn) {
  tournamentBtn.addEventListener('click', () => {
    window.location.href = './tournament-select.html';
  });
}

if (franchiseBtn) {
  // franchiseBtn.addEventListener('click', () => {
  //   window.location.href = './franchise-select-team.html';
  // });
  franchiseBtn.addEventListener('click', () => {
    window.location.href = '/franchise/start';
  });

}

document.addEventListener('DOMContentLoaded', () => {
  const teamButtons = document.querySelectorAll('.team-button');
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
      window.location.href = `/team-roster/${encodeURIComponent(team)}`;
    });
  });

  const fallbackColor = '#ccc';
  fetch('/teams')
    .then(resp => resp.json())
    .then(teamData => {
      const colorMap = {};
      teamData.forEach(t => {
        colorMap[t.name] = t.secondary_color;
      });

      teamButtons.forEach(btn => {
        const team = btn.dataset.team;
        const taglineEl = btn.querySelector('.team-tagline');
        const color = colorMap[team] || fallbackColor;
        const taglineColor = colorMap[team] ? '#fff' : '#000';
        btn.style.borderColor = color;
        btn.style.backgroundColor = color;
        if (taglineEl) taglineEl.style.color = taglineColor;
        console.log(`Tile ${team} bgColor: ${color}`);
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
