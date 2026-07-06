import { animateGameTurns } from './animation/animateGameTurns.js?v=uess-timeline-probes-1';
import { playGameplayTrack, pauseGameplayTrack, resumeGameplayTrack, evaluateGameplayTrack } from '../musicController.js';
import { syncSceneTimePaused } from './animation/playbackPause.js';
import { loadPhaserPlayers } from './setup/loadPhaserPlayers.js';
import { preloadPlayerHeadshots } from './setup/preloadPlayerHeadshots.js';
import { gridToPixels } from './utils/gridToPixels.js';
import { finalizeGame } from './finalizeGame.js';
import { emit } from './utils/eventBus.js';
import { appendToTextScroll } from './utils/textScroll.js';
import { DEBUG } from './utils/debug.js';
import { createGameStateMachine, States } from './state/gameStateMachine.js';
import { initializePossessionManager } from './utils/possessionManager.js';
import gameStore from '../state/gameStore.js';
import { animateCountdownTransition } from './animation/countdownAnimation.js';
import { ENABLE_TIMEOUT_BUTTON, initTimeoutButton } from './utils/timeoutButtonManager.js';
import { createGameClock, parseClockToSeconds } from './utils/gameClock.js';
import { syncSpriteAttributesFromPlayerEnergy } from './utils/syncPlayerSpriteAttributes.js';
import { showSecondaryAnnouncement, getSecondaryColorForTeam } from './utils/announcements.js';
import { resolveTeamsSlotLookupKey } from './utils/loadGameStats.js';
import { getGameMode } from '../shared/getGameMode.js';

const DEBUG_SIM_PAYLOAD =
  (typeof window !== 'undefined' && window.DEBUG_SIM_PAYLOAD) ||
  (typeof process !== 'undefined' && process.env.DEBUG_SIM_PAYLOAD) ||
  false;
const DEBUG_TEAMS =
  (typeof window !== 'undefined' && window.DEBUG_TEAMS) ||
  (typeof process !== 'undefined' && process.env.DEBUG_TEAMS) ||
  false;
const DEBUG_SERIALIZATION =
  (typeof window !== 'undefined' && window.DEBUG_SERIALIZATION) ||
  (typeof process !== 'undefined' && process.env.DEBUG_SERIALIZATION) ||
  false;
const DEBUG_FLOW =
  (typeof window !== 'undefined' && window.DEBUG_FLOW) ||
  (typeof process !== 'undefined' && process.env.DEBUG_FLOW) ||
  false;
const DEBUG_SKIP =
  (typeof window !== 'undefined' && window.DEBUG_SKIP) ||
  (typeof process !== 'undefined' && process.env.DEBUG_SKIP) ||
  false;

function getUessTimingDiagnostics() {
  if (typeof window === 'undefined') return null;
  if (!window.__UESS_TIMING_DIAGNOSTICS__) {
    window.__UESS_TIMING_DIAGNOSTICS__ = {
      pauseStartedAtMs: null,
      pauseAccumulatedMs: 0,
      hiddenStartedAtMs: null,
      hiddenAccumulatedMs: 0,
      pauseTransitions: 0,
      visibilityTransitions: 0,
      lastPauseTransitionAtMs: null,
      lastVisibilityTransitionAtMs: null,
      pauseIntervals: [],
      hiddenIntervals: [],
    };
  }
  return window.__UESS_TIMING_DIAGNOSTICS__;
}

function setUessTimingState(kind, active) {
  const diagnostics = getUessTimingDiagnostics();
  if (!diagnostics) return;
  const now = Date.now();
  const startKey = kind === 'pause' ? 'pauseStartedAtMs' : 'hiddenStartedAtMs';
  const accumulatedKey =
    kind === 'pause' ? 'pauseAccumulatedMs' : 'hiddenAccumulatedMs';
  const transitionsKey =
    kind === 'pause' ? 'pauseTransitions' : 'visibilityTransitions';
  const lastTransitionKey =
    kind === 'pause' ? 'lastPauseTransitionAtMs' : 'lastVisibilityTransitionAtMs';

  if (active && diagnostics[startKey] == null) {
    diagnostics[startKey] = now;
    diagnostics[transitionsKey] += 1;
    diagnostics[lastTransitionKey] = now;
  } else if (!active && diagnostics[startKey] != null) {
    const interval = {
      startMs: diagnostics[startKey],
      endMs: now,
    };
    diagnostics[accumulatedKey] += Math.max(0, interval.endMs - interval.startMs);
    const intervalsKey = kind === 'pause' ? 'pauseIntervals' : 'hiddenIntervals';
    if (!Array.isArray(diagnostics[intervalsKey])) {
      diagnostics[intervalsKey] = [];
    }
    diagnostics[intervalsKey].push(interval);
    if (diagnostics[intervalsKey].length > 100) {
      diagnostics[intervalsKey].splice(
        0,
        diagnostics[intervalsKey].length - 100
      );
    }
    diagnostics[startKey] = null;
    diagnostics[transitionsKey] += 1;
    diagnostics[lastTransitionKey] = now;
  }
}

if (
  typeof document !== 'undefined' &&
  typeof window !== 'undefined' &&
  !window.__UESS_VISIBILITY_DIAGNOSTICS_INSTALLED__
) {
  window.__UESS_VISIBILITY_DIAGNOSTICS_INSTALLED__ = true;
  setUessTimingState('hidden', document.hidden === true);
  document.addEventListener('visibilitychange', () => {
    setUessTimingState('hidden', document.hidden === true);
  });
}

/** URL flag: ?debug_pc=1|true|yes — forwards to API so Railway logs without DEBUG_PC env. */
function isDebugPlaycall() {
  if (typeof window === 'undefined') return false;
  try {
    if (typeof window.isDebugPlaycallSearch === 'function') {
      return window.isDebugPlaycallSearch(window.location.search);
    }
    const v = (new URLSearchParams(window.location.search).get('debug_pc') || '').trim().toLowerCase();
    return v === '1' || v === 'true' || v === 'yes';
  } catch (e) {
    return false;
  }
}

function resolvePrimaryHexFromTeamColors(colors) {
  if (!colors) return null;
  if (typeof colors === 'string') return colors;
  return (
    colors.primary_color ||
    colors.primary ||
    colors.Primary ||
    colors.primaryColor ||
    null
  );
}

function hexToRgbTripletString(hex) {
  if (!hex || typeof hex !== 'string') return null;
  let h = hex.trim();
  if (h.startsWith('#')) h = h.slice(1);
  if (h.length === 3) {
    h = h.split('').map((c) => c + c).join('');
  }
  if (h.length !== 6) return null;
  const n = parseInt(h, 16);
  if (!Number.isFinite(n)) return null;
  return `${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}`;
}

function applyVibrantRgbDocumentVarsFromTeamColors(homeColors, awayColors) {
  if (typeof document === 'undefined') return;
  const hh = hexToRgbTripletString(resolvePrimaryHexFromTeamColors(homeColors));
  const ah = hexToRgbTripletString(resolvePrimaryHexFromTeamColors(awayColors));
  if (hh) {
    document.documentElement.style.setProperty('--home-vibrant-rgb', hh);
  }
  if (ah) {
    document.documentElement.style.setProperty('--away-vibrant-rgb', ah);
  }
}

/** Playcall cockpit uses `.pcc-pause-text`; legacy controls used `textContent` only. */
function syncPauseButtonDom(isPaused) {
  if (typeof document === 'undefined') return;
  const el = document.getElementById('pause-btn');
  if (!el) return;
  const label = el.querySelector('.pcc-pause-text');
  if (label) {
    label.textContent = isPaused ? 'RESUME' : 'PAUSE';
    el.classList.toggle('paused', !!isPaused);
  } else {
    el.textContent = isPaused ? 'Resume' : 'Pause';
  }
}

// Team Momentum frontend range — mirrors BackEnd MO_TEAM_MAX (= 5 × MO_MAX).
// Keep in sync with BackEnd/constants/momentum.py (Player_Momentum_System.md).
const MO_TEAM_MAX_FE = 25;

function updateMomentumBar(teamSide, value) {
  const negEl = document.getElementById(`${teamSide}-momentum-neg`);
  const posEl = document.getElementById(`${teamSide}-momentum-pos`);
  if (!negEl || !posEl) return;
  // Sticky: a null/undefined value means "this update carried no momentum info"
  // (e.g. a tween onUpdate frame or a partial scoreboard payload). Leave the bar
  // exactly as it was rather than blanking it to 0. A real 0 still paints empty.
  if (value === null || value === undefined) return;
  const v = Math.max(-MO_TEAM_MAX_FE, Math.min(MO_TEAM_MAX_FE, Number(value) || 0));
  const pct = Math.abs(v) / MO_TEAM_MAX_FE * 50; // rail fills the half-bar (50% of container)
  if (v < 0) {
    negEl.style.width = `${pct}%`;
    posEl.style.width = '0%';
  } else if (v > 0) {
    posEl.style.width = `${pct}%`;
    negEl.style.width = '0%';
  } else {
    negEl.style.width = '0%';
    posEl.style.width = '0%';
  }
}

/** Box-score momentum glyphs — inline SVG with explicit fills (independent of
 *  the energy-driven name color). Material "whatshot" flame + "ac_unit" snowflake. */
function moFlameSvg() {
  // Gold fill (solid flame, behind) + orange flame ring (whatshot, in front).
  // Both share the same outer edge, so gold fills the interior and orange
  // reads as the border — the hollow center of the whatshot path shows gold.
  return '<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true" focusable="false">'
    + '<path fill="#FFD23F" d="M13.5.67s.74 2.65.74 4.8c0 2.06-1.35 3.73-3.41 3.73-2.07 0-3.63-1.67-3.63-3.73l.03-.36C5.21 7.51 4 10.62 4 14c0 4.42 3.58 8 8 8s8-3.58 8-8C20 8.61 17.41 3.8 13.5.67z"/>'
    + '<path fill="#FF9A2E" d="M13.5.67s.74 2.65.74 4.8c0 2.06-1.35 3.73-3.41 3.73-2.07 0-3.63-1.67-3.63-3.73l.03-.36C5.21 7.51 4 10.62 4 14c0 4.42 3.58 8 8 8s8-3.58 8-8C20 8.61 17.41 3.8 13.5.67zM11.71 19c-1.78 0-3.22-1.4-3.22-3.14 0-1.62 1.05-2.76 2.81-3.12 1.77-.36 3.6-1.21 4.62-2.58.39 1.29.59 2.65.59 4.04 0 2.65-2.15 4.8-4.8 4.8z"/>'
    + '</svg>';
}
function moSnowflakeSvg() {
  return '<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true" focusable="false">'
    + '<path fill="#A6ECFF" d="M22 11h-4.17l3.24-3.24-1.41-1.42L15 11h-2V9l4.66-4.66-1.42-1.41L13 6.17V2h-2v4.17L7.76 2.93 6.34 4.34 11 9v2H9L4.34 6.34 2.93 7.76 6.17 11H2v2h4.17l-3.24 3.24 1.41 1.42L9 13h2v2l-4.66 4.66 1.42 1.41L11 17.83V22h2v-4.17l3.24 3.24 1.42-1.41L13 15v-2h2l4.66 4.66 1.41-1.42L17.83 13H22z"/>'
    + '</svg>';
}
// Momentum display thresholds (±5 MO scale — Player_Momentum_System.md).
const MO_GLYPH_THRESHOLD = 4;   // box-score flame/snowflake at |MO| >= 4
const MO_WARM_MAG = 3;          // callout warm at |MO| == 3; hot at |MO| 4 and 5

/** Show/hide a box-score momentum glyph: flame at MO>=+4, snowflake at MO<=-4, else hidden. */
function setBoxScoreMoGlyph(glyphEl, mo) {
  if (!glyphEl) return;
  const v = Number(mo) || 0;
  if (v >= MO_GLYPH_THRESHOLD) {
    glyphEl.innerHTML = moFlameSvg();
    glyphEl.style.display = 'inline-flex';
  } else if (v <= -MO_GLYPH_THRESHOLD) {
    glyphEl.innerHTML = moSnowflakeSvg();
    glyphEl.style.display = 'inline-flex';
  } else if (glyphEl.style.display !== 'none') {
    glyphEl.innerHTML = '';
    glyphEl.style.display = 'none';
  }
}

/** Momentum secondary-callout headline: warm at |MO|==3, hot/cold at >=4 (±5 scale). */
function momentumCalloutHeadline(sign, mag) {
  const hot = sign > 0;
  if (mag <= MO_WARM_MAG) return hot ? 'Getting Warm!' : 'Getting Cold!';
  return hot ? 'Red Hot!' : 'Ice Cold!';
}
/** True if the secondary ribbon is currently showing/exiting — momentum callouts
 *  are lowest priority and YIELD (drop) to any other secondary announcement. */
function isSecondaryRibbonBusy() {
  if (typeof document === 'undefined') return false;
  const overlay = document.getElementById('announcement-overlay-secondary');
  return !!(overlay && !overlay.classList.contains('hidden'));
}
/** Fire a momentum callout through the existing secondary ribbon (silent).
 *  Drops if any other secondary announcement is showing. */
function fireMomentumCallout(scene, playerId, teamSide, sign, mo) {
  if (isSecondaryRibbonBusy()) return;
  const sprite = scene.playerSprites?.[playerId];
  const playerData = sprite
    ? {
        playerId,
        photo: sprite.photo || null,
        teamName: sprite.team_id,
        secondaryColor: getSecondaryColorForTeam(scene, sprite.team_id),
      }
    : { playerId };
  const headline = momentumCalloutHeadline(sign, Math.abs(mo));
  showSecondaryAnnouncement(headline, teamSide, playerData, {
    moValue: mo,
    moFlavor: sign > 0 ? 'hot' : 'cold',
    sfx: null, // silent for now (no SFX hook)
  });
}

/** Solid left-pointing chevron (offense advantage); currentColor fill */
function pcsEvSvgChevronLeftSolid() {
  return '<svg viewBox="0 0 10 12" width="10" height="12" aria-hidden="true"><path fill="currentColor" d="M8.6 1.2L8.6 10.8L1.2 6z"/></svg>';
}

/** Solid right-pointing chevron (defense advantage) */
function pcsEvSvgChevronRightSolid() {
  return '<svg viewBox="0 0 10 12" width="10" height="12" aria-hidden="true"><path fill="currentColor" d="M1.4 1.2L1.4 10.8L8.8 6z"/></svg>';
}

/** Hollow chevron, tip points left */
function pcsEvSvgChevronLeftHollow() {
  return '<svg viewBox="0 0 10 12" width="10" height="12" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="1.1" stroke-linejoin="miter" d="M8.4 1.8L8.4 10.2L1.8 6z"/></svg>';
}

/** Hollow chevron, tip points right */
function pcsEvSvgChevronRightHollow() {
  return '<svg viewBox="0 0 10 12" width="10" height="12" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="1.1" stroke-linejoin="miter" d="M1.6 1.8L1.6 10.2L8.2 6z"/></svg>';
}

/** Fixed center pivot label + hairline ticks (meter metaphor). */
function pcsEvPivotMarkup(withZeroPercent) {
  const ticksAndLabel = `<span class="pcs-ev-pivot-tick" aria-hidden="true"></span><span class="pcs-ev-pivot-label">EV</span><span class="pcs-ev-pivot-tick" aria-hidden="true"></span>`;
  if (withZeroPercent) {
    return `<div class="pcs-ev-pivot pcs-ev-pivot--with-zero"><div class="pcs-ev-pivot-mark" aria-hidden="true">${ticksAndLabel}</div><span class="pcs-ev-num pcs-ev-num--zero-pivot">0%</span></div>`;
  }
  return `<div class="pcs-ev-pivot" aria-hidden="true"><div class="pcs-ev-pivot-mark">${ticksAndLabel}</div></div>`;
}

function pcsEvAxisColor(evInt) {
  if (evInt > 0) return '#34EC27';
  if (evInt < 0) return '#ff4444';
  return '';
}

function applyPcsEvAxisColor(el, axisColor) {
  const previousAxisColor = el.dataset.evAxisColor || '';
  if (previousAxisColor) {
    el.style.setProperty('--ev-axis-color', previousAxisColor);
  } else {
    el.style.removeProperty('--ev-axis-color');
  }
  void el.offsetWidth;
  requestAnimationFrame(() => {
    if (axisColor) {
      el.style.setProperty('--ev-axis-color', axisColor);
    } else {
      el.style.removeProperty('--ev-axis-color');
    }
    el.dataset.evAxisColor = axisColor;
  });
}

/**
 * HCO playcall strip: dual chevron rows + fixed "EV" pivot + signed % (presentation only).
 * EV is clamped to [-100, 100]; lit count per side = round(|EV|/10), 0–10.
 * Left row: ◀ lit when offense advantage; right row: ▶ lit when defense advantage.
 */
function renderPlaycallEvMeter(el, ev) {
  if (!el) return;
  const evNum = parseFloat(ev);
  if (!Number.isFinite(evNum)) {
    el.className = 'pcs-ev-meter pcs-ev-meter--na';
    el.setAttribute('aria-label', 'Expected value not available');
    el.innerHTML = '<span class="pcs-ev-num">--</span>';
    applyPcsEvAxisColor(el, '');
    return;
  }
  const evInt = Math.max(-100, Math.min(100, Math.round(evNum)));
  const axisColor = pcsEvAxisColor(evInt);
  const nLit = Math.min(10, Math.max(0, Math.round(Math.abs(evInt) / 10)));
  let label = 'Even expected value';
  if (evInt > 0) label = `Offense advantage, ${evInt} percent`;
  else if (evInt < 0) label = `Defense advantage, ${evInt} percent`;
  el.setAttribute('aria-label', label);

  const numTextPos = evInt > 0 ? `+${evInt}%` : '';
  const numTextNeg = evInt < 0 ? `${evInt}%` : '';

  const triggerEnter = () => {
    el.classList.remove('pcs-ev-meter--enter');
    void el.offsetWidth;
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        el.classList.add('pcs-ev-meter--enter');
      });
    });
  };

  const slotLeft = (inner) =>
    `<span class="pcs-ev-num-slot pcs-ev-num-slot--left">${inner}</span>`;
  const slotRight = (inner) =>
    `<span class="pcs-ev-num-slot pcs-ev-num-slot--right">${inner}</span>`;

  if (evInt === 0) {
    const leftRow = Array.from({ length: 10 }, () => {
      return `<span class="pcs-ev-slot pcs-ev-slot--neu" aria-hidden="true">${pcsEvSvgChevronLeftHollow()}</span>`;
    }).join('');
    const rightRow = Array.from({ length: 10 }, () => {
      return `<span class="pcs-ev-slot pcs-ev-slot--neu" aria-hidden="true">${pcsEvSvgChevronRightHollow()}</span>`;
    }).join('');
    el.className = 'pcs-ev-meter pcs-ev-meter--zero';
    el.innerHTML = `${slotLeft('')}${`<div class="pcs-ev-chevron-row pcs-ev-chevron-row--left" aria-hidden="true">${leftRow}</div>`}${pcsEvPivotMarkup(true)}${`<div class="pcs-ev-chevron-row pcs-ev-chevron-row--right" aria-hidden="true">${rightRow}</div>`}${slotRight('')}`;
    applyPcsEvAxisColor(el, axisColor);
    triggerEnter();
    return;
  }

  if (evInt > 0) {
    const leftParts = [];
    for (let i = 0; i < 10; i++) {
      const lit = i >= 10 - nLit;
      const litOrder = lit ? 9 - i : -1;
      const delayMs =
        lit && nLit > 1 ? Math.round((litOrder / (nLit - 1)) * 200) : 0;
      const style = lit ? ` style="--pcs-ev-d:${delayMs}ms"` : '';
      const glyph = lit ? pcsEvSvgChevronLeftSolid() : pcsEvSvgChevronRightHollow();
      leftParts.push(
        `<span class="pcs-ev-slot${lit ? ' is-lit' : ''}"${style} aria-hidden="true">${glyph}</span>`
      );
    }
    const rightParts = Array.from({ length: 10 }, () => {
      return `<span class="pcs-ev-slot" aria-hidden="true">${pcsEvSvgChevronRightHollow()}</span>`;
    });
    el.className = 'pcs-ev-meter pcs-ev-meter--pos';
    el.innerHTML = `${slotLeft(`<span class="pcs-ev-num">${numTextPos}</span>`)}<div class="pcs-ev-chevron-row pcs-ev-chevron-row--left" aria-hidden="true">${leftParts.join('')}</div>${pcsEvPivotMarkup(false)}<div class="pcs-ev-chevron-row pcs-ev-chevron-row--right" aria-hidden="true">${rightParts.join('')}</div>${slotRight('')}`;
    applyPcsEvAxisColor(el, axisColor);
    triggerEnter();
    return;
  }

  const leftPartsNeg = Array.from({ length: 10 }, () => {
    return `<span class="pcs-ev-slot" aria-hidden="true">${pcsEvSvgChevronLeftHollow()}</span>`;
  });
  const rightParts = [];
  for (let i = 0; i < 10; i++) {
    const lit = i < nLit;
    const delayMs = lit && nLit > 1 ? Math.round((i / (nLit - 1)) * 200) : 0;
    const style = lit ? ` style="--pcs-ev-d:${delayMs}ms"` : '';
    const glyph = lit ? pcsEvSvgChevronRightSolid() : pcsEvSvgChevronLeftHollow();
    rightParts.push(
      `<span class="pcs-ev-slot${lit ? ' is-lit' : ''}"${style} aria-hidden="true">${glyph}</span>`
    );
  }
  el.className = 'pcs-ev-meter pcs-ev-meter--neg';
  el.innerHTML = `${slotLeft('')}<div class="pcs-ev-chevron-row pcs-ev-chevron-row--left" aria-hidden="true">${leftPartsNeg.join('')}</div>${pcsEvPivotMarkup(false)}<div class="pcs-ev-chevron-row pcs-ev-chevron-row--right" aria-hidden="true">${rightParts.join('')}</div>${slotRight(`<span class="pcs-ev-num">${numTextNeg}</span>`)}`;
  applyPcsEvAxisColor(el, axisColor);
  triggerEnter();
}

function showPlaycallStrip(offensePlay, offenseTarget, defensePlay, ev) {
  const strip = document.getElementById('playcall-strip');
  if (!strip) return;
  const oPlay = document.getElementById('pcs-offense-play');
  const oTgt = document.getElementById('pcs-offense-target');
  const dPlay = document.getElementById('pcs-defense-play');
  const evEl = document.getElementById('pcs-ev');
  if (oPlay) oPlay.textContent = offensePlay || '--';
  if (oTgt) oTgt.textContent = offenseTarget != null && String(offenseTarget).length ? String(offenseTarget) : '';
  if (dPlay) dPlay.textContent = defensePlay || '--';
  if (evEl) renderPlaycallEvMeter(evEl, ev);
  strip.classList.remove('hidden');
}

function hidePlaycallStrip() {
  const strip = document.getElementById('playcall-strip');
  if (strip) strip.classList.add('hidden');
}

if (typeof window !== 'undefined' && !window.__gobPlaycallStripListenersInstalled) {
  window.__gobPlaycallStripListenersInstalled = true;
  window.addEventListener('gob:playcall-strip-show', (event) => {
    const detail = event?.detail || {};
    showPlaycallStrip(detail.offensePlay, detail.offenseTarget, detail.defensePlay, detail.ev);
  });
  window.addEventListener('gob:playcall-strip-hide', hidePlaycallStrip);
}

function syncShotClockCriticalClass(shotSeconds) {
  const el = document.getElementById('shot-clock');
  if (!el) return;
  if (shotSeconds == null || !Number.isFinite(Number(shotSeconds))) {
    el.classList.remove('critical');
    return;
  }
  el.classList.toggle('critical', Number(shotSeconds) < 7);
}

function updateTimeoutPipsUsedCount(remainingTimeouts, maxTimeouts = 4) {
  const pipWrap = document.getElementById('timeout-pips');
  if (!pipWrap) return;
  const rem = Math.max(0, Math.floor(Number(remainingTimeouts) || 0));
  const used = Math.max(0, Math.min(maxTimeouts, maxTimeouts - rem));
  pipWrap.querySelectorAll('.to-pip').forEach((pip, i) => {
    pip.classList.toggle('used', i < used);
  });
}

function formatSbRank(teamObj) {
  const r = Number(teamObj?.natl_rank);
  if (Number.isInteger(r) && r >= 1) return `#${r}`;
  return '#--';
}

function formatSbRecord(teamObj) {
  const w = teamObj?.wins ?? teamObj?.team_wins;
  const l = teamObj?.losses ?? teamObj?.team_losses;
  if (w == null || l == null) return '--';
  const wn = Number(w);
  const ln = Number(l);
  if (Number.isFinite(wn) && Number.isFinite(ln)) {
    return `${wn}-${ln}`;
  }
  return '--';
}

/**
 * Resolve unified `teams[id]` row for scoreboard rank/record. Keys on `teams` may not
 * strictly equal `home_team_id` (string/ObjectId); legacy `home_team` / `away_team`
 * may carry natl_rank without a matching teams row.
 */
function resolveTeamRowForScoreboard(simData, side) {
  if (!simData || typeof simData !== 'object') return null;
  const teamsObj = simData.teams || {};
  const storedId = side === 'home' ? simData.home_team_id : simData.away_team_id;
  const legacy = side === 'home' ? simData.home_team : simData.away_team;
  const legacyObj = typeof legacy === 'object' && legacy != null ? legacy : null;
  let urlHome = null;
  let urlAway = null;
  try {
    if (typeof window !== 'undefined') {
      const sp = new URLSearchParams(window.location.search);
      urlHome = sp.get('home_id');
      urlAway = sp.get('away_id');
    }
  } catch (e) {
    /* ignore */
  }
  const urlId = side === 'home' ? urlHome : urlAway;
  const resolvedKey = resolveTeamsSlotLookupKey(teamsObj, storedId, urlId, legacyObj);
  const id = resolvedKey != null && resolvedKey !== '' ? resolvedKey : storedId;

  let row = null;
  if (id != null && id !== '') {
    const idStr = String(id);
    if (teamsObj[idStr]) row = teamsObj[idStr];
    if (!row && teamsObj[id]) row = teamsObj[id];
    if (!row) {
      for (const k of Object.keys(teamsObj)) {
        if (String(k) === idStr) {
          row = teamsObj[k];
          break;
        }
      }
    }
    if (!row) {
      for (const k of Object.keys(teamsObj)) {
        const t = teamsObj[k];
        if (t && String(t.team_id) === idStr) {
          row = t;
          break;
        }
      }
    }
  }

  let out = null;
  if (row && legacyObj) out = { ...legacyObj, ...row };
  else if (row) out = row;
  else out = legacyObj;

  let nameKey = null;
  try {
    if (typeof window !== 'undefined') {
      const sp = new URLSearchParams(window.location.search);
      nameKey = side === 'home' ? sp.get('home') : sp.get('away');
    }
  } catch (e) {
    /* ignore */
  }
  const tsm = simData.team_scoreboard_meta;
  let snap = null;
  if (nameKey && tsm && typeof tsm === 'object') {
    snap = tsm[nameKey] || null;
    if (!snap) {
      const nk = String(nameKey).trim();
      let found = Object.keys(tsm).find((x) => String(x).trim() === nk);
      if (!found) found = Object.keys(tsm).find((x) => String(x).trim().toLowerCase() === nk.toLowerCase());
      if (found) snap = tsm[found];
    }
  }
  if (out && snap) return { ...out, ...snap };
  if (snap) return { ...(typeof out === 'object' && out ? out : {}), ...snap };
  return out;
}

/** Append `&debug_scoreboard=1` to the court URL to log rank/record resolution and DOM-bound strings. */
function isCourtDebugScoreboard() {
  try {
    return typeof window !== 'undefined' && new URLSearchParams(window.location.search).get('debug_scoreboard') === '1';
  } catch (e) {
    return false;
  }
}

function momentumValueForTeam(teamObj, turn, side) {
  const fromTurn =
    side === 'home'
      ? Number(turn?.home_momentum_bar ?? turn?.home_momentum ?? turn?.home_team_momentum)
      : Number(turn?.away_momentum_bar ?? turn?.away_momentum ?? turn?.away_team_momentum);
  if (Number.isFinite(fromTurn)) {
    return Math.max(-MO_TEAM_MAX_FE, Math.min(MO_TEAM_MAX_FE, fromTurn));
  }
  // Derived Team Momentum (−25..+25) from the game summary team object —
  // used for the initial render / resume when the turn lacks the stamp.
  const fromTeam = Number(teamObj?.team_momentum);
  if (Number.isFinite(fromTeam)) {
    return Math.max(-MO_TEAM_MAX_FE, Math.min(MO_TEAM_MAX_FE, fromTeam));
  }
  const attrs = teamObj?.attributes || teamObj?.team_attributes || {};
  const m = Number(attrs.momentum ?? teamObj?.momentum_score);
  if (Number.isFinite(m)) {
    if (m >= 0 && m <= 10) {
      return Math.round((m - 5) * 5);
    }
    return Math.max(-MO_TEAM_MAX_FE, Math.min(MO_TEAM_MAX_FE, m));
  }
  // No authoritative source on this update → null so the bar stays as-is (sticky).
  return null;
}

function isHcoTurnContext(turn) {
  if (!turn || typeof turn !== 'object') return false;
  const keys = ['offensive_state', 'current_turn', 'play_type'];
  for (let i = 0; i < keys.length; i += 1) {
    const v = turn[keys[i]];
    if (v != null && String(v).toUpperCase() === 'HCO') return true;
  }
  if (turn.playcall === 'HCO') return true;
  return false;
}

function resolveCourtImagePath(teamNameOrSlug) {
  const fallbackPath = '/images/teams/general/general_court.jpg';
  const preferredPath = typeof getTeamAssetPath === 'function'
    ? getTeamAssetPath(teamNameOrSlug, 'court')
    : fallbackPath;

  if (!preferredPath || preferredPath === fallbackPath) {
    return Promise.resolve(fallbackPath);
  }

  return new Promise((resolve) => {
    const img = new Image();
    img.onload = function () {
      resolve(preferredPath);
    };
    img.onerror = function () {
      resolve(fallbackPath);
    };
    img.src = preferredPath;
  });
}

function installOwnershipContractGlobalHelpers() {
  const scope = typeof window !== 'undefined' ? window : globalThis;
  if (!scope || scope.__ownershipContractHelpersInstalled) return;
  scope.__ownershipContractHelpersInstalled = true;

  const resolveOwnershipWarnThresholds = () => ({
    minRows: Math.max(1, Math.floor(Number(scope.UESS_OWNERSHIP_WARN_MIN_ROWS ?? 40) || 40)),
    invalidApplicableRateMax: Math.max(
      0,
      Number(scope.UESS_OWNERSHIP_WARN_INVALID_APPLICABLE_RATE_MAX ?? 0.02) || 0.02
    ),
    missingContractRowsMax: Math.max(
      0,
      Math.floor(Number(scope.UESS_OWNERSHIP_WARN_MISSING_CONTRACT_ROWS_MAX ?? 0) || 0)
    ),
  });

  scope.showOwnershipContractConfig = () => {
    const summaryEvery = Math.max(
      1,
      Math.floor(Number(scope.UESS_OWNERSHIP_SUMMARY_EVERY ?? 10) || 10)
    );
    const thresholds = resolveOwnershipWarnThresholds();
    const config = {
      mode: String(scope.UESS_OWNERSHIP_CONTRACT_MODE ?? "warn"),
      summaryEvery,
      thresholds,
      latestSummary: scope.__OWNERSHIP_CONTRACT_SUMMARY_LAST__ ?? null,
    };
    console.log("[OWNERSHIP CONTRACT CONFIG]", config);
    return config;
  };
  scope.getOwnershipContractSummaryLatest = (n = 5) => {
    const count = Math.max(0, Math.floor(Number(n) || 0));
    const list = Array.isArray(scope.__OWNERSHIP_CONTRACT_SUMMARY_BUFFER__)
      ? scope.__OWNERSHIP_CONTRACT_SUMMARY_BUFFER__
      : [];
    return list.slice(-count);
  };
  scope.clearOwnershipContractBuffers = () => {
    scope.__OWNERSHIP_CONTRACT_LAST__ = undefined;
    scope.__OWNERSHIP_CONTRACT_BUFFER__ = [];
    scope.__OWNERSHIP_CONTRACT_SUMMARY_LAST__ = undefined;
    scope.__OWNERSHIP_CONTRACT_SUMMARY_BUFFER__ = [];
    scope.__OWNERSHIP_CONTRACT_SESSION__ = undefined;
  };
}

function installPressureReworkGlobalHelpers() {
  const scope = typeof window !== 'undefined' ? window : globalThis;
  if (!scope || scope.__pressureReworkHelpersInstalled) return;
  scope.__pressureReworkHelpersInstalled = true;

  const resolvePressureReworkWarnThresholds = () => ({
    minRows: Math.max(
      1,
      Math.floor(Number(scope.UESS_PRESSURE_REWORK_WARN_MIN_ROWS ?? 10) || 10)
    ),
    warnRowsMax: Math.max(
      0,
      Math.floor(Number(scope.UESS_PRESSURE_REWORK_WARN_ROWS_MAX ?? 0) || 0)
    ),
    warnRateMax: Math.max(
      0,
      Number(scope.UESS_PRESSURE_REWORK_WARN_RATE_MAX ?? 0.02) || 0.02
    ),
  });

  scope.showPressureReworkConfig = () => {
    const phase = String(scope.UESS_PRESSURE_REWORK_PHASE ?? "off");
    const leadInContractMode = String(scope.UESS_PRESSURE_LEAD_IN_CONTRACT_MODE ?? "off");
    const stepContractMode = String(scope.UESS_PRESSURE_REWORK_STEP_CONTRACT_MODE ?? "inherit_legacy");
    const resolutionContractMode = String(scope.UESS_PRESSURE_REWORK_RESOLUTION_CONTRACT_MODE ?? "inherit_step_mode");
    const outContractMode = String(scope.UESS_PRESSURE_REWORK_OUT_CONTRACT_MODE ?? "inherit_step_mode");
    const summaryEvery = Math.max(
      1,
      Math.floor(Number(scope.UESS_PRESSURE_REWORK_SUMMARY_EVERY ?? 5) || 5)
    );
    const thresholds = resolvePressureReworkWarnThresholds();
    const buffer = Array.isArray(scope.__PRESSURE_REWORK_BUFFER__)
      ? scope.__PRESSURE_REWORK_BUFFER__
      : [];
    const enabledPhases = new Set(["phase1_scaffold", "phase2_split", "phase3_lead_in"]);
    const config = {
      phase,
      enabled: enabledPhases.has(phase),
      leadInContractMode,
      stepContractMode,
      resolutionContractMode,
      outContractMode,
      summaryEvery,
      thresholds,
      bufferRows: buffer.length,
      latestSummary: scope.__PRESSURE_REWORK_SUMMARY_LAST__ ?? null,
      lastEvent: scope.__PRESSURE_REWORK_LAST__ ?? null,
    };
    console.log("[PRESSURE REWORK CONFIG]", config);
    return config;
  };
  scope.getPressureReworkLatest = (n = 5) => {
    const count = Math.max(0, Math.floor(Number(n) || 0));
    const buffer = Array.isArray(scope.__PRESSURE_REWORK_BUFFER__)
      ? scope.__PRESSURE_REWORK_BUFFER__
      : [];
    return buffer.slice(-count);
  };
  scope.clearPressureReworkBuffer = () => {
    scope.__PRESSURE_REWORK_LAST__ = undefined;
    scope.__PRESSURE_REWORK_BUFFER__ = [];
    scope.__PRESSURE_REWORK_SUMMARY_LAST__ = undefined;
    scope.__PRESSURE_REWORK_SUMMARY_BUFFER__ = [];
    scope.__PRESSURE_REWORK_SESSION__ = undefined;
  };
  scope.getPressureReworkSummaryLatest = (n = 5) => {
    const count = Math.max(0, Math.floor(Number(n) || 0));
    const list = Array.isArray(scope.__PRESSURE_REWORK_SUMMARY_BUFFER__)
      ? scope.__PRESSURE_REWORK_SUMMARY_BUFFER__
      : [];
    return list.slice(-count);
  };
  scope.showPressureReworkPromotionReadiness = () => {
    const summary = scope.__PRESSURE_REWORK_SUMMARY_LAST__ || null;
    const readiness = {
      phase: String(scope.UESS_PRESSURE_REWORK_PHASE ?? "off"),
      summaryPresent: Boolean(summary),
      rows: summary?.rows ?? 0,
      warnRows: summary?.warnRows ?? 0,
      warnRate: summary?.warnRate ?? 0,
      hasEnoughRows: summary?.hasEnoughRows ?? false,
      meetsWarnPromotionGate: summary?.meetsWarnPromotionGate ?? false,
      thresholds: summary?.thresholds ?? resolvePressureReworkWarnThresholds(),
    };
    console.log("[PRESSURE REWORK READINESS]", readiness);
    return readiness;
  };
  scope.applyPressureReworkPromotionProfile = (profile = "warn") => {
    const p = String(profile || "").trim().toLowerCase();
    // Shared baseline for pressure rework.
    scope.UESS_PRESSURE_REWORK_PHASE = "phase3_lead_in";
    scope.UESS_PRESSURE_LEAD_IN_CONTRACT_MODE = "warn";
    scope.UESS_PRESSURE_REWORK_SUMMARY_EVERY = 1;
    if (p === "full_throw") {
      scope.UESS_PRESSURE_REWORK_STEP_CONTRACT_MODE = "throw";
      scope.UESS_PRESSURE_REWORK_RESOLUTION_CONTRACT_MODE = "throw";
      scope.UESS_PRESSURE_REWORK_OUT_CONTRACT_MODE = "throw";
    } else if (p === "pilot_throw") {
      scope.UESS_PRESSURE_REWORK_STEP_CONTRACT_MODE = "throw";
      scope.UESS_PRESSURE_REWORK_RESOLUTION_CONTRACT_MODE = "warn";
      scope.UESS_PRESSURE_REWORK_OUT_CONTRACT_MODE = "warn";
    } else {
      // Default/invalid profile falls back to warn-only rollout.
      scope.UESS_PRESSURE_REWORK_STEP_CONTRACT_MODE = "warn";
      scope.UESS_PRESSURE_REWORK_RESOLUTION_CONTRACT_MODE = "warn";
      scope.UESS_PRESSURE_REWORK_OUT_CONTRACT_MODE = "warn";
      profile = "warn";
    }
    const applied = {
      profile: p === "pilot_throw" || p === "full_throw" ? p : "warn",
      phase: scope.UESS_PRESSURE_REWORK_PHASE,
      leadInContractMode: scope.UESS_PRESSURE_LEAD_IN_CONTRACT_MODE,
      stepContractMode: scope.UESS_PRESSURE_REWORK_STEP_CONTRACT_MODE,
      resolutionContractMode: scope.UESS_PRESSURE_REWORK_RESOLUTION_CONTRACT_MODE,
      outContractMode: scope.UESS_PRESSURE_REWORK_OUT_CONTRACT_MODE,
      summaryEvery: scope.UESS_PRESSURE_REWORK_SUMMARY_EVERY,
    };
    console.log("[PRESSURE REWORK PROFILE APPLIED]", applied);
    return applied;
  };
}

export function createGameScene(Phaser) {
  return class GameScene extends Phaser.Scene {
    constructor() {
      super("GameScene");
      this.lastTurnShown = -1;
      this.rebounderId = null;
      this.stateMachine = createGameStateMachine(States.Inbound);
      
      // Initialize centralized possession manager
      this.possessionManager = null; // Will be initialized in create()
      this.gameClock = null;
      this.shotClock = null;
      /** Merged team_scoreboard_meta from simulate responses (turns often omit it). */
      this._courtScoreboardMetaByName = null;
      installOwnershipContractGlobalHelpers();
      installPressureReworkGlobalHelpers();
    }

    init(data) {
        this.tournamentId = data.tournamentId;
        this.franchiseId = data.franchiseId;
        this.animate = data.animate;
        this.mode = data.mode;
        this.homeLineup = data.homeLineup || {};
        this.awayLineup = data.awayLineup || {};
        this.periodLabel = data.periodLabel;
        this.quarter = data.quarter || 1;
        
        // ✅ REMOVED: Quarter transition debug logging (cluttering console)
        
        this.gameId = gameStore.getGameId();
        // ✅ PHASE 2.4: Removed commented localStorage fallback code
        
        if (!this.gameId && typeof localStorage !== 'undefined') {
          localStorage.removeItem('game_id');
        }
        this.gamePlanSettings = data.gamePlanSettings;
        this.playbookSettings = data.playbookSettings; // ✅ UNIFIED: Store playbook settings (same pattern as gamePlanSettings)
        // Court / bootGame may have a fresher GET /api/playbooks (live URL after replaceState).
        if (typeof window !== 'undefined' && window.__courtPlaybookApiData) {
          this.playbookSettings = window.__courtPlaybookApiData;
        }
        this.userTeamSide = data.userTeamSide;
        this.resumeActive = !!data.resumeActive;
        // ✅ SS&S: Store team_id (ObjectId) for navigation anchor preservation
        this.teamId = data.teamId;
        
        // Reset pause state for new game
        this.isPaused = false;
        this._courtScoreboardMetaByName = null;
        if (typeof window !== 'undefined') {
          window.__gobCourtScoreboardMetaByName = null;
        }

        if (DEBUG_FLOW) {
          const teams = gameStore.getTeams();
          console.log("🧠 Game initialized with:", {
            rosters: gameStore.getRosters(),
            tournamentId: this.tournamentId,
            franchiseId: this.franchiseId,
            homeTeam: teams.home,
            awayTeam: teams.away,
            mode: this.mode,
            periodLabel: this.periodLabel,
          });
        }
      }


    shutdown() {
      if (DEBUG_FLOW) console.log("🧹 GameScene shutdown - cleaning up sprites");
      
      // Reset pause state and kill all tweens
      this.isPaused = false;
      if (this.gameClock) {
        this.gameClock.stop();
        this.gameClock = null;
      }
      if (this.shotClock) {
        this.shotClock.stop();
        this.shotClock = null;
      }
      if (this.tweens) {
        // Resume all tweens before killing them to prevent stuck state
        this.tweens.resumeAll();
        // Kill all active tweens
        if (typeof this.tweens.killAll === 'function') {
          this.tweens.killAll();
        } else {
          // Fallback: kill all tweens individually
          const allTweens = this.tweens.getAll ? this.tweens.getAll() : [];
          allTweens.forEach(tween => {
            if (tween && typeof tween.stop === 'function') {
              tween.stop();
            }
          });
        }
      }
      
      // Update pause button text if it exists (element may not exist during shutdown)
      syncPauseButtonDom(false);
      
      // Destroy all player sprites
      if (this.playerSprites) {
        Object.values(this.playerSprites).forEach(sprite => {
          if (sprite && sprite.destroy) {
            sprite.destroy();
          }
        });
        this.playerSprites = {};
      }
      
      // Destroy ball sprite if it exists
      if (this.ballSprite && this.ballSprite.destroy) {
        this.ballSprite.destroy();
        this.ballSprite = null;
      }
      
      // Clear other references
      this.nameToId = {};
      this.playerInfo = {};
      this.playerStats = {};
      this.teamPlaysData = {};  // Store team plays data for tooltips
      this.teamStatsData = {};  // Store team stats data for tooltips
      
      console.log("✅ GameScene cleanup complete");
    }

    async preload() {
      if (DEBUG_FLOW) console.log("✅ GameScene preloaded");
      if (this.animate) {
        this.load.image("ball", "/images/ball.png");
        const { home } = gameStore.getTeams();
        const courtPath = await resolveCourtImagePath(home);
        this.load.image("court-bg", courtPath);
      }

    }

    async create() {
      if (DEBUG_FLOW) console.log("🎬 GameScene created");
      
      // Expose gameScene globally for Playcall Center tooltips
      window.currentGameScene = this;
      
      // ✅ TIMEOUT: Initialize timeout button
      if (ENABLE_TIMEOUT_BUTTON) {
        initTimeoutButton();
      }
      
      // ✅ DEFENSE MATCHUPS: Store trigger info for after simData loads
      // We'll show the popup after simData is fetched but before animation starts
      const urlParams = new URLSearchParams(window.location.search);
      const resumeFromTimeout = urlParams.get('resume_from_timeout') === 'true';
      const activeResume = urlParams.get('active_resume') === 'true' || this.resumeActive;
      const timeoutTraceId = urlParams.get('timeout_trace_id');
      // Defense Matchups popup trigger:
      // - Q1 start (non-timeout)
      // - Any quarter > 1 entry (quarter breaks)
      // - Any timeout/foul-out resume (resume_from_timeout=true)
      // Keep timeout/navigation contracts unchanged; this only controls popup visibility.
      const isQ1Start = this.quarter === 1 && !resumeFromTimeout && !activeResume;
      const isQuarterBreakEntry = this.quarter > 1 && !activeResume;
      const isTimeoutOrFoulOutResume = resumeFromTimeout;
      this.shouldShowMatchupsPopup = (isQ1Start || isQuarterBreakEntry || isTimeoutOrFoulOutResume) && this.gameId;
      const shouldGateCourtEntryVisuals = this.animate && !isQ1Start;
      const showCourtEntryVisualGate = (message = 'Loading game...') => {
        if (typeof window === 'undefined') return;
        window.__GOB_COURT_ENTRY_VISUAL_GATE__ = true;
        if (window.PageLoadOverlay && typeof window.PageLoadOverlay.show === 'function') {
          window.PageLoadOverlay.show(message);
        }
      };
      const hideCourtEntryVisualGate = () => {
        if (typeof window === 'undefined') return;
        window.__GOB_COURT_ENTRY_VISUAL_GATE__ = false;
        if (window.PageLoadOverlay && typeof window.PageLoadOverlay.hide === 'function') {
          window.PageLoadOverlay.hide();
        }
      };
      if (shouldGateCourtEntryVisuals) {
        showCourtEntryVisualGate();
      }

      // Gameplay background music start is deferred until after the Defense
      // Matchups modal flow completes (see below, right after
      // `showDefenseMatchupsPopup`). That hook handles both cases:
      //   - Modal renders → user clicks Submit → await resolves → music starts.
      //   - Modal doesn't render (don't-show-again, sim mode, etc.) → control
      //     reaches the hook immediately and music starts.
      // Q1 opening tip is still gated separately — music waits for the
      // tip-winner SFX in openingTip.js regardless of modal flow.
      
      // Reset pause state BEFORE killing tweens
      this.isPaused = false;
      if (this.tweens) {
        // Resume all tweens first (if any were paused)
        this.tweens.resumeAll();
        // Kill all active tweens to start fresh
        if (typeof this.tweens.killAll === 'function') {
          this.tweens.killAll();
        } else {
          // Fallback: kill all tweens individually
          const allTweens = this.tweens.getAll ? this.tweens.getAll() : [];
          allTweens.forEach(tween => {
            if (tween && typeof tween.stop === 'function') {
              tween.stop();
            }
          });
        }
        // Ensure tween manager is not paused for new animations
        // Phaser doesn't have a direct "unpause" for the manager, but new tweens should start normally
      }
      
      // Run structure validation for inbound passes
      this.runStructureValidation();

      const homeStatsEl = document.getElementById('home-stats-body');
      const awayStatsEl = document.getElementById('away-stats-body');
      if (homeStatsEl) homeStatsEl.innerHTML = '';
      if (awayStatsEl) awayStatsEl.innerHTML = '';

      // Ensure clean slate - destroy any existing sprites before creating new ones
      if (this.playerSprites) {
        Object.values(this.playerSprites).forEach(sprite => {
          if (sprite && sprite.destroy) {
            sprite.destroy();
          }
        });
      }
      
      this.playerSprites = {};
      this.nameToId = {};
      this.playerInfo = {};
      this.playerStats = {};
      this.teamPlaysData = {};  // Store team plays data for tooltips
      this.teamStatsData = {};  // Store team stats data for tooltips

      const { home: homeTeam, away: awayTeam } = gameStore.getTeams();

      if (DEBUG_TEAMS) {
        console.log("📨 Sending /api/simulate-quarter request for:", homeTeam, "vs", awayTeam);
        console.log("🔢 Quarter:", this.quarter, "Game ID:", this.gameId);
      }

      // ✅ NEW GAME DETECTION: Determine if this is a truly new game
      // New game if: no game_id, OR Q1 with no game_id in URL and not resuming from timeout
      // Reuse urlParams and resumeFromTimeout from above (lines 167-168)
      const urlGameId = urlParams.get('game_id');
      const isNewGameStart = !this.gameId || 
                        (this.quarter === 1 && !urlGameId && !resumeFromTimeout);
      
      if (isNewGameStart) {
        // Clear stale game_id for new game
        // ✅ REMOVED: New game logging (cluttering console)
        this.gameId = null;
        if (typeof localStorage !== 'undefined') {
          localStorage.removeItem('game_id');
        }
      }
      
      const payload = { home_team: homeTeam, away_team: awayTeam, quarter: this.quarter };
      const hRim = urlParams.get('home_rim_runner_player_id');
      const aRim = urlParams.get('away_rim_runner_player_id');
      if (hRim) payload.home_rim_runner_player_id = hRim;
      if (aRim) payload.away_rim_runner_player_id = aRim;
      // Only pass game_id if we have one AND it's not a new game
      if (this.gameId && !isNewGameStart) {
        payload.game_id = this.gameId;
      }
      
      // ✅ SS&S: Add mode and mode-specific IDs to payload (matches bootGame.js pattern)
      // This ensures backend sets correct mode on game document for finalize_game() processing
      if (this.mode) {
        payload.mode = this.mode;
      }
      if (this.tournamentId) {
        payload.tournament_id = this.tournamentId;
      }
      if (this.franchiseId) {
        payload.franchise_id = this.franchiseId;
      }
      
      // ✅ TIMEOUT: Add resume_from_timeout flag if present in URL
      if (resumeFromTimeout) {
        payload.resume_from_timeout = true;
        // ✅ REMOVED: Timeout resume logging (cluttering console)
      }
      if (urlParams.get('resume_from_anchor') === 'true') {
        payload.resume_from_anchor = true;
        console.warn('[RESUME-ANCHOR-CLIENT] simulate-quarter payload from anchor', {
          game_id: this.gameId,
          quarter: this.quarter,
          resume_from_timeout: !!payload.resume_from_timeout,
          clock: urlParams.get('clock'),
        });
      }
      if (urlParams.get('consume_resume_anchor') === 'true') {
        payload.consume_resume_anchor = true;
        console.warn('[RESUME-ANCHOR-CLIENT] simulate-quarter payload consume-only anchor', {
          game_id: this.gameId,
          quarter: this.quarter,
          quarter_break_from: urlParams.get('quarter_break_from'),
        });
      }
      if (resumeFromTimeout && urlParams.get('resume_from_anchor') !== 'true') {
        const futureParams = new URLSearchParams(window.location.search);
        futureParams.set('resume_from_timeout', 'false');
        if (typeof history !== 'undefined' && history.replaceState) {
          history.replaceState(null, '', `${window.location.pathname}?${futureParams.toString()}`);
        }
        console.warn('[RESUME-ANCHOR-CLIENT] converted timeout-return URL for future refreshes', {
          game_id: this.gameId,
          quarter: this.quarter,
          current_request_resume_from_timeout: true,
          future_resume_from_timeout: false,
          future_resume_from_anchor: false,
        });
      }
      if (urlParams.get('locked_exhausted_user_lineup') === 'true') {
        payload.locked_exhausted_user_lineup = true;
        payload.user_team_side = urlParams.get('my_team');
      }
      if (urlParams.get('lineup_checkpoint') === 'true') {
        payload.lineup_checkpoint = true;
      }
      if (timeoutTraceId) {
        payload.timeout_trace_id = timeoutTraceId;
      }
      if (timeoutTraceId) {
        console.log('🧭 [TIMEOUT TRACE] lineup->court URL', {
          timeout_trace_id: timeoutTraceId,
          game_id: this.gameId,
          quarter: this.quarter,
          resume_from_timeout: resumeFromTimeout,
          clock: urlParams.get('clock')
        });
      }
      if (DEBUG_FLOW) {
        console.log('[gameScene] request payload', {
          mode: this.mode,
          home: homeTeam,
          away: awayTeam,
          quarter: this.quarter,
          gameId: this.gameId,
        });
      }
      if (DEBUG_TEAMS) {
        console.log('/api/simulate-quarter payload teams:', {
          home: payload.home_team,
          away: payload.away_team,
        });
      }
      if (DEBUG_SIM_PAYLOAD) {
        console.debug('Sim payload teams:', homeTeam, awayTeam, 'gameId:', this.gameId);
      }
      if (Object.keys(this.homeLineup).length) payload.home_lineup = this.homeLineup;
      if (Object.keys(this.awayLineup).length) payload.away_lineup = this.awayLineup;
      
      // ✅ UNIFIED: Send both game plan and playbook settings for ALL quarters (not just Q1)
      // This ensures settings are available when resuming games from DB
      // If DB has None/missing settings, backend can use request settings as fallback
      if (this.gamePlanSettings && this.userTeamSide) {
        payload.user_team_side = this.userTeamSide;
        payload.strategy_settings = this.gamePlanSettings.strategy_settings;
        console.log('🎮 [gameScene] Sending game plan settings to backend:', {
          user_team_side: this.userTeamSide,
          aggression: this.gamePlanSettings.strategy_settings?.aggression,
          quarter: this.quarter
        });
      } else if (this.quarter === 1) {
        console.warn('⚠️ [gameScene] Not sending game plan:', { 
          hasSettings: !!this.gamePlanSettings, 
          userTeamSide: this.userTeamSide,
          gamePlanSettings: this.gamePlanSettings
        });
      }
      
      // ✅ UNIFIED: Send playbook settings (same pattern as strategy_settings)
      if (this.playbookSettings && this.userTeamSide) {
        // Backend cached-GM playbook merge requires user_team_side on the same payload
        payload.user_team_side = this.userTeamSide;
        payload.playbook_settings = this.playbookSettings;
        const pcOrder = this.playbookSettings.pc_order || {};
        console.log('🎮 [gameScene] Sending playbook settings to backend:', {
          user_team_side: this.userTeamSide,
          pc_order_offense: Array.isArray(pcOrder.offense) ? pcOrder.offense.length : 0,
          pc_order_defense: Array.isArray(pcOrder.defense) ? pcOrder.defense.length : 0,
          quarter: this.quarter
        });
      } else if (this.quarter === 1) {
        console.warn('⚠️ [gameScene] Not sending playbook settings:', { 
          hasSettings: !!this.playbookSettings, 
          userTeamSide: this.userTeamSide,
          playbookSettings: this.playbookSettings
        });
      }
      
      // Note: Q4 possession is handled by backend using opening_tip_winner from Q1
      // No need to pass start_with_inbound for standard Q4 logic
      let url = API_CONFIG.buildUrl('/api/simulate-quarter');
      if (isDebugPlaycall()) {
        url += (url.includes('?') ? '&' : '?') + 'debug_pc=1';
        const po = payload.playbook_settings && payload.playbook_settings.pc_order;
        const _row = {
          url,
          gameId: this.gameId,
          quarter: this.quarter,
          user_team_side: payload.user_team_side,
          has_playbook_settings: !!payload.playbook_settings,
          pc_offense_len: po && Array.isArray(po.offense) ? po.offense.length : null,
          pc_defense_len: po && Array.isArray(po.defense) ? po.defense.length : null,
        };
        console.info('[DEBUG_PC] gameScene POST /api/simulate-quarter', _row);
        console.warn('[DEBUG_PC] gameScene POST /api/simulate-quarter', _row);
      }
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (DEBUG_FLOW) {
        console.log('[gameScene] response status', res.status);
      }
      if (!this.constructor._loggedSimQuarter) {
        console.debug("🛠️ /api/simulate-quarter payload keys:", Object.keys(payload), "response status:", res.status);
        this.constructor._loggedSimQuarter = true;
      }


      if (!res.ok) {
        let errorMessage;
        try {
          const errData = await res.clone().json();
          errorMessage = errData.detail || errData.message || errData.error || JSON.stringify(errData);
        } catch {
          try {
            errorMessage = await res.text();
          } catch {
            errorMessage = res.statusText;
          }
        }
        console.error("❌ Failed to fetch sim data:", errorMessage);
        appendToTextScroll(`❌ ${errorMessage}`);
        return;
      }

      const simData = await res.json();
      const acceptedResumeAnchorRestore =
        payload.resume_from_anchor === true && payload.consume_resume_anchor === true;
      if (typeof window !== 'undefined' && typeof history !== 'undefined' && history.replaceState) {
        const liveEntryParams = new URLSearchParams(window.location.search);
        const quarterBreakFrom = liveEntryParams.get('quarter_break_from');
        if (quarterBreakFrom === 'play_quarter' || quarterBreakFrom === 'sim_quarter') {
          liveEntryParams.delete('quarter_break_from');
          history.replaceState(null, '', `${window.location.pathname}?${liveEntryParams.toString()}`);
          console.warn('[COURT BOOT MODE] consumed live quarter entry marker after successful quarter start', {
            game_id: this.gameId,
            quarter: this.quarter,
            quarter_break_from: quarterBreakFrom,
          });
        }
      }
      if (acceptedResumeAnchorRestore) {
        const firstTurn = Array.isArray(simData.turns) ? simData.turns[0] : null;
        this._skipFirstRestoredSipSetup = firstTurn?.result_type === "SIDE_INBOUND";
        if (this._skipFirstRestoredSipSetup) {
          console.warn('[RESUME-ANCHOR-CLIENT] first restored SIP will skip setup walk-in', {
            game_id: this.gameId,
            quarter: this.quarter,
            first_turn_type: firstTurn?.result_type || null,
            first_turn_animation_steps: Array.isArray(firstTurn?.animation_steps) ? firstTurn.animation_steps.length : 0,
          });
        }
      } else {
        this._skipFirstRestoredSipSetup = false;
      }
      if ((payload.resume_from_anchor || payload.consume_resume_anchor) && typeof window !== 'undefined' && typeof history !== 'undefined' && history.replaceState) {
        const consumedParams = new URLSearchParams(window.location.search);
        consumedParams.delete('resume_from_anchor');
        consumedParams.delete('consume_resume_anchor');
        consumedParams.delete('active_resume');
        consumedParams.delete('anchor_type');
        consumedParams.set('resume_from_timeout', 'false');
        history.replaceState(null, '', `${window.location.pathname}?${consumedParams.toString()}`);
        console.warn('[RESUME-ANCHOR-CLIENT] consumed anchor URL state after successful resume', {
          game_id: this.gameId,
          quarter: this.quarter,
          response_quarter: simData.quarter,
          clock: simData.clock || null,
          consume_only: !!payload.consume_resume_anchor,
        });
      }
      // ✅ TIMEOUT: Store simData in scene for timeout button manager access
      this.simData = simData;
      const _tsm0 = simData.team_scoreboard_meta;
      if (_tsm0 && typeof _tsm0 === 'object' && Object.keys(_tsm0).length) {
        this._courtScoreboardMetaByName = { ...(this._courtScoreboardMetaByName || {}), ..._tsm0 };
      }
      DEBUG && console.log('[gameScene] simData.turns', simData.turns.length, simData.turns[0]);
      if (DEBUG_FLOW) {
        console.log("📦 simData received:", simData);
        const turnsLen = Array.isArray(simData.turns) ? simData.turns.length : 0;
        console.log('🔄 Sim response arrived', { turns: turnsLen });
      }
      DEBUG_FLOW && console.log('[gameScene] quarters', { requested: this.quarter, sim: simData.quarter });
      
      // ✅ UNIFIED STRUCTURE: Prefer unified teams object, fallback to backward-compatible fields
      const homeTeamId = simData.home_team_id;
      const awayTeamId = simData.away_team_id;
      const teamsObj = simData.teams || {};

      // Get team data (unified teams + legacy); tolerate teams{} key != home_team_id string
      let homeTeamObj = resolveTeamRowForScoreboard(simData, 'home');
      let awayTeamObj = resolveTeamRowForScoreboard(simData, 'away');

      if (isCourtDebugScoreboard()) {
        const tk = Object.keys(teamsObj);
        console.info('[court scoreboard] simulate response → team rows', {
          home_team_id: homeTeamId,
          away_team_id: awayTeamId,
          teams_key_count: tk.length,
          teams_keys: tk.slice(0, 12),
          home_resolved: homeTeamObj
            ? {
                natl_rank: homeTeamObj.natl_rank,
                wins: homeTeamObj.wins ?? homeTeamObj.team_wins,
                losses: homeTeamObj.losses ?? homeTeamObj.team_losses,
              }
            : null,
          away_resolved: awayTeamObj
            ? {
                natl_rank: awayTeamObj.natl_rank,
                wins: awayTeamObj.wins ?? awayTeamObj.team_wins,
                losses: awayTeamObj.losses ?? awayTeamObj.team_losses,
              }
            : null,
          dom_rank_home: formatSbRank(homeTeamObj),
          dom_rec_home: formatSbRecord(homeTeamObj),
          dom_rank_away: formatSbRank(awayTeamObj),
          dom_rec_away: formatSbRecord(awayTeamObj),
        });
      }
      
      // Extract team names (unified structure preferred, fallback to old structure)
      const logHome = homeTeamObj?.name || simData.home_team || simData.homeTeam?.name;
      const logAway = awayTeamObj?.name || simData.away_team || simData.awayTeam?.name;
      
      // Extract team IDs
      const homeId = homeTeamId || homeTeamObj?.team_id || simData.home_team_id || simData.homeTeam?.team_id;
      const awayId = awayTeamId || awayTeamObj?.team_id || simData.away_team_id || simData.awayTeam?.team_id;
      
      // ✅ TIMEOUT: Store team names in scene for timeout button manager
      this.homeTeam = logHome;
      this.awayTeam = logAway;
      
      // Extract team colors (unified structure preferred)
      const homeColors = homeTeamObj?.colors || simData.home_team_colors;
      const awayColors = awayTeamObj?.colors || simData.away_team_colors;
      const homePlayersHeaderEl = document.getElementById('home-players-header');
      const awayPlayersHeaderEl = document.getElementById('away-players-header');
      if (homePlayersHeaderEl) {
        homePlayersHeaderEl.textContent = logHome || '';
      }
      if (awayPlayersHeaderEl) {
        awayPlayersHeaderEl.textContent = logAway || '';
      }
      
      if (DEBUG_TEAMS) {
        console.log('Resolved team IDs:', { home_team_id: homeId, away_team_id: awayId });
        console.log('Team colors from simData:', {
          mode: this.mode,
          home: homeColors,
          away: awayColors,
        });
      }
      // Detect if this is a new game (Q1 with no existing gameId or new gameId)
      const previousGameId = this.gameId;
      this.gameId = simData.game_id || this.gameId;
      const isNewGame = this.quarter === 1 && (!previousGameId || (simData.game_id && simData.game_id !== previousGameId));
      
      // ✅ REMOVED: Quarter transition debug logging (cluttering console)
      
      // ✅ PHASE 1.2: Removed automatic localStorage write - only save for explicit "Resume Last Game" feature
      gameStore.setGameId(this.gameId);
      
      // Set team IDs on scene for animation systems
      this.homeTeamId = homeId;
      this.awayTeamId = awayId;
      gameStore.setColors({
        home: homeColors,
        away: awayColors,
      });
      applyVibrantRgbDocumentVarsFromTeamColors(homeColors, awayColors);
      this.isFinal = simData.is_final;
      
      // ⏸️ TABLED: Resume Last Game feature - Exact game state restoration
      // TODO: Revisit after Phase 1.3+ and site go-live priorities complete
      // Current implementation resumes at lineup screen (functional but basic)
      // Future enhancement: Resume at exact moment (play step, time remaining, mid-animation, etc.)
      // See: docs/To Do/resume_last_game_exact_state.md
      /*
      // ✅ PHASE 1.2: Save game_id and user_team_side to localStorage when user quits mid-game (only for single mode, only if not final)
      // This enables "Resume Last Game" feature - save only when user explicitly quits (beforeunload)
      if (this.mode === 'single' && this.gameId && !this.isFinal && typeof window !== 'undefined') {
        const saveGameForResume = () => {
          if (this.gameId && !this.isFinal && this.mode === 'single' && typeof localStorage !== 'undefined') {
            localStorage.setItem('last_game_id', this.gameId);
            // Also save user_team_side so we can identify which team the user was playing
            if (this.userTeamSide) {
              localStorage.setItem('last_game_user_team_side', this.userTeamSide);
            }
            console.log('💾 [RESUME] Saved game_id and user_team_side for resume:', {
              game_id: this.gameId,
              user_team_side: this.userTeamSide
            });
          }
        };
        // Save on page unload (user closes tab/browser)
        window.addEventListener('beforeunload', saveGameForResume);
        // Also save on visibility change (user switches tabs - might come back)
        document.addEventListener('visibilitychange', () => {
          if (document.hidden) {
            saveGameForResume();
          }
        });
      }
      */
      
      if (DEBUG_FLOW) {
        console.log(
          `✅ Simulated matchup: ${logHome} vs ${logAway}`
        );
        console.log("📦 First turn:", simData.turns?.[0]);
      }

      const homeLogoEl = document.getElementById('home-logo');
      const awayLogoEl = document.getElementById('away-logo');
      if (homeLogoEl) homeLogoEl.src = typeof getTeamAssetPath === 'function' ? getTeamAssetPath(homeTeam, 'banner_primary') : '/images/teams/general/general_banner_primary.jpg';
      if (awayLogoEl) awayLogoEl.src = typeof getTeamAssetPath === 'function' ? getTeamAssetPath(awayTeam, 'banner_primary') : '/images/teams/general/general_banner_primary.jpg';

      const homeScoreEl = document.getElementById('home-score');
      const awayScoreEl = document.getElementById('away-score');
      const homeFoulsEl = document.getElementById('home-fouls');
      const awayFoulsEl = document.getElementById('away-fouls');
      const homeTolEl = document.getElementById('home-tol');
      const awayTolEl = document.getElementById('away-tol');
      const clockEl = document.getElementById('game-clock');
      const quarterEl = document.getElementById('quarter');
      const shotClockEl = document.getElementById('shot-clock');
      
      // ✅ FOUL OUT RESUME: Initialize clock early (before DOM usage)
      // When resuming from timeout/foul out, the first turn has the correct clock from backend
      // Note: resumeFromTimeout is already declared earlier in this function (line 222)
      
      // For timeout resumes, use first turn's clock if available (backend source of truth)
      let liveClock = '8:00'; // Default
      if (resumeFromTimeout && simData.turns && simData.turns.length > 0) {
        const firstTurn = simData.turns[0];
        liveClock = firstTurn.clock || firstTurn.game_clock || simData.clock || '8:00';
        console.log(`✅ TIMEOUT RESUME: Using first turn clock: ${liveClock}`);
      } else {
        // For new games or non-timeout resumes, use URL param or simData
        // Reuse urlParams from above (line 167)
        const urlClock = urlParams.get('clock');
        // ✅ BUG 2 FIX: Quarter break (Q2+ start) — backend is source of truth; ignore URL clock so stale Q1 clock never overrides 8:00
        if (this.quarter > 1 && !resumeFromTimeout) {
          liveClock = simData.clock || '8:00';
        } else {
          liveClock = urlClock || simData.clock || '8:00';
        }
      }
      
      let liveQuarter = this.quarter;
      let livePeriodLabel = simData.period_label || `Q${this.quarter}`;
      
      // ✅ FOUL OUT RESUME: Set clock immediately on page load (before turn processing)
      // This ensures correct clock display when returning from lineup/game plan screens
      if (clockEl && liveClock) {
        clockEl.textContent = liveClock;
      }
      if (this.gameClock) {
        this.gameClock.stop();
      }
      if (this.shotClock) {
        this.shotClock.stop();
      }
      const initialClockSeconds =
        (typeof simData.time_remaining === 'number' ? simData.time_remaining : null) ??
        parseClockToSeconds(liveClock);
      this.gameClock = createGameClock({
        timeRemainingSeconds: initialClockSeconds,
        clockElement: clockEl,
        tickMs: 350,
      });
      this.gameClock.syncWithBackend(initialClockSeconds); // Backend-driven: display from backend only; no countdown interval.
      this.shotClock = createGameClock({
        timeRemainingSeconds: 30,
        clockElement: shotClockEl,
        tickMs: 350,
        formatter: (seconds) => String(Math.max(0, Math.floor(Number(seconds) || 0))),
      });
      this.shotClock.syncWithBackend(30);
      syncShotClockCriticalClass(30);
      // Clocks are backend-driven: updated only when turn data is applied (updateScoreboard), not by a countdown interval.
      if (quarterEl && livePeriodLabel) {
        quarterEl.textContent = livePeriodLabel;
      }

      const positions = ["PG","SG","SF","PF","C"];
      // Filter out the ball and inactive players (those without a position)
      const actualPlayers = simData.players.filter(p => {
        const id = p.playerId ?? p.player_id;
        const isBall = id === "ball" || id === "Ball" || p.name === "ball" || p.name === "Ball";
        const hasPosition = p.pos !== null && p.pos !== undefined; // Only include players in current lineup
        
        if (!isBall && !hasPosition) {
        }
        
        return !isBall && hasPosition;
      });

      const openingTipTurn = Array.isArray(simData.turns)
        ? simData.turns.find(turn => turn?.result_type === "OPENING_TIP")
        : null;
      const firstSimTurn = Array.isArray(simData.turns) ? simData.turns[0] : null;
      const schemaInboundOnFirstTurn =
        Array.isArray(firstSimTurn?.animation_steps) && firstSimTurn.animation_steps.length > 0;
      const authoredEntryAnimations = Array.isArray(simData.entry_animation?.animations)
        ? simData.entry_animation.animations
        : (openingTipTurn?.animations || []);
      const authoredEntranceByPlayerId = new Map(
        authoredEntryAnimations
          .filter(anim => anim?.playerId && anim?.entrance)
          .map(anim => [String(anim.playerId), anim.entrance])
      );
      if (authoredEntranceByPlayerId.size > 0 && !schemaInboundOnFirstTurn) {
        actualPlayers.forEach(player => {
          const playerId = String(player.playerId ?? player.player_id);
          const entranceCoords = authoredEntranceByPlayerId.get(playerId);
          if (entranceCoords) player.startingCoords = { ...entranceCoords };
        });
      } else if (schemaInboundOnFirstTurn) {
        console.warn("🏠 [BENCH_ENTRY] spawn skipped — schema animation_steps handle triangle→setup");
      }

      // Resume/cold-load contract: backend summaries persist authoritative
      // lineup coords as player.x/player.y, while Phaser sprite creation reads
      // player.startingCoords. Hydrate that bridge before sprites are created so
      // a restored inbound/timeout state does not spawn everyone at center court.
      let resumeCoordsHydrated = 0;
      actualPlayers.forEach(player => {
        if (player.startingCoords && player.startingCoords.x != null && player.startingCoords.y != null) {
          return;
        }
        const x = Number(player.x);
        const y = Number(player.y);
        if (Number.isFinite(x) && Number.isFinite(y)) {
          player.startingCoords = { x, y };
          resumeCoordsHydrated += 1;
        }
      });
      if (urlParams.get('resume_from_anchor') === 'true' || urlParams.get('active_resume') === 'true') {
        console.warn('[RESUME-ANCHOR-CLIENT] hydrated player starting coords', {
          actual_players: actualPlayers.length,
          hydrated_from_xy: resumeCoordsHydrated,
          with_starting_coords: actualPlayers.filter(p => p.startingCoords?.x != null && p.startingCoords?.y != null).length,
          first_turn_type: firstSimTurn?.result_type || null,
          first_turn_animation_steps: Array.isArray(firstSimTurn?.animation_steps) ? firstSimTurn.animation_steps.length : 0,
        });
      }
      
      // Filtered active players from roster
      
      this.nameToId = Object.fromEntries(actualPlayers.map(p => [p.name, p.playerId ?? p.player_id]));
      this.playerInfo = Object.fromEntries(actualPlayers.map(p => [
        p.playerId ?? p.player_id,
        { name: p.name, team: p.team, pos: p.pos, jersey: p.jersey },
      ]));
      
      // Initialize player stats from simData.players (accumulated stats from previous quarters)
      // For Q2+, stats are restored from the database; for Q1, stats start at 0
      this.playerStats = {};
      simData.players.forEach(p => {
        const id = p.playerId ?? p.player_id;
        // Use stats from simData if available (Q2+), otherwise initialize to 0 (Q1)
        const savedStats = p.stats || {};
        // IMPORTANT: Initialize OREB and DREB separately (not just REB)
        // REB is calculated from OREB + DREB, so we need to track all three
        const oreb = savedStats.OREB || 0;
        const dreb = savedStats.DREB || 0;
        const reb = savedStats.REB || (oreb + dreb); // Use saved REB, or calculate from OREB + DREB
        this.playerStats[id] = { 
          PTS: savedStats.PTS || 0,
          F: savedStats.F || 0,
          OREB: oreb,
          DREB: dreb,
          REB: reb,
          AST: savedStats.AST || 0,
          STL: savedStats.STL || 0,
          BLK: savedStats.BLK || 0,
          TO: savedStats.TO || 0,
          DEF_A: savedStats.DEF_A || 0,
          DEF_S: savedStats.DEF_S || 0
        };
      });
      this.rowRefs = { home: {}, away: {} };
      this.currentLineup = { home: {}, away: {} };

      const homeBody = document.getElementById('home-stats-body');
      const awayBody = document.getElementById('away-stats-body');

      const formatName = (name, jersey) => {
        if (!name && jersey == null) return '';
        const parts = (name || '').trim().split(/\s+/).filter(Boolean);
        const lastName = parts.length ? parts[parts.length - 1] : '';
        const hasJersey = jersey !== undefined && jersey !== null && jersey !== '';
        if (hasJersey && lastName) return `#${jersey} ${lastName}`;
        if (lastName) return lastName;
        if (hasJersey) return `#${jersey}`;
        return '';
      };

      const getEnergyColor = (ng) => {
        if (ng > 0.89) return '#00aa00';      // Green
        if (ng >= 0.8) return '#cccc00';      // Yellow
        if (ng >= 0.7) return '#ff8800';      // Orange
        return '#cc0000';                      // Red
      };

      // Player tooltip functions
      const showPlayerTooltip = (event, playerId, player) => {
        const tooltip = document.getElementById('player-tooltip');
        const image = document.getElementById('tooltip-player-image');
        const energyEl = document.getElementById('tooltip-player-energy');
        const momentumEl = document.getElementById('tooltip-player-momentum');
        const emotionEl = document.getElementById('tooltip-player-emotion');
        
        if (!tooltip) return;
        
        // Set player image via central resolver (R2 + transforms); generic fallback on error.
        const base = (typeof window !== 'undefined' && window.API_CONFIG?.getStaticPath) ? window.API_CONFIG.getStaticPath() : ((window.location?.hostname === 'localhost' || window.location?.hostname === '127.0.0.1') ? '/static' : '');
        image.src = (typeof window !== 'undefined' && window.API_CONFIG?.getPlayerImageUrl)
          ? window.API_CONFIG.getPlayerImageUrl(playerId, { size: 'card' })
          : `${base}/images/players/${playerId}.png`;
        image.onerror = () => {
          image.onerror = null;
          image.src = `${base}/images/players/generic_headshot.png`;
        };
        
        // Get current player stats (including current energy)
        const stats = this.playerStats[playerId] || {};
        
        // Get current energy from playerStats (updated each turn from player_energy)
        const ng = stats.NG ?? 1.0;
        const ngPercent = Math.round(ng * 100);
        
        // Get LIVE momentum: playerStats.MO is refreshed every turn from
        // turn.player_momentum; fall back to the load-time player attribute.
        const momentum = stats.MO ?? player.attributes?.MO ?? player.MO ?? '--';
        
        // Get emotion score (EM) from player attributes
        const em = player.attributes?.EM ?? player.EM ?? 50;
        
        // Determine emoji based on EM score
        let emoji = '😐'; // Default straight face
        if (em >= 80) emoji = '😎';        // Sunglasses
        else if (em >= 60) emoji = '😊';   // Big smile
        else if (em >= 40) emoji = '😐';   // Straight face
        else if (em >= 20) emoji = '😕';   // Slight frown
        else emoji = '😡';                  // Angry face
        
        // Update tooltip content
        energyEl.textContent = `${ngPercent}%`;
        energyEl.className = 'tooltip-stat-value';
        if (ng > 0.89) energyEl.classList.add('energy-high');
        else if (ng >= 0.8) energyEl.classList.add('energy-medium');
        else if (ng >= 0.7) energyEl.classList.add('energy-low');
        else energyEl.classList.add('energy-critical');
        
        // Update momentum bar (visual instead of text)
        const leftBar = document.getElementById('tooltip-momentum-left');
        const rightBar = document.getElementById('tooltip-momentum-right');
        const moValueEl = document.getElementById('tooltip-momentum-value');

        if (leftBar && rightBar) {
          const moValue = typeof momentum === 'number' ? momentum : 0;

          if (moValue < 0) {
            // Negative momentum: fill left side with red (MO scale ±5)
            // Bar is center-anchored (right:50%), width = % of container, so the
            // half = 50%. -5 fills the whole half (50%); -1 = 20% of half (10%).
            const fillPercent = Math.min(50, Math.abs(moValue) / 5 * 50);
            leftBar.style.width = `${fillPercent}%`;
            rightBar.style.width = '0%';
          } else if (moValue > 0) {
            // Positive momentum: fill right side with green (MO scale ±5)
            // +5 fills the whole half (50% of container); +1 = 20% of half (10%).
            const fillPercent = Math.min(50, moValue / 5 * 50);
            leftBar.style.width = '0%';
            rightBar.style.width = `${fillPercent}%`;
          } else {
            // Zero momentum: no fill, just yellow line
            leftBar.style.width = '0%';
            rightBar.style.width = '0%';
          }

          // Numeric MO value: signed, positive on the right, negative on the
          // left; hidden at 0 (per spec).
          if (moValueEl) {
            if (moValue > 0) {
              moValueEl.textContent = `+${moValue}`;
              moValueEl.style.left = 'auto';
              moValueEl.style.right = '0';
              moValueEl.style.display = 'flex';
            } else if (moValue < 0) {
              moValueEl.textContent = `${moValue}`;
              moValueEl.style.right = 'auto';
              moValueEl.style.left = '0';
              moValueEl.style.display = 'flex';
            } else {
              moValueEl.textContent = '';
              moValueEl.style.display = 'none';
            }
          }
        }
        
        emotionEl.textContent = emoji;
        
        // Position and show tooltip
        tooltip.classList.add('visible');
        updateTooltipPosition(event);
      };

      const updateTooltipPosition = (event) => {
        const tooltip = document.getElementById('player-tooltip');
        if (!tooltip) return;

        const offsetX = 15;
        const offsetY = 15;
        const pad = 8;
        const tooltipWidth = tooltip.offsetWidth || 220;
        const tooltipHeight = tooltip.offsetHeight || 96;

        let left = event.clientX + offsetX;
        let top = event.clientY + offsetY;

        if (left + tooltipWidth > window.innerWidth - pad) {
          left = event.clientX - tooltipWidth - offsetX;
        }
        if (left < pad) left = pad;
        if (top + tooltipHeight > window.innerHeight - pad) {
          top = window.innerHeight - tooltipHeight - pad;
        }
        if (top < pad) top = pad;

        tooltip.style.left = `${left}px`;
        tooltip.style.top = `${top}px`;
      };

      const hidePlayerTooltip = () => {
        const tooltip = document.getElementById('player-tooltip');
        if (tooltip) {
          tooltip.classList.remove('visible');
        }
      };

      // Play tooltip functions (for S2 tab play categories)
      const showPlayTooltip = (event, category, teamKey) => {
        const tooltip = document.getElementById('play-tooltip');
        const playNameEl = document.getElementById('tooltip-play-name');
        const commandEl = document.getElementById('tooltip-play-command');
        
        if (!tooltip || !this.teamPlaysData) return;
        
        // Get team name from simData (handle nested structure)
        const homeTeamField = this.simData?.home_team;
        const awayTeamField = this.simData?.away_team;
        const homeTeamName = typeof homeTeamField === 'object' ? homeTeamField?.name : homeTeamField;
        const awayTeamName = typeof awayTeamField === 'object' ? awayTeamField?.name : awayTeamField;
        const teamName = teamKey === 'home' ? homeTeamName : awayTeamName;
        if (!teamName) return;
        
        // Get last play run for this category
        const lastPlayByCategory = this.teamStatsData?.[teamName]?.offense?.last_play_by_category || {};
        const lastPlayName = lastPlayByCategory[category];
        
        // Get command score from plays data (API field: game_stats.effectiveness)
        const teamPlays = this.teamPlaysData[teamName] || [];
        const playData = teamPlays.find(p => p.name === lastPlayName);
        const commandScore = playData?.game_stats?.effectiveness ?? '--';
        
        // Update tooltip content
        playNameEl.textContent = lastPlayName || 'None';
        if (commandEl) {
          commandEl.textContent = commandScore !== '--' ? `${commandScore}` : '--';
        }
        
        // Position and show tooltip
        tooltip.classList.add('visible');
        updatePlayTooltipPosition(event);
      };
      
      const updatePlayTooltipPosition = (event) => {
        const tooltip = document.getElementById('play-tooltip');
        if (!tooltip) return;

        const offset = 15;
        const pad = 8;
        const tooltipWidth = tooltip.offsetWidth || 220;
        const tooltipHeight = tooltip.offsetHeight || 80;

        let left = event.clientX + offset;
        let top = event.clientY + offset;

        if (left + tooltipWidth > window.innerWidth - pad) {
          left = event.clientX - tooltipWidth - offset;
        }
        if (left < pad) left = pad;
        if (top + tooltipHeight > window.innerHeight - pad) {
          top = window.innerHeight - tooltipHeight - pad;
        }
        if (top < pad) top = pad;

        tooltip.style.left = `${left}px`;
        tooltip.style.top = `${top}px`;
      };
      
      const hidePlayTooltip = () => {
        const tooltip = document.getElementById('play-tooltip');
        if (tooltip) {
          tooltip.classList.remove('visible');
        }
      };

      const initTeamTable = (teamKey, bodyEl) => {
        positions.forEach(pos => {
          const player = simData.players.find(p => p.team === teamKey && p.pos === pos);
          const playerId = player?.playerId ?? player?.player_id;
          const tr = document.createElement('tr');
          const nameTd = document.createElement('td');
          const ptsTd = document.createElement('td');
          const rebTd = document.createElement('td');
          const astTd = document.createElement('td');
          const foulsTd = document.createElement('td');
          const stlTd = document.createElement('td');
          const blkTd = document.createElement('td');
          const toTd = document.createElement('td');
          const defAttemptsTd = document.createElement('td');
          const defTd = document.createElement('td');
          
          // Name lives in its own span so the momentum glyph (sibling) survives
          // textContent updates on substitution. Energy color is set on the <td>
          // and inherits to the text span; the glyph uses its own SVG fills.
          const nameTextSpan = document.createElement('span');
          nameTextSpan.className = 'bs-name-text';
          nameTextSpan.textContent = formatName(player?.name, player?.jersey) || '';
          const moGlyphSpan = document.createElement('span');
          moGlyphSpan.className = 'bs-mo-glyph';
          moGlyphSpan.style.display = 'none';
          nameTd.append(nameTextSpan, moGlyphSpan);
          nameTd.style.cursor = 'pointer';
          nameTd.dataset.playerId = playerId;
          
          // Add tooltip functionality for player names
          nameTd.addEventListener('mouseenter', (e) => {
            if (playerId && player) {
              showPlayerTooltip(e, playerId, player);
            }
          });
          nameTd.addEventListener('mousemove', (e) => {
            updateTooltipPosition(e);
          });
          nameTd.addEventListener('mouseleave', () => {
            hidePlayerTooltip();
          });
          
          ptsTd.textContent = '0';
          rebTd.textContent = '0';
          astTd.textContent = '0';
          foulsTd.textContent = '0';
          stlTd.textContent = '0';
          blkTd.textContent = '0';
          toTd.textContent = '0';
          defAttemptsTd.textContent = '0';
          defTd.textContent = '0%';
          
          // Initialize energy color (defaults to green for fresh players at 1.0)
          const initialNG = player?.NG ?? 1.0;
          const initialColor = getEnergyColor(initialNG);
          nameTd.style.color = initialColor;
          ptsTd.style.color = initialColor;
          rebTd.style.color = initialColor;
          astTd.style.color = initialColor;
          foulsTd.style.color = initialColor;
          stlTd.style.color = initialColor;
          blkTd.style.color = initialColor;
          toTd.style.color = initialColor;
          defAttemptsTd.style.color = initialColor;
          defTd.style.color = initialColor;
          
          // Hide S2 and S3 columns by default (S1 is visible)
          stlTd.style.display = 'none';
          blkTd.style.display = 'none';
          toTd.style.display = 'none';
          defAttemptsTd.style.display = 'none';
          defTd.style.display = 'none';
          
          tr.append(nameTd, ptsTd, rebTd, astTd, foulsTd, stlTd, blkTd, toTd, defAttemptsTd, defTd);
          bodyEl.appendChild(tr);
          this.rowRefs[teamKey][pos] = {
            nameCell: nameTd, nameTextCell: nameTextSpan, moGlyph: moGlyphSpan,
            ptsCell: ptsTd, rebCell: rebTd, astCell: astTd, foulsCell: foulsTd,
            stlCell: stlTd, blkCell: blkTd, toCell: toTd, defAttemptsCell: defAttemptsTd, defCell: defTd
          };
          if (playerId) {
            this.playerStats[playerId].cells = { 
              pts: ptsTd, reb: rebTd, ast: astTd, fouls: foulsTd,
              stl: stlTd, blk: blkTd, to: toTd, defAttempts: defAttemptsTd, def: defTd
            };
            this.playerStats[playerId].nameCell = nameTd; // Store name cell for energy color coding
            this.currentLineup[teamKey][pos] = playerId;
          }
        });
      };

      initTeamTable('home', homeBody);
      initTeamTable('away', awayBody);

      // Add event listeners for play tooltip (S2 tab play categories)
      const playStatRows = document.querySelectorAll('.play-stat-row');
      playStatRows.forEach(row => {
        const category = row.dataset.playCategory;
        const teamKey = row.dataset.team;
        
        row.addEventListener('mouseenter', (e) => {
          if (category && teamKey) {
            showPlayTooltip(e, category, teamKey);
          }
        });
        
        row.addEventListener('mousemove', (e) => {
          updatePlayTooltipPosition(e);
        });
        
        row.addEventListener('mouseleave', () => {
          hidePlayTooltip();
        });
      });

      const updateLineup = (teamKey, lineup) => {
        if (!lineup) return;
        positions.forEach(pos => {
          const playerId = lineup[pos];
          if (!playerId) return;
          this.currentLineup[teamKey][pos] = playerId;
          const info = this.playerInfo[playerId];
          const row = this.rowRefs[teamKey][pos];
          if (info && row) {
            // Update only the text span so the momentum glyph sibling survives.
            (row.nameTextCell || row.nameCell).textContent = formatName(info.name, info.jersey);
            const stats = this.playerStats[playerId] || { 
              PTS: 0, F: 0, REB: 0, AST: 0, STL: 0, BLK: 0, TO: 0, DEF_A: 0, DEF_S: 0 
            };
            this.playerStats[playerId] = stats;
            row.ptsCell.textContent = stats.PTS;
            row.foulsCell.textContent = stats.F;
            row.rebCell.textContent = stats.REB;
            row.astCell.textContent = stats.AST;
            row.stlCell.textContent = stats.STL;
            row.blkCell.textContent = stats.BLK;
            row.toCell.textContent = stats.TO;
            row.defAttemptsCell.textContent = stats.DEF_A;
            
            // Calculate defensive win percentage (no decimals)
            const defRate = stats.DEF_A > 0 ? Math.round((stats.DEF_S / stats.DEF_A) * 100) : 0;
            stats.DEF_PCT = `${defRate}%`;  // Store for S3 tab access
            row.defCell.textContent = stats.DEF_PCT;
            
            stats.cells = { 
              pts: row.ptsCell, fouls: row.foulsCell, reb: row.rebCell, ast: row.astCell,
              stl: row.stlCell, blk: row.blkCell, to: row.toCell, defAttempts: row.defAttemptsCell, def: row.defCell
            };
            stats.nameCell = row.nameCell; // Store name cell for energy color coding
          }
        });
      };

      const hydrateBoxScore = () => {
        // Use the baseline stats captured at the start of the quarter so the
        // table initially reflects pre-tip totals.
        // For new games, force empty box score to ensure stats start at 0
        const box = isNewGame ? {} : (simData.start_box_score || {});
        // Preserve the final (cumulative) box score separately for any
        // consumers that need the completed stats (e.g. post-game summaries).
        this.finalBoxScore = simData.final_box_score || simData.box_score || {};
        ['home', 'away'].forEach(teamKey => {
          const teamName = teamKey === 'home' ? homeTeam : awayTeam;
          const teamBox = box[teamName] || {};
          const lineup = {};
          positions.forEach(pos => {
            const statBlock = teamBox[pos];
            if (!statBlock) return;
            const playerId = this.nameToId[statBlock.name];
            if (!playerId) return;
            const pts = statBlock.PTS ?? 0;
            const reb = statBlock.REB ?? ((statBlock.OREB || 0) + (statBlock.DREB || 0));
            const ast = statBlock.AST ?? 0;
            const fouls = statBlock.F ?? 0;
            const stl = statBlock.STL ?? 0;
            const blk = statBlock.BLK ?? 0;
            const to = statBlock.TO ?? 0;
            const defA = statBlock.DEF_A ?? 0;
            const defS = statBlock.DEF_S ?? 0;
            
            const ps = this.playerStats[playerId] || { 
              PTS: 0, F: 0, REB: 0, AST: 0, STL: 0, BLK: 0, TO: 0, DEF_A: 0, DEF_S: 0 
            };
            ps.PTS = pts;
            ps.F = fouls;
            ps.REB = reb;
            ps.AST = ast;
            ps.STL = stl;
            ps.BLK = blk;
            ps.TO = to;
            ps.DEF_A = defA;
            ps.DEF_S = defS;
            // Calculate defensive win percentage (no decimals)
            const defPct = ps.DEF_A > 0 ? Math.round((ps.DEF_S / ps.DEF_A) * 100) : 0;
            ps.DEF_PCT = `${defPct}%`;
            this.playerStats[playerId] = ps;
            lineup[pos] = playerId;
          });
          updateLineup(teamKey, lineup);
        });
      };

      hydrateBoxScore();

      // Initialize Team Box Score with team attributes (S3 tab) only
      // Stats will be updated in real-time from turn data via applyTeamStats
      if (typeof window.setTeamBoxData === 'function') {
        // Get team attributes from new nested structure or old flat structure
        const homeAttrs = homeTeamObj?.attributes || simData.team_attributes?.[homeTeam] || {};
        const awayAttrs = awayTeamObj?.attributes || simData.team_attributes?.[awayTeam] || {};
        
        // Initialize with empty offense, defense, and empty totals (will be populated from turn data in real-time)
        window.setTeamBoxData({
          home: {
            offense: {},
            defense: {},
            attributes: homeAttrs,
            totals: {} // Start empty - will update from turn.team_totals in real-time
          },
          away: {
            offense: {},
            defense: {},
            attributes: awayAttrs,
            totals: {} // Start empty - will update from turn.team_totals in real-time
          }
        });
      }

      // Resumed game (timeout/quarter break/foul-out): force Player and Team box scores from current game state
      // so they match the scoreboard; only these two areas are updated—nothing else on court.
      if (this.gameId && homeTeam && awayTeam) {
        try {
          const { fetchGameState } = await import('./utils/loadGameStats.js');
          const gameData = await fetchGameState(this.gameId);
          if (gameData) {
            // Force Team Box Score (S1, S2, S3) from current game state
            if (typeof window.setTeamBoxData === 'function') {
              const homeTotals = gameData.team_totals?.[homeTeam] || {};
              const awayTotals = gameData.team_totals?.[awayTeam] || {};
              const hTeamId = gameData.home_team_id;
              const aTeamId = gameData.away_team_id;
              const teamsObj = gameData.teams || {};
              const hObj = hTeamId && teamsObj[hTeamId] ? teamsObj[hTeamId] : null;
              const aObj = aTeamId && teamsObj[aTeamId] ? teamsObj[aTeamId] : null;
              const hAttrs = hObj?.attributes || gameData.home_team?.attributes || {};
              const aAttrs = aObj?.attributes || gameData.away_team?.attributes || {};
              const hOff = gameData.team_stats?.[homeTeam]?.offense || {};
              const aOff = gameData.team_stats?.[awayTeam]?.offense || {};
              const hDef = gameData.team_stats?.[homeTeam]?.defense || {};
              const aDef = gameData.team_stats?.[awayTeam]?.defense || {};
              window.setTeamBoxData({
                home: { offense: hOff, defense: hDef, attributes: hAttrs, totals: homeTotals },
                away: { offense: aOff, defense: aDef, attributes: aAttrs, totals: awayTotals }
              });
            }
            // Force Player Box Score: sync this.playerStats and DOM cells from current game state
            // API returns box_score keyed by team_id (not team name) - use home_team_id/away_team_id
            const boxScore = gameData.box_score || {};
            const homeTeamId = gameData.home_team_id;
            const awayTeamId = gameData.away_team_id;
            ['home', 'away'].forEach(teamKey => {
              const teamId = teamKey === 'home' ? homeTeamId : awayTeamId;
              const teamName = teamKey === 'home' ? homeTeam : awayTeam;
              const teamBox = (teamId && boxScore[teamId]) ? boxScore[teamId] : (boxScore[teamName] || {});
              Object.values(teamBox).forEach((statBlock) => {
                if (!statBlock || typeof statBlock !== 'object' || !statBlock.name) return;
                const playerId = (statBlock.playerId ?? statBlock.player_id) || this.nameToId[statBlock.name];
                if (!playerId) return;
                const ps = this.playerStats[playerId];
                if (!ps || !ps.cells) return;
                const oreb = statBlock.OREB ?? 0;
                const dreb = statBlock.DREB ?? 0;
                const reb = statBlock.REB ?? (oreb + dreb);
                ps.PTS = statBlock.PTS ?? 0;
                ps.F = statBlock.F ?? 0;
                ps.OREB = oreb;
                ps.DREB = dreb;
                ps.REB = reb;
                ps.AST = statBlock.AST ?? 0;
                ps.STL = statBlock.STL ?? 0;
                ps.BLK = statBlock.BLK ?? 0;
                ps.TO = statBlock.TO ?? 0;
                ps.DEF_A = statBlock.DEF_A ?? 0;
                ps.DEF_S = statBlock.DEF_S ?? 0;
                const defPct = ps.DEF_A > 0 ? Math.round((ps.DEF_S / ps.DEF_A) * 100) : 0;
                ps.DEF_PCT = `${defPct}%`;
                if (ps.cells.pts) ps.cells.pts.textContent = ps.PTS;
                if (ps.cells.reb) ps.cells.reb.textContent = ps.REB;
                if (ps.cells.ast) ps.cells.ast.textContent = ps.AST;
                if (ps.cells.fouls) ps.cells.fouls.textContent = ps.F;
                if (ps.cells.stl) ps.cells.stl.textContent = ps.STL;
                if (ps.cells.blk) ps.cells.blk.textContent = ps.BLK;
                if (ps.cells.to) ps.cells.to.textContent = ps.TO;
                if (ps.cells.defAttempts) ps.cells.defAttempts.textContent = ps.DEF_A;
                if (ps.cells.def) ps.cells.def.textContent = ps.DEF_PCT;
              });
            });
            // Apply energy (NG) from gameData.players so rows show correct energy color on resume
            const playersList = gameData.players || [];
            playersList.forEach((p) => {
              const playerId = p._id ?? p.playerId ?? p.player_id;
              if (!playerId) return;
              const ps = this.playerStats[playerId];
              if (!ps || !ps.cells) return;
              const ng = p.NG ?? p.attributes?.NG ?? 1.0;
              ps.NG = ng;
              const color = getEnergyColor(ng);
              Object.values(ps.cells).forEach((cell) => {
                if (cell) cell.style.color = color;
              });
              if (ps.nameCell) ps.nameCell.style.color = color;
            });
            const homeBox = (homeTeamId && boxScore[homeTeamId]) ? boxScore[homeTeamId] : (boxScore[homeTeam] || {});
            const awayBox = (awayTeamId && boxScore[awayTeamId]) ? boxScore[awayTeamId] : (boxScore[awayTeam] || {});
            if (Object.keys(homeBox).length || Object.keys(awayBox).length) {
              window.currentPlayerStats = { home: homeBox, away: awayBox };
            }
          }
        } catch (err) {
          console.warn('⚠️ Could not refresh box scores from game state:', err);
        }
      }

      if (this.animate) {
        // Count existing sprites in the scene BEFORE creating new ones
        const existingContainers = this.children.list.filter(child => 
          child.type === 'Container' && 
          child.list && 
          child.list.some(item => item.type === 'Circle')
        );
        // console.log('🔍 PRE-CREATION: Existing containers in scene:', existingContainers.length);

        await preloadPlayerHeadshots(this, actualPlayers);

        this.playerSprites = loadPhaserPlayers(this, actualPlayers, Phaser);
        
        // Count sprites AFTER creation
        const postCreationContainers = this.children.list.filter(child => 
          child.type === 'Container' && 
          child.list && 
          child.list.some(item => item.type === 'Circle')
        );
        // console.log('🔍 POST-CREATION: Total containers in scene:', postCreationContainers.length);
        // console.log('🔍 POST-CREATION: playerSprites object size:', Object.keys(this.playerSprites).length);
        
        // Clean up any extra sprites that don't have corresponding playerInfo
        const spriteKeys = Object.keys(this.playerSprites);
        const playerInfoKeys = Object.keys(this.playerInfo || {});
        const extraSprites = spriteKeys.filter(id => !this.playerInfo?.[id]);
        
        // console.log('SPRITE CLEANUP DEBUG:', {
        //   totalSprites: spriteKeys.length,
        //   totalPlayerInfo: playerInfoKeys.length,
        //   spriteKeys,
        //   playerInfoKeys,
        //   extraSprites
        // });
        
        if (extraSprites.length > 0) {
          console.warn('EXTRA SPRITES DETECTED at game start (no playerInfo):', extraSprites);
          extraSprites.forEach(id => {
            const sprite = this.playerSprites[id];
            if (sprite) {
              console.log(`Hiding extra sprite at game start: ${id}`, { 
                team: sprite.team, 
                position: { x: sprite.x, y: sprite.y },
                visible: sprite.visible,
                team_id: sprite.team_id,
                playerId: sprite.playerId
              });
              sprite.setVisible(false);
              // Remove from playerSprites object to prevent future issues
              delete this.playerSprites[id];
            }
          });
        }
        
        // Also check for any sprites that might have been created elsewhere
        // console.log('Final playerSprites after cleanup:', Object.keys(this.playerSprites));
        
        // Check all children in the scene to see if there are any extra sprites
        const allChildren = this.children.list;
        const playerSprites = allChildren.filter(child => 
          child.type === 'Container' && 
          child.list && 
          child.list.some(item => item.type === 'Circle')
        );
        // console.log('All container sprites in scene:', playerSprites.map(sprite => ({
        //   id: sprite.playerId,
        //   team: sprite.team,
        //   position: { x: sprite.x, y: sprite.y },
        //   visible: sprite.visible
        // })));
      }

      const applyPlayerStats = (turn = {}) => {
        if (turn.home_lineup) updateLineup('home', turn.home_lineup);
        if (turn.away_lineup) updateLineup('away', turn.away_lineup);

        if (turn.deltas) {
          for (const [playerId, delta] of Object.entries(turn.deltas)) {
            const ps = this.playerStats[playerId];
            if (ps && delta.stats) {
              for (const [stat, value] of Object.entries(delta.stats)) {
                // Skip REB - it's calculated from OREB + DREB to avoid double-counting
                // REB should NOT be in deltas (backend excludes it), but defensive check just in case
                if (stat === 'REB') continue;
                
                ps[stat] = (ps[stat] || 0) + value;
                if (ps.cells) {
                  // Map stat names to cell keys
                  const statToCellKey = {
                    'PTS': 'pts',
                    'REB': 'reb',
                    'OREB': 'reb',  // Both OREB and DREB update reb
                    'DREB': 'reb',
                    'AST': 'ast',
                    'F': 'fouls',   // Fix: F maps to fouls, not f
                    'STL': 'stl',
                    'BLK': 'blk',
                    'TO': 'to',
                    'DEF_A': 'defAttempts',
                    'DEF_S': 'def'
                  };
                  const cellKey = statToCellKey[stat];
                  
                  if (cellKey && ps.cells[cellKey]) {
                    if (stat === 'DEF_A' || stat === 'DEF_S') {
                      // Update defensive attempts and success rate when defensive stats change
                      if (ps.cells.defAttempts) ps.cells.defAttempts.textContent = ps.DEF_A;
                      const defRate = ps.DEF_A > 0 ? Math.round((ps.DEF_S / ps.DEF_A) * 100) : 0;
                      ps.DEF_PCT = `${defRate}%`;  // Store for S3 tab access
                      ps.cells.def.textContent = ps.DEF_PCT;
                    } else if (stat === 'OREB' || stat === 'DREB') {
                      // Update combined rebounds (OREB + DREB)
                      ps.REB = (ps.OREB || 0) + (ps.DREB || 0);
                      ps.cells.reb.textContent = ps.REB;
                    } else {
                      ps.cells[cellKey].textContent = ps[stat];
                    }
                  }
                }
              }
            }
          }
        }
        
        // Apply energy-based color coding to player rows
        if (turn.player_energy) {
          for (const [playerId, energyData] of Object.entries(turn.player_energy)) {
            const ps = this.playerStats[playerId];
            if (ps && ps.cells) {
              const ng = energyData.NG || 1.0;
              
              // Store current NG in playerStats for tooltip access
              ps.NG = ng;
              
              const color = getEnergyColor(ng);
              
              // Apply color to all cells in the player's row
              Object.values(ps.cells).forEach(cell => {
                if (cell) cell.style.color = color;
              });
              
              // Also apply to name cell if we have a reference to it
              if (ps.nameCell) {
                ps.nameCell.style.color = color;
              }
            }
          }
          syncSpriteAttributesFromPlayerEnergy(this.playerSprites, turn.player_energy);
        }

        // Store live per-player MO for the tooltip (mirrors player_energy → NG).
        if (turn.player_momentum) {
          for (const [playerId, mo] of Object.entries(turn.player_momentum)) {
            const ps = this.playerStats[playerId];
            if (ps) ps.MO = Number(mo) || 0;
          }
          // Refresh box-score momentum glyphs by lineup slot (robust to subs):
          // each row's glyph reflects the current occupant's MO (flame/snowflake
          // at |MO|>=5, hidden otherwise). Name color stays energy-driven.
          // Also evaluate momentum callouts for the 10 on-court players.
          this.moCallout = this.moCallout || {};
          ['home', 'away'].forEach(teamKey => {
            positions.forEach(pos => {
              const row = this.rowRefs?.[teamKey]?.[pos];
              const pid = this.currentLineup?.[teamKey]?.[pos];
              const mo = pid ? (this.playerStats?.[pid]?.MO ?? 0) : 0;
              if (row && row.moGlyph) setBoxScoreMoGlyph(row.moGlyph, mo);
              if (!pid) return;

              // Streak tracking (±5 scale): announce once per crossing on the way
              // UP at |MO| 3 (warm), 4 and 5 (hot); never when cooling. Reset when
              // the player drops below |MO| 3 or flips sign / crosses 0. announcedMag
              // is the streak's high-water mark, so re-climbing doesn't re-fire,
              // and a single big jump fires only the most extreme level reached.
              const mag = Math.abs(mo);
              const sign = mo > 0 ? 1 : (mo < 0 ? -1 : 0);
              let st = this.moCallout[pid];
              if (!st || mag < MO_WARM_MAG || sign !== st.sign) {
                st = { sign, announcedMag: 0 };
              }
              if (mag >= MO_WARM_MAG && sign !== 0 && mag > st.announcedMag) {
                st.announcedMag = mag; // advance even if the callout yields/drops
                fireMomentumCallout(this, pid, teamKey, sign, mo);
              }
              this.moCallout[pid] = st;
            });
          });
        }
      };

      const applyTeamStats = (turn = {}) => {
        // Simple approach: read team stats directly from turn data (like turn.score)
        // Update if we have team_stats (S2 tab) or team_totals (S1 tab)
        if ((!turn.team_stats && !turn.team_totals) || typeof window.setTeamBoxData !== 'function') {
          return;
        }

        const homeOffense = turn.team_stats?.[homeTeam]?.offense || {};
        const awayOffense = turn.team_stats?.[awayTeam]?.offense || {};
        const homeDefense = turn.team_stats?.[homeTeam]?.defense || {};
        const awayDefense = turn.team_stats?.[awayTeam]?.defense || {};
        
        // ✅ UNIFIED STRUCTURE: Get team attributes from unified teams object
        // Reuse team objects from outer scope if available, otherwise get from simData
        let localHomeTeamObj = homeTeamObj;
        let localAwayTeamObj = awayTeamObj;
        if (!localHomeTeamObj && simData.home_team_id && simData.teams) {
          localHomeTeamObj = simData.teams[simData.home_team_id];
        }
        if (!localHomeTeamObj) {
          localHomeTeamObj = typeof simData.home_team === 'object' ? simData.home_team : null;
        }
        if (!localAwayTeamObj && simData.away_team_id && simData.teams) {
          localAwayTeamObj = simData.teams[simData.away_team_id];
        }
        if (!localAwayTeamObj) {
          localAwayTeamObj = typeof simData.away_team === 'object' ? simData.away_team : null;
        }
        const homeAttrs = localHomeTeamObj?.attributes || simData.team_attributes?.[homeTeam] || {};
        const awayAttrs = localAwayTeamObj?.attributes || simData.team_attributes?.[awayTeam] || {};
        
        // Get cumulative team stats for S1 tab
        const homeTotals = turn.team_totals?.[homeTeam] || {};
        const awayTotals = turn.team_totals?.[awayTeam] || {};
        
        // Store team plays and stats data for tooltips
        if (turn.team_plays) {
          this.teamPlaysData = turn.team_plays;
        }
        if (turn.team_stats) {
          this.teamStatsData = turn.team_stats;
        }

        // Update UI directly from turn data (like scoreboard updates)
        window.setTeamBoxData({
          home: {
            offense: homeOffense,
            defense: homeDefense,
            attributes: homeAttrs,
            totals: homeTotals
          },
          away: {
            offense: awayOffense,
            defense: awayDefense,
            attributes: awayAttrs,
            totals: awayTotals
          }
        });
      };

      const formatTurnText = (turn = {}) => {
        const parts = [];
        
        // Add turn number for debugging
        if (turn.index !== undefined) {
          parts.push(`Turn ${turn.index}:`);
        }
        
        const q =
          turn.period_label ||
          (turn.quarter != null
            ? turn.quarter > 4
              ? `OT${turn.quarter - 4}`
              : `Q${turn.quarter}`
            : null);
        const clk = turn.clock || turn.game_clock;
        if (q || clk) {
          const timePart = [q, clk].filter(Boolean).join(' ');
          parts.push(`[${timePart}]`);
        }
        if (turn.team) {
          const teamName =
            turn.team === 'home'
              ? homeTeam
              : turn.team === 'away'
              ? awayTeam
              : turn.team;
          parts.push(teamName);
        }
        if (turn.text) parts.push(turn.text);
        return parts.join(' ');
      };

      // Live scoreboard state - force to 0 for new games
      // Only use persisted scores if continuing an existing game
      // ✅ TIMEOUT RESUME: Check team objects first (same pattern as timeouts) for consistency
      const homeScoreFromData = homeTeamObj?.score ?? simData.score?.[homeTeam];
      const awayScoreFromData = awayTeamObj?.score ?? simData.score?.[awayTeam];
      const liveScore = {
        [homeTeam]: isNewGame ? 0 : (homeScoreFromData ?? 0),
        [awayTeam]: isNewGame ? 0 : (awayScoreFromData ?? 0),
      };
      
        // Explicitly reset scoreboard UI for new games
        if (isNewGame) {
          // ✅ REFACTOR: Direct DOM updates (same as other scoreboard items)
          if (homeScoreEl) homeScoreEl.textContent = 0;
          if (awayScoreEl) awayScoreEl.textContent = 0;
          // Initialize timeout display for new games (default 4)
          if (homeTolEl) homeTolEl.textContent = 'TOL: 4';
          if (awayTolEl) awayTolEl.textContent = 'TOL: 4';
        }
      // ✅ TIMEOUT RESUME: Check team objects first (same pattern as timeouts) for consistency
      const homeFoulsFromData = homeTeamObj?.team_fouls ?? simData.fouls?.home;
      const awayFoulsFromData = awayTeamObj?.team_fouls ?? simData.fouls?.away;
      let liveHomeFouls = typeof homeFoulsFromData === 'number' ? homeFoulsFromData : 0;
      let liveAwayFouls = typeof awayFoulsFromData === 'number' ? awayFoulsFromData : 0;
      // Extract timeouts from nested team objects or flat structure, default to 5 for new games
      const homeTimeoutsFromData = homeTeamObj?.timeouts ?? simData.timeouts?.home ?? simData.home_team_timeouts;
      const awayTimeoutsFromData = awayTeamObj?.timeouts ?? simData.timeouts?.away ?? simData.away_team_timeouts;
      let liveHomeTimeouts = typeof homeTimeoutsFromData === 'number' ? homeTimeoutsFromData : (isNewGame ? 4 : 4);
      let liveAwayTimeouts = typeof awayTimeoutsFromData === 'number' ? awayTimeoutsFromData : (isNewGame ? 4 : 4);
      const noImpactShotClockTypes = new Set(['FREE_THROW', 'BASELINE_INBOUND', 'SIDE_INBOUND']);
      const isNoImpactShotClockTurn = (turn = {}) => noImpactShotClockTypes.has(turn?.result_type);

      const updateScoreboard = (turn = {}) => {
        const prevHome = liveScore[homeTeam];
        const prevAway = liveScore[awayTeam];
        
        // ✅ TIMEOUT: Track if we're updating from initial values (not a turn)
        const isInitialUpdate = turn.score && !turn.index && !turn.result_type;

        // ``turn.score`` is authoritative. ``turn.points`` may appear in the
        // payload for context but must **not** be re-applied here to avoid
        // double counting.
        if (turn.score) {
          if (typeof turn.score[homeTeam] === 'number') liveScore[homeTeam] = turn.score[homeTeam];
          if (typeof turn.score[awayTeam] === 'number') liveScore[awayTeam] = turn.score[awayTeam];
        }

        // ✅ TIMEOUT: Update fouls from turn data (exact same pattern as scores)
        if (turn.homeFouls !== undefined || turn.awayFouls !== undefined) {
          if (typeof turn.homeFouls === 'number') liveHomeFouls = turn.homeFouls;
          if (typeof turn.awayFouls === 'number') liveAwayFouls = turn.awayFouls;
        }
        // Also check alternative keys (for turn data)
        const homeF = turn.home_team_fouls ?? turn.fouls?.home;
        const awayF = turn.away_team_fouls ?? turn.fouls?.away;
        if (typeof homeF === 'number') liveHomeFouls = homeF;
        if (typeof awayF === 'number') liveAwayFouls = awayF;

        // ✅ TIMEOUT: Update timeouts from turn data (exact same pattern as scores and fouls)
        if (turn.homeTimeouts !== undefined || turn.awayTimeouts !== undefined) {
          if (typeof turn.homeTimeouts === 'number') liveHomeTimeouts = turn.homeTimeouts;
          if (typeof turn.awayTimeouts === 'number') liveAwayTimeouts = turn.awayTimeouts;
        }
        // Also check alternative keys (for turn data)
        const homeT = turn.home_team_timeouts ?? turn.timeouts?.home;
        const awayT = turn.away_team_timeouts ?? turn.timeouts?.away;
        if (typeof homeT === 'number') liveHomeTimeouts = homeT;
        if (typeof awayT === 'number') liveAwayTimeouts = awayT;

        if (turn.clock || turn.game_clock) {
          liveClock = turn.clock || turn.game_clock;
          // ✅ TIMEOUT: Update scene.simData.clock so it's accessible for timeout navigation
          if (this.simData) {
            this.simData.clock = liveClock;
          }
        }
        // Same code path for both clocks: get incoming value (explicit then contract end), then sync. Game: monotonic check. Shot: backend authority only (Shot_Clock_System.md — live clock end-of-turn snap).
        const incomingGameSec = typeof turn.time_remaining === 'number'
          ? Math.max(0, Math.floor(turn.time_remaining))
          : (turn.clock || turn.game_clock)
            ? parseClockToSeconds(turn.clock || turn.game_clock)
            : Number.isFinite(Number(turn?.clock_end ?? turn?.clockEnd))
              ? Math.max(0, Math.floor(Number(turn.clock_end ?? turn.clockEnd)))
              : null;
        // Single source: turn/response from backend (shot_clock_remaining, then contract end, then start). No frontend reset logic.
        const incomingShotSecRaw = Number(turn?.shot_clock_remaining ?? turn?.shotClockRemaining ?? turn?.shot_clock_end ?? turn?.shotClockEnd ?? turn?.shot_clock_start ?? turn?.shotClockStart);
        const incomingShotSec = Number.isFinite(incomingShotSecRaw) ? Math.max(0, Math.min(30, Math.floor(incomingShotSecRaw))) : null;

        if (this.gameClock && Number.isFinite(incomingGameSec)) {
          const clockState = this.gameClock.getState?.() || {};
          const currentClockSec = Number.isFinite(clockState.timeRemaining) ? clockState.timeRemaining : null;
          const incomingQuarter = (typeof turn.quarter === 'number') ? turn.quarter : liveQuarter;
          const allowIncrease = incomingQuarter > liveQuarter;
          const nonMonotonicSlackSeconds = Math.max(
            0,
            Number(window?.UESS_CLOCK_NON_MONOTONIC_SLACK_SECONDS ?? 1) || 1
          );
          const inboundOrBoundaryTypes = new Set([
            'FREE_THROW',
            'SIDE_INBOUND',
            'BASELINE_INBOUND',
            'TIMEOUT',
            'PUTBACK_MAKE',
            'PUTBACK_MISS',
            'OREB_KICKOUT',
          ]);
          const resultTypeKey = String(turn?.result_type || '').toUpperCase();
          const increaseDeltaSeconds =
            currentClockSec == null ? 0 : Number(incomingGameSec) - Number(currentClockSec);
          const allowBoundarySlackIncrease =
            increaseDeltaSeconds > 0 &&
            increaseDeltaSeconds <= nonMonotonicSlackSeconds &&
            inboundOrBoundaryTypes.has(resultTypeKey);

          if (
            currentClockSec == null ||
            allowIncrease ||
            incomingGameSec <= currentClockSec ||
            allowBoundarySlackIncrease
          ) {
            this.gameClock.syncWithBackend(incomingGameSec);
          } else {
            console.warn('⏱️ Ignoring non-monotonic clock update', {
              currentClockSec,
              incomingClockSec: incomingGameSec,
              increaseDeltaSeconds,
              nonMonotonicSlackSeconds,
              allowBoundarySlackIncrease,
              liveQuarter,
              incomingQuarter,
              result_type: turn.result_type
            });
          }
        }
        if (this.shotClock && incomingShotSec !== null) {
          this.shotClock.syncWithBackend(incomingShotSec);
        }
        if (this.shotClock && isNoImpactShotClockTurn(turn)) {
          this.shotClock.pause('no_impact_turn');
        }

        let shotSecForCritical = incomingShotSec;
        if (shotSecForCritical == null && this.shotClock?.getState) {
          const st = this.shotClock.getState();
          if (Number.isFinite(st?.timeRemaining)) shotSecForCritical = st.timeRemaining;
        }
        if (isNoImpactShotClockTurn(turn)) {
          syncShotClockCriticalClass(null);
        } else {
          syncShotClockCriticalClass(shotSecForCritical);
        }

        if (turn.quarter != null) liveQuarter = turn.quarter;
        if (turn.period_label) {
          livePeriodLabel = turn.period_label;
        } else if (turn.quarter != null) {
          livePeriodLabel = turn.quarter > 4 ? `OT${turn.quarter - 4}` : `Q${turn.quarter}`;
        }

        // Reactive gameplay music: every real turn re-evaluates which track
        // should play. Switches to/from crunch (pixel-pulse) and default
        // (arcade-pulse) are hard-cut at this boundary.
        //
        // Skip on the initial pre-turn render — that fires before any
        // animation runs and would start music during the Q1 opening-tip
        // window where we explicitly want silence until the tip-winner SFX.
        // The on-load evaluator in create() has already set the right
        // initial track for non-opening-tip entries.
        if (!isInitialUpdate) {
          evaluateGameplayTrack({
            quarter: liveQuarter,
            clock: this.gameClock?.getState?.()?.timeRemaining,
            homeScore: liveScore[homeTeam],
            awayScore: liveScore[awayTeam],
          });
        }

        // ✅ REFACTOR: Direct DOM updates for all scoreboard items (consistent pattern)
        if (homeScoreEl) homeScoreEl.textContent = liveScore[homeTeam];
        if (awayScoreEl) awayScoreEl.textContent = liveScore[awayTeam];
        if (homeFoulsEl) homeFoulsEl.textContent = `F: ${liveHomeFouls}`;
        if (awayFoulsEl) awayFoulsEl.textContent = `F: ${liveAwayFouls}`;
        if (homeTolEl) homeTolEl.textContent = `TOL: ${liveHomeTimeouts}`;
        if (awayTolEl) awayTolEl.textContent = `TOL: ${liveAwayTimeouts}`;
        // Clock text is written only by gameClock (single-writer authority).
        if (quarterEl) quarterEl.textContent = livePeriodLabel;

        const awayRankEl = document.getElementById('away-rank');
        const awayRecEl = document.getElementById('away-record');
        const homeRankEl = document.getElementById('home-rank');
        const homeRecEl = document.getElementById('home-record');
        const sd = this.simData || simData;
        const fromWin =
          typeof window !== 'undefined' && window.__gobCourtScoreboardMetaByName &&
          typeof window.__gobCourtScoreboardMetaByName === 'object'
            ? window.__gobCourtScoreboardMetaByName
            : {};
        const fromTurn = sd?.team_scoreboard_meta && typeof sd.team_scoreboard_meta === 'object' ? sd.team_scoreboard_meta : {};
        if (Object.keys(fromTurn).length) {
          this._courtScoreboardMetaByName = { ...(this._courtScoreboardMetaByName || {}), ...fromTurn };
        }
        const mergedTsm = {
          ...fromWin,
          ...(this._courtScoreboardMetaByName || {}),
          ...fromTurn,
        };
        const sdSb = sd && Object.keys(mergedTsm).length ? { ...sd, team_scoreboard_meta: mergedTsm } : sd;
        const rowHome = resolveTeamRowForScoreboard(sdSb, 'home');
        const rowAway = resolveTeamRowForScoreboard(sdSb, 'away');
        if (awayRankEl) awayRankEl.textContent = formatSbRank(rowAway);
        if (awayRecEl) awayRecEl.textContent = formatSbRecord(rowAway);
        if (homeRankEl) homeRankEl.textContent = formatSbRank(rowHome);
        if (homeRecEl) homeRecEl.textContent = formatSbRecord(rowHome);

        if (isCourtDebugScoreboard()) {
          const sig = `${formatSbRank(rowAway)}|${formatSbRecord(rowAway)}|${formatSbRank(rowHome)}|${formatSbRecord(rowHome)}`;
          if (typeof window !== 'undefined' && window.__courtSbDbgSig !== sig) {
            window.__courtSbDbgSig = sig;
            console.info('[court scoreboard] updateScoreboard → #away-rank/#home-rank text', {
              away_rank_text: formatSbRank(rowAway),
              away_rec_text: formatSbRecord(rowAway),
              home_rank_text: formatSbRank(rowHome),
              home_rec_text: formatSbRecord(rowHome),
              turn_index: turn?.index,
            });
          }
        }

        updateMomentumBar('home', momentumValueForTeam(rowHome, turn, 'home'));
        updateMomentumBar('away', momentumValueForTeam(rowAway, turn, 'away'));

        const mySide = urlParams.get('my_team');
        if (mySide === 'home') {
          updateTimeoutPipsUsedCount(liveHomeTimeouts);
        } else if (mySide === 'away') {
          updateTimeoutPipsUsedCount(liveAwayTimeouts);
        }

        // Playcall strip lifecycle now starts from updatePlaycallCenter() at HCO turn start
        // and hides from finalizeTurnAfterAnimation() when the instigating event resolves.
        // Keeping the old scoreboard-driven implementation commented for easy rollback.
        /*
        if (isHcoTurnContext(turn)) {
          const offPlay = turn.offensive_playcall || turn.current_playcall || '';
          const focusRaw = turn.offensive_play_focus || turn.offensive_focus || '';
          const focus =
            typeof focusRaw === 'string' && focusRaw.length
              ? focusRaw.charAt(0).toUpperCase() + focusRaw.slice(1)
              : '';
          const defPlay =
            turn.defensive_playcall_display || turn.defensive_playcall || turn.defense_playcall || '';
          showPlaycallStrip(offPlay, focus, defPlay);
        } else {
          hidePlaycallStrip();
        }
        */

        applyPlayerStats(turn);
        applyTeamStats(turn);

        // Check for foul out and show popup
        // NOTE: foul-out can surface as either:
        // - a regular turn with ``fouled_out`` + ``foul_out_player`` (common), or
        // - a TIMEOUT turn with ``timeout_reason=FOUL_OUT`` (backend always sends foul_out_player; use placeholder if missing).
        const isFoulOutTimeoutTurn = turn.result_type === 'TIMEOUT' && turn.timeout_reason === 'FOUL_OUT';
        const isFoulOutFlaggedTurn = turn.fouled_out && turn.foul_out_player;
        const shouldShowFoulOutPopup = isFoulOutFlaggedTurn || isFoulOutTimeoutTurn;
        const rawFoulOutPlayer = turn.foul_out_player || (isFoulOutTimeoutTurn ? { name: 'Unknown', player_id: null, team: null, photo: null } : null);
        // Resolve fouled-out player from simData by id so we always show the player who fouled out (not the player who was fouled)
        const foulOutId = rawFoulOutPlayer?.player_id ?? rawFoulOutPlayer?.playerId;
        const foulOutPlayer = (foulOutId && this.simData?.players)
          ? (this.simData.players.find(p => (p.playerId ?? p.player_id) === foulOutId) || rawFoulOutPlayer)
          : rawFoulOutPlayer;

        if (shouldShowFoulOutPopup && foulOutPlayer && !document.querySelector('.foul-out-popup')) {
          // Dynamically import foul out popup
          import('./utils/foulOutPopup.js').then(({ showFoulOutPopup }) => {
            // Get game context from scene
            const mode = this.mode || (typeof sessionStorage !== 'undefined' ? sessionStorage.getItem('mode') : null) || 'single';
            const urlParams = new URLSearchParams(window.location.search);
            const tournamentId = urlParams.get('tournament_id') || null;
            const franchiseId = urlParams.get('franchise_id') || null;
            
            // Get team information from gameStore or URL
            const { home: homeTeam, away: awayTeam } = gameStore.getTeams();
            const homeId = this.homeTeamId || urlParams.get('home_id');
            const awayId = this.awayTeamId || urlParams.get('away_id');
            const myTeamSide = urlParams.get('my_team');
            const userTeamId = urlParams.get('user_team_id');
            
            showFoulOutPopup({
              player: foulOutPlayer,
              foulOutPlayerId: foulOutId,
              gameId: this.gameId,
              mode: mode,
              quarter: liveQuarter,
              clock: liveClock, // ✅ Pass current clock time to preserve it
              tournamentId: tournamentId,
              franchiseId: franchiseId,
              homeTeam: homeTeam,
              awayTeam: awayTeam,
              homeId: homeId,
              awayId: awayId,
              myTeamSide: myTeamSide,
              userTeamId: userTeamId
            });
          }).catch(err => {
            console.error('Failed to load foul out popup:', err);
          });
        }

        // ✅ REFACTOR: Scores now use direct DOM updates (same as fouls/timeouts/clock)
        // No need for event system - scores are updated directly above with other scoreboard items

        if (turn.text && turn.index !== this.lastTurnShown) {
          if (typeof window !== 'undefined' && window.TEXT_SCROLL_ENABLED) {
            // Display debug info first (if available)
            if (turn.debug_turn_start) {
              appendToTextScroll(turn.debug_turn_start);
            }
            
            // Display normal turn text
            appendToTextScroll(formatTurnText(turn));
            
            // Display debug result info (if available)
            if (turn.debug_turn_result) {
              appendToTextScroll(turn.debug_turn_result);
            }
          }
          this.lastTurnShown = turn.index;
        }
      };

      // Show cumulative state immediately
      // ✅ TIMEOUT: updateScoreboard() now handles initial score updates (same system as other items)
      updateScoreboard({
        score: liveScore,  // Pass scores so updateScoreboard can update them
        homeFouls: liveHomeFouls,
        awayFouls: liveAwayFouls,
        homeTimeouts: liveHomeTimeouts,  // ✅ TIMEOUT: Pass timeouts for immediate update
        awayTimeouts: liveAwayTimeouts,
        clock: liveClock,
        quarter: liveQuarter,
        period_label: livePeriodLabel,
      });

      const pauseBtn = document.getElementById('pause-btn');
      const skipBtn = document.getElementById('skip-btn');
      const gameSpeedBtn = document.getElementById('game-speed-btn');
      const speedDropdown = document.getElementById('speed-dropdown');
      this.isPaused = false;
      this.skipToEnd = false;
      this.isSkipping = false;
      this.finalized = false;
      
      // Initialize game speed from localStorage
      const { loadSpeedPreference, setGameSpeed, getSpeedPresets } = await import('./utils/gameSpeedManager.js');
      const initialSpeed = loadSpeedPreference();
      updateSpeedDropdown(initialSpeed);
      
      // Game Speed button handler
      if (gameSpeedBtn && speedDropdown && !gameSpeedBtn.disabled) {
        const positionSpeedDropdown = () => {
          if (!gameSpeedBtn || !speedDropdown) return;
          const rect = gameSpeedBtn.getBoundingClientRect();
          speedDropdown.style.left = `${Math.round(rect.left)}px`;
          speedDropdown.style.top = `${Math.round(rect.top - speedDropdown.offsetHeight - 8)}px`;
        };

        gameSpeedBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          if (typeof window.playSound === 'function') window.playSound('click-tiny.wav');
          const isVisible = speedDropdown.style.display !== 'none';
          if (isVisible) {
            speedDropdown.style.display = 'none';
          } else {
            speedDropdown.style.display = 'flex';
            positionSpeedDropdown();
          }
        });

        window.addEventListener('resize', () => {
          if (speedDropdown.style.display !== 'none') {
            positionSpeedDropdown();
          }
        });
        
        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
          if (!speedDropdown.contains(e.target) && e.target !== gameSpeedBtn) {
            speedDropdown.style.display = 'none';
          }
        });
        
        // Speed option handlers
        const speedOptions = speedDropdown.querySelectorAll('.speed-option');
        speedOptions.forEach(option => {
          option.addEventListener('click', (e) => {
            e.stopPropagation();
            if (typeof window.playSound === 'function') window.playSound('click-tiny.wav');
            const speed = parseInt(option.dataset.speed, 10);
            setGameSpeed(speed);
            updateSpeedDropdown(speed);
            speedDropdown.style.display = 'none';
          });
        });
      } else if (speedDropdown) {
        speedDropdown.style.display = 'none';
      }
      
      function updateSpeedDropdown(currentSpeed) {
        if (!speedDropdown) return;
        const speedOptions = speedDropdown.querySelectorAll('.speed-option');
        speedOptions.forEach(option => {
          const optionSpeed = parseInt(option.dataset.speed, 10);
          if (optionSpeed === currentSpeed) {
            option.classList.add('active');
          } else {
            option.classList.remove('active');
          }
        });
      }
      
      if (pauseBtn) {
        pauseBtn.addEventListener('click', () => {
          if (typeof window.playSound === 'function') window.playSound('click-tiny.wav');
          this.isPaused = !this.isPaused;
          if (this.isPaused) {
            setUessTimingState('pause', true);
            syncSceneTimePaused(this, true);
            // Pause all tweens
            if (this.tweens) {
              this.tweens.pauseAll();
              const activeTweens = this.tweens.getAll ? this.tweens.getAll() : [];
              if (DEBUG_FLOW) console.log('⏸️ Game paused', {
                activeTweensCount: activeTweens.length,
                tweenManagerPaused: typeof this.tweens.isPaused === 'function' ? this.tweens.isPaused() : 'N/A',
                tweenManagerTimeScale: this.tweens.timeScale
              });
            }
            if (this.gameClock) this.gameClock.pause('user_pause');
            if (this.shotClock) this.shotClock.pause('user_pause');
            pauseGameplayTrack();
            syncPauseButtonDom(true);
          } else {
            setUessTimingState('pause', false);
            syncSceneTimePaused(this, false);
            // Resume all tweens
            if (this.tweens) {
              // Ensure timeScale is set to 1 (normal speed) - it might have been set to 0
              if (typeof this.tweens.timeScale !== 'undefined') {
                this.tweens.timeScale = 1;
              }
              
              // Resume all existing tweens
              this.tweens.resumeAll();
              
              // Also explicitly resume each tween individually (in case resumeAll() doesn't work)
              const activeTweens = this.tweens.getAll ? this.tweens.getAll() : [];
              activeTweens.forEach(tween => {
                if (tween) {
                  // Try multiple methods to ensure tween resumes
                  if (typeof tween.resume === 'function') {
                    tween.resume();
                  }
                  if (typeof tween.play === 'function' && !tween.isPlaying()) {
                    tween.play();
                  }
                  // If tween has an isPaused check, ensure it's not paused
                  if (typeof tween.isPaused === 'function' && tween.isPaused()) {
                    if (typeof tween.resume === 'function') {
                      tween.resume();
                    }
                  }
                  // Ensure tween's timeScale is set to 1 (normal speed)
                  if (typeof tween.timeScale !== 'undefined') {
                    tween.timeScale = 1;
                  }
                }
              });
              
              if (DEBUG_FLOW) console.log('▶️ Game resumed', {
                activeTweensCount: activeTweens.length,
                tweenManagerPaused: typeof this.tweens.isPaused === 'function' ? this.tweens.isPaused() : 'N/A',
                tweenManagerTimeScale: this.tweens.timeScale,
                resumedTweens: activeTweens.length
              });
            }
            if (this.gameClock) this.gameClock.resume('user_pause');
            if (this.shotClock) this.shotClock.resume('user_pause');
            resumeGameplayTrack();

            syncPauseButtonDom(false);
          }
        });
      }
      if (skipBtn && DEBUG_SKIP) {
        skipBtn.addEventListener('click', async () => {
          if (this.isSkipping) return;
          this.skipToEnd = true;
          this.isSkipping = true;
          this.isPaused = false;
          skipBtn.disabled = true;
          syncPauseButtonDom(false);
          this.tweens.resumeAll();
          this.tweens.getAllTweens().forEach(t => t.stop());
          await finalize();
        });
      }

      const finalize = async () => {
        if (this.finalized) return this.finalScore;
        const finalScore = await finalizeGame({
          simData,
          tournamentId: this.tournamentId,
          franchiseId: this.franchiseId,
          game: this.game,
        });
        this.finalScore = finalScore;
        this.finalized = true;
        if (window.GOB_Analytics) {
          if (this.tournamentId) window.GOB_Analytics.tournamentGameCompleted();
          else if (this.franchiseId) window.GOB_Analytics.franchiseGameCompleted();
          else window.GOB_Analytics.singleGameCompleted();
        }
        // Show game completion popup (absolute path for Netlify/module resolution)
        const base = (typeof window !== 'undefined' && window.API_CONFIG) ? window.API_CONFIG.getStaticPath() : '';
        const { showGameCompletionPopup } = await import(`${base}/js/phaser/utils/gameCompletionPopup.js`);
          showGameCompletionPopup({
            gameId: this.gameId || simData.game_id,
            mode: getGameMode({ scene: this, tournamentId: this.tournamentId, franchiseId: this.franchiseId }),
            tournamentId: this.tournamentId,
            franchiseId: this.franchiseId,
            teamId: this.teamId,
            userTeamSide: this.userTeamSide,
            finalScore: finalScore,
            gameData: simData
          });
        
        return finalScore;
      };

      // console.log('🚨 GAMESCENE: animate parameter:', this.animate);
      // console.log('🚨 GAMESCENE: typeof animate:', typeof this.animate);
      
      if (this.animate) {
        // console.log('🚨 GAMESCENE: Taking animation path');
        const courtKey = "court-bg";

        const startAnimation = async () => {
          const spriteKeys = Object.keys(this.playerSprites || {});
          if (urlParams.get('resume_from_anchor') === 'true' || urlParams.get('active_resume') === 'true') {
            const firstTurn = Array.isArray(simData.turns) ? simData.turns[0] : null;
            console.warn('[RESUME-ANCHOR-CLIENT] animation start', {
              sprite_count: spriteKeys.length,
              turns: Array.isArray(simData.turns) ? simData.turns.length : 0,
              first_turn_type: firstTurn?.result_type || null,
              first_turn_animation_steps: Array.isArray(firstTurn?.animation_steps) ? firstTurn.animation_steps.length : 0,
              first_turn_animations: Array.isArray(firstTurn?.animations) ? firstTurn.animations.length : 0,
              should_show_matchups_popup: !!this.shouldShowMatchupsPopup,
            });
          }
          if (DEBUG_TEAMS) {
            console.log('playerSprites keys:', spriteKeys);
          }
          const turnIds = Array.from(new Set((simData.turns || []).flatMap(t => {
            const ids = [];
            if (t.playerId) ids.push(t.playerId);
            if (t.player_id) ids.push(t.player_id);
            if (Array.isArray(t.animations)) {
              t.animations.forEach(a => {
                if (a.playerId) ids.push(a.playerId);
                if (a.player_id) ids.push(a.player_id);
              });
            }
            return ids;
          })));
          if (DEBUG_FLOW) console.log('IDs in turns:', turnIds);

          if (DEBUG_TEAMS) {
            simData.players.forEach(p => {
              console.log(`Sprite initialized: ${p.name} -> ${p.team}`);
            });
          }

          // ✅ DEFENSE MATCHUPS: Show popup before animation starts (if needed)
          // Only show popup if animate=true (Play Quarter was pressed), not for Sim Quarter/Sim Full Game
          if (this.shouldShowMatchupsPopup && this.animate) {
            try {
              const { showDefenseMatchupsPopup, resetDontShowAgainFlag } = await import('./utils/defenseMatchupsPopup.js');
              // Reset only for a truly new game (new game_id at Q1), not URL-shape heuristics.
              if (isNewGame) {
                resetDontShowAgainFlag(this.gameId);
              }

              // Show popup and wait for user to submit before starting animation
              if (shouldGateCourtEntryVisuals) {
                hideCourtEntryVisualGate();
              }
              await showDefenseMatchupsPopup(this.gameId, this);
              if (shouldGateCourtEntryVisuals) {
                showCourtEntryVisualGate();
              }
            } catch (error) {
              console.error('❌ DEFENSE MATCHUPS: Failed to show popup:', error);
              // Don't block gameplay if popup fails
              if (shouldGateCourtEntryVisuals) {
                showCourtEntryVisualGate();
              }
            }
          }

          // Gameplay music: starts now for every non-Q1-opening-tip entry.
          // If the Defense Matchups modal rendered, the await above blocked
          // until the user clicked Submit Matchups → music starts on submit.
          // If the modal was skipped (don't-show-again, sim mode), music
          // starts immediately. Q1 opening tip is still deferred to the
          // tip-winner SFX in openingTip.js.
          if (!isQ1Start) {
            evaluateGameplayTrack({
              quarter: this.quarter,
              clock: urlParams.get('clock'),
              homeScore: urlParams.get('home_score'),
              awayScore: urlParams.get('away_score'),
            });
          }

          this.ballSprite = this.add.image(0, 0, "ball").setVisible(true).setDepth(1000).setScale(1.5);  // 50% larger

          // Initialize BallController for the new animation system
          try {
            const { initializeBallController } = await import('./animation/BallControllerAdapter.js');
            this.ballController = initializeBallController(this, this.ballSprite);
            if (DEBUG_FLOW) {
              console.log('🎬 GameScene: BallController initialized');
            }
          } catch (error) {
            console.error('🎬 GameScene: Failed to initialize BallController:', error);
          }

          if (typeof window !== 'undefined') {
            const defenseTransitionWasActive = !!window.__GOB_DEFENSE_MATCHUPS_TRANSITION_OVERLAY__;
            window.__GOB_DEFENSE_MATCHUPS_TRANSITION_OVERLAY__ = false;
            if (shouldGateCourtEntryVisuals || window.__GOB_COURT_ENTRY_VISUAL_GATE__) {
              hideCourtEntryVisualGate();
            } else if (defenseTransitionWasActive && window.PageLoadOverlay && typeof window.PageLoadOverlay.hide === 'function') {
              window.PageLoadOverlay.hide();
            }
          }

          this.tweens.add({
            targets: this.ballSprite,
            scale: { from: 1, to: 1.3 },
            duration: 400,
            yoyo: true,
            repeat: -1,
            ease: 'Sine.easeInOut'
          });

          let animStart;
          if (DEBUG_FLOW) {
            animStart = Date.now();
            console.log('🚀 animateGameTurns start', animStart);
          }
          
          // Turn-by-turn simulation loop
          // Initial turns (opening tip for Q1, empty for Q2+) are passed in
          // Turns are generated on-demand via /api/simulate-turn calls
          // ✅ REMOVED: Starting quarter logging (cluttering console)
          const turnResult = await this.simulateTurnByTurn(simData, updateScoreboard);
          
          // ✅ FIX: Skip quarter completion logic if timeout was detected
          // Timeout navigation is handled by timeoutButtonManager, so we should exit here
          if (turnResult?.timeoutDetected) {
            console.log('⏸️ TIMEOUT: simulateTurnByTurn returned timeoutDetected=true - skipping quarter completion logic');
            return; // Exit - timeout navigation is handled elsewhere
          }
          
          console.log('🎬 GameScene: Turn-by-turn simulation completed');
          if (DEBUG_FLOW) {
            const animEnd = Date.now();
            console.log('🏁 animateGameTurns finish', animEnd, 'duration', animEnd - animStart);
          }

          if (DEBUG_FLOW) {
            console.log('🧭 Navigation condition', {
              isFinal: this.isFinal,
              quarter: this.quarter,
              turnCount: quarterTurns.length
            });
          }

          if (DEBUG_FLOW) console.log("✅ GameScene animation complete");
          if (this.isFinal) {
            await finalize();
          } else {
            console.log('✅ Quarter complete - showing locker room popup');
            const nextQ = this.quarter + 1;

            // ✅ SS&S: Use TimeoutNavigationHelper (same as Sim Quarter and other quarter-break paths)
            // Ensures resume_from_timeout=false so next court load shows Gameplay Buttons popup
            const helper = window.TimeoutNavigationHelper;
            let params;
            if (!helper) {
              const fallback = new URLSearchParams(window.location.search);
              fallback.set('game_id', this.gameId);
              fallback.set('quarter', nextQ);
              fallback.set('period', `Q${nextQ}`);
              fallback.set('resume_from_timeout', 'false');
              params = fallback;
            } else {
              const teams = gameStore.getTeams();
              const sourceParams = new URLSearchParams(window.location.search);
              params = helper.buildGameNavigationParams({
                sourceParams: sourceParams,
                targetQuarter: nextQ,
                gameId: this.gameId,
                resumeFromTimeout: false, // Quarter break, not timeout resume
                lineup: {},
                myTeamSide: this.userTeamSide || 'home',
                overrides: {
                  home: teams.home,
                  away: teams.away,
                  mode: this.mode,
                  tournament_id: this.tournamentId,
                  franchise_id: this.franchiseId,
                  team_id: this.teamId
                }
              });
            }
            params.set('quarter_break_from', 'play_quarter');

            // Create locker room popup
            const popup = document.createElement('div');
            popup.className = 'locker-room-popup';
            popup.innerHTML = `
              <div class="locker-room-content">
                <h2>Quarter ${this.quarter} Complete!</h2>
                <button class="locker-room-button">Go To Locker Room</button>
              </div>
            `;
            document.body.appendChild(popup);

            const button = popup.querySelector('.locker-room-button');
            button.addEventListener('click', () => {
              if (typeof window.playSound === 'function') window.playSound('click-tiny.wav');
              window.location.href = `/set-lineup.html?${params.toString()}`;
            });

            return;
          }
      };

        const logAndStart = () => {
          DEBUG_FLOW && console.log('skipToEnd before startAnimation:', this.skipToEnd);
          startAnimation();
        };

        if (this.textures.exists(courtKey)) {
          this.add.image(0, 0, courtKey)
              .setOrigin(0)
              .setDisplaySize(this.game.config.width, this.game.config.height)
              .setDepth(0);
          logAndStart();
        } else {
          this.load.once("complete", () => {
              this.add.image(0, 0, courtKey)
              .setOrigin(0)
              .setDisplaySize(this.game.config.width, this.game.config.height)
              .setDepth(0);
              logAndStart();
          });
          this.load.start();
        }
      } else {
        // console.log('🚨 GAMESCENE: Taking NO animation path - skipping to next quarter');
        if (this.isFinal) {
          await finalize();
        } else {
          // console.log('🚨 GAMESCENE: About to navigate to next quarter - BLOCKING FOR DEBUG');
          // console.log('🚨 GAMESCENE: If you see this, the animation was skipped!');
          
          // TEMPORARY DEBUG: Block navigation to see what's happening
          if (window.DEBUG_BLOCK_NAVIGATION !== false) {
            // console.log('🚨 GAMESCENE: Navigation blocked for debugging. Set window.DEBUG_BLOCK_NAVIGATION = false to allow navigation.');
            return; // Block navigation
          }
          
          // ✅ SS&S: Use unified Timeout Navigation Helper for consistent parameter building
          const nextQ = this.quarter + 1;
          const urlParams = new URLSearchParams(window.location.search);
          
          // ✅ REMOVED: Quarter navigation debug logging (cluttering console)
          
          // ✅ SS&S: Use global helper (works in both regular scripts and modules)
          const helper = window.TimeoutNavigationHelper;
          if (!helper) {
            console.error('❌ [GAMESCENE] TimeoutNavigationHelper not loaded!');
            return;
          }
          
          // ✅ PHASE 2.4: Removed localStorage fallback - game_id must come from URL
          
          // ✅ QUARTER BREAK: Quarter breaks should NOT have resume_from_timeout
          // Helper will automatically exclude it for quarter breaks (resumeFromTimeout=false)
          const params = helper.buildGameNavigationParams({
            sourceParams: urlParams,
            targetQuarter: nextQ,
            gameId: this.gameId,
            resumeFromTimeout: false, // ✅ QUARTER BREAK: Not a timeout resume
            lineup: {}, // Lineup will be set on lineup screen
            myTeamSide: urlParams.get('my_team')
          });
          params.set('quarter_break_from', 'play_quarter');
          
          // ✅ REMOVED: Navigation params debug logging (cluttering console)
          
          // ✅ PHASE 1.2: Removed automatic localStorage write - only save for explicit "Resume Last Game" feature
          DEBUG_FLOW && console.log('➡️ Advancing to lineup', { nextQ, gameId: this.gameId });
          DEBUG_FLOW && console.log('skipToEnd at navigation:', this.skipToEnd);
          window.location.href = `/set-lineup.html?${params.toString()}`;
        }
      }
    }

    /**
     * Run structure validation for inbound pass system
     */
    runStructureValidation() {
      try {
        // Running inbound pass structure validation
        
        // Import and run validation
        import('./animation/validateStructure.js').then(module => {
          const result = module.validateInboundPassStructure();
          
          if (result.isValid) {
            // Inbound pass structure validation passed
          } else {
            console.log('❌ Inbound pass structure validation failed:');
            result.issues.forEach(issue => {
              console.log(`   - ${issue}`);
            });
            console.log('💡 Check the PotentialIssues.md file for solutions');
          }
        }).catch(error => {
          console.log('⚠️ Could not run structure validation:', error.message);
        });
        
      } catch (error) {
        console.log('⚠️ Structure validation error:', error.message);
      }
    }
    
    /**
     * NEW: Turn-by-turn simulation method
     * Replaces the old batch simulation approach
     */
    async simulateTurnByTurn(initialSimData, updateScoreboard) {
      // ✅ REMOVED: Starting turn-by-turn simulation logging (cluttering console)
      
      const gameId = initialSimData.game_id;
      const { home: homeTeam, away: awayTeam } = gameStore.getTeams();
      
      let quarterComplete = false;
      let turnCount = 0;
      let lastHomeScore = initialSimData.home_score || 0;
      let lastAwayScore = initialSimData.away_score || 0;
      let nextQuarterNumber = this.quarter + 1; // Will be updated when quarter completes
      let lastTurnData = null; // Track last turn data to check is_final
      let timeoutTurnDetected = false; // ✅ FIX: Track if timeout turn was detected to prevent quarter completion logic
      
      // Initialize with any turns from the initial simulation (e.g., opening tip, inbound)
      const initialTurns = initialSimData.turns || [];
      // Discrete DREB outlet lead-in needs the prior animated row (MISS/BLOCK); turn-by-turn only
      // passes `turns: [current]` into animateGameTurns, so simData.turns has no predecessor — we thread
      // the last completed turn on the scene for AnimationEngine._maybeRunDiscreteDrebOutletLeadIn.
      this._priorAnimatedTurnForLeadIn = null;

      // Live clock mode: disable speculative preloading so backend turn decisions
      // (forced-shot/violation at 0) are computed after the visible turn completes.
      const ENABLE_TURN_PRELOAD = true;

      // Part 2 (Preload): helper and state defined early so we can preload during initial turns (opening tip → first HCO).
      const simMode = this.mode || 'single';
      const fetchTurnData = async (offenseOverride, defenseOverride) => {
        const resolveClockAuthorityMode = () => {
          const raw = String(window?.UESS_CLOCK_AUTHORITY_MODE ?? "").trim().toLowerCase();
          if (raw === "observe" || raw === "warn" || raw === "throw" || raw === "off") {
            return raw;
          }
          return null;
        };
        const resolveClockElapsedAuthority = () => {
          const raw = String(window?.UESS_CLOCK_ELAPSED_AUTHORITY ?? "").trim().toLowerCase();
          if (raw === "legacy" || raw === "ledger") {
            return raw;
          }
          return null;
        };
        const resolveOwnershipContractMode = () => {
          const raw = String(window?.UESS_OWNERSHIP_CONTRACT_MODE ?? "").trim().toLowerCase();
          if (raw === "off" || raw === "observe" || raw === "warn" || raw === "throw") {
            return raw;
          }
          return null;
        };
        const resolveClockReconToleranceSeconds = () => {
          const raw = window?.UESS_CLOCK_RECON_TOLERANCE_SECONDS;
          if (raw === null || typeof raw === "undefined" || raw === "") return null;
          const parsed = Number(raw);
          if (!Number.isFinite(parsed) || parsed < 0) return null;
          return parsed;
        };
        const response = await fetch(API_CONFIG.buildUrl('/api/simulate-turn'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            game_id: gameId,
            offense_override: offenseOverride ?? null,
            defense_override: defenseOverride ?? null,
            mode: simMode,
            uess_clock_authority_mode: resolveClockAuthorityMode(),
            uess_clock_elapsed_authority: resolveClockElapsedAuthority(),
            uess_ownership_contract_mode: resolveOwnershipContractMode(),
            uess_clock_recon_tolerance_seconds: resolveClockReconToleranceSeconds(),
          })
        });
        if (!response.ok) {
          let errorData;
          try {
            errorData = await response.json();
          } catch {
            errorData = { detail: `HTTP ${response.status}: ${response.statusText}` };
          }
          console.error('❌ /api/simulate-turn failed:', errorData);
          if (response.status === 404 && errorData.detail && errorData.detail.includes('not found')) {
            if (window.ErrorHandler && window.ErrorHandler.showMissingTruthError) {
              const urlParams = new URLSearchParams(window.location.search);
              window.ErrorHandler.showMissingTruthError({
                pointerType: 'game_id',
                pointerValue: urlParams.get('game_id') || 'unknown',
                message: errorData.detail || 'Game was cleared from backend memory. This may indicate a backend restart or timeout.',
                mode: urlParams.get('mode') || 'single',
                recoveryOptions: { redirectTo: 'mode-select', redirectLabel: 'Go to Mode Select' }
              });
            }
            throw new Error(`Game not found: ${errorData.detail || 'Game was cleared from backend memory'}`);
          }
          throw new Error(`API error: ${errorData.detail || `HTTP ${response.status}`}`);
        }
        return await response.json();
      };

      const mirrorClockReconDebug = (turnPayload) => {
        try {
          installOwnershipContractGlobalHelpers();
          const scope = typeof window !== 'undefined' ? window : globalThis;
          if (!turnPayload || typeof turnPayload !== 'object') return;
          const requestedOwnershipMode = resolveOwnershipContractMode();
          const firstBatchTurn =
            turnPayload.result_type === 'BATCH' && Array.isArray(turnPayload.batch_turns)
              ? turnPayload.batch_turns.find((row) => row && typeof row === 'object') ?? null
              : null;

          const defaultOwnershipMode =
            turnPayload.uess_ownership_contract_mode ??
            turnPayload.uess_ownership_contract?.mode ??
            firstBatchTurn?.uess_ownership_contract_mode ??
            firstBatchTurn?.uess_ownership_contract?.mode ??
            requestedOwnershipMode ??
            null;
          const rows =
            turnPayload.result_type === 'BATCH' && Array.isArray(turnPayload.batch_turns)
              ? turnPayload.batch_turns
              : [turnPayload];
          for (const row of rows) {
            if (!row || typeof row !== 'object') continue;
            const ownershipMode =
              row.uess_ownership_contract_mode ??
              row.uess_ownership_contract?.mode ??
              defaultOwnershipMode ??
              requestedOwnershipMode ??
              null;
            const snapshot = {
              resultType: row.result_type ?? null,
              mode: row.uess_clock_authority_mode ?? row.uess_clock_reconciliation?.mode ?? null,
              elapsedAuthority:
                row.uess_clock_elapsed_authority ?? row.uess_clock_reconciliation?.elapsed_authority ?? null,
              ownershipMode: ownershipMode ?? null,
              ledgerCount: Array.isArray(row.clock_event_ledger) ? row.clock_event_ledger.length : 0,
              ledgerElapsed: row.uess_clock_elapsed_game_seconds ?? null,
              legacyElapsed: row.uess_clock_elapsed_legacy_game_seconds ?? row.time_elapsed ?? null,
              delta: row.uess_clock_elapsed_delta_seconds ?? null,
              withinTolerance: row.uess_clock_elapsed_observe_within_tolerance ?? row.uess_clock_reconciliation?.within_tolerance ?? null,
              timestampMs: Date.now(),
            };
            scope.__CLOCK_RECON_LAST__ = snapshot;
            if (!Array.isArray(scope.__CLOCK_RECON_BUFFER__)) {
              scope.__CLOCK_RECON_BUFFER__ = [];
            }
            scope.__CLOCK_RECON_BUFFER__.push(snapshot);
            if (scope.__CLOCK_RECON_BUFFER__.length > 100) {
              scope.__CLOCK_RECON_BUFFER__.splice(0, scope.__CLOCK_RECON_BUFFER__.length - 100);
            }

            const ownershipContract = row.uess_ownership_contract;
            const ownershipSnapshot = {
              resultType: row.result_type ?? null,
              mode: ownershipMode ?? null,
              applicable:
                typeof ownershipContract?.applicable === "boolean"
                  ? ownershipContract.applicable
                  : null,
              passLifecycleValid:
                typeof ownershipContract?.pass_lifecycle_valid === "boolean"
                  ? ownershipContract.pass_lifecycle_valid
                  : null,
              passEventCount: Number(ownershipContract?.pass_event_count ?? 0) || 0,
              validReceiptCount: Number(ownershipContract?.pass_receipt_valid_count ?? 0) || 0,
              terminalOwnerPos: ownershipContract?.terminal_owner_pos ?? null,
              timestampMs: Date.now(),
            };
            scope.__OWNERSHIP_CONTRACT_LAST__ = ownershipSnapshot;
            if (!Array.isArray(scope.__OWNERSHIP_CONTRACT_BUFFER__)) {
              scope.__OWNERSHIP_CONTRACT_BUFFER__ = [];
            }
            scope.__OWNERSHIP_CONTRACT_BUFFER__.push(ownershipSnapshot);
            if (scope.__OWNERSHIP_CONTRACT_BUFFER__.length > 100) {
              scope.__OWNERSHIP_CONTRACT_BUFFER__.splice(
                0,
                scope.__OWNERSHIP_CONTRACT_BUFFER__.length - 100
              );
            }

            const summaryEvery = Math.max(
              1,
              Math.floor(Number(scope.UESS_OWNERSHIP_SUMMARY_EVERY ?? 10) || 10)
            );
            if (!scope.__OWNERSHIP_CONTRACT_SESSION__) {
              scope.__OWNERSHIP_CONTRACT_SESSION__ = {
                rows: 0,
                applicableRows: 0,
                invalidRows: 0,
                missingContractRows: 0,
              };
            }
            const session = scope.__OWNERSHIP_CONTRACT_SESSION__;
            session.rows += 1;
            if (ownershipSnapshot.applicable === true) {
              session.applicableRows += 1;
              if (ownershipSnapshot.passLifecycleValid === false) {
                session.invalidRows += 1;
              }
            } else if (ownershipSnapshot.applicable === null) {
              session.missingContractRows += 1;
            }

            if (session.rows % summaryEvery === 0) {
              const applicableRows = session.applicableRows;
              const invalidRows = session.invalidRows;
              const invalidApplicableRate =
                applicableRows > 0 ? Number((invalidRows / applicableRows).toFixed(4)) : 0;
              const thresholds = {
                minRows: Math.max(
                  1,
                  Math.floor(Number(scope.UESS_OWNERSHIP_WARN_MIN_ROWS ?? 40) || 40)
                ),
                invalidApplicableRateMax: Math.max(
                  0,
                  Number(scope.UESS_OWNERSHIP_WARN_INVALID_APPLICABLE_RATE_MAX ?? 0.02) || 0.02
                ),
                missingContractRowsMax: Math.max(
                  0,
                  Math.floor(Number(scope.UESS_OWNERSHIP_WARN_MISSING_CONTRACT_ROWS_MAX ?? 0) || 0)
                ),
              };
              const hasEnoughRows = session.rows >= thresholds.minRows;
              const meetsWarnPromotionGate =
                hasEnoughRows &&
                invalidApplicableRate <= thresholds.invalidApplicableRateMax &&
                session.missingContractRows <= thresholds.missingContractRowsMax;
              const summary = {
                event: "ownership_contract_summary",
                mode: String(ownershipSnapshot.mode ?? "warn"),
                rows: session.rows,
                applicableRows,
                invalidRows,
                invalidApplicableRate,
                missingContractRows: session.missingContractRows,
                thresholds,
                hasEnoughRows,
                meetsWarnPromotionGate,
                timestampMs: Date.now(),
              };
              scope.__OWNERSHIP_CONTRACT_SUMMARY_LAST__ = summary;
              if (!Array.isArray(scope.__OWNERSHIP_CONTRACT_SUMMARY_BUFFER__)) {
                scope.__OWNERSHIP_CONTRACT_SUMMARY_BUFFER__ = [];
              }
              scope.__OWNERSHIP_CONTRACT_SUMMARY_BUFFER__.push(summary);
              if (scope.__OWNERSHIP_CONTRACT_SUMMARY_BUFFER__.length > 50) {
                scope.__OWNERSHIP_CONTRACT_SUMMARY_BUFFER__.splice(
                  0,
                  scope.__OWNERSHIP_CONTRACT_SUMMARY_BUFFER__.length - 50
                );
              }
              if (!meetsWarnPromotionGate) {
                const breach = {
                  event: "ownership_contract_threshold_breach",
                  mode: summary.mode,
                  rows: summary.rows,
                  invalidApplicableRate: summary.invalidApplicableRate,
                  missingContractRows: summary.missingContractRows,
                  thresholds: summary.thresholds,
                  hasEnoughRows: summary.hasEnoughRows,
                  meetsWarnPromotionGate: summary.meetsWarnPromotionGate,
                  timestampMs: Date.now(),
                };
                scope.__OWNERSHIP_CONTRACT_SUMMARY_BUFFER__.push(breach);
                if (scope.__OWNERSHIP_CONTRACT_SUMMARY_BUFFER__.length > 50) {
                  scope.__OWNERSHIP_CONTRACT_SUMMARY_BUFFER__.splice(
                    0,
                    scope.__OWNERSHIP_CONTRACT_SUMMARY_BUFFER__.length - 50
                  );
                }
              }
            }
          }
        } catch (_) {
          // Debug mirror must never impact gameplay loop.
        }
      };

      const getBatchBoundaryHoldBudgetMs = () => {
        const scope = typeof window !== "undefined" ? window : globalThis;
        const raw = Number(scope?.UESS_BATCH_BOUNDARY_UNDECLARED_HOLD_BUDGET_MS);
        if (Number.isFinite(raw) && raw > 0) return raw;
        return 1200;
      };

      const isBoundaryInterruptResultType = (resultType) => {
        const key = String(resultType || "").toUpperCase();
        return (
          key === "TIMEOUT" ||
          key === "DEAD BALL" ||
          key === "FOUL" ||
          key === "CHARGE" ||
          key === "TURNOVER" ||
          key === "PERIOD_END"
        );
      };

      const emitBatchBoundaryTelemetry = (event, payload = {}) => {
        const scope = typeof window !== "undefined" ? window : globalThis;
        const row = {
          event,
          branchKind: "batch_transition_boundary",
          timestampMs: Date.now(),
          ...payload,
        };
        this.events?.emit?.("animTelemetry", row);
        scope.__BATCH_BOUNDARY_LAST__ = row;
        if (!Array.isArray(scope.__BATCH_BOUNDARY_BUFFER__)) {
          scope.__BATCH_BOUNDARY_BUFFER__ = [];
        }
        scope.__BATCH_BOUNDARY_BUFFER__.push(row);
        if (scope.__BATCH_BOUNDARY_BUFFER__.length > 100) {
          scope.__BATCH_BOUNDARY_BUFFER__.splice(
            0,
            scope.__BATCH_BOUNDARY_BUFFER__.length - 100
          );
        }
      };

      const validateBatchBoundaryDuration = ({
        turnLike,
        elapsedMs,
        contextType,
        turnIndex,
        batchIndex = null,
      }) => {
        const expectedMs = Math.max(
          0,
          Number(turnLike?.real_time_elapsed_ms ?? turnLike?.realTimeElapsedMs ?? 0) || 0
        );
        const overrunMs = Math.max(0, Number(elapsedMs) - expectedMs);
        const holdBudgetMs = getBatchBoundaryHoldBudgetMs();
        const resultType = String(turnLike?.result_type ?? "");
        const interruptResult = isBoundaryInterruptResultType(resultType);
        if (!interruptResult && overrunMs > holdBudgetMs) {
          emitBatchBoundaryTelemetry("batch_boundary_undeclared_hold_violation", {
            violationType: "turn_duration_exceeds_contract_elapsed_without_interrupt",
            resultType: resultType || null,
            contextType,
            turnIndex: Number.isFinite(turnIndex) ? turnIndex : null,
            batchIndex: Number.isFinite(batchIndex) ? batchIndex : null,
            elapsedMs: Math.round(elapsedMs),
            expectedElapsedMs: Math.round(expectedMs),
            overrunMs: Math.round(overrunMs),
            holdBudgetMs,
            allowedInterrupts: [
              "dead_ball_or_whistle_stop",
              "timeout_pause_barrier",
              "period_end",
            ],
          });
        }
      };

      let preloadedTurnPromise = null;

      // Animate initial turns first (opening tip, quarter start inbound, etc.)
      if (initialTurns.length > 0) {
        const firstInitialTurn = initialTurns[0];
        const schemaInboundSteps = Array.isArray(firstInitialTurn?.animation_steps)
          && firstInitialTurn.animation_steps.length > 0;
        if (initialSimData.entry_animation?.kind === "BENCH_ENTRY" && !schemaInboundSteps) {
          const { runBenchEntrySequence } = await import('./animation/benchEntry.js');
          await runBenchEntrySequence(this, {
            playerSprites: this.playerSprites,
            entryAnimation: initialSimData.entry_animation,
          });
        } else if (schemaInboundSteps) {
          console.warn("🏠 [BENCH_ENTRY] skipped — inbound turn has animation_steps (schema handles triangle→setup)");
        }
        // Add indices to initial turns for text scroll
        initialTurns.forEach((turn, idx) => {
          turn.index = idx;
          turnCount++;
        });

        await animateGameTurns({
          scene: this,
          simData: { ...initialSimData, turns: initialTurns },
          playerSprites: this.playerSprites,
          ballSprite: this.ballSprite,
          onUpdate: updateScoreboard
        });
        this._priorAnimatedTurnForLeadIn =
          initialTurns.length > 0 ? initialTurns[initialTurns.length - 1] : null;
        // Preload first HCO only AFTER opening-tip animation completes (see comment
        // on main-loop preload below — same reason).
        if (ENABLE_TURN_PRELOAD) {
          preloadedTurnPromise = fetchTurnData(null, null);
        }
      }

      // Main turn-by-turn loop
      while (!quarterComplete) {
        try {
          const offenseOverride = window.nextOffenseOverride || null;
          const defenseOverride = window.nextDefenseOverride || null;
          window.nextOffenseOverride = null;
          window.nextDefenseOverride = null;
          window.nextDefenseTypeOverride = null;
          window.nextDefenseAggressionOverride = null;
          if (window.clearPlaycallOverrides && (offenseOverride || defenseOverride)) {
            window.clearPlaycallOverrides();
          }

          // Part 2: Use preloaded turn when available and no overrides; else fetch. On preload failure, fetch with overrides.
          let turnData;
          const turnFetchWaitStartMs = performance.now();
          let turnFetchSource = "direct";
          if (preloadedTurnPromise && !offenseOverride && !defenseOverride) {
            try {
              turnFetchSource = "preload";
              turnData = await preloadedTurnPromise;
            } catch (e) {
              console.warn('⚠️ Preloaded turn failed, fetching fresh:', e?.message);
              turnFetchSource = "preload_failed_direct";
              turnData = await fetchTurnData(offenseOverride, defenseOverride);
            }
            preloadedTurnPromise = null;
          } else {
            if (preloadedTurnPromise) preloadedTurnPromise = null;
            turnData = await fetchTurnData(offenseOverride, defenseOverride);
          }
          // ✅ FIX: Only break if there's no turn to animate
          // If quarter_complete is True but turn exists, animate the turn first (it's the final turn of the quarter)
          if (!turnData.turn) {
            console.log('✅ Quarter complete! (no turn returned)', {
              time_remaining: turnData.time_remaining,
              turnCount,
              home_score: turnData.home_score,
              away_score: turnData.away_score,
              is_final: turnData.is_final
            });
            quarterComplete = true;
            lastTurnData = turnData; // Store last turn data for game completion check
            
            // Update final scores (include response shot_clock for backend authority)
            updateScoreboard({
              home_score: turnData.home_score,
              away_score: turnData.away_score,
              home_team_fouls: turnData.home_team_fouls,
              away_team_fouls: turnData.away_team_fouls,
              clock: turnData.clock,
              shot_clock_remaining: turnData.shot_clock_remaining,
              time_remaining: turnData.time_remaining
            });
            
            // Update tracked scores from final turnData
            if (turnData.home_score !== undefined) {
              lastHomeScore = turnData.home_score;
            }
            if (turnData.away_score !== undefined) {
              lastAwayScore = turnData.away_score;
            }
            
            // Track the next quarter number from backend
            if (turnData.quarter !== undefined) {
              nextQuarterNumber = turnData.quarter;
            }
            
            break;
          }
          
          // Animate this single turn (or batch of turns)
          const turn = turnData.turn;
          mirrorClockReconDebug(turn);
          // Guarantee clock contract on turn so AnimationRouter always has clock_start/shot_clock_start (API now sends at top level)
          const clockContractKeys = [
            ['clock_start', 'clockStart'],
            ['clock_end', 'clockEnd'],
            ['shot_clock_start', 'shotClockStart'],
            ['shot_clock_end', 'shotClockEnd'],
            ['real_time_elapsed_ms', 'realTimeElapsedMs'],
          ];
          const mergeClockContract = (target, source) => {
            if (!target || !source) return;
            for (const [snake, camel] of clockContractKeys) {
              const val = source[snake] ?? source[camel];
              if (val != null && (target[snake] == null || target[snake] === undefined)) target[snake] = val;
            }
          };
          mergeClockContract(turn, turnData);
          if (turn.home_score === undefined && turnData.home_score !== undefined) turn.home_score = turnData.home_score;
          if (turn.away_score === undefined && turnData.away_score !== undefined) turn.away_score = turnData.away_score;
          if (turn.clock === undefined && turnData.clock !== undefined) turn.clock = turnData.clock;
          if (turn.time_remaining === undefined && turnData.time_remaining !== undefined) turn.time_remaining = turnData.time_remaining;
          if (turn.shot_clock_remaining === undefined && turnData.shot_clock_remaining !== undefined) {
            turn.shot_clock_remaining = turnData.shot_clock_remaining;
          }

          try {
            const { logEoqApiReceipt } = await import('./utils/eoqDebugLog.js');
            logEoqApiReceipt(this, turnData, {
              turn_count: turnCount,
              quarter_complete: turnData.quarter_complete,
              time_remaining: turnData.time_remaining,
              clock: turnData.clock,
              clock_start: turnData.clock_start,
              clock_end: turnData.clock_end,
            });
          } catch (_eoqLogErr) {
            // trace only
          }

          // ✅ FIX: Check if this is the final turn of the quarter AFTER getting the turn
          // This ensures the final turn is animated before handling quarter completion
          if (turnData.quarter_complete) {
            // Mark that this is the final turn - we'll handle quarter completion after animation
            turn.is_final_turn_of_quarter = true;
            console.log('🔍 [FINAL TURN DEBUG] Received turn with quarter_complete=true BEFORE animation', {
              turn_result_type: turn.result_type,
              turn_text: turn.text?.substring(0, 50),
              time_remaining_before_turn: turnData.time_remaining,
              clock_before_turn: turnData.clock,
              turnCount,
              will_animate: true
            });
          }
          let finalTurn = turn; // Track the final turn for Quick Adjust logic

          // ✅ TIMEOUT: Check if this is a timeout turn - if so, stop the simulation loop
          if (turn.result_type === "TIMEOUT") {
            console.log('⏸️ TIMEOUT: Timeout turn detected in simulateTurnByTurn - stopping simulation loop');
            // ✅ FIX: Set flag to prevent quarter completion logic
            timeoutTurnDetected = true;
            // ✅ UNIFIED: Store full response data in turn for animation system to access clock/time_remaining
            turn._responseData = {
              clock: turnData.clock,
              time_remaining: turnData.time_remaining,
              quarter: turnData.quarter,
              home_score: turnData.home_score,
              away_score: turnData.away_score,
              home_team_timeouts: turnData.home_team_timeouts,
              away_team_timeouts: turnData.away_team_timeouts,
              timeout_trace_id: turnData.timeout_trace_id
            };
            // Animate the timeout turn (will handle navigation)
            await animateGameTurns({
              scene: this,
              simData: { 
                ...initialSimData,
                turns: [turn],
                home_team: initialSimData.home_team,
                away_team: initialSimData.away_team,
                __priorAnimatedTurn: this._priorAnimatedTurnForLeadIn,
              },
              playerSprites: this.playerSprites,
              ballSprite: this.ballSprite,
              onUpdate: updateScoreboard
            });
            this._priorAnimatedTurnForLeadIn = turn;
            // Break out of the while loop - don't make any more API calls
            break;
          }
          
          // Handle BATCH turns (e.g., HCO miss → OREB)
          if (turn.result_type === 'BATCH' && turn.batch_turns) {
            // ✅ REMOVED: Batch turn logging (cluttering console)
            
            // Animate each turn in the batch (try/catch so timeout sub-turn still runs if foul sub-turn errors)
            let previousSubTurnEndAtMs = Date.now();
            for (let subTurnIndex = 0; subTurnIndex < turn.batch_turns.length; subTurnIndex++) {
              const subTurn = turn.batch_turns[subTurnIndex];
              turnCount++;
              subTurn.index = turnCount;
              mergeClockContract(subTurn, turnData);
              if (subTurn.home_score === undefined && turnData.home_score !== undefined) subTurn.home_score = turnData.home_score;
              if (subTurn.away_score === undefined && turnData.away_score !== undefined) subTurn.away_score = turnData.away_score;
              if (subTurn.clock === undefined && turnData.clock !== undefined) subTurn.clock = turnData.clock;
              if (subTurn.time_remaining === undefined && turnData.time_remaining !== undefined) subTurn.time_remaining = turnData.time_remaining;
              if (subTurn.shot_clock_remaining === undefined && turnData.shot_clock_remaining !== undefined) {
                subTurn.shot_clock_remaining = turnData.shot_clock_remaining;
              }
              console.log(`🎬 Turn ${turnCount}: ${subTurn.result_type} - ${subTurn.text?.substring(0, 50)}...`);
              const subTurnStartAtMs = Date.now();
              const boundaryGapMs = subTurnStartAtMs - previousSubTurnEndAtMs;
              const holdBudgetMs = getBatchBoundaryHoldBudgetMs();
              const previousResultType =
                subTurnIndex > 0
                  ? String(turn.batch_turns[subTurnIndex - 1]?.result_type || "")
                  : null;
              if (
                subTurnIndex > 0 &&
                !isBoundaryInterruptResultType(previousResultType) &&
                boundaryGapMs > holdBudgetMs
              ) {
                emitBatchBoundaryTelemetry("batch_subturn_boundary_gap_overrun", {
                  violationType: "gap_between_subturns_without_interrupt",
                  previousResultType: previousResultType || null,
                  nextResultType: String(subTurn?.result_type || "") || null,
                  turnIndex: turnCount,
                  batchIndex: subTurnIndex,
                  gapMs: Math.round(boundaryGapMs),
                  holdBudgetMs,
                });
              }
              
              // Display debug info in text scroll
              if (subTurn.debug_turn_start) {
                appendToTextScroll(subTurn.debug_turn_start);
              }
              if (subTurn.text) {
                appendToTextScroll(`Turn ${turnCount}: ${subTurn.text}`);
              }
              if (subTurn.debug_turn_result) {
                appendToTextScroll(subTurn.debug_turn_result);
              }
              
              try {
                const priorForSubTurn =
                  subTurnIndex === 0
                    ? this._priorAnimatedTurnForLeadIn
                    : turn.batch_turns[subTurnIndex - 1];
                await animateGameTurns({
                  scene: this,
                  simData: { 
                    ...initialSimData,
                    turns: [subTurn],
                    home_team: initialSimData.home_team,
                    away_team: initialSimData.away_team,
                    __priorAnimatedTurn: priorForSubTurn,
                  },
                  playerSprites: this.playerSprites,
                  ballSprite: this.ballSprite,
                  onUpdate: updateScoreboard
                });
                this._priorAnimatedTurnForLeadIn = subTurn;
                const subTurnElapsedMs = Date.now() - subTurnStartAtMs;
                validateBatchBoundaryDuration({
                  turnLike: subTurn,
                  elapsedMs: subTurnElapsedMs,
                  contextType: "batch_subturn",
                  turnIndex: turnCount,
                  batchIndex: subTurnIndex,
                });
              } catch (batchSubErr) {
                console.error(`❌ BATCH sub-turn (${subTurn.result_type}) animation error; continuing to next sub-turn:`, batchSubErr);
                // Continue so timeout sub-turn (e.g. foul-out) still runs
              }
              previousSubTurnEndAtMs = Date.now();
              
              // Update finalTurn to be the last sub-turn in the batch
              finalTurn = subTurn;

              // ✅ FOUL OUT/TIMEOUT SAFETY: A timeout can be appended inside a batch (e.g. foul-out timeout).
              // When it happens, we must stop the simulate-turn loop immediately, same as the non-batch timeout path.
              if (subTurn.result_type === 'TIMEOUT') {
                console.log('⏸️ TIMEOUT: Timeout subTurn detected inside BATCH - stopping simulation loop');
                timeoutTurnDetected = true;
                subTurn._responseData = {
                  clock: turnData.clock,
                  time_remaining: turnData.time_remaining,
                  quarter: turnData.quarter,
                  home_score: turnData.home_score,
                  away_score: turnData.away_score,
                  home_team_timeouts: turnData.home_team_timeouts,
                  away_team_timeouts: turnData.away_team_timeouts,
                  timeout_trace_id: turnData.timeout_trace_id
                };
                // Stop processing remaining batch turns and exit the main loop.
                break;
              }
            }

            if (timeoutTurnDetected) {
              break;
            }
          } else {
            // Normal single turn
            turnCount++;
            turn.index = turnCount;
            const singleTurnStartAtMs = Date.now();
            
            console.log(`🎬 Turn ${turnCount}: ${turn.result_type} - ${turn.text?.substring(0, 50)}...`);
            
            // Display debug info in text scroll
            if (turn.debug_turn_start) {
              appendToTextScroll(turn.debug_turn_start);
            }
            if (turn.text) {
              appendToTextScroll(`Turn ${turnCount}: ${turn.text}`);
            }
            if (turn.debug_turn_result) {
              appendToTextScroll(turn.debug_turn_result);
            }
            
            // Wrap single turn in array for animateGameTurns
            if (turn.is_final_turn_of_quarter) {
              console.log('🎬 [FINAL TURN DEBUG] Starting animation of final turn', {
                turn_result_type: turn.result_type,
                turn_text: turn.text?.substring(0, 50)
              });
            }
            await animateGameTurns({
              scene: this,
              simData: {
                ...initialSimData,
                turns: [turn],
                home_team: initialSimData.home_team,
                away_team: initialSimData.away_team,
                __priorAnimatedTurn: this._priorAnimatedTurnForLeadIn,
              },
              playerSprites: this.playerSprites,
              ballSprite: this.ballSprite,
              onUpdate: updateScoreboard
            });
            this._priorAnimatedTurnForLeadIn = turn;
            const singleTurnElapsedMs = Date.now() - singleTurnStartAtMs;
            validateBatchBoundaryDuration({
              turnLike: turn,
              elapsedMs: singleTurnElapsedMs,
              contextType: "single_turn",
              turnIndex: turnCount,
            });
            if (turn.is_final_turn_of_quarter) {
              console.log('✅ [FINAL TURN DEBUG] Animation of final turn completed', {
                turn_result_type: turn.result_type,
                turn_text: turn.text?.substring(0, 50)
              });
            }
          }
          
          // Preload next turn only AFTER current animation completes. Parallel preload
          // would let backend simulate possession-changing events (DREB, MAKE→BIP flip)
          // while the user is still watching the prior animation — a user timeout
          // captured during that window snapshots state the user hasn't seen yet.
          if (ENABLE_TURN_PRELOAD && turn.result_type !== 'TIMEOUT' && !turnData.quarter_complete) {
            preloadedTurnPromise = fetchTurnData(null, null);
          }

          // Update scores and game state after each turn (include response shot_clock so display uses backend authority)
          updateScoreboard({
            home_score: turnData.home_score,
            away_score: turnData.away_score,
            home_team_fouls: turnData.home_team_fouls,
            away_team_fouls: turnData.away_team_fouls,
            clock: turnData.clock,
            shot_clock_remaining: turnData.shot_clock_remaining,
            time_remaining: turnData.time_remaining,
            // Forward the backend-stamped derived Team Momentum so the bar
            // refreshes once per turn (undefined-safe; sticky holds otherwise).
            home_team_momentum: turnData.home_team_momentum,
            away_team_momentum: turnData.away_team_momentum
          });
          
          // Track latest scores for game completion check
          if (turnData.home_score !== undefined) {
            lastHomeScore = turnData.home_score;
          }
          if (turnData.away_score !== undefined) {
            lastAwayScore = turnData.away_score;
          }
          
          // Check if next turn is HCO (eligible for quick adjust window)
          // Use finalTurn (last sub-turn in batch, or the single turn)
          const nextIsHCO = turnData.next_offensive_state === 'HCO';
          const currentIsFastBreak = finalTurn.fast_break || finalTurn.result_type === 'FAST_BREAK';
          const currentIsFreethrow = finalTurn.result_type === 'FREE_THROW';
          const currentIsFCP = finalTurn.fcp_foul || finalTurn.result_type === 'FCP';
          const currentIsHCT = finalTurn.hct_foul || finalTurn.result_type === 'HCT';
          
          // SIMPLIFIED: turnData.offense_team is ALREADY who has offense next
          // (API returns this AFTER possession flips have been processed)
          const nextOffenseTeam = turnData.offense_team;
          const userTeamName = this.userTeamSide === 'home' ? homeTeam : awayTeam;
          const userHasOffenseNext = nextOffenseTeam === userTeamName;
          
          // Quick Adjust Check
          
          // ==================== CLIPBOARD COUNTDOWN (DISABLED FOR NOW) ====================
          // User can preset calls anytime; no forced decision window
          // Future: Re-enable for "coaching moments" feature
          /*
          // Show clipboard countdown if:
          // 1. Next state is HCO
          // 2. Current turn is NOT Fast Break, Free Throw, FCP, or HCT
          // 3. User's team is on offense next
          if (nextIsHCO && !currentIsFastBreak && !currentIsFreethrow && !currentIsFCP && !currentIsHCT && userHasOffenseNext) {
            console.log('📋 Showing clipboard countdown (5 seconds)');
            
            // Determine transition type for animation
            let transitionType = 'INBOUND_PASS'; // Default
            if (finalTurn.result_type === 'DREB') {
              transitionType = 'DREB';
            } else if (finalTurn.result_type === 'SIDE_INBOUND') {
              transitionType = 'SIDE_INBOUND';
            }
            
            // Start clipboard countdown timer UI and player animation simultaneously
            const countdownPromise = window.showClipboardCountdown ? window.showClipboardCountdown(5000) : Promise.resolve();
            const animationPromise = animateCountdownTransition({
              scene: this,
              playerSprites: this.playerSprites,
              ballSprite: this.ballSprite,
              transitionType: transitionType,
              offenseTeamId: nextOffenseTeam,
              homeTeamId: initialSimData.home_team_id,
              duration: 5000
            });
            
            // Wait for both to complete
            await Promise.all([countdownPromise, animationPromise]);
            
            console.log('📋 Countdown complete, using preset overrides:', {
              offense: window.nextOffenseOverride || 'auto',
              defense: window.nextDefenseOverride || 'auto'
            });
          }
          */
          
          // ✅ FIX: Check if quarter is complete AFTER animating the turn
          // This ensures the final turn of the quarter is animated before handling quarter completion.
          // Phase 6: Final Turn shot and FINAL_HOLD are covered — backend sets quarter_complete when
          // time_remaining hits 0 (after the turn or after FTs); we advance to Quarter Break / game end here.
          if (turnData.quarter_complete) {
            console.log('✅ [FINAL TURN DEBUG] Quarter complete! (after final turn animation)', {
              turn_result_type: turn?.result_type,
              turn_text: turn?.text?.substring(0, 50),
              time_remaining_after_turn: turnData.time_remaining,
              clock_after_turn: turnData.clock,
              turnCount,
              home_score: turnData.home_score,
              away_score: turnData.away_score,
              is_final: turnData.is_final,
              animation_completed: true
            });
            quarterComplete = true;
            lastTurnData = turnData; // Store last turn data for game completion check
            
            // Update final scores (include response shot_clock for backend authority)
            updateScoreboard({
              home_score: turnData.home_score,
              away_score: turnData.away_score,
              home_team_fouls: turnData.home_team_fouls,
              away_team_fouls: turnData.away_team_fouls,
              clock: turnData.clock,
              shot_clock_remaining: turnData.shot_clock_remaining,
              time_remaining: turnData.time_remaining
            });
            
            // Update tracked scores from final turnData
            if (turnData.home_score !== undefined) {
              lastHomeScore = turnData.home_score;
            }
            if (turnData.away_score !== undefined) {
              lastAwayScore = turnData.away_score;
            }
            
            // Track the next quarter number from backend
            if (turnData.quarter !== undefined) {
              nextQuarterNumber = turnData.quarter;
            }
            
            break;
          }
          
        } catch (error) {
          console.error('❌ Error in turn-by-turn loop:', error);
          // ✅ FIX: Don't end quarter on API errors (404, network issues, etc.)
          // Only end quarter if backend explicitly signals completion (quarter_complete=true)
          // Check if the current or last turn data indicates quarter completion before breaking
          // ✅ FIX: Use lastTurnData (turnData may be undefined if error occurred before assignment)
          const dataToCheck = lastTurnData;
          if (dataToCheck && (dataToCheck.quarter_complete === true || dataToCheck.time_remaining <= 0)) {
            // Backend signaled quarter completion - exit loop normally
            console.log('✅ Quarter complete detected after error, exiting loop');
            quarterComplete = true;
            lastTurnData = dataToCheck;
            break;
          }
          // ✅ FIX: For API errors (404, network issues), don't continue - show error and exit
          // This prevents premature quarter completion
          if (error.message && (error.message.includes('Game not found') || error.message.includes('API error'))) {
            console.error('❌ Critical API error - stopping simulation:', error.message);
            // Don't set quarterComplete - exit loop without triggering quarter completion
            break;
          }
          // For animation errors (like missing showAnnouncement), log and continue
          // The backend will signal quarter completion when time_remaining <= 0
          console.warn('⚠️ Animation error occurred, continuing to next turn');
          continue;
        }
      }
      
      // ✅ FIX: Skip quarter completion logic if timeout turn was detected
      // Timeout turns should exit immediately - navigation is handled by timeoutButtonManager
      if (timeoutTurnDetected) {
        console.log('⏸️ TIMEOUT: Exiting simulateTurnByTurn after timeout turn - preventing quarter completion');
        return { timeoutDetected: true };
      }
      
      // ✅ FIX: Only proceed with quarter completion if backend explicitly signaled it
      // Don't complete quarter on API errors (404, network issues, etc.)
      if (!quarterComplete) {
        console.warn('⚠️ Simulation loop ended but quarter not complete. This may indicate an API error or game state issue.');
        // Don't proceed with quarter completion logic - return early
        return { timeoutDetected: false };
      }
      
      console.log(`🏁 Quarter ${this.quarter} finished! Total turns: ${turnCount}`);
      
      // Backend owns the game-end decision. The frontend only renders either
      // the final flow or the next backend-provided quarter break.
      const quarterThatJustFinished = this.quarter;
      
      // Use scores from lastTurnData if available (most recent/accurate), otherwise fall back to tracked scores
      const finalHomeScore = (lastTurnData && lastTurnData.home_score !== undefined) 
        ? lastTurnData.home_score 
        : lastHomeScore;
      const finalAwayScore = (lastTurnData && lastTurnData.away_score !== undefined)
        ? lastTurnData.away_score
        : lastAwayScore;
      const isFinalFromBackend = lastTurnData?.is_final === true;
      const backendNextQuarterRaw = lastTurnData?.next_quarter ?? lastTurnData?.quarter ?? nextQuarterNumber;
      const backendNextQuarter = Number(backendNextQuarterRaw);
      const nextQuarterFromBackend = Number.isFinite(backendNextQuarter)
        ? backendNextQuarter
        : nextQuarterNumber;
      
      console.log('🏁 Game completion check:', {
        quarterJustFinished: quarterThatJustFinished,
        nextQuarter: nextQuarterFromBackend,
        homeScore: finalHomeScore,
        awayScore: finalAwayScore,
        isFinalFromBackend: isFinalFromBackend,
        backendDecisionSource: 'lastTurnData.is_final',
        lastTurnDataScores: lastTurnData ? { home: lastTurnData.home_score, away: lastTurnData.away_score } : null
      });

      if (isFinalFromBackend) {
        // Game is over - finalize
        console.log('🏆 Game complete! Finalizing...');
        
        // ✅ FIX: Update this.isFinal so the "no animation" path also knows game is final
        this.isFinal = true;
        
        const finalize = async () => {
          const { finalizeGame } = await import('./finalizeGame.js');
          
          // ✅ FIX: Use final_game_document from simulate-quarter response if available
          // This eliminates race condition - backend returns complete document when is_final=True
          // Works for Q4 (not tied) and any OT that ends with a winner
          let finalGameData = initialSimData;
          
          // Check if lastTurnData contains final_game_document (returned from simulate-quarter)
          if (lastTurnData && lastTurnData.final_game_document) {
            console.log('✅ Using final_game_document from simulate-quarter response (no fetch needed)');
            finalGameData = lastTurnData.final_game_document;
            console.log('✅ Final game document details:', {
              game_id: finalGameData.game_id || finalGameData._id,
              quarter: finalGameData.quarter,
              is_final: finalGameData.is_final,
              hasBoxScore: !!finalGameData.box_score,
              boxScoreKeys: finalGameData.box_score ? Object.keys(finalGameData.box_score) : []
            });
          } else if (gameId) {
            // Fallback: Fetch from API if final_game_document not in response
            try {
              console.log('📥 final_game_document not in response, fetching from API...');
              const gameResponse = await fetch(API_CONFIG.buildUrl(`/api/game/${gameId}`), { headers: API_CONFIG.getAuthHeaders() });
              if (gameResponse.ok) {
                finalGameData = await gameResponse.json();
                console.log('✅ Fetched final game data:', {
                  game_id: finalGameData.game_id || finalGameData._id,
                  quarter: finalGameData.quarter,
                  is_final: finalGameData.is_final,
                  hasBoxScore: !!finalGameData.box_score,
                  boxScoreKeys: finalGameData.box_score ? Object.keys(finalGameData.box_score) : []
                });
              } else {
                console.warn('⚠️ Failed to fetch final game data, using initialSimData:', gameResponse.status);
              }
            } catch (err) {
              console.error('❌ Error fetching final game data, using initialSimData:', err);
            }
          }
          
          // ✅ UNIFIED STRUCTURE: Get team names from unified teams object, fallback to old structure
          const { home: homeTeamName, away: awayTeamName } = gameStore.getTeams();
          const finalHomeTeamId = finalGameData.home_team_id;
          const finalAwayTeamId = finalGameData.away_team_id;
          const finalTeamsObj = finalGameData.teams || {};
          const finalHomeTeamObj = finalHomeTeamId && finalTeamsObj[finalHomeTeamId] ? finalTeamsObj[finalHomeTeamId] : null;
          const finalAwayTeamObj = finalAwayTeamId && finalTeamsObj[finalAwayTeamId] ? finalTeamsObj[finalAwayTeamId] : null;
          
          const homeName = homeTeamName || finalHomeTeamObj?.name || finalGameData.home_team?.name || finalGameData.home_team;
          const awayName = awayTeamName || finalAwayTeamObj?.name || finalGameData.away_team?.name || finalGameData.away_team;
          
          // ✅ UNIFIED STRUCTURE: Update team objects with final scores (if unified structure exists)
          // For unified structure, scores are updated in teams object
          // For backward compatibility, maintain old structure if it exists
          let updatedHomeTeam = null;
          let updatedAwayTeam = null;
          if (finalHomeTeamObj) {
            updatedHomeTeam = { ...finalHomeTeamObj, score: finalHomeScore };
          } else if (typeof finalGameData.home_team === 'object') {
            updatedHomeTeam = { ...finalGameData.home_team, score: finalHomeScore };
          } else {
            updatedHomeTeam = finalGameData.home_team;
          }
          if (finalAwayTeamObj) {
            updatedAwayTeam = { ...finalAwayTeamObj, score: finalAwayScore };
          } else if (typeof finalGameData.away_team === 'object') {
            updatedAwayTeam = { ...finalGameData.away_team, score: finalAwayScore };
          } else {
            updatedAwayTeam = finalGameData.away_team;
          }
          
          // Update simData.score with current final scores (finalizeGame prioritizes this)
          // ✅ FIX: Preserve final_game_document if it was in the response (from simulate-quarter)
          // This ensures complete_week() gets the complete document without database lookup
          const updatedSimData = {
            ...finalGameData,
            home_score: finalHomeScore,
            away_score: finalAwayScore,
            game_id: gameId || finalGameData.game_id || finalGameData._id,
            home_team: updatedHomeTeam,
            away_team: updatedAwayTeam,
            score: {
              ...(finalGameData.score || {}),
              [homeName]: finalHomeScore,
              [awayName]: finalAwayScore
            }
          };
          
          // ✅ FIX: Preserve final_game_document if it was in lastTurnData (from simulate-quarter)
          if (lastTurnData && lastTurnData.final_game_document) {
            updatedSimData.final_game_document = lastTurnData.final_game_document;
          }
          
          console.log('🔍 [GAMESCENE] Calling finalizeGame with:', {
            tournamentId: this.tournamentId,
            franchiseId: this.franchiseId,
            game_id: updatedSimData.game_id || updatedSimData._id,
            hasFinalGameDocument: !!updatedSimData.final_game_document
          });
          
          const finalScore = await finalizeGame({
            simData: updatedSimData,
            tournamentId: this.tournamentId,
            franchiseId: this.franchiseId,
            game: this.game,
          });
          this.finalScore = finalScore;
          this.finalized = true;
          if (window.GOB_Analytics) {
            if (this.tournamentId) window.GOB_Analytics.tournamentGameCompleted();
            else if (this.franchiseId) window.GOB_Analytics.franchiseGameCompleted();
            else window.GOB_Analytics.singleGameCompleted();
          }
          // Show game completion popup (absolute path for Netlify/module resolution)
          const base = (typeof window !== 'undefined' && window.API_CONFIG) ? window.API_CONFIG.getStaticPath() : '';
          const { showGameCompletionPopup } = await import(`${base}/js/phaser/utils/gameCompletionPopup.js`);
          showGameCompletionPopup({
            gameId: gameId,
            mode: getGameMode({ scene: this, tournamentId: this.tournamentId, franchiseId: this.franchiseId }),
            tournamentId: this.tournamentId,
            franchiseId: this.franchiseId,
            teamId: this.teamId,
            userTeamSide: this.userTeamSide,
            finalScore: finalScore,
            gameData: updatedSimData
          });
          
          return finalScore;
        };
        await finalize();
        return; // Exit - game is over
      } else {
        // Regular quarter complete (Q1-Q3) - show locker room popup
        console.log('✅ Quarter complete - showing locker room popup');
        const nextQ = nextQuarterFromBackend;
        
        // ✅ FIX: Use TimeoutNavigationHelper (same as Sim Quarter) to ensure resume_from_timeout=false
        // This matches the working Sim Quarter pattern exactly
        const helper = window.TimeoutNavigationHelper;
        if (!helper) {
          console.error('❌ [GAMESCENE] TimeoutNavigationHelper not loaded!');
          // Fallback to manual params if helper not available
          const params = new URLSearchParams(window.location.search);
          params.set('game_id', this.gameId);
          params.set('quarter', nextQ);
          params.set('period', `Q${nextQ}`);
          params.set('resume_from_timeout', 'false');
          const finalUrl = `/set-lineup.html?${params.toString()}`;
          window.location.href = finalUrl;
          return;
        }
        
        // Get teams from gameStore (same as Sim Quarter pattern)
        const teams = gameStore.getTeams();
        const sourceParams = new URLSearchParams(window.location.search);
        
        // Build params using helper (exactly like Sim Quarter does)
        const params = helper.buildGameNavigationParams({
          sourceParams: sourceParams,
          targetQuarter: nextQ,
          gameId: this.gameId,
          resumeFromTimeout: false, // ✅ CRITICAL: Not a timeout resume (quarter break)
          lineup: {}, // Lineup will be set on lineup screen
          myTeamSide: this.userTeamSide || 'home',
          overrides: {
            home: teams.home,
            away: teams.away,
            mode: this.mode,
            tournament_id: this.tournamentId,
            franchise_id: this.franchiseId,
            team_id: this.teamId
          }
        });
        params.set('quarter_break_from', 'play_quarter'); // Airhorn only on Play Quarter quarter break
        console.log('🔍 [DEBUG QTR BREAK] gameScene.js - Using TimeoutNavigationHelper (Sim Quarter pattern):', {
          quarter: this.quarter,
          nextQ: nextQ,
          gameId: this.gameId,
          resume_from_timeout: params.get('resume_from_timeout'),
          fullParams: Object.fromEntries(params.entries())
        });
        
        // ✅ PHASE 1.2: Removed automatic localStorage write - only save for explicit "Resume Last Game" feature
        
        // Create locker room popup
        const popup = document.createElement('div');
        popup.className = 'locker-room-popup';
        popup.innerHTML = `
          <div class="locker-room-content">
            <h2>Quarter ${this.quarter} Complete!</h2>
            <button class="locker-room-button">Go To Locker Room</button>
          </div>
        `;
        document.body.appendChild(popup);
        
        // Wire up button
        const button = popup.querySelector('.locker-room-button');
        button.addEventListener('click', () => {
          if (typeof window.playSound === 'function') window.playSound('click-tiny.wav');
          const finalUrl = `/set-lineup.html?${params.toString()}`;
          console.log('🔍 [DEBUG QTR BREAK] gameScene.js - Navigating to set-lineup:', finalUrl);
          window.location.href = finalUrl;
        });
        return;
      }
    }
  };
}
