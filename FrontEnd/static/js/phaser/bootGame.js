import * as Phaser from 'https://cdn.jsdelivr.net/npm/phaser@3.60.0/dist/phaser.esm.js';
import { createGameScene } from './gameScene.js';
import { setCourtOffsets } from './utils/gridToPixels.js';
import { on, emit } from './utils/eventBus.js';
import { finalizeGame } from './finalizeGame.js';
import { DEBUG } from './utils/debug.js';
import gameStore from '../state/gameStore.js';

const DEBUG_GAME_ID =
  (typeof window !== 'undefined' && window.DEBUG_GAME_ID) ||
  (typeof process !== 'undefined' && process.env.DEBUG_GAME_ID) ||
  false;
const DEBUG_TEAMS =
  (typeof window !== 'undefined' && window.DEBUG_TEAMS) ||
  (typeof process !== 'undefined' && process.env.DEBUG_TEAMS) ||
  false;
const DEBUG_SERIALIZATION =
  (typeof window !== 'undefined' && window.DEBUG_SERIALIZATION) ||
  (typeof process !== 'undefined' && process.env.DEBUG_SERIALIZATION) ||
  false;

if (typeof window !== 'undefined') {
  window.TEXT_SCROLL_ENABLED =
    window.TEXT_SCROLL_ENABLED !== undefined ? window.TEXT_SCROLL_ENABLED : true;
  window.TEXT_SCROLL_CONFIG = {
    autoScroll: true,
    smooth: false,
    lineSpacing: '1em',
    ...(window.TEXT_SCROLL_CONFIG || {}),
  };
  window.animation_config = window.animation_config || {};
}

function updateScoreboardScores({ home, away }) {
  const homeScoreEl = document.getElementById('home-score');
  const awayScoreEl = document.getElementById('away-score');
  if (homeScoreEl) homeScoreEl.textContent = home;
  if (awayScoreEl) awayScoreEl.textContent = away;
}

if (typeof on === 'function' && typeof emit === 'function') {
  on('score:update', updateScoreboardScores);
  emit('score:update', { home: 0, away: 0 });
} else {
  updateScoreboardScores({ home: 0, away: 0 });
}

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
const weekParam = parseInt(urlParams.get('week'), 10);
if (weekParam && !Number.isNaN(weekParam) && typeof localStorage !== 'undefined') {
  localStorage.setItem('franchise_week', weekParam);
}
const mode = urlParams.get('mode') || getMode({ tournamentId, franchiseId });
let quarter = parseInt(urlParams.get('quarter'), 10) || 1;
let gameId =
  urlParams.get('game_id') ||
  (typeof localStorage !== 'undefined' ? localStorage.getItem('game_id') : null);
let periodLabel = urlParams.get('period') || `Q${quarter}`;

const homeLineup = {};
const awayLineup = {};
['pg', 'sg', 'sf', 'pf', 'c'].forEach(pos => {
  const h = urlParams.get(`home_${pos}`);
  const a = urlParams.get(`away_${pos}`);
  if (h) homeLineup[pos.toUpperCase()] = h;
  if (a) awayLineup[pos.toUpperCase()] = a;
});

console.log("🏀 Tournament launch params:", {
  tournamentId,
  franchiseId,
  homeTeam,
  awayTeam,
  mode,
  periodLabel,
});

const GameScene = createGameScene(Phaser);
let game;
let isSimulating = false;

function showStatus(msg) {
  let el = document.getElementById('sim-status');
  if (!el) {
    el = document.createElement('div');
    el.id = 'sim-status';
    el.style.color = '#fff';
    el.style.fontFamily = 'Bebas Neue, sans-serif';
    const container = document.getElementById('phaser-container');
    if (container) container.appendChild(el);
  }
  el.textContent = msg;
}

function updateOffsets() {
  if (typeof document === 'undefined') return;
  const container = document.getElementById('phaser-container');
  if (!container || !container.getBoundingClientRect) return;
  const rect = container.getBoundingClientRect();
  setCourtOffsets(rect.left, rect.top);
}

if (typeof window !== 'undefined' && window.addEventListener) {
  window.addEventListener('resize', updateOffsets);
}

function resetGameContext() {
  gameId = null;
  quarter = 1;
  periodLabel = 'Q1';
  isSimulating = false;
  if (typeof localStorage !== 'undefined' && typeof localStorage.removeItem === 'function') {
    localStorage.removeItem('game_id');
  }
  gameStore.reset();
  updateScoreboardScores({ home: 0, away: 0 });
}


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
  DEBUG && console.log('[bootGame] startGame', { quarter, animate });
  gameStore.reset();
  gameStore.setTeams({ home: homeTeam, away: awayTeam });
  gameStore.setRosters({ home: homeRoster, away: awayRoster });
  gameStore.setColors({
    home: {
      primary_color: homeRoster.primary_color,
      secondary_color: homeRoster.secondary_color,
    },
    away: {
      primary_color: awayRoster.primary_color,
      secondary_color: awayRoster.secondary_color,
    },
  });
  gameStore.setGameId(gameId);
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
    tournamentId,
    franchiseId,
    animate,
    homeLineup,
    awayLineup,
    periodLabel,
    quarter,
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
  if (!gameId && typeof localStorage !== 'undefined') {
    gameId = localStorage.getItem('game_id');
  }
  const startingFresh = !gameId;
  if (startingFresh) {
    resetGameContext();
  }
  DEBUG && console.log('[handleButtonClick]', { startingFresh, quarter, gameId });
  isSimulating = true;
  const playBtn = document.querySelector('.play-button');
  const simFullBtn = document.querySelector('.sim-full-game-button');
  const sim4Btn = document.querySelector('.sim-to-fourth-button');
  if (playBtn) playBtn.style.display = 'none';
  if (simFullBtn) simFullBtn.style.display = 'none';
  if (sim4Btn) sim4Btn.style.display = 'none';

  try {
    if (DEBUG_TEAMS) {
      console.log('Fetching rosters for teams:', { homeTeam, awayTeam });
    }
    const [homeRoster, awayRoster] = await Promise.all([
      fetchTeamRoster(homeTeam),
      fetchTeamRoster(awayTeam),
    ]);
    console.log('startGame animate:', animate);
    const finalScore = await startGame({ homeRoster, awayRoster, animate });
    showPopup(finalScore);
  } catch (err) {
    console.error('Error starting game:', err);
  } finally {
    if (isSimulating) {
      isSimulating = false;
      if (playBtn) playBtn.style.display = '';
      if (simFullBtn) simFullBtn.style.display = '';
      if (sim4Btn && quarter < 4) sim4Btn.style.display = '';
    }
  }
}

async function handleSimToFourth() {
  if (isSimulating || quarter >= 4) return;
  if (!gameId && typeof localStorage !== 'undefined') {
    gameId = localStorage.getItem('game_id');
  }
  if (!gameId) {
    resetGameContext();
  }
  isSimulating = true;
  const playBtn = document.querySelector('.play-button');
  const simFullBtn = document.querySelector('.sim-full-game-button');
  const sim4Btn = document.querySelector('.sim-to-fourth-button');
  [playBtn, simFullBtn, sim4Btn].forEach(btn => { if (btn) btn.disabled = true; });

  try {
    let currentQ = quarter;
    let gId = gameId;
    let lastSummary;
      while (currentQ <= 3) {
        showStatus(`Simulating Q${currentQ}...`);
      const payload = {
        home_team: homeTeam,
        away_team: awayTeam,
        quarter: currentQ,
      };
      if (gId) payload.game_id = gId;
      if (currentQ === quarter) {
        if (Object.keys(homeLineup).length) payload.home_lineup = homeLineup;
        if (Object.keys(awayLineup).length) payload.away_lineup = awayLineup;
      }
      if (DEBUG_TEAMS) {
        console.log('/api/simulate-quarter payload teams:', {
          home: payload.home_team,
          away: payload.away_team,
        });
      }
      console.log({event:'simulate-quarter:request', mode, homeTeam, awayTeam, quarter: currentQ, gameId: gId});
      const res = await fetch('/api/simulate-quarter', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error('Simulation failed');
      lastSummary = await res.json();
      gId = lastSummary.game_id;
      currentQ += 1;
    }

    gameId = gId;
    quarter = 4;
    periodLabel = 'Q4';
    const params = new URLSearchParams(window.location.search);
    params.set('game_id', gameId);
    params.set('quarter', 4);
    params.set('period', 'Q4');
    ['home_pg','home_sg','home_sf','home_pf','home_c','away_pg','away_sg','away_sf','away_pf','away_c']
      .forEach(p => params.delete(p));
    window.history.replaceState({}, '', `${window.location.pathname}?${params.toString()}`);
    updateScoreboardScores({
      home: lastSummary.score[homeTeam] || 0,
      away: lastSummary.score[awayTeam] || 0,
    });
    const qEl = document.getElementById('quarter');
    if (qEl) qEl.textContent = 'Q:4';
    showStatus('Simulating Q1…Q2…Q3 complete. Ready for Q4. Press Play Quarter to proceed.');
  } catch (err) {
    console.error('Error simming to 4th quarter:', err);
    showStatus('Simulation failed. Please try again.');
  } finally {
    isSimulating = false;
    if (playBtn) playBtn.disabled = false;
    if (simFullBtn) simFullBtn.disabled = false;
    if (sim4Btn) sim4Btn.disabled = true;
  }
}

async function handleSimFullGame() {
  if (isSimulating) return;
  if (!gameId && typeof localStorage !== 'undefined') {
    gameId = localStorage.getItem('game_id');
  }
  if (!gameId) {
    resetGameContext();
  }
  isSimulating = true;
  const playBtn = document.querySelector('.play-button');
  const simFullBtn = document.querySelector('.sim-full-game-button');
  const sim4Btn = document.querySelector('.sim-to-fourth-button');
  [playBtn, simFullBtn, sim4Btn].forEach(btn => { if (btn) btn.disabled = true; });

  try {
    let currentQ = quarter;
    let gId = gameId;
    let lastSummary;
    while (true) {
      showStatus(`Simulating Q${currentQ}...`);
      const payload = {
        home_team: homeTeam,
        away_team: awayTeam,
        quarter: currentQ,
      };
      if (gId) payload.game_id = gId;
      if (currentQ === quarter) {
        if (Object.keys(homeLineup).length) payload.home_lineup = homeLineup;
        if (Object.keys(awayLineup).length) payload.away_lineup = awayLineup;
      }
      if (DEBUG_TEAMS) {
        console.log('/api/simulate-quarter payload teams:', {
          home: payload.home_team,
          away: payload.away_team,
        });
      }
      console.log({event:'simulate-quarter:request', mode, homeTeam, awayTeam, quarter: currentQ, gameId: gId});
      const res = await fetch('/api/simulate-quarter', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error('Simulation failed');
      lastSummary = await res.json();
      gId = lastSummary.game_id;
      if (lastSummary.is_final) break;
      currentQ += 1;
    }

    gameId = gId;
    quarter = lastSummary.quarter || currentQ;
    periodLabel = lastSummary.period_label || (quarter > 4 ? `OT${quarter - 4}` : `Q${quarter}`);

    const finalScore = await finalizeGame({ simData: lastSummary, tournamentId, franchiseId });
    showPopup(finalScore);
  } catch (err) {
    console.error('Error simming full game:', err);
    showStatus('Simulation failed. Please try again.');
    [playBtn, simFullBtn, sim4Btn].forEach(btn => { if (btn) btn.disabled = false; });
  } finally {
    isSimulating = false;
  }
}

function initGame() {
  const playBtn = document.querySelector('.play-button');
  const simFullBtn = document.querySelector('.sim-full-game-button');
  const sim4Btn = document.querySelector('.sim-to-fourth-button');
  if (playBtn) {
    playBtn.addEventListener('click', () => handleButtonClick(true));
  }
  if (simFullBtn) {
    simFullBtn.addEventListener('click', handleSimFullGame);
  }
  if (sim4Btn) {
    if (quarter >= 4) {
      sim4Btn.disabled = true;
      sim4Btn.title = 'Already in 4th quarter';
    } else {
      sim4Btn.addEventListener('click', handleSimToFourth);
    }
  }
}

initGame();
updateOffsets();

// new Phaser.Game(config);
