/**
 * Recruiting Hub — D1 (Prompt 1) + D2 Invite Dock (Prompt 2).
 *
 * The persistent hub shell in every phase: topbar + Recruit Pool anchor, the
 * calendar-driven phase strip, the passive story strip, and the pool (region A–H
 * collapse, sort, filters) with the shared lean ladder. Phase-aware:
 *   - Passive              → pool only (no dock), story strip.
 *   - Invite (wks 20–26)   → condensed pool + add-column, the INVITE DOCK on the right
 *                            (rank up to 20; Save Board → /franchise/recruiting-orders).
 *                            Execution stays in Run Training (not decoupled, by decision).
 *   - Signing / Results    → condensed pool + a transition dock linking to the existing
 *                            pages until Prompts 3–4 fold them in.
 *
 * Reuses window.RecruitingCommon and window.RecruitingSpine. Takes over recruiting.html.
 */
(function () {
  'use strict';

  var Common = window.RecruitingCommon;
  var Spine = window.RecruitingSpine;
  var ATTR_KEYS = Common.ATTR_KEYS;
  var REGION_ORDER = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'];
  var YEAR_FILTERS = [
    { value: 'all', label: 'All' },
    { value: 'Junior', label: 'JR' },
    { value: 'Sophomore', label: 'SO' },
    { value: 'Freshman', label: 'FR' },
    { value: 'JH', label: 'JH' }
  ];
  var SORTABLE = { name: 'text', pos: 'num', year: 'num', height: 'num', region: 'text', rt: 'num' };
  var INVITE_WEEKS = [20, 21, 22, 23, 24, 25, 26];
  var POS_ORDER = ['PG', 'SG', 'SF', 'PF', 'C'];
  var MAX_BOARD = 20;

  var context = Common.getQueryContext();
  var state = {
    week: 1, phase: 'passive', userTeamId: null, userRegion: '',
    recruits: [], byId: {}, newLeanIds: new Set(),
    board: [],                       // ordered recruit ids (invite phase)
    search: '', region: 'all', pos: 'all', year: 'all',
    view: 'all',                     // 'all' | 'watch' | 'leans' | 'unranked'
    watchlist: new Set(),            // unordered, uncapped shortlist of recruit ids
    wire: {},                        // Prompt 1 event log (recruiting_wire payload)
    boardSeededFromWatchlist: false, // drives the seed notice; cleared on save/reorder
    seedNoticeDismissed: false,
    sort: { key: 'rt', dir: 'desc' }, collapsed: {},
    drag: { from: null, over: null },
    // Signing Day (wk 35)
    alloc: {},                       // { recruitId: {points, promise} } — starts EMPTY
    rosterCapacity: {},              // from payload.roster_capacity
    competitionCounts: {},           // recruit_id -> programs funding him
    sTab: 'mine', sRegion: 'all', sSearch: '', week35Ran: false, flashId: null,
    // Results (D4)
    currentResultsWeek: null, weeklyDismissed: false, visitTree: null,
    playback: { index: 0, auto: false, done: false, timer: null },
    week35Results: {}, signFilter: 'all'
  };
  var SIGN = { TOTAL: 50, MAX_PER: 20, PROMISE_W: 18 };

  function boardActive() { return state.phase === 'invite'; }
  function attrClass(v) { return v >= 65 ? 'attr-hi' : v >= 40 ? 'attr-mid' : v >= 20 ? 'attr-lo' : 'attr-zero'; }
  function regionOf(rec) { var v = rec && rec.homeRegion ? String(rec.homeRegion).trim().toUpperCase() : ''; return v ? v.charAt(0) : ''; }
  // Recruit | Pos | RT | Yr | Ht | Rgn | Attributes | Lean | Watch — attributes are a
  // single cell of chips now, not 12 columns. +1 for the add column in the invite phase.
  function colspan() { return (boardActive() ? 1 : 0) + 9; }

  var CHEVRON = '<svg class="region-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M6 9l6 6 6-6"></path></svg>';
  var ARROW_UP = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6"><path d="M7 17L17 7M9 7h8v8"></path></svg>';
  var INFO = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="12" cy="12" r="9"></circle><path d="M12 11v5M12 7.5v.5"></path></svg>';
  var CHECK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M20 6L9 17l-5-5"></path></svg>';

  // Only the invite phase uses the standard pool+dock layout. Signing (day) and Results
  // are their own full-width bodies, handled in renderShell.
  function hasDock() { return boardActive(); }

  // ===================== POOL =====================
  // ---------- filters ----------
  // Region is a dropdown (9 options, rarely changed); Position and Year are segmented
  // controls (few options, switched constantly — a dropdown costs a click every time).
  function filteredRecruits() {
    var q = state.search.trim().toLowerCase();
    return state.recruits.filter(function (r) {
      if (state.region !== 'all' && regionOf(r) !== state.region) return false;
      if (state.pos !== 'all' && String(r.pos).toUpperCase() !== state.pos) return false;
      if (state.year !== 'all' && r.year !== state.year) return false;
      if (state.view === 'watch' && !state.watchlist.has(String(r.recruitId))) return false;
      if (state.view === 'leans' && !r.leansToUser) return false;
      if (state.view === 'unranked' && state.board.indexOf(r.recruitId) !== -1) return false;
      if (q && String(r.name).toLowerCase().indexOf(q) === -1) return false;
      return true;
    });
  }
  function sortValue(r, key) {
    switch (key) {
      case 'name': return r.name;
      case 'pos': return POS_ORDER.indexOf(String(r.pos).toUpperCase());
      case 'year': return Common.getYearSortValue(r.year);
      case 'height': return r.heightRaw;
      case 'region': return regionOf(r);
      case 'rt': return r.rt != null ? r.rt : -1;
      default: return r[key];
    }
  }
  function sortRecs(recs) {
    var key = state.sort.key, dir = state.sort.dir, num = SORTABLE[key] === 'num';
    return recs.slice().sort(function (a, b) {
      var av = sortValue(a, key), bv = sortValue(b, key), c;
      if (num) c = dir === 'asc' ? av - bv : bv - av;
      else c = dir === 'asc' ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
      return c || (b.rt != null ? b.rt : -1) - (a.rt != null ? a.rt : -1);
    });
  }
  function arrow(key) { return state.sort.key === key ? '<span class="arrow">' + (state.sort.dir === 'asc' ? '▲' : '▼') + '</span>' : ''; }
  function th(key, label, cls) {
    return '<th class="' + (cls || 'num') + '" data-sortkey="' + key + '">' + label + arrow(key) + '</th>';
  }

  // ---------- head ----------
  // Order: Recruit | Pos | RT | Yr | Ht | Rgn | Attributes | Lean | Watch.
  // Name/Pos/RT lead because they answer "is he worth watching" fastest, and it keeps
  // the sorted column beside the name. Lean and Watch pair at the right edge: both are
  // about you and him, not about him.
  function colgroupHtml() {
    return '<colgroup>' +
      (boardActive() ? '<col class="c-add">' : '') +
      '<col class="c-name"><col class="c-pos"><col class="c-rt"><col class="c-yr"><col class="c-ht">' +
      '<col class="c-rgn"><col class="c-attrs"><col class="c-lean"><col class="c-watch">' +
      '</colgroup>';
  }
  function headHtml() {
    return '<thead><tr>' +
      (boardActive() ? '<th class="act"></th>' : '') +
      th('name', 'Recruit', 'name-col') +
      th('pos', 'Pos') +
      '<th class="num" data-sortkey="rt" data-tooltip="current/potential" title="current/potential">RT' + arrow('rt') + '</th>' +
      th('year', 'Yr') +
      th('height', 'Ht') +
      th('region', 'Rgn') +
      '<th class="attrs-col attr-tiles-head">Attributes</th>' +
      '<th class="lean-h">Lean</th>' +
      '<th class="watch-col">Watch</th>' +
      '</tr></thead>';
  }

  // ---------- row ----------
  function headshotHtml(r) {
    var imageId = r.imageId;
    if (!imageId || typeof API_CONFIG === 'undefined' || typeof API_CONFIG.getRecruitImageUrl !== 'function') {
      return '<span class="pc-av"></span>';
    }
    return '<span class="pc-av"><img src="' + Common.escapeHtml(API_CONFIG.getRecruitImageUrl(imageId, { size: 'card' })) + '"' +
      ' alt="" loading="lazy" decoding="async" data-image-id="' + Common.escapeHtml(imageId) + '"></span>';
  }
  // Delegates to the shared builder so this screen, the FCC Roster/Recruits tabs and
  // team-roster-view all render identical tiles with identical hover copy.
  function attrChipsHtml(r) {
    return window.GOB_AttrTiles.tilesHtml(r.rawAttrs);
  }

  function watchButtonHtml(r) {
    var on = state.watchlist.has(String(r.recruitId));
    var path = 'M12 2.6l2.9 5.9 6.5.95-4.7 4.58 1.11 6.47L12 17.44l-5.81 3.06 1.11-6.47-4.7-4.58 6.5-.95z';
    return '<button class="wt' + (on ? ' is-on' : '') + '" data-watch-id="' + r.recruitId + '" type="button"' +
      ' aria-pressed="' + (on ? 'true' : 'false') + '" aria-label="' + (on ? 'Remove from' : 'Add to') + ' watchlist">' +
      '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="' + path + '" stroke="currentColor" stroke-width="1.7"' +
      ' fill="' + (on ? 'currentColor' : 'none') + '" stroke-linejoin="round"></path></svg></button>';
  }
  function rowHtml(r) {
    var rowCls = r.yourRank === 1 ? 'mine' : r.yourRank > 1 ? 'list-mine' : '';
    var actCell = '';
    if (boardActive()) {
      var idx = state.board.indexOf(r.recruitId);
      actCell = '<td class="act">' + (idx !== -1
        ? '<button class="pool-rankbadge" data-id="' + r.recruitId + '" title="Remove from board" type="button">' + (idx + 1) + '</button>'
        : '<button class="pool-add" data-id="' + r.recruitId + '" title="Add to invite board" type="button">+</button>') + '</td>';
      if (idx !== -1) rowCls += ' on-board';
    }
    var flags = (state.newLeanIds.has(String(r.recruitId)) ? '<span class="flag new">New</span>' : '');
    return '<tr class="rec ' + rowCls + '" data-rec-id="' + r.recruitId + '">' + actCell +
      '<td class="name-col"><div class="pc-id">' + headshotHtml(r) + '<span class="pc-txt">' +
        '<span class="pc-name"><span class="nm">' + Common.recruitNameLinkHtml(r.recruitId, context.franchiseId, r.name) + '</span>' + flags + '</span>' +
        '<span class="pc-arch">' + Common.escapeHtml(r.archetype) + '</span></span></div></td>' +
      '<td class="pos">' + Common.escapeHtml(r.pos) + '</td>' +
      '<td class="rt" data-tooltip="current/potential" title="current/potential"><span class="v ' + Spine.rtClassForYear(r.rt, r.year) + '">' + Common.formatRtWithPotential(r.rt, r.potentialRt) + '</span></td>' +
      '<td class="year">' + Common.escapeHtml(r.yearDisplay) + '</td>' +
      '<td class="num">' + Common.escapeHtml(r.height) + '</td>' +
      '<td class="num">' + Common.escapeHtml(regionOf(r) || '--') + '</td>' +
      '<td class="attr-tiles-cell">' + attrChipsHtml(r) + '</td>' +
      '<td class="lean-col">' + Spine.Lean.ladderHtml(r.leanModel) + '</td>' +
      '<td class="watch-cell">' + watchButtonHtml(r) + '</td>' +
      '</tr>';
  }
  function poolBodyHtml() {
    var recs = sortRecs(filteredRecruits());
    if (!recs.length) {
      return '<tr><td colspan="' + colspan() + '" style="padding:26px;text-align:center;color:var(--muted-3)">No recruits match your filters.</td></tr>';
    }
    return recs.map(rowHtml).join('');
  }

  // ---------- filter bar ----------
  function segHtml(attr, options, current) {
    return '<div class="pool-seg">' + options.map(function (o) {
      return '<button class="' + (current === o.value ? 'is-on' : '') + '" data-' + attr + '="' + o.value + '" type="button">' + o.label + '</button>';
    }).join('') + '</div>';
  }
  function viewCounts() {
    var watch = 0, leans = 0, unranked = 0;
    state.recruits.forEach(function (r) {
      if (state.watchlist.has(String(r.recruitId))) watch++;
      if (r.leansToUser) leans++;
      if (state.board.indexOf(r.recruitId) === -1) unranked++;
    });
    return { watch: watch, leans: leans, unranked: unranked };
  }
  function viewBtn(value, label, count, iconSvg) {
    return '<button class="pool-view' + (state.view === value ? ' is-on' : '') + '" data-view="' + value + '" type="button">' +
      (iconSvg || '') + label + '<span class="n">' + count + '</span></button>';
  }
  function toolbarHtml(total, shown) {
    var STAR = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2.6l2.9 5.9 6.5.95-4.7 4.58 1.11 6.47L12 17.44l-5.81 3.06 1.11-6.47-4.7-4.58 6.5-.95z" fill="currentColor"/></svg>';
    var counts = viewCounts();
    var regionOpts = '<option value="all"' + (state.region === 'all' ? ' selected' : '') + '>All regions</option>' +
      REGION_ORDER.map(function (r) {
        var mine = state.userRegion === r ? ' — yours' : '';
        return '<option value="' + r + '"' + (state.region === r ? ' selected' : '') + '>Region ' + r + mine + '</option>';
      }).join('');
    var posOpts = [{ value: 'all', label: 'All' }].concat(POS_ORDER.map(function (p) { return { value: p, label: p }; }));
    var activeFilters = (state.region !== 'all') + (state.pos !== 'all') + (state.year !== 'all')
      + (state.view !== 'all') + (state.search.trim() ? 1 : 0);
    return '<div class="pool-fbar">' +
      '<div class="pool-frow"><span class="pool-flab">Filter</span>' +
        '<span class="pool-sel"><select id="pool-region" aria-label="Region">' + regionOpts + '</select></span>' +
        segHtml('pos', posOpts, state.pos) +
        segHtml('year', YEAR_FILTERS, state.year) +
        '<input class="pool-srch" id="pool-search" placeholder="Search name…" value="' + Common.escapeHtml(state.search) + '">' +
      '</div>' +
      '<div class="pool-frow"><span class="pool-flab">Views</span>' +
        viewBtn('watch', 'Watchlist', counts.watch, STAR) +
        viewBtn('leans', 'Leans to me', counts.leans) +
        viewBtn('unranked', 'Unranked by me', counts.unranked) +
        '<span class="pool-fcount">Showing <b>' + shown + '</b> of ' + total +
          (activeFilters ? '' : ' · no filters') + '</span>' +
      '</div></div>';
  }

  // ---------- render ----------
  function renderPool() {
    var host = document.getElementById('hub-pool'); if (!host) return;
    host.innerHTML = toolbarHtml(state.recruits.length, filteredRecruits().length) +
      '<div class="pool-scroll"><table class="pool">' + colgroupHtml() + headHtml() +
      '<tbody>' + poolBodyHtml() + '</tbody></table></div>';
    bindPool(host);
    if (typeof window.initAttributeTooltips === 'function') window.initAttributeTooltips(host, ['th', 'td', '.attr-tile']);
  }
  function bindPool(host) {
    var search = host.querySelector('#pool-search');
    if (search) search.addEventListener('input', function () { state.search = this.value; renderPoolBodyOnly(); updateCount(); });
    var region = host.querySelector('#pool-region');
    if (region) region.addEventListener('change', function () { state.region = this.value; renderPool(); });
    host.querySelectorAll('.pool-seg button[data-pos]').forEach(function (b) {
      b.addEventListener('click', function () { state.pos = this.dataset.pos; renderPool(); });
    });
    host.querySelectorAll('.pool-seg button[data-year]').forEach(function (b) {
      b.addEventListener('click', function () { state.year = this.dataset.year; renderPool(); });
    });
    host.querySelectorAll('.pool-view[data-view]').forEach(function (b) {
      // Views are mutually exclusive; clicking the active one clears it.
      b.addEventListener('click', function () {
        state.view = state.view === this.dataset.view ? 'all' : this.dataset.view;
        renderPool();
      });
    });
    host.querySelectorAll('th[data-sortkey]').forEach(function (thEl) {
      if (!SORTABLE[thEl.dataset.sortkey]) return;
      thEl.style.cursor = 'pointer';
      thEl.addEventListener('click', function () {
        var k = this.dataset.sortkey;
        if (state.sort.key === k) state.sort.dir = state.sort.dir === 'asc' ? 'desc' : 'asc';
        else state.sort = { key: k, dir: (k === 'name' || k === 'pos' || k === 'year' || k === 'region') ? 'asc' : 'desc' };
        renderPool();
      });
    });
    bindPoolBodyHandlers(host);
  }
  function bindPoolBodyHandlers(host) {
    host.querySelectorAll('.pool-add, .pool-rankbadge').forEach(function (b) {
      b.addEventListener('click', function (e) { e.stopPropagation(); toggleBoard(this.dataset.id); });
    });
    host.querySelectorAll('.wt[data-watch-id]').forEach(function (b) {
      b.addEventListener('click', function (e) { e.stopPropagation(); toggleWatch(this); });
    });
    bindHeadshotFallbacks(host);
  }
  // Lazy paint: on a 404 ask the backend to paint the master, retry once, then generic.
  function bindHeadshotFallbacks(host) {
    host.querySelectorAll('.pc-av img[data-image-id]').forEach(function (img) {
      if (img.dataset.fallbackBound) return;
      img.dataset.fallbackBound = '1';
      img.addEventListener('error', function () {
        var el = this, imageId = el.dataset.imageId;
        if (el.dataset.retried || typeof API_CONFIG === 'undefined') {
          el.remove();
          return;
        }
        el.dataset.retried = '1';
        API_CONFIG.ensureRecruitImage(imageId).then(function () {
          el.src = API_CONFIG.getRecruitImageUrl(imageId, { size: 'card' }) + '?r=1';
        }).catch(function () { el.remove(); });
      });
    });
  }
  function renderPoolBodyOnly() {
    var tbody = document.querySelector('#hub-pool tbody'); if (tbody) tbody.innerHTML = poolBodyHtml();
    bindPoolBodyHandlers(document.getElementById('hub-pool'));
    if (typeof window.initAttributeTooltips === 'function') window.initAttributeTooltips(document.getElementById('hub-pool'), ['td', '.attr-tile']);
  }
  function updateCount() {
    var el = document.querySelector('#hub-pool .pool-fcount b');
    if (el) el.textContent = filteredRecruits().length;
  }

  // ---------- watchlist ----------
  // A shortlist: no ranks, no cap. Ordering is the invite board's job at week 20.
  function toggleWatch(btn) {
    var id = String(btn.dataset.watchId || ''); if (!id) return;
    var turningOn = !state.watchlist.has(id);
    // Optimistic: flip locally so 450 rows don't wait on the network.
    if (turningOn) state.watchlist.add(id); else state.watchlist.delete(id);
    paintWatchButton(btn, turningOn);
    refreshWatchDependentChrome();
    btn.disabled = true;
    Common.fetchJSON(API_CONFIG.buildUrl('/franchise/recruiting-watchlist'), {
      method: 'PATCH',
      body: JSON.stringify({ franchise_id: context.franchiseId, recruit_id: id, watching: turningOn })
    }).then(function (res) {
      state.watchlist = new Set((res && res.watchlist ? res.watchlist : []).map(String));
      paintWatchButton(btn, state.watchlist.has(id));
      refreshWatchDependentChrome();
    }).catch(function (err) {
      console.error('[WATCHLIST] toggle failed, reverting', err);
      if (turningOn) state.watchlist.delete(id); else state.watchlist.add(id);
      paintWatchButton(btn, state.watchlist.has(id));
      refreshWatchDependentChrome();
    }).then(function () { btn.disabled = false; });
  }
  function paintWatchButton(btn, on) {
    btn.classList.toggle('is-on', !!on);
    btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    btn.setAttribute('aria-label', (on ? 'Remove from' : 'Add to') + ' watchlist');
    var path = btn.querySelector('path');
    if (path) path.setAttribute('fill', on ? 'currentColor' : 'none');
  }
  function refreshWatchDependentChrome() {
    var counts = viewCounts();
    var btn = document.querySelector('#hub-pool .pool-view[data-view="watch"] .n');
    if (btn) btn.textContent = counts.watch;
    // The watchlist view is itself filtered by the watchlist, so a toggle changes rows.
    if (state.view === 'watch') { renderPoolBodyOnly(); updateCount(); }
  }

  // ===================== BOARD ops =====================
  function toggleBoard(id) {
    var i = state.board.indexOf(id);
    if (i !== -1) state.board.splice(i, 1);
    else if (state.board.length < MAX_BOARD) state.board.push(id);
    clearSeedNotice();   // any edit makes the board the player's, not the seed's
    renderBoardDependent();
  }
  function removeFromBoard(id) {
    var i = state.board.indexOf(id);
    if (i !== -1) { state.board.splice(i, 1); clearSeedNotice(); renderBoardDependent(); }
  }
  function reorderBoard(from, to) {
    if (from == null || from === to) return;
    var m = state.board.splice(from, 1)[0]; state.board.splice(to, 0, m);
    clearSeedNotice();   // the order is the player's now, not the seed's
    renderBoardDependent();
  }
  function renderBoardDependent() { renderPoolBodyOnly(); renderDock(); }

  // ===================== INVITE BOARD =====================
  // Re-ranking IS the invite decision: the hero shows the top UNVISITED board recruit,
  // so there is no second selection step. Board order drives it.

  // ---------- wire events, indexed for the board ----------
  function wireEventsThisWeek() {
    var wire = state.wire || {};
    return (wire.events_this_week || []).filter(function (e) { return e && e.recruit_id; });
  }
  function wireByRecruit() {
    var map = {};
    wireEventsThisWeek().forEach(function (e) {
      var id = String(e.recruit_id);
      // One badge per row: a drop outranks anything else that touched the same recruit.
      if (!map[id] || (e.kind === 'dropped_you' && map[id].kind !== 'dropped_you')) map[id] = e;
    });
    return map;
  }
  var GAIN_KINDS = { gained_you: 1, moved_up: 1 };
  var DROP_KINDS = { dropped_you: 1, moved_down: 1, rival_took_your_top: 1 };
  function movementClass(kind) {
    if (DROP_KINDS[kind]) return 'dropped';
    if (GAIN_KINDS[kind]) return 'gained';
    return '';
  }
  // "Dropped you / Fairview took #1" — headline plus its cause, split for two lines.
  function movementParts(event) {
    var line = String(event.line || '');
    var dash = line.indexOf(' — ');
    var head = dash === -1 ? line : line.slice(0, dash);
    var why = dash === -1 ? '' : line.slice(dash + 3);
    // The recruit's name already leads the row, so strip it from the headline.
    var rec = state.byId[String(event.recruit_id)];
    if (rec && head.indexOf(rec.name) === 0) head = head.slice(rec.name.length).trim();
    return { head: head || '—', why: why };
  }
  function thisWeekCellHtml(id) {
    var event = wireByRecruit()[String(id)];
    if (!event) return '<div class="bmv"><span class="bmv-quiet">—</span></div>';
    var drop = !!DROP_KINDS[event.kind];
    var parts = movementParts(event);
    return '<div class="bmv"><span class="bmv-ico ' + (drop ? 'dn' : 'up') + '">' + (drop ? '↓' : '↑') + '</span>' +
      '<span class="bmv-txt' + (drop ? ' dn' : '') + '">' + Common.escapeHtml(parts.head) +
      (parts.why ? '<small>' + Common.escapeHtml(parts.why) + '</small>' : '') + '</span></div>';
  }

  function headshotBoxHtml(r, cls) {
    if (!r) return '<span class="' + cls + '"></span>';
    var imageId = r.imageId;
    if (!imageId || typeof API_CONFIG === 'undefined' || typeof API_CONFIG.getRecruitImageUrl !== 'function') {
      return '<span class="' + cls + '"></span>';
    }
    return '<span class="' + cls + '"><img src="' + Common.escapeHtml(API_CONFIG.getRecruitImageUrl(imageId, { size: 'card' })) + '"' +
      ' alt="" loading="lazy" decoding="async" data-image-id="' + Common.escapeHtml(imageId) + '"></span>';
  }

  // ---------- hero: the top unvisited recruit ----------
  function visitedRecruitIds() {
    var out = {};
    ((state.wire && state.wire.visited_recruit_ids) || []).forEach(function (id) { out[String(id)] = true; });
    return out;
  }
  function topUnvisitedId() {
    var visited = visitedRecruitIds();
    for (var i = 0; i < state.board.length; i++) {
      if (!visited[String(state.board[i])]) return state.board[i];
    }
    return null;
  }
  function heroHtml() {
    var id = topUnvisitedId();
    if (!id) {
      return '<div class="bhero bhero-empty"><div class="bhero-body">' +
        '<div class="bhero-name">No invite target</div>' +
        '<div class="bhero-meta">' + (state.board.length
          ? 'Every ranked recruit has already had a visit. Add more from the pool below.'
          : 'Rank recruits below and your top unvisited name is invited each week.') +
        '</div></div></div>';
    }
    var r = state.byId[id]; if (!r) return '';
    var rank = state.board.indexOf(id) + 1;
    var why = r.yourRank === 1 ? 'Already #1 on his ladder — the visit protects it.'
      : r.yourRank > 1 ? 'You sit #' + r.yourRank + ' on his ladder — a visit is your move up.'
        : 'Not on his ladder yet — a visit is how you get on it.';
    return '<div class="bhero">' + headshotBoxHtml(r, 'bhero-av') +
      '<div class="bhero-body">' +
        '<div class="bhero-eyebrow">This week’s invite · board rank ' + rank + '</div>' +
        '<div class="bhero-name">' + Common.recruitNameLinkHtml(r.recruitId, context.franchiseId, r.name) + '</div>' +
        '<div class="bhero-meta"><b>' + Common.escapeHtml(r.pos) + '</b> · ' + Common.escapeHtml(r.archetype) +
          ' · Region ' + regionOf(r) + ' · ' + Common.escapeHtml(r.height) + '</div>' +
        '<div class="bhero-why">' + Common.escapeHtml(why) + '</div></div>' +
      '<div class="bhero-right"><span class="bhero-rt ' + Spine.rtClassForYear(r.rt, r.year) + '" data-tooltip="current/potential" title="current/potential">' +
        Common.formatRtWithPotential(r.rt, r.potentialRt) + '</span><span class="bhero-cap">RT</span></div></div>';
  }

  // ---------- seed notice ----------
  // Shown only when the board came from the watchlist seed, never from a real save —
  // otherwise it would be a lie. Says plainly that nothing is sent yet, because the
  // whole point of the client-side seed is that the player is not yet committed.
  function seedNoticeHtml() {
    if (!state.boardSeededFromWatchlist || state.seedNoticeDismissed) return '';
    return '<div class="bseed" id="board-seed-notice">' +
      '<span class="bseed-txt">Seeded from your watchlist, ranked by RT. Drag to re-order — ' +
      '<b>nothing is sent until you save</b>.</span>' +
      '<button class="bseed-x" id="board-seed-dismiss" type="button" aria-label="Dismiss">×</button></div>';
  }
  // Any real reorder means the order is now the player's, so the notice has served out.
  function clearSeedNotice() { state.boardSeededFromWatchlist = false; }

  // ---------- board rows ----------
  function boardRowHtml(id, index) {
    var r = state.byId[id]; if (!r) return '';
    var event = wireByRecruit()[String(id)];
    var moveCls = event ? movementClass(event.kind) : '';
    return '<div class="brow ' + moveCls + '" draggable="true" data-index="' + index + '" data-id="' + id + '">' +
      '<div class="brank"><span class="bgrip" aria-hidden="true"></span><span class="bnum">' + (index + 1) + '</span></div>' +
      '<div class="bname">' + headshotBoxHtml(r, 'bav') + '<span class="btxt">' +
        Common.recruitNameLinkHtml(r.recruitId, context.franchiseId, r.name) +
        '<small>' + Common.escapeHtml(r.archetype) + ' · Region ' + regionOf(r) + '</small></span></div>' +
      '<div class="bc">' + Common.escapeHtml(r.pos) + '</div>' +
      '<div class="bc dim">' + Common.escapeHtml(r.yearDisplay) + '</div>' +
      '<div class="brt ' + Spine.rtClassForYear(r.rt, r.year) + '" data-tooltip="current/potential" title="current/potential">' +
        Common.formatRtWithPotential(r.rt, r.potentialRt) + '</div>' +
      '<div class="bladder">' + Spine.Lean.ladderHtml(r.leanModel) + '</div>' +
      thisWeekCellHtml(id) +
      '<div><button class="bx" data-remove-id="' + id + '" title="Remove from board" type="button">×</button></div>' +
      '</div>';
  }
  function boardHtml() {
    var rows = state.board.length
      ? state.board.map(boardRowHtml).join('')
      : '<div class="brow-empty">No recruits ranked. Click <strong>+</strong> in the pool below — each week the hub invites your top-ranked unvisited recruit.</div>';
    return '<section class="bpanel">' +
      '<div class="bpanel-head"><div class="bpanel-title"><small>Invite Season · Wk ' + state.week + '</small>Invite Board</div>' +
        '<div class="bpanel-count"><span class="n">' + state.board.length + '</span><span class="of">/ ' + MAX_BOARD + '</span></div></div>' +
      heroHtml() + seedNoticeHtml() +
      '<div class="brows">' +
        '<div class="brow bhdr"><div>#</div><div>Recruit</div><div class="bc">Pos</div><div class="bc">Yr</div>' +
          '<div>RT</div><div>Lean</div><div>This week</div><div></div></div>' +
        rows + '</div>' +
      '<div class="bpanel-foot"><button class="bbtn-clear" id="dock-clear" type="button">Clear</button>' +
        '<button class="bbtn-save" id="dock-save" type="button">Save Board</button></div></section>';
  }

  // ---------- right rail ----------
  // Capacity is the HEADER number and comes from payload.roster_capacity — the same
  // source signing day reads. Position mix answers a different question (what shape the
  // board is), so it sits beneath rather than standing in for capacity.
  function rosterNeedsHtml() {
    var cap = capacity();
    var counted = {};
    POS_ORDER.forEach(function (p) { counted[p] = 0; });
    state.board.forEach(function (id) {
      var r = state.byId[id]; if (!r) return;
      var pos = String(r.pos).toUpperCase();
      if (counted[pos] != null) counted[pos] += 1;
    });
    var mix = POS_ORDER.map(function (pos) {
      var n = counted[pos];
      return '<span class="rneed' + (n === 0 ? ' hot' : '') + '">' + pos + ' · ' + n + '</span>';
    }).join('');
    return '<div class="cap-row cap-row--rail">' +
        '<span class="cap-item"><b>' + cap.spots + '</b>/' + cap.cap + ' roster spots</span>' +
        '<span class="cap-item"><b>' + cap.scholarships + '</b> scholarships</span></div>' +
      '<div class="rneeds-lab">Board position mix</div>' +
      '<div class="rneeds">' + mix + '</div>';
  }

  function boardRailHtml() {
    var events = wireEventsThisWeek();
    // Only events that land on a ranked recruit "affect your board" — annotate each with
    // the board rank it hits, which is the whole point of the panel.
    var affecting = events.map(function (e) {
      var idx = state.board.indexOf(String(e.recruit_id));
      if (idx === -1) idx = state.board.indexOf(e.recruit_id);
      return { event: e, rank: idx === -1 ? null : idx + 1 };
    }).filter(function (x) { return x.rank !== null; });
    affecting.sort(function (a, b) {
      var ad = DROP_KINDS[a.event.kind] ? 0 : 1, bd = DROP_KINDS[b.event.kind] ? 0 : 1;
      return ad - bd || a.rank - b.rank;
    });

    var changes;
    if (!affecting.length) {
      // Quiet, not empty: a week with no movement still says so.
      changes = '<div class="rpanel"><div class="reyebrow">This week</div>' +
        '<div class="rquiet">No changes affect your board this week. Your order still stands.</div></div>';
    } else {
      changes = '<div class="rpanel"><div class="reyebrow is-live">' + affecting.length +
        ' change' + (affecting.length === 1 ? '' : 's') + ' affect' + (affecting.length === 1 ? 's' : '') + ' your board</div>' +
        affecting.map(function (x) {
          var drop = !!DROP_KINDS[x.event.kind];
          var parts = movementParts(x.event);
          var rec = state.byId[String(x.event.recruit_id)];
          return '<div class="rev"><span class="rico ' + (drop ? 'dn' : 'up') + '">' + (drop ? '↓' : '↑') + '</span>' +
            '<span class="rtxt"><b>' + Common.escapeHtml(rec ? rec.name : 'A recruit') + '</b> ' +
            Common.escapeHtml(parts.head.toLowerCase()) +
            '<em>' + (parts.why ? Common.escapeHtml(parts.why) + ' · ' : '') + 'board rank ' + x.rank + '</em></span></div>';
        }).join('') + '</div>';
    }

    var invitesLeft = INVITE_WEEKS.filter(function (w) { return w >= state.week; }).length;
    var needs = '<div class="rpanel"><div class="reyebrow">Roster capacity</div>' + rosterNeedsHtml() +
      '<div class="rsplit"></div>' +
      '<div class="rstat"><span>Board slots used</span><span class="v">' + state.board.length + '<s>/' + MAX_BOARD + '</s></span></div>' +
      '<div class="rstat"><span>Invites remaining</span><span class="v">' + invitesLeft + '<s>/7</s></span></div></div>';

    return '<aside class="brail">' + changes + needs + '</aside>';
  }

  function renderDock() {
    var board = document.getElementById('hub-board');
    if (board) { board.innerHTML = boardHtml(); bindBoard(board); }
    var host = document.getElementById('hub-dock');
    if (host) { host.innerHTML = boardRailHtml(); }
    if (typeof window.initAttributeTooltips === 'function') {
      if (board) window.initAttributeTooltips(board, ['div', 'span']);
    }
  }
  function bindBoard(host) {
    host.querySelectorAll('[data-remove-id]').forEach(function (b) {
      b.addEventListener('click', function (e) { e.stopPropagation(); removeFromBoard(this.dataset.removeId); });
    });
    host.querySelectorAll('.brow[data-index]').forEach(function (row) {
      row.addEventListener('dragstart', function (e) { state.drag.from = Number(this.dataset.index); e.dataTransfer.effectAllowed = 'move'; });
      row.addEventListener('dragover', function (e) { e.preventDefault(); var i = Number(this.dataset.index); if (i !== state.drag.over) { state.drag.over = i; this.classList.add('dragover'); } });
      row.addEventListener('dragleave', function () { this.classList.remove('dragover'); });
      row.addEventListener('drop', function (e) { e.preventDefault(); reorderBoard(state.drag.from, Number(this.dataset.index)); state.drag.from = state.drag.over = null; });
      row.addEventListener('dragend', function () { state.drag.from = state.drag.over = null; host.querySelectorAll('.brow').forEach(function (s) { s.classList.remove('dragover'); }); });
    });
    var dismiss = host.querySelector('#board-seed-dismiss');
    if (dismiss) dismiss.addEventListener('click', function () { state.seedNoticeDismissed = true; renderDock(); });
    var clear = host.querySelector('#dock-clear');
    if (clear) clear.addEventListener('click', function () { state.board = []; clearSeedNotice(); renderBoardDependent(); });
    var save = host.querySelector('#dock-save');
    if (save) save.addEventListener('click', saveBoard);
    bindHeadshotFallbacks(host);
  }

  function saveBoard() {
    var btn = document.getElementById('dock-save'); if (btn) { btn.disabled = true; btn.textContent = 'Saving…'; }
    Common.fetchJSON(API_CONFIG.buildUrl('/franchise/recruiting-orders'), {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ franchise_id: context.franchiseId, recruit_ids: state.board })
    }).then(function () {
      // Committed: the notice says "nothing is sent until you save", which is no longer
      // true, so it must go. Also flips this board from seeded to saved.
      clearSeedNotice();
      renderDock();
      showToast();
    })
      .catch(function (err) { console.error(err); showToast('Save failed', String(err && err.message || err), false); })
      .then(function () { if (btn) { btn.disabled = false; btn.textContent = 'Save Board'; } });
  }

  // ===================== TOAST =====================
  function showToast(title, sub, ok) {
    var el = document.getElementById('hub-toast');
    if (!el) { el = document.createElement('div'); el.id = 'hub-toast'; el.className = 'hub-toast'; document.body.appendChild(el); }
    el.innerHTML = '<span class="ti">' + CHECK + '</span><div><div class="tt1">' + Common.escapeHtml(title || 'Invite Board Saved') +
      '</div><div class="tt2">' + Common.escapeHtml(sub || 'Your ranked board runs each week (Wks 20–26).') + '</div></div>';
    el.style.borderLeftColor = ok === false ? 'var(--red)' : 'var(--green)';
    void el.offsetWidth; el.classList.add('show');
    clearTimeout(showToast._t); showToast._t = setTimeout(function () { el.classList.remove('show'); }, 3200);
  }

  // ===================== STORY (passive) =====================
  function storyHtml() {
    var gains = state.recruits.filter(function (r) { return state.newLeanIds.has(String(r.recruitId)); });
    var items = gains.map(function (r) {
      var rank = r.yourRank ? '#' + r.yourRank : 'your list';
      return '<div class="story-item"><span class="ico gain">' + ARROW_UP + '</span><span class="tx"><span class="t1">' +
        Common.escapeHtml(r.name) + '</span><span class="t2">now leaning you · <b>' + rank + '</b></span></span></div>';
    }).join('');
    if (!items) items = '<div class="story-empty">Quiet week — no new leans.</div>';
    return '<div class="story"><div class="story-lead"><span class="wkn">Wk ' + state.week + '</span><span class="lbl">This week</span></div>' +
      '<div class="story-items">' + items + '</div></div>';
  }

  // ===================== SIGNING BOARD (wk 35) =====================
  var WARN_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M12 9v4M12 17v.5"></path><path d="M10.3 3.9L2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"></path></svg>';
  var DOT_SVG = '<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="6"></circle></svg>';

  // Lean multipliers come from the SERVER (payload.lean_multipliers), which is the same
  // map _week_35_team_score uses. Hardcoding them here is how this drifted the first
  // time: slot 3 scores x2, and an earlier client table defaulted it to x1.
  var LEAN_MULT_FALLBACK = { 1: 5, 2: 3, 3: 2 };
  function leanMultiplier(rank) {
    var served = state.leanMultipliers || {};
    var key = String(Number(rank) || 0);
    var v = served[key] != null ? served[key] : LEAN_MULT_FALLBACK[key];
    return Number(v) || 1;
  }

  // ── Standing + Field: two honest columns, no percentage anywhere ─────────────
  // There is deliberately no probability on this screen. A number like "62%" is a
  // promise the sim cannot keep; a count and a multiplier are facts. If you ever find
  // yourself deriving one to rank or sort, that is the old placeholder growing back.
  function standingCellHtml(r) {
    var rank = Number(r.yourRank || 0);
    var mult = leanMultiplier(rank);
    var label = rank === 1 ? '#1' : rank > 1 ? '#' + rank : '—';
    var cls = rank === 1 ? ' s-you1' : rank > 1 ? ' s-list' : '';
    return '<div class="stand-cell' + cls + '">' +
      '<span class="stand-pos">' + label + '</span>' +
      '<span class="stand-mult">x' + mult + '</span></div>';
  }
  function competitionCount(id) {
    var counts = (state.competitionCounts || {});
    var raw = counts[String(id)];
    return raw == null ? null : Number(raw);
  }
  // Segment bar: one segment per funding program, the user's own highlighted.
  function fieldCellHtml(r) {
    var id = r.recruitId;
    var count = competitionCount(id);
    var funded = allocOf(id).points > 0;
    if (count == null) {
      return '<div class="field-cell"><span class="field-n dim">—</span>' +
        '<span class="field-lab">no field yet</span></div>';
    }
    // The user's own funding may not be in the server snapshot yet (it is written on
    // save), so add it here rather than under-reporting the field.
    var total = count + (funded && !state.week35Ran ? 1 : 0);
    var segs = '';
    for (var i = 0; i < Math.min(total, 12); i++) {
      segs += '<i class="' + (funded && i === 0 ? 'mine' : '') + '"></i>';
    }
    return '<div class="field-cell">' +
      '<span class="field-n">' + total + '</span>' +
      '<span class="field-bar">' + segs + '</span>' +
      '<span class="field-lab">' + (total === 1 ? 'program' : 'programs') + '</span></div>';
  }

  function allocOf(id) { return state.alloc[id] || { points: 0, promise: false }; }
  function committedIds() { return Object.keys(state.alloc).filter(function (id) { var a = state.alloc[id]; return a && (a.points > 0 || a.promise); }); }
  function spent() { return committedIds().reduce(function (s, id) { return s + (state.alloc[id].points || 0); }, 0); }
  function remaining() { return SIGN.TOTAL - spent(); }
  function pruneAlloc(id) { var a = state.alloc[id]; if (a && a.points === 0 && !a.promise) delete state.alloc[id]; }

  // seedAlloc() is DELETED on purpose. It allocated 12/9/6 points — 27 of 50 — and
  // attached BINDING playing-time promises to two recruits, unmarked, on page load.
  // The page loads at 0 of 50 with no promises; the player makes every commitment.
  // Any future helper must be a button they press, never a load-time side effect.

  // ── Roster capacity — read from the payload, never recomputed ────────────────
  function capacity() {
    var c = state.rosterCapacity || {};
    return {
      spots: Number(c.roster_spots || 0),
      scholarships: Number(c.scholarships || 0),
      cap: Number(c.roster_cap || 15),
      used: Number(c.roster_used || 0),
    };
  }
  function signFiltered() {
    var q = state.sSearch.trim().toLowerCase();
    return state.recruits.filter(function (r) {
      if (state.sTab === 'mine' && !r.leansToUser) return false;
      if (state.sRegion !== 'all' && regionOf(r) !== state.sRegion) return false;
      if (q && String(r.name).toLowerCase().indexOf(q) === -1) return false;
      return true;
    }).sort(function (a, b) { return (b.rt || 0) - (a.rt || 0); });
  }

  function prowHtml(r) {
    var a = allocOf(r.recruitId);
    var committed = a.points > 0 || a.promise;
    var canPlus = remaining() > 0 && a.points < SIGN.MAX_PER;
    return '<div class="prow' + (committed ? ' funded' : '') + (state.flashId === r.recruitId ? ' flash' : '') + '" data-id="' + r.recruitId + '">' +
      '<div class="prow-name"><div class="nm">' +
          Common.recruitNameLinkHtml(r.recruitId, context.franchiseId, r.name) + '</div>' +
        // Year and archetype belong here: a senior and a freshman must not look identical
        // on the screen where 50 points get committed.
        '<div class="prow-arch"><span class="prow-yr">' + Common.escapeHtml(r.yearDisplay) + '</span>' +
          Common.escapeHtml(r.archetype) + '</div></div>' +
      '<span class="prow-pos">' + Common.escapeHtml(r.pos) + '</span>' +
      '<span class="prow-region">' + regionOf(r) + '</span>' +
      '<span class="prow-rt" data-tooltip="current/potential" title="current/potential"><span class="v ' + Spine.rtClassForYear(r.rt, r.year) + '">' + Common.formatRtWithPotential(r.rt, r.potentialRt) + '</span></span>' +
      standingCellHtml(r) +
      fieldCellHtml(r) +
      '<div><div class="stepper"><button data-step="-1" data-id="' + r.recruitId + '"' + (a.points === 0 ? ' disabled' : '') + '>−</button>' +
        '<span class="val' + (a.points === 0 ? ' zero' : '') + '">' + a.points + '</span>' +
        '<button data-step="1" data-id="' + r.recruitId + '"' + (canPlus ? '' : ' disabled') + '>+</button><span class="stepper-pts">pts</span></div></div>' +
      '<div class="promise-cell' + (a.promise ? ' set' : '') + '"><button class="promise-toggle" data-promise="' + r.recruitId + '" title="Promise playing time">' +
        '<span class="box">' + CHECK + '</span>' + (a.promise ? 'Binding' : 'Promise') + '</button></div>' +
      '</div>';
  }

  // ── Pre-flight warnings ──────────────────────────────────────────────────────
  // The one place on this screen allowed to editorialize. Each warning must name the
  // recruit and the number driving it — a warning without both is a stat, not advice.
  function preflightWarnings() {
    var out = [];
    var cap = capacity();
    var rem = remaining();
    var ids = committedIds();

    ids.forEach(function (id) {
      var r = state.byId[id]; if (!r) return;
      var a = state.alloc[id];
      var rank = Number(r.yourRank || 0);
      var mult = leanMultiplier(rank);
      var field = competitionCount(id);
      var standing = rank === 1 ? "you're #1 at x5" : rank > 1 ? "you're #" + rank + ' at x' + mult : "you're not on his ladder at x1";
      // Thin funding against a crowded field.
      if (field != null && field >= 4 && a.points > 0 && a.points <= 6) {
        out.push({
          id: id,
          level: 'warn',
          text: field + ' programs funding ' + r.name + ', ' + standing + ' — ' + a.points +
            ' point' + (a.points === 1 ? '' : 's') + ' is unlikely to carry.',
        });
      }
      // A binding promise where the multiplier is working against you.
      if (a.promise && mult === 1) {
        out.push({
          id: id,
          level: 'warn',
          text: 'Binding promise on ' + r.name + ' at x1 — he has no lean toward you, so the promise carries the whole bid.',
        });
      }
    });

    // Points left on the table while roster spots remain, called out against the
    // cheapest uncontested name so the advice is actionable.
    if (rem > 0 && cap.spots > 0) {
      var uncontested = state.recruits.filter(function (r) {
        var field = competitionCount(r.recruitId);
        return field != null && field <= 1 && !allocOf(r.recruitId).points;
      }).sort(function (x, y) { return (y.rt || 0) - (x.rt || 0); })[0];
      if (uncontested) {
        out.push({
          id: uncontested.recruitId,
          level: 'info',
          text: rem + ' point' + (rem === 1 ? '' : 's') + ' unspent and ' + cap.spots +
            ' roster spot' + (cap.spots === 1 ? '' : 's') + '; ' + uncontested.name +
            ' is uncontested at x' + leanMultiplier(uncontested.yourRank) + '.',
        });
      }
    }

    // More commitments than spots is a hard problem, not a nudge.
    if (ids.length > cap.spots) {
      out.push({
        level: 'warn',
        text: ids.length + ' recruits funded but only ' + cap.spots + ' roster spot' +
          (cap.spots === 1 ? '' : 's') + ' — signings beyond that cannot be taken.',
      });
    }
    if (rem < 0) {
      out.push({ level: 'warn', text: Math.abs(rem) + ' points over budget — trim before submitting.' });
    }
    return out;
  }

  function railHtml() {
    var cids = committedIds().map(function (id) { return { r: state.byId[id], a: state.alloc[id] }; })
      .filter(function (x) { return x.r; })
      .sort(function (x, y) { return (y.a.points - x.a.points) || ((y.r.rt || 0) - (x.r.rt || 0)); });
    var rem = remaining(), promises = committedIds().filter(function (id) { return state.alloc[id].promise; }).length;
    var pct = Math.min(100, (spent() / SIGN.TOTAL) * 100);
    var cap = capacity();

    var list = cids.length === 0
      ? '<div class="rail-list"><div class="rail-empty"><div class="t1">Nothing committed</div><div class="t2">Add points to a recruit in the pool and they\'ll appear here.</div></div></div>'
      : '<div class="rail-list">' + cids.map(function (x) {
          var rank = Number(x.r.yourRank || 0);
          return '<div class="citem" data-jump="' + x.r.recruitId + '" title="Jump to recruit"><div class="citem-body">' +
            '<div class="citem-name"><span class="nm">' + Common.escapeHtml(x.r.name) + '</span>' + (x.a.promise ? '<span class="pmk">· PT</span>' : '') + '</div>' +
            '<div class="citem-meta"><span class="citem-pts">' + x.a.points + ' pts</span>' +
            '<span data-tooltip="current/potential" title="current/potential">' + Common.escapeHtml(x.r.pos) + ' · ' + Common.formatRtWithPotential(x.r.rt, x.r.potentialRt) + ' RT</span>' +
            '<span class="citem-mult">' + (rank ? '#' + rank : '—') + ' x' + leanMultiplier(rank) + '</span></div></div>' +
            '<button class="citem-x" data-remove="' + x.r.recruitId + '" title="Remove">×</button></div>';
        }).join('') + '</div>';

    var warnings = preflightWarnings();
    var preflight = warnings.length
      ? '<div class="preflight">' + warnings.map(function (w) {
          // Clickable when the warning is about a specific recruit: jumpTo() reveals him
          // even when the 'mine' tab hides him. The mine default stays — the problem was
          // the unreachable warning, not the tab.
          var tag = w.id ? 'button' : 'div';
          var attrs = w.id ? ' type="button" data-pfw-jump="' + w.id + '"' : '';
          return '<' + tag + ' class="pfw ' + w.level + (w.id ? ' is-clickable' : '') + '"' + attrs + '>' +
            (w.level === 'warn' ? WARN_SVG : DOT_SVG) +
            '<span>' + Common.escapeHtml(w.text) + '</span></' + tag + '>';
        }).join('') + '</div>'
      : '<div class="preflight"><div class="pfw ok">' + DOT_SVG +
        '<span>Nothing flagged. Your commitments fit your budget and your roster.</span></div></div>';

    var note = promises > 0
      ? '<div class="rail-note">' + WARN_SVG + '<span><b>' + promises + ' binding ' + (promises === 1 ? 'promise' : 'promises') + '</b> — honor the playing time or your program\'s standing suffers.</span></div>'
      : '<div class="rail-note"><span>Promises are <b>binding</b> — set one only if you\'ll honor the minutes.</span></div>';
    var disabled = rem < 0 || state.week35Ran;

    return '<div class="rail-head"><div class="rail-title">Your Orders</div>' +
      '<div class="budget-nums"><span class="rem' + (rem < 0 ? ' over' : '') + '">' + rem + '</span><span class="of">/ ' + SIGN.TOTAL + '</span></div>' +
      '<div class="budget-caprow"><span class="budget-cap">Points to spend</span>' +
        '<span class="budget-promises"><b>' + promises + '</b> ' + (promises === 1 ? 'promise' : 'promises') + '</span></div>' +
      '<div class="budget-bar"><div class="budget-fill' + (rem < 0 ? ' over' : '') + '" style="width:' + pct + '%"></div></div>' +
      // Capacity is the header number, straight from the payload.
      '<div class="cap-row"><span class="cap-item"><b>' + cap.spots + '</b>/' + cap.cap + ' roster spots</span>' +
        '<span class="cap-item"><b>' + cap.scholarships + '</b> scholarships</span></div></div>' +
      list + preflight +
      '<div class="rail-foot">' + note +
        '<button class="rail-submit" id="sign-submit"' + (disabled ? ' disabled' : '') + '>' + (state.week35Ran ? 'Signings Run' : 'Submit Orders') + '</button></div>';
  }

  function signBoardHtml() {
    var regionOpts = '<option value="all">All regions</option>' + REGION_ORDER.map(function (r) { return '<option value="' + r + '"' + (state.sRegion === r ? ' selected' : '') + '>' + r + '</option>'; }).join('');
    return '<div class="spool"><div class="spool-head"><div class="spool-title">Recruit Pool</div>' +
        '<div class="spool-tools"><div class="spool-tabs">' +
          '<button class="spool-tab' + (state.sTab === 'mine' ? ' on' : '') + '" data-stab="mine">Leaning to you</button>' +
          '<button class="spool-tab' + (state.sTab === 'all' ? ' on' : '') + '" data-stab="all">All</button></div>' +
          '<select class="spool-region" id="sign-region">' + regionOpts + '</select>' +
          '<input class="spool-search" id="sign-search" placeholder="Search name…" value="' + Common.escapeHtml(state.sSearch) + '"></div></div>' +
        '<div class="spool-colhdr"><span>Recruit</span><span class="c-num">Pos</span><span class="c-num">Region</span><span class="c-num">RT</span>' +
          '<span class="c-num">Standing</span><span class="c-num">Field</span><span>Points</span><span>Playing Time</span></div>' +
        '<div class="spool-rows" id="sign-rows">' + signFiltered().map(prowHtml).join('') + '</div></div>' +
      '<aside class="rail" id="sign-rail">' + railHtml() + '</aside>';
  }

  function renderSignRows() {
    var rows = document.getElementById('sign-rows'); if (!rows) return;
    var top = rows.scrollTop;
    rows.innerHTML = signFiltered().map(prowHtml).join('');
    rows.scrollTop = top;
    bindSignRows();
  }
  function renderSignRail() { var rail = document.getElementById('sign-rail'); if (rail) { rail.innerHTML = railHtml(); bindSignRail(); } }

  function stepPoints(id, d) {
    var a = allocOf(id), nv = a.points + d;
    if (nv < 0 || nv > SIGN.MAX_PER) return;
    if (d > 0 && remaining() <= 0) return;
    state.alloc[id] = { points: nv, promise: a.promise }; pruneAlloc(id);
    renderSignRows(); renderSignRail();
  }
  function togglePromise(id) {
    var a = allocOf(id);
    state.alloc[id] = { points: a.points, promise: !a.promise }; pruneAlloc(id);
    renderSignRows(); renderSignRail();
  }
  function removeCommit(id) { delete state.alloc[id]; renderSignRows(); renderSignRail(); }
  function jumpTo(id) {
    var r = state.byId[id]; if (!r) return;
    if (state.sTab === 'mine' && !r.leansToUser) { state.sTab = 'all'; renderSignRows(); document.querySelectorAll('[data-stab]').forEach(function (b) { b.classList.toggle('on', b.dataset.stab === 'all'); }); }
    var rows = document.getElementById('sign-rows'), row = rows && rows.querySelector('[data-id="' + id + '"]');
    if (row) rows.scrollTop = row.offsetTop - 8;
    state.flashId = id; renderSignRows();
    setTimeout(function () { state.flashId = null; renderSignRows(); }, 1100);
  }

  function bindSignRows() {
    var host = document.getElementById('sign-rows'); if (!host) return;
    host.querySelectorAll('button[data-step]').forEach(function (b) { b.addEventListener('click', function () { stepPoints(this.dataset.id, Number(this.dataset.step)); }); });
    host.querySelectorAll('button[data-promise]').forEach(function (b) { b.addEventListener('click', function () { togglePromise(this.dataset.promise); }); });
  }
  function bindSignRail() {
    var host = document.getElementById('sign-rail'); if (!host) return;
    host.querySelectorAll('[data-jump]').forEach(function (b) { b.addEventListener('click', function () { jumpTo(this.dataset.jump); }); });
    host.querySelectorAll('[data-remove]').forEach(function (b) { b.addEventListener('click', function (e) { e.stopPropagation(); removeCommit(this.dataset.remove); }); });
    // A warning that names a recruit must be able to reach him — jumpTo() switches off
    // the 'mine' tab when he doesn't lean to us, then flashes the row.
    host.querySelectorAll('[data-pfw-jump]').forEach(function (b) {
      b.addEventListener('click', function () { jumpTo(this.dataset.pfwJump); });
    });
    var submit = host.querySelector('#sign-submit'); if (submit) submit.addEventListener('click', submitOrders);
  }
  function bindSignBoard() {
    document.querySelectorAll('[data-stab]').forEach(function (b) { b.addEventListener('click', function () { state.sTab = this.dataset.stab; renderSignRows(); document.querySelectorAll('[data-stab]').forEach(function (x) { x.classList.toggle('on', x.dataset.stab === state.sTab); }); }); });
    var region = document.getElementById('sign-region'); if (region) region.addEventListener('change', function () { state.sRegion = this.value; renderSignRows(); });
    var search = document.getElementById('sign-search'); if (search) search.addEventListener('input', function () { state.sSearch = this.value; renderSignRows(); });
    bindSignRows(); bindSignRail();
  }

  // Snapshot taken BEFORE submitting, so the summary reports what was actually sent
  // even though state.alloc is about to be locked by week35Ran.
  function submitSummaryRows() {
    return committedIds().map(function (id) {
      var r = state.byId[id], a = state.alloc[id];
      var rank = Number((r && r.yourRank) || 0);
      return {
        name: r ? r.name : id,
        pos: r ? r.pos : '--',
        points: a.points,
        promise: !!a.promise,
        standing: rank ? '#' + rank : '—',
        mult: leanMultiplier(rank),
        field: competitionCount(id),
      };
    }).sort(function (x, y) { return y.points - x.points; });
  }

  // Replaces the blind 950ms redirect: the player sees what they committed, then leaves
  // on their own click. No percentage here either — points, standing, multiplier, field.
  function showSubmitSummary(rows) {
    var total = rows.reduce(function (n, x) { return n + x.points; }, 0);
    var promises = rows.filter(function (x) { return x.promise; }).length;
    var body = rows.length
      ? '<div class="ssum-rows">' + rows.map(function (x) {
          return '<div class="ssum-row"><span class="ssum-nm">' + Common.escapeHtml(x.name) +
            (x.promise ? '<b>· PT</b>' : '') + '</span>' +
            '<span class="ssum-pos">' + Common.escapeHtml(x.pos) + '</span>' +
            '<span class="ssum-stand">' + x.standing + ' x' + x.mult + '</span>' +
            '<span class="ssum-field">' + (x.field == null ? '—' : x.field + (x.field === 1 ? ' program' : ' programs')) + '</span>' +
            '<span class="ssum-pts">' + x.points + ' pts</span></div>';
        }).join('') + '</div>'
      : '<div class="ssum-empty">You submitted no funding. Every recruit signs elsewhere.</div>';
    var overlay = document.createElement('div');
    overlay.className = 'ssum-overlay';
    overlay.innerHTML = '<div class="ssum" role="dialog" aria-modal="true" aria-label="Orders submitted">' +
      '<div class="ssum-head"><div class="ssum-title">Orders Submitted</div>' +
        '<div class="ssum-sub">' + total + ' of ' + SIGN.TOTAL + ' points committed across ' +
        rows.length + ' recruit' + (rows.length === 1 ? '' : 's') +
        (promises ? ' · ' + promises + ' binding ' + (promises === 1 ? 'promise' : 'promises') : '') +
        '</div></div>' + body +
      '<div class="ssum-foot"><button class="ssum-go" id="ssum-go" type="button">Back to Locker Room</button></div></div>';
    document.body.appendChild(overlay);
    var go = overlay.querySelector('#ssum-go');
    go.addEventListener('click', function () { window.location.href = Common.buildFccUrl(context); });
    go.focus();
  }

  function submitOrders() {
    if (remaining() < 0 || state.week35Ran) return;
    var btn = document.getElementById('sign-submit'); if (btn) { btn.disabled = true; btn.textContent = 'Submitting…'; }
    var entries = committedIds().map(function (id) { return { id: id, points: state.alloc[id].points, playing_time: !!state.alloc[id].promise }; });
    var summaryRows = submitSummaryRows();
    Common.fetchJSON(API_CONFIG.buildUrl('/franchise/recruiting-orders'), {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ franchise_id: context.franchiseId, order_entries: entries })
    }).then(function () {
      return Common.fetchJSON(API_CONFIG.buildUrl('/franchise/run-week-35-recruiting'), {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ franchise_id: context.franchiseId })
      });
    }).then(function () {
      state.week35Ran = true;
      showSubmitSummary(summaryRows);
    }).catch(function (err) {
      console.error(err); showToast('Submit failed', String(err && err.message || err), false);
      if (btn) { btn.disabled = false; btn.textContent = 'Submit Orders'; }
    });
  }

  // ===================== RESULTS (D4) =====================
  // ---- Week-36 final signings ----
  function signStandChip(r, cls) {
    cls = cls || 'sstand';
    if (r.yourRank === 1) return '<span class="' + cls + ' you1">' + DOT_SVG + '#1</span>';
    if (r.yourRank > 1) return '<span class="' + cls + ' list">#' + r.yourRank + '</span>';
    return '<span class="' + cls + ' none">—</span>';
  }
  // ===================== RESULTS (week 36) =====================
  // Playback of a sequence that ALREADY happens: the engine resolves recruits one at a
  // time in RT order. Nothing here changes who signs where — it only reveals the order
  // the engine already produced.

  function signedEntriesForUserView() {
    var entries = (state.week35Results.signed_players || []).filter(function (e) {
      return e && !e.walk_on && e.recruit_id;
    });
    var uid = String(state.userTeamId);
    return entries.map(function (e) {
      var r = state.byId[String(e.recruit_id)];
      var res = e.resolution || {};
      var pts = (res.points_by_team || {});
      var mults = (res.lean_multipliers || {});
      return {
        id: String(e.recruit_id),
        r: r,
        name: r ? r.name : (e.name || '--'),
        pos: e.pos || (r ? r.pos : '--'),
        rt: e.rt != null ? e.rt : (r ? r.rt : null),
        potentialRt: r ? r.potentialRt : null,
        year: r ? r.yearDisplay : '',
        imageId: r ? r.imageId : e.image_id,
        team: e.team_name || '—',
        withYou: String(e.team_id) === uid,
        // Every number below was RECORDED BY THE RESOLUTION. None is recomputed here.
        yourPoints: Number(pts[uid] || 0),
        yourMult: Number(mults[uid] || 0),
        fieldSize: Number(res.field_size || 0),
        reason: e.signing_reason || '',
        boarded: Object.prototype.hasOwnProperty.call(res.scores_by_team || {}, uid),
      };
    }).filter(function (x) {
      // The sequence is about your season: recruits you boarded, plus everyone you signed.
      return x.withYou || x.boarded;
    });
  }

  // Signing order = the order the engine resolved them, i.e. RT descending.
  function playbackList() {
    return signedEntriesForUserView().sort(function (a, b) {
      return (b.rt != null ? b.rt : -1) - (a.rt != null ? a.rt : -1);
    });
  }

  function resultRowHtml(x, revealed) {
    var standing = x.yourMult
      ? (x.yourMult === 5 ? '#1 x5' : x.yourMult === 3 ? '#2 x3' : x.yourMult === 2 ? '#3 x2' : 'no lean x1')
      : '—';
    return '<div class="rrow' + (x.withYou ? ' won' : ' lost') + (revealed ? ' is-in' : '') + '" data-rid="' + x.id + '">' +
      headshotBoxHtml({ imageId: x.imageId }, 'rav') +
      '<div class="rid"><div class="rnm">' +
        (x.r ? Common.recruitNameLinkHtml(x.id, context.franchiseId, x.name) : Common.escapeHtml(x.name)) +
        '</div><div class="rmeta">' + Common.escapeHtml(x.pos) +
        (x.year ? ' · ' + Common.escapeHtml(x.year) : '') + '</div></div>' +
      '<div class="rrt ' + (x.r ? Spine.rtClassForYear(x.rt, x.r.year) : '') + '" data-tooltip="current/potential" title="current/potential">' +
        Common.formatRtWithPotential(x.rt, x.potentialRt) + '</div>' +
      '<div class="rsigned"><span class="rsigned-lab">Signed with</span>' +
        '<span class="rsigned-team' + (x.withYou ? ' mine' : '') + '">' + Common.escapeHtml(x.team) + '</span></div>' +
      '<div class="rnum"><b>' + x.yourPoints + '</b><span>pts</span></div>' +
      '<div class="rnum"><b>' + standing + '</b><span>standing</span></div>' +
      '<div class="rnum"><b>' + (x.fieldSize || '—') + '</b><span>field</span></div>' +
      '<div class="rwhy">' + Common.escapeHtml(x.reason || '—') + '</div>' +
      '</div>';
  }

  function classSummaryHtml(list) {
    var cap = capacity();
    var signed = list.filter(function (x) { return x.withYou; });
    var funded = list.filter(function (x) { return x.yourPoints > 0; });
    var pointsSpent = list.reduce(function (n, x) { return n + x.yourPoints; }, 0);
    var rts = signed.map(function (x) { return Number(x.rt || 0); }).filter(function (v) { return v > 0; });
    var avg = rts.length ? Math.round(rts.reduce(function (a, b) { return a + b; }, 0) / rts.length) : null;
    var avgDisplay = avg == null ? '—'
      : (typeof formatRtDisplay === 'function' ? formatRtDisplay(avg) : String(avg));
    return '<section class="rsum"><div class="rsum-title">Your Class</div>' +
      '<div class="rsum-grid">' +
        '<div class="rsum-cell"><b>' + signed.length + '</b><span>signed</span></div>' +
        '<div class="rsum-cell"><b>' + funded.length + '</b><span>funded</span></div>' +
        '<div class="rsum-cell"><b>' + avgDisplay + '</b><span>class avg RT</span></div>' +
        '<div class="rsum-cell"><b>' + pointsSpent + '</b><span>points spent</span></div>' +
        // Same _roster_capacity_payload helper signing day reads.
        '<div class="rsum-cell"><b>' + Math.max(0, cap.spots - signed.length) + '</b><span>roster spots left</span></div>' +
      '</div></section>';
  }

  function finalSigningsHtml() {
    var list = playbackList();
    if (!list.length) {
      return '<div class="rstage"><div class="rempty">No recruits to report — you never boarded anyone this season.</div></div>';
    }
    var pb = state.playback;
    var shown = pb.done ? list.length : Math.min(pb.index, list.length);
    var rows = list.slice(0, shown).map(function (x, i) {
      return resultRowHtml(x, i === shown - 1 && !pb.done);
    }).join('');
    var remaining = list.length - shown;
    var controls = pb.done || remaining <= 0
      ? '<div class="rctl"><span class="rctl-done">All ' + list.length + ' revealed</span></div>'
      : '<div class="rctl">' +
          '<button class="rbtn main" id="pb-next" type="button">Next recruit →</button>' +
          '<button class="rbtn" id="pb-auto" type="button">' + (pb.auto ? 'Pause' : 'Auto-play') + '</button>' +
          '<button class="rbtn" id="pb-skip" type="button">Skip all</button>' +
          '<span class="rctl-count">' + shown + ' of ' + list.length + '</span>' +
        '</div>';
    return '<div class="rstage">' +
      '<div class="rhead"><div class="rhead-t">Signing Day Results</div>' +
        '<div class="rhead-s">Revealed in the order the engine resolved them — highest RT first.</div></div>' +
      controls +
      '<div class="rrows">' + rows + '</div>' +
      ((pb.done || remaining <= 0) ? classSummaryHtml(list) : '') +
      '</div>';
  }

  function stopAutoPlay() {
    if (state.playback.timer) { clearInterval(state.playback.timer); state.playback.timer = null; }
    state.playback.auto = false;
  }
  function renderSignings() {
    var host = document.getElementById('hub-signings'); if (!host) return;
    host.innerHTML = finalSigningsHtml();
    bindSignings();
    if (typeof window.initAttributeTooltips === 'function') window.initAttributeTooltips(host, ['div']);
  }
  function playbackAdvance() {
    var total = playbackList().length;
    if (state.playback.index >= total) { state.playback.done = true; stopAutoPlay(); }
    else state.playback.index += 1;
    if (state.playback.index >= total) { state.playback.done = true; stopAutoPlay(); }
    renderSignings();
  }
  function bindSignings() {
    var next = document.getElementById('pb-next');
    if (next) next.addEventListener('click', function () { stopAutoPlay(); playbackAdvance(); });
    var skip = document.getElementById('pb-skip');
    if (skip) skip.addEventListener('click', function () {
      stopAutoPlay();
      state.playback.index = playbackList().length;
      state.playback.done = true;
      renderSignings();
    });
    var auto = document.getElementById('pb-auto');
    if (auto) auto.addEventListener('click', function () {
      if (state.playback.auto) { stopAutoPlay(); renderSignings(); return; }
      state.playback.auto = true;
      state.playback.timer = setInterval(playbackAdvance, 900);
      renderSignings();
    });
  }

  // ---- Weekly-visit results panel (wks 20-26) ----
  function showWeeklyPanel() { return state.phase === 'invite' && state.currentResultsWeek === state.week && !state.weeklyDismissed; }
  function weeklyPanelHtml() {
    var tree = state.visitTree;
    if (!tree) return '<div class="wpanel"><div class="wpanel-head"><div class="wpanel-title"><small>Loading</small>This Week\'s Results</div></div></div>';
    // Flatten team visits → your visit + a recruit→visitors map.
    var yourVisit = null, visitors = {};
    (tree.regions || []).forEach(function (rg) {
      (rg.conferences || []).forEach(function (cf) {
        (cf.teams || []).forEach(function (t) {
          if (!t.visit) return;
          var rid = String(t.visit.recruit_id);
          (visitors[rid] = visitors[rid] || []).push({ team_id: String(t.team_id), team_name: t.team_name });
          if (String(t.team_id) === String(state.userTeamId)) yourVisit = t.visit;
        });
      });
    });
    var mineCount = state.recruits.filter(function (r) { return r.leansToUser; }).length;
    var invitesLeft = INVITE_WEEKS.filter(function (w) { return w > state.week; }).length;

    // Hero: your visit
    var heroVisit;
    if (yourVisit) {
      var vrec = state.byId[String(yourVisit.recruit_id)];
      var leanNote = vrec && vrec.leansToUser ? 'now leaning you at <b>#' + (vrec.yourRank || 1) + '</b>. Odds up sharply.' : 'visit logged this week.';
      heroVisit = '<div class="wvisit"><span class="wvisit-mark gain">' + ARROW_UP + '</span><div class="wvisit-body">' +
        '<div class="nm">' + Common.recruitNameLinkHtml(yourVisit.recruit_id, context.franchiseId, yourVisit.name) + '<span class="wmeta" data-tooltip="current/potential" title="current/potential"><span class="pos">' + Common.escapeHtml(yourVisit.pos) + '</span>Region ' + Common.escapeHtml(yourVisit.home_region) + ' · ' + Common.formatRtWithPotential(yourVisit.rt, yourVisit.potential_rt_ratcheted) + ' RT</span></div>' +
        '<div class="sub">Visit landed — ' + leanNote + '</div></div></div>';
    } else {
      heroVisit = '<div class="wvisit"><div class="wvisit-body"><div class="nm">No visit this week</div><div class="sub">Your program didn\'t land a visit in Week ' + state.week + '.</div></div></div>';
    }

    // Contested region activity: your leaners a rival visited this week, grouped by region.
    var byRegion = {};
    state.recruits.filter(function (r) { return r.leansToUser; }).forEach(function (r) {
      var v = visitors[String(r.recruitId)]; if (!v) return;
      var rival = v.filter(function (x) { return x.team_id !== String(state.userTeamId); })[0];
      (byRegion[regionOf(r)] = byRegion[regionOf(r)] || []).push({ r: r, rival: rival });
    });
    var regionsShown = REGION_ORDER.filter(function (rg) { return byRegion[rg]; }).slice(0, 4);
    var regionHtml = regionsShown.map(function (rg) {
      var visits = byRegion[rg].slice(0, 6).map(function (x) {
        var rivalPart = x.rival
          ? '<span class="team">' + Common.escapeHtml(Spine.Lean.deriveAbbr(x.rival.team_name, x.rival.team_id)) + '</span><span class="note threat">also visited — contested</span>'
          : '<span class="note">no rival visits — clear lane</span>';
        return '<div class="wvrow"><span class="team you">' + Common.escapeHtml(Spine.Lean.deriveAbbr(state.teamName || 'You', state.userTeamId)) + '</span>' +
          '<span class="who">' + Common.escapeHtml(x.r.name) + '</span><span class="arrow">·</span>' + rivalPart + '</div>';
      }).join('');
      return '<div class="wregion-row"><span class="wregion-tag">' + rg + '</span><div class="wregion-visits">' + visits + '</div></div>';
    }).join('');
    if (!regionHtml) regionHtml = '<div class="wregion-empty"><span class="note">No contested visits among your leaners this week — clear lanes.</span></div>';

    return '<div class="wpanel"><div class="wpanel-head"><span class="wpanel-badge">' +
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M4 22V4M4 4h13l-2 4 2 4H4"></path></svg></span>' +
        '<div class="wpanel-title"><small>Week ' + state.week + ' · Visits processed</small>This Week\'s Results</div></div>' +
      '<div class="wpanel-hero"><div class="whero"><div class="whero-lbl">Your visit</div>' + heroVisit + '</div>' +
        '<div class="whero"><div class="whero-lbl">What it changed</div><div class="wvisit"><span class="wvisit-mark gain">' + DOT_SVG + '</span>' +
          '<div class="wvisit-body"><div class="nm">' + state.newLeanIds.size + ' new lean' + (state.newLeanIds.size === 1 ? '' : 's') + ' this week</div>' +
          '<div class="sub"><b>' + mineCount + '</b> recruits now have your team on their list. ' + invitesLeft + ' invite' + (invitesLeft === 1 ? '' : 's') + ' left this season.</div></div></div></div></div>' +
      '<div class="wregion">' + regionHtml + '</div></div>';
  }
  function dismissWeekly() {
    state.weeklyDismissed = true;
    var host = document.getElementById('hub-weekly'); if (host) host.innerHTML = '';
    var pool = document.querySelector('.pool-wrap');
    if (pool) window.scrollTo({ top: pool.getBoundingClientRect().top + window.scrollY - 60, behavior: 'smooth' });
  }
  function loadWeeklyPanel() {
    var host = document.getElementById('hub-weekly'); if (!host) return;
    var render = function () { host.innerHTML = weeklyPanelHtml(); var d = host.querySelector('#weekly-dismiss'); if (d) d.addEventListener('click', dismissWeekly); };
    if (state.visitTree) { render(); return; }
    Common.fetchJSON(API_CONFIG.buildUrl('/franchise/recruiting-results') + '?franchise_id=' + encodeURIComponent(context.franchiseId) + '&week=' + encodeURIComponent(state.week))
      .then(function (tree) { state.visitTree = tree || {}; render(); })
      .catch(function (err) { console.error(err); state.weeklyDismissed = true; host.innerHTML = ''; });
  }

  // ===================== SHELL =====================
  function renderShell() {
    var root = document.getElementById('hub-root');
    var signing = state.phase === 'day', results = state.phase === 'results';
    var body;
    if (signing) body = '<div class="hub-body-sign" id="hub-sign"></div>';
    else if (results) body = '<div id="hub-signings"></div>';
    else body =
      (showWeeklyPanel() ? '<div id="hub-weekly"></div>' : '') +
      '<div class="spine-body ' + (hasDock() ? 'with-dock' : 'no-dock') + '" style="padding-top:14px">' +
        '<div style="min-width:0;display:flex;flex-direction:column;gap:14px">' +
          (state.phase === 'passive' ? storyHtml() : '') +
          // Invite phase: hero + board rows lead the main column (mockup .desk), with the
          // pool beneath as the add source. The right column is the rail.
          (hasDock() ? '<div id="hub-board"></div>' : '') +
          '<div class="pool-wrap"><div id="hub-pool"></div></div></div>' +
        (hasDock() ? '<div id="hub-dock"></div>' : '') + '</div>';
    root.innerHTML =
      '<div class="spine-topbar"><span class="spine-h">Recruiting <b>Hub</b></span><span id="hub-anchor-mount"></span></div>' +
      '<div class="spine-topbar" style="padding-top:12px;padding-bottom:0"><div style="flex:1" id="hub-phase"></div></div>' + body;
    var phaseHost = document.getElementById('hub-phase');
    phaseHost.innerHTML = Spine.Phase.stripHtml({ phase: state.phase, week: state.week,
      inviteSent: Math.max(0, INVITE_WEEKS.filter(function (w) { return w < state.week; }).length), points: remaining() });
    Spine.Phase.bind(phaseHost);
    var mount = document.getElementById('hub-anchor-mount');
    mount.innerHTML = Spine.Anchor.html();
    Spine.Anchor.bind(mount.querySelector('.hub-anchor'), {
      poolSelector: signing ? '.spool' : results ? '.signings-wrap' : '.pool-wrap',
      onDismiss: null   // weekly-results panel is persistent now; the anchor only scrolls to the pool
    });
    if (signing) { document.getElementById('hub-sign').innerHTML = signBoardHtml(); bindSignBoard(); }
    else if (results) { renderSignings(); }
    else { renderPool(); if (hasDock()) renderDock(); if (showWeeklyPanel()) loadWeeklyPanel(); }
  }

  // ===================== INIT =====================
  function init() {
    var root = document.getElementById('hub-root'), backBtn = document.getElementById('back-btn');
    if (!context.franchiseId || !context.teamId) { if (root) root.innerHTML = '<div class="hub-error">Missing franchise context.</div>'; return; }
    if (backBtn) backBtn.href = Common.buildFccUrl(context);
    Common.fetchJSON(API_CONFIG.buildUrl('/franchise/recruiting-data') + '?franchise_id=' + encodeURIComponent(context.franchiseId))
      .then(function (data) {
        state.week = Number(data.week || 1);
        state.phase = Spine.Phase.forWeek(state.week);
        state.userTeamId = data.team_id || context.teamId;
        state.userRegion = REGION_ORDER.indexOf(String(data.team_region || '').trim().toUpperCase()) !== -1
          ? String(data.team_region).trim().toUpperCase() : '';
        state.teamName = data.team || 'your program';
        state.currentResultsWeek = data.current_results_week;
        state.week35Results = data.week_35_recruiting_results || {};
        state.newLeanIds = new Set((data.new_lean_recruit_ids || []).map(String));
        var teamNameMap = data.team_name_map || {};
        state.recruits = Common.normalizeRecruits(data.recruits || [], teamNameMap).map(function (r) {
          var model = Spine.Lean.fromBackend({ Lean: r.lean }, { userTeamId: state.userTeamId, teamNameMap: teamNameMap });
          r.leanModel = model; r.leansToUser = model.leansToUser; r.yourRank = model.yourRank;
          state.byId[r.recruitId] = r; return r;
        });
        state.wire = data.recruiting_wire || {};
        // Capacity and competition are SERVER numbers — never recomputed client-side.
        state.rosterCapacity = data.roster_capacity || {};
        state.competitionCounts = data.competition_counts || {};
        state.leanMultipliers = data.lean_multipliers || {};
        state.watchlist = new Set((data.watchlist || []).map(String));
        // Seed the board from saved orders ({"1":id,...} → ordered), keeping only still-valid,
        // unique recruits (backend already dedupes; guard defensively).
        var seen = {};
        state.board = Common.recruitingOrderIds(data.saved_orders || {}).filter(function (id) {
          if (!state.byId[id] || seen[id]) return false; seen[id] = true; return true;
        });
        // Watchlist pre-populates the invite board — CLIENT-SIDE STATE ONLY.
        //
        // HARD RULE: this must never persist. has_saved_board derives from
        // _team_order_list(ftd["Recruits"]), and both the week-20 gate and the server
        // guard at franchise_routes:11966 key off it. Writing Recruits here would flip
        // the gate open before the player had saved anything — seedAlloc()'s mistake
        // (pre-committing the player to a choice they never made) in a new location.
        // Recruits is written by save_recruiting_orders and nowhere else.
        //
        // Only seeds when nothing is saved yet, so it can never reorder or overwrite a
        // board the player built. The watchlist has no ranks, so RT descending supplies
        // the initial order the board needs — the star press implied no position.
        state.boardSeededFromWatchlist = false;
        if (!state.board.length && state.watchlist.size) {
          state.boardSeededFromWatchlist = true;
          state.board = state.recruits
            .filter(function (r) { return state.watchlist.has(String(r.recruitId)); })
            .sort(function (a, b) { return (b.rt != null ? b.rt : -1) - (a.rt != null ? a.rt : -1); })
            .slice(0, MAX_BOARD)
            .map(function (r) { return r.recruitId; });
        }
        // Signing Day: restore the budget from saved entries; else auto-fill top leaners.
        state.week35Ran = !!data.week_35_recruiting_ran;
        if (state.phase === 'day') {
          // Restore what the player previously SAVED, and nothing else. There is no
          // load-time seed: an empty board loads at 0 of 50 with zero promises.
          (data.saved_order_entries_week_35 || [])
            .filter(function (e) { return e && state.byId[e.id]; })
            .forEach(function (e) {
              state.alloc[e.id] = { points: Number(e.points) || 0, promise: !!e.playing_time };
              pruneAlloc(e.id);
            });
        }
        renderShell();
      })
      .catch(function (err) { console.error(err); if (root) root.innerHTML = '<div class="hub-error">Failed to load recruits.</div>'; });
  }

  init();
})();
