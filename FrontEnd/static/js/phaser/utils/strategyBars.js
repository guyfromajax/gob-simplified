/**
 * Scoreboard strategy stacks — tempo / aggression / alterations (display only).
 * Markup + CSS in court.html; updated each turn from turn payload + simData.teams.
 */

const SB_TIER = { yellow: '#F2C744', green: '#46C06A', blue: '#4A90D9' };

const SB_TEMPO = {
  slow: { pct: 10, hue: 'yellow', word: 'SLOW' },
  normal: { pct: 50, hue: 'green', word: 'NORMAL' },
  fast: { pct: 90, hue: 'blue', word: 'FAST' },
};

const SB_AGGR = {
  passive: { pct: 10, hue: 'yellow', word: 'PASSIVE' },
  normal: { pct: 50, hue: 'green', word: 'NORMAL' },
  aggressive: { pct: 90, hue: 'blue', word: 'AGGR' },
};

const SB_ALT = {
  0: { pct: 10, hue: 'yellow', word: 'LEAST' },
  1: { pct: 30, hue: 'yellow', word: 'LESS' },
  2: { pct: 50, hue: 'green', word: 'NORMAL' },
  3: { pct: 70, hue: 'green', word: 'MORE' },
  4: { pct: 90, hue: 'blue', word: 'MOST' },
};

const SB_ROWS = [
  { key: 'tempo', lab: 'TEMPO', map: SB_TEMPO },
  { key: 'aggr', lab: 'AGGR', map: SB_AGGR },
  { key: 'alt', lab: 'ALT', map: SB_ALT },
];

const SB_STOPS = [10, 30, 50, 70, 90];

let stacksBuilt = false;
let stacksRevealed = false;

function normalizeCall(raw, map) {
  if (raw == null || raw === '') return null;
  const key = String(raw).trim().toLowerCase();
  return map[key] ? key : null;
}

function normalizeAlterations(raw) {
  const n = Number(raw);
  if (!Number.isFinite(n)) return 2;
  return Math.max(0, Math.min(4, Math.round(n)));
}

function buildStrategyStack(side) {
  const el = document.getElementById(`sb-strat-${side}`);
  if (!el) return;
  el.innerHTML = '';
  SB_ROWS.forEach((r) => {
    const row = document.createElement('div');
    row.className = 'srow';
    row.dataset.row = r.key;

    const lab = document.createElement('div');
    lab.className = 'lab';
    lab.textContent = r.lab;

    const rail = document.createElement('div');
    rail.className = 'rail';
    const track = document.createElement('div');
    track.className = 'track';
    SB_STOPS.forEach((p) => {
      const pos = side === 'home' ? 100 - p : p;
      const tick = document.createElement('div');
      tick.className = 'tick';
      tick.style.left = `${pos}%`;
      track.appendChild(tick);
    });
    const marker = document.createElement('div');
    marker.className = 'marker';
    rail.append(track, marker);

    const val = document.createElement('div');
    val.className = 'val';

    row.append(lab, rail, val);
    el.appendChild(row);
  });
}

function ensureStacksBuilt() {
  if (stacksBuilt) return;
  buildStrategyStack('away');
  buildStrategyStack('home');
  stacksBuilt = true;
}

function revealStacks() {
  if (stacksRevealed) return;
  ['away', 'home'].forEach((side) => {
    const el = document.getElementById(`sb-strat-${side}`);
    if (!el) return;
    el.classList.add('is-visible');
    el.setAttribute('aria-hidden', 'false');
  });
  stacksRevealed = true;
}

function updateStrategyStack(side, values) {
  if (!values) return;
  ensureStacksBuilt();
  const el = document.getElementById(`sb-strat-${side}`);
  if (!el) return;

  const lookup = {
    tempo: SB_TEMPO[values.tempo],
    aggr: SB_AGGR[values.aggression],
    alt: SB_ALT[values.alterations],
  };

  SB_ROWS.forEach((r) => {
    const def = lookup[r.key];
    if (!def) return;
    const row = el.querySelector(`[data-row="${r.key}"]`);
    if (!row) return;
    const marker = row.querySelector('.marker');
    const val = row.querySelector('.val');
    if (!marker || !val) return;
    const color = SB_TIER[def.hue];
    const leftPct = side === 'home' ? 100 - def.pct : def.pct;
    marker.style.left = `${leftPct}%`;
    marker.style.background = color;
    marker.style.boxShadow = `0 0 10px ${color}cc`;
    val.textContent = def.word;
    val.style.color = color;
  });
}

function resolveSideValues(turnData, homeTeamId, awayTeamId, simData, side) {
  const isHome = side === 'home';
  const teamId = isHome ? homeTeamId : awayTeamId;
  const offenseTeamId = turnData?.possession_team_id ?? turnData?.offense_team_id;
  const isOnOffense = teamId != null && offenseTeamId != null
    && String(offenseTeamId) === String(teamId);

  let tempoRaw;
  let aggrRaw;
  if (isOnOffense) {
    tempoRaw = turnData.offense_tempo_call;
    aggrRaw = turnData.offense_aggression_call;
  } else {
    tempoRaw = turnData.defense_tempo_call;
    aggrRaw = turnData.defense_aggression_call;
  }

  const tempo = normalizeCall(tempoRaw, SB_TEMPO) || 'normal';
  const aggression = normalizeCall(aggrRaw, SB_AGGR) || 'normal';

  const teamsObj = simData?.teams || {};
  const teamRow = teamId != null ? (teamsObj[teamId] || teamsObj[String(teamId)]) : null;
  const alterations = normalizeAlterations(teamRow?.strategy_settings?.alterations);

  return { tempo, aggression, alterations };
}

function turnHasStrategyCalls(turnData) {
  return Boolean(
    turnData?.offense_tempo_call
    && turnData?.offense_aggression_call
    && turnData?.defense_tempo_call
    && turnData?.defense_aggression_call,
  );
}

/**
 * Update scoreboard strategy stacks for both teams.
 * Hidden until the first turn that carries all four strategy call fields.
 *
 * @param {Object} turnData
 * @param {string} homeTeamId
 * @param {Object} [simData] — game doc; alterations read from teams[teamId].strategy_settings
 */
export function updateStrategyBars(turnData, homeTeamId, simData = null) {
  if (!turnHasStrategyCalls(turnData)) {
    return;
  }

  const awayTeamId = simData?.away_team_id ?? null;

  revealStacks();

  updateStrategyStack('away', resolveSideValues(turnData, homeTeamId, awayTeamId, simData, 'away'));
  updateStrategyStack('home', resolveSideValues(turnData, homeTeamId, awayTeamId, simData, 'home'));
}
