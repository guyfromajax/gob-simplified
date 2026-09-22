/**
 * Training-by-Position matrix — renders window.GOB_TRAINING_MATRIX.
 *
 * Two orientations over one dataset:
 *   By Position — pick a position, compare its six development focuses.
 *   By Focus    — pick a focus, compare the five positions under it.
 *
 * Both read the same generated asset, so the page cannot disagree with the engine and the
 * two views cannot disagree with each other.
 *
 * Lands on By Focus → Standard: five positions under the default focus, which is the table
 * this page has always shown and the state every player is actually in. The focus
 * dimension is then something a coach opts into rather than something he arrives inside.
 */
(function () {
  'use strict';

  var DATA = window.GOB_TRAINING_MATRIX;
  var head = document.getElementById('fitgrid-head');
  var body = document.getElementById('fitgrid-body');
  var picks = document.getElementById('fg-picks');
  var legend = document.getElementById('fitgrid-legend');
  var caption = document.getElementById('fg-caption');
  if (!DATA || !head || !body || !picks) return;

  var state = { mode: 'focus', position: DATA.positions[0], focus: DATA.focuses[0].value };

  function esc(v) {
    return String(v == null ? '' : v).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  /** First band the value clears. The asset publishes them in descending order. */
  function bandFor(value) {
    for (var i = 0; i < DATA.bands.length; i++) {
      if (value >= DATA.bands[i].min) return DATA.bands[i].key;
    }
    return DATA.bands[DATA.bands.length - 1].key;
  }

  function focusLabel(value) {
    for (var i = 0; i < DATA.focuses.length; i++) {
      if (DATA.focuses[i].value === value) return DATA.focuses[i].label;
    }
    return value;
  }

  /** Columns for the current orientation: {key, label} in display order. */
  function columns() {
    return state.mode === 'position'
      ? DATA.focuses.map(function (f) { return { key: f.value, label: f.label }; })
      : DATA.positions.map(function (p) { return { key: p, label: p }; });
  }

  /** The cell value for one column and one attribute, whichever way the table is turned. */
  function valueAt(columnKey, attrCode) {
    return state.mode === 'position'
      ? DATA.matrix[state.position][columnKey][attrCode]
      : DATA.matrix[columnKey][state.focus][attrCode];
  }

  function renderPicks() {
    var options = state.mode === 'position'
      ? DATA.positions.map(function (p) { return { key: p, label: p }; })
      : DATA.focuses.map(function (f) { return { key: f.value, label: f.label }; });
    var current = state.mode === 'position' ? state.position : state.focus;
    picks.innerHTML = options.map(function (o) {
      var on = o.key === current;
      return '<button type="button" class="fg-pick' + (on ? ' is-on' : '') + '"' +
        ' role="tab" aria-selected="' + (on ? 'true' : 'false') + '"' +
        ' data-fg-pick="' + esc(o.key) + '">' + esc(o.label) + '</button>';
    }).join('');
  }

  function renderCaption() {
    if (!caption) return;
    caption.textContent = state.mode === 'position'
      ? 'How a ' + state.position + ' retains each point, by the focus you set for him.'
      : 'How each position retains a point on ' + focusLabel(state.focus) + '.';
  }

  function renderTable() {
    var cols = columns();
    head.innerHTML = '<tr><th class="fg-corner" scope="col">Attribute</th>' +
      cols.map(function (c) { return '<th scope="col">' + esc(c.label) + '</th>'; }).join('') +
      '</tr>';

    body.innerHTML = DATA.attributes.map(function (attr) {
      var cells = cols.map(function (c) {
        var v = valueAt(c.key, attr.code);
        return '<td><span class="fg-cell" data-band="' + bandFor(v) + '">' + v + '%</span></td>';
      }).join('');
      return '<tr><th scope="row"><span class="fg-attr">' + esc(attr.name) + '</span>' +
        '<span class="fg-code">' + esc(attr.code) + '</span></th>' + cells + '</tr>';
    }).join('');
  }

  function renderLegend() {
    if (!legend) return;
    // Descending in the asset; shown ascending, which is how the eye reads a scale.
    legend.innerHTML = DATA.bands.slice().reverse().map(function (b) {
      return '<span class="fl-item"><span class="fl-sw" data-band="' + esc(b.key) + '"></span> ' +
        esc(b.label) + '</span>';
    }).join('');
  }

  function render() {
    renderPicks();
    renderCaption();
    renderTable();
  }

  document.querySelectorAll('[data-fg-mode]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      if (state.mode === btn.dataset.fgMode) return;
      state.mode = btn.dataset.fgMode;
      document.querySelectorAll('[data-fg-mode]').forEach(function (b) {
        var on = b.dataset.fgMode === state.mode;
        b.classList.toggle('is-on', on);
        b.setAttribute('aria-selected', on ? 'true' : 'false');
      });
      render();
    });
  });

  // Delegated: the pick buttons are rebuilt on every orientation change.
  picks.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-fg-pick]');
    if (!btn) return;
    if (state.mode === 'position') state.position = btn.dataset.fgPick;
    else state.focus = btn.dataset.fgPick;
    render();
  });

  renderLegend();
  render();
})();
