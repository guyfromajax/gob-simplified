/**
 * Coach's Office. Renders office_digest. Does not rank, streak, gate, or bucket.
 */
(function (global) {
  'use strict';

  var TODO_COPY = {
    finish_cpu_sims: 'Finish CPU sims',
    assign_practice_squad: 'Assign practice squad',
    review_recruit_invites: 'Review recruit invites',
    run_recruiting_day: 'Run recruiting day',
    run_signing_day: 'Run Signing Day',
    view_recruiting_results: 'View recruiting results',
    go_to_next_season: 'Go to next season',
    sim_next_round: 'Sim next round',
    resume_training: 'Resume training',
    run_training_camp: 'Run training camp',
    run_training: 'Run training',
    play_next_game: 'Play next game'
  };

  var MEASURE_LABELS = {
    shot_threshold: 'Shooting',
    rebound_modifier: 'Rebounding',
    offensive_efficiency: 'Offense',
    defensive_efficiency: 'Defense',
    fb_efficiency: 'Fast Break',
    pt_efficiency: 'P/T Defense',
    fight: 'Fight',
    discipline: 'Discipline',
    team_chemistry: 'Team Chemistry',
    fb_opp_modifier: 'Fast Break Defense',
    pt_opp_modifier: 'P/T Offense'
  };

  var ATTITUDE_BAR_MAX = 5;

  var EMOJI = {
    em_0_19: '😡',
    em_20_39: '😕',
    em_40_59: '😐',
    em_60_79: '😊',
    em_80_plus: '😎'
  };

  var ARRIVAL_KEY = 'gob-office-arrival';
  // Per page load: whether each result key is a first showing, and whether its win
  // sting has already fired — so repeated renders don't replay either.
  var arrivalDecided = {};
  var stingPlayed = {};

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null && text !== '') node.textContent = text;
    return node;
  }

  function present(value) {
    return value != null && value !== '';
  }

  function advanceLabel() {
    var play = document.getElementById('play-now');
    var text = play ? String(play.textContent || '').replace(/\s+/g, ' ').trim() : '';
    if (!text || text === 'STARTING…') return '';
    return text;
  }

  function winsLosses(record) {
    if (!record || typeof record !== 'object') return '';
    if (!present(record.wins) || !present(record.losses)) return '';
    return record.wins + '–' + record.losses;
  }

  function conferenceLabel(value) {
    if (!present(value) || typeof value === 'object') return '';
    if (typeof global.formatConferenceShortLabel === 'function') {
      return global.formatConferenceShortLabel(value) || '';
    }
    return '';
  }

  function wholeMinutes(value) {
    var seconds = Number(value);
    if (!isFinite(seconds)) return '';
    if (typeof global.formatMinutes !== 'function') return '';
    return global.formatMinutes(seconds);
  }

  function reducedMotion() {
    try {
      return global.matchMedia('(prefers-reduced-motion: reduce)').matches;
    } catch (err) {
      return false;
    }
  }

  function clickTiny() {
    import('/js/shared/uiSfx.js').then(function (mod) {
      if (mod && mod.playSelect) mod.playSelect();
    }).catch(function () {});
  }

  function inAppView(url) {
    var views = global.GOBViews;
    if (!views || typeof views.has !== 'function' || typeof views.open !== 'function') return false;
    if (!/\/franchise-command-center\.html$/i.test(global.location.pathname || '')) return false;
    try {
      var parsed = new URL(url, global.location.origin);
      return /\/franchise-command-center\.html$/i.test(parsed.pathname) && views.has(parsed.searchParams.get('tab') || '');
    } catch (err) {
      return false;
    }
  }

  function go(url) {
    if (!url) return;
    clickTiny();
    if (inAppView(url)) global.GOBViews.open(url, 'push');
    else if (global.GOBNav && typeof global.GOBNav.go === 'function') global.GOBNav.go(url);
    else global.location.assign(url);
  }

  function bindGo(node, url) {
    if (!node || !url) return;
    node.addEventListener('click', function (event) {
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) return;
      event.preventDefault();
      go(url);
    });
  }

  // The coach's team for an outbound link. The address carries it on some arrivals only:
  // after a game, from the mode select and from Set Lineup the Office opens with
  // franchise_id alone, and a standalone page (the Training Report) cannot load without a
  // team. The command center notes the franchise's own team on GOBViews as soon as its
  // data is in, so that is the fallback.
  function userTeamId(current) {
    var fromUrl = current.get('team_id') || current.get('user_team_id');
    if (fromUrl) return fromUrl;
    var views = global.GOBViews;
    try {
      return (views && typeof views.userTeamId === 'function' && views.userTeamId()) || '';
    } catch (err) {
      return '';
    }
  }

  function href(path, params) {
    if (!path) return '';
    var query = new URLSearchParams();
    var bag = params || {};
    Object.keys(bag).forEach(function (key) {
      if (present(bag[key])) query.set(key, String(bag[key]));
    });
    var text = query.toString();
    return text ? path + '?' + text : path;
  }

  function franchiseHref(path) {
    var current = new URLSearchParams(global.location.search);
    var params = {};
    if (current.get('franchise_id')) params.franchise_id = current.get('franchise_id');
    var teamId = userTeamId(current);
    if (teamId) params.team_id = teamId;
    return href(path, params);
  }

  function viewHref(changes, stubPath, stubParams) {
    var tables = global.GOBTables;
    if (tables && typeof tables.viewHref === 'function') return tables.viewHref(changes);
    return href(stubPath, stubParams);
  }

  function playerHref(playerId) {
    if (!present(playerId)) return '';
    var current = new URLSearchParams(global.location.search);
    var params = { id: playerId, return_tab: 'home-tab', origin: 'office', up: 'Office' };
    if (current.get('franchise_id')) {
      params.mode = 'franchise';
      params.franchise_id = current.get('franchise_id');
    }
    if (current.get('team_id')) params.team_id = current.get('team_id');
    return viewHref({
      tab: 'player-view', player_id: playerId, return_tab: 'home-tab', origin: 'office', up: 'Office'
    }, '/player-detail.html', params);
  }

  function teamHref(teamId) {
    if (!present(teamId)) return '';
    var current = new URLSearchParams(global.location.search);
    var params = { roster_team_id: teamId, return_tab: 'home-tab' };
    if (current.get('franchise_id')) params.franchise_id = current.get('franchise_id');
    var owner = userTeamId(current);
    if (owner) params.team_id = owner;
    else params.team_id = teamId;
    return viewHref({
      tab: 'team-view', view_team_id: teamId, team_id: params.team_id, return_tab: 'home-tab', origin: 'office'
    }, '/team-roster-view.html', params);
  }

  function recruitingHref() {
    return franchiseHref('/recruiting.html');
  }

  function initials(name) {
    var parts = String(name || '').trim().split(/\s+/).filter(Boolean);
    if (!parts.length) return '';
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
    return (parts[0].charAt(0) + parts[parts.length - 1].charAt(0)).toUpperCase();
  }

  function portrait(playerId, name, className) {
    var box = el('span', className || 'portrait');
    var letters = initials(name);
    var api = global.API_CONFIG;
    var hasApi = api && typeof api.getPlayerImageUrl === 'function';
    var url = (present(playerId) && hasApi) ? api.getPlayerImageUrl(playerId, { size: 'card' }) : '';
    function showInitials() {
      box.textContent = '';
      if (letters) box.appendChild(el('span', 'office-initials', letters));
    }
    if (!url) { showInitials(); return box; }
    // The painted headshot, then the shared silhouette on a miss, then centred
    // initials only if even the silhouette is unavailable.
    var img = el('img');
    img.alt = '';
    var triedSilhouette = false;
    img.addEventListener('error', function onErr() {
      if (!triedSilhouette && hasApi && typeof api.getGenericHeadshotUrl === 'function') {
        triedSilhouette = true;
        img.src = api.getGenericHeadshotUrl({ size: 'card' });
        return;
      }
      img.removeEventListener('error', onErr);
      showInitials();
    });
    img.src = url;
    box.appendChild(img);
    return box;
  }

  function linkName(className, label, url) {
    if (!present(label)) return null;
    var node = el(url ? 'a' : 'span', className, label);
    if (url) {
      node.href = url;
      bindGo(node, url);
    }
    return node;
  }

  function digitClass(value) {
    var api = global.GOB_AttributeDisplay;
    var tier = api && api.attrTier ? api.attrTier(value) : null;
    if (tier === 'elite') return 't-blue';
    if (tier === 'high') return 't-green';
    if (tier === 'mid') return 't-yellow';
    return 't-red';
  }

  function rtLetters(value) {
    if (!present(value)) return '';
    if (typeof value === 'number' || /^-?\d+(\.\d+)?$/.test(String(value))) {
      if (typeof global.formatRtDisplay === 'function') {
        var shown = global.formatRtDisplay(value);
        return shown && shown !== '--' ? shown : '';
      }
    }
    return String(value);
  }

  function rtColorClass(letters) {
    if (/^A/.test(letters)) return 't-blue';
    if (/^B/.test(letters)) return 't-green';
    if (/^C/.test(letters)) return 't-yellow';
    return 't-red';
  }

  function labelize(key) {
    var raw = String(key || '');
    if (MEASURE_LABELS[raw]) return MEASURE_LABELS[raw];
    return raw.replace(/_/g, ' ').replace(/\b\w/g, function (ch) { return ch.toUpperCase(); });
  }

  function chip(delta, popIndex) {
    if (delta == null || delta === '') return null;
    var n = Number(delta);
    if (!isFinite(n) || n === 0) return null;
    var kind = n > 0 ? 'up' : 'down';
    var text = n > 0 ? '▲' + n : '▼' + Math.abs(n);
    var node = el('span', 'chip ' + kind + (popIndex != null ? ' ar-pop' : ''), text);
    if (popIndex != null) node.style.setProperty('--i', String(popIndex));
    return node;
  }

  function streakChip(streak) {
    if (!present(streak)) return null;
    var text = String(streak);
    var kind = text.charAt(0) === 'W' ? 'up' : (text.charAt(0) === 'L' ? 'down' : 'flat');
    return el('span', 'chip ' + kind, text);
  }

  function chevron() {
    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 16 16');
    svg.setAttribute('aria-hidden', 'true');
    var path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', 'M6 3.5 11 8 6 12.5');
    path.setAttribute('fill', 'none');
    path.setAttribute('stroke', 'currentColor');
    path.setAttribute('stroke-width', '1.6');
    svg.appendChild(path);
    return svg;
  }

  function checkMark() {
    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 12 12');
    svg.setAttribute('aria-hidden', 'true');
    var path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', 'M2 6.2 4.6 9 10 3');
    path.setAttribute('fill', 'none');
    path.setAttribute('stroke', 'currentColor');
    path.setAttribute('stroke-width', '1.8');
    svg.appendChild(path);
    return svg;
  }

  function countUp(root) {
    root.querySelectorAll('[data-cu-from]').forEach(function (node) {
      var from = +node.dataset.cuFrom;
      var to = +node.dataset.cuTo;
      var pre = node.dataset.cuPre || '';
      var suf = node.dataset.cuSuf || '';
      var start = performance.now() + 320;
      function step(now) {
        var k = Math.min(1, Math.max(0, (now - start) / 600));
        var eased = 1 - Math.pow(1 - k, 3);
        node.textContent = pre + Math.round(from + (to - from) * eased) + suf;
        if (k < 1) requestAnimationFrame(step);
      }
      requestAnimationFrame(step);
    });
  }

  function arrivalKey(digest) {
    var result = digest && digest.result;
    if (!result) return '';
    // Falls back to a composite when the game has no id.
    return present(result.result_key)
      ? String(result.result_key)
      : [digest.state, result.week, result.home_score, result.away_score, result.opponent_team_id].join(':');
  }

  function arrivalFor(digest) {
    var result = digest && digest.result;
    if (!result) return { firstShowing: false, arriving: false, calm: false };
    // The entrance plays once per result. "Seen" is the client's own state: the
    // last-shown result_key in localStorage. The decision is cached per key for the
    // page's lifetime so a second render in the same load does not flip it (the FCC
    // renders the office more than once). If storage fails, treat it as already
    // seen — show the final state rather than replaying on every load.
    var key = arrivalKey(digest);
    var firstShowing;
    if (Object.prototype.hasOwnProperty.call(arrivalDecided, key)) {
      firstShowing = arrivalDecided[key];
    } else {
      try {
        var seen = localStorage.getItem(ARRIVAL_KEY) || '';
        firstShowing = seen !== key;
        if (firstShowing) localStorage.setItem(ARRIVAL_KEY, key);
      } catch (err) {
        firstShowing = false;
      }
      arrivalDecided[key] = firstShowing;
    }
    var lost = result.user_won === false || digest.state === 'loss';
    // Motion is first-showing only and honours reduced motion; the sting follows
    // the audio settings, so it stays keyed to firstShowing alone.
    return { firstShowing: firstShowing, arriving: firstShowing && !reducedMotion(), calm: lost };
  }

  function column(index, title, aside, linkUrl) {
    var col = el('section', 'office-col');
    var head = el('header', 'office-h');
    var h2 = el('h2');
    h2.appendChild(el('i', '', index));
    h2.appendChild(document.createTextNode(title));
    if (linkUrl) {
      var link = el('a', 'col-link');
      link.href = linkUrl;
      link.appendChild(h2);
      bindGo(link, linkUrl);
      head.appendChild(link);
    } else {
      head.appendChild(h2);
    }
    if (present(aside)) head.appendChild(el('span', '', aside));
    col.appendChild(head);
    return col;
  }

  function card(className, index) {
    var node = el('section', 'card ' + className + ' ar-card');
    node.style.setProperty('--i', String(index));
    return node;
  }

  function attrParts(raw) {
    var names = global.ATTRIBUTE_NAMES || {};
    var key = String(raw || '');
    var upper = key.toUpperCase();
    if (names[upper]) return { code: upper, title: names[upper] };
    var codes = Object.keys(names);
    for (var i = 0; i < codes.length; i++) {
      if (String(names[codes[i]]).toLowerCase() === key.toLowerCase()) {
        return { code: codes[i], title: names[codes[i]] };
      }
    }
    return { code: upper.length <= 3 ? upper : upper.slice(0, 2), title: labelize(key) };
  }

  // The shell adds .gob-1920 / .gob-1280 from a dynamic import, which can land after the
  // Office's first render. Until it does, the row caps read the same media query the
  // shell binds (gobDensity.js), so a 1920 window never opens on the 1280 caps.
  function largeDensity() {
    var root = document.documentElement;
    if (root.classList.contains('gob-1920')) return true;
    if (root.classList.contains('gob-1280')) return false;
    try {
      return !!global.matchMedia('(min-width: 1680px) and (min-height: 1000px)').matches;
    } catch (err) {
      return false;
    }
  }

  function playerCap() {
    return largeDensity() ? 8 : 5;
  }

  function groupAttributes(changes) {
    var order = [];
    var map = {};
    (Array.isArray(changes) ? changes : []).forEach(function (change) {
      if (!change || !present(change.from) || !present(change.to)) return;
      // CH is a hidden attribute: the server does not send it, and it is never a chip.
      if (change.attribute === 'CH') return;
      var delta = Number(change.to) - Number(change.from);
      if (!isFinite(delta) || delta === 0) return;
      var id = present(change.player_id) ? String(change.player_id) : String(change.name || '');
      if (!map[id]) {
        map[id] = {
          id: id,
          name: present(change.name) ? String(change.name) : '',
          chips: [],
          total: 0
        };
        order.push(id);
      }
      var row = map[id];
      if (present(change.name)) row.name = String(change.name);
      row.total += Math.abs(delta);
      row.chips.push({
        attribute: change.attribute,
        to: change.to,
        delta: delta,
        // Server-owned flag; the client never recomputes the gain threshold.
        exceptional: change.exceptional === true
      });
    });
    var rows = order.map(function (id) { return map[id]; });
    rows.forEach(function (row) {
      row.chips.sort(function (a, b) {
        var upA = a.delta > 0 ? 0 : 1;
        var upB = b.delta > 0 ? 0 : 1;
        return upA - upB;
      });
    });
    rows.sort(function (a, b) {
      if (b.total !== a.total) return b.total - a.total;
      return a.name.localeCompare(b.name);
    });
    return rows;
  }

  // A training chip (.gc): attribute code, the app's tier-coloured value tile, and
  // a NEUTRAL ▲/▼ delta. `exceptional` (server flag only) turns it into the one
  // weekly gold marker; the client never recomputes the gain threshold.
  function gainChip(change) {
    var parts = attrParts(change.attribute);
    var down = change.delta < 0;
    var node = el('span', 'gc' + (change.exceptional ? ' xg' : '') + (down ? ' dn' : ''));
    node.title = parts.title;
    node.appendChild(el('b', '', parts.code));
    var tiles = global.GOB_AttrTiles;
    if (tiles && typeof tiles.tileHtml === 'function') {
      var holder = el('span');
      holder.innerHTML = tiles.tileHtml(parts.code, change.to, false);
      if (holder.firstChild) node.appendChild(holder.firstChild);
    } else {
      node.appendChild(el('b', 'tdig ' + digitClass(change.to), String(change.to)));
    }
    node.appendChild(el('i', '', (down ? '▼' : '▲') + Math.abs(change.delta)));
    return node;
  }

  function trainingReportHref(digest) {
    var current = new URLSearchParams(global.location.search);
    // Standalone focus page. `from` picks Continue to Office vs Back to Locker Room.
    var params = { mode: 'franchise', from: 'office', origin: 'office' };
    if (current.get('franchise_id')) params.franchise_id = current.get('franchise_id');
    var teamId = userTeamId(current);
    if (teamId) params.team_id = teamId;
    var week = digest && digest.result && digest.result.week;
    if (!present(week) && digest && digest.next_game) week = digest.next_game.week;
    if (present(week)) params.week = week;
    return href('/training-report.html', params);
  }

  // The week's steps, as status. Read-only: a list, not controls. Nothing here navigates
  // or advances; the action button in the top bar is the only control that does.
  function weekStrip(digest) {
    var list = Array.isArray(digest && digest.todos) ? digest.todos : [];
    var nextIndex = -1;
    list.forEach(function (todo, index) {
      if (nextIndex === -1 && todo && !todo.done && todo.required !== false) nextIndex = index;
    });
    var strip = el('div', 'week-strip' + (list.length > 6 ? ' is-tight' : ''));
    var track = el('ol', 'week-track');
    track.setAttribute('aria-label', 'This week');
    list.forEach(function (todo, index) {
      if (!todo) return;
      var classes = 'wk-step';
      var state = 'upcoming';
      if (todo.done) {
        classes += ' done';
        state = 'done';
      } else if (todo.gates_advance && !todo.is_advance_action) {
        classes += ' gated';
        state = 'blocking';
        if (index === nextIndex) classes += ' is-next';
      } else if (index === nextIndex) {
        classes += ' is-next';
        state = 'next';
      } else {
        classes += ' is-upcoming';
      }
      var row = el('li', classes);
      row.dataset.officeTodo = todo.id || '';
      row.dataset.stepState = state;
      if (index === nextIndex) row.setAttribute('aria-current', 'step');
      if (todo.is_advance_action && !todo.done) row.dataset.advanceMirror = '1';
      var dot = el('span', 'wk-dot');
      dot.setAttribute('aria-hidden', 'true');
      if (todo.done) dot.appendChild(checkMark());
      row.appendChild(dot);
      var copy = (todo.is_advance_action && !todo.done)
        ? advanceLabel()
        : (TODO_COPY[todo.label_key] || labelize(todo.label_key));
      row.appendChild(el('span', 'td-l', copy));
      // What the mark says, for a reader that cannot see it.
      if (todo.done) row.appendChild(el('span', 'wk-sr', ' (done)'));
      track.appendChild(row);
    });
    strip.appendChild(track);
    return strip;
  }

  function tightenStrip(strip) {
    if (!strip) return;
    strip.classList.remove('is-tight', 'is-tighter');
    if (strip.scrollWidth <= strip.clientWidth + 1) return;
    strip.classList.add('is-tight');
    if (strip.scrollWidth <= strip.clientWidth + 1) return;
    strip.classList.add('is-tighter');
  }

  function userSide(result) {
    if (!result) return null;
    if (result.user_is_home === true) {
      return { id: result.home_team_id, name: result.home_team_name, score: result.home_score };
    }
    if (result.user_is_home === false) {
      return { id: result.away_team_id, name: result.away_team_name, score: result.away_score };
    }
    return null;
  }

  function otherSide(result) {
    if (!result) return null;
    if (result.user_is_home === true) {
      return { id: result.away_team_id, name: result.opponent_team_name || result.away_team_name, score: result.away_score };
    }
    if (result.user_is_home === false) {
      return { id: result.home_team_id, name: result.opponent_team_name || result.home_team_name, score: result.home_score };
    }
    return null;
  }

  function scoreNode(value, className, count) {
    var node = el('b', className, count ? '0' : (present(value) ? String(value) : ''));
    if (count && present(value)) {
      node.dataset.cuFrom = '0';
      node.dataset.cuTo = String(value);
    } else if (present(value)) {
      node.textContent = String(value);
    }
    return node;
  }

  function ordinal(n) {
    var num = Number(n);
    if (!isFinite(num)) return String(n);
    var mod100 = num % 100;
    if (mod100 >= 11 && mod100 <= 13) return num + 'th';
    switch (num % 10) {
      case 1: return num + 'st';
      case 2: return num + 'nd';
      case 3: return num + 'rd';
      default: return num + 'th';
    }
  }

  function weeklyPlayerCap() {
    return largeDensity() ? 5 : 3;
  }

  // One scoreboard row. `winRow` carries the emphasis; on a loss the card drops
  // every row to t87 in CSS, so the loser is never dimmed on the coach's own page.
  function scoreRow(name, rank, score, winRow, countScore) {
    var row = el('div', 'sb2-r' + (winRow ? ' w' : ''));
    var who = el('span', 'sb2-n');
    if (present(rank)) who.appendChild(el('em', '', '#' + rank));
    who.appendChild(el('span', '', present(name) ? String(name) : ''));
    row.appendChild(who);
    var pts = el('span', 'sb2-p');
    if (countScore && present(score)) {
      pts.textContent = '0';
      pts.dataset.cuFrom = '0';
      pts.dataset.cuTo = String(score);
    } else {
      pts.textContent = present(score) ? String(score) : '';
    }
    row.appendChild(pts);
    return row;
  }

  function weeklyBadge(label, value, delta) {
    if (!present(value)) return null;
    var cell = el('div', 'bdg');
    cell.appendChild(el('span', '', label));
    var v = el('div', 'bdg-v');
    v.appendChild(el('b', '', String(value)));
    var n = Number(delta);
    if (present(delta) && isFinite(n) && n !== 0) {
      // Neutral by law: ▲ t87 / ▼ t60. Never green or red.
      v.appendChild(el('em', n < 0 ? 'dn' : '', (n < 0 ? '▼' : '▲') + Math.abs(n)));
    }
    cell.appendChild(v);
    return cell;
  }

  // The folded moment(s): the Also row from digest.also, plus an inline "+N more"
  // that reveals the rest of weekly_card_items in place.
  function weeklyAlso(digest) {
    var also = digest && digest.also;
    if (!also || (!present(also.title) && !present(also.line))) return null;
    var items = Array.isArray(digest.weekly_card_items) ? digest.weekly_card_items.filter(Boolean) : [];
    var wrap = el('div', 'wkc-more-wrap ar-item');

    function alsoRow(item) {
      var er = el('div', 'wkc-also');
      er.appendChild(el('span', '', 'Also'));
      er.appendChild(el('b', '', present(item.title) ? item.title : item.line));
      var url = weeklyHref(item);
      if (url) {
        var link = el('a', 'lnk', 'View');
        link.href = url;
        bindGo(link, url);
        er.appendChild(link);
      }
      return er;
    }

    wrap.appendChild(alsoRow(also));

    var rest = items.slice(1);
    if (rest.length) {
      var extra = el('div', 'wkc-extra');
      extra.hidden = true;
      rest.forEach(function (item) { if (item) extra.appendChild(alsoRow(item)); });
      var toggle = el('button', 'wkc-more', '+' + rest.length + ' more');
      toggle.type = 'button';
      toggle.setAttribute('aria-expanded', 'false');
      // Reveal/hide is not a navigation, so it never routes through go()/clickTiny.
      // Give it the same tiny select tick every other office control has, via the
      // delegated data-sfx hook (one sound per click — the toggle handler is silent).
      toggle.setAttribute('data-sfx', 'SFX_SELECT');
      toggle.addEventListener('click', function () {
        var open = extra.hidden;
        extra.hidden = !open;
        toggle.setAttribute('aria-expanded', String(open));
        toggle.textContent = open ? 'Show less' : '+' + rest.length + ' more';
      });
      wrap.appendChild(extra);
      wrap.appendChild(toggle);
    }
    return wrap;
  }

  // The weekly "Since last week" card. Replaces the Result + What moved cards in
  // Office column 1. No team wash (the WIN tag carries the result); neutral
  // deltas; reward gold only on the exceptional-gain marker.
  function sinceLastWeekCard(digest, index, countScores, userRank) {
    var result = digest && digest.result;
    var won = result ? result.user_won : null;
    var loss = won === false;
    var node = el('section', 'wkc ar-card' + (won === true ? ' is-win' : '') + (loss ? ' is-loss' : ''));
    node.style.setProperty('--i', String(index));
    var itemIndex = 0;
    function markItem(el0) { el0.classList.add('ar-item'); el0.style.setProperty('--i', String(itemIndex)); itemIndex += 1; return el0; }

    // The result-specific top of the card. A week with training but no last game
    // (result null) still shows what moved below, so training is never lost.
    if (result) {
      // Kicker: WIN/LOSS tag, week · round · site, Box score.
      var kick = el('div', 'wkc-k');
      if (won === true) kick.appendChild(el('span', 'wtag', 'WIN'));
      else if (loss) kick.appendChild(el('span', 'wtag', 'LOSS'));
      var when = [];
      if (present(result.week)) when.push('Week ' + result.week);
      if (present(result.round_name)) when.push(result.round_name);
      if (result.site === 'home') when.push('Home');
      else if (result.site === 'away') when.push('Away');
      kick.appendChild(el('span', 'wkc-when', when.join(' · ')));
      var boxUrl = (result.box_score && present(result.box_score.path))
        ? href(result.box_score.path, result.box_score.params) : '';
      if (boxUrl) {
        var box = el('a', 'lnk', 'Box score');
        box.href = boxUrl;
        // `data-return`: GOBNav adds return_url on the click, which marks the box score
        // as a read and brings its Back here. Without it the page treats last week's
        // game as a finished flow and returns to the Office. A plain link, so that
        // GOBNav's own click handling runs; the listener only plays the sound.
        box.setAttribute('data-return', '');
        box.addEventListener('click', function (event) {
          if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) return;
          clickTiny();
        });
        kick.appendChild(box);
      }
      node.appendChild(kick);

      // Scoreboard: your team always on top.
      var mine = userSide(result);
      var theirs = otherSide(result);
      var sb = el('div', 'sb2');
      sb.appendChild(scoreRow(mine && mine.name, userRank, mine && mine.score, won === true, countScores));
      sb.appendChild(scoreRow(theirs && theirs.name, result.opponent_rank, theirs && theirs.score, loss, countScores));
      node.appendChild(sb);

      // Headline (only when the server carries one).
      if (present(result.headline)) {
        var hl = el('a', 'wkc-hl', result.headline);
        if (boxUrl) {
          // The same read link as "Box score" above: `data-return`, GOBNav handles the
          // click, and the listener only plays the sound.
          hl.href = boxUrl;
          hl.setAttribute('data-return', '');
          hl.addEventListener('click', function (event) {
            if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) return;
            clickTiny();
          });
        }
        node.appendChild(markItem(hl));
      }

      // Player of the Game (win) / Team leader (loss).
      var leader = result.leader;
      if (leader && (present(leader.name) || leader.stats)) {
        var pg = el('div', 'pg2');
        pg.appendChild(portrait(leader.player_id, leader.name));
        var idb = el('div', 'pg2-id');
        if (result.leader_role === 'potg') idb.appendChild(el('span', 'eyebrow', 'Player of the Game'));
        else if (result.leader_role === 'team_leader') idb.appendChild(el('span', 'eyebrow', 'Team leader'));
        var nameEl = linkName('nm', leader.name, playerHref(leader.player_id));
        if (nameEl) idb.appendChild(nameEl);
        var stats = leader.stats || {};
        var line = el('div', 'pg2-l');
        [['pts', 'PTS'], ['reb', 'REB'], ['ast', 'AST']].forEach(function (pair) {
          if (!present(stats[pair[0]])) return;
          var cell = el('div');
          cell.appendChild(el('b', '', String(stats[pair[0]])));
          cell.appendChild(el('span', '', pair[1]));
          line.appendChild(cell);
        });
        if (line.childNodes.length) idb.appendChild(line);
        pg.appendChild(idb);
        node.appendChild(markItem(pg));
      }
    }

    // Four badges: National, Conference, Record, Streak.
    var moved = digest.what_moved || {};
    var rank = moved.national_rank || {};
    var conf = moved.conference_standing || {};
    var badges = el('div', 'bdgs');
    [
      weeklyBadge('National', present(rank.now) ? '#' + rank.now : null, rank.delta),
      weeklyBadge('Conference', present(conf.now) ? ordinal(conf.now) : null, conf.delta),
      weeklyBadge('Record', winsLosses(moved.record) || null, null),
      weeklyBadge('Streak', present(moved.streak) ? String(moved.streak) : null, null)
    ].forEach(function (b) { if (b) badges.appendChild(b); });
    if (badges.childNodes.length) node.appendChild(markItem(badges));

    // Training: capped players; the gold key shows only when the server flagged an
    // exceptional gain on a shown chip.
    var rows = groupAttributes(moved.attribute_changes);
    var shown = rows.slice(0, weeklyPlayerCap());
    if (shown.length) {
      var tr = el('div', 'wkc-tr');
      var trh = el('div', 'wkc-tr-h');
      trh.appendChild(el('span', 'sub-h', 'Training · this week'));
      var anyXg = shown.some(function (p) { return p.chips.some(function (c) { return c.exceptional; }); });
      if (anyXg) trh.appendChild(el('span', 'xg-key', 'Exceptional gain'));
      tr.appendChild(trh);
      shown.forEach(function (player) {
        var gn = el('div', 'gn');
        if (present(player.id)) gn.dataset.playerId = player.id;
        var who = linkName('nm', player.name, playerHref(player.id));
        gn.appendChild(who || el('span', 'nm', player.name));
        var chips = el('div', 'gn-c');
        player.chips.forEach(function (change) { chips.appendChild(gainChip(change)); });
        gn.appendChild(chips);
        tr.appendChild(gn);
      });
      node.appendChild(markItem(tr));
    }

    // Folded moment(s).
    var also = weeklyAlso(digest);
    if (also) { markItem(also); node.appendChild(also); }

    // All changes → training report.
    if (rows.length) {
      var foot = el('div', 'wkc-f');
      var allUrl = trainingReportHref(digest);
      var all = el('a', 'lnk', 'All changes');
      all.href = allUrl;
      all.dataset.officeLink = 'training-report';
      bindGo(all, allUrl);
      foot.appendChild(all);
      node.appendChild(foot);
    }

    return node.childNodes.length ? node : null;
  }

  function wireDetail(event) {
    if (present(event.event_detail)) return String(event.event_detail);
    if (present(event.event_text)) return String(event.event_text);
    return '';
  }

  function wireRow(event, index) {
    if (!event) return null;
    var detail = wireDetail(event);
    if (!present(event.recruit) && !detail) return null;
    var url = recruitingHref();
    var row = el('a', 'wr ar-item');
    row.style.setProperty('--i', String(index));
    row.href = url;
    bindGo(row, url);
    if (present(event.direction) && event.direction !== 'flat') row.classList.add(event.direction === 'down' ? 'dn' : 'up');
    var body = el('span', 'wr-b');
    var line = el('span', 'wr-1');
    if (present(event.recruit)) line.appendChild(el('span', 'nm', event.recruit));
    if (present(event.position)) line.appendChild(el('span', 'wr-m', event.position));
    body.appendChild(line);
    body.appendChild(el('span', 'wr-2', detail));
    row.appendChild(body);
    if (event.direction === 'up' || event.direction === 'down') {
      row.appendChild(el('span', 'wr-tag', event.direction === 'up' ? '▲' : '▼'));
    }
    return row;
  }

  function recruitKey(event) {
    if (!event) return '';
    if (present(event.recruit_id)) return 'id:' + event.recruit_id;
    if (present(event.recruit)) return 'name:' + event.recruit;
    return '';
  }

  function latestRecruitEvents(events) {
    var order = [];
    var map = {};
    (Array.isArray(events) ? events : []).forEach(function (event) {
      var key = recruitKey(event);
      if (!key) return;
      var seen = order.indexOf(key);
      if (seen !== -1) order.splice(seen, 1);
      order.push(key);
      map[key] = event;
    });
    return order.map(function (key) { return map[key]; });
  }

  function recruitCap() {
    return largeDensity() ? 12 : 8;
  }

  function wireCard(wire, oneLine, index) {
    var events = latestRecruitEvents(wire && wire.events);
    var cap = recruitCap();
    if (events.length > cap) events = events.slice(events.length - cap);
    var node = card('office-wire', index);
    var rows = [];
    if (!oneLine) {
      events.forEach(function (event, eventIndex) {
        var row = wireRow(event, eventIndex);
        if (!row) return;
        var key = recruitKey(event);
        if (key) row.dataset.recruitKey = key;
        rows.push(row);
      });
    }
    rows.forEach(function (row) { node.appendChild(row); });
    if (!rows.length) {
      // Week 1 (the one-line wire): before a lean has moved there is nothing to report.
      var line = (oneLine && wire && present(wire.status))
        ? wire.status
        : (oneLine ? 'No preseason leans' : 'No recruiting movement this week');
      node.appendChild(el('p', 'wr-empty', line));
    }
    return node;
  }

  // ---- Week 1 of every season: the season preview (BackEnd/utils/season_preview.py) ----------
  // Every section is built from one payload, so it paints whole or not at all. The lists
  // (.office-list) share the signing-class card's rules: two-line rows, grade on the right.

  function listOf(value) {
    return Array.isArray(value) ? value.filter(Boolean) : [];
  }

  function titledCard(className, index, title, meta) {
    var node = card(className, index);
    var head = el('div', 'card-h');
    head.appendChild(el('h3', '', title));
    if (present(meta)) head.appendChild(el('span', 'meta', meta));
    node.appendChild(head);
    return node;
  }

  // RT as a letter in the canonical ramp (rtBucket.js), the same one the roster paints.
  function rtNode(value) {
    var letters = rtLetters(value);
    if (!letters) return null;
    var cls = (typeof global.getRtBucketClass === 'function' && isFinite(Number(value)))
      ? global.getRtBucketClass(Number(value))
      : rtColorClass(letters);
    return el('b', 'tdig ' + cls, letters);
  }

  function gradeCell(value) {
    var grade = el('span', 'sg-rt');
    var node = rtNode(value);
    if (node) grade.appendChild(node);
    return grade;
  }

  function heightText(inches) {
    var n = Number(inches);
    if (!isFinite(n) || n <= 0) return '';
    return Math.floor(n / 12) + '′' + (n % 12) + '″';
  }

  // One two-line row: [tag] name + small label / second line ............ grade
  function personRow(opts) {
    var row = el(opts.url ? 'a' : 'div', 'wr sg-c' + (opts.mine ? ' me' : ''));
    if (opts.url) {
      row.href = opts.url;
      bindGo(row, opts.url);
    }
    if (present(opts.tag)) row.appendChild(el('span', 'wr-k', opts.tag));
    if (opts.portrait) row.appendChild(opts.portrait);
    var body = el('span', 'wr-b');
    var line = el('span', 'wr-1');
    line.appendChild(el('span', 'nm', opts.name));
    if (present(opts.label)) line.appendChild(el('span', 'wr-m', opts.label));
    body.appendChild(line);
    if (present(opts.detail)) body.appendChild(el('span', 'wr-2', opts.detail));
    row.appendChild(body);
    if (opts.right) row.appendChild(opts.right);
    return row;
  }

  function rankingsCard(preview, index) {
    var ranks = preview && preview.rankings;
    if (!ranks) return null;
    var node = titledCard('sp-card office-ranks', index, 'Rankings');
    [['Conference', ranks.conference], ['Region', ranks.region], ['National', ranks.national]].forEach(function (pair) {
      var place = pair[1];
      if (!place || !present(place.rank) || !present(place.of)) return;
      var row = el('div', 'ptw');
      row.appendChild(el('span', 'nm', pair[0]));
      row.appendChild(el('span', 'ptw-r', ''));
      row.appendChild(el('b', '', String(place.rank)));
      row.appendChild(el('em', '', 'of ' + place.of));
      node.appendChild(row);
    });
    if (!node.querySelector('.ptw')) return null;
    // Last season, as one quiet line at the bottom: "Last season: 18–8, lost in the Region
    // semifinal." Season 1 has no last season, so the card ends at the rows.
    var last = preview.outlook && preview.outlook.last_season;
    if (last && present(last.wins) && present(last.losses)) {
      node.appendChild(el('p', 'rk-last', 'Last season: ' + last.wins + '\u2013' + last.losses
        + (present(last.finish) ? ', ' + last.finish : '') + '.'));
    }
    return node;
  }

  // The roster's columns, in the roster's order: Player, RT, Pos, Yr, Ht, Wt.
  function keyPlayersCard(preview, index) {
    var rows = listOf(preview && preview.key_players).filter(function (row) { return present(row.name); });
    if (!rows.length) return null;
    var node = titledCard('office-tb office-kp', index, 'Key Players');
    var head = el('div', 'st-r st-hd');
    ['Player', 'RT', 'Pos', 'Yr', 'Ht', 'Wt'].forEach(function (label) { head.appendChild(el('span', '', label)); });
    node.appendChild(head);
    rows.forEach(function (row) {
      var line = el('div', 'st-r');
      var name = el('span', 'st-n');
      name.appendChild(linkName('st-nm', row.name, playerHref(row.player_id)));
      line.appendChild(name);
      var rt = el('span', 'tb-rt');
      var grade = rtNode(row.rt);
      if (grade) rt.appendChild(grade);
      line.appendChild(rt);
      line.appendChild(el('span', 'tb-c', present(row.pos) ? String(row.pos) : ''));
      line.appendChild(el('span', 'tb-c', present(row.year) ? String(row.year) : ''));
      line.appendChild(el('span', 'tb-c', heightText(row.height)));
      line.appendChild(el('span', 'tb-c', present(row.weight) ? String(row.weight) : ''));
      node.appendChild(line);
    });
    return node;
  }

  function plural(count, one, many) {
    return count + ' ' + (Number(count) === 1 ? one : many);
  }

  function newcomersCard(preview, index) {
    var block = preview && preview.newcomers;
    var rows = listOf(block && block.players).filter(function (row) { return present(row.name); });
    if (!rows.length) return null;
    var node = titledCard('office-list office-new', index, 'Newcomers');
    rows.forEach(function (row) {
      node.appendChild(personRow({
        name: row.name, label: row.pos, url: playerHref(row.player_id), right: gradeCell(row.rt)
      }));
    });
    var parts = [];
    if (present(block.returning)) parts.push('Returning ' + block.returning);
    if (present(block.lost_seniors)) parts.push('Lost ' + plural(block.lost_seniors, 'senior', 'seniors'));
    if (present(block.newcomers)) parts.push(plural(block.newcomers, 'newcomer', 'newcomers'));
    if (parts.length) node.appendChild(el('p', 'nc-sum', parts.join(' · ')));
    return node;
  }

  function allAmericansCard(preview, index) {
    var rows = listOf(preview && preview.all_americans).filter(function (row) { return present(row.name); });
    if (!rows.length) return null;
    var node = titledCard('office-list office-aa', index, 'Preseason All-Americans', 'First team');
    rows.forEach(function (row) {
      node.appendChild(personRow({
        tag: row.position, name: row.name, detail: row.team_name, mine: !!row.is_user,
        // The player's headshot: square with a small corner, the silhouette on a miss.
        portrait: portrait(row.player_id, row.name, 'av aa-pt'),
        url: playerHref(row.player_id), right: gradeCell(row.rt)
      }));
    });
    return node;
  }

  function circleCard(preview, index) {
    var rows = listOf(preview && preview.circle_these).filter(function (row) { return present(row.opponent); });
    if (!rows.length) return null;
    var node = titledCard('office-list office-circle', index, 'Circle these');
    rows.forEach(function (row) {
      var rank = el('span', 'sg-rt');
      if (present(row.rank)) rank.appendChild(el('b', 'tdig', '#' + row.rank));
      node.appendChild(personRow({
        tag: 'Wk ' + row.week, name: row.opponent,
        label: row.site === 'away' ? 'Away' : (row.site === 'home' ? 'Home' : ''),
        url: teamHref(row.opponent_team_id), right: rank
      }));
    });
    return node;
  }

  function walkOnsCard(preview, index) {
    var rows = listOf(preview && preview.walk_ons).filter(function (row) { return present(row.name); });
    var node = titledCard('office-list office-walk', index, 'Walk-ons', rows.length ? String(rows.length) : '');
    if (!rows.length) {
      node.appendChild(el('p', 'wr-empty', 'No walk-ons'));
      return node;
    }
    rows.forEach(function (row) {
      node.appendChild(personRow({
        name: row.name, label: [row.pos, row.year].filter(present).join(' · '),
        url: playerHref(row.player_id), right: gradeCell(row.rt)
      }));
    });
    return node;
  }

  // One labelled fact on a recruit's second line: a quiet label, then the value as it was.
  function recruitFact(label, value) {
    var fact = el('span', 'rc-f');
    fact.appendChild(el('i', 'rc-k', label + ':'));
    fact.appendChild(document.createTextNode(' '));
    fact.appendChild(value);
    return fact;
  }

  // One recruit, the same on every recruiting list of the Office: the name on top; under
  // it "Pos: C  RT: C  YR: JH", in that order (Jamie, 2026-10-03). A fact the server did
  // not send is left out, label and all. The right-hand column is the list's own (who he
  // leans to, or the points the coach put on him).
  function recruitRow(row, right, mine) {
    var url = recruitingHref();
    var node = el('a', 'wr sg-c rc-row' + (mine ? ' me' : ''));
    node.href = url;
    bindGo(node, url);
    var body = el('span', 'wr-b');
    var line = el('span', 'wr-1');
    line.appendChild(el('span', 'nm', row.name));
    body.appendChild(line);
    var facts = el('span', 'wr-2 rc-facts');
    if (present(row.position)) facts.appendChild(recruitFact('Pos', el('span', 'rc-pos', row.position)));
    var grade = rtNode(row.rt);
    if (grade) facts.appendChild(recruitFact('RT', grade));
    if (present(row.year)) facts.appendChild(recruitFact('YR', el('span', 'rc-yr', row.year)));
    if (facts.childNodes.length) body.appendChild(facts);
    node.appendChild(body);
    if (right) node.appendChild(right);
    return node;
  }

  function leanCell(row) {
    var has = present(row.lean_team_name);
    return el('span', 'rc-lean' + (has ? '' : ' is-none'), has ? String(row.lean_team_name) : 'No lean');
  }

  // Top or Watchlist: remembered for the session (a tab's sessionStorage), Top by default.
  var RECRUIT_LIST_KEY = 'gob-office-recruits-list';
  function recruitListChoice() {
    try {
      return global.sessionStorage.getItem(RECRUIT_LIST_KEY) === 'watchlist' ? 'watchlist' : 'top';
    } catch (err) {
      return 'top';
    }
  }
  function rememberRecruitList(which) {
    try { global.sessionStorage.setItem(RECRUIT_LIST_KEY, which); } catch (err) { /* not remembered */ }
  }

  // All season until Signing Day. Top: the region's five best and who leads for each.
  // Watchlist: the five best the coach is watching, from any region.
  // The Watchlist side exists only when the server sent a `watchlist` block. A server from
  // before the block (the site can deploy ahead of it) sends none: the card is then the
  // Top list alone, and never says the coach's watchlist is empty when it was not read.
  function topRecruitsCard(top, index) {
    if (!top) return null;
    var watchSent = !!top.watchlist && Array.isArray(top.watchlist.rows);
    var lists = {
      top: listOf(top.rows).filter(function (row) { return present(row.name); }),
      watchlist: watchSent ? top.watchlist.rows.filter(function (row) { return present(row.name); }) : []
    };
    var node = card('office-list office-top', index);
    var head = el('div', 'card-h');
    var title = el('h3', '', 'Top Recruits');
    head.appendChild(title);
    // The app's segment control (.stats-toggle), right-aligned in the title row.
    var seg = el('div', 'stats-toggle office-seg');
    seg.setAttribute('role', 'group');
    seg.setAttribute('aria-label', 'Recruit list');
    var buttons = {};
    (watchSent ? [['top', 'Top'], ['watchlist', 'Watchlist']] : []).forEach(function (pair) {
      var button = el('button', '', pair[1]);
      button.type = 'button';
      button.dataset.value = pair[0];
      // A choice, not a navigation: the delegated data-sfx hook gives it the select tick.
      button.setAttribute('data-sfx', 'SFX_SELECT');
      button.addEventListener('click', function () {
        if (node.dataset.recruitList === pair[0]) return;
        rememberRecruitList(pair[0]);
        paint(pair[0]);
      });
      buttons[pair[0]] = button;
      seg.appendChild(button);
    });
    if (watchSent) head.appendChild(seg);
    node.appendChild(head);
    node.dataset.watchlist = watchSent ? 'sent' : 'not-sent';

    function paint(which) {
      node.dataset.recruitList = which;
      // The region belongs to the Top list only; the watchlist is from every region.
      if (which === 'watchlist') {
        title.textContent = 'Your Watchlist';
      } else {
        title.textContent = present(top.region)
          ? 'Top Recruits (Region ' + top.region + ')'
          : 'Top Recruits';
      }
      Object.keys(buttons).forEach(function (key) {
        buttons[key].classList.toggle('on', key === which);
        buttons[key].setAttribute('aria-pressed', key === which ? 'true' : 'false');
      });
      while (head.nextSibling) node.removeChild(head.nextSibling);
      var rows = lists[which];
      if (!rows.length) {
        node.appendChild(el('p', 'wr-empty', which === 'watchlist'
          ? 'Hey Coach, add players to your watchlist'
          : 'No recruits in your region yet'));
        return;
      }
      rows.forEach(function (row) {
        node.appendChild(recruitRow(row, leanCell(row), !!row.lean_is_user));
      });
    }

    paint(watchSent ? recruitListChoice() : 'top');
    return node;
  }

  // Week 35, once the Orders list is in and until Signing Day runs: every recruit the
  // coach put points on, most points first (the server's order).
  function ordersCard(signing, index) {
    if (!signing || !signing.orders_submitted) return null;
    var rows = listOf(signing.orders).filter(function (row) { return present(row.name); });
    if (!rows.length) return null;
    var node = titledCard('office-list office-orders', index, 'Your Orders');
    rows.forEach(function (row) {
      var points = el('span', 'rc-pts');
      points.appendChild(el('b', 'tdig', String(row.points)));
      points.appendChild(el('i', '', Number(row.points) === 1 ? 'pt' : 'pts'));
      node.appendChild(recruitRow(row, points, false));
    });
    return node;
  }

  // The user's conference by preseason national rank, in the standings card's rows.
  function preseasonRankingsCard(table, index) {
    var rows = listOf(table && table.rows);
    if (!rows.length) return null;
    var node = card('office-st office-pre', index);
    var head = el('div', 'card-h');
    head.appendChild(el('h3', '', 'Preseason National Rankings'));
    var moreUrl = viewHref({ tab: 'rankings-view' }, '/franchise-command-center.html', { tab: 'rankings-view' });
    var more = el('a', 'lnk st-more', 'Full rankings');
    more.href = moreUrl;
    bindGo(more, moreUrl);
    head.appendChild(more);
    node.appendChild(head);
    var labels = el('div', 'st-r st-hd');
    labels.appendChild(el('span', '', 'Natl'));
    labels.appendChild(el('span', '', 'Team'));
    labels.appendChild(el('span', 'st-wl', ''));
    node.appendChild(labels);
    rows.forEach(function (row) {
      var line = el('div', 'st-r' + (row.is_user ? ' me' : ''));
      line.dataset.teamId = row.team_id || '';
      line.appendChild(el('span', 'st-pos', present(row.national_rank) ? String(row.national_rank) : ''));
      var team = el('span', 'st-n');
      var mark = standingsMark(row.team_name);
      if (mark) team.appendChild(mark);
      team.appendChild(el('span', 'st-nm', present(row.team_name) ? String(row.team_name) : ''));
      line.appendChild(team);
      line.appendChild(el('span', 'st-wl', ''));
      node.appendChild(line);
    });
    node.dataset.standingsTotal = String(rows.length);
    node.dataset.standingsShown = String(rows.length);
    if (present(table.conference)) node.dataset.conference = String(table.conference);
    return node;
  }

  function weeklyHref(item) {
    var raw = item && item.href;
    if (!present(raw)) return '';
    var current = new URLSearchParams(global.location.search);
    var url;
    try { url = new URL(raw, 'http://local.invalid'); } catch (err) { return String(raw); }
    if (current.get('franchise_id') && !url.searchParams.get('franchise_id')) {
      url.searchParams.set('franchise_id', current.get('franchise_id'));
    }
    var teamId = userTeamId(current);
    if (teamId && !url.searchParams.get('team_id')) url.searchParams.set('team_id', teamId);
    return url.pathname + (url.search || '');
  }

  function nextCard(game, digest, index) {
    if (!game) return null;
    var tournament = digest.state === 'tournament';
    var node = card('office-next' + (tournament ? ' tier' : ''), index);
    if (tournament && global.GOBTierEmblem && global.GOBTierEmblem.tierForWeek) {
      var tier = global.GOBTierEmblem.tierForWeek(game.week);
      var tokens = tier && global.GOBTierEmblem.TIER_TOKENS ? global.GOBTierEmblem.TIER_TOKENS[tier] : null;
      if (tokens) {
        node.style.setProperty('--tier-metal', tokens.metal);
        node.style.setProperty('--tier-metal-hi', tokens.metalHi);
        if (global.GOBTierEmblem.injectCss) global.GOBTierEmblem.injectCss();
        var band = el('div', 'tn-band');
        if (present(game.round_name)) band.appendChild(el('div', 'tn-round', game.round_name));
        var lock = el('div', 'tn-lock');
        lock.innerHTML = global.GOBTierEmblem.renderLockup({
          tier: tier,
          size: global.GOBTierEmblem.EMBLEM_SIZING.fccGameCardHeader.emblem,
          l1: global.GOBTierEmblem.EMBLEM_SIZING.fccGameCardHeader.labelL1,
          l2: global.GOBTierEmblem.EMBLEM_SIZING.fccGameCardHeader.labelL2,
          variant: 'inline'
        });
        band.appendChild(lock);
        node.appendChild(band);
      } else if (present(game.round_name)) {
        node.appendChild(el('div', 'tn-round', game.round_name));
      }
    }
    if (digest.state === 'first_week') node.appendChild(el('div', 'sub-h nx-open', 'Season Opener'));
    var top = el('div', 'nx-top');
    var main = el('div', 'nx-m');
    var names = el('div');
    var site = game.site === 'away' ? 'AT' : (game.site === 'home' ? 'VS' : '');
    if (site) names.appendChild(el('span', 'nx-at', site));
    var oppUrl = teamHref(game.opponent_team_id);
    if (present(game.opponent)) {
      var opp = el(oppUrl ? 'a' : 'span', 'nx-name');
      if (present(game.rank)) opp.appendChild(el('span', 'nx-rank', game.rank + '. '));
      opp.appendChild(document.createTextNode(game.opponent));
      if (oppUrl) {
        opp.href = oppUrl;
        bindGo(opp, oppUrl);
      }
      names.appendChild(opp);
    }
    var sub = [];
    var opener = digest.state === 'first_week';
    var recordLine = winsLosses(game.record);
    var confLine = conferenceLabel(game.conference);
    // Before a game is played the record says nothing: the opener shows the opponent's
    // preseason rank and, when they met last season, how that went.
    if (opener) {
      if (present(game.rank)) sub.push('Preseason #' + game.rank);
      if (confLine) sub.push('Conference ' + confLine);
      var met = game.last_meeting;
      if (met && present(met.user_score) && present(met.opp_score)) {
        sub.push('Last season: ' + (met.won ? 'W ' : 'L ') + met.user_score + '\u2013' + met.opp_score);
      }
    } else if (recordLine) sub.push(recordLine);
    if (confLine && !opener) {
      var place = 'Conference ' + confLine;
      if (present(game.conference_position) && present(game.conference_size)) {
        place += ' (' + game.conference_position + ' of ' + game.conference_size + ')';
      }
      sub.push(place);
    }
    if (sub.length) names.appendChild(el('span', 'nx-sub', sub.join(' · ')));
    if (names.childNodes.length) main.appendChild(names);
    if (main.childNodes.length) top.appendChild(main);
    if (top.childNodes.length) node.appendChild(top);

    function watch(row, label, unit) {
      if (!row || !present(row.name)) return;
      var line = el('div', 'ptw');
      line.appendChild(el('span', 'nm', row.name));
      line.appendChild(el('span', 'ptw-r', label));
      if (present(row.average)) line.appendChild(el('b', '', String(row.average)));
      line.appendChild(el('em', '', unit));
      node.appendChild(line);
    }
    watch(game.top_scorer, 'Top scorer', 'PPG');
    watch(game.top_rebounder, 'Top rebounder', 'RPG');
    return node.childNodes.length ? node : null;
  }

  // The signed-scale team attributes: the only ones "Moved most" may rank.
  var MOVED_MOST = {
    offensive_efficiency: true, defensive_efficiency: true, discipline: true, fb_efficiency: true,
    fb_opp_modifier: true, fight: true, pt_opp_modifier: true, pt_efficiency: true
  };

  function snapshotCard(snap, index) {
    if (!snap) return null;
    var node = card('office-snap', index);
    var head = el('div', 'card-h');
    head.appendChild(el('h3', '', 'Team snapshot'));
    node.appendChild(head);
    var chemistry = snap.chemistry || {};
    if (present(chemistry.value) && present(chemistry.max) && Number(chemistry.max) > 0) {
      var chemValue = Number(chemistry.value);
      var band = chemValue <= 8 ? 'red' : (chemValue <= 16 ? 'yellow' : 'green');
      var row = el('div', 'sn-row');
      row.appendChild(el('span', 'sn-l', 'Chemistry'));
      row.appendChild(el('span', 'sn-v', chemistry.value + '/' + chemistry.max));
      node.appendChild(row);
      var meter = el('div', 'meter chem is-' + band);
      meter.dataset.chemBand = band;
      var fill = el('i');
      var pct = Math.max(0, Math.min(100, (chemValue / Number(chemistry.max)) * 100));
      fill.style.width = pct + '%';
      meter.appendChild(fill);
      node.appendChild(meter);
    }
    var attitude = snap.attitude || {};
    var buckets = Array.isArray(attitude.buckets) ? attitude.buckets : [];
    if (buckets.length) {
      node.appendChild(el('div', 'sub-h', 'Attitude'));
      var spread = el('div', 'att');
      buckets.forEach(function (bucket) {
        if (!bucket) return;
        var count = Number(bucket.count) || 0;
        var col = el('div', 'att-col');
        col.dataset.bucket = bucket.id || '';
        col.appendChild(el('span', 'att-emoji', EMOJI[bucket.id] || ''));
        col.appendChild(el('span', 'att-n', String(count)));
        var bar = el('span', 'att-bar');
        var share = el('i');
        var width = (Math.min(count, ATTITUDE_BAR_MAX) / ATTITUDE_BAR_MAX) * 100;
        share.style.width = width + '%';
        bar.appendChild(share);
        col.appendChild(bar);
        spread.appendChild(col);
      });
      node.appendChild(spread);
    }
    // "Moved most" ranks only the eight team attributes on the signed scale. Chemistry
    // (its own bar above), Shooting and Rebounding are on other scales, so their movement
    // is not comparable, and Momentum is never shown. The server filters the list
    // (office_digest.MOVED_MOST_KEYS); this is the guard for a payload that did not.
    var moved = (Array.isArray(snap.moved_most) ? snap.moved_most : []).filter(function (row) {
      return row && MOVED_MOST[row.measure] === true;
    });
    node.appendChild(el('div', 'sub-h', 'Team Attributes Moved Most'));
    if (snap.state === 'set_after_camp' || !moved.length) {
      // One quiet line: before camp there is nothing to compare; after it, none of the
      // eight moved. Never a fallback to a measure on another scale.
      // The line stands alone in both states: no trailing dash.
      var line = el('div', 'msr msr-empty');
      line.appendChild(el('span', '', snap.state === 'set_after_camp' ? 'Set after camp' : 'No movement this week'));
      node.appendChild(line);
    } else {
      moved.slice(0, 2).forEach(function (row) {
        if (!present(row.measure)) return;
        var line = el('div', 'msr');
        line.appendChild(el('span', '', labelize(row.measure)));
        if (present(row.value)) line.appendChild(el('b', '', String(row.value)));
        var deltaChip = chip(row.delta, null);
        if (deltaChip) line.appendChild(deltaChip);
        node.appendChild(line);
      });
    }
    return node;
  }

  function signingCard(signing, index, ordersListed) {
    if (!signing) return null;
    var node = card('office-sign', index);
    var head = el('div', 'card-h');
    head.appendChild(el('h3', '', 'Signing Day'));
    node.appendChild(head);
    if (present(signing.points_remaining) && present(signing.points_total)) {
      var points = el('div', 'sg-pts');
      var pv = el('div', 'sg-pv');
      pv.appendChild(el('b', '', String(signing.points_remaining)));
      pv.appendChild(el('i', '', '/ ' + signing.points_total));
      points.appendChild(pv);
      points.appendChild(el('span', 'sn-l', 'Points remaining'));
      node.appendChild(points);
    }
    var pair = el('div', 'sg-2');
    if (present(signing.promises_made)) {
      var promises = el('div', 'mv-cell');
      promises.appendChild(el('span', 'mv-l', 'Promises'));
      promises.appendChild(el('b', '', String(signing.promises_made)));
      pair.appendChild(promises);
    }
    if (present(signing.open_roster_spots)) {
      var spots = el('div', 'mv-cell');
      spots.appendChild(el('span', 'mv-l', 'Open spots'));
      spots.appendChild(el('b', '', String(signing.open_roster_spots)));
      pair.appendChild(spots);
    }
    if (pair.childNodes.length) node.appendChild(pair);
    var targets = (!ordersListed && Array.isArray(signing.targets)) ? signing.targets : [];
    if (targets.length) node.appendChild(el('div', 'sub-h', 'Targets'));
    targets.forEach(function (target) {
      if (!target || !present(target.name)) return;
      var url = recruitingHref();
      var row = el('a', 'wr sg-t');
      row.href = url;
      bindGo(row, url);
      var body = el('span', 'wr-b');
      var line = el('span', 'wr-1');
      line.appendChild(el('span', 'nm', target.name));
      if (present(target.position)) line.appendChild(el('span', 'wr-m', target.position));
      body.appendChild(line);
      var letters = rtLetters(target.rt);
      if (letters) body.appendChild(el('b', 'tdig ' + rtColorClass(letters), letters));
      row.appendChild(body);
      if (present(target.lean_rank)) {
        var lean = '#' + target.lean_rank;
        if (target.direction === 'up') lean = '▲ ' + lean;
        else if (target.direction === 'down') lean = '▼ ' + lean;
        var kind = target.direction === 'up' ? 'up' : (target.direction === 'down' ? 'down' : 'flat');
        row.appendChild(el('span', 'chip ' + kind, lean));
      }
      node.appendChild(row);
    });
    return node;
  }

  // Week 36, after Signing Day has run: every recruit who signed with the
  // program. The rows are the server's (office_digest.signed_class); nothing
  // here is derived.
  function signedClassCard(signed, index) {
    var recruits = Array.isArray(signed && signed.recruits) ? signed.recruits : [];
    var rows = recruits.filter(function (recruit) { return recruit && present(recruit.name); });
    var node = card('office-sign office-class', index);
    var head = el('div', 'card-h');
    head.appendChild(el('h3', '', 'Signing class'));
    if (rows.length) head.appendChild(el('span', 'meta', rows.length + ' signed'));
    node.appendChild(head);
    if (!rows.length) {
      node.appendChild(el('p', 'wr-empty', 'No recruits signed with your program.'));
      return node;
    }
    var url = recruitingHref();
    rows.forEach(function (recruit) {
      var row = el('a', 'wr sg-c');
      row.href = url;
      bindGo(row, url);
      var body = el('span', 'wr-b');
      var line = el('span', 'wr-1');
      line.appendChild(el('span', 'nm', recruit.name));
      if (present(recruit.position)) line.appendChild(el('span', 'wr-m', recruit.position));
      body.appendChild(line);
      if (present(recruit.home_region)) body.appendChild(el('span', 'wr-2', 'Region ' + recruit.home_region));
      row.appendChild(body);
      var now = rtLetters(recruit.rt_now);
      var potential = rtLetters(recruit.rt_potential);
      if (now) {
        var grade = el('span', 'sg-rt');
        grade.appendChild(el('b', 'tdig ' + rtColorClass(now), now));
        if (potential && potential !== now) {
          grade.appendChild(el('i', '', '\u2192'));
          grade.appendChild(el('b', 'tdig ' + rtColorClass(potential), potential));
        }
        row.appendChild(grade);
      }
      node.appendChild(row);
    });
    return node;
  }

  function standingsHref() {
    var current = new URLSearchParams(global.location.search);
    var params = { tab: 'standings-view' };
    if (current.get('franchise_id')) params.franchise_id = current.get('franchise_id');
    var teamId = userTeamId(current);
    if (teamId) params.team_id = teamId;
    return href('/franchise-command-center.html', params);
  }

  // The team's mark as the league tables draw it (logo, or the letter tile).
  function standingsMark(name) {
    var tables = global.GOBTables;
    if (!tables || typeof tables.markHtml !== 'function' || !present(name)) return null;
    var holder = document.createElement('span');
    holder.innerHTML = tables.markHtml(String(name));
    return holder.firstElementChild;
  }

  function standingsRow(row) {
    if (!row) return null;
    var line = el('div', 'st-r' + (row.is_user ? ' me' : ''));
    line.dataset.teamId = row.team_id || '';
    line.appendChild(el('span', 'st-pos', present(row.position) ? String(row.position) : ''));
    var team = el('span', 'st-n');
    var mark = standingsMark(row.team_name);
    if (mark) team.appendChild(mark);
    team.appendChild(el('span', 'st-nm', present(row.team_name) ? String(row.team_name) : ''));
    line.appendChild(team);
    var record = '';
    if (present(row.wins) && present(row.losses)) record = row.wins + '-' + row.losses;
    line.appendChild(el('span', 'st-wl', record));
    return line;
  }

  // Every team of the user's conference, in the server's standings order, at the normal
  // Office row spacing. Never sliced and never tightened to fit: on a short window the
  // Office scrolls instead. "Full standings" is always in the card header.
  function paintStandingsRows(node, rows) {
    node.querySelectorAll('.st-r, .st-more').forEach(function (child) { child.remove(); });
    var head = el('div', 'st-r st-hd');
    head.appendChild(el('span', '', '#'));
    head.appendChild(el('span', '', 'Team'));
    head.appendChild(el('span', 'st-wl', 'W-L'));
    node.appendChild(head);
    rows.forEach(function (row) {
      var line = standingsRow(row);
      if (line) node.appendChild(line);
    });
    var moreUrl = standingsHref();
    var more = el('a', 'lnk st-more', 'Full standings');
    more.href = moreUrl;
    bindGo(more, moreUrl);
    var title = node.querySelector('.card-h');
    if (title) title.appendChild(more);
    else node.appendChild(more);
    node.dataset.standingsShown = String(rows.length);
  }

  function standingsCard(table, index) {
    var rows = table && Array.isArray(table.rows) ? table.rows.filter(Boolean) : [];
    if (!rows.length) return null;
    var node = card('office-st', index);
    var label = conferenceLabel(table.conference);
    var head = el('div', 'card-h');
    head.appendChild(el('h3', '', label ? ('Conference ' + label + ' standings') : 'Conference standings'));
    node.appendChild(head);
    node.dataset.standingsTotal = String(rows.length);
    if (present(table.region)) node.dataset.region = String(table.region);
    if (present(table.conference)) node.dataset.conference = String(table.conference);
    paintStandingsRows(node, rows);
    return node;
  }

  function foldBottom() {
    var main = document.querySelector('html.gob-shell .main') || document.querySelector('.main');
    if (!main) return global.innerHeight;
    return main.getBoundingClientRect().top + main.clientHeight;
  }

  function trimRecruiting(root) {
    var wire = root.querySelector('.office-wire');
    if (!wire) return;
    var guard = 0;
    while (guard < 24) {
      var rows = wire.querySelectorAll(':scope > .wr');
      if (!rows.length) break;
      var last = rows[rows.length - 1];
      if (last.getBoundingClientRect().bottom <= foldBottom() + 0.5) break;
      last.remove();
      guard += 1;
    }
  }

  function paintRail(wire) {
    var btn = document.getElementById('gob-rail-recruiting');
    if (!btn) return;
    var old = btn.querySelector('.inbox-badge');
    if (old) old.remove();
    var badge = btn.querySelector('em.office-rail-count');
    var count = wire && Number(wire.pending_count);
    if (!count) {
      if (badge) badge.remove();
      return;
    }
    if (!badge) {
      badge = el('em', 'office-rail-count');
      btn.appendChild(badge);
    }
    badge.textContent = String(count);
    badge.classList.toggle('urgent', !!(wire && wire.urgent));
  }

  function skeleton() {
    var root = el('div', 'office');
    root.id = 'office-root';
    root.setAttribute('aria-busy', 'true');
    root.appendChild(el('div', 'week-strip office-skel'));
    var grid = el('div', 'office-grid');
    ['01', '02', '03'].forEach(function (index, nth) {
      var titles = ['Since last week', 'This Week', 'Recruiting'];
      var col = column(index, titles[nth], '');
      col.appendChild(el('div', 'card office-skel'));
      grid.appendChild(col);
    });
    root.appendChild(grid);
    return root;
  }

  function render(digest) {
    var root = document.getElementById('office-root');
    if (!root) return;
    paintRail(digest && digest.recruiting_wire);
    if (!digest || !digest.state) {
      root.setAttribute('aria-busy', 'true');
      return;
    }
    var motion = arrivalFor(digest);
    var countScores = motion.arriving && !motion.calm && digest.result && digest.result.user_won === true;
    root.classList.toggle('arriving', motion.arriving);
    root.classList.toggle('calm', motion.calm);
    root.classList.remove('is-todos-open');
    root.setAttribute('data-office-state', digest.state);
    root.setAttribute('aria-busy', 'false');
    root.replaceChildren();

    var userRank = digest.what_moved && digest.what_moved.national_rank
      ? digest.what_moved.national_rank.now
      : null;
    var week1 = digest.state === 'first_week';
    var preview = week1 && digest.season_preview && digest.season_preview.ready !== false
      ? digest.season_preview
      : null;
    var col1 = column('01', week1 ? 'Season Preview' : 'Since last week', '');
    var col2 = column('02', week1 ? 'Opening Week' : 'This Week', '');
    var col3 = column('03', 'Recruiting', '', recruitingHref());
    var first = [];
    var second = [];
    var third = [];
    if (week1) {
      // Week 1 of every season. The opener carries last season's meeting when the preview has it.
      var opener = (preview && preview.opener) || digest.next_game;
      first = preview ? [
        rankingsCard(preview, 2),
        keyPlayersCard(preview, 3),
        newcomersCard(preview, 4),
        allAmericansCard(preview, 5)
      ] : [];
      // No Team snapshot in week 1: before camp it could only say "Set after camp".
      second = [
        nextCard(opener, digest, 2),
        preview ? circleCard(preview, 3) : null,
        (preview && preseasonRankingsCard(preview.preseason_rankings, 4))
          || standingsCard(digest.conference_standings, 4)
      ];
      third = [
        wireCard(digest.recruiting_wire, true, 6),
        preview ? walkOnsCard(preview, 7) : null
      ];
    } else if (digest.state === 'signing_day') {
      first = [sinceLastWeekCard(digest, 1, false, userRank)];
      second = [
        snapshotCard(digest.team_snapshot, 3),
        standingsCard(digest.conference_standings, 4)
      ];
      // Orders submitted: the list of everyone with points sits under the Signing Day
      // card, which then drops its own three "Targets" (the list is all of them).
      var orders = ordersCard(digest.signing_day, 6);
      third = [signingCard(digest.signing_day, 5, !!orders), orders];
    } else {
      first = [sinceLastWeekCard(digest, 1, countScores, userRank)];
      second = [
        nextCard(digest.next_game, digest, 3),
        snapshotCard(digest.team_snapshot, 4),
        standingsCard(digest.conference_standings, 5)
      ];
      third = [wireCard(digest.recruiting_wire, false, 6)];
    }
    // Top Recruits stays all season (the server stops sending it from Signing Day).
    if (digest.top_recruits && digest.state !== 'signing_day') third.push(topRecruitsCard(digest.top_recruits, 8));
    // Once Signing Day has run the recruiting column is the class that signed.
    if (digest.signed_class) third = [signedClassCard(digest.signed_class, 6)];
    // The moment-queue weekly items now fold into the card's Also row / "+N more",
    // so column 2 no longer carries a separate "This week" card.
    first.forEach(function (node) { if (node) col1.appendChild(node); });
    second.forEach(function (node) { if (node) col2.appendChild(node); });
    third.forEach(function (node) { if (node) col3.appendChild(node); });
    var grid = el('div', 'office-grid');
    grid.append(col1, col2, col3);
    var strip = weekStrip(digest);
    root.append(strip, grid);
    tightenStrip(strip);
    function settle() {
      trimRecruiting(root);
    }
    settle();
    if (global.requestAnimationFrame) {
      global.requestAnimationFrame(function () {
        settle();
        global.requestAnimationFrame(settle);
      });
    }
    // The display font (Bebas Neue Pro) loads async and its metrics change card
    // heights, so a settle() during first paint can trim the recruiting wire one row
    // short. Re-fit once the font is actually ready (the real signal, not a timeout).
    var fonts = global.document && global.document.fonts;
    if (fonts && fonts.ready && typeof fonts.ready.then === 'function') {
      fonts.ready.then(function () {
        if (global.document && global.document.contains(root)) settle();
      });
    }
    if (countScores) countUp(root);
    // The win sting plays once per result (first showing), at the cue time when the
    // score lands. It follows the audio settings, so it fires under reduced motion
    // too; a loss is silent. Guarded per key so a re-render doesn't replay it.
    if (motion.firstShowing && digest.result && digest.result.user_won === true) {
      var stingKey = arrivalKey(digest);
      if (!stingPlayed[stingKey]) {
        stingPlayed[stingKey] = true;
        playWinSting();
      }
    }
  }

  function playWinSting() {
    var CUE_MS = 720; // --delay-cue: the score lands
    global.setTimeout(function () {
      import('/js/shared/uiSfx.js').then(function (mod) {
        if (mod && typeof mod.playSfx === 'function') mod.playSfx(mod.STING_WIN);
      }).catch(function () {});
    }, CUE_MS);
  }

  global.GOBOffice = {
    render: render,
    skeleton: skeleton
  };
})(typeof window !== 'undefined' ? window : this);
