(function () {
  'use strict';

  var Recruiting = window.RecruitingCommon;
  var context = Recruiting.getQueryContext();
  var sortState = { key: 'rt', direction: 'desc' };
  var recruits = [];
  var signedMap = {};
  var walkOns = [];
  var week = 1;

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

  function getWeek36SortValue(row, key) {
    if (Recruiting.ATTR_KEYS.indexOf(key) !== -1) return row.attrs[key];
    switch (key) {
      case 'name': return row.name;
      case 'homeRegion': return row.homeRegion;
      case 'archetype': return row.archetype;
      case 'height': return row.heightRaw;
      case 'weight': return row.weight != null ? row.weight : -1;
      case 'pos': return row.pos;
      case 'rt': return row.rt != null ? row.rt : -1;
      case 'signed': return row.signedDisplay === '--' ? '' : row.signedDisplay;
      default: return row[key];
    }
  }

  function sortWeek36Rows(rows) {
    var key = sortState && sortState.key ? sortState.key : 'rt';
    var direction = sortState && sortState.direction ? sortState.direction : 'desc';
    return rows.slice().sort(function (a, b) {
      var primary = compareValues(getWeek36SortValue(a, key), getWeek36SortValue(b, key), direction);
      if (primary !== 0) return primary;
      return compareValues(a.rt != null ? a.rt : -1, b.rt != null ? b.rt : -1, 'desc');
    });
  }

  function renderStandardRows() {
    Recruiting.renderRecruitTableRows(
      document.getElementById('recruiting-body'),
      Recruiting.sortRecruits(recruits, sortState)
    );
  }

  function renderWeek36Rows() {
    var tbody = document.getElementById('recruiting-body');
    var rows = recruits.map(function (recruit) {
      var signedInfo = signedMap[recruit.recruitId];
      return {
        name: recruit.name,
        homeRegion: recruit.homeRegion,
        archetype: recruit.archetype,
        height: recruit.height,
        weight: recruit.weight,
        pos: recruit.pos,
        attrs: recruit.attrs,
        rt: recruit.rt,
        heightRaw: recruit.heightRaw,
        signedDisplay: signedInfo ? signedInfo.team_name + (signedInfo.walk_on ? ' (walk on)' : '') : '--'
      };
    }).concat(walkOns);
    rows = sortWeek36Rows(rows);

    tbody.innerHTML = '';
    rows.forEach(function (row) {
      var tr = document.createElement('tr');
      tr.innerHTML = [
        '<td>' + row.name + '</td>',
        '<td>' + (row.homeRegion || '--') + '</td>',
        '<td>' + (row.archetype || '--') + '</td>',
        '<td>' + (row.height || '--') + '</td>',
        '<td>' + (row.weight != null ? row.weight : '--') + '</td>',
        '<td>' + (row.pos || '--') + '</td>',
        '<td>' + row.attrs.SC + '</td>',
        '<td>' + row.attrs.SH + '</td>',
        '<td>' + row.attrs.ID + '</td>',
        '<td>' + row.attrs.OD + '</td>',
        '<td>' + row.attrs.PS + '</td>',
        '<td>' + row.attrs.BH + '</td>',
        '<td>' + row.attrs.RB + '</td>',
        '<td>' + row.attrs.AG + '</td>',
        '<td>' + row.attrs.ST + '</td>',
        '<td>' + row.attrs.ND + '</td>',
        '<td>' + row.attrs.IQ + '</td>',
        '<td>' + row.attrs.FT + '</td>',
        '<td>' + (row.rt != null ? row.rt : '--') + '</td>',
        '<td>' + row.signedDisplay + '</td>'
      ].join('');
      tbody.appendChild(tr);
    });
  }

  function render() {
    if (week === 36) {
      renderWeek36Rows();
      return;
    }
    renderStandardRows();
  }

  function setOrdersButton(data) {
    var btn = document.getElementById('orders-btn');
    if (!btn) return;
    btn.replaceWith(btn.cloneNode(true));
    btn = document.getElementById('orders-btn');
    if (week >= 20 && week <= 26) {
      btn.style.display = 'inline-flex';
      if (Number(data.current_results_week || 0) === week) {
        btn.textContent = 'Week ' + week + ' Recruiting Visits';
        btn.addEventListener('click', function () {
          window.location.href = Recruiting.buildRecruitingUrl('recruiting-results.html', context, { from: 'recruiting', week: String(week) });
        });
      } else {
        btn.textContent = 'Recruiting Orders';
        btn.addEventListener('click', function () {
          window.location.href = Recruiting.buildRecruitingUrl('recruiting-orders.html', context, { from: 'recruiting' });
        });
      }
      return;
    }
    if (week !== 35) {
      btn.style.display = 'none';
      return;
    }
    btn.style.display = 'inline-flex';
    btn.textContent = 'Recruiting Orders';
    btn.addEventListener('click', function () {
      window.location.href = Recruiting.buildRecruitingUrl('recruiting-orders.html', context, { from: 'recruiting' });
    });
  }

  function setHeaders() {
    var title = document.querySelector('.recruiting-section h1');
    var help = document.querySelector('.recruiting-help');
    var lastCol = document.getElementById('recruiting-last-col');
    if (week === 36) {
      title.textContent = 'Recruiting Results';
      help.textContent = 'All recruits are shown below. Signed recruits display their chosen team.';
      lastCol.textContent = 'Signed';
      lastCol.dataset.sortKey = 'signed';
      return;
    }
    title.textContent = 'Recruiting';
    help.textContent = 'Recruits are sorted by top RT by default. Click any sortable header to reorder the table.';
    lastCol.textContent = 'Current Lean';
    lastCol.dataset.sortKey = 'lean';
  }

  function normalizeWalkOns(results) {
    return (results.signed_players || []).filter(function (player) {
      return !!player.walk_on;
    }).map(function (player) {
      return {
        name: player.name,
        homeRegion: '--',
        archetype: 'Walk On',
        height: window.formatHeight ? formatHeight(player.height) : '--',
        heightRaw: Number(player.height) || 0,
        weight: player.weight,
        pos: player.pos || '--',
        attrs: (function () {
          var attrs = player.attributes || {};
          return {
            SC: Math.floor((Number(attrs.SC) || 0) / 10),
            SH: Math.floor((Number(attrs.SH) || 0) / 10),
            ID: Math.floor((Number(attrs.ID) || 0) / 10),
            OD: Math.floor((Number(attrs.OD) || 0) / 10),
            PS: Math.floor((Number(attrs.PS) || 0) / 10),
            BH: Math.floor((Number(attrs.BH) || 0) / 10),
            RB: Math.floor((Number(attrs.RB) || 0) / 10),
            AG: Math.floor((Number(attrs.AG) || 0) / 10),
            ST: Math.floor((Number(attrs.ST) || 0) / 10),
            ND: Math.floor((Number(attrs.ND) || 0) / 10),
            IQ: Math.floor((Number(attrs.IQ) || 0) / 10),
            FT: Math.floor((Number(attrs.FT) || 0) / 10)
          };
        })(),
        rt: player.rt,
        signedDisplay: player.team_name + ' (walk on)'
      };
    });
  }

  function init() {
    if (!context.franchiseId || !context.teamId) {
      document.getElementById('recruiting-body').innerHTML = '<tr><td colspan="20">Missing franchise context.</td></tr>';
      return;
    }

    document.getElementById('back-btn').href = Recruiting.buildFccUrl(context);

    Recruiting.fetchJSON(API_CONFIG.buildUrl('/franchise/recruiting-data') + '?franchise_id=' + encodeURIComponent(context.franchiseId))
      .then(function (data) {
        week = Number(data.week || 1);
        setHeaders();
        recruits = Recruiting.normalizeRecruits(data.recruits || [], data.team_name_map || {});
        if (week === 36) {
          signedMap = (data.week_35_recruiting_results && data.week_35_recruiting_results.signed_by_recruit_id) || {};
          walkOns = normalizeWalkOns(data.week_35_recruiting_results || {});
        }
        Recruiting.bindSortableHeaders(
          document.getElementById('recruiting-table'),
          sortState,
          render
        );
        render();
        setOrdersButton(data);
        if (typeof window.initAttributeTooltips === 'function') {
          window.initAttributeTooltips(document.getElementById('recruiting-table'), ['th']);
        }
      })
      .catch(function (err) {
        console.error(err);
        document.getElementById('recruiting-body').innerHTML = '<tr><td colspan="20">Failed to load recruits.</td></tr>';
      });
  }

  init();
})();
