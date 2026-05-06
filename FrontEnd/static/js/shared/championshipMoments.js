/* eslint-disable */
/**
 * Championship Announce Moments — four overlay templates that replace the
 * standard EOG modal at specific franchise milestones. Source of truth for
 * visual treatment: _documentation_master/projects/Championship Announce.html.
 *
 * Public API (window.ChampionshipMoments):
 *   showMoment(moment, options) -> Promise<void>
 *     `moment` shape is the dict produced by
 *       BackEnd/utils/franchise_championship_moments.py
 *     `options.lockerRoomUrl`  navigation target for primary action
 *     `options.boxScoreUrl`    optional secondary-action target (variations
 *                              that have a Box Score button)
 *
 *   processPendingMoments(franchiseId, moments, options) -> Promise<void>
 *     Show each moment in sequence; clears each one server-side after the user
 *     dismisses via the action button. Backdrop click + ESC do NOT dismiss.
 */
(function () {
  'use strict';

  const STYLE_ID = 'championship-moments-styles';
  const ROOT_ID = 'championship-moments-root';

  // ----- CSS -----
  const CSS = `
.cm-overlay {
  position: fixed; inset: 0;
  z-index: 10001;
  display: none;
  align-items: center; justify-content: center;
  pointer-events: none;
}
.cm-overlay.is-visible {
  display: grid; place-items: center;
  pointer-events: auto;
}
.cm-backdrop {
  position: absolute; inset: 0;
  background: rgba(0, 0, 0, 0.72);
  backdrop-filter: blur(2px);
  opacity: 0;
  transition: opacity 280ms ease;
}
.cm-overlay.is-visible .cm-backdrop { opacity: 1; }
.cm-variation { position: relative; z-index: 1; opacity: 0; transition: opacity 240ms ease; }
.cm-overlay.is-visible .cm-variation { opacity: 1; }

.cm-btn {
  height: 44px;
  min-width: 138px;
  padding: 0 22px;
  border-radius: 10px;
  border: 1px solid rgba(255,255,255,0.28);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.18);
  font-family: 'Bebas Neue Pro', 'Bebas Neue', sans-serif;
  font-size: 18px;
  letter-spacing: 1.4px;
  cursor: pointer;
  color: #15181f;
  background: #34EC27;
  transition: transform 120ms ease, filter 160ms ease;
  display: inline-flex; align-items: center; justify-content: center;
  text-decoration: none;
}
.cm-btn:hover { transform: translateY(-1px); filter: brightness(1.06); }
.cm-btn:active { transform: translateY(0); filter: brightness(0.96); }
.cm-btn.ghost { background: rgba(255,255,255,0.08); color: #fff; }
.cm-btn.dark  { background: rgba(0,0,0,0.35); color: #fff; border-color: rgba(255,255,255,0.2); }

/* ============ Variation A — Classic Modal ============ */
.cm-va {
  width: min(560px, calc(100vw - 32px));
  border-radius: 16px;
  overflow: hidden;
  background: rgba(13, 17, 36, 0.97);
  border: 1px solid rgba(255,255,255,0.12);
  box-shadow: 0 30px 60px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.06);
  transform: scale(0.96);
  transition: transform 320ms cubic-bezier(.22,1,.36,1);
}
.cm-overlay.is-visible .cm-va { transform: scale(1); }
.cm-va-banner {
  position: relative; height: 220px; overflow: hidden;
  background:
    linear-gradient(180deg, rgba(13,17,36,0.0) 0%, rgba(13,17,36,0.55) 60%, rgba(13,17,36,0.97) 100%),
    linear-gradient(135deg, var(--cm-team, #C0392B) 0%, var(--cm-team-deep, #6f1f17) 100%);
}
.cm-va-banner::before {
  content: ''; position: absolute; inset: 0;
  background:
    radial-gradient(ellipse at 30% 20%, rgba(255,255,255,0.18), transparent 55%),
    radial-gradient(ellipse at 80% 80%, rgba(0,0,0,0.4), transparent 55%);
}
.cm-va-banner::after {
  content: ''; position: absolute; inset: 0;
  background: repeating-linear-gradient(115deg, transparent 0 14px, rgba(255,255,255,0.05) 14px 15px);
  mix-blend-mode: overlay;
}
.cm-va-badge {
  position: absolute; top: 16px; right: 16px;
  background: #34EC27; color: #0a1605;
  font-family: 'Bebas Neue Pro', 'Bebas Neue', sans-serif;
  letter-spacing: 1.2px; font-size: 13px;
  padding: 6px 12px; border-radius: 999px; z-index: 2;
  box-shadow: 0 0 0 1px rgba(0,0,0,0.4), 0 6px 14px rgba(52,236,39,0.25);
}
.cm-va-banner-inner {
  position: absolute; inset: 0;
  display: flex; flex-direction: column; align-items: center; justify-content: flex-end;
  padding: 22px 28px; z-index: 2;
}
.cm-va-trophy-chip {
  width: 64px; height: 64px; border-radius: 50%;
  background: rgba(0,0,0,0.45);
  border: 1px solid rgba(255,255,255,0.25);
  display: grid; place-items: center;
  margin-bottom: 14px;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.15), 0 8px 18px rgba(0,0,0,0.4);
}
.cm-va-eyebrow {
  font-family: 'Bebas Neue Pro', 'Bebas Neue', sans-serif;
  letter-spacing: 0.32em; font-size: 13px; color: #FFD700; margin-bottom: 6px;
}
.cm-va-headline {
  font-family: 'Bebas Neue Pro', 'Bebas Neue', sans-serif;
  font-weight: 700; font-size: 56px; letter-spacing: 1px;
  line-height: 0.95; text-align: center; color: #fff;
  text-shadow: 0 3px 0 rgba(0,0,0,0.35);
}
.cm-va-body { padding: 22px 28px; text-align: center; color: #fff; }
.cm-va-team {
  font-family: 'Bebas Neue Pro', 'Bebas Neue', sans-serif;
  font-weight: 700; font-size: 32px; letter-spacing: 0.5px;
  margin: 0 0 10px;
}
.cm-va-score { font-family: 'Inter', sans-serif; color: rgba(255,255,255,0.55); font-size: 14px; margin-bottom: 6px; }
.cm-va-score strong { color: #fff; font-weight: 600; }
.cm-va-meta {
  display: inline-flex; gap: 8px; color: rgba(255,255,255,0.55); font-size: 12px;
  letter-spacing: 0.06em; text-transform: uppercase;
  font-family: 'Bebas Neue Pro', 'Bebas Neue', sans-serif; margin-top: 4px;
}
.cm-va-meta .dot { width: 4px; height: 4px; border-radius: 50%; background: rgba(255,255,255,0.3); align-self: center; }
.cm-va-actions { display: flex; gap: 12px; padding: 0 28px 28px; }
.cm-va-actions .cm-btn:first-child { flex: 2; }
.cm-va-actions .cm-btn:last-child { flex: 1; min-width: 0; }

/* ============ Variation B — Cinematic Full-Bleed ============ */
.cm-vb-wrap {
  position: fixed; inset: 0; width: 100vw; height: 100vh;
  background: #04050a; overflow: hidden;
}
.cm-vb-floor {
  position: absolute; left: 50%; bottom: -25%;
  transform: translateX(-50%);
  width: 1200px; height: 1200px; border-radius: 50%;
  background: radial-gradient(circle, var(--cm-team, #C0392B) 0%, color-mix(in oklab, var(--cm-team, #C0392B), #04050a 70%) 35%, transparent 65%);
  filter: blur(8px); opacity: 0.92;
}
.cm-vb-spot {
  position: absolute; left: 50%; top: -120px; transform: translateX(-50%);
  width: 900px; height: 900px;
  background: radial-gradient(circle at center, rgba(255,255,255,0.16) 0%, rgba(255,255,255,0.04) 30%, transparent 60%);
  pointer-events: none;
}
.cm-vb-grain {
  position: absolute; inset: 0;
  background: repeating-linear-gradient(0deg, rgba(255,255,255,0.02) 0 1px, transparent 1px 3px);
  mix-blend-mode: overlay; pointer-events: none;
}
.cm-vb-content {
  position: relative; z-index: 2; height: 100%;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 0 24px; text-align: center; color: #fff;
}
.cm-vb-eyebrow {
  font-family: 'Bebas Neue Pro', 'Bebas Neue', sans-serif;
  letter-spacing: 0.6em; font-size: 14px; color: #FFD700;
  margin-bottom: 28px;
  padding: 8px 18px; border: 1px solid rgba(255,215,0,0.3); border-radius: 999px;
  background: rgba(255,215,0,0.06);
}
.cm-vb-headline {
  font-family: 'Bebas Neue Pro', 'Bebas Neue', sans-serif;
  font-weight: 700; font-size: clamp(96px, 14vw, 220px); letter-spacing: -2px; line-height: 0.85;
  margin: 0;
  background: linear-gradient(180deg, #fff 0%, #fff 55%, color-mix(in oklab, var(--cm-team, #C0392B), #fff 30%) 100%);
  -webkit-background-clip: text; background-clip: text; color: transparent;
  text-shadow: 0 8px 40px rgba(0,0,0,0.6);
}
.cm-vb-headline .line2 {
  display: block; font-size: 0.6em;
  background: linear-gradient(180deg, #FFD700 0%, #d4a017 100%);
  -webkit-background-clip: text; background-clip: text; color: transparent;
  margin-top: -8px;
}
.cm-vb-team {
  margin-top: 40px;
  font-family: 'Bebas Neue Pro', 'Bebas Neue', sans-serif;
  font-weight: 700; font-size: 48px; letter-spacing: 4px;
}
.cm-vb-score-row {
  display: flex; align-items: center; gap: 36px; margin-top: 18px;
  font-family: 'Bebas Neue Pro', 'Bebas Neue', sans-serif;
}
.cm-vb-score-team { font-size: 22px; color: rgba(255,255,255,0.72); letter-spacing: 0.18em; }
.cm-vb-score-num { font-size: 88px; font-weight: 700; line-height: 1; color: #fff; text-shadow: 0 4px 24px rgba(0,0,0,0.5); }
.cm-vb-score-num.lose { color: rgba(255,255,255,0.45); }
.cm-vb-score-divider { font-size: 64px; color: rgba(255,255,255,0.25); }
.cm-vb-actions { display: flex; gap: 16px; margin-top: 56px; }
.cm-vb-actions .cm-btn { height: 52px; min-width: 200px; font-size: 20px; }

/* ============ Variation C — Trophy Spotlight ============ */
.cm-vc {
  width: min(600px, calc(100vw - 32px));
  border-radius: 18px; overflow: hidden;
  background:
    radial-gradient(ellipse at 50% 0%, rgba(255,215,0,0.18), transparent 55%),
    linear-gradient(180deg, #14182a 0%, #0a0d18 100%);
  border: 1px solid rgba(255,215,0,0.22);
  box-shadow: 0 30px 80px rgba(0,0,0,0.7), inset 0 1px 0 rgba(255,215,0,0.18), 0 0 0 1px rgba(255,255,255,0.04);
  position: relative;
  color: #fff;
  transform: scale(0.96);
  transition: transform 320ms cubic-bezier(.22,1,.36,1);
}
.cm-overlay.is-visible .cm-vc { transform: scale(1); }
.cm-vc::before {
  content: ''; position: absolute; top: 0; left: 50%; transform: translateX(-50%);
  width: 380px; height: 320px;
  background: linear-gradient(180deg, rgba(255,215,0,0.22) 0%, rgba(255,215,0,0.06) 40%, transparent 75%);
  clip-path: polygon(35% 0, 65% 0, 100% 100%, 0 100%);
  pointer-events: none;
}
.cm-vc-eyebrow {
  text-align: center; padding-top: 28px;
  font-family: 'Bebas Neue Pro', 'Bebas Neue', sans-serif;
  letter-spacing: 0.42em; font-size: 12px; color: #FFD700;
  position: relative; z-index: 1;
}
.cm-vc-eyebrow::before, .cm-vc-eyebrow::after {
  content: ''; display: inline-block;
  width: 36px; height: 1px;
  background: rgba(255,215,0,0.5);
  vertical-align: middle; margin: 0 14px;
}
.cm-vc-trophy { position: relative; z-index: 1; margin: 18px auto 0; width: 132px; height: 160px; display: grid; place-items: center; }
.cm-vc-trophy svg { display: block; filter: drop-shadow(0 12px 24px rgba(255,215,0,0.25)); }
.cm-vc-headline {
  text-align: center;
  font-family: 'Bebas Neue Pro', 'Bebas Neue', sans-serif;
  font-weight: 700; font-size: 38px; letter-spacing: 1px;
  margin: 8px 24px 0; line-height: 1; position: relative; z-index: 1;
}
.cm-vc-sub {
  text-align: center;
  font-family: 'Bebas Neue Pro', 'Bebas Neue', sans-serif;
  font-size: 22px; color: #FFD700; letter-spacing: 0.18em;
  margin: 6px 0 0; position: relative; z-index: 1;
}
.cm-vc-pedestal {
  margin: 22px 28px 0; padding: 18px 22px;
  border-radius: 12px;
  background: linear-gradient(180deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.02) 100%);
  border: 1px solid rgba(255,255,255,0.10);
  display: grid; grid-template-columns: 56px 1fr;
  gap: 16px; align-items: center;
  position: relative; z-index: 1;
}
.cm-vc-crest {
  width: 56px; height: 56px; border-radius: 8px;
  background: linear-gradient(135deg, var(--cm-team, #C0392B), var(--cm-team-deep, #6f1f17));
  border: 1px solid rgba(255,255,255,0.18);
  display: grid; place-items: center; color: #fff;
  font-family: 'Bebas Neue Pro', 'Bebas Neue', sans-serif;
  font-weight: 700; font-size: 24px; letter-spacing: 1px;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.2);
}
.cm-vc-team-meta { text-align: left; }
.cm-vc-team-name {
  font-family: 'Bebas Neue Pro', 'Bebas Neue', sans-serif;
  font-weight: 700; font-size: 22px; line-height: 1; margin: 0 0 6px;
}
.cm-vc-team-record {
  font-family: 'Inter', sans-serif; color: rgba(255,255,255,0.55);
  font-size: 12px; letter-spacing: 0.04em;
}
.cm-vc-actions {
  display: flex; gap: 12px; padding: 22px 28px 26px; position: relative; z-index: 1;
}
.cm-vc-actions .cm-btn { flex: 1; }

/* ============ Variation D — Banner Raise ============ */
.cm-vd-wrap {
  position: fixed; inset: 0; width: 100vw; height: 100vh;
  background: linear-gradient(180deg, #050609 0%, #0b0d14 60%, #050609 100%);
  overflow: hidden;
}
.cm-vd-rafters {
  position: absolute; top: 0; left: 0; right: 0; height: 60px;
  background:
    linear-gradient(180deg, rgba(0,0,0,0.85) 0%, rgba(0,0,0,0.5) 60%, transparent 100%),
    repeating-linear-gradient(90deg, rgba(255,255,255,0.05) 0 2px, transparent 2px 80px);
  z-index: 3;
}
.cm-vd-spot {
  position: absolute; left: 50%; top: 0; transform: translateX(-50%);
  width: 700px; height: 100%;
  background: radial-gradient(ellipse at 50% 30%, rgba(255,255,255,0.10) 0%, transparent 55%);
  pointer-events: none;
}
.cm-vd-banner {
  position: absolute; left: 50%; top: 0;
  transform: translate(-50%, -100%);
  width: 360px; height: 540px;
  background:
    linear-gradient(180deg, rgba(0,0,0,0.18) 0%, transparent 12%),
    linear-gradient(180deg, var(--cm-team, #C0392B) 0%, var(--cm-team-deep, #6f1f17) 100%);
  border-left: 4px solid rgba(255,215,0,0.85);
  border-right: 4px solid rgba(255,215,0,0.85);
  border-bottom: 6px solid rgba(255,215,0,0.95);
  box-shadow: 0 30px 80px rgba(0,0,0,0.6), inset 0 0 80px rgba(0,0,0,0.4);
  z-index: 2;
  transition: transform 1100ms cubic-bezier(.22,1,.36,1) 200ms;
}
.cm-vd-banner.is-shown { transform: translate(-50%, 0); }
.cm-vd-banner::before {
  content: ''; position: absolute; top: -120px; left: 50%;
  width: 2px; height: 120px;
  background: linear-gradient(180deg, transparent 0%, rgba(255,255,255,0.18) 100%);
  transform: translateX(-50%);
}
.cm-vd-banner::after {
  content: ''; position: absolute; bottom: -16px; left: 0; right: 0;
  height: 16px;
  background: repeating-linear-gradient(90deg, rgba(255,215,0,0.95) 0 6px, transparent 6px 12px);
}
.cm-vd-banner-inner {
  height: 100%;
  display: flex; flex-direction: column; align-items: center; justify-content: space-between;
  padding: 56px 24px 48px;
  position: relative; color: #fff;
}
.cm-vd-banner-crest {
  width: 96px; height: 96px; border-radius: 50%;
  background: rgba(0,0,0,0.45);
  border: 3px solid rgba(255,215,0,0.85);
  display: grid; place-items: center; color: #FFD700;
  font-family: 'Bebas Neue Pro', 'Bebas Neue', sans-serif;
  font-weight: 700; font-size: 36px;
  box-shadow: inset 0 2px 0 rgba(255,255,255,0.1);
}
.cm-vd-banner-text { text-align: center; color: #fff; }
.cm-vd-banner-eyebrow {
  font-family: 'Bebas Neue Pro', 'Bebas Neue', sans-serif;
  letter-spacing: 0.4em; font-size: 12px; color: rgba(255,215,0,0.92);
  margin-bottom: 8px;
}
.cm-vd-banner-title {
  font-family: 'Bebas Neue Pro', 'Bebas Neue', sans-serif;
  font-weight: 700; font-size: 64px; line-height: 0.9; letter-spacing: 1px;
  margin: 0; text-shadow: 0 2px 0 rgba(0,0,0,0.5);
}
.cm-vd-banner-team {
  font-family: 'Bebas Neue Pro', 'Bebas Neue', sans-serif;
  font-weight: 700; font-size: 32px; letter-spacing: 1px;
  margin-top: 12px;
}
.cm-vd-banner-year {
  font-family: 'Bebas Neue Pro', 'Bebas Neue', sans-serif;
  letter-spacing: 0.32em; font-size: 14px; color: rgba(255,215,0,0.92);
  border-top: 1px solid rgba(255,215,0,0.4);
  border-bottom: 1px solid rgba(255,215,0,0.4);
  padding: 8px 16px;
}
.cm-vd-actions {
  position: absolute; left: 50%; bottom: 48px;
  transform: translate(-50%, 12px);
  display: flex; gap: 14px; z-index: 4;
  opacity: 0;
  transition: opacity 600ms ease 1400ms, transform 600ms ease 1400ms;
}
.cm-vd-actions.is-shown { opacity: 1; transform: translate(-50%, 0); }
.cm-vd-actions .cm-btn { height: 48px; min-width: 220px; font-size: 18px; }
.cm-vd-confetti {
  position: absolute; inset: 0; pointer-events: none; z-index: 3; overflow: hidden;
}
.cm-vd-confetti i {
  position: absolute; top: -20px; width: 8px; height: 14px;
  opacity: 0;
  animation: cm-confetti-fall var(--dur, 4s) linear var(--delay, 0s) infinite;
}
@keyframes cm-confetti-fall {
  0%   { transform: translateY(-20px) rotate(0deg); opacity: 0; }
  8%   { opacity: 1; }
  100% { transform: translateY(110vh) rotate(720deg); opacity: 0.9; }
}
`;

  function ensureStyles() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = CSS;
    document.head.appendChild(style);
  }

  function ensureRoot() {
    let root = document.getElementById(ROOT_ID);
    if (!root) {
      root = document.createElement('div');
      root.id = ROOT_ID;
      root.className = 'cm-overlay';
      root.innerHTML = '<div class="cm-backdrop"></div>';
      document.body.appendChild(root);
    }
    return root;
  }

  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  // ----- color helpers -----
  function hexToRgb(hex) {
    if (!hex || typeof hex !== 'string') return null;
    let h = hex.trim().replace(/^#/, '');
    if (h.length === 3) h = h.split('').map(c => c + c).join('');
    if (h.length !== 6) return null;
    const num = parseInt(h, 16);
    if (Number.isNaN(num)) return null;
    return { r: (num >> 16) & 255, g: (num >> 8) & 255, b: num & 255 };
  }
  function rgbToHex(r, g, b) {
    const c = v => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, '0');
    return '#' + c(r) + c(g) + c(b);
  }
  /** Darken a hex color by `pct` (0-1). Returns the original on parse failure. */
  function darkenHex(hex, pct) {
    const rgb = hexToRgb(hex);
    if (!rgb) return hex;
    const f = 1 - pct;
    return rgbToHex(rgb.r * f, rgb.g * f, rgb.b * f);
  }

  function applyTeamCss(root, primary) {
    const teamColor = primary || '#C0392B';
    root.style.setProperty('--cm-team', teamColor);
    root.style.setProperty('--cm-team-deep', darkenHex(teamColor, 0.55));
  }

  function teamInitial(name) {
    const t = (name || '').trim();
    return t ? t.charAt(0).toUpperCase() : '?';
  }

  function recordLabel(record) {
    if (!record) return '';
    const w = Number(record.W || record.wins || 0);
    const l = Number(record.L || record.losses || 0);
    return `${w}-${l}`;
  }

  // ----- variation builders -----
  function buildVariationA(moment) {
    const phase = moment.type === 'region_championship' ? 'REGION' : 'CONFERENCE';
    const num = moment.type === 'region_championship'
      ? (moment.region || '')
      : (moment.conference != null ? String(moment.conference) : '');
    const eyebrow = `SEASON ${moment.season} · ${phase} ${num}`.trim();
    const team = moment.winner_team_name || '';
    const score = moment.score || {};
    const winnerScore = Number(score.winner != null ? score.winner : 0);
    const loserScore  = Number(score.loser  != null ? score.loser  : 0);
    const loser = moment.loser_team_name || '';
    const recLine = recordLabel(moment.winner_record);
    const meta = recLine ? `REC ${escapeHtml(recLine)}` : '';
    return `
      <div class="cm-variation cm-va">
        <div class="cm-va-banner">
          <div class="cm-va-badge">CHAMPIONS</div>
          <div class="cm-va-banner-inner">
            <div class="cm-va-trophy-chip">
              <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
                <path d="M9 5h14v6a7 7 0 0 1-14 0V5z" stroke="#FFD700" stroke-width="1.6"/>
                <path d="M9 7H5a4 4 0 0 0 4 4M23 7h4a4 4 0 0 1-4 4" stroke="#FFD700" stroke-width="1.6"/>
                <path d="M13 18v4h6v-4M11 26h10" stroke="#FFD700" stroke-width="1.6" stroke-linecap="round"/>
              </svg>
            </div>
            <div class="cm-va-eyebrow">${escapeHtml(eyebrow)}</div>
            <div class="cm-va-headline">CHAMPIONS</div>
          </div>
        </div>
        <div class="cm-va-body">
          <h2 class="cm-va-team">${escapeHtml(team)}</h2>
          <div class="cm-va-score">
            Defeated <strong>${escapeHtml(loser)}</strong> &nbsp;<strong>${winnerScore}–${loserScore}</strong>
          </div>
          <div class="cm-va-meta">
            <span>FINAL · CHAMPIONSHIP GAME</span>
            ${meta ? `<span class="dot"></span><span>${meta}</span>` : ''}
          </div>
        </div>
        <div class="cm-va-actions">
          <button type="button" class="cm-btn" data-cm-action="primary">Back to Locker Room</button>
          <button type="button" class="cm-btn ghost" data-cm-action="boxscore">Box Score</button>
        </div>
      </div>
    `;
  }

  function buildVariationB(moment) {
    const winner = moment.winner_team_name || '';
    const loser = moment.loser_team_name || '';
    const winnerShort = (winner || '').toUpperCase();
    const loserShort = (loser || '').toUpperCase();
    const score = moment.score || {};
    const winnerScore = Number(score.winner != null ? score.winner : 0);
    const loserScore  = Number(score.loser  != null ? score.loser  : 0);
    return `
      <div class="cm-variation cm-vb-wrap">
        <div class="cm-vb-floor"></div>
        <div class="cm-vb-spot"></div>
        <div class="cm-vb-grain"></div>
        <div class="cm-vb-content">
          <div class="cm-vb-eyebrow">SEASON ${escapeHtml(moment.season)} · CHAMPIONSHIP</div>
          <h1 class="cm-vb-headline">
            NATIONAL
            <span class="line2">— CHAMPIONS —</span>
          </h1>
          <div class="cm-vb-team">${escapeHtml(winnerShort)}</div>
          <div class="cm-vb-score-row">
            <div>
              <div class="cm-vb-score-team">${escapeHtml(winnerShort)}</div>
              <div class="cm-vb-score-num">${winnerScore}</div>
            </div>
            <div class="cm-vb-score-divider">—</div>
            <div>
              <div class="cm-vb-score-team">${escapeHtml(loserShort)}</div>
              <div class="cm-vb-score-num lose">${loserScore}</div>
            </div>
          </div>
          <div class="cm-vb-actions">
            <button type="button" class="cm-btn" data-cm-action="primary">Back to Locker Room</button>
            <button type="button" class="cm-btn dark" data-cm-action="boxscore">Box Score</button>
          </div>
        </div>
      </div>
    `;
  }

  function buildVariationC(moment) {
    const sub = moment.conference != null
      ? `CONFERENCE ${escapeHtml(moment.conference)} · SEASON ${escapeHtml(moment.season)}`
      : `SEASON ${escapeHtml(moment.season)}`;
    const team = moment.winner_team_name || '';
    const rank = moment.winner_natl_rank;
    const seed = moment.winner_seed != null ? moment.winner_seed : 1;
    const recLine = recordLabel(moment.winner_record);
    const recordParts = [];
    if (recLine) recordParts.push(recLine);
    if (rank != null) recordParts.push(`NO. ${rank} NATIONAL`);
    recordParts.push(`NO. ${seed} SEED`);
    const recordLine = recordParts.join(' · ');
    return `
      <div class="cm-variation cm-vc">
        <div class="cm-vc-eyebrow">SEASON ${escapeHtml(moment.season)}</div>
        <div class="cm-vc-trophy">
          <svg width="120" height="150" viewBox="0 0 120 150" fill="none">
            <defs>
              <linearGradient id="cmGoldGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="#FFE680"/>
                <stop offset="50%" stop-color="#FFD700"/>
                <stop offset="100%" stop-color="#B8860B"/>
              </linearGradient>
              <linearGradient id="cmGoldHL" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stop-color="#FFF6C0"/>
                <stop offset="100%" stop-color="#D4A017"/>
              </linearGradient>
            </defs>
            <path d="M30 16 H90 V52 a30 30 0 0 1-60 0 Z" fill="url(#cmGoldGrad)" stroke="#8B6914" stroke-width="1.2"/>
            <path d="M30 22 C18 22 14 30 14 38 C14 46 22 50 30 48" stroke="url(#cmGoldHL)" stroke-width="3" fill="none"/>
            <path d="M90 22 C102 22 106 30 106 38 C106 46 98 50 90 48" stroke="url(#cmGoldHL)" stroke-width="3" fill="none"/>
            <rect x="54" y="80" width="12" height="22" fill="url(#cmGoldGrad)"/>
            <rect x="36" y="100" width="48" height="10" rx="2" fill="url(#cmGoldHL)"/>
            <rect x="30" y="108" width="60" height="14" rx="2" fill="url(#cmGoldGrad)"/>
            <rect x="26" y="120" width="68" height="6" rx="1" fill="#8B6914"/>
            <circle cx="60" cy="34" r="9" fill="#8B6914" opacity="0.35"/>
            <path d="M60 27 l2 5 l5 .5 l-4 4 l1 5 l-4 -3 l-4 3 l1 -5 l-4 -4 l5 -.5 z" fill="#FFF6C0"/>
            <path d="M40 22 V40" stroke="rgba(255,255,255,0.5)" stroke-width="2"/>
          </svg>
        </div>
        <h1 class="cm-vc-headline">REGULAR SEASON CHAMPIONS</h1>
        <div class="cm-vc-sub">${sub}</div>
        <div class="cm-vc-pedestal">
          <div class="cm-vc-crest">${escapeHtml(teamInitial(team))}</div>
          <div class="cm-vc-team-meta">
            <h3 class="cm-vc-team-name">${escapeHtml(team)}</h3>
            <div class="cm-vc-team-record">${escapeHtml(recordLine)}</div>
          </div>
        </div>
        <div class="cm-vc-actions">
          <button type="button" class="cm-btn" data-cm-action="primary">Back to Locker Room</button>
        </div>
      </div>
    `;
  }

  function buildVariationD(moment) {
    const team = moment.winner_team_name || '';
    return `
      <div class="cm-variation cm-vd-wrap">
        <div class="cm-vd-rafters"></div>
        <div class="cm-vd-spot"></div>
        <div class="cm-vd-confetti" data-cm-confetti></div>
        <div class="cm-vd-banner" data-cm-banner>
          <div class="cm-vd-banner-inner">
            <div class="cm-vd-banner-crest">${escapeHtml(teamInitial(team))}</div>
            <div class="cm-vd-banner-text">
              <div class="cm-vd-banner-eyebrow">CHAMPIONS</div>
              <h1 class="cm-vd-banner-title">RAISE<br/>THE<br/>BANNER</h1>
              <div class="cm-vd-banner-team">${escapeHtml(team.toUpperCase())}</div>
            </div>
            <div class="cm-vd-banner-year">SEASON ${escapeHtml(moment.season)}</div>
          </div>
        </div>
        <div class="cm-vd-actions" data-cm-actions>
          <button type="button" class="cm-btn" data-cm-action="primary">Back to Locker Room</button>
        </div>
      </div>
    `;
  }

  function spawnConfetti(host, primary) {
    if (!host) return;
    host.innerHTML = '';
    const colors = ['#FFD700', '#F79420', '#34EC27', '#4A90D9', '#ffffff', primary || '#C0392B'];
    const N = 80;
    for (let i = 0; i < N; i++) {
      const c = document.createElement('i');
      c.style.left = (Math.random() * 100) + '%';
      c.style.background = colors[Math.floor(Math.random() * colors.length)];
      c.style.setProperty('--dur', (3 + Math.random() * 3) + 's');
      c.style.setProperty('--delay', (Math.random() * 4) + 's');
      c.style.transform = `rotate(${Math.random() * 360}deg)`;
      const r = Math.random();
      if (r < 0.3) {
        c.style.width = '6px'; c.style.height = '6px'; c.style.borderRadius = '50%';
      } else if (r < 0.5) {
        c.style.width = '14px'; c.style.height = '3px';
      }
      host.appendChild(c);
    }
  }

  function buildVariationHtml(moment) {
    switch (moment.type) {
      case 'conference_championship':
      case 'region_championship':
        return buildVariationA(moment);
      case 'national_championship':
        return buildVariationB(moment);
      case 'trophy_spotlight':
        return buildVariationC(moment);
      case 'banner_raise':
        return buildVariationD(moment);
      default:
        return '';
    }
  }

  function showMoment(moment, options) {
    return new Promise((resolve) => {
      if (!moment || !moment.type) {
        resolve();
        return;
      }
      ensureStyles();
      const root = ensureRoot();
      applyTeamCss(root, moment.winner_primary_color);

      // Backdrop only on the FIRST child; replace any prior variation.
      const existing = root.querySelector('.cm-variation');
      if (existing) existing.remove();

      const html = buildVariationHtml(moment);
      if (!html) { resolve(); return; }
      const tmp = document.createElement('div');
      tmp.innerHTML = html.trim();
      const variationNode = tmp.firstChild;
      root.appendChild(variationNode);

      // Animate-in: needs to render first, then add is-visible on root.
      requestAnimationFrame(() => {
        root.classList.add('is-visible');
        if (moment.type === 'banner_raise') {
          const banner  = variationNode.querySelector('[data-cm-banner]');
          const actions = variationNode.querySelector('[data-cm-actions]');
          const confetti = variationNode.querySelector('[data-cm-confetti]');
          spawnConfetti(confetti, moment.winner_primary_color);
          requestAnimationFrame(() => {
            requestAnimationFrame(() => {
              if (banner) banner.classList.add('is-shown');
              if (actions) actions.classList.add('is-shown');
            });
          });
        }
      });

      function dismiss(action) {
        root.classList.remove('is-visible');
        // Allow fade out, then clean up.
        setTimeout(() => {
          try { variationNode.remove(); } catch (_) {}
        }, 320);
        const opts = options || {};
        if (action === 'primary' && opts.lockerRoomUrl) {
          window.location.href = opts.lockerRoomUrl;
          return;
        }
        if (action === 'boxscore') {
          let url = opts.boxScoreUrl;
          if (typeof opts.boxScoreUrlBuilder === 'function') {
            try { url = opts.boxScoreUrlBuilder(moment); } catch (_) {}
          }
          if (url) {
            window.location.href = url;
            return;
          }
        }
        resolve();
      }

      variationNode.addEventListener('click', (e) => {
        const target = e.target.closest('[data-cm-action]');
        if (!target) return;
        const action = target.getAttribute('data-cm-action');
        if (typeof window.playSound === 'function') {
          try { window.playSound('click-tiny.wav'); } catch (_) {}
        }
        dismiss(action);
      });
    });
  }

  async function dismissOnServer(franchiseId, momentId) {
    if (!franchiseId || !momentId) return;
    if (typeof window === 'undefined' || typeof fetch !== 'function') return;
    if (typeof window.API_CONFIG === 'undefined' || !window.API_CONFIG.buildUrl) return;
    try {
      await fetch(window.API_CONFIG.buildUrl('/franchise/championship-moments/dismiss'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(window.API_CONFIG.getAuthHeaders ? window.API_CONFIG.getAuthHeaders() : {}),
        },
        body: JSON.stringify({ franchise_id: franchiseId, moment_id: momentId }),
      });
    } catch (err) {
      console.warn('[ChampionshipMoments] dismiss request failed:', err);
    }
  }

  async function processPendingMoments(franchiseId, moments, options) {
    if (!Array.isArray(moments) || !moments.length) return;
    for (const moment of moments) {
      // Each call awaits user dismissal before showing the next.
      // For "primary" action we navigate away; navigation kills the loop naturally.
      // eslint-disable-next-line no-await-in-loop
      await showMoment(moment, options);
      // eslint-disable-next-line no-await-in-loop
      await dismissOnServer(franchiseId, moment.id);
    }
  }

  window.ChampionshipMoments = {
    showMoment,
    processPendingMoments,
    dismissOnServer,
  };
})();
