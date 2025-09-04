export const DEBUG =
  (typeof window !== 'undefined' && window.DEBUG) ||
  (typeof process !== 'undefined' && process.env.DEBUG) ||
  false;

const debugFlagsSource =
  (typeof window !== "undefined" && window.DebugFlags) ||
  (typeof process !== "undefined" && process.env.DebugFlags) ||
  {};

export const DebugFlags = { FB_PAUSE: true, ...debugFlagsSource };
