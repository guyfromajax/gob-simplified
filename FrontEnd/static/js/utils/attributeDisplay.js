/**
 * Convert attribute value (0-120+) to display scale (0-12)
 * Examples: 89 → 8, 95 → 9, 105 → 10, 118 → 11
 */
export function formatAttribute(value) {
  if (value === null || value === undefined || isNaN(value)) {
    return '--';
  }
  return Math.floor(value / 10);
}

/**
 * Format NG attribute with 2 decimal places (unchanged)
 */
export function formatNG(value) {
  if (value === null || value === undefined || isNaN(value)) {
    return '--';
  }
  return value.toFixed(2);
}

