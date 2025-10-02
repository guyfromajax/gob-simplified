import { States, safeTransition, getDebugTransitions } from "../state/gameStateMachine.js";

export function buildFastBreakTransitionPath(start, target) {
  if (!target || start === target) return [];

  if (start === States.Inbound) {
    return [States.HalfCourt, ...buildFastBreakTransitionPath(States.HalfCourt, target)];
  }

  if (start === States.HalfCourt) {
    if (target === States.FastBreak) {
      return [States.FastBreak];
    }
    if (target === States.Rebound) {
      return [States.FastBreak, States.Rebound];
    }
    if (target === States.FastBreakOutlet) {
      return [States.FastBreak, States.Rebound, States.FastBreakOutlet];
    }
    return [States.FastBreak, States.Rebound, target];
  }

  if (start === States.FastBreak) {
    if (target === States.FastBreakOutlet) {
      return [States.Rebound, States.FastBreakOutlet];
    }
    if (target === States.Rebound) {
      return [States.Rebound];
    }
  }

  return [target];
}

export function transitionFastBreakState(scene, target, options = {}) {
  const machine = scene?.stateMachine;
  if (!machine || !target) return;

  const startState = machine.state;
  if (startState === target) return;

  const steps = buildFastBreakTransitionPath(startState, target);
  if (!steps.length) return;

  const { debugStepIndex, context, applyContextToAllSteps = false } = options;
  const finalIndex = steps.length - 1;

  for (let index = 0; index < steps.length; index++) {
    const step = steps[index];
    if (machine.state === step) continue;

    let ctx;
    if (applyContextToAllSteps || index === finalIndex) {
      if (context) ctx = context;
      if (debugStepIndex != null && getDebugTransitions()) {
        ctx = { ...(ctx || {}), stepIndex: debugStepIndex };
      }
    }

    const prev = machine.state;
    safeTransition(machine, step, ctx);
    if (machine.state === prev) {
      console.warn("fastBreakTransition: blocked transition", {
        from: startState,
        target,
        attempted: step,
        current: machine.state,
      });
      break;
    }
  }

  if (machine.state !== target) {
    console.warn("fastBreakTransition: final state mismatch", {
      from: startState,
      target,
      current: machine.state,
    });
  }
}
