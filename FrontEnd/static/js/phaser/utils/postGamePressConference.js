/**
 * Post-game press conference (franchise): runs in a modal on court.html while
 * phase-b (CPU games) completes. Phase-b may already be in flight from the EOG popup
 * (`getOrStartFranchisePhaseB`); this module attaches to the same Promise.
 *
 * Persists answers via POST /franchise/press-conference/session (+ /answer, /complete).
 */

import { getOrStartFranchisePhaseB } from './franchisePhaseBClient.js';

const PGPC_STYLE_ID = 'post-game-press-conference-styles';
/** Dummy / placeholder UI only; live sessions use four choices (A–D) from the API. */
const CHOICE_LABELS = ['A', 'B', 'C', 'D'];

function buildDummyQuestions() {
  const out = [];
  for (let i = 1; i <= 10; i += 1) {
    out.push({
      id: i,
      text: `Question ${i}`,
      answers: CHOICE_LABELS.map((letter) => ({
        letter,
        text: `Answer ${letter}`,
      })),
    });
  }
  return out;
}

export const PGPC_DUMMY_QUESTIONS = buildDummyQuestions();

function jsonHeaders() {
  return Object.assign(
    { 'Content-Type': 'application/json' },
    typeof API_CONFIG !== 'undefined' && API_CONFIG.getAuthHeaders ? API_CONFIG.getAuthHeaders() : {}
  );
}

function ensurePgpcStyles() {
  if (document.getElementById(PGPC_STYLE_ID)) return;
  const style = document.createElement('style');
  style.id = PGPC_STYLE_ID;
  style.textContent = `
    .pgpc-overlay {
      position: fixed;
      inset: 0;
      z-index: 10050;
      background: rgba(0,0,0,0.88);
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 18px;
      box-sizing: border-box;
    }
    .pgpc-panel {
      width: min(520px, 100%);
      max-height: min(90vh, 640px);
      overflow: auto;
      background: rgba(13, 17, 36, 0.98);
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 16px;
      padding: 22px 24px 26px;
      box-shadow: 0 24px 48px rgba(0,0,0,0.55);
    }
    .pgpc-modal-title {
      font-family: 'Bebas Neue', sans-serif;
      font-size: 22px;
      color: rgba(255,255,255,0.92);
      letter-spacing: 0.08em;
      text-transform: uppercase;
      margin: 0 0 14px;
    }
    .pgpc-question {
      font-family: 'Bebas Neue', sans-serif;
      font-size: 28px;
      color: #fff;
      line-height: 1.15;
      margin: 0 0 16px;
    }
    .pgpc-choices {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .pgpc-choice-row {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 12px 14px;
      border-radius: 10px;
      border: 1px solid rgba(255,255,255,0.12);
      background: rgba(255,255,255,0.05);
      cursor: pointer;
      text-align: left;
      transition: background 0.12s ease, border-color 0.12s ease;
      font-family: 'Inter', sans-serif;
      font-size: 16px;
      font-weight: 400;
      letter-spacing: normal;
      color: rgba(255,255,255,0.92);
    }
    .pgpc-choice-row:hover {
      background: rgba(247, 148, 32, 0.12);
      border-color: rgba(247, 148, 32, 0.35);
    }
    .pgpc-choice-letter {
      font-family: 'Bebas Neue', sans-serif;
      font-size: 20px;
      color: #F79420;
      min-width: 28px;
    }
    .pgpc-wait-logo {
      width: 140px;
      max-width: 55%;
      height: auto;
      display: block;
      margin: 0 auto;
      border-radius: 12px;
      box-shadow: 0 14px 28px rgba(0,0,0,0.35);
    }
    .pgpc-wait-sub {
      font-family: 'Inter', sans-serif;
      font-size: 15px;
      color: rgba(255,255,255,0.68);
      text-align: center;
      margin: 22px 0 20px;
    }
    .pgpc-pulse-track {
      width: min(220px, 100%);
      height: 8px;
      margin: 0 auto;
      border-radius: 999px;
      overflow: hidden;
      background: rgba(255,255,255,0.08);
    }
    .pgpc-pulse-bar {
      display: block;
      width: 100%;
      height: 100%;
      border-radius: inherit;
      background: linear-gradient(90deg, rgba(52,236,39,0.35), #34EC27 48%, rgba(52,236,39,0.45));
      transform-origin: left center;
      animation: pgpcPulseBar 1.2s ease-in-out infinite;
    }
    @keyframes pgpcPulseBar {
      0%, 100% { opacity: 0.5; transform: scaleX(0.35); }
      50% { opacity: 1; transform: scaleX(1); }
    }
    .pgpc-primary-btn {
      margin-top: 18px;
      width: 100%;
      height: 46px;
      border: none;
      border-radius: 10px;
      background: #34EC27;
      color: #15181f;
      font-family: 'Bebas Neue', sans-serif;
      font-size: 18px;
      letter-spacing: 0.04em;
      cursor: pointer;
    }
    .pgpc-primary-btn:hover { filter: brightness(1.06); }
  `;
  document.head.appendChild(style);
}

/** Square team logo for the “still simming” waiting state (after all PC questions). */
function logoSrcForTeam(userTeamName) {
  if (userTeamName && typeof getTeamAssetPath === 'function') {
    return getTeamAssetPath(userTeamName, 'logo_square');
  }
  return '/images/teams/general/general_logo_square.png';
}

/**
 * @param {Object} opts
 * @param {{ franchise_id: string, week: number }} opts.franchisePhaseBPending
 * @param {string} [opts.userTeamName]
 * @param {string} [opts.gameId]
 * @param {string} [opts.lockerRoomUrl]
 * @param {() => void} [opts.onCloseParentPopup] - remove EOG popup first
 */
export async function launchPostGamePressConference(opts) {
  const {
    franchisePhaseBPending,
    userTeamName,
    gameId,
    lockerRoomUrl,
    onCloseParentPopup,
  } = opts;

  if (!franchisePhaseBPending || typeof API_CONFIG === 'undefined' || !API_CONFIG.buildUrl) {
    console.warn('[PGPC] Missing pending payload or API_CONFIG');
    return;
  }

  ensurePgpcStyles();
  if (typeof onCloseParentPopup === 'function') onCloseParentPopup();

  const overlay = document.createElement('div');
  overlay.className = 'pgpc-overlay';
  overlay.setAttribute('role', 'dialog');
  overlay.setAttribute('aria-modal', 'true');
  overlay.setAttribute('aria-label', 'Post-game press conference');

  const panel = document.createElement('div');
  panel.className = 'pgpc-panel';
  overlay.appendChild(panel);
  document.body.appendChild(overlay);

  const weekNum = Number(franchisePhaseBPending.week);
  const franchiseId = String(franchisePhaseBPending.franchise_id);

  let sessionId = null;
  let questionIndex = 0;
  let phaseBResolved = false;
  let phaseBOk = false;
  let questions = PGPC_DUMMY_QUESTIONS;

  const renderBody = (html) => {
    panel.innerHTML = html;
  };

  function attachPhaseBHandlers(promise) {
    promise
      .then(async (res) => {
        phaseBResolved = true;
        phaseBOk = res.ok;
        if (!res.ok) {
          try {
            console.error('[PGPC] phase-b failed:', res.status, await res.text());
          } catch (_) {}
        }
        try {
          if (phaseBOk && typeof localStorage !== 'undefined') {
            localStorage.removeItem('franchise_complete_week_pending');
            localStorage.removeItem('franchise_eog_pgpc_snapshot');
          }
        } catch (_) {}
        if (allAnswered()) {
          tryShowFinal();
        }
      })
      .catch((err) => {
        phaseBResolved = true;
        phaseBOk = false;
        console.error('[PGPC] phase-b error:', err);
        if (allAnswered()) {
          tryShowFinal();
        }
      });
  }

  const phaseBPromise = getOrStartFranchisePhaseB(franchisePhaseBPending);
  attachPhaseBHandlers(phaseBPromise);

  function allAnswered() {
    return questionIndex >= questions.length;
  }

  function renderQuestionView() {
    const q = questions[questionIndex];
    if (!q) return;
    const rows = q.answers
      .map(
        (a) => `
      <button type="button" class="pgpc-choice-row" data-choice="${a.letter}">
        <span class="pgpc-choice-letter">${a.letter}</span>
        <span>${a.text}</span>
      </button>
    `
      )
      .join('');
    renderBody(`
      <h1 class="pgpc-modal-title">Question ${questionIndex + 1} of ${questions.length}</h1>
      <h2 class="pgpc-question">${q.text}</h2>
      <div class="pgpc-choices">${rows}</div>
    `);

    panel.querySelectorAll('.pgpc-choice-row').forEach((btn) => {
      btn.addEventListener('click', onChoiceClick);
    });
  }

  async function onChoiceClick(e) {
    const btn = e.currentTarget;
    const choice = btn.getAttribute('data-choice');
    if (!choice || !sessionId) return;
    if (typeof window.playSound === 'function') window.playSound('click-tiny.wav');

    try {
      const res = await fetch(
        API_CONFIG.buildUrl(`/franchise/press-conference/session/${sessionId}/answer`),
        {
          method: 'POST',
          headers: jsonHeaders(),
          body: JSON.stringify({ question_index: questionIndex, choice }),
        }
      );
      if (!res.ok) {
        try {
          console.warn('[PGPC] answer save failed:', res.status, await res.text());
        } catch (_) {}
      }
    } catch (err) {
      console.warn('[PGPC] answer save failed:', err);
    }

    questionIndex += 1;
    if (!allAnswered()) {
      renderQuestionView();
      return;
    }
    tryShowFinal();
  }

  function renderWaitingView() {
    const src = logoSrcForTeam(userTeamName);
    renderBody(`
      <img class="pgpc-wait-logo" src="${src}" alt="" />
      <p class="pgpc-wait-sub">Simming Computer Games</p>
      <div class="pgpc-pulse-track" aria-hidden="true"><span class="pgpc-pulse-bar"></span></div>
    `);
  }

  function renderCompleteView() {
    const weekLabel = Number.isFinite(weekNum) ? weekNum : '?';
    renderBody(`
      <h2 class="pgpc-question" style="text-align:center;">Week ${weekLabel} complete.</h2>
      <button type="button" class="pgpc-primary-btn pgpc-gtlr">Go To Locker Room</button>
    `);
    const gtlr = panel.querySelector('.pgpc-gtlr');
    if (gtlr) {
      gtlr.addEventListener('click', async () => {
        if (typeof window.playSound === 'function') window.playSound('click-tiny.wav');
        if (sessionId) {
          try {
            await fetch(API_CONFIG.buildUrl(`/franchise/press-conference/session/${sessionId}/complete`), {
              method: 'POST',
              headers: jsonHeaders(),
            });
          } catch (_) {}
        }
        overlay.remove();
        if (lockerRoomUrl) window.location.href = lockerRoomUrl;
      });
    }
  }

  function tryShowFinal() {
    if (!allAnswered()) return;
    if (!phaseBResolved) {
      renderWaitingView();
      return;
    }
    if (!phaseBOk) {
      renderBody(`
        <p class="pgpc-question" style="font-size:20px;">Could not finish computer games for this week. Check your connection and try again from the command center.</p>
        <button type="button" class="pgpc-primary-btn pgpc-dismiss">OK</button>
      `);
      const d = panel.querySelector('.pgpc-dismiss');
      if (d) {
        d.addEventListener('click', () => {
          overlay.remove();
          if (lockerRoomUrl) window.location.href = lockerRoomUrl;
        });
      }
      return;
    }
    renderCompleteView();
  }

  try {
    const createRes = await fetch(API_CONFIG.buildUrl('/franchise/press-conference/session'), {
      method: 'POST',
      headers: jsonHeaders(),
      body: JSON.stringify({
        franchise_id: franchiseId,
        week: weekNum,
        game_id: gameId || null,
        question_set_id: 'bank_v1',
      }),
    });
    if (!createRes.ok) {
      const t = await createRes.text();
      console.error('[PGPC] session create failed:', createRes.status, t);
      renderBody(`
        <h1 class="pgpc-modal-title">Press conference unavailable</h1>
        <p class="pgpc-question" style="font-size:18px;">Could not start press conference (${createRes.status}). You can still finish the week from the franchise command center.</p>
        <button type="button" class="pgpc-primary-btn pgpc-dismiss">Go To Locker Room</button>
      `);
      const d = panel.querySelector('.pgpc-dismiss');
      if (d) {
        d.addEventListener('click', () => {
          overlay.remove();
          if (lockerRoomUrl) window.location.href = lockerRoomUrl;
        });
      }
      return;
    }
    const created = await createRes.json();
    sessionId = created.session_id;
    if (Array.isArray(created.questions) && created.questions.length > 0) {
      questions = created.questions;
    }
  } catch (err) {
    console.error('[PGPC] session create error:', err);
    renderBody(`
      <h1 class="pgpc-modal-title">Press conference unavailable</h1>
      <p class="pgpc-question" style="font-size:18px;">Network error starting press conference.</p>
      <button type="button" class="pgpc-primary-btn pgpc-dismiss">Go To Locker Room</button>
    `);
    const d = panel.querySelector('.pgpc-dismiss');
    if (d) {
      d.addEventListener('click', () => {
        overlay.remove();
        if (lockerRoomUrl) window.location.href = lockerRoomUrl;
      });
    }
    return;
  }

  renderQuestionView();
}
