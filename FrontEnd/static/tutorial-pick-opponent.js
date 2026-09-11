/**
 * Tutorial Pick Opponent — Screen 4 of the FTE v3 funnel.
 *
 * Shows the user's seven conference rivals ranked most → least talented and lets
 * them choose who they debut against. Ranking is computed SERVER-SIDE
 * (GET /api/auth/tutorial-opponents) so the talent metric has one home — see the
 * warning on TUTORIAL_OPPONENT_TALENT_FIELD in auth_routes.py.
 *
 * This screen also OWNS GAME CREATION. FTE v3 moved init-game here from the
 * tip-off screen because the two screens that follow — Game Plan and Lineup —
 * both write through to the game doc and therefore need it to already exist.
 *
 * Flow:
 *   1. GET /api/auth/tutorial-opponents → ranked list + mid-table default
 *   2. User selects a card (default pre-selected)
 *   3. CONTINUE → POST /api/init-game (mode=tutorial) → creates the game doc
 *   4. POST /api/auth/tutorial-advance { step: 'set_lineup', opponent_pick, game_id }
 *   5. → /set-lineup.html?mode=tutorial&...&game_id=...
 *
 * The game_id is persisted on tutorial_state (not just the URL) so a refresh
 * resumes the SAME game instead of initialising a second one.
 */

import { showSammyModal } from '/js/shared/sammyModal.js';
import { playAdvance, playSelect } from '/js/shared/uiSfx.js';
import { mountTutorialProgress } from '/js/shared/tutorialProgressThread.js';

mountTutorialProgress('opponent');

const listEl = document.getElementById('opp-list');
const ctaEl = document.getElementById('opp-cta');
const errEl = document.getElementById('opp-error');
const eyebrowEl = document.getElementById('opp-eyebrow');

let opponents = [];
let selectedName = null;
let userTeam = null;

function setError(msg) {
  errEl.textContent = msg || '';
}

function authHeaders() {
  return Object.assign({ 'Content-Type': 'application/json' }, API_CONFIG.getAuthHeaders());
}

function renderCards() {
  listEl.innerHTML = '';
  opponents.forEach((team) => {
    const li = document.createElement('li');
    li.className = 'opp-card';
    li.dataset.name = team.name;
    li.tabIndex = 0;
    li.setAttribute('role', 'button');
    li.setAttribute('aria-pressed', String(team.name === selectedName));
    if (team.name === selectedName) li.classList.add('is-selected');
    // Team colors drive the card's left rail, matching the Pick Program card pattern.
    if (team.primary_color) li.style.setProperty('--opp-primary', team.primary_color);
    if (team.secondary_color) li.style.setProperty('--opp-secondary', team.secondary_color);

    li.innerHTML = [
      '<span class="opp-card__rank">', String(team.rank), '</span>',
      '<span class="opp-card__id">',
      '  <span class="opp-card__name"></span>',
      '  <span class="opp-card__mascot"></span>',
      '</span>',
      '<span class="opp-card__check" aria-hidden="true">&#10003;</span>',
    ].join('');
    // textContent, not innerHTML — team names are data.
    li.querySelector('.opp-card__name').textContent = team.name;
    li.querySelector('.opp-card__mascot').textContent = team.mascot || '';

    const choose = () => select(team.name);
    li.addEventListener('click', choose);
    li.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); choose(); }
    });
    listEl.appendChild(li);
  });
}

function select(name) {
  // click-tiny on every opponent tap (owner call: click-beep stays reserved for
  // committing to YOUR program, which is the weightier choice).
  if (name !== selectedName) playSelect();
  selectedName = name;
  Array.from(listEl.querySelectorAll('.opp-card')).forEach((el) => {
    const on = el.dataset.name === name;
    el.classList.toggle('is-selected', on);
    el.setAttribute('aria-pressed', String(on));
  });
  ctaEl.disabled = !name;
}

async function load() {
  try {
    const res = await fetch(API_CONFIG.buildUrl('/api/auth/tutorial-opponents'), {
      headers: authHeaders(),
    });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    opponents = data.opponents || [];
    userTeam = data.user_team || null;
    selectedName = data.default_opponent || (opponents[0] && opponents[0].name) || null;
    if (data.conference != null) {
      eyebrowEl.textContent = 'CONFERENCE ' + data.conference;
    }
    renderCards();
    ctaEl.disabled = !selectedName;
    showSammyModal({
      body: 'Pick your opponent. Top is toughest.',
      ctaLabel: 'GOT IT',
    });
  } catch (e) {
    console.error('[tutorial] opponents load failed:', e);
    listEl.innerHTML = '';
    setError('Could not load your conference. Refresh to try again.');
  }
}

/** Create the tutorial game doc. Returns game_id, or null on failure. */
async function initGame(opponent) {
  const res = await fetch(API_CONFIG.buildUrl('/api/init-game'), {
    method: 'POST',
    headers: authHeaders(),
    // The user is ALWAYS home in the tutorial game (fte_inject_state.md §1-§2).
    // Key is `user_team_side`, not `my_team` — init_game reads the former
    // (api.py:7419); the latter is the SET-LINEUP/court query param and is
    // silently ignored here, which would leave the tutorial nerf unassigned.
    body: JSON.stringify({
      home_team: userTeam,
      away_team: opponent,
      mode: 'tutorial',
      user_team_side: 'home',
    }),
  });
  if (!res.ok) {
    console.error('[tutorial] init-game failed:', res.status, await res.text().catch(() => ''));
    return null;
  }
  const data = await res.json();
  return data.game_id || null;
}

ctaEl.addEventListener('click', async () => {
  if (!selectedName) return;
  playAdvance();
  ctaEl.disabled = true;
  setError('');
  try {
    const gameId = await initGame(selectedName);
    if (!gameId) {
      setError('Could not start your game. Try again.');
      ctaEl.disabled = false;
      return;
    }
    const adv = await fetch(API_CONFIG.buildUrl('/api/auth/tutorial-advance'), {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ step: 'set_lineup', opponent_pick: selectedName, game_id: gameId }),
    });
    if (!adv.ok) throw new Error('advance HTTP ' + adv.status);

    // team_id is REQUIRED by game-plan.js and set-lineup.js in tutorial mode:
    // both resolve settings by it, and GET /api/gameplan 400s on a missing one
    // (it arrives as the literal string "null"). In tutorial/single mode the
    // team_id IS the team name — the backend resolves via gm.<team>.name.
    // Every downstream screen forwards the query string verbatim, so setting it
    // once here carries it through Lineup -> Game Plan -> Tip-off.
    const params = new URLSearchParams({
      mode: 'tutorial',
      home: userTeam,
      away: selectedName,
      my_team: 'home',
      team_id: userTeam,
      game_id: gameId,
    });
    window.location.href = '/set-lineup.html?' + params.toString();
  } catch (e) {
    console.error('[tutorial] advance failed:', e);
    setError('Something went wrong. Try again.');
    ctaEl.disabled = false;
  }
});

load();
