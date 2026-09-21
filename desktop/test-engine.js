'use strict';

const assert = require('assert');
const path = require('path');
const engine = require('./engine');

const repo = engine.findRepoRoot(__dirname);
assert.ok(repo, 'findRepoRoot from desktop/');
assert.ok(require('fs').existsSync(path.join(repo, 'BackEnd', 'loopback.py')));

assert.strictEqual(engine.assertStablePort(8765), 8765);
assert.strictEqual(engine.assertStablePort('8765'), 8765);
assert.throws(() => engine.assertStablePort(0), /Invalid/);
assert.throws(() => engine.assertStablePort('nope'), /Invalid/);

(async () => {
  const free = await engine.portIsFree(8765);
  assert.strictEqual(typeof free, 'boolean');
  console.log('desktop/test-engine.js ok repo=' + repo + ' port8765Free=' + free);
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
