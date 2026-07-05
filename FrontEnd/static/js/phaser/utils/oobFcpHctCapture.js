/**
 * Auto-capture FCP/HCT over-and-back repro data on the client.
 *
 * Fires after animation when a dynamic press/trap turn had a backcourt §6 pass,
 * OVER_BACK turnover_type, or "over & back" in text.
 *
 * Toggle via window.LOG_OOB_FCP_HCT_CAPTURE = false in the console.
 */

const CAPTURE_PREFIX = '[OOB FCP/HCT CAPTURE]';

function captureEnabled() {
  if (typeof window !== 'undefined' && window.LOG_OOB_FCP_HCT_CAPTURE === false) {
    return false;
  }
  return true;
}

function isInBackcourt(x, isAwayOffense) {
  const fx = Number(x);
  if (!Number.isFinite(fx)) return false;
  return isAwayOffense ? fx > 50 : fx < 50;
}

function resolveIsAwayOffense(turn, scene) {
  const offenseId = turn?.offense_team_id ?? turn?.offenseTeamId ?? null;
  const homeId =
    scene?.simData?.home_team_id ??
    scene?.homeTeamId ??
    (typeof scene?.simData?.home_team === 'object'
      ? scene?.simData?.home_team?.team_id
      : null);
  if (offenseId != null && homeId != null) {
    return String(offenseId) !== String(homeId);
  }
  return null;
}

function loopSegmentsFromTurn(turn) {
  return (
    turn?.fcp_loop_segments ??
    turn?.hct_loop_segments ??
    []
  );
}

function summarizeBackcourtPasses(turn, isAwayOffense) {
  if (isAwayOffense == null) return [];
  const segments = loopSegmentsFromTurn(turn);
  const out = [];
  for (let idx = 0; idx < segments.length; idx += 1) {
    const seg = segments[idx];
    if ((seg?.reason || '') !== 'hct_pass') continue;
    const receiverPos = seg.pass_to_pos || seg.ball_owner_pos;
    const receiverXy = seg?.off_end?.[receiverPos] || {};
    const rx = Number(receiverXy.x);
    if (!isInBackcourt(rx, isAwayOffense)) continue;
    const passerPos = seg.pass_from_pos;
    out.push({
      segment_index: idx,
      passer_pos: passerPos,
      receiver_pos: receiverPos,
      passer_xy: seg?.off_end?.[passerPos] || null,
      receiver_xy: receiverXy,
      step_label: seg.step_label || seg.reason,
    });
  }
  return out;
}

function isDynamicFcpHctTurn(turn) {
  const current = String(turn?.current_turn || '').toUpperCase();
  if (current === 'FCP' || current === 'HCT') return true;
  if (Array.isArray(turn?.fcp_loop_segments) && turn.fcp_loop_segments.length > 0) {
    return true;
  }
  if (Array.isArray(turn?.hct_loop_segments) && turn.hct_loop_segments.length > 0) {
    return true;
  }
  return false;
}

function shouldCaptureTurn(turn, backcourtPasses) {
  if (!isDynamicFcpHctTurn(turn)) return false;
  const turnoverType = String(turn?.turnover_type || '').toUpperCase();
  const text = String(turn?.text || '').toLowerCase();
  if (backcourtPasses.length > 0) return true;
  if (turnoverType === 'OVER_BACK') return true;
  if (text.includes('over & back') || text.includes('over and back')) return true;
  return false;
}

function slimTurnForCapture(turn) {
  return {
    index: turn?.index ?? null,
    turn_count: turn?.turn_count ?? turn?.id ?? null,
    current_turn: turn?.current_turn ?? null,
    result_type: turn?.result_type ?? null,
    turnover_type: turn?.turnover_type ?? null,
    suppress_turn_prep_turnover_announce: turn?.suppress_turn_prep_turnover_announce ?? null,
    text: turn?.text ?? null,
    possession_flips: turn?.possession_flips ?? null,
    next_play_type: turn?.next_play_type ?? null,
    offense_team_id: turn?.offense_team_id ?? null,
    victim_id: turn?.victim_id ?? null,
    fcp_bh_pos: turn?.fcp_bh_pos ?? turn?.hct_bh_pos ?? null,
    animation_step_count: Array.isArray(turn?.animation_steps)
      ? turn.animation_steps.length
      : 0,
    loop_segment_count: loopSegmentsFromTurn(turn).length,
  };
}

/**
 * Call after FCP/HCT turn animation completes. Logs to console and stores on window.
 */
export function captureOobFcpHctTurnIfRelevant(turn, scene, context = {}) {
  if (!captureEnabled() || !turn) return null;

  const isAwayOffense = resolveIsAwayOffense(turn, scene);
  const backcourtPasses = summarizeBackcourtPasses(turn, isAwayOffense);
  if (!shouldCaptureTurn(turn, backcourtPasses)) return null;

  const payload = {
    phase: 'frontend_turn_end',
    ...slimTurnForCapture(turn),
    is_away_offense: isAwayOffense,
    backcourt_pass_count: backcourtPasses.length,
    backcourt_passes: backcourtPasses,
    turnIndex: context.turnIndex ?? turn?.index ?? null,
    captured_at: new Date().toISOString(),
  };

  if (typeof window !== 'undefined') {
    window.__oobFcpHctCaptures = window.__oobFcpHctCaptures || [];
    window.__oobFcpHctCaptures.push(payload);
    window.__lastOobFcpHctCapture = payload;
  }

  console.warn(CAPTURE_PREFIX, payload);
  try {
    console.warn(`${CAPTURE_PREFIX} JSON`, JSON.stringify(payload, null, 2));
  } catch (_) {
    // ignore stringify failures
  }

  return payload;
}

export default captureOobFcpHctTurnIfRelevant;
