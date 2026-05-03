/**
 * Single-flight POST /franchise/complete-week/start-cpu-sims for a franchise week.
 * Fired when the user begins Q1 (Play Quarter or Sim Quarter) so CPU games can run in parallel.
 */

const startCpuPromiseByKey = new Map();

function franchiseStartCpuKey(payload) {
  if (!payload || payload.franchise_id == null || payload.week == null) return '';
  return `${String(payload.franchise_id)}:${String(payload.week)}`;
}

/**
 * @param {{ franchise_id: string, week: number }} payload
 * @returns {Promise<Response>}
 */
export function getOrStartFranchiseStartCpuSims(payload) {
  const key = franchiseStartCpuKey(payload);
  if (!key) {
    return Promise.reject(new Error('[franchise start-cpu-sims] invalid payload'));
  }
  const API = typeof window !== 'undefined' ? window.API_CONFIG : undefined;
  if (!API || typeof API.buildUrl !== 'function') {
    return Promise.reject(new Error('[franchise start-cpu-sims] API_CONFIG unavailable'));
  }

  const existing = startCpuPromiseByKey.get(key);
  if (existing) return existing;

  const headers = Object.assign(
    { 'Content-Type': 'application/json' },
    typeof API.getAuthHeaders === 'function' ? API.getAuthHeaders() : {}
  );

  const promise = fetch(API.buildUrl('/franchise/complete-week/start-cpu-sims'), {
    method: 'POST',
    headers,
    body: JSON.stringify({
      franchise_id: payload.franchise_id,
      week: payload.week,
    }),
  });

  startCpuPromiseByKey.set(key, promise);
  return promise;
}
