/**
 * Player drill-in. Formats GET /franchise/player-detail.
 * Rates, letters, and attribute digits arrive on the payload.
 */

import { barHtml, bindPager, bindUp, oneDecimal, query, readPager, stampOrigin, withParams } from './detailBar.js';

var RATE = [
  ['pts_per_game', 'PTS'],
  ['reb_per_game', 'REB'],
  ['ast_per_game', 'AST'],
  ['fg_pct', 'FG%'],
  ['tp_pct', '3PT%'],
  ['ft_pct', 'FT%'],
  ['def_pct', 'DEF%']
];

var LINE = [
  ['gp', 'GP'],
  ['min_per_game', 'MIN'],
  ['pts_per_game', 'PTS'],
  ['reb_per_game', 'REB'],
  ['ast_per_game', 'AST'],
  ['stl_per_game', 'STL'],
  ['blk_per_game', 'BLK'],
  ['fg_pct', 'FG%'],
  ['tp_pct', '3PT%'],
  ['ft_pct', 'FT%'],
  ['def_pct', 'DEF%']
];

function initials(name) {
  var parts = String(name || '').trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return '';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0].charAt(0) + parts[parts.length - 1].charAt(0)).toUpperCase();
}

function heightText(value) {
  var n = Number(value);
  if (!isFinite(n) || n <= 0) return '';
  var total = Math.round(n);
  return Math.floor(total / 12) + "'" + (total % 12) + '"';
}

function portraitHtml(tables, player) {
  var letters = initials(player && player.name);
  var pid = player && player.player_id;
  var url = '';
  if (pid && window.API_CONFIG && typeof window.API_CONFIG.getPlayerImageUrl === 'function') {
    url = window.API_CONFIG.getPlayerImageUrl(pid, { size: 'card' });
  }
  if (!url) return tables.esc(letters);
  return '<img alt="" src="' + tables.esc(url) + '" data-letters="' + tables.esc(letters)
    + '" onerror="var box=this.parentNode;if(box){box.textContent=this.getAttribute(\'data-letters\')||\'\';}">';
}

function rtHtml(tables, current, potential) {
  if (current == null || current === '' || typeof window.formatRtDisplay !== 'function') return '';
  var bucket = typeof window.getRtBucketClass === 'function' ? window.getRtBucketClass : function () { return ''; };
  var html = '<b class="' + bucket(current) + '">' + tables.esc(window.formatRtDisplay(current)) + '</b>';
  if (potential != null && potential !== '') {
    html += '<i>→</i><b class="pot ' + bucket(potential) + '">' + tables.esc(window.formatRtDisplay(potential)) + '</b>';
  }
  return html;
}

function changesHtml(tables, weeks) {
  var rows = [];
  (weeks || []).forEach(function (week) {
    (week.changes || []).forEach(function (change) {
      if (change == null || change.from == null || change.to == null) return;
      if (Object.prototype.hasOwnProperty.call(change, 'delta') && change.from == null) return;
      rows.push({
        week: week.week,
        attr: change.attr,
        from: change.from,
        to: change.to
      });
    });
  });
  if (!rows.length) return '<p class="gob-quiet">No attribute changes yet this season</p>';
  var html = '<div class="gob-chg-list">';
  rows.forEach(function (row) {
    var up = Number(row.to) > Number(row.from);
    var down = Number(row.to) < Number(row.from);
    var dir = up ? ' is-up' : (down ? ' is-down' : '');
    html += '<div class="gob-chg"><span>' + tables.esc(row.attr || '') + '</span>'
      + '<b class="' + dir.trim() + '">' + tables.esc(row.from) + ' <i>→</i> ' + tables.esc(row.to) + '</b>'
      + (row.week == null ? '' : '<em>Wk ' + tables.esc(row.week) + '</em>')
      + '</div>';
  });
  return html + '</div>';
}

function focusHtml(tables, development) {
  var dev = development || {};
  var label = dev.focus_label || 'Standard';
  var codes = Array.isArray(dev.emphasises) ? dev.emphasises.filter(Boolean) : [];
  var line = codes.length ? 'Emphasises ' + codes.join(' · ') : '';
  if (!dev.editable) {
    return '<p class="gob-focus-read"><b>' + tables.esc(label) + '</b>'
      + (line ? '<span>' + tables.esc(line) + '</span>' : '') + '</p>';
  }
  var api = window.GOBDevelopmentFocus;
  var focuses = (api && api.FOCUSES) || [];
  var html = '<div class="gob-focus-edit"><div class="gob-focus stats-toggle" role="radiogroup" aria-label="Development focus">';
  focuses.forEach(function (item) {
    var id = item.value || item.id || item;
    var text = item.label || id;
    html += '<button type="button" data-value="' + tables.esc(id) + '"'
      + (id === dev.focus ? ' class="on"' : '') + '>' + tables.esc(text) + '</button>';
  });
  html += '</div>';
  if (line) html += '<p class="gob-focus-note">' + tables.esc(line) + '</p>';
  html += '<button type="button" class="gob-save" disabled>Save</button></div>';
  return html;
}

export function mount(container, ctx) {
  var tables = window.GOBTables;
  var franchiseId = (ctx && ctx.franchiseId) || '';
  var player = null;
  var signature = '';
  var loaded = false;
  var requestId = 0;

  function playerId() {
    return query().get('player_id') || '';
  }

  function detailUrl() {
    return tables.apiBase('/franchise/player-detail')
      + '?franchise_id=' + encodeURIComponent(franchiseId)
      + '&player_id=' + encodeURIComponent(playerId());
  }

  function showSkeleton() {
    container.innerHTML = barHtml(tables, '', null)
      + '<div class="gob-view-skel" aria-hidden="true"><div class="gob-view-skel-bar"></div>'
      + '<div class="gob-view-skel-row"></div><div class="gob-view-skel-row"></div></div>';
    bindUp(container);
  }

  function showError() {
    container.innerHTML = barHtml(tables, '', null)
      + '<div class="gob-view-error" role="alert"><p>This player could not be opened.</p>'
      + '<button type="button" class="gob-view-retry">Retry</button></div>';
    bindUp(container);
    var button = container.querySelector('.gob-view-retry');
    if (button) button.addEventListener('click', load);
  }

  function render() {
    var body = player || {};
    var season = body.season || {};
    var career = body.career || {};
    var pager = readPager(body.player_id);
    var color = body.team_primary_color || '';
    var bits = [body.team_name, body.position, body.year, body.jersey ? '#' + body.jersey : ''].filter(Boolean);
    var size = [heightText(body.height_in), body.weight != null && body.weight !== '' ? body.weight + ' lb' : ''].filter(Boolean);
    var teamHref = body.team_id
      ? withParams({
        tab: 'team-view',
        view_team_id: body.team_id,
        player_id: '',
        pager: '',
        up: pageUp()
      })
      : '';
    var html = barHtml(tables, body.name || '', pager);
    html += '<section class="gob-hero' + (color ? '' : ' is-neutral') + '"'
      + (color ? ' style="--tc:' + tables.esc(color) + '"' : '') + '>'
      + '<div class="gob-portrait">' + portraitHtml(tables, body) + '</div>'
      + '<div class="gob-hero-id"><div class="gob-hero-k">'
      + (body.team_name
        ? (teamHref
          ? '<a data-gob-drill href="' + tables.esc(teamHref) + '">' + tables.esc(body.team_name) + '</a>'
          : tables.esc(body.team_name))
        : '')
      + '</div><h1 class="gob-hero-n">' + tables.esc(body.name || '') + '</h1>'
      + '<div class="gob-hero-bio">' + tables.esc(bits.join(' · '))
      + (size.length ? ' · ' + tables.esc(size.join(' · ')) : '') + '</div>'
      + '<div class="gob-hero-rt">' + rtHtml(tables, body.rt, body.potential)
      + '<span>Rating · current → potential</span></div></div>'
      + '<div class="gob-hero-stats"><span class="gob-eyebrow">'
      + tables.esc((season.gp == null ? '—' : String(season.gp)) + ' GP')
      + '</span><div class="gob-hs">';
    RATE.forEach(function (pair) {
      html += '<div><b>' + tables.esc(oneDecimal(season[pair[0]])) + '</b><span>' + pair[1] + '</span></div>';
    });
    html += '</div></div></section><div class="gob-dt-body"><section class="gob-tcard"><div class="card-h"><h3>Attributes</h3></div><div class="gob-apan">';
    (body.attributes || []).forEach(function (group) {
      html += '<div class="gob-apg"><h4>' + tables.esc(group.label || '') + '</h4>';
      (group.attrs || []).forEach(function (attr) {
        var tiles = window.GOB_AttrTiles;
        var tile = tiles ? tiles.tileHtml(attr.attr, attr.display, false) : tables.esc(attr.display == null ? '—' : attr.display);
        html += '<div class="gob-apr"><span>' + tables.esc(attr.attr || '') + '</span>' + tile + '</div>';
      });
      html += '</div>';
    });
    html += '</div></section><div class="gob-dt-side"><section class="gob-tcard"><div class="card-h"><h3>Recent changes</h3></div>'
      + changesHtml(tables, body.recent_changes)
      + '</section><section class="gob-tcard"><div class="card-h"><h3>Development focus</h3></div>'
      + focusHtml(tables, body.development)
      + '</section></div><section class="gob-tcard gob-span"><div class="card-h"><h3>Stats</h3></div>'
      + '<div class="gob-xs"><table class="gob-tbl"><thead><tr><th class="left">Line</th>';
    LINE.forEach(function (pair) { html += '<th>' + pair[1] + '</th>'; });
    html += '</tr></thead><tbody>';
    [['Season', season], ['Career', career]].forEach(function (pair) {
      html += '<tr><td class="left">' + pair[0] + '</td>';
      LINE.forEach(function (col) {
        html += '<td>' + tables.esc(oneDecimal(pair[1][col[0]])) + '</td>';
      });
      html += '</tr>';
    });
    html += '</tbody></table></div></section></div>';
    container.innerHTML = html;
    tables.bindWide(container.querySelector('.gob-xs'));
    bindUp(container);
    bindPager(container, function (id) {
      if (window.GOBViews && typeof window.GOBViews.open === 'function') {
        window.GOBViews.open(withParams({ tab: 'player-view', player_id: id }), 'replace');
      }
    });
    var team = container.querySelector('a[data-gob-drill]');
    if (team) {
      team.addEventListener('click', function (event) {
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        if (window.GOBViews && typeof window.GOBViews.open === 'function') {
          window.GOBViews.open(team.getAttribute('href'), 'push');
        }
      });
    }
    bindFocus();
    if (typeof window.initAttributeTooltips === 'function') {
      window.initAttributeTooltips(container, ['[data-tooltip]']);
    }
  }

  function pageUp() {
    return query().get('up') || 'Player';
  }

  function selectedFocus() {
    var on = container.querySelector('.gob-focus button.on');
    return on ? (on.getAttribute('data-value') || '') : '';
  }

  function postFocus(value) {
    var config = window.API_CONFIG;
    var url = config && typeof config.buildUrl === 'function'
      ? config.buildUrl('/franchise/player/development-focus')
      : '/franchise/player/development-focus';
    var headers = { 'Content-Type': 'application/json' };
    if (config && typeof config.getAuthHeaders === 'function') {
      headers = Object.assign(headers, config.getAuthHeaders());
    }
    var init = {
      method: 'POST',
      headers: headers,
      body: JSON.stringify({
        franchise_id: franchiseId,
        player_id: playerId(),
        training_focus: value
      })
    };
    var store = window.GOBStore;
    var sent = store && typeof store.mutate === 'function'
      ? store.mutate(url, init)
      : fetch(url, init);
    return sent.then(function (res) {
      if (!res.ok) throw new Error('save failed');
      return res.json().catch(function () { return {}; });
    });
  }

  function bindFocus() {
    var group = container.querySelector('.gob-focus');
    var button = container.querySelector('.gob-save');
    if (!group || !button) return;
    var saved = selectedFocus();
    group.querySelectorAll('button').forEach(function (choice) {
      choice.addEventListener('click', function () {
        group.querySelectorAll('button').forEach(function (other) { other.classList.remove('on'); });
        choice.classList.add('on');
        var dirty = selectedFocus() !== saved;
        button.disabled = !dirty;
        button.textContent = 'Save';
        button.classList.remove('is-saved');
      });
    });
    button.addEventListener('click', function () {
      if (button.disabled) return;
      var next = selectedFocus();
      button.disabled = true;
      postFocus(next).then(function () {
        saved = next;
        button.textContent = 'Saved';
        button.classList.add('is-saved');
        button.disabled = true;
      }, function () {
        button.textContent = 'Save';
        button.classList.remove('is-saved');
        button.disabled = selectedFocus() === saved;
      });
    });
  }

  function apply(payload) {
    var next = payload || {};
    if (stampOrigin(!!next.is_user_team, 'player-view')) return;
    var stamp = JSON.stringify(next);
    if (loaded && stamp === signature && query().get('player_id') === String(next.player_id || '')) return;
    signature = stamp;
    player = next;
    loaded = true;
    render();
  }

  function load() {
    var store = ctx && ctx.store;
    var id = playerId();
    if (!store || typeof store.get !== 'function' || !franchiseId || !id) {
      showError();
      return;
    }
    if (!loaded) showSkeleton();
    var token = ++requestId;
    store.get(detailUrl()).then(function (payload) {
      if (token !== requestId) return;
      apply(payload || {});
    }).catch(function () {
      if (token !== requestId) return;
      loaded = false;
      showError();
    });
  }

  function revalidate() {
    var store = ctx && ctx.store;
    var id = playerId();
    if (!id || !store) return;
    if (player && String(player.player_id || '') !== String(id)) {
      loaded = false;
      signature = '';
      load();
      return;
    }
    if (!loaded || typeof store.revalidate !== 'function') {
      load();
      return;
    }
    var token = ++requestId;
    store.revalidate(detailUrl()).then(function (payload) {
      if (token !== requestId || !payload) return;
      apply(payload);
    }).catch(function () { /* keep the mounted page */ });
  }

  load();
  return { revalidate: revalidate, unmount: function () {} };
}

export function unmount() {}
