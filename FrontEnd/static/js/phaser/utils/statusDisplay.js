/**
 * Shared status display utility for simulation status messages.
 * Used by bootGame.js and finalizeGame.js to show "Simulating Q..." and "Simulating Computer Games..." messages.
 */

/**
 * Show status message (e.g., "Simulating Q1...", "Simulating Computer Games...")
 * @param {string} msg - Status message to display
 */
export function showStatus(msg) {
  let el = document.getElementById('sim-status');
  if (!el) {
    el = document.createElement('div');
    el.id = 'sim-status';
    el.style.color = '#fff';
    el.style.fontFamily = 'Bebas Neue, sans-serif';
    el.style.position = 'fixed';
    el.style.top = '50%';
    el.style.left = '50%';
    el.style.transform = 'translate(-50%, -50%)';
    el.style.fontSize = '24px';
    el.style.zIndex = '10000';
    const container = document.getElementById('phaser-container') || document.body;
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

