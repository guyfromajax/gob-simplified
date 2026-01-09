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

**Date:** January 9, 2026 (Third measurement)

| Endpoint/Resource | Status | Type | Size | Time |
|-------------------|--------|------|------|------|
| play-next-game | 200 | fetch | 0.2 kB | 3.61 s |
| team-stats?franchise_id=69611c58dc2455c1cf683171 | 200 | fetch | 1.9 kB | 3.08 s |
| schedule?franchise_id=69611c58dc2455c1cf683171 | 200 | fetch | 12.3 kB | 2.54 s |
| roster?franchise_id=69611c58dc2455c1cf683171&team_name=Ocean%20City | 200 | fetch | 7.6 kB | 1.84 s |
| state?franchise_id=69611c58dc2455c1cf683171 | 200 | fetch | 142 kB | 1.81 s |
| team-data?franchise_id=69611c58dc2455c1cf683171&team_id=68c98b09674d3f9b04546b31 | 200 | fetch | 14.1 kB | 1.56 s |
| gameplan?mode=franchise&franchise_id=69611c58dc2455c1cf683171&team_id=68c98b09674d3f9b04546b31 | 200 | fetch | 0.3 kB | 1.51 s |
| data?franchise_id=69611c58dc2455c1cf683171 | 200 | fetch | 0.4 kB | 1.43 s |
| team-data?franchise_id=69611c58dc2455c1cf683171&team_id=68c98b09674d3f9b04546b31 | 200 | fetch | 14.1 kB | 1.41 s |
| franchise-command-center.html | 200 | document | 2.6 kB | 264 ms |
| leaders?franchise_id=69611c58dc2455c1cf683171 | 200 | fetch | 6.7 kB | 232 ms |
| recruits?franchise_id=69611c58dc2455c1cf683171 | 200 | fetch | 15.9 kB | 216 ms |
| teamStatsTable.js | 200 | script | 2.1 kB | 177 ms |
| franchise-command-center.js | 200 | script | 18.7 kB | 172 ms |
| tournament.css | 200 | stylesheet | 2.4 kB | 166 ms |
| franchise-command-center.css | 200 | stylesheet | 0.6 kB | 154 ms |
| command-center-team-styles.css | 200 | stylesheet | 1.5 kB | 150 ms |
| scouting-report.css | 200 | stylesheet | 0.7 kB | 150 ms |
| attributeTooltips.js | 200 | script | 2.0 kB | 145 ms |
| ImageOcean%20City.png | 200 | png | 41.8 kB | 142 ms |
| common.js | 200 | script | 0.6 kB | 137 ms |
| standings?franchise_id=69611c58dc2455c1cf683171 | 200 | fetch | 1.1 kB | 102 ms |
| teams | 200 | fetch | 0.7 kB | 63 ms |
| api-config.js | 200 | script | 1.4 kB | 58 ms |
| UcC73FwrK3iLTeHuS_nVMrMxCp50SjIa1ZL7W0Q5nw.woff2 | 200 | font | 48.5 kB | 44 ms |
| css2?family=Bebas+Neue&family=Inter:wght@400;700&display=swap | 200 | stylesheet | 0.8 kB | 44 ms |
| play-next-game | 200 | preflight | 0.0 kB | 44 ms |
| JTUSjIg69CK48gW7PXoo9WlhyyTh89Y.woff2 | 200 | font | 8.6 kB | 30 ms |
| hive_keychain.js | 200 | script | 5.6 kB | 1 ms |
| roster?franchise_id=69611c58dc2455c1cf683171&team_name= | 200 | fetch | 7.7 kB | 1.86 s |

### Notes
- Slowest calls: `play-next-game` (3.61s), `team-stats` (3.08s), `schedule` (2.54s)
- Largest payload: `state` endpoint (142 kB)
- Fastest calls: `hive_keychain.js` (1ms), fonts (30-44ms), `teams` endpoint (63ms), `standings` (102ms)
- **Consistency:** Speeds very similar to second measurement, showing stable performance

---

**Date:** January 9, 2026 (Navigating back from Game Plan screen)

| Endpoint/Resource | Status | Type | Size | Time |
|-------------------|--------|------|------|------|
| team-stats?franchise_id=69611c58dc2455c1cf683171 | 200 | fetch | 1.9 kB | 3.03 s |
| schedule?franchise_id=69611c58dc2455c1cf683171 | 200 | fetch | 12.2 kB | 2.65 s |
| roster?franchise_id=69611c58dc2455c1cf683171&team_name= | 200 | fetch | 7.7 kB | 1.84 s |
| gameplan?mode=franchise&franchise_id=69611c58dc2455c1cf683171&team_id=68c98b09674d3f9b04546b31 | 200 | fetch | 0.3 kB | 1.42 s |
| team-data?franchise_id=69611c58dc2455c1cf683171&team_id=68c98b09674d3f9b04546b31 | 200 | fetch | 14.1 kB | 1.41 s |
| recruits?franchise_id=69611c58dc2455c1cf683171 | 200 | fetch | 15.9 kB | 223 ms |
| leaders?franchise_id=69611c58dc2455c1cf683171 | 200 | fetch | 6.7 kB | 220 ms |
| standings?franchise_id=69611c58dc2455c1cf683171 | 200 | fetch | 1.1 kB | 107 ms |

### Notes
- **Context:** Speeds when navigating back to FCC from Game Plan screen
- Slowest calls: `team-stats` (3.03s), `schedule` (2.65s)
- Fastest calls: `standings` (107ms), `leaders` (220ms), `recruits` (223ms)
- **Observation:** No `play-next-game` or `state` calls on return navigation (expected - these are only on initial load)
- **Observation:** Fewer API calls than initial load (8 vs 20+), which is expected for return navigation

---

**Date:** January 9, 2026 (Navigating back from Playbooks screen)

| Endpoint/Resource | Status | Type | Size | Time |
|-------------------|--------|------|------|------|
| team-stats?franchise_id=69611c58dc2455c1cf683171 | 200 | fetch | 1.9 kB | 3.22 s |
| schedule?franchise_id=69611c58dc2455c1cf683171 | 200 | fetch | 12.2 kB | 2.72 s |
| roster?franchise_id=69611c58dc2455c1cf683171&team_name= | 200 | fetch | 7.7 kB | 1.85 s |
| team-data?franchise_id=69611c58dc2455c1cf683171&team_id=68c98b09674d3f9b04546b33 | 200 | fetch | 14.1 kB | 1.59 s |
| gameplan?mode=franchise&franchise_id=69611c58dc2455c1cf683171&team_id=68c98b09674d3f9b04546b33 | 200 | fetch | 0.3 kB | 1.58 s |
| leaders?franchise_id=69611c58dc2455c1cf683171 | 200 | fetch | 6.7 kB | 223 ms |
| recruits?franchise_id=69611c58dc2455c1cf683171 | 200 | fetch | 15.9 kB | 213 ms |
| standings?franchise_id=69611c58dc2455c1cf683171 | 200 | fetch | 1.1 kB | 105 ms |

### Notes
- **Context:** Speeds when navigating back to FCC from Playbooks screen
- Slowest calls: `team-stats` (3.22s), `schedule` (2.72s)
- Fastest calls: `standings` (105ms), `recruits` (213ms), `leaders` (223ms)
- **Observation:** Similar API call pattern to Game Plan return navigation (8 calls, no `play-next-game` or `state`)
- **Comparison:** Slightly slower than Game Plan return (`team-stats`: 3.22s vs 3.03s, `schedule`: 2.72s vs 2.65s)

---

**Date:** January 9, 2026 (Fourth measurement)

| Endpoint/Resource | Status | Type | Size | Time |
|-------------------|--------|------|------|------|
| play-next-game | 200 | fetch | 0.2 kB | 3.72 s |
| team-stats?franchise_id=696149297cd33b86528bd1ed | 200 | fetch | 1.9 kB | 3.06 s |
| schedule?franchise_id=696149297cd33b86528bd1ed | 200 | fetch | 12.3 kB | 2.57 s |
| roster?franchise_id=696149297cd33b86528bd1ed&team_name= | 200 | fetch | 7.6 kB | 1.94 s |
| roster?franchise_id=696149297cd33b86528bd1ed&team_name=Morristown | 200 | fetch | 7.6 kB | 1.92 s |
| state?franchise_id=696149297cd33b86528bd1ed | 200 | fetch | 142 kB | 1.84 s |
| team-data?franchise_id=696149297cd33b86528bd1ed&team_id=68c98b09674d3f9b04546b33 | 200 | fetch | 14.1 kB | 1.56 s |
| data?franchise_id=696149297cd33b86528bd1ed | 200 | fetch | 0.4 kB | 1.48 s |
| gameplan?mode=franchise&franchise_id=696149297cd33b86528bd1ed&team_id=68c98b09674d3f9b04546b33 | 200 | fetch | 0.3 kB | 1.47 s |
| team-data?franchise_id=696149297cd33b86528bd1ed&team_id=68c98b09674d3f9b04546b33 | 200 | fetch | 14.0 kB | 1.45 s |
| franchise-command-center.js | 200 | script | 18.6 kB | 239 ms |
| leaders?franchise_id=696149297cd33b86528bd1ed | 200 | fetch | 6.7 kB | 229 ms |
| recruits?franchise_id=696149297cd33b86528bd1ed | 200 | fetch | 16.0 kB | 218 ms |
| scouting-report.css | 200 | stylesheet | 0.7 kB | 205 ms |
| attributeTooltips.js | 200 | script | 2.0 kB | 205 ms |
| common.js | 200 | script | 0.6 kB | 205 ms |
| command-center-team-styles.css | 200 | stylesheet | 1.4 kB | 204 ms |
| teamStatsTable.js | 200 | script | 2.1 kB | 204 ms |
| franchise-command-center.html | 200 | document | 2.4 kB | 197 ms |
| tournament.css | 200 | stylesheet | 2.4 kB | 184 ms |
| franchise-command-center.css | 200 | stylesheet | 0.6 kB | 169 ms |
| ImageMorristown.png | 200 | png | 43.0 kB | 121 ms |
| standings?franchise_id=696149297cd33b86528bd1ed | 200 | fetch | 1.1 kB | 111 ms |
| teams | 200 | fetch | 0.7 kB | 63 ms |
| api-config.js | 200 | script | 1.4 kB | 45 ms |
| css2?family=Bebas+Neue&family=Inter:wght@400;700&display=swap | 200 | stylesheet | 0.8 kB | 43 ms |
| play-next-game | 200 | preflight | 0.0 kB | 42 ms |
| UcC73FwrK3iLTeHuS_nVMrMxCp50SjIa1ZL7W0Q5nw.woff2 | 200 | font | 48.5 kB | 39 ms |
| JTUSjIg69CK48gW7PXoo9WlhyyTh89Y.woff2 | 200 | font | 8.6 kB | 33 ms |
| hive_keychain.js | 200 | script | 5.6 kB | 1 ms |

### Notes
- Slowest calls: `play-next-game` (3.72s), `team-stats` (3.06s), `schedule` (2.57s)
- Largest payload: `state` endpoint (142 kB)
- Fastest calls: `hive_keychain.js` (1ms), fonts (33-39ms), `teams` endpoint (63ms), `standings` (111ms)
- **Consistency:** Speeds very similar to previous measurements, showing stable performance across multiple loads

---

