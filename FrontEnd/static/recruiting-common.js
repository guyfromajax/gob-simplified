(function (global) {
  'use strict';

  var ATTR_KEYS = ['SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'AG', 'ST', 'ND', 'IQ', 'FT'];

  function recruitRtClass(rt) {
    return typeof global.getRecruitRtBucketClass === 'function' ? global.getRecruitRtBucketClass(rt) : '';
  }

  function fetchJSON(url, options) {
    options = options || {};
    var headers = Object.assign({}, global.API_CONFIG ? API_CONFIG.getAuthHeaders() : {}, options.headers || {});
    return fetch(url, Object.assign({}, options, { headers: headers })).then(function (res) {
      if (!res.ok) {
        return res.text().then(function (text) {
          throw new Error(text || 'Request failed');
        });
      }
      return res.json();
    });
  }

  function playSound(filename) {
    try {
      var base = (global.API_CONFIG && API_CONFIG.buildStaticPath) ? API_CONFIG.buildStaticPath('/sounds/') : '/sounds/';
      var audio = new Audio(base + encodeURIComponent(filename));
      audio.volume = 0.7;
      audio.play().catch(function () {});
    } catch (e) {}
  }

  function getQueryContext() {
    var params = new URLSearchParams(global.location.search);
    return {
      franchiseId: params.get('franchise_id'),
      teamId: params.get('team_id'),
      from: params.get('from') || 'fcc',
      returnUrl: params.get('return_url'),
    };
  }

  function buildFccUrl(context) {
    if (global.resolveFranchiseLockerRoomUrl) {
      return global.resolveFranchiseLockerRoomUrl({
        returnUrl: context.returnUrl,
        franchiseId: context.franchiseId,
        teamId: context.teamId
      });
    }
    var params = new URLSearchParams();
    params.set('mode', 'franchise');
    if (context.franchiseId) params.set('franchise_id', context.franchiseId);
    if (context.teamId) params.set('team_id', context.teamId);
    return '/franchise-command-center.html?' + params.toString();
  }

  function buildRecruitingUrl(page, context, extraParams) {
    var params = new URLSearchParams();
    if (context.franchiseId) params.set('franchise_id', context.franchiseId);
    if (context.teamId) params.set('team_id', context.teamId);
    if (context.from) params.set('from', context.from);
    if (context.returnUrl) params.set('return_url', context.returnUrl);
    Object.keys(extraParams || {}).forEach(function (key) {
      if (extraParams[key] != null) params.set(key, extraParams[key]);
    });
    return '/' + page + '?' + params.toString();
  }

  function formatAttrValue(value) {
    return Math.floor((Number(value) || 0) / 10);
  }

  function getLeanDisplay(lean, teamNameMap) {
    var parts = [];
    ['1', '2', '3'].forEach(function (key) {
      var value = lean && lean[key];
      if (!value) return;
      if (value === 'open') {
        parts.push('open');
        return;
      }
      parts.push(teamNameMap[value] || value);
    });
    return parts.join(', ');
  }

  function getLeanSortValue(lean, teamNameMap) {
    var first = lean && lean['1'];
    if (!first) return '';
    if (first === 'open') return 'open';
    return teamNameMap[first] || first;
  }

  function normalizeRecruits(recruits, teamNameMap) {
    return (recruits || []).map(function (recruit) {
      var best = getBestPosition(recruit.position_ratings || {});
      var lean = recruit.Lean || {};
      var attrs = recruit.attributes || {};
      var normalizedAttrs = {};
      ATTR_KEYS.forEach(function (key) {
        normalizedAttrs[key] = formatAttrValue(attrs[key]);
      });
      return {
        recruitId: recruit.recruit_id,
        name: recruit.name || '--',
        homeRegion: recruit['Home Region'] || '--',
        archetype: recruit.archetype || '--',
        height: formatHeight(recruit.height),
        heightRaw: Number(recruit.height) || 0,
        weight: recruit.weight != null ? Number(recruit.weight) : null,
        pos: best.pos || '--',
        rt: best.rating != null ? Number(best.rating) : null,
        lean: lean,
        leanDisplay: getLeanDisplay(lean, teamNameMap),
        leanSortValue: getLeanSortValue(lean, teamNameMap),
        attrs: normalizedAttrs,
        raw: recruit,
      };
    });
  }

  function compareValues(a, b, direction) {
    if (typeof a === 'number' && typeof b === 'number') {
      return direction === 'asc' ? a - b : b - a;
    }
    var aStr = (a == null ? '' : String(a)).toLowerCase();
    var bStr = (b == null ? '' : String(b)).toLowerCase();
    if (aStr === bStr) return 0;
    if (direction === 'asc') return aStr < bStr ? -1 : 1;
    return aStr > bStr ? -1 : 1;
  }

  function getSortValue(recruit, key) {
    if (ATTR_KEYS.indexOf(key) !== -1) return recruit.attrs[key];
    switch (key) {
      case 'homeRegion': return recruit.homeRegion;
      case 'archetype': return recruit.archetype;
      case 'height': return recruit.heightRaw;
      case 'weight': return recruit.weight != null ? recruit.weight : -1;
      case 'pos': return recruit.pos;
      case 'rt': return recruit.rt != null ? recruit.rt : -1;
      case 'lean': return recruit.leanSortValue;
      default: return recruit[key];
    }
  }

  function sortRecruits(recruits, sortState) {
    var key = sortState && sortState.key ? sortState.key : 'rt';
    var direction = sortState && sortState.direction ? sortState.direction : 'desc';
    return recruits.slice().sort(function (a, b) {
      var primary = compareValues(getSortValue(a, key), getSortValue(b, key), direction);
      if (primary !== 0) return primary;
      return compareValues(a.rt != null ? a.rt : -1, b.rt != null ? b.rt : -1, 'desc');
    });
  }

  function toggleSort(sortState, key) {
    if (sortState.key !== key) {
      sortState.key = key;
      sortState.direction = 'desc';
      return sortState;
    }
    sortState.direction = sortState.direction === 'desc' ? 'asc' : 'desc';
    return sortState;
  }

  function applySortIndicators(table, sortState) {
    if (!table) return;
    table.querySelectorAll('th[data-sort-key]').forEach(function (th) {
      var active = th.dataset.sortKey === sortState.key;
      th.classList.toggle('sorted', active);
      th.classList.toggle('sorted-asc', active && sortState.direction === 'asc');
      th.classList.toggle('sorted-desc', active && sortState.direction === 'desc');
    });
  }

  function bindSortableHeaders(table, sortState, onSortChange) {
    if (!table) return;
    table.querySelectorAll('th[data-sort-key]').forEach(function (th) {
      if (th.dataset.bound === '1') return;
      th.dataset.bound = '1';
      th.addEventListener('click', function () {
        toggleSort(sortState, th.dataset.sortKey);
        applySortIndicators(table, sortState);
        onSortChange();
      });
    });
    applySortIndicators(table, sortState);
  }

  function renderRecruitTableRows(tbody, recruits, options) {
    if (!tbody) return;
    var selectedIds = options && options.selectedIds ? options.selectedIds : new Set();
    var onRowClick = options && options.onRowClick;
    var onActionClick = options && options.onActionClick;
    var getActionLabel = options && options.getActionLabel;
    tbody.innerHTML = '';

    recruits.forEach(function (recruit) {
      var tr = document.createElement('tr');
      tr.dataset.recruitId = recruit.recruitId;
      if (selectedIds.has(recruit.recruitId)) tr.classList.add('recruit-selected');
      if (onRowClick) tr.classList.add('recruit-clickable');
      tr.innerHTML = [
        '<td>' + recruit.name + '</td>',
        '<td>' + recruit.homeRegion + '</td>',
        '<td>' + recruit.archetype + '</td>',
        '<td>' + recruit.height + '</td>',
        '<td>' + (recruit.weight != null ? recruit.weight : '--') + '</td>',
        '<td>' + recruit.pos + '</td>',
        '<td>' + recruit.attrs.SC + '</td>',
        '<td>' + recruit.attrs.SH + '</td>',
        '<td>' + recruit.attrs.ID + '</td>',
        '<td>' + recruit.attrs.OD + '</td>',
        '<td>' + recruit.attrs.PS + '</td>',
        '<td>' + recruit.attrs.BH + '</td>',
        '<td>' + recruit.attrs.RB + '</td>',
        '<td>' + recruit.attrs.AG + '</td>',
        '<td>' + recruit.attrs.ST + '</td>',
        '<td>' + recruit.attrs.ND + '</td>',
        '<td>' + recruit.attrs.IQ + '</td>',
        '<td>' + recruit.attrs.FT + '</td>',
        '<td class="' + recruitRtClass(recruit.rt) + '">' + (recruit.rt != null ? recruit.rt : '--') + '</td>',
        '<td>' + (recruit.leanDisplay || '--') + '</td>',
        onActionClick ? '<td><button class="recruiting-row-action-btn" type="button">' + (getActionLabel ? getActionLabel(recruit, selectedIds.has(recruit.recruitId)) : '+') + '</button></td>' : ''
      ].join('');
      if (onActionClick) {
        tr.querySelector('.recruiting-row-action-btn').addEventListener('click', function (e) {
          e.stopPropagation();
          onActionClick(recruit);
        });
      }
      if (onRowClick) {
        tr.addEventListener('click', function () {
          onRowClick(recruit);
        });
      }
      tbody.appendChild(tr);
    });

    if (typeof global.initAttributeTooltips === 'function') {
      global.initAttributeTooltips(tbody, ['td']);
    }
  }

  function recruitingOrderIds(savedOrders) {
    return Object.keys(savedOrders || {})
      .sort(function (a, b) { return Number(a) - Number(b); })
      .map(function (key) { return savedOrders[key]; })
      .filter(Boolean);
  }

  function arraysEqual(a, b) {
    if ((a || []).length !== (b || []).length) return false;
    for (var i = 0; i < (a || []).length; i += 1) {
      if (a[i] !== b[i]) return false;
    }
    return true;
  }

  global.RecruitingCommon = {
    ATTR_KEYS: ATTR_KEYS,
    arraysEqual: arraysEqual,
    bindSortableHeaders: bindSortableHeaders,
    buildFccUrl: buildFccUrl,
    buildRecruitingUrl: buildRecruitingUrl,
    fetchJSON: fetchJSON,
    getQueryContext: getQueryContext,
    normalizeRecruits: normalizeRecruits,
    playSound: playSound,
    recruitRtClass: recruitRtClass,
    recruitingOrderIds: recruitingOrderIds,
    renderRecruitTableRows: renderRecruitTableRows,
    sortRecruits: sortRecruits,
  };
})(window);
