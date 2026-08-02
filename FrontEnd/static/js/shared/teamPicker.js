/**
 * TeamPicker — reusable 128-team program picker.
 *
 * Consumers:
 *   1. franchise-select-team — Scout + Select → create franchise
 *   2. Team Builder Step 0 — confirmation panel + "Choose this slot →"
 *
 * Phase 2 (§5): conference geography (alongside region A–H), card stats,
 * talent/prestige/geography filters with dead-button (no reflow) behavior.
 */
(function (global) {
  'use strict';

  // Verbatim from team-builder-v2-plan.md §5.1 — conference-level geography.
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

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

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

  function formatInt(n) {
    return (Number(n) || 0).toLocaleString();
  }

  function assetPath(teamName, assetKey) {
    if (typeof global.getTeamAssetPath === 'function') {
      return global.getTeamAssetPath(teamName, assetKey);
    }
    return '/images/teams/general/general_banner_primary.jpg';
  }

  function playClick() {
    try {
      var a = new Audio('/sounds/' + encodeURIComponent('click-beep.wav'));
      a.volume = 0.7;
      a.play().catch(function () {});
    } catch (_) { /* ignore */ }
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

  function compareTeams(a, b) {
    var ca = normalizeConference(a.conference);
    var cb = normalizeConference(b.conference);
    if (ca != null && cb != null && ca !== cb) return ca - cb;
    if (ca != null && cb == null) return -1;
    if (ca == null && cb != null) return 1;
    return String(a.name || '').localeCompare(String(b.name || ''), undefined, { sensitivity: 'base' });
  }

  /**
   * @param {HTMLElement} rootEl
   * @param {object} options
   */
  function mount(rootEl, options) {
    if (!rootEl) throw new Error('TeamPicker.mount requires a root element');
    options = options || {};

    var primaryAction = options.primaryAction || { label: 'Select', onClick: function () {} };
    var secondaryAction = options.secondaryAction || null;
    var confirmation = options.confirmation || null;
    var confirmationEnabled = !!(confirmation && confirmation.enabled);

    var state = {
      teams: Array.isArray(options.teams) ? options.teams.slice() : [],
      search: '',
      talentBand: 'all',
      prestigeBand: 'all',
      geography: 'all',
      talentBands: {},
      prestigeBands: {},
      // Canonical selection key = Mongo ObjectId string (team.object_id).
      selectedObjectId: options.initiallySelectedObjectId || null,
      destroyed: false,
    };

    rootEl.classList.add('team-picker');
    rootEl.innerHTML =
      '<div class="team-picker-toolbar">' +
      '  <label class="team-picker-search">' +
      '    <span class="team-picker-search-label">Search</span>' +
      '    <input type="search" class="team-picker-search-input" placeholder="Search programs…" autocomplete="off" spellcheck="false">' +
      '  </label>' +
      '  <div class="team-picker-filters">' +
      '    <label class="team-picker-filter">' +
      '      <span class="team-picker-filter-label">Talent</span>' +
      '      <select class="team-picker-talent-select"></select>' +
      '    </label>' +
      '    <label class="team-picker-filter">' +
      '      <span class="team-picker-filter-label">Prestige</span>' +
      '      <select class="team-picker-prestige-select"></select>' +
      '    </label>' +
      '    <label class="team-picker-filter team-picker-filter-geography">' +
      '      <span class="team-picker-filter-label">Geography</span>' +
      '      <select class="team-picker-geography-select"></select>' +
      '    </label>' +
      '  </div>' +
      '  <div class="team-picker-count" aria-live="polite"></div>' +
      '</div>' +
      '<div class="team-picker-status" hidden></div>' +
      '<div class="team-picker-confirm" hidden>' +
      '  <div class="team-picker-confirm-body"></div>' +
      '  <div class="team-picker-confirm-actions">' +
      '    <button type="button" class="team-picker-confirm-cancel">Cancel</button>' +
      '    <button type="button" class="team-picker-confirm-cta"></button>' +
      '  </div>' +
      '</div>' +
      '<div class="team-picker-list"></div>';

    var searchInput = rootEl.querySelector('.team-picker-search-input');
    var talentSelect = rootEl.querySelector('.team-picker-talent-select');
    var prestigeSelect = rootEl.querySelector('.team-picker-prestige-select');
    var geographySelect = rootEl.querySelector('.team-picker-geography-select');
    var countEl = rootEl.querySelector('.team-picker-count');
    var statusEl = rootEl.querySelector('.team-picker-status');
    var listEl = rootEl.querySelector('.team-picker-list');
    var confirmEl = rootEl.querySelector('.team-picker-confirm');
    var confirmBody = rootEl.querySelector('.team-picker-confirm-body');
    var confirmCancel = rootEl.querySelector('.team-picker-confirm-cancel');
    var confirmCta = rootEl.querySelector('.team-picker-confirm-cta');

    if (confirmationEnabled && confirmCta) {
      confirmCta.textContent = confirmation.confirmLabel || 'Choose this slot →';
    }

    function setStatus(message, isError) {
      if (!statusEl) return;
      if (!message) {
        statusEl.hidden = true;
        statusEl.textContent = '';
        statusEl.classList.remove('is-error');
        return;
      }
      statusEl.hidden = false;
      statusEl.textContent = message;
      statusEl.classList.toggle('is-error', !!isError);
    }

    function recomputeBands() {
      state.talentBands = assignRankBands(state.teams, 'total_player_attrs');
      state.prestigeBands = assignRankBands(state.teams, 'prestige');
    }

    function rebuildFilterOptions() {
      var bandOptions =
        '<option value="all">All tiers</option>' +
        BAND_CUTOFFS.map(function (b) {
          return '<option value="' + b.band + '">Tier ' + b.band + '</option>';
        }).join('');
      talentSelect.innerHTML = bandOptions;
      prestigeSelect.innerHTML = bandOptions;
      talentSelect.value = state.talentBand;
      prestigeSelect.value = state.prestigeBand;

      var geos = distinctGeographies();
      geographySelect.innerHTML =
        '<option value="all">All geographies</option>' +
        geos
          .map(function (g) {
            return '<option value="' + escapeHtml(g) + '">' + escapeHtml(g) + '</option>';
          })
          .join('');
      if (state.geography !== 'all' && geos.indexOf(state.geography) === -1) {
        state.geography = 'all';
      }
      geographySelect.value = state.geography;
    }

    function teamPassesStackFilters(team) {
      var conf = normalizeConference(team.conference);
      var region = normalizeRegion(team.region) || regionFromConference(conf);
      var oid = teamObjectId(team);

      if (state.talentBand !== 'all') {
        if (Number(state.talentBands[oid]) !== Number(state.talentBand)) return false;
      }
      if (state.prestigeBand !== 'all') {
        if (Number(state.prestigeBands[oid]) !== Number(state.prestigeBand)) return false;
      }
      if (state.geography !== 'all') {
        var geos = geographyForConference(conf);
        if (geos.indexOf(state.geography) === -1) return false;
      }

      var q = String(state.search || '')
        .trim()
        .toLowerCase();
      if (q) {
        var hay = [
          team.name,
          team.mascot,
          formatConferenceLabel(conf),
          region,
          formatGeographyList(conf),
        ]
          .filter(Boolean)
          .join(' ')
          .toLowerCase();
        if (hay.indexOf(q) === -1) return false;
      }
      return true;
    }

    function groupByConference(teams) {
      var groups = {};
      var order = [];
      teams.forEach(function (team) {
        var conf = normalizeConference(team.conference);
        var key = conf == null ? 'other' : String(conf);
        if (!groups[key]) {
          groups[key] = [];
          order.push(key);
        }
        groups[key].push(team);
      });
      order.sort(function (a, b) {
        if (a === 'other') return 1;
        if (b === 'other') return -1;
        return Number(a) - Number(b);
      });
      return order.map(function (key) {
        var sample = groups[key][0];
        var conf = key === 'other' ? null : Number(key);
        var region = normalizeRegion(sample && sample.region) || regionFromConference(conf);
        var geo = conf != null ? formatGeographyList(conf) : '';
        var title =
          conf == null
            ? 'Other programs'
            : formatConferenceLabel(conf) +
              (region ? ' · Region ' + region : '') +
              (geo ? ' · ' + geo : '');
        return { key: key, title: title, teams: groups[key].slice().sort(compareTeams) };
      });
    }

    function hideConfirmation() {
      if (!confirmEl) return;
      confirmEl.hidden = true;
      if (confirmBody) confirmBody.innerHTML = '';
    }

    function showConfirmation(team) {
      if (!confirmationEnabled || !confirmEl || !confirmBody) return;
      confirmBody.innerHTML = '';
      if (typeof confirmation.renderBody === 'function') {
        confirmation.renderBody(team, confirmBody);
      } else {
        confirmBody.innerHTML =
          '<p class="team-picker-confirm-fallback"><strong>' +
          escapeHtml(team.name) +
          '</strong> selected.</p>';
      }
      confirmEl.hidden = false;
      try {
        confirmEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      } catch (_) { /* ignore */ }
    }

    function setSelected(objectId, opts) {
      opts = opts || {};
      state.selectedObjectId = objectId || null;
      listEl.querySelectorAll('.team-card.is-selected').forEach(function (el) {
        el.classList.remove('is-selected');
      });
      if (state.selectedObjectId) {
        var cards = listEl.querySelectorAll('.team-card');
        for (var i = 0; i < cards.length; i++) {
          if (cards[i].dataset.objectId === state.selectedObjectId) {
            cards[i].classList.add('is-selected');
            break;
          }
        }
      }
      if (!state.selectedObjectId) {
        hideConfirmation();
        return;
      }
      if (confirmationEnabled && !opts.skipConfirm) {
        var team = findTeamByObjectId(state.selectedObjectId);
        if (team) showConfirmation(team);
      }
    }

    function findTeamByObjectId(objectId) {
      var key = String(objectId || '').trim();
      if (!key) return null;
      return (
        state.teams.find(function (t) {
          return teamObjectId(t) === key;
        }) || null
      );
    }

    function onPrimary(team) {
      if (!teamPassesStackFilters(team)) return;
      if (confirmationEnabled) {
        setSelected(teamObjectId(team));
        return;
      }
      if (typeof primaryAction.onClick === 'function') primaryAction.onClick(team);
    }

    function buildCard(team, isActive) {
      var oid = teamObjectId(team);
      var card = document.createElement('div');
      card.className = 'team-card' + (isActive ? '' : ' is-filtered-out');
      card.dataset.team = team.name || '';
      card.dataset.objectId = oid;
      if (state.selectedObjectId && oid && oid === state.selectedObjectId && isActive) {
        card.classList.add('is-selected');
      }
      if (!isActive) {
        card.setAttribute('aria-disabled', 'true');
      }

      // Conference / region / geography live on the group header — cards keep attrs + prestige.
      var statsLine =
        'Attrs ' +
        formatInt(numericField(team, 'total_player_attrs')) +
        ' · Prestige ' +
        formatInt(numericField(team, 'prestige'));

      var primaryLabel = primaryAction.label || 'Select';
      var hasSecondary = !!(secondaryAction && secondaryAction.label && isActive);
      var overlayClass = 'team-card-overlay' + (hasSecondary ? '' : ' is-single-action');
      var secondaryHtml = hasSecondary
        ? '<button class="team-card-action team-card-action-secondary" type="button">' +
          escapeHtml(secondaryAction.label) +
          '</button>'
        : '';

      var cardSrc = assetPath(team.name, 'banner_card');
      var fullSrc = assetPath(team.name, 'banner_primary');

      card.innerHTML =
        '<div class="team-card-check" aria-hidden="true">✓</div>' +
        '<div class="team-card-banner">' +
        '  <img src="' +
        escapeHtml(cardSrc) +
        '" alt="' +
        escapeHtml(team.name) +
        '" loading="lazy" decoding="async" data-fallback="' +
        escapeHtml(fullSrc) +
        '">' +
        '  <div class="team-card-caption">' +
        '    <div class="team-card-name">' +
        escapeHtml(team.name) +
        '</div>' +
        '    <div class="team-card-stats">' +
        escapeHtml(statsLine) +
        '</div>' +
        '  </div>' +
        (isActive
          ? '  <div class="' +
            overlayClass +
            '">' +
            secondaryHtml +
            '    <button class="team-card-action team-card-action-primary" type="button">' +
            escapeHtml(primaryLabel) +
            '</button>' +
            '  </div>'
          : '') +
        '</div>';

      var img = card.querySelector('.team-card-banner img');
      if (img) {
        img.addEventListener('error', function onBannerErr() {
          img.removeEventListener('error', onBannerErr);
          var fb = img.getAttribute('data-fallback');
          if (fb && img.src !== fb) img.src = fb;
        });
      }

      if (!isActive) return card;

      var secondaryBtn = card.querySelector('.team-card-action-secondary');
      var primaryBtn = card.querySelector('.team-card-action-primary');

      if (secondaryBtn) {
        secondaryBtn.addEventListener('click', function () {
          playClick();
          if (typeof secondaryAction.onClick === 'function') secondaryAction.onClick(team);
        });
      }
      if (primaryBtn) {
        primaryBtn.addEventListener('click', function () {
          playClick();
          onPrimary(team);
        });
      }

      return card;
    }

    function render() {
      if (state.destroyed) return;
      // Always render the full 128 — filters dim, they never reflow or empty (§5.3).
      var teams = state.teams.slice().sort(compareTeams);
      var groups = groupByConference(teams);
      var activeCount = 0;

      listEl.innerHTML = '';
      if (!teams.length) {
        listEl.innerHTML =
          '<div class="team-picker-empty">No programs available.</div>';
      } else {
        groups.forEach(function (group) {
          var section = document.createElement('section');
          section.className = 'team-picker-group';
          section.innerHTML =
            '<h2 class="team-picker-group-title">' +
            escapeHtml(group.title) +
            '</h2>' +
            '<div class="team-picker-grid"></div>';
          var grid = section.querySelector('.team-picker-grid');
          group.teams.forEach(function (team) {
            var active = teamPassesStackFilters(team);
            if (active) activeCount += 1;
            grid.appendChild(buildCard(team, active));
          });
          listEl.appendChild(section);
        });
      }

      if (countEl) {
        countEl.textContent =
          activeCount === teams.length
            ? teams.length + ' programs'
            : activeCount + ' available · ' + teams.length + ' shown';
      }

      if (confirmationEnabled && state.selectedObjectId) {
        var selected = findTeamByObjectId(state.selectedObjectId);
        if (!selected || !teamPassesStackFilters(selected)) {
          hideConfirmation();
        } else {
          showConfirmation(selected);
        }
      }
    }

    function onSearchInput() {
      state.search = searchInput.value || '';
      render();
    }

    function onTalentChange() {
      state.talentBand = talentSelect.value || 'all';
      render();
    }

    function onPrestigeChange() {
      state.prestigeBand = prestigeSelect.value || 'all';
      render();
    }

    function onGeographyChange() {
      state.geography = geographySelect.value || 'all';
      render();
    }

    searchInput.addEventListener('input', onSearchInput);
    talentSelect.addEventListener('change', onTalentChange);
    prestigeSelect.addEventListener('change', onPrestigeChange);
    geographySelect.addEventListener('change', onGeographyChange);

    if (confirmCancel) {
      confirmCancel.addEventListener('click', function () {
        playClick();
        setSelected(null);
        if (confirmation && typeof confirmation.onCancel === 'function') {
          confirmation.onCancel();
        }
      });
    }
    if (confirmCta) {
      confirmCta.addEventListener('click', function () {
        playClick();
        var team = findTeamByObjectId(state.selectedObjectId);
        if (!team || !teamPassesStackFilters(team)) return;
        if (confirmation && typeof confirmation.onConfirm === 'function') {
          confirmation.onConfirm(team);
        }
      });
    }

    function setTeams(teams) {
      state.teams = Array.isArray(teams) ? teams.slice() : [];
      recomputeBands();
      rebuildFilterOptions();
      render();
    }

    function destroy() {
      state.destroyed = true;
      searchInput.removeEventListener('input', onSearchInput);
      talentSelect.removeEventListener('change', onTalentChange);
      prestigeSelect.removeEventListener('change', onPrestigeChange);
      geographySelect.removeEventListener('change', onGeographyChange);
      rootEl.classList.remove('team-picker');
      rootEl.innerHTML = '';
    }

    if (state.teams.length) {
      recomputeBands();
      rebuildFilterOptions();
      render();
      setStatus('');
    } else if (options.teams === null) {
      setStatus('No programs available.', true);
    } else {
      setStatus('Loading programs…');
      listEl.innerHTML = '<div class="team-picker-empty">Loading programs…</div>';
      fetchTeams()
        .then(function (teams) {
          if (state.destroyed) return;
          setTeams(teams);
          setStatus(teams.length ? '' : 'No programs available.', !teams.length);
        })
        .catch(function (err) {
          if (state.destroyed) return;
          console.error('[TeamPicker] failed to load teams:', err);
          setStatus(err.message || 'Could not load programs.', true);
          listEl.innerHTML =
            '<div class="team-picker-empty">Could not load programs. Refresh and try again.</div>';
        });
    }

    return {
      destroy: destroy,
      setTeams: setTeams,
      getSelected: function () {
        return findTeamByObjectId(state.selectedObjectId);
      },
      setSelected: function (objectIdOrTeam) {
        if (objectIdOrTeam && typeof objectIdOrTeam === 'object') {
          setSelected(teamObjectId(objectIdOrTeam));
        } else {
          setSelected(objectIdOrTeam || null);
        }
      },
      clearSelection: function () {
        setSelected(null);
      },
      refresh: render,
      getBandHistograms: function () {
        return {
          talent: bandSizeHistogram(state.talentBands),
          prestige: bandSizeHistogram(state.prestigeBands),
        };
      },
    };
  }

  global.TeamPicker = {
    mount: mount,
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
