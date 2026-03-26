/**
 * Run: cd FrontEnd/static/js/phaser && node --test utils/animationEndFromTurn.test.js
 */
import test from "node:test";
import assert from "node:assert/strict";
import { getAnimationEndGridForPlayer } from "./animationEndFromTurn.js";

test("returns null when no animations", () => {
  assert.equal(getAnimationEndGridForPlayer({}, "p1"), null);
  assert.equal(getAnimationEndGridForPlayer({ animations: [] }, "p1"), null);
});

test("matches playerId string/number", () => {
  const turn = {
    animations: [{ playerId: "42", end: { x: 60, y: 22 } }],
  };
  assert.deepEqual(getAnimationEndGridForPlayer(turn, "42"), { x: 60, y: 22 });
  assert.deepEqual(getAnimationEndGridForPlayer(turn, 42), { x: 60, y: 22 });
});

test("clamps coords", () => {
  const turn = {
    animations: [{ playerId: "a", end: { x: 1, y: 99 } }],
  };
  assert.deepEqual(getAnimationEndGridForPlayer(turn, "a"), { x: 4, y: 49 });
});

test("falls back to last movement coords", () => {
  const turn = {
    animations: [
      {
        playerId: "b",
        movement: [
          { timestamp: 0, coords: { x: 50, y: 25 } },
          { timestamp: 500, coords: { x: 55, y: 30 } },
        ],
      },
    ],
  };
  assert.deepEqual(getAnimationEndGridForPlayer(turn, "b"), { x: 55, y: 30 });
});
