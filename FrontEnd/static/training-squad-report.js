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

(function () {
  'use strict';

  var urlParams = liveParams();
  var franchiseId = urlParams.get('franchise_id');
  var teamId = urlParams.get('team_id');
  // Default to the changes view, mirroring the training report.
  // The twelve visible attributes. CH is hidden: never a column, and the server does not send it.
  var ATTR_KEYS = ['SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'AG', 'ST', 'ND', 'IQ', 'FT'];

  function buildFccUrl() {
    if (typeof resolveFranchiseLockerRoomUrl === 'function') {
      return resolveFranchiseLockerRoomUrl({ params: urlParams, franchiseId: franchiseId, teamId: teamId });
    }
    var p = emptyParams();
    p.set('mode', 'franchise');
    if (franchiseId) p.set('franchise_id', franchiseId);
    if (teamId) p.set('team_id', teamId);
    return '/franchise-command-center.html?' + p.toString();
  }

  // The twelve attributes read as six pairs, in the roster's order (Styleguide, Tables).
  // Presentation only: values are read by key, so the server's key order is not relied on.
  var PAIR_ORDER = ['SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'ST', 'AG', 'ND', 'IQ', 'FT'];

  /** The pair attributes the server sent, in pair order. Nothing else is ever a column:
   *  CH is a hidden attribute (UX_System, "CH is hidden"), whatever a payload carries. */
  function orderKeys(keys) {
    var list = keys || [];
    return PAIR_ORDER.filter(function (key) { return list.indexOf(key) !== -1; });
  }

  /** `gstart` opens a pair and `gend` closes it; an attribute outside the pairs stands alone. */
  function pairClass(key) {
    var at = PAIR_ORDER.indexOf(key);
    if (at === -1) return 'gsolo';
    return at % 2 ? 'gend' : 'gstart';
  }

  /** One attribute cell: the text in a fixed-width box, so a label sits over its values. */
  function attrCell(key, text, tone) {
    var td = document.createElement('td');
    td.className = pairClass(key) + (tone ? ' ' + tone : '');
    var box = document.createElement('span');
    box.className = 'ak';
    box.textContent = text;
    td.appendChild(box);
    return td;
  }

  function changeCell(key, delta) {
    if (delta > 0) return attrCell(key, '+' + delta, 'tsr-up');
    if (delta < 0) return attrCell(key, String(delta), 'tsr-down');
    return attrCell(key, '0', 'tsr-zero');
  }

  function cell(text, cls) {
    var td = document.createElement('td');
    td.textContent = text;
    if (cls) td.className = cls;
    return td;
  }

  function renderReport(report, serverKeys) {
    var attrKeys = orderKeys(serverKeys);
    var wrap = document.createElement('section');
    wrap.className = 'tsr-report';

    var head = document.createElement('div');
    head.className = 'tsr-report-head';
    var title = document.createElement('h2');
    title.className = 'tsr-report-title';
    title.textContent = 'Week #' + report.week + ' Practice Squad Development';
    head.appendChild(title);

    var toggle = document.createElement('div');
    toggle.className = 'tsr-toggle';
    var changesBtn = document.createElement('button');
    changesBtn.className = 'toggle-btn active';
    changesBtn.textContent = 'Changes';
    var absBtn = document.createElement('button');
    absBtn.className = 'toggle-btn';
    absBtn.textContent = 'Absolute';
    toggle.appendChild(changesBtn);
    toggle.appendChild(absBtn);
    head.appendChild(toggle);
    wrap.appendChild(head);

    var table = document.createElement('table');
    table.className = 'tsr-table';
    var thead = document.createElement('thead');
    var hr = document.createElement('tr');
    hr.appendChild(cell('Name'));
    hr.appendChild(cell('POS', 'tsr-lead'));
    attrKeys.forEach(function (k) { hr.appendChild(attrCell(k, k)); });
    thead.appendChild(hr);
    table.appendChild(thead);
    var tbody = document.createElement('tbody');
    table.appendChild(tbody);
    wrap.appendChild(table);

    function render(view) {
      tbody.innerHTML = '';
      (report.players || []).forEach(function (p) {
        var tr = document.createElement('tr');
        tr.appendChild(cell(p.name || p.player_id));
        tr.appendChild(cell(p.pos || '--', 'tsr-pos tsr-lead'));
        var baseline = p.baseline || {};
        var current = p.current || {};
        attrKeys.forEach(function (k) {
          var cur = Number(current[k]);
          var base = Number(baseline[k]);
          if (view === 'absolute') {
            tr.appendChild(attrCell(k, isFinite(cur) ? String(cur) : '--'));
          } else {
            var delta = (isFinite(cur) ? cur : 0) - (isFinite(base) ? base : 0);
            tr.appendChild(changeCell(k, delta));
          }
        });
        tbody.appendChild(tr);
      });
    }

    changesBtn.addEventListener('click', function () {
      changesBtn.classList.add('active'); absBtn.classList.remove('active'); render('changes');
    });
    absBtn.addEventListener('click', function () {
      absBtn.classList.add('active'); changesBtn.classList.remove('active'); render('absolute');
    });
    render('changes');
    return wrap;
  }

  function load() {
    var container = document.getElementById('tsr-reports');
    fetch(API_CONFIG.buildUrl('/franchise/training-squad-reports') + '?franchise_id=' + encodeURIComponent(franchiseId), { headers: API_CONFIG.getAuthHeaders() })
      .then(function (res) { return res.ok ? res.json() : { reports: [] }; })
      .then(function (data) {
        var reports = (data && data.reports) || [];
        var attrKeys = (data && data.attr_keys) || ATTR_KEYS;
        if (!reports.length) {
          var p = document.createElement('p');
          p.className = 'tsr-empty';
          p.textContent = 'No Practice Squad development reports yet. The first one publishes after your Week 6 game.';
          container.appendChild(p);
          return;
        }
        // Newest first (server already sorts desc); stack with separators.
        reports.forEach(function (report) {
          container.appendChild(renderReport(report, attrKeys));
        });
      })
      .catch(function (err) {
        console.error(err);
        var p = document.createElement('p');
        p.className = 'tsr-empty';
        p.textContent = 'Unable to load Practice Squad development reports.';
        container.appendChild(p);
      });
  }

  document.addEventListener('DOMContentLoaded', function () {
    var back = document.getElementById('back-btn');
    if (back) back.addEventListener('click', function (e) {
      e.preventDefault();
      var url = buildFccUrl();
      if (window.GOBNav) window.GOBNav.back(url);
      else window.location.replace(url);
    });
    if (!franchiseId) {
      document.getElementById('tsr-reports').innerHTML = '<p class="tsr-empty">Missing franchise.</p>';
      return;
    }
    load();
  });
})();
