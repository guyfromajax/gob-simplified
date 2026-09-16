import assert from "node:assert/strict";
import test from "node:test";

import { showHcoStepStrictConfig } from "./fbTelemetryDebug.js";
import {
  evaluateStepPassClockOverrun,
  resolveHcoStepStrictMode,
} from "./hcoStepStrictContract.js";

function withHcoStrictFlag(value, fn) {
  const had = Object.prototype.hasOwnProperty.call(
    globalThis,
    "HCO_STEP_MOVEMENT_STRICT_CONTRACT",
  );
  const prev = globalThis.HCO_STEP_MOVEMENT_STRICT_CONTRACT;
  if (value === undefined) {
    delete globalThis.HCO_STEP_MOVEMENT_STRICT_CONTRACT;
  } else {
    globalThis.HCO_STEP_MOVEMENT_STRICT_CONTRACT = value;
  }
  try {
    return fn();
  } finally {
    if (had) globalThis.HCO_STEP_MOVEMENT_STRICT_CONTRACT = prev;
    else delete globalThis.HCO_STEP_MOVEMENT_STRICT_CONTRACT;
  }
}

test("showHcoStepStrictConfig matches resolveHcoStepStrictMode for unset, known, and unknown", () => {
  const cases = [
    { label: "unset", value: undefined },
    { label: "throw", value: "throw" },
    { label: "off", value: "off" },
    { label: "false", value: false },
    { label: "warn (resolver does not accept it)", value: "warn" },
    { label: "true (unknown)", value: true },
    { label: "garbage", value: "banana" },
  ];
  for (const { value } of cases) {
    withHcoStrictFlag(value, () => {
      const expected = resolveHcoStepStrictMode(globalThis);
      const reported = showHcoStepStrictConfig();
      assert.equal(reported.strictMode, expected);
    });
  }
  assert.equal(resolveHcoStepStrictMode({}), "throw");
  assert.equal(resolveHcoStepStrictMode({ HCO_STEP_MOVEMENT_STRICT_CONTRACT: "off" }), "off");
  assert.equal(resolveHcoStepStrictMode({ HCO_STEP_MOVEMENT_STRICT_CONTRACT: "nope" }), "throw");
});

test("step-pass clock overrun warns on HCO stall and genuine over-budget; does not throw", () => {
  const stall = evaluateStepPassClockOverrun({
    elapsedGameSeconds: 649,
    hardFailThresholdSeconds: 16,
    isPressureSkeletonTurn: false,
  });
  const genuine = evaluateStepPassClockOverrun({
    elapsedGameSeconds: 20,
    hardFailThresholdSeconds: 16,
    isPressureSkeletonTurn: false,
  });
  const inBudget = evaluateStepPassClockOverrun({
    elapsedGameSeconds: 5,
    hardFailThresholdSeconds: 16,
    isPressureSkeletonTurn: false,
  });
  assert.equal(stall, "warn");
  assert.equal(genuine, "warn");
  assert.equal(inBudget, "ok");
});

test("step-pass clock overrun still throws only when pressure mode is throw", () => {
  assert.equal(
    evaluateStepPassClockOverrun({
      elapsedGameSeconds: 20,
      hardFailThresholdSeconds: 16,
      isPressureSkeletonTurn: true,
      pressureStepStrictMode: "throw",
    }),
    "throw",
  );
  assert.equal(
    evaluateStepPassClockOverrun({
      elapsedGameSeconds: 20,
      hardFailThresholdSeconds: 16,
      isPressureSkeletonTurn: true,
      pressureStepStrictMode: "warn",
    }),
    "warn",
  );
});
