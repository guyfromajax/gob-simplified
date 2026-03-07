(function () {
  'use strict';

  var Recruiting = window.RecruitingCommon;
  var context = Recruiting.getQueryContext();
  var sortState = { key: 'rt', direction: 'desc' };
  var recruits = [];
  var recruitMap = {};
  var currentOrder = [];
  var savedOrder = [];
  var allowLeave = false;

  function resolveBackUrl() {
    if (context.from === 'recruiting') {
      return Recruiting.buildRecruitingUrl('recruiting.html', context, { from: 'fcc' });
    }
    return Recruiting.buildFccUrl(context);
  }

  function hasUnsavedChanges() {
    return !Recruiting.arraysEqual(currentOrder, savedOrder);
  }

  function updateSubmitButton() {
    var btn = document.getElementById('submit-btn');
    var active = currentOrder.length > 0;
    btn.disabled = !active;
    btn.classList.toggle('is-dead', !active);
  }

  function renderRecruitList() {
    Recruiting.renderRecruitTableRows(
      document.getElementById('recruits-body'),
      Recruiting.sortRecruits(recruits, sortState),
      {
        selectedIds: new Set(currentOrder),
        onRowClick: function (recruit) {
          toggleRecruitSelection(recruit.recruitId);
        }
      }
    );
  }

  function buildAdjustButtons(index, filled) {
    var upDisabled = !filled || index === 0;
    var downDisabled = !filled || index === 9;
    return [
      '<div class="recruiting-adjust">',
      '<button class="recruiting-adjust-btn" type="button" data-action="up" data-index="' + index + '"' + (upDisabled ? ' disabled' : '') + '>↑</button>',
      '<button class="recruiting-adjust-btn" type="button" data-action="down" data-index="' + index + '"' + (downDisabled ? ' disabled' : '') + '>↓</button>',
      '</div>'
    ].join('');
  }

  function renderTopGrid() {
    var tbody = document.getElementById('orders-grid-body');
    tbody.innerHTML = '';

    for (var i = 0; i < 10; i += 1) {
      var recruitId = currentOrder[i] || null;
      var recruit = recruitId ? recruitMap[recruitId] : null;
      var tr = document.createElement('tr');
      tr.dataset.index = String(i);
      tr.dataset.filled = recruit ? 'true' : 'false';
      tr.draggable = !!recruit;

      tr.innerHTML = [
        '<td class="priority-cell">' + (i + 1) + '</td>',
        '<td>' + (recruit ? recruit.name : '<span class="recruiting-top-grid-empty">--</span>') + '</td>',
        '<td>' + (recruit ? recruit.homeRegion : '--') + '</td>',
        '<td>' + (recruit ? recruit.archetype : '--') + '</td>',
        '<td>' + (recruit ? recruit.pos : '--') + '</td>',
        '<td>' + (recruit && recruit.rt != null ? recruit.rt : '--') + '</td>',
        '<td>' + (recruit ? (recruit.leanDisplay || '--') : '--') + '</td>',
        '<td>' + buildAdjustButtons(i, !!recruit) + '</td>',
        '<td><button class="recruiting-remove-btn" type="button" data-action="remove" data-index="' + i + '"' + (recruit ? '' : ' disabled') + '>x</button></td>'
      ].join('');

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
    if (targetIndex < 0 || targetIndex > 9 || !currentOrder[index]) return;
    var currentId = currentOrder[index];
    var targetId = currentOrder[targetIndex] || null;
    currentOrder[targetIndex] = currentId;
    if (targetId) currentOrder[index] = targetId;
    else currentOrder.splice(index, 1);
    Recruiting.playSound('click-tiny.wav');
    rerender();
  }

  function removeRecruitAt(index) {
    if (!currentOrder[index]) return;
    currentOrder.splice(index, 1);
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

  function toggleRecruitSelection(recruitId) {
    var existingIndex = currentOrder.indexOf(recruitId);
    if (existingIndex !== -1) {
      removeRecruitAt(existingIndex);
      return;
    }
    if (currentOrder.length >= 10) {
      showModal({
        title: 'All 10 Rows Are Occupied',
        message: 'All 10 rows are occupied. You must remove a recruit',
        actions: [{ label: 'Close', variant: 'secondary' }]
      });
      return;
    }
    currentOrder.push(recruitId);
    Recruiting.playSound('click-tiny.wav');
    rerender();
  }

  function bindTopGridInteractions() {
    var tbody = document.getElementById('orders-grid-body');
    tbody.querySelectorAll('button[data-action]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var action = btn.dataset.action;
        var index = Number(btn.dataset.index);
        if (action === 'up') moveRecruit(index, -1);
        if (action === 'down') moveRecruit(index, 1);
        if (action === 'remove') removeRecruitAt(index);
      });
    });

    tbody.querySelectorAll('tr').forEach(function (row) {
      row.addEventListener('dragstart', function (e) {
        if (row.dataset.filled !== 'true') return;
        e.dataTransfer.setData('text/plain', row.dataset.index);
      });
      row.addEventListener('dragover', function (e) {
        if (row.dataset.filled !== 'true') return;
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
        if (row.dataset.filled !== 'true') return;
        if (Number.isNaN(fromIndex) || Number.isNaN(toIndex) || fromIndex === toIndex || !currentOrder[fromIndex]) return;
        var draggedId = currentOrder[fromIndex];
        var targetId = currentOrder[toIndex] || null;
        currentOrder[toIndex] = draggedId;
        if (targetId) currentOrder[fromIndex] = targetId;
        else currentOrder.splice(fromIndex, 1);
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
    if (!currentOrder.length) return;
    var btn = document.getElementById('submit-btn');
    btn.disabled = true;
    btn.textContent = 'Saving...';
    Recruiting.fetchJSON(API_CONFIG.buildUrl('/franchise/recruiting-orders'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        franchise_id: context.franchiseId,
        recruit_ids: currentOrder
      })
    }).then(function () {
      savedOrder = currentOrder.slice();
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

  function init() {
    if (!context.franchiseId || !context.teamId) {
      document.getElementById('recruits-body').innerHTML = '<tr><td colspan="20">Missing franchise context.</td></tr>';
      return;
    }

    document.getElementById('submit-btn').addEventListener('click', submitOrders);
    initNavigationGuards();

    Recruiting.fetchJSON(API_CONFIG.buildUrl('/franchise/recruiting-data') + '?franchise_id=' + encodeURIComponent(context.franchiseId))
      .then(function (data) {
        var week = Number(data.week || 1);
        if (Number(data.current_results_week || 0) === week) {
          navigateAway(Recruiting.buildRecruitingUrl('recruiting-results.html', context, { week: String(week) }));
          return;
        }
        recruits = Recruiting.normalizeRecruits(data.recruits || [], data.team_name_map || {});
        recruitMap = {};
        recruits.forEach(function (recruit) {
          recruitMap[recruit.recruitId] = recruit;
        });
        currentOrder = Recruiting.recruitingOrderIds(data.saved_orders).filter(function (recruitId) {
          return !!recruitMap[recruitId];
        });
        savedOrder = currentOrder.slice();
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
        document.getElementById('recruits-body').innerHTML = '<tr><td colspan="20">Failed to load recruits.</td></tr>';
      });
  }

  init();
})();
