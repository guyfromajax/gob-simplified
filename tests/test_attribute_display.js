const test = require('node:test');
const assert = require('node:assert/strict');
const { rawAttr, displayAttr, attrTier } = require('../FrontEnd/static/js/utils/attributeDisplay.js');

test('displayAttr is the first digit, uncapped, and 0 is valid', () => {
  const cases = [
    [1, 0], [9, 0], [10, 1], [19, 1], [77, 7], [89, 8],
    [90, 9], [99, 9], [100, 10], [105, 10], [160, 16],
  ];
  for (const [raw, shown] of cases) {
    assert.equal(displayAttr(raw), shown, `raw ${raw}`);
  }
  assert.equal(displayAttr(null), null);
  assert.equal(displayAttr(undefined), null);
  assert.equal(displayAttr(''), null);
  assert.equal(displayAttr('nope'), null);
  assert.equal(displayAttr(NaN), null);
});

test('attrTier follows the displayed value', () => {
  assert.equal(attrTier(0), 'low');
  assert.equal(attrTier(4), 'low');
  assert.equal(attrTier(5), 'mid');
  assert.equal(attrTier(6), 'mid');
  assert.equal(attrTier(7), 'high');
  assert.equal(attrTier(8), 'high');
  assert.equal(attrTier(9), 'elite');
  assert.equal(attrTier(12), 'elite');
  assert.equal(attrTier(null), null);
});

test('rawAttr prefers anchor_<KEY>, then <KEY>, and keeps 0', () => {
  assert.equal(rawAttr({ anchor_SC: 85, SC: 40 }, 'SC'), 85);
  assert.equal(rawAttr({ SC: 40 }, 'SC'), 40);
  assert.equal(rawAttr({ anchor_SC: '', SC: 40 }, 'SC'), 40);
  assert.equal(rawAttr({ anchor_SC: 0, SC: 40 }, 'SC'), 0);
  assert.equal(rawAttr({}, 'SC'), null);
  assert.equal(rawAttr(null, 'SC'), null);
});

test('raw 85 displays 8 and is high; raw 90 displays 9 and is elite', () => {
  assert.equal(displayAttr(85), 8);
  assert.equal(attrTier(displayAttr(85)), 'high');
  assert.equal(displayAttr(90), 9);
  assert.equal(attrTier(displayAttr(90)), 'elite');
});
