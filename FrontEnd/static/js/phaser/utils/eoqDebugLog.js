/**
 * Frontend tracing for Final Shot / FLSS EOQ chains.
 * Filter browser console with: EOQ-TRACE
 *
 * On by default. Disable with: window.GOB_EOQ_TRACE = false
 */

import { pixelsToGrid } from './gridToPixels.js';

export function isEoqTraceEnabled(_scene) {
  if (typeof window !== 'undefined' && window.GOB_EOQ_TRACE === false) {
    return false;
  }
  return true;
}

function roundCoord(n) {
  return Math.round(Number(n) * 100) / 100;
}

export function isEoqTurnData(turnData) {
  if (!turnData || typeof turnData !== 'object') return false;
  return Boolean(
    turnData.final_turn
    || turnData.flss
    || turnData.final_shot_possession
    || turnData.late_clock_eoq
    || turnData.terminal_dreb_eoq
    || turnData.eoq_trace_seq
    || turnData.eoq_trace_role
    || (
      (turnData.result_type === 'BASELINE_INBOUND' || turnData.result_type === 'SIDE_INBOUND')
      && turnData.eoq_trace_seq
    ),
  );
}

export function snapshotClockFromTurn(turnData, scene) {
  const gs = scene?.gameClock?.getState?.() || {};
  return {
    quarter: turnData?.quarter ?? scene?.simData?.quarter ?? scene?.quarter ?? null,
    time_remaining:
      turnData?.time_remaining
      ?? turnData?.clock_end
      ?? gs.remainingSec
      ?? null,
    shot_clock_remaining: turnData?.shot_clock_remaining ?? null,
    clock_start: turnData?.clock_start ?? turnData?.clockStart ?? null,
    clock_end: turnData?.clock_end ?? turnData?.clockEnd ?? null,
    clock_display: turnData?.clock ?? gs.display ?? null,
  };
}

export function snapshotPlayersFromSprites(scene, playerSprites) {
  const width = scene?.game?.config?.width;
  const height = scene?.game?.config?.height;
  const offense = {};
  const defense = {};
  const offenseTeamId = scene?.offenseTeamId ?? scene?.simData?.offense_team_id;

  for (const [playerId, sprite] of Object.entries(playerSprites || {})) {
    if (!sprite) continue;
    const info = scene?.playerInfo?.[playerId];
    const pos = info?.pos ?? '?';
    let coords = null;
    if (Number.isFinite(width) && Number.isFinite(height) && width > 0 && height > 0) {
      coords = pixelsToGrid(sprite.x, sprite.y, width, height);
      coords = { x: roundCoord(coords.x), y: roundCoord(coords.y) };
    } else if (sprite.gridX != null && sprite.gridY != null) {
      coords = { x: roundCoord(sprite.gridX), y: roundCoord(sprite.gridY) };
    }
    const row = {
      player_id: playerId,
      pos,
      coords,
      team_id: sprite.team_id ?? info?.team_id ?? null,
    };
    const isOffense = offenseTeamId != null && String(sprite.team_id) === String(offenseTeamId);
    if (isOffense) {
      offense[pos] = row;
    } else {
      defense[pos] = row;
    }
  }
  return { offense, defense };
}

export function snapshotShooterFromTurn(turnData, scene, playerSprites, label = 'shooter') {
  const shooterId =
    turnData?.shooter_id
    ?? turnData?.shooterId
    ?? turnData?.roles?.shooter_id
    ?? turnData?.ball_handler_id;
  const sprite = shooterId ? playerSprites?.[shooterId] : null;
  const info = shooterId ? scene?.playerInfo?.[shooterId] : null;
  const width = scene?.game?.config?.width;
  const height = scene?.game?.config?.height;
  let coords = turnData?.shooter_coords ?? null;
  if (!coords && sprite && width && height) {
    coords = pixelsToGrid(sprite.x, sprite.y, width, height);
    coords = { x: roundCoord(coords.x), y: roundCoord(coords.y) };
  }
  return {
    label,
    player_id: shooterId ?? null,
    pos: info?.pos ?? turnData?.shooter_pos ?? null,
    name: info?.name ?? null,
    coords,
    flss_zone: turnData?.flss_zone ?? null,
    flss: turnData?.flss ?? false,
    final_turn: turnData?.final_turn ?? false,
  };
}

function clockFromSchemaBlock(block) {
  if (!block || typeof block !== 'object') return {};
  const clock = block.clock && typeof block.clock === 'object' ? block.clock : {};
  return {
    clock_remaining: clock.clock_remaining ?? null,
    shot_clock_remaining: clock.shot_clock_remaining ?? null,
  };
}

export function summarizeAnimationStep(step, index) {
  if (!step || typeof step !== 'object') {
    return { index, error: 'not_an_object' };
  }
  const start = step.start && typeof step.start === 'object' ? step.start : {};
  const end = step.end && typeof step.end === 'object' ? step.end : {};
  const actions = start.action && typeof start.action === 'object' ? start.action : {};
  const actionEntries = Object.entries(actions).slice(0, 8);
  return {
    index,
    id: step.id ?? null,
    start_clock: clockFromSchemaBlock(start),
    end_clock: clockFromSchemaBlock(end),
    duration_ms: step.duration_ms ?? end.time_elapsed ?? null,
    actions: Object.fromEntries(actionEntries),
    next_step_index: step.next_step_index ?? null,
    branch: step.branch ?? null,
  };
}

export function summarizeTurnData(turnData) {
  if (!turnData || typeof turnData !== 'object') return {};
  return {
    eoq_trace_seq: turnData.eoq_trace_seq ?? null,
    eoq_trace_turn_in_seq: turnData.eoq_trace_turn_in_seq ?? null,
    eoq_trace_role: turnData.eoq_trace_role ?? null,
    result_type: turnData.result_type ?? null,
    current_turn: turnData.current_turn ?? null,
    time_elapsed: turnData.time_elapsed ?? null,
    clock_start: turnData.clock_start ?? null,
    clock_end: turnData.clock_end ?? null,
    shot_clock_start: turnData.shot_clock_start ?? null,
    shot_clock_end: turnData.shot_clock_end ?? null,
    next_play_type: turnData.next_play_type ?? null,
    quarter_ends_after: turnData.quarter_ends_after ?? null,
    late_clock_eoq: turnData.late_clock_eoq ?? null,
    flss: turnData.flss ?? null,
    flss_zone: turnData.flss_zone ?? null,
    final_turn: turnData.final_turn ?? null,
    final_shot_possession: turnData.final_shot_possession ?? null,
    terminal_dreb_eoq: turnData.terminal_dreb_eoq ?? null,
    animation_step_count: Array.isArray(turnData.animation_steps)
      ? turnData.animation_steps.length
      : 0,
  };
}

function emitTrace(event, payload) {
  console.warn('[EOQ-TRACE]', event, payload);
}

export function logEoqStep(scene, flow, step, phase, turnData, context = {}, extra = {}) {
  if (!isEoqTraceEnabled(scene)) return;
  const playerSprites = context.playerSprites || scene?.playerSprites || {};
  const payload = {
    event: 'STEP',
    flow,
    step,
    phase,
    turn_index: turnData?.index ?? scene?.currentTurn ?? null,
    turn: summarizeTurnData(turnData),
    clock: snapshotClockFromTurn(turnData, scene),
    players: snapshotPlayersFromSprites(scene, playerSprites),
    shooter: snapshotShooterFromTurn(turnData, scene, playerSprites),
    ...extra,
  };
  emitTrace('STEP', payload);
}

export function logEoqTurn(scene, phase, turnData, context = {}, extra = {}) {
  if (!isEoqTraceEnabled(scene) || !isEoqTurnData(turnData)) return;
  const playerSprites = context.playerSprites || scene?.playerSprites || {};
  const flow = turnData?.flss
    ? 'FLSS'
    : (turnData?.eoq_trace_role || (turnData?.final_turn ? 'FINAL_SHOT' : 'EOQ'));
  const steps = Array.isArray(turnData?.animation_steps) ? turnData.animation_steps : [];
  emitTrace('TURN', {
    event: 'TURN',
    phase,
    flow,
    turn_index: turnData?.index ?? scene?.currentTurn ?? null,
    turn: summarizeTurnData(turnData),
    clock: snapshotClockFromTurn(turnData, scene),
    animation_steps: steps.map((s, i) => summarizeAnimationStep(s, i)),
    players: snapshotPlayersFromSprites(scene, playerSprites),
    shooter: snapshotShooterFromTurn(turnData, scene, playerSprites),
    ...extra,
  });
}

export function logEoqApiReceipt(scene, turnData, responseMeta = {}) {
  if (!isEoqTraceEnabled(scene)) return;
  const turn = turnData?.turn ?? turnData;
  const batch = turn?.result_type === 'BATCH' ? (turn.batch_turns || []) : [turn].filter(Boolean);
  const eoqTurns = batch.filter(isEoqTurnData);
  if (!eoqTurns.length && !responseMeta?.quarter_complete) return;
  emitTrace('API', {
    event: 'API',
    phase: 'RECEIVED',
    response_meta: responseMeta,
    eoq_turns: eoqTurns.map((t) => ({
      turn: summarizeTurnData(t),
      animation_steps: (t.animation_steps || []).map((s, i) => summarizeAnimationStep(s, i)),
    })),
  });
}

export function logEoqSchemaStep(scene, flow, stepIndex, phase, turnData, step, context = {}) {
  if (!isEoqTraceEnabled(scene)) return;
  const playerSprites = context.playerSprites || scene?.playerSprites || {};
  emitTrace('STEP', {
    event: 'STEP',
    flow,
    phase,
    step_index: stepIndex,
    step: summarizeAnimationStep(step, stepIndex),
    turn: summarizeTurnData(turnData),
    clock: snapshotClockFromTurn(turnData, scene),
    players: snapshotPlayersFromSprites(scene, playerSprites),
  });
}
