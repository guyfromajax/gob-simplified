/**
 * Tutorial Progress Thread — quiet 5-step indicator for the FTE v2 funnel.
 *
 * Per spec: "a subtle progress indicator across the onboarding steps (quiet
 * step thread; should not compete with content)."
 *
 *   import { mountTutorialProgress } from '/js/shared/tutorialProgressThread.js';
 *   mountTutorialProgress('username');   // step IDs below
 *
 * Steps mirror the user-visible flow, not the backend's TutorialStep enum:
 *   persona | program | username | tipoff | lineup
 */

const STEPS = [
  { id: 'persona', label: 'Persona' },
  { id: 'program', label: 'Program' },
  { id: 'username', label: 'Username' },
  { id: 'tipoff', label: 'Tip-off' },
  { id: 'lineup', label: 'Lineup' },
];

const STYLESHEET_HREF = '/css/tutorial-progress.css';
const HOST_ID = 'tutorial-progress-thread';

function ensureStylesheetLoaded() {
  if (document.querySelector(`link[href="${STYLESHEET_HREF}"]`)) return;
  const link = document.createElement('link');
  link.rel = 'stylesheet';
  link.href = STYLESHEET_HREF;
  document.head.appendChild(link);
}

export function mountTutorialProgress(activeStepId) {
  ensureStylesheetLoaded();

  // Remove a prior instance if any (idempotent — safe to call from any page).
  const existing = document.getElementById(HOST_ID);
  if (existing) existing.remove();

  const activeIdx = STEPS.findIndex((s) => s.id === activeStepId);
  const host = document.createElement('div');
  host.id = HOST_ID;
  host.className = 'tutorial-progress-thread';
  host.setAttribute('role', 'progressbar');
  host.setAttribute('aria-valuemin', '1');
  host.setAttribute('aria-valuemax', String(STEPS.length));
  host.setAttribute('aria-valuenow', String(activeIdx >= 0 ? activeIdx + 1 : 1));

  STEPS.forEach((step, idx) => {
    const stepEl = document.createElement('div');
    stepEl.className = 'tutorial-progress-step';
    if (activeIdx >= 0 && idx < activeIdx) stepEl.classList.add('is-complete');
    if (idx === activeIdx) stepEl.classList.add('is-active');
    stepEl.innerHTML = `
      <span class="tutorial-progress-dot" aria-hidden="true"></span>
      <span class="tutorial-progress-label">${step.label}</span>
    `;
    host.appendChild(stepEl);
    if (idx < STEPS.length - 1) {
      const sep = document.createElement('span');
      sep.className = 'tutorial-progress-sep';
      sep.setAttribute('aria-hidden', 'true');
      host.appendChild(sep);
    }
  });

  document.body.appendChild(host);
  return host;
}

export const TUTORIAL_STEP_IDS = STEPS.map((s) => s.id);
