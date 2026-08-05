/**
 * Team Builder — Review curtain.
 * No work on this screen. Context: the program among its conference.
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

  function hexToRgba(hex, a) {
    var h = String(hex || '').replace('#', '');
    if (h.length === 3) {
      h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
    }
    if (h.length !== 6) return 'rgba(30,90,140,' + a + ')';
    var r = parseInt(h.slice(0, 2), 16);
    var g = parseInt(h.slice(2, 4), 16);
    var b = parseInt(h.slice(4, 6), 16);
    return 'rgba(' + r + ',' + g + ',' + b + ',' + a + ')';
  }

  function ReviewChapter(opts) {
    bootDeps();
    this.root = opts.root;
    this.host = opts.host || {};
    this.onBack = opts.onBack || function () {};
    this.onEstablish = opts.onEstablish || function () {};
    this._fontsReady = false;
    this._bound = false;
  }

  ReviewChapter.prototype.mount = function () {
    bootDeps();
    if (!this.root) return;
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
  };

  ReviewChapter.prototype._ctx = function () {
    var host = this.host;
    var id = (host.getIdentity && host.getIdentity()) || {};
    var replaced = (host.getReplaced && host.getReplaced()) || {};
    var mode = host.getBuildMode ? host.getBuildMode() : null;
    var roster = host.getRosterChapter ? host.getRosterChapter() : null;
    var players = roster && roster.loaded ? roster.players || [] : [];
    var status = roster && roster.getStatus ? roster.getStatus() : null;
    var leg = roster && roster.legality ? roster.legality() : null;
    var allTeams = (host.getAllTeams && host.getAllTeams()) || [];
    var conf = Number(replaced.conference);
    var region =
      replaced.region ||
      (global.TeamPicker && typeof TeamPicker.regionFromConference === 'function'
        ? TeamPicker.regionFromConference(conf)
        : '');
    return {
      id: id,
      replaced: replaced,
      mode: mode,
      players: players,
      status: status,
      leg: leg,
      allTeams: allTeams,
      conf: conf,
      region: region,
    };
  };

  ReviewChapter.prototype._conferenceStandings = function (ctx) {
    var conf = ctx.conf;
    var replacedName = ctx.replaced.name;
    var programName = ctx.id.name || 'Program';
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
    return mates.map(function (t) {
      var isMe = String(t.object_id) === String(ctx.replaced.object_id);
      return {
        name: isMe ? programName : t.name,
        conf: '—',
        ov: '—',
        me: isMe,
      };
    });
  };

  ReviewChapter.prototype.paint = function () {
    bootDeps();
    var ctx = this._ctx();
    var id = ctx.id;
    var capped = ctx.mode === 'capped';
    var players = ctx.players;
    var leg = ctx.leg || {};
    var htUsed = leg.heightUsed != null ? leg.heightUsed : 0;
    var htBudget = leg.heightBudget;
    var clUsed = leg.classUsed != null ? leg.classUsed : 0;
    var clBudget = leg.classBudget;
    var changed = ctx.status ? ctx.status.changed : 0;
    var avgHt = players.length ? htUsed / players.length : 0;
    var shape = (C.CLASSES || ['FR', 'SO', 'JR', 'SR'])
      .slice()
      .reverse()
      .map(function (c) {
        var n = players.filter(function (p) {
          return String(p.cls).toUpperCase() === c;
        }).length;
        return n + ' ' + c;
      })
      .join(' · ');

    var atInherited = players.filter(function (p) {
      if (!p.base || !p.base.attrs) return true;
      var codes = C.CORE_12_ATTRS || [];
      for (var i = 0; i < codes.length; i++) {
        var code = codes[i].code;
        if (Number(p.attrs[code]) !== Number(p.base.attrs[code])) return false;
      }
      return true;
    }).length;

    var standings = this._conferenceStandings(ctx);
    var confLabel =
      global.TeamPicker && typeof TeamPicker.formatConferenceLabel === 'function'
        ? TeamPicker.formatConferenceLabel(ctx.conf)
        : ctx.conf >= 1
          ? 'Conference ' + ctx.conf
          : 'Conference';
    var regionLabel = ctx.region
      ? 'Region ' + String(ctx.region).toUpperCase()
      : '';

    var htNote =
      htBudget == null || isNaN(htBudget)
        ? ''
        : htUsed === htBudget
          ? 'at the cap'
          : htBudget - htUsed + '″ under';
    var clNote =
      clBudget == null || isNaN(clBudget)
        ? ''
        : clUsed === clBudget
          ? 'exact'
          : '';

    var rosterHtml = players
      .map(function (p) {
        var pos = p.pos || primaryPos(p.ratings);
        var rt = p.ratings && p.ratings[pos] != null ? p.ratings[pos] : '—';
        var img =
          p.image_id && API_CONFIG.getRecruitImageUrl
            ? '<img src="' +
              escapeHtml(API_CONFIG.getRecruitImageUrl(p.image_id, { size: 'card' })) +
              '" alt="">'
            : '';
        var tone = 'rgba(255,255,255,.12)';
        if (p.portrait_meta && p.portrait_meta.skin_hex) {
          tone = p.portrait_meta.skin_hex;
        }
        return (
          '<div class="pl">' +
          '<div class="pt" style="background:' +
          escapeHtml(tone) +
          '">' +
          img +
          '<i></i><b>' +
          escapeHtml(initials(p.first_name + ' ' + p.last_name)) +
          '</b></div>' +
          '<div class="pl-t"><div class="pl-n"><span>' +
          escapeHtml(p.n === '' || p.n == null ? '—' : p.n) +
          '</span>' +
          escapeHtml((p.first_name || '') + ' ' + (p.last_name || '')) +
          '</div><div class="pl-m">' +
          '<span class="pos-b" style="background:' +
          escapeHtml((C.POS_COLOR && C.POS_COLOR[pos]) || '#4A90D9') +
          '">' +
          escapeHtml(pos) +
          '</span>' +
          '<span class="cl">' +
          escapeHtml(p.cls || '') +
          '</span>' +
          '<span class="ht">' +
          escapeHtml(feetInches(p.ht)) +
          '</span>' +
          (p.wo ? '<span class="wo">WO</span>' : '') +
          '</div></div>' +
          '<div class="rt">' +
          escapeHtml(rt) +
          '</div></div>'
        );
      })
      .join('');

    var standingsRows = standings
      .map(function (s, i) {
        var meStyle = s.me
          ? ' style="--me:' +
            hexToRgba(id.primary, 0.5) +
            ';--me2:' +
            escapeHtml(id.primary || '#1e5a8c') +
            '"'
          : '';
        return (
          '<tr class="' +
          (s.me ? 'me' : '') +
          '"' +
          meStyle +
          '>' +
          '<td class="l nm"><span class="pos">' +
          (i + 1) +
          '</span>' +
          escapeHtml(s.name) +
          '</td>' +
          '<td>' +
          escapeHtml(s.conf) +
          '</td><td>' +
          escapeHtml(s.ov) +
          '</td><td>0–0</td></tr>'
        );
      })
      .join('');

    this.root.innerHTML =
      '<div class="rv">' +
      '<div class="rv-top">' +
      '<div class="rv-eb">Review</div>' +
      '<div class="rv-note">Everything below is still editable until you establish the program.</div>' +
      '</div>' +
      '<div class="hero"><canvas id="tb-rv-banner" aria-label="Program banner"></canvas></div>' +
      '<div class="card" style="margin-top:14px">' +
      '<div class="c-hd"><h2>Roster</h2></div>' +
      '<div class="fifteen">' +
      rosterHtml +
      '</div></div>' +
      '<div class="rv-grid">' +
      '<div class="col">' +
      '<div class="elig' +
      (capped ? '' : ' no') +
      '">' +
      '<div class="elig-v">' +
      (capped ? 'Eligible for online play' : 'Not eligible for online play') +
      '</div>' +
      '<div class="elig-b">Built <b>' +
      (capped ? 'capped' : 'uncapped') +
      '</b>. <b>This cannot be changed later.</b></div></div>' +
      '<div class="card">' +
      '<div class="c-hd"><h2 style="white-space:nowrap">' +
      escapeHtml(confLabel) +
      '</h2>' +
      (regionLabel ? '<div class="sup">' + escapeHtml(regionLabel) + '</div>' : '') +
      '</div>' +
      '<table class="tbl"><thead><tr>' +
      '<th class="l">Program</th><th>Conf</th><th>Overall</th><th>Preseason</th>' +
      '</tr></thead><tbody>' +
      standingsRows +
      '</tbody></table></div></div>' +
      '<div class="col">' +
      '<div class="card"><div class="c-hd"><h2>Team Measures</h2></div><div class="ms">' +
      '<div class="ms-r"><div class="ms-k">Height budget</div><div class="ms-v">' +
      escapeHtml(String(htUsed)) +
      '″' +
      (htNote ? '<em>' + escapeHtml(htNote) + '</em>' : '') +
      '</div></div>' +
      '<div class="ms-r"><div class="ms-k">Year budget</div><div class="ms-v">' +
      escapeHtml(String(clUsed)) +
      (clBudget != null && !isNaN(clBudget) ? ' / ' + escapeHtml(String(clBudget)) : '') +
      (clNote ? '<em class="ok">' + escapeHtml(clNote) + '</em>' : '') +
      '</div></div>' +
      '<div class="ms-r"><div class="ms-k">Attribute points</div><div class="ms-v">' +
      atInherited +
      ' / ' +
      players.length +
      '<em class="' +
      (atInherited === players.length ? 'ok' : 'ch') +
      '">' +
      (atInherited === players.length ? 'all at inherited totals' : 'departed') +
      '</em></div></div>' +
      '<div class="ms-r"><div class="ms-k">Changed from inherited</div><div class="ms-v">' +
      changed +
      '<em class="ch">of fifteen</em></div></div>' +
      '<div class="ms-r"><div class="ms-k">Average Height</div><div class="ms-v">' +
      escapeHtml(feetInches(Math.round(avgHt))) +
      '</div></div>' +
      '<div class="ms-r"><div class="ms-k">Year shape</div><div class="ms-v" style="font-size:15px">' +
      escapeHtml(shape) +
      '</div></div>' +
      '</div></div>' +
      '<div class="card"><div class="c-hd"><h2>Program Details</h2></div><div class="ms">' +
      '<div class="ms-r"><div class="ms-k">Conference</div><div class="ms-v">' +
      escapeHtml(ctx.conf >= 1 ? String(ctx.conf) : '—') +
      '</div></div>' +
      '<div class="ms-r"><div class="ms-k">Region</div><div class="ms-v">' +
      escapeHtml(ctx.region ? String(ctx.region).toUpperCase() : '—') +
      '</div></div>' +
      '<div class="ms-r"><div class="ms-k">Replacing</div><div class="ms-v" style="font-size:17px">' +
      escapeHtml(ctx.replaced.name || '—') +
      '</div></div>' +
      '<div class="ms-r"><div class="ms-k">National Programs</div><div class="ms-v">128</div></div>' +
      '</div></div></div></div>' +
      '<div class="card" style="margin-top:14px"><div class="c-hd"><h2>Home Court</h2></div>' +
      '<div style="padding:12px 16px 16px"><div class="courtwrap">' +
      '<canvas id="tb-rv-court" class="court" aria-label="Home court"></canvas>' +
      '</div></div></div></div>' +
      '<div class="footbar"><div class="fb-in">' +
      '<button type="button" class="btn ghost" id="tb-rv-back">← Back to the Roster</button>' +
      '<div class="fb-t"></div>' +
      '<button type="button" class="btn" id="tb-rv-establish">Establish</button>' +
      '</div></div>';

    this._els = {
      banner: this.root.querySelector('#tb-rv-banner'),
      court: this.root.querySelector('#tb-rv-court'),
      back: this.root.querySelector('#tb-rv-back'),
      establish: this.root.querySelector('#tb-rv-establish'),
    };
    this._bind();
    this._paintBanner();
    this._paintCourt();
    this._fitEstablish();
  };

  ReviewChapter.prototype._bind = function () {
    if (this._bound) return;
    this._bound = true;
    var self = this;
    this.root.addEventListener('click', function (e) {
      var t = e.target;
      if (t && t.id === 'tb-rv-back') {
        self.onBack();
        return;
      }
      if (t && t.id === 'tb-rv-establish') {
        self.onEstablish();
      }
    });
  };

  ReviewChapter.prototype._fitEstablish = function () {
    var btn = this._els && this._els.establish;
    if (!btn) return;
    var name = (this.host.getIdentity && this.host.getIdentity().name) || 'Program';
    var label = 'Establish ' + name;
    btn.textContent = label;
    btn.style.fontSize = '';
    var size = 17;
    var min = 12;
    btn.style.fontSize = size + 'px';
    while (size > min && btn.scrollWidth > btn.clientWidth + 1) {
      size -= 0.5;
      btn.style.fontSize = size + 'px';
    }
  };

  ReviewChapter.prototype._paintBanner = function () {
    var canvas = this._els && this._els.banner;
    if (!canvas || !TGA || typeof TGA.drawBanner !== 'function') return;
    if (!this._fontsReady) return;
    var id = (this.host.getIdentity && this.host.getIdentity()) || {};
    var width = 820;
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

  ReviewChapter.prototype._paintCourt = function () {
    var canvas = this._els && this._els.court;
    if (!canvas || !TCG || typeof TCG.renderCourtCanvas !== 'function') return;
    var id = (this.host.getIdentity && this.host.getIdentity()) || {};
    var resolve =
      global.TeamBuilderIdentity && global.TeamBuilderIdentity.resolveCourtCfg
        ? global.TeamBuilderIdentity.resolveCourtCfg
        : null;
    if (!resolve) return;
    var cfg = resolve(id);
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
    var width = 700;
    canvas.width = width;
    canvas.height = Math.round(width * (TCG.HEIGHT / TCG.WIDTH));
    var ctx = canvas.getContext('2d');
    ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(full, 0, 0, canvas.width, canvas.height);
  };

  global.TeamBuilderReview = {
    ReviewChapter: ReviewChapter,
  };
})(typeof window !== 'undefined' ? window : globalThis);
