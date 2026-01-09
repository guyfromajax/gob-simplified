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

**Date:** January 9, 2026 (Second measurement)

| Endpoint/Resource | Status | Type | Size | Time |
|-------------------|--------|------|------|------|
| play-next-game | 200 | fetch | 0.2 kB | 3.58 s |
| team-stats?franchise_id=696118726bba2a35261db177 | 200 | fetch | 1.9 kB | 3.11 s |
| schedule?franchise_id=696118726bba2a35261db177 | 200 | fetch | 12.3 kB | 2.57 s |
| roster?franchise_id=696118726bba2a35261db177&team_name= | 200 | fetch | 7.7 kB | 1.95 s |
| roster?franchise_id=696118726bba2a35261db177&team_name=Ocean%20City | 200 | fetch | 7.6 kB | 1.86 s |
| state?franchise_id=696118726bba2a35261db177 | 200 | fetch | 142 kB | 1.74 s |
| data?franchise_id=696118726bba2a35261db177 | 200 | fetch | 0.4 kB | 1.53 s |
| gameplan?mode=franchise&franchise_id=696118726bba2a35261db177&team_id=68c98b09674d3f9b04546b31 | 200 | fetch | 0.3 kB | 1.51 s |
| team-data?franchise_id=696118726bba2a35261db177&team_id=68c98b09674d3f9b04546b31 | 200 | fetch | 14.1 kB | 1.47 s |
| team-data?franchise_id=696118726bba2a35261db177&team_id=68c98b09674d3f9b04546b31 | 200 | fetch | 14.0 kB | 1.42 s |
| franchise-command-center.js | 200 | script | 18.8 kB | 239 ms |
| leaders?franchise_id=696118726bba2a35261db177 | 200 | fetch | 6.7 kB | 227 ms |
| recruits?franchise_id=696118726bba2a35261db177 | 200 | fetch | 16.0 kB | 223 ms |
| franchise-command-center.html | 200 | document | 2.4 kB | 219 ms |
| tournament.css | 200 | stylesheet | 2.4 kB | 187 ms |
| common.js | 200 | script | 0.6 kB | 186 ms |
| scouting-report.css | 200 | stylesheet | 0.7 kB | 186 ms |
| attributeTooltips.js | 200 | script | 2.0 kB | 186 ms |
| teamStatsTable.js | 200 | script | 2.1 kB | 153 ms |
| command-center-team-styles.css | 200 | stylesheet | 1.5 kB | 148 ms |
| franchise-command-center.css | 200 | stylesheet | 0.6 kB | 147 ms |
| ImageOcean%20City.png | 200 | png | 41.8 kB | 119 ms |
| standings?franchise_id=696118726bba2a35261db177 | 200 | fetch | 1.1 kB | 104 ms |
| teams | 200 | fetch | 0.7 kB | 64 ms |
| api-config.js | 200 | script | 1.4 kB | 44 ms |
| play-next-game | 200 | preflight | 0.0 kB | 43 ms |
| css2?family=Bebas+Neue&family=Inter:wght@400;700&display=swap | 200 | stylesheet | 0.8 kB | 42 ms |
| UcC73FwrK3iLTeHuS_nVMrMxCp50SjIa1ZL7W0Q5nw.woff2 | 200 | font | 48.5 kB | 36 ms |
| JTUSjIg69CK48gW7PXoo9WlhyyTh89Y.woff2 | 200 | font | 8.6 kB | 17 ms |
| hive_keychain.js | 200 | script | 5.6 kB | 1 ms |

### Notes
- Slowest calls: `play-next-game` (3.58s), `team-stats` (3.11s), `schedule` (2.57s)
- Largest payload: `state` endpoint (142 kB)
- Fastest calls: `hive_keychain.js` (1ms), fonts (17-36ms), `teams` endpoint (64ms), `standings` (104ms)
- **Improvement:** Overall speeds slightly faster than first measurement (play-next-game: 4.27s → 3.58s, schedule: 2.92s → 2.57s)

---

