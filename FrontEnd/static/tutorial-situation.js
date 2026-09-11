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
 *      → /court.html?...&quarter=0&sim_full_game=1  (broadcast, ~80-85s)
 *
 * Per fte_inject_state.md §1-§2 the user is always HOME in the tutorial game.
 */

import { getTeamSammyImage } from '/js/shared/teamCoachAsset.js';
import { mountTutorialProgress } from '/js/shared/tutorialProgressThread.js';

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
    ctaBtn.disabled = true;
    try {
      // FTE v3: NO init-game here. The game doc was created back at the opponent
      // pick, because Game Plan and Lineup both write through to it. Calling
      // init again would mint a SECOND game and discard the user's strategy and
      // lineup — the two things this screen exists to pay off.
      const gameId = new URLSearchParams(window.location.search).get('game_id');
      if (!gameId) {
        console.error('[tutorial] no game_id at tip-off');
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
