/**
 * Team Builder — Build Mode Gate.
 * The only irreversible decision: capped vs uncapped.
 */
(function (global) {
  'use strict';

  function GateChapter(opts) {
    this.root = opts.root;
    this.getContext = opts.getContext;
    this.getMode = opts.getMode;
    this.setMode = opts.setMode;
    this.onContinue = opts.onContinue || function () {};
    this.onBack = opts.onBack || function () {};
    this._bound = false;
  }

  GateChapter.prototype.mount = function () {
    if (!this.root) return;
    var ctx = this.getContext() || {};
    var heightLabel =
      ctx.heightBudget != null
        ? Number(ctx.heightBudget).toLocaleString('en-US')
        : '—';
    var classLabel = ctx.classBudget != null ? String(ctx.classBudget) : '—';
    var replaced = ctx.replacedName || 'the replaced program';
    var program = ctx.programName || 'Your program';
    var abbr = ctx.abbr || '—';
    var conference = ctx.conferenceLabel || 'Conference';

    this.root.innerHTML =
      '<div class="gate">' +
      '<div class="ctx">' +
      '<b>' +
      escapeHtml(program) +
      '</b><i></i><span>' +
      escapeHtml(abbr) +
      '</span><i></i>replacing <span>' +
      escapeHtml(replaced) +
      '</span><i></i><span>' +
      escapeHtml(conference) +
      '</span></div>' +
      '<h1>This Choice Is Permanent</h1>' +
      '<div class="rule"></div>' +
      '<div class="cards">' +
      '<button type="button" class="mode" data-mode="capped">' +
      '<div class="m-hd">' +
      '<div class="m-k">Capped</div>' +
      '<div class="m-elig ok">Eligible for online play</div>' +
      '<div class="m-sub"><b>Multiplayer or Single-Player</b>' +
      'Eligible for leaderboards, multiplayer leagues, and head-to-head games.</div></div>' +
      '<div class="m-body">' +
      '<p class="m-lead">Three budgets, inherited from ' +
      escapeHtml(replaced) +
      '.</p>' +
      '<ul class="m-rules">' +
      '<li><b>Attributes</b><span>Every player keeps his own total. Points never move between players.</span></li>' +
      '<li><b>Height</b><span>' +
      escapeHtml(heightLabel) +
      '″ across the fifteen. Under the cap is allowed.</span></li>' +
      '<li><b>Year</b><span>' +
      escapeHtml(classLabel) +
      ' exactly. Not more, not less.</span></li>' +
      '</ul></div>' +
      '<div class="m-ft"><span class="m-pick">Click to choose</span>' +
      '<span class="m-tick"><i>✓</i>Chosen</span></div></button>' +
      '<button type="button" class="mode" data-mode="uncapped">' +
      '<div class="m-hd">' +
      '<div class="m-k">Uncapped</div>' +
      '<div class="m-elig no">Not eligible for online play</div>' +
      '<div class="m-sub"><b>Single Player only</b>Total anarchy.</div></div>' +
      '<div class="m-body"><p class="m-lead">No budgets at all.</p>' +
      '<ul class="m-rules">' +
      '<li><b>Attributes</b><span>Any value from 5 to 99. No total to land on.</span></li>' +
      '<li><b>Height</b><span>Any height from 5′6″ to 7′0″. No team cap.</span></li>' +
      '<li><b>Year</b><span>Any mix of years. No team total.</span></li>' +
      '</ul></div>' +
      '<div class="m-ft"><span class="m-pick">Click to choose</span>' +
      '<span class="m-tick"><i>✓</i>Chosen</span></div></button>' +
      '</div>' +
      // Year vs potential — appears once on the gate only. Potential is fixed at
      // generation (entry_tier / potential_factor); Year does not change it.
      '<p class="year-guard">A younger roster has more seasons ahead, not better players. ' +
      'Potential is fixed at generation.</p>' +
      '<div class="commit" id="tb-gate-commit">' +
      '<div class="c-txt" id="tb-gate-ctext">Nothing is chosen yet.</div>' +
      '<button type="button" class="btn" id="tb-gate-go" disabled>Continue to Roster</button>' +
      '</div>' +
      '<button type="button" class="back" id="tb-gate-back">← Back to Identity</button>' +
      '</div>';

    this._els = {
      cards: [].slice.call(this.root.querySelectorAll('.mode')),
      commit: this.root.querySelector('#tb-gate-commit'),
      ctext: this.root.querySelector('#tb-gate-ctext'),
      go: this.root.querySelector('#tb-gate-go'),
      back: this.root.querySelector('#tb-gate-back'),
    };
    this._bind();
    this.sync();
  };

  GateChapter.prototype._bind = function () {
    var self = this;
    this._els.cards.forEach(function (card) {
      card.addEventListener('click', function () {
        self.setMode(card.getAttribute('data-mode'));
        self.sync();
      });
    });
    this._els.go.addEventListener('click', function () {
      if (!self.getMode()) return;
      self.onContinue();
    });
    this._els.back.addEventListener('click', function () {
      self.onBack();
    });
  };

  GateChapter.prototype.sync = function () {
    var mode = this.getMode();
    var ctx = this.getContext() || {};
    var program = ctx.programName || 'Your program';
    this._els.cards.forEach(function (c) {
      c.classList.toggle('on', c.getAttribute('data-mode') === mode);
    });
    if (!mode) {
      this._els.ctext.textContent = 'Nothing is chosen yet.';
      this._els.commit.classList.remove('armed');
      this._els.go.disabled = true;
      return;
    }
    if (mode === 'capped') {
      this._els.ctext.innerHTML =
        escapeHtml(program) +
        ' will be built <b>capped</b> and <b>will be eligible</b> for online play.';
    } else {
      this._els.ctext.innerHTML =
        escapeHtml(program) +
        ' will be built <b>uncapped</b> and <b>will never be eligible</b> for online play.';
    }
    this._els.commit.classList.add('armed');
    this._els.go.disabled = false;
  };

  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  global.TeamBuilderGate = {
    GateChapter: GateChapter,
  };
})(typeof window !== 'undefined' ? window : globalThis);
