/**
 * Team › Roster. Grouped attribute grid. Position, RT, and the starting
 * lineup come from GET /roster. This view formats them.
 */

var GROUPS = [
  { name: 'Offense', keys: ['SC', 'SH'], shade: false },
  { name: 'Defense', keys: ['ID', 'OD'], shade: true },
  { name: 'Skills', keys: ['PS', 'BH'], shade: false },
  { name: 'Grit', keys: ['RB', 'ST'], shade: true },
  { name: 'Body', keys: ['AG', 'ND'], shade: false },
  { name: 'Mind', keys: ['IQ', 'FT'], shade: true }
];

var LEAD = {
  SC: "Simply put, this is a player's ability to put the ball in the hoop.",
  SH: "You guessed it! This is a player's ability to shoot the rock.",
  ID: 'The ability to defend near and around the basket.',
  OD: "This trait represents a player's ability to guard the perimeter.",
  PS: "This is a player's ability to make good fundamental passes.",
  BH: 'This trait is all about dribbling and handling the ball.',
  RB: "This trait represents a player's technical know-how when fighting for rebounds.",
  ST: 'This is the measure of how strong a player is.',
  AG: "An indication of a player's foot speed.",
  ND: "This represents a player's conditioning and willingness to fight through fatigue.",
  IQ: "Basketball IQ is the closest thing you'll get to understanding a player's intangibles.",
  FT: 'Exactly what you would expect.'
};

// `cls` carries the column's alignment and its share of the table rhythm:
// `rt` reads left so Current → Pot starts at the column edge, `code` centres the
// short codes, `num` right-aligns the measurements so their digits line up, and
// `wt` closes the identity block before the attribute gutter.
var IDENTITY = [
  { key: 'name', label: 'Player', pin: true, cls: 'pin team' },
  { key: 'rt', label: 'RT', cls: 'rt' },
  { key: 'pos', label: 'POS', cls: 'code' },
  { key: 'yr', label: 'YR', cls: 'code' },
  { key: 'ht', label: 'HT', cls: 'num' },
  { key: 'wt', label: 'WT', cls: 'num wt' }
];

function params() {
  try { return new URLSearchParams(window.location.search); }
  catch (err) { return new URLSearchParams(); }
}

function safeReturn() {
  var raw = params().get('return_url') || '';
  if (typeof window.getSafeReturnUrl === 'function') return window.getSafeReturnUrl(raw) || '';
  return raw.charAt(0) === '/' ? raw : '';
}

function idOf(player) {
  return String((player && (player._id || player.player_id || player.id)) || '');
}

function displayName(player) {
  if (!player) return '';
  if (player.name) return String(player.name);
  return [player.first_name, player.last_name].filter(Boolean).join(' ');
}

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

function fullName(key) {
  var names = window.GOB_AttrTiles && window.GOB_AttrTiles.ATTR_FULL_NAMES;
  return (names && names[key]) || key;
}

function tip(key) {
  var name = fullName(key);
  return LEAD[key] ? name + ' — ' + LEAD[key] : name;
}

function portraitHtml(tables, player) {
  var letters = initials(displayName(player));
  var pid = idOf(player);
  var url = '';
  if (player && player.portrait_source === 'recruit' && window.API_CONFIG
      && typeof window.API_CONFIG.getRecruitImageUrl === 'function') {
    // An unsigned recruit (a practice squad has them) has a recruit portrait, by image id.
    url = window.API_CONFIG.getRecruitImageUrl(player.image_id, { size: 'card' });
  } else if (pid && window.API_CONFIG && typeof window.API_CONFIG.getPlayerImageUrl === 'function') {
    url = window.API_CONFIG.getPlayerImageUrl(pid, { size: 'card' });
  }
  if (!url) return tables.esc(letters);
  return '<img alt="" src="' + tables.esc(url) + '" data-letters="' + tables.esc(letters)
    + '" onerror="var box=this.parentNode;if(box){box.textContent=this.getAttribute(\'data-letters\')||\'\';}">';
}

function rtHtml(tables, player) {
  if (player.rt == null || player.rt === '') return '';
  if (typeof window.formatRtDisplay !== 'function') return tables.esc(player.rt);
  var bucket = typeof window.getRtBucketClass === 'function' ? window.getRtBucketClass : function () { return ''; };
  var html = '<span class="rtl"><b class="' + bucket(player.rt) + '">' + tables.esc(window.formatRtDisplay(player.rt)) + '</b>';
  if (player.potential_rt_ratcheted != null && player.potential_rt_ratcheted !== '') {
    html += '<i>→</i><b class="pot ' + bucket(player.potential_rt_ratcheted) + '">'
      + tables.esc(window.formatRtDisplay(player.potential_rt_ratcheted)) + '</b>';
  }
  return html + '</span>';
}

function devText(player, userTeam) {
  if (!userTeam) return '';
  var api = window.GOBDevelopmentFocus;
  if (!api || typeof api.focusLabel !== 'function') return '';
  return api.focusLabel(player) || '';
}

var COMPACT_ATTRS = ['SC', 'SH', 'ID', 'OD', 'RB'];

function compactRosterHtml(tables, rows, opts) {
  var hrefFor = opts.playerHref || function () { return '#'; };
  var lineup = !!opts.lineup;
  var cols = 5 + COMPACT_ATTRS.length;
  var html = '<div class="gob-roster is-compact"><table class="gob-tbl"><colgroup><col class="c-player"><col class="c-rt"><col class="c-pos"><col class="c-yr"><col class="c-ht">';
  COMPACT_ATTRS.forEach(function () { html += '<col class="c-attr">'; });
  html += '</colgroup><thead><tr>';
  html += '<th class="pin team">Player</th><th class="rt">RT</th><th>POS</th><th>YR</th><th>HT</th>';
  COMPACT_ATTRS.forEach(function (key) {
    html += '<th data-tooltip="' + tables.esc(tip(key)) + '"'
      + ' title="' + tables.esc(fullName(key)) + '">' + tables.esc(key) + '</th>';
  });
  html += '</tr></thead><tbody>';
  var seenStarter = false;
  var seenBench = false;
  rows.forEach(function (player) {
    if (lineup && player.starter && !seenStarter) {
      html += '<tr class="gob-sep"><td colspan="' + cols + '">Starters</td></tr>';
      seenStarter = true;
    }
    if (lineup && !player.starter && seenStarter && !seenBench) {
      html += '<tr class="gob-sep"><td colspan="' + cols + '">Bench</td></tr>';
      seenBench = true;
    }
    html += '<tr><td class="pin team"><a class="gob-team gob-player" href="' + tables.esc(hrefFor(player)) + '">'
      + '<span class="av">' + portraitHtml(tables, player) + '</span><span>' + tables.esc(displayName(player)) + '</span></a></td>';
    html += '<td class="rt">' + rtHtml(tables, player) + '</td>';
    html += '<td>' + tables.esc(player.position || '') + '</td>';
    html += '<td>' + tables.esc(player.year || '') + '</td>';
    html += '<td>' + tables.esc(heightText(player.height)) + '</td>';
    COMPACT_ATTRS.forEach(function (key) {
      var tiles = window.GOB_AttrTiles;
      var value = tiles ? tiles.tileValue(player.attributes || {}, key) : null;
      html += '<td>' + (tiles ? tiles.tileHtml(key, value, false) : '') + '</td>';
    });
    html += '</tr>';
  });
  return html + '</tbody></table></div>';
}

export function orderLineup(rows) {
  return (rows || []).slice().sort(function (a, b) {
    var as = a.starter ? 0 : 1;
    var bs = b.starter ? 0 : 1;
    if (as !== bs) return as - bs;
    if (a.starter) return (Number(a.lineup_order) || 0) - (Number(b.lineup_order) || 0);
    return displayName(a).localeCompare(displayName(b));
  });
}

/** What a column sorts by. Shared by Team › Roster and the team page. */
export function rosterSortValue(player, key, userTeam) {
  if (key === 'name') return displayName(player);
  if (key === 'rt') return player.rt == null || player.rt === '' ? null : Number(player.rt);
  if (key === 'pos') return player.position || '';
  if (key === 'yr') return player.year || '';
  if (key === 'ht') return player.height == null || player.height === '' ? null : Number(player.height);
  if (key === 'wt') return player.weight == null || player.weight === '' ? null : Number(player.weight);
  if (key === 'dev') return devText(player, userTeam);
  var tiles = window.GOB_AttrTiles;
  if (!tiles) return null;
  return tiles.tileValue(player.attributes || {}, key);
}

/** First click on a text column sorts A to Z; on a number, highest first. */
export function rosterSortDir(key) {
  return key === 'name' || key === 'pos' || key === 'yr' || key === 'dev' ? 1 : -1;
}

/**
 * The roster grid. `dev: false` leaves the Dev focus column out: it is only stored
 * for the user's own players, so on another team it would be an empty column.
 */
export function rosterTableHtml(tables, rows, options) {
  var opts = options || {};
  if (opts.compact) return compactRosterHtml(tables, rows, opts);
  var sortKey = opts.sortKey || '';
  var lineup = !!opts.lineup;
  var userTeam = !!opts.userTeam;
  var dev = opts.dev !== false;
  var span = dev ? 19 : 18;
  var hrefFor = opts.playerHref || function () { return '#'; };
  // `gob-pairs`: the six attribute pairs share one gutter rule (Styleguide › Tables).
  // `program`: a practice squad is drawn from several programs, so a signed player's own
  // sits on a quiet second line under his name. The name block has one height with or
  // without it, so every row stays the same.
  var program = !!opts.program;
  var html = '<div class="gob-xs gob-roster gob-pairs' + (program ? ' has-program' : '') + '"><table class="gob-tbl"><thead>';
  html += '<tr class="gob-groups"><th colspan="6"></th>';
  GROUPS.forEach(function (group) {
    html += '<th class="gob-g' + (group.shade ? ' gshade' : '') + '" colspan="2">' + tables.esc(group.name) + '</th>';
  });
  html += (dev ? '<th></th>' : '') + '</tr>';
  html += headerRow(tables, sortKey, opts.sortDir, false, dev);
  html += '</thead><tbody>';
  var seenStarter = false;
  var seenBench = false;
  rows.forEach(function (player, index) {
    if (index > 0 && index % 16 === 0) html += headerRow(tables, sortKey, opts.sortDir, true, dev);
    if (lineup && player.starter && !seenStarter) {
      html += '<tr class="gob-sep"><td colspan="' + span + '">Starters</td></tr>';
      seenStarter = true;
    }
    if (lineup && !player.starter && seenStarter && !seenBench) {
      html += '<tr class="gob-sep"><td colspan="' + span + '">Bench</td></tr>';
      seenBench = true;
    }
    html += '<tr>';
    var nameHtml = '<span>' + tables.esc(displayName(player)) + '</span>';
    if (program) {
      nameHtml = '<span class="gob-id">' + nameHtml
        + (player.parent_team_name ? '<span class="sub">' + tables.esc(player.parent_team_name) + '</span>' : '')
        + '</span>';
    }
    html += '<td class="pin team"><a class="gob-team gob-player" href="' + tables.esc(hrefFor(player)) + '">'
      + '<span class="av">' + portraitHtml(tables, player) + '</span>' + nameHtml + '</a></td>';
    html += '<td class="rt' + (sortKey === 'rt' ? ' on' : '') + '">' + rtHtml(tables, player) + '</td>';
    html += '<td class="code' + (sortKey === 'pos' ? ' on' : '') + '">' + tables.esc(player.position || '') + '</td>';
    html += '<td class="code' + (sortKey === 'yr' ? ' on' : '') + '">' + tables.esc(player.year || '') + '</td>';
    html += '<td class="num' + (sortKey === 'ht' ? ' on' : '') + '">' + tables.esc(heightText(player.height)) + '</td>';
    html += '<td class="num wt' + (sortKey === 'wt' ? ' on' : '') + '">' + (player.weight == null || player.weight === '' ? '' : tables.esc(player.weight)) + '</td>';
    GROUPS.forEach(function (group) {
      group.keys.forEach(function (key, position) {
        var tiles = window.GOB_AttrTiles;
        var value = tiles ? tiles.tileValue(player.attributes || {}, key) : null;
        var cell = tiles ? tiles.tileHtml(key, value, false) : '';
        var cls = (position === 0 ? 'gstart' : 'gend')
          + (group.shade ? ' gshade' : '') + (sortKey === key ? ' on' : '');
        html += '<td class="' + cls + '">' + cell + '</td>';
      });
    });
    if (dev) {
      var focus = devText(player, userTeam);
      html += '<td class="dev' + (focus ? '' : ' none') + (sortKey === 'dev' ? ' on' : '') + '">' + tables.esc(focus) + '</td>';
    }
    html += '</tr>';
  });
  return html + '</tbody></table></div>';
}

function headerRow(tables, sortKey, sortDir, repeat, dev) {
  var html = '<tr' + (repeat ? ' class="gob-rep"' : '') + '>';
  IDENTITY.forEach(function (col) {
    var cls = 's ' + col.cls + (sortKey === col.key ? ' on ' + (sortDir < 0 ? 'desc' : 'asc') : '');
    html += '<th class="' + cls.trim() + '" data-sort="' + col.key + '">' + tables.esc(col.label) + '</th>';
  });
  GROUPS.forEach(function (group) {
    group.keys.forEach(function (key, position) {
      var on = sortKey === key;
      var cls = 's ' + (position === 0 ? 'gstart' : 'gend')
        + (group.shade ? ' gshade' : '') + (on ? ' on ' + (sortDir < 0 ? 'desc' : 'asc') : '');
      html += '<th class="' + cls.trim() + '" data-sort="' + key + '"'
        + ' data-tooltip="' + tables.esc(tip(key)) + '"'
        + ' aria-label="Sort by ' + tables.esc(fullName(key)) + '"'
        + ' title="' + tables.esc(fullName(key)) + '"><span class="ak">' + tables.esc(key) + '</span></th>';
    });
  });
  if (dev !== false) {
    var devOn = sortKey === 'dev';
    html += '<th class="s dev' + (devOn ? ' on ' + (sortDir < 0 ? 'desc' : 'asc') : '') + '" data-sort="dev">Dev focus</th>';
  }
  return html + '</tr>';
}

export function mount(container, ctx) {
  var tables = window.GOBTables;
  var franchiseId = (ctx && ctx.franchiseId) || '';
  var userId = (ctx && ctx.teamId) || '';
  var viewed = params().get('roster_team_id') || userId;
  var returnUrl = safeReturn();
  var scope = tables.readKey('gob-view-roster-scope', 'varsity');
  if (scope !== 'practice') scope = 'varsity';
  var sortKey = scope === 'practice' ? 'rt' : '';
  var sortDir = -1;
  var body = null;
  var signature = '';
  var loaded = false;
  var restored = false;

  function rosterUrl() {
    var base = tables.apiBase('/roster/' + encodeURIComponent(viewed || userId));
    return base + '?franchise_id=' + encodeURIComponent(franchiseId);
  }

  function restoreScroll() {
    if (restored || !tables.backForward()) return;
    restored = true;
    var nav = ctx && ctx.nav;
    if (!nav || typeof nav.restoreScroll !== 'function') return;
    requestAnimationFrame(function () {
      nav.restoreScroll();
      requestAnimationFrame(function () { nav.restoreScroll(); });
    });
  }

  function backHtml() {
    return returnUrl ? '<button type="button" id="back-button" class="gob-back">Back</button>' : '';
  }

  function bindBack() {
    var button = container.querySelector('#back-button');
    if (!button) return;
    button.addEventListener('click', function () {
      if (window.GOBNav && typeof window.GOBNav.back === 'function') window.GOBNav.back(returnUrl);
      else window.location.assign(returnUrl);
    });
  }

  function lists() {
    var varsity = (body && body.players) || [];
    var practice = ((body && body.training_squad) || []).concat((body && body.practice_squad_recruits) || []);
    return { varsity: varsity, practice: practice };
  }

  function paintTools(slot) {
    var counts = lists();
    var options = [
      { id: 'varsity', label: 'Varsity', count: counts.varsity.length },
      { id: 'practice', label: 'Practice Squad', count: counts.practice.length }
    ];
    var html = '<div class="stats-toggle" role="group">';
    options.forEach(function (opt) {
      html += '<button type="button" data-value="' + opt.id + '"'
        + (opt.id === scope ? ' class="on"' : '') + '>'
        + tables.esc(opt.label) + '<em>' + opt.count + '</em></button>';
    });
    html += '</div>';
    slot.innerHTML = html;
    slot.querySelectorAll('button').forEach(function (button) {
      button.addEventListener('click', function () {
        var next = button.getAttribute('data-value');
        if (!next || next === scope) return;
        scope = next;
        tables.writeKey('gob-view-roster-scope', scope);
        sortKey = scope === 'practice' ? 'rt' : '';
        sortDir = -1;
        tables.resetScroll();
        paintTools(slot);
        render();
      });
    });
  }

  function ownTools() {
    tables.registerTools('roster-view', paintTools);
    var host = document.getElementById('gob-subtabs');
    var old = host && host.querySelector('.pg-tools[data-owner="roster-view"]');
    if (old) old.remove();
    tables.placeTools();
  }

  function onTab() {
    if (container.classList.contains('active')) ownTools();
  }

  function readValue(player, key) {
    return rosterSortValue(player, key, body && body.is_user_team);
  }

  function playerHref(player) {
    var q = new URLSearchParams(window.location.search);
    q.set('tab', 'player-view');
    q.set('player_id', idOf(player));
    q.set('origin', 'team');
    q.set('up', 'Roster');
    q.set('return_tab', 'roster-view');
    q.set('pager', 'roster');
    q.delete('view_team_id');
    q.delete('id');
    var text = q.toString();
    return window.location.pathname + (text ? '?' + text : '');
  }

  function render() {
    var counts = lists();
    var source = scope === 'practice' ? counts.practice : counts.varsity;
    var lineup = scope === 'varsity' && !sortKey;
    var rows = lineup ? orderLineup(source) : source.slice();
    if (sortKey) {
      rows = tables.sortRows(rows, function (player) { return readValue(player, sortKey); }, sortDir);
    }
    var html = backHtml() + '<section class="gob-tcard">' + rosterTableHtml(tables, rows, {
      sortKey: sortKey,
      sortDir: sortDir,
      lineup: lineup,
      userTeam: !!(body && body.is_user_team),
      playerHref: playerHref
    }) + '</section>';
    container.innerHTML = html;
    tables.bindWide(container.querySelector('.gob-xs'));
    bindBack();
    container.querySelectorAll('th.s').forEach(function (th) {
      th.addEventListener('click', function () {
        var key = th.getAttribute('data-sort');
        if (sortKey === key) sortDir = -sortDir;
        else {
          sortKey = key;
          sortDir = rosterSortDir(key);
        }
        render();
      });
    });
    var order = rows.map(idOf);
    container.querySelectorAll('a.gob-player').forEach(function (link) {
      link.addEventListener('click', function (event) {
        try { sessionStorage.setItem('gob-view-roster-order', JSON.stringify(order)); }
        catch (err) { /* the pager reads this later */ }
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button) return;
        event.preventDefault();
        if (window.GOBViews && typeof window.GOBViews.open === 'function') {
          window.GOBViews.open(link.getAttribute('href'), 'push');
        }
      });
    });
    if (typeof window.initAttributeTooltips === 'function') {
      window.initAttributeTooltips(container, ['[data-tooltip]']);
    }
    ownTools();
    restoreScroll();
  }

  function apply(payload) {
    var next = payload || {};
    var stamp = JSON.stringify({
      players: next.players || [],
      training_squad: next.training_squad || [],
      practice_squad_recruits: next.practice_squad_recruits || [],
      is_user_team: !!next.is_user_team
    });
    if (loaded && stamp === signature) return;
    signature = stamp;
    body = next;
    loaded = true;
    render();
  }

  function showSkeleton() {
    tables.paintSkeleton(container);
    if (returnUrl) container.insertAdjacentHTML('afterbegin', backHtml());
    bindBack();
  }

  function showError() {
    tables.paintError(container, 'Roster could not be opened.', load);
    if (returnUrl) container.insertAdjacentHTML('afterbegin', backHtml());
    bindBack();
  }

  function load() {
    var store = ctx && ctx.store;
    if (!store || typeof store.get !== 'function' || !franchiseId || !viewed) {
      showError();
      return;
    }
    if (!loaded) showSkeleton();
    store.get(rosterUrl()).then(function (payload) {
      apply(payload || { players: [] });
    }).catch(function () {
      loaded = false;
      showError();
    });
  }

  function revalidate() {
    var store = ctx && ctx.store;
    if (!loaded || !store || typeof store.revalidate !== 'function' || !franchiseId || !viewed) return;
    store.revalidate(rosterUrl()).then(function (payload) {
      if (payload) apply(payload);
    }).catch(function () { /* keep the mounted table */ });
  }

  document.addEventListener('gob-tab-shown', onTab);
  ownTools();
  load();

  return {
    revalidate: revalidate,
    unmount: function () {
      document.removeEventListener('gob-tab-shown', onTab);
      tables.registerTools('roster-view', null);
    }
  };
}

export function unmount() {}
