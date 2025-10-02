const globalScope =
  (typeof window !== 'undefined' && window) ||
  (typeof globalThis !== 'undefined' && globalThis) ||
  undefined;

const envScope =
  (typeof process !== 'undefined' && process?.env) ||
  undefined;

const DebugFlags = {
  BALL: false,
  FSM: false,
  FB_PAUSE: true,
  OUTLET: false,
};

function coerceBoolean(value) {
  if (typeof value === 'string') {
    return !['false', '0', 'no'].includes(value.toLowerCase());
  }
  return Boolean(value);
}

function resolveAnimationDebug() {
  if (globalScope && typeof globalScope.DEBUG_ANIM !== 'undefined') {
    return coerceBoolean(globalScope.DEBUG_ANIM);
  }
  if (envScope && typeof envScope.DEBUG_ANIM !== 'undefined') {
    return coerceBoolean(envScope.DEBUG_ANIM);
  }
  return false;
}

function resolveFeatureFlag(flagName, defaultValue = false) {
  if (!flagName) return defaultValue;
  if (globalScope && typeof globalScope[flagName] !== 'undefined') {
    return coerceBoolean(globalScope[flagName]);
  }
  if (envScope && typeof envScope[flagName] !== 'undefined') {
    return coerceBoolean(envScope[flagName]);
  }
  return defaultValue;
}

export function isAnimationDebugEnabled() {
  return resolveAnimationDebug();
}

export function setAnimationDebugEnabled(value) {
  if (globalScope) {
    globalScope.DEBUG_ANIM = coerceBoolean(value);
  }
}

export function isPossessionRunnerEnabled() {
  return resolveFeatureFlag('FEATURE_POSSESSION_RUNNER');
}

export function setPossessionRunnerEnabled(value) {
  if (globalScope) {
    globalScope.FEATURE_POSSESSION_RUNNER = coerceBoolean(value);
  }
}

export function animationDebugLog(...args) {
  if (!isAnimationDebugEnabled()) return;
  if (args.length === 1) {
    console.log(args[0]);
  } else {
    console.log(...args);
  }
}

export function animationDebugWarn(...args) {
  if (!isAnimationDebugEnabled()) return;
  if (args.length === 1) {
    console.warn(args[0]);
  } else {
    console.warn(...args);
  }
}

Object.defineProperty(DebugFlags, 'ANIM', {
  enumerable: true,
  get: () => isAnimationDebugEnabled(),
});

Object.defineProperty(DebugFlags, 'FEATURE_POSSESSION_RUNNER', {
  enumerable: true,
  get: () => isPossessionRunnerEnabled(),
});

export { DebugFlags };

export default DebugFlags;
