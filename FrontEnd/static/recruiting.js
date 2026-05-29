(function () {
  'use strict';

  var Recruiting = window.RecruitingCommon;
  var context = Recruiting.getQueryContext();
  var sortState = { key: 'rt', direction: 'desc' };
  var recruits = [];
  var signedMap = {};
  var walkOns = [];
  var week = 1;
  var REGION_ORDER = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'];

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

  function getRowRegion(row) {
    var value = row && row.homeRegion ? String(row.homeRegion).trim().toUpperCase() : '';
    if (!value) return '';
    return value.charAt(0);
  }

  function getGroupedRows() {
    var grouped = {};
    REGION_ORDER.forEach(function (region) { grouped[region] = []; });

    if (week === 36) {
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
      rows.forEach(function (row) {
        var region = getRowRegion(row);
        if (grouped[region]) grouped[region].push(row);
      });
      return grouped;
    }

    Recruiting.sortRecruits(recruits, sortState).forEach(function (row) {
      var region = getRowRegion(row);
      if (grouped[region]) grouped[region].push(row);
    });
    return grouped;
  }

  function buildHeadHtml(lastColLabel, lastColKey) {
    return [
      '<thead><tr>',
      '<th data-sort-key="name">Name</th>',
      '<th data-sort-key="archetype">Archetype</th>',
      '<th data-sort-key="height">HT</th>',
      '<th data-sort-key="weight">WT</th>',
      '<th data-sort-key="pos">POS</th>',
      '<th data-sort-key="SC">SC</th>',
      '<th data-sort-key="SH">SH</th>',
      '<th data-sort-key="ID">ID</th>',
      '<th data-sort-key="OD">OD</th>',
      '<th data-sort-key="PS">PS</th>',
      '<th data-sort-key="BH">BH</th>',
      '<th data-sort-key="RB">RB</th>',
      '<th data-sort-key="AG">AG</th>',
      '<th data-sort-key="ST">ST</th>',
      '<th data-sort-key="ND">ND</th>',
      '<th data-sort-key="IQ">IQ</th>',
      '<th data-sort-key="FT">FT</th>',
      '<th data-sort-key="rt">RT</th>',
      '<th data-sort-key="' + lastColKey + '">' + lastColLabel + '</th>',
      '</tr></thead>'
    ].join('');
  }

  function appendStandardRow(tbody, row, isWeek36) {
    // RT colored per canonical Attribute Bar Scale (see /css/rt-buckets.css).
    var rtClass = typeof window.getRtBucketClass === 'function' ? window.getRtBucketClass(row.rt) : '';
    var rtCell = '<td class="' + rtClass + '">' + (row.rt != null ? row.rt : '--') + '</td>';
    var tr = document.createElement('tr');
    tr.innerHTML = isWeek36 ? [
      '<td>' + row.name + '</td>',
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
      rtCell,
      '<td>' + row.signedDisplay + '</td>'
    ].join('') : [
      '<td>' + row.name + '</td>',
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
      rtCell,
      '<td>' + (row.leanDisplay || '--') + '</td>'
    ].join('');
    tbody.appendChild(tr);
  }

  function buildRegionCard(region, rows, isWeek36) {
    var lastColLabel = isWeek36 ? 'Signed' : 'Current Lean';
    var lastColKey = isWeek36 ? 'signed' : 'lean';
    var emptyMarkup = '<div class="recruiting-region-empty">No recruits in this region.</div>';
    return [
      '<section class="recruiting-region-card">',
      '<div class="recruiting-region-title">Region ' + region + '</div>',
      '<div class="recruiting-region-body">',
      rows.length
        ? '<div class="scroll-x"><table class="roster-table recruiting-table recruiting-region-table">' + buildHeadHtml(lastColLabel, lastColKey) + '<tbody id="recruiting-region-body-' + region + '"></tbody></table></div>'
        : emptyMarkup,
      '</div>',
      '</section>'
    ].join('');
  }

  function render() {
    var host = document.getElementById('recruiting-regions');
    if (!host) return;

    var grouped = getGroupedRows();
    host.innerHTML = REGION_ORDER.map(function (region) {
      return buildRegionCard(region, grouped[region] || [], week === 36);
    }).join('');

    REGION_ORDER.forEach(function (region) {
      var tbody = document.getElementById('recruiting-region-body-' + region);
      if (!tbody) return;
      grouped[region].forEach(function (row) {
        appendStandardRow(tbody, row, week === 36);
      });
      if (typeof window.initAttributeTooltips === 'function') {
        window.initAttributeTooltips(tbody, ['td']);
      }
    });

    host.querySelectorAll('table.recruiting-region-table').forEach(function (table) {
      Recruiting.bindSortableHeaders(table, sortState, render);
    });
    if (typeof window.initAttributeTooltips === 'function') {
      host.querySelectorAll('table.recruiting-region-table').forEach(function (table) {
        window.initAttributeTooltips(table, ['th']);
      });
    }
  }

  function setPageText() {
    var title = document.getElementById('recruiting-page-title');
    var note = document.getElementById('recruiting-status-note');
    if (week === 36) {
      if (title) title.textContent = 'Recruiting Results';
      if (note) note.textContent = 'Signed recruits are grouped below by home region.';
      return;
    }
    if (title) title.textContent = 'Recruiting';
    if (note) note.textContent = 'Recruits are grouped by home region and sorted by RT by default. Click any header to reorder all regions.';
  }

  function init() {
    var host = document.getElementById('recruiting-regions');
    var backBtn = document.getElementById('back-btn');

    if (!context.franchiseId || !context.teamId) {
      if (host) host.innerHTML = '<div class="recruiting-region-empty">Missing franchise context.</div>';
      return;
    }

    if (backBtn) backBtn.href = Recruiting.buildFccUrl(context);

    Recruiting.fetchJSON(API_CONFIG.buildUrl('/franchise/recruiting-data') + '?franchise_id=' + encodeURIComponent(context.franchiseId))
      .then(function (data) {
        week = Number(data.week || 1);
        recruits = Recruiting.normalizeRecruits(data.recruits || [], data.team_name_map || {});
        if (week === 36) {
          signedMap = (data.week_35_recruiting_results && data.week_35_recruiting_results.signed_by_recruit_id) || {};
          walkOns = normalizeWalkOns(data.week_35_recruiting_results || {});
        }
        setPageText();
        render();
      })
      .catch(function (err) {
        console.error(err);
        if (host) host.innerHTML = '<div class="recruiting-region-empty">Failed to load recruits.</div>';
      });
  }

  init();
})();
