/**
 * Shared bracket renderer for FCC (Franchise EOS Tournament) and TCC (Tournament Command Center).
 * Legacy DOM for compact/full layouts; arena theme when options.arena === true (TCC).
 */
(function (global) {
  'use strict';

  var TROPHY_SVG =
    '<svg viewBox="0 0 48 48" fill="none" aria-hidden="true">' +
    '<path d="M14 7h20v8a10 10 0 0 1-20 0V7z" fill="url(#tg)" stroke="#f0c560" stroke-width="1.2"/>' +
    '<path d="M14 9H8v3a7 7 0 0 0 7 7" stroke="#d4a848" stroke-width="2" fill="none" stroke-linecap="round"/>' +
    '<path d="M34 9h6v3a7 7 0 0 1-7 7" stroke="#d4a848" stroke-width="2" fill="none" stroke-linecap="round"/>' +
    '<path d="M24 25v7" stroke="#d4a848" stroke-width="2.4" stroke-linecap="round"/>' +
    '<path d="M17 40c0-3 3-5 7-5s7 2 7 5H17z" fill="url(#tg)" stroke="#f0c560" stroke-width="1.2"/>' +
    '<rect x="20" y="32" width="8" height="4" rx="1" fill="#d4a848"/>' +
    '<defs><linearGradient id="tg" x1="24" y1="7" x2="24" y2="41" gradientUnits="userSpaceOnUse">' +
    '<stop stop-color="#f4d27a"/><stop offset="1" stop-color="#c79a3e"/></linearGradient></defs></svg>';

  var CROWN_SVG =
    '<svg class="crown" viewBox="0 0 24 24" fill="none" aria-hidden="true">' +
    '<path d="M3 8l4 4 5-7 5 7 4-4-2 12H5L3 8z" fill="#f0c560" stroke="#c79a3e" stroke-width="1"/></svg>';

  var STAGGER_DELAYS = [0, 80, 160, 240, 320, 400, 480];

  function defaultGetLogo(teamName) {
    if (typeof getTeamAssetPath === 'function') {
      return getTeamAssetPath(teamName || '', 'banner_primary');
    }
    return '/images/teams/general/general_banner_primary.jpg';
  }

  function defaultIsUserTeam() {
    return false;
  }

  function renderBracketShared(container, bracketData, teamIdToNameMap, options) {
    if (!container) return;
    options = options || {};
    if (options.arena) {
      renderBracketArena(container, bracketData, teamIdToNameMap, options);
      return;
    }
    renderBracketLegacy(container, bracketData, teamIdToNameMap, options);
  }

  /* ── Arena (TCC) renderer ─────────────────────────────────────────── */

  function renderBracketArena(container, bracketData, teamIdToNameMap, options) {
    var getLogo = options.getLogo || defaultGetLogo;
    var isUserTeam = options.isUserTeam || defaultIsUserTeam;
    var getTooltipData = typeof options.getTooltipData === 'function' ? options.getTooltipData : null;
    var results = options.results || [];
    var seedsOption = options.seeds || null;
    var userTeamId = options.userTeamId != null ? String(options.userTeamId) : null;
    var tournamentLabel = options.tournamentLabel || 'TOURNAMENT';
    var champEyebrow = options.champEyebrow || 'Tournament Champions';

    var round1 = bracketData.round1 || [];
    var round2 = bracketData.round2 || [];
    var finalRound = bracketData.final || [];

    container.innerHTML = '';

    var seedMap = {};
    if (seedsOption && typeof seedsOption === 'object') {
      seedMap = seedsOption;
    } else if (round1.length >= 4) {
      seedMap[round1[0].home_team] = 1;
      seedMap[round1[0].away_team] = 8;
      seedMap[round1[1].home_team] = 4;
      seedMap[round1[1].away_team] = 5;
      seedMap[round1[2].home_team] = 2;
      seedMap[round1[2].away_team] = 7;
      seedMap[round1[3].home_team] = 3;
      seedMap[round1[3].away_team] = 6;
    }

    function getResult(round, index) {
      return results.find(function (r) { return r.round === round && r.match_index === index; }) || null;
    }

    function resolveName(id) {
      if (id == null) return '';
      var s = teamIdToNameMap[String(id)];
      return s != null ? String(s) : String(id);
    }

    function isWinner(m, id, res) {
      if (!m || id == null) return false;
      var w = (res && res.winner != null) ? res.winner : m.winner;
      return w != null && String(w) === String(id);
    }

    function scoreFor(m, id, name, res) {
      if (!m) return '';
      var sc = (res && res.score) || m.score || {};
      if (sc[id] != null) return sc[id];
      if (sc[name] != null) return sc[name];
      return '';
    }

    function createTeamRow(m, id, side, round, index, opts) {
      opts = opts || {};
      var row = document.createElement('div');
      row.className = 'team';
      var res = getResult(round, index);
      var name = resolveName(id);
      var winner = isWinner(m, id, res);
      var decided = (res && res.winner != null) || (m && m.winner != null);
      var lost = decided && !winner;

      if (winner) row.classList.add('team--winner');
      if (lost) row.classList.add('team--loser');
      if (isUserTeam(id) || isUserTeam(name)) row.classList.add('team--user');
      if (opts.champion && winner) row.classList.add('team--champion');
      if (id != null) row.dataset.teamId = String(id);

      var seedEl = document.createElement('span');
      seedEl.className = 'seed';
      seedEl.textContent = seedMap[id] != null ? String(seedMap[id]) : '';

      var img = document.createElement('img');
      img.className = 'logo';
      img.src = getLogo(name);
      img.alt = name || 'Team';
      img.loading = 'lazy';
      if (getTooltipData) {
        img.dataset.tip = '1';
        img._tipData = getTooltipData(id, name);
      }

      var tname = document.createElement('span');
      tname.className = 'tname';
      tname.textContent = name || '';

      if (opts.champion && winner) {
        row.insertAdjacentHTML('afterbegin', CROWN_SVG);
      }

      var scoreEl = document.createElement('span');
      scoreEl.className = 'score';
      scoreEl.textContent = scoreFor(m, id, name, res);

      row.appendChild(seedEl);
      row.appendChild(img);
      row.appendChild(tname);
      row.appendChild(scoreEl);
      return row;
    }

    function createMatchupWrap(m, round, index, opts) {
      opts = opts || {};
      var wrap = document.createElement('div');
      wrap.className = 'mu-wrap';
      var card = document.createElement('div');
      card.className = 'mu';

      if (!m) {
        card.classList.add('mu--tbd');
        var tbd1 = document.createElement('div');
        tbd1.className = 'team team--tbd';
        tbd1.innerHTML = '<span class="seed"></span><span class="logo logo--tbd"></span><span class="tname tname--tbd">TBD</span><span class="score"></span>';
        var tbd2 = tbd1.cloneNode(true);
        card.appendChild(tbd1);
        card.appendChild(tbd2);
        wrap.appendChild(card);
        return wrap;
      }

      var res = getResult(round, index);
      var hid = m.home_team;
      var aid = m.away_team;
      var hName = resolveName(hid);
      var aName = resolveName(aid);
      var winner = (res && res.winner != null) ? res.winner : m.winner;

      if (isUserTeam(hid) || isUserTeam(aid) || isUserTeam(hName) || isUserTeam(aName)) {
        card.classList.add('mu--user');
      }
      if (opts.championship) {
        card.classList.add('mu--champ');
        var vs = document.createElement('div');
        vs.className = 'champ-vs';
        vs.textContent = 'VS';
        card.appendChild(vs);
      }

      card.appendChild(createTeamRow(m, hid, 'home', round, index, opts));
      card.appendChild(createTeamRow(m, aid, 'away', round, index, opts));

      if (winner != null) wrap.dataset.winnerId = String(winner);
      wrap.appendChild(card);
      return wrap;
    }

    function colHead(text) {
      var h = document.createElement('div');
      h.className = 'col-head';
      h.textContent = text;
      return h;
    }

    function col(className, head, nodes) {
      var c = document.createElement('div');
      c.className = 'bracket-col ' + (className || '');
      c.appendChild(colHead(head));
      nodes.forEach(function (n) { c.appendChild(n); });
      return c;
    }

    var gradId = 'tb-tg-' + String(Math.random()).slice(2, 10);
    var trophyHtml = TROPHY_SVG.replace(/#tg/g, '#' + gradId).replace(/id="tg"/g, 'id="' + gradId + '"');

    var midNodes = [];
    var trophyWrap = document.createElement('div');
    trophyWrap.className = 'trophy';
    trophyWrap.innerHTML = trophyHtml;
    var badge = document.createElement('div');
    badge.className = 'champ-badge';
    badge.textContent = '★ ' + tournamentLabel + ' ★';
    midNodes.push(trophyWrap);
    midNodes.push(badge);

    var fin = finalRound[0] || null;
    var finWrap = createMatchupWrap(fin, 3, 0, { championship: true, champion: true });
    midNodes.push(finWrap);

    if (fin && fin.winner) {
      var plate = document.createElement('div');
      plate.className = 'champ-plate';
      var eyebrow = document.createElement('div');
      eyebrow.className = 'champ-plate__eyebrow';
      eyebrow.textContent = champEyebrow;
      var champName = document.createElement('div');
      champName.className = 'champ-plate__name';
      champName.textContent = resolveName(fin.winner) || 'Champion';
      plate.appendChild(eyebrow);
      plate.appendChild(champName);
      midNodes.push(plate);
    }

    var delayIdx = 0;
    function staggered(wrap) {
      if (wrap && STAGGER_DELAYS[delayIdx] != null) {
        wrap.style.setProperty('--d', STAGGER_DELAYS[delayIdx] + 'ms');
      }
      delayIdx += 1;
      return wrap;
    }

    container.appendChild(
      col('bracket-col--qf-l', 'Quarterfinals', [
        staggered(createMatchupWrap(round1[0], 1, 0)),
        staggered(createMatchupWrap(round1[1], 1, 1)),
      ])
    );
    container.appendChild(
      col('bracket-col--sf-l', 'Semifinals', [staggered(createMatchupWrap(round2[0], 2, 0))])
    );
    container.appendChild(col('bracket-col--final', 'Championship', midNodes.map(staggered)));
    container.appendChild(
      col('bracket-col--sf-r', 'Semifinals', [staggered(createMatchupWrap(round2[1], 2, 1))])
    );
    container.appendChild(
      col('bracket-col--qf-r', 'Quarterfinals', [
        staggered(createMatchupWrap(round1[2], 1, 2)),
        staggered(createMatchupWrap(round1[3], 1, 3)),
      ])
    );

    wireArenaTooltips(container);
    scheduleArenaConnectors(container, userTeamId);

    if (typeof options.onRendered === 'function') {
      options.onRendered({ final: fin, seedMap: seedMap });
    }
  }

  function wireArenaTooltips(container) {
    var tipEl = document.getElementById('bracket-tip');
    if (!tipEl) return;

    function hideTip() {
      tipEl.classList.remove('show');
      tipEl.setAttribute('aria-hidden', 'true');
    }

    function showTip(data, x, y) {
      if (!data) return;
      var seed = data.seed != null && data.seed !== '' ? String(data.seed) : '';
      var region = data.region ? String(data.region) : '';
      var name = data.name ? String(data.name) : '';
      var rank = data.natlRank != null && data.natlRank !== '' ? '#' + data.natlRank : '';
      var record = data.record ? String(data.record) : '';

      tipEl.innerHTML =
        '<div class="tip__top">' +
        (seed ? '<span class="tip__seed">' + seed + '</span>' : '') +
        (seed && region ? '<span class="tip__sep"> · </span>' : '') +
        (region ? '<span class="tip__region">' + region + '</span>' : '') +
        ((seed || region) && name ? '<span class="tip__sep"> — </span>' : '') +
        (name ? '<span class="tip__name-inline">' + name + '</span>' : '') +
        '</div>' +
        ((rank || record)
          ? '<div class="tip__row">' +
            (rank ? '<span>' + rank + '</span>' : '') +
            (rank && record ? '<span> · </span>' : '') +
            (record ? '<span>' + record + '</span>' : '') +
            '</div>'
          : '');

      tipEl.classList.add('show');
      tipEl.setAttribute('aria-hidden', 'false');
      var rect = tipEl.getBoundingClientRect();
      var left = x + 14;
      var top = y + 14;
      if (left + rect.width > window.innerWidth - 8) left = x - rect.width - 14;
      if (top + rect.height > window.innerHeight - 8) top = y - rect.height - 14;
      tipEl.style.left = left + 'px';
      tipEl.style.top = top + 'px';
    }

    container.querySelectorAll('img.logo[data-tip]').forEach(function (img) {
      img.addEventListener('mouseenter', function (e) {
        showTip(img._tipData, e.clientX, e.clientY);
      });
      img.addEventListener('mousemove', function (e) {
        if (tipEl.classList.contains('show')) showTip(img._tipData, e.clientX, e.clientY);
      });
      img.addEventListener('mouseleave', hideTip);
    });
  }

  function connectorToneFromWrap(wrap, userTeamId) {
    if (!wrap) return 'undecided';
    var winnerId = wrap.dataset.winnerId;
    if (!winnerId) {
      var winRow = wrap.querySelector('.team--winner');
      winnerId = winRow && winRow.dataset.teamId ? winRow.dataset.teamId : '';
    }
    if (!winnerId) return 'undecided';
    if (userTeamId && String(winnerId) === String(userTeamId)) return 'user';
    return 'winner';
  }

  function applyConnLineStyle(lineEl, tone) {
    if (tone === 'user') {
      lineEl.setAttribute('stroke', '#2bd66a');
      lineEl.setAttribute('stroke-width', '2.4');
      lineEl.setAttribute('stroke-linecap', 'round');
      lineEl.setAttribute('filter', 'url(#tb-conn-glow-green)');
      return;
    }
    if (tone === 'winner') {
      lineEl.setAttribute('stroke', 'rgba(212, 168, 72, 0.72)');
      lineEl.setAttribute('stroke-width', '1.8');
      lineEl.setAttribute('stroke-linecap', 'round');
      return;
    }
    lineEl.setAttribute('stroke', 'rgba(255,255,255,0.12)');
    lineEl.setAttribute('stroke-width', '1');
    lineEl.setAttribute('stroke-linecap', 'round');
  }

  function ensureConnDefs(svg) {
    if (svg.querySelector('defs')) return;
    var defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
    var filter = document.createElementNS('http://www.w3.org/2000/svg', 'filter');
    filter.setAttribute('id', 'tb-conn-glow-green');
    filter.setAttribute('x', '-50%');
    filter.setAttribute('y', '-50%');
    filter.setAttribute('width', '200%');
    filter.setAttribute('height', '200%');
    var blur = document.createElementNS('http://www.w3.org/2000/svg', 'feDropShadow');
    blur.setAttribute('dx', '0');
    blur.setAttribute('dy', '0');
    blur.setAttribute('stdDeviation', '2.5');
    blur.setAttribute('flood-color', '#2bd66a');
    blur.setAttribute('flood-opacity', '0.55');
    filter.appendChild(blur);
    defs.appendChild(filter);
    svg.appendChild(defs);
  }

  function drawArenaConnectors(grid, userTeamId) {
    var arena = grid.closest('.arena') || grid.parentElement;
    if (!arena) return;

    var old = arena.querySelector('svg.conn');
    if (old) old.remove();

    var wraps = grid.querySelectorAll(':scope > .bracket-col > .mu-wrap');
    if (wraps.length < 7) return;

    var ns = 'http://www.w3.org/2000/svg';
    var grect = grid.getBoundingClientRect();
    if (grect.width < 40 || grect.height < 40) return;

    var svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('class', 'conn');
    svg.setAttribute('viewBox', '0 0 ' + grect.width + ' ' + grect.height);
    svg.setAttribute('width', String(grect.width));
    svg.setAttribute('height', String(grect.height));
    ensureConnDefs(svg);

    function line(x1, y1, x2, y2, tone) {
      var p = document.createElementNS(ns, 'line');
      p.setAttribute('x1', x1);
      p.setAttribute('y1', y1);
      p.setAttribute('x2', x2);
      p.setAttribute('y2', y2);
      applyConnLineStyle(p, tone);
      svg.appendChild(p);
    }

    function cxWrap(wrap) {
      var r = wrap.getBoundingClientRect();
      return {
        x: r.left - grect.left + r.width,
        xl: r.left - grect.left,
        y: r.top - grect.top + r.height / 2,
      };
    }

    var w0 = wraps[0];
    var w1 = wraps[1];
    var w2 = wraps[2];
    var w3 = wraps[3];
    var w4 = wraps[4];
    var w5 = wraps[5];
    var w6 = wraps[6];
    if (!w0 || !w1 || !w2 || !w3 || !w4 || !w5 || !w6) return;

    var c0a = cxWrap(w0);
    var c0b = cxWrap(w1);
    var c1 = cxWrap(w2);
    var cf = cxWrap(w3);
    var c1r = cxWrap(w4);
    var c4a = cxWrap(w5);
    var c4b = cxWrap(w6);

    var midL = c0a.x + (c1.xl - c0a.x) * 0.45;
    var midR = c4a.xl - (c4a.xl - cf.x) * 0.45;

    var t0 = connectorToneFromWrap(w0, userTeamId);
    var t1 = connectorToneFromWrap(w1, userTeamId);
    var t2 = connectorToneFromWrap(w2, userTeamId);
    var t3 = connectorToneFromWrap(w3, userTeamId);
    var t4 = connectorToneFromWrap(w4, userTeamId);
    var t5 = connectorToneFromWrap(w5, userTeamId);
    var t6 = connectorToneFromWrap(w6, userTeamId);

    line(c0a.x, c0a.y, midL, c0a.y, t0);
    line(midL, c0a.y, midL, c1.y, t2);
    line(midL, c1.y, c1.xl, c1.y, t2);
    line(c0b.x, c0b.y, midL, c0b.y, t1);
    line(midL, c0b.y, midL, c1.y, t2);
    line(c1.x, c1.y, cf.xl, cf.y, t2);
    line(c1r.xl, c1r.y, cf.x, cf.y, t4);
    line(c4a.xl, c4a.y, midR, c4a.y, t5);
    line(midR, c4a.y, midR, c1r.y, t4);
    line(midR, c1r.y, c1r.x, c1r.y, t4);
    line(c4b.xl, c4b.y, midR, c4b.y, t6);
    line(midR, c4b.y, midR, c1r.y, t4);

    grid.style.position = 'relative';
    grid.insertBefore(svg, grid.firstChild);
  }

  function scheduleArenaConnectors(grid, userTeamId) {
    if (!grid) return;
    var run = function () {
      drawArenaConnectors(grid, userTeamId);
    };
    if (typeof requestAnimationFrame === 'function') {
      requestAnimationFrame(function () {
        requestAnimationFrame(run);
      });
    } else {
      setTimeout(run, 30);
    }
    if (!grid._tbConnResizeBound) {
      grid._tbConnResizeBound = true;
      var resizeTimer;
      window.addEventListener('resize', function () {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(run, 120);
      });
    }
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(run).catch(function () {});
    }
  }

  /* ── Legacy renderer (unchanged structure) ─────────────────────────── */

  function renderBracketLegacy(container, bracketData, teamIdToNameMap, options) {
    options = options || {};
    var getLogo = options.getLogo || defaultGetLogo;
    var isUserTeam = options.isUserTeam || defaultIsUserTeam;
    var getTooltip = typeof options.getTooltip === 'function' ? options.getTooltip : null;
    var results = options.results || [];
    var seedsOption = options.seeds || null;
    var layout = options.layout || 'full';

    var round1 = bracketData.round1 || [];
    var round2 = bracketData.round2 || [];
    var finalRound = bracketData.final || [];

    container.innerHTML = '';

    var seedMap = {};
    if (seedsOption && typeof seedsOption === 'object') {
      seedMap = seedsOption;
    } else if (round1.length >= 4) {
      seedMap[round1[0].home_team] = 1;
      seedMap[round1[0].away_team] = 8;
      seedMap[round1[1].home_team] = 4;
      seedMap[round1[1].away_team] = 5;
      seedMap[round1[2].home_team] = 2;
      seedMap[round1[2].away_team] = 7;
      seedMap[round1[3].home_team] = 3;
      seedMap[round1[3].away_team] = 6;
    }

    function getResult(round, index) {
      return results.find(function (r) { return r.round === round && r.match_index === index; }) || null;
    }

    function teamName(id) {
      if (id == null) return id;
      var s = teamIdToNameMap[String(id)];
      return s != null ? s : id;
    }

    function createTeamEntry(teamId, teamNameVal, side, score, isWinner) {
      var div = document.createElement('div');
      div.className = 'team-entry';
      if (isWinner) div.classList.add('winner');
      var label = document.createElement('span');
      label.className = 'seed-label ' + (side === 'left' ? 'seed-left' : 'seed-right');
      label.textContent = seedMap[teamId] ? '#' + seedMap[teamId] : '';
      var img = document.createElement('img');
      img.src = getLogo(teamNameVal);
      img.classList.add('team-logo', 'bracket-logo');
      if (isUserTeam(teamId) || isUserTeam(teamNameVal)) img.classList.add('user-team');
      var tooltipText = getTooltip ? getTooltip(teamId, teamNameVal) : '';
      var logoNode = img;
      if (tooltipText) {
        var tooltipHost = document.createElement('span');
        tooltipHost.className = 'team-tooltip-host';
        tooltipHost.setAttribute('data-team-tooltip', tooltipText);
        tooltipHost.setAttribute('aria-label', tooltipText);
        tooltipHost.appendChild(img);
        logoNode = tooltipHost;
      }
      var scoreSpan = document.createElement('span');
      scoreSpan.className = 'score';
      scoreSpan.textContent = score !== undefined && score !== null ? score : '';
      if (side === 'left') {
        div.appendChild(label);
        div.appendChild(logoNode);
        div.appendChild(scoreSpan);
      } else {
        div.appendChild(scoreSpan);
        div.appendChild(logoNode);
        div.appendChild(label);
      }
      return div;
    }

    function createMatchup(m, side, round, index) {
      var wrap = document.createElement('div');
      wrap.className = 'matchup-wrapper';
      var matchup = document.createElement('div');
      matchup.className = 'matchup';
      var homeId = m.home_team;
      var awayId = m.away_team;
      var homeName = teamName(homeId);
      var awayName = teamName(awayId);
      var res = getResult(round, index);
      var homeScore = res && res.score && res.score[homeName] !== undefined ? res.score[homeName] : (m.score && (m.score[homeName] != null ? m.score[homeName] : m.score[homeId]));
      var awayScore = res && res.score && res.score[awayName] !== undefined ? res.score[awayName] : (m.score && (m.score[awayName] != null ? m.score[awayName] : m.score[awayId]));
      var winner = (res && res.winner != null) ? res.winner : m.winner;
      if (side === 'center') {
        matchup.appendChild(createTeamEntry(homeId, homeName, 'left', homeScore, winner === homeId || String(winner) === String(homeId)));
        matchup.appendChild(createTeamEntry(awayId, awayName, 'right', awayScore, winner === awayId || String(winner) === String(awayId)));
      } else {
        matchup.appendChild(createTeamEntry(homeId, homeName, side, homeScore, winner === homeId || String(winner) === String(homeId)));
        matchup.appendChild(createTeamEntry(awayId, awayName, side, awayScore, winner === awayId || String(winner) === String(awayId)));
      }
      wrap.appendChild(matchup);
      return wrap;
    }

    function createPlaceholder(label) {
      var wrap = document.createElement('div');
      wrap.className = 'matchup-wrapper';
      var matchup = document.createElement('div');
      matchup.className = 'matchup';
      var placeholder = document.createElement('div');
      placeholder.className = 'placeholder';
      placeholder.textContent = label || 'TBD';
      matchup.appendChild(placeholder);
      wrap.appendChild(matchup);
      return wrap;
    }

    if (layout === 'compact4') {
      var compactRound1 = document.createElement('div');
      compactRound1.className = 'round round-1 semifinals';
      if (round1[0]) compactRound1.appendChild(createMatchup(round1[0], 'left', 1, 0));
      var compactSpacer = document.createElement('div');
      compactSpacer.style.height = '40px';
      compactSpacer.className = 'bracket-spacer';
      compactRound1.appendChild(compactSpacer);
      if (round1[1]) compactRound1.appendChild(createMatchup(round1[1], 'left', 1, 1));

      var compactFinal = document.createElement('div');
      compactFinal.className = 'round round-3 final';
      if (finalRound[0]) compactFinal.appendChild(createMatchup(finalRound[0], 'center', 3, 0));
      else compactFinal.appendChild(createPlaceholder('Championship!'));

      container.appendChild(compactRound1);
      container.appendChild(compactFinal);
      return;
    }

    var leftR1 = document.createElement('div');
    leftR1.className = 'round round-1 quarterfinals';
    if (round1[0]) leftR1.appendChild(createMatchup(round1[0], 'left', 1, 0));
    var leftSpacer = document.createElement('div');
    leftSpacer.style.height = '40px';
    leftSpacer.className = 'bracket-spacer';
    leftR1.appendChild(leftSpacer);
    if (round1[1]) leftR1.appendChild(createMatchup(round1[1], 'left', 1, 1));

    var leftSemi = document.createElement('div');
    leftSemi.className = 'round round-2 semifinals';
    if (round2[0]) leftSemi.appendChild(createMatchup(round2[0], 'left', 2, 0));
    else leftSemi.appendChild(createPlaceholder('Semifinals'));

    var finalEl = document.createElement('div');
    finalEl.className = 'round round-3 final';
    if (finalRound[0]) finalEl.appendChild(createMatchup(finalRound[0], 'center', 3, 0));
    else finalEl.appendChild(createPlaceholder('Championship!'));

    var rightSemi = document.createElement('div');
    rightSemi.className = 'round round-4 semifinals';
    if (round2[1]) rightSemi.appendChild(createMatchup(round2[1], 'right', 2, 1));
    else rightSemi.appendChild(createPlaceholder('Semifinals'));

    var rightR1 = document.createElement('div');
    rightR1.className = 'round round-5 quarterfinals';
    if (round1[2]) rightR1.appendChild(createMatchup(round1[2], 'right', 1, 2));
    var rightSpacer = document.createElement('div');
    rightSpacer.style.height = '40px';
    rightSpacer.className = 'bracket-spacer';
    rightR1.appendChild(rightSpacer);
    if (round1[3]) rightR1.appendChild(createMatchup(round1[3], 'right', 1, 3));

    container.appendChild(leftR1);
    container.appendChild(leftSemi);
    container.appendChild(finalEl);
    container.appendChild(rightSemi);
    container.appendChild(rightR1);
  }

  global.renderBracketShared = renderBracketShared;
  global.scheduleArenaConnectors = scheduleArenaConnectors;
})(typeof window !== 'undefined' ? window : this);
