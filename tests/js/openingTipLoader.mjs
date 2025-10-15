import { pathToFileURL } from 'url';

export async function resolve(specifier, context, defaultResolve) {
  if (specifier.startsWith('https://')) {
    return { url: specifier, format: 'module', shortCircuit: true };
  }
  if (specifier.endsWith('textScroll.js')) {
    // Stub out textScroll to avoid DOM dependencies
    return { url: 'data:text/javascript,export function appendToTextScroll() {}', format: 'module', shortCircuit: true };
  }
  return defaultResolve(specifier, context, defaultResolve);
}

export async function load(url, context, defaultLoad) {
  if (url.startsWith('https://')) {
    // Stub Phaser
    return {
      format: 'module',
      source: 'export const Math = { Distance: { Between: (x1,y1,x2,y2) => globalThis.Math.hypot(x2 - x1, y2 - y1) }, Between: (min,max) => min };',
      shortCircuit: true
    };
  }
  return defaultLoad(url, context, defaultLoad);
}

