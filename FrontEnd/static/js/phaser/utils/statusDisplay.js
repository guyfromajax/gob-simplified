/**
 * Shared status display utility for simulation status messages.
 * Used by bootGame.js and finalizeGame.js to show "Simulating Q..." and "Simulating Computer Games..." messages.
 */

/**
 * Show status message (e.g., "Simulating Q1...", "Simulating Computer Games...")
 * @param {string} msg - Status message to display
 */
export function showStatus(msg) {
  const container = document.getElementById('phaser-container') || document.body;
  let el = document.getElementById('sim-status');
  if (!el) {
    el = document.createElement('div');
    el.id = 'sim-status';
    el.style.color = '#fff';
    el.style.fontFamily = 'Bebas Neue, sans-serif';
    // Position relative to court container so "Simulating Q..." is vertically centered in the court
    el.style.position = 'absolute';
    el.style.top = '50%';
    el.style.left = '50%';
    el.style.transform = 'translate(-50%, -50%)';
    el.style.fontSize = '24px';
    el.style.zIndex = '10000';
    el.style.pointerEvents = 'none';
    el.style.padding = '16px 24px';
    el.style.background = 'rgba(12, 12, 12, 0.82)';
    el.style.border = '2px solid rgba(255, 255, 255, 0.18)';
    el.style.borderRadius = '14px';
    el.style.boxShadow = '0 18px 40px rgba(0, 0, 0, 0.42)';
    el.style.backdropFilter = 'blur(3px)';
    el.style.textAlign = 'center';
    el.style.letterSpacing = '0.04em';
    el.style.textTransform = 'uppercase';
    el.style.minWidth = '320px';
    container.appendChild(el);
  }
  el.textContent = msg;
  el.style.display = 'block';
}

/**
 * Hide status message
 */
export function hideStatus() {
  const el = document.getElementById('sim-status');
  if (el) {
    el.style.display = 'none';
  }
}
