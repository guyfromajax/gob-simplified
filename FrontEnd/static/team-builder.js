(function () {
  'use strict';

  const params = new URLSearchParams(window.location.search);
  const HOME_SLOT = (function () {
    const n = parseInt(params.get('home_slot'), 10);
    return n === 1 || n === 2 ? n : null;
  })();

  const BUDGET = {
    TEAM: 6400,
    TOP5: 3950,
    CEILING: 1035,
    FLOOR: 24,
    FLOOR_TOP_N: 12,
    MAX_PLAYERS: 15,
    LEAGUE_TEAM_MEDIAN: 5567,
    LEAGUE_TEAM_BEST: 7027,
    LEAGUE_TOP5_MEDIAN: 3148,
    LEAGUE_TOP5_BEST: 3954,
  };

  const CORE_12 = ['SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'ST', 'AG', 'ND', 'IQ', 'FT'];
  const INTANGIBLES = ['CH', 'EM', 'MO'];

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
    accent_color: ['accent_color', 'accent', 'color_accent'],
    position: ['position', 'pos'],
  };

  CORE_12.forEach(function (a) {
    FIELD_ALIASES[a] = [a.toLowerCase(), a];
  });
  INTANGIBLES.forEach(function (a) {
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
    'accent_color',
  ].concat(CORE_12, INTANGIBLES);

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

  const state = {
    step: 0,
    slot: null,
    identity: {
      name: '',
      abbreviation: '',
      mascot: '',
      city_state: '',
    },
    colors: {
      primary: '#27408E',
      secondary: '#15181f',
      accent: '#F79420',
      jersey_preset: 1,
    },
    roster_mode: 'keep',
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
      limitToFirst15: false,
      budgetWarnings: [],
    },
    budget: null,
    slotRosterAttrs: null,
    slotRosterLoading: false,
  };

  const errorHost = document.getElementById('tb-error');
  const panels = {
    0: document.getElementById('tb-step-0'),
    1: document.getElementById('tb-step-1'),
    2: document.getElementById('tb-step-2'),
    3: document.getElementById('tb-step-3'),
    4: document.getElementById('tb-step-4'),
  };

  function showError(msg) {
    if (!errorHost) return;
    if (!msg) {
      errorHost.hidden = true;
      errorHost.textContent = '';
      return;
    }
    errorHost.hidden = false;
    errorHost.textContent = msg;
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

  function evaluateRosterBudget(playerAttrsList) {
    const totals = (playerAttrsList || []).map(core12Total);
    const sorted = totals.slice().sort(function (a, b) {
      return b - a;
    });
    const teamTotal = totals.reduce(function (s, t) {
      return s + t;
    }, 0);
    const maxPlayer = sorted.length ? sorted[0] : 0;
    const top5 = sorted.slice(0, 5).reduce(function (s, t) {
      return s + t;
    }, 0);
    const overBudget = Math.max(0, teamTotal - BUDGET.TEAM);
    const overTop5 = Math.max(0, top5 - BUDGET.TOP5);
    const ceilingViolations = totals.filter(function (t) {
      return t > BUDGET.CEILING;
    }).length;
    const floorPool = sorted.slice(0, BUDGET.FLOOR_TOP_N);
    const floorViolations = floorPool.filter(function (t) {
      return t < BUDGET.FLOOR;
    }).length;
    const eligible =
      overBudget === 0 && overTop5 === 0 && ceilingViolations === 0 && floorViolations === 0;
    return {
      team_total: teamTotal,
      team_budget: BUDGET.TEAM,
      over_budget_by: overBudget,
      top5_total: top5,
      top5_cap: BUDGET.TOP5,
      over_top5_by: overTop5,
      max_player: maxPlayer,
      player_ceiling: BUDGET.CEILING,
      ceiling_violations: ceilingViolations,
      floor: BUDGET.FLOOR,
      floor_violations: floorViolations,
      eligible_for_online: eligible,
    };
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

  function placeLeagueMarkers() {
    // Markers share each bar's cap scale; values past the cap clamp to 100%.
    setMarker(document.getElementById('tb-team-marker-median'), BUDGET.LEAGUE_TEAM_MEDIAN, BUDGET.TEAM);
    setMarker(document.getElementById('tb-team-marker-best'), BUDGET.LEAGUE_TEAM_BEST, BUDGET.TEAM);
    setMarker(document.getElementById('tb-top5-marker-median'), BUDGET.LEAGUE_TOP5_MEDIAN, BUDGET.TOP5);
    setMarker(document.getElementById('tb-top5-marker-best'), BUDGET.LEAGUE_TOP5_BEST, BUDGET.TOP5);
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
    state.import.limitToFirst15 = false;
    state.import.budgetWarnings = [];

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

    let dataRows = state.import.rawRows.slice();
    if (state.import.tooManyRows > BUDGET.MAX_PLAYERS && !state.import.limitToFirst15) {
      // Validate all rows for error reporting, but commit path requires limit or trim.
    } else if (state.import.limitToFirst15 && dataRows.length > BUDGET.MAX_PLAYERS) {
      dataRows = dataRows.slice(0, BUDGET.MAX_PLAYERS);
    }

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
          state.import.rowWarnings.push(rowFieldWarning(rowObj._rowNum, 'height_in', rowObj.height_in, "We'll generate a height."));
        }
        if (!rowObj.weight_lb) {
          state.import.rowWarnings.push(rowFieldWarning(rowObj._rowNum, 'weight_lb', rowObj.weight_lb, "We'll generate a weight."));
        }
        if (!rowObj.jersey) {
          state.import.rowWarnings.push(rowFieldWarning(rowObj._rowNum, 'jersey', rowObj.jersey, "We'll generate a jersey number."));
        }
        state.import.validPlayers.push(normalizeImportedPlayer(rowObj));
      } else {
        state.import.skippedRows.push(rowObj);
      }
    });

    if (showProgress && progressHost) progressHost.hidden = true;

    renderMessageList('tb-import-errors', state.import.rowErrors);
    renderMessageList('tb-import-warnings', state.import.rowWarnings);

    const attrsList = state.import.validPlayers.map(function (p) {
      return p.attributes || {};
    });
    const budgetEval = evaluateRosterBudget(attrsList);
    if (budgetEval.over_budget_by > 0) {
      state.import.budgetWarnings.push(
        'Over budget by ' +
          budgetEval.over_budget_by +
          ' points. This franchise won\'t be eligible for online competitions. Everything else works normally — you can keep playing, and you can trim attributes now if you want to stay eligible.'
      );
    }
    if (budgetEval.ceiling_violations > 0) {
      state.import.budgetWarnings.push(
        budgetEval.ceiling_violations +
          ' player' +
          (budgetEval.ceiling_violations === 1 ? ' exceeds' : 's exceed') +
          ' the per-player ceiling. This franchise won\'t be eligible for online competitions. Everything else works normally.'
      );
    }
    if (budgetEval.floor_violations > 0) {
      state.import.budgetWarnings.push(
        budgetEval.floor_violations +
          ' player' +
          (budgetEval.floor_violations === 1 ? ' is' : 's are') +
          ' below the minimum. This franchise won\'t be eligible for online competitions. Everything else works normally.'
      );
    }
    if (budgetEval.over_top5_by > 0) {
      state.import.budgetWarnings.push(
        'Your top five is ' +
          budgetEval.over_top5_by +
          ' over the cap. The best starting five in the league totals 3,954. This franchise won\'t be eligible for online competitions; everything else works normally.'
      );
    }
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

    const hasIdentityCols = used.team_name || used.mascot || used.primary_color || used.secondary_color || used.accent_color;
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

    if (tooManyHost && state.import.tooManyRows > BUDGET.MAX_PLAYERS && !state.import.limitToFirst15) {
      tooManyHost.hidden = false;
      tooManyHost.innerHTML =
        'That file has ' +
        state.import.tooManyRows +
        ' players. A roster holds 15. Trim the file, or import the first 15. ' +
        '<button type="button" class="tb-btn tb-btn-secondary" id="tb-import-first-15">Import the first 15</button>';
      const btn = document.getElementById('tb-import-first-15');
      if (btn) {
        btn.onclick = function () {
          state.import.limitToFirst15 = true;
          tooManyHost.hidden = true;
          runValidation(true);
        };
      }
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
    if (firstRowObj.accent_color) {
      state.colors.accent = normalizeColor(firstRowObj.accent_color);
      document.getElementById('tb-accent').value = state.colors.accent;
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

    if (
      rosterOn &&
      state.import.tooManyRows > BUDGET.MAX_PLAYERS &&
      !state.import.limitToFirst15
    ) {
      showError('That file has too many players. Trim the file or import the first 15.');
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
    if (state.roster_mode === 'import' || state.roster_mode === 'generate') {
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
    const identityOn = state.import.parts.identity;
    const rosterOn = state.import.parts.roster;

    if (identityOn) {
      const rowObjects = getRowObjects(state.import.rawRows.slice(0, 1));
      if (rowObjects[0]) applyIdentityFromImport(rowObjects[0]);
    }

    if (rosterOn) {
      state.import.importedPlayers = state.import.validPlayers.slice(0, BUDGET.MAX_PLAYERS);
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

  function currentRosterAttrsForBudget() {
    if (state.roster_mode === 'import' && state.import.importedPlayers && state.import.importedPlayers.length) {
      return state.import.importedPlayers.map(function (p) {
        return p.attributes || {};
      });
    }
    if (state.roster_mode === 'keep' && state.slotRosterAttrs) {
      return state.slotRosterAttrs;
    }
    return null;
  }

  function updateBudgetFromCurrentRoster() {
    const attrsList = currentRosterAttrsForBudget();
    if (!attrsList || !attrsList.length) {
      state.budget = null;
      renderBudgetMeter(null);
      return;
    }
    state.budget = evaluateRosterBudget(attrsList);
    renderBudgetMeter(state.budget);
  }

  function renderBudgetMeter(evalResult) {
    const fill = document.getElementById('tb-budget-fill');
    const top5Fill = document.getElementById('tb-top5-fill');
    const teamBar = document.getElementById('tb-budget-bar-team');
    const top5Bar = document.getElementById('tb-budget-bar-top5');
    const label = document.getElementById('tb-budget-label');
    const top5Label = document.getElementById('tb-top5-label');
    const ceiling = document.getElementById('tb-ceiling-line');
    const floor = document.getElementById('tb-floor-line');
    const badge = document.getElementById('tb-elig-badge');
    const warn = document.getElementById('tb-budget-warn');
    const details = document.getElementById('tb-budget-details');
    const toggle = document.getElementById('tb-budget-details-toggle');

    placeLeagueMarkers();

    if (!evalResult) {
      setBarFill(fill, teamBar, 0, BUDGET.TEAM);
      setBarFill(top5Fill, top5Bar, 0, BUDGET.TOP5);
      if (state.roster_mode === 'generate') {
        if (label) {
          label.textContent = 'Team total: estimated until Apply (band resampling)';
        }
        if (top5Label) {
          top5Label.textContent = 'Top-5: estimated until Apply';
        }
        if (ceiling) {
          ceiling.textContent = 'Per-player ceiling: estimated until Apply';
          ceiling.className = 'tb-ceiling-line';
        }
        if (floor) {
          floor.textContent = 'Per-player floor (top 12): estimated until Apply';
          floor.className = 'tb-floor-line';
        }
        if (badge) {
          badge.textContent = 'Eligibility estimated — confirmed at Apply';
          badge.className = 'tb-elig is-yes';
        }
        if (warn) warn.hidden = true;
        if (details) details.hidden = true;
        if (toggle) toggle.hidden = true;
      } else if (state.roster_mode === 'keep') {
        if (label) {
          label.textContent = state.slotRosterLoading
            ? 'Team total: loading slot roster…'
            : 'Team total: estimated within 6,400 (keep)';
        }
        if (top5Label) {
          top5Label.textContent = state.slotRosterLoading
            ? 'Top-5: loading…'
            : 'Top-5: estimated within 3,950 (keep)';
        }
        if (ceiling) {
          ceiling.textContent = 'Per-player ceiling: —';
          ceiling.className = 'tb-ceiling-line';
        }
        if (floor) {
          floor.textContent = 'Per-player floor (top 12): —';
          floor.className = 'tb-floor-line';
        }
        if (badge) {
          badge.textContent = 'Eligible for online competitions';
          badge.className = 'tb-elig is-yes';
        }
        if (warn) warn.hidden = true;
        if (details) details.hidden = true;
        if (toggle) toggle.hidden = true;
      } else {
        if (label) label.textContent = 'Team total: — / 6,400';
        if (top5Label) top5Label.textContent = 'Top-5: — / 3,950';
        if (ceiling) {
          ceiling.textContent = 'Per-player ceiling: —';
          ceiling.className = 'tb-ceiling-line';
        }
        if (floor) {
          floor.textContent = 'Per-player floor (top 12): —';
          floor.className = 'tb-floor-line';
        }
        if (badge) {
          badge.textContent = 'Eligible for online competitions';
          badge.className = 'tb-elig is-yes';
        }
        if (warn) warn.hidden = true;
      }
      return;
    }

    setBarFill(fill, teamBar, evalResult.team_total, BUDGET.TEAM);
    setBarFill(top5Fill, top5Bar, evalResult.top5_total, BUDGET.TOP5);
    if (label) {
      label.textContent =
        'Team total: ' +
        evalResult.team_total.toLocaleString() +
        ' / ' +
        BUDGET.TEAM.toLocaleString();
    }
    if (top5Label) {
      top5Label.textContent =
        'Top-5: ' +
        evalResult.top5_total.toLocaleString() +
        ' / ' +
        BUDGET.TOP5.toLocaleString();
    }
    if (ceiling) {
      const pass = evalResult.ceiling_violations === 0;
      ceiling.textContent =
        'Per-player ceiling: ' +
        (pass ? 'pass' : 'fail (' + evalResult.ceiling_violations + ' over ' + BUDGET.CEILING + ')');
      ceiling.className = 'tb-ceiling-line ' + (pass ? 'is-pass' : 'is-fail');
    }
    if (floor) {
      const pass = evalResult.floor_violations === 0;
      floor.textContent =
        'Per-player floor (top 12): ' +
        (pass ? 'pass' : 'fail (' + evalResult.floor_violations + ' below ' + BUDGET.FLOOR + ')');
      floor.className = 'tb-floor-line ' + (pass ? 'is-pass' : 'is-fail');
    }
    if (badge) {
      if (evalResult.eligible_for_online) {
        badge.textContent = 'Eligible for online competitions';
        badge.className = 'tb-elig is-yes';
      } else {
        badge.textContent = 'Not eligible for online competitions';
        badge.className = 'tb-elig is-no';
      }
    }
    if (warn) {
      const msgs = [];
      if (evalResult.over_budget_by > 0) {
        msgs.push(
          'Over budget by ' +
            evalResult.over_budget_by +
            ' points. This franchise won\'t be eligible for online competitions. Everything else works normally — you can keep playing, and you can trim attributes now if you want to stay eligible.'
        );
      }
      if (evalResult.over_top5_by > 0) {
        msgs.push(
          'Your top five is ' +
            evalResult.over_top5_by +
            ' over the cap. The best starting five in the league totals 3,954. This franchise won\'t be eligible for online competitions; everything else works normally.'
        );
      }
      if (evalResult.floor_violations > 0) {
        msgs.push(
          evalResult.floor_violations +
            ' player' +
            (evalResult.floor_violations === 1 ? ' is' : 's are') +
            ' below the minimum. This franchise won\'t be eligible for online competitions. Everything else works normally.'
        );
      }
      if (evalResult.ceiling_violations > 0) {
        msgs.push(
          evalResult.ceiling_violations +
            ' player' +
            (evalResult.ceiling_violations === 1 ? ' exceeds' : 's exceed') +
            ' the per-player ceiling. This franchise won\'t be eligible for online competitions. Everything else works normally.'
        );
      }
      if (msgs.length) {
        warn.hidden = false;
        warn.innerHTML = msgs.map(function (m) {
          return '<p>' + escapeHtml(m) + '</p>';
        }).join('');
      } else {
        warn.hidden = true;
        warn.textContent = '';
      }
    }
    if (details && toggle) {
      toggle.hidden = false;
      details.textContent =
        'Team total ' +
        evalResult.team_total +
        ', top-5 ' +
        evalResult.top5_total +
        ' (cap ' +
        BUDGET.TOP5 +
        '), max player ' +
        evalResult.max_player +
        ', ceiling ' +
        BUDGET.CEILING +
        ', floor ' +
        BUDGET.FLOOR +
        ' (top ' +
        BUDGET.FLOOR_TOP_N +
        ').';
    }
  }

  async function fetchSlotRosterBudget() {
    if (!state.slot) return;
    state.slotRosterLoading = true;
    if (state.roster_mode === 'keep') renderBudgetMeter(null);
    try {
      const url = API_CONFIG.buildUrl('/roster/' + encodeURIComponent(state.slot.name));
      const res = await fetch(url, { headers: API_CONFIG.getAuthHeaders() });
      if (!res.ok) throw new Error('roster fetch failed');
      const data = await res.json();
      state.slotRosterAttrs = (data.players || []).map(function (p) {
        const a = p.attributes || {};
        const out = {};
        CORE_12.forEach(function (k) {
          if (a[k] != null) out[k] = a[k];
        });
        return out;
      });
      if (state.roster_mode === 'keep') updateBudgetFromCurrentRoster();
    } catch (_) {
      state.slotRosterAttrs = null;
    } finally {
      state.slotRosterLoading = false;
      if (state.roster_mode === 'keep') renderBudgetMeter(state.budget);
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
          document.getElementById('tb-keep-label').textContent = "Keep " + team.name + "'s roster";
          const dl = document.getElementById('tb-dl-slot');
          if (dl) dl.textContent = "Download " + team.name + "'s current roster";
          fetchSlotRosterBudget();
          setStep(1);
        },
      },
    });
  }

  function readIdentity() {
    state.identity = {
      name: (document.getElementById('tb-name').value || '').trim(),
      abbreviation: (document.getElementById('tb-abbr').value || '').trim().toUpperCase(),
      mascot: (document.getElementById('tb-mascot').value || '').trim(),
      city_state: (document.getElementById('tb-city').value || '').trim(),
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

  function readColors() {
    state.colors.primary = document.getElementById('tb-primary').value;
    state.colors.secondary = document.getElementById('tb-secondary').value;
    state.colors.accent = document.getElementById('tb-accent').value;
    const preset = document.querySelector('input[name="jersey"]:checked');
    state.colors.jersey_preset = preset ? Number(preset.value) : 1;
  }

  function refreshColorPreviews() {
    readIdentity();
    readColors();
    if (!window.TeamGeneratedArt) return;
    const opts = {
      name: state.identity.name || 'Custom Program',
      abbreviation: state.identity.abbreviation,
      primary: state.colors.primary,
      secondary: state.colors.secondary,
      accent: state.colors.accent,
      jerseyPreset: state.colors.jersey_preset,
    };
    const mark = document.getElementById('tb-mark-preview');
    const jersey = document.getElementById('tb-jersey-preview');
    const court = document.getElementById('tb-court-preview');
    if (mark) mark.src = TeamGeneratedArt.markDataUrl(opts);
    if (jersey) jersey.src = TeamGeneratedArt.jerseyPreviewDataUrl(opts);
    if (court) court.src = TeamGeneratedArt.courtPreviewDataUrl(opts);
    updateIdentityPreview();
  }

  function refreshRosterStep() {
    const importPanel = document.getElementById('tb-import-panel');
    if (importPanel) importPanel.hidden = state.roster_mode !== 'import';
    updateBudgetFromCurrentRoster();
    if (state.roster_mode === 'keep' && !state.slotRosterAttrs && state.slot) {
      fetchSlotRosterBudget();
    }
  }

  function budgetReviewLine() {
    if (state.budget) {
      const elig = state.budget.eligible_for_online
        ? 'eligible for online competitions'
        : 'not eligible for online competitions';
      return (
        'Attribute budget: ' +
        state.budget.team_total.toLocaleString() +
        ' / ' +
        BUDGET.TEAM.toLocaleString() +
        ' · top-5 ' +
        state.budget.top5_total.toLocaleString() +
        ' / ' +
        BUDGET.TOP5.toLocaleString() +
        ' — ' +
        elig
      );
    }
    if (state.roster_mode === 'generate') {
      return 'Attribute budget: estimated until Apply (band resampling) — eligibility confirmed at Apply';
    }
    if (state.roster_mode === 'keep') {
      return 'Attribute budget: estimated within 6,400 / top-5 3,950 — eligible for online competitions when under caps';
    }
    return 'Attribute budget: — / 6,400 · top-5 — / 3,950';
  }

  function renderReview() {
    readIdentity();
    readColors();
    const host = document.getElementById('tb-review');
    if (!host || !state.slot) return;
    const conf = confLabel(state.slot);
    let rosterLine;
    if (state.roster_mode === 'keep') {
      rosterLine = "Roster: keeping " + state.slot.name + "'s players";
    } else if (state.roster_mode === 'generate') {
      rosterLine = 'Roster: generate new players at slot talent band';
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
      escapeHtml(budgetReviewLine()) +
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

  async function applyFranchise() {
    const loading = document.getElementById('tb-loading');
    const modal = document.getElementById('tb-confirm-modal');
    modal.hidden = true;
    loading.hidden = false;
    try {
      const payload = {
        replaced_object_id: state.slot.object_id,
        home_slot: HOME_SLOT,
        name: state.identity.name,
        abbreviation: state.identity.abbreviation,
        mascot: state.identity.mascot,
        city_state: state.identity.city_state,
        primary_color: state.colors.primary,
        secondary_color: state.colors.secondary,
        accent_color: state.colors.accent,
        jersey_preset: state.colors.jersey_preset,
        roster_mode: state.roster_mode,
      };
      if (
        state.roster_mode === 'import' &&
        state.import.importedPlayers &&
        state.import.importedPlayers.length
      ) {
        payload.imported_players = state.import.importedPlayers;
      }
      const res = await fetch(API_CONFIG.buildUrl('/franchise/team-builder/apply'), {
        method: 'POST',
        headers: { ...API_CONFIG.getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        let msg = 'Unable to apply Team Builder';
        try {
          const err = await res.json();
          if (err.detail) msg = typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail);
        } catch (_) {}
        throw new Error(msg);
      }
      const data = await res.json();
      if (data.franchise_id) {
        if (typeof hydrateTeamBuilderVisualFromFranchisePayload === 'function') {
          hydrateTeamBuilderVisualFromFranchisePayload(
            {
              team: state.identity.name,
              abbreviation: state.identity.abbreviation,
              primary_color: state.colors.primary,
              secondary_color: state.colors.secondary,
              accent_color: state.colors.accent,
              jersey_preset: state.colors.jersey_preset,
              asset_strategy: 'generated',
              is_custom_team: true,
              team_builder_replaced_name: state.slot.name,
              user_team_object_id: state.slot.object_id,
              online_eligibility: data.online_eligibility,
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
      showError(err.message || 'Unable to apply Team Builder');
    }
  }

  function blankTemplateCsv() {
    return (
      'first_name,last_name,class_year,height_in,weight_lb,jersey,SC,SH,ID,OD,PS,BH,RB,ST,AG,ND,IQ,FT\n' +
      'Jamie,Example,FR,,,,,,,,,,,\n' +
      'Alex,Sample,SO,,,,,,,,,,,\n'
    );
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

  async function downloadSlotRoster() {
    const status = document.getElementById('tb-import-status');
    if (!state.slot) return;
    const slug = state.slot.name.replace(/\s+/g, '-').toLowerCase();
    try {
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
    const back = document.getElementById('tb-back');
    if (back) {
      const q = HOME_SLOT ? ('?home_slot=' + HOME_SLOT) : '';
      back.href = '/franchise-select-team.html' + q;
    }

    try {
      state.allTeams = await TeamPicker.fetchTeams();
    } catch (_) {
      state.allTeams = [];
    }

    mountPicker();

    document.querySelectorAll('[data-nav]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        const next = Number(btn.dataset.nav);
        if (btn.dataset.skipRoster) state.roster_mode = 'generate';
        if (state.step === 1 && next > 1) {
          readIdentity();
          if (!state.identity.name) return showError('School name is required.');
          if (!validateAbbr()) return showError(document.getElementById('tb-abbr-hint').textContent);
        }
        if (!state.slot && next > 0) return showError('Choose a slot first.');
        setStep(next);
      });
    });

    ['tb-name', 'tb-abbr', 'tb-mascot', 'tb-city'].forEach(function (id) {
      const el = document.getElementById(id);
      if (!el) return;
      el.addEventListener('input', updateIdentityPreview);
      if (id === 'tb-abbr') el.addEventListener('blur', validateAbbr);
    });

    ['tb-primary', 'tb-secondary', 'tb-accent'].forEach(function (id) {
      const el = document.getElementById(id);
      if (el) el.addEventListener('input', refreshColorPreviews);
    });
    document.querySelectorAll('input[name="jersey"]').forEach(function (el) {
      el.addEventListener('change', refreshColorPreviews);
    });

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

    const budgetToggle = document.getElementById('tb-budget-details-toggle');
    if (budgetToggle) {
      budgetToggle.addEventListener('click', function () {
        const details = document.getElementById('tb-budget-details');
        if (!details) return;
        const show = details.hidden;
        details.hidden = !show;
        budgetToggle.textContent = show ? 'Hide details' : 'Show details';
      });
    }

    document.getElementById('tb-apply').addEventListener('click', function () {
      readIdentity();
      readColors();
      if (!state.slot) return showError('Choose a slot first.');
      if (!state.identity.name || !validateAbbr()) return showError('Finish identity before applying.');
      if (
        state.roster_mode === 'import' &&
        state.import.headers.length &&
        !state.import.committed
      ) {
        return showError('Finish your CSV import or choose another roster option.');
      }
      openConfirmModal();
    });
    document.getElementById('tb-confirm-cancel').addEventListener('click', function () {
      document.getElementById('tb-confirm-modal').hidden = true;
    });
    document.getElementById('tb-confirm-apply').addEventListener('click', applyFranchise);

    setStep(0);
  });
})();
