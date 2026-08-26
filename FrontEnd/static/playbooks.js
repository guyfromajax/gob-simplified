(function () {
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

  const LOCK_API_KEYS = {
    motion: "motion",
    setPlays: "set_plays",
    fastBreaks: "fast_breaks",
    hcTraps: "hc_traps",
    manDefense: "man_defense",
    zoneDefense: "zone_defense",
  };

  const LOCK_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="11" width="14" height="9" rx="2"></rect><path d="M8 11V8a4 4 0 0 1 8 0v3"></path></svg>';
  const CHK_SVG = '<svg viewBox="0 0 12 12" fill="none" stroke="#0b0d14" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M2.5 6.5L5 9L9.5 3.5"/></svg>';
  const NOSLACK_COPY = "No room — the slack is locked. Unlock a play to make space.";

  function playSound(filename) {
    try {
      const base = (typeof API_CONFIG !== "undefined" && API_CONFIG.buildStaticPath)
        ? API_CONFIG.buildStaticPath("/sounds/")
        : "/sounds/";
      const audio = new Audio(base + encodeURIComponent(filename));
      audio.volume = 0.7;
      audio.play().catch(() => {});
    } catch (error) {}
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
    const params = new URLSearchParams();
    params.set("mode", context.mode);
    params.set("team_id", context.teamId);
    if (context.franchiseId) params.set("franchise_id", context.franchiseId);
    if (context.tournamentId) params.set("tournament_id", context.tournamentId);
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
    const params = new URLSearchParams();
    params.set("mode", context.mode);
    params.set("team_id", context.teamId);
    if (context.franchiseId) params.set("franchise_id", context.franchiseId);
    if (context.tournamentId) params.set("tournament_id", context.tournamentId);
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
    function getPswColor(pct) {
      if (pct > 35) return "#4A90D9";
      if (pct >= 21) return "#34EC27";
      if (pct >= 11) return "#FFD700";
      return "#ff6d6d";
    }
    function renderGroup(label, data) {
      if (!data) return "";
      const values = POSITIONS.map((pos) => ({ pos, pct: data[pos] ?? 0 }));
      const maxPct = Math.max(...values.map((value) => value.pct));
      const pills = values.map(({ pos, pct }) => {
        const color = getPswColor(pct);
        const isDominant = pct === maxPct;
        return `
          <div class="psw-pill" style="border: 1px solid rgba(255,255,255,0.08);">
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
    constructor() {
      this.params = new URLSearchParams(window.location.search);
      this.context = {
        params: this.params,
        mode: this.params.get("mode") || "single",
        teamId: this.params.get("team_id") || "",
        franchiseId: this.params.get("franchise_id") || "",
        tournamentId: this.params.get("tournament_id") || "",
        gameId: this.params.get("game_id") || "",
        from: this.params.get("from") || "",
        isGameplayContext: Boolean(this.params.get("game_id") || ""),
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
        saveBtn: document.getElementById("save-btn"),
        backBtn: document.getElementById("back-btn"),
        sectionsReadyIndicator: document.getElementById("sections-ready-indicator"),
        toast: document.getElementById("toast"),
        editColumn: document.getElementById("playbooks-edit-column"),
        shotWeightsLive: document.getElementById("shot-weights-live"),
        motionGrid: document.getElementById("motion-grid"),
        setPlaysGrid: document.getElementById("set-plays-grid"),
        manDefenseGrid: document.getElementById("man-defense-grid"),
        zoneDefenseGrid: document.getElementById("zone-defense-grid"),
        fastBreaksChips: document.getElementById("fast-breaks-chips"),
        hcTrapsChips: document.getElementById("hc-traps-chips"),
        motionTotal: document.getElementById("motion-total"),
        setPlaysTotal: document.getElementById("set-plays-total"),
        fastBreakTotal: document.getElementById("fast-breaks-total"),
        hcTrapTotal: document.getElementById("hc-traps-total"),
        manDefenseTotal: document.getElementById("man-defense-total"),
        zoneDefenseTotal: document.getElementById("zone-defense-total"),
        fastBreaksNormalize: document.getElementById("fast-breaks-normalize"),
        hcTrapsNormalize: document.getElementById("hc-traps-normalize"),
        pcOffense: document.getElementById("pc-order-offense"),
        pcDefense: document.getElementById("pc-order-defense"),
        pcCapOffense: document.getElementById("pc-cap-offense"),
        pcCapDefense: document.getElementById("pc-cap-defense"),
        pcErrorOffense: document.getElementById("pc-error-offense"),
        pcErrorDefense: document.getElementById("pc-error-defense"),
        gameplayLockout: document.getElementById("gameplay-lockout"),
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
      this.restoreDraftState();
      this.render();
      this.syncStickyOffsets();
      this.scheduleShotWeightsPreview(true);
    }

    syncStickyOffsets() {
      const body = document.querySelector(".playbooks-page-card-body");
      const header = document.querySelector(".playbooks-page-card-header");
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
        this.context.tournamentId || "",
        this.context.gameId || "",
      ].join(":");
    }

    buildDraftRestoreFlagKey() {
      return [
        "playbooksDraftRestoreOnce",
        this.context.mode || "single",
        this.context.teamId || "",
        this.context.franchiseId || "",
        this.context.tournamentId || "",
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
        if (draft.activeTab === "offense" || draft.activeTab === "defense") {
          this.state.activeTab = draft.activeTab;
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
      document.querySelector(".pc-card")?.setAttribute("hidden", "");
      if (this.elements.saveBtn) this.elements.saveBtn.hidden = true;
      if (this.elements.sectionsReadyIndicator) this.elements.sectionsReadyIndicator.hidden = true;
    }

    bindGlobalEvents() {
      this.elements.backBtn?.addEventListener("click", (event) => {
        event.preventDefault();
        this.handleBack();
      });
      this.elements.saveBtn?.addEventListener("click", () => this.handleSave());

      document.querySelectorAll(".playbooks-tab").forEach((tab) => {
        tab.addEventListener("click", () => {
          this.state.activeTab = tab.dataset.tab === "defense" ? "defense" : "offense";
          this.applyTab();
        });
      });

      this.elements.fastBreaksNormalize?.addEventListener("click", () => {
        playSound("click-tiny.wav");
        this.normalizeSection("fastBreaks");
      });
      this.elements.hcTrapsNormalize?.addEventListener("click", () => {
        playSound("click-tiny.wav");
        this.normalizeSection("hcTraps");
      });
      window.addEventListener("resize", () => this.syncStickyOffsets());
    }

    applyTab() {
      const tab = this.state.activeTab === "defense" ? "defense" : "offense";
      document.querySelectorAll(".playbooks-tab").forEach((button) => {
        const on = button.dataset.tab === tab;
        button.classList.toggle("on", on);
        button.setAttribute("aria-selected", on ? "true" : "false");
      });
      document.querySelectorAll(".playbooks-tabpane").forEach((pane) => {
        const on = pane.dataset.pane === tab;
        pane.classList.toggle("on", on);
        pane.hidden = !on;
      });
    }

    async loadData() {
      const params = new URLSearchParams();
      params.set("mode", this.context.mode);
      params.set("team_id", this.context.teamId);
      if (this.context.franchiseId) params.set("franchise_id", this.context.franchiseId);
      if (this.context.tournamentId) params.set("tournament_id", this.context.tournamentId);
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
        isActive: true,
        _apiIndex: index,
      }));
      // Stable focus groups while editing; full %-primary sort runs after Save Playbooks.
      if (typeof compareSetPlaysForDisplay === "function") {
        this.state.setPlays.sort((a, b) => compareSetPlaysForDisplay(a, b, { percentPrimary: false }));
      }

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
        const el = document.getElementById(id);
        if (el) el.textContent = text;
      };
      set("motion-count", `${this.state.motion.length} plays · enforced`);
      set("set-plays-count", `${this.state.setPlays.length} plays · enforced`);
      const manActive = activeItems(this.state.manDefense).length;
      set(
        "man-defense-count",
        `${manActive} of ${this.state.manDefense.length} active · enforced`
      );
      set("zone-defense-count", `${this.state.zoneDefense.length} plays · enforced`);
      set("fast-breaks-count", `${this.state.fastBreaks.length} plays · normalize`);
      set("hc-traps-count", `${this.state.hcTraps.length} plays · normalize`);
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

      arr.forEach((item, idx) => {
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
      });
    }

    buildDeadTile(item) {
      const el = document.createElement("div");
      el.className = "et is-dead";
      el.dataset.id = item.id;
      el.title = "Not editable until this play ships";
      el.innerHTML = `
        <div class="et-top">
          <span class="et-deadpill">${LOCK_SVG} Coming Later</span>
          <span class="et-name">${escapeHtml(item.name)}</span>
          <span></span>
          <span class="et-pct"><span class="et-computed" style="color:var(--faint)">—</span></span>
        </div>
        <div class="et-slider"><div class="et-track"><div class="et-fill" style="width:0"></div><div class="et-thumb" style="left:0"></div></div></div>
        <div class="et-meta">
          <span class="et-top-s" style="color:var(--faint)">Not yet available</span>
          <span class="et-cmd"><span class="et-cmd-l">CMD</span><span class="et-cmd-v" style="color:var(--faint)">—</span></span>
        </div>
      `;
      return el;
    }

    buildPccButton(item, side) {
      const assigned = this.inPCC(item.id, side);
      const badge = this.pccBadge(item.id, side);
      const full = this.state.pcOrder[side].length >= MAX_PC_ITEMS_PER_SIDE && !assigned;
      const sc = side === "offense" ? "side-off" : "side-def";
      const sl = side === "offense" ? "OFF" : "DEF";
      if (assigned) {
        return `<button class="et-pcc ${sc} is-assigned" type="button" data-pcc-toggle="${escapeHtml(item.id)}" data-side="${side}">${sl} · <span class="slot">${badge}</span></button>`;
      }
      if (full) {
        return `<button class="et-pcc ${sc}" type="button" data-pcc-toggle="${escapeHtml(item.id)}" data-side="${side}" disabled>PCC full</button>`;
      }
      return `<button class="et-pcc ${sc}" type="button" data-pcc-toggle="${escapeHtml(item.id)}" data-side="${side}"><span class="plus">+</span> ${sl}</button>`;
    }

    buildSelectControl(item, options) {
      if (options.kind === "motion") {
        const current = displayMotionFocus(item.motion_focus);
        const opts = MOTION_FOCUS_OPTIONS.map((option) =>
          `<option value="${option.value}" ${current === option.value ? "selected" : ""}>${option.label}</option>`
        ).join("");
        return `<div class="et-select-wrap"><select class="motion-focus-select" data-id="${escapeHtml(item.id)}">${opts}</select><span class="caret">▼</span></div>`;
      }
      if (options.kind === "set") {
        const opts = TARGET_SHOOTER_OPTIONS.map((value) =>
          `<option value="${value}" ${item.target_shooter === value ? "selected" : ""}>${value}</option>`
        ).join("");
        return `<div class="et-select-wrap is-pos"><select class="target-shooter-select" data-id="${escapeHtml(item.id)}">${opts}</select><span class="caret">▼</span></div>`;
      }
      return "";
    }

    buildEnforcedTile(item, sectionKey, side, options, flags) {
      const el = document.createElement("div");
      const inPcc = this.inPCC(item.id, side);
      const dim = item.percentage === 0 && !inPcc && !item.locked && !flags.noSlack;
      const noSlackHere = item.percentage === 0 && !inPcc && flags.noSlack;
      const classes = ["et"];
      if (item.locked) classes.push("is-locked");
      if (dim) classes.push("is-dim");
      if (noSlackHere) classes.push("is-noslack");
      if (flags.isComputed) classes.push("is-computed");
      if (item.percentage === 0 && !flags.isComputed) classes.push("is-floor");
      el.className = classes.join(" ");
      el.dataset.id = item.id;
      el.dataset.section = sectionKey;

      const topScorer = item.top_scorer && item.top_scorer !== "N/A"
        ? `<span class="et-top-s"><b>${escapeHtml(item.top_scorer)}</b></span>`
        : '<span class="et-top-s"></span>';
      const selectHtml = this.buildSelectControl(item, options);
      const pctBlock = flags.isComputed
        ? `<span class="et-pct"><span class="et-computed">= ${item.percentage}%</span></span>`
        : `<span class="et-pct"><input class="et-pct-input${item.percentage >= 100 ? " threed" : ""}" data-pct="${escapeHtml(item.id)}" value="${item.percentage}" inputmode="numeric"><span class="et-suf">%</span></span>`;
      const nameHtml = (options.kind === "motion" || options.kind === "set")
        ? `<button class="et-name et-name-btn" type="button">${escapeHtml(item.name)}</button>`
        : `<span class="et-name">${escapeHtml(item.name)}</span>`;

      el.innerHTML = `
        <div class="et-top">
          ${this.buildPccButton(item, side)}
          ${nameHtml}
          <button class="et-lock" type="button" data-lock="${escapeHtml(item.id)}" title="${item.locked ? "Unlock" : "Lock"}">${LOCK_SVG}</button>
          ${pctBlock}
        </div>
        ${flags.isComputed
          ? `<div class="et-computed-note">${flags.computedNote || "Determined — the only unlocked play."}</div>`
          : `<div class="et-slider" data-sl="${escapeHtml(item.id)}"><div class="et-track"><div class="et-floor-wall"></div><div class="et-fill" style="width:${item.percentage}%"></div><div class="et-thumb" style="left:${item.percentage}%"></div></div></div>`}
        ${noSlackHere ? `<div class="et-noslack">${LOCK_SVG} ${NOSLACK_COPY}</div>` : ""}
        <div class="et-meta">
          ${selectHtml}
          ${topScorer}
          <span class="et-cmd"><span class="et-cmd-l">CMD</span><span class="et-cmd-v ${cmdClass(item.effectiveness)}">${parseInteger(item.effectiveness, 0)}</span></span>
        </div>
      `;
      return el;
    }

    bindEnforcedTile(tile, sectionKey, idx, side, options) {
      const arr = this.state[sectionKey];
      const item = arr[idx];
      if (!item || item.isActive === false) return;

      tile.querySelector(".et-name-btn")?.addEventListener("click", () => {
        this.persistDraftState();
        this.markDraftForNextLoad();
        window.location.href = buildPlayDetailsUrl(this.context, item);
      });

      tile.querySelector("[data-lock]")?.addEventListener("click", () => {
        playSound("click-tiny.wav");
        item.locked = !item.locked;
        this.state.evenDistributionAll = false;
        ensureEnforcedBalance(arr);
        this.render();
        this.scheduleShotWeightsPreview();
      });

      tile.querySelector("[data-pcc-toggle]")?.addEventListener("click", (event) => {
        const button = event.currentTarget;
        if (button.disabled) return;
        playSound("click-tiny.wav");
        this.togglePcc(item.id, side);
      });

      const select = tile.querySelector(".motion-focus-select, .target-shooter-select");
      if (select) {
        select.addEventListener("change", () => {
          playSound("click-tiny.wav");
          if (options.kind === "motion") {
            item.motion_focus = normalizeMotionFocus(select.value);
          } else if (options.kind === "set") {
            item.target_shooter = select.value;
          }
          this.state.evenDistributionAll = false;
          this.renderPcLists();
          this.scheduleShotWeightsPreview();
        });
      }

      if (tile.classList.contains("is-computed") || item.locked) {
        return;
      }

      const slider = tile.querySelector(".et-slider");
      if (slider) {
        let dragging = false;
        const move = (clientX) => {
          const track = slider.querySelector(".et-track");
          if (!track) return;
          const rect = track.getBoundingClientRect();
          const ratio = rect.width > 0 ? (clientX - rect.left) / rect.width : 0;
          setEnforced(arr, idx, ratio * 100);
          this.paintEnforcedSection(sectionKey);
          this.updateTotals();
        };
        slider.addEventListener("pointerdown", (event) => {
          if (item.locked) return;
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
          playSound("click-tiny.wav");
          this.state.evenDistributionAll = false;
          this.render();
          this.scheduleShotWeightsPreview();
        };
        slider.addEventListener("pointerup", end);
        slider.addEventListener("pointercancel", end);
      }

      const input = tile.querySelector(".et-pct-input");
      if (input) {
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
          playSound("click-tiny.wav");
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

    paintEnforcedSection(sectionKey) {
      const arr = this.state[sectionKey];
      arr.forEach((item) => {
        if (item.isActive === false) return;
        const tile = document.querySelector(`.et[data-id="${CSS.escape(item.id)}"]`);
        if (!tile) return;
        const fill = tile.querySelector(".et-fill");
        const thumb = tile.querySelector(".et-thumb");
        if (fill) fill.style.width = `${item.percentage}%`;
        if (thumb) thumb.style.left = `${item.percentage}%`;
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
      this.state[sectionKey].forEach((item) => {
        const chip = document.createElement("div");
        chip.className = "chip";
        chip.dataset.id = item.id;
        chip.dataset.section = sectionKey;
        const hasCmd = Number.isFinite(item.effectiveness) && item.effectiveness > 0;
        const top = item.top_scorer
          ? `<span class="chip-top-s">${escapeHtml(item.top_scorer)}</span>`
          : '<span class="chip-top-s"></span>';
        const cmd = hasCmd
          ? `<span class="et-cmd"><span class="et-cmd-l">CMD</span><span class="et-cmd-v ${cmdClass(item.effectiveness)}">${parseInteger(item.effectiveness, 0)}</span></span>`
          : "";
        chip.innerHTML = `
          <div class="chip-top">
            <span class="chip-name">${escapeHtml(item.name)}</span>
            <span class="chip-pct"><input data-cpct="${escapeHtml(item.id)}" value="${item.percentage}" inputmode="numeric"><span class="chip-suf">%</span></span>
          </div>
          <div class="chip-slider" data-csl="${escapeHtml(item.id)}">
            <div class="chip-track">
              <div class="chip-fill" style="width:${item.percentage}%"></div>
              <div class="chip-thumb" style="left:${item.percentage}%"></div>
            </div>
          </div>
          <div class="chip-meta">${top}${cmd}</div>
        `;
        container.appendChild(chip);
        this.bindChip(chip, sectionKey, item);
      });
    }

    bindChip(chip, sectionKey, item) {
      const slider = chip.querySelector(".chip-slider");
      if (slider) {
        let dragging = false;
        const move = (clientX) => {
          const track = slider.querySelector(".chip-track");
          if (!track) return;
          const rect = track.getBoundingClientRect();
          const ratio = rect.width > 0 ? (clientX - rect.left) / rect.width : 0;
          item.percentage = Math.max(0, Math.min(100, Math.round(ratio * 100)));
          this.paintChip(item);
          this.updateTotals();
        };
        slider.addEventListener("pointerdown", (event) => {
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
          playSound("click-tiny.wav");
          this.state.evenDistributionAll = false;
          this.render();
          this.scheduleShotWeightsPreview();
        };
        slider.addEventListener("pointerup", end);
        slider.addEventListener("pointercancel", end);
      }

      const input = chip.querySelector("[data-cpct]");
      if (input) {
        input.addEventListener("input", () => {
          input.value = input.value.replace(/[^0-9]/g, "");
        });
        const commit = () => {
          const next = Math.max(0, Math.min(100, parseInteger(input.value, 0)));
          if (next === item.percentage) {
            input.value = String(item.percentage);
            return;
          }
          playSound("click-tiny.wav");
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
      document.querySelectorAll(`.chip[data-id="${CSS.escape(item.id)}"]`).forEach((chip) => {
        const fill = chip.querySelector(".chip-fill");
        const thumb = chip.querySelector(".chip-thumb");
        if (fill) fill.style.width = `${item.percentage}%`;
        if (thumb) thumb.style.left = `${item.percentage}%`;
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
        capEl.innerHTML = open === 0
          ? "Full — 8 calls set"
          : `<b>${order.length}</b> of 8 set · <b>${open}</b> open`;
      }

      for (let index = 0; index < MAX_PC_ITEMS_PER_SIDE; index += 1) {
        if (open === 0 && !order[index]) break;

        const id = order[index];
        const item = id ? this.findItemById(listType, id) : null;
        const slot = document.createElement("div");
        slot.className = "pc-slot";
        slot.dataset.listType = listType;
        slot.dataset.slotIndex = String(index);
        slot.addEventListener("dragover", (event) => this.handleDragOver(event, slot));
        slot.addEventListener("dragleave", () => this.clearDropHints());
        slot.addEventListener("drop", (event) => this.handleDrop(event, listType, index));

        if (item) {
          const detail = this.getPcItemDetail(item, listType);
          const row = document.createElement("div");
          row.className = "pc-slot-filled";
          row.draggable = true;
          row.dataset.id = id;
          row.dataset.listType = listType;
          row.innerHTML = `
            <span class="pc-drag-handle" aria-hidden="true">⋮⋮</span>
            <span class="pc-slot-name"><span class="pc-slot-number">${index + 1}.</span> <span class="pc-slot-primary">${escapeHtml(item.name)}</span>${detail ? ` <span class="pc-slot-detail">— ${escapeHtml(detail)}</span>` : ""}</span>
            <button class="pc-remove-btn" type="button" aria-label="Remove ${escapeHtml(item.name)}">×</button>
          `;
          row.addEventListener("dragstart", (event) => this.handleDragStart(event, listType, id));
          row.addEventListener("dragend", () => this.handleDragEnd());
          row.querySelector(".pc-remove-btn").addEventListener("click", () => {
            playSound("click-tiny.wav");
            this.state.pcOrder[listType] = this.state.pcOrder[listType].filter((entry) => entry !== id);
            this.state.pcErrors[listType] = "";
            this.render();
            this.scheduleShotWeightsPreview();
          });
          slot.appendChild(row);
        } else {
          slot.classList.add("is-empty");
          const empty = document.createElement("div");
          empty.className = "pc-slot-empty";
          empty.innerHTML = `<span class="pc-slot-number">${index + 1}.</span> <span class="pc-slot-detail open-call">open call</span>`;
          slot.appendChild(empty);
        }

        container.appendChild(slot);
      }
    }

    handleDragStart(event, listType, id) {
      this.dragContext = { listType, id };
      event.dataTransfer.effectAllowed = "move";
      event.currentTarget.classList.add("dragging");
    }

    handleDragEnd() {
      document.querySelectorAll(".pc-slot-filled.dragging").forEach((node) => node.classList.remove("dragging"));
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
      playSound("click-tiny.wav");

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
      document.querySelectorAll(".pc-slot.drop-target").forEach((node) => {
        node.classList.remove("drop-target");
      });
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
      if (enforced) {
        element.innerHTML = `<span class="sec-tot"><span class="chk">${CHK_SVG}</span>100 · balanced</span>`;
        return;
      }
      if (total === 100) {
        element.innerHTML = `<span class="sec-tot"><span class="chk">${CHK_SVG}</span>100 · balanced</span>`;
        return;
      }
      const left = 100 - total;
      const copy = left > 0 ? `${left} left to assign` : `${-left} over`;
      element.innerHTML = `<span class="sec-tot warn"><span class="chk">!</span>${copy}</span>`;
    }

    updateTotals() {
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
        ready.classList.toggle("ok", okCount === 2);
        ready.classList.toggle("warn", okCount !== 2);
        if (okCount === 2) {
          copy.innerHTML = "<b>Ready to save</b> · all sections balanced";
        } else {
          copy.innerHTML = `<b>${okCount} of 2</b> flexible sections balanced`;
        }
      }
      if (this.elements.saveBtn) {
        this.elements.saveBtn.disabled = okCount !== 2;
      }
    }

    buildPreviewPayload() {
      return {
        mode: this.context.mode,
        team_id: this.context.teamId,
        franchise_id: this.context.franchiseId || null,
        tournament_id: this.context.tournamentId || null,
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
      const label = `<div class="psw-strip-label">Expected shot distribution <span class="psw-live-pill">LIVE</span></div>`;
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
      playSound("confirm-2-lowervol.wav");

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

        // Re-order Set Plays for read-only venues (% → focus → CMD → name).
        if (typeof compareSetPlaysForDisplay === "function") {
          this.state.setPlays.sort((a, b) => compareSetPlaysForDisplay(a, b, { percentPrimary: true }));
          this.renderEnforcedGrid("setPlays", this.elements.setPlaysGrid, "offense", { kind: "set" });
        }

        this.showToast("Playbooks Saved", "", { accentColor: "#34EC27" });
        window.setTimeout(() => this.handleBack(), SAVE_NAV_DELAY_MS);
      } catch (error) {
        console.error("Failed to save playbooks:", error);
        this.showToast("Failed to save playbooks", "", { accentColor: "#F79420" });
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
      const accent = options.accentColor || "#34EC27";
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

  window.addEventListener("DOMContentLoaded", async () => {
    try {
      const page = new PlaybooksPage();
      await page.init();
      window.__playbooksPage = page;
    } catch (error) {
      console.error("Failed to initialize playbooks page:", error);
      const toast = document.getElementById("toast");
      if (toast) {
        toast.innerHTML = `
          <div class="toast-icon" style="--toast-accent: #F79420;">
            <svg viewBox="0 0 20 20" aria-hidden="true" focusable="false">
              <path d="M5.1 10.4 8.3 13.6 14.9 7" fill="none" stroke="#FFFFFF" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"></path>
            </svg>
          </div>
          <div class="toast-copy">
            <div class="toast-title">Failed to load playbooks</div>
          </div>
          <button class="toast-dismiss" type="button" aria-label="Dismiss notification">×</button>
        `;
        toast.style.setProperty("--toast-accent", "#F79420");
        toast.hidden = false;
        toast.querySelector(".toast-dismiss")?.addEventListener("click", () => {
          toast.classList.remove("visible");
          window.setTimeout(() => { toast.hidden = true; }, 220);
        }, { once: true });
        requestAnimationFrame(() => toast.classList.add("visible"));
        window.setTimeout(() => {
          toast.classList.remove("visible");
          window.setTimeout(() => { toast.hidden = true; }, 220);
        }, 3000);
      }
    }
  });
})();
