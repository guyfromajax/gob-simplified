/**
 * Tutorial Tip-off — Screen 3 of the FTE v2 funnel.
 *
 * Redesigned per the FTE Onboarding Redesign: rendered as a canonical Moment
 * modal (full-bleed team banner background + score-as-hero + portrait
 * spotlight) instead of the previous Sammy card on a radial navy background.
 * This is the *one* screen in the flow where the primary CTA is green —
 * SET LINEUP genuinely advances game state.
 *
 * Flow:
 *   1. Fetch /api/auth/me → team_pick
 *   2. Derive opponent (Xavien default; South Lancaster if user is Xavien)
 *   3. Render the Moment modal with the user's banner background + team Sammy
 *   4. SET LINEUP → POST /api/init-game (mode=tutorial) → tutorial-advance →
 *      navigate to /set-lineup.html?mode=tutorial&...&quarter=4
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

async function advanceToSetLineup() {
  try {
    await fetch(API_CONFIG.buildUrl('/api/auth/tutorial-advance'), {
      method: 'POST',
      headers: { ...API_CONFIG.getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ step: 'set_lineup' }),
    });
  } catch (e) {
    console.warn('[tutorial] could not advance to set_lineup step:', e);
  }
}

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

function gotoSetLineup(userTeam, opponent, gameId, _lineup) {
  // Tutorial set-lineup deliberately leaves the 5 slots blank — the user
  // sets their own lineup as part of the lesson. We no longer forward
  // home_pg / home_sg / etc. URL params even when the backend provides a
  // tutorial_lineup hint, so the slots render empty.
  const params = new URLSearchParams({
    mode: 'tutorial',
    home: userTeam,
    away: opponent,
    my_team: 'home',
    quarter: '4',
    team_id: userTeam,
  });
  if (gameId) params.set('game_id', gameId);
  window.location.href = `/set-lineup.html?${params.toString()}`;
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

  // Score block. User team is always home (per fte_inject_state §1-§2) and
  // the visual hero shows the matchup; we use uppercase team names per spec.
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

  const opponent = deriveOpponent(teamPick);
  paintMoment(teamPick, opponent);

  const ctaBtn = document.getElementById('tipoff-cta');
  if (!ctaBtn) return;
  ctaBtn.addEventListener('click', async () => {
    if (ctaBtn.disabled) return;
    ctaBtn.disabled = true;
    try {
      // Order matters: init-game first (the heaviest call; without it,
      // set-lineup has nothing to display). The response includes the
      // engine-assigned lineup (rank_roster output) so we don't need a
      // second round-trip. Then advance state. Then navigate.
      const init = await initTutorialGame(teamPick, opponent);
      if (!init || !init.game_id) {
        console.error('[tutorial] init-game returned no game_id');
        window.alert('Could not start the tutorial game. Please refresh and try again.');
        ctaBtn.disabled = false;
        return;
      }
      await advanceToSetLineup();
      gotoSetLineup(teamPick, opponent, init.game_id, init.home_lineup || {});
    } catch (e) {
      console.error('[tutorial] tip-off cta failed:', e);
      ctaBtn.disabled = false;
    }
  });
}

main();
