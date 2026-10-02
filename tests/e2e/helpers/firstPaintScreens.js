// @ts-check
/**
 * The screens of reports/screen-gallery-2026-10-01.md, plus the two drill-in pages
 * (team, player), as the first-paint sweep opens them.
 *
 * `where`: 'both' is swept offline (desktop SQLite, real league) and online (hosted,
 * replaying the offline pass's real responses); 'online' has no offline form.
 * `owner`: a screen another agent has in flight. It is swept and listed, never edited.
 */

function screens(ctx) {
  const fcc = (tab, extra) => '/franchise-command-center.html?' + ctx.q(Object.assign({ tab }, extra || {}));
  const focus = (page, extra) => page + '?' + ctx.q(Object.assign({ mode: 'franchise' }, extra || {}));
  const game = {
    week: String(ctx.week || 1), home: ctx.home, away: ctx.away,
    home_id: ctx.homeId, away_id: ctx.awayId, my_team: ctx.myTeam,
  };
  return [
    { id: '01-office', name: 'Office', url: fcc('home-tab'), where: 'both' },
    { id: '02-team-roster', name: 'Team › Roster', url: fcc('roster-view'), where: 'both' },
    { id: '03-team-player-stats', name: 'Team › Player Stats', url: fcc('player-stats-view'), where: 'both' },
    { id: '04-team-attributes', name: 'Team › Team Attributes', url: fcc('team-attributes-view'), where: 'both' },
    { id: '05-team-schedule', name: 'Team › Schedule', url: fcc('team-schedule-view'), where: 'both' },
    { id: '06-practice-squad', name: 'Practice Squad', url: fcc('practice-squad-view'), where: 'both', owner: 'stats' },
    { id: '07-prep-player-training', name: 'Prep › Player Training', url: fcc('training-view'), where: 'both' },
    { id: '08-prep-game-plan', name: 'Prep › Game Plan', url: fcc('game-plan-view'), where: 'both' },
    { id: '09-prep-playbooks', name: 'Prep › Playbooks', url: fcc('playbooks-view'), where: 'both' },
    { id: '10-prep-scouting', name: 'Prep › Scouting', url: fcc('scouting-view'), where: 'both' },
    { id: '11-league-standings', name: 'League › Standings', url: fcc('standings-view'), where: 'both' },
    { id: '12-league-rankings', name: 'League › Rankings', url: fcc('rankings-view'), where: 'both' },
    { id: '13-league-leaders', name: 'League › Leaders', url: fcc('leaders-view'), where: 'both' },
    { id: '14-league-team-stats', name: 'League › Team Stats', url: fcc('team-stats-view'), where: 'both' },
    { id: '15-league-schedule', name: 'League › Schedule', url: fcc('league-schedule-view'), where: 'both' },
    { id: '16-league-tournament', name: 'League › Tournament', url: fcc('tournament-view'), where: 'both', owner: 'stats' },
    { id: '17-recruiting-pool', name: 'Recruiting › Pool', url: focus('/recruiting.html', { hub: 'pool' }), where: 'both', done: true },
    { id: '18-recruiting-leans', name: 'Recruiting › Leans', url: focus('/recruiting.html', { hub: 'leans' }), where: 'both', done: true },
    { id: '19-recruiting-visits', name: 'Recruiting › Visits', url: focus('/recruiting.html', { hub: 'visits' }), where: 'both', done: true },
    { id: '20-news', name: 'News', url: fcc('news-view'), where: 'both' },
    { id: '21-news-awards', name: 'News › Awards', url: fcc('awards-view'), where: 'both' },
    { id: '22-settings-panel', name: 'Settings panel', url: fcc('home-tab'), where: 'both', settings: true },
    { id: '23-weekly-training', name: 'Weekly training (focus)', url: focus('/training.html', { from: 'locker-room', session_type: 'preseason' }), where: 'both' },
    { id: '24-training-report', name: 'Training report (focus)', url: focus('/training-report.html', { week: '1', from: 'training', origin: 'prep' }), where: 'both', done: true },
    { id: '25-set-lineup', name: 'Set Lineup', url: focus('/set-lineup.html', game), where: 'both', owner: 'stats (set-lineup.js)' },
    { id: '26-court-pregame', name: 'Court pre-game', url: focus('/court.html', game), where: 'both' },
    { id: '27-focus-game-plan', name: 'Focus Game Plan (timeout)', url: focus('/game-plan.html', Object.assign({ resume_from_timeout: 'true' }, game)), where: 'both' },
    { id: '28-box-score', name: 'Box score', url: focus('/box-score.html'), where: 'both', owner: 'stats (box-score.js)' },
    { id: '29-cut-players', name: 'Cut players', url: focus('/cut-players.html'), where: 'both', owner: 'stats (practice-squad roster screen)' },
    { id: '30-training-playbooks', name: 'Training playbook', url: focus('/training-playbooks.html'), where: 'both' },
    { id: '31-playbook-report', name: 'Playbook report', url: focus('/playbook-report.html'), where: 'both', owner: 'stats' },
    { id: '32-mode-select', name: 'Mode select', url: '/mode-select.html', where: 'both' },
    { id: '34-trophy-case', name: 'Trophy case', url: '/trophy-case.html', where: 'both' },
    { id: '35-program-select', name: 'Program select', url: '/franchise-select-team.html', where: 'both' },
    { id: '36-team-builder', name: 'Team Builder (step 1)', url: '/team-builder.html', where: 'both' },
    { id: '37-login', name: 'Login', url: '/login.html', where: 'online' },
    { id: '38-signup', name: 'Sign up', url: '/signup.html', where: 'online' },
    { id: '39-reset-password', name: 'Reset password', url: '/reset-password.html', where: 'online' },
    { id: '40-archetype-leaderboard', name: 'Archetype leaderboard', url: '/coaching-archetypes-leaderboard.html', where: 'online' },
    { id: '41-coaching-archetypes', name: 'Coaching archetypes', url: '/coaching-archetypes.html', where: 'online' },
    { id: '42-account', name: 'Account', url: '/account.html', where: 'online' },
    { id: '43-tutorial-hub', name: 'Tutorial hub', url: '/tutorial.html', where: 'both' },
    { id: '44-tutorial-recruiting', name: 'Tutorial lesson (recruiting)', url: '/tutorial-recruiting.html', where: 'both' },
    { id: '45-persona-intro', name: 'Persona intro', url: '/tutorial-persona-intro.html', where: 'both' },
    { id: '46-faqs', name: 'FAQs', url: '/faqs.html', where: 'both' },
    { id: '47-team-page', name: 'Team page (drill-in)', url: fcc('team-view', { view_team_id: ctx.otherTeamId, origin: 'league', up: 'Standings', return_tab: 'standings-view' }), where: 'both' },
    { id: '48-player-page', name: 'Player page (drill-in)', url: fcc('player-view', { player_id: ctx.playerId, origin: 'team', up: 'Roster', return_tab: 'roster-view' }), where: 'both' },
  ];
}

module.exports = { screens };
