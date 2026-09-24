/**
 * One history model for browser Back and in-app Back.
 *
 * Section changes push. In-flow steps and one-way exits replace.
 * In-app Back uses history.back() only when the previous entry is that parent.
 */
(function (root, factory) {
  var api = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (root && root.document) root.GOBNav = api.install(root);
})(typeof window !== 'undefined' ? window : null, function () {
  'use strict';

  var STACK_KEY = 'gob_nav_stack';
  var SCROLL_KEY = 'gob_nav_scroll';
  var MAX_STACK = 40;

  function install(win) {
    var leaveChecks = [];
    var allowLeaveOnce = false;

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

    function currentUrl() {
      return (win.location.pathname || '') + (win.location.search || '') + (win.location.hash || '');
    }

    function parseUrl(url) {
      try { return new URL(url, win.location.origin); } catch (e) { return null; }
    }

    function pathOf(url) {
      var parsed = parseUrl(url);
      return parsed ? parsed.pathname : String(url || '').split('?')[0].split('#')[0];
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

    function sameUrl(a, b) {
      return entry(a).url === entry(b).url;
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
      if (franchiseId && /franchise-command-center\.html$/i.test(win.location.pathname) === false) {
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

    function assign(url) {
      win.location.assign(url);
    }

    function replaceUrl(url) {
      win.location.replace(url);
    }

    function go(url) {
      saveScroll();
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
      var parent = fallbackUrl || returnUrlFromQuery() || defaultFallback();
      var prev = previousEntry();
      if (prev && isParent(prev, parent)) {
        var stack = readStack();
        var here = entry(currentUrl()).url;
        if (stack.length && stack[stack.length - 1].url === here) {
          stack.pop();
          writeStack(stack);
        }
        saveScroll();
        win.history.back();
        return;
      }
      replace(parent);
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
      return /\/franchise-command-center\.html$/i.test(win.location.pathname || '');
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
      if (event && event.persisted) {
        resetBusyButtons();
        if (isFcc()) {
          win.location.reload();
          return;
        }
      }
      truncateToHere();
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
      var params = new URLSearchParams(win.location.search || '');
      var gameId = params.get('game_id');
      var franchiseId = params.get('franchise_id');
      var api = win.API_CONFIG;
      if (!gameId || !franchiseId || !api || typeof api.buildUrl !== 'function') {
        return Promise.resolve(false);
      }
      var headers = typeof api.getAuthHeaders === 'function' ? api.getAuthHeaders() : {};
      var gameUrl = api.buildUrl('/api/game/' + encodeURIComponent(gameId));
      var fccUrl = api.buildUrl('/franchise/command-center/data') + '?franchise_id=' + encodeURIComponent(franchiseId);
      return Promise.all([
        win.fetch(gameUrl, { headers: headers }).then(function (res) { return res.ok ? res.json() : null; }),
        win.fetch(fccUrl, { headers: headers }).then(function (res) { return res.ok ? res.json() : null; }),
      ]).then(function (pair) {
        var game = pair[0];
        var fcc = pair[1];
        if (!game || !fcc || game.is_final !== true) return false;
        var last = fcc.last_game_summary || null;
        var weekMoved = !!(
          last
          && String(last.game_id) === String(gameId)
          && Number(last.week) < Number(fcc.week)
        );
        if (!weekMoved) return false;
        replace('/franchise-command-center.html?franchise_id=' + encodeURIComponent(franchiseId));
        return true;
      }).catch(function () { return false; });
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
    truncateToHere();

    return {
      go: go,
      replace: replace,
      back: back,
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
