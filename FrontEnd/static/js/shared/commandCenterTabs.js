/**
 * Shared tab management for Franchise and Tournament command centers (Phase 4.4).
 * Expects DOM: .tab-buttons elements with data-tab, and .tab-content elements with id matching data-tab.
 *
 * @param {Object} options
 * @param {string} options.defaultTab - Tab id to show when URL has no tab param (e.g. 'standings-tab' or 'bracket-tab').
 * @param {function(string)=} options.onTabShow - Optional callback(tabName) when a tab is shown (for load/render logic).
 */
function initCommandCenterTabs(options) {
  var defaultTab = options.defaultTab || 'standings-tab';
  var onTabShow = options.onTabShow || function () {};

  var tabButtons = document.querySelectorAll('.tab-buttons [data-tab], .tab-buttons [data-route]');
  var tabContents = document.querySelectorAll('.tab-content');
  if (!tabButtons.length || !tabContents.length) return;

  var urlParams = new URLSearchParams(window.location.search);
  var activeTab = urlParams.get('tab') || defaultTab;

  function setActive(tabName) {
    tabButtons.forEach(function (b) {
      b.classList.toggle('active', b.dataset.tab === tabName);
    });
    tabContents.forEach(function (c) {
      c.classList.toggle('active', c.id === tabName);
    });
  }

  function updateUrl(tabName) {
    var newUrl = new URL(window.location);
    newUrl.searchParams.set('tab', tabName);
    window.history.pushState({}, '', newUrl);
  }

  var hasMatchingTab = Array.prototype.some.call(tabButtons, function (b) {
    return b.dataset.tab === activeTab;
  });
  if (!hasMatchingTab) activeTab = defaultTab;

  setActive(activeTab);
  onTabShow(activeTab);

  function playSound(filename) {
    try {
      var a = new Audio('/sounds/' + encodeURIComponent(filename));
      a.volume = 0.7;
      a.play().catch(function () {});
    } catch (e) {}
  }

  tabButtons.forEach(function (btn) {
    btn.addEventListener('click', function () {
      var route = btn.dataset.route;
      if (route) {
        playSound('click-tiny.wav');
        window.location.href = route;
        return;
      }
      var tabName = btn.dataset.tab;
      if (!tabName) return;
      playSound('click-tiny.wav');
      setActive(tabName);
      updateUrl(tabName);
      onTabShow(tabName);
    });
  });
}

(function (global) {
  'use strict';
  var api = { initCommandCenterTabs: initCommandCenterTabs };
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  } else {
    global.CommandCenterTabs = api;
  }
})(typeof window !== 'undefined' ? window : this);
