/**
 * TeamPicker — reusable 128-team program picker.
 *
 * Consumers:
 *   1. franchise-select-team (Task A) — Scout + Select → create franchise
 *   2. Team Builder Step 0 (Task B) — same list/interactions; confirmation
 *      panel + "Choose this slot →" CTA instead of immediate create
 *
 * Usage:
 *   const picker = TeamPicker.mount(rootEl, {
 *     primaryAction: { label: 'Select', onClick(team) { ... } },
 *     secondaryAction: { label: 'Scout', onClick(team) { ... } },
 *     // Task B slot mode:
 *     confirmation: {
 *       enabled: true,
 *       confirmLabel: 'Choose this slot →',
 *       renderBody(team, el) { el.textContent = '...'; },
 *       onConfirm(team) { ... },
 *     },
 *   });
 */
(function (global) {
  'use strict';

  var REGION_ORDER = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'];

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

  function teamObjectId(team) {
    if (!team) return '';
    return String(team.object_id || team.objectId || '').trim();
  }

  function assetPath(teamName, assetKey) {
    if (typeof global.getTeamAssetPath === 'function') {
      return global.getTeamAssetPath(teamName, assetKey);
    }
    if (assetKey === 'banner_card') {
      return '/images/teams/general/general_banner_primary.jpg';
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
    var getSubtitle =
      typeof options.getSubtitle === 'function'
        ? options.getSubtitle
        : function (team) {
            return formatConferenceMeta(team);
          };

    var state = {
      teams: Array.isArray(options.teams) ? options.teams.slice() : [],
      search: '',
      region: 'all',
      conference: 'all',
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
      '      <span class="team-picker-filter-label">Region</span>' +
      '      <select class="team-picker-region-select"></select>' +
      '    </label>' +
      '    <label class="team-picker-filter">' +
      '      <span class="team-picker-filter-label">Conference</span>' +
      '      <select class="team-picker-conference-select"></select>' +
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
    var regionSelect = rootEl.querySelector('.team-picker-region-select');
    var conferenceSelect = rootEl.querySelector('.team-picker-conference-select');
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

    function rebuildFilterOptions() {
      var regions = {};
      var conferences = {};
      state.teams.forEach(function (team) {
        var conf = normalizeConference(team.conference);
        var region = normalizeRegion(team.region) || regionFromConference(conf);
        if (region) regions[region] = true;
        if (conf != null) conferences[conf] = true;
      });

      var regionKeys = REGION_ORDER.filter(function (r) {
        return regions[r];
      });
      Object.keys(regions)
        .sort()
        .forEach(function (r) {
          if (regionKeys.indexOf(r) === -1) regionKeys.push(r);
        });

      regionSelect.innerHTML =
        '<option value="all">All regions</option>' +
        regionKeys
          .map(function (r) {
            return '<option value="' + escapeHtml(r) + '">Region ' + escapeHtml(r) + '</option>';
          })
          .join('');
      regionSelect.value = state.region === 'all' || regions[state.region] ? state.region : 'all';
      if (regionSelect.value !== state.region) state.region = regionSelect.value;

      var confKeys = Object.keys(conferences)
        .map(Number)
        .sort(function (a, b) {
          return a - b;
        });
      var visibleConfKeys = confKeys.filter(function (c) {
        if (state.region === 'all') return true;
        return regionFromConference(c) === state.region;
      });

      conferenceSelect.innerHTML =
        '<option value="all">All conferences</option>' +
        visibleConfKeys
          .map(function (c) {
            return (
              '<option value="' +
              c +
              '">' +
              escapeHtml(formatConferenceLabel(c)) +
              '</option>'
            );
          })
          .join('');

      if (state.conference !== 'all') {
        var stillVisible = visibleConfKeys.indexOf(Number(state.conference)) !== -1;
        if (!stillVisible) state.conference = 'all';
      }
      conferenceSelect.value = state.conference;
    }

    function filteredTeams() {
      var q = String(state.search || '')
        .trim()
        .toLowerCase();
      return state.teams.filter(function (team) {
        var conf = normalizeConference(team.conference);
        var region = normalizeRegion(team.region) || regionFromConference(conf);
        if (state.region !== 'all' && region !== state.region) return false;
        if (state.conference !== 'all' && conf !== Number(state.conference)) return false;
        if (!q) return true;
        var hay = [team.name, team.mascot, formatConferenceLabel(conf), region]
          .filter(Boolean)
          .join(' ')
          .toLowerCase();
        return hay.indexOf(q) !== -1;
      });
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
        var title =
          conf == null
            ? 'Other programs'
            : formatConferenceLabel(conf) + (region ? ' · Region ' + region : '');
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
      return state.teams.find(function (t) {
        return teamObjectId(t) === key;
      }) || null;
    }

    function onPrimary(team) {
      if (confirmationEnabled) {
        setSelected(teamObjectId(team));
        return;
      }
      if (typeof primaryAction.onClick === 'function') primaryAction.onClick(team);
    }

    function buildCard(team) {
      var oid = teamObjectId(team);
      var card = document.createElement('div');
      card.className = 'team-card';
      card.dataset.team = team.name || '';
      card.dataset.objectId = oid;
      if (state.selectedObjectId && oid && oid === state.selectedObjectId) {
        card.classList.add('is-selected');
      }

      var subtitle = getSubtitle(team) || formatConferenceMeta(team) || '';
      var primaryLabel = primaryAction.label || 'Select';
      var hasSecondary = !!(secondaryAction && secondaryAction.label);
      var overlayClass = 'team-card-overlay' + (hasSecondary ? '' : ' is-single-action');
      var secondaryHtml = hasSecondary
        ? '<button class="team-card-action team-card-action-secondary" type="button">' +
          escapeHtml(secondaryAction.label) +
          '</button>'
        : '';

      // Prefer card-sized WebP; fall back to full banner_primary if derivative missing.
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
        (subtitle
          ? '<div class="team-card-meta">' + escapeHtml(subtitle) + '</div>'
          : '') +
        '  </div>' +
        '  <div class="' +
        overlayClass +
        '">' +
        secondaryHtml +
        '    <button class="team-card-action team-card-action-primary" type="button">' +
        escapeHtml(primaryLabel) +
        '</button>' +
        '  </div>' +
        '</div>';

      var img = card.querySelector('.team-card-banner img');
      if (img) {
        img.addEventListener('error', function onBannerErr() {
          img.removeEventListener('error', onBannerErr);
          var fb = img.getAttribute('data-fallback');
          if (fb && img.src !== fb) img.src = fb;
        });
      }

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
      var teams = filteredTeams().sort(compareTeams);
      var groups = groupByConference(teams);

      listEl.innerHTML = '';
      if (!teams.length) {
        listEl.innerHTML =
          '<div class="team-picker-empty">No programs match your search or filters.</div>';
      } else {
        groups.forEach(function (group) {
          var section = document.createElement('section');
          section.className = 'team-picker-group';
          section.innerHTML =
            '<h2 class="team-picker-group-title">' +
            escapeHtml(group.title) +
            '<span class="team-picker-group-count">' +
            group.teams.length +
            '</span></h2>' +
            '<div class="team-picker-grid"></div>';
          var grid = section.querySelector('.team-picker-grid');
          group.teams.forEach(function (team) {
            grid.appendChild(buildCard(team));
          });
          listEl.appendChild(section);
        });
      }

      if (countEl) {
        countEl.textContent =
          teams.length === state.teams.length
            ? teams.length + ' programs'
            : teams.length + ' of ' + state.teams.length + ' programs';
      }

      if (confirmationEnabled && state.selectedObjectId) {
        var stillVisible = teams.some(function (t) {
          return teamObjectId(t) === state.selectedObjectId;
        });
        if (!stillVisible) {
          hideConfirmation();
        } else {
          var selected = findTeamByObjectId(state.selectedObjectId);
          if (selected) showConfirmation(selected);
        }
      }
    }

    function onSearchInput() {
      state.search = searchInput.value || '';
      render();
    }

    function onRegionChange() {
      state.region = regionSelect.value || 'all';
      // Conference options depend on region.
      rebuildFilterOptions();
      render();
    }

    function onConferenceChange() {
      state.conference = conferenceSelect.value || 'all';
      render();
    }

    searchInput.addEventListener('input', onSearchInput);
    regionSelect.addEventListener('change', onRegionChange);
    conferenceSelect.addEventListener('change', onConferenceChange);

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
        if (!team) return;
        if (confirmation && typeof confirmation.onConfirm === 'function') {
          confirmation.onConfirm(team);
        }
      });
    }

    function setTeams(teams) {
      state.teams = Array.isArray(teams) ? teams.slice() : [];
      rebuildFilterOptions();
      render();
    }

    function destroy() {
      state.destroyed = true;
      searchInput.removeEventListener('input', onSearchInput);
      regionSelect.removeEventListener('change', onRegionChange);
      conferenceSelect.removeEventListener('change', onConferenceChange);
      rootEl.classList.remove('team-picker');
      rootEl.innerHTML = '';
    }

    // Initial data
    if (state.teams.length) {
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
    };
  }

  global.TeamPicker = {
    mount: mount,
    fetchTeams: fetchTeams,
    teamObjectId: teamObjectId,
    formatConferenceLabel: formatConferenceLabel,
    formatConferenceMeta: formatConferenceMeta,
    regionFromConference: regionFromConference,
  };
})(typeof window !== 'undefined' ? window : globalThis);
