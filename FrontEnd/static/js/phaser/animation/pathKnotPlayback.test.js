import assert from "node:assert/strict";
import test from "node:test";

import {
  computePathSegmentDurationsMs,
  gridDistance,
  resolvePathKnotWaypoints,
} from "./pathKnotPlayback.js";

test("resolvePathKnotWaypoints skips anchor and returns meet-shimmy-rim", () => {
  const start = { x: 60, y: 25 };
  const knots = [
    { x: 60, y: 25 },
    { x: 75, y: 25 },
    { x: 75, y: 27 },
    { x: 88, y: 25 },
  ];
  const waypoints = resolvePathKnotWaypoints(start, knots);
  assert.deepEqual(waypoints, [
    { x: 75, y: 25 },
    { x: 75, y: 27 },
    { x: 88, y: 25 },
  ]);
});

test("computePathSegmentDurationsMs prefers backend segment game seconds", () => {
  const start = { x: 60, y: 25 };
  const waypoints = [
    { x: 75, y: 25 },
    { x: 75, y: 27 },
    { x: 88, y: 25 },
  ];
  const durations = computePathSegmentDurationsMs(
    start,
    waypoints,
    9999,
    [1.0, 0.5, 0.8],
    350,
  );
  assert.deepEqual(durations, [350, 175, 280]);
});

test("computePathSegmentDurationsMs splits proportionally when segments missing", () => {
  const start = { x: 0, y: 0 };
  const waypoints = [
    { x: 10, y: 0 },
    { x: 10, y: 10 },
  ];
  const total = 1000;
  const durations = computePathSegmentDurationsMs(start, waypoints, total, null, 350);
  const sum = durations.reduce((a, b) => a + b, 0);
  assert.equal(sum, total);
  assert.equal(durations[0], 500);
  assert.equal(durations[1], 500);
});

test("gridDistance is euclidean on grid coords", () => {
  assert.equal(gridDistance({ x: 0, y: 0 }, { x: 3, y: 4 }), 5);
});
