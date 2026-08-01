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
  var SORTABLE = { name: 'text', pos: 'text', year: 'text', height: 'num', weight: 'num', rt: 'num' };
  var INVITE_WEEKS = [20, 21, 22, 23, 24, 25, 26];
  var POS_ORDER = ['PG', 'SG', 'SF', 'PF', 'C'];
  var MAX_BOARD = 20;

  var context = Common.getQueryContext();
  var state = {
    week: 1, phase: 'passive', userTeamId: null,
    recruits: [], byId: {}, newLeanIds: new Set(),
    board: [],                       // ordered recruit ids (invite phase)
    search: '', region: 'all', mineOnly: false,
    sort: { key: 'rt', dir: 'desc' }, collapsed: {},
    drag: { from: null, over: null },
    // Signing Day (wk 35)
    alloc: {},                       // { recruitId: {points, promise} }
    sTab: 'mine', sRegion: 'all', sSearch: '', week35Ran: false, flashId: null,
    // Results (D4)
    currentResultsWeek: null, weeklyDismissed: false, visitTree: null,
    week35Results: {}, signFilter: 'all'
  };
  var SIGN = { TOTAL: 50, MAX_PER: 20, PROMISE_W: 18 };

  function boardActive() { return state.phase === 'invite'; }
  function attrClass(v) { return v >= 65 ? 'attr-hi' : v >= 40 ? 'attr-mid' : v >= 20 ? 'attr-lo' : 'attr-zero'; }
  function regionOf(rec) { var v = rec && rec.homeRegion ? String(rec.homeRegion).trim().toUpperCase() : ''; return v ? v.charAt(0) : ''; }
  function colspan() { return (boardActive() ? 1 : 0) + 5 + ATTR_KEYS.length + 2; }

  var CHEVRON = '<svg class="region-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M6 9l6 6 6-6"></path></svg>';
  var ARROW_UP = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6"><path d="M7 17L17 7M9 7h8v8"></path></svg>';
  var INFO = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="12" cy="12" r="9"></circle><path d="M12 11v5M12 7.5v.5"></path></svg>';
  var CHECK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M20 6L9 17l-5-5"></path></svg>';

  // Only the invite phase uses the standard pool+dock layout. Signing (day) and Results
  // are their own full-width bodies, handled in renderShell.
  function hasDock() { return boardActive(); }

  // ===================== POOL =====================
  function filteredRecruits() {
    var q = state.search.trim().toLowerCase();
    return state.recruits.filter(function (r) {
      if (state.region !== 'all' && regionOf(r) !== state.region) return false;
      if (state.mineOnly && !r.leansToUser) return false;
      if (q && String(r.name).toLowerCase().indexOf(q) === -1) return false;
      return true;
    });
  }
  function sortValue(r, key) {
    switch (key) {
      case 'name': return r.name; case 'pos': return r.pos;
      case 'year': return Common.getYearSortValue(r.year);
      case 'height': return r.heightRaw; case 'weight': return r.weight != null ? r.weight : -1;
      case 'rt': return r.rt != null ? r.rt : -1; default: return r[key];
    }
  }
  function sortRecs(recs) {
    var key = state.sort.key, dir = state.sort.dir, num = SORTABLE[key] === 'num' || key === 'year';
    return recs.slice().sort(function (a, b) {
      var av = sortValue(a, key), bv = sortValue(b, key), c;
      if (num) c = dir === 'asc' ? av - bv : bv - av;
      else c = dir === 'asc' ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
      return c || (b.rt != null ? b.rt : -1) - (a.rt != null ? a.rt : -1);
    });
  }
  function arrow(key) { return state.sort.key === key ? '<span class="arrow">' + (state.sort.dir === 'asc' ? '▲' : '▼') + '</span>' : ''; }
  function th(key, label, cls) { return '<th class="' + (cls || 'num') + '" data-sortkey="' + key + '">' + label + arrow(key) + '</th>'; }

  function headHtml() {
    var attrTh = ATTR_KEYS.map(function (k, i) { return '<th class="num attr-col' + (i === 0 ? ' attr-sep' : '') + '">' + k + '</th>'; }).join('');
    return '<thead><tr>' +
      (boardActive() ? '<th class="act"></th>' : '') +
      th('name', 'Name', 'name-col') + th('pos', 'Pos') + th('year', 'Yr') + th('height', 'Ht') + th('weight', 'Wt') +
      attrTh + '<th class="num attr-sep" data-sortkey="rt">RT' + arrow('rt') + '</th>' +
      '<th class="lean-col">Leans / Your Standing</th></tr></thead>';
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
    var attrs = ATTR_KEYS.map(function (k, i) { var v = r.attrs[k]; return '<td class="attr ' + attrClass(v) + (i === 0 ? ' attr-sep' : '') + '">' + v + '</td>'; }).join('');
    return '<tr class="rec ' + rowCls + '">' + actCell +
      '<td class="name-col"><div class="pc-name"><span class="nm">' + Common.recruitNameLinkHtml(r.recruitId, context.franchiseId, r.name) + '</span>' + flags + '</div>' +
        '<div class="pc-arch">' + Common.escapeHtml(r.archetype) + '</div></td>' +
      '<td class="pos">' + Common.escapeHtml(r.pos) + '</td>' +
      '<td class="year">' + Common.escapeHtml(r.yearDisplay) + '</td>' +
      '<td class="num">' + Common.escapeHtml(r.height) + '</td>' +
      '<td class="num">' + (r.weight != null ? r.weight : '--') + '</td>' + attrs +
      '<td class="rt attr-sep"><span class="v ' + Spine.rtClassForYear(r.rt, r.year) + '">' + (r.rt != null ? r.rt : '--') + '</span></td>' +
      '<td class="lean-col">' + Spine.Lean.ladderHtml(r.leanModel) + '</td></tr>';
  }
  function poolBodyHtml() {
    var recs = sortRecs(filteredRecruits()), byRegion = {};
    recs.forEach(function (r) { var g = regionOf(r); (byRegion[g] = byRegion[g] || []).push(r); });
    var rows = '', cs = colspan();
    REGION_ORDER.forEach(function (region) {
      var list = byRegion[region]; if (!list || !list.length) return;
      var collapsed = !!state.collapsed[region];
      var mineCount = list.filter(function (r) { return r.leansToUser; }).length;
      rows += '<tr class="region-row"><td colspan="' + cs + '">' +
        '<button class="region-bar' + (collapsed ? ' region-collapsed' : '') + '" data-region="' + region + '" type="button">' +
          CHEVRON + '<span class="region-letter">' + region + '</span><span class="region-name"></span>' +
          '<span class="region-stat"><b>' + list.length + '</b> recruits</span>' +
          (mineCount > 0 ? '<span class="region-mine"><span class="d"></span>' + mineCount + ' leaning to you</span>' : '') +
        '</button></td></tr>';
      if (!collapsed) rows += list.map(rowHtml).join('');
    });
    if (!rows) rows = '<tr><td colspan="' + cs + '" style="padding:26px;text-align:center;color:var(--muted-3)">No recruits match your filters.</td></tr>';
    return rows;
  }
  function toolbarHtml(total, shown) {
    var chips = '<button class="chip' + (state.region === 'all' ? ' is-active' : '') + '" data-region="all">All</button>' +
      REGION_ORDER.map(function (r) { return '<button class="chip' + (state.region === r ? ' is-active' : '') + '" data-region="' + r + '">' + r + '</button>'; }).join('');
    return '<div class="pool-toolbar"><div class="ptb-group"><span class="ptb-label">Find</span>' +
      '<input class="ptb-search" id="pool-search" placeholder="Name…" value="' + Common.escapeHtml(state.search) + '"></div>' +
      '<div class="ptb-group"><span class="ptb-label">Region</span>' + chips + '</div>' +
      '<button class="chip mine' + (state.mineOnly ? ' is-active' : '') + '" id="pool-mine">◗ Leaning to me</button>' +
      '<span class="ptb-count">Showing <strong>' + shown + '</strong> of ' + total + '</span></div>';
  }
  function renderPool() {
    var host = document.getElementById('hub-pool'); if (!host) return;
    host.innerHTML = toolbarHtml(state.recruits.length, filteredRecruits().length) +
      '<div class="pool-scroll"><table class="pool' + (hasDock() ? ' condensed' : '') + '">' + headHtml() + '<tbody>' + poolBodyHtml() + '</tbody></table></div>';
    bindPool(host);
    if (typeof window.initAttributeTooltips === 'function') window.initAttributeTooltips(host, ['th', 'td']);
  }
  function bindPool(host) {
    var search = host.querySelector('#pool-search');
    if (search) search.addEventListener('input', function () { state.search = this.value; renderPoolBodyOnly(); updateCount(); });
    host.querySelectorAll('.pool-toolbar .chip[data-region]').forEach(function (b) { b.addEventListener('click', function () { state.region = this.dataset.region; renderPool(); }); });
    var mine = host.querySelector('#pool-mine'); if (mine) mine.addEventListener('click', function () { state.mineOnly = !state.mineOnly; renderPool(); });
    host.querySelectorAll('th[data-sortkey]').forEach(function (thEl) {
      if (!SORTABLE[thEl.dataset.sortkey]) return;
      thEl.style.cursor = 'pointer';
      thEl.addEventListener('click', function () {
        var k = this.dataset.sortkey;
        if (state.sort.key === k) state.sort.dir = state.sort.dir === 'asc' ? 'desc' : 'asc';
        else state.sort = { key: k, dir: (k === 'name' || k === 'pos' || k === 'year') ? 'asc' : 'desc' };
        renderPool();
      });
    });
    bindPoolBodyHandlers(host);
  }
  function bindPoolBodyHandlers(host) {
    host.querySelectorAll('.region-bar').forEach(function (b) {
      b.addEventListener('click', function () { state.collapsed[this.dataset.region] = !state.collapsed[this.dataset.region]; renderPoolBodyOnly(); });
    });
    host.querySelectorAll('.pool-add, .pool-rankbadge').forEach(function (b) {
      b.addEventListener('click', function (e) { e.stopPropagation(); toggleBoard(this.dataset.id); });
    });
  }
  function renderPoolBodyOnly() {
    var tbody = document.querySelector('#hub-pool tbody'); if (tbody) tbody.innerHTML = poolBodyHtml();
    bindPoolBodyHandlers(document.getElementById('hub-pool'));
    if (typeof window.initAttributeTooltips === 'function') window.initAttributeTooltips(document.getElementById('hub-pool'), ['td']);
  }
  function updateCount() { var el = document.querySelector('#hub-pool .ptb-count strong'); if (el) el.textContent = filteredRecruits().length; }

  // ===================== BOARD ops =====================
  function toggleBoard(id) {
    var i = state.board.indexOf(id);
    if (i !== -1) state.board.splice(i, 1);
    else if (state.board.length < MAX_BOARD) state.board.push(id);
    renderBoardDependent();
  }
  function removeFromBoard(id) { var i = state.board.indexOf(id); if (i !== -1) { state.board.splice(i, 1); renderBoardDependent(); } }
  function reorderBoard(from, to) {
    if (from == null || from === to) return;
    var m = state.board.splice(from, 1)[0]; state.board.splice(to, 0, m); renderBoardDependent();
  }
  function renderBoardDependent() { renderPoolBodyOnly(); renderDock(); }

  // ===================== INVITE DOCK =====================
  function slotHtml(id, index) {
    var r = state.byId[id]; if (!r) return '';
    var stand = r.yourRank === 1 ? '<span class="islot-stand you1"><svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="6"></circle></svg>#1</span>'
      : r.yourRank > 1 ? '<span class="islot-stand list">#' + r.yourRank + '</span>' : '';
    var claimed = (r.leanModel.leans || []).filter(function (s) { return !s.open; }).length;
    var dots = [0, 1, 2].map(function (i) { return '<i class="' + (i < claimed ? 'on' : '') + '"></i>'; }).join('');
    return '<div class="islot queued" draggable="true" data-index="' + index + '">' +
      '<span class="islot-rank">' + (index + 1) + '</span>' +
      '<span class="islot-grip"><span></span><span></span><span></span><span></span><span></span><span></span></span>' +
      '<div class="islot-body"><div class="islot-name"><span class="nm">' + Common.escapeHtml(r.name) + '</span>' + stand + '</div>' +
        '<div class="islot-meta"><span class="islot-pos">' + Common.escapeHtml(r.pos) + '</span><span>Rgn ' + regionOf(r) + '</span>' +
        '<span class="islot-rt ' + Spine.rtClassForYear(r.rt, r.year) + '">' + (r.rt != null ? r.rt : '--') + ' RT</span></div></div>' +
      '<div class="islot-right"><span class="islot-lists c' + claimed + '" title="' + claimed + ' of 3 lean slots claimed">' +
        '<span class="dots">' + dots + '</span><span class="cap">' + (claimed === 0 ? 'Open list' : claimed + '/3 leans') + '</span></span></div>' +
      '<button class="islot-remove" data-id="' + id + '" title="Remove" type="button">×</button></div>';
  }
  function inviteDockHtml() {
    var recs = state.board.map(function (id) { return state.byId[id]; }).filter(Boolean);
    var leaning = recs.filter(function (r) { return r.leansToUser; }).length;
    var weeks = INVITE_WEEKS.map(function (w) {
      var cls = w < state.week ? 'sent' : w === state.week ? 'now' : 'future';
      return '<div class="iweek ' + cls + '"><span class="pip"></span><span class="wl">W' + w + '</span></div>';
    }).join('');
    var breakdown = POS_ORDER.map(function (p) {
      var n = recs.filter(function (r) { return r.pos === p; }).length;
      return '<span class="ibreak' + (n === 0 ? ' zero' : '') + '"><span class="bn">' + n + '</span><span class="bl">' + p + '</span></span>';
    }).join('');
    var needMore = Math.max(0, INVITE_WEEKS.length - state.board.length);
    var invitesLeft = INVITE_WEEKS.filter(function (w) { return w >= state.week; }).length;
    var list = state.board.length === 0
      ? '<div class="idock-list"><div class="idock-empty"><div class="t1">No recruits ranked</div><div class="t2">Click <strong>+</strong> on a recruit in the pool to add them. Each week the hub invites your top-ranked recruit.</div></div></div>'
      : '<div class="idock-list"><div class="idock-group-lbl">Priority order · drag to rank</div>' +
          state.board.map(function (id, i) { return slotHtml(id, i); }).join('') + '</div>';
    var nudge = needMore > 0
      ? '<div class="idock-nudge">' + INFO + '<span><b>' + invitesLeft + ' invites left</b> this season — rank ' + needMore + ' more so every week has a target.</span></div>'
      : '';
    return '<aside class="idock">' +
      '<div class="idock-head"><div class="idock-titlerow">' +
        '<div class="idock-title"><small>Invite Season · Wk ' + state.week + '</small>Invite Board</div>' +
        '<div class="idock-count"><span class="n">' + state.board.length + '</span><span class="of">/ ' + MAX_BOARD + '</span></div></div>' +
        '<div class="idock-weeks">' + weeks + '</div>' +
        '<div class="idock-meta"><span class="idock-leaning"><span class="d"></span><b>' + leaning + '</b> of ' + state.board.length + ' lean to you</span>' +
        '<span class="idock-break">' + breakdown + '</span></div></div>' +
      list + nudge +
      '<div class="idock-foot"><button class="idock-clear" id="dock-clear" type="button">Clear</button>' +
        '<button class="idock-save" id="dock-save" type="button">Save Board</button></div></aside>';
  }
  function renderDock() {
    var host = document.getElementById('hub-dock'); if (!host) return;
    host.innerHTML = inviteDockHtml(); bindDock(host);
  }
  function bindDock(host) {
    host.querySelectorAll('.islot-remove').forEach(function (b) { b.addEventListener('click', function () { removeFromBoard(this.dataset.id); }); });
    host.querySelectorAll('.islot').forEach(function (slot) {
      slot.addEventListener('dragstart', function (e) { state.drag.from = Number(this.dataset.index); e.dataTransfer.effectAllowed = 'move'; });
      slot.addEventListener('dragover', function (e) { e.preventDefault(); var i = Number(this.dataset.index); if (i !== state.drag.over) { state.drag.over = i; this.classList.add('dragover'); } });
      slot.addEventListener('dragleave', function () { this.classList.remove('dragover'); });
      slot.addEventListener('drop', function (e) { e.preventDefault(); reorderBoard(state.drag.from, Number(this.dataset.index)); state.drag.from = state.drag.over = null; });
      slot.addEventListener('dragend', function () { state.drag.from = state.drag.over = null; host.querySelectorAll('.islot').forEach(function (s) { s.classList.remove('dragover'); }); });
    });
    var clear = host.querySelector('#dock-clear'); if (clear) clear.addEventListener('click', function () { state.board = []; renderBoardDependent(); });
    var save = host.querySelector('#dock-save'); if (save) save.addEventListener('click', saveBoard);
  }

  function saveBoard() {
    var btn = document.getElementById('dock-save'); if (btn) { btn.disabled = true; btn.textContent = 'Saving…'; }
    Common.fetchJSON(API_CONFIG.buildUrl('/franchise/recruiting-orders'), {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ franchise_id: context.franchiseId, recruit_ids: state.board })
    }).then(function () { showToast(); })
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

  // Placeholder odds (per spec; real signing math is league-relative → not client-computable).
  // Kept isolated so it can be swapped. Directionally consistent with the backend
  // score = (1+points+PT_bonus)·lean_mult.
  function signOdds(rec, points, promise) {
    var a = Spine.Lean.analyze(rec.leanModel);
    var base = a.standing === 'you1' ? 48 : a.standing === 'list' ? (a.rank === 2 ? 34 : 26)
      : a.standing === 'locked' ? 8 : a.standing === 'open' ? 20 : a.standing === 'quiet' ? 16 : 14;
    var s = Math.max(4, Math.min(99, Math.round(base + points * 2.2 + (promise ? SIGN.PROMISE_W : 0))));
    var band = s >= 72 ? { cls: 'o-lock', lab: 'Strong' } : s >= 48 ? { cls: 'o-even', lab: 'In the Mix' }
      : s >= 26 ? { cls: 'o-slim', lab: 'Slim' } : { cls: 'o-long', lab: 'Long shot' };
    return { pct: s, cls: band.cls, lab: band.lab };
  }
  function allocOf(id) { return state.alloc[id] || { points: 0, promise: false }; }
  function committedIds() { return Object.keys(state.alloc).filter(function (id) { var a = state.alloc[id]; return a && (a.points > 0 || a.promise); }); }
  function spent() { return committedIds().reduce(function (s, id) { return s + (state.alloc[id].points || 0); }, 0); }
  function remaining() { return SIGN.TOTAL - spent(); }
  function pruneAlloc(id) { var a = state.alloc[id]; if (a && a.points === 0 && !a.promise) delete state.alloc[id]; }

  function seedAlloc() {
    var mine = state.recruits.filter(function (r) { return r.leansToUser; }).sort(function (a, b) { return (b.rt || 0) - (a.rt || 0); });
    var out = {};
    if (mine[0]) out[mine[0].recruitId] = { points: 12, promise: true };
    if (mine[1]) out[mine[1].recruitId] = { points: 9, promise: true };
    if (mine[2]) out[mine[2].recruitId] = { points: 6, promise: false };
    return out;
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
    var a = allocOf(r.recruitId), o = signOdds(r, a.points, a.promise);
    var committed = a.points > 0 || a.promise;
    var claimed = (r.leanModel.leans || []).filter(function (s) { return !s.open; }).length;
    var stand = r.yourRank === 1 ? '<span class="brow-stand you1">' + DOT_SVG + '#1</span>'
      : r.yourRank > 1 ? '<span class="brow-stand list">#' + r.yourRank + '</span>' : '';
    var dots = [0, 1, 2].map(function (i) { return '<i class="' + (i < claimed ? 'on' : '') + '"></i>'; }).join('');
    var canPlus = remaining() > 0 && a.points < SIGN.MAX_PER;
    return '<div class="prow' + (committed ? ' funded' : '') + (state.flashId === r.recruitId ? ' flash' : '') + '" data-id="' + r.recruitId + '">' +
      '<div class="prow-name"><div class="nm"><span class="txt">' + Common.escapeHtml(r.name) + '</span>' + stand + '</div>' +
        '<div class="prow-arch">' + Common.escapeHtml(r.archetype) + '</div></div>' +
      '<span class="prow-pos">' + Common.escapeHtml(r.pos) + '</span>' +
      '<span class="prow-region">' + regionOf(r) + '</span>' +
      '<span class="prow-rt"><span class="v ' + Spine.rtClassForYear(r.rt, r.year) + '">' + (r.rt != null ? r.rt : '--') + '</span></span>' +
      '<span class="prow-leans" title="' + claimed + ' of 3 leans">' + dots + '</span>' +
      '<div><div class="stepper"><button data-step="-1" data-id="' + r.recruitId + '"' + (a.points === 0 ? ' disabled' : '') + '>−</button>' +
        '<span class="val' + (a.points === 0 ? ' zero' : '') + '">' + a.points + '</span>' +
        '<button data-step="1" data-id="' + r.recruitId + '"' + (canPlus ? '' : ' disabled') + '>+</button><span class="stepper-pts">pts</span></div></div>' +
      '<div class="promise-cell' + (a.promise ? ' set' : '') + '"><button class="promise-toggle" data-promise="' + r.recruitId + '" title="Promise playing time">' +
        '<span class="box">' + CHECK + '</span>' + (a.promise ? 'Binding' : 'Promise') + '</button></div>' +
      '<div class="odds ' + o.cls + '"><div class="odds-top"><span class="odds-lab">' + o.lab + '</span><span class="odds-pct">' + o.pct + '%</span></div>' +
        '<div class="odds-bar"><div class="odds-fill" style="width:' + o.pct + '%"></div></div></div></div>';
  }

  function railHtml() {
    var cids = committedIds().map(function (id) { return { r: state.byId[id], a: state.alloc[id], o: signOdds(state.byId[id], state.alloc[id].points, state.alloc[id].promise) }; })
      .filter(function (x) { return x.r; })
      .sort(function (x, y) { return (y.a.points - x.a.points) || (y.o.pct - x.o.pct); });
    var rem = remaining(), promises = committedIds().filter(function (id) { return state.alloc[id].promise; }).length;
    var pct = Math.min(100, (spent() / SIGN.TOTAL) * 100);
    var list = cids.length === 0
      ? '<div class="rail-list"><div class="rail-empty"><div class="t1">Nothing committed</div><div class="t2">Add points to a recruit in the pool and they\'ll appear here.</div></div></div>'
      : '<div class="rail-list">' + cids.map(function (x) {
          return '<div class="citem" data-jump="' + x.r.recruitId + '" title="Jump to recruit"><div class="citem-body">' +
            '<div class="citem-name"><span class="nm">' + Common.escapeHtml(x.r.name) + '</span>' + (x.a.promise ? '<span class="pmk">· PT</span>' : '') + '</div>' +
            '<div class="citem-meta"><span class="citem-pts">' + x.a.points + ' pts</span><span>' + Common.escapeHtml(x.r.pos) + ' · ' + (x.r.rt != null ? x.r.rt : '--') + ' RT</span>' +
            '<span class="citem-odds" style="color:var(--muted)">' + x.o.pct + '%</span></div></div>' +
            '<button class="citem-x" data-remove="' + x.r.recruitId + '" title="Remove">×</button></div>';
        }).join('') + '</div>';
    var note = promises > 0
      ? '<div class="rail-note">' + WARN_SVG + '<span><b>' + promises + ' binding ' + (promises === 1 ? 'promise' : 'promises') + '</b> — honor the playing time or your program\'s standing suffers.</span></div>'
      : '<div class="rail-note"><span>Promises are <b>binding</b> — set one only if you\'ll honor the minutes.</span></div>';
    var disabled = rem < 0 || state.week35Ran;
    return '<div class="rail-head"><div class="rail-title">Your Orders</div>' +
      '<div class="budget-nums"><span class="rem' + (rem < 0 ? ' over' : '') + '">' + rem + '</span><span class="of">/ ' + SIGN.TOTAL + '</span></div>' +
      '<div class="budget-caprow"><span class="budget-cap">Points to spend</span>' +
        '<span class="budget-promises"><b>' + promises + '</b> ' + (promises === 1 ? 'promise' : 'promises') + '</span></div>' +
      '<div class="budget-bar"><div class="budget-fill' + (rem < 0 ? ' over' : '') + '" style="width:' + pct + '%"></div></div></div>' +
      list +
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
          '<span>Leans</span><span>Points</span><span>Playing Time</span><span>Sign odds</span></div>' +
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
    var submit = host.querySelector('#sign-submit'); if (submit) submit.addEventListener('click', submitOrders);
  }
  function bindSignBoard() {
    document.querySelectorAll('[data-stab]').forEach(function (b) { b.addEventListener('click', function () { state.sTab = this.dataset.stab; renderSignRows(); document.querySelectorAll('[data-stab]').forEach(function (x) { x.classList.toggle('on', x.dataset.stab === state.sTab); }); }); });
    var region = document.getElementById('sign-region'); if (region) region.addEventListener('change', function () { state.sRegion = this.value; renderSignRows(); });
    var search = document.getElementById('sign-search'); if (search) search.addEventListener('input', function () { state.sSearch = this.value; renderSignRows(); });
    bindSignRows(); bindSignRail();
  }

  function submitOrders() {
    if (remaining() < 0 || state.week35Ran) return;
    var btn = document.getElementById('sign-submit'); if (btn) { btn.disabled = true; btn.textContent = 'Submitting…'; }
    var entries = committedIds().map(function (id) { return { id: id, points: state.alloc[id].points, scholarship: false, playing_time: !!state.alloc[id].promise }; });
    Common.fetchJSON(API_CONFIG.buildUrl('/franchise/recruiting-orders'), {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ franchise_id: context.franchiseId, order_entries: entries })
    }).then(function () {
      return Common.fetchJSON(API_CONFIG.buildUrl('/franchise/run-week-35-recruiting'), {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ franchise_id: context.franchiseId })
      });
    }).then(function () {
      showToast('Orders Submitted', 'Points spent and promises are now binding.');
      setTimeout(function () { window.location.href = Common.buildFccUrl(context); }, 950);
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
  function signingsList() {
    var signed = state.week35Results.signed_by_recruit_id || {};
    return state.recruits.filter(function (r) { return signed[r.recruitId]; }).map(function (r) {
      var info = signed[r.recruitId] || {};
      var withYou = String(info.team_id) === String(state.userTeamId);
      return {
        r: r,
        team: info.team_name || info.team_id || '—',
        team_id: info.team_id,
        withYou: withYou,
      };
    }).sort(function (a, b) { return (b.withYou - a.withYou) || ((b.r.rt || 0) - (a.r.rt || 0)); });
  }
  function finalSigningsHtml() {
    var all = signingsList();
    var won = all.filter(function (s) { return s.withYou; });
    var targets = state.recruits.filter(function (r) { return r.leansToUser; });
    var targetsWon = targets.filter(function (r) { var s = (state.week35Results.signed_by_recruit_id || {})[r.recruitId]; return s && String(s.team_id) === String(state.userTeamId); }).length;
    var rows = state.signFilter === 'mine' ? all.filter(function (s) { return s.withYou; })
      : state.signFilter === 'targets' ? all.filter(function (s) { return s.r.leansToUser; }) : all;
    var chip = function (k, l) { return '<button class="chip' + (state.signFilter === k ? ' on' : '') + '" data-sfilter="' + k + '">' + l + '</button>'; };
    var rowsHtml = rows.map(function (s) {
      var r = s.r, ab = Spine.Lean.deriveAbbr(s.team, s.teamId || s.team_id);
      return '<div class="srow' + (s.withYou ? ' win' : '') + '">' +
        '<div class="sname"><span class="nm">' + Common.escapeHtml(r.name) + '</span></div>' +
        '<span class="scol spos">' + Common.escapeHtml(r.pos) + '</span>' +
        '<span class="scol sregion">' + regionOf(r) + '</span>' +
        '<span class="scol srt"><span class="v ' + Spine.rtClassForYear(r.rt, r.year) + '">' + (r.rt != null ? r.rt : '--') + '</span></span>' +
        '<span class="scol">' + signStandChip(r) + '</span>' +
        '<div class="ssigned"><span class="logo ' + (s.withYou ? 'you' : 'rival') + '">' + Common.escapeHtml(ab) + '</span>' +
          '<span class="team ' + (s.withYou ? 'you' : 'rival') + '">' + Common.escapeHtml(s.team) + '</span></div>' +
        '<span class="soutcome ' + (s.withYou ? 'win' : 'loss') + '">' + (s.withYou ? 'Signed' : 'Lost') + '</span></div>';
    }).join('') || '<div class="srow" style="grid-template-columns:1fr"><span style="color:var(--muted-3);padding:20px">No signings to show.</span></div>';
    return '<div class="signings-wrap" style="margin:0 22px 22px;border:1px solid var(--border);border-radius:16px;overflow:hidden;background:var(--panel-2)">' +
      '<div class="signsum"><div><div class="signsum-big"><span class="n">' + won.length + '</span><span class="of">signings</span></div>' +
        '<div class="signsum-cap">To ' + Common.escapeHtml(state.teamName || 'your program') + '</div></div>' +
        '<div class="signsum-breakdown">' +
          '<div class="ssb"><span class="v win">' + targetsWon + '</span><span class="l">Targets won</span></div>' +
          '<div class="ssb"><span class="v loss">' + (targets.length - targetsWon) + '</span><span class="l">Targets lost</span></div>' +
          '<div class="ssb"><span class="v">' + targets.length + '</span><span class="l">Leaned to you</span></div></div></div>' +
      '<div class="sign-filter">' + chip('all', 'All signings') + chip('mine', 'Signed with you') + chip('targets', 'Your targets') + '</div>' +
      '<div class="signtable"><div class="shdr"><span>Recruit</span><span class="c">Pos</span><span class="c">Region</span><span class="c">RT</span>' +
        '<span class="c">Your standing</span><span>Signed with</span><span></span></div>' + rowsHtml + '</div></div>';
  }
  function bindSignings() {
    document.querySelectorAll('[data-sfilter]').forEach(function (b) { b.addEventListener('click', function () { state.signFilter = this.dataset.sfilter; document.getElementById('hub-signings').innerHTML = finalSigningsHtml(); bindSignings(); }); });
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
        '<div class="nm">' + Common.recruitNameLinkHtml(yourVisit.recruit_id, context.franchiseId, yourVisit.name) + '<span class="wmeta"><span class="pos">' + Common.escapeHtml(yourVisit.pos) + '</span>Region ' + Common.escapeHtml(yourVisit.home_region) + ' · ' + Common.escapeHtml(yourVisit.rt) + ' RT</span></div>' +
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
    else if (results) { document.getElementById('hub-signings').innerHTML = finalSigningsHtml(); bindSignings(); }
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
        // Seed the board from saved orders ({"1":id,...} → ordered), keeping only still-valid,
        // unique recruits (backend already dedupes; guard defensively).
        var seen = {};
        state.board = Common.recruitingOrderIds(data.saved_orders || {}).filter(function (id) {
          if (!state.byId[id] || seen[id]) return false; seen[id] = true; return true;
        });
        // Signing Day: restore the budget from saved entries; else auto-fill top leaners.
        state.week35Ran = !!data.week_35_recruiting_ran;
        if (state.phase === 'day') {
          var savedEntries = (data.saved_order_entries_week_35 || []).filter(function (e) { return e && state.byId[e.id]; });
          if (savedEntries.length) {
            savedEntries.forEach(function (e) { state.alloc[e.id] = { points: Number(e.points) || 0, promise: !!e.playing_time }; pruneAlloc(e.id); });
          } else {
            state.alloc = seedAlloc();
          }
        }
        renderShell();
      })
      .catch(function (err) { console.error(err); if (root) root.innerHTML = '<div class="hub-error">Failed to load recruits.</div>'; });
  }

  init();
})();
