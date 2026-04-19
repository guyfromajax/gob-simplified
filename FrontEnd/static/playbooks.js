(function () {
  const MOTION_FOCUS_OPTIONS = [
    { value: "balanced", label: "Balanced" },
    { value: "inside", label: "Inside" },
    { value: "attack", label: "Attack" },
    { value: "outside", label: "Outside" },
  ];

  const TARGET_SHOOTER_OPTIONS = ["PG", "SG", "SF", "PF", "C"];
  const EVEN_DISTRIBUTION_WARNING_KEY = "playbooks.skipEvenDistributionWarning";
  const MAX_PC_ITEMS_PER_SIDE = 8;
  const SET_PLAY_FOCUS_ORDER = ["attack", "inside", "outside"];
  const TARGET_SHOOTER_ORDER = ["PG", "SG", "SF", "PF", "C"];

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

  function focusCode(value) {
    if (value === "attack") return "A";
    if (value === "inside") return "I";
    if (value === "outside") return "O";
    return "";
  }

  function focusLabel(value) {
    if (value === "attack") return "Attack";
    if (value === "inside") return "Inside";
    if (value === "outside") return "Outside";
    return "";
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

  function distributeEvenly(items, { activeOnly = false } = {}) {
    const eligible = activeOnly ? items.filter((item) => item.isActive !== false) : items.slice();
    if (eligible.length === 0) {
      return;
    }

    const base = Math.floor(100 / eligible.length);
    let remainder = 100 - (base * eligible.length);

    items.forEach((item) => {
      item.percentage = activeOnly && item.isActive === false ? 0 : 0;
    });

    eligible.forEach((item) => {
      item.percentage = base + (remainder > 0 ? 1 : 0);
      if (remainder > 0) {
        remainder -= 1;
      }
    });
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

    const passthroughKeys = ["quarter", "period"];
    passthroughKeys.forEach((key) => {
      if (context.params.get(key)) {
        params.set(key, context.params.get(key));
      }
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

    const passthroughKeys = ["quarter", "period", "home", "away", "my_team", "return_url"];
    passthroughKeys.forEach((key) => {
      if (context.params.get(key)) {
        params.set(key, context.params.get(key));
      }
    });

    return `/playbook-report.html?${params.toString()}`;
  }

  class ConfirmModal {
    constructor() {
      this.root = document.getElementById("confirm-modal");
      this.titleEl = document.getElementById("confirm-modal-title");
      this.messageEl = document.getElementById("confirm-modal-message");
      this.checkboxRow = document.getElementById("confirm-modal-checkbox-row");
      this.checkbox = document.getElementById("confirm-modal-checkbox");
      this.checkboxLabel = document.getElementById("confirm-modal-checkbox-label");
      this.cancelBtn = document.getElementById("confirm-cancel-btn");
      this.acceptBtn = document.getElementById("confirm-accept-btn");
    }

    open({
      title,
      message,
      acceptLabel = "Confirm",
      showCheckbox = false,
      checkboxLabel = "Don't show this pop up again.",
    }) {
      this.titleEl.textContent = title;
      this.messageEl.textContent = message;
      this.acceptBtn.textContent = acceptLabel;
      this.checkbox.checked = false;
      this.checkboxRow.style.display = showCheckbox ? "flex" : "none";
      this.checkboxLabel.textContent = checkboxLabel;
      this.root.classList.remove("hidden");
      this.root.setAttribute("aria-hidden", "false");

      return new Promise((resolve) => {
        const close = (result) => {
          this.root.classList.add("hidden");
          this.root.setAttribute("aria-hidden", "true");
          this.cancelBtn.removeEventListener("click", onCancel);
          this.acceptBtn.removeEventListener("click", onAccept);
          resolve(result);
        };

        const onCancel = () => close({ confirmed: false, checked: this.checkbox.checked });
        const onAccept = () => close({ confirmed: true, checked: this.checkbox.checked });

        this.cancelBtn.addEventListener("click", onCancel, { once: true });
        this.acceptBtn.addEventListener("click", onAccept, { once: true });
      });
    }
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
        manDefense: [],
        zoneDefense: [],
        pcOrder: { offense: [], defense: [] },
        pcErrors: { offense: "", defense: "" },
        playbookMeta: { user_saved: false, schema_version: 2 },
        positionFilters: {},
        evenDistributionAll: false,
        sorts: {},
      };

      this.toastTimer = null;
      this.toastHideTimer = null;
      this.dragContext = null;
      this.modal = new ConfirmModal();
      this.draftStorageKey = this.buildDraftStorageKey();
      this.draftRestoreFlagKey = this.buildDraftRestoreFlagKey();

      this.elements = {
        saveBtn: document.getElementById("save-btn"),
        backBtn: document.getElementById("back-btn"),
        evenAllBtn: document.getElementById("even-all-btn"),
        sectionsReadyIndicator: document.getElementById("sections-ready-indicator"),
        motionEvenBtn: document.getElementById("motion-even-btn"),
        setPlaysEvenBtn: document.getElementById("set-plays-even-btn"),
        manDefenseEvenBtn: document.getElementById("man-defense-even-btn"),
        zoneDefenseEvenBtn: document.getElementById("zone-defense-even-btn"),
        fastBreaksEvenBtn: document.getElementById("fast-breaks-even-btn"),
        toast: document.getElementById("toast"),
        motionRows: document.getElementById("motion-rows"),
        setPlaysRows: document.getElementById("set-plays-rows"),
        fastBreakRows: document.getElementById("fast-breaks-rows"),
        manDefenseRows: document.getElementById("man-defense-rows"),
        zoneDefenseRows: document.getElementById("zone-defense-rows"),
        motionTotal: document.getElementById("motion-total"),
        setPlaysTotal: document.getElementById("set-plays-total"),
        fastBreakTotal: document.getElementById("fast-breaks-total"),
        manDefenseTotal: document.getElementById("man-defense-total"),
        zoneDefenseTotal: document.getElementById("zone-defense-total"),
        pcOffense: document.getElementById("pc-order-offense"),
        pcDefense: document.getElementById("pc-order-defense"),
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
    }

    buildDraftStorageKey() {
      const parts = [
        "playbooksDraft",
        this.context.mode || "single",
        this.context.teamId || "",
        this.context.franchiseId || "",
        this.context.tournamentId || "",
        this.context.gameId || "",
      ];
      return parts.join(":");
    }

    buildDraftRestoreFlagKey() {
      const parts = [
        "playbooksDraftRestoreOnce",
        this.context.mode || "single",
        this.context.teamId || "",
        this.context.franchiseId || "",
        this.context.tournamentId || "",
        this.context.gameId || "",
      ];
      return parts.join(":");
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

        if (Array.isArray(draft.motion)) this.state.motion = draft.motion;
        if (Array.isArray(draft.setPlays)) this.state.setPlays = draft.setPlays;
        if (Array.isArray(draft.fastBreaks)) this.state.fastBreaks = draft.fastBreaks;
        if (Array.isArray(draft.manDefense)) this.state.manDefense = draft.manDefense;
        if (Array.isArray(draft.zoneDefense)) this.state.zoneDefense = draft.zoneDefense;
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
        if (draft.sorts && typeof draft.sorts === "object") {
          this.state.sorts = draft.sorts;
        }
        this.syncSelectionFromPcOrder();
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
      document.querySelectorAll(".settings-card").forEach((card) => {
        if (card !== this.elements.gameplayLockout) {
          card.hidden = true;
        }
      });
      if (this.elements.saveBtn) this.elements.saveBtn.hidden = true;
      if (this.elements.evenAllBtn) this.elements.evenAllBtn.hidden = true;
      if (this.elements.sectionsReadyIndicator) this.elements.sectionsReadyIndicator.hidden = true;
    }

    bindGlobalEvents() {
      this.elements.backBtn.addEventListener("click", (event) => {
        event.preventDefault();
        this.handleBack();
      });
      this.elements.saveBtn.addEventListener("click", () => this.handleSave());
      this.elements.evenAllBtn?.addEventListener("click", () => this.handleEvenDistributionAll());
      this.elements.motionEvenBtn?.addEventListener("click", () => this.handleEvenDistributionSection("motion"));
      this.elements.setPlaysEvenBtn?.addEventListener("click", () => this.handleEvenDistributionSection("setPlays"));
      this.elements.manDefenseEvenBtn?.addEventListener("click", () => this.handleEvenDistributionSection("manDefense"));
      this.elements.zoneDefenseEvenBtn?.addEventListener("click", () => this.handleEvenDistributionSection("zoneDefense"));
      this.elements.fastBreaksEvenBtn?.addEventListener("click", () => this.handleEvenDistributionSection("fastBreaks"));
      document.querySelectorAll(".sort-btn").forEach((button) => {
        button.addEventListener("click", () => {
          playSound("click-tiny.wav");
          this.toggleSort(button.dataset.section, button.dataset.sortKey);
        });
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
    }

    buildStateFromApi(data) {
      const percentages = data.simple_playbook_percentages || data.playbook_percentages || {};
      const pcOrder = data.pc_order || { offense: [], defense: [] };
      const offenseSelected = new Set((pcOrder.offense || []).map(String));
      const defenseSelected = new Set((pcOrder.defense || []).map(String));

      this.state.playbookMeta = data.playbook_meta || { user_saved: false, schema_version: 2 };
      this.state.positionFilters = data.position_filters || {};
      this.state.evenDistributionAll = Boolean(data.even_distribution_all);
      this.state.pcOrder = {
        offense: (pcOrder.offense || []).map(String),
        defense: (pcOrder.defense || []).map(String),
      };

      this.state.motion = (data.motion || []).map((play) => ({
        id: String(play.play_id),
        name: play.name,
        percentage: parseInteger(percentages.motion?.[play.play_id], 0),
        motion_focus: normalizeMotionFocus(play.motion_focus),
        playcallCenter: offenseSelected.has(String(play.play_id)),
        effectiveness: parseInteger(play.effectiveness, 0),
        top_scorer: play.top_scorer || "N/A",
      }));

      this.state.setPlays = (data.set_plays || []).map((play) => ({
        id: String(play.play_id),
        name: play.name,
        focus: play.play_focus || "",
        percentage: parseInteger(percentages.set_plays?.[play.play_id], 0),
        target_shooter: play.target_shooter || "PG",
        playcallCenter: offenseSelected.has(String(play.play_id)),
        effectiveness: parseInteger(play.effectiveness, 0),
        top_scorer: play.top_scorer || "N/A",
      }));

      this.state.fastBreaks = (data.fast_breaks || []).map((row) => ({
        id: String(row.id),
        name: row.name,
        percentage: parseInteger(percentages.fast_breaks?.[row.id], 0),
      }));

      this.state.manDefense = (data.man_defense_rows || []).map((row) => ({
        id: String(row.id),
        name: row.name,
        percentage: parseInteger(percentages.man_defense?.[row.id], 0),
        playcallCenter: defenseSelected.has(String(row.id)),
        effectiveness: parseInteger(row.effectiveness, 0),
        top_scorer: row.top_scorer || "N/A",
        isActive: row.is_active !== false,
      }));

      this.state.zoneDefense = (data.zone_defense_rows || []).map((row) => ({
        id: String(row.id),
        name: row.name,
        percentage: parseInteger(percentages.zone_defense?.[row.id], 0),
        playcallCenter: defenseSelected.has(String(row.id)),
        effectiveness: parseInteger(row.effectiveness, 0),
        top_scorer: row.top_scorer || "N/A",
        isActive: true,
      }));

      this.state.pcOrder.offense = this.state.pcOrder.offense.filter((id) =>
        this.state.motion.some((item) => item.id === id) || this.state.setPlays.some((item) => item.id === id)
      );
      this.state.pcOrder.defense = this.state.pcOrder.defense.filter((id) =>
        this.state.manDefense.some((item) => item.id === id) || this.state.zoneDefense.some((item) => item.id === id)
      );

      this.syncSelectionFromPcOrder();
    }

    syncSelectionFromPcOrder() {
      const offenseSet = new Set(this.state.pcOrder.offense);
      const defenseSet = new Set(this.state.pcOrder.defense);
      this.state.motion.forEach((item) => { item.playcallCenter = offenseSet.has(item.id); });
      this.state.setPlays.forEach((item) => { item.playcallCenter = offenseSet.has(item.id); });
      this.state.manDefense.forEach((item) => { item.playcallCenter = defenseSet.has(item.id); });
      this.state.zoneDefense.forEach((item) => { item.playcallCenter = defenseSet.has(item.id); });
    }

    render() {
      this.renderMotionRows();
      this.renderSetPlayRows();
      this.renderFastBreakRows();
      this.renderDefenseRows("man");
      this.renderDefenseRows("zone");
      this.renderPcLists();
      this.updateTotals();
    }

    renderMotionRows() {
      this.elements.motionRows.innerHTML = "";
      this.state.motion.forEach((play) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td class="play-name-cell">
            <button class="play-name-btn" type="button">${play.name}</button>
          </td>
          <td class="percent-cell">${this.renderPercentControl(play.id, play.percentage, "motion")}</td>
          <td class="control-cell">${this.renderSelectControl(play.id, displayMotionFocus(play.motion_focus), MOTION_FOCUS_OPTIONS, "motion-focus-select")}</td>
          <td class="checkbox-cell">${this.renderCheckbox(play.id, play.playcallCenter, "offense")}</td>
          <td class="eff-cell">${this.renderEffScore(play.effectiveness)}</td>
          <td class="top-scorer-cell"><span class="${play.top_scorer === "N/A" ? "stat-muted" : ""}">${play.top_scorer}</span></td>
        `;

        tr.querySelector(".play-name-btn").addEventListener("click", () => {
          this.persistDraftState();
          this.markDraftForNextLoad();
          window.location.href = buildPlayDetailsUrl(this.context, play);
        });
        this.bindPercentEvents(tr, play.id, "motion");
        this.bindFocusEvents(tr, play.id);
        this.bindPcCheckboxEvent(tr, play.id, "offense");
        this.elements.motionRows.appendChild(tr);
      });
    }

    renderSetPlayRows() {
      this.elements.setPlaysRows.innerHTML = "";
      this.state.setPlays.forEach((play) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td class="play-name-cell">
            <button class="play-name-btn" type="button">
              <span class="play-name-inline">
                <span>${play.name}</span>
                <span class="focus-inline">(${focusCode(play.focus)})</span>
              </span>
            </button>
          </td>
          <td class="percent-cell">${this.renderPercentControl(play.id, play.percentage, "setPlays")}</td>
          <td class="control-cell">${this.renderSelectControl(play.id, play.target_shooter, TARGET_SHOOTER_OPTIONS.map((value) => ({ value, label: value })), "target-shooter-select")}</td>
          <td class="checkbox-cell">${this.renderCheckbox(play.id, play.playcallCenter, "offense")}</td>
          <td class="eff-cell">${this.renderEffScore(play.effectiveness)}</td>
          <td class="top-scorer-cell"><span class="${play.top_scorer === "N/A" ? "stat-muted" : ""}">${play.top_scorer}</span></td>
        `;

        tr.querySelector(".play-name-btn").addEventListener("click", () => {
          this.persistDraftState();
          this.markDraftForNextLoad();
          window.location.href = buildPlayDetailsUrl(this.context, play);
        });
        this.bindPercentEvents(tr, play.id, "setPlays");
        this.bindTargetShooterEvents(tr, play.id);
        this.bindPcCheckboxEvent(tr, play.id, "offense");
        this.elements.setPlaysRows.appendChild(tr);
      });
    }

    renderFastBreakRows() {
      this.elements.fastBreakRows.innerHTML = "";
      this.state.fastBreaks.forEach((row) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td class="play-name-cell"><span class="play-name-text">${row.name}</span></td>
          <td class="percent-cell">${this.renderPercentControl(row.id, row.percentage, "fastBreaks")}</td>
        `;
        this.bindPercentEvents(tr, row.id, "fastBreaks");
        this.elements.fastBreakRows.appendChild(tr);
      });
    }

    renderDefenseRows(type) {
      const rows = type === "man" ? this.state.manDefense : this.state.zoneDefense;
      const tbody = type === "man" ? this.elements.manDefenseRows : this.elements.zoneDefenseRows;
      const sectionKey = type === "man" ? "manDefense" : "zoneDefense";
      tbody.innerHTML = "";

      rows.forEach((row) => {
        const tr = document.createElement("tr");
        if (!row.isActive) {
          tr.classList.add("row-dead");
        }
        tr.innerHTML = `
          <td class="play-name-cell">
            <span>${row.name}</span>
            ${row.isActive ? "" : '<span class="dead-pill">Coming Later</span>'}
          </td>
          <td class="percent-cell">${this.renderPercentControl(row.id, row.percentage, sectionKey, row.isActive === false)}</td>
          <td class="checkbox-cell">${this.renderCheckbox(row.id, row.playcallCenter, "defense", row.isActive === false)}</td>
          <td class="eff-cell">${this.renderEffScore(row.effectiveness)}</td>
          <td class="top-scorer-cell"><span class="${row.top_scorer === "N/A" ? "stat-muted" : ""}">${row.top_scorer}</span></td>
        `;
        if (row.isActive) {
          this.bindPercentEvents(tr, row.id, sectionKey);
          this.bindPcCheckboxEvent(tr, row.id, "defense");
        }
        tbody.appendChild(tr);
      });
    }

    renderPcLists() {
      this.renderPcList("offense", this.elements.pcOffense, this.state.pcOrder.offense);
      this.renderPcList("defense", this.elements.pcDefense, this.state.pcOrder.defense);
      if (this.elements.pcErrorOffense) {
        this.elements.pcErrorOffense.textContent = this.state.pcErrors.offense || "";
      }
      if (this.elements.pcErrorDefense) {
        this.elements.pcErrorDefense.textContent = this.state.pcErrors.defense || "";
      }
    }

    renderPcList(listType, container, order) {
      container.innerHTML = "";
      for (let index = 0; index < MAX_PC_ITEMS_PER_SIDE; index += 1) {
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
            <span class="pc-slot-name"><span class="pc-slot-number">${index + 1}.</span> <span class="pc-slot-primary">${item.name}</span>${detail ? ` <span class="pc-slot-detail">— ${detail}</span>` : ""}</span>
            <button class="pc-remove-btn" type="button" aria-label="Remove ${item.name}">×</button>
          `;
          row.addEventListener("dragstart", (event) => this.handleDragStart(event, listType, id));
          row.addEventListener("dragend", () => this.handleDragEnd());
          row.querySelector(".pc-remove-btn").addEventListener("click", () => {
            playSound("click-tiny.wav");
            this.state.pcOrder[listType] = this.state.pcOrder[listType].filter((entry) => entry !== id);
            this.state.pcErrors[listType] = "";
            this.syncSelectionFromPcOrder();
            this.render();
          });
          slot.appendChild(row);
        } else {
          slot.classList.add("is-empty");
          const empty = document.createElement("div");
          empty.className = "pc-slot-empty";
          empty.innerHTML = `<span class="pc-slot-number">${index + 1}.</span> <span class="pc-slot-detail">Empty</span>`;
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
      this.syncSelectionFromPcOrder();
      this.render();
    }

    clearDropHints() {
      document.querySelectorAll(".pc-slot.drop-target").forEach((node) => {
        node.classList.remove("drop-target");
      });
    }

    renderPercentControl(id, value, sectionKey, disabled = false) {
      return `
        <div class="number-input-wrap">
          <input type="number" min="0" max="100" step="1" value="${value}" data-id="${id}" data-section="${sectionKey}" ${disabled ? "disabled" : ""}>
          <div class="spin-btns">
            <button type="button" data-delta="-1" data-id="${id}" data-section="${sectionKey}" ${disabled ? "disabled" : ""}>−</button>
            <button type="button" data-delta="1" data-id="${id}" data-section="${sectionKey}" ${disabled ? "disabled" : ""}>+</button>
          </div>
        </div>
      `;
    }

    renderEffScore(value) {
      const numeric = parseInteger(value, 0);
      const className = numeric >= 67 ? "is-high" : (numeric >= 34 ? "is-mid" : "is-low");
      return `<span class="eff-score ${className}">${numeric}</span>`;
    }

    renderSelectControl(id, currentValue, options, cssClass) {
      return `
        <select class="control-select ${cssClass}" data-id="${id}">
          ${options.map((option) => `<option value="${option.value}" ${String(currentValue) === String(option.value) ? "selected" : ""}>${option.label}</option>`).join("")}
        </select>
      `;
    }

    renderCheckbox(id, checked, listType, disabled = false) {
      const listFull = (this.state.pcOrder[listType] || []).length >= MAX_PC_ITEMS_PER_SIDE;
      const disabledForCapacity = listFull && !checked;
      return `<label class="checkbox-wrap"><input class="control-check" type="checkbox" data-id="${id}" data-list-type="${listType}" ${checked ? "checked" : ""} ${(disabled || disabledForCapacity) ? "disabled" : ""}><span class="control-check-ui" aria-hidden="true"></span></label>`;
    }

    toggleSort(sectionKey, sortKey) {
      const current = this.state.sorts[sectionKey] || { key: null, direction: "desc" };
      const defaultDirection = (sortKey === "focus" || sortKey === "target_shooter") ? "asc" : "desc";
      const nextDirection = current.key === sortKey
        ? (current.direction === "desc" ? "asc" : "desc")
        : defaultDirection;

      const sortState = {
        key: sortKey,
        direction: nextDirection,
      };
      this.state.sorts[sectionKey] = sortState;

      const list = this.state[sectionKey];
      if (Array.isArray(list)) {
        list.sort((a, b) => this.compareForSort(a, b, sortState));
      }
      this.render();
    }

    compareForSort(a, b, sortState) {
      const direction = sortState.direction === "asc" ? 1 : -1;
      const valueFor = (item) => {
        if (sortState.key === "percentage") return item.percentage || 0;
        if (sortState.key === "effectiveness") return item.effectiveness || 0;
        if (sortState.key === "playcallCenter") return item.playcallCenter ? 1 : 0;
        if (sortState.key === "focus") return SET_PLAY_FOCUS_ORDER.indexOf(item.focus || "");
        if (sortState.key === "target_shooter") return TARGET_SHOOTER_ORDER.indexOf(item.target_shooter || "");
        return 0;
      };

      const aValue = valueFor(a);
      const bValue = valueFor(b);

      if (sortState.key === "focus" || sortState.key === "target_shooter") {
        const safeA = aValue === -1 ? Number.MAX_SAFE_INTEGER : aValue;
        const safeB = bValue === -1 ? Number.MAX_SAFE_INTEGER : bValue;
        if (safeA !== safeB) {
          return (safeA - safeB) * direction;
        }
        return a.name.localeCompare(b.name);
      }

      if (aValue !== bValue) {
        return (aValue - bValue) * direction;
      }

      return a.name.localeCompare(b.name);
    }

    bindPercentEvents(row, id, sectionKey) {
      const input = row.querySelector(`input[type="number"][data-id="${id}"]`);
      const buttons = row.querySelectorAll(`button[data-id="${id}"][data-section="${sectionKey}"]`);

      if (input) {
        input.addEventListener("change", () => {
          playSound("click-tiny.wav");
          this.setPercentage(sectionKey, id, parseInteger(input.value, 0));
        });
      }

      buttons.forEach((button) => {
        button.addEventListener("click", () => {
          playSound("click-tiny.wav");
          const delta = parseInteger(button.dataset.delta, 0);
          const current = parseInteger(input.value, 0);
          this.setPercentage(sectionKey, id, current + delta);
        });
      });
    }

    bindFocusEvents(row, id) {
      const select = row.querySelector(".motion-focus-select");
      if (!select) return;
      select.addEventListener("change", () => {
        playSound("click-tiny.wav");
        const play = this.state.motion.find((item) => item.id === id);
        if (!play) return;
        play.motion_focus = normalizeMotionFocus(select.value);
        this.state.evenDistributionAll = false;
        this.renderPcLists();
      });
    }

    bindTargetShooterEvents(row, id) {
      const select = row.querySelector(".target-shooter-select");
      if (!select) return;
      select.addEventListener("change", () => {
        playSound("click-tiny.wav");
        const play = this.state.setPlays.find((item) => item.id === id);
        if (!play) return;
        play.target_shooter = select.value;
        this.state.evenDistributionAll = false;
        this.renderPcLists();
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

    bindPcCheckboxEvent(row, id, listType) {
      const checkbox = row.querySelector(`.control-check[data-id="${id}"]`);
      if (!checkbox) return;
      checkbox.addEventListener("change", () => {
        playSound("click-tiny.wav");
        const list = this.state.pcOrder[listType];
        const isSelected = list.includes(id);

        if (checkbox.checked && !isSelected) {
          if (list.length >= MAX_PC_ITEMS_PER_SIDE) {
            checkbox.checked = false;
            this.state.pcErrors[listType] = "Playcall Center is full. Remove a play to add another.";
            this.renderPcLists();
            return;
          }
          list.push(id);
          this.state.pcErrors[listType] = "";
        } else if (!checkbox.checked && isSelected) {
          this.state.pcOrder[listType] = list.filter((entry) => entry !== id);
          this.state.pcErrors[listType] = "";
        }

        this.syncSelectionFromPcOrder();
        this.render();
      });
    }

    setPercentage(sectionKey, id, rawValue) {
      const value = Math.max(0, Math.min(100, parseInteger(rawValue, 0)));
      const item = this.findItemById(this.sectionKeyToList(sectionKey), id);
      if (!item) return;
      item.percentage = value;
      this.state.evenDistributionAll = false;
      this.render();
    }

    sectionKeyToList(sectionKey) {
      if (sectionKey === "motion") return "motion";
      if (sectionKey === "setPlays") return "setPlays";
      if (sectionKey === "fastBreaks") return "fastBreaks";
      if (sectionKey === "manDefense") return "manDefense";
      if (sectionKey === "zoneDefense") return "zoneDefense";
      return sectionKey;
    }

    findItemById(listKey, id) {
      if (listKey === "offense") {
        return this.state.motion.find((item) => item.id === id) || this.state.setPlays.find((item) => item.id === id);
      }
      if (listKey === "defense") {
        return this.state.manDefense.find((item) => item.id === id) || this.state.zoneDefense.find((item) => item.id === id);
      }
      return (this.state[listKey] || []).find((item) => item.id === id) || null;
    }

    getSectionTotals() {
      return {
        motion: this.state.motion.reduce((sum, item) => sum + item.percentage, 0),
        setPlays: this.state.setPlays.reduce((sum, item) => sum + item.percentage, 0),
        fastBreaks: this.state.fastBreaks.reduce((sum, item) => sum + item.percentage, 0),
        manDefense: this.state.manDefense.filter((item) => item.isActive !== false).reduce((sum, item) => sum + item.percentage, 0),
        zoneDefense: this.state.zoneDefense.reduce((sum, item) => sum + item.percentage, 0),
      };
    }

    updateTotals() {
      const totals = this.getSectionTotals();
      const applyTotalState = (element, total) => {
        element.textContent = `${total} / 100`;
        element.classList.toggle("valid", total === 100);
        element.classList.toggle("invalid", total !== 100);
      };

      applyTotalState(this.elements.motionTotal, totals.motion);
      applyTotalState(this.elements.setPlaysTotal, totals.setPlays);
      applyTotalState(this.elements.fastBreakTotal, totals.fastBreaks);
      applyTotalState(this.elements.manDefenseTotal, totals.manDefense);
      applyTotalState(this.elements.zoneDefenseTotal, totals.zoneDefense);

      const validSections = Object.values(totals).filter((total) => total === 100).length;
      const allValid = validSections === Object.keys(totals).length;
      if (this.elements.sectionsReadyIndicator) {
        this.elements.sectionsReadyIndicator.textContent = `${validSections} / 5 sections ready`;
        this.elements.sectionsReadyIndicator.classList.toggle("valid", allValid);
        this.elements.sectionsReadyIndicator.classList.toggle("invalid", !allValid);
      }
      this.elements.saveBtn.disabled = !allValid;
    }

    handleEvenDistributionSection(sectionKey) {
      playSound("click-tiny.wav");
      if (sectionKey === "motion") {
        distributeEvenly(this.state.motion);
      } else if (sectionKey === "setPlays") {
        distributeEvenly(this.state.setPlays);
      } else if (sectionKey === "fastBreaks") {
        distributeEvenly(this.state.fastBreaks);
      } else if (sectionKey === "manDefense") {
        distributeEvenly(this.state.manDefense, { activeOnly: true });
      } else if (sectionKey === "zoneDefense") {
        distributeEvenly(this.state.zoneDefense);
      }
      this.state.evenDistributionAll = false;
      this.render();
    }

    async handleEvenDistributionAll() {
      const skipWarning = window.localStorage.getItem(EVEN_DISTRIBUTION_WARNING_KEY) === "1";
      if (!skipWarning) {
        const result = await this.modal.open({
          title: "Even Distribution - All",
          message: "this will change all %s -- your previous settings will be lost",
          acceptLabel: "Save Anyway",
          showCheckbox: true,
        });
        if (!result.confirmed) return;
        if (result.checked) {
          window.localStorage.setItem(EVEN_DISTRIBUTION_WARNING_KEY, "1");
        }
      }

      distributeEvenly(this.state.motion);
      distributeEvenly(this.state.setPlays);
      distributeEvenly(this.state.fastBreaks);
      distributeEvenly(this.state.manDefense, { activeOnly: true });
      distributeEvenly(this.state.zoneDefense);
      this.state.evenDistributionAll = true;
      this.render();
    }

    async handleSave() {
      if (this.elements.saveBtn.disabled) {
        return;
      }
      playSound("confirm-2.mp3");

      const payload = {
        mode: this.context.mode,
        team_id: this.context.teamId,
        franchise_id: this.context.franchiseId || null,
        tournament_id: this.context.tournamentId || null,
        game_id: this.context.gameId || null,
        playbook_settings: {
          motion: toPercentMap(this.state.motion),
          set_plays: toPercentMap(this.state.setPlays),
          fast_breaks: toPercentMap(this.state.fastBreaks),
          man_defense: toPercentMap(this.state.manDefense),
          zone_defense: toPercentMap(this.state.zoneDefense),
          pc_order: {
            offense: this.state.pcOrder.offense.slice(),
            defense: this.state.pcOrder.defense.slice(),
          },
          position_filters: this.state.positionFilters,
          even_distribution_all: this.state.evenDistributionAll,
          _meta: this.state.playbookMeta,
        },
        play_updates: this.buildPlayUpdates(),
      };

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

        this.showToast("Playbooks Saved", "Changes applied successfully");
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
      } catch (error) {
        console.error("Failed to save playbooks:", error);
        this.showToast("Failed to save playbooks", "", { accentColor: "#F79420" });
      } finally {
        this.updateTotals();
      }
    }

    buildPlayUpdates() {
      const updates = {};
      this.state.motion.forEach((play) => {
        updates[play.id] = {
          motion_focus: play.motion_focus,
        };
      });
      this.state.setPlays.forEach((play) => {
        updates[play.id] = {
          target_shooter: play.target_shooter,
        };
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
      if (this.toastTimer) {
        window.clearTimeout(this.toastTimer);
      }
      if (this.toastHideTimer) {
        window.clearTimeout(this.toastHideTimer);
        this.toastHideTimer = null;
      }
      requestAnimationFrame(() => {
        toast.classList.add("visible");
      });
      this.toastTimer = window.setTimeout(() => {
        this.dismissToast();
      }, 3000);
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
        requestAnimationFrame(() => {
          toast.classList.add("visible");
        });
        window.setTimeout(() => {
          toast.classList.remove("visible");
          window.setTimeout(() => { toast.hidden = true; }, 220);
        }, 3000);
      }
    }
  });
})();
