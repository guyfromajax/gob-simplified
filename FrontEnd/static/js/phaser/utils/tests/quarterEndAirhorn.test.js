import { playEndOfQuarterAirhorn, signalQuarterEnded } from '../quarterEndAirhorn.js';

describe('signalQuarterEnded', () => {
  let playMock;

  beforeEach(() => {
    playMock = jest.fn().mockResolvedValue(undefined);
    global.Audio = jest.fn(() => ({
      volume: 0,
      currentTime: 0,
      play: playMock,
    }));
    window.API_CONFIG = { getStaticPath: () => '/static' };
  });

  test('plays once per turn when clock_end is 0 and clock_start > 0', () => {
    const scene = {};
    const turnData = { index: 42, clock_start: 15, clock_end: 0 };

    expect(signalQuarterEnded(scene, turnData, { phase: 'playbackComplete' })).toBe(true);
    expect(playMock).toHaveBeenCalledTimes(1);
    expect(global.Audio).toHaveBeenCalledWith('/static/sounds/airhorn-lowervol.wav');

    expect(signalQuarterEnded(scene, turnData, { phase: 'playbackComplete' })).toBe(false);
    expect(playMock).toHaveBeenCalledTimes(1);
  });

  test('clockTween defers when quarter_ends_after is set', () => {
    const scene = {};
    const turnData = { index: 9, quarter_ends_after: true, clock_start: 0, clock_end: 0 };

    expect(signalQuarterEnded(scene, turnData, { phase: 'clockTween' })).toBe(false);
    expect(playMock).not.toHaveBeenCalled();
  });

  test('playbackComplete plays for quarter_ends_after even without clock contract', () => {
    const scene = {};
    const turnData = { index: 9, quarter_ends_after: true, clock_start: 0, clock_end: 0 };

    expect(signalQuarterEnded(scene, turnData, { phase: 'playbackComplete' })).toBe(true);
    expect(playMock).toHaveBeenCalledTimes(1);
  });

  test('clockTween still plays for contract-only terminal turns', () => {
    const scene = {};
    const turnData = { index: 3, clock_start: 8, clock_end: 0 };

    expect(signalQuarterEnded(scene, turnData, { phase: 'clockTween' })).toBe(true);
    expect(playMock).toHaveBeenCalledTimes(1);
  });

  test('does not play when clock does not end at 0 and no quarter_ends_after', () => {
    const scene = {};
    const turnData = { index: 7, clock_start: 600, clock_end: 597 };

    expect(signalQuarterEnded(scene, turnData, { phase: 'playbackComplete' })).toBe(false);
    expect(playMock).not.toHaveBeenCalled();
  });

  test('does not play when scene.skipToEnd is set', () => {
    const scene = { skipToEnd: true };
    const turnData = { index: 1, clock_start: 12, clock_end: 0 };

    expect(signalQuarterEnded(scene, turnData, { phase: 'playbackComplete' })).toBe(false);
    expect(playMock).not.toHaveBeenCalled();
  });
});

describe('playEndOfQuarterAirhorn (deprecated wrapper)', () => {
  let playMock;

  beforeEach(() => {
    playMock = jest.fn().mockResolvedValue(undefined);
    global.Audio = jest.fn(() => ({
      volume: 0,
      currentTime: 0,
      play: playMock,
    }));
    window.API_CONFIG = { getStaticPath: () => '/static' };
  });

  test('delegates to signalQuarterEnded playbackComplete', () => {
    const scene = {};
    const turnData = { index: 42, clock_start: 15, clock_end: 0 };

    expect(playEndOfQuarterAirhorn(scene, turnData)).toBe(true);
    expect(playMock).toHaveBeenCalledTimes(1);
  });
});
