import { createGameStateMachine, States } from '../../FrontEnd/static/js/phaser/state/gameStateMachine.js';

const sm = createGameStateMachine(States.Inbound);
sm.transition(States.HalfCourt);
sm.transition(States.ShotAttempt);
sm.transition(States.Rebound);
const allowedFinal = sm.state;

const sm2 = createGameStateMachine(States.Inbound);
let illegalError = false;
try {
  sm2.transition(States.Rebound);
} catch (e) {
  illegalError = true;
}

console.log(JSON.stringify({ allowedFinal, illegalError }));
