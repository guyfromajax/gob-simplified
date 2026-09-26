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
    fb_efficiency: 'Fast Breaks',
    pt_efficiency: 'Press/Traps',
    fight: 'Fight',
    discipline: 'Discipline',
    momentum_score: 'Momentum',
    team_chemistry: 'Team Chemistry',
    fb_opp_modifier: 'Fast Break Defense',
    pt_opp_modifier: 'P/T Offense'
  };

  var EMOJI = {
    em_0_19: '😡',
    em_20_39: '😕',
    em_40_59: '😐',
    em_60_79: '😊',
    em_80_plus: '😎'
  };

  var ARRIVAL_KEY = 'gob-office-arrival';

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

  function go(url) {
    if (!url) return;
    clickTiny();
    if (global.GOBNav && typeof global.GOBNav.go === 'function') global.GOBNav.go(url);
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
    var teamId = current.get('team_id') || current.get('user_team_id');
    if (teamId) params.team_id = teamId;
    return href(path, params);
  }

  function playerHref(playerId) {
    if (!present(playerId)) return '';
    var current = new URLSearchParams(global.location.search);
    var params = { id: playerId };
    if (current.get('franchise_id')) {
      params.mode = 'franchise';
      params.franchise_id = current.get('franchise_id');
    }
    return href('/player-detail.html', params);
  }

  function teamHref(teamId) {
    if (!present(teamId)) return '';
    var current = new URLSearchParams(global.location.search);
    var params = { team_id: teamId };
    if (current.get('franchise_id')) params.franchise_id = current.get('franchise_id');
    return href('/team-roster-view.html', params);
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
    var url = '';
    if (present(playerId) && global.API_CONFIG && typeof global.API_CONFIG.getPlayerImageUrl === 'function') {
      url = global.API_CONFIG.getPlayerImageUrl(playerId, { size: 'card' });
    }
    if (url) {
      var img = el('img');
      img.alt = '';
      img.src = url;
      img.addEventListener('error', function () {
        img.remove();
        if (letters) box.appendChild(el('span', 'office-initials', letters));
      });
      box.appendChild(img);
    } else if (letters) {
      box.appendChild(el('span', 'office-initials', letters));
    }
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

  function arrivalFor(digest) {
    var result = digest && digest.result;
    if (!result || reducedMotion()) return { arriving: false, calm: false };
    var key = [digest.state, result.week, result.home_score, result.away_score, result.opponent_team_id].join(':');
    var seen = '';
    try { seen = sessionStorage.getItem(ARRIVAL_KEY) || ''; } catch (err) {}
    if (seen === key) return { arriving: false, calm: false };
    try { sessionStorage.setItem(ARRIVAL_KEY, key); } catch (err) {}
    var lost = result.user_won === false || digest.state === 'loss';
    return { arriving: true, calm: lost };
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

  function playerCap() {
    return document.documentElement.classList.contains('gob-1920') ? 8 : 5;
  }

  function groupAttributes(changes) {
    var order = [];
    var map = {};
    (Array.isArray(changes) ? changes : []).forEach(function (change) {
      if (!change || !present(change.from) || !present(change.to)) return;
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
        delta: delta
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

  function attrChip(change) {
    var parts = attrParts(change.attribute);
    var node = el('span', 'attr-chip');
    node.title = parts.title;
    node.appendChild(el('b', 'attr-code', parts.code));
    node.appendChild(el('b', 'tdig ' + digitClass(change.to), String(change.to)));
    node.appendChild(el('i', 'arr ' + (change.delta > 0 ? 'up' : 'down'), change.delta > 0 ? '▲' : '▼'));
    return node;
  }

  function trainingReportHref(digest) {
    var current = new URLSearchParams(global.location.search);
    var params = { mode: 'franchise', from: 'office' };
    if (current.get('franchise_id')) params.franchise_id = current.get('franchise_id');
    var teamId = current.get('team_id') || current.get('user_team_id');
    if (teamId) params.team_id = teamId;
    var week = digest && digest.result && digest.result.week;
    if (!present(week) && digest && digest.next_game) week = digest.next_game.week;
    if (present(week)) params.week = week;
    return href('/training-report.html', params);
  }

  function weekStrip(digest) {
    var list = Array.isArray(digest && digest.todos) ? digest.todos : [];
    var nextIndex = -1;
    list.forEach(function (todo, index) {
      if (nextIndex === -1 && todo && !todo.done && todo.required !== false) nextIndex = index;
    });
    var strip = el('div', 'week-strip' + (list.length > 6 ? ' is-tight' : ''));
    var track = el('div', 'week-track');
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
      var row = el('button', classes);
      row.type = 'button';
      row.dataset.officeTodo = todo.id || '';
      row.dataset.stepState = state;
      if (todo.is_advance_action && !todo.done) row.dataset.advanceMirror = '1';
      var dot = el('span', 'wk-dot');
      if (todo.done) dot.appendChild(checkMark());
      row.appendChild(dot);
      var copy = (todo.is_advance_action && !todo.done)
        ? advanceLabel()
        : (TODO_COPY[todo.label_key] || labelize(todo.label_key));
      row.appendChild(el('span', 'td-l', copy));
      if (!todo.done && todo.gates_advance && !todo.is_advance_action) {
        row.appendChild(el('span', 'td-gate', 'BLOCKS ADVANCE'));
      }
      row.addEventListener('click', function () {
        if (!todo.done && todo.is_advance_action) {
          var play = document.getElementById('play-now');
          if (play) play.click();
          return;
        }
        if (present(todo.route)) go(franchiseHref(todo.route));
      });
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

  function resultCard(result, countScores, index, userRank) {
    if (!result) return null;
    var mine = userSide(result);
    var theirs = otherSide(result);
    var loss = result.user_won === false;
    var node = card('office-res' + (loss ? ' is-loss' : ''), index);
    var kicker = el('div', 'res-k');
    var when = [];
    if (present(result.week)) when.push('Week ' + result.week);
    if (present(result.round_name)) when.push(result.round_name);
    if (result.site === 'home') when.push('Home');
    else if (result.site === 'away') when.push('Away');
    if (when.length) kicker.appendChild(el('span', 'res-when', when.join(' · ')));
    if (result.user_won === true) kicker.appendChild(el('span', 'wl win', 'WIN'));
    else if (result.user_won === false) kicker.appendChild(el('span', 'wl loss', 'LOSS'));
    if (kicker.childNodes.length) node.appendChild(kicker);

    var score = el('div', 'res-score');
    if (mine && present(mine.name)) {
      var left = el('a', 'rs-team');
      var leftUrl = teamHref(mine.id);
      if (leftUrl) {
        left.href = leftUrl;
        bindGo(left, leftUrl);
      }
      var userName = el('span', 'rs-n');
      if (present(userRank)) userName.appendChild(el('em', '', '#' + userRank));
      userName.appendChild(document.createTextNode(mine.name));
      left.appendChild(userName);
      score.appendChild(left);
    }
    if (mine && present(mine.score)) score.appendChild(scoreNode(mine.score, 'rs-pts', countScores));
    if (mine && theirs && present(mine.score) && present(theirs.score)) score.appendChild(el('span', 'rs-dash', '–'));
    if (theirs && present(theirs.score)) score.appendChild(scoreNode(theirs.score, 'rs-pts them', countScores));
    if (theirs && present(theirs.name)) {
      var right = el('a', 'rs-team r');
      var rightUrl = teamHref(theirs.id || result.opponent_team_id);
      if (rightUrl) {
        right.href = rightUrl;
        bindGo(right, rightUrl);
      }
      var name = el('span', 'rs-n');
      if (present(result.opponent_rank)) name.appendChild(el('em', '', '#' + result.opponent_rank));
      name.appendChild(document.createTextNode(theirs.name));
      right.appendChild(name);
      score.appendChild(right);
    }
    if (score.childNodes.length) node.appendChild(score);

    if (present(result.headline)) {
      var headline = el('p', 'res-hl', result.headline);
      node.appendChild(headline);
    }

    var leader = result.leader;
    if (leader && (present(leader.name) || leader.stats)) {
      var potg = el('div', 'potg');
      potg.appendChild(portrait(leader.player_id, leader.name));
      var id = el('div', 'pg-id');
      var role = result.leader_role;
      if (role === 'potg') id.appendChild(el('span', 'eyebrow', 'Player of the game'));
      else if (role === 'team_leader' && mine && present(mine.name)) {
        id.appendChild(el('span', 'eyebrow', mine.name + ' leader'));
      }
      var playerUrl = playerHref(leader.player_id);
      var player = linkName('nm pg-n', leader.name, playerUrl);
      if (player) id.appendChild(player);
      potg.appendChild(id);
      var stats = leader.stats || {};
      var line = el('div', 'pg-line');
      [['pts', 'PTS'], ['reb', 'REB'], ['ast', 'AST']].forEach(function (pair) {
        if (!present(stats[pair[0]])) return;
        var cell = el('div');
        cell.appendChild(el('b', '', String(stats[pair[0]])));
        cell.appendChild(el('span', '', pair[1]));
        line.appendChild(cell);
      });
      if (line.childNodes.length) potg.appendChild(line);
      node.appendChild(potg);
      var extra = el('div', 'pg-extra');
      if (present(stats.fgm) && present(stats.fga)) {
        var fg = el('div');
        fg.appendChild(el('b', '', stats.fgm + '-' + stats.fga));
        fg.appendChild(el('span', '', 'FG'));
        extra.appendChild(fg);
      }
      if (present(stats.fg3m) && present(stats.fg3a)) {
        var threes = el('div');
        threes.appendChild(el('b', '', stats.fg3m + '-' + stats.fg3a));
        threes.appendChild(el('span', '', '3PT'));
        extra.appendChild(threes);
      }
      if (present(stats.min)) {
        var minutes = wholeMinutes(stats.min);
        if (minutes) {
          var min = el('div');
          min.appendChild(el('b', '', minutes));
          min.appendChild(el('span', '', 'MIN'));
          extra.appendChild(min);
        }
      }
      if (extra.childNodes.length) node.appendChild(extra);
    }

    if (result.box_score && present(result.box_score.path)) {
      var foot = el('div', 'card-f');
      var boxUrl = href(result.box_score.path, result.box_score.params);
      var box = el('a', 'lnk', 'Box Score');
      box.href = boxUrl;
      bindGo(box, boxUrl);
      foot.appendChild(box);
      node.appendChild(foot);
    }
    return node.childNodes.length ? node : null;
  }

  function movedCell(label, value, delta, index) {
    if (!present(value)) return null;
    var cell = el('div', 'mv-cell ar-item');
    cell.style.setProperty('--i', String(index));
    cell.appendChild(el('span', 'mv-l', label));
    var row = el('span', 'mv-v');
    row.appendChild(el('b', '', String(value)));
    var deltaChip = chip(delta, index);
    if (deltaChip) row.appendChild(deltaChip);
    cell.appendChild(row);
    return cell;
  }

  function whatMovedCard(moved, digest, index) {
    if (!moved) return null;
    var node = card('office-mv', index);
    var head = el('div', 'card-h');
    head.appendChild(el('h3', '', 'What moved'));
    node.appendChild(head);
    var strip = el('div', 'mv-strip');
    var rank = moved.national_rank || {};
    var conf = moved.conference_standing || {};
    var record = moved.record || {};
    var rankCell = movedCell('National rank', present(rank.now) ? '#' + rank.now : null, rank.delta, 0);
    var confCell = movedCell('Conference', present(conf.now) ? conf.now : null, conf.delta, 1);
    var recordText = winsLosses(record) || null;
    var recordCell = movedCell('Record', recordText, null, 2);
    if (recordCell && present(moved.streak)) {
      var streak = streakChip(moved.streak);
      if (streak) recordCell.querySelector('.mv-v').appendChild(streak);
    }
    [rankCell, confCell, recordCell].forEach(function (cell) {
      if (cell) strip.appendChild(cell);
    });
    if (strip.childNodes.length) node.appendChild(strip);

    var rows = groupAttributes(moved.attribute_changes);
    var cap = playerCap();
    var shown = rows.slice(0, cap);
    if (shown.length) {
      node.appendChild(el('div', 'sub-h', 'Attributes'));
      var list = el('div', 'mv-list');
      shown.forEach(function (player, changeIndex) {
        var row = el('div', 'mv-p ar-item');
        row.style.setProperty('--i', String(changeIndex + 3));
        row.dataset.playerId = player.id;
        var url = playerHref(player.id);
        var who = el(url ? 'a' : 'span', 'nm');
        who.textContent = player.name;
        if (url) {
          who.href = url;
          bindGo(who, url);
        }
        row.appendChild(who);
        var run = el('span', 'attr-run');
        player.chips.forEach(function (change) {
          run.appendChild(attrChip(change));
        });
        row.appendChild(run);
        list.appendChild(row);
      });
      node.appendChild(list);
      if (rows.length > cap) {
        var moreUrl = trainingReportHref(digest);
        var more = el('a', 'lnk', 'All changes');
        more.href = moreUrl;
        bindGo(more, moreUrl);
        node.appendChild(more);
      }
    }
    return node;
  }

  function wireRow(event, index) {
    if (!event) return null;
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
    if (line.childNodes.length) body.appendChild(line);
    if (present(event.event_text)) body.appendChild(el('span', 'wr-2', event.event_text));
    if (!body.childNodes.length) return null;
    if (present(event.list_position)) row.appendChild(el('span', 'chip', '#' + event.list_position));
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
    return document.documentElement.classList.contains('gob-1920') ? 12 : 8;
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
      var line = (oneLine && wire && present(wire.status))
        ? wire.status
        : 'No recruiting movement this week';
      node.appendChild(el('p', 'wr-empty', line));
    }
    return node;
  }

  function previewCard(preview, index) {
    if (!preview) return null;
    var node = card('sp-card', index);
    node.appendChild(el('h3', 'sp-title', 'Season preview'));
    var grid = el('div', 'sp-grid');
    function stat(label, value) {
      if (!present(value)) return;
      var cell = el('div', 'mv-cell');
      cell.appendChild(el('span', 'mv-l', label));
      cell.appendChild(el('b', 'mv-v', String(value)));
      grid.appendChild(cell);
    }
    stat('Preseason rank', present(preview.preseason_rank) ? '#' + preview.preseason_rank : null);
    if (present(preview.national_rank) && preview.national_rank !== preview.preseason_rank) {
      stat('National rank', '#' + preview.national_rank);
    }
    stat('Conference projection', preview.conference_projection);
    stat('Returning starters', preview.returning_starters);
    if (preview.top_returner && present(preview.top_returner.name)) {
      stat('Top returner', preview.top_returner.name);
    }
    if (grid.childNodes.length) node.appendChild(grid);
    var newcomers = Array.isArray(preview.newcomers) ? preview.newcomers : [];
    if (newcomers.length) {
      node.appendChild(el('div', 'sub-h', 'Newcomers'));
      newcomers.forEach(function (row) {
        if (!row || !present(row.name)) return;
        var url = playerHref(row.player_id);
        var line = linkName('nm', row.name, url) || el('span', '', row.name);
        var wrap = el('div', 'msr');
        wrap.appendChild(line);
        node.appendChild(wrap);
      });
    }
    return node.childNodes.length > 1 ? node : null;
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
    var recordLine = winsLosses(game.record);
    var confLine = conferenceLabel(game.conference);
    if (recordLine) sub.push(recordLine);
    if (confLine) {
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
      var total = Number(attitude.player_count);
      if (!total) {
        total = buckets.reduce(function (sum, bucket) {
          return sum + (Number(bucket && bucket.count) || 0);
        }, 0);
      }
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
        var width = total > 0 ? Math.max(0, Math.min(100, (count / total) * 100)) : 0;
        share.style.width = width + '%';
        bar.appendChild(share);
        col.appendChild(bar);
        spread.appendChild(col);
      });
      node.appendChild(spread);
    }
    var moved = Array.isArray(snap.moved_most) ? snap.moved_most : [];
    if (snap.state === 'set_after_camp') {
      node.appendChild(el('div', 'sub-h', 'Moved most'));
      [0, 1].forEach(function () {
        var line = el('div', 'msr');
        line.appendChild(el('span', '', 'Set after camp'));
        line.appendChild(el('b', '', '—'));
        node.appendChild(line);
      });
    } else if (moved.length) {
      node.appendChild(el('div', 'sub-h', 'Moved most'));
      moved.slice(0, 2).forEach(function (row) {
        if (!row || !present(row.measure)) return;
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

  function signingCard(signing, index) {
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
    var targets = Array.isArray(signing.targets) ? signing.targets : [];
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

  function standingsRow(row) {
    if (!row) return null;
    var line = el('div', 'st-r' + (row.is_user ? ' me' : ''));
    line.dataset.teamId = row.team_id || '';
    line.appendChild(el('span', '', present(row.position) ? String(row.position) : ''));
    line.appendChild(el('span', 'st-n', present(row.team_name) ? String(row.team_name) : ''));
    var record = '';
    if (present(row.wins) && present(row.losses)) record = row.wins + '-' + row.losses;
    line.appendChild(el('span', '', record));
    return line;
  }

  function paintStandingsRows(node, rows) {
    node.querySelectorAll('.st-r').forEach(function (child) { child.remove(); });
    var head = el('div', 'st-r st-hd');
    head.appendChild(el('span', '', '#'));
    head.appendChild(el('span', '', 'Team'));
    head.appendChild(el('span', '', 'W-L'));
    node.appendChild(head);
    rows.forEach(function (row) {
      var line = standingsRow(row);
      if (line) node.appendChild(line);
    });
    node.dataset.standingsShown = String(rows.length);
    node.dataset.standingsMode = 'all';
  }

  function standingsCard(table, index) {
    var rows = table && Array.isArray(table.rows) ? table.rows.filter(Boolean) : [];
    if (!rows.length) return null;
    var node = card('office-st', index);
    var label = conferenceLabel(table.conference);
    var head = el('div', 'card-h');
    head.appendChild(el('h3', '', label ? ('Conference ' + label + ' standings') : 'Conference standings'));
    node.appendChild(head);
    node._rows = rows;
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

  function columnPastFold(node) {
    if (!node) return false;
    if (node.scrollHeight - node.clientHeight > 1) return true;
    return node.getBoundingClientRect().bottom > foldBottom() + 1;
  }

  function trimRecruiting(root) {
    var wire = root.querySelector('.office-wire');
    if (!wire) return;
    var col = wire.closest('.office-col');
    var guard = 0;
    while (guard < 24) {
      var rows = wire.querySelectorAll(':scope > .wr');
      if (rows.length <= 3) break;
      var last = rows[rows.length - 1];
      var past = columnPastFold(col) || last.getBoundingClientRect().bottom > foldBottom() + 0.5;
      if (!past) break;
      rows[0].remove();
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
    var col1 = column('01', 'Since last week', '');
    var col2 = column('02', 'This Week', '');
    var col3 = column('03', 'Recruiting', '', recruitingHref());
    var first = [];
    var second = [];
    var third = [];
    if (digest.state === 'first_week') {
      first = [previewCard(digest.season_preview, 1)];
      second = [
        nextCard(digest.next_game, digest, 2),
        snapshotCard(digest.team_snapshot, 3)
      ];
      third = [
        wireCard(digest.recruiting_wire, true, 4),
        standingsCard(digest.conference_standings, 5)
      ];
    } else if (digest.state === 'signing_day') {
      first = [resultCard(digest.result, false, 1, userRank), whatMovedCard(digest.what_moved, digest, 2)];
      second = [snapshotCard(digest.team_snapshot, 3)];
      third = [
        signingCard(digest.signing_day, 4),
        standingsCard(digest.conference_standings, 5)
      ];
    } else {
      first = [
        resultCard(digest.result, countScores, 1, userRank),
        whatMovedCard(digest.what_moved, digest, 2)
      ];
      second = [
        nextCard(digest.next_game, digest, 3),
        snapshotCard(digest.team_snapshot, 4)
      ];
      third = [
        wireCard(digest.recruiting_wire, false, 5),
        standingsCard(digest.conference_standings, 6)
      ];
    }
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
    if (countScores) countUp(root);
  }

  global.GOBOffice = {
    render: render,
    skeleton: skeleton
  };
})(typeof window !== 'undefined' ? window : this);
