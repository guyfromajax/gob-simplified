import animationConfig from "../animation_config.js";

const BALL_PLAYER_ID = "ball";
const PASS_ACTION = "pass";
const RECEIVE_ACTION = "receive";
const SHOT_ACTIONS = new Set(["shoot", "shot"]);
const REBOUND_ACTIONS = new Set(["rebound"]);
const TURNOVER_ACTIONS = new Set(["turnover", "steal"]);

function toNumber(value) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (value == null) return null;
  const coerced = Number(value);
  return Number.isFinite(coerced) ? coerced : null;
}

const POSSESSION_TIMING = animationConfig?.possession ?? {};
const PASS_CONFIG = animationConfig?.pass ?? {};
const resolvedMsPerTick = toNumber(POSSESSION_TIMING.msPerTick);
const MS_PER_TICK = resolvedMsPerTick != null && resolvedMsPerTick > 0 ? resolvedMsPerTick : 1;
const resolvedMinFrameDuration = toNumber(POSSESSION_TIMING.minFrameDurationMs);
const MIN_FRAME_DURATION_MS =
  resolvedMinFrameDuration != null && resolvedMinFrameDuration >= 0
    ? resolvedMinFrameDuration
    : 120;
const MIN_PASS_DURATION_MS = (() => {
  const configValue = toNumber(POSSESSION_TIMING.minPassDurationMs);
  if (configValue != null && configValue >= 0) {
    return Math.max(MIN_FRAME_DURATION_MS, configValue);
  }
  const passConfigDuration = toNumber(PASS_CONFIG.duration);
  if (passConfigDuration != null && passConfigDuration >= 0) {
    return Math.max(MIN_FRAME_DURATION_MS, passConfigDuration);
  }
  return MIN_FRAME_DURATION_MS;
})();

function scaleDurationFromTicks(ticks, { minMs = MIN_FRAME_DURATION_MS } = {}) {
  const numeric = toNumber(ticks);
  if (numeric == null) return Math.max(0, minMs ?? 0);
  const scaled = numeric * MS_PER_TICK;
  if (!Number.isFinite(scaled)) return Math.max(0, minMs ?? 0);
  const sanitized = Math.max(0, scaled);
  return minMs != null ? Math.max(minMs, sanitized) : sanitized;
}

function compactObject(value) {
  if (!value || typeof value !== "object") return null;
  const output = {};
  for (const [key, val] of Object.entries(value)) {
    if (val == null) continue;
    output[key] = val;
  }
  return Object.keys(output).length ? output : null;
}

function buildPlayerMetaLookup(simData = {}) {
  const players = Array.isArray(simData.players) ? simData.players : [];
  const lookup = new Map();
  for (const player of players) {
    const id = player?.playerId ?? player?.player_id;
    if (!id) continue;
    lookup.set(id, {
      id,
      teamId: player?.team_id ?? player?.teamId ?? null,
      team: player?.team ?? null,
      position: player?.pos ?? player?.position ?? null,
      name: player?.name ?? null,
    });
  }
  return lookup;
}

function deriveDefenseTeamId(offenseTeamId, simData = {}, turn = {}) {
  const explicit = turn?.defense_team_id ?? turn?.defenseTeamId ?? null;
  if (explicit) return explicit;
  const home = simData?.home_team_id ?? simData?.homeTeamId ?? null;
  const away = simData?.away_team_id ?? simData?.awayTeamId ?? null;
  if (!offenseTeamId) return null;
  if (offenseTeamId === home) return away;
  if (offenseTeamId === away) return home;
  return null;
}

function normalizeCoords(step = {}) {
  const coords =
    step?.coords ??
    step?.grid ??
    step?.position ??
    (Array.isArray(step?.spot) ? { x: step.spot[0], y: step.spot[1] } : step?.spot) ??
    null;
  const x = typeof coords?.x === "number" ? coords.x : toNumber(coords?.[0]);
  const y = typeof coords?.y === "number" ? coords.y : toNumber(coords?.[1]);
  return {
    x: typeof x === "number" ? x : null,
    y: typeof y === "number" ? y : null,
  };
}

function normalizeAction(value) {
  if (typeof value !== "string") return null;
  return value.trim().toLowerCase();
}

function createTrack(anim = {}) {
  const playerId = anim?.playerId ?? anim?.player_id ?? null;
  if (!playerId) return null;

  const rawMovement = Array.isArray(anim?.movement) ? anim.movement : [];
  const hasBallArr = Array.isArray(anim?.hasBallAtStep) ? anim.hasBallAtStep : [];

  const steps = [];
  let lastTimestamp = null;
  let syntheticTime = 0;

  rawMovement.forEach((step, index) => {
    let timestamp = toNumber(step?.timestamp);
    if (timestamp == null) {
      const duration = toNumber(step?.duration);
      if (lastTimestamp != null && duration != null) {
        timestamp = lastTimestamp + duration;
      } else if (lastTimestamp != null) {
        syntheticTime = lastTimestamp + 1;
        timestamp = syntheticTime;
      } else {
        timestamp = syntheticTime;
      }
    }
    if (lastTimestamp != null && timestamp < lastTimestamp) {
      timestamp = lastTimestamp;
    }
    lastTimestamp = timestamp;
    syntheticTime = timestamp;

    const coords = normalizeCoords(step);
    const action = normalizeAction(step?.action ?? step?.type ?? step?.event);
    const hasBall = Boolean(hasBallArr[index] ?? step?.hasBall);

    steps.push({
      timestamp,
      coords,
      action,
      hasBall,
      raw: step,
      index,
    });
  });

  steps.sort((a, b) => {
    if (a.timestamp == null && b.timestamp == null) return a.index - b.index;
    if (a.timestamp == null) return 1;
    if (b.timestamp == null) return -1;
    if (a.timestamp === b.timestamp) return a.index - b.index;
    return a.timestamp - b.timestamp;
  });

  return {
    playerId,
    steps,
    raw: anim,
    hasBallAtStep: hasBallArr,
    teamId: anim?.teamId ?? anim?.team_id ?? null,
    position: anim?.position ?? null,
  };
}

function buildPassKey(timestamp, fromId, toId) {
  if (timestamp == null || !fromId) return null;
  return `${timestamp}:${fromId}:${toId ?? "*"}`;
}

function normalizeExplicitPasses(passes = [], defaultDuration = 250) {
  if (!Array.isArray(passes)) return [];
  const results = [];
  const defaultDurationTicks = Math.max(0, toNumber(defaultDuration) ?? 0);
  for (const entry of passes) {
    const timestamp = toNumber(entry?.timestamp ?? entry?.start ?? entry?.startTimestamp);
    const fromId = entry?.fromId ?? entry?.from_id ?? entry?.source ?? null;
    const toId = entry?.toId ?? entry?.to_id ?? entry?.target ?? null;
    const explicitDuration = toNumber(entry?.duration);
    let completionTimestamp = toNumber(
      entry?.completionTimestamp ?? entry?.endTimestamp ?? entry?.completeTimestamp
    );

    let resolvedDurationTicks = null;
    if (explicitDuration != null && explicitDuration >= 0) {
      resolvedDurationTicks = explicitDuration;
      if (completionTimestamp == null && timestamp != null) {
        completionTimestamp = timestamp + resolvedDurationTicks;
      }
    } else if (timestamp != null && completionTimestamp != null) {
      resolvedDurationTicks = Math.max(0, completionTimestamp - timestamp);
    } else {
      resolvedDurationTicks = defaultDurationTicks;
      if (timestamp != null && completionTimestamp == null) {
        completionTimestamp = timestamp + resolvedDurationTicks;
      }
    }

    const durationMs = scaleDurationFromTicks(resolvedDurationTicks, {
      minMs: MIN_PASS_DURATION_MS,
    });

    results.push({
      timestamp,
      completionTimestamp,
      duration: durationMs,
      fromId,
      toId,
      source: "explicit",
      raw: entry,
    });
  }
  return results;
}

function inferPassesFromTracks(tracks = [], knownKeys = new Set(), defaultDuration = 250) {
  const passes = [];
  const receiveLookup = new Map();
  const defaultDurationTicks = Math.max(0, toNumber(defaultDuration) ?? 0);

  for (const track of tracks) {
    if (track.playerId === BALL_PLAYER_ID) continue;
    for (const step of track.steps) {
      if (step.timestamp == null) continue;
      if (normalizeAction(step.action) === RECEIVE_ACTION) {
        if (!receiveLookup.has(step.timestamp)) receiveLookup.set(step.timestamp, []);
        receiveLookup.get(step.timestamp).push({ playerId: track.playerId, step });
      }
    }
  }

  for (const track of tracks) {
    if (track.playerId === BALL_PLAYER_ID) continue;
    for (const step of track.steps) {
      if (step.timestamp == null) continue;
      if (normalizeAction(step.action) !== PASS_ACTION) continue;

      const receivers = receiveLookup.get(step.timestamp) ?? [];
      let receiver = null;
      for (const candidate of receivers) {
        if (candidate.used) continue;
        receiver = candidate;
        candidate.used = true;
        break;
      }

      const key = buildPassKey(step.timestamp, track.playerId, receiver?.playerId ?? null);
      if (key && knownKeys.has(key)) continue;

      let completionTimestamp = null;
      let durationTicks = defaultDurationTicks;
      if (receiver?.step?.timestamp != null && receiver.step.timestamp > step.timestamp) {
        completionTimestamp = receiver.step.timestamp;
        durationTicks = Math.max(0, receiver.step.timestamp - step.timestamp);
      } else if (receiver?.step?.raw) {
        const raw = receiver.step.raw;
        const inferredEnd = toNumber(raw?.completionTimestamp ?? raw?.endTimestamp ?? raw?.timestampComplete);
        if (inferredEnd != null && inferredEnd >= step.timestamp) {
          completionTimestamp = inferredEnd;
          durationTicks = Math.max(0, inferredEnd - step.timestamp);
        }
      }

      if (completionTimestamp == null && durationTicks != null && step.timestamp != null) {
        completionTimestamp = step.timestamp + durationTicks;
      }

      const durationMs = scaleDurationFromTicks(durationTicks, {
        minMs: MIN_PASS_DURATION_MS,
      });

      passes.push({
        timestamp: step.timestamp,
        completionTimestamp,
        duration: durationMs,
        fromId: track.playerId,
        toId: receiver?.playerId ?? null,
        source: "inferred",
      });
    }
  }

  return passes;
}

function getStepForTimestamp(track, targetTimestamp) {
  if (!track?.steps?.length) return null;
  let candidate = null;
  for (const step of track.steps) {
    if (step.timestamp == null) continue;
    if (step.timestamp === targetTimestamp) return step;
    if (step.timestamp < targetTimestamp) {
      if (!candidate || step.timestamp > candidate.timestamp) {
        candidate = step;
      }
    } else if (!candidate) {
      candidate = step;
      break;
    } else {
      break;
    }
  }
  if (!candidate) {
    candidate = track.steps[0];
  }
  return candidate;
}

function gatherTimestamps(tracks = [], passes = []) {
  const timestamps = new Set();
  for (const track of tracks) {
    for (const step of track.steps) {
      if (step.timestamp == null) continue;
      timestamps.add(step.timestamp);
    }
  }
  for (const pass of passes) {
    if (pass.timestamp != null) timestamps.add(pass.timestamp);
    if (pass.completionTimestamp != null) timestamps.add(pass.completionTimestamp);
  }
  return Array.from(timestamps).sort((a, b) => a - b);
}

function buildFrames({ tracks, timestamps, passes, defaultFrameDuration = 0 }) {
  const frames = [];
  const passByTimestamp = new Map();
  for (const pass of passes) {
    if (pass.timestamp == null) continue;
    if (!passByTimestamp.has(pass.timestamp)) passByTimestamp.set(pass.timestamp, []);
    passByTimestamp.get(pass.timestamp).push(pass);
  }

  for (let i = 0; i < timestamps.length; i++) {
    const timestamp = timestamps[i];
    const nextTimestamp = timestamps[i + 1];
    const framePlayers = {};
    const actions = [];

    for (const track of tracks) {
      const step = getStepForTimestamp(track, timestamp);
      if (!step) continue;
      const { coords, action, hasBall } = step;
      if (coords?.x == null && coords?.y == null && !action) continue;

      const payload = {
        x: coords?.x ?? null,
        y: coords?.y ?? null,
        action: action ?? null,
        hasBall: hasBall || false,
        teamId: track.teamId ?? null,
        position: track.position ?? null,
        index: step.index,
      };

      if (action) actions.push({ playerId: track.playerId, action });
      framePlayers[track.playerId] = payload;
    }

    const rawDurationTicks =
      nextTimestamp != null && Number.isFinite(nextTimestamp)
        ? Math.max(0, nextTimestamp - timestamp)
        : defaultFrameDuration;

    const frame = {
      timestamp,
      duration: scaleDurationFromTicks(rawDurationTicks, {
        minMs: MIN_FRAME_DURATION_MS,
      }),
      players: framePlayers,
    };

    const passEvents = passByTimestamp.get(timestamp) || [];
    if (passEvents.length) {
      frame.passes = passEvents.map(evt => ({ ...evt }));
    }

    if (actions.length) {
      frame.actions = actions;
    }

    frames.push(frame);
  }

  return frames;
}

function findFirstActionTimestamp(tracks = [], actionSet = new Set()) {
  let earliest = null;
  for (const track of tracks) {
    for (const step of track.steps) {
      if (!step.action || step.timestamp == null) continue;
      if (!actionSet.has(step.action)) continue;
      if (earliest == null || step.timestamp < earliest) {
        earliest = step.timestamp;
      }
    }
  }
  return earliest;
}

function extractShotMetadata({ turn, tracks, offenseTeamId, fastBreak }) {
  const shooterId = turn?.shooter_id ?? turn?.shooterId ?? turn?.shot?.shooterId ?? null;
  const assistId = turn?.assist_id ?? turn?.assistId ?? turn?.shot?.assistId ?? null;
  const points = toNumber(turn?.points ?? turn?.points_scored ?? turn?.pointsScored);
  const outcome = turn?.shot_result ?? turn?.result ?? turn?.shotOutcome ?? null;
  const resultType = turn?.result_type ?? turn?.resultType ?? null;
  const playType = turn?.play_type ?? turn?.playType ?? null;
  const location = turn?.shot_location ?? turn?.shotLocation ?? null;
  const shotClock = toNumber(turn?.shot_clock ?? turn?.shotClock);
  const gameClock = turn?.clock ?? null;
  const timestamp = findFirstActionTimestamp(tracks, SHOT_ACTIONS) ??
    toNumber(turn?.shot_timestamp ?? turn?.shotTimestamp);

  return compactObject({
    timestamp,
    shooterId,
    assistId,
    points,
    outcome,
    resultType,
    playType,
    location,
    shotClock,
    gameClock,
    teamId: offenseTeamId ?? null,
    fastBreak: fastBreak ? true : undefined,
    text: turn?.text ?? null,
  });
}

function extractReboundMetadata({ turn, tracks, offenseTeamId, playerLookup }) {
  const rebounderId =
    turn?.rebounder_id ??
    turn?.rebounderId ??
    turn?.rebound?.rebounderId ??
    null;
  const timestamp = findFirstActionTimestamp(tracks, REBOUND_ACTIONS) ??
    toNumber(turn?.rebound_timestamp ?? turn?.reboundTimestamp);
  const teamId =
    turn?.rebound_team_id ??
    turn?.reboundTeamId ??
    (rebounderId && playerLookup?.get(rebounderId)?.teamId) ??
    null;
  const outcome = turn?.rebound_outcome ?? turn?.reboundOutcome ?? null;
  const offensive = teamId != null && offenseTeamId != null ? teamId === offenseTeamId : undefined;

  return compactObject({
    timestamp,
    rebounderId,
    teamId,
    outcome,
    offensive,
  });
}

function extractTurnoverMetadata({ turn, tracks }) {
  const isTurnover =
    (turn?.result_type ?? turn?.resultType ?? "").toUpperCase() === "TURNOVER" ||
    (turn?.turnover === true);
  if (!isTurnover) return null;
  const timestamp = findFirstActionTimestamp(tracks, TURNOVER_ACTIONS) ??
    toNumber(turn?.turnover_timestamp ?? turn?.turnoverTimestamp);
  const playerId = turn?.turnover_player_id ?? turn?.turnoverPlayerId ?? turn?.victim_id ?? turn?.victimId ?? null;
  const cause = turn?.turnover_type ?? turn?.turnoverType ?? turn?.turnoverCause ?? null;
  const forcedBy = turn?.stealer_id ?? turn?.stealerId ?? null;
  return compactObject({ timestamp, playerId, cause, forcedBy });
}

function dedupePasses(passes = []) {
  const seen = new Set();
  const output = [];
  for (const pass of passes) {
    const key = buildPassKey(pass.timestamp, pass.fromId, pass.toId);
    if (key && seen.has(key)) continue;
    if (key) seen.add(key);
    output.push(pass);
  }
  return output;
}

export function normalizeTurn(turn = {}, simData = {}, options = {}) {
  const playerLookup = buildPlayerMetaLookup(simData);
  const offenseTeamId =
    options?.offenseTeamId ??
    turn?.possession_team_id ??
    turn?.possessionTeamId ??
    null;
  const defenseTeamId =
    options?.defenseTeamId ??
    deriveDefenseTeamId(offenseTeamId, simData, turn);
  const fastBreak = Boolean(
    options?.fastBreak ??
    turn?.fast_break ??
    turn?.fastBreak ??
    ((turn?.result_type ?? turn?.resultType) === "FAST_BREAK")
  );
  const secondaryBreak = Boolean(options?.secondaryBreak ?? turn?.secondary_break ?? turn?.secondaryBreak);

  const animations = Array.isArray(turn?.animations) ? turn.animations : [];
  const tracks = [];
  const setupPlayers = {};
  const playerOrder = [];
  let ballOwnerId = null;
  let ballStartCoords = null;

  for (const anim of animations) {
    const track = createTrack(anim);
    if (!track) continue;

    const meta = playerLookup.get(track.playerId) ?? {};
    if (!track.teamId && meta.teamId) {
      track.teamId = meta.teamId;
    }
    if (!track.position && meta.position) {
      track.position = meta.position;
    }

    if (track.playerId === BALL_PLAYER_ID) {
      const firstStep = track.steps.find(step => step.coords?.x != null && step.coords?.y != null);
      if (firstStep) {
        ballStartCoords = { x: firstStep.coords.x, y: firstStep.coords.y };
      }
      tracks.push(track);
      continue;
    }

    const firstStep = track.steps.find(step => step.coords?.x != null && step.coords?.y != null) ?? track.steps[0];
    if (firstStep) {
      setupPlayers[track.playerId] = {
        x: firstStep.coords?.x ?? null,
        y: firstStep.coords?.y ?? null,
        hasBall: Boolean(track.hasBallAtStep?.[firstStep.index] ?? firstStep.hasBall ?? false),
        teamId: track.teamId ?? meta.teamId ?? null,
        team: meta.team ?? null,
        position: track.position ?? meta.position ?? null,
        name: meta.name ?? null,
        action: firstStep.action ?? null,
      };
      if (!playerOrder.includes(track.playerId)) playerOrder.push(track.playerId);
    }

    if (ballOwnerId == null && Array.isArray(track.hasBallAtStep) && track.hasBallAtStep[0]) {
      ballOwnerId = track.playerId;
      if (!ballStartCoords && firstStep?.coords) {
        ballStartCoords = { x: firstStep.coords.x, y: firstStep.coords.y };
      }
    }

    tracks.push(track);
  }

  if (ballOwnerId == null) {
    const firstWithBall = animations.find(anim => Array.isArray(anim?.hasBallAtStep) && anim.hasBallAtStep[0]);
    if (firstWithBall) {
      ballOwnerId = firstWithBall.playerId ?? firstWithBall.player_id ?? null;
    }
  }

  const explicitPasses = normalizeExplicitPasses(turn?.passes, options?.defaultPassDuration ?? 250);
  const passKeys = new Set(explicitPasses.map(pass => buildPassKey(pass.timestamp, pass.fromId, pass.toId)).filter(Boolean));
  const inferredPasses = inferPassesFromTracks(tracks, passKeys, options?.defaultPassDuration ?? 250);
  const passes = dedupePasses([...explicitPasses, ...inferredPasses]).sort((a, b) => {
    if (a.timestamp == null && b.timestamp == null) return 0;
    if (a.timestamp == null) return 1;
    if (b.timestamp == null) return -1;
    if (a.timestamp !== b.timestamp) return a.timestamp - b.timestamp;
    const fromA = a.fromId ?? "";
    const fromB = b.fromId ?? "";
    if (fromA < fromB) return -1;
    if (fromA > fromB) return 1;
    return 0;
  });

  const timestamps = gatherTimestamps(tracks, passes);
  const frames = buildFrames({
    tracks,
    timestamps,
    passes,
    defaultFrameDuration: options?.defaultFrameDuration ?? 0,
  });

  const startTimestamp = timestamps.length ? timestamps[0] : null;
  const endTimestamp = timestamps.length ? timestamps[timestamps.length - 1] : null;

  const shotMeta = extractShotMetadata({ turn, tracks, offenseTeamId, fastBreak });
  const reboundMeta = extractReboundMetadata({ turn, tracks, offenseTeamId, playerLookup });
  const turnoverMeta = extractTurnoverMetadata({ turn, tracks });

  const terminal = {
    shot: shotMeta ?? null,
    rebound: reboundMeta ?? null,
    turnover: turnoverMeta ?? null,
  };

  const setup = {
    offenseTeamId,
    defenseTeamId,
    ball: compactObject({ ownerId: ballOwnerId, coords: ballStartCoords }),
    players: setupPlayers,
    order: playerOrder,
  };

  const context = compactObject({
    turnId: turn?.id ?? turn?.turn_id ?? null,
    possessionId: turn?.possession_id ?? turn?.possessionId ?? null,
    possessionIndex: turn?.possession_index ?? turn?.possessionIndex ?? null,
    offenseTeamId,
    defenseTeamId,
    homeTeamId: simData?.home_team_id ?? simData?.homeTeamId ?? null,
    awayTeamId: simData?.away_team_id ?? simData?.awayTeamId ?? null,
    startingOffenseTeamId: offenseTeamId, // ✅ CONSOLIDATED: Same as offenseTeamId (possession_team_id represents team DURING the turn)
    fastBreak: fastBreak ? true : undefined,
    secondaryBreak: secondaryBreak ? true : undefined,
    resultType: turn?.result_type ?? turn?.resultType ?? null,
    text: turn?.text ?? null,
    score: turn?.score ?? null,
    clock: turn?.clock ?? null,
    quarter: turn?.quarter ?? turn?.period ?? null,
    periodLabel: turn?.period_label ?? turn?.periodLabel ?? null,
    shotClock: toNumber(turn?.shot_clock ?? turn?.shotClock),
    timeElapsed: toNumber(turn?.time_elapsed ?? turn?.timeElapsed),
    startTimestamp,
    endTimestamp,
  }) || {};

  return {
    context,
    setup,
    timeline: {
      startTimestamp,
      endTimestamp,
      frames,
      passes,
    },
    terminal,
  };
}

export default normalizeTurn;
