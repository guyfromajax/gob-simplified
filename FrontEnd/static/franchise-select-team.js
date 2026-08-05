/**
 * Program Select + Claim — replaces the old TeamPicker-mounted franchise entry.
 *
 * Browse mode: Enter Franchise (non-mod path).
 * Builder mode: Take This Slot → team-builder.html Identity.
 * Tutorial mode: preserved (username modal funnel); TB entry hidden.
 *
 * Chrome: await ensureTeamBuilderChromeSnapshot before painting team art/labels
 * that could leak replaced-program identity. Unfinished drafts load by user_id.
 */
(function () {
  'use strict';

  var TUTORIAL_MODE = new URLSearchParams(window.location.search).get('mode') === 'tutorial';
  var HOME_SLOT_PARAM = (function () {
    var n = parseInt(new URLSearchParams(window.location.search).get('home_slot'), 10);
    return n === 1 || n === 2 ? n : null;
  })();
  var BUILDER_PARAM = new URLSearchParams(window.location.search).get('builder') === '1';

  var TIERS = {
    talent: ['Loaded', 'Deep', 'Average', 'Thin', 'Rebuilding'],
    prestige: ['Blue Blood', 'Established', 'Respected', 'Climbing', 'Unproven'],
    size: ['Tallest', 'Taller', 'Balanced', 'Quicker', 'Quickest'],
    experience: ['Most Experienced', 'Experienced', 'Balanced', 'Young', 'Youngest'],
  };

  var state = {
    builder: BUILDER_PARAM && !TUTORIAL_MODE,
    teams: [],
    talentBands: {},
    prestigeBands: {},
    q: '',
    talent: 0,
    prestige: 0,
    size: 0,
    experience: 0,
    geo: '',
    selectedId: null,
    drafts: [],
    hydrated: false,
  };

  var els = {};

  function playSound(filename) {
    try {
      var a = new Audio('/sounds/' + encodeURIComponent(filename));
      a.volume = 0.7;
      a.play().catch(function () {});
    } catch (e) {}
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function hideError() {
    if (!els.error) return;
    els.error.hidden = true;
    els.error.textContent = '';
  }

  function showError(message) {
    if (!els.error) return;
    els.error.textContent = message;
    els.error.hidden = false;
  }

  function showLoading(teamName) {
    if (!els.loading || !els.loadingBanner || !els.loadingSubline) return;
    els.loadingBanner.src =
      typeof getTeamAssetPath === 'function'
        ? getTeamAssetPath(teamName, 'banner_primary')
        : '/images/teams/general/general_banner_primary.jpg';
    els.loadingBanner.alt = teamName;
    els.loadingSubline.textContent = 'Getting ' + teamName + ' ready for the season...';
    els.loading.hidden = false;
  }

  function hideLoading() {
    if (els.loading) els.loading.hidden = true;
  }

  function teamById(objectId) {
    for (var i = 0; i < state.teams.length; i++) {
      if (String(state.teams[i].object_id) === String(objectId)) return state.teams[i];
    }
    return null;
  }

  function artForTeam(team) {
    var name = team.name || '';
    var path =
      typeof getTeamAssetPath === 'function'
        ? getTeamAssetPath(name, 'banner_card')
        : '/images/teams/general/general_banner_card.webp';
    return {
      src: path,
      fallback: '/images/teams/general/general_banner_card.webp',
    };
  }

  function conferenceNumber(team) {
    var c = Number(team.conference);
    return c >= 1 && c <= 16 ? c : 0;
  }

  function regionLetter(team) {
    if (team.region) return String(team.region);
    var c = conferenceNumber(team);
    if (!c) return '';
    return typeof TeamPicker !== 'undefined' && TeamPicker.regionFromConference
      ? TeamPicker.regionFromConference(c)
      : String.fromCharCode(64 + Math.ceil(c / 2));
  }

  function buildReturnUrl() {
    return window.location.pathname + window.location.search;
  }

  function syncStickyOffsets() {
    var mb = els.modeBanner;
    var vbh = 0;
    var mbh = mb && !mb.hidden ? mb.getBoundingClientRect().height : 0;
    document.documentElement.style.setProperty('--mbar-top', vbh + 'px');
    if (els.root) {
      els.root.style.setProperty('--fbar-top', mbh + 7 + 'px');
    }
    var barH = state.selectedId && els.actionBar ? els.actionBar.getBoundingClientRect().height : 0;
    document.body.style.paddingBottom = (barH ? barH + 26 : 26) + 'px';
  }

  function setBuilderMode(on) {
    state.builder = !!on && !TUTORIAL_MODE;
    if (els.modeBanner) els.modeBanner.hidden = !state.builder;
    if (els.root) els.root.classList.toggle('building', state.builder);
    if (els.title) {
      els.title.textContent = state.builder
        ? 'Whose place are you taking?'
        : TUTORIAL_MODE
          ? 'Pick Your Program'
          : 'Who are you coaching?';
    }
    if (els.subtitle) {
      if (state.builder) {
        els.subtitle.innerHTML =
          'Your program replaces one of these. You inherit <b>its conference, its region and its schedule</b>.';
      } else if (TUTORIAL_MODE) {
        els.subtitle.textContent =
          "This one's your onboarding — a single game to feel out the controls. Your real franchise comes next. Pick whoever speaks to you.";
      } else {
        els.subtitle.textContent = 'Take over one of the 128 programs below.';
      }
    }
    // Deep-linkable builder flag without losing home_slot / tutorial.
    try {
      var url = new URL(window.location.href);
      if (state.builder) url.searchParams.set('builder', '1');
      else url.searchParams.delete('builder');
      window.history.replaceState({}, '', url.pathname + url.search);
    } catch (e) {}
    // Draft card ↔ Open Team Builder exclusivity lives in renderDraftCard.
    if (TUTORIAL_MODE) {
      if (els.tbEntry) els.tbEntry.hidden = true;
      if (els.draftHost) {
        els.draftHost.hidden = true;
        els.draftHost.innerHTML = '';
      }
    } else {
      renderDraftCard();
    }
    renderActionBar();
    syncStickyOffsets();
  }

  function fillFilterSelects() {
    function fillTier(select, labels) {
      var html = '<option value="0">Any tier</option>';
      for (var i = 0; i < labels.length; i++) {
        html +=
          '<option value="' +
          (i + 1) +
          '">' +
          escapeHtml(labels[i]) +
          '</option>';
      }
      select.innerHTML = html;
    }
    fillTier(els.filterTalent, TIERS.talent);
    fillTier(els.filterPrestige, TIERS.prestige);
    fillTier(els.filterSize, TIERS.size);
    fillTier(els.filterExperience, TIERS.experience);

    var geos =
      typeof TeamPicker !== 'undefined' && TeamPicker.distinctGeographies
        ? TeamPicker.distinctGeographies()
        : [];
    var geoHtml = '<option value="">Anywhere</option>';
    for (var g = 0; g < geos.length; g++) {
      geoHtml += '<option value="' + escapeHtml(geos[g]) + '">' + escapeHtml(geos[g]) + '</option>';
    }
    els.filterGeo.innerHTML = geoHtml;
  }

  function teamMatches(team) {
    var oid = String(team.object_id);
    if (state.talent && Number(state.talentBands[oid]) !== state.talent) return false;
    if (state.prestige && Number(state.prestigeBands[oid]) !== state.prestige) return false;
    if (state.size && Number(team.height_band) !== state.size) return false;
    if (state.experience && Number(team.class_band) !== state.experience) return false;
    if (state.geo) {
      var conf = conferenceNumber(team);
      var list =
        typeof TeamPicker !== 'undefined' && TeamPicker.geographyForConference
          ? TeamPicker.geographyForConference(conf) || []
          : [];
      if (list.indexOf(state.geo) < 0) return false;
    }
    var needle = state.q.trim().toLowerCase();
    if (!needle) return true;
    var hay =
      String(team.name || '').toLowerCase() +
      ' conference ' +
      conferenceNumber(team) +
      ' ' +
      (typeof TeamPicker !== 'undefined' && TeamPicker.formatGeographyList
        ? TeamPicker.formatGeographyList(conferenceNumber(team))
        : ''
      ).toLowerCase();
    return hay.indexOf(needle) >= 0;
  }

  function activeFilterCount() {
    return (
      (state.q.trim() ? 1 : 0) +
      (state.talent ? 1 : 0) +
      (state.prestige ? 1 : 0) +
      (state.size ? 1 : 0) +
      (state.experience ? 1 : 0) +
      (state.geo ? 1 : 0)
    );
  }

  function renderDraftCard() {
    if (!els.draftHost) return;

    // Builder / tutorial: neither draft card nor (for tutorial) Open Team Builder.
    if (TUTORIAL_MODE || state.builder) {
      els.draftHost.hidden = true;
      els.draftHost.innerHTML = '';
      if (els.tbEntry) els.tbEntry.hidden = true;
      return;
    }

    var draft = state.drafts && state.drafts[0];
    var hasDraft = !!(draft && draft.replaced_object_id);

    // Mutually exclusive with Open Team Builder: draft present → card only.
    if (!hasDraft) {
      els.draftHost.hidden = true;
      els.draftHost.innerHTML = '';
      if (els.tbEntry) els.tbEntry.hidden = false;
      return;
    }

    els.draftHost.hidden = false;
    if (els.tbEntry) els.tbEntry.hidden = true;

    var slotTeam = teamById(draft.replaced_object_id);
    var programName =
      (draft.identity && draft.identity.name) ||
      (slotTeam && slotTeam.name) ||
      'Unfinished program';
    els.draftHost.innerHTML =
      '<div class="dc-t">' +
      '<div class="dc-h">' +
      escapeHtml(programName) +
      '</div>' +
      '<div class="dc-s">Unfinished · continue where you left off' +
      (slotTeam ? ' · taking ' + escapeHtml(slotTeam.name) + "'s place" : '') +
      '</div></div>' +
      '<div class="dc-a">' +
      '<button type="button" class="btn ghost" id="draft-discard">Discard</button>' +
      '<button type="button" class="btn" id="draft-continue">Continue</button>' +
      '</div>';

    var discardBtn = document.getElementById('draft-discard');
    var continueBtn = document.getElementById('draft-continue');
    if (discardBtn) {
      discardBtn.addEventListener('click', function () {
        discardDraft(draft.replaced_object_id);
      });
    }
    if (continueBtn) {
      continueBtn.addEventListener('click', function () {
        resumeDraft(draft);
      });
    }
  }

  function resumeDraft(draft) {
    var params = new URLSearchParams();
    params.set('replaced_object_id', draft.replaced_object_id);
    params.set('draft_id', draft.draft_id || '');
    params.set('chapter', draft.chapter || 'identity');
    if (draft.build_mode) params.set('mode', draft.build_mode);
    if (HOME_SLOT_PARAM) params.set('home_slot', String(HOME_SLOT_PARAM));
    window.location.href = '/team-builder.html?' + params.toString();
  }

  async function discardDraft(replacedObjectId) {
    try {
      var res = await fetch(
        API_CONFIG.buildUrl(
          '/franchise/team-builder/drafts/' + encodeURIComponent(replacedObjectId)
        ),
        { method: 'DELETE', headers: API_CONFIG.getAuthHeaders() }
      );
      if (!res.ok) throw new Error('Could not discard draft');
      state.drafts = (state.drafts || []).filter(function (d) {
        return String(d.replaced_object_id) !== String(replacedObjectId);
      });
      renderDraftCard();
    } catch (err) {
      showError(err.message || 'Could not discard draft');
    }
  }

  function renderGrid() {
    if (!els.grid) return;
    var matchCount = 0;
    var html = '';
    for (var conf = 1; conf <= 16; conf++) {
      var list = state.teams.filter(function (t) {
        return conferenceNumber(t) === conf;
      });
      list.sort(function (a, b) {
        var ta = Number(a.total_player_attrs) || 0;
        var tb = Number(b.total_player_attrs) || 0;
        if (tb !== ta) return tb - ta;
        return String(a.name || '').localeCompare(String(b.name || ''));
      });
      var hit = 0;
      var cards = '';
      for (var i = 0; i < list.length; i++) {
        var team = list[i];
        var ok = teamMatches(team);
        if (ok) {
          hit++;
          matchCount++;
        }
        var oid = String(team.object_id);
        var art = artForTeam(team);
        var talent = Number(state.talentBands[oid]) || 5;
        var prestige = Number(state.prestigeBands[oid]) || 5;
        var size = Number(team.height_band) || 5;
        var exp = Number(team.class_band) || 5;
        var selected = state.selectedId && String(state.selectedId) === oid;
        cards +=
          '<button type="button" class="pg' +
          (ok ? '' : ' out') +
          (selected ? ' sel' : '') +
          '" data-oid="' +
          escapeHtml(oid) +
          '"' +
          (ok ? '' : ' aria-disabled="true"') +
          '>' +
          '<div class="pg-art"><img src="' +
          escapeHtml(art.src) +
          '" alt="' +
          escapeHtml(team.name) +
          '" loading="lazy" decoding="async" data-fallback="' +
          escapeHtml(art.fallback) +
          '"></div>' +
          '<div class="pg-b"><div class="pg-nm">' +
          escapeHtml(team.name) +
          '</div><div class="pg-t">' +
          '<div class="tr' +
          (talent === 1 ? ' top1t' : '') +
          '"><b>Tlnt</b><span>' +
          escapeHtml(TIERS.talent[talent - 1] || '') +
          '</span></div>' +
          '<div class="tr' +
          (prestige === 1 ? ' top1' : '') +
          '"><b>Prstg</b><span>' +
          escapeHtml(TIERS.prestige[prestige - 1] || '') +
          '</span></div>' +
          '<div class="tr"><b>Size</b><span>' +
          escapeHtml(TIERS.size[size - 1] || '') +
          '</span></div>' +
          '<div class="tr"><b>Exp</b><span>' +
          escapeHtml(TIERS.experience[exp - 1] || '') +
          '</span></div>' +
          '</div></div>' +
          (selected ? '<div class="pg-check">✓</div>' : '') +
          '<div class="pg-more">' +
          '<div class="r"><b>Talent</b><span>' +
          escapeHtml(String(team.total_player_attrs || 0)) +
          ' pts</span></div>' +
          '<div class="r"><b>Prestige</b><span>' +
          escapeHtml(String(team.prestige || 0)) +
          '</span></div>' +
          '<div class="r"><b>Conference</b><span>' +
          conf +
          ' · Region ' +
          escapeHtml(regionLetter(team)) +
          '</span></div>' +
          '<div class="r"><b>Mascot</b><span>' +
          escapeHtml(team.mascot || '—') +
          '</span></div>' +
          '</div></button>';
      }
      var geo =
        typeof TeamPicker !== 'undefined' && TeamPicker.formatGeographyList
          ? TeamPicker.formatGeographyList(conf)
          : '';
      html +=
        '<div class="conf" data-conf="' +
        conf +
        '"><div class="conf-k"><h2>Conference ' +
        conf +
        '</h2><span class="cid">Region ' +
        escapeHtml(regionLetter(list[0] || { region: '' })) +
        '</span><span class="cgeo">' +
        escapeHtml(geo) +
        '</span><i></i><span class="cn">' +
        hit +
        ' of ' +
        list.length +
        '</span></div><div class="row">' +
        cards +
        '</div></div>';
    }
    els.grid.innerHTML = html;
    if (els.matchCount) els.matchCount.textContent = String(matchCount);
    var active = activeFilterCount();
    if (els.filterClear) {
      els.filterClear.hidden = active === 0;
      els.filterClear.textContent = active ? 'Clear ' + active : 'Clear';
    }
    ['talent', 'prestige', 'size', 'experience', 'geo'].forEach(function (key) {
      var wrap = document.querySelector('.fsel[data-filter="' + key + '"]');
      if (!wrap) return;
      var on =
        key === 'geo' ? !!state.geo : !!state[key === 'size' ? 'size' : key === 'experience' ? 'experience' : key];
      wrap.classList.toggle('on', on);
    });
  }

  function renderActionBar() {
    if (!els.actionBar || !els.actionInner) return;
    var team = state.selectedId ? teamById(state.selectedId) : null;
    if (!team) {
      els.actionBar.classList.remove('up');
      els.actionBar.setAttribute('aria-hidden', 'true');
      els.actionInner.innerHTML = '';
      syncStickyOffsets();
      return;
    }
    var oid = String(team.object_id);
    var art = artForTeam(team);
    var talent = Number(state.talentBands[oid]) || 5;
    var prestige = Number(state.prestigeBands[oid]) || 5;
    var size = Number(team.height_band) || 5;
    var exp = Number(team.class_band) || 5;
    var headline = state.builder
      ? 'You are taking <em>' + escapeHtml(team.name) + "</em>'s place"
      : escapeHtml(team.name) + ' <em>' + escapeHtml(team.mascot || '') + '</em>';
    var cta = state.builder ? 'Take This Slot' : 'Enter Franchise';
    var ctaClass = state.builder ? 'btn lg' : 'btn lg grn';
    els.actionInner.innerHTML =
      '<div class="ab-art"><img src="' +
      escapeHtml(art.src) +
      '" alt="" data-fallback="' +
      escapeHtml(art.fallback) +
      '"></div>' +
      '<div class="ab-t"><div class="ab-h">' +
      headline +
      '</div><div class="ab-s"><b>Conference ' +
      conferenceNumber(team) +
      ' · Region ' +
      escapeHtml(regionLetter(team)) +
      '</b> · ' +
      escapeHtml(TIERS.prestige[prestige - 1] || '') +
      ' · ' +
      escapeHtml(TIERS.talent[talent - 1] || '') +
      '</div></div>' +
      '<div class="ab-f">' +
      '<div><div class="k">Prestige</div><div class="v">' +
      escapeHtml(TIERS.prestige[prestige - 1] || '') +
      '</div></div>' +
      '<div><div class="k">Talent</div><div class="v">' +
      escapeHtml(TIERS.talent[talent - 1] || '') +
      '</div></div>' +
      '<div><div class="k">Size</div><div class="v">' +
      escapeHtml(TIERS.size[size - 1] || '') +
      '</div></div>' +
      '<div><div class="k">Experience</div><div class="v">' +
      escapeHtml(TIERS.experience[exp - 1] || '') +
      '</div></div>' +
      '</div>' +
      '<button type="button" class="btn ghost" id="ab-scout">Scout</button>' +
      '<button type="button" class="btn ghost" id="ab-clear">Clear</button>' +
      '<button type="button" class="' +
      ctaClass +
      '" id="ab-primary">' +
      escapeHtml(cta) +
      '</button>';
    els.actionBar.classList.add('up');
    els.actionBar.setAttribute('aria-hidden', 'false');
    var scoutBtn = document.getElementById('ab-scout');
    var clearBtn = document.getElementById('ab-clear');
    var primaryBtn = document.getElementById('ab-primary');
    if (scoutBtn) {
      scoutBtn.addEventListener('click', function () {
        scoutTeam(team);
      });
    }
    if (clearBtn) {
      clearBtn.addEventListener('click', function () {
        state.selectedId = null;
        renderGrid();
        renderActionBar();
      });
    }
    if (primaryBtn) {
      primaryBtn.addEventListener('click', function () {
        if (state.builder) takeThisPlace(team);
        else if (TUTORIAL_MODE) selectTutorialTeam(team);
        else selectTeam(team);
      });
    }
    syncStickyOffsets();
  }

  function takeThisPlace(team) {
    playSound('click-beep.wav');
    var params = new URLSearchParams();
    params.set('replaced_object_id', team.object_id);
    params.set('chapter', 'identity');
    if (HOME_SLOT_PARAM) params.set('home_slot', String(HOME_SLOT_PARAM));
    window.location.href = '/team-builder.html?' + params.toString();
  }

  async function selectTeam(team) {
    var name = team && team.name ? team.name : team;
    hideError();
    showLoading(name);
    try {
      var headers = { ...API_CONFIG.getAuthHeaders(), 'Content-Type': 'application/json' };
      var payload = { team_name: name };
      if (HOME_SLOT_PARAM) payload.home_slot = HOME_SLOT_PARAM;
      var res = await fetch(API_CONFIG.buildUrl('/franchise/select-team?profile=1'), {
        method: 'POST',
        headers: headers,
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        var msg = 'Unable to start franchise';
        try {
          var errBody = await res.json();
          if (errBody.detail) msg = errBody.detail;
        } catch (_) {}
        throw new Error(msg);
      }
      var data = await res.json();
      if (window.FranchiseLS && data.franchise_id) {
        window.FranchiseLS.clearBareKeys();
        window.FranchiseLS.setTeamContext(data.franchise_id, { teamName: name });
      }
      window.location.href =
        './franchise-command-center.html?franchise_id=' + encodeURIComponent(data.franchise_id);
    } catch (err) {
      console.error(err);
      hideLoading();
      showError(err.message || 'Unable to start franchise');
    }
  }

  async function selectTutorialTeam(team) {
    var name = team && team.name ? team.name : team;
    hideError();
    try {
      var advanceRes = await fetch(API_CONFIG.buildUrl('/api/auth/tutorial-advance'), {
        method: 'POST',
        headers: { ...API_CONFIG.getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ step: 'username', team_pick: name }),
      });
      if (!advanceRes.ok) throw new Error('Could not start tutorial');
    } catch (err) {
      console.error('[tutorial] team-pick advance failed:', err);
      showError(err.message || 'Could not start tutorial');
      return;
    }
    var mascot = (team && team.mascot) || name;
    var existingUsername = '';
    try {
      var raw = localStorage.getItem('auth_user');
      if (raw) existingUsername = (JSON.parse(raw) || {}).username || '';
    } catch (_) {}
    var mod = await import('/js/shared/usernameModal.js');
    mod.openUsernameModal({
      teamName: name,
      mascot: mascot,
      initialUsername: existingUsername,
      onSuccess: async function () {
        if (window.PageLoadOverlay && window.PageLoadOverlay.show) {
          window.PageLoadOverlay.show();
        }
        try {
          await fetch(API_CONFIG.buildUrl('/api/auth/tutorial-advance'), {
            method: 'POST',
            headers: { ...API_CONFIG.getAuthHeaders(), 'Content-Type': 'application/json' },
            body: JSON.stringify({ step: 'situation' }),
          });
        } catch (e) {
          console.warn('[tutorial] could not advance to situation step:', e);
        }
        window.location.href = '/tutorial-situation.html';
      },
    });
  }

  function scoutTeam(team) {
    var name = team && team.name ? team.name : team;
    playSound('click-beep.wav');
    var scoutParams = new URLSearchParams();
    scoutParams.set('team_name', name);
    scoutParams.set('return_url', buildReturnUrl());
    if (TUTORIAL_MODE) scoutParams.set('mode', 'tutorial');
    window.location.href = '/team-roster-view.html?' + scoutParams.toString();
  }

  function bindFilters() {
    els.filterSearch.addEventListener('input', function () {
      state.q = els.filterSearch.value || '';
      renderGrid();
    });
    function bindSelect(el, key) {
      el.addEventListener('change', function () {
        state[key] = key === 'geo' ? el.value || '' : parseInt(el.value, 10) || 0;
        if (state.selectedId) {
          var t = teamById(state.selectedId);
          if (t && !teamMatches(t)) {
            state.selectedId = null;
            renderActionBar();
          }
        }
        renderGrid();
      });
    }
    bindSelect(els.filterTalent, 'talent');
    bindSelect(els.filterPrestige, 'prestige');
    bindSelect(els.filterSize, 'size');
    bindSelect(els.filterExperience, 'experience');
    bindSelect(els.filterGeo, 'geo');
    els.filterClear.addEventListener('click', function () {
      state.q = '';
      state.talent = 0;
      state.prestige = 0;
      state.size = 0;
      state.experience = 0;
      state.geo = '';
      els.filterSearch.value = '';
      els.filterTalent.value = '0';
      els.filterPrestige.value = '0';
      els.filterSize.value = '0';
      els.filterExperience.value = '0';
      els.filterGeo.value = '';
      renderGrid();
    });
  }

  function bindGridClicks() {
    els.grid.addEventListener('click', function (ev) {
      var img = ev.target.closest('img[data-fallback]');
      if (img && img.tagName === 'IMG' && img.dataset.fallback) {
        // handled via error below
      }
      var btn = ev.target.closest('button.pg');
      if (!btn || btn.classList.contains('out')) return;
      var oid = btn.getAttribute('data-oid');
      if (!oid) return;
      playSound('click-tiny.wav');
      state.selectedId = oid;
      renderGrid();
      renderActionBar();
    });
    els.grid.addEventListener(
      'error',
      function (ev) {
        var img = ev.target;
        if (img && img.tagName === 'IMG' && img.dataset.fallback && img.src.indexOf('general_') === -1) {
          img.src = img.dataset.fallback;
        }
      },
      true
    );
  }

  async function loadTeams() {
    if (typeof TeamPicker === 'undefined' || !TeamPicker.fetchTeams) {
      throw new Error('Team picker failed to load. Refresh and try again.');
    }
    var teams = await TeamPicker.fetchTeams();
    state.teams = teams || [];
    state.talentBands = TeamPicker.assignRankBands(state.teams, 'total_player_attrs') || {};
    state.prestigeBands = TeamPicker.assignRankBands(state.teams, 'prestige') || {};
  }

  async function loadDrafts() {
    if (TUTORIAL_MODE) {
      state.drafts = [];
      return;
    }
    try {
      var res = await fetch(API_CONFIG.buildUrl('/franchise/team-builder/drafts'), {
        headers: API_CONFIG.getAuthHeaders(),
      });
      if (!res.ok) {
        state.drafts = [];
        return;
      }
      var data = await res.json();
      state.drafts = (data && data.drafts) || [];
    } catch (e) {
      state.drafts = [];
    }
  }

  document.addEventListener('DOMContentLoaded', async function () {
    els = {
      root: document.getElementById('claim-root'),
      title: document.getElementById('page-title'),
      subtitle: document.getElementById('page-subtitle'),
      modeBanner: document.getElementById('mode-banner'),
      tbEntry: document.getElementById('team-builder-entry'),
      openTb: document.getElementById('open-team-builder'),
      cancelTb: document.getElementById('tb-cancel-builder'),
      draftHost: document.getElementById('unfinished-draft'),
      error: document.getElementById('team-select-error'),
      grid: document.getElementById('conference-grid'),
      matchCount: document.getElementById('match-count'),
      filterSearch: document.getElementById('filter-search'),
      filterTalent: document.getElementById('filter-talent'),
      filterPrestige: document.getElementById('filter-prestige'),
      filterSize: document.getElementById('filter-size'),
      filterExperience: document.getElementById('filter-experience'),
      filterGeo: document.getElementById('filter-geo'),
      filterClear: document.getElementById('filter-clear'),
      actionBar: document.getElementById('action-bar'),
      actionInner: document.getElementById('action-bar-inner'),
      loading: document.getElementById('team-select-loading'),
      loadingBanner: document.getElementById('team-select-loading-banner'),
      loadingSubline: document.getElementById('team-select-loading-subline'),
      backLink: document.getElementById('team-select-back-link'),
    };

    try {
      var lobbyMusic = new Audio('/sounds/crossover-21738.mp3');
      lobbyMusic.loop = true;
      lobbyMusic.volume = 0.4;
      lobbyMusic.play().catch(function () {});
    } catch (e) {}

    // Hydration gate — protects non-TB users on this rewritten entry path too.
    if (typeof ensureTeamBuilderChromeSnapshot === 'function') {
      try {
        await ensureTeamBuilderChromeSnapshot();
      } catch (e) {
        console.warn('[franchise-select] chrome snapshot failed', e);
      }
    }
    state.hydrated = true;

    fillFilterSelects();
    bindFilters();
    bindGridClicks();
    window.addEventListener('resize', syncStickyOffsets);

    if (els.openTb) {
      els.openTb.addEventListener('click', function () {
        // Same confirm SFX as the FCC green Advance button.
        playSound('confirm-1-lowervol.wav');
        setBuilderMode(true);
      });
    }
    if (els.cancelTb) {
      els.cancelTb.addEventListener('click', function () {
        state.selectedId = null;
        setBuilderMode(false);
        renderGrid();
        renderDraftCard();
      });
    }

    if (TUTORIAL_MODE) {
      if (els.backLink) els.backLink.style.display = 'none';
      if (els.tbEntry) els.tbEntry.hidden = true;
      import('/js/shared/tutorialProgressThread.js')
        .then(function (m) {
          m.mountTutorialProgress('program');
        })
        .catch(function (e) {
          console.warn('[tutorial] could not mount progress thread:', e);
        });
    } else if (els.backLink) {
      els.backLink.addEventListener('click', function (event) {
        event.preventDefault();
        window.location.href = '/mode-select.html';
      });
    }

    setBuilderMode(state.builder);

    try {
      await loadTeams();
      await loadDrafts();
      renderDraftCard();
      renderGrid();
      renderActionBar();
      syncStickyOffsets();
    } catch (err) {
      console.error(err);
      showError(err.message || 'Unable to load programs');
    }
  });
})();
