import test from "node:test";
import assert from "node:assert/strict";
import {
  isLaneFoulContext,
  pickOffensiveFoulAnnouncementText,
  pickDefensiveFoulAnnouncementText,
} from "./foulAnnouncementLanguage.js";

test("detects lane context from explicit lane location", () => {
  assert.equal(isLaneFoulContext({ location: "topLane" }), true);
  assert.equal(isLaneFoulContext({ spot: "highPost" }), true);
});

test("detects non-lane context for wing/key spots", () => {
  assert.equal(isLaneFoulContext({ location: "upper wing" }), false);
  assert.equal(isLaneFoulContext({ spot: "key" }), false);
});

test("selects weighted offensive text (deterministic random)", () => {
  const text = pickOffensiveFoulAnnouncementText({ location: "upper wing" }, () => 0);
  assert.equal(text, "Push Off!");
});

test("selects weighted defensive text in lane context", () => {
  const text = pickDefensiveFoulAnnouncementText({ location: "topLane" }, () => 0.99);
  assert.equal(text, "Illegal Post Defense!");
});
