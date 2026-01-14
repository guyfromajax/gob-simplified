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
 */

const API_CONFIG = {
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
    
    // Production (custom domain)
    if (hostname === 'www.geekedoutbasketball.com') {
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
  }
};

// Make it globally available
window.API_CONFIG = API_CONFIG;

// Export for ES6 modules
export { API_CONFIG };

