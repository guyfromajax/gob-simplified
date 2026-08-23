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
  var SORTABLE = { name: 'text', pos: 'num', year: 'num', height: 'num', weight: 'num', region: 'text', rt: 'num' };
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
    boardSeeded: false,              // drives the seed notice; cleared on save/reorder
    seedModalSeen: false,            // season-stamped server-side
    seedNoticeDismissed: false,
    sort: { key: 'rt', dir: 'desc' }, collapsed: {},
    drag: { from: null, over: null },
    // Signing Day (wk 35)
    alloc: {},                       // { recruitId: {points, promise} } — starts EMPTY
    rosterCapacity: {},              // from payload.roster_capacity
    competitionCounts: {},           // recruit_id -> programs funding him
    sTab: 'mine', sRegion: 'all', sSearch: '', week35Ran: false, flashId: null,
    // Signing Day filters mirror the pool's, but keep their own state: the two
    // screens are read for different jobs and a filter carried across surprises.
    sPos: 'all', sYear: 'all', sWatch: false, sView: 'pool',
    // Results (D4)
    currentResultsWeek: null, weeklyDismissed: false, visitTree: null,
    playback: { index: 0, auto: false, done: false, timer: null },
    week35Results: {}, signFilter: 'all',
    // Signing Day conference reveal (payload `conferences`; `revealSeen` season-stamped
    // server-side so a refresh after submitting does not replay it).
    conferences: null, teamNameMap: {}, revealSeen: false, visitHistory: [],
    reveal: { index: 0, done: false, timer: null, summaryRows: null, seenSent: false }
  };
  // No per-recruit cap: the 50-point budget is the only limit, so every point can go
  // on one recruit if that is the call the coach wants to make.
  var SIGN = { TOTAL: 50, PROMISE_W: 18 };

  function boardActive() { return state.phase === 'invite'; }
  function attrClass(v) { return v >= 65 ? 'attr-hi' : v >= 40 ? 'attr-mid' : v >= 20 ? 'attr-lo' : 'attr-zero'; }
  function regionOf(rec) { var v = rec && rec.homeRegion ? String(rec.homeRegion).trim().toUpperCase() : ''; return v ? v.charAt(0) : ''; }
  // Recruit | Pos | RT | Yr | Ht | Rgn | Attributes | Lean | Watch — attributes are a
  // single cell of chips now, not 12 columns. +1 for the add column in the invite phase.
  function colspan() { return (boardActive() ? 1 : 0) + 10; }   // +1: Wt

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
      '<col class="c-wt"><col class="c-rgn"><col class="c-attrs"><col class="c-lean"><col class="c-watch">' +
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
      th('weight', 'Wt') +
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
      '<td class="num">' + (r.weight != null ? Common.escapeHtml(r.weight) : '--') + '</td>' +
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

  /**
   * Region <option>s with the user's own region lifted to the top, above a divider.
   * His region is the one he recruits in every week, so it should not be hunted for
   * halfway down an alphabetical list. It still appears in the A-H run below the rule,
   * so the list stays complete and scanning by letter works — the same value twice is
   * intentional, and selecting either filters identically.
   */
  function regionOptionsHtml(selected) {
    var mine = state.userRegion;
    var opt = function (value, label) {
      return '<option value="' + value + '"' + (selected === value ? ' selected' : '') + '>' + label + '</option>';
    };
    var head = '';
    if (mine && REGION_ORDER.indexOf(mine) !== -1) {
      head = opt(mine, 'Region ' + mine + ' — your region')
        + '<option disabled>──────────</option>';
    }
    return head + opt('all', 'All regions')
      + REGION_ORDER.map(function (r) { return opt(r, 'Region ' + r); }).join('');
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
      // fetchJSON does not set Content-Type, and fetch() defaults a string body to
      // text/plain — which FastAPI rejects with 422 before the handler runs. Every
      // other body-carrying call in this file sets it; this one did not, so the star
      // flipped optimistically and the catch below reverted it on every click.
      method: 'PATCH', headers: { 'Content-Type': 'application/json' },
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

  // ===================== UNSUBMITTED DRAFT =====================
  // Opening a recruit's profile and coming back must not silently discard edits — the
  // board and the week-35 allocation are both real work, and a full page navigation
  // otherwise reloads them from the server copy.
  //
  // Same shape as the training form draft (training.js): sessionStorage, keyed by
  // franchise + team + week, versioned, and re-validated on restore. It is CLIENT-ONLY
  // and writes nothing to FTD `Recruits`, so it cannot flip `has_saved_board` — the
  // seeding rule applies here for exactly the same reason it applies to the watchlist
  // seed: a draft is not a submission.
  var DRAFT_V = 1;

  function draftKey() {
    if (!context.franchiseId) return null;
    return 'gob_recruiting_draft_' + context.franchiseId + '|' + (context.teamId || '') + '|w' + state.week;
  }

  function saveDraft() {
    var key = draftKey(); if (!key) return;
    try {
      sessionStorage.setItem(key, JSON.stringify({
        v: DRAFT_V, week: state.week, phase: state.phase,
        board: state.board, alloc: state.alloc,
      }));
    } catch (_e) {}
  }

  function clearDraft() {
    var key = draftKey(); if (!key) return;
    try { sessionStorage.removeItem(key); } catch (_e) {}
  }

  /** Parsed draft for THIS week and phase, or null. */
  function readDraft() {
    var key = draftKey(); if (!key) return null;
    var raw; try { raw = sessionStorage.getItem(key); } catch (_e) { return null; }
    if (!raw) return null;
    var o; try { o = JSON.parse(raw); } catch (_e) { return null; }
    if (!o || o.v !== DRAFT_V) return null;
    // The key already carries the week, but a week can advance in another tab under the
    // same key, so the payload re-states it. Phase likewise: an invite board must never
    // be restored onto Signing Day.
    if (Number(o.week) !== Number(state.week)) return null;
    if (o.phase !== state.phase) return null;
    return o;
  }

  /**
   * Lay a draft over the server copy, dropping anything it cannot vouch for.
   *
   * A draft is untrusted input by the time it is read back: the pool is regenerated at
   * rollover, so ids can vanish, and sessionStorage is user-editable. Everything is
   * re-checked against the loaded recruits and the same caps the UI enforces.
   */
  function restoreDraft() {
    var d = readDraft(); if (!d) return;
    if (state.phase === 'invite' && Array.isArray(d.board)) {
      var seen = {};
      state.board = d.board.filter(function (id) {
        if (!state.byId[id] || seen[id]) return false; seen[id] = true; return true;
      }).slice(0, MAX_BOARD);
      // An edited board is the player's, whatever seeded it.
      clearSeedNotice();
    }
    if (state.phase === 'day' && d.alloc && typeof d.alloc === 'object') {
      var alloc = {}, total = 0;
      Object.keys(d.alloc).forEach(function (id) {
        var a = d.alloc[id];
        if (!state.byId[id] || !a) return;
        var pts = Math.max(0, Math.floor(Number(a.points) || 0));
        var promise = !!a.promise;
        if (!pts && !promise) return;
        alloc[id] = { points: pts, promise: promise };
        total += pts;
      });
      // Over budget can only come from a tampered or stale payload — the UI cannot
      // produce one. Drop the whole draft rather than restoring a board that cannot
      // be submitted.
      if (total <= SIGN.TOTAL) state.alloc = alloc;
    }
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
  // Every board edit passes through here, so it is the one place the draft needs
  // stamping — reorder included, which no click handler alone would cover.
  function renderBoardDependent() { saveDraft(); renderPoolBodyOnly(); renderDock(); }

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
  /**
   * DORMANT — the board's "This week" column was removed from the layout but the
   * feature is kept on purpose so it can be switched back on. Render this cell from
   * boardRowHtml() and re-add its header to restore it.
   */
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
  /** DORMANT — see thisWeekCellHtml: kept with the "This week" feature it belongs to. */
  function topUnvisitedId() {
    var visited = visitedRecruitIds();
    for (var i = 0; i < state.board.length; i++) {
      if (!visited[String(state.board[i])]) return state.board[i];
    }
    return null;
  }
  // ---------- board seed ----------
  /**
   * The board a player who has never saved one lands on.
   *
   * Leans first, then the watchlist tops it up. A recruit leaning to you is the live
   * signal — he is already interested — so he outranks a name you starred to keep an eye
   * on; but a star still counts for something rather than being ignored. RT descending
   * within each group: neither source carries ranks, so the board needs an order and
   * "best available first" is the only defensible one.
   *
   * Sets no state and writes nothing — the caller owns both.
   */
  function seedBoard() {
    var byRt = function (a, b) { return (b.rt != null ? b.rt : -1) - (a.rt != null ? a.rt : -1); };
    var leans = state.recruits.filter(function (r) { return r.leansToUser; }).sort(byRt);
    var picked = {};
    var out = leans.slice(0, MAX_BOARD).map(function (r) { picked[r.recruitId] = 1; return r.recruitId; });
    if (out.length < MAX_BOARD && state.watchlist.size) {
      state.recruits
        .filter(function (r) { return state.watchlist.has(String(r.recruitId)) && !picked[r.recruitId]; })
        .sort(byRt)
        .slice(0, MAX_BOARD - out.length)
        .forEach(function (r) { out.push(r.recruitId); });
    }
    state.boardSeeded = out.length > 0;
    return out;
  }

  /**
   * One-time Sammy note explaining the seeded board.
   *
   * Fires on the Hub, not the FCC: it explains something the player is looking at, so
   * it belongs on the screen that shows it. Season-stamped server-side
   * (/franchise/invite-seed-modal-seen), so a refresh does not replay it and a new
   * season re-arms it with nothing having to clear a flag.
   *
   * Gated on the seed HAVING HAPPENED, not merely on the week: a board with no leans
   * and no watchlist seeds nothing, and a note about a pre-populated board would then
   * be describing an empty one.
   */
  function maybeShowSeedModal() {
    if (state.phase !== 'invite' || !state.boardSeeded || state.seedModalSeen) return;
    state.seedModalSeen = true;
    var path = function (p) {
      return (window.API_CONFIG && API_CONFIG.buildStaticPath) ? API_CONFIG.buildStaticPath(p) : p;
    };
    Promise.all([
      import(path('/js/shared/sammyModal.js')),
      import(path('/js/shared/teamCoachAsset.js')),
    ]).then(function (loaded) {
      loaded[0].showSammyModal({
        eyebrow: 'Week ' + state.week + ' \u00b7 Invite Season',
        body: 'Hey Coach, your Invite Board is pre-populated with your current leans, '
          + 'but you can add other players too.',
        ctaLabel: 'Got It',
        // Team-coloured Sammy for the eight mapped teams, generic white otherwise —
        // the mapping already encodes the conference-1 rule, so there is no check here.
        imageSrc: loaded[1].getTeamSammyImage(state.teamName || ''),
        primaryClass: 'is-orange',
      });
      return Common.fetchJSON(API_CONFIG.buildUrl('/franchise/invite-seed-modal-seen'), {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ franchise_id: context.franchiseId })
      });
    }).catch(function (err) { console.warn('[SEED-MODAL] skipped', err); });
  }

  // ---------- seed notice ----------
  // Shown only when the board came from the seed, never from a real save — otherwise it
  // would be a lie. Says plainly that nothing is sent yet, because the whole point of
  // the client-side seed is that the player is not yet committed.
  function seedNoticeHtml() {
    if (!state.boardSeeded || state.seedNoticeDismissed) return '';
    return '<div class="bseed" id="board-seed-notice">' +
      '<span class="bseed-txt">Seeded from your current leans, ranked by RT. Drag to re-order — ' +
      '<b>nothing is sent until you save</b>.</span>' +
      '<button class="bseed-x" id="board-seed-dismiss" type="button" aria-label="Dismiss">×</button></div>';
  }
  // Any real reorder means the order is now the player's, so the notice has served out.
  function clearSeedNotice() { state.boardSeeded = false; }

  // ---------- board rows ----------
  /** Which invite week (if any) this recruit visited the user's team. */
  /**
   * How many of weeks 20-26 this recruit has spent visiting the user's team.
   *
   * A COUNT, not a week: a recruit can come back, and the seven-square calendar above
   * already says which weeks. Repeat interest is the thing the board row could not
   * show, and the number fits where a week stamp did not.
   */
  function visitCountFor(id) {
    var hist = state.visitHistory || [];
    var n = 0;
    for (var i = 0; i < hist.length; i++) {
      if (hist[i].recruit_id && String(hist[i].recruit_id) === String(id)) n++;
    }
    return n;
  }

  function boardRowHtml(id, index) {
    var r = state.byId[id];
    // Every rank 1-20 is always drawn. An unfilled slot is a slot, not an absence —
    // it keeps the panel a fixed size and shows how much board is left.
    if (!r) {
      return '<div class="brow is-empty" data-index="' + index + '">' +
        '<div class="brank"><span class="bnum">' + (index + 1) + '</span></div>' +
        '<div class="bempty-hint">Open</div></div>';
    }
    var event = wireByRecruit()[String(id)];
    var moveCls = event ? movementClass(event.kind) : '';
    var visits = visitCountFor(id);
    return '<div class="brow ' + moveCls + (visits ? ' is-visited' : '') +
        '" draggable="true" data-index="' + index + '" data-id="' + id + '">' +
      '<div class="brank"><span class="bgrip" aria-hidden="true"></span><span class="bnum">' + (index + 1) + '</span></div>' +
      '<div class="bname">' + headshotBoxHtml(r, 'bav') + '<span class="btxt">' +
        Common.recruitNameLinkHtml(r.recruitId, context.franchiseId, r.name) +
        // Visit count rides beside the archetype, not in a column of its own: a stamp
        // out at the row's edge sat next to the lean ladder and fought it for space the
        // moment a recruit had three leans.
        '<small><span class="barch">' + Common.escapeHtml(r.archetype) + '</span>' +
          (visits ? '<span class="bvisit-pill">' + visits + (visits === 1 ? ' visit' : ' visits') + '</span>' : '') +
        '</small></span></div>' +
      '<div class="bc">' + Common.escapeHtml(r.pos) + '</div>' +
      '<div class="brt ' + Spine.rtClassForYear(r.rt, r.year) + '" data-tooltip="current/potential" title="current/potential">' +
        Common.formatRtWithPotential(r.rt, r.potentialRt) + '</div>' +
      '<div class="bc dim">' + Common.escapeHtml(r.yearDisplay) + '</div>' +
      '<div class="bc dim">' + Common.escapeHtml(r.height) + '</div>' +
      '<div class="bc dim">' + (r.weight != null ? Common.escapeHtml(r.weight) : '--') + '</div>' +
      '<div class="bladder">' + Spine.Lean.ladderHtml(r.leanModel) + '</div>' +
      '<div><button class="bx" data-remove-id="' + id + '" title="Remove from board" type="button">\u00d7</button></div>' +
      '</div>';
  }

  function boardColumnHtml(from, to) {
    var out = '';
    for (var i = from; i < to; i++) out += boardRowHtml(state.board[i], i);
    return '<div class="bcol">' +
      '<div class="brow bhdr"><div>#</div><div>Recruit</div><div class="bc">Pos</div>' +
        '<div>RT</div><div class="bc">Yr</div><div class="bc">Ht</div><div class="bc">Wt</div>' +
        '<div>Lean</div><div></div></div>' + out + '</div>';
  }

  // Board shape at a glance — position mix and class mix. Every key is always drawn,
  // zero included: the gap is the point, and a tile that disappears at zero hides
  // exactly the thing worth seeing.
  //
  // Playbook order for positions; youngest-first for years, matching the pool's own
  // year sort (GOB_PlayerYear.YEAR_SORT_ORDER) rather than inventing a second order.
  var BOARD_POSITIONS = ['PG', 'SG', 'SF', 'PF', 'C'];
  var BOARD_YEARS = ['JH', 'FR', 'SO', 'JR'];

  /** keys -> count, over the board, using `pick` to read each recruit's key. */
  function boardTileCounts(keys, pick) {
    var counts = {};
    keys.forEach(function (k) { counts[k] = 0; });
    state.board.forEach(function (id) {
      var r = state.byId[id];
      if (!r) return;
      var k = pick(r);
      if (counts[k] != null) counts[k]++;
    });
    return counts;
  }

  function tileGroupHtml(keys, counts) {
    return '<div class="bpos">' + keys.map(function (k) {
      return '<span class="bpos-t' + (counts[k] ? '' : ' is-zero') + '">' +
        '<b>' + k + '</b><i>' + counts[k] + '</i></span>';
    }).join('') + '</div>';
  }

  function boardShapeTilesHtml() {
    // yearDisplay is already the abbreviation the tiles are keyed on (formatYearAbbrev),
    // so nothing re-derives it here and the two cannot drift.
    return '<div class="bshape">' +
      tileGroupHtml(BOARD_POSITIONS, boardTileCounts(BOARD_POSITIONS, function (r) { return r.pos; })) +
      '<span class="bshape-div" aria-hidden="true"></span>' +
      tileGroupHtml(BOARD_YEARS, boardTileCounts(BOARD_YEARS, function (r) { return r.yearDisplay; })) +
      '</div>';
  }

  function boardHtml() {
    // Header carries the count and the CTA; the hero panel that repeated rank 1 is gone.
    return '<section class="bpanel">' +
      '<div class="bpanel-head">' +
        '<div class="bpanel-title">Invite Board</div>' +
        boardShapeTilesHtml() +
        '<div class="bpanel-count"><span class="n">' + state.board.length + '</span><span class="of">/ ' + MAX_BOARD + '</span></div>' +
        '<button class="bbtn-save" id="dock-save" type="button">Submit Invites</button>' +
      '</div>' +
      seedNoticeHtml() +
      // Two fixed columns of ten: ranks 1-10 and 11-20.
      '<div class="bgrid">' + boardColumnHtml(0, 10) + boardColumnHtml(10, MAX_BOARD) + '</div>' +
      '</section>';
  }

  function renderDock() {
    var board = document.getElementById('hub-board');
    if (board) { board.innerHTML = boardHtml(); bindBoard(board); }
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
    var save = host.querySelector('#dock-save');
    if (save) save.addEventListener('click', saveBoard);
    bindHeadshotFallbacks(host);
  }

  function saveBoard() {
    var btn = document.getElementById('dock-save'); if (btn) { btn.disabled = true; btn.textContent = 'Submitting…'; }
    Common.fetchJSON(API_CONFIG.buildUrl('/franchise/recruiting-orders'), {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ franchise_id: context.franchiseId, recruit_ids: state.board })
    }).then(function () {
      // Committed: the notice says "nothing is sent until you save", which is no longer
      // true, so it must go. Also flips this board from seeded to saved.
      clearSeedNotice();
      // The server copy now IS the board, so the draft has nothing left to preserve.
      clearDraft();
      // Straight to the locker room — no confirmation hold. The loading screen IS the
      // acknowledgement, and a 2s toast in front of it read as a stall rather than a
      // beat. No success toast either: it would be torn down by the navigation before
      // anyone could read it.
      //
      // The button is disabled first and never re-armed: the navigation is not
      // instantaneous, and a second press in that window would post the same board again
      // and re-stamp board_saved_week. Re-queried, NOT the `btn` captured above —
      // renderDock() above rebuilds the panel, so that reference is already detached.
      renderDock();
      var live = document.getElementById('dock-save');
      if (live) live.disabled = true;
      window.location.href = Common.buildFccUrl(context);
    })
      .catch(function (err) {
        console.error(err);
        showToast('Submit failed', String(err && err.message || err), false);
        // Only a FAILED submit re-arms the button, and it goes back to the label the
        // board actually renders. No renderDock() on this path, so `btn` is still live.
        if (btn) { btn.disabled = false; btn.textContent = 'Submit Invites'; }
      });
  }

  // ===================== TOAST =====================
  function showToast(title, sub, ok) {
    var el = document.getElementById('hub-toast');
    if (!el) { el = document.createElement('div'); el.id = 'hub-toast'; el.className = 'hub-toast'; document.body.appendChild(el); }
    el.innerHTML = '<span class="ti">' + CHECK + '</span><div><div class="tt1">' + Common.escapeHtml(title || 'Invites Submitted') +
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

  // ── Standing + Lean: two honest columns, no percentage anywhere ────────────
  // There is deliberately no probability on this screen. A number like "62%" is a
  // promise the sim cannot keep; a multiplier and the actual ladder are facts. If you
  // ever find yourself deriving a percent to rank or sort, that is the old placeholder
  // growing back.
  function standingCellHtml(r) {
    var rank = Number(r.yourRank || 0);
    var mult = leanMultiplier(rank);
    var label = rank === 1 ? '#1' : rank > 1 ? '#' + rank : '—';
    var cls = rank === 1 ? ' s-you1' : rank > 1 ? ' s-list' : '';
    return '<div class="stand-cell' + cls + '">' +
      '<span class="stand-pos">' + label + '</span>' +
      // "5x odds" rather than "x5": the number is a multiplier ON HIS ODDS of signing
      // with you, and the bare "x5" read as a quantity.
      '<span class="stand-mult">' + mult + 'x odds</span></div>';
  }
  function competitionCount(id) {
    var counts = (state.competitionCounts || {});
    var raw = counts[String(id)];
    return raw == null ? null : Number(raw);
  }
  function leanCellHtml(r) {
    return '<div class="prow-lean">' + Spine.Lean.ladderHtml(r.leanModel) + '</div>';
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
      if (state.sWatch && !state.watchlist.has(String(r.recruitId))) return false;
      if (state.sRegion !== 'all' && regionOf(r) !== state.sRegion) return false;
      if (state.sPos !== 'all' && r.pos !== state.sPos) return false;
      if (state.sYear !== 'all' && r.year !== state.sYear) return false;
      if (q && String(r.name).toLowerCase().indexOf(q) === -1) return false;
      return true;
    }).sort(function (a, b) { return (b.rt || 0) - (a.rt || 0); });
  }

  function prowHtml(r) {
    var a = allocOf(r.recruitId);
    var committed = a.points > 0 || a.promise;
    var canPlus = remaining() > 0;
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
      leanCellHtml(r) +
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
            '<span data-tooltip="current/potential" title="current/potential">' + Common.escapeHtml(x.r.pos) +
              ' · <span class="v ' + Spine.rtClassForYear(x.r.rt, x.r.year) + '">' +
              Common.formatRtWithPotential(x.r.rt, x.r.potentialRt) + '</span> RT</span>' +
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
        '</div>' +
      list + preflight +
      '<div class="rail-foot">' + note +
        '<button class="rail-submit" id="sign-submit"' + (disabled ? ' disabled' : '') + '>' + (state.week35Ran ? 'Signings Run' : 'Submit Orders') + '</button></div>';
  }

  function signBoardHtml() {
    var STAR = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2.6l2.9 5.9 6.5.95-4.7 4.58 1.11 6.47L12 17.44l-5.81 3.06 1.11-6.47-4.7-4.58 6.5-.95z" fill="currentColor"/></svg>';
    var watchCount = state.recruits.filter(function (r) { return state.watchlist.has(String(r.recruitId)); }).length;
    var posOpts = [{ value: 'all', label: 'All' }].concat(POS_ORDER.map(function (p) { return { value: p, label: p }; }));
    return '<div class="spool"><div class="spool-head"><div class="spool-title">Recruit Pool</div>' +
        '<div class="spool-tools"><div class="spool-tabs">' +
          '<button class="spool-tab' + (state.sTab === 'mine' ? ' on' : '') + '" data-stab="mine">Leaning to you</button>' +
          '<button class="spool-tab' + (state.sTab === 'all' ? ' on' : '') + '" data-stab="all">All</button></div>' +
          // The watchlist he built all season is the shortest path to the recruits he
          // actually means to spend on, so it sits with the other filters here too.
          '<button class="spool-watch' + (state.sWatch ? ' on' : '') + '" id="sign-watch" type="button" aria-pressed="' +
            (state.sWatch ? 'true' : 'false') + '">' + STAR + 'Watchlist<span class="n">' + watchCount + '</span></button>' +
          '<select class="spool-region" id="sign-region">' + regionOptionsHtml(state.sRegion) + '</select>' +
          segHtml('spos', posOpts, state.sPos) +
          segHtml('syear', YEAR_FILTERS, state.sYear) +
          '<input class="spool-search" id="sign-search" placeholder="Search name…" value="' + Common.escapeHtml(state.sSearch) + '"></div></div>' +
        '<div class="spool-colhdr"><span>Recruit</span><span class="c-num">Pos</span><span class="c-num">Region</span><span class="c-num">RT</span>' +
          '<span class="c-num">Standing</span><span>Lean</span><span>Points</span><span>Playing Time</span></div>' +
        '<div class="spool-rows" id="sign-rows">' + signFiltered().map(prowHtml).join('') + '</div></div>' +
      '<aside class="rail" id="sign-rail">' + railHtml() + '</aside>';
  }

  /**
   * Signing Day view switch. 'orders' drops the Recruit Pool entirely and lets Your
   * Orders take the full width — the state where the coach is reviewing what he has
   * committed rather than shopping. A class on the container, not a re-render, so
   * scroll position and the rail's own state survive the switch.
   */
  function applySignView() {
    var host = document.getElementById('hub-sign');
    if (host) host.classList.toggle('is-orders-only', state.sView === 'orders');
    var btn = document.getElementById('hub-orders-toggle');
    if (btn) {
      btn.classList.toggle('is-on', state.sView === 'orders');
      btn.setAttribute('aria-pressed', state.sView === 'orders' ? 'true' : 'false');
    }
  }

  function setSignView(view) {
    state.sView = view === 'orders' ? 'orders' : 'pool';
    applySignView();
  }

  /** Re-render the whole signing board: the toolbar's pressed states move with the filters. */
  function refreshSignBoard() {
    var host = document.getElementById('hub-sign');
    if (!host) return;
    host.innerHTML = signBoardHtml();
    applySignView();
    bindSignBoard();
  }

  function renderSignRows() {
    var rows = document.getElementById('sign-rows'); if (!rows) return;
    var top = rows.scrollTop;
    rows.innerHTML = signFiltered().map(prowHtml).join('');
    rows.scrollTop = top;
    bindSignRows();
  }
  function renderSignRail() { var rail = document.getElementById('sign-rail'); if (rail) { rail.innerHTML = railHtml(); bindSignRail(); } }

  // Shared tail for every allocation edit — the one place the draft is stamped.
  function afterAllocChange() { saveDraft(); renderSignRows(); renderSignRail(); }
  function stepPoints(id, d) {
    var a = allocOf(id), nv = a.points + d;
    if (nv < 0) return;
    if (d > 0 && remaining() <= 0) return;
    state.alloc[id] = { points: nv, promise: a.promise }; pruneAlloc(id);
    afterAllocChange();
  }
  function togglePromise(id) {
    var a = allocOf(id);
    state.alloc[id] = { points: a.points, promise: !a.promise }; pruneAlloc(id);
    afterAllocChange();
  }
  function removeCommit(id) { delete state.alloc[id]; afterAllocChange(); }
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
    var watch = document.getElementById('sign-watch');
    if (watch) watch.addEventListener('click', function () { state.sWatch = !state.sWatch; refreshSignBoard(); });
    document.querySelectorAll('[data-spos]').forEach(function (b) {
      b.addEventListener('click', function () { state.sPos = this.dataset.spos; refreshSignBoard(); });
    });
    document.querySelectorAll('[data-syear]').forEach(function (b) {
      b.addEventListener('click', function () { state.sYear = this.dataset.syear; refreshSignBoard(); });
    });
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
      '<div class="ssum-foot">' +
        '<button class="ssum-back" id="ssum-back" type="button">Back to Orders</button>' +
        '<button class="ssum-lr" id="ssum-go" type="button">Go To Locker Room</button>' +
      '</div></div>';
    document.body.appendChild(overlay);
    // Back to Orders: the orders are already saved, so closing loses nothing and the
    // board is still editable.
    var back = overlay.querySelector('#ssum-back');
    if (back) back.addEventListener('click', function () {
      overlay.remove();
      var btn = document.getElementById('sign-submit');
      if (btn) { btn.disabled = false; btn.textContent = 'Submit Orders'; }
    });
    // The irreversible step MOVED to the FCC. Submitting saves; running is a separate
    // press on the locker-room screen, where "Edit Recruiting Orders" sits beside it.
    // Amber, not green: this button no longer commits anything.
    var go = overlay.querySelector('#ssum-go');
    go.addEventListener('click', function () {
      overlay.remove();
      window.location.href = Common.buildFccUrl(context);
    });
    go.focus();
  }

  /**
   * Entry from the FCC's "Run Recruiting Day" (?action=run).
   *
   * The run and the reveal both live here, so the FCC hands the press over rather than
   * duplicating them. Guarded three ways because a URL is user-editable: only on
   * Signing Day, only once the orders the endpoint requires exist, and never after the
   * signings have already run (the run itself advances the franchise to week 36, so
   * this is belt-and-braces against a stale tab).
   */
  function maybeAutoRun() {
    if (context.action !== 'run') return;
    if (state.phase !== 'day' || state.week35Ran) return;
    if (!committedIds().length) return;
    runRecruiting();
  }

  /**
   * Run the signings, then hand straight to the reveal.
   *
   * Split out of submitOrders so the confirm modal sits between SAVING the orders and
   * RUNNING them — previously it appeared after the results were already resolved, which
   * put "Orders Submitted" on screen after the decision could no longer be changed.
   */
  function runRecruiting() {
    var btn = document.getElementById('sign-submit');
    if (btn) { btn.disabled = true; btn.textContent = 'Running…'; }
    Common.fetchJSON(API_CONFIG.buildUrl('/franchise/run-week-35-recruiting'), {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ franchise_id: context.franchiseId })
    }).then(function (res) {
      state.week35Ran = true;
      // The signings were resolved by the call we just made, so state.week35Results —
      // loaded when the page opened — is stale. Take what the endpoint produced.
      if (res && res.results) state.week35Results = res.results;
      startReveal();
    }).catch(function (err) {
      console.error(err); showToast('Run failed', String(err && err.message || err), false);
      if (btn) { btn.disabled = false; btn.textContent = 'Submit Orders'; }
    });
  }

  // ===================== SIGNING DAY REVEAL =====================
  // Presentation only. The engine resolved every signing in one pass at week 35, so
  // nothing here decides anything — it paces a result that already exists (Prompt 6's
  // rule). Widened from the user's conference to their REGION: 16 teams, two
  // conferences, which is the unit the class tallies are read in.
  //
  // All eight regions advance at the same pace so the national top 25 fills as the
  // league walks. Only the user's region produces cards; the other seven exist to move
  // numbers — except for a recruit the user FUNDED, who earns a card wherever he signs
  // (spending points and then losing him off-screen is the one outcome the screen owes
  // the player).

  var REVEAL_HOLD_MS = 5000;
  var REVEAL_NATIONAL_TOP = 25;
  /** The reveal owns the screen, so it owns the audio: the National Tournament bed. */
  var REVEAL_TRACK = 'pregame-national-tourney.mp3';

  /**
   * Swap the franchise loop for the tournament bed while the reveal is up.
   * recruiting-hub.js is a classic script, so the module is pulled in dynamically —
   * same URL as the page's own import, therefore the same audio elements.
   */
  function revealMusic(on) {
    var url = (window.API_CONFIG && API_CONFIG.buildStaticPath)
      ? API_CONFIG.buildStaticPath('/js/musicController.js')
      : '/js/musicController.js';
    import(url).then(function (m) {
      if (on) {
        if (m.clearFranchiseMusicState) m.clearFranchiseMusicState();
        if (m.playGameplayTrack) m.playGameplayTrack(REVEAL_TRACK);
      } else if (m.stopGameplayTrack) {
        m.stopGameplayTrack();
      }
    }).catch(function (err) { console.warn('[REVEAL] music skipped', err); });
  }

  function byRtDesc(a, b) { return (b.rt != null ? b.rt : -1) - (a.rt != null ? a.rt : -1); }
  function isUserSigning(entry) { return String(entry.team_id) === String(state.userTeamId); }
  function teamNameOf(teamId, fallback) {
    return (state.teamNameMap && state.teamNameMap[String(teamId)]) || fallback || '';
  }

  /** Recruit ids the user committed points or a promise to. */
  function fundedIds() {
    var out = {};
    Object.keys(state.alloc || {}).forEach(function (id) {
      var a = state.alloc[id];
      if (a && (a.points > 0 || a.promise)) out[String(id)] = a;
    });
    return out;
  }

  /**
   * Every non-walk-on signing bucketed by region, each bucket RT-descending.
   *
   * Built once per reveal and cached: it is read on every render and every tick, and
   * re-sorting ~400 entries sixty times a minute for a list that cannot change is
   * waste.
   */
  function revealBuckets() {
    if (state.reveal.buckets) return state.reveal.buckets;
    var regionOf = (state.conferences && state.conferences.region_by_team_id) || {};
    var buckets = {};
    (state.week35Results.signed_players || []).forEach(function (e) {
      if (!e || e.walk_on) return;
      var rg = regionOf[String(e.team_id)];
      if (!rg) return;
      (buckets[rg] = buckets[rg] || []).push(e);
    });
    Object.keys(buckets).forEach(function (rg) { buckets[rg].sort(byRtDesc); });
    state.reveal.buckets = buckets;
    return buckets;
  }

  function userRegion() { return (state.conferences && state.conferences.user_region) || null; }

  /** The user's region, RT-descending. Its length sets the tick count for the league. */
  function revealList() {
    var b = revealBuckets()[userRegion()];
    return b || [];
  }

  /**
   * How many of region `rg` have resolved after `tick` ticks.
   *
   * Every region finishes on the SAME tick as the user's, so the national tally is
   * complete exactly when the cards run out. Regions differ by a few signings, so the
   * rate is near 1.0 either way — but pinning it to the total means the top 25 can
   * never be left half-filled on the last card.
   */
  function consumedAt(rg, tick, totalTicks) {
    var len = (revealBuckets()[rg] || []).length;
    if (!totalTicks) return 0;
    return Math.min(len, Math.round(len * tick / totalTicks));
  }

  /**
   * The card queue: the user's region in order, plus any recruit they funded who
   * signed OUTSIDE it, slotted in at the tick his own region resolves him.
   */
  function revealCards() {
    if (state.reveal.cards) return state.reveal.cards;
    var buckets = revealBuckets();
    var home = userRegion();
    var total = (buckets[home] || []).length;
    var funded = fundedIds();
    var cards = (buckets[home] || []).map(function (e, i) {
      return { entry: e, tick: i + 1, away: false };
    });
    Object.keys(buckets).forEach(function (rg) {
      if (rg === home) return;
      var list = buckets[rg];
      list.forEach(function (e, i) {
        if (!funded[String(e.recruit_id)]) return;
        // The tick this signing lands on under the same proportional rate the tally
        // uses, so his card and his score arrive together.
        var tick = list.length ? Math.ceil((i + 1) * total / list.length) : total;
        cards.push({ entry: e, tick: Math.max(1, Math.min(total, tick)), away: true });
      });
    });
    cards.sort(function (a, b) {
      if (a.tick !== b.tick) return a.tick - b.tick;
      return byRtDesc(a.entry, b.entry);
    });
    state.reveal.cards = cards;
    return cards;
  }

  function revealTotalTicks() { return revealList().length; }

  /** team_id -> class score, after `cardIndex` cards have shown. */
  function revealScores(cardIndex) {
    var cards = revealCards();
    var total = revealTotalTicks();
    var tick = cardIndex > 0 ? cards[Math.min(cardIndex, cards.length) - 1].tick : 0;
    var buckets = revealBuckets();
    var scores = {};
    Object.keys(buckets).forEach(function (rg) {
      var n = rg === userRegion() ? Math.min(tick, buckets[rg].length) : consumedAt(rg, tick, total);
      for (var i = 0; i < n; i++) {
        var e = buckets[rg][i];
        var tid = String(e.team_id);
        scores[tid] = (scores[tid] || 0) + (Number(e.rt) || 0);
      }
    });
    return scores;
  }

  /** [{teamId,name,score}] for `teamIds`, score descending. */
  function rankTeams(teamIds, scores) {
    return teamIds.map(function (tid) {
      return { teamId: String(tid), name: teamNameOf(tid), score: scores[String(tid)] || 0 };
    }).sort(function (a, b) {
      if (b.score !== a.score) return b.score - a.score;
      return a.name.localeCompare(b.name);
    });
  }

  // ---------- view ----------
  function revealRailHtml(rows, opts) {
    var prev = opts.prevRanks || {};
    var hit = opts.hitTeamId ? String(opts.hitTeamId) : null;
    var body = rows.map(function (r, i) {
      var was = prev[r.teamId];
      // No delta against an empty board: before anything is scored the order is
      // alphabetical, so the first card would show every team moving.
      var delta = (was == null || !r.score || was === i + 1) ? 0 : was - (i + 1);
      var mark = '';
      if (opts.showDelta && delta) {
        mark = '<span class="dl' + (delta < 0 ? ' dn' : '') + '">' +
          (delta > 0 ? '▲' : '▼') + Math.abs(delta) + '</span>';
      } else if (r.teamId === hit && opts.gain) {
        mark = '<span class="dl">+' + opts.gain + '</span>';
      }
      return '<div class="sd-tm' + (String(r.teamId) === String(state.userTeamId) ? ' is-user' : '') +
          (r.teamId === hit ? ' is-hit' : '') + '">' +
        '<span class="rk">' + (i + 1) + '</span>' +
        '<span class="nm">' + Common.escapeHtml(r.name) + '</span>' +
        '<span class="sc">' + r.score + mark + '</span></div>';
    }).join('');
    return '<div class="sd-rail' + (opts.right ? ' is-right' : '') + '">' +
      '<div class="sd-rail-h"><span class="sd-rail-t">' + Common.escapeHtml(opts.title) + '</span>' +
        '<span class="sd-rail-s">' + Common.escapeHtml(opts.sub) + '</span></div>' +
      '<div class="sd-list">' + body + '</div></div>';
  }

  /**
   * The signed player's UNIFORMED portrait.
   *
   * Not headshotBoxHtml: that asks for `recruits/white/<image_id>.png`, the pre-signing
   * WHITE master. The uniform lives at `players/master/<player_id>.png`, which is what
   * the week-35 warm paint produces — so the card was requesting the one image the warm
   * pass never touches, and every recruit showed in a blank white jersey.
   *
   * An unpainted master 404s and the global paint-on-miss handler in api-config.js
   * paints then retries, so an out-of-region signing still resolves on its own.
   */
  function signedShotHtml(e) {
    var pid = e && e.player_id;
    if (!pid || typeof API_CONFIG === 'undefined' || typeof API_CONFIG.getPlayerImageUrl !== 'function') {
      return headshotBoxHtml({ imageId: e && e.image_id }, 'sd-shot-img');
    }
    return '<span class="sd-shot-img"><img src="' +
      Common.escapeHtml(API_CONFIG.getPlayerImageUrl(pid, { size: 'modal' })) +
      '" alt="" decoding="async"></span>';
  }

  function revealCardHtml(card) {
    if (!card) {
      return '<div class="sd-card-wrap"><div class="sd-card-wait">Signings begin…</div></div>';
    }
    var e = card.entry;
    var mine = isUserSigning(e);
    var funded = !!fundedIds()[String(e.recruit_id)];
    // Red is earned: only a recruit the user actually funded can be a loss. Everyone
    // else in the region is news, not defeat.
    var state_ = mine ? 'won' : (funded ? 'lost' : 'neutral');
    var team = teamNameOf(e.team_id, e.team_name);
    // The team's own branding IS the answer to the question the card asks, so the plate
    // carries it. Typography alone could not make a 9.5px team name compete with a
    // 430px portrait; a full-width banner does it without demoting the player's name.
    //
    // getTeamAssetPath (not a hand-built path): it resolves Team Builder overlays to
    // generated art, so a franchise with custom chrome gets its own banner. All 129
    // teams have one on disk, so there is no missing-asset case. banner_primary, not
    // banner_card — the latter is a ~400px picker derivative and this plate is ~860.
    var plate = '';
    if (typeof getTeamAssetPath === 'function') {
      plate = '<div class="sd-plate"><img src="' +
        Common.escapeHtml(getTeamAssetPath(team, 'banner_primary')) + '" alt="" decoding="async"></div>';
    }
    return '<div class="sd-card-wrap"><div class="sd-card is-' + state_ + '">' +
      '<div class="sd-card-lbl">' + (mine ? 'Signs with you' : 'Signs with') + '</div>' +
      plate +
      '<div class="sd-card-body">' +
        signedShotHtml(e) +
        '<div class="sd-card-id">' +
          '<div class="sd-card-nm">' + Common.escapeHtml(e.name || '--') + '</div>' +
      '<div class="sd-meta">' +
        '<div><small>Pos</small><b>' + Common.escapeHtml(e.pos || '--') + '</b></div>' +
        '<div><small>Year</small><b>' + Common.escapeHtml(Common.formatYearAbbrev(e.year)) + '</b></div>' +
        '<div><small>RT</small><b class="' + Spine.rtClassForYear(e.rt, e.year) + '">' +
          Common.formatRtWithPotential(e.rt, e.potential_rt_ratcheted) + '</b></div>' +
      '</div></div></div></div></div>';
  }

  /** One tile per funded recruit, in board order, resolving as his signing shows. */
  function revealTargetsHtml(cardIndex) {
    var funded = fundedIds();
    var ids = state.board.filter(function (id) { return funded[String(id)]; });
    Object.keys(funded).forEach(function (id) { if (ids.indexOf(id) === -1) ids.push(id); });
    if (!ids.length) return '';
    var shownIds = {};
    revealCards().slice(0, cardIndex).forEach(function (c) {
      shownIds[String(c.entry.recruit_id)] = c.entry;
    });
    var tiles = ids.map(function (id) {
      var r = state.byId[String(id)];
      var e = shownIds[String(id)];
      var cls = 'is-open';
      var status = (funded[String(id)].points || 0) + ' pts · unsigned';
      if (e) {
        if (isUserSigning(e)) { cls = 'is-won'; status = 'Signed with you'; }
        else { cls = 'is-lost'; status = 'Lost · ' + teamNameOf(e.team_id, e.team_name); }
      }
      return '<div class="sd-tg ' + cls + '">' +
        headshotBoxHtml(r, 'sd-tg-av') +
        '<span class="sd-tg-tx"><span class="sd-tg-nm">' +
          Common.escapeHtml((r && r.name) || (e && e.name) || '--') + '</span>' +
        '<span class="sd-tg-st">' + Common.escapeHtml(status) + '</span></span></div>';
    }).join('');
    return '<div class="sd-targets"><div class="sd-targets-h"><small>Your board</small>' +
      '<b>Funded Targets</b></div><div class="sd-tgts">' + tiles + '</div></div>';
  }

  /**
   * mm:ss left, from the cards actually remaining — never a hard-coded total.
   *
   * The card on screen counts down in real time: whole cards still ahead of it, plus
   * whatever is unspent of its own hold. Counting whole cards alone made the clock sit
   * still for five seconds and then jump.
   */
  function revealTimeLeft(cardIndex) {
    var whole = Math.max(0, revealCards().length - cardIndex);
    var ms = whole * REVEAL_HOLD_MS;
    if (whole > 0 && state.reveal.cardAt && !state.reveal.paused) {
      ms -= Math.max(0, Math.min(REVEAL_HOLD_MS, Date.now() - state.reveal.cardAt));
    }
    var secs = Math.max(0, Math.round(ms / 1000));
    return Math.floor(secs / 60) + ':' + String(secs % 60).padStart(2, '0');
  }

  /** End-of-run announcement. Centre of screen, one action, impossible to miss. */
  function revealDoneModalHtml(season) {
    return '<div class="sd-done" role="dialog" aria-modal="true" aria-label="Signing Day complete">' +
      '<div class="sd-done-box">' +
        '<div class="sd-done-t">Season ' + Common.escapeHtml(String(season || '1')) +
          ' Signing Day is Complete</div>' +
        '<button class="sd-done-cta" id="rv-done" type="button">Go To Locker Room</button>' +
      '</div></div>';
  }

  function revealHtml() {
    var cards = revealCards();
    var i = Math.min(state.reveal.index, cards.length);
    var current = cards[i - 1];
    var scores = revealScores(i);
    var regionIds = (state.conferences && state.conferences.region_team_ids) || [];
    var natIds = Object.keys((state.conferences && state.conferences.region_by_team_id) || {});
    // Scored teams only, same as the national rail. Listing all 16 at zero put them in
    // alphabetical order, which reads as a standing and gives the finishing order a
    // shape before a single recruit has signed. A team earns its row by signing someone
    // — which means the user's own team is absent until it does.
    var regionRows = rankTeams(regionIds, scores).filter(function (r) { return r.score > 0; });
    // Scored teams only. Ranking 128 teams that have all signed nobody puts 25 zeroes
    // in alphabetical order on screen, which says nothing — the table is supposed to
    // FILL as the league walks, so an unscored team has not earned a row yet.
    var natRows = rankTeams(natIds, scores)
      .filter(function (r) { return r.score > 0; })
      .slice(0, REVEAL_NATIONAL_TOP);
    var pct = cards.length ? (i / cards.length) * 100 : 0;
    var remaining = nextUserIndex(cards, i);
    var mineLeft = cards.slice(i).filter(function (c) { return isUserSigning(c.entry); }).length;

    // Nothing in the header once it is over: the end is announced by a modal
    // (revealDoneModalHtml) because a small Continue button in the top-right corner
    // was being missed at the end of a five-minute screen.
    // Nothing in the header once it is over: the end is announced by a modal
    // (revealDoneModalHtml) because a small Continue button in the top-right corner
    // was being missed at the end of a five-minute screen.
    //
    // Each control carries its keycap, and REVEAL_KEYS binds the same three keys — the
    // cap is a promise, so the shortcut has to actually exist.
    var controls = state.reveal.done ? '' :
      '<button class="sd-btn is-pause" id="rv-pause" type="button" ' +
        'aria-pressed="' + (state.reveal.paused ? 'true' : 'false') + '">' +
        '<span class="ic">' + (state.reveal.paused ? '\u25B6' : '\u2759\u2759') + '</span>' +
        (state.reveal.paused ? 'Resume' : 'Pause') + '<kbd>Space</kbd></button>' +
      '<button class="sd-btn is-next" id="rv-skip" type="button">' +
        '<span class="ic">\u25B6|</span>' +
        (remaining === -1 ? 'No more of yours' : 'My Next') + '<kbd>N</kbd></button>' +
      '<button class="sd-btn" id="rv-end" type="button">' +
        '<span class="ic">\u25B6\u25B6</span>End<kbd>E</kbd></button>';

    var season = state.season || '';
    return '<div class="sd">' +
      '<div class="sd-top">' +
        '<div class="sd-brand"><small>' +
          (season ? 'Season ' + Common.escapeHtml(String(season)) + ' · ' : '') +
          'Signing Day</small><b>Region ' + Common.escapeHtml(userRegion() || '--') +
          ' Signings</b></div>' +
        '<div class="sd-prog"><div class="sd-prog-n"><b>' + i + '</b>of ' + cards.length +
          ' · Region ' + Common.escapeHtml(userRegion() || '--') +
          ' · <b id="rv-clock">' + revealTimeLeft(i) + '</b>left</div>' +
          '<div class="sd-prog-bar"><i style="width:' + pct.toFixed(1) + '%"></i></div></div>' +
        '<div class="sd-ctl">' + controls + '</div>' +
      '</div>' +
      '<div class="sd-stage">' +
        revealRailHtml(regionRows, {
          title: 'Region ' + (userRegion() || ''), sub: 'Class score',
          hitTeamId: current && current.entry.team_id,
          gain: current ? current.entry.rt : 0,
        }) +
        revealCardHtml(current) +
        revealRailHtml(natRows, {
          title: 'Top ' + REVEAL_NATIONAL_TOP + ' Classes', sub: 'National', right: true,
          showDelta: true, prevRanks: state.reveal.prevNatRanks || {},
        }) +
      '</div>' +
      revealTargetsHtml(i) +
      (state.reveal.done ? revealDoneModalHtml(season) : '') +
      '</div>';
  }

  // ---------- controls ----------
  /** Index of the next card that is the user's own signing, or -1 when none remain. */
  function nextUserIndex(cards, from) {
    for (var i = from; i < cards.length; i++) { if (isUserSigning(cards[i].entry)) return i; }
    return -1;
  }

  function renderReveal() {
    var host = document.getElementById('hub-reveal');
    if (!host) return;
    host.innerHTML = revealHtml();
    var skip = host.querySelector('#rv-skip');
    if (skip) skip.addEventListener('click', function () {
      var cards = revealCards();
      var next = nextUserIndex(cards, state.reveal.index);
      revealTo(next === -1 ? cards.length : next + 1);
    });
    var end = host.querySelector('#rv-end');
    if (end) end.addEventListener('click', function () { revealTo(revealCards().length); });
    var pause = host.querySelector('#rv-pause');
    if (pause) pause.addEventListener('click', function () { toggleRevealPause(); });
    var done = host.querySelector('#rv-done');
    if (done) done.addEventListener('click', function () { finishReveal(); });
  }

  // Test seam: lets a spec force extra renders to prove the seen-stamp fires once.
  window.__hubRenderReveal = function () { renderReveal(); };

  function revealTo(index) {
    var cards = revealCards();
    // Snapshot the national order BEFORE the move, so the next render can show which
    // way each team travelled. Ranks, not scores — a team can gain and still fall.
    var before = rankTeams(
      Object.keys((state.conferences && state.conferences.region_by_team_id) || {}),
      revealScores(state.reveal.index)
    ).slice(0, REVEAL_NATIONAL_TOP);
    var prev = {};
    before.forEach(function (r, i) { prev[r.teamId] = i + 1; });
    state.reveal.prevNatRanks = prev;

    state.reveal.index = Math.max(0, Math.min(index, cards.length));
    state.reveal.cardAt = Date.now();          // this card's hold starts now
    if (state.reveal.index >= cards.length) {
      state.reveal.done = true;
      stopReveal();
      markRevealSeen();
    }
    renderReveal();
  }

  function revealTick() { revealTo(state.reveal.index + 1); }

  function startRevealTimer() {
    stopReveal();
    state.reveal.cardAt = Date.now();
    state.reveal.timer = setInterval(revealTick, REVEAL_HOLD_MS);
    // The clock gets its own 1s interval. Driven off the card interval it moved in 5s
    // steps, which reads as a stalled timer rather than a countdown. Only the clock
    // text is repainted, so the card and both rails stay untouched.
    stopRevealClock();
    state.reveal.clock = setInterval(paintRevealClock, 1000);
  }

  /**
   * Space / N / E, matching the keycaps printed on the controls.
   *
   * Bound on the document while the stage is up and removed when it closes — the
   * reveal owns the screen, so it owns the keyboard. Ignored once the run is done so
   * a stray keypress cannot act on a finished screen, and ignored while focus is in a
   * field in case one ever appears here.
   */
  function revealKeyHandler(e) {
    if (!document.getElementById('hub-reveal') || state.reveal.done) return;
    var t = e.target;
    if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return;
    var k = e.key;
    if (k === ' ' || k === 'Spacebar') { e.preventDefault(); toggleRevealPause(); return; }
    if (k === 'n' || k === 'N') {
      e.preventDefault();
      var cards = revealCards();
      var next = nextUserIndex(cards, state.reveal.index);
      revealTo(next === -1 ? cards.length : next + 1);
      return;
    }
    if (k === 'e' || k === 'E') { e.preventDefault(); revealTo(revealCards().length); }
  }

  function bindRevealKeys(on) {
    if (on) document.addEventListener('keydown', revealKeyHandler);
    else document.removeEventListener('keydown', revealKeyHandler);
  }

  function stopRevealClock() {
    if (state.reveal.clock) { clearInterval(state.reveal.clock); state.reveal.clock = null; }
  }

  /** Repaint just the countdown — no re-render, so nothing else moves. */
  function paintRevealClock() {
    var el = document.getElementById('rv-clock');
    if (el) el.textContent = revealTimeLeft(state.reveal.index);
  }

  function toggleRevealPause() {
    if (state.reveal.done) return;
    state.reveal.paused = !state.reveal.paused;
    if (state.reveal.paused) { stopReveal(); } else { startRevealTimer(); }
    renderReveal();
  }

  function stopReveal() {
    if (state.reveal.timer) { clearInterval(state.reveal.timer); state.reveal.timer = null; }
    stopRevealClock();
  }

  /** Season-stamped so a refresh after submitting does not replay it. */
  function markRevealSeen() {
    if (state.reveal.seenSent) return;
    state.reveal.seenSent = true;
    Common.fetchJSON(API_CONFIG.buildUrl('/franchise/week-35-reveal-seen'), {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ franchise_id: context.franchiseId })
    }).catch(function (err) { console.error('[REVEAL] seen stamp failed', err); });
  }

  function finishReveal() {
    stopReveal();
    bindRevealKeys(false);
    revealMusic(false);
    var host = document.getElementById('hub-reveal');
    if (host) host.remove();
    // The confirm modal now comes BEFORE the run, so Continue leaves for the FCC.
    window.location.href = Common.buildFccUrl(context);
  }

  // How many masters to force-paint before the stage opens. The background warm on the
  // server paints the whole region, but it starts cold and each master costs ~1.2s of
  // CPU plus R2 round trips — so the playhead (one card per 5s) outran it and the first
  // ~20 cards showed a blank white jersey. Painting this many up front puts the warm
  // that far ahead, and it stays ahead for the rest of the run.
  var REVEAL_PREPAINT = 15;

  /**
   * Force the first N cards' uniformed masters, then resolve.
   *
   * /player-image/ensure paints synchronously and returns `exists` when it is already
   * there, so a second visit is nearly free. Failures resolve too: a master that cannot
   * be painted must not hold the screen shut — the card falls back to paint-on-miss and
   * then the generic frame, exactly as it does today.
   */
  function prepaintLead(cards) {
    if (typeof API_CONFIG === 'undefined' || typeof API_CONFIG.ensurePlayerImage !== 'function') {
      return Promise.resolve();
    }
    var ids = [];
    for (var i = 0; i < cards.length && ids.length < REVEAL_PREPAINT; i++) {
      var pid = cards[i].entry && cards[i].entry.player_id;
      if (pid) ids.push(String(pid));
    }
    if (!ids.length) return Promise.resolve();
    return Promise.all(ids.map(function (pid) {
      return API_CONFIG.ensurePlayerImage(context.franchiseId, pid).catch(function () { return null; });
    }));
  }

  function prepHostHtml() {
    return '<div class="sd sd-prep"><div class="sd-prep-box">' +
      '<div class="sd-prep-t">Prepping Signing Day</div>' +
      '<div class="sd-prep-bar"><i></i></div></div></div>';
  }

  function startReveal() {
    // Reset the caches too: buckets and cards are derived from week_35_results, which
    // runRecruiting() has just replaced.
    state.reveal = {
      index: 0, done: false, timer: null, seenSent: false, paused: false,
      buckets: null, cards: null, prevNatRanks: {},
    };
    // Nothing to reveal: stamp it seen and go, rather than opening an empty screen.
    if (!revealCards().length) {
      markRevealSeen(); window.location.href = Common.buildFccUrl(context); return;
    }
    revealMusic(true);
    var host = document.createElement('div');
    host.className = 'rvhost';
    host.id = 'hub-reveal';
    document.body.appendChild(host);
    // Hold on "Prepping Signing Day" until the lead is painted, so the opening cards
    // arrive in team colours rather than blank white.
    host.innerHTML = prepHostHtml();
    bindRevealKeys(true);
    prepaintLead(revealCards()).then(function () {
      if (!document.getElementById('hub-reveal')) return;   // player left during the prep
      renderReveal();
      startRevealTimer();
    });
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
      // Orders are SAVED, not run. The modal is the confirm step: Back to Orders keeps
      // editing, the FCC's Run Recruiting Day commits.
      clearDraft();
      showSubmitSummary(summaryRows);
    }).catch(function (err) {
      console.error(err); showToast('Submit failed', String(err && err.message || err), false);
      if (btn) { btn.disabled = false; btn.textContent = 'Submit Orders'; }
    });
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

  /**
   * League signing list (week 36). No playback — the drama happened on Signing Day; this
   * is the durable record you come back to.
   *
   * Grouped by conference then team, ordered user's conference -> sister conference ->
   * 1..16 ascending with those two removed so neither repeats. The order comes from the
   * server (`conferences.order`); "same region, other conference" has one definition and
   * the client does not re-derive it.
   *
   * Walk-ons are excluded here as everywhere before rollover — they are roster backfill,
   * not signings, and their first reveal is next season's Walk-On Welcome.
   */
  function leagueSigningGroups() {
    var conf = state.conferences || {};
    var byTeam = conf.by_team_id || {};
    var order = conf.order || [];
    var buckets = {};
    (state.week35Results.signed_players || []).forEach(function (e) {
      if (!e || e.walk_on) return;
      var c = Number(byTeam[String(e.team_id)]) || 0;
      if (!c) return;
      (buckets[c] = buckets[c] || {});
      var tid = String(e.team_id);
      (buckets[c][tid] = buckets[c][tid] || []).push(e);
    });
    return order.filter(function (c) { return buckets[c]; }).map(function (c) {
      var teams = Object.keys(buckets[c]).map(function (tid) {
        return {
          teamId: tid,
          name: (state.teamNameMap && state.teamNameMap[tid]) || (buckets[c][tid][0] || {}).team_name || '',
          isUser: String(tid) === String(state.userTeamId),
          signings: buckets[c][tid].sort(function (a, b) {
            return (b.rt != null ? b.rt : -1) - (a.rt != null ? a.rt : -1);
          })
        };
      }).sort(function (a, b) { return a.name.localeCompare(b.name); });
      return {
        conference: c,
        label: conferenceLabel(c),
        isUser: Number(c) === Number(conf.user_conference),
        isSister: Number(c) === Number(conf.sister_conference),
        teams: teams
      };
    });
  }

  /**
   * Region letter + the conference's OWN number: A1 A2 B3 B4 C5 C6 … H15 H16.
   *
   * Not letter + 1|2. That printed A1/A2, B1/B2, C1/C2 …, so every region had a "1" and
   * a "2" and the number said nothing about WHICH conference — B2 and D2 are different
   * conferences with the same suffix. The number here is the real conference id, so the
   * label is unique across the league and reversible.
   */
  function conferenceLabel(c) {
    var n = Number(c);
    if (!isFinite(n) || n < 1 || n > 16) return '';
    return String.fromCharCode(65 + Math.floor((n - 1) / 2)) + n;
  }

  function leagueRowHtml(e) {
    return '<div class="lsrow">' +
      '<span class="lsnm">' + Common.escapeHtml(e.name || '--') + '</span>' +
      '<span class="lspos">' + Common.escapeHtml(e.pos || '--') + '</span>' +
      '<span class="lsyr">' + Common.escapeHtml(Common.formatYearAbbrev(e.year)) + '</span>' +
      '<span class="lsrt ' + Spine.rtClassForYear(e.rt, e.year) + '" ' +
        'data-tooltip="current/potential" title="current/potential">' +
        Common.formatRtWithPotential(e.rt, e.potential_rt_ratcheted) + '</span>' +
      '</div>';
  }

  function finalSigningsHtml() {
    var groups = leagueSigningGroups();
    if (!groups.length) {
      return '<div class="rstage"><div class="rempty">No signings to report yet.</div></div>';
    }
    var body = groups.map(function (g) {
      var tag = g.isUser ? '<span class="lstag you">Your conference</span>'
        : g.isSister ? '<span class="lstag sis">Sister conference</span>' : '';
      var teams = g.teams.map(function (t) {
        return '<div class="lsteam' + (t.isUser ? ' is-user' : '') + '">' +
          '<div class="lsteam-h">' + Common.escapeHtml(t.name) +
            '<span class="lsn">' + t.signings.length + '</span></div>' +
          t.signings.map(leagueRowHtml).join('') + '</div>';
      }).join('');
      return '<section class="lsconf' + (g.isUser ? ' is-user' : '') + '">' +
        '<div class="lsconf-h"><span class="lsconf-t">Conference ' + g.label + '</span>' + tag + '</div>' +
        '<div class="lsconf-teams">' + teams + '</div></section>';
    }).join('');
    return '<div class="rstage">' +
      '<div class="rhead"><div class="rhead-t">Signing Day Results</div>' +
        '<div class="rhead-s">Every signing in the league, by conference.</div></div>' +
      '<div class="lswrap">' + body + '</div></div>';
  }

  // The week-36 screen is a league LIST now, not a playback — the reveal moved to
  // Signing Day itself, so its Next / Auto-play / Skip all controls and the
  // per-row reveal helpers went with it.
  function renderSignings() {
    var host = document.getElementById('hub-signings'); if (!host) return;
    host.innerHTML = finalSigningsHtml();
    if (typeof window.initAttributeTooltips === 'function') window.initAttributeTooltips(host, ['div']);
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

  /**
   * Season-panel visit log: every invite week 20-26 in ascending order.
   *
   * A week with no recruit is an invite the player still has — shown as an open row
   * rather than omitted, so the remaining count is readable at a glance rather than
   * arithmetic. Each visited week carries the recruit's CURRENT lean, not a snapshot,
   * so the log answers "where does that visit stand now".
   */
  /**
   * The invite season as a seven-square calendar — one square per week 20-26.
   *
   * It replaces the Season-panel list. A list of seven rows makes the season read as
   * history; seven squares in a row make it read as a BUDGET, which is what it is: seven
   * invites, some spent, some still to come. The spent ones carry the recruit they
   * bought, so the record and the remaining count are the same picture.
   *
   * Four states, and a past week that produced nothing is NOT the same as a week still
   * to come — one is spent, the other is available:
   *
   *   filled   — a recruit visited: headshot, name, RT, year, current leans
   *   pending  — this week, not yet resolved (visits are assigned at run-training)
   *   missed   — a week that ran and gave no visit (empty board, or lost the draw)
   *   upcoming — a week not yet reached
   */
  function visitWeekTileHtml(v) {
    var wk = Number(v.week);
    var label = '<span class="vwk-wk">Wk ' + wk + '</span>';

    if (!v.recruit_id) {
      var state_ = wk > state.week ? 'upcoming' : wk === state.week ? 'pending' : 'missed';
      var copy = { upcoming: 'Upcoming', pending: 'This week', missed: 'No visit' }[state_];
      var sub = { upcoming: 'Invite open', pending: 'Set at training', missed: 'Invite spent' }[state_];
      return '<div class="vwk is-' + state_ + '">' +
        '<div class="vwk-hd">' + label + '</div>' +
        '<div class="vwk-empty"><span class="vwk-mark" aria-hidden="true"></span>' +
          '<span class="vwk-state">' + copy + '</span>' +
          '<span class="vwk-note">' + sub + '</span></div>' +
        '</div>';
    }

    // The pool is the source for everything the visit payload does not carry (headshot,
    // RT, year). Every visited recruit is still in it during weeks 20-26, but the
    // fallback keeps a name and a lean on screen if one ever is not.
    var r = state.byId[String(v.recruit_id)];
    var model = r ? r.leanModel
      : Spine.Lean.fromBackend({ Lean: v.lean }, { userTeamId: state.userTeamId, teamNameMap: state.teamNameMap });
    var name = Common.escapeHtml(v.name || (r && r.name) || '--');
    var rt = r ? Common.formatRtWithPotential(r.rt, r.potentialRt) : '--';
    var rtCls = r ? Spine.rtClassForYear(r.rt, r.year) : '';
    var year = r ? Common.escapeHtml(r.yearDisplay) : '--';
    var pos = r ? Common.escapeHtml(r.pos) : '--';
    // ONE header row above the image: week left, position centre, RT right. The week and
    // the spec line were two rows of small type stacked a few pixels apart, which read as
    // one crowded four-item header rather than a stamp plus a spec.
    return '<div class="vwk is-filled">' +
      '<div class="vwk-hd">' + label +
        '<span class="vwk-pos">' + pos + '</span>' +
        '<span class="vwk-rt ' + rtCls + '">' + rt + '</span></div>' +
      headshotBoxHtml(r, 'vwk-av') +
      // Name and year are ONE unit, centred as a pair. The name is the part that
      // truncates and the year holds its size, so a long name clips rather than
      // shunting the year off-centre or out of the tile.
      '<div class="vwk-nm"><span class="vwk-nmtx">' + name + '</span>' +
        '<span class="vwk-yr">' + year + '</span></div>' +
      '<div class="vwk-lean">' + Spine.Lean.ladderHtml(model) + '</div>' +
      '</div>';
  }

  function visitCalendarHtml() {
    var hist = state.visitHistory || [];
    if (!hist.length) return '';
    return '<section class="vcal">' +
      // No counter: the seven squares ARE the count, and a number beside them restated
      // what the row already shows.
      '<div class="vcal-head"><div class="vcal-title">Invite Visits</div></div>' +
      '<div class="vcal-grid">' + hist.map(visitWeekTileHtml).join('') + '</div>' +
      '</section>';
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
      // Single column in every phase. The invite phase used to carry a 306px rail
      // (This week / Roster capacity) beside the board, which squeezed the pool table
      // and pushed its Lean and Watch columns out of view — the two columns the pool
      // exists to be scanned for.
      '<div class="spine-body no-dock" style="padding-top:14px">' +
        '<div style="min-width:0;display:flex;flex-direction:column;gap:14px">' +
          (state.phase === 'passive' ? storyHtml() : '') +
          // Invite phase: the seven-week visit calendar sits ABOVE the board — what the
          // season has bought, then what is still ranked to buy — with the pool beneath
          // as the add source.
          (hasDock() ? '<div id="hub-visits"></div><div id="hub-board"></div>' : '') +
          '<div class="pool-wrap"><div id="hub-pool"></div></div></div></div>';
    root.innerHTML =
      '<div class="spine-topbar"><span class="spine-h">Recruiting <b>Hub</b></span><span id="hub-anchor-mount"></span></div>' +
      '<div class="spine-topbar" style="padding-top:12px;padding-bottom:0"><div style="flex:1" id="hub-phase"></div></div>' + body;
    var phaseHost = document.getElementById('hub-phase');
    phaseHost.innerHTML = Spine.Phase.stripHtml({ phase: state.phase, week: state.week,
      inviteSent: Math.max(0, INVITE_WEEKS.filter(function (w) { return w < state.week; }).length),
      points: remaining() });
    Spine.Phase.bind(phaseHost);
    var mount = document.getElementById('hub-anchor-mount');
    // Signing Day pairs the pool anchor with a My Orders view: the same two things the
    // screen is about, switched from one place. Outside Signing Day there is no orders
    // view to switch to, so the anchor stands alone as before.
    mount.innerHTML = Spine.Anchor.html()
      + (signing
        ? '<button class="hub-anchor hub-anchor--orders' + (state.sView === 'orders' ? ' is-on' : '') +
          '" id="hub-orders-toggle" type="button" aria-pressed="' + (state.sView === 'orders' ? 'true' : 'false') +
          '"><span class="ic">◧</span> My Orders</button>'
        : '');
    Spine.Anchor.bind(mount.querySelector('.hub-anchor'), {
      poolSelector: signing ? '.spool' : results ? '.signings-wrap' : '.pool-wrap',
      onDismiss: null   // weekly-results panel is persistent now; the anchor only scrolls to the pool
    });
    if (signing) {
      // The pool anchor is also the way back: pressing it leaves the orders-only view.
      var poolBtn = mount.querySelector('.hub-anchor:not(.hub-anchor--orders)');
      if (poolBtn) poolBtn.addEventListener('click', function () { setSignView('pool'); });
      var ordersBtn = document.getElementById('hub-orders-toggle');
      if (ordersBtn) ordersBtn.addEventListener('click', function () {
        setSignView(state.sView === 'orders' ? 'pool' : 'orders');
      });
    }
    var visits = document.getElementById('hub-visits');
    if (visits) visits.innerHTML = visitCalendarHtml();
    if (signing) { document.getElementById('hub-sign').innerHTML = signBoardHtml(); applySignView(); bindSignBoard(); }
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
        state.teamNameMap = teamNameMap;
        state.conferences = data.conferences || null;
        state.season = data.season || null;
        state.revealSeen = !!data.week_35_reveal_seen;
        state.seedModalSeen = !!data.invite_seed_modal_seen;
        state.visitHistory = data.visit_history || [];
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
        // Pre-populate the invite board — CLIENT-SIDE STATE ONLY.
        //
        // HARD RULE: this must never persist. has_saved_board derives from
        // _team_order_list(ftd["Recruits"]), and both the week-20 gate and the server
        // guard at franchise_routes:11966 key off it. Writing Recruits here would flip
        // the gate open before the player had saved anything — seedAlloc()'s mistake
        // (pre-committing the player to a choice they never made) in a new location.
        // Recruits is written by save_recruiting_orders and nowhere else.
        //
        // Only seeds when nothing is saved yet, so it can never reorder or overwrite a
        // board the player built. In practice that means week 20: the board persists in
        // FTD across weeks 20-26, so once it is submitted it carries forward and this
        // never fires again until the season rolls over.
        state.boardSeeded = false;
        if (!state.board.length) state.board = seedBoard();
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
        // LAST, so it lays over the server copy, the watchlist seed and the restored
        // week-35 entries alike — an unsubmitted edit is newer than all three.
        restoreDraft();
        renderShell();
        // AFTER restoreDraft: a returning player whose draft refilled the board is not
        // looking at a seed, and must not be told they are.
        maybeShowSeedModal();
        maybeAutoRun();
      })
      .catch(function (err) { console.error(err); if (root) root.innerHTML = '<div class="hub-error">Failed to load recruits.</div>'; });
  }

  init();
})();
