(function () {
  'use strict';

  var urlParams = new URLSearchParams(window.location.search);
  var franchiseId = urlParams.get('franchise_id');
  var teamId = urlParams.get('team_id');
  var selectedIds = new Set();
  var players = [];
  var cutCount = 0;
  var allowLeave = false;
  // mode 'cut' = week-35 real cuts (any number, FPD deleted). Default = training-squad assignment.
  var isCutMode = urlParams.get('mode') === 'cut';
  var nextUrl = urlParams.get('next_url');

  function playSound(filename) {
    try {
      var base = (typeof API_CONFIG !== 'undefined' && API_CONFIG.buildStaticPath) ? API_CONFIG.buildStaticPath('/sounds/') : '/sounds/';
      var a = new Audio(base + encodeURIComponent(filename));
      a.volume = 0.7;
      a.play().catch(function () {});
    } catch (e) {}
  }

  function buildFccUrl() {
    if (typeof resolveFranchiseLockerRoomUrl === 'function') {
      return resolveFranchiseLockerRoomUrl({
        params: urlParams,
        franchiseId: franchiseId,
        teamId: teamId
      });
    }
    var params = new URLSearchParams();
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
      accent.className = 'gob-modal-accent';
      accent.classList.add(config.accent || 'is-red');
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
      btn.textContent = action.label;
      btn.disabled = !!action.disabled;
      btn.addEventListener('click', function () {
        // Dismiss-only actions close here. Actions with onClick own the next
        // step (replace modal, navigate, etc.) so Confirm is not dumped back
        // onto the assign table while the POST is in flight.
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
    var rawVal = (attrs || {})['anchor_' + key];
    if (rawVal == null) rawVal = (attrs || {})[key] || 0;
    return Math.floor(Number(rawVal || 0) / 10);
  }

  function formatNames(names) {
    if (!names.length) return '';
    if (names.length === 1) return names[0];
    if (names.length === 2) return names[0] + ' and ' + names[1];
    return names.slice(0, -1).join(', ') + ', and ' + names[names.length - 1];
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

  function updateStatus() {
    var status = document.getElementById('cut-status');
    var selectedCount = selectedIds.size;
    var submitBtn = document.getElementById('submit-btn');
    if (isCutMode) {
      // Any number (including 0) may be cut; submit is always enabled.
      status.textContent = 'Select any players to cut — they will be lost forever. Selected: ' + selectedCount + '.';
      submitBtn.disabled = false;
      submitBtn.classList.remove('is-dead');
      return;
    }
    status.textContent = 'You need to assign ' + cutCount + ' player' + (cutCount === 1 ? '' : 's') + ' to the practice squad. Selected: ' + selectedCount + '.';
    var active = selectedCount === cutCount;
    submitBtn.disabled = !active;
    submitBtn.classList.toggle('is-dead', !active);
  }

  function renderTable() {
    var tbody = document.getElementById('cut-players-body');
    tbody.innerHTML = '';
    players.forEach(function (player) {
      var tr = document.createElement('tr');
      var attrs = player.attributes || {};
      var nameTd = document.createElement('td');
      var link = document.createElement('a');
      link.href = '/player-detail.html?id=' + encodeURIComponent(player._id) + '&mode=franchise&franchise_id=' + encodeURIComponent(franchiseId || '') + '&return_url=' + encodeURIComponent(getCurrentRelativeUrl());
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
      addCell(player.weight || '--');
      ['SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'AG', 'ST', 'ND', 'IQ', 'FT'].forEach(function (key) {
        addCell(formatAttr(attrs, key));
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
    window.location.href = buildFccUrl();
  }

  function attemptLeave() {
    if (!selectedIds.size) {
      navigateBack();
      return;
    }
    showModal({
      title: 'Leave Without Assigning?',
      message: 'You have selected players for the practice squad but have not submitted them. Are you sure you want to leave?',
      accent: 'is-red',
      actions: [
        { label: 'Stay', variant: 'gob-modal-btn-primary' },
        { label: 'Leave', variant: 'gob-modal-btn-secondary', onClick: navigateBack }
      ]
    });
  }

  function goNext() {
    allowLeave = true;
    window.location.href = nextUrl || buildFccUrl();
  }

  function submitCuts() {
    if (isCutMode) { submitFinalCuts(); return; }
    if (selectedIds.size !== cutCount) return;
    var namesInOrder = players.filter(function (player) {
      return selectedIds.has(player._id);
    }).map(function (player) {
      return player.name;
    });
    showModal({
      title: 'Confirm Practice Squad',
      message: 'You are going to assign ' + formatNames(namesInOrder) + ' to the practice squad. They will be ineligible to play this season, but available for training camp next season. Proceed?',
      accent: 'is-red',
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
              accent: 'is-green',
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
                window.location.href = buildFccUrl();
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

  function submitFinalCuts() {
    var namesInOrder = players.filter(function (player) {
      return selectedIds.has(player._id);
    }).map(function (player) { return player.name; });

    if (!namesInOrder.length) {
      // No cuts selected — proceed straight to recruiting.
      goNext();
      return;
    }
    showModal({
      title: 'Confirm Cuts',
      message: 'You are going to cut ' + formatNames(namesInOrder) + '. These players will be lost forever. Proceed?',
      accent: 'is-red',
      actions: [
        { label: 'Cancel', variant: 'gob-modal-btn-secondary' },
        {
          label: 'Cut Players',
          variant: 'gob-modal-btn-primary',
          onClick: function () {
            fetch(API_CONFIG.buildUrl('/franchise/cut-players-final'), {
              method: 'POST',
              headers: { ...API_CONFIG.getAuthHeaders(), 'Content-Type': 'application/json' },
              body: JSON.stringify({ franchise_id: franchiseId, player_ids: Array.from(selectedIds) })
            })
              .then(function (res) {
                if (!res.ok) throw new Error('Failed to cut players');
                return res.json();
              })
              .then(function (data) {
                playSound('confirm-1-lowervol.wav');
                showModal({
                  title: 'Players Cut',
                  message: formatNames(data.cut_names || namesInOrder) + ' have been cut. Continuing to recruiting.',
                  accent: 'is-green',
                  actions: [{ label: 'Continue to Recruiting', variant: 'gob-modal-btn-primary', onClick: goNext }]
                });
              })
              .catch(function (err) {
                console.error(err);
                showModal({
                  title: 'Cut Failed',
                  message: 'Unable to cut players.',
                  actions: [{ label: 'Close', variant: 'gob-modal-btn-secondary' }]
                });
              });
          }
        }
      ]
    });
  }

  function loadData() {
    Promise.all([
      fetch(API_CONFIG.buildUrl('/franchise/command-center/data') + '?franchise_id=' + encodeURIComponent(franchiseId) + '&profile=1', { headers: API_CONFIG.getAuthHeaders() })
        .then(function (res) { return res.ok ? res.json() : null; }),
      fetch(API_CONFIG.buildUrl('/roster/' + encodeURIComponent(teamId)) + '?franchise_id=' + encodeURIComponent(franchiseId) + '&profile=1', { headers: API_CONFIG.getAuthHeaders() })
        .then(function (res) {
          if (!res.ok) throw new Error('Failed to load roster');
          return res.json();
        })
    ]).then(function (results) {
      var topData = results[0] || {};
      var roster = results[1] || {};
      cutCount = Number(topData.cut_count || 0);
      // Week-35 cut mode: cut from active roster AND training squad. Assignment mode: active only.
      var pool = (roster.players || []).slice();
      if (isCutMode && Array.isArray(roster.training_squad)) {
        pool = pool.concat(roster.training_squad);
      }
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
      if (!isCutMode && (!topData.cut_required || cutCount <= 0)) {
        showModal({
          title: 'No Cuts Required',
          message: 'Your roster is already at the legal 12-player limit.',
          accent: 'is-green',
          actions: [{
            label: 'Back To Locker Room',
            variant: 'gob-modal-btn-primary',
            onClick: navigateBack
          }]
        });
      }
    }).catch(function (err) {
      console.error(err);
      showModal({
        title: 'Cut Players',
        message: 'Unable to load cut players data.',
        accent: 'is-red',
        actions: [{ label: 'Back To Locker Room', variant: 'gob-modal-btn-primary', onClick: navigateBack }]
      });
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    if (isCutMode) {
      // Relabel the page for real cuts (page chrome defaults to training-squad assignment).
      document.title = 'Cut Players';
      var h1 = document.querySelector('.cut-players-header h1');
      if (h1) h1.textContent = 'Cut Players';
      var submitLabel = document.getElementById('submit-btn');
      if (submitLabel) submitLabel.textContent = 'Submit Cuts';
      var lastTh = document.querySelector('#cut-players-table thead th:last-child');
      if (lastTh) lastTh.textContent = 'Cut';
    }
    document.getElementById('back-btn').addEventListener('click', attemptLeave);
    document.getElementById('submit-btn').addEventListener('click', function () {
      playSound('confirm-2-lowervol.wav');
      submitCuts();
    });
    window.addEventListener('beforeunload', function (e) {
      if (allowLeave || !selectedIds.size) return;
      e.preventDefault();
      e.returnValue = '';
    });
    loadData();
  });
})();
