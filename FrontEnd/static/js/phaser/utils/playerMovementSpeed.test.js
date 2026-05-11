/**
 * Run from repo: cd FrontEnd/static/js/phaser && node --test utils/playerMovementSpeed.test.js
 */
import test from "node:test";
import assert from "node:assert/strict";
import {
  agToSpeedPxPerSec,
  getEffectiveAgilityForMovement,
  MOVEMENT_SPEED_BASE,
  MOVEMENT_SPEED_SLOPE,
  DEFAULT_AG_WHEN_MISSING,
  BALL_HANDLER_SPEED_MULTIPLIER,
} from "./playerMovementSpeed.js";

test("agToSpeedPxPerSec is linear and monotone", () => {
  assert.equal(
    agToSpeedPxPerSec(0),
    MOVEMENT_SPEED_BASE + MOVEMENT_SPEED_SLOPE * 0
  );
  assert.equal(agToSpeedPxPerSec(50), 450);
  assert.equal(agToSpeedPxPerSec(100), 500);
  assert.equal(agToSpeedPxPerSec(120), 520);
  assert.ok(agToSpeedPxPerSec(101) > agToSpeedPxPerSec(100));
});

test("agToSpeedPxPerSec extrapolates above 100 with no cap", () => {
  assert.equal(agToSpeedPxPerSec(200), MOVEMENT_SPEED_BASE + 200);
});

test("ball handler speed has parity with off-ball at equal AG", () => {
  const off = agToSpeedPxPerSec(80, { isBallHandler: false });
  const bh = agToSpeedPxPerSec(80, { isBallHandler: true });
  assert.equal(BALL_HANDLER_SPEED_MULTIPLIER, 1.0);
  assert.equal(bh, off);
  assert.ok(Math.abs(bh - off * BALL_HANDLER_SPEED_MULTIPLIER) < 1e-9);
});

test("invalid AG falls back to default 50", () => {
  assert.equal(agToSpeedPxPerSec(NaN), MOVEMENT_SPEED_BASE + 50);
  assert.equal(agToSpeedPxPerSec(undefined), MOVEMENT_SPEED_BASE + 50);
});

test("getEffectiveAgilityForMovement uses sprite.attributes first", () => {
  const sprite = {
    playerId: "p1",
    attributes: { AG: 72 },
  };
  assert.equal(getEffectiveAgilityForMovement(sprite, null), 72);
});

test("getEffectiveAgilityForMovement falls back to simData.players", () => {
  const sprite = { playerId: "p9" };
  const scene = {
    simData: {
      players: [{ player_id: "p9", attributes: { AG: 61 } }],
    },
  };
  assert.equal(getEffectiveAgilityForMovement(sprite, scene), 61);
});

test("getEffectiveAgilityForMovement uses default when missing", () => {
  const sprite = { playerId: "x" };
  const scene = { simData: { players: [] } };
  assert.equal(getEffectiveAgilityForMovement(sprite, scene), DEFAULT_AG_WHEN_MISSING);
});
