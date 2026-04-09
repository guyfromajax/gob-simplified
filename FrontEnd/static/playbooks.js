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

    return `${API_CONFIG.buildUrl("/static/play-details.html")}?${params.toString()}`;
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
        playbookMeta: { user_saved: false, schema_version: 2 },
        positionFilters: {},
        evenDistributionAll: false,
        sorts: {},
      };

      this.toastTimer = null;
      this.dragContext = null;
      this.modal = new ConfirmModal();

      this.elements = {
        saveBtn: document.getElementById("save-btn"),
        backBtn: document.getElementById("back-btn"),
        evenAllBtn: document.getElementById("even-all-btn"),
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
      this.render();
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
    }

    bindGlobalEvents() {
      this.elements.backBtn.addEventListener("click", () => this.handleBack());
      this.elements.saveBtn.addEventListener("click", () => this.handleSave());
      this.elements.evenAllBtn.addEventListener("click", () => this.handleEvenDistributionAll());
      document.querySelectorAll(".sort-btn").forEach((button) => {
        button.addEventListener("click", () => {
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
        isActive: row.is_active !== false,
      }));

      this.state.zoneDefense = (data.zone_defense_rows || []).map((row) => ({
        id: String(row.id),
        name: row.name,
        percentage: parseInteger(percentages.zone_defense?.[row.id], 0),
        playcallCenter: defenseSelected.has(String(row.id)),
        effectiveness: parseInteger(row.effectiveness, 0),
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
          <td>
            <button class="play-name-btn" type="button">${play.name}</button>
          </td>
          <td>${this.renderPercentControl(play.id, play.percentage, "motion")}</td>
          <td>${this.renderSelectControl(play.id, displayMotionFocus(play.motion_focus), MOTION_FOCUS_OPTIONS, "motion-focus-select")}</td>
          <td class="checkbox-cell">${this.renderCheckbox(play.id, play.playcallCenter, "offense")}</td>
          <td><span class="stat-pill">${play.effectiveness}/100</span></td>
          <td><span class="${play.top_scorer === "N/A" ? "stat-muted" : ""}">${play.top_scorer}</span></td>
        `;

        tr.querySelector(".play-name-btn").addEventListener("click", () => {
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
          <td>
            <button class="play-name-btn" type="button">
              <span class="play-name-inline">
                <span>${play.name}</span>
                <span class="focus-inline">(${focusCode(play.focus)})</span>
              </span>
            </button>
          </td>
          <td>${this.renderPercentControl(play.id, play.percentage, "setPlays")}</td>
          <td>${this.renderSelectControl(play.id, play.target_shooter, TARGET_SHOOTER_OPTIONS.map((value) => ({ value, label: value })), "target-shooter-select")}</td>
          <td class="checkbox-cell">${this.renderCheckbox(play.id, play.playcallCenter, "offense")}</td>
          <td><span class="stat-pill">${play.effectiveness}/100</span></td>
          <td><span class="${play.top_scorer === "N/A" ? "stat-muted" : ""}">${play.top_scorer}</span></td>
        `;

        tr.querySelector(".play-name-btn").addEventListener("click", () => {
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
          <td>${row.name}</td>
          <td>${this.renderPercentControl(row.id, row.percentage, "fastBreaks")}</td>
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
          <td>
            <span>${row.name}</span>
            ${row.isActive ? "" : '<span class="dead-pill">Coming Later</span>'}
          </td>
          <td>${this.renderPercentControl(row.id, row.percentage, sectionKey, row.isActive === false)}</td>
          <td class="checkbox-cell">${this.renderCheckbox(row.id, row.playcallCenter, "defense", row.isActive === false)}</td>
          <td><span class="stat-pill">${row.effectiveness}/100</span></td>
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
    }

    renderPcList(listType, container, order) {
      container.innerHTML = "";
      if (!order.length) {
        const empty = document.createElement("div");
        empty.className = "pc-empty";
        empty.textContent = "No plays selected.";
        container.appendChild(empty);
        return;
      }

      order.forEach((id, index) => {
        const item = this.findItemById(listType, id);
        if (!item) return;
        const row = document.createElement("div");
        row.className = "pc-item";
        row.draggable = true;
        row.dataset.id = id;
        row.dataset.listType = listType;
        row.innerHTML = `
          <span class="pc-index">${index + 1}.</span>
          <span>${item.name}</span>
        `;
        row.addEventListener("dragstart", (event) => this.handleDragStart(event, listType, id));
        row.addEventListener("dragend", () => this.handleDragEnd());
        row.addEventListener("dragover", (event) => this.handleDragOver(event, row));
        row.addEventListener("dragleave", () => this.clearDropHints());
        row.addEventListener("drop", (event) => this.handleDrop(event, listType, id));
        container.appendChild(row);
      });

      container.ondragover = (event) => this.handleDragOver(event);
      container.ondrop = (event) => this.handleDrop(event, listType, null);
    }

    handleDragStart(event, listType, id) {
      this.dragContext = { listType, id };
      event.dataTransfer.effectAllowed = "move";
      event.currentTarget.classList.add("dragging");
    }

    handleDragEnd() {
      document.querySelectorAll(".pc-item.dragging").forEach((node) => node.classList.remove("dragging"));
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
      const rect = row.getBoundingClientRect();
      const placeAfter = event.clientY >= rect.top + (rect.height / 2);
      row.classList.add(placeAfter ? "drop-after" : "drop-before");
    }

    handleDrop(event, listType, targetId) {
      event.preventDefault();
      event.stopPropagation();
      if (!this.dragContext || this.dragContext.listType !== listType) {
        return;
      }

      const order = this.state.pcOrder[listType];
      const sourceIndex = order.indexOf(this.dragContext.id);
      if (sourceIndex === -1) return;

      const nextOrder = order.slice();
      nextOrder.splice(sourceIndex, 1);

      if (!targetId) {
        nextOrder.push(this.dragContext.id);
      } else {
        const targetIndex = nextOrder.indexOf(targetId);
        const targetRow = event.currentTarget?.closest?.(".pc-item") || event.currentTarget;
        const rect = targetRow?.getBoundingClientRect?.();
        const placeAfter = rect ? event.clientY >= rect.top + (rect.height / 2) : false;
        const insertionIndex = targetIndex === -1 ? nextOrder.length : targetIndex + (placeAfter ? 1 : 0);
        nextOrder.splice(insertionIndex, 0, this.dragContext.id);
      }

      this.state.pcOrder[listType] = nextOrder;
      this.syncSelectionFromPcOrder();
      this.render();
    }

    clearDropHints() {
      document.querySelectorAll(".pc-item.drop-before, .pc-item.drop-after").forEach((node) => {
        node.classList.remove("drop-before", "drop-after");
      });
    }

    renderPercentControl(id, value, sectionKey, disabled = false) {
      return `
        <div class="number-input-wrap">
          <input type="number" min="0" max="100" step="1" value="${value}" data-id="${id}" data-section="${sectionKey}" ${disabled ? "disabled" : ""}>
          <div class="spin-btns">
            <button type="button" data-delta="1" data-id="${id}" data-section="${sectionKey}" ${disabled ? "disabled" : ""}>▲</button>
            <button type="button" data-delta="-1" data-id="${id}" data-section="${sectionKey}" ${disabled ? "disabled" : ""}>▼</button>
          </div>
        </div>
      `;
    }

    renderSelectControl(id, currentValue, options, cssClass) {
      return `
        <select class="control-select ${cssClass}" data-id="${id}">
          ${options.map((option) => `<option value="${option.value}" ${String(currentValue) === String(option.value) ? "selected" : ""}>${option.label}</option>`).join("")}
        </select>
      `;
    }

    renderCheckbox(id, checked, listType, disabled = false) {
      return `<div class="checkbox-wrap"><input class="control-check" type="checkbox" data-id="${id}" data-list-type="${listType}" ${checked ? "checked" : ""} ${disabled ? "disabled" : ""}></div>`;
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
          this.setPercentage(sectionKey, id, parseInteger(input.value, 0));
        });
      }

      buttons.forEach((button) => {
        button.addEventListener("click", () => {
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
        const play = this.state.motion.find((item) => item.id === id);
        if (!play) return;
        play.motion_focus = normalizeMotionFocus(select.value);
        this.state.evenDistributionAll = false;
      });
    }

    bindTargetShooterEvents(row, id) {
      const select = row.querySelector(".target-shooter-select");
      if (!select) return;
      select.addEventListener("change", () => {
        const play = this.state.setPlays.find((item) => item.id === id);
        if (!play) return;
        play.target_shooter = select.value;
        this.state.evenDistributionAll = false;
      });
    }

    bindPcCheckboxEvent(row, id, listType) {
      const checkbox = row.querySelector(`.control-check[data-id="${id}"]`);
      if (!checkbox) return;
      checkbox.addEventListener("change", () => {
        const list = this.state.pcOrder[listType];
        const isSelected = list.includes(id);

        if (checkbox.checked && !isSelected) {
          if (list.length >= MAX_PC_ITEMS_PER_SIDE) {
            checkbox.checked = false;
            window.alert("8 plays max can be added to the playcall center, please remove one to add another");
            return;
          }
          list.push(id);
        } else if (!checkbox.checked && isSelected) {
          this.state.pcOrder[listType] = list.filter((entry) => entry !== id);
        }

        this.syncSelectionFromPcOrder();
        this.renderPcLists();
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
        element.textContent = `Total: ${total}%`;
        element.classList.toggle("valid", total === 100);
        element.classList.toggle("invalid", total !== 100);
      };

      applyTotalState(this.elements.motionTotal, totals.motion);
      applyTotalState(this.elements.setPlaysTotal, totals.setPlays);
      applyTotalState(this.elements.fastBreakTotal, totals.fastBreaks);
      applyTotalState(this.elements.manDefenseTotal, totals.manDefense);
      applyTotalState(this.elements.zoneDefenseTotal, totals.zoneDefense);

      const allValid = Object.values(totals).every((total) => total === 100);
      this.elements.saveBtn.disabled = !allValid;
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

        this.showToast("Playbooks saved");
        this.state.playbookMeta.user_saved = true;
      } catch (error) {
        console.error("Failed to save playbooks:", error);
        this.showToast("Failed to save playbooks");
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
      const returnUrl = this.params.get("return_url");
      if (returnUrl) {
        window.location.href = returnUrl;
        return;
      }
      window.history.back();
    }

    showToast(message) {
      const toast = this.elements.toast;
      toast.textContent = message;
      toast.classList.add("visible");
      if (this.toastTimer) {
        window.clearTimeout(this.toastTimer);
      }
      this.toastTimer = window.setTimeout(() => {
        toast.classList.remove("visible");
      }, 2200);
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
        toast.textContent = "Failed to load playbooks";
        toast.classList.add("visible");
      }
    }
  });
})();
