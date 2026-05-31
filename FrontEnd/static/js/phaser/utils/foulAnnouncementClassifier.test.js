/**
 * Run: cd FrontEnd/static/js/phaser && node --test utils/foulAnnouncementClassifier.test.js
 */
import test from "node:test";
import assert from "node:assert/strict";
import {
  isBonusFreeThrowFoulTurn,
  isShotResultShootingFoulTurn,
} from "./foulAnnouncementClassifier.js";

test("classifies FOUL + FREE_THROW as bonus foul turn", () => {
  const turn = {
    result_type: "FOUL",
    foul_team: "DEFENSE",
    next_play_type: "FREE_THROW",
    free_throws_remaining: 1,
  };
  assert.equal(isBonusFreeThrowFoulTurn(turn), true);
  assert.equal(isShotResultShootingFoulTurn(turn), false);
});

test("does not classify non-bonus FOUL as shooting foul", () => {
  const turn = {
    result_type: "FOUL",
    foul_team: "DEFENSE",
    next_play_type: "SIDE_INBOUND",
    free_throws_remaining: 0,
  };
  assert.equal(isBonusFreeThrowFoulTurn(turn), false);
  assert.equal(isShotResultShootingFoulTurn(turn), false);
});

test("classifies MISS + FREE_THROW continuation as shooting foul shot result", () => {
  const turn = {
    result_type: "MISS",
    foul_team: "DEFENSE",
    next_play_type: "FREE_THROW",
    free_throws_remaining: 2,
  };
  assert.equal(isShotResultShootingFoulTurn(turn), true);
  assert.equal(isBonusFreeThrowFoulTurn(turn), false);
});

test("classifies PUTBACK_MISS + FREE_THROW continuation as shooting foul shot result", () => {
  const turn = {
    result_type: "PUTBACK_MISS",
    foul_team: "DEFENSE",
    next_play_type: "FREE_THROW",
    free_throws_remaining: 2,
    foul_player_id: "def-1",
  };
  assert.equal(isShotResultShootingFoulTurn(turn), true);
  assert.equal(isBonusFreeThrowFoulTurn(turn), false);
});

test("does not classify PUTBACK_MISS without free throws as shooting foul", () => {
  const turn = {
    result_type: "PUTBACK_MISS",
    next_play_type: "HCO",
    free_throws_remaining: 0,
  };
  assert.equal(isShotResultShootingFoulTurn(turn), false);
});

