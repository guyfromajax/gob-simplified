/**
 * Tutorial Persona Intro — Screen 0 of the FTE v2 funnel.
 *
 * First time the user meets Sammy. Only screen where Sammy appears in the
 * generic white-kit portrait — every subsequent screen uses the team-linked
 * variant via teamCoachAsset.js.
 *
 * Flow: LET'S GO → POST /api/auth/tutorial-advance { step: 'team_select' } →
 * navigate to /franchise-select-team.html?mode=tutorial.
 */

import { mountTutorialProgress } from '/js/shared/tutorialProgressThread.js';

const ctaBtn = document.getElementById('persona-intro-cta');
const errorEl = document.getElementById('persona-intro-error');

mountTutorialProgress('persona');

// Lobby music — same track + volume as mode-select / franchise-select-team
// so the audio feels continuous across the onboarding funnel. Each page
// owns its own Audio instance (the prior page's instance is GC'd on
// unload); matches the existing precedent on those two pages.
try {
  const lobbyMusic = new Audio('/sounds/crossover-21738.mp3');
  lobbyMusic.loop = true;
  lobbyMusic.volume = 0.4;
  lobbyMusic.play().catch(function () {});
} catch (e) { /* autoplay or codec fail — silent */ }

function showError(msg) {
  if (errorEl) errorEl.textContent = msg || '';
}

async function advanceToTeamSelect() {
  if (typeof API_CONFIG === 'undefined' ||
      typeof API_CONFIG.buildUrl !== 'function' ||
      typeof API_CONFIG.getAuthHeaders !== 'function') {
    // Public-only page guard — let the user move forward; the team-select
    // page will handle its own auth state.
    return true;
  }
  try {
    const res = await fetch(API_CONFIG.buildUrl('/api/auth/tutorial-advance'), {
      method: 'POST',
      headers: { ...API_CONFIG.getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ step: 'team_select' }),
    });
    if (!res.ok) {
      console.warn('[tutorial][persona-intro] advance failed:', res.status);
      // Don't block the user — they can still complete the flow; server state
      // will be reconciled on the next step.
      return true;
    }
    return true;
  } catch (e) {
    console.warn('[tutorial][persona-intro] advance threw:', e);
    return true;
  }
}

if (ctaBtn) {
  ctaBtn.addEventListener('click', async () => {
    if (ctaBtn.disabled) return;
    ctaBtn.disabled = true;
    showError('');
    try {
      await advanceToTeamSelect();
      window.location.href = '/franchise-select-team.html?mode=tutorial';
    } catch (e) {
      console.error('[tutorial][persona-intro]', e);
      showError('Something went wrong. Please try again.');
      ctaBtn.disabled = false;
    }
  });
}
