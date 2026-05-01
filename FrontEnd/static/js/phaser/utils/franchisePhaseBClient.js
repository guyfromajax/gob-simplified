/**
 * Single-flight POST /franchise/complete-week/phase-b for a given franchise week.
 * Started when the franchise EOG popup appears; PGPC reuses the same Promise so
 * CPU sims are not kicked off twice in the same tab.
 */

const phaseBPromiseByKey = new Map();

function franchisePhaseBKey(pending) {
  if (!pending || pending.franchise_id == null || pending.week == null) return '';
  return `${String(pending.franchise_id)}:${String(pending.week)}`;
}

/**
 * @param {{ franchise_id: string, week: number }} pending
 * @returns {Promise<Response>}
 */
export function getOrStartFranchisePhaseB(pending) {
  const key = franchisePhaseBKey(pending);
  if (!key) {
    return Promise.reject(new Error('[franchise phase-b] invalid pending payload'));
  }
  if (typeof API_CONFIG === 'undefined' || !API_CONFIG.buildUrl) {
    return Promise.reject(new Error('[franchise phase-b] API_CONFIG unavailable'));
  }

  const existing = phaseBPromiseByKey.get(key);
  if (existing) return existing;

  const headers = Object.assign(
    { 'Content-Type': 'application/json' },
    typeof API_CONFIG.getAuthHeaders === 'function' ? API_CONFIG.getAuthHeaders() : {}
  );

  const promise = fetch(API_CONFIG.buildUrl('/franchise/complete-week/phase-b'), {
    method: 'POST',
    headers,
    body: JSON.stringify({
      franchise_id: pending.franchise_id,
      week: pending.week,
    }),
  });

  phaseBPromiseByKey.set(key, promise);
  return promise;
}
