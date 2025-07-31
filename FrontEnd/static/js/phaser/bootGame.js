import * as Phaser from 'https://cdn.jsdelivr.net/npm/phaser@3.60.0/dist/phaser.esm.js';
import { createGameScene } from './gameScene.js';

const urlParams = new URLSearchParams(window.location.search);
const tournamentId = urlParams.get('tournament_id');
const franchise = urlParams.get('franchise');
const homeTeam = urlParams.get('home');
const awayTeam = urlParams.get('away');

console.log('🏀 Tournament launch params:', {
  tournamentId,
  homeTeam,
  awayTeam,
});

const GameScene = createGameScene(Phaser);
let game;
let gamePromise;


async function fetchTeamRoster(teamName) {
  const res = await fetch(`/roster/${encodeURIComponent(teamName)}?tournament_id=${tournamentId}`);
  if (!res.ok) {
    throw new Error(`Failed to load roster for ${teamName}`);
  }
  return res.json();
}

async function startGameAnimation({ homeRoster, awayRoster }) {
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
    homeTeam,
    awayTeam,
  };

  if (game.scene.isActive('GameScene')) {
    game.scene.restart('GameScene', sceneData);
  } else {
    game.scene.start('GameScene', sceneData);
  }

  gamePromise = new Promise((resolve) => {
    // Listen on the global event emitter so we don't lose the listener when
    // GameScene is restarted or recreated
    game.events.once('gameComplete', (finalScore) => {
      resolve(finalScore);
    });
  });

  return gamePromise;
}

function showPopup(score) {
  const container = document.getElementById('phaser-container');
  const popup = document.createElement('div');
  popup.className = 'result-popup';

  let backUrl;
  if (tournamentId) {
    backUrl = 'https://gob-simplified-production.up.railway.app/static/tournament.html';
  } else if (franchise) {
    backUrl = 'https://gob-simplified-production.up.railway.app/franchise-command-center.html';
  } else {
    backUrl = 'https://gob-simplified-production.up.railway.app/static/mode-select.html';
  }

  popup.innerHTML = `
    <div class="popup-content">
      <h2>Final Score</h2>
      <p>${score.homeTeam} ${score.homeScore} - ${score.awayScore} ${score.awayTeam}</p>
      <a href="${backUrl}" class="back-button">Back To Locker Room</a>
    </div>
  `;
  container.appendChild(popup);
}

async function playGame() {
  playBtn.style.display = 'none';
  resultsBtn.style.display = 'none';

  if (!homeTeam || !awayTeam) {
    alert('Please select teams before playing.');
    return;
  }

  const [homeRoster, awayRoster] = await Promise.all([
    fetchTeamRoster(homeTeam),
    fetchTeamRoster(awayTeam),
  ]);

  const score = await startGameAnimation({ homeRoster, awayRoster });
  if (score) {
    showPopup(score);
  }
}

async function showResults() {
  playBtn.style.display = 'none';
  resultsBtn.style.display = 'none';
  try {
    const res = await fetch(`/game/result?tournament_id=${tournamentId}`);
    const data = await res.json();
    const score = {
      homeTeam: data.home_team || homeTeam,
      awayTeam: data.away_team || awayTeam,
      homeScore: data.score?.[data.home_team] ?? 0,
      awayScore: data.score?.[data.away_team] ?? 0,
    };
    showPopup(score);
  } catch (err) {
    console.error('Failed to fetch results', err);
  }
}

const playBtn = document.querySelector('.play-button');
const resultsBtn = document.querySelector('.results-button');
if (playBtn) playBtn.addEventListener('click', playGame);
if (resultsBtn) resultsBtn.addEventListener('click', showResults);


// new Phaser.Game(config);



