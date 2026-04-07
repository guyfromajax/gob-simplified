export const CLAMP_BOUNDS = Object.freeze({
  minX: 5,
  maxX: 95,
  minY: 2,
  maxY: 49,
});

const EXEMPT_RESULT_TYPES = new Set([
  "SIDE_INBOUND",
  "BASELINE_INBOUND",
  "TIMEOUT",
]);

function clampValue(value, min, max) {
  if (!Number.isFinite(value)) return value;
  return Math.min(max, Math.max(min, value));
}

export function isClampExempt(turnData, context = {}) {
  if (context?.forceExempt === true) return true;
  const resultType = context?.resultType ?? turnData?.result_type ?? null;
  return EXEMPT_RESULT_TYPES.has(resultType);
}

export function clampGridCoords(coords, turnData, context = {}) {
  if (!coords || typeof coords !== "object") return coords;
  if (isClampExempt(turnData, context)) return coords;

  return {
    ...coords,
    x: clampValue(coords.x, CLAMP_BOUNDS.minX, CLAMP_BOUNDS.maxX),
    y: clampValue(coords.y, CLAMP_BOUNDS.minY, CLAMP_BOUNDS.maxY),
  };
}
