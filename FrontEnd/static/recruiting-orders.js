(function () {
  'use strict';

  var Recruiting = window.RecruitingCommon;
  var MAX_RECRUITING_ORDER_SLOTS = 20;
  var context = Recruiting.getQueryContext();
  var sortState = { key: 'rt', direction: 'desc' };
  var recruits = [];
  var recruitMap = {};
  var currentEntries = [];
  var savedEntries = [];
  var poolFilters = { regions: [], search: '', rtMin: 35, leansOnly: false };
  var showOnlyMine = false;
  var lastAddedRecruitId = null;
  var dragFromIndex = null;
  var allowLeave = false;
  var activeWeek = 1;
  var availableRosterSpots = 0;
  var mode = 'visits';
  var userTeamId = context.teamId || '';
  var WEEK_35_POINTS_BUDGET = 20;
  var FILTER_STORAGE_KEY = 'gob-recruiting-orders-v2-filters';

  window.addEventListener('pageshow', function (event) {
    if (event.persisted) {
      window.location.reload();
    }
  });

  function isWeek35Mode() {
    return mode === 'week35';
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  /** Same behavior as training-playbooks.js: toast + auto-dismiss 3.2s; dismiss button ends early. */
  function showToast(title, subtitle) {
    var toast = document.getElementById('toast');
    if (!toast) return;
    toast.innerHTML =
      '<div class="toast-icon" aria-hidden="true"></div>' +
      '<div class="toast-copy">' +
      '<div class="toast-title">' + escapeHtml(title) + '</div>' +
      (subtitle ? '<div class="toast-subline">' + escapeHtml(subtitle) + '</div>' : '') +
      '</div>' +
      '<button type="button" class="toast-dismiss" aria-label="Dismiss">×</button>';
    toast.hidden = false;
    requestAnimationFrame(function () {
      toast.classList.add('visible');
    });
    var dismiss = function () {
      toast.classList.remove('visible');
      window.setTimeout(function () {
        toast.hidden = true;
      }, 220);
    };
    var dismissBtn = toast.querySelector('.toast-dismiss');
    if (dismissBtn) dismissBtn.addEventListener('click', dismiss, { once: true });
    window.setTimeout(dismiss, 3200);
  }

  /** Invite list cards: "David Jones" → "D Jones" (first initial + last name). Single token unchanged. */
  function formatInviteListNameDisplay(name) {
    var s = String(name == null ? '' : name).trim();
    if (!s) return '';
    var parts = s.split(/\s+/).filter(Boolean);
    if (parts.length === 1) return escapeHtml(parts[0]);
    var initial = parts[0].charAt(0);
    var last = parts[parts.length - 1];
    return escapeHtml(initial + ' ' + last);
  }

  function getVisitStorageKey() {
    return FILTER_STORAGE_KEY + ':' + (context.franchiseId || 'global') + ':' + (context.teamId || 'team');
  }

  function loadVisitPreferences() {
    try {
      var raw = window.localStorage.getItem(getVisitStorageKey());
      if (!raw) return;
      var parsed = JSON.parse(raw);
      if (parsed && typeof parsed === 'object') {
        poolFilters = Object.assign({}, poolFilters, parsed.filters || {});
        if (!Array.isArray(poolFilters.regions)) poolFilters.regions = [];
        poolFilters.rtMin = Number(poolFilters.rtMin || 0);
        showOnlyMine = !!parsed.showOnlyMine;
        if (parsed.sort && parsed.sort.key) {
          sortState.key = parsed.sort.key;
          sortState.direction = parsed.sort.direction === 'asc' ? 'asc' : 'desc';
        }
      }
    } catch (e) {}
  }

  function saveVisitPreferences() {
    try {
      window.localStorage.setItem(getVisitStorageKey(), JSON.stringify({
        filters: poolFilters,
        showOnlyMine: showOnlyMine,
        sort: sortState
      }));
    } catch (e) {}
  }

  function getRecruitRank(recruitId) {
    var index = currentEntries.findIndex(function (entry) { return entry.id === recruitId; });
    return index === -1 ? 0 : index + 1;
  }

  function getLeanRankForUser(recruit) {
    var lean = recruit && recruit.lean ? recruit.lean : {};
    var teamId = String(userTeamId || context.teamId || '');
    if (!teamId) return 0;
    if (String(lean['1'] || '') === teamId) return 1;
    if (String(lean['2'] || '') === teamId) return 2;
    if (String(lean['3'] || '') === teamId) return 3;
    return 0;
  }

  /** True when the user's team appears in this recruit's lean slots 1, 2, or 3. */
  function isUserInLeanTopThree(recruit) {
    return getLeanRankForUser(recruit) > 0;
  }

  function getLeanCellHtml(recruit) {
    var rank = getLeanRankForUser(recruit);
    if (rank >= 1 && rank <= 3) {
      var display = recruit.leanDisplay && String(recruit.leanDisplay).trim() ? recruit.leanDisplay : 'Open';
      return '<span class="lean-cell lean-cell-full-list">' + escapeHtml(display) + '</span>';
    }
    return '<span class="lean-cell">' + escapeHtml(recruit.leanDisplay || 'Open') + '</span>';
  }

  function getRecruitNameCellHtml(recruit) {
    if (!recruit) return '<span class="recruiting-top-grid-empty">--</span>';
    var dot = isUserInLeanTopThree(recruit)
      ? '<span class="lean-dot is-solid lean-after-name" aria-label="Your team is on this recruit\u2019s lean list"></span>'
      : '';
    return escapeHtml(recruit.name || '') + dot;
  }

  function getPositionCounts() {
    var counts = { PG: 0, SG: 0, SF: 0, PF: 0, C: 0 };
    currentEntries.forEach(function (entry) {
      var recruit = recruitMap[entry.id];
      var pos = recruit && recruit.pos;
      if (Object.prototype.hasOwnProperty.call(counts, pos)) counts[pos] += 1;
    });
    return counts;
  }

  function getLeaningPickCount() {
    return currentEntries.reduce(function (total, entry) {
      return total + (isUserInLeanTopThree(recruitMap[entry.id]) ? 1 : 0);
    }, 0);
  }

  function cloneEntry(entry) {
    return {
      id: entry.id,
      points: Number(entry.points || 0),
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
      if (Number(left.points || 0) !== Number(right.points || 0)) return false;
      if (!!left.playing_time !== !!right.playing_time) return false;
    }
    return true;
  }

  function resolveBackUrl() {
    if (context.from === 'training') {
      var params = new URLSearchParams();
      if (context.franchiseId) params.set('franchise_id', context.franchiseId);
      if (context.teamId) params.set('team_id', context.teamId);
      params.set('mode', 'franchise');
      params.set('session_type', new URLSearchParams(window.location.search).get('session_type') || 'in-season');
      return '/training.html?' + params.toString();
    }
    if (context.from === 'recruiting') {
      return Recruiting.buildRecruitingUrl('recruiting.html', context, { from: 'fcc' });
    }
    return Recruiting.buildFccUrl(context);
  }

  function hasUnsavedChanges() {
    return !entriesEqual(currentEntries, savedEntries);
  }

  function updateActionButtons() {
    var saveBtn = document.getElementById('save-btn');
    var runBtn = document.getElementById('run-btn');
    var hasCurrent = currentEntries.length > 0;
    var hasSaved = savedEntries.length > 0;
    saveBtn.textContent = 'Save Orders';
    saveBtn.disabled = !hasCurrent;
    saveBtn.classList.toggle('is-dead', !hasCurrent);
    runBtn.style.display = isWeek35Mode() ? 'inline-flex' : 'none';
    if (isWeek35Mode()) {
      runBtn.disabled = !(hasCurrent || hasSaved);
      runBtn.classList.toggle('is-dead', !(hasCurrent || hasSaved));
    }
  }

  function getSelectedIds() {
    return new Set(currentEntries.map(function (entry) { return entry.id; }));
  }

  function showModal(config) {
    var backdrop = document.getElementById('recruiting-modal-backdrop');
    var accent = document.getElementById('recruiting-modal-accent');
    var title = document.getElementById('recruiting-modal-title');
    var message = document.getElementById('recruiting-modal-message');
    var actions = document.getElementById('recruiting-modal-actions');
    title.textContent = config.title || 'Recruiting';
    message.textContent = config.message || '';
    if (accent) {
      accent.className = 'gob-modal-accent';
      if (config.accent) accent.classList.add(config.accent);
    }
    actions.innerHTML = '';
    (config.actions || []).forEach(function (action) {
      var btn = document.createElement('button');
      btn.type = 'button';
      var variant = action.variant || 'secondary';
      btn.className = variant === 'primary' ? 'gob-modal-btn-primary' : 'gob-modal-btn-secondary';
      btn.textContent = action.label;
      btn.addEventListener('click', function () {
        backdrop.classList.remove('open', 'is-visible');
        backdrop.setAttribute('aria-hidden', 'true');
        if (action.onClick) action.onClick();
      });
      actions.appendChild(btn);
    });
    backdrop.classList.add('open', 'is-visible');
    backdrop.setAttribute('aria-hidden', 'false');
  }

  function setOrdersScreenCopy() {
    var title = document.getElementById('orders-title');
    var help = document.getElementById('orders-help');
    var status = document.getElementById('orders-status');
    var table = document.getElementById('orders-grid-table');
    var visitsDock = document.getElementById('visits-dock-section');
    var ordersTableSection = document.getElementById('orders-table-section');
    var poolTitle = document.getElementById('recruit-pool-title');
    var poolFiltersEl = document.getElementById('recruit-pool-filters');
    var picksToggle = document.getElementById('show-only-picks-toggle');
    if (table) table.classList.toggle('orders-grid-table-week36', isWeek35Mode());
    if (isWeek35Mode()) {
      if (title) title.textContent = 'Recruiting Focus List';
      if (help) help.textContent = '';
      if (status) status.textContent = 'Available Roster Spots: ' + availableRosterSpots + ', Points Remaining: ' + getWeek35PointsRemaining();
      if (visitsDock) visitsDock.hidden = true;
      if (ordersTableSection) ordersTableSection.hidden = false;
      if (poolTitle) poolTitle.textContent = 'All Recruits';
      if (poolFiltersEl) poolFiltersEl.hidden = true;
      if (picksToggle) picksToggle.hidden = true;
    } else {
      if (title) title.textContent = 'Recruiting Orders';
      if (help) help.textContent = '';
      if (status) status.textContent = '';
      if (visitsDock) visitsDock.hidden = false;
      if (ordersTableSection) ordersTableSection.hidden = true;
      if (poolTitle) poolTitle.textContent = 'Recruit Pool';
      if (poolFiltersEl) poolFiltersEl.hidden = false;
      if (picksToggle) picksToggle.hidden = false;
    }
  }

  function getWeek35AssignedPoints() {
    return currentEntries.reduce(function (total, entry) {
      return total + Number((entry || {}).points || 0);
    }, 0);
  }

  function getWeek35PointsRemaining() {
    return Math.max(0, WEEK_35_POINTS_BUDGET - getWeek35AssignedPoints());
  }

  function renderRecruitList() {
    if (!isWeek35Mode()) {
      renderRecruitPool();
      return;
    }
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

  function applyPoolFilters(list) {
    var selectedIds = getSelectedIds();
    var search = String(poolFilters.search || '').trim().toLowerCase();
    var regions = poolFilters.regions || [];
    var rtMin = Number(poolFilters.rtMin || 0);
    return list.filter(function (recruit) {
      if (showOnlyMine && !selectedIds.has(recruit.recruitId)) return false;
      if (regions.length && regions.indexOf(String(recruit.homeRegion || '').trim().toUpperCase().charAt(0)) === -1) return false;
      if (search) {
        var haystack = [
          recruit.name,
          recruit.pos,
          recruit.homeRegion,
          recruit.archetype,
          recruit.leanDisplay
        ].join(' ').toLowerCase();
        if (haystack.indexOf(search) === -1) return false;
      }
      if (recruit.rt != null && recruit.rt < rtMin) return false;
      if (recruit.rt == null && rtMin > 0) return false;
      if (poolFilters.leansOnly && !isUserInLeanTopThree(recruit)) return false;
      return true;
    });
  }

  function renderRecruitPool() {
    var tbody = document.getElementById('recruits-body');
    if (!tbody) return;
    var sorted = Recruiting.sortRecruits(applyPoolFilters(recruits), sortState);
    tbody.innerHTML = '';
    sorted.forEach(function (recruit) {
      var rank = getRecruitRank(recruit.recruitId);
      var tr = document.createElement('tr');
      tr.dataset.recruitId = recruit.recruitId;
      if (rank) tr.classList.add('recruit-selected');
      if (isUserInLeanTopThree(recruit)) tr.classList.add('is-leaning-row');
      tr.innerHTML = [
        '<td>' + getRecruitNameCellHtml(recruit) + '</td>',
        '<td>' + escapeHtml(recruit.homeRegion) + '</td>',
        '<td>' + escapeHtml(recruit.archetype) + '</td>',
        '<td>' + escapeHtml(recruit.height) + '</td>',
        '<td>' + (recruit.weight != null ? escapeHtml(recruit.weight) : '--') + '</td>',
        '<td>' + escapeHtml(recruit.pos) + '</td>',
        '<td>' + escapeHtml(recruit.attrs.SC) + '</td>',
        '<td>' + escapeHtml(recruit.attrs.SH) + '</td>',
        '<td>' + escapeHtml(recruit.attrs.ID) + '</td>',
        '<td>' + escapeHtml(recruit.attrs.OD) + '</td>',
        '<td>' + escapeHtml(recruit.attrs.PS) + '</td>',
        '<td>' + escapeHtml(recruit.attrs.BH) + '</td>',
        '<td>' + escapeHtml(recruit.attrs.RB) + '</td>',
        '<td>' + escapeHtml(recruit.attrs.AG) + '</td>',
        '<td>' + escapeHtml(recruit.attrs.ST) + '</td>',
        '<td>' + escapeHtml(recruit.attrs.ND) + '</td>',
        '<td>' + escapeHtml(recruit.attrs.IQ) + '</td>',
        '<td>' + escapeHtml(recruit.attrs.FT) + '</td>',
        '<td>' + (recruit.rt != null ? escapeHtml(recruit.rt) : '--') + '</td>',
        '<td>' + getLeanCellHtml(recruit) + '</td>',
        '<td>' + (rank
          ? '<button class="picked-rank-badge" type="button" data-action="scroll-to-pick" data-recruit-id="' + escapeHtml(recruit.recruitId) + '">' + rank + '</button>'
          : '<button class="recruiting-row-action-btn" type="button" data-action="add-recruit" data-recruit-id="' + escapeHtml(recruit.recruitId) + '">+</button>') + '</td>'
      ].join('');
      tbody.appendChild(tr);
    });
    if (!sorted.length) {
      tbody.innerHTML = '<tr><td colspan="21">No recruits match the current filters.</td></tr>';
    }
    tbody.querySelectorAll('button[data-action="add-recruit"]').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        toggleRecruitSelection(btn.dataset.recruitId);
      });
    });
    tbody.querySelectorAll('button[data-action="scroll-to-pick"]').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        scrollToPick(btn.dataset.recruitId);
      });
    });
    if (typeof window.initAttributeTooltips === 'function') {
      window.initAttributeTooltips(tbody, ['td']);
    }
    var picksToggle = document.getElementById('show-only-picks-toggle');
    if (picksToggle) {
      picksToggle.classList.toggle('is-active', showOnlyMine);
      picksToggle.setAttribute('aria-pressed', showOnlyMine ? 'true' : 'false');
    }
  }

  function buildTopGridHead() {
    var head = document.getElementById('orders-grid-head');
    if (!head) return;
    if (isWeek35Mode()) {
      head.innerHTML = [
        '<tr>',
        '<th>Priority</th>',
        '<th>Recruit</th>',
        '<th>Home Region</th>',
        '<th>Archetype</th>',
        '<th>HT</th>',
        '<th>WT</th>',
        '<th>POS</th>',
        '<th>RT</th>',
        '<th>Current Lean</th>',
        '<th>Points</th>',
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
    var maxIndex = isWeek35Mode() ? currentEntries.length - 1 : MAX_RECRUITING_ORDER_SLOTS - 1;
    var upDisabled = !filled || index === 0;
    var downDisabled = !filled || index >= maxIndex;
    return [
      '<div class="recruiting-adjust">',
      '<button class="recruiting-adjust-btn" type="button" data-action="up" data-index="' + index + '"' + (upDisabled ? ' disabled' : '') + '>↑</button>',
      '<button class="recruiting-adjust-btn" type="button" data-action="down" data-index="' + index + '"' + (downDisabled ? ' disabled' : '') + '>↓</button>',
      '</div>'
    ].join('');
  }

  function buildWeek35Row(index, recruit) {
    var entry = currentEntries[index] || {};
    var pointsValue = recruit ? Number(entry.points || 0) : 0;
    return [
      '<td class="priority-cell">' + (index + 1) + '</td>',
      '<td>' + getRecruitNameCellHtml(recruit) + '</td>',
      '<td>' + (recruit ? recruit.homeRegion : '--') + '</td>',
      '<td>' + (recruit ? recruit.archetype : '--') + '</td>',
      '<td>' + (recruit ? recruit.height : '--') + '</td>',
      '<td>' + (recruit && recruit.weight != null ? recruit.weight : '--') + '</td>',
      '<td>' + (recruit ? recruit.pos : '--') + '</td>',
      '<td>' + (recruit && recruit.rt != null ? recruit.rt : '--') + '</td>',
      '<td>' + (recruit ? getLeanCellHtml(recruit) : '--') + '</td>',
      '<td><input class="recruiting-points-input" inputmode="numeric" type="text" data-action="points" data-index="' + index + '" value="' + pointsValue + '"' + (recruit ? '' : ' disabled') + '></td>',
      '<td><input class="recruiting-checkbox" type="checkbox" data-action="playing_time" data-index="' + index + '"' + (recruit && !!entry.playing_time ? ' checked' : '') + (recruit ? '' : ' disabled') + '></td>',
      '<td>' + buildAdjustButtons(index, !!recruit) + '</td>',
      '<td><button class="recruiting-remove-btn" type="button" data-action="remove" data-index="' + index + '"' + (recruit ? '' : ' disabled') + '>x</button></td>'
    ].join('');
  }

  function buildVisitRow(index, recruit) {
    return [
      '<td class="priority-cell">' + (index + 1) + '</td>',
      '<td>' + getRecruitNameCellHtml(recruit) + '</td>',
      '<td>' + (recruit ? recruit.homeRegion : '--') + '</td>',
      '<td>' + (recruit ? recruit.archetype : '--') + '</td>',
      '<td>' + (recruit ? recruit.pos : '--') + '</td>',
      '<td>' + (recruit && recruit.rt != null ? recruit.rt : '--') + '</td>',
      '<td>' + (recruit ? getLeanCellHtml(recruit) : '--') + '</td>',
      '<td>' + buildAdjustButtons(index, !!recruit) + '</td>',
      '<td><button class="recruiting-remove-btn" type="button" data-action="remove" data-index="' + index + '"' + (recruit ? '' : ' disabled') + '>x</button></td>'
    ].join('');
  }

  function renderTopGrid() {
    if (!isWeek35Mode()) {
      renderInviteDock();
      updateActionButtons();
      return;
    }
    var tbody = document.getElementById('orders-grid-body');
    var rowCount = MAX_RECRUITING_ORDER_SLOTS;
    tbody.innerHTML = '';

    for (var i = 0; i < rowCount; i += 1) {
      var entry = currentEntries[i] || null;
      var recruit = entry ? recruitMap[entry.id] : null;
      var tr = document.createElement('tr');
      tr.dataset.index = String(i);
      tr.dataset.filled = recruit ? 'true' : 'false';
      tr.draggable = !!recruit;
      tr.innerHTML = isWeek35Mode() ? buildWeek35Row(i, recruit) : buildVisitRow(i, recruit);
      tbody.appendChild(tr);
    }

    bindTopGridInteractions();
    updateActionButtons();
  }

  function renderInviteDock() {
    renderInviteDockHeader();
    renderInviteSlots();
  }

  function renderInviteDockHeader() {
    var counts = getPositionCounts();
    var breakdown = document.getElementById('position-breakdown');
    var leaningBadge = document.getElementById('leaning-badge');
    var leaningDivider = document.getElementById('leaning-divider');
    var firstDivider = document.getElementById('meta-first-divider');
    var fillMoreLink = document.getElementById('fill-more-link');
    var inviteCount = document.getElementById('invite-count');
    var positions = ['PG', 'SG', 'SF', 'PF', 'C'];
    if (breakdown) {
      breakdown.innerHTML = positions.map(function (pos) {
        var count = counts[pos] || 0;
        return '<div class="position-group' + (count ? '' : ' is-zero') + '"><span class="position-count">' + count + '</span><span class="position-label">' + pos + '</span></div>';
      }).join('');
    }
    var leaningCount = getLeaningPickCount();
    if (leaningBadge) {
      leaningBadge.hidden = leaningCount <= 0;
      leaningBadge.innerHTML = '<span class="leaning-dot"></span><span class="leaning-count">' + leaningCount + '</span><span>leaning to you</span>';
    }
    if (leaningDivider) leaningDivider.hidden = leaningCount <= 0 || currentEntries.length >= MAX_RECRUITING_ORDER_SLOTS;
    if (fillMoreLink) {
      var remaining = MAX_RECRUITING_ORDER_SLOTS - currentEntries.length;
      fillMoreLink.hidden = !(currentEntries.length > 0 && remaining > 0);
      fillMoreLink.textContent = remaining + ' more to fill ↓';
    }
    if (firstDivider) firstDivider.hidden = leaningCount <= 0 && !(currentEntries.length > 0 && currentEntries.length < MAX_RECRUITING_ORDER_SLOTS);
    if (inviteCount) inviteCount.textContent = String(currentEntries.length);
  }

  function buildGripHtml() {
    return '<span></span><span></span><span></span><span></span><span></span><span></span>';
  }

  function buildSlotHtml(index, recruit) {
    if (!recruit) {
      return [
        '<div class="slot-rank">' + (index + 1) + '</div>',
        '<div class="slot-body"><div class="slot-name">' + (index === currentEntries.length ? 'Add next' : 'Empty') + '</div></div>'
      ].join('');
    }
    return [
      '<div class="slot-grip" aria-hidden="true">' + buildGripHtml() + '</div>',
      '<div class="slot-body">',
      '<div class="slot-name" title="' + escapeHtml(recruit.name) + '">' + formatInviteListNameDisplay(recruit.name) + '</div>',
      '<div class="slot-meta"><span class="slot-rank">' + (index + 1) + '</span><span class="slot-pos-badge">' + escapeHtml(recruit.pos) + '</span><span>' + escapeHtml(recruit.homeRegion) + '</span><span class="slot-rt">RT ' + (recruit.rt != null ? escapeHtml(recruit.rt) : '--') + '</span></div>',
      '</div>',
      isUserInLeanTopThree(recruit) ? '<span class="lean-dot is-solid" aria-label="Your team is on this recruit\u2019s lean list"></span>' : '<span></span>',
      '<button class="slot-remove" type="button" data-action="remove" data-index="' + index + '" aria-label="Remove ' + escapeHtml(recruit.name) + '">×</button>'
    ].join('');
  }

  function renderInviteSlots() {
    var grid = document.getElementById('invite-slot-grid');
    if (!grid) return;
    grid.innerHTML = '';
    for (var i = 0; i < MAX_RECRUITING_ORDER_SLOTS; i += 1) {
      var entry = currentEntries[i] || null;
      var recruit = entry ? recruitMap[entry.id] : null;
      var slot = document.createElement('div');
      slot.className = 'invite-slot ' + (recruit ? 'is-filled' : 'is-empty');
      if (!recruit && i === currentEntries.length) slot.classList.add('is-next-empty');
      if (recruit && isUserInLeanTopThree(recruit)) slot.classList.add('is-leaning');
      if (recruit && recruit.recruitId === lastAddedRecruitId) slot.classList.add('is-new-add');
      slot.dataset.index = String(i);
      slot.dataset.filled = recruit ? 'true' : 'false';
      slot.draggable = !!recruit;
      slot.innerHTML = buildSlotHtml(i, recruit);
      grid.appendChild(slot);
    }
    if (lastAddedRecruitId) {
      window.setTimeout(function () {
        lastAddedRecruitId = null;
      }, 750);
    }
    bindInviteSlotInteractions();
  }

  function rerender() {
    setOrdersScreenCopy();
    renderTopGrid();
    renderRecruitList();
  }

  function defaultEntryForRecruit(recruitId) {
    return {
      id: recruitId,
      points: 0,
      scholarship: false,
      playing_time: false
    };
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

  function requestRemoveRecruitAt(index) {
    var entry = currentEntries[index];
    if (!entry) return;
    var recruit = recruitMap[entry.id];
    if (recruit && Number(recruit.rt || 0) >= 60 && !isWeek35Mode()) {
      showModal({
        title: 'Remove Recruit?',
        message: 'This recruit is rated ' + recruit.rt + '. Remove ' + recruit.name + ' from your invite list?',
        accent: 'is-red',
        actions: [
          { label: 'Keep', variant: 'secondary' },
          { label: 'Remove', variant: 'primary', onClick: function () { removeRecruitAt(index); } }
        ]
      });
      return;
    }
    removeRecruitAt(index);
  }

  function toggleRecruitSelection(recruitId) {
    var existingIndex = currentEntries.findIndex(function (entry) {
      return entry.id === recruitId;
    });
    if (existingIndex !== -1) {
      removeRecruitAt(existingIndex);
      return;
    }
    if (currentEntries.length >= MAX_RECRUITING_ORDER_SLOTS) {
      showModal({
        title: 'All 20 Rows Are Occupied',
        message: 'All 20 rows are occupied. You must remove a recruit',
        actions: [{ label: 'Close', variant: 'secondary' }]
      });
      return;
    }
    currentEntries.push(defaultEntryForRecruit(recruitId));
    lastAddedRecruitId = recruitId;
    Recruiting.playSound('click-tiny.wav');
    rerender();
  }

  function insertMove(fromIndex, toIndex) {
    if (fromIndex < 0 || fromIndex >= currentEntries.length || !currentEntries[fromIndex]) return;
    var entry = currentEntries.splice(fromIndex, 1)[0];
    var insertAt = Math.max(0, Math.min(toIndex, currentEntries.length));
    currentEntries.splice(insertAt, 0, entry);
    if (!isWeek35Mode() && currentEntries.length > MAX_RECRUITING_ORDER_SLOTS) {
      currentEntries = currentEntries.slice(0, MAX_RECRUITING_ORDER_SLOTS);
    }
  }

  function scrollToPoolAndFocusSearch() {
    var pool = document.getElementById('recruit-pool-title');
    if (pool) pool.scrollIntoView({ behavior: 'smooth', block: 'start' });
    window.setTimeout(function () {
      var search = document.getElementById('recruit-search');
      if (search) search.focus({ preventScroll: true });
    }, 300);
  }

  function scrollToPick(recruitId) {
    var rank = getRecruitRank(recruitId);
    var slot = rank ? document.querySelector('.invite-slot[data-index="' + (rank - 1) + '"]') : null;
    if (slot) {
      slot.scrollIntoView({ behavior: 'smooth', block: 'center' });
      slot.classList.add('is-new-add');
      window.setTimeout(function () { slot.classList.remove('is-new-add'); }, 750);
    }
  }

  function bindInviteSlotInteractions() {
    var grid = document.getElementById('invite-slot-grid');
    if (!grid) return;
    grid.querySelectorAll('.invite-slot').forEach(function (slot) {
      slot.addEventListener('click', function () {
        if (slot.dataset.filled === 'false') scrollToPoolAndFocusSearch();
      });
      var removeBtn = slot.querySelector('.slot-remove');
      if (removeBtn) {
        removeBtn.addEventListener('click', function (e) {
          e.stopPropagation();
          requestRemoveRecruitAt(Number(removeBtn.dataset.index));
        });
      }
      slot.addEventListener('dragstart', function (e) {
        if (slot.dataset.filled !== 'true') return;
        dragFromIndex = Number(slot.dataset.index);
        e.dataTransfer.setData('text/plain', slot.dataset.index);
        slot.classList.add('is-dragging');
      });
      slot.addEventListener('dragend', function () {
        dragFromIndex = null;
        grid.querySelectorAll('.invite-slot').forEach(function (item) {
          item.classList.remove('is-dragging', 'is-drag-over', 'is-shift-preview');
        });
      });
      slot.addEventListener('dragover', function (e) {
        e.preventDefault();
        var toIndex = Number(slot.dataset.index);
        grid.querySelectorAll('.invite-slot').forEach(function (item) {
          item.classList.remove('is-drag-over', 'is-shift-preview');
        });
        slot.classList.add('is-drag-over');
        if (dragFromIndex != null && toIndex !== dragFromIndex) {
          slot.classList.add('is-shift-preview');
        }
      });
      slot.addEventListener('dragleave', function () {
        slot.classList.remove('is-drag-over', 'is-shift-preview');
      });
      slot.addEventListener('drop', function (e) {
        e.preventDefault();
        var fromIndex = Number(e.dataTransfer.getData('text/plain'));
        var toIndex = Number(slot.dataset.index);
        if (Number.isNaN(fromIndex) || Number.isNaN(toIndex) || fromIndex === toIndex || !currentEntries[fromIndex]) return;
        insertMove(fromIndex, Math.min(toIndex, currentEntries.length - 1));
        Recruiting.playSound('click-tiny.wav');
        rerender();
      });
    });
  }

  function bindTopGridInteractions() {
    var tbody = document.getElementById('orders-grid-body');
    tbody.querySelectorAll('button[data-action], input[data-action]').forEach(function (control) {
      if (control.dataset.action === 'points') {
        control.addEventListener('keydown', function (e) {
          var allowedKeys = ['Backspace', 'Delete', 'ArrowLeft', 'ArrowRight', 'Tab', 'Home', 'End'];
          if (allowedKeys.indexOf(e.key) !== -1) return;
          if (!/^\d$/.test(e.key)) {
            e.preventDefault();
            return;
          }
          var index = Number(control.dataset.index);
          if (Number.isNaN(index) || !currentEntries[index]) {
            e.preventDefault();
            return;
          }
          var currentValue = String(control.value || '');
          var selectionStart = control.selectionStart != null ? control.selectionStart : currentValue.length;
          var selectionEnd = control.selectionEnd != null ? control.selectionEnd : currentValue.length;
          var nextValue = currentValue.slice(0, selectionStart) + e.key + currentValue.slice(selectionEnd);
          var parsed = Number(nextValue || 0);
          var totalWithoutCurrent = getWeek35AssignedPoints() - Number(currentEntries[index].points || 0);
          if (parsed + totalWithoutCurrent > WEEK_35_POINTS_BUDGET) {
            e.preventDefault();
          }
        });
      }
      control.addEventListener('click', function (e) {
        e.stopPropagation();
      });
      control.addEventListener('input', function () {
        if (control.tagName !== 'INPUT') return;
        var action = control.dataset.action;
        var index = Number(control.dataset.index);
        if (Number.isNaN(index) || !currentEntries[index]) return;
        if (action !== 'points') return;
        var normalized = String(control.value || '').replace(/[^\d]/g, '');
        var parsed = Number(normalized || 0);
        var totalWithoutCurrent = getWeek35AssignedPoints() - Number(currentEntries[index].points || 0);
        if (parsed + totalWithoutCurrent > WEEK_35_POINTS_BUDGET) {
          parsed = Math.max(0, WEEK_35_POINTS_BUDGET - totalWithoutCurrent);
        }
        currentEntries[index].points = parsed;
        control.value = String(parsed);
        setOrdersScreenCopy();
      });
      control.addEventListener('change', function () {
        if (control.tagName !== 'INPUT') return;
        var action = control.dataset.action;
        var index = Number(control.dataset.index);
        if (Number.isNaN(index) || !currentEntries[index]) return;
        if (action === 'points') {
          return;
        }
        if (action === 'playing_time') {
          currentEntries[index].playing_time = control.checked;
        }
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

  function syncVisitFilterControls() {
    var search = document.getElementById('recruit-search');
    var slider = document.getElementById('rt-min-slider');
    var sliderValue = document.getElementById('rt-min-value');
    var leansOnly = document.getElementById('leans-only-checkbox');
    var picksToggle = document.getElementById('show-only-picks-toggle');
    if (search) search.value = poolFilters.search || '';
    if (slider) slider.value = String(poolFilters.rtMin || 0);
    if (sliderValue) sliderValue.textContent = String(poolFilters.rtMin || 0);
    if (leansOnly) leansOnly.checked = !!poolFilters.leansOnly;
    if (picksToggle) {
      picksToggle.classList.toggle('is-active', showOnlyMine);
      picksToggle.setAttribute('aria-pressed', showOnlyMine ? 'true' : 'false');
    }
    document.querySelectorAll('.region-chip').forEach(function (chip) {
      var region = chip.dataset.region;
      var active = region === 'all' ? !(poolFilters.regions || []).length : (poolFilters.regions || []).indexOf(region) !== -1;
      chip.classList.toggle('is-active', active);
    });
  }

  function bindVisitFilters() {
    var search = document.getElementById('recruit-search');
    var slider = document.getElementById('rt-min-slider');
    var leansOnly = document.getElementById('leans-only-checkbox');
    var picksToggle = document.getElementById('show-only-picks-toggle');
    var fillMoreLink = document.getElementById('fill-more-link');
    document.querySelectorAll('.region-chip').forEach(function (chip) {
      if (chip.dataset.bound === '1') return;
      chip.dataset.bound = '1';
      chip.addEventListener('click', function () {
        var region = chip.dataset.region;
        if (region === 'all') {
          poolFilters.regions = [];
        } else {
          var regions = poolFilters.regions || [];
          if (regions.indexOf(region) === -1) regions.push(region);
          else regions = regions.filter(function (item) { return item !== region; });
          poolFilters.regions = regions;
        }
        saveVisitPreferences();
        syncVisitFilterControls();
        renderRecruitList();
      });
    });
    if (search && search.dataset.bound !== '1') {
      search.dataset.bound = '1';
      search.addEventListener('input', function () {
        poolFilters.search = search.value;
        saveVisitPreferences();
        renderRecruitList();
      });
    }
    if (slider && slider.dataset.bound !== '1') {
      slider.dataset.bound = '1';
      slider.addEventListener('input', function () {
        poolFilters.rtMin = Number(slider.value || 0);
        var sliderValue = document.getElementById('rt-min-value');
        if (sliderValue) sliderValue.textContent = String(poolFilters.rtMin);
        saveVisitPreferences();
        renderRecruitList();
      });
    }
    if (leansOnly && leansOnly.dataset.bound !== '1') {
      leansOnly.dataset.bound = '1';
      leansOnly.addEventListener('change', function () {
        poolFilters.leansOnly = leansOnly.checked;
        saveVisitPreferences();
        renderRecruitList();
      });
    }
    if (picksToggle && picksToggle.dataset.bound !== '1') {
      picksToggle.dataset.bound = '1';
      picksToggle.addEventListener('click', function () {
        showOnlyMine = !showOnlyMine;
        saveVisitPreferences();
        syncVisitFilterControls();
        renderRecruitList();
      });
    }
    if (fillMoreLink && fillMoreLink.dataset.bound !== '1') {
      fillMoreLink.dataset.bound = '1';
      fillMoreLink.addEventListener('click', scrollToPoolAndFocusSearch);
    }
    syncVisitFilterControls();
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

  function buildSavePayload() {
    var payload = { franchise_id: context.franchiseId };
    if (isWeek35Mode()) {
      payload.order_entries = currentEntries.map(function (entry) {
        return {
          id: entry.id,
          points: Number(entry.points || 0),
          scholarship: false,
          playing_time: !!entry.playing_time
        };
      });
    } else {
      payload.recruit_ids = currentEntries.map(function (entry) { return entry.id; });
    }
    return payload;
  }

  function saveOrders(onSuccess) {
    var saveBtn = document.getElementById('save-btn');
    if (!currentEntries.length) return Promise.resolve(null);
    saveBtn.disabled = true;
    saveBtn.textContent = isWeek35Mode() ? 'Saving...' : 'Submitting...';

    return Recruiting.fetchJSON(API_CONFIG.buildUrl('/franchise/recruiting-orders'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(buildSavePayload())
    }).then(function (response) {
      savedEntries = cloneEntries(currentEntries);
      updateActionButtons();
      saveBtn.textContent = 'Save Orders';
      if (onSuccess) onSuccess(response);
      return response;
    }).catch(function (err) {
      console.error(err);
      saveBtn.textContent = 'Save Orders';
      updateActionButtons();
      throw err;
    });
  }

  function handleSaveClick() {
    if (!currentEntries.length) return;
    Recruiting.playSound('confirm-2-lowervol.wav');
    saveOrders(function () {
      var subtitle = isWeek35Mode()
        ? 'Recruiting orders are saved. You can now run recruiting.'
        : 'Recruiting orders are saved.';
      showToast('Orders Saved', subtitle);
      window.setTimeout(function () {
        navigateAway(resolveBackUrl());
      }, 400);
    }).catch(function () {
      showModal({
        title: 'Save Failed',
        message: 'Unable to save recruiting orders.',
        actions: [{ label: 'Close', variant: 'secondary' }]
      });
    });
  }

  function handleRunClick() {
    if (!savedEntries.length && !currentEntries.length) {
      showModal({
        title: 'Save Orders First',
        message: 'You must save recruiting orders before you can run recruiting.',
        actions: [{ label: 'Close', variant: 'secondary' }]
      });
      return;
    }

    var proceed = function () {
      var runBtn = document.getElementById('run-btn');
      runBtn.disabled = true;
      runBtn.textContent = 'Running...';
      Recruiting.fetchJSON(API_CONFIG.buildUrl('/franchise/run-week-35-recruiting'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ franchise_id: context.franchiseId })
      }).then(function () {
        navigateAway(Recruiting.buildRecruitingUrl('recruiting.html', context, { from: 'fcc' }));
      }).catch(function (err) {
        console.error(err);
        runBtn.textContent = 'Run Recruiting';
        updateActionButtons();
        showModal({
          title: 'Run Failed',
          message: 'Unable to run recruiting.',
          actions: [{ label: 'Close', variant: 'secondary' }]
        });
      });
    };

    if (hasUnsavedChanges()) {
      saveOrders(proceed).catch(function () {
        showModal({
          title: 'Save Failed',
          message: 'Unable to save recruiting orders before running recruiting.',
          actions: [{ label: 'Close', variant: 'secondary' }]
        });
      });
      return;
    }
    proceed();
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

  function getWeek35AutofillEntries(userTeamId) {
    return Recruiting.sortRecruits(
      recruits.filter(function (recruit) {
        var lean = recruit.lean || {};
        return lean['1'] === userTeamId || lean['2'] === userTeamId || lean['3'] === userTeamId;
      }),
      { key: 'rt', direction: 'desc' }
    ).slice(0, MAX_RECRUITING_ORDER_SLOTS).map(function (recruit) {
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

  function getSavedWeek35Entries(savedOrderEntries) {
    return (savedOrderEntries || []).map(function (entry) {
      return {
        id: entry.id,
        points: Number(entry.points || 0),
        scholarship: false,
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

    document.getElementById('save-btn').addEventListener('click', handleSaveClick);
    var runBtn = document.getElementById('run-btn');
    if (runBtn) runBtn.addEventListener('click', handleRunClick);
    initNavigationGuards();

    Recruiting.fetchJSON(API_CONFIG.buildUrl('/franchise/recruiting-data') + '?franchise_id=' + encodeURIComponent(context.franchiseId))
      .then(function (data) {
        activeWeek = Number(data.week || 1);
        if (activeWeek === 36) {
          navigateAway(Recruiting.buildRecruitingUrl('recruiting.html', context, { from: 'fcc' }));
          return;
        }
        if (Number(data.current_results_week || 0) === activeWeek && activeWeek >= 20 && activeWeek <= 26) {
          navigateAway(Recruiting.buildRecruitingUrl('recruiting-results.html', context, { week: String(activeWeek) }));
          return;
        }

        mode = activeWeek === 35 ? 'week35' : 'visits';
        userTeamId = data.team_id || context.teamId || '';
        availableRosterSpots = Number(data.available_roster_spots || 0);
        recruits = Recruiting.normalizeRecruits(data.recruits || [], data.team_name_map || {});
        if (!isWeek35Mode()) loadVisitPreferences();
        recruitMap = {};
        recruits.forEach(function (recruit) {
          recruitMap[recruit.recruitId] = recruit;
        });

        buildTopGridHead();
        setOrdersScreenCopy();

        if (isWeek35Mode()) {
          currentEntries = getSavedWeek35Entries(data.saved_order_entries_week_35);
          if (!currentEntries.length) {
            currentEntries = getWeek35AutofillEntries(data.team_id);
          }
        } else {
          currentEntries = getSavedVisitEntries(data.saved_orders);
        }
        savedEntries = cloneEntries(currentEntries);

        Recruiting.bindSortableHeaders(
          document.getElementById('recruits-table'),
          sortState,
          function () {
            if (!isWeek35Mode()) saveVisitPreferences();
            renderRecruitList();
          }
        );
        if (!isWeek35Mode()) bindVisitFilters();
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
