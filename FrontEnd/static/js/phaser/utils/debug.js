export const DEBUG =
  (typeof window !== 'undefined' && window.DEBUG) ||
  (typeof process !== 'undefined' && process.env.DEBUG) ||
  false;
