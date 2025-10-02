const PHASER_URLS = new Set([
  'https://cdn.jsdelivr.net/npm/phaser@3.70.0/dist/phaser.esm.js',
  'https://cdn.jsdelivr.net/npm/phaser@3.60.0/dist/phaser.esm.js',
]);

export function resolve(specifier, context, defaultResolve) {
  if (PHASER_URLS.has(specifier)) {
    const url = new URL('./stubs/phaserStub.mjs', import.meta.url);
    return { url: url.href, shortCircuit: true };
  }
  return defaultResolve(specifier, context, defaultResolve);
}
