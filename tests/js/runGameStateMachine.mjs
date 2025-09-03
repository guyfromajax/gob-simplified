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

const sm3 = createGameStateMachine(States.HalfCourt);
sm3.transition(States.Turnover);
sm3.transition(States.Inbound);
const turnoverFinal = sm3.state;

console.log(JSON.stringify({ allowedFinal, illegalError, turnoverFinal }));
