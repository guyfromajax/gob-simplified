# Local Storage Cleanup

## One-time cleanup (current cruft)

Run this in the **browser DevTools Console** on any gob page (e.g. gob-test.netlify.app):

```javascript
(function () {
  const ls = localStorage;
  [
    'franchiseId', 'franchise_id', 'franchise_week', 'franchise_user_team', 'franchise_user_team_id',
    'activeTournament', 'userTeamId',
    'last_game_id', 'last_box_score_gameId', 'last_box_score_url', 'last_game_user_team_side',
    'game_home', 'game_away'
  ].forEach((k) => ls.removeItem(k));
  Object.keys(ls).forEach((k) => {
    if (k.startsWith('playbooks_position_filters_franchise_') || k.startsWith('playbooks_position_filters_tournament_')) {
      ls.removeItem(k);
    }
  });
  console.log('Local storage cleanup done. Kept auth_token, auth_user, gameSpeed.');
})();
```

**Leaves intact:** `auth_token`, `auth_user`, `gameSpeed`, and any other keys not listed above.

## Sustainable behavior (implemented)

- **Franchise delete:** When the user confirms "New Franchise" and the backend delete succeeds, `clearFranchiseLocalStorage()` runs (in `FrontEnd/static/mode-select.js`). All franchise-related and playbook-filter keys for franchise are removed.
- **Tournament delete:** When the user confirms "New Tournament" and the backend delete succeeds, `clearTournamentLocalStorage()` runs. All tournament-related and playbook-filter keys for tournament are removed.

So after each delete, localStorage no longer accumulates orphaned franchise/tournament data.
