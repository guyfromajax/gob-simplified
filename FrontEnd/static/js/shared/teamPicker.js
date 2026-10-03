/**
 * TeamPicker — data helpers for the 128-team league (no UI).
 *
 * Consumers: franchise-select-team (program select), Team Builder
 * (team-builder.js, js/team-builder/review.js, establish.js) and
 * scripts/tb_phase2_team_select.mjs. The old picker UI (TeamPicker.mount and
 * its render helpers) and css/team-picker.css were removed on 2026-10-01:
 * nothing called mount and no page loaded the sheet.
 *
 * Conference geography (alongside region A–H) and talent/prestige rank bands.
 */
(function (global) {
  'use strict';

  // Verbatim from projects/Z-Completed/team-builder-v2-plan.md §5.1 — conference-level geography.
  // Does not replace or overload region A–H.
  var CONFERENCE_GEOGRAPHY = {
    1: ['Pennsylvania', 'New Jersey', 'Delaware'],
    2: ['West Virginia', 'North Carolina', 'Virginia', 'Maryland'],
    3: [
      'Massachusetts',
      'Rhode Island',
      'Vermont',
      'Maine',
      'New Hampshire',
      'Connecticut',
    ],
    4: ['New York', 'East Canada', 'Europe'],
    5: ['Michigan', 'Ohio', 'Indiana'],
    6: ['Illinois', 'Minnesota', 'Wisconsin'],
    7: ['Mississippi', 'Tennessee', 'Kentucky', 'South Carolina', 'Alabama'],
    8: ['Florida', 'Georgia'],
    9: ['Iowa', 'Kansas', 'Missouri'],
    10: [
      'Nebraska',
      'South Dakota',
      'North Dakota',
      'Wyoming',
      'Montana',
      'Central Canada',
    ],
    11: ['Oklahoma', 'Texas', 'Arkansas'],
    12: ['Texas', 'Louisiana'],
    13: ['Arizona', 'New Mexico', 'Nevada', 'Colorado', 'Utah'],
    14: ['Idaho', 'Washington', 'Oregon', 'West Canada'],
    15: ['California'],
    16: ['California', 'Hawaii', 'Alaska', 'Asia', 'Australia'],
  };

  // Rank positions → band (sizes 26/25/26/25/26). Descending value, ties by team_id.
  // Rank cutoffs (descending): sizes 26/25/26/25/26 across 128 teams.
  var BAND_CUTOFFS = [
    { maxRank: 26, band: 1 },
    { maxRank: 51, band: 2 },
    { maxRank: 77, band: 3 },
    { maxRank: 102, band: 4 },
    { maxRank: 128, band: 5 },
  ];

  // §10.5 / plan — named end-bands for height / class filters (verbatim).
  function normalizeRegion(region) {
    if (region == null || region === '') return '';
    return String(region).trim().toUpperCase();
  }

  function normalizeConference(conference) {
    var n = Number(conference);
    return Number.isInteger(n) && n >= 1 && n <= 16 ? n : null;
  }

  /** Region letter from conference 1–16 (mirrors FCC / backend mapping). */
  function regionFromConference(conference) {
    var n = normalizeConference(conference);
    if (n == null) return '';
    return String.fromCharCode(65 + Math.floor((n - 1) / 2));
  }

  function formatConferenceLabel(conference) {
    var n = normalizeConference(conference);
    if (n == null) return conference == null || conference === '' ? '—' : String(conference);
    return 'Conference ' + n;
  }

  function formatConferenceMeta(team) {
    var conf = normalizeConference(team && team.conference);
    var region = normalizeRegion(team && team.region) || regionFromConference(conf);
    if (conf == null && !region) return '';
    if (conf != null && region) return formatConferenceLabel(conf) + ' · Region ' + region;
    if (conf != null) return formatConferenceLabel(conf);
    return 'Region ' + region;
  }

  function geographyForConference(conference) {
    var n = normalizeConference(conference);
    if (n == null) return [];
    return (CONFERENCE_GEOGRAPHY[n] || []).slice();
  }

  function formatGeographyList(conference) {
    var list = geographyForConference(conference);
    return list.length ? list.join(', ') : '—';
  }

  function distinctGeographies() {
    var found = {};
    Object.keys(CONFERENCE_GEOGRAPHY).forEach(function (key) {
      CONFERENCE_GEOGRAPHY[key].forEach(function (g) {
        found[g] = true;
      });
    });
    return Object.keys(found).sort(function (a, b) {
      return a.localeCompare(b);
    });
  }

  function conferencesForGeography(geography) {
    var label = String(geography || '').trim();
    if (!label) return [];
    var out = [];
    Object.keys(CONFERENCE_GEOGRAPHY).forEach(function (key) {
      var conf = Number(key);
      if (CONFERENCE_GEOGRAPHY[key].indexOf(label) !== -1) out.push(conf);
    });
    return out.sort(function (a, b) {
      return a - b;
    });
  }

  function teamObjectId(team) {
    if (!team) return '';
    return String(team.object_id || team.objectId || '').trim();
  }

  function teamSortId(team) {
    return String(team && (team.team_id || team.object_id || team.name) || '');
  }

  function numericField(team, key) {
    var n = Number(team && team[key]);
    return isFinite(n) ? n : 0;
  }

  /**
   * Assign percentile bands by rank across the 128.
   * Descending value; ties broken by team_id ascending.
   * Band sizes: 26 / 25 / 26 / 25 / 26.
   */
  function assignRankBands(teams, valueKey) {
    var sorted = (teams || []).slice().sort(function (a, b) {
      var va = numericField(a, valueKey);
      var vb = numericField(b, valueKey);
      if (vb !== va) return vb - va;
      return teamSortId(a).localeCompare(teamSortId(b));
    });
    var byOid = {};
    sorted.forEach(function (team, idx) {
      var rank = idx + 1;
      var band = 5;
      for (var i = 0; i < BAND_CUTOFFS.length; i++) {
        if (rank <= BAND_CUTOFFS[i].maxRank) {
          band = BAND_CUTOFFS[i].band;
          break;
        }
      }
      byOid[teamObjectId(team)] = band;
    });
    return byOid;
  }

  function bandSizeHistogram(bandByOid) {
    var hist = { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 };
    Object.keys(bandByOid || {}).forEach(function (oid) {
      var b = bandByOid[oid];
      if (hist[b] != null) hist[b] += 1;
    });
    return hist;
  }

  async function fetchTeams() {
    var headers =
      global.API_CONFIG && typeof global.API_CONFIG.getAuthHeaders === 'function'
        ? global.API_CONFIG.getAuthHeaders()
        : {};
    var url =
      global.API_CONFIG && typeof global.API_CONFIG.buildUrl === 'function'
        ? global.API_CONFIG.buildUrl('/teams')
        : '/teams';
    var res = await fetch(url, { headers: headers });
    if (!res.ok) throw new Error('Could not load programs');
    var data = await res.json();
    return Array.isArray(data) ? data : [];
  }

  /**
   * @param {HTMLElement} rootEl
   * @param {object} options
   */
  global.TeamPicker = {
    fetchTeams: fetchTeams,
    teamObjectId: teamObjectId,
    formatConferenceLabel: formatConferenceLabel,
    formatConferenceMeta: formatConferenceMeta,
    regionFromConference: regionFromConference,
    geographyForConference: geographyForConference,
    formatGeographyList: formatGeographyList,
    distinctGeographies: distinctGeographies,
    conferencesForGeography: conferencesForGeography,
    assignRankBands: assignRankBands,
    bandSizeHistogram: bandSizeHistogram,
    CONFERENCE_GEOGRAPHY: CONFERENCE_GEOGRAPHY,
  };
})(typeof window !== 'undefined' ? window : globalThis);
