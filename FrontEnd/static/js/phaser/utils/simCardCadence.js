/**
 * Sim broadcast card cadence — selection and gating only (brief §9).
 *
 * Ported from the design handoff's `sim-card-engine.js`, with one deliberate change: the
 * mockup SYNTHESISES events from a weighted mix because it has no game behind it. Here the
 * events are the real emitted per-player deltas, arriving on `frame.events` from the timeline
 * assembler. Everything else — the weights, the four gates, the per-quarter curve, the
 * milestone jump, the variety hold — is the tuned design and is kept as-is.
 *
 * This module owns WHICH card and WHEN. It never renders, and it holds no copy: it asks the
 * moment pack for a line and hands a finished model to the presenter.
 *
 * Time is PLAYBACK seconds (what the viewer experiences), not game seconds — every gate in
 * §9 is expressed that way.
 */

import { pickLine } from './simMomentCopy.js';

/** Card-priority weights: how INTERESTING an event is, independent of how often it happens. */
const KIND_BASE = {
  three: 3.0, bucket: 2.0, paint: 2.2, board: 1.4, dime: 1.6, stock: 2.4, foul: 1.0, miss: 2.0,
};

/**
 * Every binding gate curves across the game, not just the card-to-card gap — tightening the
 * gap alone changes nothing after Q1, because by then the rest floor, the per-player cooldown
 * and event supply are what bind.
 */
export const QUARTER_PROFILES = [
  { gap: 6.5, restFloor: 1.6, playerCool: 15, variety: 0.35 },
  { gap: 5.5, restFloor: 1.3, playerCool: 13, variety: 0.35 },
  { gap: 5.0, restFloor: 1.1, playerCool: 11, variety: 0.30 },
  { gap: 4.2, restFloor: 0.8, playerCool: 8, variety: 0.22 },
];
export const CLUTCH_PROFILE = { gap: 3.4, restFloor: 0.5, playerCool: 6, variety: 0 };

/** Hold is the same for every type, clutch included. */
export const CARD_HOLD_S = 2.6;

/** Spacing for the non-moment beats. */
const RUN_MIN_PTS = 8;
const RUN_GAP_S = 14;
const MARGIN_GAP_S = 26;
const MARGIN_CHANCE = 0.18;
const CONTEXT_GAP_S = 30;

/** Candidate score needed to fire a moment. */
const MOMENT_THRESHOLD = 2.6;
/** Deliberate boost so the feed never becomes one player's channel. */
const QUIET_PLAYER_PTS = 8;
const QUIET_BOOST = 1.6;
const HEADLINER_PTS = 14;
const STREAK_PTS = 6;
const STREAK_BONUS = 1.4;

/** Tug rows only — rates (FG%, 3PM) are pivots and have no edge to promote. */
const MARGIN_STATS = [
  { key: 'reb', label: 'REBOUNDS' },
  { key: 'to', label: 'TURNOVERS' },
  { key: 'fb', label: 'FAST BREAK' },
  { key: 'paint', label: 'PTS IN PAINT' },
  { key: 'fouls', label: 'TEAM FOULS' },
];

/** Deterministic RNG so a replay of the same game produces the same feed. */
export function mulberry(seed) {
  let a = seed;
  return function next() {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const num = (v) => (Number.isFinite(Number(v)) ? Number(v) : 0);

/** Margin is the §7 tug at higher emphasis: whichever currently has the widest RELATIVE edge. */
export function widestTug(teamPanel) {
  const a = (teamPanel && teamPanel.away) || {};
  const h = (teamPanel && teamPanel.home) || {};
  let best = null;
  MARGIN_STATS.forEach((spec) => {
    const av = num(a[spec.key]);
    const hv = num(h[spec.key]);
    const edge = Math.abs(av - hv) / Math.max(av, hv, 1);
    if (edge <= 0) return;
    if (!best || edge > best.edge) best = { label: spec.label, away: av, home: hv, edge };
  });
  return best;
}

export class CardCadence {
  /**
   * @param {object} o { pack, teams, onCard, onLog, seed, clutch? }
   *   onCard(model) must return true if the card was actually presented.
   */
  constructor(o) {
    const opts = o || {};
    this.pack = opts.pack;
    this.teams = opts.teams || {};
    this.onCard = opts.onCard || (() => false);
    this.onLog = opts.onLog || null;
    this.rnd = mulberry(opts.seed == null ? 7 : opts.seed);

    this.t = 0;                 // playback seconds
    this.quarter = 1;
    this.clutch = false;
    this.suspended = false;     // Team Stats hold mode

    this.cardUntil = -99;
    this.lastCardEnd = -99;
    this.lastFire = -99;
    this.cool = {};             // player id -> t of their last card
    this.lastRun = -99;
    this.lastMargin = -99;
    this.lastCtx = -99;
    this.ctxI = 0;
    this.run = { side: null, pts: 0 };

    this.players = {};          // id -> running totals + milestone latches
    this.counts = { moment: 0, run: 0, margin: 0, context: 0 };
    this.suppressed = 0;
    this.cardTime = 0;
    this.byQ = [1, 2, 3, 4].map(() => ({ fired: 0, cardTime: 0 }));
    this.log = [];
  }

  /** Team Stats is a hold mode: the game keeps running, the CARD is what's gated. */
  suspend(on) { this.suspended = !!on; }

  profile() {
    if (this.clutch) return CLUTCH_PROFILE;
    return QUARTER_PROFILES[Math.min(QUARTER_PROFILES.length - 1, Math.max(0, this.quarter - 1))];
  }

  _record(entry) {
    this.log.push(entry);
    if (this.log.length > 400) this.log.shift();
    if (this.onLog) this.onLog(entry);
  }

  _hold(reason, tag, detail) {
    this.suppressed += 1;
    this._record({ t: this.t, q: this.quarter, tag, detail: detail || '', fired: false, reason });
    return false;
  }

  /** The four cadence gates, in the order they bind. */
  _gate() {
    const p = this.profile();
    if (this.suspended) return 'team stats held';
    if (this.t < this.cardUntil) return 'card up';
    if (this.t < this.lastCardEnd + p.restFloor) return 'rest floor';
    if (this.t < this.lastFire + p.gap) return 'cadence gap';
    return null;
  }

  _fire(model, playerId) {
    const shown = this.onCard(model);
    if (!shown) return this._hold('presenter refused', String(model.tag || model.kind).toUpperCase());
    this.cardUntil = this.t + CARD_HOLD_S;
    this.lastFire = this.t;
    this.counts[model.kind] = (this.counts[model.kind] || 0) + 1;
    this.byQ[Math.min(3, this.quarter - 1)].fired += 1;
    if (playerId) this.cool[playerId] = this.t;
    this._record({ t: this.t, q: this.quarter, tag: model.tag || model.kind, detail: model.line || '', fired: true, reason: null });
    return true;
  }

  _player(id, meta) {
    if (!this.players[id]) {
      this.players[id] = {
        id, name: (meta && meta.name) || '', pos: (meta && meta.pos) || '', side: (meta && meta.side) || '',
        pts: 0, reb: 0, ast: 0, fgm: 0, fga: 0, fouls: 0, streak: 0,
        m10: false, m20: false, m30: false, r10: false, dd: false,
      };
    }
    const p = this.players[id];
    if (meta) {
      // Totals are the emitted cumulative line — never accumulated here.
      ['pts', 'reb', 'ast', 'fgm', 'fga', 'fouls'].forEach((k) => {
        if (meta[k] != null) p[k] = num(meta[k]);
      });
      if (meta.name) p.name = meta.name;
      if (meta.pos) p.pos = meta.pos;
      if (meta.side) p.side = meta.side;
    }
    return p;
  }

  /**
   * The milestone this player is currently owed, if any — a PEEK, with no side effects.
   *
   * Latching here would be a bug: a milestone reached while a card is up, or inside the
   * cadence gap, would mark itself as spent and the card would never fire. Milestones are
   * supposed to jump the queue, so the crossing has to stay owed until it is actually shown.
   */
  _peekMilestone(p) {
    if (!p.m30 && p.pts >= 30) return 'milestone30';
    if (!p.m20 && p.pts >= 20) return 'milestone20';
    if (!p.dd && p.pts >= 10 && p.reb >= 10) return 'doubleDouble';
    if (!p.m10 && p.pts >= 10) return 'milestone10';
    if (!p.r10 && p.reb >= 10) return 'boards10';
    return null;
  }

  /** Spend a milestone — called only once its card is on screen. */
  _latchMilestone(p, mile) {
    const key = { milestone30: 'm30', milestone20: 'm20', doubleDouble: 'dd', milestone10: 'm10', boards10: 'r10' }[mile];
    if (key) p[key] = true;
  }

  /**
   * Advance playback and consider the frame's events.
   * @param {object} frame the frame being rendered
   * @param {number} dt playback seconds since the previous frame
   */
  step(frame, dt) {
    this.t += num(dt);
    if (this.t < this.cardUntil) {
      this.cardTime += num(dt);
      this.byQ[Math.min(3, this.quarter - 1)].cardTime += num(dt);
    }
    if (this.cardUntil > -1 && this.t >= this.cardUntil && this.lastCardEnd < this.cardUntil) {
      this.lastCardEnd = this.cardUntil;
    }
    if (!frame) return false;

    this.quarter = Math.max(1, Math.min(4, num(frame.quarter) || 1));

    // Keep running totals in step with the emitted rows, and track the run.
    const roster = [].concat(
      (frame.away || []).map((p) => ({ ...p, side: 'away' })),
      (frame.home || []).map((p) => ({ ...p, side: 'home' })),
    );
    const meta = {};
    roster.forEach((p) => { meta[p.id] = p; });

    const prevPts = this.lastScore || { away: 0, home: 0 };
    const sc = frame.score || {};
    const dAway = num(sc.away) - num(prevPts.away);
    const dHome = num(sc.home) - num(prevPts.home);
    this.lastScore = { away: num(sc.away), home: num(sc.home) };
    if (dAway > 0 || dHome > 0) {
      const side = dAway > dHome ? 'away' : 'home';
      const gained = Math.max(dAway, dHome);
      if (this.run.side === side) this.run.pts += gained;
      else this.run = { side, pts: gained };
    }

    if (this.suspended) {
      return this._hold('team stats held', 'HELD', 'stage is the team panel');
    }

    // --- priority beats: run / margin / context outrank moments but respect cadence ---
    if (this.run.pts >= RUN_MIN_PTS && this.t - this.lastRun > RUN_GAP_S) {
      const g = this._gate();
      if (g) this._hold(g, 'RUN');
      else {
        const team = this.teams[this.run.side] || {};
        const c = pickLine(this.pack, 'run', {
          TEAM: String(team.name || team.teamName || '').toUpperCase(),
          RUN: `${this.run.pts}–0`,
        }, this.rnd);
        if (c) {
          const side = this.run.side;
          this.lastRun = this.t;
          this.run = { side: null, pts: 0 };
          return this._fire({ kind: 'run', tag: c.tag, color: c.color, line: c.line, side, sub: null });
        }
      }
    }

    // Analysis is suppressed in clutch — nobody wants a rebounding differential there.
    if (!this.clutch && this.t - this.lastMargin > MARGIN_GAP_S && this.rnd() < MARGIN_CHANCE) {
      const g = this._gate();
      if (g) this._hold(g, 'MARGIN');
      else {
        const tug = widestTug(frame.teamPanel);
        if (tug) {
          this.lastMargin = this.t;
          return this._fire({
            kind: 'margin', tag: tug.label, color: 'blue', sub: null,
            margin: { label: tug.label, away: tug.away, home: tug.home },
          });
        }
      }
    }

    if (!this.clutch && this.t - this.lastCtx > CONTEXT_GAP_S) {
      const g = this._gate();
      if (g) this._hold(g, 'CONTEXT');
      else if (this.pack && this.pack.context && this.pack.context.length) {
        const c = this.pack.context[this.ctxI % this.pack.context.length];
        this.ctxI += 1;
        this.lastCtx = this.t;
        return this._fire({
          kind: 'context', tag: 'CONTEXT', color: 'gold', ctx: c,
          sub: `${c.base} · ${c.league}`,
        });
      }
    }

    // --- moments ---
    const events = frame.events || [];
    for (let i = 0; i < events.length; i += 1) {
      const ev = events[i];
      const row = meta[ev.id];
      if (!row) continue;                       // not on court / not in this frame's five
      const p = this._player(ev.id, row);

      if (ev.kind === 'three' || ev.kind === 'bucket' || ev.kind === 'paint') p.streak += num(ev.last);
      else if (ev.kind !== 'miss') p.streak = 0;

      const mile = this._peekMilestone(p);
      if (ev.kind === 'miss' && !mile) {
        // A miss only earns a card as a cold line, and only from a genuinely cold shooter.
        const cold = p.fga >= 6 && (p.fgm / Math.max(p.fga, 1)) < 0.34;
        if (!cold || this.rnd() >= 0.25) continue;
      }
      const cat = mile
        || (ev.kind === 'miss' ? 'cold' : (ev.kind === 'foul' && p.fouls >= 4 ? 'foul' : ev.kind));
      if (ev.kind === 'foul' && p.fouls < 4 && !mile) continue;   // 4th/5th foul only

      let score = (mile ? 6 : (KIND_BASE[ev.kind] || 1)) * (0.6 + p.pts / 30);
      if (p.pts < QUIET_PLAYER_PTS) score *= QUIET_BOOST;
      if (p.streak >= STREAK_PTS && !mile) score += STREAK_BONUS;

      const g = this._gate();
      if (g) { this._hold(g, String(cat).toUpperCase(), p.name); continue; }
      const prof = this.profile();
      if (this.cool[p.id] != null && this.t - this.cool[p.id] < prof.playerCool) {
        this._hold('player cooldown', String(cat).toUpperCase(), p.name); continue;
      }
      if (!mile && p.pts >= HEADLINER_PTS && prof.variety > 0 && this.rnd() < prof.variety) {
        this._hold('variety hold', String(cat).toUpperCase(), p.name); continue;
      }
      if (score < MOMENT_THRESHOLD) {
        this._hold('below threshold', String(cat).toUpperCase(), p.name); continue;
      }

      const useCat = (p.streak >= STREAK_PTS && !mile) ? 'streak' : cat;
      const c = pickLine(this.pack, useCat, {
        NAME: String(p.name || '').replace(/^[A-Z]\.\s/, '').toUpperCase(),
        PTS: p.pts, REB: p.reb, AST: p.ast, FGM: p.fgm, FGA: p.fga,
        LAST: ev.last, STREAK: p.streak,
      }, this.rnd);
      if (!c) continue;
      const fired = this._fire({
        kind: 'moment', tag: c.tag, color: c.color, line: c.line, side: p.side,
        sub: `${p.pos} · ${p.pts} PTS · ${p.reb} REB · ${p.ast} AST`,
      }, p.id);
      if (fired && mile) this._latchMilestone(p, mile);
      return fired;
    }
    return false;
  }

  /** Instrumentation: how the weights get tuned (brief §9). */
  stats() {
    const total = this.counts.moment + this.counts.run + this.counts.margin + this.counts.context;
    return {
      t: this.t,
      total,
      counts: { ...this.counts },
      suppressed: this.suppressed,
      share: this.t > 0 ? Math.round((this.cardTime / this.t) * 100) : 0,
      byQuarter: this.byQ.map((q, i) => ({ q: i + 1, fired: q.fired, cardTime: Math.round(q.cardTime * 10) / 10 })),
      // Every suppressed candidate keeps its reason — silent drops are untunable.
      suppressedByReason: this.log.filter((e) => !e.fired).reduce((acc, e) => {
        acc[e.reason] = (acc[e.reason] || 0) + 1;
        return acc;
      }, {}),
    };
  }
}
