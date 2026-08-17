/**
 * Unit tests for sim timeline worm time-domain helpers.
 * Run: node --test FrontEnd/static/js/phaser/utils/simTimelineAssembler.worm.test.js
 */
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  clockToSeconds,
  elapsedGameSeconds,
  wormDomainSeconds,
  REG_Q_SEC,
  OT_Q_SEC,
} from './simWormTime.js';

describe('clockToSeconds', () => {
  it('parses MM:SS', () => {
    assert.equal(clockToSeconds('8:00'), 480);
    assert.equal(clockToSeconds('0:12'), 12);
    assert.equal(clockToSeconds('4:00'), 240);
  });
});

describe('elapsedGameSeconds', () => {
  it('tracks regulation from tip', () => {
    assert.equal(elapsedGameSeconds(1, '8:00'), 0);
    assert.equal(elapsedGameSeconds(1, '4:00'), 240);
    assert.equal(elapsedGameSeconds(2, '8:00'), REG_Q_SEC);
    assert.equal(elapsedGameSeconds(3, '0:00'), 3 * REG_Q_SEC);
  });

  it('extends through OT periods of OT_Q_SEC', () => {
    assert.equal(elapsedGameSeconds(5, '4:00'), 4 * REG_Q_SEC);
    assert.equal(elapsedGameSeconds(5, '2:00'), 4 * REG_Q_SEC + 120);
    assert.equal(elapsedGameSeconds(6, '4:00'), 4 * REG_Q_SEC + OT_Q_SEC);
  });
});

describe('wormDomainSeconds', () => {
  it('is regulation until OT', () => {
    assert.equal(wormDomainSeconds(1), 4 * REG_Q_SEC);
    assert.equal(wormDomainSeconds(4), 4 * REG_Q_SEC);
  });

  it('grows with OT', () => {
    assert.equal(wormDomainSeconds(5), 4 * REG_Q_SEC + OT_Q_SEC);
    assert.equal(wormDomainSeconds(6), 4 * REG_Q_SEC + 2 * OT_Q_SEC);
  });
});

describe('progress at quarter ticks', () => {
  it('lands on 25/50/75/100 of regulation domain', () => {
    const domain = wormDomainSeconds(4);
    assert.equal(elapsedGameSeconds(2, '8:00') / domain, 0.25);
    assert.equal(elapsedGameSeconds(3, '8:00') / domain, 0.5);
    assert.equal(elapsedGameSeconds(4, '8:00') / domain, 0.75);
    assert.equal(elapsedGameSeconds(4, '0:00') / domain, 1);
  });
});
