import test from "node:test";
import assert from "node:assert/strict";
import { resolveDrebOutletReceiverTarget } from "../drebOutletTargetResolver.js";

test("strict mode uses contract receiver target when meaningful", () => {
  const result = resolveDrebOutletReceiverTarget({
    requiresDrebOutletPassContract: true,
    contractReceiverTarget: { x: 20, y: 20 },
    authorityAnimEnd: { x: 40, y: 40 },
    turnDataAnimEnd: { x: 50, y: 50 },
    currentReceiverGrid: { x: 10, y: 10 },
  });
  assert.equal(result.source, "dreb_outlet_pass.receiver_target");
  assert.deepEqual(result.target, { x: 20, y: 20 });
  assert.equal(result.reason, null);
});

test("strict mode ignores animations_end when contract target missing", () => {
  const result = resolveDrebOutletReceiverTarget({
    requiresDrebOutletPassContract: true,
    contractReceiverTarget: null,
    authorityAnimEnd: { x: 40, y: 40 },
    turnDataAnimEnd: { x: 50, y: 50 },
    currentReceiverGrid: { x: 10, y: 10 },
  });
  assert.equal(result.target, null);
  assert.equal(result.reason, "missing_contract_receiver_target");
});

test("strict mode accepts no-op contract target with warning reason", () => {
  const result = resolveDrebOutletReceiverTarget({
    requiresDrebOutletPassContract: true,
    contractReceiverTarget: { x: 10.2, y: 10.2 },
    currentReceiverGrid: { x: 10, y: 10 },
    meaningfulDeltaThreshold: 1,
  });
  assert.deepEqual(result.target, { x: 10.2, y: 10.2 });
  assert.equal(result.source, "dreb_outlet_pass.receiver_target");
  assert.equal(result.reason, "contract_receiver_target_no_op");
});

test("non-strict mode can use authority animations_end", () => {
  const result = resolveDrebOutletReceiverTarget({
    requiresDrebOutletPassContract: false,
    contractReceiverTarget: null,
    authorityAnimEnd: { x: 22, y: 10 },
    turnDataAnimEnd: { x: 12, y: 11 },
    currentReceiverGrid: { x: 10, y: 10 },
  });
  assert.equal(result.source, "authority_turn.animations_end");
  assert.deepEqual(result.target, { x: 22, y: 10 });
});

