import assert from "node:assert/strict";
import test from "node:test";

import {
  BALL_ACTIONS,
  BALL_DEPTH,
  COURT_MAX_Y,
  DEPTH_BAND_MAX,
  DEPTH_BASE,
  DEPTH_BALL_OWNER_BIAS,
  DEPTH_MODE,
  DEPTH_OFFENCE_BIAS,
  DEPTH_PER_GRID_Y,
  DEPTH_PROMOTED_BASE,
  resolvePlayerDepths,
  resolveStepBallOwnerId,
  resolveStepShooterId,
} from "./playerDepth.js";

const OFF = "OFFENCE";
const DEF = "DEFENCE";

function scene({ ownerHasFlag = true } = {}) {
  return {
    animations: [
      { playerId: "o_near", hasBallAtStep: [false], movement: [{ coords: { x: 50, y: 5 }, action: "cut" }] },
      { playerId: "o_far", hasBallAtStep: [false], movement: [{ coords: { x: 50, y: 45 }, action: "drift" }] },
      { playerId: "o_ball", hasBallAtStep: [ownerHasFlag], movement: [{ coords: { x: 50, y: 25 }, action: "handle_ball" }] },
      { playerId: "d_near", hasBallAtStep: [false], movement: [{ coords: { x: 50, y: 5 }, action: "guard_offball" }] },
    ],
    playersById: {
      o_near: { team_id: OFF }, o_far: { team_id: OFF },
      o_ball: { team_id: OFF }, d_near: { team_id: DEF },
    },
  };
}

const resolve = (extra = {}) => {
  const s = scene();
  return resolvePlayerDepths({
    animations: s.animations, stepIndex: 0, offenseTeamId: OFF,
    playersById: s.playersById, ...extra,
  });
};

// ── orientation: the whole effect inverts if this is wrong ──────────────────

test("LOWER grid y draws ON TOP (gridToPixels maps y=0 to the bottom of the canvas)", () => {
  const d = resolve();
  assert.ok(d.get("o_near") > d.get("o_far"),
    "a player nearer the viewer (lower grid y) must have the HIGHER depth");
});

test("the y term dominates both tie-breaks combined", () => {
  // one grid unit of separation must outrank offence + ball-owner together
  assert.ok(DEPTH_PER_GRID_Y > DEPTH_OFFENCE_BIAS + DEPTH_BALL_OWNER_BIAS,
    "a tie-break could otherwise reorder two players a full grid unit apart");
});

test("depth is a strict function of grid y before tie-breaks", () => {
  const d = resolve();
  const expected = DEPTH_BASE + (COURT_MAX_Y - 5) * DEPTH_PER_GRID_Y + DEPTH_OFFENCE_BIAS;
  assert.equal(d.get("o_near"), expected);
});

// ── tie-breaks ──────────────────────────────────────────────────────────────

test("offence wins a tie against defence on the same line", () => {
  const d = resolve();
  assert.equal(d.get("o_near") - d.get("d_near"), DEPTH_OFFENCE_BIAS);
});

test("sub-mode (i): the ball owner wins only a NEAR-TIE, not the whole floor", () => {
  const d = resolve();
  assert.ok(d.get("o_ball") < d.get("o_near"),
    "in tie_break mode a ball owner further from the viewer must stay behind");
});

test("sub-mode (ii): hard promotion puts the ball owner above every other player", () => {
  const d = resolve({ mode: DEPTH_MODE.HARD_PROMOTION });
  const others = ["o_near", "o_far", "d_near"].map((k) => d.get(k));
  assert.ok(others.every((v) => d.get("o_ball") > v),
    "hard promotion must beat every unpromoted player regardless of y");
});

test("the two sub-modes differ ONLY for the promoted players", () => {
  const a = resolve();
  const b = resolve({ mode: DEPTH_MODE.HARD_PROMOTION });
  for (const k of ["o_near", "o_far", "d_near"]) assert.equal(a.get(k), b.get(k));
  assert.notEqual(a.get("o_ball"), b.get("o_ball"));
});

// ── the ball must stay on top in BOTH modes ─────────────────────────────────

test("every player depth stays strictly below BALL_DEPTH, in both modes", () => {
  for (const mode of [DEPTH_MODE.TIE_BREAK, DEPTH_MODE.HARD_PROMOTION]) {
    for (const v of resolve({ mode }).values()) {
      assert.ok(v < BALL_DEPTH, `depth ${v} is not below the ball (${BALL_DEPTH})`);
    }
  }
});

test("the promoted band is provably above the unpromoted band and below the ball", () => {
  // worst case: a promoted player at the FAR end vs an unpromoted player at the NEAR end
  assert.ok(DEPTH_PROMOTED_BASE > DEPTH_BAND_MAX);
  assert.equal(DEPTH_BAND_MAX,
    DEPTH_BASE + COURT_MAX_Y * DEPTH_PER_GRID_Y + DEPTH_OFFENCE_BIAS + DEPTH_BALL_OWNER_BIAS);
  assert.ok(DEPTH_PROMOTED_BASE + COURT_MAX_Y * 0.5 < BALL_DEPTH);
});

// ── ball owner resolution: the previously dead accessor, now single-sourced ──

test("hasBallAtStep wins; the action set is the fallback", () => {
  const s = scene();
  assert.equal(resolveStepBallOwnerId(s.animations, 0), "o_ball");
  const noFlag = scene({ ownerHasFlag: false });
  assert.equal(resolveStepBallOwnerId(noFlag.animations, 0), "o_ball",
    "must fall back to the handle_ball action");
});

test("the action set matches collision_separation.BALL_ACTIONS exactly", () => {
  assert.deepEqual([...BALL_ACTIONS].sort(),
    ["drive", "handle_ball", "pass", "receive", "shoot"]);
});

test("no ball owner anywhere resolves to null, not to a guess", () => {
  assert.equal(resolveStepBallOwnerId([{ playerId: "x", movement: [{ action: "cut" }] }], 0), null);
  assert.equal(resolveStepBallOwnerId(null, 0), null);
});

test("the shooter is read from the payload, never inferred", () => {
  const anims = [{ playerId: "s", movement: [{ coords: { y: 10 }, action: "shoot" }] }];
  assert.equal(resolveStepShooterId(anims, 0), "s");
  assert.equal(resolveStepShooterId(anims, 1), null);
});

// ── never invent a coordinate ───────────────────────────────────────────────

test("a player with no usable y is OMITTED rather than given a stand-in depth", () => {
  const d = resolvePlayerDepths({
    animations: [{ playerId: "ghost", movement: [{}] }, { playerId: "ok", movement: [{ coords: { y: 20 } }] }],
    stepIndex: 0,
  });
  assert.equal(d.has("ghost"), false);
  assert.equal(d.has("ok"), true);
});

test("a live grid-y override beats the authored coordinate (the per-frame path)", () => {
  const s = scene();
  const d = resolvePlayerDepths({
    animations: s.animations, stepIndex: 0, offenseTeamId: OFF, playersById: s.playersById,
    gridYById: new Map([["o_far", 5]]),
  });
  assert.equal(d.get("o_far"), DEPTH_BASE + (COURT_MAX_Y - 5) * DEPTH_PER_GRID_Y + DEPTH_OFFENCE_BIAS);
});

test("bad input returns an empty map rather than throwing", () => {
  assert.equal(resolvePlayerDepths().size, 0);
  assert.equal(resolvePlayerDepths({ animations: null }).size, 0);
});
