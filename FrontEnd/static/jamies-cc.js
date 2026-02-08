(function () {
  var API_BASE = "/api/admin";
  var currentValues = {}; // Snapshot at page load; used only for "Current Value: XX" (static until next visit)

  var sections = [
    {
      header: "Turn Results",
      keys: [
        { key: "STANDARD_D_FOUL", label: "STANDARD_D_FOUL" },
        { key: "STANDARD_O_FOUL", label: "STANDARD_O_FOUL" },
        { key: "HARD_STEAL", label: "HARD_STEAL" },
        { key: "SOFT_STEAL", label: "SOFT_STEAL" },
        { key: "HARD_FOUL", label: "HARD_FOUL" },
        { key: "SOFT_FOUL", label: "SOFT_FOUL" },
        { key: "STEAL_ATTEMPT", label: "STEAL_ATTEMPT" },
        { key: "DEAD_BALL_TURNOVER", label: "DEAD_BALL_TURNOVER" }
      ]
    },
    {
      header: "Charges",
      keys: [
        { key: "CHARGE_THRESHOLD", label: "CHARGE_THRESHOLD" },
        { key: "BLOCKING_FOUL_THRESHOLD", label: "BLOCKING_FOUL_THRESHOLD" }
      ]
    },
    {
      header: "Blocks",
      keys: [
        { key: "BLOCK_RECONCILIATION_SHOOTING_FOUL_THRESHOLD", label: "BLOCK_RECONCILIATION_SHOOTING_FOUL_THRESHOLD" },
        { key: "BLOCK_RECONCILIATION_BLOCK_THRESHOLD", label: "BLOCK_RECONCILIATION_BLOCK_THRESHOLD" },
        { key: "BLOCK_Y_ROLL_MIN", label: "Y Random Range Min" },
        { key: "BLOCK_Y_ROLL_MAX", label: "Y Random Range Max" }
      ]
    },
    {
      header: "Aggression Foul Multiplier",
      keys: [
        { key: "aggression_foul_1", label: "1" },
        { key: "aggression_foul_2", label: "2" },
        { key: "aggression_foul_3", label: "3" },
        { key: "aggression_foul_4", label: "4" },
        { key: "aggression_foul_5", label: "5" }
      ]
    },
    {
      header: "Shooting Thresholds",
      keys: [
        { key: "HARD_SHOOTING_FOUL_THRESHOLD", label: "Hard Shooting Foul Threshold" },
        { key: "SOFT_SHOOTING_FOUL_THRESHOLD", label: "Soft Shooting Foul Threshold" },
        { key: "SOFT_PROB", label: "SOFT_PROB" },
        { key: "THREE_POINTER_FOUL_MISS_CHANCE", label: "THREE_POINTER_FOUL_MISS_CHANCE" },
        { key: "TWO_POINTER_FOUL_MISS_CHANCE", label: "TWO_POINTER_FOUL_MISS_CHANCE" },
        { key: "THREE_POINT_SHOT_THRESHOLD_INCREASE", label: "Three Pointer Shot Threshold Increase Amount" }
      ]
    },
    {
      header: "Team Attribute Ranges",
      keys: [
        { key: "shot_threshold_min", label: "shot_threshold Min" },
        { key: "shot_threshold_max", label: "shot_threshold Max" },
        { key: "rebound_modifier_min", label: "rebound_modifier Min" },
        { key: "rebound_modifier_max", label: "rebound_modifier Max" }
      ]
    },
    {
      header: "Tempo Time Elapsed Ranges",
      keys: [
        { key: "tempo_slow_mean", label: "Slow – Mean" },
        { key: "tempo_slow_std", label: "Slow – STD" },
        { key: "tempo_slow_min", label: "Slow – Min" },
        { key: "tempo_slow_max", label: "Slow – Max" },
        { key: "tempo_normal_mean", label: "Normal – Mean" },
        { key: "tempo_normal_std", label: "Normal – STD" },
        { key: "tempo_normal_min", label: "Normal – Min" },
        { key: "tempo_normal_max", label: "Normal – Max" },
        { key: "tempo_fast_mean", label: "Fast – Mean" },
        { key: "tempo_fast_std", label: "Fast – STD" },
        { key: "tempo_fast_min", label: "Fast – Min" },
        { key: "tempo_fast_max", label: "Fast – Max" }
      ]
    }
  ];

  function getToken() {
    try {
      return localStorage.getItem("auth_token") || "";
    } catch (e) {
      return "";
    }
  }

  function showMessage(text, isError) {
    var el = document.getElementById("jcc-message");
    if (!el) return;
    el.textContent = text;
    el.className = "jcc-message " + (isError ? "jcc-message-error" : "jcc-message-ok");
  }

  function renderRow(container, item, value) {
    var row = document.createElement("div");
    row.className = "jcc-row";
    var label = document.createElement("label");
    label.className = "jcc-label";
    label.textContent = item.label;
    var input = document.createElement("input");
    input.type = "number";
    input.step = item.key.indexOf("_min") !== -1 || item.key.indexOf("_max") !== -1 || item.key.indexOf("PROB") !== -1 || item.key.indexOf("CHANCE") !== -1 || item.key.indexOf("aggression") !== -1 ? "any" : "1";
    input.dataset.key = item.key;
    input.value = value;
    input.className = "jcc-input";
    var currentSpan = document.createElement("span");
    currentSpan.className = "jcc-current";
    currentSpan.textContent = "Current Value: " + value;
    currentSpan.dataset.key = item.key;
    row.appendChild(label);
    row.appendChild(input);
    row.appendChild(currentSpan);
    container.appendChild(row);
  }

  function render(config) {
    currentValues = Object.assign({}, config);
    var content = document.getElementById("jcc-content");
    content.innerHTML = "";
    sections.forEach(function (sec) {
      var section = document.createElement("section");
      section.className = "jcc-section";
      var h2 = document.createElement("h2");
      h2.className = "jcc-section-header";
      h2.textContent = sec.header;
      section.appendChild(h2);
      var list = document.createElement("div");
      list.className = "jcc-rows";
      sec.keys.forEach(function (item) {
        var val = config[item.key];
        if (val === undefined) val = "";
        renderRow(list, item, val);
      });
      section.appendChild(list);
      content.appendChild(section);
    });
    document.getElementById("jcc-loading").style.display = "none";
    document.getElementById("jcc-content").style.display = "block";
  }

  function loadConfig() {
    var loading = document.getElementById("jcc-loading");
    var denied = document.getElementById("jcc-denied");
    var content = document.getElementById("jcc-content");
    loading.style.display = "block";
    denied.style.display = "none";
    content.style.display = "none";

    var token = getToken();
    var headers = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = "Bearer " + token;

    fetch(API_BASE + "/config", { method: "GET", credentials: "include", headers: headers })
      .then(function (res) {
        if (res.status === 403) {
          loading.style.display = "none";
          denied.style.display = "block";
          return null;
        }
        if (!res.ok) throw new Error("Config load failed: " + res.status);
        return res.json();
      })
      .then(function (data) {
        if (data) render(data);
      })
      .catch(function (err) {
        loading.style.display = "none";
        showMessage(err.message || "Failed to load config", true);
      });
  }

  function collectUpdates() {
    var out = {};
    document.querySelectorAll(".jcc-input[data-key]").forEach(function (input) {
      var key = input.dataset.key;
      var current = currentValues[key];
      var raw = input.value.trim();
      if (raw === "") return;
      var num = Number(raw);
      if (key.indexOf("rebound_modifier") !== -1 || key.indexOf("aggression_foul") !== -1 || key.indexOf("SOFT_PROB") !== -1 || key.indexOf("CHANCE") !== -1) {
        if (!Number.isNaN(num)) out[key] = num;
      } else {
        if (Number.isInteger(num)) out[key] = num;
        else if (!Number.isNaN(num)) out[key] = num;
      }
    });
    return out;
  }

  function saveConfig() {
    var updates = collectUpdates();
    if (Object.keys(updates).length === 0) {
      showMessage("No changes to save.", true);
      return;
    }
    var token = getToken();
    var headers = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = "Bearer " + token;

    fetch(API_BASE + "/config", {
      method: "PATCH",
      credentials: "include",
      headers: headers,
      body: JSON.stringify(updates)
    })
      .then(function (res) {
        if (res.status === 403) {
          showMessage("Admin access required.", true);
          return null;
        }
        if (!res.ok) throw new Error("Save failed: " + res.status);
        return res.json();
      })
      .then(function () {
        showMessage("Saved. Current Value labels will update on your next visit.");
      })
      .catch(function (err) {
        showMessage(err.message || "Save failed", true);
      });
  }

  document.getElementById("jcc-save").addEventListener("click", saveConfig);
  loadConfig();
})();
