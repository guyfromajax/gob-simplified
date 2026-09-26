/**
 * Shared table pieces for League browse views (Standings, Leaders, Team Stats,
 * and later T2/T3). The shell calls placeTools after it rebuilds the sub-tab row.
 */
(function (global) {
  'use strict';

  var tools = Object.create(null);

  function esc(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function apiBase(path) {
    if (global.API_CONFIG && typeof global.API_CONFIG.buildUrl === 'function') {
      return global.API_CONFIG.buildUrl(path);
    }
    return path;
  }

  function readKey(key, fallback) {
    try {
      var value = sessionStorage.getItem(key);
      return value == null || value === '' ? fallback : value;
    } catch (err) {
      return fallback;
    }
  }

  function writeKey(key, value) {
    try { sessionStorage.setItem(key, value); } catch (err) { /* ignore */ }
  }

  function logo(name) {
    try {
      if (name && typeof global.getTeamAssetPath === 'function') {
        return global.getTeamAssetPath(name, 'logo_square');
      }
    } catch (err) { /* generated art can fail closed */ }
    return '/images/teams/general/general_logo_square.png';
  }

  function teamLink(href, name, logoName) {
    var src = logo(logoName || name);
    return '<a class="gob-team" data-return href="' + esc(href) + '">'
      + '<img alt="" src="' + esc(src) + '">'
      + '<span>' + esc(name || '') + '</span></a>';
  }

  function nextCell(name, week) {
    if (!name && (week == null || week === '')) return '';
    var img = name ? '<img alt="" src="' + esc(logo(name)) + '">' : '';
    var label = week == null || week === '' ? '' : ('W' + week);
    return '<span class="gob-next">' + img + '<span>' + esc(label) + '</span></span>';
  }

  function diffCell(value, maxAbs) {
    var n = Number(value);
    if (!isFinite(n)) n = 0;
    var scale = maxAbs > 0 ? Math.min(1, Math.abs(n) / maxAbs) : 0;
    var side = n < 0 ? ' neg' : '';
    var text = (n > 0 ? '+' : '') + n;
    return '<span class="gob-diff' + side + '"><i class="' + (n < 0 ? 'neg' : 'pos')
      + '" style="--v:' + scale + '"></i><span>' + esc(text) + '</span></span>';
  }

  function formatPct(value) {
    var n = Number(value);
    if (!isFinite(n)) return '';
    var text = Math.abs(n).toFixed(3);
    if (text.charAt(0) === '0') text = text.slice(1);
    return (n < 0 ? '-' : '') + text;
  }

  function segment(options, current) {
    var html = '<div class="stats-toggle" role="group">';
    options.forEach(function (opt) {
      html += '<button type="button" data-value="' + esc(opt.id) + '"'
        + (opt.id === current ? ' class="on"' : '') + '>' + esc(opt.label) + '</button>';
    });
    html += '</div>';
    return html;
  }

  function searchBox(label) {
    return '<input class="gob-search" type="search" placeholder="' + esc(label) + '" aria-label="' + esc(label) + '">';
  }

  function registerTools(id, render) {
    if (!id) return;
    if (typeof render === 'function') tools[id] = render;
    else delete tools[id];
  }

  function currentTab() {
    try { return new URLSearchParams(global.location.search).get('tab') || ''; }
    catch (err) { return ''; }
  }

  function placeTools(host) {
    var slotHost = host || document.getElementById('gob-subtabs');
    if (!slotHost) return;
    var render = tools[currentTab()];
    var old = slotHost.querySelector('.pg-tools');
    if (typeof render !== 'function') {
      if (old) old.remove();
      return;
    }
    if (old && old.getAttribute('data-owner') === currentTab()) return;
    if (old) old.remove();
    var slot = document.createElement('div');
    slot.className = 'pg-tools';
    slot.setAttribute('data-owner', currentTab());
    slotHost.appendChild(slot);
    render(slot);
  }

  function bindWide(card) {
    if (!card) return function () {};
    function sync() {
      var max = card.scrollWidth - card.clientWidth;
      card.classList.toggle('can-l', card.scrollLeft > 2);
      card.classList.toggle('can-r', max > 2 && card.scrollLeft < max - 2);
    }
    card.addEventListener('scroll', sync, { passive: true });
    sync();
    return sync;
  }

  function sortRows(rows, read, dir) {
    var copy = rows.slice();
    copy.sort(function (a, b) {
      var av = read(a);
      var bv = read(b);
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      if (typeof av === 'string' || typeof bv === 'string') {
        return String(av).localeCompare(String(bv)) * dir;
      }
      if (av === bv) return 0;
      return av < bv ? -dir : dir;
    });
    return copy;
  }

  function paintSkeleton(container) {
    var html = '<div class="gob-view-skel" aria-hidden="true"><div class="gob-view-skel-bar"></div>';
    var i;
    for (i = 0; i < 8; i++) html += '<div class="gob-view-skel-row"></div>';
    html += '</div>';
    container.innerHTML = html;
  }

  function paintError(container, message, onRetry) {
    container.innerHTML = '<div class="gob-view-error" role="alert"><p>' + esc(message) + '</p>'
      + '<button type="button" class="gob-view-retry">Retry</button></div>';
    var button = container.querySelector('.gob-view-retry');
    if (button) button.addEventListener('click', onRetry);
  }

  function backForward() {
    try {
      var nav = performance.getEntriesByType('navigation')[0];
      return !!(nav && nav.type === 'back_forward');
    } catch (err) {
      return false;
    }
  }

  function rosterHref(franchiseId, teamId, teamName, returnTab) {
    return '/team-roster-view.html?mode=franchise&franchise_id=' + encodeURIComponent(franchiseId || '')
      + '&team_id=' + encodeURIComponent(teamId || '')
      + '&team_name=' + encodeURIComponent(teamName || '')
      + '&return_tab=' + encodeURIComponent(returnTab || '');
  }

  function resetScroll() {
    var main = document.querySelector('html.gob-shell .main');
    if (main) main.scrollTop = 0;
  }

  global.GOBTables = {
    esc: esc,
    apiBase: apiBase,
    readKey: readKey,
    writeKey: writeKey,
    logo: logo,
    teamLink: teamLink,
    nextCell: nextCell,
    diffCell: diffCell,
    formatPct: formatPct,
    segment: segment,
    searchBox: searchBox,
    registerTools: registerTools,
    placeTools: placeTools,
    bindWide: bindWide,
    sortRows: sortRows,
    paintSkeleton: paintSkeleton,
    paintError: paintError,
    backForward: backForward,
    rosterHref: rosterHref,
    resetScroll: resetScroll
  };
})(typeof window !== 'undefined' ? window : this);
