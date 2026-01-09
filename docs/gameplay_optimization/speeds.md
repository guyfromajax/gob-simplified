# Page Download Speeds

This document tracks page load and API call speeds over time to measure performance improvements.

---

## FCC (Franchise Command Center)

**Date:** January 9, 2026

| Endpoint/Resource | Status | Type | Size | Time |
|-------------------|--------|------|------|------|
| play-next-game | 200 | fetch | 0.2 kB | 4.27 s |
| team-stats?franchise_id=69611225389f8bb0414d33db | 200 | fetch | 1.9 kB | 3.12 s |
| schedule?franchise_id=69611225389f8bb0414d33db | 200 | fetch | 12.3 kB | 2.92 s |
| state?franchise_id=69611225389f8bb0414d33db | 200 | fetch | 142 kB | 2.38 s |
| roster?franchise_id=69611225389f8bb0414d33db&team_name= | 200 | fetch | 7.7 kB | 2.05 s |
| roster?franchise_id=69611225389f8bb0414d33db&team_name=Bentley-Truman | 200 | fetch | 7.7 kB | 1.98 s |
| data?franchise_id=69611225389f8bb0414d33db | 200 | fetch | 0.6 kB | 1.81 s |
| team-data?franchise_id=69611225389f8bb0414d33db&team_id=68c98b09674d3f9b04546b31 | 200 | fetch | 14.1 kB | 1.61 s |
| team-data?franchise_id=69611225389f8bb0414d33db&team_id=68c98b09674d3f9b04546b31 | 200 | fetch | 14.1 kB | 1.54 s |
| gameplan?mode=franchise&franchise_id=69611225389f8bb0414d33db&team_id=68c98b09674d3f9b04546b31 | 200 | fetch | 0.3 kB | 1.43 s |
| recruits?franchise_id=69611225389f8bb0414d33db | 200 | fetch | 16.0 kB | 435 ms |
| leaders?franchise_id=69611225389f8bb0414d33db | 200 | fetch | 6.7 kB | 403 ms |
| standings?franchise_id=69611225389f8bb0414d33db | 200 | fetch | 1.1 kB | 348 ms |
| ImageBentley-Truman.png | 200 | png | 42.8 kB | 147 ms |
| teams | 200 | fetch | 0.7 kB | 67 ms |
| play-next-game | 200 | preflight | 0.0 kB | 54 ms |
| hive_keychain.js | 200 | script | 5.6 kB | 1 ms |
| JTUSjIg69CK48gW7PXoo9WlhyyTh89Y.woff2 | 200 | font | (memory cache) | 0 ms |
| UcC73FwrK3iLTeHuS_nVMrMxCp50SjIa1ZL7W0Q5nw.woff2 | 200 | font | (memory cache) | 0 ms |

### Notes
- Slowest calls: `play-next-game` (4.27s), `team-stats` (3.12s), `schedule` (2.92s)
- Largest payload: `state` endpoint (142 kB)
- Fastest calls: Font files (cached), `teams` endpoint (67ms), `standings` (348ms)

---

