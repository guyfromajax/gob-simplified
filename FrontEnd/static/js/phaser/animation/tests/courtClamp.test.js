import test from "node:test";
import assert from "node:assert/strict";
import { CLAMP_BOUNDS, clampGridCoords, isClampExempt } from "../courtClamp.js";

test("clamps generic turn coords to canonical bounds", () => {
  const turnData = { result_type: "MISS" };
  const clamped = clampGridCoords({ x: 120, y: -5 }, turnData);
  assert.deepEqual(clamped, { x: CLAMP_BOUNDS.maxX, y: CLAMP_BOUNDS.minY });
});

test("preserves exact boundary values", () => {
  const turnData = { result_type: "MAKE" };
  const coords = {
    x: CLAMP_BOUNDS.minX,
    y: CLAMP_BOUNDS.maxY,
  };
  const clamped = clampGridCoords(coords, turnData);
  assert.deepEqual(clamped, coords);
});

test("does not clamp exempt SIP/BIP/TIMEOUT turns", () => {
  const outOfBounds = { x: 2, y: 52 };
  assert.equal(isClampExempt({ result_type: "SIDE_INBOUND" }), true);
  assert.equal(isClampExempt({ result_type: "BASELINE_INBOUND" }), true);
  assert.equal(isClampExempt({ result_type: "TIMEOUT" }), true);

  assert.deepEqual(
    clampGridCoords(outOfBounds, { result_type: "SIDE_INBOUND" }),
    outOfBounds
  );
  assert.deepEqual(
    clampGridCoords(outOfBounds, { result_type: "BASELINE_INBOUND" }),
    outOfBounds
  );
  assert.deepEqual(
    clampGridCoords(outOfBounds, { result_type: "TIMEOUT" }),
    outOfBounds
  );
});

test("supports explicit context exemption", () => {
  const turnData = { result_type: "MISS" };
  const coords = { x: 0, y: 60 };
  const clamped = clampGridCoords(coords, turnData, { forceExempt: true });
  assert.deepEqual(clamped, coords);
});
