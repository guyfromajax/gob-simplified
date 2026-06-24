import { patchFinalTurnSchemaEntryStepFromAlignment } from '../turnAnimation.js';

describe('patchFinalTurnSchemaEntryStepFromAlignment', () => {
  test('overwrites entry step start.coords from live sprite pixels', () => {
    const scene = {
      game: { config: { width: 1000, height: 500 } },
    };
    const sprites = {
      p1: { x: 500, y: 250 },
      p2: { x: 800, y: 100 },
    };
    const stepsToPlay = [
      {
        start: {
          coords: {
            p1: { x: 10, y: 10 },
            p2: { x: 20, y: 20 },
          },
        },
      },
    ];

    patchFinalTurnSchemaEntryStepFromAlignment({ scene, stepsToPlay, sprites });

    expect(stepsToPlay[0].start.coords.p1).toEqual({ x: 50, y: 25 });
    expect(stepsToPlay[0].start.coords.p2).toEqual({ x: 80, y: 40 });
  });

  test('no-ops when stepsToPlay is empty', () => {
    expect(() =>
      patchFinalTurnSchemaEntryStepFromAlignment({
        scene: { game: { config: { width: 1000, height: 500 } } },
        stepsToPlay: [],
        sprites: {},
      }),
    ).not.toThrow();
  });
});
