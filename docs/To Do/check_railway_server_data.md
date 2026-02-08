# Checking data on the Railway server (for slow performance)

Railway does **not** persist the app’s filesystem by default. Restarts wipe any written files. So “data on the Railway server” means:

1. **In-memory state** (lost on restart)  
2. **Persistent data** only if you added a **Volume**  
3. **Database** (MongoDB) – your real persistent data lives there (e.g. Atlas)

---

## 1. In-memory state (e.g. `ongoing_games`)

- **What:** The app keeps an in-memory cache of active games (`ongoing_games` in `BackEnd/api/api.py`). It’s not written to disk.
- **How to check:** Call the debug endpoint (after deploy):
  ```bash
  curl -s https://YOUR-RAILWAY-URL/debug/server-state
  ```
  Example response:
  ```json
  {
    "ongoing_games_count": 2,
    "config_overrides_path": "/app/config_overrides.json",
    "config_overrides_file_exists": false
  }
  ```
- **Railway metrics:** In the Railway project → your service → **Metrics**: check **Memory** over time. If it grows and never drops, in-memory caches may be growing (e.g. many games never evicted).

---

## 2. Disk / files on Railway

- **Default:** No volume → filesystem is **ephemeral**. Anything written (e.g. `config_overrides.json`) is lost on deploy or restart.
- **If you added a Volume:**  
  - Railway project → your service → **Volumes** → see mounted path.  
  - To see what’s on it you have to run a command inside the container (e.g. Railway **Shell** or a one-off run that `ls`’s the mount path). Railway doesn’t provide a file browser for volumes.
- **Config overrides:** The app writes to `CONFIG_OVERRIDES_PATH` (default `config_overrides.json`). On Railway without a volume that file disappears on restart.

---

## 3. Persistent data (MongoDB)

- **Where:** Your real data is in **MongoDB** (e.g. Atlas, or a Railway MongoDB plugin), not in “Railway server” disk/memory.
- **How to check:**  
  - **Atlas:** Cluster → **Metrics** (Connections, Ops, etc.) and **Storage** / **Database** size.  
  - **Railway MongoDB:** Use the same metrics/storage views if your DB is there.  
- Use the DB to inspect collection sizes, document counts, and slow queries; that’s separate from “data on the Railway server.”

---

## Summary

| What              | Where to check                                                                 |
|-------------------|---------------------------------------------------------------------------------|
| In-memory caches  | `GET /debug/server-state` on your Railway URL; Railway Metrics → Memory        |
| Disk/files        | Ephemeral unless you added a Volume; then inspect via Shell/one-off in container |
| Persistent data   | MongoDB (Atlas or Railway) – metrics, storage, and collection stats            |

If you see `ongoing_games_count` staying high and memory climbing, consider evicting finished games from the cache or adding a TTL. See `docs/docs_1_systems/03_Data_Persistence/Data_Persistence_System.md` for cache behaviour.
