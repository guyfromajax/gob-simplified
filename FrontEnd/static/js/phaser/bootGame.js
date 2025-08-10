import * as Phaser from 'https://cdn.jsdelivr.net/npm/phaser@3.60.0/dist/phaser.esm.js';
import { createGameScene } from './gameScene.js';

function getMode({ tournamentId, franchiseId }) {
  if (tournamentId) return 'tournament';
  if (franchiseId) return 'franchise';
  return 'standalone';
}

function buildQuery(params = {}) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value) search.append(key, value);
  });
  const str = search.toString();
  return str ? `?${str}` : '';
}

const urlParams = new URLSearchParams(window.location.search);
const tournamentId = urlParams.get('tournament_id');
const homeTeam = urlParams.get('home');
const awayTeam = urlParams.get('away');
const queryFranchiseId = urlParams.get('franchise_id');
const storedFranchiseId =
  typeof localStorage !== 'undefined'
    ? localStorage.getItem('franchise_id') || localStorage.getItem('franchiseId')
    : null;
const franchiseId = queryFranchiseId || storedFranchiseId;
if (queryFranchiseId && typeof localStorage !== 'undefined') {
  localStorage.setItem('franchise_id', queryFranchiseId);
}
const mode = urlParams.get('mode') || getMode({ tournamentId, franchiseId });

console.log("🏀 Tournament launch params:", {
  tournamentId,
  franchiseId,
  homeTeam,
  awayTeam,
  mode
});

const GameScene = createGameScene(Phaser);
let game;
let isSimulating = false;


async function fetchTeamRoster(teamName) {
  const query = buildQuery({
    tournament_id: mode === 'tournament' ? tournamentId : null,
    franchise_id: mode === 'franchise' ? franchiseId : null,
  });
  const res = await fetch(`/roster/${encodeURIComponent(teamName)}${query}`);
  if (!res.ok) {
    throw new Error(`Failed to load roster for ${teamName}`);
  }
  return res.json();
}

async function startGame({ homeRoster, awayRoster, animate = true }) {
  if (!game) {
    game = new Phaser.Game({
      type: Phaser.AUTO,
      width: 1229,
      height: 768,
      backgroundColor: '#1e1e1e',
      parent: 'phaser-container',
      audio: { noAudio: true },
      scene: [], // prevent auto-start
    });
    game.scene.add('GameScene', GameScene);
  }

  const sceneData = {
    rosters: { homeRoster, awayRoster },
    tournamentId,
    franchiseId,
    homeTeam,
    awayTeam,
    animate,
  };

  if (game.scene.isActive('GameScene')) {
    game.scene.restart('GameScene', sceneData);
  } else {
    game.scene.start('GameScene', sceneData);
  }

  return new Promise((resolve) => {
    // Listen on the global event emitter so we don't lose the listener when
    // GameScene is restarted or recreated
    game.events.once('gameComplete', (finalScore) => {
      resolve(finalScore);
    });
  });
}

function showPopup(score) {
  const container = document.getElementById('phaser-container');
  const popup = document.createElement('div');
  popup.className = 'result-popup';

  let backUrl;
  switch (mode) {
    case 'tournament':
      backUrl = '/static/tournament.html';
      break;
    case 'franchise':
      backUrl = '/franchise/command-center' + buildQuery({ franchise_id: franchiseId });
      break;
    default:
      backUrl = '/static/mode-select.html';
  }

  console.log('showPopup back navigation', { tournamentId, franchiseId, mode, backUrl });

  popup.innerHTML = `
    <div class="popup-content">
      <h2>Final Score</h2>
      <p>${score.homeTeam} ${score.homeScore} - ${score.awayScore} ${score.awayTeam}</p>
      <a href="${backUrl}" class="back-button">Back To Locker Room</a>
    </div>
  `;
  container.appendChild(popup);
}

async function handleButtonClick(animate) {
  if (isSimulating) return;
  isSimulating = true;
  const playBtn = document.querySelector('.play-button');
  const resultsBtn = document.querySelector('.results-button');
  if (playBtn) playBtn.style.display = 'none';
  if (resultsBtn) resultsBtn.style.display = 'none';

  try {
    const [homeRoster, awayRoster] = await Promise.all([
      fetchTeamRoster(homeTeam),
      fetchTeamRoster(awayTeam),
    ]);
    const finalScore = await startGame({ homeRoster, awayRoster, animate });
    showPopup(finalScore);
  } catch (err) {
    console.error('Error starting game:', err);
    isSimulating = false;
    if (playBtn) playBtn.style.display = '';
    if (resultsBtn) resultsBtn.style.display = '';
  }
}

function initGame() {
  const playBtn = document.querySelector('.play-button');
  const resultsBtn = document.querySelector('.results-button');
  if (playBtn) {
    playBtn.addEventListener('click', () => handleButtonClick(true));
  }
  if (resultsBtn) {
    resultsBtn.addEventListener('click', () => handleButtonClick(false));
  }
}

initGame();

// new Phaser.Game(config);
