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
  // Copy locked by Coach in PR 2c spec discussion.
  return `Ok Coach, let's play ball. You're playing ${opponent}, ` +
         `and the score is tied 60-60 with 4 minutes remaining. Let's win this!`;
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


function gotoSetLineup(userTeam, opponent) {
  const params = new URLSearchParams({
    mode: 'tutorial',
    home: userTeam,
    away: opponent,
    my_team: 'home',
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
      await advanceToSetLineup();
      gotoSetLineup(teamPick, opponent);
    },
  });
}


main();
