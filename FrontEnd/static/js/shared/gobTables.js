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
    if (!name) return '';
    try {
      if (typeof global.getTeamAssetPath === 'function') {
        return global.getTeamAssetPath(name, 'logo_square') || '';
      }
    } catch (err) { /* generated art can fail closed */ }
    return '/images/teams/general/general_logo_square.png';
  }

  function safeColor(color) {
    var text = String(color || '').trim();
    if (/^#[0-9a-fA-F]{3,8}$/.test(text)) return text;
    return '#27408E';
  }

  function letterOf(name) {
    var text = String(name || '').trim();
    return text ? text.charAt(0).toUpperCase() : '';
  }

  function monogram(name, color) {
    return '<span class="gob-mark" style="background:' + esc(safeColor(color)) + '">'
      + esc(letterOf(name)) + '</span>';
  }

  function markHtml(name, color) {
    var src = logo(name);
    if (!src) return monogram(name, color);
    return '<img alt="" src="' + esc(src) + '" data-letter="' + esc(letterOf(name))
      + '" data-color="' + esc(safeColor(color))
      + '" onerror="var s=document.createElement(\'span\');s.className=\'gob-mark\';s.style.background=this.getAttribute(\'data-color\')||\'\';s.textContent=this.getAttribute(\'data-letter\')||\'\';this.replaceWith(s);">';
  }

  function teamLink(href, name, logoName, color) {
    return '<a class="gob-team" data-return href="' + esc(href) + '">'
      + markHtml(logoName || name, color)
      + '<span>' + esc(name || '') + '</span></a>';
  }

  function nextCell(name, week, color) {
    if (!name && (week == null || week === '')) return '';
    var mark = name ? markHtml(name, color) : '';
    var label = week == null || week === '' ? '' : ('W' + week);
    return '<span class="gob-next">' + mark + '<span>' + esc(label) + '</span></span>';
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

  function formatOneDecimal(value) {
    var n = Number(value);
    if (!isFinite(n)) return '';
    return n.toFixed(1);
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
    var owner = '';
    try {
      var params = new URLSearchParams(global.location.search);
      owner = params.get('team_id') || params.get('user_team_id') || '';
    } catch (err) { owner = ''; }
    if (!owner && global.GOBViews && typeof global.GOBViews.userTeamId === 'function') {
      owner = global.GOBViews.userTeamId() || '';
    }
    var viewed = teamId || '';
    return '/team-roster-view.html?mode=franchise&franchise_id=' + encodeURIComponent(franchiseId || '')
      + '&team_id=' + encodeURIComponent(owner || viewed)
      + '&roster_team_id=' + encodeURIComponent(viewed)
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
    markHtml: markHtml,
    teamLink: teamLink,
    nextCell: nextCell,
    diffCell: diffCell,
    formatPct: formatPct,
    formatOneDecimal: formatOneDecimal,
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
