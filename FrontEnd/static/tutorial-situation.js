/**
 * Tutorial Situation Card — step 3 of the FTE v2 funnel.
 *
 * Flow:
 *   1. Fetch /api/auth/me to read tutorial_state.team_pick (user's picked team)
 *   2. Derive opponent: Xavien, unless user picked Xavien (then South Lancaster)
 *   3. Show Sammy modal with the situation copy
 *   4. CTA: POST /api/auth/tutorial-advance { step: "set_lineup" } and
 *      navigate to /set-lineup.html?mode=tutorial&home=<user>&away=<opp>&my_team=home
 *
 * Per fte_inject_state.md §1-§2, the user is always HOME in the tutorial game.
 */

import { showSammyModal } from '/js/shared/sammyModal.js';


const DEFAULT_OPPONENT = 'Xavien';
const XAVIEN_FALLBACK_OPPONENT = 'South Lancaster';


function deriveOpponent(userTeam) {
  if (!userTeam) return DEFAULT_OPPONENT;
  return userTeam === DEFAULT_OPPONENT ? XAVIEN_FALLBACK_OPPONENT : DEFAULT_OPPONENT;
}


function situationBody(opponent) {
  // Copy locked by Coach. En-dash (–) between scores, not a hyphen.
  return `You're playing against ${opponent}. Tied 60–60. 4 minutes left in the 4th quarter. Go win it, Coach!`;
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


async function advanceToSetLineup() {
  try {
    await fetch(API_CONFIG.buildUrl('/api/auth/tutorial-advance'), {
      method: 'POST',
      headers: { ...API_CONFIG.getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ step: 'set_lineup' }),
    });
  } catch (e) {
    console.warn('[tutorial] could not advance to set_lineup step:', e);
    // Continue anyway — server state can be recovered on the next page.
  }
}


// Returns { game_id, home_lineup: { PG, SG, SF, PF, C } } or null on failure.
// home_lineup is the engine-assigned starting 5 (rank_roster output) which the
// situation page passes forward as URL params so set-lineup pre-populates with
// the right players. Backend returns this in the response body when mode=tutorial.
async function initTutorialGame(userTeam, opponent) {
  try {
    const res = await fetch(API_CONFIG.buildUrl('/api/init-game'), {
      method: 'POST',
      headers: { ...API_CONFIG.getAuthHeaders(), 'Content-Type': 'application/json' },
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
    if (!data.game_id) return null;
    const tutorialLineup = (data.tutorial_lineup || {}).home || {};
    const homeLineup = {};
    ['PG', 'SG', 'SF', 'PF', 'C'].forEach(pos => {
      if (tutorialLineup[pos]) homeLineup[pos] = String(tutorialLineup[pos]);
    });
    return { game_id: data.game_id, home_lineup: homeLineup };
  } catch (e) {
    console.error('[tutorial] init-game threw:', e);
    return null;
  }
}


function gotoSetLineup(userTeam, opponent, gameId, lineup) {
  // quarter=4 is critical: without it, set-lineup's module-level `quarter`
  // defaults to 1, and the /api/game fetch passes ?quarter=1 — which the
  // backend treats as a "new game scenario" (request Q1 + saved Q4) and
  // returns empty stats. With quarter=4 in the URL, the fetch returns the
  // real Q4 60-60 state populated by apply_tutorial_initial_state.
  const params = new URLSearchParams({
    mode: 'tutorial',
    home: userTeam,
    away: opponent,
    my_team: 'home',
    quarter: '4',
  });
  if (gameId) params.set('game_id', gameId);
  ['PG', 'SG', 'SF', 'PF', 'C'].forEach(pos => {
    if (lineup[pos]) params.set(`home_${pos.toLowerCase()}`, lineup[pos]);
  });
  window.location.href = `/set-lineup.html?${params.toString()}`;
}


async function main() {
  let me;
  try {
    me = await fetchMe();
  } catch (e) {
    console.error('[tutorial] failed to load /api/auth/me:', e);
    // Show a degraded fallback so the user isn't stuck on a black screen.
    showSammyModal({
      eyebrow: 'Hmm',
      body: 'We had trouble loading your tutorial. Please refresh the page.',
      ctaLabel: 'Reload',
      dismissOnCta: false,
      onCta: () => window.location.reload(),
    });
    return;
  }

  const teamPick = me?.tutorial_state?.team_pick;
  if (!teamPick) {
    // No team picked yet — bounce back to team-select.
    window.location.replace('/franchise-select-team.html?mode=tutorial');
    return;
  }

  const opponent = deriveOpponent(teamPick);

  showSammyModal({
    body: situationBody(opponent),
    ctaLabel: 'Set Lineup',
    dismissOnCta: false,
    onCta: async () => {
      // Order matters: init-game first (the heaviest call; without it,
      // set-lineup has nothing to display). The response includes the
      // engine-assigned lineup (rank_roster output) so we don't need a
      // second round-trip. Then advance state. Then navigate.
      const init = await initTutorialGame(teamPick, opponent);
      if (!init || !init.game_id) {
        console.error('[tutorial] init-game returned no game_id');
        window.alert('Could not start the tutorial game. Please refresh and try again.');
        return;
      }
      await advanceToSetLineup();
      gotoSetLineup(teamPick, opponent, init.game_id, init.home_lineup || {});
    },
  });
}


main();
