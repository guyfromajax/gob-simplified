# mode-select.js — three copy/markup changes for the redesign

All in `buildOccupiedSlotHtml()` in `FrontEnd/static/mode-select.js`. Everything else
(the layout, spacing, hierarchy) is handled by `mode-select.css`; these are the only
changes that can't be done from CSS.

## 1 · Drop the Rank and Prestige chips

The compact card shows Record and Next Opponent only. Delete the two middle chips:

```diff
           '<div class="franchise-card-grid">' +
             '<div class="franchise-chip"><div class="franchise-chip-label">Record</div><div class="franchise-chip-value">' + escapeHtml(record) + '</div></div>' +
-            '<div class="franchise-chip"><div class="franchise-chip-label">Rank</div><div class="franchise-chip-value">' + escapeHtml(rank) + '</div></div>' +
-            '<div class="franchise-chip"><div class="franchise-chip-label">Prestige</div><div class="franchise-chip-value">' + escapeHtml(prestige) + '</div></div>' +
             '<div class="franchise-chip"><div class="franchise-chip-label">Next Opponent</div><div class="franchise-chip-value franchise-chip-value-small">' + escapeHtml(nextOpponent) + '</div></div>' +
           '</div>' +
```

`deriveRank()` / `derivePrestige()` and the `rank` / `prestige` locals can stay (harmless)
or be removed — nothing else on the page reads them.

Until this lands, the CSS hides the middle chips
(`.franchise-card-grid .franchise-chip:nth-child(n+2):nth-last-child(n+2){display:none}`),
so the card looks correct either way. That rule can be deleted once the JS ships.

## 2 · Game-in-progress line shows the opponent only

`@ Opponent` when the user's team is away, `vs Opponent` when it's home.

```diff
   if (activeGameResume) {
     enterLabel = 'Resume Game →';
+    const resumeIsAway = String(activeGameResume.user_team_side || 'home').toLowerCase() === 'away';
+    const resumeOpponent = resumeIsAway
+      ? (activeGameResume.home_team_name || 'Opponent')
+      : (activeGameResume.away_team_name || 'Opponent');
     resumeHtml =
       '<div class="franchise-resume-card">' +
         '<div>' +
           '<div class="franchise-resume-kicker">Game In Progress</div>' +
           '<div class="franchise-resume-matchup">' +
-            escapeHtml((activeGameResume.away_team_name || 'Away') + ' at ' + (activeGameResume.home_team_name || 'Home')) +
+            escapeHtml((resumeIsAway ? '@ ' : 'vs ') + resumeOpponent) +
           '</div>' +
```

`user_team_side` is the same field `buildActiveGameCourtUrl()` already passes as `my_team`.

## 3 · Delete button label

```diff
-            '<button type="button" class="franchise-slot-delete-btn" data-action="delete-franchise" data-franchise-id="' + escapeHtml(franchiseId) + '">Delete</button>' +
+            '<button type="button" class="franchise-slot-delete-btn" data-action="delete-franchise" data-franchise-id="' + escapeHtml(franchiseId) + '">Delete Franchise</button>' +
```

No handler changes — `data-action="delete-franchise"` still drives the confirm modal.

## Also needed in mode-select.html

`#franchise-home-slots` carries the layout class: `class="franchise-home-slots fv-a"`.
Keep it — the CSS ships three card layouts (`fv-a` stacked band, `fv-b` status band,
`fv-c` editorial ledger) and the class selects which one renders.
