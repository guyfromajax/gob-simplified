# Single Game Delete Automation (To Do)

**Goal:** Reduce DB bloat from single game and abandoned-game documents by running a periodic cleanup, without ever deleting games linked to existing franchises or tournaments.

---

## Context

- **Completed single games** are already deleted when the user clicks "Go To Locker Room" from the end-of-game popup (court) or from the Box Score page. Backend: `POST /api/games/delete-completed-single`.
- **Abandoned single games** (user leaves before the game ends) are not deleted in real time and remain in the `games` collection.
- Deleting on "abandon" in real time was discussed and rejected: it's hard to define reliably (closed tab, navigate away, etc.) and risks deleting games the user might still want.

---

## Approach: Weekly Orphan-Cleanup Script

Run a **scheduled job** (e.g. weekly) that deletes games that are safe to remove, using **conservative rules** so we never touch franchise or tournament games.

### Conservative delete rule

**Only consider for deletion games that have no `franchise_id` and no `tournament_id`.**

- Do **not** delete any game where `franchise_id` or `tournament_id` is set.
- That way, any game "linked" to a franchise or tournament is never in scope. We don't need to query the franchises/tournaments collections to decide; we simply never delete documents that have those fields set.

### Additional filters (recommended)

On that subset (no `franchise_id`, no `tournament_id`), apply one or more of:

- **Age:** e.g. only delete games older than 7 days (`created_at` or last updated). Gives a buffer if someone returns to an "abandoned" game.
- **Completion:** e.g. only delete games where `is_final` is true, so we don't remove in-progress games until they're clearly stale (or combine with age: in-progress older than 30 days).
- **Limit per run:** e.g. delete at most N documents per run to avoid long-running or heavy writes.

### Safety

- **Franchise games:** Must always be written with `franchise_id` set when created/updated. Before shipping the script, verify in the codebase that every franchise game sets `franchise_id`. As long as that's true, the conservative rule guarantees we never delete a game linked to an existing franchise.
- **Tournament games:** Same idea for `tournament_id` if we ever include tournament orphans in scope (optional; can limit to single-only for simplicity).

---

## Automation Options

The script logic can live in the backend (e.g. shared with an admin endpoint). Then automate in one of these ways:

1. **Scheduled HTTP endpoint**  
   - Add an admin-only route, e.g. `POST /api/admin/cleanup-orphan-games`, that runs the delete logic.  
   - Trigger it weekly via:
     - **External cron service** (e.g. cron-job.org, EasyCron) calling the URL with admin auth or a secret.
     - **GitHub Actions** workflow scheduled weekly, calling the production URL with a secret.
     - **Railway** (or host) cron/scheduler if available.

2. **Cron on a server**  
   - If you have a machine that can reach the DB, run a small script from cron (e.g. `0 2 * * 0` for 2am every Sunday). Script connects to MongoDB and runs the same delete logic.

3. **Platform scheduler**  
   - Use the host’s scheduler (e.g. Heroku Scheduler, AWS EventBridge + Lambda) to run the script or call the cleanup endpoint weekly.

**Recommendation:** Implement the logic once in the backend; expose it as an admin-only HTTP endpoint; use one of the options above to call that endpoint weekly. No manual steps after setup.

---

## Implementation checklist (when ready)

- [ ] Confirm in codebase that every franchise game has `franchise_id` set (and tournament games have `tournament_id` if needed).
- [ ] Implement delete logic: query games where `franchise_id` is null/absent and `tournament_id` is null/absent; apply age/completion/limit filters; delete in batches; log what was deleted.
- [ ] Expose as admin-only endpoint (e.g. `POST /api/admin/cleanup-orphan-games`) with auth or secret.
- [ ] Choose automation (external cron, GitHub Actions, or host scheduler) and set weekly schedule.
- [ ] Run once manually in staging/test, then enable in production.

---

## References

- Backend delete endpoint (completed single game, user-triggered): `POST /api/games/delete-completed-single` in `BackEnd/api/api.py`.
- Franchise delete (games removed when franchise is deleted): `db.games.delete_many({"franchise_id": ...})` in `BackEnd/api/franchise_routes.py` and admin routes.
