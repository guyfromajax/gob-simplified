/**
 * Team Builder — Establish sequence.
 * Curtain after Apply. Timing floors are design beats; close waits on the server.
 * Wait row uses the same green pulse bar as the training load overlay.
 */
(function (global) {
  'use strict';

  var C = null;
  var TGA = null;

  function bootDeps() {
    C = global.TeamBuilderConstants;
    TGA = global.TeamGeneratedArt;
  }

  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function hardwoodLabel(id) {
    var tone = id && id.outside === 'custom' ? 'Custom' : id && id.outside;
    if (!tone) tone = 'medium';
    return String(tone).charAt(0).toUpperCase() + String(tone).slice(1) + ' hardwood';
  }

  function jerseyLabel(preset) {
    return Number(preset) === 2 ? 'Solid with trim' : 'Solid';
  }

  function EstablishChapter(opts) {
    bootDeps();
    this.root = opts.root;
    this.host = opts.host || {};
    this.onEnter = opts.onEnter || function () {};
    this.onError = opts.onError || function () {};
    this.onBack = opts.onBack || function () {};
    this._timers = [];
    this._phase = -1;
    this._lines = 0;
    this._swapped = false;
    this._ready = false;
    this._franchiseId = null;
    this._error = null;
    this._fontsReady = false;
    this._running = false;
  }

  EstablishChapter.prototype.mount = function () {
    bootDeps();
    if (!this.root || this._running) return;
    this._running = true;
    this._phase = -1;
    this._lines = 0;
    this._swapped = false;
    this._ready = false;
    this._error = null;
    this._franchiseId = null;
    this.paint();
    var self = this;
    if (TGA && typeof TGA.ensureBannerFonts === 'function') {
      TGA.ensureBannerFonts().then(function () {
        self._fontsReady = true;
        self._paintBanner();
      });
    } else {
      this._fontsReady = true;
      this._paintBanner();
    }
    this._startSequence();
    this._startApply();
  };

  EstablishChapter.prototype.destroy = function () {
    this._clearTimers();
    this._running = false;
  };

  EstablishChapter.prototype._clearTimers = function () {
    this._timers.forEach(clearTimeout);
    this._timers = [];
  };

  EstablishChapter.prototype._at = function (ms, fn) {
    this._timers.push(setTimeout(fn, ms));
  };

  EstablishChapter.prototype._ctx = function () {
    var host = this.host;
    var id = (host.getIdentity && host.getIdentity()) || {};
    var replaced = (host.getReplaced && host.getReplaced()) || {};
    var mode = host.getBuildMode ? host.getBuildMode() : 'capped';
    var allTeams = (host.getAllTeams && host.getAllTeams()) || [];
    var conf = Number(replaced.conference);
    var region =
      replaced.region ||
      (global.TeamPicker && typeof TeamPicker.regionFromConference === 'function'
        ? TeamPicker.regionFromConference(conf)
        : '');
    return { id: id, replaced: replaced, mode: mode, allTeams: allTeams, conf: conf, region: region };
  };

  EstablishChapter.prototype._charter = function (ctx) {
    var id = ctx.id;
    var capped = ctx.mode === 'capped';
    return [
      { k: 'Program registered', v: id.name || 'Program', e: id.abbreviation || '' },
      {
        k: 'Conference seat',
        v: ctx.conf >= 1 ? 'Conference ' + ctx.conf : 'Conference',
        e: ctx.region ? 'Region ' + String(ctx.region).toUpperCase() : '',
      },
      { k: 'Taking the place of', v: ctx.replaced.name || '—' },
      { k: 'Roster assigned', v: '15 players', e: '12 scholarship · 3 walk-ons' },
      {
        k: 'Court and uniforms',
        v: hardwoodLabel(id),
        e: jerseyLabel(id.jersey_preset),
      },
      {
        k: 'Build mode',
        v: capped ? 'Capped' : 'Uncapped',
        e: capped ? 'eligible for online play' : 'not eligible for online play',
        ok: capped,
      },
    ];
  };

  EstablishChapter.prototype._standings = function (ctx) {
    var conf = ctx.conf;
    var mates = (ctx.allTeams || []).filter(function (t) {
      return Number(t.conference) === conf;
    });
    mates.sort(function (a, b) {
      var pa = Number(b.prestige || 0) - Number(a.prestige || 0);
      if (pa) return pa;
      var ta = Number(b.total_player_attrs || 0) - Number(a.total_player_attrs || 0);
      if (ta) return ta;
      return String(a.name || '').localeCompare(String(b.name || ''));
    });
    return mates;
  };

  EstablishChapter.prototype.paint = function () {
    var ctx = this._ctx();
    var charter = this._charter(ctx);
    var mates = this._standings(ctx);
    var phaseClass = this._phase < 0 ? 'est' : 'est p' + this._phase;
    var waitLabel = !this._swapped
      ? 'Writing the charter'
      : !this._ready
        ? 'Waiting on the league office'
        : 'Complete';
    if (this._error) waitLabel = 'Could not establish';

    var charterHtml = charter
      .map(function (c, i) {
        var emClass =
          c.ok === undefined ? '' : c.ok ? 'yes' : 'no';
        return (
          '<div class="ch-r' +
          (i < this._lines ? ' in' : '') +
          '"><div class="ch-k">' +
          escapeHtml(c.k) +
          '</div><div class="ch-v">' +
          escapeHtml(c.v) +
          (c.e
            ? '<em class="' + emClass + '">' + escapeHtml(c.e) + '</em>'
            : '') +
          '</div></div>'
        );
      }, this)
      .join('');

    var programName = ctx.id.name || 'Program';
    var rows = mates
      .map(function (p, i) {
        var isSlot = String(p.object_id) === String(ctx.replaced.object_id);
        var slotClass = isSlot
          ? 'slot ' + (this._swapped ? 'now' : 'was')
          : '';
        var name = isSlot && this._swapped ? programName : p.name;
        return (
          '<tr class="' +
          slotClass +
          '"><td class="sw-mark">' +
          (i + 1) +
          '</td><td class="n">' +
          escapeHtml(name) +
          '</td><td class="r">—</td></tr>'
        );
      }, this)
      .join('');

    var year = new Date().getFullYear();
    var confLabel = ctx.conf >= 1 ? 'Conference ' + ctx.conf : 'Conference';

    this.root.innerHTML =
      '<div class="' +
      phaseClass +
      '" id="tb-est-root">' +
      '<div class="stage">' +
      '<div class="art"><canvas id="tb-est-banner" aria-label="Program banner"></canvas></div>' +
      '<div class="cols">' +
      '<div class="charter">' +
      charterHtml +
      '</div>' +
      '<div class="swap">' +
      '<div class="sw-k">Conference ' +
      escapeHtml(ctx.conf >= 1 ? String(ctx.conf) : '—') +
      ' · ' +
      (this._swapped ? 'your seat' : 'the seat you are taking') +
      '</div>' +
      '<table class="sw-t"><tbody>' +
      rows +
      '</tbody></table></div></div>' +
      '<div class="wait">' +
      '<div class="w-pulse" aria-hidden="true"><span></span></div>' +
      '<div class="w-t">' +
      escapeHtml(waitLabel) +
      '</div></div>' +
      (this._error
        ? '<div class="est-err">' +
          escapeHtml(this._error) +
          '<div style="margin-top:12px"><button type="button" class="btn ghost" id="tb-est-back">← Back to Review</button></div></div>'
        : '') +
      '<div class="close">' +
      '<div class="cl-t"><div class="cl-h">' +
      escapeHtml(programName) +
      ' ' +
      escapeHtml(ctx.id.mascot || '') +
      '</div>' +
      '<div class="cl-s">Established ' +
      year +
      ' · ' +
      escapeHtml(confLabel) +
      '</div></div>' +
      '<button type="button" class="btn" id="tb-est-enter"' +
      (this._phase >= 3 && this._franchiseId ? '' : ' disabled') +
      '>Enter Franchise</button></div></div></div>';

    this._els = {
      banner: this.root.querySelector('#tb-est-banner'),
      enter: this.root.querySelector('#tb-est-enter'),
    };
    var self = this;
    if (this._els.enter) {
      this._els.enter.onclick = function () {
        if (!self._franchiseId) return;
        self.onEnter(self._franchiseId);
      };
    }
    var back = this.root.querySelector('#tb-est-back');
    if (back) {
      back.onclick = function () {
        self.destroy();
        self.onBack();
      };
    }
    this._paintBanner();
  };

  EstablishChapter.prototype._paintBanner = function () {
    var canvas = this._els && this._els.banner;
    if (!canvas || !TGA || typeof TGA.drawBanner !== 'function') return;
    if (!this._fontsReady) return;
    var id = (this.host.getIdentity && this.host.getIdentity()) || {};
    var width = 660;
    var height = Math.round(width * (TGA.CARD_H / TGA.CARD_W));
    var dpr = Math.min(2, global.devicePixelRatio || 1);
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    canvas.style.width = '100%';
    canvas.style.height = 'auto';
    TGA.drawBanner(canvas.getContext('2d'), canvas.width, canvas.height, {
      name: id.name || 'Program',
      mascot: id.mascot || '',
      abbreviation: id.abbreviation || '',
      primary: id.primary,
      secondary: id.secondary,
      banner_variant: id.banner_variant || C.DEFAULT_BANNER_VARIANT,
    });
  };

  EstablishChapter.prototype._startSequence = function () {
    var self = this;
    var CHARTER_LEN = 6;
    // Design beats (floor). Close still waits on Apply.
    this._at(60, function () {
      self._phase = 0;
      self.paint();
    });
    this._at(720, function () {
      self._phase = 1;
      self.paint();
    });
    for (var i = 0; i < CHARTER_LEN; i++) {
      (function (n) {
        self._at(760 + n * 210, function () {
          self._lines = n + 1;
          self.paint();
        });
      })(i);
    }
    var standingsAt = 760 + CHARTER_LEN * 210 + 180;
    this._at(standingsAt, function () {
      self._phase = 2;
      self.paint();
    });
    this._at(standingsAt + 700, function () {
      self._swapped = true;
      self.paint();
      self._maybeClose();
    });
  };

  EstablishChapter.prototype._maybeClose = function () {
    var self = this;
    if (this._ready && this._swapped && !this._error && this._phase < 3) {
      this._at(420, function () {
        self._phase = 3;
        self.paint();
      });
    }
  };

  EstablishChapter.prototype._startApply = function () {
    var self = this;
    var applyFn = this.host.applyFranchise;
    if (typeof applyFn !== 'function') {
      this._error = 'Apply is not wired.';
      this.paint();
      this.onError(this._error);
      return;
    }

    Promise.resolve()
      .then(function () {
        return applyFn();
      })
      .then(function (result) {
        self._ready = true;
        self._franchiseId = result && result.franchise_id ? result.franchise_id : null;
        if (!self._franchiseId) {
          self._error = 'Apply succeeded without a franchise id.';
          self.paint();
          self.onError(self._error);
          return;
        }
        self.paint();
        self._maybeClose();
      })
      .catch(function (err) {
        self._error = (err && err.message) || 'Unable to establish the program.';
        self._ready = false;
        self.paint();
        self.onError(self._error);
      });
  };

  global.TeamBuilderEstablish = {
    EstablishChapter: EstablishChapter,
  };
})(typeof window !== 'undefined' ? window : globalThis);
