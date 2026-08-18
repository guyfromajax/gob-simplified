/**
 * Sim broadcast callout cadence — special beats only (wide-worm restructure).
 *
 * Routine events are dropped, not queued. Global min gap 9s + per-player cool from the
 * old quarter curve. Copy from simCalloutCopy.js / sim-callout-copy.md only.
 */

import { pickCalloutLine } from './simCalloutCopy.js';
import { clockToSeconds } from './simWormTime.js';

export const QUARTER_PROFILES = [
  { gap: 6.5, restFloor: 1.6, playerCool: 15, variety: 0.35 },
  { gap: 5.5, restFloor: 1.3, playerCool: 13, variety: 0.35 },
  { gap: 5.0, restFloor: 1.1, playerCool: 11, variety: 0.30 },
  { gap: 4.2, restFloor: 0.8, playerCool: 8, variety: 0.22 },
];

export const CALLOUT_HOLD_S = 2.6;
/**
 * The one tier that holds longer. The shot that won the game is the loudest moment in
 * the broadcast, so it takes the screen for 6s and is exempt from the cadence gates —
 * a "rest floor" or "cadence gap" must never be the reason the game-winner went unseen.
 */
export const GAME_WINNER_HOLD_S = 6;
export const GAME_WINNER_TIER = 'gamewinner';
export const GLOBAL_GAP_S = 9;
export const STREAK_PTS = 8;
export const RUN_MIN_PTS = 10;
export const DEFENSE_MAX_PER_TEAM = 2;

const ADV_POS = [
  { key: 'reb', label: 'rebounding', panel: 'reb' },
  { key: 'tpm', label: '3PT', panel: 'tpm' },
  { key: 'fb', label: 'fast break', panel: 'fb' },
  { key: 'paint', label: 'paint', panel: 'paint' },
];
const ADV_NEG = [
  { key: 'to', label: 'turnover', panel: 'to' },
  { key: 'fouls', label: 'foul', panel: 'fouls' },
];
const ADV_EDGES = [10, 20];

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

function shortName(name) {
  return String(name || '').replace(/^[A-Z]\.\s*/, '').trim();
}

function ddCats(p) {
  const cats = [];
  if (p.pts >= 10) cats.push({ key: 'PTS', val: p.pts });
  if (p.reb >= 10) cats.push({ key: 'REB', val: p.reb });
  if (p.ast >= 10) cats.push({ key: 'AST', val: p.ast });
  if (p.stl >= 10) cats.push({ key: 'STL', val: p.stl });
  if (p.blk >= 10) cats.push({ key: 'BLK', val: p.blk });
  return cats;
}

/** Highest unlatched point milestone (≥20, steps of 10). */
export function peekPointMilestone(p) {
  if (!p || !(p.pts >= 20)) return null;
  const tier = Math.floor(p.pts / 10) * 10;
  const latched = p.pointLatches || {};
  for (let t = tier; t >= 20; t -= 10) {
    if (!latched[t]) return t;
  }
  return null;
}

export class CalloutCadence {
  /**
   * @param {object} o { pack, teams, onCallout, onLog, seed }
   *   onCallout(model) must return true if presented.
   */
  constructor(o) {
    const opts = o || {};
    this.pack = opts.pack;
    this.teams = opts.teams || {};
    this.onCallout = opts.onCallout || (() => false);
    this.onLog = opts.onLog || null;
    this.rnd = mulberry(opts.seed == null ? 7 : opts.seed);

    this.t = 0;
    this.quarter = 1;
    this.suspended = false; // HIGHLIGHTS off

    this.busyUntil = -99;
    this.lastEnd = -99;
    this.lastFire = -99;
    this.cool = {};
    this.lastRun = -99;
    this.run = { side: null, pts: 0 };

    this.players = {};
    this.gameWinnerFired = false;   // fires at most once per game
    this.advLatched = {}; // `${side}:${key}:${edge}` -> true
    this.defCount = { away: 0, home: 0 };
    this.counts = {};
    this.suppressed = 0;
    this.calloutTime = 0;
    this.byQ = [1, 2, 3, 4].map(() => ({ fired: 0, calloutTime: 0 }));
    this.log = [];
    this.lastScore = null;
  }

  /** HIGHLIGHTS off — suppress all callouts; nothing queues. */
  suspend(on) { this.suspended = !!on; }

  profile() {
    const q = Math.min(4, Math.max(1, this.quarter));
    return QUARTER_PROFILES[q - 1];
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

  _gate(playerId) {
    if (this.suspended) return 'highlights off';
    if (this.t < this.busyUntil) return 'callout up';
    if (this.t < this.lastEnd + this.profile().restFloor) return 'rest floor';
    if (this.t < this.lastFire + GLOBAL_GAP_S) return 'cadence gap';
    if (playerId && this.cool[playerId] != null
        && this.t - this.cool[playerId] < this.profile().playerCool) {
      return 'player cooldown';
    }
    return null;
  }

  _fire(model, playerId) {
    const shown = this.onCallout(model);
    if (!shown) return this._hold('presenter refused', String(model.tier || '').toUpperCase());
    this.busyUntil = this.t + (model.tier === GAME_WINNER_TIER ? GAME_WINNER_HOLD_S : CALLOUT_HOLD_S);
    this.lastFire = this.t;
    const tier = model.tier || 'other';
    this.counts[tier] = (this.counts[tier] || 0) + 1;
    this.byQ[Math.min(3, Math.max(0, this.quarter - 1))].fired += 1;
    if (playerId) this.cool[playerId] = this.t;
    this._record({
      t: this.t, q: this.quarter, tag: tier, detail: model.line || '', fired: true, reason: null,
    });
    return true;
  }

  _player(id, meta) {
    if (!this.players[id]) {
      this.players[id] = {
        id,
        name: (meta && meta.name) || '',
        pos: (meta && meta.pos) || '',
        side: (meta && meta.side) || '',
        pts: 0, reb: 0, ast: 0, stl: 0, blk: 0, fouls: 0, def: 0, defA: 0,
        streak: 0,
        pointLatches: {},
        r10: false, dd: false, outLatched: false, defLatched: false,
      };
    }
    const p = this.players[id];
    if (meta) {
      ['pts', 'reb', 'ast', 'stl', 'blk', 'fouls', 'def', 'defA'].forEach((k) => {
        if (meta[k] != null) p[k] = num(meta[k]);
      });
      if (meta.name) p.name = meta.name;
      if (meta.pos) p.pos = meta.pos;
      if (meta.side) p.side = meta.side;
      if (meta.out) p.out = true;
    }
    return p;
  }

  _try(tier, values, side, playerId, avatarOverride) {
    const g = this._gate(playerId);
    if (g) return this._hold(g, String(tier).toUpperCase(), values && values.NAME);
    let pack = this.pack;
    // Prefer tie-flavoured lines when the bucket knotted the score.
    if (tier === 'clutch' && values && values.__tied && pack && pack.categories && pack.categories.clutch) {
      const tiedLines = pack.categories.clutch.lines.filter((l) => /tie/i.test(l));
      if (tiedLines.length) {
        pack = {
          ...pack,
          categories: {
            ...pack.categories,
            clutch: { ...pack.categories.clutch, lines: tiedLines },
          },
        };
      }
    }
    const picked = pickCalloutLine(pack, tier, values, this.rnd);
    if (!picked) return this._hold('no copy', String(tier).toUpperCase());
    return this._fire({
      ...picked,
      avatar: avatarOverride || picked.avatar,
      side,
      playerId: playerId || null,
      teamAbbr: (this.teams[side] || {}).abbr || '',
      tied: !!values && values.__tied,
    }, playerId);
  }

  _endgameWindow(frame) {
    const q = num(frame.quarter) || 1;
    if (q < 4) return false;
    const clock = (frame.score && frame.score.clock) || '';
    return clockToSeconds(clock) <= 120;
  }

  _peekAdvantage(teamPanel) {
    const a = (teamPanel && teamPanel.away) || {};
    const h = (teamPanel && teamPanel.home) || {};
    const candidates = [];

    ADV_POS.forEach((spec) => {
      const av = num(a[spec.panel]);
      const hv = num(h[spec.panel]);
      const edge = Math.abs(av - hv);
      const side = av > hv ? 'away' : (hv > av ? 'home' : null);
      if (!side) return;
      ADV_EDGES.forEach((thr) => {
        if (edge < thr) return;
        const key = `${side}:${spec.key}:${thr}`;
        if (this.advLatched[key]) return;
        candidates.push({
          key, side, thr, label: spec.label, kind: 'advantage',
          team: shortName((this.teams[side] || {}).name || (this.teams[side] || {}).abbr || ''),
        });
      });
    });

    ADV_NEG.forEach((spec) => {
      const av = num(a[spec.panel]);
      const hv = num(h[spec.panel]);
      const edge = Math.abs(av - hv);
      // Higher total = the disadvantaged team.
      const side = av > hv ? 'away' : (hv > av ? 'home' : null);
      if (!side) return;
      ADV_EDGES.forEach((thr) => {
        if (edge < thr) return;
        const key = `${side}:${spec.key}:${thr}`;
        if (this.advLatched[key]) return;
        candidates.push({
          key, side, thr, label: spec.label, kind: 'disadvantage',
          team: shortName((this.teams[side] || {}).name || (this.teams[side] || {}).abbr || ''),
        });
      });
    });

    // Prefer larger edges, then positive advantages over disadvantages.
    candidates.sort((x, y) => y.thr - x.thr || (x.kind === 'advantage' ? -1 : 1));
    return candidates[0] || null;
  }

  step(frame, dt) {
    this.t += num(dt);
    if (this.t < this.busyUntil) {
      this.calloutTime += num(dt);
      this.byQ[Math.min(3, Math.max(0, this.quarter - 1))].calloutTime += num(dt);
    }
    if (this.busyUntil > -1 && this.t >= this.busyUntil && this.lastEnd < this.busyUntil) {
      this.lastEnd = this.busyUntil;
    }
    if (!frame) return false;

    this.quarter = Math.max(1, num(frame.quarter) || 1);

    const roster = [].concat(
      (frame.away || []).map((p) => ({ ...p, side: 'away' })),
      (frame.home || []).map((p) => ({ ...p, side: 'home' })),
    );
    const meta = {};
    roster.forEach((p) => {
      meta[p.id] = p;
      this._player(p.id, p);
    });

    const sc = frame.score || {};
    const prev = this.lastScore || { away: 0, home: 0 };
    const dAway = num(sc.away) - num(prev.away);
    const dHome = num(sc.home) - num(prev.home);
    const scoreChanged = dAway > 0 || dHome > 0;
    const scoringSide = dAway > dHome ? 'away' : (dHome > dAway ? 'home' : null);

    if (scoreChanged && scoringSide) {
      const gained = Math.max(dAway, dHome);
      if (this.run.side === scoringSide) this.run.pts += gained;
      else this.run = { side: scoringSide, pts: gained };
    }

    const prevLead = Math.sign(num(prev.home) - num(prev.away));
    const newLead = Math.sign(num(sc.home) - num(sc.away));
    const becameTied = num(sc.home) === num(sc.away) && num(prev.home) !== num(prev.away);
    const leadChange = newLead !== 0 && prevLead !== newLead;
    const endgameBucket = scoreChanged && this._endgameWindow(frame) && (becameTied || leadChange);

    this.lastScore = { away: num(sc.away), home: num(sc.home) };

    if (this.suspended) {
      return this._hold('highlights off', 'HELD');
    }

    // --- special beats (priority order). Drops on gate fail; never queues. ---

    // 0) Game-winning shot. Stamped on its frame by the timeline assembler: the last
    // lead-changing score inside the final 10 seconds, by the team that went on to win
    // (free throws included). Outranks everything and ignores the gates — it fires even
    // if another callout is mid-hold, because there is no later chance to show it.
    if (frame.gameWinner && !this.gameWinnerFired) {
      const gw = frame.gameWinner;
      const picked = pickCalloutLine(this.pack, GAME_WINNER_TIER, {
        NAME: shortName(gw.name),
        PTS: gw.points,
      }, this.rnd);
      if (picked) {
        this.gameWinnerFired = true;
        // Clear any hold so the presenter accepts it immediately.
        this.busyUntil = -99;
        return this._fire({
          ...picked,
          tier: GAME_WINNER_TIER,
          avatar: 'headshot',
          side: gw.side,
          playerId: gw.playerId,
          teamAbbr: (this.teams[gw.side] || {}).abbr || '',
        }, gw.playerId);
      }
    }

    // 1) Foul-out
    for (let i = 0; i < roster.length; i += 1) {
      const row = roster[i];
      const p = this._player(row.id, row);
      if (!p.outLatched && (row.out || p.fouls >= 5)) {
        const ok = this._try('fouledout', { NAME: shortName(p.name) }, p.side, p.id);
        if (ok) { p.outLatched = true; return true; }
      }
    }

    // 2) Endgame tie / lead-change bucket
    if (endgameBucket && scoringSide) {
      const scorer = (frame.events || []).find((ev) => {
        const r = meta[ev.id];
        return r && r.side === scoringSide
          && (ev.kind === 'three' || ev.kind === 'bucket' || ev.kind === 'paint');
      });
      if (scorer) {
        const p = this._player(scorer.id, meta[scorer.id]);
        const ok = this._try('clutch', {
          NAME: shortName(p.name),
          __tied: becameTied,
        }, p.side, p.id);
        if (ok) return true;
      }
    }

    // 3–6) Per-player: milestone / boards / DD / defense / streak (via events + totals)
    for (let i = 0; i < roster.length; i += 1) {
      const row = roster[i];
      const p = this._player(row.id, row);

      const mile = peekPointMilestone(p);
      if (mile != null) {
        const ok = this._try('milestone', {
          NAME: shortName(p.name), PTS: mile,
        }, p.side, p.id);
        if (ok) {
          p.pointLatches[mile] = true;
          return true;
        }
      }

      if (!p.r10 && p.reb >= 10) {
        const ok = this._try('boards10', {
          NAME: shortName(p.name), REB: p.reb,
        }, p.side, p.id);
        if (ok) { p.r10 = true; return true; }
      }

      const cats = ddCats(p);
      if (!p.dd && cats.length >= 2) {
        const ok = this._try('doubleDouble', {
          NAME: shortName(p.name),
          PTS: p.pts, REB: p.reb, AST: p.ast,
          CATS: cats.slice(0, 2).map((c) => `${c.val} ${c.key}`).join(', '),
        }, p.side, p.id);
        if (ok) { p.dd = true; return true; }
      }

      if (!p.defLatched
          && p.defA >= 10
          && p.def >= 80
          && this.defCount[p.side] < DEFENSE_MAX_PER_TEAM) {
        const ok = this._try('defense', {
          NAME: shortName(p.name), DEF: p.def,
        }, p.side, p.id);
        if (ok) {
          p.defLatched = true;
          this.defCount[p.side] += 1;
          return true;
        }
      }
    }

    // Streak from scoring events this frame — scoring by A resets everyone else's streak.
    const events = frame.events || [];
    const scorers = new Set();
    for (let i = 0; i < events.length; i += 1) {
      const ev = events[i];
      if (ev.kind === 'three' || ev.kind === 'bucket' || ev.kind === 'paint') scorers.add(ev.id);
    }
    if (scorers.size) {
      Object.keys(this.players).forEach((id) => {
        if (!scorers.has(id)) this.players[id].streak = 0;
      });
    }
    for (let i = 0; i < events.length; i += 1) {
      const ev = events[i];
      const row = meta[ev.id];
      if (!row) continue;
      const p = this._player(ev.id, row);
      if (ev.kind === 'three' || ev.kind === 'bucket' || ev.kind === 'paint') {
        p.streak += num(ev.last);
      } else if (ev.kind !== 'miss' && !scorers.has(ev.id)) {
        p.streak = 0;
      }
      if (p.streak >= STREAK_PTS) {
        const ok = this._try('streak', {
          NAME: shortName(p.name), STREAK: p.streak,
        }, p.side, p.id);
        if (ok) {
          p.streak = 0;
          return true;
        }
      }
    }

    // 7) Team run
    if (this.run.pts >= RUN_MIN_PTS && this.t - this.lastRun > GLOBAL_GAP_S) {
      const side = this.run.side;
      const runPts = this.run.pts;
      const team = this.teams[side] || {};
      const ok = this._try('run', {
        TEAM: shortName(team.name || team.abbr || ''),
        RUN: `${runPts}–0`,
      }, side, null);
      if (ok) {
        this.lastRun = this.t;
        this.run = { side: null, pts: 0 };
        return true;
      }
    }

    // 8) Advantage / disadvantage (first crossing per team/stat/edge)
    const adv = this._peekAdvantage(frame.teamPanel);
    if (adv) {
      const ok = this._try(adv.kind, {
        TEAM: adv.team, EDGE: adv.thr, STAT: adv.label,
      }, adv.side, null);
      if (ok) {
        this.advLatched[adv.key] = true;
        return true;
      }
    }

    return false;
  }

  stats() {
    const total = Object.values(this.counts).reduce((s, n) => s + n, 0);
    return {
      t: this.t,
      total,
      counts: { ...this.counts },
      suppressed: this.suppressed,
      share: this.t > 0 ? Math.round((this.calloutTime / this.t) * 100) : 0,
      byQuarter: this.byQ.map((q, i) => ({
        q: i + 1, fired: q.fired, calloutTime: Math.round(q.calloutTime * 10) / 10,
      })),
      suppressedByReason: this.log.filter((e) => !e.fired).reduce((acc, e) => {
        acc[e.reason] = (acc[e.reason] || 0) + 1;
        return acc;
      }, {}),
    };
  }
}
