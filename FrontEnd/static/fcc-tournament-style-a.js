/**
 * FCC Tournament tab — Style A "Classic horizontal" bracket (dark theme).
 * Consumes the same franchise bracket payloads as renderBracketShared (round1 / round2 / final).
 */
(function (global) {
  'use strict';

  function isRealTeamId(id) {
    if (id == null || id === '') return false;
    return /^[a-f0-9]{24}$/i.test(String(id));
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

  /** Single monospace column title, e.g. "WEEK 27 · ROUND 1" */
  function colHeadDual(primaryLine) {
    var div = document.createElement('div');
    div.className = 'fcc-tb-col-head';
    var w = document.createElement('span');
    w.className = 'fcc-tb-col-head-primary';
    w.textContent = primaryLine;
    div.appendChild(w);
    return div;
  }

  function createTeamRowEl(slot, userTeamId) {
    var row = document.createElement('div');
    row.className = 'fcc-tb-team';
    if (slot.tbd) {
      row.classList.add('fcc-tb-team--tbd');
      row.appendChild(elSpan('fcc-tb-seed', ''));
      var name = document.createElement('div');
      name.className = 'fcc-tb-name';
      name.appendChild(elSpan('fcc-tb-name-tbd', 'TBD'));
      row.appendChild(name);
      row.appendChild(elSpan('fcc-tb-score', ''));
      return row;
    }
    if (slot.isUser) row.classList.add('fcc-tb-team--user');
    if (slot.outcome === 'winner') row.classList.add('fcc-tb-team--winner');
    if (slot.outcome === 'loser') row.classList.add('fcc-tb-team--loser');

    row.appendChild(elSpan('fcc-tb-seed', slot.seed != null ? String(slot.seed) : ''));

    var nameCell = document.createElement('div');
    nameCell.className = 'fcc-tb-name';
    if (slot.regionChip) {
      var chip = document.createElement('span');
      chip.className = 'fcc-tb-region-chip';
      chip.textContent = slot.regionChip;
      nameCell.appendChild(chip);
    }
    if (slot.rank != null) {
      var rk = document.createElement('span');
      rk.className = 'fcc-tb-rank-prefix';
      rk.textContent = '#' + slot.rank + ' ';
      nameCell.appendChild(rk);
    }
    var nm = document.createElement('span');
    nm.className = 'fcc-tb-name-text';
    nm.textContent = slot.name || '';
    nameCell.appendChild(nm);
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

  function buildSlot(id, m, side, seeds, teamIdToNameMap, teamIdMetaMap, userTeamId, rankMap, regionChip) {
    if (!m || !isRealTeamId(id)) return { tbd: true };
    var w = m.winner;
    var won = w != null && String(w) === String(id);
    var lost = w != null && !won;
    var name = teamName(id, teamIdToNameMap);
    var sc = scoresFor(m, m.home_team, m.away_team, name, teamName(m.away_team, teamIdToNameMap));
    var score = side === 'home' ? sc.hs : sc.as;
    return {
      tbd: false,
      seed: seedFor(id, seeds),
      rank: natRankFor(id, teamIdMetaMap, rankMap),
      name: name,
      score: score,
      isUser: userTeamId != null && String(userTeamId) === String(id),
      outcome: won ? 'winner' : lost ? 'loser' : null,
      regionChip: regionChip || null,
    };
  }

  function createMatchupEl(m, seeds, teamIdToNameMap, teamIdMetaMap, userTeamId, rankMap, natChips) {
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

    if (!isRealTeamId(hid) && !isRealTeamId(aid)) {
      card.classList.add('fcc-tb-mu--tbd');
      card.appendChild(createTeamRowEl({ tbd: true }, userTeamId));
      card.appendChild(createTeamRowEl({ tbd: true }, userTeamId));
      wrap.appendChild(card);
      return wrap;
    }

    var topSlot = isRealTeamId(hid) ? buildSlot(hid, m, 'home', seeds, teamIdToNameMap, teamIdMetaMap, userTeamId, rankMap, chipH) : { tbd: true };
    var botSlot = isRealTeamId(aid) ? buildSlot(aid, m, 'away', seeds, teamIdToNameMap, teamIdMetaMap, userTeamId, rankMap, chipA) : { tbd: true };

    if ((topSlot.isUser || botSlot.isUser) && !card.classList.contains('fcc-tb-mu--tbd')) {
      card.classList.add('fcc-tb-mu--user');
    }

    card.appendChild(createTeamRowEl(topSlot, userTeamId));
    card.appendChild(createTeamRowEl(botSlot, userTeamId));
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

  function renderClassic8(container, model, opts) {
    var seeds = opts.seeds || {};
    var teamIdToNameMap = opts.teamIdToNameMap || {};
    var teamIdMetaMap = opts.teamIdMetaMap || {};
    var userTeamId = opts.userTeamId;
    var rankMap = opts.rankMap || {};
    var natChips = opts.nationalRegionChips || null;
    var wl = opts.weekLines || {};
    var finalBadge = opts.finalBadge || '★ CONFERENCE ★';

    var grid = document.createElement('div');
    grid.className = 'fcc-tb-classic';

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

    grid.appendChild(
      col('fcc-tb-col--r1l', wl.r1 || 'WEEK 27 · ROUND 1', [
        createMatchupEl(r1[0], seeds, teamIdToNameMap, teamIdMetaMap, userTeamId, rankMap, natChips),
        createMatchupEl(r1[1], seeds, teamIdToNameMap, teamIdMetaMap, userTeamId, rankMap, natChips),
      ])
    );

    grid.appendChild(
      col('fcc-tb-col--r2l', wl.r2 || 'WEEK 28 · SEMIFINALS', [
        createMatchupEl(r2[0], seeds, teamIdToNameMap, teamIdMetaMap, userTeamId, rankMap, natChips),
      ])
    );

    var mid = document.createElement('div');
    mid.className = 'fcc-tb-col fcc-tb-col--final';
    mid.appendChild(colHeadDual(wl.fn || 'WEEK 29 · CHAMPIONSHIP'));
    var trophy = document.createElement('div');
    trophy.className = 'fcc-tb-trophy';
    var badge = document.createElement('div');
    badge.className = 'fcc-tb-trophy-badge';
    badge.textContent = finalBadge;
    trophy.appendChild(badge);
    mid.appendChild(trophy);
    mid.appendChild(createMatchupEl(fin, seeds, teamIdToNameMap, teamIdMetaMap, userTeamId, rankMap, natChips));
    grid.appendChild(mid);

    grid.appendChild(
      col('fcc-tb-col--r2r', wl.r2 || 'WEEK 28 · SEMIFINALS', [
        createMatchupEl(r2[1], seeds, teamIdToNameMap, teamIdMetaMap, userTeamId, rankMap, natChips),
      ])
    );

    grid.appendChild(
      col('fcc-tb-col--r1r', wl.r1 || 'WEEK 27 · ROUND 1', [
        createMatchupEl(r1[2], seeds, teamIdToNameMap, teamIdMetaMap, userTeamId, rankMap, natChips),
        createMatchupEl(r1[3], seeds, teamIdToNameMap, teamIdMetaMap, userTeamId, rankMap, natChips),
      ])
    );

    container.appendChild(grid);
    scheduleConnectorRedraw(grid);
  }

  /** Debounced connector paint for 5-column classic brackets */
  function scheduleConnectorRedraw(grid) {
    if (!grid || grid.dataset.tbConnScheduled === '1') return;
    grid.dataset.tbConnScheduled = '1';
    var run = function () {
      grid.dataset.tbConnScheduled = '0';
      drawClassicConnectors(grid);
    };
    if (typeof requestAnimationFrame === 'function') {
      requestAnimationFrame(function () {
        requestAnimationFrame(run);
      });
    } else {
      setTimeout(run, 30);
    }
  }

  function drawClassicConnectors(grid) {
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

    function line(x1, y1, x2, y2) {
      var p = document.createElementNS(ns, 'line');
      p.setAttribute('x1', x1);
      p.setAttribute('y1', y1);
      p.setAttribute('x2', x2);
      p.setAttribute('y2', y2);
      p.setAttribute('stroke', 'rgba(255,255,255,0.10)');
      p.setAttribute('stroke-width', '1');
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

    line(c0a.x, c0a.y, midL, c0a.y);
    line(midL, c0a.y, midL, c1.y);
    line(midL, c1.y, c1.xl, c1.y);

    line(c0b.x, c0b.y, midL, c0b.y);
    line(midL, c0b.y, midL, c1.y);

    line(c1.x, c1.y, cf.xl, cf.y);
    line(c1r.xl, c1r.y, cf.x, cf.y);

    line(c4a.xl, c4a.y, midR, c4a.y);
    line(midR, c4a.y, midR, c1r.y);
    line(midR, c1r.y, c1r.x, c1r.y);

    line(c4b.xl, c4b.y, midR, c4b.y);
    line(midR, c4b.y, midR, c1r.y);

    grid.style.position = 'relative';
    grid.insertBefore(svg, grid.firstChild);
  }

  function renderRegion4(container, bracket, opts) {
    var seeds = opts.seeds || {};
    var teamIdToNameMap = opts.teamIdToNameMap || {};
    var teamIdMetaMap = opts.teamIdMetaMap || {};
    var userTeamId = opts.userTeamId;
    var rankMap = opts.rankMap || {};
    var r1 = padMatchups(bracket.round1, 2);
    var fin = bracket.final && bracket.final[0] ? bracket.final[0] : null;

    var frame = document.createElement('div');
    frame.className = 'fcc-tb-region fcc-tb-region--4';

    var c0 = document.createElement('div');
    c0.className = 'fcc-tb-region-col';
    c0.appendChild(colHeadDual('WEEK 30 · ROUND 1'));
    c0.appendChild(createMatchupEl(r1[0], seeds, teamIdToNameMap, teamIdMetaMap, userTeamId, rankMap, null));
    c0.appendChild(createMatchupEl(r1[1], seeds, teamIdToNameMap, teamIdMetaMap, userTeamId, rankMap, null));

    var c1 = document.createElement('div');
    c1.className = 'fcc-tb-region-col';
    c1.appendChild(colHeadDual('WEEK 31 · CHAMPIONSHIP'));
    var champWrap = document.createElement('div');
    champWrap.className = 'fcc-tb-mu-wrap fcc-tb-mu-wrap--champ';
    var inner = createMatchupEl(fin, seeds, teamIdToNameMap, teamIdMetaMap, userTeamId, rankMap, null);
    var muEl = inner.querySelector('.fcc-tb-mu');
    if (muEl) muEl.classList.add('fcc-tb-mu--championship');
    champWrap.appendChild(inner);
    c1.appendChild(champWrap);

    var c2 = document.createElement('div');
    c2.className = 'fcc-tb-region-col fcc-tb-region-col--spacer';

    frame.appendChild(c0);
    frame.appendChild(c1);
    frame.appendChild(c2);
    container.appendChild(frame);
  }

  function renderRegion3(container, bracket, opts) {
    var seeds = opts.seeds || {};
    var teamIdToNameMap = opts.teamIdToNameMap || {};
    var teamIdMetaMap = opts.teamIdMetaMap || {};
    var userTeamId = opts.userTeamId;
    var rankMap = opts.rankMap || {};
    var r1 = (bracket.round1 || [])[0] || null;
    var fin = bracket.final && bracket.final[0] ? bracket.final[0] : null;
    var byeId = regionByeTeamId(fin);

    var frame = document.createElement('div');
    frame.className = 'fcc-tb-region fcc-tb-region--3';

    var c0 = document.createElement('div');
    c0.className = 'fcc-tb-region-col';
    c0.appendChild(colHeadDual('WEEK 30 · ROUND 1'));
    c0.appendChild(createMatchupEl(r1, seeds, teamIdToNameMap, teamIdMetaMap, userTeamId, rankMap, null));
    var bye = document.createElement('div');
    bye.className = 'fcc-tb-bye-card';
    if (byeId && isRealTeamId(byeId)) {
      var sd = seedFor(byeId, seeds);
      var rk = natRankFor(byeId, teamIdMetaMap, rankMap);
      var bs = document.createElement('span');
      bs.className = 'fcc-tb-bye-seed';
      if (sd != null) bs.textContent = String(sd);
      var bn = document.createElement('span');
      bn.className = 'fcc-tb-bye-name';
      if (rk != null) {
        var rp = document.createElement('span');
        rp.className = 'fcc-tb-rank-prefix';
        rp.textContent = '#' + rk + ' ';
        bn.appendChild(rp);
      }
      bn.appendChild(document.createTextNode(teamName(byeId, teamIdToNameMap)));
      var bb = document.createElement('span');
      bb.className = 'fcc-tb-bye-badge';
      bb.textContent = 'BYE →';
      bye.appendChild(bs);
      bye.appendChild(bn);
      bye.appendChild(bb);
    }
    c0.appendChild(bye);

    var c1 = document.createElement('div');
    c1.className = 'fcc-tb-region-col';
    c1.appendChild(colHeadDual('WEEK 31 · CHAMPIONSHIP'));
    var cw = document.createElement('div');
    cw.className = 'fcc-tb-mu-wrap fcc-tb-mu-wrap--champ';
    var inner = createMatchupEl(fin, seeds, teamIdToNameMap, teamIdMetaMap, userTeamId, rankMap, null);
    var muR3 = inner.querySelector('.fcc-tb-mu');
    if (muR3) muR3.classList.add('fcc-tb-mu--championship');
    cw.appendChild(inner);
    c1.appendChild(cw);

    var c2 = document.createElement('div');
    c2.className = 'fcc-tb-region-col fcc-tb-region-col--spacer';

    frame.appendChild(c0);
    frame.appendChild(c1);
    frame.appendChild(c2);
    container.appendChild(frame);
  }

  function renderRegion2(container, bracket, opts) {
    var seeds = opts.seeds || {};
    var teamIdToNameMap = opts.teamIdToNameMap || {};
    var teamIdMetaMap = opts.teamIdMetaMap || {};
    var userTeamId = opts.userTeamId;
    var rankMap = opts.rankMap || {};
    var fin = bracket.final && bracket.final[0] ? bracket.final[0] : null;

    var frame = document.createElement('div');
    frame.className = 'fcc-tb-region fcc-tb-region--2';
    var note = document.createElement('div');
    note.className = 'fcc-tb-both-bye-note';
    note.textContent = 'Both teams earned byes — Week 30 skipped. Region Championship plays in Week 31.';
    frame.appendChild(note);

    var col = document.createElement('div');
    col.className = 'fcc-tb-region-col fcc-tb-region-col--solo';
    col.appendChild(colHeadDual('WEEK 31 · CHAMPIONSHIP'));
    var cw = document.createElement('div');
    cw.className = 'fcc-tb-mu-wrap fcc-tb-mu-wrap--champ';
    var inner = createMatchupEl(fin, seeds, teamIdToNameMap, teamIdMetaMap, userTeamId, rankMap, null);
    var muN = inner.querySelector('.fcc-tb-mu');
    if (muN) muN.classList.add('fcc-tb-mu--championship');
    cw.appendChild(inner);
    col.appendChild(cw);
    frame.appendChild(col);
    container.appendChild(frame);
  }

  function renderInto(bodyEl, config) {
    bodyEl.innerHTML = '';
    var layout = config.layout || 'full';
    var tier = config.tierHint || inferTier(config.sectionTitle);
    if (layout === 'compact4') tier = 'region';
    var bracket = config.bracket || {};
    var topData = config.topData || {};
    var week = Number(topData.week || 0);
    var allBrackets = !!config.allBrackets;
    var seeds = config.seeds || {};
    var teamIdToNameMap = config.teamIdToNameMap || {};
    var teamIdMetaMap = config.teamIdMetaMap || {};
    var userTeamId = config.userTeamId;
    var rankMap = buildRankMap(topData);

    if (tier === 'region' || layout === 'compact4') {
      var shape = detectRegionShape(bracket);
      if (shape === '2') renderRegion2(bodyEl, bracket, { seeds: seeds, teamIdToNameMap: teamIdToNameMap, teamIdMetaMap: teamIdMetaMap, userTeamId: userTeamId, rankMap: rankMap });
      else if (shape === '3') renderRegion3(bodyEl, bracket, { seeds: seeds, teamIdToNameMap: teamIdToNameMap, teamIdMetaMap: teamIdMetaMap, userTeamId: userTeamId, rankMap: rankMap });
      else renderRegion4(bodyEl, bracket, { seeds: seeds, teamIdToNameMap: teamIdToNameMap, teamIdMetaMap: teamIdMetaMap, userTeamId: userTeamId, rankMap: rankMap });
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
