export async function resolve(specifier, context, defaultResolve) {
  if (specifier.startsWith('https://')) {
    return { url: specifier, format: 'module', shortCircuit: true };
  }
  return defaultResolve(specifier, context, defaultResolve);
}

export async function load(url, context, defaultLoad) {
  if (url.startsWith('https://')) {
    return {
      format: 'module',
      source: `export const Math = {
  Distance: { Between: (x1, y1, x2, y2) => globalThis.Math.hypot(x2 - x1, y2 - y1) },
  Between: (min, max) => min,
  Clamp: (value, min, max) => {
    if (min > max) [min, max] = [max, min];
    return globalThis.Math.max(min, globalThis.Math.min(max, value));
  }
};`,
      shortCircuit: true
    };
  }
  return defaultLoad(url, context, defaultLoad);
}
