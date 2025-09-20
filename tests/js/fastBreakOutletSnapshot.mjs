import { deriveOffenseContext, computeFastBreakOutletTarget } from '../../FrontEnd/static/js/phaser/animation/outletUtils.js';

const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

function snapshot({ rebounderTeam, rebounderGridX, rebounderGridY, horizontalDistance, verticalOffset }) {
  const { newOffenseTeam, newOffenseBasket } = deriveOffenseContext(rebounderTeam);
  const plan = computeFastBreakOutletTarget({
    rebounderGridX,
    rebounderGridY,
    newOffenseTeam,
    newOffenseBasket,
    randomDistance: () => horizontalDistance,
    randomYOffset: () => verticalOffset,
    clamp,
  });

  const advancesTowardBasket = plan.direction > 0
    ? plan.target.x >= rebounderGridX
    : plan.target.x <= rebounderGridX;

  return {
    rebounderTeam,
    newOffenseTeam,
    rimX: newOffenseBasket.x,
    rebounderGridX,
    direction: plan.direction,
    distance: plan.distance,
    target: plan.target,
    bounds: plan.bounds,
    advancesTowardBasket,
  };
}

const snapshots = [
  snapshot({ rebounderTeam: 'home', rebounderGridX: 32, rebounderGridY: 22, horizontalDistance: 20, verticalOffset: 0 }),
  snapshot({ rebounderTeam: 'away', rebounderGridX: 68, rebounderGridY: 28, horizontalDistance: 18, verticalOffset: 0 }),
];

console.log(JSON.stringify(snapshots, null, 2));

