/**
 * Shared access-denied handler for 401/403 responses.
 * Use when fetching user-specific data (franchise, tournament).
 * Shows alert and redirects to mode-select immediately.
 */
(function () {
  'use strict';

  function handleAccessDenied() {
    alert("You don't have access to this resource.");
    window.location.href = '/mode-select.html';
  }

  /**
   * Check response for 401/403. If access denied, handles it and returns false.
   * @param {Response} response - fetch response
   * @returns {boolean} - false if 401/403 (caller should return), true otherwise
   */
  function checkAccessDenied(response) {
    if (response.status === 401 || response.status === 403) {
      handleAccessDenied();
      return true;
    }
    return false;
  }

  window.AccessDenied = {
    handleAccessDenied: handleAccessDenied,
    checkAccessDenied: checkAccessDenied
  };
})();
