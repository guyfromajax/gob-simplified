/**
 * FCC Tournament tab — Style A "Classic horizontal" bracket (Bold / arena theme).
 * Consumes the same franchise bracket payloads as renderBracketShared (round1 / round2 / final).
 */
(function (global) {
  'use strict';

  var BYE_SENTINEL = '__BYE__';

  var CHAMP_EYEBROW = {
    conference: 'Conference Champion',
    region: 'Region Champion',
    national: 'National Champion',
  };

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
    '<svg class="fcc-tb-crown" viewBox="0 0 24 24" fill="none" aria-hidden="true">' +
    '<path d="M3 8l4 4 5-7 5 7 4-4-2 12H5L3 8z" fill="#f0c560" stroke="#c79a3e" stroke-width="1"/></svg>';

  function isRealTeamId(id) {
    if (id == null || id === '') return false;
    if (String(id) === BYE_SENTINEL) return false;
    return /^[a-f0-9]{24}$/i.test(String(id));
  }

  function isByeId(id) {
    return id == null || String(id) === BYE_SENTINEL || String(id).indexOf('R1_') === 0;
  }

  function padMatchups(arr, n) {
    var x = (arr || []).slice(0, n);
    while (x.length < n) x.push(null);
    return x;
  }

  function teamName(id, teamIdToNameMap) {
    if (!isRealTeamId(id)) return '';
    var s = teamIdToNameMap[String(id)];
    return s != null ? String(s) : String(id);
  }

  function natRankFor(id, teamIdMetaMap, rankMap) {
    if (!isRealTeamId(id)) return null;
    var m = teamIdMetaMap[String(id)] || {};
    if (m.natl_rank != null && Number.isFinite(Number(m.natl_rank))) return Number(m.natl_rank);
    if (rankMap && rankMap[String(id)] != null) return Number(rankMap[String(id)]);
    return null;
  }

  function recordStrFor(id, teamIdMetaMap) {
    if (!isRealTeamId(id)) return '';
    var m = teamIdMetaMap[String(id)] || {};
    if (!Object.prototype.hasOwnProperty.call(m, 'W') && !Object.prototype.hasOwnProperty.call(m, 'L')) return '';
    var w = Number.isFinite(Number(m.W)) ? Number(m.W) : 0;
    var l = Number.isFinite(Number(m.L)) ? Number(m.L) : 0;
    return w + '-' + l;
  }

  function seedFor(id, seeds) {
    if (!seeds || !isRealTeamId(id)) return null;
    var s = seeds[String(id)];
    if (s == null) s = seeds[id];
    return s != null ? Number(s) : null;
  }

  function buildRankMap(topData) {
    var m = {};
    (topData && topData.rankings ? topData.rankings : []).forEach(function (r) {
      if (r && r.team_id != null && r.natl_rank != null) m[String(r.team_id)] = Number(r.natl_rank);
    });
    return m;
  }

  function scoresFor(m, hid, aid, hName, aName) {
    var sc = (m && m.score) || {};
    var hs = sc[hid];
    if (hs == null) hs = sc[hName];
    var as = sc[aid];
    if (as == null) as = sc[aName];
    return { hs: hs != null ? hs : '', as: as != null ? as : '' };
  }

  function conferenceDisplayModel(week, bracket, allBrackets) {
    var r1 = padMatchups(bracket.round1, 4);
    var r2 = padMatchups(bracket.round2, 2);
    var fin = bracket.final && bracket.final[0] ? bracket.final[0] : null;
    if (allBrackets) return { r1: r1, r2: r2, fin: fin };
    if (week < 27) return { r1: [null, null, null, null], r2: [null, null], fin: null };
    if (week === 27) return { r1: r1, r2: [null, null], fin: null };
    if (week === 28) return { r1: r1, r2: r2, fin: null };
    return { r1: r1, r2: r2, fin: fin };
  }

  function nationalDisplayModel(week, bracket, allBrackets) {
    var r1 = padMatchups(bracket.round1, 4);
    var r2 = padMatchups(bracket.round2, 2);
    var fin = bracket.final && bracket.final[0] ? bracket.final[0] : null;
    if (allBrackets) return { r1: r1, r2: r2, fin: fin };
    if (week < 32) return { r1: [null, null, null, null], r2: [null, null], fin: null };
    if (week === 32) return { r1: r1, r2: [null, null], fin: null };
    if (week === 33) return { r1: r1, r2: r2, fin: null };
    return { r1: r1, r2: r2, fin: fin };
  }

  function detectRegionShape(bracket) {
    var r1 = bracket.round1 || [];
    var fin = bracket.final || [];
    if (!r1.length && fin.length === 1) return '2';
    if (r1.length === 1 && fin.length === 1) return '3';
    return '4';
  }

  function regionByeTeamId(finalM) {
    if (!finalM) return null;
    var h = finalM.home_team;
    var a = finalM.away_team;
    if (String(h).indexOf('R1_') === 0) return isRealTeamId(a) ? a : null;
    if (String(a).indexOf('R1_') === 0) return isRealTeamId(h) ? h : null;
    return null;
  }

  function syntheticByeMatchup(teamId) {
    if (!isRealTeamId(teamId)) return null;
    return {
      home_team: teamId,
      away_team: BYE_SENTINEL,
      winner: teamId,
      score: {},
    };
  }

  function normalizeRegionRound1Matchups(bracket) {
    var fin = bracket.final && bracket.final[0] ? bracket.final[0] : null;
    var shape = detectRegionShape(bracket);
    if (shape === '4') {
      return padMatchups(bracket.round1, 2);
    }
    if (shape === '3') {
      var byeId = regionByeTeamId(fin);
      var real = (bracket.round1 || [])[0] || null;
      return [syntheticByeMatchup(byeId), real];
    }
    var h = fin && fin.home_team;
    var a = fin && fin.away_team;
    return [syntheticByeMatchup(h), syntheticByeMatchup(a)];
  }

  function colHeadDual(primaryLine) {
    var div = document.createElement('div');
    div.className = 'fcc-tb-col-head';
    var w = document.createElement('span');
    w.className = 'fcc-tb-col-head-primary';
    w.textContent = primaryLine;
    div.appendChild(w);
    return div;
  }

  function buildTrophyBlock(finalBadge) {
    var gradId = 'fcc-tb-tg-' + String(Math.random()).slice(2, 10);
    var trophy = document.createElement('div');
    trophy.className = 'fcc-tb-trophy';
    trophy.innerHTML = TROPHY_SVG.replace(/#tg/g, '#' + gradId).replace(/id="tg"/g, 'id="' + gradId + '"');
    var badge = document.createElement('div');
    badge.className = 'fcc-tb-trophy-badge';
    badge.textContent = finalBadge;
    trophy.appendChild(badge);
    return trophy;
  }

  function winnerTeamIdFromMatchup(m) {
    if (!m) return null;
    if (m.winner && isRealTeamId(m.winner)) return String(m.winner);
    var hid = m.home_team;
    var aid = m.away_team;
    if (isByeId(aid) && isRealTeamId(hid)) return String(hid);
    if (isByeId(hid) && isRealTeamId(aid)) return String(aid);
    return null;
  }

  function appendChampionNameplate(parent, fin, tier, teamIdToNameMap) {
    if (!fin || !fin.winner || !isRealTeamId(fin.winner)) return;
    var plate = document.createElement('div');
    plate.className = 'fcc-tb-champ-plate';
    var eyebrow = document.createElement('div');
    eyebrow.className = 'fcc-tb-champ-plate__eyebrow';
    eyebrow.textContent = CHAMP_EYEBROW[tier] || 'Champion';
    var name = document.createElement('div');
    name.className = 'fcc-tb-champ-plate__name';
    name.textContent = teamName(fin.winner, teamIdToNameMap) || 'Champion';
    plate.appendChild(eyebrow);
    plate.appendChild(name);
    parent.appendChild(plate);
  }

  function createBannerEl(teamName) {
    var wrap = document.createElement('span');
    wrap.className = 'fcc-tb-logo';
    var img = document.createElement('img');
    img.src =
      typeof getTeamAssetPath === 'function'
        ? getTeamAssetPath(teamName || '', 'banner_primary')
        : '/images/teams/general/general_banner_primary.jpg';
    img.alt = teamName || 'Team';
    img.loading = 'lazy';
    wrap.appendChild(img);
    return wrap;
  }

  function wrapHasUserTeam(wrap, userTeamId) {
    if (!wrap || !userTeamId) return false;
    var rows = wrap.querySelectorAll('.fcc-tb-team[data-team-id]');
    for (var i = 0; i < rows.length; i++) {
      if (String(rows[i].dataset.teamId) === String(userTeamId)) return true;
    }
    return false;
  }

  function createTeamRowEl(slot, userTeamId) {
    var row = document.createElement('div');
    row.className = 'fcc-tb-team';

    if (slot.bye) {
      row.classList.add('fcc-tb-team--bye');
      row.appendChild(elSpan('fcc-tb-seed', ''));
      var byeName = document.createElement('div');
      byeName.className = 'fcc-tb-name';
      var byeLabel = document.createElement('span');
      byeLabel.className = 'fcc-tb-bye-label';
      byeLabel.textContent = 'BYE';
      byeName.appendChild(byeLabel);
      row.appendChild(byeName);
      row.appendChild(elSpan('fcc-tb-score', ''));
      return row;
    }

    if (slot.tbd) {
      row.classList.add('fcc-tb-team--tbd');
      row.appendChild(elSpan('fcc-tb-seed', ''));
      var nameTbd = document.createElement('div');
      nameTbd.className = 'fcc-tb-name';
      nameTbd.appendChild(elSpan('fcc-tb-name-tbd', 'TBD'));
      row.appendChild(nameTbd);
      row.appendChild(elSpan('fcc-tb-score', ''));
      return row;
    }

    if (slot.teamId) row.dataset.teamId = String(slot.teamId);
    if (slot.isUser) row.classList.add('fcc-tb-team--user');
    if (slot.outcome === 'winner') row.classList.add('fcc-tb-team--winner');
    if (slot.outcome === 'loser') row.classList.add('fcc-tb-team--loser');
    if (slot.outcome === 'winner' && slot.showChampion) row.classList.add('fcc-tb-team--champion');

    row.appendChild(elSpan('fcc-tb-seed', slot.seed != null ? String(slot.seed) : ''));

    if (slot.name) {
      row.appendChild(createBannerEl(slot.name));
    } else {
      var logoSpacer = document.createElement('span');
      logoSpacer.className = 'fcc-tb-logo fcc-tb-logo--empty';
      row.appendChild(logoSpacer);
    }

    var nameCell = document.createElement('div');
    nameCell.className = 'fcc-tb-name';
    if (slot.regionChip) {
      var chip = document.createElement('span');
      chip.className = 'fcc-tb-region-chip';
      chip.textContent = slot.regionChip;
      nameCell.appendChild(chip);
    }
    if (slot.rank != null && !slot.revealMode) {
      var rk = document.createElement('span');
      rk.className = 'fcc-tb-rank-prefix';
      rk.textContent = '#' + slot.rank + ' ';
      nameCell.appendChild(rk);
    }
    var nm = document.createElement('span');
    nm.className = 'fcc-tb-name-text';
    nm.textContent = slot.name || '';
    nameCell.appendChild(nm);
    if (slot.showCrown) {
      nameCell.insertAdjacentHTML('beforeend', CROWN_SVG);
    }
    if (slot.recordStr && !slot.revealMode) {
      var rec = document.createElement('span');
      rec.className = 'fcc-tb-record';
      rec.textContent = '\u00a0' + slot.recordStr;
      nameCell.appendChild(rec);
    }
    row.appendChild(nameCell);

    row.appendChild(elSpan('fcc-tb-score', slot.score !== '' && slot.score != null ? String(slot.score) : ''));
    return row;
  }

  function elSpan(cls, text) {
    var s = document.createElement('span');
    if (cls) s.className = cls;
    s.textContent = text;
    return s;
  }

  function buildSlot(id, m, side, seeds, teamIdToNameMap, teamIdMetaMap, userTeamId, rankMap, regionChip, opts) {
    opts = opts || {};
    if (!m || !isRealTeamId(id)) return { tbd: true };
    var opponentIsBye =
      side === 'home'
        ? String(m.away_team) === BYE_SENTINEL || isByeId(m.away_team)
        : String(m.home_team) === BYE_SENTINEL || isByeId(m.home_team);
    var w = m.winner;
    var won = w != null && String(w) === String(id);
    if (!won && opponentIsBye && isRealTeamId(id)) won = true;
    var lost = w != null && !won && isRealTeamId(w);
    var name = teamName(id, teamIdToNameMap);
    var sc = scoresFor(m, m.home_team, m.away_team, name, teamName(m.away_team, teamIdToNameMap));
    var score = opponentIsBye ? '' : side === 'home' ? sc.hs : sc.as;
    if (opts.revealMode) {
      won = false;
      lost = false;
      score = '';
    }
    return {
      tbd: false,
      teamId: id,
      seed: seedFor(id, seeds),
      rank: natRankFor(id, teamIdMetaMap, rankMap),
      name: name,
      recordStr: recordStrFor(id, teamIdMetaMap),
      score: score,
      isUser: userTeamId != null && String(userTeamId) === String(id),
      outcome: won ? 'winner' : lost ? 'loser' : null,
      regionChip: regionChip || null,
      showCrown: !!opts.showCrown && won,
      showChampion: !!opts.showChampion && won,
      revealMode: !!opts.revealMode,
    };
  }

  function createMatchupEl(m, seeds, teamIdToNameMap, teamIdMetaMap, userTeamId, rankMap, natChips, opts) {
    opts = opts || {};
    var wrap = document.createElement('div');
    wrap.className = 'fcc-tb-mu-wrap';
    var card = document.createElement('div');
    card.className = 'fcc-tb-mu';

    if (!m) {
      card.classList.add('fcc-tb-mu--tbd');
      card.appendChild(createTeamRowEl({ tbd: true }, userTeamId));
      card.appendChild(createTeamRowEl({ tbd: true }, userTeamId));
      wrap.appendChild(card);
      return wrap;
    }

    var hid = m.home_team;
    var aid = m.away_team;
    var chipH = natChips ? natChips[String(hid)] : null;
    var chipA = natChips ? natChips[String(aid)] : null;
    var homeIsBye = String(hid) === BYE_SENTINEL || isByeId(hid);
    var awayIsBye = String(aid) === BYE_SENTINEL || isByeId(aid);

    if (!isRealTeamId(hid) && !isRealTeamId(aid) && !homeIsBye && !awayIsBye) {
      card.classList.add('fcc-tb-mu--tbd');
      card.appendChild(createTeamRowEl({ tbd: true }, userTeamId));
      card.appendChild(createTeamRowEl({ tbd: true }, userTeamId));
      wrap.appendChild(card);
      return wrap;
    }

    var slotOpts = {
      showCrown: !!opts.showCrown,
      showChampion: !!opts.showChampion,
      revealMode: !!opts.revealMode,
    };
    var topSlot = homeIsBye
      ? { bye: true }
      : isRealTeamId(hid)
        ? buildSlot(hid, m, 'home', seeds, teamIdToNameMap, teamIdMetaMap, userTeamId, rankMap, chipH, slotOpts)
        : { tbd: true };
    var botSlot = awayIsBye
      ? { bye: true }
      : isRealTeamId(aid)
        ? buildSlot(aid, m, 'away', seeds, teamIdToNameMap, teamIdMetaMap, userTeamId, rankMap, chipA, slotOpts)
        : { tbd: true };

    if ((topSlot.isUser || botSlot.isUser) && !card.classList.contains('fcc-tb-mu--tbd')) {
      card.classList.add('fcc-tb-mu--user');
    }
    if (opts.championship) card.classList.add('fcc-tb-mu--championship');

    card.appendChild(createTeamRowEl(topSlot, userTeamId));
    card.appendChild(createTeamRowEl(botSlot, userTeamId));
    if (!opts.revealMode) {
      wrap.dataset.winnerId = winnerTeamIdFromMatchup(m) || '';
    }
    wrap.appendChild(card);
    return wrap;
  }

  function buildNationalRegionChips(teamIdMetaMap, bracket) {
    var chips = {};
    function note(id) {
      if (!isRealTeamId(id)) return;
      var r = (teamIdMetaMap[String(id)] || {}).region;
      if (r != null && String(r).length === 1) chips[String(id)] = String(r).toUpperCase();
    }
    (bracket.round1 || []).forEach(function (m) {
      if (m) {
        note(m.home_team);
        note(m.away_team);
      }
    });
    (bracket.round2 || []).forEach(function (m) {
      if (m) {
        note(m.home_team);
        note(m.away_team);
      }
    });
    if (bracket.final && bracket.final[0]) {
      var f = bracket.final[0];
      note(f.home_team);
      note(f.away_team);
    }
    return chips;
  }

  function connectorToneFromWrap(wrap, userTeamId, revealMode, isR1) {
    if (revealMode) {
      if (isR1 && wrapHasUserTeam(wrap, userTeamId)) return 'user';
      return 'undecided';
    }
    if (!wrap) return 'undecided';
    var winnerId = wrap.dataset.winnerId;
    if (!winnerId) {
      var winRow = wrap.querySelector('.fcc-tb-team--winner');
      winnerId = winRow && winRow.dataset.teamId ? winRow.dataset.teamId : '';
    }
    if (!winnerId) return 'undecided';
    if (userTeamId && String(winnerId) === String(userTeamId)) return 'user';
    return 'winner';
  }

  function applyLineStyle(lineEl, tone) {
    if (tone === 'user') {
      lineEl.setAttribute('stroke', '#2bd66a');
      lineEl.setAttribute('stroke-width', '2.4');
      lineEl.setAttribute('stroke-linecap', 'round');
      lineEl.setAttribute('filter', 'url(#fcc-tb-conn-glow-green)');
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
    var defs = svg.querySelector('defs');
    if (defs) return;
    defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
    var filter = document.createElementNS('http://www.w3.org/2000/svg', 'filter');
    filter.setAttribute('id', 'fcc-tb-conn-glow-green');
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

  function renderClassic8(container, model, opts) {
    var seeds = opts.seeds || {};
    var teamIdToNameMap = opts.teamIdToNameMap || {};
    var teamIdMetaMap = opts.teamIdMetaMap || {};
    var userTeamId = opts.userTeamId;
    var rankMap = opts.rankMap || {};
    var natChips = opts.nationalRegionChips || null;
    var wl = opts.weekLines || {};
    var finalBadge = opts.finalBadge || '★ CONFERENCE ★';
    var tier = opts.tier || 'conference';
    var revealMode = !!opts.revealMode;

    var grid = document.createElement('div');
    grid.className = 'fcc-tb-classic fcc-tb-enter';
    if (revealMode) grid.dataset.revealMode = '1';

    function col(classExtra, headline, innerNodes) {
      var c = document.createElement('div');
      c.className = 'fcc-tb-col ' + classExtra;
      c.appendChild(colHeadDual(headline));
      innerNodes.forEach(function (node) {
        c.appendChild(node);
      });
      return c;
    }

    var r1 = model.r1;
    var r2 = model.r2;
    var fin = model.fin;
    var slotOpts = { revealMode: revealMode };
    var finOpts = revealMode
      ? { championship: true, revealMode: true }
      : { championship: true, showCrown: true, showChampion: true, revealMode: false };

    grid.appendChild(
      col('fcc-tb-col--r1l', wl.r1 || 'WEEK 27 · ROUND 1', [
        createMatchupEl(r1[0], seeds, teamIdToNameMap, teamIdMetaMap, userTeamId, rankMap, natChips, slotOpts),
        createMatchupEl(r1[1], seeds, teamIdToNameMap, teamIdMetaMap, userTeamId, rankMap, natChips, slotOpts),
      ])
    );

    grid.appendChild(
      col('fcc-tb-col--r2l', wl.r2 || 'WEEK 28 · SEMIFINALS', [
        createMatchupEl(r2[0], seeds, teamIdToNameMap, teamIdMetaMap, userTeamId, rankMap, natChips, slotOpts),
      ])
    );

    var mid = document.createElement('div');
    mid.className = 'fcc-tb-col fcc-tb-col--final';
    mid.appendChild(colHeadDual(wl.fn || 'WEEK 29 · CHAMPIONSHIP'));
    mid.appendChild(buildTrophyBlock(finalBadge));
    mid.appendChild(createMatchupEl(fin, seeds, teamIdToNameMap, teamIdMetaMap, userTeamId, rankMap, natChips, finOpts));
    if (!revealMode) appendChampionNameplate(mid, fin, tier, teamIdToNameMap);
    grid.appendChild(mid);

    grid.appendChild(
      col('fcc-tb-col--r2r', wl.r2 || 'WEEK 28 · SEMIFINALS', [
        createMatchupEl(r2[1], seeds, teamIdToNameMap, teamIdMetaMap, userTeamId, rankMap, natChips, slotOpts),
      ])
    );

    grid.appendChild(
      col('fcc-tb-col--r1r', wl.r1 || 'WEEK 27 · ROUND 1', [
        createMatchupEl(r1[2], seeds, teamIdToNameMap, teamIdMetaMap, userTeamId, rankMap, natChips, slotOpts),
        createMatchupEl(r1[3], seeds, teamIdToNameMap, teamIdMetaMap, userTeamId, rankMap, natChips, slotOpts),
      ])
    );

    container.appendChild(grid);
    scheduleConnectorRedraw(grid, userTeamId, { revealMode: revealMode });
  }

  function scheduleConnectorRedraw(grid, userTeamId, options) {
    options = options || {};
    if (!grid || grid.dataset.tbConnScheduled === '1') return;
    grid.dataset.tbConnScheduled = '1';
    var run = function () {
      grid.dataset.tbConnScheduled = '0';
      if (grid.classList.contains('fcc-tb-region')) drawRegionConnectors(grid, userTeamId, options);
      else drawClassicConnectors(grid, userTeamId, options);
    };
    if (typeof requestAnimationFrame === 'function') {
      requestAnimationFrame(function () {
        requestAnimationFrame(run);
      });
    } else {
      setTimeout(run, 30);
    }
  }

  function drawClassicConnectors(grid, userTeamId, options) {
    options = options || {};
    var revealMode = !!options.revealMode;
    var old = grid.querySelector('svg.fcc-tb-conn');
    if (old) old.remove();
    var wraps = grid.querySelectorAll(':scope > .fcc-tb-col > .fcc-tb-mu-wrap');
    if (wraps.length < 7) return;

    var ns = 'http://www.w3.org/2000/svg';
    var grect = grid.getBoundingClientRect();
    if (grect.width < 40 || grect.height < 40) return;

    var svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('class', 'fcc-tb-conn');
    svg.setAttribute('viewBox', '0 0 ' + grect.width + ' ' + grect.height);
    svg.setAttribute('width', String(grect.width));
    svg.setAttribute('height', String(grect.height));
    svg.style.position = 'absolute';
    svg.style.left = '0';
    svg.style.top = '0';
    svg.style.pointerEvents = 'none';
    svg.style.overflow = 'visible';
    ensureConnDefs(svg);

    function line(x1, y1, x2, y2, tone) {
      var p = document.createElementNS(ns, 'line');
      p.setAttribute('x1', x1);
      p.setAttribute('y1', y1);
      p.setAttribute('x2', x2);
      p.setAttribute('y2', y2);
      applyLineStyle(p, tone);
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

    var t0 = connectorToneFromWrap(w0, userTeamId, revealMode, true);
    var t1 = connectorToneFromWrap(w1, userTeamId, revealMode, true);
    var t2 = connectorToneFromWrap(w2, userTeamId, revealMode, false);
    var t3 = connectorToneFromWrap(w3, userTeamId, revealMode, false);
    var t4 = connectorToneFromWrap(w4, userTeamId, revealMode, false);
    var t5 = connectorToneFromWrap(w5, userTeamId, revealMode, true);
    var t6 = connectorToneFromWrap(w6, userTeamId, revealMode, true);

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

  function drawRegionConnectors(grid, userTeamId, options) {
    options = options || {};
    var revealMode = !!options.revealMode;
    var old = grid.querySelector('svg.fcc-tb-conn');
    if (old) old.remove();
    var wraps = grid.querySelectorAll(':scope > .fcc-tb-region-col .fcc-tb-mu-wrap');
    if (wraps.length < 3) return;

    var ns = 'http://www.w3.org/2000/svg';
    var grect = grid.getBoundingClientRect();
    if (grect.width < 40 || grect.height < 40) return;

    var svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('class', 'fcc-tb-conn');
    svg.setAttribute('viewBox', '0 0 ' + grect.width + ' ' + grect.height);
    svg.setAttribute('width', String(grect.width));
    svg.setAttribute('height', String(grect.height));
    svg.style.position = 'absolute';
    svg.style.left = '0';
    svg.style.top = '0';
    svg.style.pointerEvents = 'none';
    svg.style.overflow = 'visible';
    ensureConnDefs(svg);

    function line(x1, y1, x2, y2, tone) {
      var p = document.createElementNS(ns, 'line');
      p.setAttribute('x1', x1);
      p.setAttribute('y1', y1);
      p.setAttribute('x2', x2);
      p.setAttribute('y2', y2);
      applyLineStyle(p, tone);
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
    var c0 = cxWrap(w0);
    var c1 = cxWrap(w1);
    var cf = cxWrap(w2);
    var t0 = connectorToneFromWrap(w0, userTeamId, revealMode, true);
    var t1 = connectorToneFromWrap(w1, userTeamId, revealMode, true);
    var tf = connectorToneFromWrap(w2, userTeamId, revealMode, false);
    var midY = (c0.y + c1.y) / 2;

    line(c0.x, c0.y, cf.xl, c0.y, t0);
    line(c1.x, c1.y, cf.xl, c1.y, t1);
    line(cf.xl, midY, cf.xl, cf.y, tf);

    grid.style.position = 'relative';
    grid.insertBefore(svg, grid.firstChild);
  }

  function renderRegionBracket(container, bracket, opts) {
    var seeds = opts.seeds || {};
    var teamIdToNameMap = opts.teamIdToNameMap || {};
    var teamIdMetaMap = opts.teamIdMetaMap || {};
    var userTeamId = opts.userTeamId;
    var rankMap = opts.rankMap || {};
    var tier = opts.tier || 'region';
    var revealMode = !!opts.revealMode;
    var r1 = normalizeRegionRound1Matchups(bracket);
    var fin = bracket.final && bracket.final[0] ? bracket.final[0] : null;
    var slotOpts = { revealMode: revealMode };
    var finOpts = revealMode
      ? { championship: true, revealMode: true }
      : { championship: true, showCrown: true, showChampion: true, revealMode: false };

    var frame = document.createElement('div');
    frame.className = 'fcc-tb-region fcc-tb-region--full fcc-tb-enter';
    if (revealMode) frame.dataset.revealMode = '1';

    var c0 = document.createElement('div');
    c0.className = 'fcc-tb-region-col';
    c0.appendChild(colHeadDual('WEEK 30 · ROUND 1'));
    c0.appendChild(createMatchupEl(r1[0], seeds, teamIdToNameMap, teamIdMetaMap, userTeamId, rankMap, null, slotOpts));
    c0.appendChild(createMatchupEl(r1[1], seeds, teamIdToNameMap, teamIdMetaMap, userTeamId, rankMap, null, slotOpts));

    var c1 = document.createElement('div');
    c1.className = 'fcc-tb-region-col';
    c1.appendChild(colHeadDual('WEEK 31 · CHAMPIONSHIP'));
    c1.appendChild(buildTrophyBlock('★ REGION ★'));
    var champWrap = document.createElement('div');
    champWrap.className = 'fcc-tb-mu-wrap fcc-tb-mu-wrap--champ fcc-tb-mu-wrap--region4-champ';
    champWrap.appendChild(
      createMatchupEl(fin, seeds, teamIdToNameMap, teamIdMetaMap, userTeamId, rankMap, null, finOpts)
    );
    c1.appendChild(champWrap);
    if (!revealMode) appendChampionNameplate(c1, fin, tier, teamIdToNameMap);

    var c2 = document.createElement('div');
    c2.className = 'fcc-tb-region-col fcc-tb-region-col--spacer';

    frame.appendChild(c0);
    frame.appendChild(c1);
    frame.appendChild(c2);
    container.appendChild(frame);
    scheduleConnectorRedraw(frame, userTeamId, { revealMode: revealMode });
  }

  function renderInto(bodyEl, config) {
    bodyEl.innerHTML = '';
    var layout = config.layout || 'full';
    var tier = config.tierHint || inferTier(config.sectionTitle);
    if (layout === 'compact4') tier = 'region';
    var bracket = config.bracket || {};
    var topData = config.topData || {};
    var week = Number(config.displayWeek != null ? config.displayWeek : topData.week || 0);
    var allBrackets = !!config.allBrackets;
    var revealMode = !!config.revealMode;
    var seeds = config.seeds || {};
    var teamIdToNameMap = config.teamIdToNameMap || {};
    var teamIdMetaMap = config.teamIdMetaMap || {};
    var userTeamId = config.userTeamId;
    var rankMap = buildRankMap(topData);

    if (tier === 'region' || layout === 'compact4') {
      renderRegionBracket(bodyEl, bracket, {
        seeds: seeds,
        teamIdToNameMap: teamIdToNameMap,
        teamIdMetaMap: teamIdMetaMap,
        userTeamId: userTeamId,
        rankMap: rankMap,
        tier: tier,
        revealMode: revealMode,
      });
      return;
    }

    var natChips = tier === 'national' ? buildNationalRegionChips(teamIdMetaMap, bracket) : null;

    var model =
      tier === 'national' ? nationalDisplayModel(week, bracket, allBrackets) : conferenceDisplayModel(week, bracket, allBrackets);

    var weekLines =
      tier === 'national'
        ? {
            r1: 'WEEK 32 · QUARTERFINALS',
            r2: 'WEEK 33 · SEMIFINALS',
            fn: 'WEEK 34 · CHAMPIONSHIP',
          }
        : {
            r1: 'WEEK 27 · ROUND 1',
            r2: 'WEEK 28 · SEMIFINALS',
            fn: 'WEEK 29 · CHAMPIONSHIP',
          };

    var badge = tier === 'national' ? '★ NATIONAL ★' : '★ CONFERENCE ★';

    renderClassic8(bodyEl, model, {
      seeds: seeds,
      teamIdToNameMap: teamIdToNameMap,
      teamIdMetaMap: teamIdMetaMap,
      userTeamId: userTeamId,
      rankMap: rankMap,
      nationalRegionChips: natChips,
      weekLines: weekLines,
      finalBadge: badge,
      tier: tier,
      revealMode: revealMode,
    });
  }

  function inferTier(sectionTitle) {
    var t = String(sectionTitle || '');
    if (t.indexOf('National') === 0 || t === 'National Tournament') return 'national';
    if (t.indexOf('Region') === 0) return 'region';
    return 'conference';
  }

  global.FccTournamentStyleA = {
    renderInto: renderInto,
    inferTier: inferTier,
    scheduleConnectorRedraw: scheduleConnectorRedraw,
  };
})(typeof window !== 'undefined' ? window : this);
