/**
 * Shared access-denied handler for 401/403 responses.
 * Use when fetching user-specific data (franchise, tournament).
 * Shows non-blocking message and redirects after 1.5s.
 * 401 -> login; 403 -> mode-select
 */
(function () {
  'use strict';

  const REDIRECT_DELAY_MS = 1500;

  function showMessage(message) {
    if (typeof window.PageLoadOverlay !== 'undefined' && window.PageLoadOverlay.hide) {
      window.PageLoadOverlay.hide();
    }
    var overlay = document.getElementById('cc-loading-overlay');
    if (overlay) {
      overlay.textContent = message;
      overlay.classList.add('cc-loading-overlay--denied');
      overlay.style.display = 'flex';
    } else {
      var div = document.createElement('div');
      div.id = 'cc-loading-overlay';
      div.className = 'cc-loading-overlay cc-loading-overlay--denied';
      div.textContent = message;
      Object.assign(div.style, {
        position: 'fixed',
        top: 0, left: 0, right: 0, bottom: 0,
        background: 'rgba(0,0,0,0.85)',
        color: '#fff',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: '18px',
        zIndex: 99999,
        fontFamily: 'Inter, sans-serif'
      });
      document.body.appendChild(div);
    }
  }

  function handleAccessDenied(response) {
    var is401 = response && response.status === 401;
    var message = is401
      ? 'Please sign in. Redirecting...'
      : 'Access denied. Redirecting...';
    var redirectTo = is401 ? '/login.html' : '/mode-select.html';

    var currentPath = window.location.pathname + window.location.search;
    if (is401 && currentPath && currentPath !== '/login.html') {
      redirectTo += '?redirect=' + encodeURIComponent(currentPath);
    }

    showMessage(message);
    setTimeout(function () {
      window.location.href = redirectTo;
    }, REDIRECT_DELAY_MS);
  }

  /**
   * Check response for 401/403. If access denied, handles it and returns true.
   * @param {Response} response - fetch response
   * @returns {boolean} - true if 401/403 (caller should return), false otherwise
   */
  function checkAccessDenied(response) {
    if (response.status === 401 || response.status === 403) {
      handleAccessDenied(response);
      return true;
    }
    return false;
  }

  function hideLoadingOverlay() {
    var overlay = document.getElementById('cc-loading-overlay');
    if (overlay) overlay.style.display = 'none';
  }

  window.AccessDenied = {
    handleAccessDenied: handleAccessDenied,
    checkAccessDenied: checkAccessDenied,
    hideLoadingOverlay: hideLoadingOverlay
  };
})();
