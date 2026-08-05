/**
 * Team Builder chaptered SPA — Identity → Gate → Roster → Review → Establish.
 *
 * Entry: /team-builder.html?replaced_object_id=&chapter=identity&home_slot=
 * Chrome: await ensureTeamBuilderChromeSnapshot() before painting identity/chrome.
 */
(function () {
  'use strict';

  var C = window.TeamBuilderConstants;
  var params = new URLSearchParams(window.location.search);
  var HOME_SLOT = (function () {
    var n = parseInt(params.get('home_slot'), 10);
    return n === 1 || n === 2 ? n : null;
  })();
  var REPLACED_OID = String(params.get('replaced_object_id') || '').trim();
  var INITIAL_CHAPTER = normalizeChapter(params.get('chapter') || 'identity');

  var state = {
    chapter: INITIAL_CHAPTER,
    draftId: String(params.get('draft_id') || '').trim() || null,
    replaced: null,
    allTeams: [],
    identity: C.defaultIdentity(),
    buildMode: normalizeMode(params.get('mode') || params.get('build_mode')),
    shape: {
      height_budget: null,
      class_budget: null,
      class_rank: null,
      loaded: false,
    },
    identityChapter: null,
    gateChapter: null,
    rosterChapter: null,
    reviewChapter: null,
    establishChapter: null,
    draftRoster: null,
    saveTimer: null,
    saving: false,
  };

  var els = {};

  function normalizeChapter(raw) {
    var c = String(raw || '').toLowerCase().trim();
    if (C.CHAPTERS.indexOf(c) >= 0) return c;
    return 'identity';
  }

  function normalizeMode(raw) {
    var m = String(raw || '').toLowerCase().trim();
    if (m === 'capped' || m === 'uncapped') return m;
    return null;
  }

  function normalizeBannerVariant(raw) {
    if (window.TeamGeneratedArt && typeof TeamGeneratedArt.normalizeBannerVariant === 'function') {
      var v = TeamGeneratedArt.normalizeBannerVariant(raw);
      if (v === 'chevron') return C.DEFAULT_BANNER_VARIANT;
      return v;
    }
    var key = String(raw || '').toLowerCase();
    return ['baseline', 'keel', 'plate', 'sash'].indexOf(key) >= 0
      ? key
      : C.DEFAULT_BANNER_VARIANT;
  }

  function claimUrl() {
    var q = new URLSearchParams();
    q.set('builder', '1');
    if (HOME_SLOT) q.set('home_slot', String(HOME_SLOT));
    return '/franchise-select-team.html?' + q.toString();
  }

  function showFatal(msg) {
    els.boot.hidden = true;
    els.app.hidden = true;
    els.fatal.hidden = false;
    els.fatal.textContent = msg || 'Unable to open Team Builder.';
  }

  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function teamAbbr(team) {
    if (!team) return '';
    if (team.abbreviation) {
      return String(team.abbreviation).trim().toUpperCase().slice(0, 3);
    }
    if (window.TeamGeneratedArt && typeof TeamGeneratedArt.initialsFromName === 'function') {
      return String(TeamGeneratedArt.initialsFromName(team.name, null, team.object_id) || '')
        .toUpperCase()
        .slice(0, 3);
    }
    if (typeof deriveTeamAbbreviationFromName === 'function') {
      return deriveTeamAbbreviationFromName(team.name);
    }
    return String(team.name || '')
      .replace(/[^A-Za-z0-9]/g, '')
      .slice(0, 3)
      .toUpperCase();
  }

  function leagueTakenAbbrs() {
    var slotId = state.replaced && state.replaced.object_id;
    var out = [];
    (state.allTeams || []).forEach(function (t) {
      if (slotId && String(t.object_id) === String(slotId)) return;
      var a = teamAbbr(t);
      if (a && a.length === 3) out.push(a);
    });
    return out;
  }

  function conferenceLabel(team) {
    if (window.TeamPicker && typeof TeamPicker.formatConferenceLabel === 'function') {
      return TeamPicker.formatConferenceLabel(team && team.conference);
    }
    var n = Number(team && team.conference);
    return n >= 1 && n <= 16 ? 'Conference ' + n : 'Conference';
  }

  function regionLabel(team) {
    if (window.TeamPicker && typeof TeamPicker.regionFromConference === 'function') {
      var r =
        (team && team.region) ||
        TeamPicker.regionFromConference(team && team.conference);
      return r ? 'Region ' + String(r).toUpperCase() : '';
    }
    return team && team.region ? 'Region ' + String(team.region).toUpperCase() : '';
  }

  function mergeIdentity(raw) {
    var base = C.defaultIdentity();
    if (!raw || typeof raw !== 'object') return base;
    var next = Object.assign({}, base, raw);
    next.name = window.TeamBuilderIdentity.clampName(next.name || '');
    next.mascot = String(next.mascot || '').slice(0, C.MASCOT_MAX_LEN);
    next.abbreviation = String(next.abbreviation || next.abbr || '')
      .toUpperCase()
      .replace(/[^A-Z0-9]/g, '')
      .slice(0, 3);
    next.abbr_touched = !!(next.abbr_touched || next.abbrTouched);
    next.banner_variant = normalizeBannerVariant(
      next.banner_variant || next.bannerVariant
    );
    next.jersey_preset = Number(next.jersey_preset || next.jerseyPreset) === 2 ? 2 : 1;
    // Accept either snake or camel from older drafts.
    if (raw.oobCustom && !raw.oob_custom) next.oob_custom = raw.oobCustom;
    if (raw.laneCustom && !raw.lane_custom) next.lane_custom = raw.laneCustom;
    if (raw.arcCustom && !raw.arc_custom) next.arc_custom = raw.arcCustom;
    if (raw.outsideCustom && !raw.outside_custom) next.outside_custom = raw.outsideCustom;
    if (raw.insideCustom && !raw.inside_custom) next.inside_custom = raw.insideCustom;
    return next;
  }

  function identityPayload() {
    var id = state.identity;
    return {
      name: id.name,
      mascot: id.mascot,
      abbreviation: id.abbreviation,
      abbr_touched: !!id.abbr_touched,
      primary: id.primary,
      secondary: id.secondary,
      jersey_preset: id.jersey_preset,
      banner_variant: normalizeBannerVariant(id.banner_variant),
      inside: id.inside,
      outside: id.outside,
      oob: id.oob,
      lane: id.lane,
      arc: id.arc,
      oob_custom: id.oob_custom,
      lane_custom: id.lane_custom,
      arc_custom: id.arc_custom,
      outside_custom: id.outside_custom,
      inside_custom: id.inside_custom,
    };
  }

  async function upsertDraft(patch) {
    if (!REPLACED_OID) throw new Error('replaced_object_id required');
    var body = Object.assign(
      {
        replaced_object_id: REPLACED_OID,
        draft_id: state.draftId || undefined,
      },
      patch || {}
    );
    var res = await fetch(API_CONFIG.buildUrl('/franchise/team-builder/drafts'), {
      method: 'POST',
      headers: Object.assign({}, API_CONFIG.getAuthHeaders(), {
        'Content-Type': 'application/json',
      }),
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      var detail = 'Could not save draft';
      try {
        var err = await res.json();
        if (err && err.detail) detail = String(err.detail);
      } catch (_) {}
      throw new Error(detail);
    }
    var data = await res.json();
    var draft = data.draft || data;
    if (draft && draft.draft_id) state.draftId = draft.draft_id;
    return draft;
  }

  function scheduleSave() {
    clearTimeout(state.saveTimer);
    state.saveTimer = setTimeout(function () {
      persistDraft().catch(function (err) {
        console.warn('[TeamBuilder] draft save failed', err);
      });
    }, C.DRAFT_SAVE_MS);
  }

  async function persistDraft(extra) {
    var patch = Object.assign(
      {
        chapter: state.chapter,
        identity: identityPayload(),
      },
      extra || {}
    );
    if (state.buildMode) patch.build_mode = state.buildMode;
    if (state.rosterChapter && state.rosterChapter.loaded) {
      patch.roster = state.rosterChapter.draftPayload();
      state.draftRoster = patch.roster;
    } else if (state.draftRoster && !patch.roster) {
      patch.roster = state.draftRoster;
    }
    state.saving = true;
    try {
      return await upsertDraft(patch);
    } finally {
      state.saving = false;
    }
  }

  async function loadShapeBudgets() {
    if (!state.draftId) {
      var minted = await upsertDraft({ chapter: state.chapter, identity: identityPayload() });
      state.draftId = minted.draft_id;
    }
    var res = await fetch(API_CONFIG.buildUrl('/franchise/team-builder/wizard-walk-ons'), {
      method: 'POST',
      headers: Object.assign({}, API_CONFIG.getAuthHeaders(), {
        'Content-Type': 'application/json',
      }),
      body: JSON.stringify({
        replaced_object_id: REPLACED_OID,
        draft_id: state.draftId,
      }),
    });
    if (!res.ok) return;
    var data = await res.json();
    applyShapeFromWalkOns(data);
  }

  function applyShapeFromWalkOns(data) {
    if (!data) return;
    state.shape.height_budget =
      data.height_budget != null ? Number(data.height_budget) : state.shape.height_budget;
    state.shape.class_budget =
      data.class_budget != null ? Number(data.class_budget) : state.shape.class_budget;
    state.shape.class_rank = data.class_rank || state.shape.class_rank;
    if (data.height_min_in != null) state.shape.height_min_in = Number(data.height_min_in);
    if (data.height_max_in != null) state.shape.height_max_in = Number(data.height_max_in);
    state.shape.loaded = true;
  }

  function buildCourtPayload(id) {
    var resolve =
      window.TeamBuilderIdentity && typeof TeamBuilderIdentity.resolveCourtCfg === 'function'
        ? TeamBuilderIdentity.resolveCourtCfg
        : null;
    if (!resolve) return null;
    var cfg = resolve(id);
    var court = {
      hardwoodStyle: cfg.hardwoodStyle,
      oobColor: cfg.oobColor,
      laneColor: cfg.laneColor,
      outsideWoodColor: cfg.outsideWoodColor,
      halfArcFillColor: cfg.halfArcFillColor,
    };
    if (cfg.insideWoodColor) court.insideWoodColor = cfg.insideWoodColor;
    return court;
  }

  function buildApplyPayload() {
    var id = state.identity;
    var rows =
      state.rosterChapter && typeof state.rosterChapter.applyRows === 'function'
        ? state.rosterChapter.applyRows()
        : [];
    var payload = {
      replaced_object_id: REPLACED_OID,
      name: id.name,
      abbreviation: id.abbreviation,
      mascot: id.mascot || '',
      primary_color: id.primary,
      secondary_color: id.secondary,
      jersey_preset: Number(id.jersey_preset) === 2 ? 2 : 1,
      banner_variant: normalizeBannerVariant(id.banner_variant),
      court: buildCourtPayload(id),
      roster_mode: 'edit',
      attribute_mode: state.buildMode === 'uncapped' ? 'uncapped' : 'capped',
      build_mode: state.buildMode === 'uncapped' ? 'uncapped' : 'capped',
      imported_players: rows,
    };
    if (HOME_SLOT) payload.home_slot = HOME_SLOT;
    if (state.draftId) payload.draft_id = state.draftId;
    return payload;
  }

  async function applyFranchise() {
    if (
      window.TeamBuilderIdentity &&
      typeof TeamBuilderIdentity.insideWoodContrastOk === 'function' &&
      !TeamBuilderIdentity.insideWoodContrastOk(state.identity)
    ) {
      throw new Error(
        'Inside wood colour does not meet the contrast floor against court lines.'
      );
    }
    if (!state.buildMode) {
      throw new Error('Build mode must be chosen before establishing.');
    }
    if (!state.rosterChapter || !state.rosterChapter.loaded) {
      throw new Error('Roster is not ready.');
    }
    var status = state.rosterChapter.getStatus();
    if (!status.legal) {
      throw new Error('Roster is not legal.');
    }
    var payload = buildApplyPayload();
    var res = await fetch(API_CONFIG.buildUrl('/franchise/team-builder/apply'), {
      method: 'POST',
      headers: Object.assign({}, API_CONFIG.getAuthHeaders(), {
        'Content-Type': 'application/json',
      }),
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      var detail = 'Unable to establish the program';
      try {
        var err = await res.json();
        if (err && err.detail) {
          detail = typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail);
        }
      } catch (_) {}
      throw new Error(detail);
    }
    var data = await res.json();
    if (window.FranchiseLS && data.franchise_id) {
      window.FranchiseLS.clearBareKeys();
      window.FranchiseLS.setTeamContext(data.franchise_id, {
        teamName: state.identity.name,
      });
    }
    state.draftId = null;
    return data;
  }

  function setChapter(chapter, opts) {
    var next = normalizeChapter(chapter);
    // Linear on the way in: roster+ requires build_mode.
    if ((next === 'roster' || next === 'review' || next === 'establish') && !state.buildMode) {
      next = 'gate';
    }
    state.chapter = next;
    var url = new URL(window.location.href);
    url.searchParams.set('chapter', next);
    url.searchParams.set('replaced_object_id', REPLACED_OID);
    if (HOME_SLOT) url.searchParams.set('home_slot', String(HOME_SLOT));
    if (state.draftId) url.searchParams.set('draft_id', state.draftId);
    if (state.buildMode) url.searchParams.set('mode', state.buildMode);
    if (!(opts && opts.replace === false)) {
      window.history.replaceState({}, '', url.pathname + '?' + url.searchParams.toString());
    }
    render();
    scheduleSave();
  }

  function measureChrome() {
    var bar = els.statebar;
    var h = 0;
    if (bar && !bar.hidden) {
      h = Math.ceil(bar.getBoundingClientRect().height) || 0;
    }
    document.documentElement.style.setProperty('--tb-statebar-h', h + 'px');
    // Establish / full-bleed chapters subtract total top chrome (auth + band).
    var auth = document.querySelector('.auth-bar');
    var authH = auth ? Math.ceil(auth.getBoundingClientRect().height) || 0 : 0;
    document.documentElement.style.setProperty('--chrome-h', authH + h + 'px');
  }

  function ensureChromeObserver() {
    if (!els.statebar || els._chromeObs) return;
    if (typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', measureChrome);
      els._chromeObs = true;
      return;
    }
    els._chromeObs = new ResizeObserver(function () {
      measureChrome();
    });
    els._chromeObs.observe(els.statebar);
  }

  function stripReasonHtml(html) {
    return String(html || '')
      .replace(/<[^>]+>/g, '')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function renderStatebar() {
    var bar = els.statebar;
    if (!bar) return;
    // Primary action lives in the band on every chapter screen. Establish (curtain) has none.
    var show =
      state.chapter === 'identity' ||
      state.chapter === 'gate' ||
      state.chapter === 'roster' ||
      state.chapter === 'review';
    bar.hidden = !show;
    if (!show) {
      measureChrome();
      return;
    }

    var id = state.identity;
    var replaced = state.replaced || {};
    var conf = conferenceLabel(replaced);
    var region = regionLabel(replaced);
    var chapMeta = {
      identity: {
        label: 'Ⅱ · Identity',
        path: 'Claim · <b style="color:#fff">Identity</b> · Gate · Roster · Review',
      },
      gate: {
        label: 'Gate · Build mode',
        path: 'Claim · Identity · <b style="color:#fff">Gate</b> · Roster · Review',
      },
      roster: {
        label: 'Ⅲ · Roster',
        path: 'Claim · Identity · Gate · <b style="color:#fff">Roster</b> · Review',
      },
      review: {
        label: 'Review',
        path: 'Claim · Identity · Gate · Roster · <b style="color:#fff">Review</b>',
      },
    };
    var meta = chapMeta[state.chapter] || { label: '—', path: '' };
    var modeHtml = state.buildMode
      ? '<span class="dot ' +
        (state.buildMode === 'capped' ? 'd-ok' : 'd-bad') +
        '"></span>' +
        (state.buildMode === 'capped' ? 'Capped' : 'Uncapped') +
        '<small>' +
        (state.buildMode === 'capped'
          ? 'eligible for online play'
          : 'not eligible for online play') +
        '</small>'
      : '<span class="dot d-off"></span>Not chosen<small>decides online play</small>';

    var rosterStatus =
      state.rosterChapter && state.rosterChapter.loaded
        ? state.rosterChapter.getStatus()
        : null;
    var rosterCell;
    if ((state.chapter === 'roster' || state.chapter === 'review') && rosterStatus) {
      rosterCell =
        '<span class="dot ' +
        (rosterStatus.legal ? 'd-ok' : 'd-bad') +
        '"></span>' +
        (rosterStatus.legal ? 'Ready' : 'Not legal') +
        '<small>' +
        (rosterStatus.changed === 0
          ? 'inherited, unchanged'
          : rosterStatus.changed +
            ' player' +
            (rosterStatus.changed > 1 ? 's' : '') +
            ' changed') +
        '</small>';
    } else {
      rosterCell =
        '<span class="dot d-ok"></span>Inherited<small>15 from ' +
        escapeHtml(replaced.name || 'slot') +
        '</small>';
    }

    var actionReady = false;
    var actionLabel = 'Continue';
    var actionId = 'tb-sb-continue';
    var actionClass = 'btn';
    var reasonHtml = '';
    var programName = id.name || 'Program';

    if (state.chapter === 'identity') {
      actionReady =
        state.identityChapter && typeof state.identityChapter.isReady === 'function'
          ? state.identityChapter.isReady()
          : false;
      actionLabel = 'Continue';
      actionId = 'tb-sb-continue';
      reasonHtml = actionReady
        ? 'Editable until you establish the program'
        : (state.identityChapter && state.identityChapter.getBlockedReason
            ? state.identityChapter.getBlockedReason()
            : 'Finish identity to continue.') || 'Finish identity to continue.';
    } else if (state.chapter === 'gate') {
      var gateCopy =
        state.gateChapter && typeof state.gateChapter.getActionCopy === 'function'
          ? state.gateChapter.getActionCopy()
          : { ready: !!state.buildMode, reason: 'Nothing is chosen yet.' };
      actionReady = !!gateCopy.ready;
      actionLabel = 'Continue';
      actionId = 'tb-sb-continue';
      reasonHtml = gateCopy.reason || 'Nothing is chosen yet.';
    } else if (state.chapter === 'roster') {
      var legal = rosterStatus ? rosterStatus.legal : false;
      actionReady = legal;
      actionLabel = 'Continue to Review';
      actionId = 'tb-sb-roster-next';
      actionClass = 'btn';
      reasonHtml = legal
        ? 'Editable until you establish the program'
        : stripReasonHtml((rosterStatus && rosterStatus.reason) || 'Roster is not legal.');
    } else if (state.chapter === 'review') {
      actionReady = true;
      actionLabel = 'Establish ' + programName;
      actionId = 'tb-sb-establish';
      // Orange like Continue; heavier type + padding (not green — green means valid in this product).
      actionClass = 'btn sb-commit';
      reasonHtml =
        'Writes <b>' +
        escapeHtml(programName) +
        '</b> into the league. This cannot be undone.';
    }

    var reasonIsHtml =
      state.chapter === 'gate' || state.chapter === 'review'
        ? reasonHtml.indexOf('<') !== -1
        : false;

    bar.innerHTML =
      '<div class="sb-cell chap"><div class="sb-k">Chapter</div>' +
      '<div class="sb-v">' +
      meta.label +
      '<small>' +
      meta.path +
      '</small></div></div>' +
      '<div class="sb-cell link" id="tb-sb-claim"><div class="sb-k">Replacing</div>' +
      '<div class="sb-v">' +
      escapeHtml(replaced.name || '—') +
      '<small>' +
      escapeHtml(conf) +
      (region ? ' · ' + escapeHtml(region) : '') +
      '</small></div></div>' +
      '<div class="sb-cell' +
      (state.chapter === 'roster' || state.chapter === 'review' ? ' link' : '') +
      '" id="tb-sb-program"><div class="sb-k">Program</div>' +
      '<div class="sb-v">' +
      escapeHtml(id.name || '—') +
      '<small>' +
      escapeHtml(id.abbreviation || '—') +
      ' · ' +
      escapeHtml(id.mascot || '—') +
      '</small></div></div>' +
      '<div class="sb-cell' +
      (state.chapter === 'roster' || state.chapter === 'review' ? ' link' : '') +
      '" id="tb-sb-mode"><div class="sb-k">Build mode</div>' +
      '<div class="sb-v">' +
      modeHtml +
      '</div></div>' +
      '<div class="sb-cell"><div class="sb-k">Roster</div>' +
      '<div class="sb-v">' +
      rosterCell +
      '</div></div>' +
      '<div class="sb-spacer"></div>' +
      '<div class="sb-cell act">' +
      '<span class="sb-rev' +
      (actionReady ? '' : ' blocked') +
      '" id="tb-sb-reason">' +
      (reasonIsHtml ? reasonHtml : escapeHtml(reasonHtml)) +
      '</span>' +
      '<button type="button" class="' +
      actionClass +
      '" id="' +
      actionId +
      '"' +
      (actionReady ? '' : ' disabled') +
      ' aria-disabled="' +
      (actionReady ? 'false' : 'true') +
      '">' +
      escapeHtml(actionLabel) +
      '</button></div>';

    if (state.chapter === 'review') {
      var estBtn = document.getElementById('tb-sb-establish');
      if (
        estBtn &&
        state.rosterChapter &&
        typeof state.rosterChapter.fitEstablishLabel === 'function'
      ) {
        state.rosterChapter.fitEstablishLabel(estBtn, programName);
      }
    }

    var claim = document.getElementById('tb-sb-claim');
    if (claim) {
      claim.addEventListener('click', function () {
        window.location.href = claimUrl();
      });
    }
    var prog = document.getElementById('tb-sb-program');
    if (prog && (state.chapter === 'roster' || state.chapter === 'review')) {
      prog.addEventListener('click', function () {
        setChapter('identity');
      });
    }
    var modeCell = document.getElementById('tb-sb-mode');
    if (modeCell && (state.chapter === 'roster' || state.chapter === 'review')) {
      modeCell.addEventListener('click', function () {
        setChapter('gate');
      });
    }
    var cont = document.getElementById('tb-sb-continue');
    if (cont) {
      cont.addEventListener('click', function () {
        if (cont.disabled) return;
        if (state.chapter === 'identity') {
          if (state.identityChapter && state.identityChapter.isReady()) setChapter('gate');
        } else if (state.chapter === 'gate') {
          if (state.gateChapter && state.gateChapter.onContinue) state.gateChapter.onContinue();
        }
      });
    }
    var rosterNext = document.getElementById('tb-sb-roster-next');
    if (rosterNext) {
      rosterNext.addEventListener('click', function () {
        if (rosterNext.disabled) return;
        setChapter('review');
      });
    }
    var establish = document.getElementById('tb-sb-establish');
    if (establish && state.chapter === 'review') {
      establish.addEventListener('click', function () {
        if (establish.disabled) return;
        setChapter('establish');
      });
    }

    ensureChromeObserver();
    measureChrome();
  }

  function ensureIdentityChapter() {
    if (state.identityChapter) return state.identityChapter;
    state.identityChapter = new window.TeamBuilderIdentity.IdentityChapter({
      root: els.identity,
      getIdentity: function () {
        return state.identity;
      },
      setIdentity: function (next) {
        state.identity = mergeIdentity(next);
      },
      leagueAbbrs: leagueTakenAbbrs,
      onChange: function () {
        renderStatebar();
        scheduleSave();
      },
      onReadyChange: function () {
        renderStatebar();
      },
      onContinue: function () {
        setChapter('gate');
      },
      onBack: function () {
        window.location.href = claimUrl();
      },
    });
    state.identityChapter.mount();
    return state.identityChapter;
  }

  function ensureGateChapter() {
    // Remount when slot budgets or program name change so copy stays live.
    var stamp =
      String(state.identity.name || '') +
      '|' +
      String(state.identity.abbreviation || '') +
      '|' +
      String(state.shape.height_budget) +
      '|' +
      String(state.shape.class_budget) +
      '|' +
      String(state.buildMode || '');
    if (state.gateChapter && state._gateStamp === stamp) {
      state.gateChapter.sync();
      return state.gateChapter;
    }
    state._gateStamp = stamp;
    state.gateChapter = new window.TeamBuilderGate.GateChapter({
      root: els.gate,
      getContext: function () {
        return {
          programName: state.identity.name || 'Your program',
          abbr: state.identity.abbreviation || '—',
          replacedName: (state.replaced && state.replaced.name) || '—',
          conferenceLabel: conferenceLabel(state.replaced),
          heightBudget: state.shape.height_budget,
          classBudget: state.shape.class_budget,
        };
      },
      getMode: function () {
        return state.buildMode;
      },
      setMode: function (mode) {
        state.buildMode = normalizeMode(mode);
        scheduleSave();
      },
      onModeChange: function () {
        renderStatebar();
      },
      onContinue: async function () {
        if (!state.buildMode) return;
        try {
          await persistDraft({
            chapter: 'roster',
            build_mode: state.buildMode,
            identity: identityPayload(),
          });
        } catch (err) {
          console.warn('[TeamBuilder] could not lock build_mode', err);
        }
        setChapter('roster');
      },
      onBack: function () {
        setChapter('identity');
      },
    });
    state.gateChapter.mount();
    return state.gateChapter;
  }

  function ensureRosterChapter() {
    if (state.rosterChapter && state.rosterChapter.root === els.roster) {
      if (!state.rosterChapter.loaded && !state.rosterChapter.loading) {
        state.rosterChapter.mount();
      }
      return state.rosterChapter;
    }
    state.rosterChapter = new window.TeamBuilderRoster.RosterChapter({
      root: els.roster,
      host: {
        getReplacedObjectId: function () {
          return REPLACED_OID;
        },
        getDraftId: function () {
          return state.draftId;
        },
        getBuildMode: function () {
          return state.buildMode;
        },
        getShape: function () {
          return state.shape;
        },
        setShapeFromWalkOns: applyShapeFromWalkOns,
        getDraftRoster: function () {
          return state.draftRoster;
        },
      },
      onChange: function () {
        scheduleSave();
      },
      onStatusChange: function () {
        renderStatebar();
      },
      onEstablish: function () {
        setChapter('review');
      },
      onBackGate: function () {
        setChapter('gate');
      },
      onNavigateChapter: function (ch) {
        setChapter(ch);
      },
    });
    state.rosterChapter.mount();
    return state.rosterChapter;
  }

  function reviewHost() {
    return {
      getIdentity: function () {
        return state.identity;
      },
      getReplaced: function () {
        return state.replaced;
      },
      getBuildMode: function () {
        return state.buildMode;
      },
      getAllTeams: function () {
        return state.allTeams;
      },
      getRosterChapter: function () {
        return state.rosterChapter;
      },
    };
  }

  function ensureReviewChapter() {
    if (!state.rosterChapter || !state.rosterChapter.loaded) {
      ensureRosterChapter();
    }
    if (state.reviewChapter && state.reviewChapter.root === els.review && state.reviewChapter._mounted) {
      return state.reviewChapter;
    }
    state.reviewChapter = new window.TeamBuilderReview.ReviewChapter({
      root: els.review,
      host: reviewHost(),
      onBack: function () {
        setChapter('roster');
      },
      onEstablish: function () {
        setChapter('establish');
      },
    });
    state.reviewChapter.mount();
    state.reviewChapter._mounted = true;
    return state.reviewChapter;
  }

  function ensureEstablishChapter() {
    if (state.establishChapter && state.establishChapter._running) {
      return state.establishChapter;
    }
    if (state.establishChapter && typeof state.establishChapter.destroy === 'function') {
      state.establishChapter.destroy();
    }
    state.establishChapter = new window.TeamBuilderEstablish.EstablishChapter({
      root: els.establish,
      host: {
        getIdentity: function () {
          return state.identity;
        },
        getReplaced: function () {
          return state.replaced;
        },
        getBuildMode: function () {
          return state.buildMode;
        },
        getAllTeams: function () {
          return state.allTeams;
        },
        applyFranchise: applyFranchise,
      },
      onEnter: function (franchiseId) {
        var q = new URLSearchParams();
        q.set('franchise_id', String(franchiseId));
        window.location.href = '/franchise-command-center.html?' + q.toString();
      },
      onBack: function () {
        if (state.establishChapter) {
          state.establishChapter.destroy();
          state.establishChapter = null;
        }
        setChapter('review');
      },
      onError: function (msg) {
        console.error('[TeamBuilder] establish failed', msg);
      },
    });
    state.establishChapter.mount();
    return state.establishChapter;
  }

  function render() {
    els.identity.hidden = state.chapter !== 'identity';
    els.gate.hidden = state.chapter !== 'gate';
    els.roster.hidden = state.chapter !== 'roster';
    els.review.hidden = state.chapter !== 'review';
    els.establish.hidden = state.chapter !== 'establish';

    // Establish owns the viewport — hide shell chrome when active.
    if (els.app) {
      els.app.classList.toggle('establishing', state.chapter === 'establish');
      els.app.classList.toggle('reviewing', state.chapter === 'review');
      els.app.classList.toggle('gating', state.chapter === 'gate');
    }

    if (state.chapter === 'identity') {
      var chapter = ensureIdentityChapter();
      if (!chapter._paintedOnce) {
        chapter.paint();
        chapter._paintedOnce = true;
      } else {
        chapter.paintFields();
        chapter.paintPreviews();
        chapter.syncContinue();
      }
    } else if (state.chapter === 'gate') {
      ensureGateChapter();
    } else if (state.chapter === 'roster') {
      ensureRosterChapter();
    } else if (state.chapter === 'review') {
      ensureReviewChapter();
    } else if (state.chapter === 'establish') {
      ensureEstablishChapter();
    }

    renderStatebar();
  }

  async function loadExistingDraft() {
    try {
      var res = await fetch(API_CONFIG.buildUrl('/franchise/team-builder/drafts'), {
        headers: API_CONFIG.getAuthHeaders(),
      });
      if (!res.ok) return null;
      var data = await res.json();
      var drafts = data.drafts || [];
      for (var i = 0; i < drafts.length; i++) {
        if (String(drafts[i].replaced_object_id) === String(REPLACED_OID)) {
          return drafts[i];
        }
      }
    } catch (_) {}
    return null;
  }

  async function boot() {
    els.boot = document.getElementById('tb-boot');
    els.fatal = document.getElementById('tb-fatal');
    els.app = document.getElementById('tb-app');
    els.statebar = document.getElementById('tb-statebar');
    els.identity = document.getElementById('chapter-identity');
    els.gate = document.getElementById('chapter-gate');
    els.roster = document.getElementById('chapter-roster');
    els.review = document.getElementById('chapter-review');
    els.establish = document.getElementById('chapter-establish');

    if (!REPLACED_OID) {
      window.location.replace(claimUrl());
      return;
    }

    // Hydration gate — every entry, including mid-flow deep links.
    if (typeof ensureTeamBuilderChromeSnapshot === 'function') {
      try {
        await ensureTeamBuilderChromeSnapshot();
      } catch (err) {
        console.warn('[TeamBuilder] chrome snapshot failed', err);
      }
    }

    try {
      state.allTeams =
        window.TeamPicker && typeof TeamPicker.fetchTeams === 'function'
          ? await TeamPicker.fetchTeams()
          : [];
    } catch (err) {
      showFatal(err.message || 'Could not load league programs.');
      return;
    }

    state.replaced =
      state.allTeams.find(function (t) {
        return String(t.object_id) === String(REPLACED_OID);
      }) || null;
    if (!state.replaced) {
      showFatal('That program is not in the league.');
      return;
    }

    var existing = await loadExistingDraft();
    if (existing) {
      state.draftId = existing.draft_id || state.draftId;
      if (existing.identity) state.identity = mergeIdentity(existing.identity);
      if (existing.build_mode) state.buildMode = normalizeMode(existing.build_mode);
      if (existing.roster && typeof existing.roster === 'object') {
        state.draftRoster = existing.roster;
      }
      if (existing.chapter && !params.get('chapter')) {
        state.chapter = normalizeChapter(existing.chapter);
      }
    }

    if (!String(state.identity.name || '').trim()) {
      // Soft start — empty fields; Surprise me fills a starting point.
      state.identity.abbreviation = '';
    }

    try {
      await upsertDraft({
        chapter: state.chapter,
        identity: identityPayload(),
        build_mode: state.buildMode || undefined,
      });
    } catch (err) {
      showFatal(err.message || 'Could not open draft.');
      return;
    }

    try {
      await loadShapeBudgets();
    } catch (err) {
      console.warn('[TeamBuilder] shape budgets unavailable', err);
    }

    els.boot.hidden = true;
    els.app.hidden = false;
    setChapter(state.chapter, { replace: true });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
