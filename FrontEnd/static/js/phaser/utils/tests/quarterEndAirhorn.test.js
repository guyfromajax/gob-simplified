import { playEndOfQuarterAirhorn } from '../quarterEndAirhorn.js';

describe('playEndOfQuarterAirhorn', () => {
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

    expect(playEndOfQuarterAirhorn(scene, turnData)).toBe(true);
    expect(playMock).toHaveBeenCalledTimes(1);
    expect(global.Audio).toHaveBeenCalledWith('/static/sounds/airhorn-lowervol.wav');

    expect(playEndOfQuarterAirhorn(scene, turnData)).toBe(false);
    expect(playMock).toHaveBeenCalledTimes(1);
  });

  test('does not play when clock does not end at 0', () => {
    const scene = {};
    const turnData = { index: 7, clock_start: 600, clock_end: 597 };

    expect(playEndOfQuarterAirhorn(scene, turnData)).toBe(false);
    expect(playMock).not.toHaveBeenCalled();
  });

  test('does not play when scene.skipToEnd is set', () => {
    const scene = { skipToEnd: true };
    const turnData = { index: 1, clock_start: 12, clock_end: 0 };

    expect(playEndOfQuarterAirhorn(scene, turnData)).toBe(false);
    expect(playMock).not.toHaveBeenCalled();
  });
});
