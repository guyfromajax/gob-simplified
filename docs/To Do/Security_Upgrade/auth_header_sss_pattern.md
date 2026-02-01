# Auth Header Pattern: SS&S Approach

**Context:** After 5.2 (User Data Exposure Prevention), protected endpoints require `Authorization: Bearer` on requests. The first fix was siloed; a holistic pattern is needed.

---

## Lesson: Avoid Siloed Fixes

- **Bad:** Fixing only the page that 401’d (e.g. franchise-select) without checking the rest of the app.
- **Better:** Audit all protected endpoints and all fetches, then apply one shared pattern everywhere.

---

## Current Pattern (Alpha)

- `API_CONFIG.getAuthHeaders()` — single source for auth headers.
- Each fetch manually adds `headers: API_CONFIG.getAuthHeaders()` or merges it with `Content-Type`.
- **Risk:** New fetches can forget auth; no enforcement.

---

## Stronger SS&S Options

1. **`apiFetch(url, options)`** — wrapper that always merges auth headers into every request. If all API calls use it, auth is automatic.
2. **Audit checklist** — map protected endpoints → frontend files that call them; verify each uses the shared pattern.
3. **Review rule** — new fetches to franchise/tournament/game endpoints must use `getAuthHeaders()` or `apiFetch`.

---

## Related

- `FrontEnd/static/js/config/api-config.js` — `getAuthHeaders()`
- `docs/docs_1_systems/SECURITY_BASELINE.md` — protected endpoint list
