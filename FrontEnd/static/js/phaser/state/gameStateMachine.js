export const States = {
  Inbound: 'Inbound',
  HalfCourt: 'HalfCourt',
  ShotAttempt: 'ShotAttempt',
  Rebound: 'Rebound',
  FastBreak: 'FastBreak',
  FreeThrow: 'FreeThrow',
  EndQuarter: 'EndQuarter'
};

const transitions = {
  [States.Inbound]: [States.HalfCourt, States.EndQuarter],
  [States.HalfCourt]: [States.ShotAttempt, States.FreeThrow, States.FastBreak, States.EndQuarter],
  [States.ShotAttempt]: [States.Rebound, States.FastBreak, States.FreeThrow, States.Inbound, States.EndQuarter],
  [States.Rebound]: [States.HalfCourt, States.ShotAttempt, States.FastBreak, States.FreeThrow, States.EndQuarter],
  [States.FastBreak]: [States.ShotAttempt, States.Rebound, States.FreeThrow, States.Inbound, States.EndQuarter],
  [States.FreeThrow]: [States.Rebound, States.Inbound, States.EndQuarter],
  [States.EndQuarter]: [States.Inbound]
};

export function createGameStateMachine(initialState = States.Inbound) {
  let state = initialState;
  return {
    transition(next) {
      const allowed = transitions[state] || [];
      if (!allowed.includes(next)) {
        throw new Error(`Invalid transition: ${state} -> ${next}`);
      }
      state = next;
    },
    is(s) {
      return state === s;
    },
    get state() {
      return state;
    }
  };
}

export default createGameStateMachine;
