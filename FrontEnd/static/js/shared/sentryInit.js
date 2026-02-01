/**
 * Sentry Frontend Error Tracking
 * Fetches app-config for sentryDsn, then loads and initializes Sentry browser SDK if present.
 * Runs asynchronously and does not block page load.
 */
(function () {
  'use strict';

  function getApiBaseUrl() {
    if (window.API_BASE_URL) return window.API_BASE_URL;
    var hostname = window.location.hostname;
    if (hostname === 'www.geekedoutbasketball.com' || hostname === 'geekedoutbasketball.com') return 'https://api.geekedoutbasketball.com';
    if (hostname === 'staging.geekedoutbasketball.com') return 'https://api-staging.geekedoutbasketball.com';
    if (hostname.includes('.railway.app') || hostname.includes('.netlify.app')) {
      return hostname.includes('staging') || hostname.includes('test')
        ? 'https://gob-simplified-staging.up.railway.app'
        : 'https://gob-simplified-gob-backend-prod.up.railway.app';
    }
    return 'http://localhost:8000';
  }

  function setUserContext() {
    try {
      var authUser = typeof localStorage !== 'undefined' && localStorage.getItem('auth_user');
      if (authUser && window.Sentry) {
        var user = JSON.parse(authUser);
        window.Sentry.setUser({ id: user.user_id || user.email, email: user.email });
      }
    } catch (e) {}
  }

  function initSentry(dsn) {
    var script = document.createElement('script');
    script.src = 'https://browser.sentry-cdn.com/8.34.0/bundle.min.js';
    script.crossOrigin = 'anonymous';
    script.async = true;
    script.onload = function () {
      if (window.Sentry && dsn) {
        window.Sentry.init({
          dsn: dsn,
          tracesSampleRate: 0.1,
        });
        setUserContext();
      }
    };
    document.head.appendChild(script);
  }

  fetch(getApiBaseUrl() + '/app-config')
    .then(function (r) { return r.json(); })
    .then(function (config) {
      if (config && config.sentryDsn) initSentry(config.sentryDsn);
    })
    .catch(function () {});
})();
