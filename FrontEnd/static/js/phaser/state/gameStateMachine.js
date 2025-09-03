import { DebugFlags } from "../utils/debugFlags.js";

export const States = {
  Inbound: 'Inbound',
  HalfCourt: 'HalfCourt',
  ShotAttempt: 'ShotAttempt',
  Rebound: 'Rebound',
  OutletSetup: 'OutletSetup',
  FastBreakOutlet: 'FastBreakOutlet',
  FastBreak: 'FastBreak',
  FreeThrow: 'FreeThrow',
  Turnover: 'Turnover',
  EndQuarter: 'EndQuarter'
};

export const transitions = {
  [States.Inbound]: [States.HalfCourt, States.EndQuarter],
  [States.HalfCourt]: [States.ShotAttempt, States.FreeThrow, States.FastBreak, States.Turnover, States.EndQuarter],
  [States.ShotAttempt]: [States.Rebound, States.FastBreak, States.FreeThrow, States.Inbound, States.EndQuarter],
  [States.Rebound]: [
    States.OutletSetup,
    States.FastBreakOutlet,
    States.HalfCourt,
    States.ShotAttempt,
    States.FastBreak,
    States.FreeThrow,
    States.EndQuarter,
  ],
  [States.OutletSetup]: [States.HalfCourt],
  [States.FastBreakOutlet]: [States.FastBreak],
  [States.FastBreak]: [States.ShotAttempt, States.Rebound, States.FreeThrow, States.Inbound, States.EndQuarter],
  [States.Turnover]: [States.FastBreak, States.Inbound],
  [States.FreeThrow]: [States.Rebound, States.Inbound, States.EndQuarter],
  [States.EndQuarter]: [States.Inbound]
};

let debugTransitions = false;

export function setDebugTransitions(value) {
  debugTransitions = !!value;
}

export function getDebugTransitions() {
  return debugTransitions;
}

export function createTransitionGuard(machine, disallowed = []) {
  if (!machine) return () => {};
  const original = machine.transition.bind(machine);
  machine.transition = (next, ...args) => {
    if (disallowed.includes(next)) {
      if (DebugFlags?.FSM)
        console.log("FSM: guard rejected", next);
      return;
    }
    return original(next, ...args);
  };
  return () => {
    machine.transition = original;
  };
}

export function safeTransition(machine, next, ctx = {}, required = []) {
  if (!machine) return;
  const missing = required.filter(
    (key) => ctx[key] === undefined || ctx[key] === null
  );
  if (missing.length) {
    const stack = new Error().stack?.split("\n")[2]?.trim();
    console.warn("safeTransition missing context", { missing, caller: stack });
    return;
  }

  const allowed = transitions[machine.state] || [];
  if (!allowed.includes(next)) {
    const stack = new Error().stack?.split("\n")[2]?.trim();
    console.warn(`Invalid transition: ${machine.state} -> ${next}`, {
      caller: stack,
    });
    return;
  }

  const prevState = machine.state;
  machine.transition(next);
  if (debugTransitions) {
    const { stepIndex, shotResult, currentOwnerId, pendingOwnerId } = ctx;
    console.log({
      prevState,
      event: next,
      nextState: machine.state,
      stepIndex,
      shotResult,
      currentOwnerId,
      pendingOwnerId,
    });
  }
}

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
    },
  };
}

export default createGameStateMachine;
