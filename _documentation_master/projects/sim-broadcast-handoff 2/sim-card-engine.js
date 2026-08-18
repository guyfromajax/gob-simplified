/* GOB — sim broadcast card engine. Selection + cadence only; copy comes from MOMENT_PACK.
   Consumes emitted per-player deltas (here: a synthetic stream standing in for turns[]).
   Nothing here derives prose — a Moment card is a stat readout, not a play description. */
(function () {
  // Card-priority weights. NOT the event distribution — see EV_MIX. Keeping these separate is
  // the point: how interesting an event is has nothing to do with how often it happens.
  const KIND_BASE = { three: 3.0, bucket: 2.0, paint: 2.2, board: 1.4, dime: 1.6, stock: 2.4, foul: 1.0, miss: 2.0 };
  // Emitted-event mix, tuned so a full run lands near a real box score (~75 a side, FG% ~46).
  const EV_MIX = { three: .70, bucket: 1.30, paint: 1.20, miss: 3.00, board: 2.60, dime: 1.40, stock: .55, foul: .80 };
  const POS_BIAS = {
    PG: { dime: 2.4, three: 1.4, board: .5, paint: .7, stock: 1.2 },
    SG: { three: 1.8, dime: 1.1, board: .6, paint: .8 },
    SF: { three: 1.2, paint: 1.2, board: 1.1, stock: 1.1 },
    PF: { paint: 1.6, board: 2.0, three: .5, dime: .6 },
    C:  { paint: 1.8, board: 2.4, three: .2, dime: .5, stock: 1.4 }
  };
  const KINDS = ['three', 'bucket', 'paint', 'miss', 'board', 'dime', 'stock', 'foul'];
  const COLORS = { green: '#34EC27', blue: '#4A90D9', orange: '#F79420', gold: '#FFD700', red: '#ff6d6d' };

  function mulberry(seed) {
    return function () {
      seed |= 0; seed = seed + 0x6D2B79F5 | 0;
      let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }

  function Engine(o) {
    this.cfg = Object.assign({
      eventEvery: 0.9,    // s of playback between emitted events
      hold: 1.2,          // s a card stays up (flat mode)
      holdMode: 'type',   // 'type' = per-card-type holds below, 'flat' = cfg.hold for all
      holds: { moment: 2.6, run: 2.6, margin: 2.6, context: 2.6 },
      runtime: 85,        // s of playback for a full game
      curve: true,        // escalate density across the game instead of a flat profile
      // every binding gate curves, not just the gap — tightening the gap alone does nothing
      // after Q1 because rest floor / cooldown / event supply become the constraints
      profiles: [
        { gap: 6.5, restFloor: 1.6, playerCool: 15, variety: .35, eventEvery: .40 },
        { gap: 5.5, restFloor: 1.3, playerCool: 13, variety: .35, eventEvery: .36 },
        { gap: 5.0, restFloor: 1.1, playerCool: 11, variety: .30, eventEvery: .34 },
        { gap: 4.2, restFloor: 0.8, playerCool: 8,  variety: .22, eventEvery: .30 }
      ],
      clutchProfile: { gap: 3.4, restFloor: .5, playerCool: 6, variety: 0, eventEvery: .28 },
      clutchFrom: .88,    // fraction of runtime where clutch begins
      clutchMargin: 6,    // ...and only within two possessions — a blowout is not drama
      clutchHold: 2.6,
      restFloor: 1.4,     // s of guaranteed rest after a card exits
      cadenceGap: 4.0,    // s minimum card-to-card (flat mode)
      threshold: 2.6,     // candidate score needed to fire a moment
      playerCool: 15,     // s before the same player can carry another card
      varietyHold: .35    // chance a headliner is passed over for someone quieter
    }, o.cfg || {});
    this.pack = o.pack; this.teams = o.teams;
    this.onCard = o.onCard; this.onRest = o.onRest; this.onLog = o.onLog;
    this.rnd = mulberry(o.seed || 7);
    this.players = [].concat(
      o.away.map(p => Object.assign({}, p, { side: 'away' })),
      o.home.map(p => Object.assign({}, p, { side: 'home' }))
    ).map(p => Object.assign(p, {
      fgm: Math.max(1, Math.round(p.pts * .38)), fga: Math.max(2, Math.round(p.pts * .38) + 3),
      m10: p.pts >= 10, m20: p.pts >= 20, m30: p.pts >= 30, r10: p.reb >= 10, dd: p.pts >= 10 && p.reb >= 10,
      streak: 0
    }));
    this.t = 0; this.nextEvent = this.cfg.eventEvery;
    this.cardUntil = -99; this.lastCardEnd = -99; this.lastFire = -99;
    this.cool = {}; this.run = { side: null, pts: 0 }; this.lastRun = -99;
    this.lastCtx = 8; this.lastMargin = -99; this.ctxI = 0;
    this.counts = { moment: 0, run: 0, margin: 0, context: 0 }; this.suppressed = 0; this.cardTime = 0;
    this.pts = { away: 0, home: 0 };
    this.byQ = [0, 1, 2, 3].map(() => ({ fired: 0, cardTime: 0, span: this.cfg.runtime / 4 }));
    // team totals move with the same event stream the cards read, so the tugs are live
    this.team = {
      away: { reb: 31, to: 9, fb: 6, paint: 18, fgm: 28, fga: 65, tpm: 5, fouls: 7 },
      home: { reb: 27, to: 14, fb: 17, paint: 26, fgm: 30, fga: 63, tpm: 8, fouls: 11 }
    };
    if (o.fromTip) {   // live playback runs a whole game, so start every counter at zero
      this.players.forEach(p => Object.assign(p, {
        pts: 0, reb: 0, ast: 0, fouls: 0, fgm: 0, fga: 0, streak: 0,
        m10: false, m20: false, m30: false, r10: false, dd: false, out: false, sub: false
      }));
      this.team = {
        away: { reb: 0, to: 0, fb: 0, paint: 0, fgm: 0, fga: 0, tpm: 0, fouls: 0 },
        home: { reb: 0, to: 0, fb: 0, paint: 0, fgm: 0, fga: 0, tpm: 0, fouls: 0 }
      };
    }
  }

  Engine.prototype._pick = function (arr, w) {
    let sum = 0; for (const x of w) sum += x;
    let r = this.rnd() * sum;
    for (let i = 0; i < arr.length; i++) { r -= w[i]; if (r <= 0) return arr[i]; }
    return arr[arr.length - 1];
  };

  Engine.prototype._line = function (cat, p, extra) {
    const c = this.pack.categories[cat];
    const line = c.lines[Math.floor(this.rnd() * c.lines.length)];
    const map = Object.assign({
      NAME: (p && p.name ? p.name.replace(/^[A-Z]\. /, '') : '').toUpperCase(),
      PTS: p && p.pts, REB: p && p.reb, AST: p && p.ast, FGM: p && p.fgm, FGA: p && p.fga
    }, extra || {});
    return {
      tag: c.tag, color: COLORS[c.color],
      line: line.replace(/\{(\w+)\}/g, (_, k) => map[k] == null ? '' : map[k])
    };
  };

  Engine.prototype._event = function () {
    const side = this.rnd() < .5 ? 'away' : 'home';
    const pool = this.players.filter(p => p.side === side && !p.out);
    const p = this._pick(pool, pool.map(x => .4 + x.rt / 100 + x.pts / 40));
    const kind = this._pick(KINDS, KINDS.map(k => EV_MIX[k] * ((POS_BIAS[p.pos] || {})[k] || 1)));
    let last = 2, mile = null;
    if (kind === 'three') { p.pts += 3; p.fgm++; p.fga++; last = 3; p.streak += 3; }
    else if (kind === 'bucket' || kind === 'paint') { p.pts += 2; p.fgm++; p.fga++; p.streak += 2; }
    else if (kind === 'miss') { p.fga++; }
    else if (kind === 'board') { p.reb++; p.fga += this.rnd() < .4 ? 1 : 0; }
    else if (kind === 'dime') { p.ast++; }
    else if (kind === 'stock') { /* no box change beyond possession */ }
    else if (kind === 'foul') { p.fouls = Math.min(5, p.fouls + 1); last = p.fouls + 'TH'; }
    if (kind !== 'three' && kind !== 'bucket' && kind !== 'paint') p.streak = 0;
    // ---- team totals ----
    const tm = this.team[side], opp = this.team[side === 'away' ? 'home' : 'away'];
    if (kind === 'three') { tm.fgm++; tm.fga++; tm.tpm++; }
    else if (kind === 'bucket') { tm.fgm++; tm.fga++; }
    else if (kind === 'paint') { tm.fgm++; tm.fga++; tm.paint += 2; }
    else if (kind === 'miss') { tm.fga++; }
    else if (kind === 'board') { tm.reb++; if (this.rnd() < .55) opp.fga++; }
    else if (kind === 'stock') { opp.to++; }
    else if (kind === 'foul') { tm.fouls++; }
    if ((kind === 'bucket' || kind === 'paint') && this.rnd() < .28) tm.fb += 2;
    if (this.rnd() < .12) tm.to++;
    if (!p.m30 && p.pts >= 30) { p.m30 = true; mile = 'milestone30'; }
    else if (!p.m20 && p.pts >= 20) { p.m20 = true; mile = 'milestone20'; }
    else if (!p.m10 && p.pts >= 10) { p.m10 = true; mile = 'milestone10'; }
    if (!p.dd && p.pts >= 10 && p.reb >= 10) { p.dd = true; mile = 'doubleDouble'; }
    else if (!p.r10 && p.reb >= 10) { p.r10 = true; mile = 'boards10'; }
    // run tracking on scoring plays only
    const scored = kind === 'three' ? 3 : (kind === 'bucket' || kind === 'paint') ? 2 : 0;
    if (scored) this.pts[side] += scored;
    if (scored) {
      if (this.run.side === side) this.run.pts += scored;
      else { this.run.side = side; this.run.pts = scored; }
    }
    return { p, kind, side, last, mile, scored };
  };

  Engine.prototype._log = function (e) { if (this.onLog) this.onLog(e); };

  Engine.prototype.phase = function () {
    const c = this.cfg, rt = c.runtime;
    const q = Math.min(3, Math.floor(this.t / (rt / 4)));
    const clutch = c.curve && this.t >= rt * c.clutchFrom && Math.abs(this.pts.home - this.pts.away) <= (c.clutchMargin || 6);
    const p = !c.curve
      ? { gap: c.cadenceGap, restFloor: c.restFloor, playerCool: c.playerCool, variety: c.varietyHold, eventEvery: c.eventEvery }
      : (clutch ? c.clutchProfile : c.profiles[q]);
    return { q: q + 1, qi: q, clutch, gap: p.gap, restFloor: p.restFloor, playerCool: p.playerCool, variety: p.variety, eventEvery: p.eventEvery };
  };

  Engine.prototype._hold = function (kind) {
    const c = this.cfg;
    if (this.phase().clutch) return c.clutchHold;
    return c.holdMode === 'type' ? (c.holds[kind] || c.hold) : c.hold;
  };

  Engine.prototype._fire = function (card) {
    this.cardUntil = this.t + this._hold(card.kind); this.lastFire = this.t;
    this.counts[card.kind]++;
    this.byQ[this.phase().qi].fired++;
    if (card.player) this.cool[card.player] = this.t;
    this._log({ t: this.t, tag: card.tag, text: card.line, fired: true });
    this.onCard(card);
  };

  Engine.prototype.teamStats = function () {
    const a = this.team.away, h = this.team.home;
    const pct = t => (t.fga ? (t.fgm / t.fga * 100) : 0).toFixed(1);
    // [label, away, home, kind, betterIsLow, barPointsLow] — see TEAMSTATS in sim-broadcast-parts.js
    return [
      ['FG%', pct(a), pct(h), 'tug', false, false],
      ['3PT', a.tpm, h.tpm, 'tug', false, false],
      ['PTS IN PAINT', a.paint, h.paint, 'tug', false, false],
      ['FAST BREAK', a.fb, h.fb, 'tug', false, false],
      ['REBOUNDS', a.reb, h.reb, 'tug', false, false],
      ['TURNOVERS', a.to, h.to, 'tug', true, false],
      ['TEAM FOULS', a.fouls, h.fouls, 'tug', true, true]
    ];
  };

  // the Margin card is not its own component — it is whichever live tug has the widest edge
  Engine.prototype._biggestTug = function () {
    const rows = this.teamStats().filter(r => r[3] === 'tug');
    let best = null;
    rows.forEach(([lb, a, h]) => {
      const edge = Math.abs(a - h) / Math.max(a, h, 1);
      if (!best || edge > best.edge) best = { label: lb, away: a, home: h, edge };
    });
    return best;
  };

  Engine.prototype.suspend = function (b) { this.suspended = !!b; };

  Engine.prototype._gate = function (label) {
    const ph = this.phase();
    if (this.suspended) return 'team stats held';
    if (this.t < this.cardUntil) return 'card up';
    if (this.t < this.lastCardEnd + ph.restFloor) return 'rest floor';
    if (this.t < this.lastFire + ph.gap) return 'cadence gap';
    return null;
  };

  Engine.prototype.step = function (dt) {
    this.t += dt;
    const ph = this.phase();
    if (this.t < this.cardUntil) { this.cardTime += dt; this.byQ[ph.qi].cardTime += dt; }
    if (this.cardUntil > -1 && this.t >= this.cardUntil && this.lastCardEnd < this.cardUntil) {
      this.lastCardEnd = this.cardUntil; this.onRest();
    }
    if (this.t < this.nextEvent) return;
    this.nextEvent = this.t + ph.eventEvery * (.7 + this.rnd() * .6);
    const ev = this._event();   // the sim always advances; suspend gates the CARD, never the game
    if (this.suspended) { this.suspended_ticks = (this.suspended_ticks || 0) + 1; if (this.suspended_ticks % 6 === 1) { this.suppressed++; this._log({ t: this.t, tag: 'HELD', text: 'stage is the team panel', fired: false, reason: 'team stats held' }); } return; }

    // --- priority beats: run / margin / context outrank moments but respect cadence ---
    if (this.run.pts >= 8 && this.t - this.lastRun > 14) {
      const g = this._gate();
      if (g) { this.suppressed++; this._log({ t: this.t, tag: 'RUN', text: 'held', fired: false, reason: g }); }
      else {
        const T = this.teams[this.run.side];
        const c = this._line('run', null, { TEAM: T.name.toUpperCase(), RUN: this.run.pts + '–0' });
        this.lastRun = this.t; this.run = { side: null, pts: 0 };
        return this._fire({ kind: 'run', tag: c.tag, color: c.color, line: c.line, sub: 'unanswered · ' + Math.round(this.t) + 's' });
      }
    }
    if (this.t - this.lastMargin > 26 && this.rnd() < .18) {
      if (this.phase().clutch) { this.suppressed++; this._log({ t: this.t, tag: 'MARGIN', text: 'held', fired: false, reason: 'clutch — no analysis' }); }
      else {
      const g = this._gate();
      if (!g) {
        this.lastMargin = this.t;
        const tug = this._biggestTug();
        return this._fire({
          kind: 'margin', tag: tug.label, color: COLORS.blue, line: tug.label,
          margin: { label: tug.label, away: tug.away, home: tug.home, awayName: this.teams.away.abbr, homeName: this.teams.home.abbr },
          sub: 'same tug, promoted'
        });
      }
      this.suppressed++; this._log({ t: this.t, tag: 'MARGIN', text: 'held', fired: false, reason: g });
      }
    }
    if (this.t - this.lastCtx > 30 && !this.phase().clutch) {
      const g = this._gate();
      if (!g) {
        const c = this.pack.context[this.ctxI++ % this.pack.context.length];
        this.lastCtx = this.t;
        return this._fire({
          kind: 'context', tag: 'CONTEXT', color: COLORS.gold, line: c.stat + ' ' + c.now,
          ctx: c, sub: c.base + ' · ' + c.league
        });
      }
      this.suppressed++; this._log({ t: this.t, tag: 'CONTEXT', text: 'held', fired: false, reason: g });
    }

    // --- moments ---
    const p = ev.p;
    if (ev.kind === 'miss') {   // misses move the box score but only earn a card as a cold line
      const coldish = p.fga >= 6 && p.fgm / p.fga < .34;
      if (!(coldish && this.rnd() < .25)) return;
    }
    const cat = ev.mile || (ev.kind === 'miss' ? 'cold' : (ev.kind === 'foul' && p.fouls >= 4 ? 'foul' : ev.kind));
    let score = (ev.mile ? 6 : KIND_BASE[ev.kind]) * (.6 + p.pts / 30);
    if (p.pts < 8) score *= 1.6;                       // deliberate variety boost for quiet players
    if (p.streak >= 6 && !ev.mile) score += 1.4;
    const g = this._gate();
    if (g) { this.suppressed++; return this._log({ t: this.t, tag: cat.toUpperCase(), text: p.name, fired: false, reason: g }); }
    if (this.cool[p.name] != null && this.t - this.cool[p.name] < ph.playerCool) {
      this.suppressed++; return this._log({ t: this.t, tag: cat.toUpperCase(), text: p.name, fired: false, reason: 'player cooldown' });
    }
    if (!ev.mile && p.pts >= 14 && ph.variety > 0 && this.rnd() < ph.variety) {
      this.suppressed++; return this._log({ t: this.t, tag: cat.toUpperCase(), text: p.name, fired: false, reason: 'variety hold' });
    }
    if (score < this.cfg.threshold) {
      this.suppressed++; return this._log({ t: this.t, tag: cat.toUpperCase(), text: p.name, fired: false, reason: 'below threshold' });
    }
    const use = p.streak >= 6 && !ev.mile ? 'streak' : cat;
    const c = this._line(use, p, { LAST: ev.last, STREAK: p.streak });
    this._fire({
      kind: 'moment', tag: c.tag, color: c.color, line: c.line, player: p.name,
      side: p.side, sub: p.pos + ' · ' + p.pts + ' PTS · ' + p.reb + ' REB · ' + p.ast + ' AST'
    });
  };

  Engine.prototype.stats = function () {
    const mins = Math.max(this.t / 60, .01), tot = this.counts.moment + this.counts.run + this.counts.margin + this.counts.context;
    const ph = this.phase();
    return {
      perMin: (tot / mins).toFixed(1), total: tot, suppressed: this.suppressed,
      share: Math.round(this.cardTime / Math.max(this.t, .01) * 100), counts: this.counts,
      t: this.t, q: ph.q, clutch: ph.clutch, gap: ph.gap.toFixed(1), hold: this._hold('moment').toFixed(1),
      byQ: this.byQ.map(x => ({ fired: x.fired, share: Math.round(x.cardTime / x.span * 100) }))
    };
  };

  window.SimCards = { Engine, COLORS };
})();
