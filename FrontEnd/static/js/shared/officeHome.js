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

  function monogram(name) {
    var mark = el('span', 'logo');
    mark.style.setProperty('--tc', '#3a4254');
    mark.style.width = '34px';
    mark.style.height = '34px';
    mark.style.fontSize = '18px';
    mark.textContent = initials(name).charAt(0) || '';
    return mark;
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
    if (!isFinite(n)) return null;
    var kind = n > 0 ? 'up' : (n < 0 ? 'down' : 'flat');
    var text = n > 0 ? '▲' + n : (n < 0 ? '▼' + Math.abs(n) : '0');
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

  function column(index, title, aside) {
    var col = el('section', 'office-col');
    var head = el('header', 'office-h');
    var h2 = el('h2');
    h2.appendChild(el('i', '', index));
    h2.appendChild(document.createTextNode(title));
    head.appendChild(h2);
    if (present(aside)) head.appendChild(el('span', '', aside));
    col.appendChild(head);
    return col;
  }

  function card(className, index) {
    var node = el('section', 'card ' + className + ' ar-card');
    node.style.setProperty('--i', String(index));
    return node;
  }

  function weekAside(digest) {
    var next = digest.next_game;
    if (next && present(next.week)) return 'Week ' + next.week;
    var result = digest.result;
    if (result && present(result.week)) return 'Week ' + result.week;
    return '';
  }

  function todosCard(todos) {
    var list = Array.isArray(todos) ? todos : [];
    var node = card('office-todo', 0);
    var head = el('div', 'card-h');
    head.appendChild(el('h3', '', 'To do'));
    node.appendChild(head);
    var wrap = el('div', 'todo-list');
    list.forEach(function (todo, index) {
      if (!todo) return;
      var classes = 'todo ar-item';
      if (todo.done) classes += ' done';
      if (todo.gates_advance) classes += ' gated';
      var row = el('button', classes);
      row.type = 'button';
      row.style.setProperty('--i', String(index));
      row.dataset.officeTodo = todo.id || '';
      if (todo.is_advance_action) row.dataset.advanceMirror = '1';
      var box = el('span', 'cbox');
      if (todo.done) box.appendChild(checkMark());
      row.appendChild(box);
      var text = el('span', 'td-t');
      var copy = TODO_COPY[todo.label_key] || labelize(todo.label_key);
      text.appendChild(el('span', 'td-l', copy));
      if (todo.gates_advance || todo.is_advance_action) {
        var tags = el('span', 'td-tags');
        if (todo.gates_advance) tags.appendChild(el('span', 'td-gate', 'BLOCKS ADVANCE'));
        if (todo.is_advance_action) tags.appendChild(el('span', 'td-adv', 'ADVANCE'));
        text.appendChild(tags);
      }
      row.appendChild(text);
      var cue = el('span', 'td-c');
      cue.appendChild(chevron());
      row.appendChild(cue);
      row.addEventListener('click', function () {
        if (todo.is_advance_action) {
          var play = document.getElementById('play-now');
          if (play) play.click();
          return;
        }
        if (present(todo.route)) go(franchiseHref(todo.route));
      });
      wrap.appendChild(row);
    });
    node.appendChild(wrap);
    if (list.length > 4) {
      var more = el('button', 'lnk more office-more', 'See all · ' + (list.length - 4) + ' more');
      more.type = 'button';
      more.addEventListener('click', function () {
        clickTiny();
        var root = document.getElementById('office-root');
        if (!root) return;
        var open = root.classList.toggle('is-todos-open');
        more.textContent = open ? 'Show less' : ('See all · ' + (list.length - 4) + ' more');
      });
      node.appendChild(more);
    }
    return node;
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

  function resultCard(result, countScores, index) {
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
      left.appendChild(monogram(mine.name));
      left.appendChild(el('span', 'rs-n', mine.name));
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
      right.appendChild(monogram(theirs.name));
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
        var min = el('div');
        min.appendChild(el('b', '', String(stats.min)));
        min.appendChild(el('span', '', 'MIN'));
        extra.appendChild(min);
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

  function whatMovedCard(moved, index) {
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
    var recordText = present(record.wins) && present(record.losses) ? record.wins + '–' + record.losses : null;
    var recordCell = movedCell('Record', recordText, null, 2);
    if (recordCell && present(moved.streak)) {
      var streak = streakChip(moved.streak);
      if (streak) recordCell.querySelector('.mv-v').appendChild(streak);
    }
    [rankCell, confCell, recordCell].forEach(function (cell) {
      if (cell) strip.appendChild(cell);
    });
    if (strip.childNodes.length) node.appendChild(strip);

    var changes = Array.isArray(moved.attribute_changes) ? moved.attribute_changes : [];
    if (changes.length) {
      node.appendChild(el('div', 'sub-h', 'Attributes'));
      var list = el('div', 'mv-list');
      changes.forEach(function (change, changeIndex) {
        if (!change || !present(change.from) || !present(change.to)) return;
        var url = playerHref(change.player_id);
        var row = el(url ? 'a' : 'div', 'mv-p ar-item');
        row.style.setProperty('--i', String(changeIndex + 3));
        if (url) {
          row.href = url;
          bindGo(row, url);
        }
        var who = el('span', 'mv-pn');
        if (present(change.name)) who.appendChild(el('span', 'nm', change.name));
        if (present(change.attribute)) who.appendChild(el('span', '', labelize(change.attribute)));
        row.appendChild(who);
        var ft = el('span', 'mv-ft');
        ft.appendChild(el('b', 'tdig ' + digitClass(change.from), String(change.from)));
        ft.appendChild(el('i', '', '→'));
        ft.appendChild(el('b', 'tdig ' + digitClass(change.to), String(change.to)));
        row.appendChild(ft);
        var delta = Number(change.to) - Number(change.from);
        if (isFinite(delta) && delta !== 0) {
          var deltaChip = chip(delta, changeIndex + 3);
          if (deltaChip) row.appendChild(deltaChip);
        }
        list.appendChild(row);
      });
      if (list.childNodes.length) node.appendChild(list);
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

  function wireCard(wire, oneLine, index) {
    if (!wire) return null;
    var events = Array.isArray(wire.events) ? wire.events : [];
    if (!present(wire.status) && !events.length) return null;
    var node = card('office-wire', index);
    var head = el('div', 'card-h');
    head.appendChild(el('h3', '', 'Recruiting wire'));
    if (!oneLine && present(wire.status)) head.appendChild(el('span', 'meta', wire.status));
    var open = el('a', 'lnk', 'Recruiting');
    var url = recruitingHref();
    open.href = url;
    bindGo(open, url);
    head.appendChild(open);
    node.appendChild(head);
    if (oneLine) {
      if (present(wire.status)) node.appendChild(el('p', 'wr-2', wire.status));
      return node;
    }
    events.forEach(function (event, eventIndex) {
      var row = wireRow(event, eventIndex);
      if (row) node.appendChild(row);
    });
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
    if (present(game.opponent)) main.appendChild(monogram(game.opponent));
    var names = el('div');
    var site = game.site === 'away' ? 'AT' : (game.site === 'home' ? 'VS' : '');
    if (site) names.appendChild(el('span', 'nx-at', site));
    var oppUrl = teamHref(game.opponent_team_id);
    var opp = linkName('nx-name', game.opponent, oppUrl);
    if (opp) {
      if (present(game.rank)) opp.insertBefore(el('em', '', '#' + game.rank + ' '), opp.firstChild);
      names.appendChild(opp);
    }
    var sub = [];
    if (present(game.record)) sub.push(String(game.record));
    if (present(game.conference)) sub.push(String(game.conference));
    if (present(game.week)) sub.push('Week ' + game.week);
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
      var row = el('div', 'sn-row');
      row.appendChild(el('span', 'sn-l', 'Chemistry'));
      row.appendChild(el('span', 'sn-v', chemistry.value + '/' + chemistry.max));
      node.appendChild(row);
      var meter = el('div', 'meter');
      var fill = el('i');
      var pct = Math.max(0, Math.min(100, (Number(chemistry.value) / Number(chemistry.max)) * 100));
      fill.style.width = pct + '%';
      meter.appendChild(fill);
      node.appendChild(meter);
    }
    var attitude = snap.attitude || {};
    var buckets = Array.isArray(attitude.buckets) ? attitude.buckets : [];
    if (buckets.length) {
      node.appendChild(el('div', 'sub-h', 'Attitude'));
      var spread = el('div', 'spread');
      var key = el('div', 'sp-key');
      var any = buckets.some(function (bucket) { return Number(bucket && bucket.count) > 0; });
      buckets.forEach(function (bucket) {
        if (!bucket) return;
        var count = Number(bucket.count) || 0;
        var seg = el('i');
        seg.style.flex = any ? String(count) : '1';
        if (bucket.id === 'em_0_19' && count > 0) seg.classList.add('is-low');
        spread.appendChild(seg);
        var item = el('span', bucket.id === 'em_0_19' && count > 0 ? 'bad' : '');
        item.appendChild(el('b', '', EMOJI[bucket.id] || ''));
        item.appendChild(document.createTextNode(String(count)));
        key.appendChild(item);
      });
      node.appendChild(spread);
      node.appendChild(key);
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
    ['01', '02', '03'].forEach(function (index, nth) {
      var titles = ['This week', 'Since last week', 'Next game'];
      var col = column(index, titles[nth], '');
      col.appendChild(el('div', 'card office-skel'));
      col.appendChild(el('div', 'card office-skel'));
      root.appendChild(col);
    });
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

    var col1 = column('01', 'This week', weekAside(digest));
    col1.appendChild(todosCard(digest.todos));
    var col2 = column('02', 'Since last week', '');
    var col3 = column('03', 'Next game', '');
    var second = [];
    var third = [];
    if (digest.state === 'first_week') {
      second = [previewCard(digest.season_preview, 1), wireCard(digest.recruiting_wire, true, 2)];
      third = [nextCard(digest.next_game, digest, 3), snapshotCard(digest.team_snapshot, 4)];
    } else if (digest.state === 'signing_day') {
      second = [resultCard(digest.result, false, 1)];
      third = [signingCard(digest.signing_day, 2)];
    } else {
      second = [
        resultCard(digest.result, countScores, 1),
        whatMovedCard(digest.what_moved, 2),
        wireCard(digest.recruiting_wire, false, 3)
      ];
      third = [nextCard(digest.next_game, digest, 4), snapshotCard(digest.team_snapshot, 5)];
    }
    second.forEach(function (node) { if (node) col2.appendChild(node); });
    third.forEach(function (node) { if (node) col3.appendChild(node); });
    root.append(col1, col2, col3);
    if (countScores) countUp(root);
  }

  global.GOBOffice = {
    render: render,
    skeleton: skeleton
  };
})(typeof window !== 'undefined' ? window : this);
