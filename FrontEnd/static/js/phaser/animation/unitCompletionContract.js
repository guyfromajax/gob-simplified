function normalizeFailurePolicy(policy) {
  if (policy === "throw" || policy === "warn" || policy === "degrade") return policy;
  return "warn";
}

/**
 * Enforce execution-mode completion semantics for a unit contract.
 *
 * Rules:
 * - skeleton: must include final offensive mover settled unless explicitly shot-terminating.
 * - dynamic_event: must include authorizing event receipt.
 */
export function enforceUnitCompletionContract({
  contract,
  observed = {},
  context = {},
  emitTelemetry,
  logger = console,
}) {
  const unitId = contract?.unit_id ?? "unknown_unit";
  const executionMode = contract?.execution_mode ?? "dynamic_event";
  const failurePolicy = normalizeFailurePolicy(contract?.failure_policy);
  const errors = [];

  if (executionMode === "skeleton") {
    const shotTerminatesUnit = contract?.shot_terminates_unit === true;
    const shotTerminated = observed?.shotTerminated === true;
    const finalOffensiveMoverSettled = observed?.finalOffensiveMoverSettled === true;
    if (!(finalOffensiveMoverSettled || (shotTerminatesUnit && shotTerminated))) {
      errors.push("missing_final_offensive_mover_settle");
    }
  } else if (executionMode === "dynamic_event") {
    if (observed?.authorizingEventReceived !== true) {
      errors.push("missing_authorizing_event_receipt");
    }
  } else {
    errors.push(`unsupported_execution_mode:${executionMode}`);
  }

  const payloadBase = {
    unitId,
    executionMode,
    failurePolicy,
    advanceTrigger: contract?.advance_trigger ?? null,
    visualSettleTrigger: contract?.visual_settle_trigger ?? null,
    ...context,
  };

  if (!errors.length) {
    emitTelemetry?.("unit_completion_contract_validated", {
      ...payloadBase,
      visualSettled: observed?.visualSettled === true,
    });
    return { ok: true, errors: [] };
  }

  const payload = {
    ...payloadBase,
    errors,
    visualSettled: observed?.visualSettled === true,
  };
  emitTelemetry?.("unit_completion_contract_violation", payload);

  const message =
    `[completion contract] validation failed ` +
    `(unit=${unitId}, mode=${executionMode}, errors=${errors.join(",")})`;

  if (failurePolicy === "throw") {
    throw new Error(message);
  }
  logger?.warn?.(message, payload);
  return { ok: false, errors };
}

