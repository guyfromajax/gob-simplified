/**
 * Development Focus — shared controls for the roster surfaces.
 *
 * One implementation for the FCC roster tab, the roster page and the player detail block,
 * so the six focus values, their labels and the save call cannot drift between screens.
 *
 * Contract (GOB_DEVELOPMENT_FOCUS_PLAN.md):
 *   - FPD is authoritative; every write goes to POST /franchise/player/development-focus.
 *   - Controls render for the USER'S OWN TEAM ONLY. Opponent and scouted players show
 *     nothing at all — not an empty cell, not a dash.
 *   - Changing either value affects FUTURE training only.
 *   - A legacy player with nothing stored reads as his resolved value (Standard), so the
 *     control always shows a real current setting rather than a blank.
 */
(function () {
  'use strict';

  var POSITIONS = ['PG', 'SG', 'SF', 'PF', 'C'];

  // Stored value → coach-facing label. Stored values are lowercase and stable; labels are
  // the only thing that should ever change.
  var FOCUSES = [
    { value: 'standard', label: 'Standard' },
    { value: 'offensive', label: 'Offensive' },
    { value: 'defensive', label: 'Defensive' },
    { value: 'athletic', label: 'Athletic' },
    { value: 'fundamentals', label: 'Fundamentals' },
    { value: 'rebounding', label: 'Rebounding' }
  ];

  var FOCUS_LABELS = FOCUSES.reduce(function (acc, f) { acc[f.value] = f.label; return acc; }, {});

  function focusOf(player) {
    var raw = (player && (player.resolved_training_focus || player.training_focus)) || 'standard';
    raw = String(raw).trim().toLowerCase();
    return FOCUS_LABELS[raw] ? raw : 'standard';
  }

  function positionOf(player) {
    var raw = player && (player.resolved_training_position || player.training_position);
    raw = String(raw || '').trim();
    if (POSITIONS.indexOf(raw) !== -1) return raw;
    // Fall back to the best position rating so the control is never blank.
    var ratings = (player && player.position_ratings) || {};
    var best = null;
    var bestVal = -Infinity;
    POSITIONS.forEach(function (p) {
      var v = Number(ratings[p]);
      if (isFinite(v) && v > bestVal) { bestVal = v; best = p; }
    });
    return best || 'SF';
  }

  function focusLabel(player) {
    return FOCUS_LABELS[focusOf(player)];
  }

  function escapeAttr(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function selectHtml(opts) {
    var options = opts.options.map(function (o) {
      var sel = o.value === opts.value ? ' selected' : '';
      return '<option value="' + escapeAttr(o.value) + '"' + sel + '>' + escapeAttr(o.label) + '</option>';
    }).join('');
    return '<select class="devfocus-select ' + opts.className + '"' +
      ' data-devfocus-field="' + escapeAttr(opts.field) + '"' +
      ' data-player-id="' + escapeAttr(opts.playerId) + '"' +
      ' aria-label="' + escapeAttr(opts.ariaLabel) + '">' + options + '</select>';
  }

  function positionSelectHtml(player) {
    return selectHtml({
      field: 'training_position',
      className: 'devfocus-select--pos',
      playerId: player._id || player.player_id,
      value: positionOf(player),
      ariaLabel: 'Training position',
      options: POSITIONS.map(function (p) { return { value: p, label: p }; })
    });
  }

  function focusSelectHtml(player) {
    return selectHtml({
      field: 'training_focus',
      className: 'devfocus-select--focus',
      playerId: player._id || player.player_id,
      value: focusOf(player),
      ariaLabel: 'Development focus',
      options: FOCUSES
    });
  }

  /**
   * Read-only renderings, for the roster surfaces.
   *
   * The roster tables are reference: you scan and compare there, you do not develop
   * there. The one editor is the training page's Player Development grid, where the
   * setting sits beside the points it governs. A live control in a twelve-tile-wide row
   * also invites a stray click that writes to the database with no undo.
   */
  function positionTextHtml(player) {
    return '<span class="devfocus-value devfocus-value--pos">' +
      escapeAttr(positionOf(player)) + '</span>';
  }

  function focusTextHtml(player) {
    var value = focusOf(player);
    // Standard is the default nearly everyone sits on; muting it lets the players who
    // have actually been given a focus stand out in a twelve-row scan.
    var muted = value === 'standard' ? ' is-default' : '';
    return '<span class="devfocus-value devfocus-value--focus' + muted + '">' +
      escapeAttr(FOCUS_LABELS[value]) + '</span>';
  }

  /** Persist one field for one player. Resolves to the server's echo of what it stored. */
  function save(franchiseId, playerId, field, value) {
    var body = { franchise_id: String(franchiseId), player_id: String(playerId) };
    body[field] = value;
    return fetch(API_CONFIG.buildUrl('/franchise/player/development-focus'), {
      method: 'POST',
      headers: Object.assign({ 'Content-Type': 'application/json' }, authHeaders()),
      body: JSON.stringify(body)
    }).then(function (res) {
      if (!res.ok) {
        return res.json().catch(function () { return {}; }).then(function (err) {
          throw new Error(err.detail || ('Save failed (' + res.status + ')'));
        });
      }
      return res.json();
    });
  }

  // The app's one auth-header source. Rolling our own localStorage read here would be a
  // second place for the token key to be wrong.
  function authHeaders() {
    return (window.API_CONFIG && typeof window.API_CONFIG.getAuthHeaders === 'function')
      ? window.API_CONFIG.getAuthHeaders()
      : {};
  }

  /**
   * Wire every control inside `root`. `getFranchiseId` is a function so a page that
   * resolves its franchise late still binds correctly.
   *
   * On success the in-memory player object is updated through `onSaved` so a re-render
   * (sort, scope switch) does not show the pre-change value.
   */
  function bind(root, getFranchiseId, onSaved) {
    if (!root) return;
    root.querySelectorAll('.devfocus-select').forEach(function (select) {
      if (select.dataset.devfocusBound) return;
      select.dataset.devfocusBound = '1';
      select.addEventListener('change', function () {
        var field = select.dataset.devfocusField;
        var playerId = select.dataset.playerId;
        var value = select.value;
        var previous = select.dataset.devfocusPrev || '';
        select.disabled = true;
        save(getFranchiseId(), playerId, field, value).then(
          // SUCCESS. Nothing in here may reject the chain: the rejection handler below
          // reverts the control, so a throw after a SAVED change would put the old value
          // back on screen while the database held the new one. A missing `toastTimer`
          // declaration did exactly that — every first change looked like it failed, and
          // picking a different value second left the control showing neither.
          function (result) {
            select.dataset.devfocusPrev = value;
            runSafely(function () {
              if (typeof onSaved === 'function') onSaved(playerId, field, value, result);
            });
            runSafely(function () {
              toast(field === 'training_focus'
                ? 'Development focus updated'
                : 'Training position updated');
            });
          },
          // FAILURE. Passed as .then's SECOND argument, not .catch, so it cannot see
          // anything thrown by the success handler above it — only a genuine rejection
          // from save() can revert the control. That is structural, not a convention.
          function (err) {
            if (previous) select.value = previous;
            runSafely(function () { toast((err && err.message) || 'Could not save', true); });
          }
        ).finally(function () { select.disabled = false; });
      });
      select.dataset.devfocusPrev = select.value;
    });
  }

  /** Run a side effect that must never decide whether the save succeeded. */
  function runSafely(fn) {
    try {
      fn();
    } catch (err) {
      console.error('[Development Focus] post-save step failed:', err);
    }
  }

  var toastTimer = null;

  function toast(message, isError) {
    var el = document.getElementById('devfocus-toast');
    if (!el) {
      el = document.createElement('div');
      el.id = 'devfocus-toast';
      el.setAttribute('role', 'status');
      el.setAttribute('aria-live', 'polite');
      document.body.appendChild(el);
    }
    el.textContent = message;
    el.className = isError ? 'devfocus-toast is-error is-open' : 'devfocus-toast is-open';
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { el.classList.remove('is-open'); }, isError ? 5000 : 2200);
  }

  window.GOBDevelopmentFocus = {
    POSITIONS: POSITIONS,
    FOCUSES: FOCUSES,
    FOCUS_LABELS: FOCUS_LABELS,
    positionOf: positionOf,
    focusOf: focusOf,
    focusLabel: focusLabel,
    positionSelectHtml: positionSelectHtml,
    focusSelectHtml: focusSelectHtml,
    positionTextHtml: positionTextHtml,
    focusTextHtml: focusTextHtml,
    save: save,
    bind: bind
  };
})();
