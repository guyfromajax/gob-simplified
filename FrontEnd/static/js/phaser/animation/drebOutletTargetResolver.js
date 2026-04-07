function toNumericTarget(raw) {
  if (!raw) return null;
  const x = Number(raw.x);
  const y = Number(raw.y);
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
  return { x, y };
}

function deltaGrid(from, to) {
  return Math.hypot((to?.x ?? 0) - (from?.x ?? 0), (to?.y ?? 0) - (from?.y ?? 0));
}

/**
 * Resolve outlet receiver movement target authority for DREB -> half-court transitions.
 */
export function resolveDrebOutletReceiverTarget({
  requiresDrebOutletPassContract = false,
  contractReceiverTarget = null,
  authorityAnimEnd = null,
  turnDataAnimEnd = null,
  currentReceiverGrid = null,
  meaningfulDeltaThreshold = 1,
}) {
  const current = toNumericTarget(currentReceiverGrid);
  if (!current) {
    return { target: null, source: null, reason: "missing_current_receiver_grid" };
  }

  const contractTarget = toNumericTarget(contractReceiverTarget);
  const authorityTarget = toNumericTarget(authorityAnimEnd);
  const turnTarget = toNumericTarget(turnDataAnimEnd);

  if (requiresDrebOutletPassContract) {
    if (!contractTarget) {
      return { target: null, source: null, reason: "missing_contract_receiver_target" };
    }
    const d = deltaGrid(current, contractTarget);
    if (d <= meaningfulDeltaThreshold) {
      return {
        target: contractTarget,
        source: "dreb_outlet_pass.receiver_target",
        reason: "contract_receiver_target_no_op",
      };
    }
    return { target: contractTarget, source: "dreb_outlet_pass.receiver_target", reason: null };
  }

  const candidates = [
    { source: "dreb_outlet_pass.receiver_target", target: contractTarget },
    { source: "authority_turn.animations_end", target: authorityTarget },
    { source: "turnData.animations_end", target: turnTarget },
  ].filter((c) => !!c.target);

  for (const c of candidates) {
    const d = deltaGrid(current, c.target);
    if (d > meaningfulDeltaThreshold) {
      return { target: c.target, source: c.source, reason: null };
    }
  }

  if (!candidates.length) {
    return { target: null, source: null, reason: "missing_outlet_receiver_animation_end" };
  }
  return { target: null, source: null, reason: "invalid_outlet_receiver_animation_end_no_op" };
}

