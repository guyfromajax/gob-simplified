/**
 * League › Tournament. Read-only brackets from GET /franchise/tournament/brackets.
 */

var PHASES = ['conference', 'region', 'national'];
var PHASE_LABELS = {
  conference: 'Conference',
  region: 'Region',
  national: 'National'
};

function bracketsUrl(tables, franchiseId) {
  return tables.apiBase('/franchise/tournament/brackets')
    + '?franchise_id=' + encodeURIComponent(franchiseId);
}

function phaseFromUrl(defaultPhase) {
  try {
    var raw = new URLSearchParams(window.location.search).get('tournament_phase');
    if (PHASES.indexOf(String(raw)) !== -1) return String(raw);
  } catch (err) { /* default */ }
  return defaultPhase || 'conference';
}

function writePhase(phase) {
  var q = new URLSearchParams(window.location.search);
  q.set('tab', 'tournament-view');
  q.set('tournament_phase', phase);
  var text = q.toString();
  window.history.replaceState({}, '', window.location.pathname + (text ? '?' + text : ''));
}

function normalizeRegion(rt) {
  if (!rt) return null;
  var finalList = rt.final || [];
  return {
    bracket: { round1: rt.round1 || [], round2: [], final: finalList },
    seeds: rt.seeds || {},
    champion: finalList[0] && finalList[0].winner ? finalList[0].winner : rt.champion
  };
}

function teamsToMaps(teams) {
  var names = {};
  var meta = {};
  Object.keys(teams || {}).forEach(function (id) {
    var t = teams[id] || {};
    names[id] = t.name || id;
    meta[id] = {
      natl_rank: t.natl_rank,
      W: t.W,
      L: t.L,
      region: t.region,
      conference: t.conference
    };
  });
  return { names: names, meta: meta };
}

function boxHref(franchiseId, teamId, gameId) {
  if (!gameId) return '';
  return '/box-score.html?game_id=' + encodeURIComponent(gameId)
    + '&mode=franchise&franchise_id=' + encodeURIComponent(franchiseId)
    + '&team_id=' + encodeURIComponent(teamId);
}

function phasePayload(data, phase) {
  if (!data) return null;
  if (phase === 'national') return data.national_tournament;
  if (phase === 'region') {
    var region = String(data.user_region || '').toUpperCase();
    return normalizeRegion((data.region_tournaments || {})[region]);
  }
  var conf = data.user_conference != null ? String(data.user_conference) : '';
  return conf ? (data.conference_tournaments || {})[conf] : null;
}

function phaseDrawCopy(data, phase) {
  var week = Number(data.week || 0);
  var opens = (data.phase_draw_week || {})[phase] || 27;
  if (week >= opens) return '';
  return 'Draws after Week ' + opens;
}

function statusHtml(data) {
  var parts = [];
  if (data.tournament_complete && data.champion) {
    var teams = data.teams || {};
    var champ = teams[String(data.champion)] || {};
    parts.push('<p class="gob-tour-champ">Champion: <strong>'
      + window.GOBTables.esc(champ.name || data.champion) + '</strong></p>');
  } else if (data.user_eliminated && data.eliminated_in_round) {
    parts.push('<p class="gob-tour-note">Eliminated in '
      + window.GOBTables.esc(data.eliminated_in_round) + '</p>');
  } else if (data.has_bye_this_week) {
    parts.push('<p class="gob-tour-note">Bye this round</p>');
  }
  return parts.join('');
}

function phasePickerHtml(data, phase) {
  var tables = window.GOBTables;
  var html = '<div class="stats-toggle gob-tour-phases" role="group" aria-label="Tournament phase">';
  PHASES.forEach(function (key) {
    html += '<button type="button" data-tour-phase="' + key + '"'
      + (key === phase ? ' class="on" aria-pressed="true"' : ' aria-pressed="false"')
      + '>' + tables.esc(PHASE_LABELS[key]) + '</button>';
  });
  html += '</div>';
  return html;
}

function renderBracket(host, data, phase, maps, ctx) {
  host.innerHTML = '';
  var draw = phaseDrawCopy(data, phase);
  if (draw) {
    host.innerHTML = '<p class="gob-tour-empty">' + window.GOBTables.esc(draw) + '</p>';
    return;
  }
  var payload = phasePayload(data, phase);
  if (!payload || !payload.bracket) {
    host.innerHTML = '<p class="gob-tour-empty">This bracket has not been drawn yet.</p>';
    return;
  }
  var layout = phase === 'region' ? 'compact4' : 'full';
  if (typeof window.FccTournamentStyleA === 'undefined') {
    host.innerHTML = '<p class="gob-tour-empty">Tournament bracket UI not loaded.</p>';
    return;
  }
  window.FccTournamentStyleA.renderInto(host, {
    sectionTitle: PHASE_LABELS[phase] + ' Tournament',
    layout: layout,
    bracket: payload.bracket || {},
    seeds: payload.seeds || {},
    teamIdToNameMap: maps.names,
    teamIdMetaMap: maps.meta,
    userTeamId: data.user_team_id,
    topData: { week: data.week, rankings: [] },
    allBrackets: Number(data.week) > 34,
    tierHint: phase,
    displayWeek: data.week,
    boxScoreHref: function (gameId) {
      return boxHref(ctx.franchiseId, ctx.teamId, gameId);
    }
  });
}

export function mount(container, ctx) {
  var tables = window.GOBTables;
  var franchiseId = (ctx && ctx.franchiseId) || '';
  var loaded = false;
  var signature = '';
  var data = null;

  function bindPhasePicker() {
    container.querySelectorAll('[data-tour-phase]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var phase = btn.getAttribute('data-tour-phase');
        writePhase(phase);
        paint();
      });
    });
  }

  function paint() {
    if (!data) return;
    var phase = phaseFromUrl(data.current_phase || 'conference');
    var maps = teamsToMaps(data.teams);
    var locked = !!data.locked;
    var html = '';
    if (locked) {
      html += '<p class="gob-tour-locked">Tournament opens Week ' + (data.first_week || 27) + '.</p>';
    }
    html += statusHtml(data);
    html += phasePickerHtml(data, phase);
    html += '<div class="gob-tour-bracket fcc-tournament-bracket"></div>';
    container.innerHTML = html;
    bindPhasePicker();
    if (!locked) {
      renderBracket(container.querySelector('.gob-tour-bracket'), data, phase, maps, ctx);
    }
  }

  function apply(payload) {
    var stamp = JSON.stringify(payload || {});
    if (loaded && stamp === signature) return;
    signature = stamp;
    loaded = true;
    data = payload || {};
    paint();
  }

  function load() {
    var store = ctx && ctx.store;
    if (!store || !franchiseId) {
      tables.paintError(container, 'Tournament could not be opened.', load);
      return;
    }
    if (!loaded) tables.paintSkeleton(container);
    store.get(bracketsUrl(tables, franchiseId)).then(function (payload) {
      apply(payload || {});
    }).catch(function () {
      loaded = false;
      tables.paintError(container, 'Tournament could not be opened.', load);
    });
  }

  function revalidate() {
    var store = ctx && ctx.store;
    if (!loaded || !store || !franchiseId) return;
    store.revalidate(bracketsUrl(tables, franchiseId)).then(function (payload) {
      if (payload) apply(payload);
    }).catch(function () { /* keep table */ });
  }

  function onTab(event) {
    if (event && event.detail && event.detail.tab === 'tournament-view') revalidate();
  }

  document.addEventListener('gob-tab-shown', onTab);
  load();

  return {
    revalidate: revalidate,
    unmount: function () {
      document.removeEventListener('gob-tab-shown', onTab);
    }
  };
}

export function unmount() {}
