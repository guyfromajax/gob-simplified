import { ensureCss, loadScript } from './prepEmbed.js';

var CSS = [
  '/css/gob-browse-templates.css',
  '/css/prep-v2.css',
  '/css/prep-v2-scouting.css',
  '/css/rt-buckets.css'
];

var ATTR_GROUPS = [
  { label: 'Offense', keys: ['SC', 'SH'], gs: true },
  { label: 'Defense', keys: ['ID', 'OD'], gs: true },
  { label: 'Skills', keys: ['PS', 'BH'], gs: true },
  { label: 'Grit', keys: ['RB', 'ST'], gs: true },
  { label: 'Body', keys: ['AG', 'ND'], gs: true },
  { label: 'Mind', keys: ['IQ', 'FT'], gs: true }
];

var MEASURE_ROWS = [
  { key: 'offensive_efficiency', label: 'Offense' },
  { key: 'defensive_efficiency', label: 'Defense' },
  { key: 'fb_efficiency', label: 'Fast Break Offense' },
  { key: 'fb_opp_modifier', label: 'Fast Break Defense' },
  { key: 'pt_efficiency', label: 'Press/Trap Defense' },
  { key: 'pt_opp_modifier', label: 'Press Break' },
  { key: 'discipline', label: 'Discipline' },
  { key: 'fight', label: 'Fight' }
];

var HEADER_MEASURE_KEYS = ['shot_threshold', 'rebound_modifier', 'team_chemistry'];

function esc(v) {
  return String(v == null ? '' : v)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function franchiseIdFrom(ctx) {
  if (ctx && ctx.franchiseId) return ctx.franchiseId;
  try { return new URLSearchParams(window.location.search).get('franchise_id') || ''; }
  catch (err) { return ''; }
}

function userTeamIdFrom(ctx) {
  if (ctx && ctx.teamId) return ctx.teamId;
  if (window.GOBViews && typeof window.GOBViews.userTeamId === 'function') {
    return window.GOBViews.userTeamId() || '';
  }
  return '';
}

function ordinal(rank) {
  var n = Math.round(Number(rank));
  if (!isFinite(n) || n <= 0) return '';
  var mod100 = n % 100;
  var suffix = 'th';
  if (mod100 < 11 || mod100 > 13) {
    if (n % 10 === 1) suffix = 'st';
    else if (n % 10 === 2) suffix = 'nd';
    else if (n % 10 === 3) suffix = 'rd';
  }
  return n + suffix;
}

function placeText(row) {
  if (!row || row.rank == null || row.rank === '' || row.rank_of == null || row.rank_of === '') return '—';
  return ordinal(row.rank) + ' of ' + row.rank_of;
}

function formatMeasureValue(value) {
  var n = Number(value);
  if (!isFinite(n)) return '0';
  var rounded = Math.round(n);
  if (Math.abs(n - rounded) < 1e-6) {
    return (rounded > 0 ? '+' : '') + String(rounded);
  }
  return (n > 0 ? '+' : '') + n.toFixed(1);
}

function adTierClass(displayVal) {
  var ad = window.GOB_AttributeDisplay;
  if (!ad || displayVal == null) return '';
  var tier = ad.attrTier(displayVal);
  if (tier === 'elite') return 't-blue';
  if (tier === 'high') return 't-green';
  if (tier === 'mid') return 't-yellow';
  if (tier === 'low') return 't-red';
  return '';
}

function attrTile(key, attrs) {
  var ad = window.GOB_AttributeDisplay;
  var raw = ad ? ad.rawAttr(attrs, key) : null;
  var display = ad ? ad.displayAttr(raw) : null;
  var text = display == null ? '—' : String(display);
  return '<span class="ad ' + adTierClass(display) + '">' + esc(text) + '</span>';
}

function rtLockupHtml(rt, potentialRt) {
  var curCls = typeof window.getRtBucketClass === 'function' ? window.getRtBucketClass(rt) : '';
  var cur = typeof window.formatRtDisplay === 'function' ? window.formatRtDisplay(rt) : (rt == null ? '—' : String(rt));
  var map = { 'rt-a': 't-blue', 'rt-b': 't-green', 'rt-c': 't-yellow', 'rt-d': 't-red', 'rt-f': 't-red' };
  var curTone = map[curCls] || '';
  var html = '<span class="rtl"><b class="' + esc(curTone) + '">' + esc(cur) + '</b><i>→</i>';
  if (potentialRt != null && potentialRt !== '') {
    var pCls = typeof window.getRtBucketClass === 'function' ? window.getRtBucketClass(potentialRt) : '';
    var pot = typeof window.formatRtDisplay === 'function' ? window.formatRtDisplay(potentialRt) : String(potentialRt);
    html += '<b class="pot ' + esc(map[pCls] || '') + '">' + esc(pot) + '</b>';
  } else {
    html += '<b class="pot">' + esc(cur) + '</b>';
  }
  return html + '</span>';
}

function yearLabel(year) {
  if (window.GOB_PlayerYear && typeof window.GOB_PlayerYear.formatDisplay === 'function') {
    return window.GOB_PlayerYear.formatDisplay(year);
  }
  return year != null && year !== '' ? String(year).toUpperCase() : '—';
}

function playerPortraitHtml(row) {
  var name = row.name || '—';
  var initials = name.trim().split(/\s+/).filter(Boolean);
  var mono = initials.length >= 2
    ? (initials[0].charAt(0) + initials[initials.length - 1].charAt(0)).toUpperCase()
    : (initials[0] || '?').slice(0, 2).toUpperCase();
  var pid = row.player_id != null ? String(row.player_id) : '';
  var imageId = row.image_id != null ? String(row.image_id) : '';
  var isRecruit = row.portrait_source === 'recruit' && imageId;
  var src = '';
  if (isRecruit && window.API_CONFIG && typeof window.API_CONFIG.getRecruitImageUrl === 'function') {
    src = window.API_CONFIG.getRecruitImageUrl(imageId, { size: 'card' });
  } else if (pid && window.API_CONFIG && typeof window.API_CONFIG.getPlayerImageUrl === 'function') {
    src = window.API_CONFIG.getPlayerImageUrl(pid, { size: 'card' });
  }
  if (src) {
    return '<span class="av"><img src="' + esc(src) + '" alt="" loading="lazy" width="28" height="28"></span>';
  }
  return '<span class="av">' + esc(mono) + '</span>';
}

function agridHead(mode) {
  if (mode === 'stats') {
    var cols = (window.SCOUTING_PROJECTED_STATS_COLUMNS || []);
    var h = '<thead><tr class="g">';
    h += '<th rowspan="2" class="l pl-h">Player</th>';
    h += '<th rowspan="2" class="c">Pos</th>';
    cols.forEach(function (c) {
      h += '<th class="aa">' + esc(c) + '</th>';
    });
    return h + '</tr></thead>';
  }
  var html = '<thead><tr class="g">';
  html += '<th rowspan="2" class="l pl-h">Player</th>';
  html += '<th rowspan="2" class="c">RT<span class="cap">cur → pot</span></th>';
  html += '<th rowspan="2" class="c">Pos</th>';
  html += '<th rowspan="2" class="c">Yr</th>';
  ATTR_GROUPS.forEach(function (g) {
    html += '<th colspan="2" class="ag gs">' + esc(g.label) + '</th>';
  });
  html += '</tr><tr>';
  ATTR_GROUPS.forEach(function (g) {
    g.keys.forEach(function (key, idx) {
      html += '<th class="aa' + (idx === 0 ? ' gs' : '') + '" title="' + esc(key) + '">' + esc(key) + '</th>';
    });
  });
  return html + '</tr></thead>';
}

function agridBodyAttributes(rows) {
  var body = '<tbody>';
  (rows || []).forEach(function (r) {
    body += '<tr><td class="l pcol"><span class="pc">';
    body += playerPortraitHtml(r);
    body += '<span class="jn">' + esc(r.jersey == null ? '' : r.jersey) + '</span>';
    body += '<a class="nm">' + esc(r.name || '—') + '</a></span></td>';
    body += '<td class="c">' + rtLockupHtml(r.rt, r.potential_rt_ratcheted) + '</td>';
    body += '<td class="c"><span class="pos">' + esc(r.position || '—') + '</span></td>';
    body += '<td class="c dim">' + esc(yearLabel(r.year)) + '</td>';
    ATTR_GROUPS.forEach(function (g) {
      g.keys.forEach(function (key, idx) {
        var gb = idx === 0 ? ' gs gb' : ' gb';
        body += '<td class="a' + gb + '">' + attrTile(key, r.attributes || {}) + '</td>';
      });
    });
    body += '</tr>';
  });
  return body + '</tbody>';
}

function agridBodyStats(rows, statsByPlayer) {
  var cols = window.SCOUTING_PROJECTED_STATS_COLUMNS || [];
  var fmt = typeof window.formatScoutingSeasonStat === 'function'
    ? window.formatScoutingSeasonStat
    : function (stats, col) { return stats && stats[col] != null ? String(stats[col]) : '0'; };
  var map = statsByPlayer && typeof statsByPlayer === 'object' ? statsByPlayer : {};
  var body = '<tbody>';
  (rows || []).forEach(function (r) {
    var pid = r.player_id != null ? String(r.player_id) : '';
    var stats = map[pid] || {};
    body += '<tr><td class="l pcol"><span class="pc">';
    body += playerPortraitHtml(r);
    body += '<span class="jn">' + esc(r.jersey == null ? '' : r.jersey) + '</span>';
    body += '<a class="nm">' + esc(r.name || '—') + '</a></span></td>';
    body += '<td class="c"><span class="pos">' + esc(r.position || '—') + '</span></td>';
    cols.forEach(function (col) {
      body += '<td class="num">' + esc(fmt(stats, col)) + '</td>';
    });
    body += '</tr>';
  });
  return body + '</tbody>';
}

function measuresByKey(measures) {
  var out = Object.create(null);
  (measures || []).forEach(function (row) {
    if (row && row.key) out[row.key] = row;
  });
  return out;
}

function renderHeaderRanks(host, measures) {
  var byKey = measuresByKey(measures);
  var html = '';
  HEADER_MEASURE_KEYS.forEach(function (key) {
    var row = byKey[key] || {};
    var label = row.label || key;
    var pct = row.percentile != null && row.percentile !== '' ? Number(row.percentile) : 0;
    var chem = '';
    if (key === 'team_chemistry' && row.value != null && row.scale_max != null) {
      chem = '<span class="meta">' + esc(row.value) + '/' + esc(row.scale_max) + '</span>';
    }
    html += '<div class="opp-rank-row"><span class="lbl">' + esc(label) + '</span>'
      + '<span class="place">' + esc(placeText(row)) + '</span>'
      + chem
      + '<span class="gob-meter' + (row.rank != null ? '' : ' is-empty') + '"><i style="--w:' + pct + '%"></i></span></div>';
  });
  host.innerHTML = html;
}

function renderMeasureRows(host, teamAttrs) {
  var attrs = teamAttrs || {};
  function column(specs) {
    var html = '';
    specs.forEach(function (spec) {
      var val = Number(attrs[spec.key]);
      if (!isFinite(val)) val = 0;
      var clamped = Math.max(-20, Math.min(20, val));
      var mag = Math.abs(clamped) / 20;
      var neg = clamped < 0 ? ' neg' : '';
      html += '<div class="ms"><span>' + esc(spec.label) + '</span><b>' + esc(formatMeasureValue(val))
        + '</b><span class="dv' + neg + '" style="--v:' + mag + '"><i></i></span></div>';
    });
    return html;
  }
  host.innerHTML = '<div class="cols2"><div>' + column(MEASURE_ROWS.slice(0, 4)) + '</div><div>'
    + column(MEASURE_ROWS.slice(4)) + '</div></div>';
}

function renderUsageTable(tbodyId, plays, emptyMessage) {
  var tbody = document.getElementById(tbodyId);
  if (!tbody) return;
  if (typeof window.renderPlayUsage === 'function') {
    window.renderPlayUsage(plays, emptyMessage, tbodyId);
    tbody.querySelectorAll('tr td[colspan]').forEach(function (td) {
      td.classList.add('empty-td');
      td.removeAttribute('style');
    });
    tbody.querySelectorAll('tr').forEach(function (tr) {
      var cells = tr.querySelectorAll('td');
      if (cells.length >= 4 && !cells[0].colSpan) {
        cells[0].classList.add('l', 'b');
        var usage = cells[3];
        var text = usage.textContent || '';
        usage.innerHTML = '<b class="uv">' + esc(text.replace('%', '')) + '%</b>';
      }
    });
    return;
  }
  tbody.innerHTML = '<tr><td colspan="4" class="empty-td">' + esc(emptyMessage) + '</td></tr>';
}

export function mount(container, ctx) {
  CSS.forEach(ensureCss);
  var franchiseId = franchiseIdFrom(ctx);
  var userTeamId = userTeamIdFrom(ctx);
  var projectedMode = 'attributes';
  var cache = { playUsage: null, projected: [], stats: {}, teamAttrs: {}, measures: [] };

  container.innerHTML = '<div class="pv sc" data-state="loading">'
    + '<p class="scouting-status" role="status">Loading scouting report…</p>'
    + '<div class="scouting-ready" hidden></div></div>';

  var statusEl = container.querySelector('.scouting-status');
  var readyEl = container.querySelector('.scouting-ready');

  function setStatus(text) {
    if (statusEl) statusEl.textContent = text;
    readyEl.hidden = true;
  }

  function fcc() {
    return window.GOBFccPrep || {};
  }

  function waitFcc() {
    var prep = fcc();
    if (prep.whenReady) return Promise.resolve(prep.whenReady());
    return Promise.resolve();
  }

  function resolveOpponent() {
    var prep = fcc();
    if (prep.resolveUpcomingOpponent) return prep.resolveUpcomingOpponent();
    return Promise.resolve(null);
  }

  function rankingEntry(teamId) {
    var prep = fcc();
    if (prep.rankingEntry) return prep.rankingEntry(teamId);
    return null;
  }

  function standingsEntry(teamId) {
    var prep = fcc();
    if (prep.standingsEntry) return prep.standingsEntry(teamId);
    return null;
  }

  function teamLogoHtml(teamName) {
    var src = '';
    if (typeof window.getTeamAssetPath === 'function') {
      src = window.getTeamAssetPath(teamName, 'logo_square') || '';
    }
    if (src) {
      return '<span class="logo"><img src="' + esc(src) + '" alt="" width="48" height="48"></span>';
    }
    var parts = String(teamName || '').trim().split(/\s+/).filter(Boolean);
    var mono = parts.length ? parts[0].charAt(0).toUpperCase() : '?';
    return '<span class="logo" style="width:48px;height:48px;font-size:28px">' + esc(mono) + '</span>';
  }

  function paintProjectedTable() {
    var tableHost = readyEl.querySelector('#scouting-projected-table');
    if (!tableHost) return;
    var mode = projectedMode;
    tableHost.innerHTML = '<table class="tbl grp agrid">'
      + agridHead(mode)
      + (mode === 'stats'
        ? agridBodyStats(cache.projected, cache.stats)
        : agridBodyAttributes(cache.projected))
      + '</table>';
    if (typeof window.initAttributeTooltips === 'function') {
      window.initAttributeTooltips(tableHost, ['[data-tooltip]', '.aa']);
    }
  }

  function wireToggle() {
    var seg = readyEl.querySelector('[data-scouting-projected-toggle]');
    if (!seg || seg.__wired) return;
    seg.__wired = true;
    seg.querySelectorAll('button').forEach(function (btn) {
      btn.addEventListener('click', function () {
        projectedMode = btn.getAttribute('data-mode') || 'attributes';
        seg.querySelectorAll('button').forEach(function (b) {
          var on = b === btn;
          b.classList.toggle('on', on);
          b.setAttribute('aria-checked', on ? 'true' : 'false');
        });
        paintProjectedTable();
      });
    });
  }

  function paintReady(opponent, teamData, playUsage) {
    cache.teamAttrs = (teamData && teamData.team_attributes) || {};
    cache.measures = (teamData && teamData.measures) || [];
    cache.projected = (playUsage && playUsage.projected_starting_five) || [];
    cache.stats = (playUsage && playUsage.player_season_stats) || {};
    cache.playUsage = playUsage || {};

    var rankEntry = rankingEntry(opponent.id);
    var stand = standingsEntry(opponent.id);
    var wins = Number(stand && stand.W != null ? stand.W : (rankEntry && rankEntry.W) || 0);
    var losses = Number(stand && stand.L != null ? stand.L : (rankEntry && rankEntry.L) || 0);
    var rank = Number(rankEntry && rankEntry.natl_rank != null ? rankEntry.natl_rank : 0);
    var rankText = rank > 0 ? 'National #' + rank : 'National —';
    var teamPage = '#';
    if (fcc().teamPageUrl && opponent.id) {
      teamPage = fcc().teamPageUrl(opponent.id, opponent.name, 'scouting-view');
    }

    readyEl.innerHTML = ''
      + '<div class="opp">' + teamLogoHtml(opponent.name)
      + '<div><div class="opp-n">' + esc(opponent.name || '—') + '</div>'
      + '<div class="opp-m"><span>' + esc(wins + '–' + losses) + '</span><i>·</i><span>' + esc(rankText) + '</span><i>·</i>'
      + '<a class="lnk" href="' + esc(teamPage) + '" data-return>View Team Page</a></div></div>'
      + '<div class="opp-ranks" id="scouting-header-ranks"></div></div>'
      + '<section><div class="sh"><h2>Projected Starting 5</h2><div class="r"><div class="seg" role="radiogroup" data-scouting-projected-toggle>'
      + '<button type="button" class="on" data-mode="attributes" role="radio" aria-checked="true">Attributes</button>'
      + '<button type="button" data-mode="stats" role="radio" aria-checked="false">Stats</button>'
      + '</div></div></div><div class="tcard scroll-x" id="scouting-projected-table"></div></section>'
      + '<section><div class="sh"><h2>Team Measures</h2><span class="m">−20 to +20</span></div>'
      + '<div id="scouting-measure-rows"></div></section>'
      + '<div class="cols3">'
      + '<section><div class="sh"><h2>Half-Court Offense</h2></div><div class="tcard"><table class="tbl tight ut"><thead><tr>'
      + '<th class="l">Play</th><th>Run</th><th>Success</th><th>Usage</th></tr></thead>'
      + '<tbody id="scouting-hco-body"></tbody></table></div></section>'
      + '<section><div class="sh"><h2>Fast Breaks</h2></div><div class="tcard"><table class="tbl tight ut"><thead><tr>'
      + '<th class="l">Play</th><th>Run</th><th>Success</th><th>Usage</th></tr></thead>'
      + '<tbody id="scouting-fb-body"></tbody></table></div></section>'
      + '<section><div class="sh"><h2>Half-Court Traps</h2></div><div class="tcard"><table class="tbl tight ut"><thead><tr>'
      + '<th class="l">Play</th><th>Run</th><th>Success</th><th>Usage</th></tr></thead>'
      + '<tbody id="scouting-hct-body"></tbody></table></div></section>'
      + '</div>';

    renderHeaderRanks(readyEl.querySelector('#scouting-header-ranks'), cache.measures);
    renderMeasureRows(readyEl.querySelector('#scouting-measure-rows'), cache.teamAttrs);
    paintProjectedTable();
    wireToggle();

    var pu = cache.playUsage;
    var playUsageUnlocked = pu.play_usage_unlocked !== false;
    renderUsageTable(
      'scouting-hco-body',
      playUsageUnlocked ? (pu.plays || []) : [],
      playUsageUnlocked
        ? 'No previous game data available. Opponent has not played a game yet this season.'
        : "N/A — Run Film Study in training this week to scout this opponent's play usage."
    );
    var extendedHint = "N/A — Set Film Study above 1 in training this week to scout this opponent's play usage.";
    var fbUnlocked = pu.fast_break_usage_unlocked === true;
    renderUsageTable(
      'scouting-fb-body',
      fbUnlocked ? (pu.fast_break_plays || []) : [],
      fbUnlocked
        ? "No fast break data available from the opponent's last game."
        : extendedHint
    );
    var hctUnlocked = pu.hct_usage_unlocked === true;
    renderUsageTable(
      'scouting-hct-body',
      hctUnlocked ? (pu.hct_trap_plays || []) : [],
      hctUnlocked
        ? 'No half-court trap data available from the opponent\'s last game.'
        : extendedHint
    );

    statusEl.hidden = true;
    readyEl.hidden = false;
    container.querySelector('.pv').setAttribute('data-state', 'ready');
  }

  function load() {
    setStatus('Loading scouting report…');
    return loadScript('/js/utils/attributeDisplay.js')
      .then(function () { return loadScript('/js/shared/scoutingReport.js'); })
      .then(function () { return loadScript('/js/shared/playerYear.js'); })
      .then(waitFcc)
      .then(resolveOpponent)
      .then(function (opponent) {
        if (!opponent || !opponent.name) {
          setStatus('No upcoming opponent available for scouting.');
          return;
        }
        if (!franchiseId) {
          setStatus('Unable to open scouting report.');
          return;
        }
        var authHeaders = window.API_CONFIG && window.API_CONFIG.getAuthHeaders
          ? window.API_CONFIG.getAuthHeaders()
          : {};
        var teamQ = 'franchise_id=' + encodeURIComponent(franchiseId);
        if (opponent.id) teamQ += '&team_id=' + encodeURIComponent(opponent.id);
        else teamQ += '&team_name=' + encodeURIComponent(opponent.name);
        return Promise.all([
          fetch(window.API_CONFIG.buildUrl('/franchise/team-data') + '?' + teamQ, { headers: authHeaders }),
          fetch(window.API_CONFIG.buildUrl('/franchise/scouting-report') + '?franchise_id='
            + encodeURIComponent(franchiseId) + '&team_name=' + encodeURIComponent(opponent.name), { headers: authHeaders })
        ]).then(function (resPair) {
          if (!resPair[0].ok || !resPair[1].ok) throw new Error('load failed');
          return Promise.all([resPair[0].json(), resPair[1].json()]).then(function (payloads) {
            paintReady(opponent, payloads[0], payloads[1]);
          });
        });
      })
      .catch(function () {
        setStatus('Unable to load scouting report.');
      });
  }

  load();

  return {
    revalidate: function () { load(); },
    unmount: function () {}
  };
}

export function unmount() {}
