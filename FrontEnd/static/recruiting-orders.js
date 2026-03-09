(function () {
  'use strict';

  var Recruiting = window.RecruitingCommon;
  var MAX_RECRUITING_ORDER_SLOTS = 20;
  var WEEK_36_START = 35;
  var WEEK_36_END = 36;
  var context = Recruiting.getQueryContext();
  var sortState = { key: 'rt', direction: 'desc' };
  var recruits = [];
  var recruitMap = {};
  var currentEntries = [];
  var savedEntries = [];
  var allowLeave = false;
  var activeWeek = 1;
  var availableRosterSpots = 0;
  var mode = 'visits';

  function isWeek36Mode() {
    return mode === 'week36';
  }

  function cloneEntry(entry) {
    return {
      id: entry.id,
      scholarship: !!entry.scholarship,
      playing_time: !!entry.playing_time
    };
  }

  function cloneEntries(entries) {
    return (entries || []).map(cloneEntry);
  }

  function entriesEqual(a, b) {
    if ((a || []).length !== (b || []).length) return false;
    for (var i = 0; i < (a || []).length; i += 1) {
      var left = a[i] || {};
      var right = b[i] || {};
      if (left.id !== right.id) return false;
      if (!!left.scholarship !== !!right.scholarship) return false;
      if (!!left.playing_time !== !!right.playing_time) return false;
    }
    return true;
  }

  function resolveBackUrl() {
    if (context.from === 'recruiting') {
      return Recruiting.buildRecruitingUrl('recruiting.html', context, { from: 'fcc' });
    }
    return Recruiting.buildFccUrl(context);
  }

  function hasUnsavedChanges() {
    return !entriesEqual(currentEntries, savedEntries);
  }

  function updateSubmitButton() {
    var btn = document.getElementById('submit-btn');
    var active = currentEntries.length > 0;
    btn.disabled = !active;
    btn.classList.toggle('is-dead', !active);
  }

  function getSelectedIds() {
    return new Set(currentEntries.map(function (entry) { return entry.id; }));
  }

  function setOrdersScreenCopy() {
    var help = document.getElementById('orders-help');
    var status = document.getElementById('orders-status');
    var table = document.getElementById('orders-grid-table');
    if (table) table.classList.toggle('orders-grid-table-week36', isWeek36Mode());
    if (isWeek36Mode()) {
      help.textContent = 'Drag to reorder the board, use the + column or row click to add and remove recruits, and save scholarship / playing time promises for later commitment logic.';
      status.textContent = 'Available Roster Spots ' + availableRosterSpots;
    } else {
      help.textContent = 'Rank up to 20 recruits. Drag and drop rows or use the up/down buttons to adjust priority.';
      status.textContent = '';
    }
  }

  function renderRecruitList() {
    Recruiting.renderRecruitTableRows(
      document.getElementById('recruits-body'),
      Recruiting.sortRecruits(recruits, sortState),
      {
        selectedIds: getSelectedIds(),
        onRowClick: function (recruit) {
          toggleRecruitSelection(recruit.recruitId);
        },
        onActionClick: function (recruit) {
          toggleRecruitSelection(recruit.recruitId);
        },
        getActionLabel: function (_recruit, selected) {
          return selected ? 'x' : '+';
        }
      }
    );
  }

  function buildTopGridHead() {
    var head = document.getElementById('orders-grid-head');
    if (!head) return;
    if (isWeek36Mode()) {
      head.innerHTML = [
        '<tr>',
        '<th>Priority</th>',
        '<th>Name</th>',
        '<th>Home Region</th>',
        '<th>Archetype</th>',
        '<th>HT</th>',
        '<th>WT</th>',
        '<th>POS</th>',
        '<th>SC</th>',
        '<th>SH</th>',
        '<th>ID</th>',
        '<th>OD</th>',
        '<th>PS</th>',
        '<th>BH</th>',
        '<th>RB</th>',
        '<th>AG</th>',
        '<th>ST</th>',
        '<th>ND</th>',
        '<th>IQ</th>',
        '<th>FT</th>',
        '<th>RT</th>',
        '<th>Current Lean</th>',
        '<th>Scholarship</th>',
        '<th>Playing Time</th>',
        '<th>Adjust</th>',
        '<th>Remove</th>',
        '</tr>'
      ].join('');
      return;
    }

    head.innerHTML = [
      '<tr>',
      '<th>Priority</th>',
      '<th>Recruit</th>',
      '<th>Home Region</th>',
      '<th>Archetype</th>',
      '<th>Pos</th>',
      '<th>RT</th>',
      '<th>Current Lean</th>',
      '<th>Adjust</th>',
      '<th>Remove</th>',
      '</tr>'
    ].join('');
  }

  function buildAdjustButtons(index, filled) {
    var maxIndex = isWeek36Mode() ? currentEntries.length - 1 : MAX_RECRUITING_ORDER_SLOTS - 1;
    var upDisabled = !filled || index === 0;
    var downDisabled = !filled || index >= maxIndex;
    return [
      '<div class="recruiting-adjust">',
      '<button class="recruiting-adjust-btn" type="button" data-action="up" data-index="' + index + '"' + (upDisabled ? ' disabled' : '') + '>↑</button>',
      '<button class="recruiting-adjust-btn" type="button" data-action="down" data-index="' + index + '"' + (downDisabled ? ' disabled' : '') + '>↓</button>',
      '</div>'
    ].join('');
  }

  function buildWeek36Row(index, recruit) {
    var attrs = recruit ? recruit.attrs : {};
    return [
      '<td class="priority-cell">' + (index + 1) + '</td>',
      '<td>' + (recruit ? recruit.name : '<span class="recruiting-top-grid-empty">--</span>') + '</td>',
      '<td>' + (recruit ? recruit.homeRegion : '--') + '</td>',
      '<td>' + (recruit ? recruit.archetype : '--') + '</td>',
      '<td>' + (recruit ? recruit.height : '--') + '</td>',
      '<td>' + (recruit && recruit.weight != null ? recruit.weight : '--') + '</td>',
      '<td>' + (recruit ? recruit.pos : '--') + '</td>',
      '<td>' + (recruit ? attrs.SC : '--') + '</td>',
      '<td>' + (recruit ? attrs.SH : '--') + '</td>',
      '<td>' + (recruit ? attrs.ID : '--') + '</td>',
      '<td>' + (recruit ? attrs.OD : '--') + '</td>',
      '<td>' + (recruit ? attrs.PS : '--') + '</td>',
      '<td>' + (recruit ? attrs.BH : '--') + '</td>',
      '<td>' + (recruit ? attrs.RB : '--') + '</td>',
      '<td>' + (recruit ? attrs.AG : '--') + '</td>',
      '<td>' + (recruit ? attrs.ST : '--') + '</td>',
      '<td>' + (recruit ? attrs.ND : '--') + '</td>',
      '<td>' + (recruit ? attrs.IQ : '--') + '</td>',
      '<td>' + (recruit ? attrs.FT : '--') + '</td>',
      '<td>' + (recruit && recruit.rt != null ? recruit.rt : '--') + '</td>',
      '<td>' + (recruit ? (recruit.leanDisplay || '--') : '--') + '</td>',
      '<td><input class="recruiting-checkbox" type="checkbox" data-action="scholarship" data-index="' + index + '"' + (recruit && currentEntries[index].scholarship ? ' checked' : '') + (recruit ? '' : ' disabled') + '></td>',
      '<td><input class="recruiting-checkbox" type="checkbox" data-action="playing_time" data-index="' + index + '"' + (recruit && currentEntries[index].playing_time ? ' checked' : '') + (recruit ? '' : ' disabled') + '></td>',
      '<td>' + buildAdjustButtons(index, !!recruit) + '</td>',
      '<td><button class="recruiting-remove-btn" type="button" data-action="remove" data-index="' + index + '"' + (recruit ? '' : ' disabled') + '>x</button></td>'
    ].join('');
  }

  function buildVisitRow(index, recruit) {
    return [
      '<td class="priority-cell">' + (index + 1) + '</td>',
      '<td>' + (recruit ? recruit.name : '<span class="recruiting-top-grid-empty">--</span>') + '</td>',
      '<td>' + (recruit ? recruit.homeRegion : '--') + '</td>',
      '<td>' + (recruit ? recruit.archetype : '--') + '</td>',
      '<td>' + (recruit ? recruit.pos : '--') + '</td>',
      '<td>' + (recruit && recruit.rt != null ? recruit.rt : '--') + '</td>',
      '<td>' + (recruit ? (recruit.leanDisplay || '--') : '--') + '</td>',
      '<td>' + buildAdjustButtons(index, !!recruit) + '</td>',
      '<td><button class="recruiting-remove-btn" type="button" data-action="remove" data-index="' + index + '"' + (recruit ? '' : ' disabled') + '>x</button></td>'
    ].join('');
  }

  function renderTopGrid() {
    var tbody = document.getElementById('orders-grid-body');
    var rowCount = isWeek36Mode() ? Math.max(currentEntries.length, 1) : MAX_RECRUITING_ORDER_SLOTS;
    tbody.innerHTML = '';

    for (var i = 0; i < rowCount; i += 1) {
      var entry = currentEntries[i] || null;
      var recruit = entry ? recruitMap[entry.id] : null;
      var tr = document.createElement('tr');
      tr.dataset.index = String(i);
      tr.dataset.filled = recruit ? 'true' : 'false';
      tr.draggable = !!recruit;
      tr.innerHTML = isWeek36Mode() ? buildWeek36Row(i, recruit) : buildVisitRow(i, recruit);
      tbody.appendChild(tr);
    }

    bindTopGridInteractions();
    updateSubmitButton();
  }

  function rerender() {
    renderTopGrid();
    renderRecruitList();
  }

  function moveRecruit(index, direction) {
    var targetIndex = index + direction;
    if (targetIndex < 0 || targetIndex >= currentEntries.length || !currentEntries[index]) return;
    var currentEntry = currentEntries[index];
    currentEntries[index] = currentEntries[targetIndex];
    currentEntries[targetIndex] = currentEntry;
    Recruiting.playSound('click-tiny.wav');
    rerender();
  }

  function removeRecruitAt(index) {
    if (!currentEntries[index]) return;
    currentEntries.splice(index, 1);
    Recruiting.playSound('x-back.mp3');
    rerender();
  }

  function showModal(config) {
    var backdrop = document.getElementById('recruiting-modal-backdrop');
    var title = document.getElementById('recruiting-modal-title');
    var message = document.getElementById('recruiting-modal-message');
    var actions = document.getElementById('recruiting-modal-actions');
    title.textContent = config.title || 'Recruiting';
    message.textContent = config.message || '';
    actions.innerHTML = '';
    (config.actions || []).forEach(function (action) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'recruiting-modal-btn ' + (action.variant || 'secondary');
      btn.textContent = action.label;
      btn.addEventListener('click', function () {
        backdrop.classList.remove('open');
        backdrop.setAttribute('aria-hidden', 'true');
        if (action.onClick) action.onClick();
      });
      actions.appendChild(btn);
    });
    backdrop.classList.add('open');
    backdrop.setAttribute('aria-hidden', 'false');
  }

  function defaultEntryForRecruit(recruitId) {
    return {
      id: recruitId,
      scholarship: false,
      playing_time: false
    };
  }

  function toggleRecruitSelection(recruitId) {
    var existingIndex = currentEntries.findIndex(function (entry) {
      return entry.id === recruitId;
    });
    if (existingIndex !== -1) {
      removeRecruitAt(existingIndex);
      return;
    }
    if (!isWeek36Mode() && currentEntries.length >= MAX_RECRUITING_ORDER_SLOTS) {
      showModal({
        title: 'All 20 Rows Are Occupied',
        message: 'All 20 rows are occupied. You must remove a recruit',
        actions: [{ label: 'Close', variant: 'secondary' }]
      });
      return;
    }
    currentEntries.push(defaultEntryForRecruit(recruitId));
    Recruiting.playSound('click-tiny.wav');
    rerender();
  }

  function insertMove(fromIndex, toIndex) {
    if (fromIndex < 0 || fromIndex >= currentEntries.length || !currentEntries[fromIndex]) return;
    var entry = currentEntries.splice(fromIndex, 1)[0];
    var insertAt = Math.max(0, Math.min(toIndex, currentEntries.length));
    if (fromIndex < toIndex) insertAt = Math.max(0, insertAt);
    currentEntries.splice(insertAt, 0, entry);
  }

  function bindTopGridInteractions() {
    var tbody = document.getElementById('orders-grid-body');
    tbody.querySelectorAll('button[data-action], input[data-action]').forEach(function (control) {
      control.addEventListener('click', function (e) {
        e.stopPropagation();
      });
      control.addEventListener('change', function () {
        if (control.tagName !== 'INPUT') return;
        var action = control.dataset.action;
        var index = Number(control.dataset.index);
        if (Number.isNaN(index) || !currentEntries[index]) return;
        if (action === 'scholarship') currentEntries[index].scholarship = control.checked;
        if (action === 'playing_time') currentEntries[index].playing_time = control.checked;
      });
      if (control.tagName === 'BUTTON') {
        control.addEventListener('click', function () {
          var action = control.dataset.action;
          var index = Number(control.dataset.index);
          if (action === 'up') moveRecruit(index, -1);
          if (action === 'down') moveRecruit(index, 1);
          if (action === 'remove') removeRecruitAt(index);
        });
      }
    });

    tbody.querySelectorAll('tr').forEach(function (row) {
      row.addEventListener('dragstart', function (e) {
        if (row.dataset.filled !== 'true') return;
        e.dataTransfer.setData('text/plain', row.dataset.index);
      });
      row.addEventListener('dragover', function (e) {
        e.preventDefault();
        row.classList.add('drag-over');
      });
      row.addEventListener('dragleave', function () {
        row.classList.remove('drag-over');
      });
      row.addEventListener('drop', function (e) {
        e.preventDefault();
        row.classList.remove('drag-over');
        var fromIndex = Number(e.dataTransfer.getData('text/plain'));
        var toIndex = Number(row.dataset.index);
        if (Number.isNaN(fromIndex) || Number.isNaN(toIndex) || fromIndex === toIndex || !currentEntries[fromIndex]) return;
        insertMove(fromIndex, toIndex);
        Recruiting.playSound('click-tiny.wav');
        rerender();
      });
    });
  }

  function navigateAway(url) {
    allowLeave = true;
    window.location.href = url;
  }

  function attemptLeave(url) {
    if (!hasUnsavedChanges()) {
      navigateAway(url);
      return;
    }
    showModal({
      title: 'Unsaved Recruiting Orders',
      message: 'You have unsaved recruiting orders. Are you sure you want to leave?',
      actions: [
        { label: 'Back To Recruiting', variant: 'primary' },
        { label: 'Leave', variant: 'secondary', onClick: function () { navigateAway(url); } }
      ]
    });
  }

  function submitOrders() {
    if (!currentEntries.length) return;
    var btn = document.getElementById('submit-btn');
    btn.disabled = true;
    btn.textContent = 'Saving...';

    var payload = { franchise_id: context.franchiseId };
    if (isWeek36Mode()) {
      payload.order_entries = currentEntries.map(function (entry) {
        return {
          id: entry.id,
          scholarship: !!entry.scholarship,
          playing_time: !!entry.playing_time
        };
      });
    } else {
      payload.recruit_ids = currentEntries.map(function (entry) { return entry.id; });
    }

    Recruiting.fetchJSON(API_CONFIG.buildUrl('/franchise/recruiting-orders'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(function () {
      savedEntries = cloneEntries(currentEntries);
      navigateAway(Recruiting.buildFccUrl(context));
    }).catch(function (err) {
      console.error(err);
      btn.disabled = false;
      btn.textContent = 'Submit Orders';
      updateSubmitButton();
      showModal({
        title: 'Save Failed',
        message: 'Unable to save recruiting orders.',
        actions: [{ label: 'Close', variant: 'secondary' }]
      });
    });
  }

  function initNavigationGuards() {
    var backBtn = document.getElementById('back-btn');
    backBtn.addEventListener('click', function () {
      attemptLeave(resolveBackUrl());
    });

    window.addEventListener('beforeunload', function (e) {
      if (!allowLeave && hasUnsavedChanges()) {
        e.preventDefault();
        e.returnValue = '';
      }
    });

    window.history.pushState({ recruitingOrders: true }, '', window.location.href);
    window.addEventListener('popstate', function () {
      if (allowLeave) return;
      attemptLeave(resolveBackUrl());
      window.history.pushState({ recruitingOrders: true }, '', window.location.href);
    });
  }

  function getWeek36AutofillEntries(userTeamId) {
    return Recruiting.sortRecruits(
      recruits.filter(function (recruit) {
        var lean = recruit.lean || {};
        return lean['1'] === userTeamId || lean['2'] === userTeamId || lean['3'] === userTeamId;
      }),
      { key: 'rt', direction: 'desc' }
    ).map(function (recruit) {
      return defaultEntryForRecruit(recruit.recruitId);
    });
  }

  function getSavedVisitEntries(savedOrders) {
    return Recruiting.recruitingOrderIds(savedOrders).filter(function (recruitId) {
      return !!recruitMap[recruitId];
    }).map(function (recruitId) {
      return defaultEntryForRecruit(recruitId);
    });
  }

  function getSavedWeek36Entries(savedOrderEntries) {
    return (savedOrderEntries || []).map(function (entry) {
      return {
        id: entry.id,
        scholarship: !!entry.scholarship,
        playing_time: !!entry.playing_time
      };
    }).filter(function (entry) {
      return !!recruitMap[entry.id];
    });
  }

  function init() {
    if (!context.franchiseId || !context.teamId) {
      document.getElementById('recruits-body').innerHTML = '<tr><td colspan="21">Missing franchise context.</td></tr>';
      return;
    }

    document.getElementById('submit-btn').addEventListener('click', submitOrders);
    initNavigationGuards();

    Recruiting.fetchJSON(API_CONFIG.buildUrl('/franchise/recruiting-data') + '?franchise_id=' + encodeURIComponent(context.franchiseId))
      .then(function (data) {
        activeWeek = Number(data.week || 1);
        if (Number(data.current_results_week || 0) === activeWeek && activeWeek >= 20 && activeWeek <= 26) {
          navigateAway(Recruiting.buildRecruitingUrl('recruiting-results.html', context, { week: String(activeWeek) }));
          return;
        }

        mode = activeWeek >= WEEK_36_START && activeWeek <= WEEK_36_END ? 'week36' : 'visits';
        availableRosterSpots = Number(data.available_roster_spots || 0);
        recruits = Recruiting.normalizeRecruits(data.recruits || [], data.team_name_map || {});
        recruitMap = {};
        recruits.forEach(function (recruit) {
          recruitMap[recruit.recruitId] = recruit;
        });

        buildTopGridHead();
        setOrdersScreenCopy();

        if (isWeek36Mode()) {
          currentEntries = getSavedWeek36Entries(data.saved_order_entries_week_36);
          if (!currentEntries.length) {
            currentEntries = getWeek36AutofillEntries(data.team_id);
          }
        } else {
          currentEntries = getSavedVisitEntries(data.saved_orders);
        }
        savedEntries = cloneEntries(currentEntries);

        Recruiting.bindSortableHeaders(
          document.getElementById('recruits-table'),
          sortState,
          renderRecruitList
        );
        rerender();
        if (typeof window.initAttributeTooltips === 'function') {
          window.initAttributeTooltips(document.getElementById('recruits-table'), ['th']);
        }
      })
      .catch(function (err) {
        console.error(err);
        document.getElementById('recruits-body').innerHTML = '<tr><td colspan="21">Failed to load recruits.</td></tr>';
      });
  }

  init();
})();
