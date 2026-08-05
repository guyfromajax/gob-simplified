/**
 * Team Builder — Chapter Ⅲ · Roster.
 * Diff editor: bind by player identity; inherited values stay unless edited.
 * Budgets: client totals against server-shipped caps. Ratings: server only.
 */
(function (global) {
  'use strict';

  var C = null;

  function bootDeps() {
    C = global.TeamBuilderConstants;
  }

  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function feetInches(inches) {
    var n = Math.round(Number(inches) || 0);
    return Math.floor(n / 12) + "'" + (n % 12) + '"';
  }

  function scaleColor(v) {
    var n = Number(v) || 0;
    if (n <= 40) return '#ff6d6d';
    if (n <= 60) return '#FFD700';
    if (n <= 80) return '#34EC27';
    return '#4A90D9';
  }

  function coreTotal(attrs) {
    var sum = 0;
    (C.CORE_12_ATTRS || []).forEach(function (t) {
      sum += Number((attrs && attrs[t.code]) || 0) || 0;
    });
    return sum;
  }

  function cappedBudget(raw) {
    var n = Math.max(0, Number(raw) || 0);
    return n < C.TOPUP_FLOOR ? C.TOPUP_FLOOR : n;
  }

  function primaryPos(ratings) {
    var best = 'SF';
    var bestVal = -1;
    (C.POSITIONS || []).forEach(function (pos) {
      var v = Number(ratings && ratings[pos]);
      if (!isNaN(v) && v > bestVal) {
        bestVal = v;
        best = pos;
      }
    });
    return best;
  }

  function initials(name) {
    return (name || '')
      .trim()
      .split(/\s+/)
      .map(function (w) {
        return w[0] || '';
      })
      .join('')
      .slice(0, 3)
      .toUpperCase() || '—';
  }

  function firstOf(name) {
    return (name || '').trim().split(/\s+/)[0] || '';
  }

  function lastOf(name) {
    return (name || '').trim().split(/\s+/).slice(1).join(' ');
  }

  function yearAbbrev(raw) {
    if (!raw) return 'FR';
    var t = String(raw).trim();
    if (/^(FR|SO|JR|SR)$/i.test(t)) return t.toUpperCase();
    var lower = t.toLowerCase();
    if (lower.indexOf('senior') >= 0 || lower === 'sr') return 'SR';
    if (lower.indexOf('junior') >= 0 || lower === 'jr') return 'JR';
    if (lower.indexOf('soph') >= 0 || lower === 'so') return 'SO';
    return 'FR';
  }

  function classRank(cls, table) {
    var key = yearAbbrev(cls);
    if (table && table[key] != null) return Number(table[key]) || 0;
    var fallback = { FR: 1, SO: 2, JR: 3, SR: 4 };
    return fallback[key] || 1;
  }

  function cloneAttrs(src) {
    var out = {};
    (C.CORE_12_ATTRS || []).forEach(function (t) {
      var v = Number((src && src[t.code]) || C.ATTR_MIN);
      if (isNaN(v)) v = C.ATTR_MIN;
      out[t.code] = Math.max(C.ATTR_MIN, Math.min(C.ATTR_MAX, Math.round(v)));
    });
    return out;
  }

  function normalizePlayerRow(raw, opts) {
    opts = opts || {};
    var wo = !!(raw.walk_on || opts.walk_on);
    var id =
      String(
        raw.id ||
          raw.source_player_id ||
          raw.wizard_player_id ||
          raw.player_id ||
          ''
      ).trim() || 'row-' + String(opts.slot || 0);
    var first = String(raw.first_name || firstOf(raw.name) || '').trim();
    var last = String(raw.last_name || lastOf(raw.name) || '').trim();
    var name = (first + ' ' + last).trim() || String(raw.name || 'Player').trim();
    var attrs = cloneAttrs(raw.attributes || raw.attrs);
    var rawTotal = coreTotal(attrs);
    var ht = Number(raw.height_in != null ? raw.height_in : raw.height);
    if (isNaN(ht) || ht <= 0) ht = C.HEIGHT_MIN_IN;
    ht = Math.max(C.HEIGHT_MIN_IN, Math.min(C.HEIGHT_MAX_IN, Math.round(ht)));
    var cls = yearAbbrev(raw.class_year || raw.year || raw.cls);
    var ratings = raw.position_ratings || raw.ratings || null;
    var jersey = raw.jersey != null ? raw.jersey : raw.n;
    if (jersey === '' || jersey == null) jersey = '';
    else jersey = String(Number(jersey));
    if (jersey === 'NaN') jersey = '';

    return {
      id: id,
      source_player_id: raw.source_player_id ? String(raw.source_player_id) : wo ? null : id,
      wizard_player_id: raw.wizard_player_id ? String(raw.wizard_player_id) : wo ? id : null,
      minted_player_id: raw.minted_player_id || raw.player_id || null,
      first_name: first,
      last_name: last,
      name: name,
      n: jersey,
      pos: ratings ? primaryPos(ratings) : String(raw.pos || 'SF'),
      cls: cls,
      ht: ht,
      wt: raw.weight_lb != null ? Number(raw.weight_lb) : Number(raw.weight) || null,
      attrs: attrs,
      base: {
        first_name: first,
        last_name: last,
        name: name,
        n: jersey,
        cls: cls,
        ht: ht,
        wt: raw.weight_lb != null ? Number(raw.weight_lb) : Number(raw.weight) || null,
        attrs: cloneAttrs(attrs),
      },
      budget: cappedBudget(rawTotal),
      raw_total: rawTotal,
      wo: wo,
      portrait_locked: !!raw.portrait_locked,
      image_id: raw.image_id || null,
      portrait_meta: raw.portrait_meta || null,
      ratings: ratings,
      ratings_pending: false,
    };
  }

  function playerChanged(p) {
    if (!p || !p.base) return false;
    if (p.ht !== p.base.ht) return true;
    if (p.cls !== p.base.cls) return true;
    if (String(p.n) !== String(p.base.n)) return true;
    if (p.first_name !== p.base.first_name || p.last_name !== p.base.last_name) return true;
    return C.CORE_12_ATTRS.some(function (t) {
      return p.attrs[t.code] !== p.base.attrs[t.code];
    });
  }

  function attrPoolDelta(p) {
    return p.budget - coreTotal(p.attrs);
  }

  /** Capped: hard ceiling for one attr = remaining pool + current value. */
  function cappedAttrMax(p, code) {
    var current = Number(p.attrs[code]);
    if (isNaN(current)) current = C.ATTR_MIN;
    var pool = attrPoolDelta(p);
    return Math.min(C.ATTR_MAX, current + Math.max(0, pool));
  }

  function RosterChapter(opts) {
    bootDeps();
    this.root = opts.root;
    this.host = opts.host || {};
    this.onChange = opts.onChange || function () {};
    this.onStatusChange = opts.onStatusChange || function () {};
    this.onEstablish = opts.onEstablish || function () {};
    this.onBackGate = opts.onBackGate || function () {};
    this.onNavigateChapter = opts.onNavigateChapter || function () {};

    this.players = [];
    this.selectedId = null;
    this.view = 'sig';
    this.pickerOpen = false;
    this.pickerFilter = { skin: null, frame: null, definition: null };
    this.catalog = null;
    this.loaded = false;
    this.loading = false;
    this.error = null;
    this._ratingsTimer = null;
    this._bound = false;
    this._portraitBusy = false;
  }

  RosterChapter.prototype.getMode = function () {
    return this.host.getBuildMode ? this.host.getBuildMode() : null;
  };

  RosterChapter.prototype.getShape = function () {
    return (this.host.getShape && this.host.getShape()) || {};
  };

  RosterChapter.prototype.findById = function (id) {
    var key = String(id || '');
    for (var i = 0; i < this.players.length; i++) {
      if (String(this.players[i].id) === key) return this.players[i];
    }
    return null;
  };

  RosterChapter.prototype.selectedIndex = function () {
    var id = this.selectedId;
    for (var i = 0; i < this.players.length; i++) {
      if (String(this.players[i].id) === String(id)) return i;
    }
    return 0;
  };

  RosterChapter.prototype.selectedPlayer = function () {
    return this.findById(this.selectedId) || this.players[0] || null;
  };

  RosterChapter.prototype.heightUsed = function () {
    return this.players.reduce(function (s, p) {
      return s + (Number(p.ht) || 0);
    }, 0);
  };

  RosterChapter.prototype.classUsed = function () {
    var table = this.getShape().class_rank;
    return this.players.reduce(function (s, p) {
      return s + classRank(p.cls, table);
    }, 0);
  };

  RosterChapter.prototype.changedCount = function () {
    return this.players.filter(playerChanged).length;
  };

  RosterChapter.prototype.legality = function () {
    var mode = this.getMode();
    var shape = this.getShape();
    var heightBudget =
      shape.height_budget != null && shape.height_budget !== ''
        ? Number(shape.height_budget)
        : NaN;
    var classBudget =
      shape.class_budget != null && shape.class_budget !== ''
        ? Number(shape.class_budget)
        : NaN;
    var heightUsed = this.heightUsed();
    var classUsed = this.classUsed();
    var capped = mode === 'capped';

    if (!capped) {
      return {
        legal: true,
        reason: null,
        jumpId: null,
        heightUsed: heightUsed,
        classUsed: classUsed,
        heightBudget: heightBudget,
        classBudget: classBudget,
        capped: false,
      };
    }

    var offenders = this.players.filter(function (p) {
      return attrPoolDelta(p) !== 0;
    });
    var classOff = !isNaN(classBudget) && classUsed !== classBudget;
    var heightOff = !isNaN(heightBudget) && heightUsed > heightBudget;
    var legal = !offenders.length && !classOff && !heightOff;
    var reason = null;
    var jumpId = null;
    if (offenders.length) {
      reason =
        '<b>' +
        offenders.length +
        ' player' +
        (offenders.length > 1 ? 's' : '') +
        '</b> ' +
        (offenders.length > 1 ? 'have' : 'has') +
        ' attribute points unplaced.';
      jumpId = offenders[0].id;
    } else if (classOff) {
      var cd = classUsed - classBudget;
      reason =
        'Year budget is <b>' +
        (cd > 0 ? '+' + cd : cd) +
        '</b> against ' +
        classBudget +
        '. It has to match exactly.';
    } else if (heightOff) {
      reason =
        'Height budget is <b>' +
        (heightUsed - heightBudget) +
        '″ over</b> the inherited cap.';
    }
    return {
      legal: legal,
      reason: reason,
      jumpId: jumpId,
      heightUsed: heightUsed,
      classUsed: classUsed,
      heightBudget: heightBudget,
      classBudget: classBudget,
      capped: true,
    };
  };

  RosterChapter.prototype.getStatus = function () {
    var leg = this.legality();
    return {
      legal: leg.legal,
      changed: this.changedCount(),
      reason: leg.reason,
      jumpId: leg.jumpId,
      mode: this.getMode(),
      loaded: this.loaded,
      pending: this.players.some(function (p) {
        return p.ratings_pending;
      }),
    };
  };

  RosterChapter.prototype.draftPayload = function () {
    return {
      view: this.view,
      selected_id: this.selectedId,
      players: this.players.map(function (p) {
        return {
          id: p.id,
          source_player_id: p.source_player_id,
          wizard_player_id: p.wizard_player_id,
          minted_player_id: p.minted_player_id,
          first_name: p.first_name,
          last_name: p.last_name,
          jersey: p.n === '' ? null : Number(p.n),
          class_year: p.cls,
          height_in: p.ht,
          weight_lb: p.ht === p.base.ht ? p.base.wt : null,
          attributes: cloneAttrs(p.attrs),
          walk_on: !!p.wo,
          portrait_locked: !!p.portrait_locked,
          image_id: p.image_id,
          position_ratings: p.ratings,
        };
      }),
    };
  };

  /** Rows for Apply — only authored editor fields; identity bind via order+ids. */
  RosterChapter.prototype.applyRows = function () {
    return this.players.map(function (p) {
      var row = {
        first_name: p.first_name,
        last_name: p.last_name,
        class_year: p.cls,
        height_in: p.ht,
        jersey: p.n === '' ? null : Number(p.n),
        attributes: cloneAttrs(p.attrs),
      };
      if (p.minted_player_id) row.player_id = p.minted_player_id;
      // Top-level image_id — Apply stamp reads row.image_id (not row.meta.image_id).
      if (p.image_id) row.image_id = p.image_id;
      return row;
    });
  };

  RosterChapter.prototype.notify = function () {
    this.onChange();
    this.onStatusChange(this.getStatus());
  };

  RosterChapter.prototype.mount = function () {
    if (!this.root) return;
    this.root.innerHTML =
      '<div class="roster-boot">Loading roster…</div>';
    this.load().catch(
      function (err) {
        this.error = (err && err.message) || 'Could not load roster.';
        this.root.innerHTML =
          '<div class="roster-boot bad">' + escapeHtml(this.error) + '</div>';
      }.bind(this)
    );
  };

  RosterChapter.prototype.load = async function () {
    if (this.loading) return;
    this.loading = true;
    try {
      var host = this.host;
      var replacedOid = host.getReplacedObjectId();
      var draftId = host.getDraftId();
      if (!replacedOid || !draftId) throw new Error('Draft is not ready.');

      var coreRes = await fetch(
        API_CONFIG.buildUrl(
          '/franchise/team-builder/slot-roster?object_id=' + encodeURIComponent(replacedOid)
        ),
        { headers: API_CONFIG.getAuthHeaders() }
      );
      if (!coreRes.ok) throw new Error('Could not load inherited roster.');
      var coreData = await coreRes.json();
      var coreRows = coreData.players || [];

      var woRes = await fetch(API_CONFIG.buildUrl('/franchise/team-builder/wizard-walk-ons'), {
        method: 'POST',
        headers: Object.assign({}, API_CONFIG.getAuthHeaders(), {
          'Content-Type': 'application/json',
        }),
        body: JSON.stringify({
          replaced_object_id: replacedOid,
          draft_id: draftId,
        }),
      });
      if (!woRes.ok) throw new Error('Could not load walk-ons.');
      var woData = await woRes.json();
      if (host.setShapeFromWalkOns) host.setShapeFromWalkOns(woData);

      var players = [];
      for (var i = 0; i < Math.min(C.SCHOLARSHIP_SIZE, coreRows.length); i++) {
        players.push(normalizePlayerRow(coreRows[i], { slot: i, walk_on: false }));
      }
      var walkOns = woData.walk_ons || [];
      for (var w = 0; w < walkOns.length && players.length < C.AUTHORED_ROSTER_SIZE; w++) {
        players.push(
          normalizePlayerRow(walkOns[w], {
            slot: players.length,
            walk_on: true,
          })
        );
      }
      if (players.length !== C.AUTHORED_ROSTER_SIZE) {
        throw new Error(
          'Roster needs 15 players (got ' + players.length + ').'
        );
      }

      var draftRoster = host.getDraftRoster && host.getDraftRoster();
      this._applyDraftOverlay(players, draftRoster);
      this.players = players;
      this.view = (draftRoster && draftRoster.view) || 'sig';
      this.selectedId =
        (draftRoster && draftRoster.selected_id) ||
        (players[0] && players[0].id) ||
        null;
      this.loaded = true;
      this.error = null;
      this.paint();
      await this.ensurePortraits({ forceSlots: [] });
      this.requestRatings();
      this.notify();
    } finally {
      this.loading = false;
    }
  };

  RosterChapter.prototype._applyDraftOverlay = function (players, draft) {
    if (!draft || !draft.players || !draft.players.length) return;
    var byId = {};
    draft.players.forEach(function (row) {
      if (row && row.id) byId[String(row.id)] = row;
    });
    players.forEach(function (p) {
      var row = byId[String(p.id)];
      if (!row) return;
      if (row.first_name != null) p.first_name = String(row.first_name);
      if (row.last_name != null) p.last_name = String(row.last_name);
      p.name = (p.first_name + ' ' + p.last_name).trim();
      if (row.jersey != null && row.jersey !== '') p.n = String(Number(row.jersey));
      if (row.class_year) p.cls = yearAbbrev(row.class_year);
      if (row.height_in != null) {
        p.ht = Math.max(
          C.HEIGHT_MIN_IN,
          Math.min(C.HEIGHT_MAX_IN, Math.round(Number(row.height_in)))
        );
      }
      if (row.attributes) p.attrs = cloneAttrs(row.attributes);
      if (row.portrait_locked != null) p.portrait_locked = !!row.portrait_locked;
      if (row.image_id) p.image_id = row.image_id;
      if (row.minted_player_id) p.minted_player_id = row.minted_player_id;
      if (row.position_ratings) p.ratings = row.position_ratings;
    });
  };

  RosterChapter.prototype.portraitPlayersPayload = function () {
    return this.players.map(function (p) {
      return {
        first_name: p.first_name,
        last_name: p.last_name,
        class_year: p.cls,
        height_in: p.ht,
        weight_lb: p.ht === p.base.ht ? p.base.wt : null,
        attributes: cloneAttrs(p.attrs),
        player_id: p.minted_player_id || undefined,
        image_id: p.image_id || undefined,
        position_ratings: p.ratings || undefined,
      };
    });
  };

  RosterChapter.prototype._mergePortraitAssignments = function (portraits) {
    if (!Array.isArray(portraits)) return;
    for (var i = 0; i < this.players.length && i < portraits.length; i++) {
      var a = portraits[i] || {};
      var p = this.players[i];
      if (a.player_id) p.minted_player_id = String(a.player_id);
      if (a.image_id) p.image_id = String(a.image_id);
      p.portrait_meta = {
        skin: a.skin,
        frame: a.frame,
        definition: a.definition,
        source: a.source,
      };
      if (a.source === 'picker') p.portrait_locked = true;
    }
  };

  RosterChapter.prototype.ensurePortraits = async function (opts) {
    opts = opts || {};
    if (this._portraitBusy) return;
    this._portraitBusy = true;
    try {
      var body = {
        replaced_object_id: this.host.getReplacedObjectId(),
        draft_id: this.host.getDraftId(),
        players: this.portraitPlayersPayload(),
        force_reassign: !!opts.forceAll,
      };
      if (opts.forceSlots && opts.forceSlots.length) {
        body.force_reassign_slots = opts.forceSlots.slice();
      }
      var res = await fetch(API_CONFIG.buildUrl('/franchise/team-builder/portraits/assign'), {
        method: 'POST',
        headers: Object.assign({}, API_CONFIG.getAuthHeaders(), {
          'Content-Type': 'application/json',
        }),
        body: JSON.stringify(body),
      });
      if (!res.ok) return;
      var data = await res.json();
      this._mergePortraitAssignments(data.portraits);
      this.paint();
      this.notify();
    } finally {
      this._portraitBusy = false;
    }
  };

  RosterChapter.prototype.requestRatings = function () {
    var self = this;
    this.players.forEach(function (p) {
      p.ratings_pending = true;
    });
    this.paintRatingsOnly();
    this.onStatusChange(this.getStatus());
    clearTimeout(this._ratingsTimer);
    this._ratingsTimer = setTimeout(function () {
      self._fetchRatings();
    }, C.RATINGS_DEBOUNCE_MS);
  };

  RosterChapter.prototype._fetchRatings = async function () {
    var self = this;
    var payload = {
      players: this.players.map(function (p) {
        var attrs = {};
        C.RT_ATTR_KEYS.forEach(function (k) {
          attrs[k] = p.attrs[k];
        });
        return {
          player_id: p.id,
          height: p.ht,
          attributes: attrs,
        };
      }),
    };
    try {
      var res = await fetch(API_CONFIG.buildUrl('/franchise/team-builder/position-ratings'), {
        method: 'POST',
        headers: Object.assign({}, API_CONFIG.getAuthHeaders(), {
          'Content-Type': 'application/json',
        }),
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error('ratings failed');
      var data = await res.json();
      var rows = data.players || [];
      rows.forEach(function (row, idx) {
        var id = row.player_id != null ? String(row.player_id) : null;
        var p = (id && self.findById(id)) || self.players[idx];
        if (!p) return;
        p.ratings = row.position_ratings || null;
        if (p.ratings) p.pos = primaryPos(p.ratings);
        p.ratings_pending = false;
      });
      self.players.forEach(function (p) {
        if (p.ratings_pending && p.ratings) p.ratings_pending = false;
      });
    } catch (_) {
      // Keep pending false only when we have prior ratings; never invent values.
      this.players.forEach(function (p) {
        if (p.ratings) p.ratings_pending = false;
      });
    }
    this.paint();
    this.onStatusChange(this.getStatus());
  };

  RosterChapter.prototype.selectById = function (id) {
    this.selectedId = id;
    this.view = 'sig';
    this.paint();
    this.notify();
  };

  RosterChapter.prototype.patchSelected = function (fn) {
    var id = this.selectedId;
    this.players = this.players.map(function (p) {
      return String(p.id) === String(id) ? fn(p) : p;
    });
  };

  RosterChapter.prototype.commitRelease = function () {
    this.requestRatings();
    this.notify();
  };

  RosterChapter.prototype.setAttr = function (code, value) {
    var p0 = this.selectedPlayer();
    if (!p0) return;
    var current = Number(p0.attrs[code]);
    if (isNaN(current)) current = C.ATTR_MIN;
    var v = Math.max(C.ATTR_MIN, Math.min(C.ATTR_MAX, Math.round(Number(value) || C.ATTR_MIN)));
    var capped = this.getMode() === 'capped';
    // Capped: cannot spend past this player's budget — free points first by lowering others.
    if (capped && v > current) {
      v = Math.min(v, cappedAttrMax(p0, code));
    }
    this.patchSelected(function (p) {
      var next = Object.assign({}, p, { attrs: Object.assign({}, p.attrs) });
      next.attrs[code] = v;
      return next;
    });
    var p = this.selectedPlayer();
    if (!p) return;
    var host = document.getElementById('tb-insp');
    if (host) {
      var row = host.querySelector('.attr[data-code="' + code + '"]');
      if (row) {
        var base = p.base.attrs[code];
        var moved = v !== base;
        var d = v - base;
        row.classList.toggle('moved', moved);
        var fill = row.querySelector('.fill');
        if (fill) {
          fill.style.width = (v / 99) * 100 + '%';
          fill.style.background = scaleColor(v);
        }
        var num = row.querySelector('.num');
        if (num) num.textContent = String(v);
        var dlt = row.querySelector('.dlt');
        if (dlt) {
          dlt.textContent = moved ? (d > 0 ? '+' + d : String(d)) : '—';
          dlt.style.color = moved ? 'var(--org)' : 'var(--tx3)';
        }
        var input = row.querySelector('input[data-attr]');
        if (input && Number(input.value) !== v) input.value = String(v);
      }
      if (capped) this._syncCappedAttrLimits(host, p);
      var poolEl = host.querySelector('.pool');
      if (poolEl) {
        var pool = attrPoolDelta(p);
        var tot = coreTotal(p.attrs);
        var vEl = poolEl.querySelector('.pool-l .v');
        if (vEl) {
          vEl.innerHTML =
            tot +
            '<span> / ' +
            p.budget +
            (capped ? '' : ' inherited') +
            '</span>';
        }
        var nEl = poolEl.querySelector('.pool-r .n');
        var cEl = poolEl.querySelector('.pool-r .c');
        if (capped) {
          poolEl.classList.toggle('ok', pool === 0);
          poolEl.classList.toggle('bad', pool !== 0);
          if (nEl) {
            nEl.textContent = pool === 0 ? '0' : pool > 0 ? '+' + pool : String(pool);
            nEl.style.color = pool === 0 ? 'var(--grn)' : 'var(--red)';
          }
          if (cEl) {
            cEl.textContent =
              pool === 0 ? 'all placed' : pool > 0 ? 'left to place' : 'over budget';
          }
        } else {
          var vs = tot - p.budget;
          if (nEl) {
            nEl.textContent = vs === 0 ? '—' : vs > 0 ? '+' + vs : String(vs);
            nEl.style.color = vs === 0 ? 'var(--tx2)' : 'var(--org)';
          }
        }
      }
    }
    this.paintBoard();
    this.paintBudgets();
  };

  /** Refresh range max so thumbs cannot drag into unfunded points (capped only). */
  RosterChapter.prototype._syncCappedAttrLimits = function (host, p) {
    if (!host || !p) return;
    var pool = attrPoolDelta(p);
    host.querySelectorAll('input[data-attr]').forEach(function (input) {
      var code = input.getAttribute('data-attr');
      var cur = Number(p.attrs[code]);
      if (isNaN(cur)) cur = C.ATTR_MIN;
      var max = Math.min(C.ATTR_MAX, cur + Math.max(0, pool));
      input.max = String(max);
    });
  };

  RosterChapter.prototype.setClass = function (cls) {
    var c = yearAbbrev(cls);
    this.patchSelected(function (p) {
      return Object.assign({}, p, { cls: c });
    });
    this.commitRelease();
    this.paint();
  };

  RosterChapter.prototype.setHeight = function (ht) {
    var h = Math.round(Number(ht));
    if (h < C.HEIGHT_MIN_IN || h > C.HEIGHT_MAX_IN) return;
    var idx = this.selectedIndex();
    var p = this.players[idx];
    if (!p || p.ht === h) return;
    this.patchSelected(function (pl) {
      return Object.assign({}, pl, { ht: h });
    });
    this.paint();
    this.commitRelease();
  };

  RosterChapter.prototype.setFirst = function (v) {
    this.patchSelected(function (p) {
      var first = String(v || '').slice(0, 16);
      return Object.assign({}, p, {
        first_name: first,
        name: (first + ' ' + p.last_name).trim(),
      });
    });
    this.paintBoard();
    this.notify();
  };

  RosterChapter.prototype.setLast = function (v) {
    this.patchSelected(function (p) {
      var last = String(v || '').slice(0, 18);
      return Object.assign({}, p, {
        last_name: last,
        name: (p.first_name + ' ' + last).trim(),
      });
    });
    this.paintBoard();
    this.notify();
  };

  RosterChapter.prototype.setNumber = function (v) {
    var d = String(v).replace(/[^0-9]/g, '').slice(0, 2);
    this.patchSelected(function (p) {
      return Object.assign({}, p, { n: d === '' ? '' : String(Number(d)) });
    });
    this.paintBoard();
    this.notify();
  };

  RosterChapter.prototype.resetPlayer = function () {
    var idx = this.selectedIndex();
    this.patchSelected(function (p) {
      return Object.assign({}, p, {
        attrs: cloneAttrs(p.base.attrs),
        ht: p.base.ht,
        cls: p.base.cls,
        n: p.base.n,
        first_name: p.base.first_name,
        last_name: p.base.last_name,
        name: p.base.name,
      });
    });
    this.paint();
    this.commitRelease();
  };

  RosterChapter.prototype.randomizePortrait = async function () {
    var idx = this.selectedIndex();
    var p = this.players[idx];
    if (!p) return;
    // Randomize clears lock and re-rolls against current height/attrs.
    p.portrait_locked = false;
    try {
      var res = await fetch(API_CONFIG.buildUrl('/franchise/team-builder/portraits/reroll'), {
        method: 'POST',
        headers: Object.assign({}, API_CONFIG.getAuthHeaders(), {
          'Content-Type': 'application/json',
        }),
        body: JSON.stringify({
          replaced_object_id: this.host.getReplacedObjectId(),
          draft_id: this.host.getDraftId(),
          slot: idx,
          players: this.portraitPlayersPayload(),
        }),
      });
      if (!res.ok) return;
      var data = await res.json();
      this._mergePortraitAssignments(data.portraits);
      var cur = this.players[idx];
      if (cur) cur.portrait_locked = false;
      this.paint();
      this.notify();
    } catch (_) {}
  };

  RosterChapter.prototype.pickPortrait = async function (imageId) {
    var idx = this.selectedIndex();
    if (!imageId) return;
    try {
      var res = await fetch(API_CONFIG.buildUrl('/franchise/team-builder/portraits/pick'), {
        method: 'POST',
        headers: Object.assign({}, API_CONFIG.getAuthHeaders(), {
          'Content-Type': 'application/json',
        }),
        body: JSON.stringify({
          replaced_object_id: this.host.getReplacedObjectId(),
          draft_id: this.host.getDraftId(),
          slot: idx,
          image_id: imageId,
          players: this.portraitPlayersPayload(),
        }),
      });
      if (!res.ok) return;
      var data = await res.json();
      this._mergePortraitAssignments(data.portraits);
      var cur = this.players[idx];
      if (cur) cur.portrait_locked = true;
      this.pickerOpen = false;
      this.paint();
      this.notify();
    } catch (_) {}
  };

  RosterChapter.prototype.openPicker = async function () {
    this.pickerOpen = true;
    this.pickerFilter = { skin: null, frame: null, definition: null };
    this.paint();
    if (!this.catalog) {
      try {
        var res = await fetch(API_CONFIG.buildUrl('/franchise/team-builder/portraits/catalog'), {
          headers: API_CONFIG.getAuthHeaders(),
        });
        if (res.ok) this.catalog = await res.json();
      } catch (_) {}
      this.paint();
    }
  };

  RosterChapter.prototype.fitEstablishLabel = function (btn, programName) {
    if (!btn) return;
    var label = 'Establish ' + (programName || 'Program');
    btn.textContent = label;
    btn.style.fontSize = '';
    var max = 16;
    var min = 11;
    var size = max;
    btn.style.fontSize = size + 'px';
    while (size > min && btn.scrollWidth > btn.clientWidth + 1) {
      size -= 0.5;
      btn.style.fontSize = size + 'px';
    }
  };

  /* ---------- paint ---------- */

  RosterChapter.prototype.paint = function () {
    if (!this.root || !this.loaded) return;
    var leg = this.legality();
    var mode = this.getMode();
    var capped = mode === 'capped';
    var p = this.selectedPlayer();

    this.root.innerHTML =
      '<div class="budgetbar" id="tb-budgetbar"></div>' +
      '<div class="work' +
      (this.view === 'grid' ? ' wide' : '') +
      '" id="tb-work">' +
      '<div class="pane" id="tb-board"></div>' +
      (this.view === 'sig' ? '<div class="pane insp" id="tb-insp"></div>' : '') +
      '</div>' +
      (this.pickerOpen ? '<div id="tb-picker-host"></div>' : '');

    this.paintBudgets();
    this.paintBoard();
    if (this.view === 'sig' && p) this.paintInspector();
    if (this.pickerOpen) this.paintPicker();
    this._bindOnce();
  };

  RosterChapter.prototype.paintBudgets = function () {
    var host = document.getElementById('tb-budgetbar');
    if (!host) return;
    var leg = this.legality();
    var capped = leg.capped;
    var hu = leg.heightUsed;
    var hb = leg.heightBudget;
    var cu = leg.classUsed;
    var cb = leg.classBudget;

    function meterHtml(k, rule, used, cap, unit, exact, info) {
      var diff = used - cap;
      var pct = cap > 0 ? Math.min(100, (used / cap) * 100) : 0;
      if (info) {
        return (
          '<div class="meter">' +
          '<div class="mt-top"><div class="mt-k">' +
          escapeHtml(k) +
          '</div><div class="mt-rule">reference</div></div>' +
          '<div class="mt-v">' +
          used +
          '<span>/ ' +
          cap +
          ' inherited</span></div>' +
          '<div class="mt-track"><div class="mt-fill" style="width:' +
          pct +
          '%;background:rgba(255,255,255,.4)"></div></div>' +
          '<div class="mt-note mute">' +
          (diff === 0 ? 'unchanged' : (diff > 0 ? '+' + diff : diff) + (unit || '') + ' vs inherited') +
          ' — no cap</div></div>'
        );
      }
      var over = exact ? used !== cap : used > cap;
      var color = over ? '#ff6d6d' : diff === 0 ? '#34EC27' : 'rgba(255,255,255,.42)';
      var note;
      if (exact) {
        note =
          diff === 0
            ? '<span class="ok">Exact match — spent</span>'
            : '<span class="bad">' +
              (diff > 0 ? '+' + diff : diff) +
              ' — must land on ' +
              cap +
              '</span>';
      } else {
        note =
          diff === 0
            ? '<span class="ok">At the cap</span>'
            : diff < 0
              ? '<span class="mute">' + Math.abs(diff) + (unit || '') + ' under — nothing to do</span>'
              : '<span class="bad">' + diff + (unit || '') + ' over the cap</span>';
      }
      return (
        '<div class="meter' +
        (over ? ' bad' : diff === 0 && exact ? ' exact' : '') +
        '">' +
        '<div class="mt-top"><div class="mt-k">' +
        escapeHtml(k) +
        '</div><div class="mt-rule">' +
        escapeHtml(rule) +
        '</div></div>' +
        '<div class="mt-v">' +
        used +
        '<span>/ ' +
        cap +
        '</span></div>' +
        '<div class="mt-track"><div class="mt-fill" style="width:' +
        pct +
        '%;background:' +
        color +
        '"></div></div>' +
        '<div class="mt-note">' +
        note +
        '</div></div>'
      );
    }

    var meters;
    if (capped) {
      meters =
        meterHtml('Height — team', 'under ok', hu, hb, '″', false, false) +
        meterHtml('Year — team', 'exact', cu, cb, '', true, false) +
        '<div class="verdict' +
        (leg.legal ? ' ok' : ' bad') +
        '">' +
        '<div class="vd-k">' +
        (leg.legal ? 'Legal' : 'Not legal') +
        '</div>' +
        '<div class="vd-t">' +
        (leg.legal ? 'All three budgets satisfied.' : leg.reason || '') +
        '</div>' +
        (!leg.legal && leg.jumpId
          ? '<button type="button" class="jump" data-jump="' +
            escapeHtml(leg.jumpId) +
            '">Take me there</button>'
          : '') +
        '</div>';
    } else {
      meters =
        meterHtml('Height — team', '', hu, hb, '″', false, true) +
        meterHtml('Year — team', '', cu, cb, '', false, true) +
        '<div class="verdict bad">' +
        '<div class="vd-k">Not eligible</div>' +
        '<div class="vd-t">Written permanently when the program is established.</div>' +
        '</div>';
    }

    host.innerHTML =
      '<div class="bb-lede"><h1>Edit Your Roster</h1></div>' + meters;

    var jump = host.querySelector('[data-jump]');
    if (jump) {
      var self = this;
      jump.addEventListener('click', function () {
        self.selectById(jump.getAttribute('data-jump'));
      });
    }
  };

  RosterChapter.prototype.paintBoard = function () {
    var host = document.getElementById('tb-board');
    if (!host) return;
    var self = this;
    var selId = this.selectedId;
    var mode = this.getMode();
    var capped = mode === 'capped';

    var head =
      '<div class="pane-hd"><h2>Roster</h2><div class="sp"></div>' +
      '<div class="seg">' +
      '<button type="button" data-view="sig"' +
      (this.view === 'sig' ? ' class="on"' : '') +
      '>Signature</button>' +
      '<button type="button" data-view="grid"' +
      (this.view === 'grid' ? ' class="on"' : '') +
      '>Full grid</button>' +
      '</div></div>';

    if (this.view === 'grid') {
      var th =
        '<th class="l">Player</th><th>Cl</th><th>Ht</th><th>Pos</th>' +
        '<th title="Position rating at the listed slot">RT</th>';
      C.CORE_12_ATTRS.forEach(function (t) {
        th += '<th>' + t.code + '</th>';
      });
      th += '<th>Tot</th>';
      var body = this.players
        .map(function (p) {
          var pool = attrPoolDelta(p);
          var bad = capped && pool !== 0;
          var rt =
            p.ratings_pending || !p.ratings
              ? '···'
              : String(p.ratings[p.pos] != null ? p.ratings[p.pos] : '—');
          var cells = C.CORE_12_ATTRS.map(function (t) {
            return (
              '<td><span class="av" style="background:' +
              scaleColor(p.attrs[t.code]) +
              '">' +
              p.attrs[t.code] +
              '</span></td>'
            );
          }).join('');
          return (
            '<tr data-id="' +
            escapeHtml(p.id) +
            '"' +
            (String(p.id) === String(selId) ? ' class="sel"' : '') +
            ' title="Edit this player">' +
            '<td class="l nm">' +
            escapeHtml(p.n === '' ? '—' : p.n) +
            ' · ' +
            escapeHtml(p.name) +
            (p.wo ? ' <em class="wo-tag">WO</em>' : '') +
            '</td>' +
            '<td>' +
            escapeHtml(p.cls) +
            '</td><td>' +
            feetInches(p.ht) +
            '</td>' +
            '<td><span class="pos" style="background:' +
            (C.POS_COLOR[p.pos] || '#888') +
            '">' +
            escapeHtml(p.pos) +
            '</span></td>' +
            '<td style="font-family:var(--disp);font-size:15px;color:#fff">' +
            escapeHtml(rt) +
            '</td>' +
            cells +
            '<td style="font-family:var(--disp);font-size:15px;color:' +
            (pool === 0 || !capped ? '#fff' : '#ff6d6d') +
            '">' +
            coreTotal(p.attrs) +
            '</td></tr>'
          );
        })
        .join('');
      host.innerHTML =
        head +
        '<div style="overflow-x:auto"><table class="gr"><thead><tr>' +
        th +
        '</tr></thead><tbody>' +
        body +
        '</tbody></table></div>';
    } else {
      function rowHtml(p) {
        var pool = attrPoolDelta(p);
        var bad = capped && pool !== 0;
        var edited = playerChanged(p);
        var rt =
          p.ratings_pending || !p.ratings
            ? '·  ·  ·'
            : String(p.ratings[p.pos] != null ? p.ratings[p.pos] : '—');
        var sig = C.CORE_12_ATTRS.map(function (t) {
          var v = p.attrs[t.code];
          return (
            '<i title="' +
            t.code +
            ' ' +
            v +
            '" style="height:' +
            Math.max(2, Math.round((v / 99) * 20)) +
            'px;background:' +
            scaleColor(v) +
            '"></i>'
          );
        }).join('');
        return (
          '<div class="bd-row' +
          (String(p.id) === String(selId) ? ' sel' : '') +
          (bad ? ' bad' : '') +
          '" data-id="' +
          escapeHtml(p.id) +
          '">' +
          '<div class="bd-num">' +
          escapeHtml(p.n === '' ? '—' : p.n) +
          '</div>' +
          portraitThumb(p) +
          '<div class="bd-name">' +
          escapeHtml(p.name) +
          (p.wo ? '<em>WO</em>' : '') +
          '<span class="cls' +
          (p.cls !== p.base.cls ? ' chg' : '') +
          '">' +
          escapeHtml(p.cls) +
          '</span></div>' +
          '<div class="bd-ht' +
          (p.ht !== p.base.ht ? ' chg' : '') +
          '">' +
          feetInches(p.ht) +
          '</div>' +
          '<div><span class="pos" style="background:' +
          (C.POS_COLOR[p.pos] || '#888') +
          '">' +
          escapeHtml(p.pos) +
          '</span></div>' +
          '<div class="bd-grade' +
          (p.ratings_pending || !p.ratings ? ' pending' : '') +
          '">' +
          escapeHtml(rt) +
          '</div>' +
          '<div class="sig">' +
          sig +
          '</div>' +
          '<div>' +
          (bad
            ? '<span class="mk bad" title="Attribute points unspent"></span>'
            : edited
              ? '<span class="mk edit" title="Changed from inherited"></span>'
              : '') +
          '</div></div>'
        );
      }

      function portraitThumb(p) {
        var bg = 'rgba(255,255,255,.08)';
        var img = '';
        if (p.image_id && API_CONFIG.getRecruitImageUrl) {
          img =
            '<img src="' +
            escapeHtml(API_CONFIG.getRecruitImageUrl(p.image_id, { size: 'card' })) +
            '" alt="" />';
        }
        return (
          '<div class="pt" style="background:' +
          bg +
          '">' +
          img +
          '<b>' +
          escapeHtml(initials(p.name)) +
          '</b></div>'
        );
      }

      var sch = this.players.slice(0, C.SCHOLARSHIP_SIZE).map(rowHtml).join('');
      var wo = this.players.slice(C.SCHOLARSHIP_SIZE).map(rowHtml).join('');
      host.innerHTML =
        head +
        '<div class="bd-head">' +
        '<div style="text-align:right">#</div><div></div><div>Player</div><div>Ht</div>' +
        '<div>Pos</div><div style="text-align:center" title="Position rating at the listed slot">RT</div>' +
        '<div>Signature · SC→FT</div><div></div></div>' +
        sch +
        '<div class="bd-split">Walk-ons — 3</div>' +
        wo +
        '<div class="bd-foot"><span><i style="background:#F79420"></i>Changed from inherited</span></div>';
    }

    host.querySelectorAll('[data-view]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        self.view = btn.getAttribute('data-view');
        self.paint();
        self.notify();
      });
    });
    host.querySelectorAll('[data-id]').forEach(function (row) {
      row.addEventListener('click', function () {
        self.selectById(row.getAttribute('data-id'));
      });
    });
  };

  RosterChapter.prototype.paintRatingsOnly = function () {
    // Full paint is cheap enough; keep API for status strip callers.
    if (this.loaded) this.paintBoard();
    var insp = document.getElementById('tb-insp');
    if (insp && this.view === 'sig') this.paintInspector();
  };

  RosterChapter.prototype.paintInspectorAttrs = function () {
    // Re-paint inspector pool + sliders without full remount when dragging.
    if (this.view === 'sig') this.paintInspector();
  };

  RosterChapter.prototype.paintInspector = function () {
    var host = document.getElementById('tb-insp');
    var p = this.selectedPlayer();
    if (!host || !p) return;
    var self = this;
    var leg = this.legality();
    var capped = leg.capped;
    var pool = attrPoolDelta(p);
    var htDiff = leg.heightUsed - leg.heightBudget;
    var clDiff = leg.classUsed - leg.classBudget;
    var pending = p.ratings_pending || !p.ratings;

    var grades = C.POSITIONS.map(function (pos) {
      var v =
        pending || !p.ratings
          ? '··'
          : String(p.ratings[pos] != null ? p.ratings[pos] : '—');
      return (
        '<div class="gcard' +
        (pending ? ' pending' : '') +
        '"><span class="gp" style="background:' +
        (C.POS_COLOR[pos] || '#888') +
        '">' +
        pos +
        '</span><span class="gv">' +
        escapeHtml(v) +
        '</span></div>'
      );
    }).join('');

    var weightHtml;
    if (p.ht === p.base.ht && p.base.wt != null && !isNaN(p.base.wt)) {
      weightHtml =
        '<div class="wt">Weight <b style="color:var(--tx2)">' +
        Math.round(p.base.wt) +
        ' lb</b> · inherited until height changes</div>';
    } else {
      weightHtml = '<div class="wt">Weight · Set at creation</div>';
    }

    var poolHtml;
    if (capped) {
      poolHtml =
        '<div class="pool' +
        (pool === 0 ? ' ok' : ' bad') +
        '"><div class="pool-l"><div class="k">Attribute points — this player</div>' +
        '<div class="v">' +
        coreTotal(p.attrs) +
        '<span> / ' +
        p.budget +
        '</span></div></div>' +
        '<div class="pool-r"><div class="n" style="color:' +
        (pool === 0 ? 'var(--grn)' : 'var(--red)') +
        '">' +
        (pool === 0 ? '0' : pool > 0 ? '+' + pool : pool) +
        '</div><div class="c">' +
        (pool === 0 ? 'all placed' : pool > 0 ? 'left to place' : 'over budget') +
        '</div></div></div>';
    } else {
      var vs = coreTotal(p.attrs) - p.budget;
      poolHtml =
        '<div class="pool"><div class="pool-l"><div class="k">Attribute points — this player</div>' +
        '<div class="v">' +
        coreTotal(p.attrs) +
        '<span> / ' +
        p.budget +
        ' inherited</span></div></div>' +
        '<div class="pool-r"><div class="n" style="color:' +
        (vs === 0 ? 'var(--tx2)' : 'var(--org)') +
        '">' +
        (vs === 0 ? '—' : vs > 0 ? '+' + vs : vs) +
        '</div><div class="c">vs inherited</div></div></div>';
    }

    // Attribute groups — ND/Endurance alone with persistent copy.
    var groups = [];
    C.CORE_12_ATTRS.forEach(function (t) {
      if (!groups.length || groups[groups.length - 1].cat !== t.cat) {
        groups.push({ cat: t.cat, items: [t] });
      } else {
        groups[groups.length - 1].items.push(t);
      }
    });

    function attrRow(t) {
      var value = p.attrs[t.code];
      var base = p.base.attrs[t.code];
      var moved = value !== base;
      var d = value - base;
      var isNd = t.code === 'ND';
      var rangeMax = capped ? cappedAttrMax(p, t.code) : C.ATTR_MAX;
      return (
        '<div class="attr' +
        (moved ? ' moved' : '') +
        (isNd ? ' attr-nd' : '') +
        '" data-code="' +
        t.code +
        '">' +
        '<div class="code" title="' +
        escapeHtml(t.name) +
        '">' +
        t.code +
        '</div>' +
        '<div class="trk"><div class="rail"><div class="fill" style="width:' +
        (value / 99) * 100 +
        '%;background:' +
        scaleColor(value) +
        '"></div></div>' +
        '<div class="tick" style="left:' +
        (base / 99) * 100 +
        '%" title="Inherited ' +
        base +
        '"></div>' +
        '<input type="range" min="' +
        C.ATTR_MIN +
        '" max="' +
        rangeMax +
        '" value="' +
        value +
        '" data-attr="' +
        t.code +
        '" /></div>' +
        '<div class="num">' +
        value +
        '</div>' +
        '<div class="dlt" style="color:' +
        (moved ? 'var(--org)' : 'var(--tx3)') +
        '">' +
        (moved ? (d > 0 ? '+' + d : d) : '—') +
        '</div></div>'
      );
    }

    var col0 = groups.slice(0, 3);
    var col1 = groups.slice(3);
    function colHtml(col) {
      return col
        .map(function (group) {
          var cat = C.ATTR_CATS[group.cat] || { label: group.cat, color: '#aaa' };
          return (
            '<div class="' +
            (group.cat === 'endurance' ? 'attr-group-nd' : '') +
            '">' +
            '<div class="catrow"><span style="color:' +
            cat.color +
            '">' +
            escapeHtml(cat.label) +
            '</span><i></i></div>' +
            group.items.map(attrRow).join('') +
            '</div>'
          );
        })
        .join('');
    }

    var legend = C.CORE_12_ATTRS.map(function (t) {
      var cat = C.ATTR_CATS[t.cat] || { color: '#aaa' };
      return (
        '<span' +
        (t.code === 'ND' ? ' class="alegend-nd"' : '') +
        '><b style="color:' +
        cat.color +
        '">' +
        t.code +
        '</b><i>' +
        escapeHtml(t.name) +
        '</i></span>'
      );
    }).join('');

    var img = '';
    if (p.image_id && API_CONFIG.getRecruitImageUrl) {
      img =
        '<img src="' +
        escapeHtml(API_CONFIG.getRecruitImageUrl(p.image_id, { size: 'modal' })) +
        '" alt="" />';
    }

    host.innerHTML =
      '<div class="insp-hd">' +
      '<div><div class="pt-lg" data-open-picker style="background:rgba(255,255,255,.08)">' +
      img +
      '<b>' +
      escapeHtml(initials(p.name)) +
      '</b>' +
      '<div class="pt-ov">' +
      '<button type="button" data-open-picker>Choose</button>' +
      '<button type="button" data-randomize>Randomize</button>' +
      '</div></div>' +
      '<div class="pt-cap">' +
      (p.portrait_locked ? 'locked · click to change' : 'auto-assigned · click to override') +
      '</div></div>' +
      '<div class="ih"><div class="ih-top">' +
      '<div class="fld num"><label>Jersey #</label><input data-jersey value="' +
      escapeHtml(p.n) +
      '" inputmode="numeric" maxlength="2" /></div>' +
      '<div class="fld nm"><label>First name</label><input data-first value="' +
      escapeHtml(p.first_name) +
      '" maxlength="16" /></div>' +
      '<div class="fld nm"><label>Last name</label><input data-last value="' +
      escapeHtml(p.last_name) +
      '" maxlength="18" /></div></div>' +
      '<div class="grades">' +
      grades +
      '</div>' +
      (pending ? '<div class="srv">recomputing…</div>' : '') +
      '</div></div>' +
      '<div class="insp-body"><div class="col-l">' +
      '<div><div class="blk-k"><span>Year</span></div><div class="cseg">' +
      C.CLASSES.map(function (c) {
        return (
          '<button type="button" data-cls="' +
          c +
          '" class="' +
          (p.cls === c ? 'on' : '') +
          (c === p.base.cls ? ' base' : '') +
          '"' +
          (c === p.base.cls ? ' title="Inherited"' : '') +
          '>' +
          c +
          '</button>'
        );
      }).join('') +
      '</div>' +
      '<div class="tally' +
      (capped ? (clDiff === 0 ? ' ok' : ' bad') : '') +
      '"><span>Team</span><b>' +
      leg.classUsed +
      ' / ' +
      leg.classBudget +
      '</b><em>' +
      (capped
        ? clDiff === 0
          ? 'exact'
          : clDiff > 0
            ? '+' + clDiff + ' over'
            : clDiff + ' short'
        : 'inherited') +
      '</em></div></div>' +
      '<div><div class="blk-k"><span>Height</span><em>' +
      feetInches(C.HEIGHT_MIN_IN) +
      ' – ' +
      feetInches(C.HEIGHT_MAX_IN) +
      '</em></div>' +
      '<div class="step">' +
      '<button type="button" data-ht-dec' +
      (p.ht <= C.HEIGHT_MIN_IN ? ' disabled' : '') +
      '>–</button>' +
      '<div class="val">' +
      feetInches(p.ht) +
      '<em>' +
      (p.ht !== p.base.ht ? feetInches(p.base.ht) + ' inherited' : 'inherited') +
      '</em></div>' +
      '<button type="button" data-ht-inc' +
      (p.ht >= C.HEIGHT_MAX_IN ? ' disabled' : '') +
      '>+</button></div>' +
      (capped
        ? '<div class="htbar"><div style="height:100%;border-radius:2px;width:' +
          Math.min(100, (leg.heightUsed / leg.heightBudget) * 100) +
          '%;background:' +
          (htDiff > 0 ? '#ff6d6d' : htDiff === 0 ? '#34EC27' : 'rgba(255,255,255,.42)') +
          '"></div></div>' +
          '<div class="tally' +
          (htDiff > 0 ? ' bad' : htDiff === 0 ? ' ok' : '') +
          '"><span>Team</span><b>' +
          leg.heightUsed +
          ' / ' +
          leg.heightBudget +
          '″</b><em>' +
          (htDiff > 0
            ? '+' + htDiff + '″ over'
            : htDiff === 0
              ? 'at the cap'
              : Math.abs(htDiff) + '″ under') +
          '</em></div>'
        : '<div class="tally"><span>Team</span><b>' +
          leg.heightUsed +
          ' / ' +
          leg.heightBudget +
          '″</b><em>inherited</em></div>') +
      weightHtml +
      '</div>' +
      '<div style="margin-top:auto"><button type="button" class="btn ghost sm" style="width:100%" data-revert>Revert to inherited</button></div>' +
      '</div><div class="col-r">' +
      poolHtml +
      '<div class="attrcols"><div>' +
      colHtml(col0) +
      '</div><div>' +
      colHtml(col1) +
      '</div></div>' +
      '<div class="attr-foot"><div class="hint">Ticks mark inherited values.' +
      (capped ? ' Points never move between players.' : '') +
      '</div></div></div></div>' +
      '<div class="alegend">' +
      legend +
      '</div>';

    host.querySelectorAll('[data-open-picker]').forEach(function (el) {
      el.addEventListener('click', function (e) {
        e.stopPropagation();
        self.openPicker();
      });
    });
    var rnd = host.querySelector('[data-randomize]');
    if (rnd) {
      rnd.addEventListener('click', function (e) {
        e.stopPropagation();
        self.randomizePortrait();
      });
    }
    var jersey = host.querySelector('[data-jersey]');
    if (jersey) {
      jersey.addEventListener('input', function () {
        self.setNumber(jersey.value);
      });
    }
    var first = host.querySelector('[data-first]');
    if (first) {
      first.addEventListener('input', function () {
        self.setFirst(first.value);
      });
    }
    var last = host.querySelector('[data-last]');
    if (last) {
      last.addEventListener('input', function () {
        self.setLast(last.value);
      });
    }
    host.querySelectorAll('[data-cls]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        self.setClass(btn.getAttribute('data-cls'));
      });
    });
    var dec = host.querySelector('[data-ht-dec]');
    if (dec) {
      dec.addEventListener('click', function () {
        self.setHeight(p.ht - 1);
      });
    }
    var inc = host.querySelector('[data-ht-inc]');
    if (inc) {
      inc.addEventListener('click', function () {
        self.setHeight(p.ht + 1);
      });
    }
    var rev = host.querySelector('[data-revert]');
    if (rev) {
      rev.addEventListener('click', function () {
        self.resetPlayer();
      });
    }
    host.querySelectorAll('input[data-attr]').forEach(function (input) {
      input.addEventListener('input', function () {
        self.setAttr(input.getAttribute('data-attr'), input.value);
      });
      input.addEventListener('pointerup', function () {
        self.commitRelease();
      });
      input.addEventListener('keyup', function (e) {
        if (e.key === 'ArrowLeft' || e.key === 'ArrowRight' || e.key === 'Home' || e.key === 'End') {
          self.commitRelease();
        }
      });
      input.addEventListener('change', function () {
        self.commitRelease();
      });
    });
  };

  RosterChapter.prototype.paintPicker = function () {
    var host = document.getElementById('tb-picker-host');
    var p = this.selectedPlayer();
    if (!host || !p) return;
    var self = this;
    var entries = (this.catalog && this.catalog.entries) || [];
    var filterSkin = this.pickerFilter.skin || null;
    var filterFrame = this.pickerFilter.frame || null;
    var filterDef = this.pickerFilter.definition || null;

    var visible = entries.filter(function (e) {
      if (filterSkin && e.skin !== filterSkin) return false;
      if (filterFrame && e.frame !== filterFrame) return false;
      if (filterDef && e.definition !== filterDef) return false;
      return true;
    });
    var matchCount = visible.length;

    var skins = Object.keys((this.catalog && this.catalog.counts && this.catalog.counts.skin) || {});
    var frames = Object.keys((this.catalog && this.catalog.counts && this.catalog.counts.frame) || {});
    var defs = Object.keys(
      (this.catalog && this.catalog.counts && this.catalog.counts.definition) || {}
    );

    function chipRow(label, values, key) {
      return (
        '<div><div class="mt-k" style="margin-bottom:5px">' +
        label +
        '</div><div class="builds">' +
        '<button type="button" data-filter-key="' +
        key +
        '" data-filter-val=""' +
        (!self.pickerFilter[key] ? ' class="on"' : '') +
        '>Any</button>' +
        values
          .map(function (v) {
            return (
              '<button type="button" data-filter-key="' +
              key +
              '" data-filter-val="' +
              escapeHtml(v) +
              '"' +
              (self.pickerFilter[key] === v ? ' class="on"' : '') +
              '>' +
              escapeHtml(v) +
              '</button>'
            );
          })
          .join('') +
        '</div></div>'
      );
    }

    host.innerHTML =
      '<div class="ov" data-picker-close>' +
      '<div class="mdl wide" data-picker-modal>' +
      '<div class="mdl-acc"></div>' +
      '<div class="pk-hd"><h3>Portrait</h3>' +
      chipRow('Skin', skins, 'skin') +
      chipRow('Frame', frames, 'frame') +
      chipRow('Build', defs, 'definition') +
      '</div>' +
      '<div class="pk-note"><b>' +
      matchCount +
      ' match' +
      (matchCount === 1 ? '' : 'es') +
      '</b></div>' +
      '<div class="pk-grid">' +
      visible
        .map(function (e) {
          var url =
            API_CONFIG.getRecruitImageUrl &&
            API_CONFIG.getRecruitImageUrl(e.image_id, { size: 'card' });
          return (
            '<div class="pk-i' +
            (e.image_id === p.image_id ? ' on' : '') +
            '" data-pick="' +
            escapeHtml(e.image_id) +
            '">' +
            (url ? '<img src="' + escapeHtml(url) + '" alt="" />' : '<i></i>') +
            '<em>' +
            escapeHtml((e.definition || '').toLowerCase()) +
            '</em></div>'
          );
        })
        .join('') +
      '</div>' +
      '<div class="pk-ft"><div class="hint">Every player already has a portrait — this is an override.</div>' +
      '<button type="button" class="btn ghost sm" data-picker-close>Done</button></div>' +
      '</div></div>';

    host.querySelectorAll('[data-picker-close]').forEach(function (el) {
      el.addEventListener('click', function (e) {
        if (el.classList.contains('ov') && e.target !== el) return;
        self.pickerOpen = false;
        self.paint();
      });
    });
    var modal = host.querySelector('[data-picker-modal]');
    if (modal) {
      modal.addEventListener('click', function (e) {
        e.stopPropagation();
      });
    }
    host.querySelectorAll('[data-filter-key]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var key = btn.getAttribute('data-filter-key');
        var val = btn.getAttribute('data-filter-val') || null;
        self.pickerFilter[key] = val || null;
        self.paintPicker();
      });
    });
    host.querySelectorAll('[data-pick]').forEach(function (el) {
      el.addEventListener('click', function () {
        self.pickPortrait(el.getAttribute('data-pick'));
      });
    });
  };

  RosterChapter.prototype._bindOnce = function () {
    // Event handlers are re-bound per paint on board/inspector nodes.
    this._bound = true;
  };

  global.TeamBuilderRoster = {
    RosterChapter: RosterChapter,
    feetInches: feetInches,
    coreTotal: coreTotal,
    yearAbbrev: yearAbbrev,
  };
})(typeof window !== 'undefined' ? window : globalThis);
