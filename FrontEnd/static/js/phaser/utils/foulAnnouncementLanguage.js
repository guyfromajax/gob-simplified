const LANE_LOCATIONS = new Set([
  "upper lowpost",
  "lower lowpost",
  "midpost",
  "highpost",
  "basketspot",
  "midlane",
  "toplane",
]);

const OFFENSIVE_WEIGHTS = {
  nonLane: [
    { text: "Push Off!", weight: 30 },
    { text: "Illegal Screen!", weight: 20 },
    { text: "Arm Extension!", weight: 15 },
    { text: "Hooking!", weight: 5 },
    { text: "Illegal Use Of Hands!", weight: 10 },
    { text: "Elbowing!", weight: 20 },
    { text: "Illegal Post Up!", weight: 0 },
  ],
  lane: [
    { text: "Push Off!", weight: 10 },
    { text: "Illegal Screen!", weight: 10 },
    { text: "Arm Extension!", weight: 10 },
    { text: "Hooking!", weight: 5 },
    { text: "Illegal Use Of Hands!", weight: 5 },
    { text: "Elbowing!", weight: 20 },
    { text: "Illegal Post Up!", weight: 40 },
  ],
};

const DEFENSIVE_WEIGHTS = {
  nonLane: [
    { text: "Blocking Foul!", weight: 25 },
    { text: "Hand-Checking!", weight: 25 },
    { text: "Illegal Contact!", weight: 10 },
    { text: "Holding!", weight: 15 },
    { text: "Arm Bar!", weight: 15 },
    { text: "Pushing!", weight: 10 },
    { text: "Illegal Post Defense!", weight: 0 },
  ],
  lane: [
    { text: "Blocking Foul!", weight: 5 },
    { text: "Hand-Checking!", weight: 0 },
    { text: "Illegal Contact!", weight: 10 },
    { text: "Holding!", weight: 20 },
    { text: "Arm Bar!", weight: 10 },
    { text: "Pushing!", weight: 30 },
    { text: "Illegal Post Defense!", weight: 25 },
  ],
};

function normalizeText(value) {
  return String(value || "").trim().toLowerCase();
}

function weightedPick(weighted, randomFn = Math.random) {
  const total = weighted.reduce((sum, row) => sum + Math.max(0, Number(row.weight) || 0), 0);
  if (!Number.isFinite(total) || total <= 0) return null;
  let cursor = randomFn() * total;
  for (const row of weighted) {
    cursor -= Math.max(0, Number(row.weight) || 0);
    if (cursor < 0) return row.text;
  }
  return weighted[weighted.length - 1]?.text || null;
}

export function isLaneFoulContext(turnData) {
  const candidates = [
    turnData?.location,
    turnData?.spot,
    turnData?.ball_spot,
    turnData?.foul_location,
    turnData?.foul_spot,
  ].map(normalizeText);
  if (candidates.some((value) => LANE_LOCATIONS.has(value))) {
    return true;
  }
  const text = normalizeText(turnData?.text);
  if (!text) return false;
  for (const lane of LANE_LOCATIONS) {
    if (text.includes(lane)) return true;
  }
  return false;
}

export function pickOffensiveFoulAnnouncementText(turnData, randomFn = Math.random) {
  const weights = isLaneFoulContext(turnData) ? OFFENSIVE_WEIGHTS.lane : OFFENSIVE_WEIGHTS.nonLane;
  return weightedPick(weights, randomFn) || "OFFENSIVE FOUL!";
}

export function pickDefensiveFoulAnnouncementText(turnData, randomFn = Math.random) {
  const weights = isLaneFoulContext(turnData) ? DEFENSIVE_WEIGHTS.lane : DEFENSIVE_WEIGHTS.nonLane;
  return weightedPick(weights, randomFn) || "DEFENSIVE FOUL!";
}
