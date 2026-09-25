function franchiseCtx() {
  return typeof window !== 'undefined' ? window.FranchiseContext : null;
}
function liveParams() {
  return franchiseCtx().toSearchParams();
}
function emptyParams() {
  return franchiseCtx().createParams();
}
function currentSearch() {
  const s = liveParams().toString();
  return s ? '?' + s : '';
}
function cloneParams(params) {
  const out = emptyParams();
  if (params && typeof params.forEach === 'function') {
    params.forEach((value, key) => out.set(key, value));
  }
  return out;
}

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

  var urlParams = liveParams();
  var activeTab = urlParams.get('tab') || defaultTab;

  function setActive(tabName) {
    tabButtons.forEach(function (b) {
      b.classList.toggle('active', b.dataset.tab === tabName);
    });
    tabContents.forEach(function (c) {
      c.classList.toggle('active', c.id === tabName);
    });
    try {
      window.dispatchEvent(new CustomEvent('gob-tab-shown', { detail: { tab: tabName } }));
    } catch (err) { /* ignore */ }
  }

  function show(tabName, historyMode) {
    var known = Array.prototype.some.call(tabButtons, function (b) {
      return b.dataset.tab === tabName;
    });
    if (!known) tabName = defaultTab;
    if (window.GOB_BUILD_PROFILE === 'desktop' && window.FranchiseContext && typeof window.FranchiseContext.set === 'function') {
      window.FranchiseContext.set('tab', tabName);
    }
    if (historyMode === 'push' && window.GOBNav && typeof window.GOBNav.pushSection === 'function') {
      var bag = liveParams();
      bag.set('tab', tabName);
      var qs = bag.toString();
      var next = window.location.pathname + (qs ? '?' + qs : '') + window.location.hash;
      window.GOBNav.pushSection(next);
    } else {
      updateUrl(tabName);
    }
    setActive(tabName);
    if (historyMode === 'push') {
      var main = document.querySelector('html.gob-shell .main');
      if (main) main.scrollTop = 0;
    }
    onTabShow(tabName);
  }

  function updateUrl(tabName) {
    var bag = liveParams();
    bag.set('tab', tabName);
    var qs = bag.toString();
    // Tabs are sub-navigation. replaceState keeps FCC as one history entry
    // so a later section rail can reuse the same tab switch.
    var next = window.location.pathname + (qs ? '?' + qs : '') + window.location.hash;
    window.history.replaceState(window.history.state, '', next);
    if (window.GOBNav && typeof window.GOBNav.syncCurrent === 'function') {
      window.GOBNav.syncCurrent();
    }
  }

  function showTabFromUrl() {
    var bag = liveParams();
    var tabName = bag.get('tab') || defaultTab;
    var known = Array.prototype.some.call(tabButtons, function (b) {
      return b.dataset.tab === tabName;
    });
    if (!known) tabName = defaultTab;
    setActive(tabName);
    onTabShow(tabName);
    if (window.GOBNav && typeof window.GOBNav.restoreScroll === 'function') {
      window.GOBNav.restoreScroll();
    }
  }

  window.addEventListener('popstate', function () {
    showTabFromUrl();
  });

  var hasMatchingTab = Array.prototype.some.call(tabButtons, function (b) {
    return b.dataset.tab === activeTab;
  });
  if (!hasMatchingTab) activeTab = defaultTab;

  // The visible tab has to be in the URL before a drill-down click captures
  // return_url. Otherwise in-app Back replaces onto Coach's Office.
  updateUrl(activeTab);
  setActive(activeTab);
  onTabShow(activeTab);

  function playSound(filename) {
    import('/js/shared/uiSfx.js').then(function (m) { m.playSfx(filename, 0.7); }).catch(function () {});
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
      show(tabName, 'replace');
    });
  });

  if (window.CommandCenterTabs) window.CommandCenterTabs.show = show;
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
