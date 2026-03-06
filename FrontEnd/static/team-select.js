const logoGrid = document.getElementById('logo-grid');
const awayBox = document.getElementById('away-box');
const homeBox = document.getElementById('home-box');
const awayCheck = document.getElementById('away-check');
const homeCheck = document.getElementById('home-check');
const playBtn = document.getElementById('play-btn');
const clickSound = new Audio('./sounds/click-beep.wav');
const addSound = new Audio('./sounds/click-handgun.mp3');

// Looping lobby music on team-select (scrimmage/single game) screen
(function () {
  try {
    var lobbyMusic = new Audio('/sounds/crossover-21738.mp3');
    lobbyMusic.loop = true;
    lobbyMusic.volume = 0.4;
    lobbyMusic.play().catch(function () {});
  } catch (e) {}
})();

const teamCodeMap = {
  "Bentley-Truman": "bt",
  "Four Corners": "fc",
  "Lancaster": "lan",
  "Little York": "ly",
  "Morristown": "mor",
  "Ocean City": "oc",
  "South Lancaster": "sl",
  "Xavien": "xav"
};

const teams = [
  'Bentley-Truman',
  'Lancaster',
  'Four Corners',
  'Ocean City',
  'Morristown',
  'Little York',
  'Xavien',
  'South Lancaster'
];

function createLogoButtons() {
  teams.forEach(name => {
    const btn = document.createElement('button');
    btn.className = 'logo-btn';
    btn.title = 'click or drag to add';
    const img = document.createElement('img');
    img.src = typeof getTeamAssetPath === 'function' ? getTeamAssetPath(name, 'logo_square') : '/images/teams/general/general_logo_square.png';
    img.alt = name;
    img.draggable = true;
    img.addEventListener('dragstart', e => {
      e.dataTransfer.setData('text/plain', name);
    });
    btn.appendChild(img);
    btn.addEventListener('click', () => {
      addSound.play();
      addToFirstAvailable(name);
    });
    logoGrid.appendChild(btn);
  });
}

function addToFirstAvailable(team) {
  const bothEmpty = !awayBox.dataset.team && !homeBox.dataset.team;
  if (bothEmpty) {
    // Place in the slot marked as "My Team" first
    if (homeCheck.checked) {
      setLogo(homeBox, team);
    } else {
      setLogo(awayBox, team);
    }
  } else if (!awayBox.dataset.team) {
    setLogo(awayBox, team);
  } else if (!homeBox.dataset.team) {
    setLogo(homeBox, team);
  }
}

function setLogo(box, team) {
  box.innerHTML = '';
  const img = document.createElement('img');
  img.src = typeof getTeamAssetPath === 'function' ? getTeamAssetPath(team, 'logo_square') : '/images/teams/general/general_logo_square.png';
  img.onerror = function() {
    img.onerror = null;
    img.src = typeof getTeamAssetPath === 'function' ? getTeamAssetPath(null, 'logo_square') : './images/teams/general/general_logo_square.png';
  };
  img.alt = team;
  box.appendChild(img);
  box.dataset.team = team;
  updatePlayBtn();
}

function handleDrop(event, target) {
  event.preventDefault();
  const team = event.dataTransfer.getData('text/plain');
  if (team) {
    const box = target === 'home' ? homeBox : awayBox;
    setLogo(box, team);
    addSound.play();
  }
}

function toggleMyTeam(which) {
  if (which === 'home') {
    if (homeCheck.checked) awayCheck.checked = false;
  } else {
    if (awayCheck.checked) homeCheck.checked = false;
  }
}

function updatePlayBtn() {
  if (homeBox.dataset.team && awayBox.dataset.team) {
    playBtn.disabled = false;
    playBtn.style.opacity = '1';
  } else {
    playBtn.disabled = true;
    playBtn.style.opacity = '0.5';
  }
}

playBtn.addEventListener('click', () => {
  if (playBtn.disabled) return;
  clickSound.play();

  const homeTeam = homeBox.dataset.team;
  const awayTeam = awayBox.dataset.team;

  // Persist selection for other pages that still rely on sessionStorage
  sessionStorage.setItem('homeTeam', homeTeam);
  sessionStorage.setItem('awayTeam', awayTeam);
  if (homeCheck.checked || awayCheck.checked) {
    sessionStorage.setItem('myTeam', homeCheck.checked ? 'home' : 'away');
  } else {
    sessionStorage.removeItem('myTeam');
  }

  const params = new URLSearchParams({
    home: homeTeam,
    away: awayTeam,
    mode: 'single'
  });

  if (homeCheck.checked || awayCheck.checked) {
    const mySide = homeCheck.checked ? 'home' : 'away';
    params.set('my_team', mySide);
    const userTeam = mySide === 'home' ? homeTeam : awayTeam;
    params.set('user_team_id', userTeam);
  }

  window.location.href = `/set-lineup.html?${params.toString()}`;
});

createLogoButtons();
