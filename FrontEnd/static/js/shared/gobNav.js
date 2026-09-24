/**
 * One history model for browser Back and in-app Back.
 *
 * Section changes push. In-flow steps and one-way exits replace.
 * In-app Back uses history.back() only when the previous entry is that parent.
 * A finished flow collapses back onto the Locker Room entry that launched it.
 */
(function (root, factory) {
  var api = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (root && root.document) root.GOBNav = api.install(root);
})(typeof window !== 'undefined' ? window : null, function () {
  'use strict';

  var STACK_KEY = 'gob_nav_stack';
  var SCROLL_KEY = 'gob_nav_scroll';
  var EXIT_KEY = 'gob_nav_exit';
  var FLOW_TAB_KEY = 'gob_nav_flow_tab';
  var MAX_STACK = 40;

  function install(win) {
    var leaveChecks = [];
    var allowLeaveOnce = false;
    var guardInflight = null;

    function storage() {
      try { return win.sessionStorage; } catch (e) { return null; }
    }

    function readJson(key) {
      var store = storage();
      if (!store) return null;
      try { return JSON.parse(store.getItem(key) || 'null'); } catch (e) { return null; }
    }

    function writeJson(key, value) {
      var store = storage();
      if (!store) return;
      try { store.setItem(key, JSON.stringify(value)); } catch (e) {}
    }

    function removeKey(key) {
      var store = storage();
      if (!store) return;
      try { store.removeItem(key); } catch (e) {}
    }

    function readStack() {
      var stack = readJson(STACK_KEY);
      return Array.isArray(stack) ? stack : [];
    }

    function writeStack(stack) {
      writeJson(STACK_KEY, stack.slice(-MAX_STACK));
    }

    function readScrolls() {
      var map = readJson(SCROLL_KEY);
      return map && typeof map === 'object' ? map : {};
    }

    function activeFccTab() {
      if (!win.document || !win.document.querySelector) return '';
      var active = win.document.querySelector('.tab-buttons [data-tab].active');
      return active ? (active.getAttribute('data-tab') || '') : '';
    }

    function currentUrl() {
      var path = win.location.pathname || '';
      var search = win.location.search || '';
      var hash = win.location.hash || '';
      var full = path + search + hash;
      if (!isFccPath(path)) return full;
      var parsed = parseUrl(full);
      if (!parsed || parsed.searchParams.get('tab')) return full;
      var tab = activeFccTab();
      if (!tab) return full;
      parsed.searchParams.set('tab', tab);
      var qs = parsed.searchParams.toString();
      return parsed.pathname + (qs ? '?' + qs : '') + parsed.hash;
    }

    function parseUrl(url) {
      try { return new URL(url, win.location.origin); } catch (e) { return null; }
    }

    function pathOf(url) {
      var parsed = parseUrl(url);
      return parsed ? parsed.pathname : String(url || '').split('?')[0].split('#')[0];
    }

    function isFccPath(url) {
      return /\/franchise-command-center\.html$/i.test(pathOf(url || ''));
    }

    function entry(url) {
      var parsed = parseUrl(url);
      var path = parsed ? parsed.pathname : pathOf(url);
      var full = parsed
        ? parsed.pathname + parsed.search + parsed.hash
        : String(url || '');
      return { url: full, path: path };
    }

    function scrollContainer() {
      if (!win.document || !win.document.querySelector) return null;
      return win.document.querySelector('#franchise-container #tournament-tabs > .tab-content.active')
        || win.document.querySelector('[data-gob-scroll]');
    }

    function saveScroll() {
      var scrolls = readScrolls();
      var box = scrollContainer();
      scrolls[currentUrl()] = {
        windowY: win.scrollY || win.pageYOffset || 0,
        containerTop: box ? box.scrollTop : 0,
      };
      var keys = Object.keys(scrolls);
      if (keys.length > 80) delete scrolls[keys[0]];
      writeJson(SCROLL_KEY, scrolls);
    }

    function noteHere() {
      var stack = readStack();
      var here = entry(currentUrl());
      if (!stack.length || stack[stack.length - 1].url !== here.url) stack.push(here);
      else stack[stack.length - 1] = here;
      writeStack(stack);
    }

    function truncateToHere() {
      var stack = readStack();
      var here = entry(currentUrl()).url;
      for (var i = stack.length - 1; i >= 0; i--) {
        if (stack[i].url === here) {
          writeStack(stack.slice(0, i + 1));
          return;
        }
      }
      stack.push(entry(currentUrl()));
      writeStack(stack);
    }

    function returnUrlFromQuery() {
      var params = new URLSearchParams(win.location.search || '');
      var raw = params.get('return_url');
      if (!raw) return '';
      if (typeof win.getSafeReturnUrl === 'function') return win.getSafeReturnUrl(raw) || '';
      var parsed = parseUrl(raw);
      if (!parsed || parsed.origin !== win.location.origin) return '';
      return parsed.pathname + parsed.search + parsed.hash;
    }

    function defaultFallback() {
      var params = new URLSearchParams(win.location.search || '');
      var franchiseId = params.get('franchise_id');
      if (franchiseId && isFccPath(win.location.pathname) === false) {
        return '/franchise-command-center.html?franchise_id=' + encodeURIComponent(franchiseId);
      }
      return '/mode-select.html';
    }

    function isParent(prev, parentUrl) {
      if (!prev || !parentUrl) return false;
      var parent = entry(parentUrl);
      if (prev.path && parent.path && prev.path === parent.path) return true;
      if (prev.url === parent.url) return true;
      var ret = returnUrlFromQuery();
      if (ret && (prev.url === entry(ret).url || prev.path === entry(ret).path)) return true;
      return false;
    }

    function previousEntry() {
      var stack = readStack();
      var here = entry(currentUrl()).url;
      var idx = stack.length - 1;
      if (idx >= 0 && stack[idx].url === here) idx -= 1;
      return idx >= 0 ? stack[idx] : null;
    }

    function referrerEntry() {
      var ref = win.document && win.document.referrer;
      if (!ref) return null;
      var parsed = parseUrl(ref);
      if (!parsed || parsed.origin !== win.location.origin) return null;
      return entry(parsed.pathname + parsed.search + parsed.hash);
    }

    function mergeReturnTab(url) {
      var params = new URLSearchParams(win.location.search || '');
      var tab = params.get('return_tab');
      if (!tab || !url || !isFccPath(url)) return url;
      var parsed = parseUrl(url);
      if (!parsed || parsed.searchParams.get('tab')) return url;
      parsed.searchParams.set('tab', tab);
      var qs = parsed.searchParams.toString();
      return parsed.pathname + (qs ? '?' + qs : '') + parsed.hash;
    }

    function popHere() {
      var stack = readStack();
      var here = entry(currentUrl()).url;
      if (stack.length && stack[stack.length - 1].url === here) {
        stack.pop();
        writeStack(stack);
      }
    }

    function assign(url) {
      win.location.assign(url);
    }

    function replaceUrl(url) {
      win.location.replace(url);
    }

    function currentFccTab() {
      var params = new URLSearchParams(win.location.search || '');
      return params.get('tab') || activeFccTab() || 'home-tab';
    }

    function readFlowTab() {
      var tab = readJson(FLOW_TAB_KEY);
      return typeof tab === 'string' && tab ? tab : '';
    }

    function rememberFlowTab(tab) {
      if (tab) writeJson(FLOW_TAB_KEY, tab);
    }

    function rememberFlowTabFromReferrer() {
      var ref = referrerEntry();
      if (!ref || !isFccPath(ref.url)) return;
      var parsed = parseUrl(ref.url);
      rememberFlowTab((parsed && parsed.searchParams.get('tab')) || 'home-tab');
    }

    function forceTab(url, tab) {
      var parsed = parseUrl(url);
      if (!parsed) return url;
      if (tab) parsed.searchParams.set('tab', tab);
      var qs = parsed.searchParams.toString();
      return parsed.pathname + (qs ? '?' + qs : '') + parsed.hash;
    }

    function resolveExitTab(hubUrl, options) {
      if (options && options.tab) return options.tab;
      var parsed = parseUrl(hubUrl);
      var urlTab = parsed && parsed.searchParams.get('tab');
      if (urlTab) return urlTab;
      if (isFcc()) return currentFccTab();
      return readFlowTab() || 'home-tab';
    }

    function go(url) {
      saveScroll();
      if (isFcc()) rememberFlowTab(currentFccTab());
      noteHere();
      assign(url);
    }

    function replace(url) {
      saveScroll();
      var stack = readStack();
      var dest = entry(url);
      var here = entry(currentUrl()).url;
      if (stack.length && stack[stack.length - 1].url === here) stack[stack.length - 1] = dest;
      else stack.push(dest);
      writeStack(stack);
      replaceUrl(dest.url);
    }

    function back(fallbackUrl) {
      var parent = mergeReturnTab(fallbackUrl || returnUrlFromQuery() || defaultFallback());
      var prev = previousEntry();
      var ref = referrerEntry();
      if ((prev && isParent(prev, parent)) || (ref && isParent(ref, parent))) {
        popHere();
        saveScroll();
        win.history.back();
        return;
      }
      replace(parent);
    }

    // Collapse a finished one-way flow onto the Locker Room entry that launched
    // it. This does not start a CPU week; the landing page is an ordinary load.
    function exitFlow(hubUrl, options) {
      options = options || {};
      var locker = isFccPath(hubUrl);
      var tab = locker ? resolveExitTab(hubUrl, options) : '';
      var hub = locker ? forceTab(hubUrl, tab) : hubUrl;
      var prev = previousEntry();
      if (prev && prev.path === entry(hub).path) {
        if (locker) writeJson(EXIT_KEY, { tab: tab, fresh: true });
        popHere();
        win.history.back();
        return;
      }
      if (entry(hub).url === entry(currentUrl()).url) {
        win.location.reload();
        return;
      }
      replace(hub);
    }

    function applyExitTab(tab) {
      if (!isFcc() || !tab) return;
      var parsed = parseUrl(win.location.pathname + (win.location.search || '') + (win.location.hash || ''));
      if (!parsed || parsed.searchParams.get('tab') === tab) return;
      parsed.searchParams.set('tab', tab);
      var qs = parsed.searchParams.toString();
      var next = parsed.pathname + (qs ? '?' + qs : '') + parsed.hash;
      if (win.history && win.history.replaceState) {
        win.history.replaceState(win.history.state, '', next);
      }
      syncCurrent();
    }

    function consumeExitLanding(event) {
      var landing = readJson(EXIT_KEY);
      if (!landing || !landing.fresh || !isFcc()) return false;
      applyExitTab(landing.tab || 'home-tab');
      if (event && event.persisted) {
        win.location.reload();
        return true;
      }
      removeKey(EXIT_KEY);
      return false;
    }

    function restoreScroll() {
      var saved = readScrolls()[currentUrl()];
      if (!saved) return;
      if (typeof win.scrollTo === 'function') win.scrollTo(0, saved.windowY || 0);
      var box = scrollContainer();
      if (box) box.scrollTop = saved.containerTop || 0;
    }

    function syncCurrent() {
      var stack = readStack();
      var here = entry(currentUrl());
      if (!stack.length) stack.push(here);
      else if (stack[stack.length - 1].path === here.path) stack[stack.length - 1] = here;
      else stack.push(here);
      writeStack(stack);
    }

    function stripParam(name) {
      var parsed = parseUrl(currentUrl());
      if (!parsed || !parsed.searchParams.has(name)) return false;
      parsed.searchParams.delete(name);
      var next = parsed.pathname + (parsed.searchParams.toString() ? '?' + parsed.searchParams.toString() : '') + parsed.hash;
      if (win.FranchiseContext && typeof win.FranchiseContext.commitParams === 'function') {
        win.FranchiseContext.commitParams(parsed.searchParams);
      } else if (win.history && win.history.replaceState) {
        win.history.replaceState(win.history.state, '', next);
      }
      syncCurrent();
      return true;
    }

    function allowNextLeave() {
      allowLeaveOnce = true;
    }

    function warnOnLeave(fn) {
      if (typeof fn === 'function') leaveChecks.push(fn);
    }

    function resetBusyButtons() {
      if (!win.document || !win.document.querySelectorAll) return;
      win.document.querySelectorAll('button, input[type="submit"]').forEach(function (btn) {
        var text = (btn.textContent || '').replace(/\s+/g, ' ').trim();
        if (/^(loading\.\.\.|starting\.\.\.|simulating.*|running…|running\.\.\.|submitting\.\.\.)$/i.test(text)) {
          btn.disabled = false;
        }
        btn.classList.remove('disabled-busy');
      });
    }

    function isFcc() {
      return isFccPath(win.location.pathname || '');
    }

    function applyReturnUrl(link) {
      var href = link.getAttribute('href');
      if (!href || href.charAt(0) === '#') return;
      var parsed = parseUrl(href);
      if (!parsed || parsed.origin !== win.location.origin) return;
      parsed.searchParams.set('return_url', currentUrl());
      link.setAttribute('href', parsed.pathname + parsed.search + parsed.hash);
    }

    function onClick(event) {
      var target = event.target;
      if (!target || !target.closest) return;
      var link = target.closest('a[href]');
      if (!link) return;
      if (link.hasAttribute('data-return')) applyReturnUrl(link);
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button) return;
      if (link.hasAttribute('data-gob-up')) {
        event.preventDefault();
        back(link.getAttribute('data-gob-up') || link.getAttribute('href'));
        return;
      }
      if (link.hasAttribute('data-gob-replace')) {
        event.preventDefault();
        replace(link.getAttribute('href'));
        return;
      }
      var href = link.getAttribute('href') || '';
      if (!href || href.charAt(0) === '#') return;
      var parsed = parseUrl(href);
      if (!parsed || parsed.origin !== win.location.origin) return;
      if (link.target && link.target !== '_self') return;
      saveScroll();
      noteHere();
    }

    function onPopState() {
      truncateToHere();
    }

    function onPageShow(event) {
      if (consumeExitLanding(event)) return;
      if (event && event.persisted) {
        resetBusyButtons();
        if (isFcc()) {
          win.location.reload();
          return;
        }
        truncateToHere();
        return;
      }
      noteHere();
    }

    function onBeforeUnload(event) {
      if (allowLeaveOnce) {
        allowLeaveOnce = false;
        return;
      }
      for (var i = 0; i < leaveChecks.length; i++) {
        try {
          if (leaveChecks[i]()) {
            event.preventDefault();
            event.returnValue = '';
            return;
          }
        } catch (err) {}
      }
    }

    function guardClosedFranchiseGame() {
      if (guardInflight) return guardInflight;
      var params = new URLSearchParams(win.location.search || '');
      var gameId = params.get('game_id');
      var franchiseId = params.get('franchise_id');
      var api = win.API_CONFIG;
      if (!gameId || !franchiseId || !api || typeof api.buildUrl !== 'function') {
        return Promise.resolve(false);
      }
      var headers = typeof api.getAuthHeaders === 'function' ? api.getAuthHeaders() : {};
      var resumeUrl = api.buildUrl('/api/game/' + encodeURIComponent(gameId) + '/resume-state');
      guardInflight = win.fetch(resumeUrl, { headers: headers }).then(function (res) {
        return res.ok ? res.json() : null;
      }).then(function (resume) {
        if (!resume || resume.status !== 'final') return false;
        var fccUrl = api.buildUrl('/franchise/command-center/data') + '?franchise_id=' + encodeURIComponent(franchiseId);
        return win.fetch(fccUrl, { headers: headers }).then(function (res) {
          return res.ok ? res.json() : null;
        }).then(function (fcc) {
          if (!fcc) return false;
          var last = fcc.last_game_summary || null;
          var weekMoved = !!(
            last
            && String(last.game_id) === String(gameId)
            && Number(last.week) < Number(fcc.week)
          );
          if (!weekMoved) return false;
          exitFlow('/franchise-command-center.html?franchise_id=' + encodeURIComponent(franchiseId), { tab: 'home-tab' });
          return true;
        });
      }).catch(function () { return false; }).finally(function () {
        guardInflight = null;
      });
      return guardInflight;
    }

    if (win.history) win.history.scrollRestoration = 'manual';
    if (win.document && win.document.addEventListener) {
      win.document.addEventListener('click', onClick, true);
    }
    if (win.addEventListener) {
      win.addEventListener('popstate', onPopState);
      win.addEventListener('pageshow', onPageShow);
      win.addEventListener('beforeunload', onBeforeUnload);
    }
    if (!isFcc()) rememberFlowTabFromReferrer();
    if (!consumeExitLanding(null)) noteHere();

    return {
      go: go,
      replace: replace,
      back: back,
      exitFlow: exitFlow,
      restoreScroll: restoreScroll,
      syncCurrent: syncCurrent,
      stripParam: stripParam,
      allowNextLeave: allowNextLeave,
      warnOnLeave: warnOnLeave,
      resetBusyButtons: resetBusyButtons,
      guardClosedFranchiseGame: guardClosedFranchiseGame,
      saveScroll: saveScroll,
    };
  }

  return { install: install };
});
