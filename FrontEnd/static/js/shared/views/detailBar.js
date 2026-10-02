/**
 * Shared chrome for the player and team drill-ins.
 * The page formats. It does not derive a rate, rank, place, streak, or bucket.
 */

var PAGES = {
  'roster-view': 'Roster',
  'player-stats-tab': 'Player Stats',
  'player-stats-view': 'Player Stats',
  'team-attributes-view': 'Team Attributes',
  'schedule-tab': 'Schedule',
  'standings-view': 'Standings',
  'standings-tab': 'Standings',
  'leaders-view': 'Leaders',
  'rankings-view': 'Rankings',
  'team-stats-view': 'Team Stats',
  'home-tab': 'Office',
  'coaches-tab': 'Scouting Report'
};

var CHEV_L = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14.5 5.5L8 12l6.5 6.5"/></svg>';
var CHEV_R = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9.5 5.5L16 12l-6.5 6.5"/></svg>';

export function query() {
  try { return new URLSearchParams(window.location.search); }
  catch (err) { return new URLSearchParams(); }
}

export function sectionLabel(origin) {
  if (origin === 'team') return 'Team';
  if (origin === 'office') return 'Office';
  if (origin === 'prep') return 'Prep';
  return 'League';
}

export function pageLabel() {
  var q = query();
  if (q.get('up')) return q.get('up');
  var named = PAGES[q.get('return_tab') || ''];
  if (named) return named;
  var origin = q.get('origin') || '';
  if (origin === 'team') return 'Roster';
  if (origin === 'office') return 'Office';
  if (origin === 'prep') return 'Scouting Report';
  return 'Standings';
}

export function oneDecimal(value) {
  if (value == null || value === '') return '—';
  var tables = window.GOBTables;
  if (!tables || typeof tables.formatOneDecimal !== 'function') return '—';
  var text = tables.formatOneDecimal(value);
  return text === '' ? '—' : text;
}

export function readPager(currentId) {
  var kind = query().get('pager') || '';
  var key = kind === 'roster' ? 'gob-view-roster-order'
    : kind === 'leaders' ? 'gob-view-leaders-order'
    : kind === 'player-stats' ? 'gob-view-player-stats-order'
    : kind === 'standings' ? 'gob-view-standings-order'
    : '';
  if (!key) return null;
  var raw = null;
  try { raw = JSON.parse(sessionStorage.getItem(key) || 'null'); }
  catch (err) { return null; }
  var ids = [];
  var label = '';
  if (kind === 'standings') {
    if (!raw || !Array.isArray(raw.ids)) return null;
    ids = raw.ids.map(String);
    label = String(raw.label || '');
  } else if (Array.isArray(raw)) {
    ids = raw.map(String);
  } else {
    return null;
  }
  var index = ids.indexOf(String(currentId || ''));
  if (index < 0 || !ids.length) return null;
  return { ids: ids, index: index, label: label, kind: kind };
}

export function fallbackUrl() {
  var q = query();
  var tab = q.get('return_tab') || (q.get('origin') === 'league' ? 'standings-view' : 'roster-view');
  if (tab === 'player-view' || tab === 'team-view') tab = 'roster-view';
  q.set('tab', tab);
  ['player_id', 'view_team_id', 'pager', 'up', 'return_url', 'origin', 'return_tab', 'roster_team_id'].forEach(function (key) {
    q.delete(key);
  });
  var text = q.toString();
  return window.location.pathname + (text ? '?' + text : '');
}

export function withParams(changes) {
  var q = query();
  Object.keys(changes || {}).forEach(function (key) {
    var value = changes[key];
    if (value == null || value === '') q.delete(key);
    else q.set(key, String(value));
  });
  var text = q.toString();
  return window.location.pathname + (text ? '?' + text : '');
}

export function barHtml(tables, name, pager) {
  var q = query();
  var origin = q.get('origin') || '';
  var section = sectionLabel(origin);
  var page = pageLabel();
  var html = '<div class="gob-dt-bar"><a class="gob-dt-up" id="back-button" href="'
    + tables.esc(fallbackUrl()) + '">← ' + tables.esc(page) + '</a>'
    + '<span class="gob-dt-crumb"><span>' + tables.esc(section) + '</span><i>/</i><span>'
    + tables.esc(page) + '</span>'
    // No name yet (the skeleton is up): no trailing separator waiting for one.
    + (name ? '<i>/</i><b>' + tables.esc(name) + '</b>' : '') + '</span>';
  if (pager) {
    var prev = pager.index > 0 ? pager.ids[pager.index - 1] : '';
    var next = pager.index < pager.ids.length - 1 ? pager.ids[pager.index + 1] : '';
    var count = (pager.index + 1) + ' of ' + pager.ids.length;
    if (pager.label) count += ' · ' + pager.label;
    html += '<div class="gob-pager"><button type="button" aria-label="Previous"'
      + (prev ? ' data-id="' + tables.esc(prev) + '"' : ' disabled') + '>' + CHEV_L + '</button><span>'
      + tables.esc(count) + '</span><button type="button" aria-label="Next"'
      + (next ? ' data-id="' + tables.esc(next) + '"' : ' disabled') + '>' + CHEV_R + '</button></div>';
  }
  return html + '</div>';
}

export function bindUp(root) {
  var link = root.querySelector('.gob-dt-up');
  if (!link) return;
  link.addEventListener('click', function (event) {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    var ret = '';
    try { ret = query().get('return_url') || ''; } catch (err) { ret = ''; }
    var dest = ret || link.getAttribute('href') || fallbackUrl();
    if (window.GOBNav && typeof window.GOBNav.back === 'function') window.GOBNav.back(dest);
    else window.history.back();
  });
}

export function bindPager(root, onPage) {
  root.querySelectorAll('.gob-pager button').forEach(function (button) {
    button.addEventListener('click', function () {
      if (button.disabled) return;
      var id = button.getAttribute('data-id');
      if (id && typeof onPage === 'function') onPage(id);
    });
  });
}

// True when the caller should drop this load: either the URL was just stamped
// (the re-show loads again), or the user has already left `tab` and the entry
// they are on now belongs to another view.
export function stampOrigin(isUser, tab) {
  var q = query();
  if (q.get('tab') !== tab) return true;
  if (q.get('origin')) return false;
  var url = withParams({ origin: isUser ? 'team' : 'league', tab: tab });
  if (window.history && window.history.replaceState) {
    window.history.replaceState(window.history.state, '', url);
  }
  if (window.GOBNav && typeof window.GOBNav.syncCurrent === 'function') window.GOBNav.syncCurrent();
  if (window.CommandCenterTabs && typeof window.CommandCenterTabs.show === 'function') {
    window.CommandCenterTabs.show(tab);
  }
  return true;
}
