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
          return { isAlpha: false, alphaDisclaimer: null, version: '1.0' };
        }
        this._appConfig = await response.json();
        console.log('[API_CONFIG] app-config loaded:', this._appConfig); // DEBUG: remove after troubleshooting
        return this._appConfig;
      } catch (error) {
        console.error('[API_CONFIG] Error loading app config:', error.message, error);
        return { isAlpha: false, alphaDisclaimer: null, version: '1.0' };
      } finally {
        this._appConfigLoading = null;
      }
    })();
    
    return this._appConfigLoading;
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
};

// Make it globally available
window.API_CONFIG = API_CONFIG;

(function loadCaptureBootstrap() {
  if (typeof document === 'undefined' || !API_CONFIG.isCaptureEnv()) return;
  const script = document.createElement('script');
  script.src = API_CONFIG.buildStaticPath('/js/shared/captureBootstrap.js');
  script.async = true;
  document.head.appendChild(script);
})();

