/**
 * Game Speed Manager
 * Manages animation speed settings and updates speed constants dynamically
 */

const SPEED_PRESETS = {
  NORMAL: 450,
  FAST: 550,
  SUPER_FAST: 1000
};

const STORAGE_KEY = 'gameSpeed';

let currentSpeed = SPEED_PRESETS.NORMAL; // Default to Normal

/**
 * Get the current game speed
 * @returns {number} Speed in pixels per second
 */
export function getGameSpeed() {
  return currentSpeed;
}

/**
 * Set the game speed and update all animation systems
 * @param {number} speed - Speed in pixels per second
 */
export function setGameSpeed(speed) {
  currentSpeed = speed;
  
  // Store preference in localStorage
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(STORAGE_KEY, speed.toString());
  }
  
  // Update animation speed constants dynamically
  // This will be used by getPlayerDuration and getBallDuration functions
  updateAnimationSpeeds(speed);
  
  // Emit event so other systems can react
  if (typeof window !== 'undefined' && window.dispatchEvent) {
    window.dispatchEvent(new CustomEvent('gameSpeedChanged', { detail: { speed } }));
  }
}

/**
 * Load speed preference from localStorage
 * @returns {number} Speed in pixels per second
 */
export function loadSpeedPreference() {
  if (typeof localStorage !== 'undefined') {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      const speed = parseInt(stored, 10);
      if (speed && speed > 0) {
        currentSpeed = speed;
        updateAnimationSpeeds(speed);
        return speed;
      }
    }
  }
  // Default to Normal
  setGameSpeed(SPEED_PRESETS.NORMAL);
  return SPEED_PRESETS.NORMAL;
}

/**
 * Update animation speed constants in the animation modules
 * This dynamically updates the speed used by getPlayerDuration and getBallDuration
 * @param {number} speed - Speed in pixels per second
 */
function updateAnimationSpeeds(speed) {
  // Update the speed in turnAnimation.js module
  // We'll need to export a setter function from turnAnimation.js
  // For now, we'll use a global or module-level variable that can be updated
  
  // Store speed in a way that animation modules can access it
  if (typeof window !== 'undefined') {
    window.__GAME_SPEED = speed;
  }
  
  // Try to update the module if it's already loaded
  // This is a bit of a hack, but necessary since we're using ES modules
  try {
    // The animation modules will check window.__GAME_SPEED or use a getter
    // We'll update turnAnimation.js to use this
  } catch (e) {
    console.warn('Could not update animation speeds:', e);
  }
}

/**
 * Get speed preset name from speed value
 * @param {number} speed - Speed in pixels per second
 * @returns {string} Preset name ('Normal', 'Fast', 'Super Fast') or 'Custom'
 */
export function getSpeedPresetName(speed) {
  if (speed === SPEED_PRESETS.NORMAL) return 'Normal';
  if (speed === SPEED_PRESETS.FAST) return 'Fast';
  if (speed === SPEED_PRESETS.SUPER_FAST) return 'Super Fast';
  return 'Custom';
}

/**
 * Get all speed presets
 * @returns {Object} Speed presets
 */
export function getSpeedPresets() {
  return SPEED_PRESETS;
}

