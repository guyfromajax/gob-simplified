/**
 * Single-flight POST /franchise/complete-week/start-cpu-sims for a franchise week.
 * Fired on first franchise play/sim for that week (any quarter) so CPU games can overlap user time.
 */

const startCpuPromiseByKey = new Map();
/** Keys that finished OK or 409 (phase A already ran) — do not POST again this session. */
const startCpuCompletedKeys = new Set();

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

  if (startCpuCompletedKeys.has(key)) {
    if (typeof console !== 'undefined' && console.info) {
      console.info('[START-CPU-SIMS][client] skip — already ran this session', { key });
    }
    return Promise.resolve(
      new Response(null, { status: 200, statusText: 'AlreadyCompleted' })
    );
  }

  const existing = startCpuPromiseByKey.get(key);
  if (existing) {
    if (typeof console !== 'undefined' && console.info) {
      console.info('[START-CPU-SIMS][client] reuse in-flight POST', { key });
    }
    return existing;
  }

  const headers = Object.assign(
    { 'Content-Type': 'application/json' },
    typeof API.getAuthHeaders === 'function' ? API.getAuthHeaders() : {}
  );

  const wallMs = typeof performance !== 'undefined' ? performance.now() : Date.now();
  if (typeof console !== 'undefined' && console.info) {
    console.info('[START-CPU-SIMS][client] POST /franchise/complete-week/start-cpu-sims', {
      key,
      t: Date.now(),
    });
  }

  const promise = fetch(API.buildUrl('/franchise/complete-week/start-cpu-sims'), {
    method: 'POST',
    headers,
    body: JSON.stringify({
      franchise_id: payload.franchise_id,
      week: payload.week,
    }),
  })
    .then((res) => {
      const elapsedMs =
        (typeof performance !== 'undefined' ? performance.now() : Date.now()) - wallMs;
      if (typeof console !== 'undefined' && console.info) {
        console.info('[START-CPU-SIMS][client] response', {
          key,
          status: res.status,
          ok: res.ok,
          elapsedMs: Math.round(elapsedMs),
        });
      }
      if (res.ok || res.status === 409) {
        startCpuCompletedKeys.add(key);
      }
      startCpuPromiseByKey.delete(key);
      return res;
    })
    .catch((err) => {
      startCpuPromiseByKey.delete(key);
      throw err;
    });

  startCpuPromiseByKey.set(key, promise);
  return promise;
}
