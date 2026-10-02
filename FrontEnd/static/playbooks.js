function franchiseCtx() {
  return typeof window !== 'undefined' ? window.FranchiseContext : null;
}
function liveParams() {
  return franchiseCtx().toSearchParams();
}
function emptyParams() {
  return franchiseCtx().createParams();
}
function currentSearch() {
  const s = liveParams().toString();
  return s ? '?' + s : '';
}
function cloneParams(params) {
  const out = emptyParams();
  if (params && typeof params.forEach === 'function') {
    params.forEach((value, key) => out.set(key, value));
  }
  return out;
}


let root = null;
let page = null;
function byId(id) {
  if (root) {
    if (root.id === id) return root;
    const found = root.querySelector('#' + CSS.escape(id));
    if (found) return found;
  }
  return document.getElementById(id);
}

function qsa(sel) {
  return root ? root.querySelectorAll(sel) : document.querySelectorAll(sel);
}

function rootQuery(sel) {
  return root ? root.querySelector(sel) : document.querySelector(sel);
}

function inAppShell() {
  return !!(root && (root.id === 'playbooks-view' || (root.closest && root.closest('#playbooks-view'))));
}

  const MOTION_FOCUS_OPTIONS = [
    { value: "balanced", label: "Balanced" },
    { value: "inside", label: "Inside" },
    { value: "attack", label: "Attack" },
    { value: "outside", label: "Outside" },
  ];

  const TARGET_SHOOTER_OPTIONS = ["PG", "SG", "SF", "PF", "C"];
  const MAX_PC_ITEMS_PER_SIDE = 8;
  const PREVIEW_DEBOUNCE_MS = 300;
  const SAVE_NAV_DELAY_MS = 900;

  const ENFORCED_SECTIONS = new Set(["motion", "setPlays", "manDefense", "zoneDefense"]);
  const NORMALIZE_SECTIONS = new Set(["fastBreaks", "hcTraps"]);
  // Tab order: Offense, Defense, Fast Breaks, Press/Traps. Each is its own pane.
  const PLAYBOOK_TABS = ["offense", "defense", "fastBreaks", "pressTraps"];
  const SET_PLAY_FOCUS_GROUPS = [
    { key: "inside", label: "Inside" },
    { key: "attack", label: "Attack" },
    { key: "outside", label: "Outside" },
  ];

  const LOCK_API_KEYS = {
    motion: "motion",
    setPlays: "set_plays",
    fastBreaks: "fast_breaks",
    hcTraps: "hc_traps",
    manDefense: "man_defense",
    zoneDefense: "zone_defense",
  };

  const LOCK_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="11" width="14" height="9" rx="2"></rect><path d="M8 11V8a4 4 0 0 1 8 0v3"></path></svg>';
  // Open padlock: the unlocked state of the same button.
  const UNLOCK_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="11" width="14" height="9" rx="2"></rect><path d="M8 11V8a4 4 0 0 1 7.6-1.7"></path></svg>';
  const NOSLACK_COPY = "No room — the slack is locked. Unlock a play to make space.";

  function playSound(name) {
    import('/js/shared/uiSfx.js').then(function (m) { m.playSfx(name, 0.7); }).catch(function () {});
  }

  function parseInteger(value, fallback = 0) {
    const parsed = Number.parseInt(value, 10);
    return Number.isFinite(parsed) ? parsed : fallback;
  }

  function toPercentMap(items) {
    const result = {};
    items.forEach((item) => {
      result[item.id] = parseInteger(item.percentage, 0);
    });
    return result;
  }

  function normalizeMotionFocus(value) {
    if (value === "inside" || value === "attack" || value === "outside") {
      return value;
    }
    return null;
  }

  function displayMotionFocus(value) {
    return value || "balanced";
  }

  function displayMotionFocusLabel(value) {
    const normalized = displayMotionFocus(value);
    if (normalized === "inside") return "Inside";
    if (normalized === "attack") return "Attack";
    if (normalized === "outside") return "Outside";
    return "Balanced";
  }

  function setPlayFocusKey(focus) {
    const key = String(focus || "").toLowerCase();
    return (key === "inside" || key === "attack" || key === "outside") ? key : "other";
  }

  function setPlayFocusRank(focus) {
    if (typeof getSetPlayFocusRank === "function") return getSetPlayFocusRank(focus);
    const order = ["inside", "attack", "outside"];
    const index = order.indexOf(String(focus || "").toLowerCase());
    return index === -1 ? order.length : index;
  }

  /** Editor order for Set Plays: Inside, Attack, Outside; CMD high to low inside each. */
  function compareSetPlaysByFocusCmd(a, b) {
    return (setPlayFocusRank(a.focus) - setPlayFocusRank(b.focus))
      || (parseInteger(b.effectiveness, 0) - parseInteger(a.effectiveness, 0))
      || String(a.name || "").localeCompare(String(b.name || ""))
      || ((a._apiIndex || 0) - (b._apiIndex || 0));
  }

  function stableStringify(value) {
    if (Array.isArray(value)) return `[${value.map(stableStringify).join(",")}]`;
    if (value && typeof value === "object") {
      return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`).join(",")}}`;
    }
    return JSON.stringify(value === undefined ? null : value);
  }

  const EDITABLE_STATE_KEYS = ["motion", "setPlays", "fastBreaks", "hcTraps", "manDefense", "zoneDefense", "pcOrder", "positionFilters", "evenDistributionAll"];

  function sliderStep(event) {
    let dir = 0;
    if (event.key === "ArrowRight" || event.key === "ArrowUp") dir = 1;
    else if (event.key === "ArrowLeft" || event.key === "ArrowDown") dir = -1;
    if (!dir) return 0;
    return dir * (event.shiftKey ? 5 : 1);
  }

  function cmdClass(value) {
    const numeric = parseInteger(value, 0);
    if (typeof getPlaybookCmdClass === "function") {
      return getPlaybookCmdClass(numeric);
    }
    if (numeric >= 70) return "is-good";
    if (numeric >= 40) return "is-mid";
    return "is-low";
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  /** Largest-remainder proportional distribution of integer S across weights. */
  function distribute(weights, S) {
    const n = weights.length;
    if (n === 0) return [];
    if (S <= 0) return weights.map(() => 0);
    const total = weights.reduce((a, b) => a + b, 0);
    const raw = weights.map((w) => (total <= 0 ? (S / n) : (w / total * S)));
    const fl = raw.map((x) => Math.floor(x));
    const left = S - fl.reduce((a, b) => a + b, 0);
    const order = raw
      .map((x, i) => ({ i, r: x - Math.floor(x) }))
      .sort((a, b) => b.r - a.r);
    for (let k = 0; k < left && order.length; k++) {
      fl[order[k % order.length].i]++;
    }
    return fl;
  }

  /**
   * Enforced section edit. Inactive rows are out of the arithmetic entirely.
   * Mutates arr[].percentage. Returns true if target was hard-capped.
   */
  function setEnforced(arr, idx, target) {
    const edited = arr[idx];
    if (!edited || edited.isActive === false || edited.locked) return false;

    target = Math.round(target);

    const live = arr.filter((p) => p.isActive !== false);
    const lockedSum = live.reduce((s, p) => s + (p.locked ? p.percentage : 0), 0);

    const max = 100 - lockedSum;
    let capped = false;
    if (target > max) {
      target = max;
      capped = true;
    }
    if (target < 0) target = 0;

    const others = arr
      .map((p, i) => i)
      .filter((i) => i !== idx && !arr[i].locked && arr[i].isActive !== false);

    const dist = distribute(
      others.map((i) => arr[i].percentage),
      100 - lockedSum - target
    );
    others.forEach((i, k) => {
      arr[i].percentage = dist[k];
    });
    arr[idx].percentage = target;

    arr.forEach((p) => {
      if (p.isActive === false) p.percentage = 0;
    });

    return capped;
  }

  function activeItems(arr) {
    return arr.filter((p) => p.isActive !== false);
  }

  function lockedSumActive(arr) {
    return activeItems(arr).reduce((s, p) => s + (p.locked ? p.percentage : 0), 0);
  }

  function getComputedPlay(arr) {
    const live = activeItems(arr);
    const unlocked = live.filter((p) => !p.locked);
    if (unlocked.length !== 1) return null;
    return unlocked[0];
  }

  function ensureEnforcedBalance(arr) {
    arr.forEach((p) => {
      if (p.isActive === false) p.percentage = 0;
    });
    const live = activeItems(arr);
    if (!live.length) return;
    const sum = live.reduce((s, p) => s + p.percentage, 0);
    if (sum === 100) return;

    const locked = lockedSumActive(arr);
    const unlocked = live.filter((p) => !p.locked);
    if (!unlocked.length) return;
    const dist = distribute(
      unlocked.map((p) => p.percentage),
      Math.max(0, 100 - locked)
    );
    unlocked.forEach((p, k) => {
      p.percentage = dist[k];
    });
  }

  function buildPlayDetailsUrl(context, play) {
    const params = emptyParams();
    params.set("mode", context.mode);
    params.set("team_id", context.teamId);
    if (context.franchiseId) params.set("franchise_id", context.franchiseId);
    if (context.gameId) params.set("game_id", context.gameId);
    if (play.id) params.set("play_id", play.id);
    params.set("play_name", play.name);
    params.set("backTo", "playbooks.html");
    if (context.from) params.set("from", context.from);

    ["quarter", "period"].forEach((key) => {
      if (context.params.get(key)) params.set(key, context.params.get(key));
    });

    const playDetailsPath = (typeof API_CONFIG !== "undefined" && API_CONFIG.buildStaticPath)
      ? API_CONFIG.buildStaticPath("/play-details.html")
      : "/play-details.html";
    return `${playDetailsPath}?${params.toString()}`;
  }

  function buildPlaybookReportUrl(context) {
    const params = emptyParams();
    params.set("mode", context.mode);
    params.set("team_id", context.teamId);
    if (context.franchiseId) params.set("franchise_id", context.franchiseId);
    if (context.gameId) params.set("game_id", context.gameId);
    if (context.from) params.set("from", context.from);

    ["quarter", "period", "home", "away", "my_team", "return_url"].forEach((key) => {
      if (context.params.get(key)) params.set(key, context.params.get(key));
    });

    return `/playbook-report.html?${params.toString()}`;
  }

  function renderShotWeightsLocal(container, shotWeights, compact = false) {
    if (typeof renderShotWeights === "function") {
      renderShotWeights(container, shotWeights, compact);
      return;
    }
    if (!container) return;
    container.setAttribute("data-compact", compact ? "true" : "false");
    if (!shotWeights || (!shotWeights.playbooks && !shotWeights.playcall_center)) {
      container.innerHTML = '<p class="psw-unavailable">Shot weight data unavailable.</p>';
      return;
    }
    const POSITIONS = ["PG", "SG", "SF", "PF", "C"];
    function tokenPaint(name, fallback) {
      const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
      return value || fallback;
    }
    function getPswColor(pct) {
      if (pct > 35) return tokenPaint("--blue", "#4A90D9");
      if (pct >= 21) return tokenPaint("--green", "#34EC27");
      if (pct >= 11) return tokenPaint("--yellow", "#FFD700");
      return tokenPaint("--red", "#ff6d6d");
    }
    function renderGroup(label, data) {
      if (!data) return "";
      const values = POSITIONS.map((pos) => ({ pos, pct: data[pos] ?? 0 }));
      const maxPct = Math.max(...values.map((value) => value.pct));
      const pills = values.map(({ pos, pct }) => {
        const color = getPswColor(pct);
        const isDominant = pct === maxPct;
        return `
          <div class="psw-pill" style="border: 1px solid var(--line);">
            <div class="psw-pill-pos">${pos}</div>
            <div class="psw-pill-val" style="color: ${color};">${pct}%</div>
            <div class="psw-pill-accent" style="${isDominant ? `background: ${color}; opacity: 1;` : "opacity: 0;"}"></div>
          </div>
        `;
      }).join("");
      return `<div class="psw-group"><div class="psw-group-label">${label}</div><div class="psw-strip">${pills}</div></div>`;
    }
    container.innerHTML = `
      ${renderGroup("PLAYBOOKS", shotWeights.playbooks)}
      ${renderGroup("PLAYCALL CENTER", shotWeights.playcall_center)}
    `;
  }

  class PlaybooksPage {
    constructor(host, options) {
      options = options || {};
      this.params = liveParams();
      this.context = {
        params: this.params,
        mode: options.mode || this.params.get("mode") || "single",
        teamId: options.teamId || this.params.get("team_id") || "",
        franchiseId: options.franchiseId || this.params.get("franchise_id") || "",
        gameId: options.game_id || this.params.get("game_id") || "",
        from: options.from || this.params.get("from") || "",
        isGameplayContext: Boolean(options.game_id || this.params.get("game_id") || ""),
      };

      this.state = {
        motion: [],
        setPlays: [],
        fastBreaks: [],
        hcTraps: [],
        manDefense: [],
        zoneDefense: [],
        pcOrder: { offense: [], defense: [] },
        pcErrors: { offense: "", defense: "" },
        playbookMeta: { user_saved: false, schema_version: 2 },
        positionFilters: {},
        evenDistributionAll: false,
        activeTab: "offense",
        openPlayId: "",
      };

      this.toastTimer = null;
      this.toastHideTimer = null;
      this.previewTimer = null;
      this.previewAbort = null;
      this.dragContext = null;
      this.sliderDragging = false;
      this.draftStorageKey = this.buildDraftStorageKey();
      this.draftRestoreFlagKey = this.buildDraftRestoreFlagKey();

      this.elements = {
        saveBtn: byId("save-btn"),
        backBtn: byId("back-btn"),
        sectionsReadyIndicator: byId("sections-ready-indicator"),
        toast: byId("toast"),
        editColumn: byId("playbooks-edit-column"),
        shotWeightsLive: byId("shot-weights-live"),
        motionGrid: byId("motion-grid"),
        setPlaysGrid: byId("set-plays-grid"),
        manDefenseGrid: byId("man-defense-grid"),
        zoneDefenseGrid: byId("zone-defense-grid"),
        fastBreaksChips: byId("fast-breaks-chips"),
        hcTrapsChips: byId("hc-traps-chips"),
        motionTotal: byId("motion-total"),
        setPlaysTotal: byId("set-plays-total"),
        fastBreakTotal: byId("fast-breaks-total"),
        hcTrapTotal: byId("hc-traps-total"),
        manDefenseTotal: byId("man-defense-total"),
        zoneDefenseTotal: byId("zone-defense-total"),
        fastBreaksNormalize: byId("fast-breaks-normalize"),
        hcTrapsNormalize: byId("hc-traps-normalize"),
        pcOffense: byId("pc-order-offense"),
        pcDefense: byId("pc-order-defense"),
        pcCapOffense: byId("pc-cap-offense"),
        pcCapDefense: byId("pc-cap-defense"),
        pcErrorOffense: byId("pc-error-offense"),
        pcErrorDefense: byId("pc-error-defense"),
        gameplayLockout: byId("gameplay-lockout"),
      };
    }

    async init() {
      if (this.context.isGameplayContext) {
        this.renderGameplayLockout();
        this.bindGlobalEvents();
        return;
      }
      this.bindGlobalEvents();
      await this.loadData();
      this.markSaved();
      this.restoreDraftState();
      this.render();
      this.syncStickyOffsets();
      this.scheduleShotWeightsPreview(true);
    }

    isHosted() {
      return inAppShell();
    }

    editSnapshot() {
      const settings = { ...this.buildPreviewPayload().playbook_settings };
      delete settings._meta;
      delete settings.even_distribution_all;
      return stableStringify({ settings, play_updates: this.buildPlayUpdates() });
    }

    markSaved() {
      this.savedSnapshot = this.editSnapshot();
      const saved = {};
      EDITABLE_STATE_KEYS.forEach((key) => { saved[key] = this.state[key]; });
      this.savedState = JSON.parse(JSON.stringify(saved));
      this.syncSaveDirtyState();
    }

    hasEdits() {
      return this.savedSnapshot != null && this.editSnapshot() !== this.savedSnapshot;
    }

    revertEdits() {
      if (!this.savedState) return;
      const saved = JSON.parse(JSON.stringify(this.savedState));
      EDITABLE_STATE_KEYS.forEach((key) => { this.state[key] = saved[key]; });
      this.clearDraftState();
      this.render();
      this.scheduleShotWeightsPreview(true);
    }

    confirmLeave(proceed) {
      if (!window.GOBLeaveConfirm) {
        proceed();
        return;
      }
      window.GOBLeaveConfirm.open({
        title: "Unsaved Playbooks",
        copy: "Save your playbook changes before you leave?",
        saveLabel: "Save Playbooks",
        onSave: async () => {
          await this.handleSave();
          return !this.hasEdits();
        },
        onDiscard: () => this.revertEdits(),
        proceed,
      });
    }

    syncStickyOffsets() {
      // The tab row pins directly under the strip, so it needs the strip's real height
      // (it grows with density and when the read-out wraps).
      const strip = this.elements.shotWeightsLive;
      const column = this.elements.editColumn;
      if (strip && column) {
        column.style.setProperty("--pb-strip-h", `${strip.getBoundingClientRect().height}px`);
        if (!this._stripObserver && typeof ResizeObserver !== "undefined") {
          this._stripObserver = new ResizeObserver(() => this.syncStickyOffsets());
          this._stripObserver.observe(strip);
        }
      }
      const body = rootQuery(".playbooks-page-card-body");
      const header = rootQuery(".playbooks-page-card-header");
      if (!body || !header) return;
      const stickyTop = parseFloat(window.getComputedStyle(header).top) || 10;
      const gap = 12;
      body.style.setProperty(
        "--playbooks-sticky-under-header",
        `${Math.ceil(stickyTop + header.offsetHeight + gap)}px`
      );
    }

    buildDraftStorageKey() {
      return [
        "playbooksDraft",
        this.context.mode || "single",
        this.context.teamId || "",
        this.context.franchiseId || "",
        this.context.gameId || "",
      ].join(":");
    }

    buildDraftRestoreFlagKey() {
      return [
        "playbooksDraftRestoreOnce",
        this.context.mode || "single",
        this.context.teamId || "",
        this.context.franchiseId || "",
        this.context.gameId || "",
      ].join(":");
    }

    persistDraftState() {
      try {
        window.sessionStorage.setItem(this.draftStorageKey, JSON.stringify(this.state));
      } catch (error) {
        console.warn("Unable to persist playbooks draft:", error);
      }
    }

    markDraftForNextLoad() {
      try {
        window.sessionStorage.setItem(this.draftRestoreFlagKey, "1");
      } catch (error) {
        console.warn("Unable to mark playbooks draft for restore:", error);
      }
    }

    restoreDraftState() {
      try {
        const shouldRestore = window.sessionStorage.getItem(this.draftRestoreFlagKey) === "1";
        if (!shouldRestore) return;

        const raw = window.sessionStorage.getItem(this.draftStorageKey);
        if (!raw) return;
        const draft = JSON.parse(raw);
        if (!draft || typeof draft !== "object") return;

        ["motion", "setPlays", "fastBreaks", "hcTraps", "manDefense", "zoneDefense"].forEach((key) => {
          if (Array.isArray(draft[key])) this.state[key] = draft[key];
        });
        if (draft.pcOrder && typeof draft.pcOrder === "object") {
          this.state.pcOrder = {
            offense: Array.isArray(draft.pcOrder.offense) ? draft.pcOrder.offense.map(String) : [],
            defense: Array.isArray(draft.pcOrder.defense) ? draft.pcOrder.defense.map(String) : [],
          };
        }
        if (draft.playbookMeta && typeof draft.playbookMeta === "object") {
          this.state.playbookMeta = draft.playbookMeta;
        }
        if (draft.positionFilters && typeof draft.positionFilters === "object") {
          this.state.positionFilters = draft.positionFilters;
        }
        if (typeof draft.evenDistributionAll === "boolean") {
          this.state.evenDistributionAll = draft.evenDistributionAll;
        }
        if (PLAYBOOK_TABS.includes(draft.activeTab)) {
          this.state.activeTab = draft.activeTab;
        }
        if (typeof draft.openPlayId === "string") {
          this.state.openPlayId = draft.openPlayId;
        }
        ENFORCED_SECTIONS.forEach((key) => ensureEnforcedBalance(this.state[key]));
      } catch (error) {
        console.warn("Unable to restore playbooks draft:", error);
      } finally {
        try {
          window.sessionStorage.removeItem(this.draftRestoreFlagKey);
        } catch (storageError) {
          console.warn("Unable to clear playbooks draft restore flag:", storageError);
        }
      }
    }

    clearDraftState() {
      try {
        window.sessionStorage.removeItem(this.draftStorageKey);
        window.sessionStorage.removeItem(this.draftRestoreFlagKey);
      } catch (error) {
        console.warn("Unable to clear playbooks draft:", error);
      }
    }

    renderGameplayLockout() {
      if (this.elements.gameplayLockout) {
        this.elements.gameplayLockout.hidden = false;
      }
      const editColumn = this.elements.editColumn;
      if (editColumn) {
        editColumn.querySelectorAll(":scope > *:not(#gameplay-lockout)").forEach((node) => {
          node.hidden = true;
        });
      }
      rootQuery(".pc-card")?.setAttribute("hidden", "");
      if (this.elements.saveBtn) this.elements.saveBtn.hidden = true;
      if (this.elements.sectionsReadyIndicator) this.elements.sectionsReadyIndicator.hidden = true;
    }

    bindGlobalEvents() {
      this.elements.backBtn?.addEventListener("click", (event) => {
        event.preventDefault();
        this.handleBack();
      });
      this.elements.saveBtn?.addEventListener("click", () => {
        playSound("SFX_COMMIT");
        this.handleSave();
      });

      qsa(".playbooks-tab").forEach((tab) => {
        tab.addEventListener("click", () => {
          playSound("SFX_SELECT");
          this.state.activeTab = PLAYBOOK_TABS.includes(tab.dataset.tab) ? tab.dataset.tab : "offense";
          this.applyTab();
        });
      });

      this.elements.fastBreaksNormalize?.addEventListener("click", () => {
        playSound("SFX_SELECT");
        this.normalizeSection("fastBreaks");
      });
      this.elements.hcTrapsNormalize?.addEventListener("click", () => {
        playSound("SFX_SELECT");
        this.normalizeSection("hcTraps");
      });
      this._onResize = () => this.syncStickyOffsets();
      window.addEventListener("resize", this._onResize);
    }

    applyTab() {
      const tab = PLAYBOOK_TABS.includes(this.state.activeTab) ? this.state.activeTab : "offense";
      qsa(".playbooks-tab").forEach((button) => {
        const on = button.dataset.tab === tab;
        button.classList.toggle("on", on);
        button.setAttribute("aria-selected", on ? "true" : "false");
      });
      qsa(".playbooks-tabpane").forEach((pane) => {
        const on = pane.dataset.pane === tab;
        pane.classList.toggle("on", on);
        pane.hidden = !on;
      });
    }

    async loadData() {
      const params = emptyParams();
      params.set("mode", this.context.mode);
      params.set("team_id", this.context.teamId);
      if (this.context.franchiseId) params.set("franchise_id", this.context.franchiseId);
      if (this.context.gameId) params.set("game_id", this.context.gameId);

      const response = await fetch(`${API_CONFIG.buildUrl("/api/playbooks")}?${params.toString()}`);
      if (!response.ok) {
        throw new Error(`Failed to load playbooks (${response.status})`);
      }

      const data = await response.json();
      if (window.StateTelemetry) {
        window.StateTelemetry.logBackendRead("playbook_settings", data, "/api/playbooks");
      }

      this.buildStateFromApi(data);

      if (data.position_shot_weights && this.elements.shotWeightsLive) {
        this.paintShotWeights(data.position_shot_weights);
      }
    }

    emptyLocks() {
      return {
        motion: [],
        set_plays: [],
        fast_breaks: [],
        hc_traps: [],
        man_defense: [],
        zone_defense: [],
      };
    }

    buildStateFromApi(data) {
      const percentages = data.simple_playbook_percentages || data.playbook_percentages || {};
      const pcOrder = data.pc_order || { offense: [], defense: [] };
      const locks = data.locks && typeof data.locks === "object"
        ? { ...this.emptyLocks(), ...data.locks }
        : this.emptyLocks();

      const lockedSet = (apiKey) => new Set((locks[apiKey] || []).map(String));

      this.state.playbookMeta = data.playbook_meta || { user_saved: false, schema_version: 2 };
      this.state.positionFilters = data.position_filters || {};
      this.state.evenDistributionAll = Boolean(data.even_distribution_all);
      this.state.pcOrder = {
        offense: (pcOrder.offense || []).map(String),
        defense: (pcOrder.defense || []).map(String),
      };

      const motionLocks = lockedSet("motion");
      this.state.motion = (data.motion || []).map((play) => ({
        id: String(play.play_id),
        name: play.name,
        percentage: parseInteger(percentages.motion?.[play.play_id], 0),
        motion_focus: normalizeMotionFocus(play.motion_focus),
        locked: motionLocks.has(String(play.play_id)),
        effectiveness: parseInteger(play.effectiveness, 0),
        top_scorer: play.top_scorer || "N/A",
        copy_1: play.copy && play.copy.copy_1 ? String(play.copy.copy_1) : "",
        isActive: true,
      }));

      const setLocks = lockedSet("set_plays");
      this.state.setPlays = (data.set_plays || []).map((play, index) => ({
        id: String(play.play_id),
        name: play.name,
        focus: play.play_focus || "",
        percentage: parseInteger(percentages.set_plays?.[play.play_id], 0),
        target_shooter: play.target_shooter || "PG",
        locked: setLocks.has(String(play.play_id)),
        effectiveness: parseInteger(play.effectiveness, 0),
        top_scorer: play.top_scorer || "N/A",
        copy_1: play.copy && play.copy.copy_1 ? String(play.copy.copy_1) : "",
        isActive: true,
        _apiIndex: index,
      }));
      this.state.setPlays.sort(compareSetPlaysByFocusCmd);

      const fbLocks = lockedSet("fast_breaks");
      this.state.fastBreaks = (data.fast_breaks || []).map((row) => ({
        id: String(row.id),
        name: row.name,
        percentage: parseInteger(percentages.fast_breaks?.[row.id], 0),
        locked: fbLocks.has(String(row.id)),
        effectiveness: parseInteger(row.effectiveness, 0),
        top_scorer: row.top_scorer || "",
        isActive: true,
      }));

      const trapLocks = lockedSet("hc_traps");
      this.state.hcTraps = (data.hc_traps || []).map((row) => ({
        id: String(row.id),
        name: row.name,
        percentage: parseInteger(percentages.hc_traps?.[row.id], 0),
        locked: trapLocks.has(String(row.id)),
        effectiveness: parseInteger(row.effectiveness, 0),
        top_scorer: row.top_scorer || "",
        isActive: true,
      }));

      const manLocks = lockedSet("man_defense");
      this.state.manDefense = (data.man_defense_rows || []).map((row) => ({
        id: String(row.id),
        name: row.name,
        percentage: parseInteger(percentages.man_defense?.[row.id], 0),
        locked: manLocks.has(String(row.id)),
        effectiveness: parseInteger(row.effectiveness, 0),
        top_scorer: row.top_scorer || "N/A",
        isActive: row.is_active !== false,
      }));

      const zoneLocks = lockedSet("zone_defense");
      this.state.zoneDefense = (data.zone_defense_rows || []).map((row) => ({
        id: String(row.id),
        name: row.name,
        percentage: parseInteger(percentages.zone_defense?.[row.id], 0),
        locked: zoneLocks.has(String(row.id)),
        effectiveness: parseInteger(row.effectiveness, 0),
        top_scorer: row.top_scorer || "N/A",
        isActive: true,
      }));

      this.state.pcOrder.offense = this.state.pcOrder.offense.filter((id) =>
        this.state.motion.some((item) => item.id === id)
        || this.state.setPlays.some((item) => item.id === id)
      );
      this.state.pcOrder.defense = this.state.pcOrder.defense.filter((id) =>
        this.state.manDefense.some((item) => item.id === id)
        || this.state.zoneDefense.some((item) => item.id === id)
      );

      ENFORCED_SECTIONS.forEach((key) => ensureEnforcedBalance(this.state[key]));
    }

    buildLocksPayload() {
      const locks = this.emptyLocks();
      Object.entries(LOCK_API_KEYS).forEach(([stateKey, apiKey]) => {
        locks[apiKey] = (this.state[stateKey] || [])
          .filter((item) => item.locked && item.isActive !== false)
          .map((item) => item.id);
      });
      return locks;
    }

    inPCC(id, side) {
      return this.state.pcOrder[side].includes(id);
    }

    pccBadge(id, side) {
      const index = this.state.pcOrder[side].indexOf(id);
      return index >= 0 ? index + 1 : null;
    }

    render() {
      this.applyTab();
      this.renderEnforcedGrid("motion", this.elements.motionGrid, "offense", { kind: "motion" });
      this.renderEnforcedGrid("setPlays", this.elements.setPlaysGrid, "offense", { kind: "set" });
      this.renderEnforcedGrid("manDefense", this.elements.manDefenseGrid, "defense", { kind: "man" });
      this.renderEnforcedGrid("zoneDefense", this.elements.zoneDefenseGrid, "defense", { kind: "zone" });
      this.renderChipStrip("fastBreaks", this.elements.fastBreaksChips);
      this.renderChipStrip("hcTraps", this.elements.hcTrapsChips);
      this.renderPcLists();
      this.updateTotals();
      this.updateSectionCounts();
    }

    updateSectionCounts() {
      const set = (id, text) => {
        const el = byId(id);
        if (el) el.textContent = text;
      };
      const describe = (arr, flexible) => {
        const live = activeItems(arr).length;
        const later = arr.filter((item) => item.isActive === false).length;
        let text = `${live} play${live === 1 ? "" : "s"}`;
        if (later) text += ` · ${later} coming later`;
        if (flexible) text += " · must total 100";
        return text;
      };
      set("motion-count", describe(this.state.motion, false));
      set("set-plays-count", describe(this.state.setPlays, false));
      set("man-defense-count", describe(this.state.manDefense, false));
      set("zone-defense-count", describe(this.state.zoneDefense, false));
      set("fast-breaks-count", describe(this.state.fastBreaks, true));
      set("hc-traps-count", describe(this.state.hcTraps, true));
    }

    renderEnforcedGrid(sectionKey, container, side, options) {
      if (!container) return;
      const arr = this.state[sectionKey];
      const noSlack = 100 - lockedSumActive(arr) === 0;
      const computed = getComputedPlay(arr);
      const liveCount = activeItems(arr).length;
      const computedNote = liveCount === 1
        ? "Determined — the only active play."
        : "Determined — the only unlocked play.";
      container.innerHTML = "";

      // Set Plays read as three sub-sections. The list is already sorted by focus
      // (compareSetPlaysByFocusCmd), so a head goes in where the focus changes.
      let lastFocus = null;
      arr.forEach((item, idx) => {
        if (options.kind === "set") {
          const focus = setPlayFocusKey(item.focus);
          if (focus !== lastFocus) {
            lastFocus = focus;
            container.appendChild(this.buildSetPlayGroupHead(focus, arr));
          }
        }
        if (item.isActive === false) {
          container.appendChild(this.buildDeadTile(item));
          return;
        }

        const tile = this.buildEnforcedTile(item, sectionKey, side, options, {
          noSlack,
          isComputed: computed && computed.id === item.id,
          computedNote,
        });
        container.appendChild(tile);
        this.bindEnforcedTile(tile, sectionKey, idx, side, options);
        if (this.state.openPlayId === item.id) {
          const detail = this.buildPlayDetail(item, sectionKey, side, options, tile._detailFlags || {});
          container.appendChild(detail);
          this.bindPlayDetail(detail, tile, sectionKey, idx, side, options);
        }
      });
    }

    /** Sub-section head inside Set Plays: the focus, its play count and its share. */
    buildSetPlayGroupHead(focus, arr) {
      const group = SET_PLAY_FOCUS_GROUPS.find((entry) => entry.key === focus);
      const plays = arr.filter((item) => setPlayFocusKey(item.focus) === focus);
      const head = document.createElement("div");
      head.className = "pb-sub";
      head.dataset.focusGroup = focus;
      head.innerHTML = `
        <div class="pb-sub-title"><h3>${escapeHtml(group ? group.label : "Other")}</h3><span class="pb-sub-cnt">${plays.length} ${plays.length === 1 ? "play" : "plays"}</span></div>
        <span class="pb-sub-tot" data-focus-total="${escapeHtml(focus)}"></span>
      `;
      return head;
    }

    /** Each Set Plays sub-section shows how much of the 100% it holds. */
    paintSetPlayGroupTotals() {
      const grid = this.elements.setPlaysGrid;
      if (!grid) return;
      grid.querySelectorAll("[data-focus-total]").forEach((el) => {
        const focus = el.dataset.focusTotal;
        const sum = activeItems(this.state.setPlays)
          .filter((item) => setPlayFocusKey(item.focus) === focus)
          .reduce((total, item) => total + item.percentage, 0);
        el.textContent = `${sum}%`;
      });
    }

    buildDeadTile(item) {
      const el = document.createElement("div");
      el.className = "play lk";
      el.dataset.id = item.id;
      el.title = "Not editable until this play ships";
      el.innerHTML = `
        <div class="pn"><b>${escapeHtml(item.name)}</b><span>Coming later</span></div>
        <span></span>
        <span></span>
        <span class="slot lk" aria-hidden="true">${LOCK_SVG}</span>
      `;
      return el;
    }

    playCanJoinCallSheet(sectionKey) {
      return sectionKey === "motion" || sectionKey === "setPlays"
        || sectionKey === "manDefense" || sectionKey === "zoneDefense";
    }

    buildPccButton(item, side, sectionKey) {
      if (!this.playCanJoinCallSheet(sectionKey)) return "<span></span>";
      const assigned = this.inPCC(item.id, side);
      const badge = this.pccBadge(item.id, side);
      const full = this.state.pcOrder[side].length >= MAX_PC_ITEMS_PER_SIDE && !assigned;
      if (assigned) {
        return `<button class="slot" type="button" data-pcc-toggle="${escapeHtml(item.id)}" data-side="${side}" title="Call sheet slot ${badge}">${badge}</button>`;
      }
      if (full) {
        return `<button class="slot add" type="button" data-pcc-toggle="${escapeHtml(item.id)}" data-side="${side}" disabled title="Call sheet full">+</button>`;
      }
      return `<button class="slot add" type="button" data-pcc-toggle="${escapeHtml(item.id)}" data-side="${side}" title="Add to call sheet">+</button>`;
    }

    playMeta(item, options) {
      if (options.kind === "motion") return `Focus · ${displayMotionFocusLabel(item.motion_focus)}`;
      // The focus is the sub-section the play sits in, so the line names only the shooter.
      if (options.kind === "set") return `Target shooter ${item.target_shooter || "PG"}`;
      if (item.top_scorer && item.top_scorer !== "N/A") return `Top scorer · ${item.top_scorer}`;
      return "";
    }

    toggleOpenPlay(id) {
      this.state.openPlayId = this.state.openPlayId === id ? "" : id;
      this.render();
    }

    buildPlayDetail(item, sectionKey, side, options, flags) {
      const detail = document.createElement("div");
      detail.className = "pdet";
      const copy = item.copy_1 ? `<p>${escapeHtml(item.copy_1)}</p>` : "";
      const slot = this.pccBadge(item.id, side);
      const shooter = options.kind === "set"
        ? `<div><span class="lbl">Target shooter</span><b>${escapeHtml(item.target_shooter || "PG")}${item.top_scorer && item.top_scorer !== "N/A" ? `<small>${escapeHtml(item.top_scorer)}</small>` : ""}</b></div>`
        : options.kind === "motion"
          ? `<div><span class="lbl">Focus</span><b>${escapeHtml(displayMotionFocusLabel(item.motion_focus))}</b></div>`
          : "";
      const top = item.top_scorer && item.top_scorer !== "N/A"
        ? `<div><span class="lbl">Top scorer</span><b>${escapeHtml(item.top_scorer)}</b></div>`
        : "";
      const sheet = this.playCanJoinCallSheet(sectionKey)
        ? `<div><span class="lbl">Call sheet</span><b>${slot ? `${slot}<small>of 8</small>` : "—"}</b></div>`
        : "";
      const selectHtml = this.buildSelectControl(item, options);
      const tools = selectHtml ? `<div class="pdet-tools">${selectHtml}</div>` : "";
      const note = flags.isComputed ? `<p class="pdet-note">${escapeHtml(flags.computedNote || "")}</p>` : "";
      const noSlack = flags.noSlackHere ? `<p class="pdet-note">${NOSLACK_COPY}</p>` : "";
      detail.innerHTML = `
        ${copy}
        ${note}
        ${noSlack}
        <div class="kv">
          <div><span class="lbl">Weight</span><b>${item.percentage}%</b></div>
          <div><span class="lbl">CMD</span><b>${parseInteger(item.effectiveness, 0)}</b></div>
          ${shooter}
          ${top}
          ${sheet}
        </div>
        ${tools}
      `;
      return detail;
    }

    buildSelectControl(item, options) {
      if (options.kind === "motion") {
        const current = displayMotionFocus(item.motion_focus);
        const opts = MOTION_FOCUS_OPTIONS.map((option) =>
          `<option value="${option.value}" ${current === option.value ? "selected" : ""}>${option.label}</option>`
        ).join("");
        return `<label class="sel lg"><select class="motion-focus-select" data-id="${escapeHtml(item.id)}">${opts}</select></label>`;
      }
      if (options.kind === "set") {
        const opts = TARGET_SHOOTER_OPTIONS.map((value) =>
          `<option value="${value}" ${item.target_shooter === value ? "selected" : ""}>${value}</option>`
        ).join("");
        return `<label class="sel"><select class="target-shooter-select" data-id="${escapeHtml(item.id)}">${opts}</select></label>`;
      }
      return "";
    }

    buildEnforcedTile(item, sectionKey, side, options, flags) {
      const el = document.createElement("div");
      const inPcc = this.inPCC(item.id, side);
      const dim = item.percentage === 0 && !inPcc && !item.locked && !flags.noSlack;
      const noSlackHere = item.percentage === 0 && !inPcc && flags.noSlack;
      const open = this.state.openPlayId === item.id;
      const classes = ["play"];
      if (inPcc) classes.push("on");
      if (open) classes.push("open");
      if (item.locked) classes.push("is-locked");
      if (dim) classes.push("is-dim");
      if (noSlackHere) classes.push("is-noslack");
      if (flags.isComputed) classes.push("is-computed");
      if (item.percentage === 0 && !flags.isComputed) classes.push("is-floor");
      el.className = classes.join(" ");
      el.dataset.id = item.id;
      el.dataset.section = sectionKey;
      if (options.kind === "set" && item.focus) el.dataset.focus = String(item.focus).toLowerCase();

      const meta = this.playMeta(item, options);
      const name = escapeHtml(item.name);
      const pctBlock = flags.isComputed
        ? `<b>${item.percentage}%</b>`
        : `<input class="et-pct-input${item.percentage >= 100 ? " threed" : ""}" data-pct="${escapeHtml(item.id)}" value="${item.percentage}" inputmode="numeric" aria-label="${name} weight"${item.locked ? ' readonly tabindex="-1" aria-readonly="true"' : ""}><b aria-hidden="true">%</b>`;
      const slider = flags.isComputed || item.locked
        ? `<span class="wb" aria-hidden="true"><i style="width:${item.percentage}%"></i></span>`
        : `<span class="wb et-slider" data-sl="${escapeHtml(item.id)}" role="slider" tabindex="0" aria-label="${name} weight" aria-valuenow="${item.percentage}" aria-valuetext="${item.percentage}%" aria-valuemin="0" aria-valuemax="100"><i style="width:${item.percentage}%"></i></span>`;
      const lock = ENFORCED_SECTIONS.has(sectionKey)
        ? `<button class="wl${item.locked ? " on" : ""}" type="button" data-lock="${escapeHtml(item.id)}" aria-pressed="${item.locked ? "true" : "false"}" aria-label="${item.locked ? "Unlock" : "Lock"} ${name}" title="${item.locked ? "Locked: click to unlock" : "Lock this weight"}">${item.locked ? LOCK_SVG : UNLOCK_SVG}</button>`
        : "";

      el.innerHTML = `
        <div class="pn"><b>${name}</b>${meta ? `<span>${escapeHtml(meta)}</span>` : ""}</div>
        <div class="wt">${lock}${slider}${pctBlock}</div>
        <div class="cmd"><b>${parseInteger(item.effectiveness, 0)}</b></div>
        ${this.buildPccButton(item, side, sectionKey)}
      `;
      el._detailFlags = { ...flags, noSlackHere };
      return el;
    }

    bindPlayDetail(detail, tile, sectionKey, idx, side, options) {
      const arr = this.state[sectionKey];
      const item = arr[idx];
      if (!item) return;

      const select = detail.querySelector(".motion-focus-select, .target-shooter-select");
      if (select) {
        select.addEventListener("change", () => {
          playSound("SFX_SELECT");
          if (options.kind === "motion") {
            item.motion_focus = normalizeMotionFocus(select.value);
          } else if (options.kind === "set") {
            item.target_shooter = select.value;
          }
          this.state.evenDistributionAll = false;
          this.render();
          this.scheduleShotWeightsPreview();
        });
      }
    }

    bindEnforcedTile(tile, sectionKey, idx, side, options) {
      const arr = this.state[sectionKey];
      const item = arr[idx];
      if (!item || item.isActive === false) return;

      tile.addEventListener("click", (event) => {
        if (event.target.closest("[data-pcc-toggle], [data-lock], .et-pct-input, .et-slider, select")) return;
        playSound("SFX_SELECT");
        this.toggleOpenPlay(item.id);
      });

      tile.querySelector("[data-pcc-toggle]")?.addEventListener("click", (event) => {
        event.stopPropagation();
        const button = event.currentTarget;
        if (button.disabled) return;
        playSound("SFX_SELECT");
        this.togglePcc(item.id, side);
      });

      tile.querySelector("[data-lock]")?.addEventListener("click", (event) => {
        event.stopPropagation();
        playSound("SFX_SELECT");
        item.locked = !item.locked;
        this.state.evenDistributionAll = false;
        ensureEnforcedBalance(arr);
        this.render();
        this.scheduleShotWeightsPreview();
        rootQuery(`.play[data-id="${CSS.escape(item.id)}"] [data-lock]`)?.focus();
      });

      if (tile.classList.contains("is-computed") || item.locked) {
        return;
      }

      const slider = tile.querySelector(".et-slider");
      if (slider) {
        slider.addEventListener("keydown", (event) => {
          const step = sliderStep(event);
          if (!step) return;
          event.preventDefault();
          event.stopPropagation();
          setEnforced(arr, idx, item.percentage + step);
          this.state.evenDistributionAll = false;
          this.paintEnforcedSection(sectionKey);
          this.updateTotals();
          this.renderPcLists();
          this.scheduleShotWeightsPreview();
        });
        let dragging = false;
        const move = (clientX) => {
          const rect = slider.getBoundingClientRect();
          const ratio = rect.width > 0 ? (clientX - rect.left) / rect.width : 0;
          setEnforced(arr, idx, ratio * 100);
          this.paintEnforcedSection(sectionKey);
          this.updateTotals();
        };
        slider.addEventListener("pointerdown", (event) => {
          if (item.locked) return;
          event.stopPropagation();
          slider.focus({ preventScroll: true });
          dragging = true;
          this.sliderDragging = true;
          this.elements.editColumn?.classList.add("no-anim");
          slider.setPointerCapture(event.pointerId);
          move(event.clientX);
        });
        slider.addEventListener("pointermove", (event) => {
          if (dragging) move(event.clientX);
        });
        const end = () => {
          if (!dragging) return;
          dragging = false;
          this.sliderDragging = false;
          this.elements.editColumn?.classList.remove("no-anim");
          playSound("SFX_SELECT");
          this.state.evenDistributionAll = false;
          this.render();
          this.refocusSlider("data-sl", item.id);
          this.scheduleShotWeightsPreview();
        };
        slider.addEventListener("pointerup", end);
        slider.addEventListener("pointercancel", end);
      }

      const input = tile.querySelector(".et-pct-input");
      if (input) {
        input.addEventListener("click", (event) => event.stopPropagation());
        input.addEventListener("input", () => {
          input.value = input.value.replace(/[^0-9]/g, "");
        });
        const commit = () => {
          const next = Math.max(0, Math.min(100, parseInteger(input.value, 0)));
          if (next === item.percentage) {
            input.value = String(item.percentage);
            input.classList.toggle("threed", item.percentage >= 100);
            return;
          }
          playSound("SFX_SELECT");
          setEnforced(arr, idx, next);
          this.state.evenDistributionAll = false;
          this.render();
          this.scheduleShotWeightsPreview();
        };
        input.addEventListener("blur", commit);
        input.addEventListener("keydown", (event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            input.blur();
          }
        });
      }
    }

    /**
     * render() rebuilds every tile, so the slider that was just dragged is gone and the
     * keyboard would have nothing to act on. Focus the slider that replaced it.
     */
    refocusSlider(attr, id) {
      const next = rootQuery(`[${attr}="${CSS.escape(id)}"]`);
      if (next && typeof next.focus === "function") next.focus({ preventScroll: true });
    }

    paintEnforcedSection(sectionKey) {
      const arr = this.state[sectionKey];
      arr.forEach((item) => {
        if (item.isActive === false) return;
        const tile = rootQuery(`.play[data-id="${CSS.escape(item.id)}"]`);
        if (!tile) return;
        const fill = tile.querySelector(".wb i");
        if (fill) fill.style.width = `${item.percentage}%`;
        const slider = tile.querySelector(".et-slider");
        if (slider) {
          slider.setAttribute("aria-valuenow", String(item.percentage));
          slider.setAttribute("aria-valuetext", `${item.percentage}%`);
        }
        const input = tile.querySelector(".et-pct-input");
        if (input && document.activeElement !== input) {
          input.value = String(item.percentage);
          input.classList.toggle("threed", item.percentage >= 100);
        }
        tile.classList.toggle("is-floor", item.percentage === 0 && !tile.classList.contains("is-computed"));
      });
    }

    renderChipStrip(sectionKey, container) {
      if (!container) return;
      container.innerHTML = "";
      const side = sectionKey === "hcTraps" ? "defense" : "offense";
      this.state[sectionKey].forEach((item) => {
        const chip = document.createElement("div");
        const open = this.state.openPlayId === item.id;
        chip.className = `play${open ? " open" : ""}`;
        chip.dataset.id = item.id;
        chip.dataset.section = sectionKey;
        const meta = this.playMeta(item, {});
        const cmd = Number.isFinite(item.effectiveness) ? parseInteger(item.effectiveness, 0) : "—";
        chip.innerHTML = `
          <div class="pn"><b>${escapeHtml(item.name)}</b>${meta ? `<span>${escapeHtml(meta)}</span>` : ""}</div>
          <div class="wt">
            <span class="wb et-slider chip-slider" data-csl="${escapeHtml(item.id)}" role="slider" tabindex="0" aria-label="${escapeHtml(item.name)} weight" aria-valuenow="${item.percentage}" aria-valuetext="${item.percentage}%" aria-valuemin="0" aria-valuemax="100"><i style="width:${item.percentage}%"></i></span>
            <input data-cpct="${escapeHtml(item.id)}" value="${item.percentage}" inputmode="numeric" aria-label="${escapeHtml(item.name)} weight">
            <b aria-hidden="true">%</b>
          </div>
          <div class="cmd"><b>${cmd}</b></div>
          <span></span>
        `;
        container.appendChild(chip);
        this.bindChip(chip, sectionKey, item);
        if (open) {
          const detail = this.buildPlayDetail(item, sectionKey, side, {}, {});
          container.appendChild(detail);
        }
      });
    }

    bindChip(chip, sectionKey, item) {
      chip.addEventListener("click", (event) => {
        if (event.target.closest("[data-cpct], .chip-slider")) return;
        playSound("SFX_SELECT");
        this.toggleOpenPlay(item.id);
      });

      const slider = chip.querySelector(".chip-slider");
      if (slider) {
        slider.addEventListener("keydown", (event) => {
          const step = sliderStep(event);
          if (!step) return;
          event.preventDefault();
          event.stopPropagation();
          item.percentage = Math.max(0, Math.min(100, item.percentage + step));
          this.state.evenDistributionAll = false;
          this.paintChip(item);
          this.updateTotals();
          this.scheduleShotWeightsPreview();
        });
        let dragging = false;
        const move = (clientX) => {
          const rect = slider.getBoundingClientRect();
          const ratio = rect.width > 0 ? (clientX - rect.left) / rect.width : 0;
          item.percentage = Math.max(0, Math.min(100, Math.round(ratio * 100)));
          this.paintChip(item);
          this.updateTotals();
        };
        slider.addEventListener("pointerdown", (event) => {
          event.stopPropagation();
          slider.focus({ preventScroll: true });
          dragging = true;
          this.elements.editColumn?.classList.add("no-anim");
          slider.setPointerCapture(event.pointerId);
          move(event.clientX);
        });
        slider.addEventListener("pointermove", (event) => {
          if (dragging) move(event.clientX);
        });
        const end = () => {
          if (!dragging) return;
          dragging = false;
          this.elements.editColumn?.classList.remove("no-anim");
          playSound("SFX_SELECT");
          this.state.evenDistributionAll = false;
          this.render();
          this.refocusSlider("data-csl", item.id);
          this.scheduleShotWeightsPreview();
        };
        slider.addEventListener("pointerup", end);
        slider.addEventListener("pointercancel", end);
      }

      const input = chip.querySelector("[data-cpct]");
      if (input) {
        input.addEventListener("click", (event) => event.stopPropagation());
        input.addEventListener("input", () => {
          input.value = input.value.replace(/[^0-9]/g, "");
        });
        const commit = () => {
          const next = Math.max(0, Math.min(100, parseInteger(input.value, 0)));
          if (next === item.percentage) {
            input.value = String(item.percentage);
            return;
          }
          playSound("SFX_SELECT");
          item.percentage = next;
          this.state.evenDistributionAll = false;
          this.render();
          this.scheduleShotWeightsPreview();
        };
        input.addEventListener("blur", commit);
        input.addEventListener("keydown", (event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            input.blur();
          }
        });
      }
    }

    paintChip(item) {
      qsa(`.play[data-id="${CSS.escape(item.id)}"]`).forEach((chip) => {
        const fill = chip.querySelector(".wb i");
        if (fill) fill.style.width = `${item.percentage}%`;
        const slider = chip.querySelector(".chip-slider");
        if (slider) {
          slider.setAttribute("aria-valuenow", String(item.percentage));
          slider.setAttribute("aria-valuetext", `${item.percentage}%`);
        }
        const input = chip.querySelector("[data-cpct]");
        if (input && document.activeElement !== input) {
          input.value = String(item.percentage);
        }
      });
    }

    normalizeSection(sectionKey) {
      const arr = this.state[sectionKey];
      const liveIndexes = [];
      const weights = [];
      arr.forEach((item, index) => {
        if (item.isActive === false) {
          item.percentage = 0;
          return;
        }
        liveIndexes.push(index);
        weights.push(item.percentage);
      });
      const dist = distribute(weights, 100);
      liveIndexes.forEach((index, k) => {
        arr[index].percentage = dist[k];
      });
      this.state.evenDistributionAll = false;
      this.render();
      this.scheduleShotWeightsPreview();
    }

    togglePcc(id, side) {
      const list = this.state.pcOrder[side];
      const index = list.indexOf(id);
      if (index >= 0) {
        list.splice(index, 1);
        this.state.pcErrors[side] = "";
      } else if (list.length >= MAX_PC_ITEMS_PER_SIDE) {
        this.state.pcErrors[side] = "Playcall Center is full. Remove a play to add another.";
        this.renderPcLists();
        return;
      } else {
        list.push(id);
        this.state.pcErrors[side] = "";
      }
      this.render();
      this.scheduleShotWeightsPreview();
    }

    renderPcLists() {
      this.renderPcList("offense", this.elements.pcOffense, this.state.pcOrder.offense, this.elements.pcCapOffense);
      this.renderPcList("defense", this.elements.pcDefense, this.state.pcOrder.defense, this.elements.pcCapDefense);
      if (this.elements.pcErrorOffense) {
        this.elements.pcErrorOffense.textContent = this.state.pcErrors.offense || "";
      }
      if (this.elements.pcErrorDefense) {
        this.elements.pcErrorDefense.textContent = this.state.pcErrors.defense || "";
      }
    }

    renderPcList(listType, container, order, capEl) {
      if (!container) return;
      container.innerHTML = "";
      const open = MAX_PC_ITEMS_PER_SIDE - order.length;
      if (capEl) {
        capEl.classList.toggle("full", open === 0);
        capEl.innerHTML = `<i>${order.length}</i> of 8`;
      }

      order.forEach((id, index) => {
        const item = this.findItemById(listType, id);
        if (!item) return;
        const section = this.getPcItemSection(item);
        const row = document.createElement("div");
        row.className = "csr";
        row.draggable = true;
        row.dataset.id = id;
        row.dataset.listType = listType;
        row.dataset.slotIndex = String(index);
        row.innerHTML = `
          <i>${index + 1}</i>
          <span class="gr" aria-hidden="true"></span>
          <span class="cs-n">${escapeHtml(item.name)}${section ? `<small>${escapeHtml(section)}</small>` : ""}</span>
          <span class="cs-p">${item.percentage}%</span>
          <span class="cs-c">${parseInteger(item.effectiveness, 0)}</span>
          <button class="pc-remove-btn" type="button" aria-label="Remove ${escapeHtml(item.name)}">×</button>
        `;
        row.addEventListener("dragover", (event) => this.handleDragOver(event, row));
        row.addEventListener("dragleave", () => this.clearDropHints());
        row.addEventListener("drop", (event) => this.handleDrop(event, listType, index));
        row.addEventListener("dragstart", (event) => this.handleDragStart(event, listType, id));
        row.addEventListener("dragend", () => this.handleDragEnd());
        row.querySelector(".pc-remove-btn").addEventListener("click", () => {
          playSound("SFX_SELECT");
          this.state.pcOrder[listType] = this.state.pcOrder[listType].filter((entry) => entry !== id);
          this.state.pcErrors[listType] = "";
          this.render();
          this.scheduleShotWeightsPreview();
        });
        container.appendChild(row);
      });

      if (open > 0) {
        const filler = document.createElement("div");
        filler.className = "csr open";
        filler.textContent = `${open} open`;
        filler.addEventListener("dragover", (event) => this.handleDragOver(event, filler));
        filler.addEventListener("dragleave", () => this.clearDropHints());
        filler.addEventListener("drop", (event) => this.handleDrop(event, listType, order.length));
        container.appendChild(filler);
      }
    }

    handleDragStart(event, listType, id) {
      this.dragContext = { listType, id };
      event.dataTransfer.effectAllowed = "move";
      event.currentTarget.classList.add("dragging");
    }

    handleDragEnd() {
      qsa(".csr.dragging").forEach((node) => node.classList.remove("dragging"));
      this.clearDropHints();
      this.dragContext = null;
    }

    handleDragOver(event, row = null) {
      event.preventDefault();
      if (!row) {
        this.clearDropHints();
        return;
      }
      this.clearDropHints();
      row.classList.add("drop-target");
    }

    handleDrop(event, listType, targetIndex) {
      event.preventDefault();
      event.stopPropagation();
      if (!this.dragContext || this.dragContext.listType !== listType) {
        return;
      }
      playSound("SFX_SELECT");

      const order = this.state.pcOrder[listType];
      const sourceIndex = order.indexOf(this.dragContext.id);
      if (sourceIndex === -1) return;

      const nextOrder = order.slice();
      nextOrder.splice(sourceIndex, 1);
      const insertionIndex = Math.max(0, Math.min(Number(targetIndex ?? nextOrder.length), nextOrder.length));
      nextOrder.splice(insertionIndex, 0, this.dragContext.id);

      this.state.pcOrder[listType] = nextOrder;
      this.state.pcErrors[listType] = "";
      this.render();
      this.scheduleShotWeightsPreview();
    }

    clearDropHints() {
      qsa(".csr.drop-target").forEach((node) => {
        node.classList.remove("drop-target");
      });
    }

    getPcItemSection(item) {
      if (!item) return "";
      if (this.state.motion.some((play) => play.id === item.id)) return "Motion";
      if (this.state.setPlays.some((play) => play.id === item.id)) return "Set";
      if (this.state.manDefense.some((play) => play.id === item.id)) return "Man";
      if (this.state.zoneDefense.some((play) => play.id === item.id)) return "Zone";
      return "";
    }

    getPcItemDetail(item, listType) {
      if (!item || listType !== "offense") return "";
      if (Object.prototype.hasOwnProperty.call(item, "motion_focus")) {
        return displayMotionFocusLabel(item.motion_focus);
      }
      if (Object.prototype.hasOwnProperty.call(item, "target_shooter")) {
        return item.target_shooter || "";
      }
      return "";
    }

    findItemById(listKey, id) {
      if (listKey === "offense") {
        return this.state.motion.find((item) => item.id === id)
          || this.state.setPlays.find((item) => item.id === id);
      }
      if (listKey === "defense") {
        return this.state.manDefense.find((item) => item.id === id)
          || this.state.zoneDefense.find((item) => item.id === id);
      }
      return (this.state[listKey] || []).find((item) => item.id === id) || null;
    }

    getSectionTotals() {
      return {
        motion: activeItems(this.state.motion).reduce((sum, item) => sum + item.percentage, 0),
        setPlays: activeItems(this.state.setPlays).reduce((sum, item) => sum + item.percentage, 0),
        fastBreaks: activeItems(this.state.fastBreaks).reduce((sum, item) => sum + item.percentage, 0),
        hcTraps: activeItems(this.state.hcTraps).reduce((sum, item) => sum + item.percentage, 0),
        manDefense: activeItems(this.state.manDefense).reduce((sum, item) => sum + item.percentage, 0),
        zoneDefense: activeItems(this.state.zoneDefense).reduce((sum, item) => sum + item.percentage, 0),
      };
    }

    renderSectionTotal(element, total, enforced) {
      if (!element) return;
      if (enforced || total === 100) {
        element.innerHTML = `<em>Total</em>100%`;
        return;
      }
      const left = 100 - total;
      const copy = left > 0 ? `${left} left` : `${-left} over`;
      element.innerHTML = `<em>Total</em><span class="tot-warn">${total}% · ${copy}</span>`;
    }

    updateTotals() {
      this.paintSetPlayGroupTotals();
      const totals = this.getSectionTotals();
      this.renderSectionTotal(this.elements.motionTotal, totals.motion, true);
      this.renderSectionTotal(this.elements.setPlaysTotal, totals.setPlays, true);
      this.renderSectionTotal(this.elements.manDefenseTotal, totals.manDefense, true);
      this.renderSectionTotal(this.elements.zoneDefenseTotal, totals.zoneDefense, true);
      this.renderSectionTotal(this.elements.fastBreakTotal, totals.fastBreaks, false);
      this.renderSectionTotal(this.elements.hcTrapTotal, totals.hcTraps, false);

      if (this.elements.fastBreaksNormalize) {
        this.elements.fastBreaksNormalize.hidden = totals.fastBreaks === 100;
      }
      if (this.elements.hcTrapsNormalize) {
        this.elements.hcTrapsNormalize.hidden = totals.hcTraps === 100;
      }

      const okCount = (totals.fastBreaks === 100 ? 1 : 0) + (totals.hcTraps === 100 ? 1 : 0);
      const ready = this.elements.sectionsReadyIndicator;
      if (ready) {
        const copy = ready.querySelector(".ready-copy") || ready;
        const check = ready.querySelector(".ck");
        ready.classList.toggle("ok", okCount === 2);
        ready.classList.toggle("warn", okCount !== 2);
        if (check) check.classList.toggle("on", okCount === 2);
        copy.innerHTML = `<b>${okCount} of 2</b> flexible sections balanced`;
      }
      if (this.elements.saveBtn) {
        this.elements.saveBtn.disabled = okCount !== 2;
      }
      this.syncSaveDirtyState();
    }

    // Colour law: Save Playbooks is orange only while there is something to save
    // (hasEdits: a real edit since the last load or save). Neutral otherwise.
    syncSaveDirtyState() {
      if (this.elements.saveBtn) this.elements.saveBtn.classList.toggle("is-dirty", this.hasEdits());
    }

    buildPreviewPayload() {
      return {
        mode: this.context.mode,
        team_id: this.context.teamId,
        franchise_id: this.context.franchiseId || null,
        game_id: this.context.gameId || null,
        playbook_settings: {
          motion: toPercentMap(this.state.motion),
          set_plays: toPercentMap(this.state.setPlays),
          fast_breaks: toPercentMap(this.state.fastBreaks),
          hc_traps: toPercentMap(this.state.hcTraps),
          man_defense: toPercentMap(this.state.manDefense),
          zone_defense: toPercentMap(this.state.zoneDefense),
          pc_order: {
            offense: this.state.pcOrder.offense.slice(),
            defense: this.state.pcOrder.defense.slice(),
          },
          locks: this.buildLocksPayload(),
          position_filters: this.state.positionFilters,
          even_distribution_all: this.state.evenDistributionAll,
          _meta: this.state.playbookMeta,
        },
        play_updates: this.buildPlayUpdates(),
      };
    }

    paintShotWeights(shotWeights) {
      const container = this.elements.shotWeightsLive;
      if (!container) return;
      const label = `<div class="psw-strip-label">Shot Distribution</div>`;
      const host = document.createElement("div");
      host.className = "psw-root";
      renderShotWeightsLocal(host, shotWeights, true);
      container.innerHTML = label + host.innerHTML;
    }

    scheduleShotWeightsPreview(immediate = false) {
      if (this.previewTimer) {
        window.clearTimeout(this.previewTimer);
        this.previewTimer = null;
      }
      if (immediate) {
        this.fetchShotWeightsPreview();
        return;
      }
      this.previewTimer = window.setTimeout(() => {
        this.previewTimer = null;
        this.fetchShotWeightsPreview();
      }, PREVIEW_DEBOUNCE_MS);
    }

    async fetchShotWeightsPreview() {
      if (this.context.isGameplayContext) return;
      if (this.previewAbort) {
        try { this.previewAbort.abort(); } catch (error) {}
      }
      const controller = typeof AbortController !== "undefined" ? new AbortController() : null;
      this.previewAbort = controller;

      try {
        const response = await fetch(API_CONFIG.buildUrl("/api/playbooks/preview-shot-weights"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(this.buildPreviewPayload()),
          signal: controller ? controller.signal : undefined,
        });
        if (!response.ok) {
          throw new Error(`Preview failed (${response.status})`);
        }
        const data = await response.json();
        this.paintShotWeights(data.position_shot_weights || null);
      } catch (error) {
        if (error && error.name === "AbortError") return;
        console.warn("Shot-weights preview failed:", error);
      }
    }

    async handleSave() {
      if (this.elements.saveBtn?.disabled) {
        return;
      }
      const payload = this.buildPreviewPayload();

      if (window.StateTelemetry) {
        window.StateTelemetry.logBackendWrite("playbook_settings", payload, "/api/playbooks");
      }

      this.elements.saveBtn.disabled = true;

      try {
        const response = await fetch(API_CONFIG.buildUrl("/api/playbooks"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        if (!response.ok) {
          throw new Error(`Save failed (${response.status})`);
        }

        const responseData = await response.json();
        if (responseData.position_shot_weights) {
          this.paintShotWeights(responseData.position_shot_weights);
        }

        this.state.playbookMeta.user_saved = true;
        this.clearDraftState();
        if (this.context.mode === "franchise" && this.context.franchiseId && this.context.teamId && !this.context.gameId) {
          try {
            window.sessionStorage.setItem(
              `playbooks_saved_refresh:${this.context.franchiseId}:${this.context.teamId}`,
              "1"
            );
          } catch (storageError) {
            console.warn("Unable to store playbook save refresh flag:", storageError);
          }
        }

        this.state.setPlays.sort(compareSetPlaysByFocusCmd);
        this.renderEnforcedGrid("setPlays", this.elements.setPlaysGrid, "offense", { kind: "set" });
        this.markSaved();

        if (this.isHosted() && window.GOBToast) {
          window.GOBToast.show("Playbooks saved");
          this.updateTotals();
        } else {
          this.showToast("Playbooks Saved", "");
          window.setTimeout(() => this.handleBack(), SAVE_NAV_DELAY_MS);
        }
      } catch (error) {
        console.error("Failed to save playbooks:", error);
        if (this.isHosted() && window.GOBToast) {
          window.GOBToast.show("Playbooks not saved. Try again.");
        } else {
          this.showToast("Failed to save playbooks", "");
        }
        this.updateTotals();
      }
    }

    buildPlayUpdates() {
      const updates = {};
      this.state.motion.forEach((play) => {
        updates[play.id] = { motion_focus: play.motion_focus };
      });
      this.state.setPlays.forEach((play) => {
        updates[play.id] = { target_shooter: play.target_shooter };
      });
      return updates;
    }

    handleBack() {
      if (typeof resolveFranchiseLockerRoomUrl === "function") {
        const resolvedUrl = resolveFranchiseLockerRoomUrl({
          params: this.params,
          franchiseId: this.context.franchiseId,
          teamId: this.context.teamId,
        });
        if (resolvedUrl) {
          window.location.href = resolvedUrl;
          return;
        }
      }
      window.location.href = buildPlaybookReportUrl(this.context);
    }

    dismissToast() {
      const toast = this.elements.toast;
      if (!toast) return;
      if (this.toastTimer) {
        window.clearTimeout(this.toastTimer);
        this.toastTimer = null;
      }
      if (this.toastHideTimer) {
        window.clearTimeout(this.toastHideTimer);
        this.toastHideTimer = null;
      }
      toast.classList.remove("visible");
      this.toastHideTimer = window.setTimeout(() => {
        toast.hidden = true;
      }, 220);
    }

    showToast(title, subtitle = "", options = {}) {
      const toast = this.elements.toast;
      if (!toast) return;
      const accent = options.accentColor || "var(--text-60)";
      const subline = subtitle ? `<div class="toast-subline">${subtitle}</div>` : "";
      toast.innerHTML = `
        <div class="toast-icon" style="--toast-accent: ${accent};">
          <svg viewBox="0 0 20 20" aria-hidden="true" focusable="false">
            <path d="M5.1 10.4 8.3 13.6 14.9 7" fill="none" stroke="#FFFFFF" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"></path>
          </svg>
        </div>
        <div class="toast-copy">
          <div class="toast-title">${title}</div>
          ${subline}
        </div>
        <button class="toast-dismiss" type="button" aria-label="Dismiss notification">×</button>
      `;
      toast.style.setProperty("--toast-accent", accent);
      toast.hidden = false;
      toast.querySelector(".toast-dismiss")?.addEventListener("click", () => this.dismissToast(), { once: true });
      if (this.toastTimer) window.clearTimeout(this.toastTimer);
      if (this.toastHideTimer) {
        window.clearTimeout(this.toastHideTimer);
        this.toastHideTimer = null;
      }
      requestAnimationFrame(() => toast.classList.add("visible"));
      this.toastTimer = window.setTimeout(() => this.dismissToast(), 3000);
    }
  }


function teardown() {
  if (page) {
    if (page.toastTimer) { window.clearTimeout(page.toastTimer); page.toastTimer = null; }
    if (page.toastHideTimer) { window.clearTimeout(page.toastHideTimer); page.toastHideTimer = null; }
    if (page.previewTimer) { window.clearTimeout(page.previewTimer); page.previewTimer = null; }
    if (page.previewAbort) { try { page.previewAbort.abort(); } catch (err) { /* ignore */ } }
    if (page._onResize) window.removeEventListener('resize', page._onResize);
    if (page._stripObserver) { try { page._stripObserver.disconnect(); } catch (err) {} page._stripObserver = null; }
  }
  if (window.GOBNav && typeof window.GOBNav.warnOnLeave === 'function') {
    try { window.GOBNav.warnOnLeave(null); } catch (err) { /* leave hook optional */ }
  }
}

function revalidate(options) {
  if (!page) return init(root, options);
  page.params = liveParams();
  if (options) {
    if (options.mode) page.context.mode = options.mode;
    if (options.teamId) page.context.teamId = options.teamId;
    if (options.franchiseId) page.context.franchiseId = options.franchiseId;
    if (options.game_id) page.context.gameId = options.game_id;
    if (options.from) page.context.from = options.from;
  }
  return page.loadData().then(function () {
    page.markSaved();
    page.render();
    page.scheduleShotWeightsPreview(true);
    return { revalidate: revalidate, unmount: teardown };
  });
}

async function init(host, options) {
  root = host || document.body;
  const hadShell = !!(root.querySelector('.pbc') || root.querySelector('.playbooks-layout'));
  if (!hadShell) {
    root.insertAdjacentHTML('beforeend', shellHtml());
  }
  if (hadShell && page) return revalidate(options);
  page = new PlaybooksPage(root, options);
  window.__playbooksPage = page;
  try {
    await page.init();
    if (window.GOBNav && typeof window.GOBNav.warnOnLeave === 'function') {
      window.GOBNav.warnOnLeave(
        () => page.hasEdits(),
        page.isHosted() ? { view: 'playbooks-view', confirm: (proceed) => page.confirmLeave(proceed) } : null
      );
    }
  } catch (error) {
    console.error('Failed to initialize playbooks page:', error);
    if (inAppShell() && window.GOBToast) {
      window.GOBToast.show('Failed to load playbooks');
    } else {
      const toast = byId('toast');
      if (toast) {
        toast.textContent = 'Failed to load playbooks';
        toast.hidden = false;
      }
    }
    window.__playbooksPage = null;
    page = null;
    throw error;
  }
  return { revalidate: revalidate, unmount: teardown };
}

function shellHtml() {
  return `<div class="resource-page-container fcc-brand-page-shell playbooks-resource-shell">
    <div class="playbooks-page-header-wrap">
      <a id="back-btn" class="back-to-locker-room brand-back-link playbooks-back-link" href="#">Back to Locker Room</a>
    </div>

    <div class="playbooks-page">
      <main class="playbooks-main">
        <section class="fcc-data-card playbooks-page-card">
          <div class="fcc-data-card-body playbooks-page-card-body">
            <header class="playbooks-page-card-header">
              <div class="playbooks-page-title">
                <h1>Playbook Settings</h1>
                <p>Configure usage, focus, and Playcall Center order.</p>
              </div>
              <div id="playbooks-tools-row" class="playbooks-tools-row">
                <div id="sections-ready-indicator" class="playbooks-sections-ready warn" aria-live="polite">
                  <span class="ck" aria-hidden="true"></span>
                  <span class="ready-copy bal"><b>0 of 2</b> flexible sections balanced</span>
                </div>
                <button id="save-btn" class="btn-o playbooks-save-btn playbooks-save-btn-header" type="button" disabled>Save Playbooks</button>
              </div>
            </header>

            <div class="pbc playbooks-layout">
              <div class="playbooks-left-column" id="playbooks-edit-column">
                <section class="settings-card gameplay-lockout-card" id="gameplay-lockout" hidden>
                  <div class="section-block">
                    <div class="section-heading">
                      <h2>Playbooks Unavailable In Game</h2>
                    </div>
                    <p class="empty-state-copy">
                      Playbooks can only be edited from the Franchise Command Center right now. In-game access will return later as a halftime-only adjustment flow.
                    </p>
                  </div>
                </section>

                <div id="shot-weights-live" class="psw playbooks-shot-weights-strip" aria-live="polite">
                  <div class="psw-strip-label">Shot Distribution</div>
                  <p class="psw-unavailable">Loading shot weights…</p>
                </div>

                <div class="playbooks-side-row">
                  <div class="seg playbooks-tabs" id="playbooks-side-seg" role="tablist" aria-label="Playbook side">
                    <button class="playbooks-tab on" type="button" role="tab" data-tab="offense" aria-selected="true" aria-controls="pane-offense">Offense</button>
                    <button class="playbooks-tab" type="button" role="tab" data-tab="defense" aria-selected="false" aria-controls="pane-defense">Defense</button>
                    <button class="playbooks-tab" type="button" role="tab" data-tab="fastBreaks" aria-selected="false" aria-controls="pane-fast-breaks">Fast Breaks</button>
                    <button class="playbooks-tab" type="button" role="tab" data-tab="pressTraps" aria-selected="false" aria-controls="pane-press-traps">Press/Traps</button>
                  </div>
                </div>

                <div class="playbooks-tabpane on" data-pane="offense" id="pane-offense" role="tabpanel">
                  <section class="pbs pb-sec" data-section="motion">
                    <div class="sh pb-sec-head">
                      <div class="pb-sec-title">
                        <h2>Motion</h2>
                        <span class="m cnt" id="motion-count"></span>
                      </div>
                      <div class="section-total tot" id="motion-total"></div>
                      <span class="cmd-h">CMD</span>
                      <span class="slot-h" aria-hidden="true"></span>
                    </div>
                    <div class="et-grid" id="motion-grid"></div>
                  </section>

                  <section class="pbs pb-sec" data-section="setPlays">
                    <div class="sh pb-sec-head">
                      <div class="pb-sec-title">
                        <h2>Set Plays</h2>
                        <span class="m cnt" id="set-plays-count"></span>
                      </div>
                      <div class="section-total tot" id="set-plays-total"></div>
                      <span class="cmd-h">CMD</span>
                      <span class="slot-h" aria-hidden="true"></span>
                    </div>
                    <div class="et-grid" id="set-plays-grid"></div>
                  </section>
                </div>

                <div class="playbooks-tabpane" data-pane="defense" id="pane-defense" role="tabpanel" hidden>
                  <section class="pbs pb-sec def-sec" data-section="manDefense">
                    <div class="sh pb-sec-head">
                      <div class="pb-sec-title">
                        <h2>Man Defense</h2>
                        <span class="m cnt" id="man-defense-count"></span>
                      </div>
                      <div class="section-total tot" id="man-defense-total"></div>
                      <span class="cmd-h">CMD</span>
                      <span class="slot-h" aria-hidden="true"></span>
                    </div>
                    <div class="et-grid" id="man-defense-grid"></div>
                  </section>

                  <section class="pbs pb-sec def-sec" data-section="zoneDefense">
                    <div class="sh pb-sec-head">
                      <div class="pb-sec-title">
                        <h2>Zone Defense</h2>
                        <span class="m cnt" id="zone-defense-count"></span>
                      </div>
                      <div class="section-total tot" id="zone-defense-total"></div>
                      <span class="cmd-h">CMD</span>
                      <span class="slot-h" aria-hidden="true"></span>
                    </div>
                    <div class="et-grid" id="zone-defense-grid"></div>
                  </section>
                </div>

                <div class="playbooks-tabpane" data-pane="fastBreaks" id="pane-fast-breaks" role="tabpanel" hidden>
                  <section class="pbs pb-sec" data-section="fastBreaks" data-norm="1">
                    <div class="sh pb-sec-head">
                      <div class="pb-sec-title">
                        <h2>Fast Breaks</h2>
                        <span class="m cnt" id="fast-breaks-count"></span>
                        <button class="norm-btn btn-q" id="fast-breaks-normalize" type="button" hidden>Normalize → 100</button>
                      </div>
                      <div class="section-total tot" id="fast-breaks-total"></div>
                      <span class="cmd-h">CMD</span>
                      <span class="slot-h" aria-hidden="true"></span>
                    </div>
                    <div class="chips et-grid" id="fast-breaks-chips"></div>
                  </section>
                </div>

                <div class="playbooks-tabpane" data-pane="pressTraps" id="pane-press-traps" role="tabpanel" hidden>
                  <section class="pbs pb-sec def-sec" data-section="hcTraps" data-norm="1">
                    <div class="sh pb-sec-head">
                      <div class="pb-sec-title">
                        <h2>Half-Court Traps</h2>
                        <span class="m cnt" id="hc-traps-count"></span>
                        <button class="norm-btn btn-q" id="hc-traps-normalize" type="button" hidden>Normalize → 100</button>
                      </div>
                      <div class="section-total tot" id="hc-traps-total"></div>
                      <span class="cmd-h">CMD</span>
                      <span class="slot-h" aria-hidden="true"></span>
                    </div>
                    <div class="chips et-grid" id="hc-traps-chips"></div>
                  </section>
                </div>
              </div>

              <aside class="pcs pc-card">
                <div class="pcs-h">
                  <div class="sh"><h2>Playcall Center</h2></div>
                  <p>Up to 8 offense and 8 defense plays. Drag to reorder.</p>
                </div>
                <div class="pcs-g">
                  <b>Offense</b>
                  <span class="pc-cap" id="pc-cap-offense"></span>
                </div>
                <div id="pc-order-offense" class="csr-l pc-list" data-list-type="offense"></div>
                <div id="pc-error-offense" class="pc-inline-error" aria-live="polite"></div>
                <div class="pcs-g">
                  <b>Defense</b>
                  <span class="pc-cap" id="pc-cap-defense"></span>
                </div>
                <div id="pc-order-defense" class="csr-l pc-list" data-list-type="defense"></div>
                <div id="pc-error-defense" class="pc-inline-error" aria-live="polite"></div>
              </aside>
            </div>
          </div>
        </section>
      </main>
    </div>
  </div>`;
}

export { init, teardown, revalidate, shellHtml };
window.initPlaybooks = function (host, options) { return init(host || document.body, options); };
