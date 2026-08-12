/**
 * Centralized API Configuration
 * 
 * This module provides a single source of truth for API base URLs across all environments.
 * All frontend API calls should use API_CONFIG.getBaseUrl() instead of hardcoded URLs.
 * 
 * Environment Detection:
 * - Production: www.geekedoutbasketball.com
 * - Staging: staging.geekedoutbasketball.com
 * - Local: localhost (any other hostname)
 * 
 * Default Domains (for initial deployment):
 * - Railway default: *.railway.app
 * - Netlify default: *.netlify.app
 * 
 * Custom Domains (after DNS configuration):
 * - Production API: api.geekedoutbasketball.com
 * - Staging API: api-staging.geekedoutbasketball.com
 * 
 * Alpha Mode:
 * - Use API_CONFIG.isAlpha() to check if app is in alpha mode
 * - Use API_CONFIG.loadAppConfig() to fetch and cache app configuration
 */

const API_CONFIG = {
  // Cached app config (loaded once from backend)
  _appConfig: null,
  _appConfigLoading: null,
  /**
   * Get the base URL for API requests based on current environment
   * @returns {string} Base URL for API requests (e.g., "https://api.geekedoutbasketball.com")
   */
  getBaseUrl() {
    // Check for explicit override (useful for testing or manual configuration)
    if (window.API_BASE_URL) {
      return window.API_BASE_URL;
    }
    
    const hostname = window.location.hostname;
    // DEBUG: remove after troubleshooting
    const baseUrl = this._resolveBaseUrl(hostname);
    console.log('[API_CONFIG] hostname=', hostname, 'baseUrl=', baseUrl);
    return baseUrl;
  },

  _resolveBaseUrl(hostname) {
    // Production (custom domain - www redirects to bare domain)
    if (hostname === 'www.geekedoutbasketball.com' || hostname === 'geekedoutbasketball.com') {
      return 'https://api.geekedoutbasketball.com';
    }
    
    // Staging (custom domain)
    if (hostname === 'staging.geekedoutbasketball.com') {
      return 'https://api-staging.geekedoutbasketball.com';
    }
    
    // Production (Railway default domain - for initial deployment before DNS)
    // Check if hostname matches Railway default pattern
    if (hostname.includes('.railway.app') || hostname.includes('.netlify.app')) {
      // For default domains, we need to detect if this is staging or production
      // This is a fallback - ideally we'll use custom domains
      // For now, assume staging if hostname contains 'staging' or 'test', otherwise production
      if (hostname.includes('staging') || hostname.includes('test')) {
        // Staging default domain - Railway staging backend
        return 'https://gob-simplified-staging.up.railway.app';
      } else {
        // Production default domain - Railway production backend
        return 'https://gob-simplified-gob-backend-prod.up.railway.app';
      }
    }
    
    // Local development (default)
    return 'http://localhost:8000';
  },
  
  /**
   * Build a full API URL from an endpoint path
   * @param {string} endpoint - API endpoint path (e.g., "/api/teams" or "api/teams")
   * @returns {string} Full API URL
   */
  buildUrl(endpoint) {
    // Ensure endpoint starts with /
    const normalizedEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
    return `${this.getBaseUrl()}${normalizedEndpoint}`;
  },
  
  /**
   * Get the static asset path prefix based on environment
   * - Local dev: "/static" (backend serves from /static/)
   * - Netlify/Production: "" (files are at root)
   * @returns {string} Path prefix for static assets
   */
  getStaticPath() {
    const hostname = window.location.hostname;
    
    // Local development - backend serves from /static/
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
      return '/static';
    }
    
    // Production/Staging (Netlify, Railway, custom domains) - files at root
    return '';
  },
  
  /**
   * Build a static asset path (images, JS, CSS)
   * @param {string} path - Asset path (e.g., "/images/players/123.png" or "js/utils.js")
   * @returns {string} Full static asset path
   */
  buildStaticPath(path) {
    // Ensure path starts with /
    const normalizedPath = path.startsWith('/') ? path : `/${path}`;
    return `${this.getStaticPath()}${normalizedPath}`;
  },
  
  /**
   * Load app configuration from backend (cached after first call)
   * @returns {Promise<Object>} App config object with isAlpha, alphaDisclaimer, version
   */
  async loadAppConfig() {
    // Return cached config if available
    if (this._appConfig) {
      return this._appConfig;
    }
    
    // If already loading, wait for that request
    if (this._appConfigLoading) {
      return this._appConfigLoading;
    }
    
    // Fetch config from backend
    this._appConfigLoading = (async () => {
      const url = this.buildUrl('/app-config');
      console.log('[API_CONFIG] Fetching app-config from', url); // DEBUG: remove after troubleshooting
      try {
        const response = await fetch(url);
        if (!response.ok) {
          console.error('[API_CONFIG] Failed to load app config:', response.status, response.statusText);
          return { isAlpha: false, alphaDisclaimer: null, version: '1.0', teamBuilderEnabled: true };
        }
        this._appConfig = await response.json();
        console.log('[API_CONFIG] app-config loaded:', this._appConfig); // DEBUG: remove after troubleshooting
        return this._appConfig;
      } catch (error) {
        console.error('[API_CONFIG] Error loading app config:', error.message, error);
        return { isAlpha: false, alphaDisclaimer: null, version: '1.0', teamBuilderEnabled: true };
      } finally {
        this._appConfigLoading = null;
      }
    })();
    
    return this._appConfigLoading;
  },
  
  /**
   * Check if Team Builder authoring is enabled (synchronous — uses cached value).
   * IMPORTANT: Call loadAppConfig() first on page load to populate cache.
   * Defaults to true when config is missing (matches backend default).
   * @returns {boolean}
   */
  isTeamBuilderEnabled() {
    if (this._appConfig && typeof this._appConfig.teamBuilderEnabled === 'boolean') {
      return this._appConfig.teamBuilderEnabled;
    }
    return true;
  },

  /**
   * Check if app is in alpha mode (synchronous - uses cached value)
   * IMPORTANT: Call loadAppConfig() first on page load to populate cache
   * @returns {boolean} True if in alpha mode
   */
  isAlpha() {
    return this._appConfig?.isAlpha ?? false;
  },
  
  /**
   * Get alpha disclaimer text (synchronous - uses cached value)
   * @returns {string|null} Disclaimer text or null if not in alpha
   */
  getAlphaDisclaimer() {
    return this._appConfig?.alphaDisclaimer ?? null;
  },
  
  /**
   * Get app version (synchronous - uses cached value)
   * @returns {string} Version string
   */
  getVersion() {
    return this._appConfig?.version ?? '1.0';
  },

  /**
   * Get headers for authenticated API requests.
   * Include in fetch() for endpoints that require auth (franchise, tournament, game).
   * @returns {Object} Headers object, e.g. { Authorization: 'Bearer ...' } or {}
   */
  getAuthHeaders() {
    const token = typeof localStorage !== 'undefined' ? localStorage.getItem('auth_token') : null;
    return token ? { 'Authorization': `Bearer ${token}` } : {};
  },

  /**
   * Staging-only screen capture tool gate.
   * True for localhost + Netlify/Railway staging hosts; false for production.
   */
  isCaptureEnv() {
    const hostname = window.location.hostname;
    if (hostname === 'localhost' || hostname === '127.0.0.1') return true;
    if (hostname === 'staging.geekedoutbasketball.com') return true;
    if (hostname === 'gob-test.netlify.app') return true;
    if ((hostname.includes('.netlify.app') || hostname.includes('.railway.app'))
      && (hostname.includes('staging') || hostname.includes('test'))) {
      return true;
    }
    return false;
  },

  // ===========================================================================
  // Player image resolution (Cloudflare R2 + Image Transformations)
  // ---------------------------------------------------------------------------
  // Canonical masters live in R2 at: players/master/<uuid>.png, served via the
  // custom domain assets.geekedoutgames.com. Cloudflare Image Transformations
  // resize + convert to AVIF/WebP on the fly. ALL player-image surfaces should
  // resolve through getPlayerImageUrl()/getGenericHeadshotUrl() — do not build
  // image paths inline.
  // ===========================================================================

  // --- Tunable constants ---
  PLAYER_IMAGE_REMOTE_BASE: 'https://assets.geekedoutgames.com', // R2 custom domain
  PLAYER_IMAGE_MASTER_PREFIX: 'players/master',                  // object key prefix
  // Named render sizes (px width). `full` = untransformed master.
  PLAYER_IMAGE_SIZES: { thumb: 128, card: 256, modal: 512, full: null },

  /**
   * Whether player images are served from remote R2/CDN.
   * - Explicit override wins: set window.PLAYER_IMAGE_REMOTE = true|false.
   * - localhost/127.0.0.1 default to LOCAL static (dev never requires Cloudflare).
   * - All other hosts (staging/prod) default to REMOTE.
   * The explicit override is also the single kill-switch for a safe rollback.
   * @returns {boolean}
   */
  usePlayerImageRemote() {
    if (typeof window !== 'undefined' && typeof window.PLAYER_IMAGE_REMOTE === 'boolean') {
      return window.PLAYER_IMAGE_REMOTE;
    }
    const host = (typeof window !== 'undefined' && window.location && window.location.hostname) || '';
    if (host === 'localhost' || host === '127.0.0.1') return false;
    return true;
  },

  /**
   * Build a Cloudflare Image Transformations URL for an R2 object.
   * @private
   */
  _remotePlayerImageUrl(objectPath, size) {
    const width = this.PLAYER_IMAGE_SIZES[size];
    const base = this.PLAYER_IMAGE_REMOTE_BASE;
    if (!width) return `${base}/${objectPath}`; // full master, no transform
    return `${base}/cdn-cgi/image/width=${width},format=auto/${objectPath}`;
  },

  /**
   * Resolve a player headshot URL (remote transformed, or local static fallback).
   * Pair with an onerror handler that falls back to getGenericHeadshotUrl().
   * @param {string} playerId - player UUID (filenames are <uuid>.png)
   * @param {Object} [opts]
   * @param {('thumb'|'card'|'modal'|'full')} [opts.size='card'] - named render size
   * @returns {string}
   */
  getPlayerImageUrl(playerId, opts = {}) {
    const size = opts.size || 'card';
    if (!playerId) return this.getGenericHeadshotUrl(opts);
    if (this.usePlayerImageRemote()) {
      return this._remotePlayerImageUrl(`${this.PLAYER_IMAGE_MASTER_PREFIX}/${playerId}.png`, size);
    }
    return this.buildStaticPath(`/images/players/${playerId}.png`);
  },

  /**
   * Resolve the generic fallback headshot URL.
   * @param {Object} [opts] - { size }
   * @returns {string}
   */
  getGenericHeadshotUrl(opts = {}) {
    const size = opts.size || 'card';
    if (this.usePlayerImageRemote()) {
      return this._remotePlayerImageUrl(`${this.PLAYER_IMAGE_MASTER_PREFIX}/generic_headshot.png`, size);
    }
    return this.buildStaticPath('/images/players/generic_headshot.png');
  },

  // --- Recruit portraits (pre-signing) --------------------------------------
  // An un-signed recruit shows a finished WHITE display master keyed by its
  // image_id (its own portrait for set recruits, a borrowed base-library one for
  // dynamic recruits — the field ships on the recruit record from the API).
  RECRUIT_IMAGE_WHITE_PREFIX: 'recruits/white',

  /**
   * Resolve an un-signed recruit's display portrait (white master) by image_id.
   * Pair with an onerror -> ensureRecruitImage(imageId) -> retry, then generic.
   * @param {string} imageId
   * @param {Object} [opts] - { size }
   * @returns {string}
   */
  getRecruitImageUrl(imageId, opts = {}) {
    const size = opts.size || 'card';
    if (!imageId) return this.getGenericHeadshotUrl(opts);
    if (this.usePlayerImageRemote()) {
      return this._remotePlayerImageUrl(`${this.RECRUIT_IMAGE_WHITE_PREFIX}/${imageId}.png`, size);
    }
    return this.buildStaticPath(`/images/recruits/${imageId}.png`);
  },

  // --- Lazy paint (generate-on-miss) ----------------------------------------
  // Call on an <img> 404 to have the backend paint the master from the recruit's
  // kit, then retry the CDN URL. Resolves to { status: 'painted'|'exists'|... };
  // any non-success just means fall back to the generic headshot.
  ensureRecruitImage(imageId) {
    if (!imageId) return Promise.resolve({ status: 'skip' });
    return fetch(this.buildUrl('/recruit-image/ensure'), {
      method: 'POST',
      headers: Object.assign({ 'Content-Type': 'application/json' }, this.getAuthHeaders()),
      body: JSON.stringify({ image_id: imageId }),
    }).then((r) => r.json()).catch(() => ({ status: 'error' }));
  },

  ensurePlayerImage(franchiseId, playerId) {
    if (!franchiseId || !playerId) return Promise.resolve({ status: 'skip' });
    return fetch(this.buildUrl('/player-image/ensure'), {
      method: 'POST',
      headers: Object.assign({ 'Content-Type': 'application/json' }, this.getAuthHeaders()),
      body: JSON.stringify({ franchise_id: franchiseId, player_id: playerId }),
    }).then((r) => r.json()).catch(() => ({ status: 'error' }));
  },

  // Franchise id for the current page. Every franchise screen carries it as the
  // `franchise_id` query param (source of truth for multi-slot). No localStorage
  // fallback — inventing an id from bare LS cross-contaminates slots
  // (multi_franchises_brief Phase 1 thin Phase 3 warm-up).
  currentFranchiseId() {
    try {
      const q = new URLSearchParams(window.location.search).get('franchise_id');
      return q || null;
    } catch (e) {
      return null;
    }
  },
};

// Make it globally available
window.API_CONFIG = API_CONFIG;

// --- Universal paint-on-miss -------------------------------------------------
// Player/recruit masters are painted lazily (generate-on-miss). Rather than wire
// the ensure->retry dance into every screen that renders a headshot, install ONE
// delegated handler: any <img> that 404s on a canonical master URL is painted and
// retried here, so every current and future render site is covered by default.
//
//   players/master/<player_id>.png   -> ensurePlayerImage(franchise_id, player_id)
//   recruits/white/<image_id>.png    -> ensureRecruitImage(image_id)
//
// Error events don't bubble, so we listen in the CAPTURE phase (3rd arg true).
// On the first miss we take over (stopImmediatePropagation) so the site's own
// onerror->generic fallback doesn't clobber the retry; if the paint fails and the
// retry 404s again, we've restored the site's handler and no longer intercept, so
// its normal fallback (generic / initials / hide) runs exactly as before.
(function installPaintOnMiss() {
  if (typeof document === 'undefined') return;
  const MASTER_RE = /players\/master\/([^/.?]+)\.png/;
  const WHITE_RE = /recruits\/white\/([^/.?]+)\.png/;

  document.addEventListener('error', function (e) {
    const img = e.target;
    if (!img || img.tagName !== 'IMG') return;
    if (img.dataset.gobPaintTried) return;                 // already attempted once
    const src = img.currentSrc || img.getAttribute('src') || '';

    const pm = src.match(MASTER_RE);
    const rw = pm ? null : src.match(WHITE_RE);
    if (!pm && !rw) return;                                 // not a canonical master — leave it alone

    img.dataset.gobPaintTried = '1';
    e.stopImmediatePropagation();                          // suppress the site's onerror until we've retried
    const originalOnerror = img.onerror;                   // preserve the site's fallback for a failed retry

    const retry = function () {
      // Restore the site's own fallback so a still-missing master degrades as it
      // always did, then re-request the (now hopefully painted) master. A cache-
      // buster forces a fresh origin fetch past any cached 404.
      img.onerror = originalOnerror;
      img.src = src + (src.indexOf('?') === -1 ? '?' : '&') + 'gobr=1';
    };

    const ensure = pm
      ? API_CONFIG.ensurePlayerImage(API_CONFIG.currentFranchiseId(), pm[1])
      : API_CONFIG.ensureRecruitImage(rw[1]);
    ensure.then(retry, retry);
  }, true);
})();

