/**
 * Alpha Banner Module
 * 
 * Provides a shared alpha badge that can be injected into any page.
 * Automatically checks IS_ALPHA status and shows/hides accordingly.
 * 
 * USAGE:
 * 1. Include this script in your HTML:
 *    <script src="/js/shared/alphaBanner.js"></script>
 * 
 * 2. Call AlphaBanner.init() after DOMContentLoaded:
 *    document.addEventListener('DOMContentLoaded', async () => {
 *      await AlphaBanner.init();
 *      // ... rest of your init code
 *    });
 * 
 * The module will:
 * - Inject the alpha badge CSS (if not already present)
 * - Inject the alpha badge HTML element (if not already present)
 * - Show the badge only if IS_ALPHA=true
 * 
 * OPTIONS:
 * - AlphaBanner.init({ showDisclaimer: true }) - Also shows disclaimer banner
 * - AlphaBanner.init({ badgeOnly: true }) - Only shows badge, no disclaimer
 */

const AlphaBanner = {
  _initialized: false,
  
  /**
   * CSS styles for alpha badge (injected once)
   */
  _css: `
    .alpha-badge {
      position: fixed;
      top: 10px;
      right: 10px;
      height: 44px;
      width: auto;
      z-index: 9999;
      display: none;
    }
    .alpha-badge.visible {
      display: block;
    }
  `,
  
  /**
   * Inject CSS styles into page (only once)
   */
  _injectStyles() {
    if (document.getElementById('alpha-banner-styles')) return;
    
    const style = document.createElement('style');
    style.id = 'alpha-banner-styles';
    style.textContent = this._css;
    document.head.appendChild(style);
  },
  
  /**
   * Inject alpha badge HTML into page (only once)
   */
  _injectBadge() {
    if (document.getElementById('alpha-badge')) return;
    
    const badge = document.createElement('img');
    badge.id = 'alpha-badge';
    badge.className = 'alpha-badge';
    badge.src = '/images/alpha_badge_gold.png';
    badge.alt = 'Alpha';
    document.body.insertBefore(badge, document.body.firstChild);
  },
  
  /**
   * Initialize alpha banner - checks API and shows badge if in alpha mode
   * @param {Object} options - Configuration options
   * @param {boolean} options.showDisclaimer - Whether to also show disclaimer (default: false)
   * @returns {Promise<boolean>} True if in alpha mode
   */
  async init(options = {}) {
    // Prevent double initialization
    if (this._initialized) {
      return API_CONFIG.isAlpha();
    }
    this._initialized = true;
    
    // Inject styles and badge
    this._injectStyles();
    this._injectBadge();
    
    // Load app config (uses API_CONFIG which should be loaded first)
    try {
      if (typeof API_CONFIG === 'undefined') {
        console.warn('[AlphaBanner] API_CONFIG not found, cannot check alpha status');
        return false;
      }
      
      const appConfig = await API_CONFIG.loadAppConfig();
      
      if (appConfig.isAlpha) {
        const badge = document.getElementById('alpha-badge');
        if (badge) badge.classList.add('visible');
        console.log('[AlphaBanner] Alpha mode enabled');
        return true;
      }
      
      return false;
    } catch (error) {
      console.error('[AlphaBanner] Failed to load app config:', error);
      return false;
    }
  },
  
  /**
   * Check if currently in alpha mode (synchronous, uses cached value)
   * @returns {boolean}
   */
  isAlpha() {
    return typeof API_CONFIG !== 'undefined' && API_CONFIG.isAlpha();
  }
};

// Make it globally available
window.AlphaBanner = AlphaBanner;
