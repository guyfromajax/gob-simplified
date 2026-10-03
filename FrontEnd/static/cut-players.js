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
  var selectedIds = new Set();
  var players = [];
  var cutCount = 0;
  var allowLeave = false;

  function playSound(filename) {
    import('/js/shared/uiSfx.js').then(function (m) { m.playSfx(filename, 0.7); }).catch(function () {});
  }

  function buildFccUrl() {
    if (typeof resolveFranchiseLockerRoomUrl === 'function') {
      return resolveFranchiseLockerRoomUrl({
        params: urlParams,
        franchiseId: franchiseId,
        teamId: teamId
      });
    }
    var params = emptyParams();
    params.set('mode', 'franchise');
    if (franchiseId) params.set('franchise_id', franchiseId);
    if (teamId) params.set('team_id', teamId);
    return '/franchise-command-center.html?' + params.toString();
  }

  function closeModal() {
    var backdrop = document.getElementById('cut-modal-backdrop');
    if (!backdrop) return;
    backdrop.classList.remove('is-visible');
    backdrop.setAttribute('aria-hidden', 'true');
  }

  function showModal(config) {
    var backdrop = document.getElementById('cut-modal-backdrop');
    if (backdrop && backdrop.parentNode !== document.body) {
      document.body.appendChild(backdrop);
    }
    var accent = document.getElementById('cut-modal-accent');
    var title = document.getElementById('cut-modal-title');
    var message = document.getElementById('cut-modal-message');
    var actions = document.getElementById('cut-modal-actions');
    var pulse = document.getElementById('cut-modal-pulse');
    title.textContent = config.title || 'Assign Practice Squad';
    title.classList.toggle('is-centered', !!config.centerTitle);
    message.textContent = config.message || '';
    message.hidden = !config.message;
    if (accent) {
      if (config.accent === false || config.accent === 'neutral') {
        accent.className = 'gob-modal-accent is-neutral';
      } else {
        accent.className = 'gob-modal-accent';
        if (config.accent) accent.classList.add(config.accent);
      }
    }
    if (pulse) {
      var showPulse = !!config.pulse;
      pulse.hidden = !showPulse;
      pulse.setAttribute('aria-hidden', showPulse ? 'false' : 'true');
    }
    actions.innerHTML = '';
    var actionList = config.actions || [];
    actions.hidden = actionList.length === 0;
    actionList.forEach(function (action) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = action.variant === 'gob-modal-btn-primary'
        ? 'gob-modal-btn-primary'
        : 'gob-modal-btn-secondary';
      if (action.neutral) btn.classList.add('is-neutral');
      btn.textContent = action.label;
      btn.disabled = !!action.disabled;
      btn.addEventListener('click', function () {
        if (action.onClick) {
          action.onClick();
          return;
        }
        closeModal();
      });
      actions.appendChild(btn);
    });
    backdrop.classList.add('is-visible');
    backdrop.setAttribute('aria-hidden', 'false');
  }

  function setSubmitBusy(busy) {
    var submitBtn = document.getElementById('submit-btn');
    if (!submitBtn) return;
    if (busy) {
      submitBtn.disabled = true;
      submitBtn.classList.add('is-dead');
      return;
    }
    updateStatus();
  }

  function formatAttr(attrs, key) {
    var d = window.GOB_AttributeDisplay.displayAttr(window.GOB_AttributeDisplay.rawAttr(attrs, key));
    return d == null ? 0 : d;
  }

  function getBestPosition(positionRatings) {
    var bestPos = '--';
    var bestRating = null;
    Object.entries(positionRatings || {}).forEach(function (entry) {
      var pos = entry[0];
      var rating = entry[1];
      if (typeof rating === 'number' && (bestRating === null || rating > bestRating)) {
        bestPos = pos;
        bestRating = rating;
      }
    });
    return {
      pos: bestPos,
      rating: bestRating
    };
  }

  function formatHeight(heightInches) {
    var total = Number(heightInches || 0);
    if (!total) return '--';
    var feet = Math.floor(total / 12);
    var inches = total % 12;
    return feet + "'" + inches + '"';
  }

  function updateSubmitReason(selectedCount) {
    var reason = document.getElementById('cut-submit-reason');
    var submitBtn = document.getElementById('submit-btn');
    if (!reason) return;
    var delta = cutCount - selectedCount;
    var copy = '';
    if (delta > 0) copy = 'Assign ' + delta + ' more to the practice squad';
    else if (delta < 0) copy = 'Remove ' + (-delta);
    reason.textContent = copy;
    reason.hidden = !copy;
    if (submitBtn) {
      if (copy) submitBtn.setAttribute('title', copy);
      else submitBtn.removeAttribute('title');
    }
  }

  function updateStatus() {
    var status = document.getElementById('cut-status');
    var selectedCount = selectedIds.size;
    var submitBtn = document.getElementById('submit-btn');
    status.textContent = 'You need to assign ' + cutCount + ' player' + (cutCount === 1 ? '' : 's') + ' to the practice squad. Selected: ' + selectedCount + '.';
    var active = selectedCount === cutCount;
    submitBtn.disabled = !active;
    submitBtn.classList.toggle('is-dead', !active);
    updateSubmitReason(selectedCount);
  }

  function renderTable() {
    var tbody = document.getElementById('cut-players-body');
    tbody.innerHTML = '';
    players.forEach(function (player) {
      var tr = document.createElement('tr');
      var attrs = player.attributes || {};
      var nameTd = document.createElement('td');
      var link = document.createElement('a');
      link.href = '/player-detail.html?id=' + encodeURIComponent(player._id) + '&mode=franchise&franchise_id=' + encodeURIComponent(franchiseId || '');
      link.setAttribute('data-return', '');
      link.textContent = player.name;
      link.className = 'cut-player-name-link';
      nameTd.appendChild(link);
      if (player.hasPlayingTimePromise) {
        var ptp = document.createElement('span');
        ptp.textContent = 'PTP';
        ptp.className = 'cut-player-badge is-ptp';
        nameTd.appendChild(ptp);
      }
      if (player.isGraduating) {
        var gr = document.createElement('span');
        gr.textContent = 'GR';
        gr.className = 'cut-player-badge is-graduating';
        nameTd.appendChild(gr);
      }
      tr.appendChild(nameTd);

      function addCell(content, className) {
        var td = document.createElement('td');
        td.textContent = content;
        if (className) td.className = className;
        tr.appendChild(td);
      }

      addCell(player.pos || '--');
      addCell(typeof GOB_PlayerYear !== 'undefined'
        ? GOB_PlayerYear.formatDisplay(player.year)
        : (typeof yearMap !== 'undefined' && player.year
          ? (yearMap[String(player.year).toLowerCase()] || String(player.year).toUpperCase())
          : (player.year || '--')));
      addCell(player.height || '--');
      addCell(player.weight || '--', 'wt');
      // Six pairs, the roster's order: SC SH, ID OD, PS BH, RB ST, AG ND, IQ FT.
      ['SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'ST', 'AG', 'ND', 'IQ', 'FT'].forEach(function (key, index) {
        var td = document.createElement('td');
        td.className = index % 2 ? 'gend' : 'gstart';
        var value = document.createElement('span');
        value.className = 'ak';
        value.textContent = formatAttr(attrs, key);
        td.appendChild(value);
        tr.appendChild(td);
      });
      var rtCell = document.createElement('td');
      rtCell.textContent = player.highestRT != null
        ? formatRtWithPotentialDisplay(player.highestRT, player.potentialRtRatcheted)
        : '-';
      if (typeof window.getRtBucketClass === 'function') {
        rtCell.className = window.getRtBucketClass(player.highestRT);
      }
      rtCell.setAttribute('data-tooltip', 'current/potential');
      rtCell.setAttribute('title', 'current/potential');
      tr.appendChild(rtCell);

      var checkTd = document.createElement('td');
      checkTd.className = 'cut-player-checkbox-cell';
      var checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.className = 'cut-player-checkbox';
      checkbox.checked = selectedIds.has(player._id);
      checkbox.addEventListener('change', function () {
        playSound('click-tiny.wav');
        if (checkbox.checked) selectedIds.add(player._id);
        else selectedIds.delete(player._id);
        updateStatus();
      });
      checkTd.appendChild(checkbox);
      tr.appendChild(checkTd);
      tbody.appendChild(tr);
    });
    updateStatus();
    if (typeof window.initAttributeTooltips === 'function') {
      window.initAttributeTooltips(document.getElementById('cut-players-table'), ['th', 'td']);
    }
  }

  function navigateBack() {
    allowLeave = true;
    var url = buildFccUrl();
    if (window.GOBNav) window.GOBNav.back(url);
    else window.location.replace(url);
  }

  function attemptLeave() {
    if (!selectedIds.size) {
      navigateBack();
      return;
    }
    showModal({
      title: 'Leave Without Assigning?',
      message: 'You have selected players for the practice squad but have not submitted them. Are you sure you want to leave?',
      accent: 'neutral',
      actions: [
        { label: 'Stay', variant: 'gob-modal-btn-primary', neutral: true },
        { label: 'Leave', variant: 'gob-modal-btn-secondary', onClick: navigateBack }
      ]
    });
  }

  function submitCuts() {
    if (selectedIds.size !== cutCount) return;
    // Title and the two buttons only: the picks are on the page behind the dialog.
    showModal({
      title: 'Confirm Practice Squad',
      accent: 'neutral',
      actions: [
        { label: 'Cancel', variant: 'gob-modal-btn-secondary' },
        {
          label: 'Confirm',
          variant: 'gob-modal-btn-primary',
          onClick: function () {
            setSubmitBusy(true);
            showModal({
              title: 'Assigning Practice Squad',
              centerTitle: true,
              accent: 'neutral',
              pulse: true,
              actions: []
            });
            fetch(API_CONFIG.buildUrl('/franchise/cut-players'), {
              method: 'POST',
              headers: { ...API_CONFIG.getAuthHeaders(), 'Content-Type': 'application/json' },
              body: JSON.stringify({
                franchise_id: franchiseId,
                player_ids: Array.from(selectedIds)
              })
            })
              .then(function (res) {
                if (!res.ok) throw new Error('Failed to assign practice squad');
                return res.json();
              })
              .then(function () {
                playSound('confirm-1-lowervol.wav');
                allowLeave = true;
                if (window.GOBNav && window.GOBNav.exitFlow) window.GOBNav.exitFlow(buildFccUrl());
                else if (window.GOBNav) window.GOBNav.replace(buildFccUrl());
                else window.location.replace(buildFccUrl());
              })
              .catch(function (err) {
                console.error(err);
                setSubmitBusy(false);
                showModal({
                  title: 'Assignment Failed',
                  message: 'Unable to assign players to the practice squad.',
                  actions: [
                    { label: 'Close', variant: 'gob-modal-btn-secondary' },
                    { label: 'Back To Locker Room', variant: 'gob-modal-btn-primary', onClick: navigateBack }
                  ]
                });
              });
          }
        }
      ]
    });
  }

  /* First paint: the page stays behind the shared loader (and hidden, see the
     is-loading rule in cut-players.css) until the roster and the cut count are in. */
  function liftLoading() {
    document.documentElement.classList.remove('is-loading');
    if (window.PageLoadOverlay && window.PageLoadOverlay.hide) window.PageLoadOverlay.hide();
  }

  function loadData() {
    var profileQ = urlParams.get('cc_profile') === '1' ? '&profile=1' : '';
    Promise.all([
      fetch(API_CONFIG.buildUrl('/franchise/command-center/data') + '?franchise_id=' + encodeURIComponent(franchiseId) + profileQ, { headers: API_CONFIG.getAuthHeaders() })
        .then(function (res) { return res.ok ? res.json() : null; }),
      fetch(API_CONFIG.buildUrl('/roster/' + encodeURIComponent(teamId)) + '?franchise_id=' + encodeURIComponent(franchiseId) + profileQ, { headers: API_CONFIG.getAuthHeaders() })
        .then(function (res) {
          if (!res.ok) throw new Error('Failed to load roster');
          return res.json();
        })
    ]).then(function (results) {
      var topData = results[0] || {};
      var roster = results[1] || {};
      cutCount = Number(topData.cut_count || 0);
      var pool = (roster.players || []).slice();
      players = pool.map(function (player) {
        var positionRatings = player.position_ratings || {};
        var best = getBestPosition(positionRatings);
        return {
          _id: player._id,
          name: player.name || [player.first_name || '', player.last_name || ''].join(' ').trim(),
          pos: best.pos,
          highestRT: best.rating,
          potentialRtRatcheted: player.potential_rt_ratcheted,
          year: (typeof GOB_PlayerYear !== 'undefined'
            ? GOB_PlayerYear.formatDisplay(player.year)
            : (typeof yearMap !== 'undefined' && player.year
              ? (yearMap[String(player.year).toLowerCase()] || String(player.year).toUpperCase())
              : (player.year || '--'))),
          height: formatHeight(player.height),
          weight: player.weight || '--',
          attributes: player.attributes || {},
          hasPlayingTimePromise: !!player.has_playing_time_promise,
          isGraduating: !!player.is_graduating
        };
      }).sort(function (a, b) {
        return Number(b.highestRT || -1) - Number(a.highestRT || -1);
      });
      renderTable();
      liftLoading();
      if (!topData.cut_required || cutCount <= 0) {
        showModal({
          title: 'No Cuts Required',
          message: 'Your roster is already at the legal 12-player limit.',
          // Not an error and not a save: neutral accent, neutral navigation button.
          accent: 'neutral',
          actions: [{
            label: 'Back To Locker Room',
            variant: 'gob-modal-btn-secondary',
            onClick: navigateBack
          }]
        });
      }
    }).catch(function (err) {
      console.error(err);
      liftLoading();
      showModal({
        title: 'Assign Practice Squad',
        message: 'Unable to load practice squad assignment data.',
        accent: 'neutral',
        actions: [{ label: 'Back To Locker Room', variant: 'gob-modal-btn-secondary', onClick: navigateBack }]
      });
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.getElementById('back-btn').addEventListener('click', attemptLeave);
    document.getElementById('submit-btn').addEventListener('click', function (event) {
      var btn = event.currentTarget;
      if (!btn || btn.disabled || btn.classList.contains('is-dead')) return;
      submitCuts();
    });
    window.addEventListener('beforeunload', function (e) {
      if (allowLeave || !selectedIds.size) return;
      e.preventDefault();
      e.returnValue = '';
    });
  });
  window.addEventListener('pageshow', function () {
    loadData();
  });
})();
