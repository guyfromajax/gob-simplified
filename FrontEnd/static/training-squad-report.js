(function () {
  'use strict';

  var urlParams = new URLSearchParams(window.location.search);
  var franchiseId = urlParams.get('franchise_id');
  var teamId = urlParams.get('team_id');
  // Default to the changes view, mirroring the training report.
  var ATTR_KEYS = ['SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'AG', 'ST', 'ND', 'IQ', 'FT', 'CH'];

  function buildFccUrl() {
    if (typeof resolveFranchiseLockerRoomUrl === 'function') {
      return resolveFranchiseLockerRoomUrl({ params: urlParams, franchiseId: franchiseId, teamId: teamId });
    }
    var p = new URLSearchParams();
    p.set('mode', 'franchise');
    if (franchiseId) p.set('franchise_id', franchiseId);
    if (teamId) p.set('team_id', teamId);
    return '/franchise-command-center.html?' + p.toString();
  }

  function changeCell(delta) {
    var td = document.createElement('td');
    if (delta > 0) { td.className = 'tsr-up'; td.textContent = '+' + delta; }
    else if (delta < 0) { td.className = 'tsr-down'; td.textContent = String(delta); }
    else { td.className = 'tsr-zero'; td.textContent = '0'; }
    return td;
  }

  function cell(text, cls) {
    var td = document.createElement('td');
    td.textContent = text;
    if (cls) td.className = cls;
    return td;
  }

  function renderReport(report, attrKeys) {
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
    hr.appendChild(cell('POS'));
    attrKeys.forEach(function (k) { hr.appendChild(cell(k)); });
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
        tr.appendChild(cell(p.pos || '--', 'tsr-pos'));
        var baseline = p.baseline || {};
        var current = p.current || {};
        attrKeys.forEach(function (k) {
          var cur = Number(current[k]);
          var base = Number(baseline[k]);
          if (view === 'absolute') {
            tr.appendChild(cell(isFinite(cur) ? String(cur) : '--'));
          } else {
            var delta = (isFinite(cur) ? cur : 0) - (isFinite(base) ? base : 0);
            tr.appendChild(changeCell(delta));
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
    if (back) back.addEventListener('click', function () { window.location.href = buildFccUrl(); });
    if (!franchiseId) {
      document.getElementById('tsr-reports').innerHTML = '<p class="tsr-empty">Missing franchise.</p>';
      return;
    }
    load();
  });
})();
