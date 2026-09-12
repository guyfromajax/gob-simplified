/**
 * Tutorial Tip-off — Screen 7 of the FTE v3 funnel.
 *
 * Redesigned per the FTE Onboarding Redesign: rendered as a canonical Moment
 * modal (full-bleed team banner background + score-as-hero + portrait
 * spotlight) instead of the previous Sammy card on a radial navy background.
 * This is the *one* screen in the flow where the primary CTA is green —
 * it genuinely advances game state.
 *
 * FTE v3 moved this screen from position 3 to position 7: the user now picks an
 * opponent, sets a game plan and confirms a lineup BEFORE the tip. It also no
 * longer creates the game — that happens at the opponent step, because the two
 * screens in between write through to the game doc.
 *
 * Flow:
 *   1. Fetch /api/auth/me → team_pick
 *   2. Opponent from the `away` param (the user's pick at step 4)
 *   3. Render the Moment modal with the user's banner background + team Sammy
 *   4. SIM GAME → tutorial-advance { step: 'in_game' }
 *      → /court.html?...&quarter=1&sim_full_game=1  (broadcast, ~80-85s)
 *
 * Per fte_inject_state.md §1-§2 the user is always HOME in the tutorial game.
 */

import { getTeamSammyImage } from '/js/shared/teamCoachAsset.js';
import { mountTutorialProgress } from '/js/shared/tutorialProgressThread.js';
import { playAdvance } from '/js/shared/uiSfx.js';

const DEFAULT_OPPONENT = 'Xavien';
const XAVIEN_FALLBACK_OPPONENT = 'South Lancaster';

mountTutorialProgress('tipoff');

function deriveOpponent(userTeam) {
  if (!userTeam) return DEFAULT_OPPONENT;
  return userTeam === DEFAULT_OPPONENT ? XAVIEN_FALLBACK_OPPONENT : DEFAULT_OPPONENT;
}

function resolveTeamBanner(teamName) {
  if (typeof getTeamAssetPath === 'function') {
    return getTeamAssetPath(teamName, 'banner_primary');
  }
  return '/images/teams/general/general_banner_primary.jpg';
}

async function fetchMe() {
  if (typeof API_CONFIG === 'undefined' ||
      typeof API_CONFIG.buildUrl !== 'function' ||
      typeof API_CONFIG.getAuthHeaders !== 'function') {
    throw new Error('API_CONFIG unavailable');
  }
  const res = await fetch(API_CONFIG.buildUrl('/api/auth/me'), {
    method: 'GET',
    headers: API_CONFIG.getAuthHeaders(),
  });
  if (!res.ok) throw new Error('Could not load user');
  return res.json();
}

async function advanceToInGame() {
  try {
    await fetch(API_CONFIG.buildUrl('/api/auth/tutorial-advance'), {
      method: 'POST',
      headers: { ...API_CONFIG.getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ step: 'in_game' }),
    });
  } catch (e) {
    console.warn('[tutorial] could not advance to in_game step:', e);
  }
}

function gotoBroadcast(userTeam, opponent, gameId) {
  // FTE v3: the tip hands off to the COURT, not to set-lineup — strategy and
  // roster are already done. quarter=0 is the pre-anchor state that
  // handleSimFullGame() requires (bootGame gates Sim Full Game on
  // `Math.max(0, quarter) < 2`); v2 sent quarter=4 because it resumed mid-Q4.
  // `sim_full_game=1` is the tutorial's instruction to boot straight into the
  // broadcast instead of showing the pre-game button row.
  // Start from the INCOMING query string, don't rebuild it. It carries the five the
  // user set as home_pg / home_sg / … — the court needs those to seed the lineup.
  // Rebuilding here is what emptied the pre-game card once already.
  const params = new URLSearchParams(window.location.search);
  params.set('mode', 'tutorial');
  params.set('home', userTeam);
  params.set('away', opponent);
  params.set('my_team', 'home');
  params.set('team_id', userTeam);
  // MUST be 1, not 0.
  //
  // bootGame's sim loop does `let currentQ = quarter`, and BOTH of the payload
  // branches that matter key off it:
  //   - `if (currentQ === quarter)`  -> sends home_lineup/away_lineup (first pass only)
  //   - `if (currentQ === 1 && ...)` -> sends strategy_settings
  // With quarter=0 the first pass simulates a non-existent Q0: the chosen five is
  // handed to a no-op quarter, Q1 onward falls through to auto-set lineups, and the
  // game plan is NEVER sent because currentQ is 0 on the only pass that would send
  // it. Observed as an empty pre-game card AND silently ignored sliders.
  // Sim Full Game still triggers correctly — its gate is `Math.max(0, quarter) < 2`.
  params.set('quarter', '1');
  params.set('sim_full_game', '1');
  params.delete('resume_from_timeout');
  params.delete('lineup_checkpoint');
  if (gameId) params.set('game_id', gameId);
  window.location.href = `/court.html?${params.toString()}`;
}

function paintMoment(userTeam, opponent) {
  const banner = resolveTeamBanner(userTeam);
  // Surface the banner asset to the CSS pipeline as a custom property so
  // the modal's ::before watermark layer can read it. The darkening
  // gradient lives in ::after now (see tutorial-tipoff.css) — JS no
  // longer composites the gradient inline.
  const moment = document.getElementById('tipoff-moment');
  if (moment) {
    moment.style.setProperty('--moment-bg-image', `url('${banner}')`);
    moment.hidden = false;
  }
  const portraitEl = document.getElementById('tipoff-portrait');
  if (portraitEl) portraitEl.src = getTeamSammyImage(userTeam);

  // Matchup block. User team is always home (per fte_inject_state §1-§2).
  // FTE v3 removed the score spans — the game has not been played yet, so there
  // is no score to show; the markup now renders "HOME vs AWAY".
  const homeTeamEl = document.getElementById('tipoff-home-team');
  const awayTeamEl = document.getElementById('tipoff-away-team');
  if (homeTeamEl) homeTeamEl.textContent = userTeam.toUpperCase();
  if (awayTeamEl) awayTeamEl.textContent = opponent.toUpperCase();
}

async function main() {
  let me;
  try {
    me = await fetchMe();
  } catch (e) {
    console.error('[tutorial] failed to load /api/auth/me:', e);
    document.body.innerHTML = '<div style="padding:40px;text-align:center;color:#fff;font-family:Inter,sans-serif;">We had trouble loading your tutorial. Please refresh.</div>';
    return;
  }

  const teamPick = me?.tutorial_state?.team_pick;
  if (!teamPick) {
    window.location.replace('/franchise-select-team.html?mode=tutorial');
    return;
  }

  // FTE v3: the user PICKED their opponent at step 4. Fall back to the v2
  // derivation only if the param is somehow absent (a hand-typed URL).
  const opponent = new URLSearchParams(window.location.search).get('away')
    || deriveOpponent(teamPick);
  paintMoment(teamPick, opponent);

  const ctaBtn = document.getElementById('tipoff-cta');
  if (!ctaBtn) return;
  ctaBtn.addEventListener('click', async () => {
    if (ctaBtn.disabled) return;
    playAdvance();
    ctaBtn.disabled = true;
    try {
      // FTE v3: NO init-game here. The game doc was created back at the opponent
      // pick, because Game Plan and Lineup both write through to it. Calling
      // init again would mint a SECOND game and discard the user's strategy and
      // lineup — the two things this screen exists to pay off.
      // URL first, then tutorial_state. The server copy is the durable one: it
      // survives a refresh, a hand-typed URL, or any upstream screen that drops
      // the param. Falling back to it is what stops a lost query string from
      // dead-ending the funnel one click from the payoff.
      let gameId = new URLSearchParams(window.location.search).get('game_id');
      if (!gameId) {
        gameId = ((me && me.tutorial_state) || {}).game_id || null;
      }
      if (!gameId) {
        console.error('[tutorial] no game_id at tip-off (URL and tutorial_state both empty)');
        window.alert('Could not start the tutorial game. Please refresh and try again.');
        ctaBtn.disabled = false;
        return;
      }
      await advanceToInGame();
      gotoBroadcast(teamPick, opponent, gameId);
    } catch (e) {
      console.error('[tutorial] tip-off cta failed:', e);
      ctaBtn.disabled = false;
    }
  });
}

main();
