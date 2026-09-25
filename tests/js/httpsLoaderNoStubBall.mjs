import { readFile } from 'fs/promises';
import path from 'path';
import { fileURLToPath, pathToFileURL } from 'url';

const ROOT = fileURLToPath(new URL('../..', import.meta.url));

const PHASER_MATH_STUB = `export const Math = {
  Distance: { Between: (x1, y1, x2, y2) => globalThis.Math.hypot(x2 - x1, y2 - y1) },
  Between: (min, max) => min,
  Clamp: (value, min, max) => {
    if (min > max) [min, max] = [max, min];
    return globalThis.Math.max(min, globalThis.Math.min(max, value));
  }
};`;

function isVendoredPhaser(url) {
  return (
    url.startsWith('file:') &&
    /\/FrontEnd\/static\/js\/vendor\/phaser-\d+\.\d+\.\d+\.esm\.js$/.test(
      fileURLToPath(url)
    )
  );
}

export async function resolve(specifier, context, defaultResolve) {
  if (specifier.startsWith('https://')) {
    return { url: specifier, format: 'module', shortCircuit: true };
  }
  if (specifier.startsWith('/js/vendor/')) {
    const disk = path.join(ROOT, 'FrontEnd/static', specifier.slice(1));
    return { url: pathToFileURL(disk).href, format: 'module', shortCircuit: true };
  }
  return defaultResolve(specifier, context, defaultResolve);
}

export async function load(url, context, defaultLoad) {
  // jsDelivr Phaser used to land here. Vendored Phaser is resolved to disk above,
  // but the browser bundle still cannot execute in Node (HTMLVideoElement).
  if (url.startsWith('https://') || isVendoredPhaser(url)) {
    return {
      format: 'module',
      source: PHASER_MATH_STUB,
      shortCircuit: true
    };
  }
  // uiSfx.js lives outside the phaser package (which is "type": "module").
  // Node would otherwise parse it as CommonJS and drop its named exports.
  if (url.includes('/FrontEnd/static/js/shared/uiSfx.js')) {
    return {
      format: 'module',
      source: await readFile(fileURLToPath(url), 'utf8'),
      shortCircuit: true
    };
  }
  return defaultLoad(url, context, defaultLoad);
}
