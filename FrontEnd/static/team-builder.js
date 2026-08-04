(function () {
  'use strict';

  const params = new URLSearchParams(window.location.search);
  const HOME_SLOT = (function () {
    const n = parseInt(params.get('home_slot'), 10);
    return n === 1 || n === 2 ? n : null;
  })();

  const BUDGET = {
    ATTR_MIN: 5,
    ATTR_MAX: 99,
    TOPUP_FLOOR: 60,
    MAX_PLAYERS: 15,
    // Height range filled from server shape payload (§10) — not hardcoded domain.
    HEIGHT_MIN: 66,
    HEIGHT_MAX: 84,
  };


  const CORE_12 = ['SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'ST', 'AG', 'ND', 'IQ', 'FT'];

  const FIELD_ALIASES = {
    first_name: ['first_name', 'firstname', 'first', 'fname', 'given_name'],
    last_name: ['last_name', 'lastname', 'last', 'lname', 'surname', 'family_name'],
    class_year: ['class_year', 'class', 'year', 'classyear', 'yr'],
    height_in: ['height_in', 'height', 'ht'],
    weight_lb: ['weight_lb', 'weight', 'wt'],
    jersey: ['jersey', 'number', 'jersey_number', 'num', '#'],
    team_name: ['team_name', 'school_name', 'school', 'program_name'],
    mascot: ['mascot'],
    primary_color: ['primary_color', 'primary', 'color_primary'],
    secondary_color: ['secondary_color', 'secondary', 'color_secondary'],
    position: ['position', 'pos'],
  };

  CORE_12.forEach(function (a) {
    FIELD_ALIASES[a] = [a.toLowerCase(), a];
  });

  const MAP_TARGETS = [
    'first_name',
    'last_name',
    'class_year',
    'height_in',
    'weight_lb',
    'jersey',
    'position',
    'team_name',
    'mascot',
    'primary_color',
    'secondary_color',
  ].concat(CORE_12);

  const YEAR_TO_CLASS = {
    freshman: 'FR',
    sophomore: 'SO',
    junior: 'JR',
    senior: 'SR',
  };

  const CLASS_YEAR_MAP = {
    FR: 'FR',
    FRESHMAN: 'FR',
    FRESH: 'FR',
    '1': 'FR',
    F: 'FR',
    SO: 'SO',
    SOPHOMORE: 'SO',
    SOPH: 'SO',
    '2': 'SO',
    JR: 'JR',
    JUNIOR: 'JR',
    '3': 'JR',
    J: 'JR',
    SR: 'SR',
    SENIOR: 'SR',
    '4': 'SR',
  };

  const YEAR_CANONICAL = {
    FR: 'freshman',
    SO: 'sophomore',
    JR: 'junior',
    SR: 'senior',
  };

  function formatHeightFtIn(inches) {
    const n = parseInt(inches, 10);
    if (isNaN(n)) return '—';
    const ft = Math.floor(n / 12);
    const inch = n % 12;
    return ft + "'" + inch + '"';
  }

  function classRankFromYear(year) {
    // Rank table is server-shipped domain data (state.shape.class_rank).
    const cy = normalizeClassYear(year);
    const ranks = (state.shape && state.shape.class_rank) || {};
    return cy && ranks[cy] != null ? Number(ranks[cy]) : 0;
  }

  function weightLabelForPlayer(player) {
    if (!player) return '—';
    if (player.height_edited) return 'Set at creation';
    const w =
      player.inherited_weight_lb != null && player.inherited_weight_lb !== ''
        ? player.inherited_weight_lb
        : player.weight_lb;
    return w != null && w !== '' ? String(w) : '—';
  }

  function currentHeightClassTotals(players) {
    // Aggregate form values for meter display against server-shipped budgets.
    const list = players || [];
    let heightTotal = 0;
    let classTotal = 0;
    list.forEach(function (p) {
      const h = parseInt(p.height_in, 10);
      if (!isNaN(h)) heightTotal += h;
      classTotal += classRankFromYear(p.class_year);
    });
    return { heightTotal: heightTotal, classTotal: classTotal };
  }


  const FRANCHISE_CAP_DEFAULT = 2;

  const state = {
    step: 0,
    franchiseCap: {
      blocked: false,
      max: FRANCHISE_CAP_DEFAULT,
      count: 0,
      message: '',
    },
    slot: null,
    identity: {
      name: '',
      abbreviation: '',
      mascot: '',
    },
    colors: {
      primary: '#27408E',
      secondary: '#15181f',
      jersey_preset: 1,
      court: {
        hardwoodStyle: 'medium_medium',
        oobColor: '#1a1a1a',
        laneColor: '#27408E',
        outsideWoodColor: '#DBB891',
        halfArcFillColor: '#15181f',
      },
    },
    roster_mode: 'edit',
    attribute_mode: 'capped',
    slotPlayers: null,
    // §4.5a: three walk-ons from generate_walk_on_profile(), idempotent per draft+slot.
    draftId: null,
    wizardWalkOns: null,
    wizardWalkOnsLoading: false,
    editor: { players: [], inherited: [], loaded: false },
    // §10 — height/class budgets + class_rank table shipped from the server.
    shape: {
      height_budget: null,
      class_budget: null,
      class_rank: null,
      loaded: false,
    },
    // §6.5: wizard-minted player_id + image_id; portrait shown must ship.
    portraits: [],
    portraitPicker: { slot: null, skin: null, frame: null, definition: null, catalog: null },
    _portraitSyncTimer: null,
    _portraitSyncPromise: null,
    abbrConflict: null,
    allTeams: [],
    import: {
      rawRows: [],
      headers: [],
      hasHeaderRow: true,
      columnMap: {},
      rowErrors: [],
      rowWarnings: [],
      skippedRows: [],
      validPlayers: [],
      importedPlayers: null,
      importSummary: null,
      committed: false,
      parts: { identity: true, roster: true },
      tooManyRows: 0,
      wrongSize: false,
      budgetWarnings: [],
      cappedTooLong: false,
    },
    budget: null,
    slotRosterAttrs: null,
    slotRosterLoading: false,
    // Runtime league context (Decision #5) — never hardcoded.
    league: {
      team_pool: 0,
      team_median: 0,
      team_best: 0,
      loaded: false,
    },
  };

  /** Set once court colour controls are bound — re-arms hardwood→outside sync. */
  let armOutsideWoodAutoSyncFromDom = function () {};

  function leaguePool() {
    return state.league.team_pool || 0;
  }

  function leagueMedian() {
    return state.league.team_median || 0;
  }

  function formatPool(n) {
    return (Number(n) || 0).toLocaleString();
  }

  function inheritedRosterCount() {
    // Authored roster is always 15 once the slot + wizard walk-ons are ready.
    if (state.slotPlayers && state.slotPlayers.length) return state.slotPlayers.length;
    if (state.slotRosterAttrs && state.slotRosterAttrs.length) return state.slotRosterAttrs.length;
    return BUDGET.MAX_PLAYERS;
  }

  function rosterSizeInvalidMessage(offered, required) {
    return (
      'A roster holds ' +
      required +
      ' players. Your file has ' +
      offered +
      '. Supply exactly ' +
      required +
      ' — not truncated, not padded.'
    );
  }

  function currentBudgetBlockReason() {
    if (state.import.wrongSize || state.import.cappedTooLong) {
      return rosterSizeInvalidMessage(
        state.import.validPlayers.length,
        BUDGET.MAX_PLAYERS
      );
    }
    if (!state.budget) return '';
    if (state.attribute_mode === 'uncapped' && state.budget.over_pool_by > 0) {
      return (
        'Team pool is ' +
        state.budget.over_pool_by +
        ' over the league maximum (' +
        formatPool(leaguePool()) +
        '). Trim attributes — Apply is blocked until you\'re within the pool.'
      );
    }
    if (state.attribute_mode === 'capped' && state.budget.per_player_over_by > 0) {
      return (
        'One or more players exceed their inherited budget by ' +
        state.budget.per_player_over_by +
        ' total points. Points cannot move between players — trim within each player.'
      );
    }
    if (state.attribute_mode === 'capped') {
      if (state.budget.height_over_by > 0) {
        return (
          'Team height is ' +
          state.budget.height_over_by +
          '" over the inherited total (' +
          state.budget.height_total +
          '" / ' +
          state.budget.height_budget +
          '"). Shorten players — under is allowed; over is not.'
        );
      }
      if (state.budget.class_delta !== 0 && state.budget.class_budget != null) {
        const d = state.budget.class_delta;
        if (d > 0) {
          return (
            'Class total is ' +
            d +
            ' over the inherited spend (' +
            state.budget.class_total +
            ' vs ' +
            state.budget.class_budget +
            '). Drop seniority until it matches exactly.'
          );
        }
        return (
          'Class total is ' +
          -d +
          ' under the inherited spend (' +
          state.budget.class_total +
          ' vs ' +
          state.budget.class_budget +
          '). Add seniority until it matches exactly.'
        );
      }
    }
    return '';
  }

  function syncBudgetRefuseUI() {
    const reason = currentBudgetBlockReason();
    const blocked = !!reason;
    ['tb-budget-refuse', 'tb-budget-refuse-apply'].forEach(function (id) {
      const el = document.getElementById(id);
      if (!el) return;
      if (blocked) {
        el.hidden = false;
        el.textContent = reason;
      } else {
        el.hidden = true;
        el.textContent = '';
      }
    });
    ['tb-next-review', 'tb-apply', 'tb-confirm-apply'].forEach(function (id) {
      const btn = document.getElementById(id);
      if (!btn) return;
      if (state.franchiseCap.blocked) return;
      btn.classList.toggle('is-blocked-budget', blocked);
      if (blocked) {
        btn.setAttribute('aria-disabled', 'true');
        btn.title = reason;
      } else if (!state.franchiseCap.blocked) {
        btn.removeAttribute('aria-disabled');
        if (btn.id !== 'tb-apply' && btn.id !== 'tb-confirm-apply') btn.removeAttribute('title');
      }
    });
  }

  async function fetchLeagueContext() {
    try {
      const res = await fetch(API_CONFIG.buildUrl('/franchise/team-builder/league-context'), {
        headers: API_CONFIG.getAuthHeaders(),
      });
      if (!res.ok) throw new Error('league-context failed');
      const data = await res.json();
      state.league.team_pool = Number(data.team_pool) || 0;
      state.league.team_median = Number(data.team_median) || 0;
      state.league.team_best = Number(data.team_best) || state.league.team_pool;
      state.league.loaded = true;
      const uncappedCopy = document.getElementById('tb-uncapped-mode-copy');
      if (uncappedCopy && state.league.team_pool) {
        uncappedCopy.textContent =
          'One team pool of ' +
          formatPool(state.league.team_pool) +
          ' points (best program in the league), free across the roster. Not eligible for online play.';
      }
      updateBudgetFromCurrentRoster();
    } catch (_) {
      state.league.loaded = false;
    }
  }

  const errorHost = document.getElementById('tb-error');
  const applyErrorHost = document.getElementById('tb-apply-error');
  const panels = {
    0: document.getElementById('tb-step-0'),
    1: document.getElementById('tb-step-1'),
    2: document.getElementById('tb-step-2'),
    3: document.getElementById('tb-step-3'),
    4: document.getElementById('tb-step-4'),
  };

  function franchiseCapMessage(count, max) {
    const n = Number(max) || FRANCHISE_CAP_DEFAULT;
    const have = Number(count) || n;
    return (
      'You already have ' +
      have +
      ' active franchise' +
      (have === 1 ? '' : 's') +
      ' (limit ' +
      n +
      '). Delete one on Mode Select, then come back to Team Builder.'
    );
  }

  function setErrorHost(host, msg, asHtml) {
    if (!host) return;
    if (!msg) {
      host.hidden = true;
      host.textContent = '';
      host.innerHTML = '';
      return;
    }
    host.hidden = false;
    if (asHtml) host.innerHTML = msg;
    else host.textContent = msg;
  }

  function showError(msg, options) {
    options = options || {};
    const asHtml = !!options.html;
    const nearApply = !!options.nearApply || state.step === 4;
    setErrorHost(errorHost, nearApply ? '' : msg, asHtml);
    setErrorHost(applyErrorHost, nearApply ? msg : '', asHtml);
    if (!msg) return;
    const target = nearApply && applyErrorHost ? applyErrorHost : errorHost;
    if (target && typeof target.scrollIntoView === 'function') {
      try {
        target.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      } catch (_) {
        target.scrollIntoView();
      }
    }
  }

  function updateApplyButtonState() {
    const reason = state.franchiseCap.blocked ? state.franchiseCap.message : '';
    ['tb-apply', 'tb-confirm-apply'].forEach(function (id) {
      const btn = document.getElementById(id);
      if (!btn) return;
      btn.disabled = !!state.franchiseCap.blocked;
      if (reason) {
        btn.title = reason;
        btn.setAttribute('aria-disabled', 'true');
      } else {
        btn.removeAttribute('title');
        btn.removeAttribute('aria-disabled');
      }
    });
  }

  function applyFranchiseCapBlock() {
    const block = document.getElementById('tb-cap-block');
    const copy = document.getElementById('tb-cap-block-copy');
    const stepsNav = document.querySelector('.tb-steps');
    if (copy) copy.textContent = state.franchiseCap.message;
    if (block) block.hidden = false;
    if (stepsNav) stepsNav.hidden = true;
    Object.keys(panels).forEach(function (k) {
      const el = panels[k];
      if (el) el.hidden = true;
    });
    updateApplyButtonState();
  }

  async function checkFranchiseCapAtEntry() {
    try {
      const res = await fetch(API_CONFIG.buildUrl('/franchise/list'), {
        headers: API_CONFIG.getAuthHeaders(),
      });
      if (!res.ok) return false;
      const data = await res.json();
      const list = Array.isArray(data && data.franchises)
        ? data.franchises
        : Array.isArray(data)
          ? data
          : [];
      const max = Number(data && data.max) || FRANCHISE_CAP_DEFAULT;
      const count = list.length;
      state.franchiseCap.max = max;
      state.franchiseCap.count = count;
      if (count >= max) {
        state.franchiseCap.blocked = true;
        state.franchiseCap.message = franchiseCapMessage(count, max);
        applyFranchiseCapBlock();
        return true;
      }
    } catch (_) {
      /* Cap check is best-effort; Apply still enforces server-side. */
    }
    updateApplyButtonState();
    return false;
  }

  function userProgramName() {
    return (state.identity.name || '').trim() || 'Your program';
  }

  function setStep(n) {
    state.step = n;
    Object.keys(panels).forEach(function (k) {
      const el = panels[k];
      if (!el) return;
      const active = Number(k) === n;
      el.hidden = !active;
      el.classList.toggle('is-active', active);
    });
    document.querySelectorAll('.tb-step').forEach(function (btn) {
      const s = Number(btn.dataset.step);
      btn.classList.toggle('is-active', s === n);
      btn.disabled = s > n && !(state.slot && s <= 4);
    });
    if (n === 2) refreshColorPreviews();
    if (n === 3) refreshRosterStep();
    if (n === 4) renderReview();
    showError('');
  }

  function confLabel(team) {
    if (window.TeamPicker && TeamPicker.formatConferenceMeta) {
      return TeamPicker.formatConferenceMeta(team);
    }
    return 'Conference ' + (team.conference || '?');
  }

  function renderSlotConfirm(team, host) {
    const userName = userProgramName();
    const replaced = team.name;
    const conf = confLabel(team);
    host.innerHTML =
      '<p><strong>' +
      escapeHtml(userName) +
      ' will replace ' +
      escapeHtml(replaced) +
      '.</strong></p>' +
      '<p>You keep ' +
      escapeHtml(replaced) +
      "'s spot in " +
      escapeHtml(conf) +
      ', their schedule, and their rivalries. Your record starts fresh at 0–0.</p>' +
      '<p>' +
      escapeHtml(replaced) +
      " won't appear in this franchise.</p>";
  }

  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function normalizeHeaderKey(h) {
    return String(h || '')
      .trim()
      .toLowerCase()
      .replace(/[\s-]+/g, '_')
      .replace(/[^\w#]/g, '');
  }

  function resolveFieldFromHeader(header) {
    const key = normalizeHeaderKey(header);
    if (!key) return null;
    for (let i = 0; i < MAP_TARGETS.length; i++) {
      const field = MAP_TARGETS[i];
      const aliases = FIELD_ALIASES[field] || [field.toLowerCase()];
      for (let j = 0; j < aliases.length; j++) {
        if (normalizeHeaderKey(aliases[j]) === key) return field;
      }
    }
    return null;
  }

  function parseCsvText(text) {
    const rows = [];
    let row = [];
    let field = '';
    let inQuotes = false;
    for (let i = 0; i < text.length; i++) {
      const c = text[i];
      const next = text[i + 1];
      if (inQuotes) {
        if (c === '"' && next === '"') {
          field += '"';
          i++;
        } else if (c === '"') {
          inQuotes = false;
        } else {
          field += c;
        }
      } else if (c === '"') {
        inQuotes = true;
      } else if (c === ',') {
        row.push(field);
        field = '';
      } else if (c === '\r' && next === '\n') {
        row.push(field);
        rows.push(row);
        row = [];
        field = '';
        i++;
      } else if (c === '\n' || c === '\r') {
        row.push(field);
        rows.push(row);
        row = [];
        field = '';
      } else {
        field += c;
      }
    }
    row.push(field);
    if (row.length > 1 || (row.length === 1 && row[0] !== '')) rows.push(row);
    return rows;
  }

  function core12Total(attrs) {
    if (!attrs) return 0;
    let total = 0;
    CORE_12.forEach(function (key) {
      const v = attrs[key];
      const n = parseInt(v, 10);
      if (!isNaN(n)) total += n;
    });
    return total;
  }

  function clampAttr(value) {
    const n = parseInt(value, 10);
    if (isNaN(n)) return BUDGET.ATTR_MIN;
    return Math.max(BUDGET.ATTR_MIN, Math.min(BUDGET.ATTR_MAX, n));
  }

  function lowestCore12Key(attrs) {
    let best = CORE_12[0];
    CORE_12.forEach(function (k) {
      if (attrs[k] < attrs[best] || (attrs[k] === attrs[best] && k < best)) best = k;
    });
    return best;
  }

  function highestCore12Key(attrs) {
    let best = CORE_12[0];
    CORE_12.forEach(function (k) {
      if (attrs[k] > attrs[best] || (attrs[k] === attrs[best] && k > best)) best = k;
    });
    return best;
  }

  function applyCappedTopup(rawAttrs) {
    const raw = rawAttrs || {};
    const rawTotal = core12Total(raw);
    const toppedUp = rawTotal < BUDGET.TOPUP_FLOOR;
    const budget = toppedUp ? BUDGET.TOPUP_FLOOR : Math.max(0, rawTotal);
    const attrs = {};
    CORE_12.forEach(function (key) {
      attrs[key] = clampAttr(raw[key]);
    });
    let total = core12Total(attrs);
    let guard = 0;
    while (total < budget && guard < 2000) {
      guard += 1;
      const key = lowestCore12Key(attrs);
      if (attrs[key] >= BUDGET.ATTR_MAX) break;
      attrs[key] += 1;
      total += 1;
    }
    guard = 0;
    while (total > budget && guard < 2000) {
      guard += 1;
      const key = highestCore12Key(attrs);
      if (attrs[key] <= BUDGET.ATTR_MIN) break;
      attrs[key] -= 1;
      total -= 1;
    }
    return {
      attrs: attrs,
      raw_total: rawTotal,
      budget: budget,
      topped_up: toppedUp,
    };
  }

  function attrsWithModeTopup(attrs) {
    if (state.attribute_mode === 'capped') {
      return applyCappedTopup(attrs).attrs;
    }
    const out = {};
    CORE_12.forEach(function (k) {
      out[k] = clampAttr(attrs[k]);
    });
    return out;
  }

  function evaluateModeRoster(attributeMode, playerAttrsList, perPlayerBudgets, playersForShape) {
    const mode = attributeMode === 'uncapped' ? 'uncapped' : 'capped';
    const eligible = mode === 'capped';
    const totals = (playerAttrsList || []).map(core12Total);
    const teamTotal = totals.reduce(function (s, t) {
      return s + t;
    }, 0);
    const pool = leaguePool();
    const overPool = mode === 'uncapped' && pool > 0 ? Math.max(0, teamTotal - pool) : 0;
    let perPlayerOver = 0;
    if (mode === 'capped' && perPlayerBudgets) {
      for (let i = 0; i < playerAttrsList.length; i++) {
        const spent = core12Total(playerAttrsList[i]);
        const cap = parseInt(perPlayerBudgets[i], 10) || 0;
        if (spent > cap) perPlayerOver += spent - cap;
      }
    }
    const shapePlayers = playersForShape || [];
    const hc = currentHeightClassTotals(shapePlayers);
    const heightBudget =
      mode === 'capped' && state.shape.height_budget != null
        ? Number(state.shape.height_budget)
        : null;
    const classBudget =
      mode === 'capped' && state.shape.class_budget != null
        ? Number(state.shape.class_budget)
        : null;
    const heightOver =
      heightBudget != null ? Math.max(0, hc.heightTotal - heightBudget) : 0;
    const classDelta =
      classBudget != null ? hc.classTotal - classBudget : 0;
    return {
      attribute_mode: mode,
      online_eligible: eligible,
      team_total: teamTotal,
      team_pool: pool,
      over_pool_by: overPool,
      per_player_over_by: perPlayerOver,
      height_total: hc.heightTotal,
      class_total: hc.classTotal,
      height_budget: heightBudget,
      class_budget: classBudget,
      height_over_by: heightOver,
      class_delta: classDelta,
    };
  }

  function extractCore12FromPlayer(p) {
    const a = (p && p.attributes) || p || {};
    const out = {};
    CORE_12.forEach(function (k) {
      const v = a[k] != null ? a[k] : a[k.toLowerCase()];
      if (v != null) out[k] = v;
    });
    return out;
  }

  function classYearFromPlayer(p) {
    // /roster returns abbreviations (FR/SO/JR/SR); full names also appear on drafts.
    if (p.class_year) return normalizeClassYear(p.class_year);
    const fromAbbrev = normalizeClassYear(p.year);
    if (fromAbbrev) return fromAbbrev;
    const y = String(p.year || '').toLowerCase();
    return YEAR_TO_CLASS[y] || null;
  }

  function buildEditorPlayerFromApi(p, attributeMode) {
    const rawAttrs = extractCore12FromPlayer(p);
    let attrs;
    let rawTotal;
    let budget;
    let toppedUp;
    if (attributeMode === 'capped') {
      const topup = applyCappedTopup(rawAttrs);
      attrs = Object.assign({}, topup.attrs);
      rawTotal = topup.raw_total;
      budget = topup.budget;
      toppedUp = topup.topped_up;
    } else {
      attrs = {};
      CORE_12.forEach(function (k) {
        attrs[k] = clampAttr(rawAttrs[k]);
      });
      rawTotal = core12Total(rawAttrs);
      budget = null;
      toppedUp = false;
    }
    const rawHeight = p.height_in != null ? p.height_in : p.height != null ? p.height : '';
    const heightClamped = (function () {
      const n = parseInt(rawHeight, 10);
      if (isNaN(n)) return '';
      return Math.max(BUDGET.HEIGHT_MIN, Math.min(BUDGET.HEIGHT_MAX, n));
    })();
    const rawWeight = p.weight_lb != null ? p.weight_lb : p.weight != null ? p.weight : '';
    return {
      first_name: p.first_name || '',
      last_name: p.last_name || '',
      class_year: classYearFromPlayer(p) || 'FR',
      height_in: heightClamped,
      inherited_height_in: heightClamped,
      weight_lb: rawWeight,
      inherited_weight_lb: rawWeight,
      height_edited: false,
      jersey: p.jersey != null ? p.jersey : '',
      attrs: attrs,
      raw_total: rawTotal,
      budget: budget,
      topped_up: toppedUp,
      inheritedAttrs: Object.assign({}, attrs),
      walk_on: !!p.walk_on || p.archetype === 'Walk On',
      entry_tier: p.entry_tier || null,
      position_intent: p.position_intent || null,
      development: p.development != null ? p.development : null,
      player_id: p.player_id || p.wizard_player_id || null,
      image_id: p.image_id || null,
      portrait_locked: false,
    };
  }

  function cloneEditorPlayers(list) {
    return (list || []).map(function (p) {
      return JSON.parse(JSON.stringify(p));
    });
  }

  function editorPlayersToImportPayload() {
    return state.editor.players.map(function (p) {
      const out = {
        first_name: String(p.first_name || '').trim(),
        last_name: String(p.last_name || '').trim(),
        class_year: p.class_year,
        attributes: Object.assign({}, p.attrs),
      };
      const h = parseInt(p.height_in, 10);
      if (!isNaN(h)) out.height_in = h;
      // §10.3b — weight is server-derived at Apply; never ship a client figure after height edit.
      if (!p.height_edited) {
        const w = parseInt(p.weight_lb, 10);
        if (!isNaN(w)) out.weight_lb = w;
      }
      const j = parseInt(p.jersey, 10);
      if (!isNaN(j)) out.jersey = j;
      if (p.player_id) out.player_id = p.player_id;
      if (p.image_id) out.image_id = p.image_id;
      if (p.walk_on) {
        out.walk_on = true;
        out.archetype = 'Walk On';
        out.entry_tier = p.entry_tier || 'Poor';
        if (p.position_intent) out.position_intent = p.position_intent;
        if (p.development != null) out.development = p.development;
      }
      if (p.budget != null) out.budget = p.budget;
      return out;
    });
  }

  function portraitPlayersPayload() {
    const source =
      state.roster_mode === 'import' && state.import.importedPlayers && state.import.importedPlayers.length
        ? state.import.importedPlayers
        : state.editor.players;
    return (source || []).map(function (p) {
      const attrs = p.attrs || p.attributes || {};
      return {
        first_name: String(p.first_name || '').trim(),
        last_name: String(p.last_name || '').trim(),
        class_year: p.class_year || null,
        height_in: parseInt(p.height_in != null ? p.height_in : p.height, 10) || null,
        // §10.3b — never send a client-derived weight; omit when height was edited.
        weight_lb: p.height_edited
          ? null
          : parseInt(p.weight_lb != null ? p.weight_lb : p.weight, 10) || null,
        attributes: Object.assign({}, attrs),
        player_id: p.player_id || null,
        image_id: p.image_id || null,
      };
    });
  }

  function applyPortraitsToRoster(portraits) {
    state.portraits = portraits || [];
    const applyTo = function (list) {
      if (!list || !list.length) return;
      state.portraits.forEach(function (row) {
        const idx = row.slot != null ? row.slot : state.portraits.indexOf(row);
        if (!list[idx]) return;
        list[idx].player_id = row.player_id;
        list[idx].image_id = row.image_id;
        if (row.source === 'picker' || row.source === 'upload') {
          list[idx].portrait_locked = true;
        }
        list[idx].portrait_meta = {
          frame: row.frame,
          definition: row.definition,
          skin: row.skin,
          match_stage: row.match_stage,
          source: row.source,
        };
      });
    };
    applyTo(state.editor.players);
    applyTo(state.import.importedPlayers);
  }

  function portraitThumbUrl(imageId) {
    if (!imageId || !window.API_CONFIG || !API_CONFIG.getRecruitImageUrl) {
      return window.API_CONFIG && API_CONFIG.getGenericHeadshotUrl
        ? API_CONFIG.getGenericHeadshotUrl({ size: 'thumb' })
        : '';
    }
    return API_CONFIG.getRecruitImageUrl(imageId, { size: 'thumb' });
  }

  function bindPortraitImg(img, imageId) {
    if (!img || !imageId) return;
    img.src = portraitThumbUrl(imageId);
    img.onerror = function () {
      if (!window.API_CONFIG || !API_CONFIG.ensureRecruitImage) {
        img.src = API_CONFIG.getGenericHeadshotUrl({ size: 'thumb' });
        return;
      }
      API_CONFIG.ensureRecruitImage(imageId).then(function () {
        img.src = portraitThumbUrl(imageId) + '?r=1';
        img.onerror = function () {
          img.src = API_CONFIG.getGenericHeadshotUrl({ size: 'thumb' });
        };
      });
    };
  }

  async function syncPortraits(opts) {
    opts = opts || {};
    if (!state.slot) return null;
    const players = portraitPlayersPayload();
    if (players.length !== 15) return null;
    const incomplete = players.some(function (p) {
      if (!p.height_in || !p.first_name || !p.last_name) return true;
      // Weight may be omitted after a height edit (§10.3b) — server derives for classify.
      return false;
    });
    if (incomplete && !opts.force) return null;

    const body = {
      replaced_object_id: state.slot.object_id,
      draft_id: ensureDraftId(),
      players: players,
      force_reassign: !!opts.force,
    };
    if (opts.reassignSlots && opts.reassignSlots.length) {
      body.force_reassign_slots = opts.reassignSlots.slice();
    }
    const res = await fetch(API_CONFIG.buildUrl('/franchise/team-builder/portraits/assign'), {
      method: 'POST',
      headers: { ...API_CONFIG.getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) return null;
    const data = await res.json();
    applyPortraitsToRoster(data.portraits || []);
    if (state.roster_mode === 'edit') renderEditor();
    return data.portraits;
  }

  function schedulePortraitSync(opts) {
    if (state._portraitSyncTimer) clearTimeout(state._portraitSyncTimer);
    state._portraitSyncTimer = setTimeout(function () {
      state._portraitSyncTimer = null;
      syncPortraits(opts || {});
    }, 450);
  }

  async function rerollPortrait(slot) {
    const players = portraitPlayersPayload();
    if (players.length !== 15) return;
    const res = await fetch(API_CONFIG.buildUrl('/franchise/team-builder/portraits/reroll'), {
      method: 'POST',
      headers: { ...API_CONFIG.getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({
        replaced_object_id: state.slot.object_id,
        draft_id: ensureDraftId(),
        slot: slot,
        players: players,
      }),
    });
    if (!res.ok) return;
    const data = await res.json();
    applyPortraitsToRoster(data.portraits || []);
    renderEditor();
  }

  async function openPortraitPicker(slot) {
    state.portraitPicker = {
      slot: slot,
      skin: null,
      frame: null,
      definition: null,
      catalog: null,
    };
    const modal = document.getElementById('tb-portrait-modal');
    const title = document.getElementById('tb-portrait-modal-title');
    const p = state.editor.players[slot];
    if (title) {
      title.textContent = p
        ? 'Portrait for ' + (p.first_name || '') + ' ' + (p.last_name || '')
        : 'Choose a portrait';
    }
    if (modal) modal.hidden = false;
    await refreshPortraitCatalog();
  }

  async function refreshPortraitCatalog() {
    const pp = state.portraitPicker;
    const params = new URLSearchParams();
    if (pp.skin) params.set('skin', pp.skin);
    if (pp.frame) params.set('frame', pp.frame);
    if (pp.definition) params.set('definition', pp.definition);
    const url =
      API_CONFIG.buildUrl('/franchise/team-builder/portraits/catalog') +
      (params.toString() ? '?' + params.toString() : '');
    const res = await fetch(url, { headers: API_CONFIG.getAuthHeaders() });
    if (!res.ok) return;
    const catalog = await res.json();
    state.portraitPicker.catalog = catalog;
    renderPortraitPicker(catalog);
  }

  function renderPortraitPicker(catalog) {
    const filters = document.getElementById('tb-portrait-filters');
    const grid = document.getElementById('tb-portrait-grid');
    const empty = document.getElementById('tb-portrait-empty');
    if (!filters || !grid || !empty) return;
    const pp = state.portraitPicker;
    const counts = (catalog && catalog.counts) || { skin: {}, frame: {}, definition: {} };

    function chips(axis, selected, countMap) {
      let html =
        '<div class="tb-portrait-filter-row"><strong>' +
        axis +
        '</strong>';
      html +=
        '<button type="button" class="tb-portrait-chip' +
        (!selected ? ' is-selected' : '') +
        '" data-filter-axis="' +
        axis +
        '" data-filter-value="">All</button>';
      Object.keys(countMap)
        .sort()
        .forEach(function (key) {
          html +=
            '<button type="button" class="tb-portrait-chip' +
            (selected === key ? ' is-selected' : '') +
            '" data-filter-axis="' +
            axis +
            '" data-filter-value="' +
            escapeHtml(key) +
            '">' +
            escapeHtml(key) +
            ' (' +
            countMap[key] +
            ')</button>';
        });
      html += '</div>';
      return html;
    }

    filters.innerHTML =
      chips('skin', pp.skin, counts.skin || {}) +
      chips('frame', pp.frame, counts.frame || {}) +
      chips('definition', pp.definition, counts.definition || {});

    if (!catalog.filtered_count) {
      empty.hidden = false;
      empty.textContent =
        catalog.empty_reason ||
        'No portraits match these filters. Clear a filter or pick another combination.';
      grid.innerHTML = '';
      return;
    }
    empty.hidden = true;
    grid.innerHTML = (catalog.entries || [])
      .map(function (e) {
        return (
          '<button type="button" class="tb-portrait-pick" data-pick-image="' +
          escapeHtml(e.image_id) +
          '"><img alt="" data-image-id="' +
          escapeHtml(e.image_id) +
          '"><span>' +
          escapeHtml(e.frame + ' · ' + e.definition + ' · ' + e.skin) +
          '</span></button>'
        );
      })
      .join('');
    grid.querySelectorAll('img[data-image-id]').forEach(function (img) {
      bindPortraitImg(img, img.dataset.imageId);
    });
  }

  async function pickPortrait(imageId) {
    const slot = state.portraitPicker.slot;
    if (slot == null) return;
    const players = portraitPlayersPayload();
    const res = await fetch(API_CONFIG.buildUrl('/franchise/team-builder/portraits/pick'), {
      method: 'POST',
      headers: { ...API_CONFIG.getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({
        replaced_object_id: state.slot.object_id,
        draft_id: ensureDraftId(),
        slot: slot,
        image_id: imageId,
        players: players,
      }),
    });
    if (!res.ok) return;
    const data = await res.json();
    applyPortraitsToRoster(data.portraits || []);
    document.getElementById('tb-portrait-modal').hidden = true;
    renderEditor();
  }

  function editorPerPlayerBudgets() {
    if (!state.editor.loaded || !state.editor.inherited.length) return null;
    return state.editor.inherited.map(function (p) {
      if (p.budget != null) return p.budget;
      return applyCappedTopup(p.attrs || p.inheritedAttrs || {}).budget;
    });
  }

  function slotPerPlayerBudgets() {
    if (!state.slotRosterAttrs || !state.slotRosterAttrs.length) return null;
    return state.slotRosterAttrs.map(function (a) {
      return applyCappedTopup(a).budget;
    });
  }

  function updateModePill() {
    const pill = document.getElementById('tb-mode-pill');
    if (!pill) return;
    pill.textContent =
      state.attribute_mode === 'capped'
        ? 'Capped · online eligible'
        : 'Uncapped · not eligible for online';
  }

  function hasModeSensitiveEdits() {
    if (state.roster_mode === 'edit' && state.editor.loaded) {
      return JSON.stringify(state.editor.players) !== JSON.stringify(state.editor.inherited);
    }
    if (state.roster_mode === 'import' && state.import.committed) return true;
    return false;
  }

  function setAttributeMode(mode, force) {
    const next = mode === 'uncapped' ? 'uncapped' : 'capped';
    if (next === state.attribute_mode) return true;
    if (!force && hasModeSensitiveEdits()) {
      const ok = window.confirm(
        'Switching modes re-bases allocations from the inherited roster. Continue?'
      );
      if (!ok) return false;
    }
    state.attribute_mode = next;
    document.querySelectorAll('.tb-mode-card').forEach(function (card) {
      card.classList.toggle('is-selected', card.dataset.attrMode === next);
    });
    updateModePill();
    const note = document.getElementById('tb-mode-switch-note');
    if (note) note.hidden = !hasModeSensitiveEdits();
    if (state.slotPlayers && state.roster_mode === 'edit') {
      initEditorFromSlot(true);
    }
    if (state.roster_mode === 'import' && state.import.validPlayers.length) {
      runValidation(false);
    }
    updateBudgetFromCurrentRoster();
    return true;
  }

  function initEditorFromSlot(rebase) {
    if (!state.slotPlayers || !state.slotPlayers.length) return;
    const built = state.slotPlayers.map(function (p) {
      return buildEditorPlayerFromApi(p, state.attribute_mode);
    });
    if (rebase || !state.editor.loaded) {
      state.editor.players = cloneEditorPlayers(built);
      state.editor.inherited = cloneEditorPlayers(built);
      state.editor.loaded = true;
    }
    renderEditor();
    syncPortraits();
  }

  function resetEditorPlayer(idx) {
    if (!state.editor.inherited[idx]) return;
    state.editor.players[idx] = JSON.parse(JSON.stringify(state.editor.inherited[idx]));
    renderEditor();
    updateBudgetFromCurrentRoster();
    schedulePortraitSync();
  }

  function resetAllEditor() {
    state.editor.players = cloneEditorPlayers(state.editor.inherited);
    renderEditor();
    updateBudgetFromCurrentRoster();
    schedulePortraitSync();
  }

  function refreshEditorPlayerBudgetChrome(idx) {
    const article = document.querySelector(
      '#tb-editor-host .tb-editor-player[data-player-idx="' + idx + '"]'
    );
    const p = state.editor.players[idx];
    if (!article || !p) return;
    const capped = state.attribute_mode === 'capped';
    const spent = core12Total(p.attrs);
    const over = capped && spent > (p.budget || 0);
    article.classList.toggle('is-over-budget', over);
    const badge = article.querySelector('.tb-player-budget');
    if (badge && capped) {
      badge.textContent = spent + ' / ' + p.budget;
      badge.classList.toggle('is-over', over);
    }
  }

  function renderEditor() {
    const host = document.getElementById('tb-editor-host');
    if (!host) return;
    if (!state.editor.players.length) {
      host.innerHTML = '<p class="tb-panel-copy">Loading inherited roster…</p>';
      return;
    }
    const capped = state.attribute_mode === 'capped';
    let html =
      '<p class="tb-weight-note">Weight is set from height when the franchise is created.</p>';
    state.editor.players.forEach(function (p, idx) {
      const spent = core12Total(p.attrs);
      const over = capped && spent > (p.budget || 0);
      html +=
        '<article class="tb-editor-player' +
        (over ? ' is-over-budget' : '') +
        '" data-player-idx="' +
        idx +
        '">';
      html += '<div class="tb-editor-player-head">';
      html += '<div class="tb-portrait-slot">';
      html +=
        '<img class="tb-portrait-thumb" alt="" data-portrait-img="' +
        idx +
        '"' +
        (p.image_id ? ' data-image-id="' + escapeHtml(p.image_id) + '"' : '') +
        '>';
      html += '<div class="tb-portrait-actions">';
      html +=
        '<button type="button" class="tb-btn tb-btn-secondary" data-portrait-reroll="' +
        idx +
        '">Re-roll</button>';
      html +=
        '<button type="button" class="tb-btn tb-btn-secondary" data-portrait-pick="' +
        idx +
        '">Pick…</button>';
      if (p.portrait_meta) {
        html +=
          '<span class="tb-portrait-meta">' +
          escapeHtml(
            (p.portrait_meta.frame || '') +
              ' · ' +
              (p.portrait_meta.definition || '') +
              ' · ' +
              (p.portrait_meta.skin || '')
          ) +
          '</span>';
      }
      html += '</div></div>';
      html +=
        '<input type="text" class="tb-editor-name" data-field="first_name" data-idx="' +
        idx +
        '" value="' +
        escapeHtml(p.first_name) +
        '" placeholder="First" maxlength="32">';
      html +=
        '<input type="text" class="tb-editor-name" data-field="last_name" data-idx="' +
        idx +
        '" value="' +
        escapeHtml(p.last_name) +
        '" placeholder="Last" maxlength="32">';
      html += '<select class="tb-editor-class" data-field="class_year" data-idx="' + idx + '">';
      ['FR', 'SO', 'JR', 'SR'].forEach(function (cy) {
        html +=
          '<option value="' +
          cy +
          '"' +
          (p.class_year === cy ? ' selected' : '') +
          '>' +
          cy +
          '</option>';
      });
      html += '</select>';
      html +=
        '<label class="tb-editor-meta">Ht<input type="number" data-field="height_in" data-idx="' +
        idx +
        '" value="' +
        escapeHtml(String(p.height_in)) +
        '" min="' +
        BUDGET.HEIGHT_MIN +
        '" max="' +
        BUDGET.HEIGHT_MAX +
        '"><span class="tb-height-ftin" data-height-label="' +
        idx +
        '">' +
        escapeHtml(formatHeightFtIn(p.height_in)) +
        '</span></label>';
      html +=
        '<label class="tb-editor-meta tb-weight-readonly">Wt<span class="tb-weight-value' +
        (p.height_edited ? ' is-pending' : '') +
        '" data-weight-label="' +
        idx +
        '" aria-readonly="true">' +
        escapeHtml(weightLabelForPlayer(p)) +
        '</span></label>';
      html +=
        '<label class="tb-editor-meta">#<input type="number" data-field="jersey" data-idx="' +
        idx +
        '" value="' +
        escapeHtml(String(p.jersey)) +
        '" min="0" max="99"></label>';
      if (capped) {
        html +=
          '<span class="tb-player-budget' +
          (over ? ' is-over' : '') +
          '">' +
          spent +
          ' / ' +
          p.budget +
          '</span>';
      }
      if (p.walk_on) {
        html += '<span class="tb-walk-on-tag">Walk-on</span>';
      }
      html +=
        '<button type="button" class="tb-btn tb-btn-secondary tb-editor-reset-one" data-reset-idx="' +
        idx +
        '">Reset</button>';
      html += '</div>';
      if (capped && p.topped_up) {
        html +=
          '<p class="tb-topup-notice">Topped up from ' +
          p.raw_total +
          ' — every player needs at least 5 in each attribute.</p>';
      }
      html += '<div class="tb-editor-attrs">';
      CORE_12.forEach(function (key) {
        html +=
          '<label class="tb-editor-attr"><span>' +
          key +
          '</span><input type="number" data-attr="' +
          key +
          '" data-idx="' +
          idx +
          '" value="' +
          (p.attrs[key] != null ? p.attrs[key] : BUDGET.ATTR_MIN) +
          '" min="' +
          BUDGET.ATTR_MIN +
          '" max="' +
          BUDGET.ATTR_MAX +
          '"></label>';
      });
      html += '</div></article>';
    });
    host.innerHTML = html;
    host.querySelectorAll('img[data-image-id]').forEach(function (img) {
      bindPortraitImg(img, img.dataset.imageId);
    });
  }

  function onEditorHostChange(e) {
    const t = e.target;
    if (!t || !t.dataset) return;
    const idx = parseInt(t.dataset.idx, 10);
    if (isNaN(idx) || !state.editor.players[idx]) return;

    if (t.dataset.attr) {
      const key = t.dataset.attr;
      const player = state.editor.players[idx];
      const prev = player.attrs[key];
      player.attrs[key] = clampAttr(t.value);
      // Capped: refuse any change that pushes the player past his inherited budget.
      if (state.attribute_mode === 'capped' && player.budget != null) {
        if (core12Total(player.attrs) > player.budget) {
          player.attrs[key] = prev;
        }
      }
      t.value = player.attrs[key];
      refreshEditorPlayerBudgetChrome(idx);
      updateBudgetFromCurrentRoster();
      schedulePortraitSync();
      return;
    }

    if (t.dataset.field) {
      const field = t.dataset.field;
      const player = state.editor.players[idx];
      if (field === 'class_year') {
        player.class_year = t.value;
        updateBudgetFromCurrentRoster();
        return;
      }
      if (field === 'height_in') {
        let h = parseInt(t.value, 10);
        if (isNaN(h)) {
          player.height_in = '';
          player.height_edited = true;
        } else {
          h = Math.max(BUDGET.HEIGHT_MIN, Math.min(BUDGET.HEIGHT_MAX, h));
          player.height_in = h;
          t.value = String(h);
          const inheritedH = parseInt(player.inherited_height_in, 10);
          player.height_edited = isNaN(inheritedH) || h !== inheritedH;
        }
        if (!player.height_edited) {
          player.weight_lb = player.inherited_weight_lb;
        }
        const ftEl = document.querySelector('[data-height-label="' + idx + '"]');
        if (ftEl) ftEl.textContent = formatHeightFtIn(player.height_in);
        const wtEl = document.querySelector('[data-weight-label="' + idx + '"]');
        if (wtEl) {
          wtEl.textContent = weightLabelForPlayer(player);
          wtEl.classList.toggle('is-pending', !!player.height_edited);
        }
        // §10.4: height edit re-runs portrait assignment unless user picked/uploaded.
        if (!player.portrait_locked) {
          player.image_id = null;
          player.portrait_meta = null;
          updateBudgetFromCurrentRoster();
          schedulePortraitSync({ reassignSlots: [idx] });
        } else {
          updateBudgetFromCurrentRoster();
          schedulePortraitSync();
        }
        return;
      }
      if (field === 'jersey') {
        player.jersey = t.value;
        return;
      }
      if (field === 'weight_lb') {
        // Read-only — ignore.
        return;
      }
      player[field] = t.value;
      if (field === 'first_name' || field === 'last_name') {
        schedulePortraitSync();
      }
    }
  }

  function onEditorHostClick(e) {
    const reroll = e.target.closest('[data-portrait-reroll]');
    if (reroll) {
      const idx = parseInt(reroll.dataset.portraitReroll, 10);
      if (!isNaN(idx)) rerollPortrait(idx);
      return;
    }
    const pick = e.target.closest('[data-portrait-pick]');
    if (pick) {
      const idx = parseInt(pick.dataset.portraitPick, 10);
      if (!isNaN(idx)) openPortraitPicker(idx);
      return;
    }
    const btn = e.target.closest('[data-reset-idx]');
    if (!btn) return;
    const idx = parseInt(btn.dataset.resetIdx, 10);
    if (!isNaN(idx)) resetEditorPlayer(idx);
  }

  function setBarFill(fillEl, barEl, value, cap) {
    const pct = cap > 0 ? Math.min(100, (value / cap) * 100) : 0;
    if (fillEl) fillEl.style.width = pct + '%';
    if (barEl) barEl.classList.toggle('is-over', value > cap);
  }

  function setMarker(el, value, scaleMax) {
    if (!el || !scaleMax) return;
    const pct = Math.max(0, Math.min(100, (value / scaleMax) * 100));
    el.style.left = pct + '%';
  }

  function placeLeagueMarkers(scaleMax) {
    const cap = scaleMax || leaguePool();
    setMarker(document.getElementById('tb-team-marker-median'), leagueMedian(), cap);
    setMarker(document.getElementById('tb-team-marker-best'), leaguePool(), cap);
  }

  function normalizeClassYear(raw) {
    const val = String(raw || '').trim();
    if (!val) return null;
    const key = val.toUpperCase().replace(/\./g, '');
    return CLASS_YEAR_MAP[key] || null;
  }

  function classYearError(rowNum, value) {
    return (
      'Row ' +
      rowNum +
      ' — class_year: "' +
      value +
      '" isn\'t a class year we recognize. Use FR, SO, JR, or SR. This row will be skipped.'
    );
  }

  function rowFieldError(rowNum, field, value, fix) {
    const shown = value === '' || value == null ? '(blank)' : value;
    return (
      'Row ' +
      rowNum +
      ' — ' +
      field +
      ': "' +
      shown +
      '" ' +
      fix +
      ' This row will be skipped.'
    );
  }

  function rowFieldWarning(rowNum, field, value, fix) {
    const shown = value === '' || value == null ? '(blank)' : value;
    return 'Row ' + rowNum + ' — ' + field + ': ' + shown + '. ' + fix;
  }

  function resetImportUi() {
    state.import.rawRows = [];
    state.import.headers = [];
    state.import.columnMap = {};
    state.import.rowErrors = [];
    state.import.rowWarnings = [];
    state.import.skippedRows = [];
    state.import.validPlayers = [];
    state.import.importedPlayers = null;
    state.import.importSummary = null;
    state.import.committed = false;
    state.import.tooManyRows = 0;
    state.import.wrongSize = false;
    state.import.budgetWarnings = [];
    state.import.cappedTooLong = false;

    ['tb-import-blocking', 'tb-import-progress', 'tb-column-map-wrap', 'tb-import-errors', 'tb-import-warnings', 'tb-too-many-rows', 'tb-parts-picker'].forEach(function (id) {
      const el = document.getElementById(id);
      if (el) el.hidden = true;
    });
    const status = document.getElementById('tb-import-status');
    if (status) status.textContent = '';
  }

  function autoMapColumns(headers) {
    const map = {};
    headers.forEach(function (h, idx) {
      map[idx] = resolveFieldFromHeader(h);
    });
    return map;
  }

  function mappedFields(columnMap) {
    const used = {};
    Object.keys(columnMap).forEach(function (k) {
      const f = columnMap[k];
      if (f) used[f] = true;
    });
    return used;
  }

  function renderColumnMapping() {
    const wrap = document.getElementById('tb-column-map-wrap');
    const tbody = document.querySelector('#tb-column-map tbody');
    if (!wrap || !tbody) return;
    tbody.innerHTML = '';
    state.import.headers.forEach(function (header, idx) {
      const tr = document.createElement('tr');
      const samples = state.import.rawRows
        .slice(0, 3)
        .map(function (row) {
          return row[idx] != null ? row[idx] : '';
        })
        .join(' · ');
      const mapped = state.import.columnMap[idx] || '';
      const status =
        mapped === 'first_name' || mapped === 'last_name' || mapped === 'class_year'
          ? 'Required field'
          : mapped
            ? 'Mapped'
            : 'Unmapped';
      const select = document.createElement('select');
      select.dataset.col = String(idx);
      const optSkip = document.createElement('option');
      optSkip.value = '';
      optSkip.textContent = "Don't import this column.";
      select.appendChild(optSkip);
      MAP_TARGETS.forEach(function (field) {
        const opt = document.createElement('option');
        opt.value = field;
        opt.textContent = field;
        if (mapped === field) opt.selected = true;
        select.appendChild(opt);
      });
      select.addEventListener('change', function () {
        state.import.columnMap[idx] = select.value || null;
        runValidation(false);
      });
      tr.innerHTML =
        '<td>' +
        escapeHtml(header || 'Column ' + (idx + 1)) +
        '</td><td>' +
        escapeHtml(samples || '—') +
        '</td><td></td><td>' +
        escapeHtml(status) +
        '</td>';
      tr.children[2].appendChild(select);
      tbody.appendChild(tr);
    });
    wrap.hidden = false;
  }

  function renderMessageList(hostId, messages, hiddenWhenEmpty) {
    const host = document.getElementById(hostId);
    if (!host) return;
    if (!messages.length) {
      host.hidden = hiddenWhenEmpty !== false;
      host.innerHTML = '';
      return;
    }
    host.hidden = false;
    host.innerHTML = messages.map(function (m) {
      return '<p>' + escapeHtml(m) + '</p>';
    }).join('');
  }

  function getRowObjects(dataRows) {
    const inv = {};
    Object.keys(state.import.columnMap).forEach(function (k) {
      const field = state.import.columnMap[k];
      if (field) inv[field] = Number(k);
    });
    return dataRows.map(function (row, i) {
      const obj = { _rowNum: i + (state.import.hasHeaderRow ? 2 : 1), _raw: row.slice() };
      Object.keys(inv).forEach(function (field) {
        obj[field] = row[inv[field]] != null ? String(row[inv[field]]).trim() : '';
      });
      return obj;
    });
  }

  function normalizeImportedPlayer(rowObj) {
    const cy = normalizeClassYear(rowObj.class_year);
    const attrs = {};
    CORE_12.forEach(function (key) {
      if (rowObj[key] !== undefined && rowObj[key] !== '') {
        const n = parseInt(rowObj[key], 10);
        if (!isNaN(n)) attrs[key] = n;
      }
    });
    const player = {
      first_name: rowObj.first_name,
      last_name: rowObj.last_name,
      class_year: cy,
      year: YEAR_CANONICAL[cy],
    };
    if (rowObj.height_in) {
      const h = parseInt(rowObj.height_in, 10);
      if (!isNaN(h)) player.height = h;
    }
    if (rowObj.weight_lb) {
      const w = parseInt(rowObj.weight_lb, 10);
      if (!isNaN(w)) player.weight = w;
    }
    if (rowObj.jersey) {
      const j = parseInt(rowObj.jersey, 10);
      if (!isNaN(j)) player.jersey = j;
    }
    if (Object.keys(attrs).length) player.attributes = attrs;
    return player;
  }

  function runValidation(showProgress) {
    const blockingHost = document.getElementById('tb-import-blocking');
    const progressHost = document.getElementById('tb-import-progress');
    const tooManyHost = document.getElementById('tb-too-many-rows');
    const partsHost = document.getElementById('tb-parts-picker');

    state.import.rowErrors = [];
    state.import.rowWarnings = [];
    state.import.skippedRows = [];
    state.import.validPlayers = [];
    state.import.budgetWarnings = [];
    if (blockingHost) blockingHost.hidden = true;

    const used = mappedFields(state.import.columnMap);
    if (!used.first_name) {
      if (blockingHost) {
        blockingHost.hidden = false;
        blockingHost.innerHTML =
          'No first_name column found. Your file needs first_name and last_name. <button type="button" class="tb-btn tb-btn-secondary tb-inline-dl">Download template</button>';
        const btn = blockingHost.querySelector('.tb-inline-dl');
        if (btn) btn.addEventListener('click', function () { downloadText('gob-roster-template.csv', blankTemplateCsv()); });
      }
      if (partsHost) partsHost.hidden = true;
      return;
    }
    if (!used.last_name) {
      if (blockingHost) {
        blockingHost.hidden = false;
        blockingHost.innerHTML =
          'No last_name column found. Your file needs first_name and last_name. <button type="button" class="tb-btn tb-btn-secondary tb-inline-dl">Download template</button>';
        const btn = blockingHost.querySelector('.tb-inline-dl');
        if (btn) btn.addEventListener('click', function () { downloadText('gob-roster-template.csv', blankTemplateCsv()); });
      }
      if (partsHost) partsHost.hidden = true;
      return;
    }
    if (!used.class_year) {
      if (blockingHost) {
        blockingHost.hidden = false;
        blockingHost.textContent =
          'No class_year column found. Your file needs class_year (FR, SO, JR, or SR). Download the template and try again.';
      }
      if (partsHost) partsHost.hidden = true;
      return;
    }

    // §4.5a: never truncate or pad — validate every row; size checked after.
    const dataRows = state.import.rawRows.slice();

    const total = dataRows.length;
    if (showProgress && progressHost) {
      progressHost.hidden = false;
      progressHost.textContent = 'Validating roster… 0 of ' + total + ' rows.';
    }

    const rowObjects = getRowObjects(dataRows);
    rowObjects.forEach(function (rowObj, idx) {
      if (showProgress && progressHost) {
        progressHost.textContent = 'Validating roster… ' + (idx + 1) + ' of ' + total + ' rows.';
      }
      let skip = false;

      if (!rowObj.first_name) {
        state.import.rowErrors.push(rowFieldError(rowObj._rowNum, 'first_name', rowObj.first_name, 'Add a first name.'));
        skip = true;
      }
      if (!rowObj.last_name) {
        state.import.rowErrors.push(rowFieldError(rowObj._rowNum, 'last_name', rowObj.last_name, 'Add a last name.'));
        skip = true;
      }
      if (!rowObj.class_year) {
        state.import.rowErrors.push(rowFieldError(rowObj._rowNum, 'class_year', rowObj.class_year, 'Use FR, SO, JR, or SR.'));
        skip = true;
      } else {
        const cy = normalizeClassYear(rowObj.class_year);
        if (!cy) {
          state.import.rowErrors.push(classYearError(rowObj._rowNum, rowObj.class_year));
          skip = true;
        } else {
          rowObj._classYearNorm = cy;
        }
      }

      if (!skip) {
        if (!rowObj.height_in) {
          state.import.rowWarnings.push(rowFieldWarning(rowObj._rowNum, 'height_in', rowObj.height_in, 'Blank — inherits from the replaced program.'));
        } else {
          const h = parseInt(rowObj.height_in, 10);
          if (isNaN(h) || h < BUDGET.HEIGHT_MIN || h > BUDGET.HEIGHT_MAX) {
            state.import.rowErrors.push(
              rowFieldError(
                rowObj._rowNum,
                'height_in',
                rowObj.height_in,
                'Use ' + BUDGET.HEIGHT_MIN + '–' + BUDGET.HEIGHT_MAX + ' inches.'
              )
            );
            skip = true;
          }
        }
        if (!rowObj.weight_lb) {
          state.import.rowWarnings.push(
            rowFieldWarning(
              rowObj._rowNum,
              'weight_lb',
              rowObj.weight_lb,
              'Weight is derived from height — blank is fine.'
            )
          );
        }
        if (!rowObj.jersey) {
          state.import.rowWarnings.push(rowFieldWarning(rowObj._rowNum, 'jersey', rowObj.jersey, 'Blank — inherits from the replaced program.'));
        }
        if (!skip) {
          state.import.validPlayers.push(normalizeImportedPlayer(rowObj));
        } else {
          state.import.skippedRows.push(rowObj);
        }
      } else {
        state.import.skippedRows.push(rowObj);
      }
    });

    if (showProgress && progressHost) progressHost.hidden = true;

    renderMessageList('tb-import-errors', state.import.rowErrors);
    renderMessageList('tb-import-warnings', state.import.rowWarnings);

    const attrsList = state.import.validPlayers.map(function (p) {
      return attrsWithModeTopup(p.attributes || {});
    });
    let budgets = null;
    if (state.attribute_mode === 'capped') {
      // Slot inherited budgets (by index) — not the import row's own total.
      if (state.slotRosterAttrs && state.slotRosterAttrs.length) {
        budgets = state.slotRosterAttrs.map(function (a) {
          return applyCappedTopup(a).budget;
        });
      } else {
        budgets = state.import.validPlayers.map(function (p) {
          return applyCappedTopup(p.attributes || {}).budget;
        });
      }
    }
    const budgetEval = evaluateModeRoster(state.attribute_mode, attrsList, budgets);
    state.import.cappedTooLong = false;
    state.import.wrongSize = state.import.validPlayers.length !== BUDGET.MAX_PLAYERS;
    if (state.import.wrongSize) {
      state.import.cappedTooLong = true;
      const sizeMsg = rosterSizeInvalidMessage(
        state.import.validPlayers.length,
        BUDGET.MAX_PLAYERS
      );
      state.import.budgetWarnings.push(sizeMsg);
      const sizeBlocking = document.getElementById('tb-import-blocking');
      if (sizeBlocking) {
        sizeBlocking.hidden = false;
        sizeBlocking.textContent = sizeMsg;
      }
    }
    if (state.attribute_mode === 'uncapped' && budgetEval.over_pool_by > 0) {
      state.import.budgetWarnings.push(
        'Team pool is ' +
          budgetEval.over_pool_by +
          ' over the league maximum (' +
          formatPool(leaguePool()) +
          '). Trim attributes before Apply.'
      );
    }
    if (
      state.attribute_mode === 'capped' &&
      !state.import.cappedTooLong &&
      budgetEval.per_player_over_by > 0
    ) {
      state.import.budgetWarnings.push(
        'Imported per-player totals differ from this program\'s inherited budgets by ' +
          budgetEval.per_player_over_by +
          ' points. On Apply, each player is forced back to his inherited total.'
      );
    }
    syncBudgetRefuseUI();
    if (state.import.budgetWarnings.length) {
      const warnHost = document.getElementById('tb-import-warnings');
      if (warnHost) {
        warnHost.hidden = false;
        warnHost.innerHTML += state.import.budgetWarnings
          .map(function (m) {
            return '<p>' + escapeHtml(m) + '</p>';
          })
          .join('');
      }
    }

    const hasIdentityCols = used.team_name || used.mascot || used.primary_color || used.secondary_color;
    const identityCb = document.getElementById('tb-part-identity');
    const rosterCb = document.getElementById('tb-part-roster');
    if (identityCb) {
      identityCb.disabled = !hasIdentityCols;
      identityCb.checked = hasIdentityCols && state.import.parts.identity;
      if (!hasIdentityCols) state.import.parts.identity = false;
    }
    if (rosterCb) rosterCb.checked = state.import.parts.roster;

    if (partsHost && (state.import.validPlayers.length || hasIdentityCols)) {
      partsHost.hidden = false;
    } else if (partsHost) {
      partsHost.hidden = true;
    }

    if (tooManyHost && state.import.wrongSize) {
      tooManyHost.hidden = false;
      tooManyHost.textContent = rosterSizeInvalidMessage(
        state.import.validPlayers.length || state.import.tooManyRows,
        BUDGET.MAX_PLAYERS
      );
    } else if (tooManyHost) {
      tooManyHost.hidden = true;
    }
  }

  function processCsvText(text) {
    resetImportUi();
    const status = document.getElementById('tb-import-status');
    let rows;
    try {
      rows = parseCsvText(text);
    } catch (_) {
      if (status) {
        status.innerHTML =
          'We couldn\'t read that file — it may not be a valid CSV. <button type="button" class="tb-btn tb-btn-secondary tb-inline-dl">Download our template</button> and paste your data into it.';
        const btn = status.querySelector('.tb-inline-dl');
        if (btn) btn.addEventListener('click', function () { downloadText('gob-roster-template.csv', blankTemplateCsv()); });
      }
      return;
    }

    if (!rows.length) {
      if (status) status.textContent = 'That file has headers but no player rows. Add at least one player, or skip roster import.';
      return;
    }

    state.import.hasHeaderRow = document.getElementById('tb-first-row-headers').checked;
    if (state.import.hasHeaderRow) {
      state.import.headers = rows[0].map(function (h, i) {
        return h && String(h).trim() ? String(h).trim() : 'Column ' + (i + 1);
      });
      state.import.rawRows = rows.slice(1).filter(function (r) {
        return r.some(function (c) {
          return String(c || '').trim() !== '';
        });
      });
    } else {
      const width = rows[0].length;
      state.import.headers = [];
      for (let i = 0; i < width; i++) state.import.headers.push('Column ' + (i + 1));
      state.import.rawRows = rows.filter(function (r) {
        return r.some(function (c) {
          return String(c || '').trim() !== '';
        });
      });
    }

    if (!state.import.rawRows.length) {
      if (status) status.textContent = 'That file has headers but no player rows. Add at least one player, or skip roster import.';
      return;
    }

    state.import.tooManyRows = state.import.rawRows.length;
    state.import.columnMap = autoMapColumns(state.import.headers);
    renderColumnMapping();
    runValidation(true);
  }

  function applyIdentityFromImport(firstRowObj) {
    if (!firstRowObj) return;
    if (firstRowObj.team_name) {
      state.identity.name = firstRowObj.team_name;
      document.getElementById('tb-name').value = firstRowObj.team_name;
    }
    if (firstRowObj.mascot) {
      state.identity.mascot = firstRowObj.mascot;
      document.getElementById('tb-mascot').value = firstRowObj.mascot;
    }
    if (firstRowObj.primary_color) {
      state.colors.primary = normalizeColor(firstRowObj.primary_color);
      document.getElementById('tb-primary').value = state.colors.primary;
    }
    if (firstRowObj.secondary_color) {
      state.colors.secondary = normalizeColor(firstRowObj.secondary_color);
      document.getElementById('tb-secondary').value = state.colors.secondary;
    }
    updateIdentityPreview();
    refreshColorPreviews();
  }

  function normalizeColor(val) {
    const s = String(val || '').trim();
    if (/^#[0-9a-fA-F]{6}$/.test(s)) return s;
    if (/^[0-9a-fA-F]{6}$/.test(s)) return '#' + s;
    return s || '#27408E';
  }

  function openPreviewModal() {
    const identityOn = document.getElementById('tb-part-identity').checked;
    const rosterOn = document.getElementById('tb-part-roster').checked;
    state.import.parts = { identity: identityOn, roster: rosterOn };

    if (!identityOn && !rosterOn) {
      showError('Select at least one part to import, or cancel the import.');
      return;
    }

    if (rosterOn && (state.import.wrongSize || state.import.cappedTooLong)) {
      showError(
        rosterSizeInvalidMessage(state.import.validPlayers.length, BUDGET.MAX_PLAYERS)
      );
      return;
    }

    const modal = document.getElementById('tb-preview-modal');
    const body = document.getElementById('tb-preview-body');
    const errHost = document.getElementById('tb-preview-errors-host');
    const commitBtn = document.getElementById('tb-preview-commit');
    const dlErrBtn = document.getElementById('tb-preview-dl-errors');
    const user = userProgramName();
    const replaced = state.slot ? state.slot.name : 'this program';
    const n = rosterOn ? state.import.validPlayers.length : 0;
    const skipped = state.import.rowErrors.length;

    let html = '';
    if (rosterOn && n) {
      html += '<p>' + n + ' player' + (n === 1 ? '' : 's') + ' will be added to ' + escapeHtml(user) + '.</p>';
    }
    if (skipped) {
      html += '<p>' + skipped + ' row' + (skipped === 1 ? '' : 's') + ' will be skipped (see below).</p>';
    }
    if (state.roster_mode === 'import' || state.roster_mode === 'edit') {
      html += '<p>' + escapeHtml(replaced) + "'s current players won't be part of this franchise.</p>";
    }
    if (identityOn) {
      html += '<p>Team identity fields from the file will be applied.</p>';
    }
    body.innerHTML = html;

    if (errHost) {
      if (skipped) {
        errHost.hidden = false;
        errHost.innerHTML = state.import.rowErrors
          .map(function (m) {
            return '<p>' + escapeHtml(m) + '</p>';
          })
          .join('');
      } else {
        errHost.hidden = true;
        errHost.innerHTML = '';
      }
    }

    if (commitBtn) {
      commitBtn.textContent = rosterOn && n ? 'Import ' + n + ' player' + (n === 1 ? '' : 's') : 'Apply import';
    }
    if (dlErrBtn) dlErrBtn.hidden = !state.import.skippedRows.length;
    modal.hidden = false;
  }

  function commitImport() {
    if (state.import.wrongSize || state.import.cappedTooLong) {
      showError(
        rosterSizeInvalidMessage(state.import.validPlayers.length, BUDGET.MAX_PLAYERS)
      );
      return;
    }
    const identityOn = state.import.parts.identity;
    const rosterOn = state.import.parts.roster;

    if (identityOn) {
      const rowObjects = getRowObjects(state.import.rawRows.slice(0, 1));
      if (rowObjects[0]) applyIdentityFromImport(rowObjects[0]);
    }

    if (rosterOn) {
      // Exact 15 — no truncate / pad (§4.5a).
      state.import.importedPlayers = state.import.validPlayers.slice();
      state.import.importSummary = {
        imported: state.import.importedPlayers.length,
        skipped: state.import.rowErrors.length,
      };
      state.roster_mode = 'import';
      document.querySelectorAll('.tb-roster-card').forEach(function (c) {
        c.classList.toggle('is-selected', c.dataset.mode === 'import');
      });
    } else {
      state.import.importedPlayers = null;
      state.import.importSummary = null;
    }

    document.getElementById('tb-preview-modal').hidden = true;
    state.import.committed = true;
    updateBudgetFromCurrentRoster();
    renderReview();
    if (rosterOn) syncPortraits();
  }

  function downloadSkippedRowsCsv() {
    if (!state.import.skippedRows.length) return;
    const headers = state.import.headers;
    const lines = [headers.map(csvEscape).join(',')];
    state.import.skippedRows.forEach(function (rowObj) {
      lines.push(rowObj._raw.map(csvEscape).join(','));
    });
    downloadText('skipped-rows.csv', lines.join('\n') + '\n');
  }

  function csvEscape(val) {
    const s = String(val == null ? '' : val);
    if (/[",\n\r]/.test(s)) return '"' + s.replace(/"/g, '""') + '"';
    return s;
  }

  function currentRosterBudgetInput() {
    if (state.roster_mode === 'edit' && state.editor.loaded && state.editor.players.length) {
      return {
        attrsList: state.editor.players.map(function (p) {
          return p.attrs;
        }),
        budgets:
          state.attribute_mode === 'capped'
            ? state.editor.players.map(function (p) {
                return p.budget;
              })
            : null,
      };
    }
    if (
      state.roster_mode === 'import' &&
      state.import.importedPlayers &&
      state.import.importedPlayers.length
    ) {
      return {
        attrsList: state.import.importedPlayers.map(function (p) {
          return attrsWithModeTopup(p.attributes || {});
        }),
        budgets:
          state.attribute_mode === 'capped'
            ? state.import.importedPlayers.map(function (p) {
                return applyCappedTopup(p.attributes || {}).budget;
              })
            : null,
      };
    }
    return null;
  }

  function updateBudgetFromCurrentRoster() {
    const input = currentRosterBudgetInput();
    if (!input || !input.attrsList.length) {
      state.budget = null;
      renderBudgetMeter(null);
      return;
    }
    const shapePlayers =
      state.roster_mode === 'edit' && state.editor.loaded
        ? state.editor.players
        : state.import.importedPlayers || [];
    state.budget = evaluateModeRoster(
      state.attribute_mode,
      input.attrsList,
      input.budgets,
      shapePlayers
    );
    renderBudgetMeter(state.budget);
    syncBudgetRefuseUI();
  }

  function renderHeightClassMeters(evalResult) {
    const heightEl = document.getElementById('tb-height-budget-label');
    const classEl = document.getElementById('tb-class-budget-label');
    const wrap = document.getElementById('tb-height-class-meters');
    const uncapped = state.attribute_mode === 'uncapped';
    if (wrap) wrap.hidden = uncapped;
    if (uncapped) return;
    if (!evalResult || evalResult.height_budget == null) {
      if (heightEl) heightEl.textContent = 'Height: —';
      if (classEl) classEl.textContent = 'Class: —';
      return;
    }
    if (heightEl) {
      heightEl.textContent =
        'Height: ' +
        evalResult.height_total +
        '" / ' +
        evalResult.height_budget +
        '"' +
        (evalResult.height_over_by > 0
          ? ' — over by ' + evalResult.height_over_by + '"'
          : ' — under permitted');
      heightEl.classList.toggle('is-over', evalResult.height_over_by > 0);
    }
    if (classEl) {
      const delta = evalResult.class_delta || 0;
      let note = ' — exact spend required';
      if (delta > 0) note = ' — over by ' + delta;
      else if (delta < 0) note = ' — short by ' + -delta;
      classEl.textContent =
        'Class: ' + evalResult.class_total + ' / ' + evalResult.class_budget + note;
      classEl.classList.toggle('is-over', delta !== 0);
    }
  }

  function renderBudgetMeter(evalResult) {
    const fill = document.getElementById('tb-budget-fill');
    const teamBar = document.getElementById('tb-budget-bar-team');
    const track = document.getElementById('tb-budget-track-team');
    const label = document.getElementById('tb-budget-label');
    const context = document.getElementById('tb-budget-context');
    const badge = document.getElementById('tb-elig-badge');
    const uncapped = state.attribute_mode === 'uncapped';
    const poolCap = leaguePool();
    const markers = [
      document.getElementById('tb-team-marker-median'),
      document.getElementById('tb-team-marker-best'),
    ];

    // Capped: no uncapped pool bar — per-player budgets are the allocation truth.
    if (track) track.hidden = !uncapped;
    markers.forEach(function (el) {
      if (el) el.hidden = !uncapped;
    });

    if (uncapped) {
      placeLeagueMarkers(poolCap);
      if (context) {
        context.hidden = !poolCap;
        context.textContent =
          'median program ' +
          formatPool(leagueMedian()) +
          ' · best program ' +
          formatPool(poolCap);
      }
    } else if (context) {
      context.hidden = true;
    }

    function setEligBadge() {
      if (!badge) return;
      badge.textContent = uncapped
        ? 'Not eligible for online play (uncapped)'
        : 'Eligible for online play (capped)';
      badge.className = uncapped ? 'tb-elig is-no' : 'tb-elig is-yes';
    }

    if (!evalResult) {
      if (uncapped) setBarFill(fill, teamBar, 0, poolCap || 1);
      if (label) {
        if (!uncapped) {
          label.textContent = state.slotRosterLoading
            ? 'Loading inherited roster…'
            : 'Per-player budgets — points stay within each player';
        } else {
          label.textContent = poolCap ? 'Team pool: — / ' + formatPool(poolCap) : 'Team pool: —';
        }
      }
      renderHeightClassMeters(null);
      setEligBadge();
      syncBudgetRefuseUI();
      return;
    }

    const teamTotal = evalResult.team_total;
    if (uncapped) {
      setBarFill(fill, teamBar, teamTotal, poolCap || Math.max(teamTotal, 1));
      if (label) {
        label.textContent =
          'Team pool: ' + formatPool(teamTotal) + ' / ' + formatPool(poolCap);
      }
    } else if (label) {
      const n = state.editor.loaded ? state.editor.players.length : (state.slotPlayers || []).length;
      label.textContent =
        'Inherited shape: ' +
        formatPool(teamTotal) +
        ' total across ' +
        n +
        ' player' +
        (n === 1 ? '' : 's') +
        ' — redistribute within each player only';
    }

    renderHeightClassMeters(evalResult);
    setEligBadge();
    syncBudgetRefuseUI();
  }

  function ensureDraftId() {
    if (state.draftId) return state.draftId;
    var existing = null;
    try {
      existing = window.localStorage.getItem('tb-draft-id');
    } catch (_) {}
    if (existing && existing.length >= 8) {
      state.draftId = existing;
      return state.draftId;
    }
    var id =
      typeof crypto !== 'undefined' && crypto.randomUUID
        ? crypto.randomUUID()
        : 'tb-' + String(Date.now()) + '-' + Math.random().toString(16).slice(2);
    state.draftId = id;
    try {
      window.localStorage.setItem('tb-draft-id', id);
    } catch (_) {}
    return state.draftId;
  }

  function clearDraftId() {
    state.draftId = null;
    try {
      window.localStorage.removeItem('tb-draft-id');
    } catch (_) {}
  }

  async function ensureWizardWalkOns() {
    // Server-keyed on draft+slot — reload-safe; not re-rollable (Decision #25).
    if (!state.slot || !state.slot.object_id) {
      throw new Error('slot required for walk-ons');
    }
    var slotKey = String(state.slot.object_id);
    if (
      state.wizardWalkOns &&
      state.wizardWalkOns.length === 3 &&
      state._wizardWalkOnsSlotKey === slotKey
    ) {
      return state.wizardWalkOns;
    }
    if (state.wizardWalkOnsLoading && state._wizardWalkOnsPromise) {
      return state._wizardWalkOnsPromise;
    }
    state.wizardWalkOnsLoading = true;
    state._wizardWalkOnsPromise = (async function () {
      var draftId = ensureDraftId();
      const res = await fetch(API_CONFIG.buildUrl('/franchise/team-builder/wizard-walk-ons'), {
        method: 'POST',
        headers: { ...API_CONFIG.getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({
          replaced_object_id: slotKey,
          draft_id: draftId,
        }),
      });
      if (!res.ok) throw new Error('walk-on generation failed');
      const data = await res.json();
      const walkOns = data.walk_ons || [];
      if (walkOns.length !== 3) throw new Error('expected 3 walk-ons');
      state.wizardWalkOns = walkOns;
      state._wizardWalkOnsSlotKey = slotKey;
      // §10 — budgets + class_rank table are server domain data.
      if (data.height_min_in != null) BUDGET.HEIGHT_MIN = Number(data.height_min_in) || BUDGET.HEIGHT_MIN;
      if (data.height_max_in != null) BUDGET.HEIGHT_MAX = Number(data.height_max_in) || BUDGET.HEIGHT_MAX;
      state.shape = {
        height_budget: data.height_budget != null ? Number(data.height_budget) : null,
        class_budget: data.class_budget != null ? Number(data.class_budget) : null,
        class_rank: data.class_rank || null,
        loaded: true,
      };
      return walkOns;
    })();
    try {
      return await state._wizardWalkOnsPromise;
    } finally {
      state.wizardWalkOnsLoading = false;
    }
  }

  function mergeSlotWithWizardWalkOns(corePlayers, walkOns) {
    const core = (corePlayers || []).slice(0, 12).map(function (p) {
      const copy = Object.assign({}, p);
      copy.walk_on = false;
      return copy;
    });
    const extras = (walkOns || []).map(function (wo) {
      return {
        wizard_player_id: wo.wizard_player_id || null,
        player_id: wo.wizard_player_id || null,
        first_name: wo.first_name || '',
        last_name: wo.last_name || '',
        year: wo.year || 'Freshman',
        height: wo.height,
        weight: wo.weight,
        jersey: wo.jersey,
        attributes: Object.assign({}, wo.attributes || {}),
        walk_on: true,
        archetype: 'Walk On',
        entry_tier: wo.entry_tier || 'Poor',
        position_intent: wo.position_intent || null,
        development: wo.development != null ? wo.development : null,
      };
    });
    return core.concat(extras);
  }

  async function fetchSlotRoster() {
    if (!state.slot) return;
    state.slotRosterLoading = true;
    if (state.roster_mode === 'edit') renderBudgetMeter(null);
    try {
      const url = API_CONFIG.buildUrl('/roster/' + encodeURIComponent(state.slot.name));
      const res = await fetch(url, { headers: API_CONFIG.getAuthHeaders() });
      if (!res.ok) throw new Error('roster fetch failed');
      const data = await res.json();
      const walkOns = await ensureWizardWalkOns();
      state.slotPlayers = mergeSlotWithWizardWalkOns(data.players || [], walkOns);
      state.slotRosterAttrs = state.slotPlayers.map(function (p) {
        return extractCore12FromPlayer(p);
      });
      if (state.roster_mode === 'edit') {
        initEditorFromSlot(!state.editor.loaded);
      }
    } catch (_) {
      state.slotPlayers = null;
      state.slotRosterAttrs = null;
    } finally {
      state.slotRosterLoading = false;
      if (state.roster_mode === 'edit') {
        renderBudgetMeter(state.budget);
      }
    }
  }

  function mountPicker() {
    const root = document.getElementById('tb-picker');
    if (!root || !window.TeamPicker) {
      showError('Team picker failed to load.');
      return;
    }
    TeamPicker.mount(root, {
      primaryAction: { label: 'Select', onClick: function () {} },
      secondaryAction: null,
      confirmation: {
        enabled: true,
        confirmLabel: 'Choose this slot →',
        renderBody: function (team, host) {
          renderSlotConfirm(team, host);
        },
        onConfirm: function (team) {
          state.slot = team;
          state.slotRosterAttrs = null;
          state.slotPlayers = null;
          // Slot change keeps draft_id but clears cached walk-ons — server key includes slot.
          state.wizardWalkOns = null;
          state._wizardWalkOnsSlotKey = null;
          state._wizardWalkOnsPromise = null;
          state.editor = { players: [], inherited: [], loaded: false };
          const editDetail = document.getElementById('tb-edit-detail');
          if (editDetail) {
            editDetail.textContent =
              team.name + "'s roster in a table — redistribute within the chosen mode.";
          }
          const dl = document.getElementById('tb-dl-slot');
          if (dl) dl.textContent = "Download " + team.name + "'s current roster";
          fetchSlotRoster();
          setStep(1);
        },
      },
    });
  }

  function normalizeJerseyPreset(value) {
    return Number(value) === 2 ? 2 : 1;
  }

  function readIdentity() {
    state.identity = {
      name: (document.getElementById('tb-name').value || '').trim(),
      abbreviation: (document.getElementById('tb-abbr').value || '').trim().toUpperCase(),
      mascot: (document.getElementById('tb-mascot').value || '').trim(),
    };
  }

  function validateAbbr() {
    const abbr = (document.getElementById('tb-abbr').value || '').trim().toUpperCase();
    const hint = document.getElementById('tb-abbr-hint');
    state.abbrConflict = null;
    if (abbr.length !== 3) {
      hint.hidden = true;
      return false;
    }
    const conflict = (state.allTeams || []).find(function (t) {
      if (state.slot && String(t.object_id) === String(state.slot.object_id)) return false;
      var otherAbbr =
        typeof deriveTeamAbbreviationFromName === 'function'
          ? deriveTeamAbbreviationFromName(t.name)
          : String(t.name || '')
              .replace(/[^A-Za-z0-9]/g, '')
              .slice(0, 3)
              .toUpperCase();
      return otherAbbr === abbr;
    });
    if (conflict) {
      state.abbrConflict = conflict.name;
      hint.hidden = false;
      hint.textContent = abbr + ' is already used by ' + conflict.name + '. Try another.';
      return false;
    }
    hint.hidden = true;
    return true;
  }

  function updateIdentityPreview() {
    readIdentity();
    // Match live chrome: scorebug → abbreviation; standings row → full name.
    const name = state.identity.name || '—';
    const abbr = state.identity.abbreviation || '—';
    const bug = document.getElementById('tb-scorebug');
    const row = document.getElementById('tb-standings-row');
    if (bug) {
      bug.textContent = abbr;
      bug.style.background = state.colors.primary;
    }
    if (row) {
      row.textContent = '1 · ' + name + ' · 0–0';
    }
  }

  function syncCourtDefaultsFromTeamColors() {
    if (!window.TeamGeneratedArt || typeof TeamGeneratedArt.defaultsFromTeamColors !== 'function') {
      return;
    }
    const d = TeamGeneratedArt.defaultsFromTeamColors(state.colors.primary, state.colors.secondary);
    state.colors.court = Object.assign({}, state.colors.court, d);
    const hw = document.getElementById('tb-court-hardwood');
    const oob = document.getElementById('tb-court-oob');
    const lane = document.getElementById('tb-court-lane');
    const outside = document.getElementById('tb-court-outside');
    const half = document.getElementById('tb-court-halfarc');
    if (hw) hw.value = state.colors.court.hardwoodStyle;
    if (oob) oob.value = state.colors.court.oobColor;
    if (lane) lane.value = state.colors.court.laneColor;
    if (outside) outside.value = state.colors.court.outsideWoodColor;
    if (half) half.value = state.colors.court.halfArcFillColor;
    // Re-arm hardwood→outside sync after programmatic defaults (linked again).
    armOutsideWoodAutoSyncFromDom();
  }

  function readColors() {
    state.colors.primary = document.getElementById('tb-primary').value;
    state.colors.secondary = document.getElementById('tb-secondary').value;
    const preset = document.querySelector('input[name="jersey"]:checked');
    state.colors.jersey_preset = normalizeJerseyPreset(preset ? preset.value : 1);
    const hw = document.getElementById('tb-court-hardwood');
    const oob = document.getElementById('tb-court-oob');
    const lane = document.getElementById('tb-court-lane');
    const outside = document.getElementById('tb-court-outside');
    const half = document.getElementById('tb-court-halfarc');
    state.colors.court = {
      hardwoodStyle: hw ? hw.value : state.colors.court.hardwoodStyle,
      oobColor: oob ? oob.value : state.colors.court.oobColor,
      laneColor: lane ? lane.value : state.colors.court.laneColor,
      outsideWoodColor: outside ? outside.value : state.colors.court.outsideWoodColor,
      halfArcFillColor: half ? half.value : state.colors.court.halfArcFillColor,
    };
  }

  function refreshColorPreviews() {
    readIdentity();
    readColors();
    if (!window.TeamGeneratedArt) return;
    const opts = {
      name: state.identity.name || 'Custom Program',
      abbreviation: state.identity.abbreviation,
      mascot: state.identity.mascot,
      primary: state.colors.primary,
      secondary: state.colors.secondary,
      jerseyPreset: state.colors.jersey_preset,
      court: state.colors.court,
    };
    function paint() {
      const banner = document.getElementById('tb-banner-preview');
      const mark = document.getElementById('tb-mark-preview');
      const jersey = document.getElementById('tb-jersey-preview');
      const court = document.getElementById('tb-court-preview');
      if (banner) banner.src = TeamGeneratedArt.bannerCardDataUrl(opts);
      if (mark) mark.src = TeamGeneratedArt.markDataUrl(opts);
      if (jersey) jersey.src = TeamGeneratedArt.jerseyPreviewDataUrl(opts);
      if (court) court.src = TeamGeneratedArt.courtPreviewDataUrl(opts);
    }
    paint();
    if (typeof TeamGeneratedArt.ensureBannerFonts === 'function') {
      TeamGeneratedArt.ensureBannerFonts().then(paint);
    }
    updateIdentityPreview();
  }

  function refreshRosterStep() {
    updateModePill();
    const importPanel = document.getElementById('tb-import-panel');
    const editorPanel = document.getElementById('tb-editor-panel');
    if (importPanel) importPanel.hidden = state.roster_mode !== 'import';
    if (editorPanel) editorPanel.hidden = state.roster_mode !== 'edit';

    const needsRoster = state.roster_mode === 'edit' && !state.slotPlayers && state.slot;

    if (needsRoster) {
      fetchSlotRoster().then(function () {
        if (state.roster_mode === 'edit' && state.slotPlayers) {
          initEditorFromSlot(true);
        }
        updateBudgetFromCurrentRoster();
      });
      return;
    }

    if (state.roster_mode === 'edit' && state.slotPlayers) {
      initEditorFromSlot(false);
    }
    updateBudgetFromCurrentRoster();
  }

  function modeReviewLine() {
    const modeLabel = state.attribute_mode === 'uncapped' ? 'Uncapped' : 'Capped';
    const elig =
      state.attribute_mode === 'capped'
        ? 'eligible for online play'
        : 'not eligible for online play';
    let line = 'Attribute mode: ' + modeLabel + ' — ' + elig;
    if (state.budget) {
      if (state.attribute_mode === 'uncapped') {
        line +=
          ' · team pool ' +
          formatPool(state.budget.team_total) +
          ' / ' +
          formatPool(leaguePool());
      } else {
        line += ' · team total ' + formatPool(state.budget.team_total);
      }
    }
    return line;
  }

  function renderReview() {
    readIdentity();
    readColors();
    const host = document.getElementById('tb-review');
    if (!host || !state.slot) return;
    const conf = confLabel(state.slot);
    const rosterCount =
      state.roster_mode === 'edit' && state.editor.loaded
        ? state.editor.players.length
        : state.roster_mode === 'import' && state.import.importedPlayers
          ? state.import.importedPlayers.length
          : (state.slotPlayers || []).length;
    let rosterLine;
    if (state.roster_mode === 'edit') {
      rosterLine =
        'Roster: editing inherited ' +
        state.slot.name +
        ' players' +
        (rosterCount ? ' (' + rosterCount + ')' : '');
    } else if (state.import.importSummary) {
      rosterLine =
        'Roster: ' +
        state.import.importSummary.imported +
        ' players imported' +
        (state.import.importSummary.skipped ? ', ' + state.import.importSummary.skipped + ' row skipped' : '');
    } else {
      rosterLine = 'Roster: import (CSV — not committed yet)';
    }
    host.innerHTML =
      '<p><strong>' +
      escapeHtml(userProgramName()) +
      '</strong> replaces <strong>' +
      escapeHtml(state.slot.name) +
      '</strong> in ' +
      escapeHtml(conf) +
      '.</p>' +
      '<p>Identity: name, mascot, colors, logo — all set</p>' +
      '<p>' +
      escapeHtml(rosterLine) +
      '</p>' +
      '<p>' +
      escapeHtml(modeReviewLine()) +
      '</p>' +
      '<p>Unchanged: schedule, conference, opponents</p>';
  }

  function openConfirmModal() {
    readIdentity();
    const modal = document.getElementById('tb-confirm-modal');
    const body = document.getElementById('tb-confirm-body');
    const conf = confLabel(state.slot);
    body.innerHTML =
      '<p><strong>' +
      escapeHtml(userProgramName()) +
      ' replaces ' +
      escapeHtml(state.slot.name) +
      '</strong> in ' +
      escapeHtml(conf) +
      '. Schedule unchanged.</p>' +
      '<p>This affects <strong>this franchise only</strong>. ' +
      escapeHtml(state.slot.name) +
      ' is unchanged in your other saves and in any new franchise you start.</p>';
    modal.hidden = false;
  }

  function formatApplyFailureMessage(detail) {
    let msg =
      typeof detail === 'string'
        ? detail
        : detail
          ? JSON.stringify(detail)
          : 'Unable to apply Team Builder.';
    const isCap =
      /active franchise/i.test(msg) ||
      /delete one before starting/i.test(msg) ||
      state.franchiseCap.blocked;
    if (isCap) {
      state.franchiseCap.blocked = true;
      if (!state.franchiseCap.message) {
        state.franchiseCap.message = franchiseCapMessage(
          state.franchiseCap.count || state.franchiseCap.max,
          state.franchiseCap.max
        );
      }
      updateApplyButtonState();
      return (
        escapeHtml(state.franchiseCap.message) +
        ' <a href="/mode-select.html">Open Mode Select</a>'
      );
    }
    if (!/try again|delete|fix|required|already/i.test(msg)) {
      msg += ' Fix the issue above, then try Apply again.';
    }
    return escapeHtml(msg);
  }

  async function applyFranchise() {
    const loading = document.getElementById('tb-loading');
    const modal = document.getElementById('tb-confirm-modal');
    if (state.franchiseCap.blocked) {
      if (modal) modal.hidden = true;
      showError(
        escapeHtml(state.franchiseCap.message) +
          ' <a href="/mode-select.html">Open Mode Select</a>',
        { nearApply: true, html: true }
      );
      return;
    }
    modal.hidden = true;
    loading.hidden = false;
    showError('');
    try {
      const payload = {
        replaced_object_id: state.slot.object_id,
        home_slot: HOME_SLOT,
        name: state.identity.name,
        abbreviation: state.identity.abbreviation,
        mascot: state.identity.mascot,
        primary_color: state.colors.primary,
        secondary_color: state.colors.secondary,
        jersey_preset: state.colors.jersey_preset,
        court: state.colors.court,
        roster_mode: state.roster_mode,
        attribute_mode: state.attribute_mode,
        draft_id: ensureDraftId(),
      };
      if (
        state.roster_mode === 'import' &&
        state.import.importedPlayers &&
        state.import.importedPlayers.length
      ) {
        payload.imported_players = state.import.importedPlayers.map(function (p, idx) {
          const row = Object.assign({}, p);
          if (idx >= 12) {
            row.walk_on = true;
            row.archetype = 'Walk On';
            row.entry_tier = row.entry_tier || 'Poor';
          }
          if (p.player_id) row.player_id = p.player_id;
          if (p.image_id) row.image_id = p.image_id;
          return row;
        });
        const missingImport = payload.imported_players.some(function (p) {
          return !p.player_id || !p.image_id;
        });
        if (missingImport) {
          await syncPortraits();
          payload.imported_players = state.import.importedPlayers.map(function (p, idx) {
            const row = Object.assign({}, p);
            if (idx >= 12) {
              row.walk_on = true;
              row.archetype = 'Walk On';
              row.entry_tier = row.entry_tier || 'Poor';
            }
            if (p.player_id) row.player_id = p.player_id;
            if (p.image_id) row.image_id = p.image_id;
            return row;
          });
        }
        const budgets = slotPerPlayerBudgets();
        if (budgets && budgets.length === 15) payload.per_player_budgets = budgets;
      }
      if (state.roster_mode === 'edit' && state.editor.loaded && state.editor.players.length) {
        // Ensure wizard-minted ids are present before Apply (seed stability).
        const missing = state.editor.players.some(function (p) {
          return !p.player_id || !p.image_id;
        });
        if (missing) await syncPortraits({ force: false });
        payload.imported_players = editorPlayersToImportPayload();
        const budgets = editorPerPlayerBudgets();
        if (budgets && budgets.length === 15) payload.per_player_budgets = budgets;
      }
      const res = await fetch(API_CONFIG.buildUrl('/franchise/team-builder/apply'), {
        method: 'POST',
        headers: { ...API_CONFIG.getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        let detail = null;
        try {
          const err = await res.json();
          detail = err.detail;
        } catch (_) {}
        loading.hidden = true;
        showError(formatApplyFailureMessage(detail || 'Unable to apply Team Builder.'), {
          nearApply: true,
          html: true,
        });
        return;
      }
      const data = await res.json();
      if (data.franchise_id) {
        clearDraftId();
        if (typeof hydrateTeamBuilderVisualFromFranchisePayload === 'function') {
          hydrateTeamBuilderVisualFromFranchisePayload(
            {
              team: state.identity.name,
              abbreviation: state.identity.abbreviation,
              primary_color: state.colors.primary,
              secondary_color: state.colors.secondary,
              jersey_preset: state.colors.jersey_preset,
              // Prefer server-persisted court from Apply response (source of truth).
              court:
                (data.team_builder && data.team_builder.court) || state.colors.court,
              asset_strategy: 'generated',
              is_custom_team: true,
              team_builder_replaced_name: state.slot.name,
              user_team_object_id: state.slot.object_id,
              online_eligible:
                data.online_eligible != null ? data.online_eligible : data.online_eligibility,
            },
            data.franchise_id
          );
        }
        if (window.FranchiseLS) {
          window.FranchiseLS.clearBareKeys();
          window.FranchiseLS.setTeamContext(data.franchise_id, {
            teamName: state.identity.name,
            primaryColor: state.colors.primary,
          });
        }
      }
      window.location.href =
        './franchise-command-center.html?franchise_id=' + encodeURIComponent(data.franchise_id);
    } catch (err) {
      loading.hidden = true;
      showError(
        escapeHtml((err && err.message) || 'Unable to apply Team Builder.') +
          ' Check your connection and try Apply again.',
        { nearApply: true, html: true }
      );
    }
  }

  function blankTemplateCsv() {
    const header =
      'first_name,last_name,class_year,height_in,weight_lb,jersey,SC,SH,ID,OD,PS,BH,RB,ST,AG,ND,IQ,FT\n';
    const years = ['FR', 'SO', 'JR', 'SR', 'FR', 'SO', 'JR', 'SR', 'FR', 'SO', 'JR', 'SR', 'FR', 'FR', 'SO'];
    const rows = years.map(function (cy, i) {
      return 'Player' + (i + 1) + ',Example,' + cy + ',,,,,,,,,,,,';
    });
    return header + rows.join('\n') + '\n';
  }

  function downloadText(filename, text) {
    const blob = new Blob([text], { type: 'text/csv;charset=utf-8' });
    downloadBlob(filename, blob);
  }

  function downloadBlob(filename, blob) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  function authoredRosterCsvFromSlotPlayers() {
    const header = [
      'first_name',
      'last_name',
      'class_year',
      'height_in',
      'weight_lb',
      'jersey',
    ].concat(CORE_12);
    const lines = [header.map(csvEscape).join(',')];
    (state.slotPlayers || []).forEach(function (p) {
      const cy = classYearFromPlayer(p) || 'FR';
      const attrs = extractCore12FromPlayer(p);
      const row = [
        p.first_name || '',
        p.last_name || '',
        cy,
        p.height != null ? p.height : '',
        p.weight != null ? p.weight : '',
        p.jersey != null ? p.jersey : '',
      ].concat(
        CORE_12.map(function (k) {
          return attrs[k] != null ? attrs[k] : '';
        })
      );
      lines.push(row.map(csvEscape).join(','));
    });
    return lines.join('\n') + '\n';
  }

  async function downloadSlotRoster() {
    const status = document.getElementById('tb-import-status');
    if (!state.slot) return;
    const slug = state.slot.name.replace(/\s+/g, '-').toLowerCase();
    try {
      // Prefer authored 15 (core 12 + wizard walk-ons) so the CSV matches Apply.
      if (!state.slotPlayers || state.slotPlayers.length !== 15) {
        await fetchSlotRoster();
      }
      if (state.slotPlayers && state.slotPlayers.length === 15) {
        downloadText(slug + '-roster.csv', authoredRosterCsvFromSlotPlayers());
        if (status) status.textContent = '';
        return;
      }
      const url = API_CONFIG.buildUrl(
        '/franchise/team-builder/slot-roster.csv?object_id=' + encodeURIComponent(state.slot.object_id)
      );
      const res = await fetch(url, { headers: API_CONFIG.getAuthHeaders() });
      if (!res.ok) {
        let detail = 'Could not download this program\'s roster (HTTP ' + res.status + ').';
        try {
          const err = await res.json();
          if (err && err.detail) detail = typeof err.detail === 'string' ? err.detail : detail;
        } catch (_) {}
        if (status) status.textContent = detail;
        return;
      }
      const blob = await res.blob();
      downloadBlob(slug + '-roster.csv', blob);
      if (status) status.textContent = '';
    } catch (err) {
      if (status) {
        status.textContent =
          (err && err.message) || 'Could not download this program\'s roster. Check your connection and try again.';
      }
    }
  }

  function handleCsvFile(file) {
    const status = document.getElementById('tb-import-status');
    if (!file) return;
    const name = (file.name || '').toLowerCase();
    if (name.endsWith('.xlsx') || name.endsWith('.xls')) {
      if (status) {
        status.textContent =
          "That's a .xlsx file. Save it as CSV (File → Save As → CSV) and try again.";
      }
      return;
    }
    if (!name.endsWith('.csv') && file.type && file.type.indexOf('csv') === -1 && file.type.indexOf('text') === -1) {
      if (status) {
        status.textContent =
          "That's a .xlsx file. Save it as CSV (File → Save As → CSV) and try again.";
      }
      return;
    }
    const reader = new FileReader();
    reader.onload = function () {
      processCsvText(String(reader.result || ''));
    };
    reader.onerror = function () {
      if (status) {
        status.innerHTML =
          'We couldn\'t read that file — it may not be a valid CSV. <button type="button" class="tb-btn tb-btn-secondary tb-inline-dl">Download our template</button> and paste your data into it.';
        const btn = status.querySelector('.tb-inline-dl');
        if (btn) btn.addEventListener('click', function () { downloadText('gob-roster-template.csv', blankTemplateCsv()); });
      }
    };
    reader.readAsText(file);
  }

  document.addEventListener('DOMContentLoaded', async function () {
    ensureDraftId();
    const back = document.getElementById('tb-back');
    if (back) {
      const q = HOME_SLOT ? ('?home_slot=' + HOME_SLOT) : '';
      back.href = '/franchise-select-team.html' + q;
    }

    const capped = await checkFranchiseCapAtEntry();
    if (capped) {
      if (back) back.href = '/mode-select.html';
      return;
    }

    try {
      state.allTeams = await TeamPicker.fetchTeams();
    } catch (_) {
      state.allTeams = [];
    }

    await fetchLeagueContext();
    mountPicker();
    updateModePill();

    document.querySelectorAll('[data-nav]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        if (state.franchiseCap.blocked) {
          return showError(
            escapeHtml(state.franchiseCap.message) +
              ' <a href="/mode-select.html">Open Mode Select</a>',
            { html: true }
          );
        }
        const next = Number(btn.dataset.nav);
        if (state.step === 1 && next > 1) {
          readIdentity();
          if (!state.identity.name) return showError('School name is required.');
          if (!validateAbbr()) return showError(document.getElementById('tb-abbr-hint').textContent);
        }
        if (!state.slot && next > 0) return showError('Choose a slot first.');
        // Budget refuse is sticky on the dock — block leaving roster while over.
        if (next === 4 && currentBudgetBlockReason()) {
          syncBudgetRefuseUI();
          const refuse = document.getElementById('tb-budget-refuse');
          if (refuse && typeof refuse.scrollIntoView === 'function') {
            refuse.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
          }
          return;
        }
        setStep(next);
      });
    });

    ['tb-name', 'tb-abbr', 'tb-mascot'].forEach(function (id) {
      const el = document.getElementById(id);
      if (!el) return;
      el.addEventListener('input', updateIdentityPreview);
      if (id === 'tb-abbr') el.addEventListener('blur', validateAbbr);
    });

    ['tb-primary', 'tb-secondary'].forEach(function (id) {
      const el = document.getElementById(id);
      if (!el) return;
      el.addEventListener('input', function () {
        readColors();
        // Primary/secondary drive court defaults until the user edits court fields.
        syncCourtDefaultsFromTeamColors();
        refreshColorPreviews();
      });
    });
    document.querySelectorAll('input[name="jersey"]').forEach(function (el) {
      el.addEventListener('change', refreshColorPreviews);
    });
    // Hardwood style is inside_outside (Node HARDWOOD_VARIANTS). outsideWoodColor
    // paints the main floor. Sync that picker to the style's outside tone only while
    // it still matches the last auto value — never overwrite a deliberate custom choice.
    const hwSelect = document.getElementById('tb-court-hardwood');
    const outsideInput = document.getElementById('tb-court-outside');
    const outsideSyncNote = document.getElementById('tb-court-outside-sync-note');
    let lastAutoOutsideTone = null;

    function _normHex(v) {
      const s = String(v || '').trim().toLowerCase();
      if (/^#[0-9a-f]{6}$/.test(s)) return s;
      if (/^#[0-9a-f]{3}$/.test(s)) {
        return '#' + s[1] + s[1] + s[2] + s[2] + s[3] + s[3];
      }
      return s;
    }

    function outsideToneForHardwood(styleKey) {
      const variants =
        window.TeamCourtGenerator && window.TeamCourtGenerator.HARDWOOD_VARIANTS;
      const tones = window.TeamCourtGenerator && window.TeamCourtGenerator.HARDWOOD_TONES;
      const variant = variants && variants[styleKey];
      return variant && tones ? tones[variant.outside] : null;
    }

    function setOutsideSyncNote(msg) {
      if (outsideSyncNote) outsideSyncNote.textContent = msg || '';
    }

    armOutsideWoodAutoSyncFromDom = function () {
      if (!hwSelect || !outsideInput) return;
      const tone = outsideToneForHardwood(hwSelect.value);
      if (tone && _normHex(outsideInput.value) === _normHex(tone)) {
        lastAutoOutsideTone = _normHex(tone);
        setOutsideSyncNote('');
      } else {
        lastAutoOutsideTone = null;
      }
    };

    if (hwSelect) {
      hwSelect.addEventListener('change', function () {
        const tone = outsideToneForHardwood(hwSelect.value);
        if (
          outsideInput &&
          tone &&
          lastAutoOutsideTone &&
          _normHex(outsideInput.value) === lastAutoOutsideTone
        ) {
          outsideInput.value = tone;
          lastAutoOutsideTone = _normHex(tone);
          setOutsideSyncNote('');
        } else if (outsideInput && tone) {
          setOutsideSyncNote('Custom outside-wood colour kept');
        }
        refreshColorPreviews();
      });
    }
    if (outsideInput) {
      outsideInput.addEventListener('input', function () {
        const tone = outsideToneForHardwood(hwSelect ? hwSelect.value : '');
        if (tone && _normHex(outsideInput.value) === _normHex(tone)) {
          lastAutoOutsideTone = _normHex(tone);
          setOutsideSyncNote('');
        } else {
          lastAutoOutsideTone = null;
          setOutsideSyncNote('');
        }
        refreshColorPreviews();
      });
    }
    armOutsideWoodAutoSyncFromDom();
    ['tb-court-oob', 'tb-court-lane', 'tb-court-halfarc'].forEach(function (id) {
      const el = document.getElementById(id);
      if (el) el.addEventListener('input', refreshColorPreviews);
    });

    document.querySelectorAll('.tb-mode-card').forEach(function (card) {
      card.addEventListener('click', function () {
        setAttributeMode(card.dataset.attrMode);
      });
    });

    const editorHost = document.getElementById('tb-editor-host');
    if (editorHost) {
      editorHost.addEventListener('input', onEditorHostChange);
      editorHost.addEventListener('change', onEditorHostChange);
      editorHost.addEventListener('click', onEditorHostClick);
    }
    const editorResetAll = document.getElementById('tb-editor-reset-all');
    if (editorResetAll) {
      editorResetAll.addEventListener('click', resetAllEditor);
    }

    document.querySelectorAll('.tb-roster-card').forEach(function (card) {
      card.addEventListener('click', function () {
        document.querySelectorAll('.tb-roster-card').forEach(function (c) {
          c.classList.remove('is-selected');
        });
        card.classList.add('is-selected');
        state.roster_mode = card.dataset.mode;
        if (state.roster_mode !== 'import') resetImportUi();
        refreshRosterStep();
      });
    });

    document.getElementById('tb-dl-blank').addEventListener('click', function () {
      downloadText('gob-roster-template.csv', blankTemplateCsv());
    });
    document.getElementById('tb-dl-slot').addEventListener('click', downloadSlotRoster);

    const csvInput = document.getElementById('tb-csv');
    if (csvInput) {
      csvInput.addEventListener('change', function () {
        handleCsvFile(csvInput.files && csvInput.files[0]);
      });
    }

    const headersToggle = document.getElementById('tb-first-row-headers');
    if (headersToggle) {
      headersToggle.addEventListener('change', function () {
        if (state.import.rawRows.length || state.import.headers.length) {
          const file = csvInput && csvInput.files && csvInput.files[0];
          if (file) handleCsvFile(file);
        }
      });
    }

    document.getElementById('tb-preview-import').addEventListener('click', openPreviewModal);
    document.getElementById('tb-preview-cancel').addEventListener('click', function () {
      document.getElementById('tb-preview-modal').hidden = true;
    });
    document.getElementById('tb-preview-commit').addEventListener('click', commitImport);
    document.getElementById('tb-preview-dl-errors').addEventListener('click', downloadSkippedRowsCsv);

    document.getElementById('tb-apply').addEventListener('click', function () {
      readIdentity();
      readColors();
      if (state.franchiseCap.blocked) {
        return showError(
          escapeHtml(state.franchiseCap.message) +
            ' <a href="/mode-select.html">Open Mode Select</a>',
          { nearApply: true, html: true }
        );
      }
      if (!state.slot) return showError('Choose a slot first.', { nearApply: true });
      if (!state.identity.name || !validateAbbr()) {
        return showError('Finish identity before applying.', { nearApply: true });
      }
      if (
        state.roster_mode === 'import' &&
        state.import.headers.length &&
        !state.import.committed
      ) {
        return showError('Finish your CSV import or choose another roster option.', {
          nearApply: true,
        });
      }
      if (state.roster_mode === 'edit' && (!state.editor.loaded || !state.editor.players.length)) {
        return showError('Wait for the inherited roster to load, or choose another roster option.', {
          nearApply: true,
        });
      }
      const blockReason = currentBudgetBlockReason();
      if (blockReason) {
        syncBudgetRefuseUI();
        return showError(blockReason, { nearApply: true });
      }
      openConfirmModal();
    });
    document.getElementById('tb-confirm-cancel').addEventListener('click', function () {
      document.getElementById('tb-confirm-modal').hidden = true;
    });
    document.getElementById('tb-confirm-apply').addEventListener('click', applyFranchise);

    const portraitCancel = document.getElementById('tb-portrait-cancel');
    if (portraitCancel) {
      portraitCancel.addEventListener('click', function () {
        document.getElementById('tb-portrait-modal').hidden = true;
      });
    }
    const portraitFilters = document.getElementById('tb-portrait-filters');
    if (portraitFilters) {
      portraitFilters.addEventListener('click', function (e) {
        const chip = e.target.closest('[data-filter-axis]');
        if (!chip) return;
        const axis = chip.dataset.filterAxis;
        const value = chip.dataset.filterValue || null;
        if (axis === 'skin') state.portraitPicker.skin = value;
        if (axis === 'frame') state.portraitPicker.frame = value;
        if (axis === 'definition') state.portraitPicker.definition = value;
        refreshPortraitCatalog();
      });
    }
    const portraitGrid = document.getElementById('tb-portrait-grid');
    if (portraitGrid) {
      portraitGrid.addEventListener('click', function (e) {
        const btn = e.target.closest('[data-pick-image]');
        if (!btn) return;
        pickPortrait(btn.dataset.pickImage);
      });
    }

    syncCourtDefaultsFromTeamColors();
    setStep(0);
    updateModePill();
    updateApplyButtonState();
  });
})();
