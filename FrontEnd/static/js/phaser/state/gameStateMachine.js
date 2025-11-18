import {
  DebugFlags,
  animationDebugLog,
  animationDebugWarn,
  isAnimationDebugEnabled,
} from "../utils/debugFlags.js";

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
  [States.FastBreak]: [States.ShotAttempt, States.Rebound, States.FreeThrow, States.Inbound, States.HalfCourt, States.EndQuarter],
  [States.Turnover]: [States.FastBreak, States.Inbound],
  [States.FreeThrow]: [States.Rebound, States.Inbound, States.EndQuarter],
  [States.EndQuarter]: [States.Inbound]
};

let debugTransitions = false;

function shouldLogTransitions() {
  return debugTransitions || isAnimationDebugEnabled();
}

function toObject(payload) {
  if (payload && typeof payload === 'object') return { ...payload };
  if (payload === undefined) return {};
  return { payload };
}

function emitTransitionWarning(message, payload = {}, debugPayload = {}) {
  const structured = {
    message,
    ...toObject(debugPayload),
    ...toObject(payload),
  };
  if (isAnimationDebugEnabled()) {
    animationDebugWarn(message, structured);
  } else {
    console.warn(message, structured);
  }
}

function emitTransitionLog(fromState, toState, payload = {}) {
  if (!shouldLogTransitions()) return;
  const basePayload = toObject(payload);
  if (basePayload.event == null) {
    basePayload.event = toState;
  }
  const message = { fromState, toState, ...basePayload };
  if (debugTransitions && !isAnimationDebugEnabled()) {
    console.log(message);
  } else {
    animationDebugLog('FSM transition', message);
  }
}

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

export function safeTransition(
  machine,
  next,
  ctx = {},
  required = [],
  debugPayload = {}
) {
  if (!machine) return;
  const missing = required.filter(
    (key) => ctx[key] === undefined || ctx[key] === null
  );
  if (missing.length) {
    const stack = new Error().stack?.split("\n")[2]?.trim();
    emitTransitionWarning(
      "safeTransition missing context",
      { missing, caller: stack, toState: next, fromState: machine.state },
      debugPayload
    );
    return;
  }

  const allowed = transitions[machine.state] || [];
  if (!allowed.includes(next)) {
    const stack = new Error().stack?.split("\n")[2]?.trim();
    emitTransitionWarning(
      `Invalid transition: ${machine.state} -> ${next}`,
      { caller: stack, fromState: machine.state, toState: next },
      debugPayload
    );
    return;
  }

  transitionWithDebug(machine, next, ctx);
}

export function transitionWithDebug(machine, next, payload = {}) {
  if (!machine) return;
  const normalized = toObject(payload);
  if (normalized.event == null) normalized.event = next;
  machine.transition(next, normalized);
}

export function createGameStateMachine(initialState = States.Inbound) {
  let state = initialState;
  return {
    transition(next, payload = {}) {
      const allowed = transitions[state] || [];
      if (!allowed.includes(next)) {
        throw new Error(`Invalid transition: ${state} -> ${next}`);
      }
      const fromState = state;
      state = next;
      emitTransitionLog(fromState, state, payload);
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
