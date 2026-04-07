/**
 * Run: cd FrontEnd/static/js/phaser && node --test utils/syncPlayerSpriteAttributes.test.js
 */
import test from "node:test";
import assert from "node:assert/strict";
import {
  attachMovementAttributeAnchor,
  syncSpriteAttributesFromPlayerEnergy,
} from "./syncPlayerSpriteAttributes.js";

test("attachMovementAttributeAnchor uses anchor_AG", () => {
  const sprite = {};
  attachMovementAttributeAnchor(
    { attributes: { anchor_AG: 80, AG: 72, NG: 0.9 } },
    sprite
  );
  assert.equal(sprite._agMovementAnchor, 80);
  assert.equal(sprite.attributes.AG, 72);
});

test("attachMovementAttributeAnchor infers anchor from AG/NG", () => {
  const sprite = {};
  attachMovementAttributeAnchor({ attributes: { AG: 63, NG: 0.7 } }, sprite);
  assert.ok(Math.abs(sprite._agMovementAnchor - 90) < 1e-6);
});

test("syncSpriteAttributesFromPlayerEnergy rescales AG", () => {
  const sprites = {
    p1: {
      _agMovementAnchor: 100,
      attributes: { AG: 100, NG: 1 },
    },
  };
  syncSpriteAttributesFromPlayerEnergy(sprites, { p1: { NG: 0.85 } });
  assert.equal(sprites.p1.attributes.AG, 85);
  assert.equal(sprites.p1.attributes.NG, 0.85);
});
