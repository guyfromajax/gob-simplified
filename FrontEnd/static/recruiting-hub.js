/**
 * Recruiting Hub — D1 (Prompt 1). The persistent hub shell present in every phase:
 * topbar + Recruit Pool anchor, the calendar-driven phase strip, the passive story
 * strip, and the ~300-recruit pool (region A–H collapse, sort, filters) with the
 * shared lean ladder. Phase-aware: Passive shows the pool alone; Invite/Signing/Results
 * dock a right rail that (for now) routes to the existing pages until Prompts 2–4 fold
 * them in. Takes over recruiting.html.
 *
 * Reuses window.RecruitingCommon (data model/helpers) and window.RecruitingSpine
 * (lean ladder, phase strip, anchor, RT class).
 */
(function () {
  'use strict';

  var Common = window.RecruitingCommon;
  var Spine = window.RecruitingSpine;
  var ATTR_KEYS = Common.ATTR_KEYS;
  var REGION_ORDER = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'];
  var COLSPAN = 5 + ATTR_KEYS.length + 2; // name,pos,year,ht,wt + 12 attrs + rt,lean = 19
  var SORTABLE = { name: 'text', pos: 'text', year: 'text', height: 'num', weight: 'num', rt: 'num' };

  var context = Common.getQueryContext();
  var state = {
    week: 1,
    phase: 'passive',
    userTeamId: null,
    recruits: [],
    newLeanIds: new Set(),
    search: '',
    region: 'all',
    mineOnly: false,
    sort: { key: 'rt', dir: 'desc' },
    collapsed: {}
  };

  // Attribute color bands rescaled from the mock's 0–8 to the real 0–100 display
  // (attributes are stored 0–1000, shown ÷10). Tunable.
  function attrClass(v) {
    return v >= 65 ? 'attr-hi' : v >= 40 ? 'attr-mid' : v >= 20 ? 'attr-lo' : 'attr-zero';
  }

  function regionOf(rec) {
    var v = rec && rec.homeRegion ? String(rec.homeRegion).trim().toUpperCase() : '';
    return v ? v.charAt(0) : '';
  }

  // ---- SVG bits (match mockup) ----
  var CHEVRON = '<svg class="region-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M6 9l6 6 6-6"></path></svg>';
  var ARROW_UP = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6"><path d="M7 17L17 7M9 7h8v8"></path></svg>';

  // Transition routing for non-passive phases (until Prompts 2–4 build the docks inline).
  function dockConfigForPhase(phase) {
    if (phase === 'invite') {
      return { pill: 'Invite Season', tag: 'Invite Board', page: 'recruiting-invites.html',
        cta: 'Open Invite Board', desc: 'Send one invite per week (Wks 20–26). The invite board opens in the current page until it docks here.' };
    }
    if (phase === 'day') {
      return { pill: 'Signing Day', tag: 'Signing Board', page: 'recruiting-orders.html',
        cta: 'Open Signing Board', desc: 'Spend your 50 points and make binding promises. The signing board opens in the current page until it docks here.' };
    }
    if (phase === 'results') {
      return { pill: 'Results', tag: 'Signing Results', page: 'recruiting-results.html',
        cta: 'View Signing Results', desc: 'Signings are final. Full results open in the current page until they dock here.' };
    }
    return null; // passive → no dock
  }

  // =========================================================================
  // POOL
  // =========================================================================
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
      case 'name': return r.name;
      case 'pos': return r.pos;
      case 'year': return Common.getYearSortValue(r.year);
      case 'height': return r.heightRaw;
      case 'weight': return r.weight != null ? r.weight : -1;
      case 'rt': return r.rt != null ? r.rt : -1;
      default: return r[key];
    }
  }

  function sortRecs(recs) {
    var key = state.sort.key, dir = state.sort.dir;
    var num = SORTABLE[key] === 'num' || key === 'year';
    return recs.slice().sort(function (a, b) {
      var av = sortValue(a, key), bv = sortValue(b, key), c;
      if (num) c = dir === 'asc' ? av - bv : bv - av;
      else c = dir === 'asc' ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
      if (c) return c;
      return (b.rt != null ? b.rt : -1) - (a.rt != null ? a.rt : -1);
    });
  }

  function arrow(key) {
    return state.sort.key === key ? '<span class="arrow">' + (state.sort.dir === 'asc' ? '▲' : '▼') + '</span>' : '';
  }
  function th(key, label, cls) {
    return '<th class="' + (cls || 'num') + '" data-sortkey="' + key + '">' + label + arrow(key) + '</th>';
  }

  function headHtml() {
    var attrTh = ATTR_KEYS.map(function (k, i) {
      return '<th class="num attr-col' + (i === 0 ? ' attr-sep' : '') + '">' + k + '</th>';
    }).join('');
    return '<thead><tr>' +
      th('name', 'Name', 'name-col') + th('pos', 'Pos') + th('year', 'Yr') +
      th('height', 'Ht') + th('weight', 'Wt') + attrTh +
      '<th class="num attr-sep" data-sortkey="rt">RT' + arrow('rt') + '</th>' +
      '<th class="lean-col">Leans / Your Standing</th></tr></thead>';
  }

  function rowHtml(r) {
    var rowCls = r.yourRank === 1 ? 'mine' : r.yourRank > 1 ? 'list-mine' : '';
    var nameLink = Common.recruitNameLinkHtml(r.recruitId, context.franchiseId, r.name);
    var flags = (state.newLeanIds.has(String(r.recruitId)) ? '<span class="flag new">New</span>' : '');
    var attrs = ATTR_KEYS.map(function (k, i) {
      var v = r.attrs[k];
      return '<td class="attr ' + attrClass(v) + (i === 0 ? ' attr-sep' : '') + '">' + v + '</td>';
    }).join('');
    var rtCls = Spine.rtClassForYear(r.rt, r.year);
    return '<tr class="rec ' + rowCls + '">' +
      '<td class="name-col"><div class="pc-name"><span class="nm">' + nameLink + '</span>' + flags + '</div>' +
        '<div class="pc-arch">' + Common.escapeHtml(r.archetype) + '</div></td>' +
      '<td class="pos">' + Common.escapeHtml(r.pos) + '</td>' +
      '<td class="year">' + Common.escapeHtml(r.yearDisplay) + '</td>' +
      '<td class="num">' + Common.escapeHtml(r.height) + '</td>' +
      '<td class="num">' + (r.weight != null ? r.weight : '--') + '</td>' +
      attrs +
      '<td class="rt attr-sep"><span class="v ' + rtCls + '">' + (r.rt != null ? r.rt : '--') + '</span></td>' +
      '<td class="lean-col">' + Spine.Lean.ladderHtml(r.leanModel) + '</td>' +
      '</tr>';
  }

  function poolBodyHtml() {
    var recs = sortRecs(filteredRecruits());
    var byRegion = {};
    recs.forEach(function (r) { var g = regionOf(r); (byRegion[g] = byRegion[g] || []).push(r); });
    var rows = '';
    REGION_ORDER.forEach(function (region) {
      var list = byRegion[region];
      if (!list || !list.length) return;
      var collapsed = !!state.collapsed[region];
      var mineCount = list.filter(function (r) { return r.leansToUser; }).length;
      rows += '<tr class="region-row"><td colspan="' + COLSPAN + '">' +
        '<button class="region-bar' + (collapsed ? ' region-collapsed' : '') + '" data-region="' + region + '" type="button">' +
          CHEVRON + '<span class="region-letter">' + region + '</span>' +
          '<span class="region-name"></span>' +
          '<span class="region-stat"><b>' + list.length + '</b> recruits</span>' +
          (mineCount > 0 ? '<span class="region-mine"><span class="d"></span>' + mineCount + ' leaning to you</span>' : '') +
        '</button></td></tr>';
      if (!collapsed) rows += list.map(rowHtml).join('');
    });
    if (!rows) rows = '<tr><td colspan="' + COLSPAN + '" style="padding:26px;text-align:center;color:var(--muted-3)">No recruits match your filters.</td></tr>';
    return rows;
  }

  function toolbarHtml(total, shown) {
    var chips = '<button class="chip' + (state.region === 'all' ? ' is-active' : '') + '" data-region="all">All</button>' +
      REGION_ORDER.map(function (r) {
        return '<button class="chip' + (state.region === r ? ' is-active' : '') + '" data-region="' + r + '">' + r + '</button>';
      }).join('');
    return '<div class="pool-toolbar">' +
      '<div class="ptb-group"><span class="ptb-label">Find</span>' +
        '<input class="ptb-search" id="pool-search" placeholder="Name…" value="' + Common.escapeHtml(state.search) + '"></div>' +
      '<div class="ptb-group"><span class="ptb-label">Region</span>' + chips + '</div>' +
      '<button class="chip mine' + (state.mineOnly ? ' is-active' : '') + '" id="pool-mine">◗ Leaning to me</button>' +
      '<span class="ptb-count">Showing <strong>' + shown + '</strong> of ' + total + '</span>' +
      '</div>';
  }

  function renderPool() {
    var host = document.getElementById('hub-pool');
    if (!host) return;
    var shown = filteredRecruits().length;
    host.innerHTML =
      toolbarHtml(state.recruits.length, shown) +
      '<div class="pool-scroll"><table class="pool' + (dockConfigForPhase(state.phase) ? ' condensed' : '') + '">' +
        headHtml() + '<tbody>' + poolBodyHtml() + '</tbody></table></div>';
    bindPool(host);
  }

  function bindPool(host) {
    var search = host.querySelector('#pool-search');
    if (search) search.addEventListener('input', function () { state.search = this.value; renderPoolBodyOnly(); updateCount(); });
    host.querySelectorAll('.pool-toolbar .chip[data-region]').forEach(function (b) {
      b.addEventListener('click', function () { state.region = this.dataset.region; renderPool(); });
    });
    var mine = host.querySelector('#pool-mine');
    if (mine) mine.addEventListener('click', function () { state.mineOnly = !state.mineOnly; renderPool(); });
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
    host.querySelectorAll('.region-bar').forEach(function (b) {
      b.addEventListener('click', function () {
        var reg = this.dataset.region;
        state.collapsed[reg] = !state.collapsed[reg];
        renderPoolBodyOnly();
      });
    });
  }

  // Lighter re-render for search/collapse (keeps toolbar focus on the search input).
  function renderPoolBodyOnly() {
    var tbody = document.querySelector('#hub-pool tbody');
    if (tbody) tbody.innerHTML = poolBodyHtml();
    document.querySelectorAll('#hub-pool .region-bar').forEach(function (b) {
      b.addEventListener('click', function () {
        state.collapsed[this.dataset.region] = !state.collapsed[this.dataset.region];
        renderPoolBodyOnly();
      });
    });
    if (typeof window.initAttributeTooltips === 'function') window.initAttributeTooltips(document.getElementById('hub-pool'), ['td']);
  }
  function updateCount() {
    var el = document.querySelector('#hub-pool .ptb-count strong');
    if (el) el.textContent = filteredRecruits().length;
  }

  // =========================================================================
  // STORY STRIP (passive) — new leans live; "dropped you" deferred (no backend signal)
  // =========================================================================
  function storyHtml() {
    var gains = state.recruits.filter(function (r) { return state.newLeanIds.has(String(r.recruitId)); });
    var items = gains.map(function (r) {
      var rank = r.yourRank ? '#' + r.yourRank : 'your list';
      return '<div class="story-item"><span class="ico gain">' + ARROW_UP + '</span>' +
        '<span class="tx"><span class="t1">' + Common.escapeHtml(r.name) + '</span>' +
        '<span class="t2">now leaning you · <b>' + rank + '</b></span></span></div>';
    }).join('');
    if (!items) items = '<div class="story-empty">Quiet week — no new leans.</div>';
    return '<div class="story"><div class="story-lead"><span class="wkn">Wk ' + state.week + '</span>' +
      '<span class="lbl">This week</span></div><div class="story-items">' + items + '</div></div>';
  }

  // =========================================================================
  // SHELL
  // =========================================================================
  function dockHtml() {
    var d = dockConfigForPhase(state.phase);
    if (!d) return '';
    var href = Common.buildRecruitingUrl(d.page, context);
    return '<div class="dock-ph">' +
      '<span class="pill">' + d.pill + '</span>' +
      '<span class="tag">' + d.tag + '</span>' +
      '<span class="desc">' + d.desc + '</span>' +
      '<a class="hub-anchor" style="margin:0;text-decoration:none" href="' + Common.escapeHtml(href) + '">' + d.cta + ' →</a>' +
      '</div>';
  }

  function renderShell() {
    var root = document.getElementById('hub-root');
    var hasDock = !!dockConfigForPhase(state.phase);
    root.innerHTML =
      '<div class="spine-topbar">' +
        '<span class="spine-h">Recruiting <b>Hub</b></span>' +
        '<span id="hub-anchor-mount"></span>' +
      '</div>' +
      '<div class="spine-topbar" style="padding-top:12px;padding-bottom:0"><div style="flex:1" id="hub-phase"></div></div>' +
      '<div class="spine-body ' + (hasDock ? 'with-dock' : 'no-dock') + '" style="padding-top:14px">' +
        '<div style="min-width:0;display:flex;flex-direction:column;gap:14px">' +
          (state.phase === 'passive' ? storyHtml() : '') +
          '<div class="pool-wrap"><div id="hub-pool"></div></div>' +
        '</div>' +
        (hasDock ? dockHtml() : '') +
      '</div>';

    // phase strip
    var phaseHost = document.getElementById('hub-phase');
    phaseHost.innerHTML = Spine.Phase.stripHtml({ phase: state.phase, week: state.week });
    Spine.Phase.bind(phaseHost);

    // anchor
    var mount = document.getElementById('hub-anchor-mount');
    mount.innerHTML = Spine.Anchor.html();
    Spine.Anchor.bind(mount.querySelector('.hub-anchor'), { poolSelector: '.pool-wrap' });

    renderPool();
    if (typeof window.initAttributeTooltips === 'function') window.initAttributeTooltips(document.getElementById('hub-pool'), ['th', 'td']);
  }

  // =========================================================================
  // INIT
  // =========================================================================
  function init() {
    var root = document.getElementById('hub-root');
    var backBtn = document.getElementById('back-btn');
    if (!context.franchiseId || !context.teamId) {
      if (root) root.innerHTML = '<div class="hub-error">Missing franchise context.</div>';
      return;
    }
    if (backBtn) backBtn.href = Common.buildFccUrl(context);

    Common.fetchJSON(API_CONFIG.buildUrl('/franchise/recruiting-data') + '?franchise_id=' + encodeURIComponent(context.franchiseId))
      .then(function (data) {
        state.week = Number(data.week || 1);
        state.phase = Spine.Phase.forWeek(state.week);
        state.userTeamId = data.team_id || context.teamId;
        state.newLeanIds = new Set((data.new_lean_recruit_ids || []).map(String));
        var teamNameMap = data.team_name_map || {};
        state.recruits = Common.normalizeRecruits(data.recruits || [], teamNameMap).map(function (r) {
          var model = Spine.Lean.fromBackend({ Lean: r.lean }, { userTeamId: state.userTeamId, teamNameMap: teamNameMap });
          r.leanModel = model;
          r.leansToUser = model.leansToUser;
          r.yourRank = model.yourRank;
          return r;
        });
        renderShell();
      })
      .catch(function (err) {
        console.error(err);
        if (root) root.innerHTML = '<div class="hub-error">Failed to load recruits.</div>';
      });
  }

  init();
})();
