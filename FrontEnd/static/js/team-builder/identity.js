/**
 * Team Builder — Chapter Ⅱ · Identity studio.
 * Previews via TeamGeneratedArt + TeamCourtGenerator only (no independent art).
 */
(function (global) {
  'use strict';

  var C = null;
  var TGA = null;
  var TCG = null;

  function bootDeps() {
    C = global.TeamBuilderConstants;
    TGA = global.TeamGeneratedArt;
    TCG = global.TeamCourtGenerator;
  }

  function hardwoodTones() {
    return (TCG && TCG.HARDWOOD_TONES) || {
      light: '#EAD8C6',
      medium: '#DBB891',
      dark: '#CB9D76',
    };
  }

  function deriveAbbr(name) {
    if (TGA && typeof TGA.initialsFromName === 'function') {
      return String(TGA.initialsFromName(name, null, null) || '')
        .toUpperCase()
        .slice(0, 3);
    }
    if (typeof global.deriveTeamAbbreviationFromName === 'function') {
      return global.deriveTeamAbbreviationFromName(name);
    }
    return String(name || '')
      .replace(/[^A-Za-z0-9]/g, '')
      .slice(0, 3)
      .toUpperCase();
  }

  function clampName(value) {
    var v = String(value == null ? '' : value);
    if (v.length > C.PROGRAM_NAME_MAX_LEN) v = v.slice(0, C.PROGRAM_NAME_MAX_LEN);
    return v;
  }

  function normalizeHex(value, fallback) {
    var h = String(value || '').trim();
    if (!/^#[0-9A-Fa-f]{6}$/.test(h)) return fallback || '#000000';
    return h.toLowerCase();
  }

  function resolveToken(identity, token, customKey) {
    if (token === 'Primary') return identity.primary;
    if (token === 'Secondary') return identity.secondary;
    if (token === 'Black') return '#101418';
    return identity[customKey];
  }

  /**
   * Resolve court render inputs. Tokens stay as tokens in draft state;
   * hex is computed only at render (and Custom stores its own hex).
   */
  function resolveCourtCfg(identity) {
    var tones = hardwoodTones();
    var insideTone = identity.inside === 'custom' ? 'medium' : identity.inside || 'medium';
    var outsideTone = identity.outside === 'custom' ? 'medium' : identity.outside || 'medium';
    if (C.HARDWOOD_TONES_KEYS.indexOf(insideTone) < 0) insideTone = 'medium';
    if (C.HARDWOOD_TONES_KEYS.indexOf(outsideTone) < 0) outsideTone = 'medium';

    var insideColor =
      identity.inside === 'custom'
        ? normalizeHex(identity.inside_custom, tones.medium)
        : tones[insideTone];
    var midcourtColor =
      identity.outside === 'custom'
        ? normalizeHex(identity.outside_custom, tones.medium)
        : tones[outsideTone];

    return {
      primary: identity.primary,
      secondary: identity.secondary,
      hardwoodStyle: insideTone + '_' + outsideTone,
      oobColor: resolveToken(identity, identity.oob, 'oob_custom'),
      laneColor: resolveToken(identity, identity.lane, 'lane_custom'),
      halfArcFillColor: resolveToken(identity, identity.arc, 'arc_custom'),
      outsideWoodColor: midcourtColor,
      // Symmetric custom for inside lobes — override only when Custom is selected.
      insideWoodColor: identity.inside === 'custom' ? insideColor : null,
      lineColor: C.COURT_LINE_COLOR,
      insideResolved: insideColor,
      midcourtResolved: midcourtColor,
      useOverlays: false,
    };
  }

  /**
   * WCAG contrast ratio ≥ 3.0 vs fixed court line #6e675f (client-only; generator stays dumb).
   */
  function insideWoodContrastOk(identity) {
    if (identity.inside !== 'custom') return true;
    var wood = normalizeHex(identity.inside_custom, '#DBB891');
    var ratio =
      TGA && typeof TGA.contrastRatio === 'function'
        ? TGA.contrastRatio(wood, C.COURT_LINE_COLOR)
        : 99;
    return ratio >= C.INSIDE_WOOD_LINE_CONTRAST_MIN;
  }

  function insideWoodContrastRatio(identity) {
    if (identity.inside !== 'custom') return null;
    var wood = normalizeHex(identity.inside_custom, '#DBB891');
    if (!TGA || typeof TGA.contrastRatio !== 'function') return null;
    return TGA.contrastRatio(wood, C.COURT_LINE_COLOR);
  }

  function isSwatch(hex) {
    var h = String(hex || '').toLowerCase();
    return C.SWATCHES.indexOf(h) >= 0;
  }

  function IdentityChapter(opts) {
    bootDeps();
    this.root = opts.root;
    this.getIdentity = opts.getIdentity;
    this.setIdentity = opts.setIdentity;
    this.onChange = opts.onChange || function () {};
    this.onReadyChange = opts.onReadyChange || function () {};
    this.onContinue = opts.onContinue || function () {};
    this.onBack = opts.onBack || function () {};
    this.leagueAbbrs = opts.leagueAbbrs || function () {
      return [];
    };
    this._abbrTimer = null;
    this._courtTimer = null;
    this._uniq = { state: 'short', code: '' };
    this._fontsReady = false;
    this._bound = false;
  }

  IdentityChapter.prototype.mount = function () {
    bootDeps();
    if (!this.root) return;
    this.root.innerHTML = this._template();
    this._els = {
      name: this.root.querySelector('#tb-id-name'),
      mascot: this.root.querySelector('#tb-id-mascot'),
      abbr: this.root.querySelector('#tb-id-abbr'),
      abbrFld: this.root.querySelector('#tb-id-abbr-fld'),
      uniq: this.root.querySelector('#tb-id-uniq'),
      pals: this.root.querySelector('#tb-id-pals'),
      primaryRow: this.root.querySelector('#tb-id-primary'),
      secondaryRow: this.root.querySelector('#tb-id-secondary'),
      insideChips: this.root.querySelector('#tb-id-inside'),
      outsideChips: this.root.querySelector('#tb-id-outside'),
      oob: this.root.querySelector('#tb-id-oob'),
      lane: this.root.querySelector('#tb-id-lane'),
      arc: this.root.querySelector('#tb-id-arc'),
      woodWarn: this.root.querySelector('#tb-id-wood-warn'),
      banner: this.root.querySelector('#tb-id-banner'),
      bannerStyles: this.root.querySelector('#tb-id-banner-styles'),
      jersey: this.root.querySelector('#tb-id-jersey'),
      jerseyStyles: this.root.querySelector('#tb-id-jersey-styles'),
      court: this.root.querySelector('#tb-id-court'),
      courtWrap: this.root.querySelector('#tb-id-court-wrap'),
      legend: this.root.querySelector('#tb-id-legend'),
      continue: this.root.querySelector('#tb-id-continue'),
      surprise: this.root.querySelector('#tb-id-surprise'),
      back: this.root.querySelector('#tb-id-back'),
    };
    this._bindOnce();
    var self = this;
    if (TGA && typeof TGA.ensureBannerFonts === 'function') {
      TGA.ensureBannerFonts().then(function () {
        self._fontsReady = true;
        self.paint();
      });
    } else {
      this._fontsReady = true;
    }
    this.paint();
  };

  IdentityChapter.prototype._template = function () {
    return (
      '<div class="studio">' +
      '<div class="pane rail">' +
      '<div class="pane-hd"><h2>Identity</h2><div class="sp"></div>' +
      '<button type="button" class="btn ghost sm" id="tb-id-surprise">Surprise me</button></div>' +
      '<div class="grp">' +
      '<div class="fld"><label for="tb-id-name">School name</label>' +
      '<input id="tb-id-name" type="text" maxlength="' +
      C.PROGRAM_NAME_MAX_LEN +
      '" autocomplete="off"></div>' +
      '<div class="row2">' +
      '<div class="fld"><label for="tb-id-mascot">Mascot</label>' +
      '<input id="tb-id-mascot" type="text" maxlength="' +
      C.MASCOT_MAX_LEN +
      '" autocomplete="off"></div>' +
      '<div class="fld abbr" id="tb-id-abbr-fld"><label for="tb-id-abbr">Abbreviation</label>' +
      '<input id="tb-id-abbr" type="text" maxlength="3" autocomplete="off" spellcheck="false"></div>' +
      '</div>' +
      '<div class="uniq" id="tb-id-uniq"></div>' +
      '</div>' +
      '<div class="grp"><div class="grp-k"><span>Palette</span></div>' +
      '<div class="pals" id="tb-id-pals"></div>' +
      '<div style="margin-top:11px">' +
      '<div class="swrow" id="tb-id-primary"></div>' +
      '<div class="swrow" id="tb-id-secondary"></div>' +
      '</div></div>' +
      '<div class="grp"><div class="grp-k"><span>Court</span></div>' +
      '<div class="crow"><span>Hardwood — inside the arcs</span>' +
      '<div class="chips" id="tb-id-inside"></div></div>' +
      '<div class="crow"><span>Hardwood — midcourt</span>' +
      '<div class="chips" id="tb-id-outside"></div></div>' +
      '<div class="crow" id="tb-id-oob"></div>' +
      '<div class="crow" id="tb-id-lane"></div>' +
      '<div class="crow" id="tb-id-arc"></div>' +
      '<div class="wood-warn" id="tb-id-wood-warn" hidden></div>' +
      '</div>' +
      '<div class="rail-ft">' +
      '<button type="button" class="btn ghost sm" id="tb-id-back">← Back to Claim</button>' +
      '</div></div>' +
      '<div class="pv">' +
      '<div class="pvtop">' +
      '<div class="frame">' +
      '<div class="frame-k">Program banner</div>' +
      '<div class="frame-b"><canvas id="tb-id-banner" class="banner-canvas" aria-label="Program banner"></canvas></div>' +
      '<div class="styles" id="tb-id-banner-styles"><span class="styles-k">Style</span></div>' +
      '</div>' +
      '<div class="situ-c jersey-c">' +
      '<div class="situ-b jersey-b"><img id="tb-id-jersey" class="jersey-svg" alt="Jersey preview"></div>' +
      '<div class="situ-styles" id="tb-id-jersey-styles"></div>' +
      '</div></div>' +
      '<div class="frame court-frame">' +
      '<div class="frame-b"><div class="court-wrap" id="tb-id-court-wrap">' +
      '<canvas id="tb-id-court" class="court-canvas" aria-label="Court preview"></canvas></div></div>' +
      '<div class="legend" id="tb-id-legend"></div>' +
      '</div></div></div>'
    );
  };

  IdentityChapter.prototype._patch = function (mutator, opts) {
    var cur = Object.assign({}, this.getIdentity());
    mutator(cur);
    this.setIdentity(cur);
    opts = opts || {};
    if (opts.soft) {
      // Keep the live <input type="color"> mounted while the OS picker is open.
      this.paintPreviews();
      this.syncContinue();
      var warn = this._els.woodWarn;
      if (warn) {
        if (cur.inside === 'custom' && !insideWoodContrastOk(cur)) {
          var ratio = insideWoodContrastRatio(cur);
          warn.hidden = false;
          warn.textContent =
            'Inside wood needs contrast ≥ 3.0 against court lines (' +
            C.COURT_LINE_COLOR +
            '). Current: ' +
            (ratio != null ? ratio.toFixed(2) : '—') +
            '.';
        } else {
          warn.hidden = true;
          warn.textContent = '';
        }
      }
    } else {
      this.paint();
    }
    this.onChange();
  };

  IdentityChapter.prototype._bindOnce = function () {
    if (this._bound) return;
    this._bound = true;
    var self = this;
    var els = this._els;

    els.name.addEventListener('input', function () {
      var id = Object.assign({}, self.getIdentity());
      var next = clampName(els.name.value);
      if (next !== els.name.value) els.name.value = next;
      id.name = next;
      if (!id.abbr_touched) id.abbreviation = deriveAbbr(next);
      self.setIdentity(id);
      self.paintFields();
      self.paintPreviews();
      self.scheduleAbbrCheck();
      self.onChange();
    });

    els.mascot.addEventListener('input', function () {
      var id = Object.assign({}, self.getIdentity());
      id.mascot = String(els.mascot.value || '').slice(0, C.MASCOT_MAX_LEN);
      self.setIdentity(id);
      self.paintPreviews();
      self.onChange();
    });

    els.abbr.addEventListener('input', function () {
      var id = Object.assign({}, self.getIdentity());
      id.abbr_touched = true;
      id.abbreviation = String(els.abbr.value || '')
        .toUpperCase()
        .replace(/[^A-Z0-9]/g, '')
        .slice(0, 3);
      els.abbr.value = id.abbreviation;
      self.setIdentity(id);
      self.paintPreviews();
      self.scheduleAbbrCheck();
      self.onChange();
    });

    els.surprise.addEventListener('click', function () {
      self.surprise();
    });
    els.back.addEventListener('click', function () {
      self.onBack();
    });

    // Delegated controls — paint() may rebuild DOM; do not re-bind per paint.
    this.root.addEventListener('click', function (e) {
      var pal = e.target.closest('[data-pal]');
      if (pal && self.root.contains(pal)) {
        var pi = Number(pal.getAttribute('data-pal'));
        var pl = C.PALETTES[pi];
        if (!pl) return;
        self._patch(function (cur) {
          var d =
            TCG && typeof TCG.defaultsFromTeamColors === 'function'
              ? TCG.defaultsFromTeamColors(pl.p, pl.s)
              : { oobColor: pl.p };
          cur.primary = pl.p;
          cur.secondary = pl.s;
          cur.oob_custom = d.oobColor || pl.p;
        });
        return;
      }
      var sw = e.target.closest('.sw[data-hex]');
      if (sw && self.root.contains(sw)) {
        var row = sw.closest('#tb-id-primary, #tb-id-secondary');
        var key = row && row.id === 'tb-id-secondary' ? 'secondary' : 'primary';
        self._patch(function (cur) {
          cur[key] = sw.getAttribute('data-hex');
        });
        return;
      }
      var tone = e.target.closest('[data-tone]');
      if (tone && self.root.contains(tone)) {
        var host = tone.closest('#tb-id-inside, #tb-id-outside');
        var toneKey = host && host.id === 'tb-id-outside' ? 'outside' : 'inside';
        self._patch(function (cur) {
          cur[toneKey] = tone.getAttribute('data-tone');
        });
        return;
      }
      var tok = e.target.closest('[data-tok]');
      if (tok && self.root.contains(tok)) {
        var field = tok.closest('#tb-id-oob, #tb-id-lane, #tb-id-arc');
        var tokenKey =
          field && field.id === 'tb-id-lane'
            ? 'lane'
            : field && field.id === 'tb-id-arc'
              ? 'arc'
              : 'oob';
        self._patch(function (cur) {
          cur[tokenKey] = tok.getAttribute('data-tok');
        });
        return;
      }
      var bv = e.target.closest('[data-bv]');
      if (bv && self.root.contains(bv)) {
        self._patch(function (cur) {
          cur.banner_variant = bv.getAttribute('data-bv');
        });
        return;
      }
      var jp = e.target.closest('[data-jp]');
      if (jp && self.root.contains(jp)) {
        self._patch(function (cur) {
          cur.jersey_preset = Number(jp.getAttribute('data-jp')) === 2 ? 2 : 1;
        });
      }
    });

    this.root.addEventListener('input', function (e) {
      var t = e.target;
      if (!t || t.type !== 'color') return;
      if (t.closest('#tb-id-primary')) {
        self._patch(function (cur) {
          cur.primary = normalizeHex(t.value, cur.primary);
        }, { soft: true });
        return;
      }
      if (t.closest('#tb-id-secondary')) {
        self._patch(function (cur) {
          cur.secondary = normalizeHex(t.value, cur.secondary);
        }, { soft: true });
        return;
      }
      if (t.closest('#tb-id-inside')) {
        self._patch(function (cur) {
          cur.inside = 'custom';
          cur.inside_custom = normalizeHex(t.value, cur.inside_custom);
        }, { soft: true });
        return;
      }
      if (t.closest('#tb-id-outside')) {
        self._patch(function (cur) {
          cur.outside = 'custom';
          cur.outside_custom = normalizeHex(t.value, cur.outside_custom);
        }, { soft: true });
        return;
      }
      if (t.closest('#tb-id-oob')) {
        self._patch(function (cur) {
          cur.oob = 'Custom';
          cur.oob_custom = normalizeHex(t.value, cur.oob_custom);
        }, { soft: true });
        return;
      }
      if (t.closest('#tb-id-lane')) {
        self._patch(function (cur) {
          cur.lane = 'Custom';
          cur.lane_custom = normalizeHex(t.value, cur.lane_custom);
        }, { soft: true });
        return;
      }
      if (t.closest('#tb-id-arc')) {
        self._patch(function (cur) {
          cur.arc = 'Custom';
          cur.arc_custom = normalizeHex(t.value, cur.arc_custom);
        }, { soft: true });
      }
    });

    this.root.addEventListener('change', function (e) {
      var t = e.target;
      if (!t || t.type !== 'color') return;
      // Picker closed — rebuild swatch/chip chrome to match the committed color.
      self.paint();
      self.onChange();
    });

    this.root.addEventListener('click', function (e) {
      var t = e.target;
      if (!t || t.type !== 'color') return;
      // Activating the custom chip selects Custom before the picker opens.
      if (t.closest('#tb-id-inside')) {
        var curIn = Object.assign({}, self.getIdentity());
        if (curIn.inside !== 'custom') {
          curIn.inside = 'custom';
          self.setIdentity(curIn);
          self.paintCourtControls();
          self.paintPreviews();
          self.onChange();
        }
      } else if (t.closest('#tb-id-outside')) {
        var curOut = Object.assign({}, self.getIdentity());
        if (curOut.outside !== 'custom') {
          curOut.outside = 'custom';
          self.setIdentity(curOut);
          self.paintCourtControls();
          self.paintPreviews();
          self.onChange();
        }
      }
    });
  };

  IdentityChapter.prototype.surprise = function () {
    var pick = C.SURPRISE[Math.floor(Math.random() * C.SURPRISE.length)];
    var pal = C.PALETTES[pick[2]];
    var d =
      TCG && typeof TCG.defaultsFromTeamColors === 'function'
        ? TCG.defaultsFromTeamColors(pal.p, pal.s)
        : { oobColor: pal.p };
    var tones = hardwoodTones();
    var variants = C.BANNER_VARIANTS.map(function (v) {
      return v.key;
    });
    var id = Object.assign({}, this.getIdentity(), {
      name: clampName(pick[0]),
      mascot: pick[1],
      abbreviation: deriveAbbr(pick[0]),
      abbr_touched: false,
      primary: pal.p,
      secondary: pal.s,
      jersey_preset: Math.random() < 0.5 ? 1 : 2,
      banner_variant: variants[Math.floor(Math.random() * variants.length)],
      inside: C.HARDWOOD_TONES_KEYS[Math.floor(Math.random() * 3)],
      outside: C.HARDWOOD_TONES_KEYS[Math.floor(Math.random() * 3)],
      oob_custom: d.oobColor || pal.p,
      lane_custom: pal.p,
      arc_custom: pal.s,
      outside_custom: d.outsideWoodColor || tones.medium,
      inside_custom: tones.medium,
    });
    this.setIdentity(id);
    this.paint();
    this.scheduleAbbrCheck();
    this.onChange();
  };

  IdentityChapter.prototype.paint = function () {
    this.paintFields();
    this.paintPalette();
    this.paintColorRows();
    this.paintCourtControls();
    this.paintBannerStyles();
    this.paintJerseyStyles();
    this.paintPreviews();
    this.scheduleAbbrCheck();
    this.syncContinue();
  };

  IdentityChapter.prototype.paintFields = function () {
    var id = this.getIdentity();
    if (this._els.name && document.activeElement !== this._els.name) {
      this._els.name.value = id.name || '';
    }
    if (this._els.mascot && document.activeElement !== this._els.mascot) {
      this._els.mascot.value = id.mascot || '';
    }
    if (this._els.abbr && document.activeElement !== this._els.abbr) {
      this._els.abbr.value = id.abbreviation || '';
    }
    this.paintUniq();
  };

  IdentityChapter.prototype.paintPalette = function () {
    var id = this.getIdentity();
    var html = '';
    C.PALETTES.forEach(function (pl, i) {
      var on = id.primary === pl.p && id.secondary === pl.s ? ' on' : '';
      html +=
        '<button type="button" class="pal' +
        on +
        '" data-pal="' +
        i +
        '" title="' +
        pl.name +
        '"><i style="background:' +
        pl.p +
        '"></i><i style="background:' +
        pl.s +
        '"></i></button>';
    });
    this._els.pals.innerHTML = html;
  };

  IdentityChapter.prototype._colorRowHtml = function (label, value) {
    var custom = !isSwatch(value);
    var html =
      '<b>' +
      label +
      '</b><div class="sws">' +
      C.SWATCHES.map(function (c) {
        return (
          '<button type="button" class="sw' +
          (String(value).toLowerCase() === c ? ' on' : '') +
          '" data-hex="' +
          c +
          '" style="background:' +
          c +
          '" aria-label="' +
          c +
          '"></button>'
        );
      }).join('') +
      '<label class="csw' +
      (custom ? ' on' : '') +
      '" style="background:' +
      value +
      '" title="Pick any color">' +
      '<input type="color" value="' +
      normalizeHex(value, '#000000') +
      '"></label></div>';
    return html;
  };

  IdentityChapter.prototype.paintColorRows = function () {
    var id = this.getIdentity();
    this._els.primaryRow.innerHTML = this._colorRowHtml('Primary', id.primary);
    this._els.secondaryRow.innerHTML = this._colorRowHtml('Secondary', id.secondary);
  };

  IdentityChapter.prototype._toneChips = function (current, customHex, includeCustom) {
    var tones = hardwoodTones();
    var html = C.HARDWOOD_TONES_KEYS.map(function (t) {
      return (
        '<button type="button" class="chip' +
        (current === t ? ' on' : '') +
        '" data-tone="' +
        t +
        '"><i style="background:' +
        tones[t] +
        '"></i>' +
        t +
        '</button>'
      );
    }).join('');
    if (includeCustom) {
      html +=
        '<label class="chip' +
        (current === 'custom' ? ' on' : '') +
        '" style="cursor:pointer;position:relative">' +
        '<i style="background:' +
        customHex +
        '"></i>custom' +
        '<input type="color" value="' +
        normalizeHex(customHex, tones.medium) +
        '" style="position:absolute;width:0;height:0;opacity:0"></label>';
    }
    return html;
  };

  IdentityChapter.prototype._courtFieldHtml = function (label, hint, tokens, value, custom, resolve) {
    var html =
      '<span>' +
      label +
      (hint ? ' — ' + hint : '') +
      '</span><div class="chips">' +
      tokens
        .map(function (t) {
          return (
            '<button type="button" class="chip' +
            (value === t ? ' on' : '') +
            '" data-tok="' +
            t +
            '"><i style="background:' +
            resolve(t) +
            '"></i>' +
            t +
            '</button>'
          );
        })
        .join('');
    if (value === 'Custom') {
      html +=
        '<label class="chip on" style="cursor:pointer;position:relative">' +
        '<i style="background:' +
        custom +
        '"></i>pick' +
        '<input type="color" value="' +
        normalizeHex(custom, '#000000') +
        '" style="position:absolute;width:0;height:0;opacity:0"></label>';
    }
    html += '</div>';
    return html;
  };

  IdentityChapter.prototype.paintCourtControls = function () {
    var id = this.getIdentity();
    var tones = hardwoodTones();

    this._els.insideChips.innerHTML = this._toneChips(
      id.inside,
      id.inside_custom || tones.medium,
      true
    );
    this._els.outsideChips.innerHTML = this._toneChips(
      id.outside,
      id.outside_custom || tones.medium,
      true
    );

    var resolve = function (t, customKey) {
      return resolveToken(id, t, customKey);
    };
    this._els.oob.innerHTML = this._courtFieldHtml(
      'Out of bounds',
      '',
      ['Primary', 'Secondary', 'Black', 'Custom'],
      id.oob,
      id.oob_custom,
      function (t) {
        return resolve(t, 'oob_custom');
      }
    );
    this._els.lane.innerHTML = this._courtFieldHtml(
      'Free-throw lane',
      '',
      ['Primary', 'Secondary', 'Custom'],
      id.lane,
      id.lane_custom,
      function (t) {
        return resolve(t, 'lane_custom');
      }
    );
    this._els.arc.innerHTML = this._courtFieldHtml(
      'Half-circle arcs',
      'lane caps',
      ['Secondary', 'Primary', 'Custom'],
      id.arc,
      id.arc_custom,
      function (t) {
        return resolve(t, 'arc_custom');
      }
    );

    var warn = this._els.woodWarn;
    if (id.inside === 'custom' && !insideWoodContrastOk(id)) {
      var ratio = insideWoodContrastRatio(id);
      warn.hidden = false;
      warn.textContent =
        'Inside wood needs contrast ≥ 3.0 against court lines (' +
        C.COURT_LINE_COLOR +
        '). Current: ' +
        (ratio != null ? ratio.toFixed(2) : '—') +
        '.';
    } else {
      warn.hidden = true;
      warn.textContent = '';
    }
  };

  IdentityChapter.prototype.paintBannerStyles = function () {
    var id = this.getIdentity();
    var html = '<span class="styles-k">Style</span>';
    C.BANNER_VARIANTS.forEach(function (v) {
      html +=
        '<button type="button" class="stbtn' +
        (id.banner_variant === v.key ? ' on' : '') +
        '" data-bv="' +
        v.key +
        '">' +
        v.name +
        '</button>';
    });
    this._els.bannerStyles.innerHTML = html;
  };

  IdentityChapter.prototype.paintJerseyStyles = function () {
    var id = this.getIdentity();
    var presets = [
      [1, 'Solid'],
      [2, 'Solid with trim'],
    ];
    this._els.jerseyStyles.innerHTML = presets
      .map(function (pair) {
        return (
          '<button type="button" class="stbtn' +
          (Number(id.jersey_preset) === pair[0] ? ' on' : '') +
          '" data-jp="' +
          pair[0] +
          '">' +
          pair[1] +
          '</button>'
        );
      })
      .join('');
  };

  IdentityChapter.prototype.paintPreviews = function () {
    var id = this.getIdentity();
    this._paintBanner(id);
    this._paintJersey(id);
    this._scheduleCourt(id);
  };

  IdentityChapter.prototype._paintBanner = function (id) {
    var canvas = this._els.banner;
    if (!canvas || !TGA || typeof TGA.drawBanner !== 'function') return;
    if (!this._fontsReady) return;
    var width = 780;
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

  IdentityChapter.prototype._paintJersey = function (id) {
    if (!this._els.jersey || !TGA || typeof TGA.jerseyPreviewDataUrl !== 'function') return;
    this._els.jersey.src = TGA.jerseyPreviewDataUrl({
      primary: id.primary,
      secondary: id.secondary,
      jerseyPreset: id.jersey_preset,
      number: 23,
    });
  };

  IdentityChapter.prototype._scheduleCourt = function (id) {
    var self = this;
    clearTimeout(this._courtTimer);
    if (this._els.courtWrap) this._els.courtWrap.classList.add('busy');
    this._courtTimer = setTimeout(function () {
      self._paintCourt(id);
    }, C.COURT_RENDER_MS);
  };

  IdentityChapter.prototype._paintCourt = function (id) {
    if (!TCG || typeof TCG.renderCourtCanvas !== 'function') return;
    var cfg = resolveCourtCfg(id);
    var opts = {
      primary: cfg.primary,
      secondary: cfg.secondary,
      hardwoodStyle: cfg.hardwoodStyle,
      oobColor: cfg.oobColor,
      laneColor: cfg.laneColor,
      outsideWoodColor: cfg.outsideWoodColor,
      halfArcFillColor: cfg.halfArcFillColor,
      lineColor: cfg.lineColor,
      useOverlays: false,
    };
    if (cfg.insideWoodColor) opts.insideWoodColor = cfg.insideWoodColor;
    var full = TCG.renderCourtCanvas(opts);
    var canvas = this._els.court;
    var width = 980;
    canvas.width = width;
    canvas.height = Math.round(width * (TCG.HEIGHT / TCG.WIDTH));
    var ctx = canvas.getContext('2d');
    ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(full, 0, 0, canvas.width, canvas.height);
    if (this._els.courtWrap) this._els.courtWrap.classList.remove('busy');
    this._els.legend.innerHTML =
      '<span><i style="background:' +
      cfg.oobColor +
      '"></i>Out of bounds</span>' +
      '<span><i style="background:' +
      cfg.midcourtResolved +
      '"></i>Midcourt</span>' +
      '<span><i style="background:' +
      cfg.insideResolved +
      '"></i>Inside arcs</span>' +
      '<span><i style="background:' +
      cfg.laneColor +
      '"></i>Lane</span>' +
      '<span><i style="background:' +
      cfg.halfArcFillColor +
      '"></i>Arcs</span>';
  };

  IdentityChapter.prototype.scheduleAbbrCheck = function () {
    var self = this;
    var id = this.getIdentity();
    var code = String(id.abbreviation || '').toUpperCase();
    if (code.length < C.ABBR_LEN) {
      this._uniq = { state: 'short', code: code };
      this.paintUniq();
      this.syncContinue();
      return;
    }
    this._uniq = { state: 'checking', code: code };
    this.paintUniq();
    this.syncContinue();
    clearTimeout(this._abbrTimer);
    this._abbrTimer = setTimeout(function () {
      var taken = self.leagueAbbrs().indexOf(code) >= 0;
      self._uniq = { state: taken ? 'taken' : 'ok', code: code };
      self.paintUniq();
      self.syncContinue();
    }, C.ABBR_CHECK_MS);
  };

  IdentityChapter.prototype.paintUniq = function () {
    var u = this._uniq;
    var el = this._els.uniq;
    var fld = this._els.abbrFld;
    if (!el) return;
    fld.classList.remove('ok', 'no');
    if (u.state === 'short') {
      el.innerHTML = '<span class="mute">three characters, exactly</span>';
    } else if (u.state === 'checking') {
      el.innerHTML = '<span class="mute">checking the league…</span>';
    } else if (u.state === 'ok') {
      el.innerHTML = '<span class="ok">✓ ' + u.code + ' is free</span>';
      fld.classList.add('ok');
    } else {
      el.innerHTML = '<span class="bad">✕ ' + u.code + ' is already in the league</span>';
      fld.classList.add('no');
    }
  };

  IdentityChapter.prototype.isReady = function () {
    var id = this.getIdentity();
    return !!(
      String(id.name || '').trim() &&
      String(id.name || '').length <= C.PROGRAM_NAME_MAX_LEN &&
      String(id.mascot || '').trim() &&
      this._uniq.state === 'ok' &&
      insideWoodContrastOk(id)
    );
  };

  IdentityChapter.prototype.syncContinue = function () {
    this.onReadyChange(this.isReady());
  };

  IdentityChapter.prototype.getUniqState = function () {
    return this._uniq;
  };

  global.TeamBuilderIdentity = {
    IdentityChapter: IdentityChapter,
    deriveAbbr: deriveAbbr,
    clampName: clampName,
    resolveCourtCfg: resolveCourtCfg,
    insideWoodContrastOk: insideWoodContrastOk,
  };
})(typeof window !== 'undefined' ? window : globalThis);
