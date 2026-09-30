/**
 * Franchise shell for franchise-command-center.html.
 * Rail section clicks push a history entry. Sub-tabs replace. Recruiting leaves via GOBNav.go.
 * Does not run on the tournament command center or the live-game court.
 */
(function () {
  'use strict';
  if (window.__gobShellStarted) return;
  window.__gobShellStarted = true;

  var ICONS = {
    office: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 10h17M5 10v10M19 10v10M8 10V6.5a1.5 1.5 0 0 1 1.5-1.5h5A1.5 1.5 0 0 1 16 6.5V10"/><path d="M9 14h6"/></svg>',
    team: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="8.5" cy="8" r="2.7"/><circle cx="16" cy="9" r="2.3"/><path d="M3.5 19c0-2.9 2.2-5 5-5 1.8 0 3.3.9 4.2 2.3"/><path d="M13.5 19c.3-2.3 1.9-3.7 3.9-3.7 1.8 0 3.4 1.3 3.6 3.7"/></svg>',
    prep: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M6 4.5h12a1 1 0 0 1 1 1V20a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V5.5a1 1 0 0 1 1-1Z"/><path d="M9 3h6v3H9z"/><path d="M8.5 12l2 2 4-4.5M8.5 17.5h7"/></svg>',
    league: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 5h16M4 10h16M4 15h16M4 20h16"/><path d="M9 5v15"/></svg>',
    recruiting: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="9.5" cy="8" r="3.1"/><path d="M3.8 20c0-3.3 2.6-5.6 5.7-5.6 1.4 0 2.7.5 3.7 1.3"/><path d="M17.5 13.5v6M14.5 16.5h6"/></svg>',
    news: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 5h13v14a1.5 1.5 0 0 0 1.5 1.5H6A2 2 0 0 1 4 18.5Z"/><path d="M17 9h3v10a1.5 1.5 0 0 1-3 0"/><path d="M7.5 9h6M7.5 12.5h6M7.5 16h4"/></svg>',
    tutorials: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="8.5"/><path d="M9.6 9.6a2.5 2.5 0 0 1 4.8.9c0 1.7-2.4 2.1-2.4 3.6"/><path d="M12 17.2v.1"/></svg>',
    feedback: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 6.5a2 2 0 0 1 2-2h11a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H11l-4 3.5v-3.5h-.5a2 2 0 0 1-2-2Z"/><path d="M8.5 9.5h7M8.5 12.5h4.5"/></svg>',
    settings: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="2.8"/><circle cx="12" cy="12" r="6.6"/><path d="M12 2.8v2.6M12 18.6v2.6M2.8 12h2.6M18.6 12h2.6M5.5 5.5l1.8 1.8M16.7 16.7l1.8 1.8M5.5 18.5l1.8-1.8M16.7 7.3l1.8-1.8"/></svg>',
    exit: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 4h4a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1h-4"/><path d="M10 16l-4-4 4-4M6 12h9"/></svg>'
  };

  var SECTIONS = [
    { id: 'office', label: 'Office', title: "Coach's Office", icon: 'office', tabs: [{ id: 'home-tab' }] },
    { id: 'team', label: 'Team', title: 'Team', icon: 'team', tabs: [
      { id: 'roster-view', label: 'Roster' },
      { id: 'player-stats-view', label: 'Player Stats' },
      { id: 'team-attributes-view', label: 'Team Attributes' },
      { id: 'team-schedule-view', label: 'Schedule' },
      { id: 'practice-squad-view', label: 'Practice Squad' }
    ]},
    { id: 'prep', label: 'Prep', title: 'Prep', icon: 'prep', tabs: [
      { id: 'game-plan-view', label: 'Game Plan' },
      { id: 'playbooks-view', label: 'Playbooks' },
      { id: 'scouting-view', label: 'Scouting Report' },
      // Per-player development only. Weekly allocation is /training.html (focus),
      // opened by Advance — same pattern as Set Lineup.
      { id: 'training-view', label: 'Player Training' }
    ]},
    { id: 'league', label: 'League', title: 'League', icon: 'league', tabs: [
      { id: 'standings-view', label: 'Standings' },
      { id: 'rankings-view', label: 'Rankings' },
      { id: 'leaders-view', label: 'Leaders' },
      { id: 'team-stats-view', label: 'Team Stats' },
      { id: 'league-schedule-view', label: 'Schedule' },
      { id: 'tournament-view', label: 'Tournament', lock: 'tournament' }
    ]},
    { id: 'recruiting', label: 'Recruiting', title: 'Recruiting', icon: 'recruiting', go: 'recruiting', tabs: [
      { id: 'pool', label: 'Pool' },
      { id: 'leans', label: 'Leans' },
      { id: 'visits', label: 'Visits' }
    ]},
    { id: 'news', label: 'News', title: 'News', icon: 'news', tabs: [
      { id: 'news-view', label: 'News' },
      { id: 'awards-view', label: 'Awards' }
    ]}
  ];

  var TAB_SECTION = {
    'home-tab': 'office',
    'roster-tab': 'team',
    'roster-view': 'team',
    'player-stats-tab': 'team',
    'player-stats-view': 'team',
    'team-stats-tab': 'team',
    'team-attributes-view': 'team',
    'schedule-tab': 'team',
    'team-schedule-view': 'team',
    'practice-squad-view': 'team',
    'training-tab': 'prep',
    'training-view': 'prep',
    'game-plan-tab': 'prep',
    'game-plan-view': 'prep',
    'playbooks-tab': 'prep',
    'playbooks-view': 'prep',
    'scouting-view': 'prep',
    'coaches-tab': 'prep',
    'standings-tab': 'league',
    'standings-view': 'league',
    'rankings-view': 'league',
    'leaders-view': 'league',
    'team-stats-view': 'league',
    'league-schedule-view': 'league',
    'tournament-view': 'league',
    'schedule-page': 'league',
    'fcc-team-stats-summary-tab': 'league',
    'awards-tab': 'league',
    'press-tab': 'news',
    'news-view': 'news',
    'awards-view': 'news',
    // Drill-ins belong to no rail section, so every rail button leaves them.
    // The highlight follows ?origin= (detailOrigin); without it, nothing is on.
    'player-view': 'detail',
    'team-view': 'detail'
  };
  var DETAIL_SECTION = { id: 'detail', label: '', title: '', tabs: [] };

  var sectionEls = {};
  var subtabHost = null;
  var titleEl = null;
  var paintedSection = '';
  var currentWeek = 0;
  var pageMode = null;
  var recruitingRowOff = false;

  var PAGES = {
    '/recruiting.html': { kind: 'browse', section: 'recruiting', sub: '', file: 'recruiting' },
    '/rankings.html': { kind: 'browse', section: 'league', sub: 'rankings' },
    '/schedule.html': { kind: 'browse', section: 'league', sub: 'schedule' },
    '/practice-squad-standings.html': { kind: 'browse', section: 'team', sub: 'practice-squad-view' },
    '/practice-squad-bracket.html': { kind: 'browse', section: 'team', sub: 'practice-squad-view', keepBack: true },
    '/brackets.html': { kind: 'browse', section: 'league', sub: 'tournament-view', keepBack: true },
    '/awards.html': { kind: 'browse', section: 'news', sub: 'awards-view' },
    '/news.html': { kind: 'browse', section: 'news', sub: 'news-view' },
    '/leaders.html': { kind: 'browse', section: 'league', sub: 'leaders-view' },
    '/standings.html': { kind: 'browse', section: 'league', sub: 'standings-view' },
    '/team-stats.html': { kind: 'browse', section: 'league', sub: 'team-stats-view' },
    '/stats.html': { kind: 'browse', section: 'league', sub: 'team-stats-view' },
    '/team-traits.html': { kind: 'browse', section: 'team', sub: 'team-attributes-view' },
    '/player-detail.html': { kind: 'browse', section: 'context', sub: '', keepBack: true },
    '/team-roster-view.html': { kind: 'browse', section: 'context', sub: '', keepBack: true },
    '/set-lineup.html': { kind: 'focus' },
    '/training.html': { kind: 'focus' },
    '/training-report.html': { kind: 'focus' },
    '/training-squad-report.html': { kind: 'focus' },
    '/training-playbooks.html': { kind: 'focus' },
    '/cut-players.html': { kind: 'focus' },
    '/game-plan.html': { kind: 'browse', section: 'prep', sub: 'game-plan-view' },
    '/playbooks.html': { kind: 'browse', section: 'prep', sub: 'playbooks-view' },
    '/playbook-report.html': { kind: 'focus' },
    '/box-score.html': { kind: 'flow-or-browse' }
  };

  function sectionById(id) {
    for (var i = 0; i < SECTIONS.length; i++) {
      if (SECTIONS[i].id === id) return SECTIONS[i];
    }
    return SECTIONS[0];
  }

  function tabFromUrl() {
    try {
      return new URLSearchParams(window.location.search).get('tab') || '';
    } catch (err) {
      return '';
    }
  }

  function currentTab() {
    var urlTab = tabFromUrl();
    if (urlTab === 'recruits-tab') return 'home-tab';
    if (urlTab === 'schedule-tab') return 'team-schedule-view';
    if (urlTab === 'training-tab') urlTab = 'training-view';
    if (urlTab === 'game-plan-tab') urlTab = 'game-plan-view';
    if (urlTab === 'playbooks-tab') urlTab = 'playbooks-view';
    if (urlTab === 'coaches-tab') urlTab = 'scouting-view';
    var actives = document.querySelectorAll('#tournament-tabs > .tab-content.active');
    var i;
    if (urlTab) {
      for (i = 0; i < actives.length; i++) {
        if (actives[i].id === urlTab) return urlTab;
      }
    }
    if (actives.length) {
      var id = actives[actives.length - 1].id;
      if (id === 'recruits-tab') return 'home-tab';
      return id;
    }
    if (urlTab && TAB_SECTION[urlTab]) return urlTab;
    return 'home-tab';
  }

  function playClick() {
    import('/js/shared/uiSfx.js').then(function (m) {
      m.playSfx('click-tiny.wav', 0.7);
    }).catch(function () {});
  }

  function openTab(tabName, historyMode) {
    if (!window.CommandCenterTabs || typeof window.CommandCenterTabs.show !== 'function') return;
    window.CommandCenterTabs.show(tabName, historyMode);
  }

  function hrefOf(el) {
    if (!el) return '';
    var href = el.getAttribute('href') || '';
    if (!href || href === '#') return '';
    return href;
  }

  function resourceHref(page) {
    var src = hrefOf(document.getElementById('home-rankings-full-link'))
      || hrefOf(document.getElementById('resources-rankings'))
      || hrefOf(document.getElementById('schedule-full-link'));
    if (!src) return '';
    try {
      var u = new URL(src, window.location.origin);
      u.pathname = '/' + page;
      return u.pathname + u.search;
    } catch (err) {
      return '';
    }
  }

  function linkHref(kind) {
    if (kind === 'rankings') return resourceHref('rankings.html');
    if (kind === 'brackets') {
      var live = document.querySelector('a[href*="brackets.html"]');
      return hrefOf(live) || resourceHref('brackets.html');
    }
    if (kind === 'awards') return resourceHref('awards.html');
    if (kind === 'practice') return hrefOf(document.getElementById('fcc-ps-season-link'));
    if (kind === 'schedule') {
      return hrefOf(document.getElementById('schedule-full-link'))
        || hrefOf(document.getElementById('resources-schedule'))
        || hrefOf(document.getElementById('tournament-schedule-link'));
    }
    if (kind === 'recruiting') return hrefOf(document.getElementById('resources-recruits'));
    return '';
  }

  function firstTournamentWeek() {
    var api = window.GOBTierEmblem;
    if (!api || typeof api.tierForWeek !== 'function') return 0;
    var w;
    for (w = 1; w <= 40; w++) {
      if (api.tierForWeek(w)) return w;
    }
    return 0;
  }

  function tournamentLockWeek() {
    var opens = firstTournamentWeek();
    if (!opens || !currentWeek || currentWeek >= opens) return 0;
    return opens;
  }

  function fallbackHref(kind) {
    var file = {
      rankings: 'rankings.html',
      brackets: 'brackets.html',
      awards: 'awards.html',
      practice: 'practice-squad-standings.html',
      schedule: 'schedule.html',
      recruiting: 'recruiting.html'
    }[kind];
    if (!file) return '';
    var q = new URLSearchParams(window.location.search);
    var p = new URLSearchParams();
    ['franchise_id', 'team_id', 'mode'].forEach(function (key) {
      if (q.get(key)) p.set(key, q.get(key));
    });
    if (kind === 'recruiting') p.set('from', 'fcc');
    var search = p.toString();
    return '/' + file + (search ? '?' + search : '');
  }

  function fccHref(tab) {
    var q = new URLSearchParams(window.location.search);
    var p = new URLSearchParams();
    if (q.get('franchise_id')) p.set('franchise_id', q.get('franchise_id'));
    var teamId = q.get('team_id') || q.get('user_team_id');
    if (teamId) p.set('team_id', teamId);
    if (tab) p.set('tab', tab);
    return '/franchise-command-center.html?' + p.toString();
  }

  function goLink(kind) {
    var href = linkHref(kind) || (pageMode ? fallbackHref(kind) : '');
    if (!href) return;
    playClick();
    var nav = window.GOBNav;
    if (pageMode) {
      if (nav && typeof nav.replace === 'function') nav.replace(href);
      else window.location.replace(href);
      return;
    }
    if (nav && typeof nav.go === 'function') nav.go(href);
    else window.location.assign(href);
  }

  function recruitingWeek() {
    if (currentWeek) return currentWeek;
    if (window.RecruitingHub && typeof window.RecruitingHub.week === 'function') {
      return Number(window.RecruitingHub.week()) || 0;
    }
    return 0;
  }

  function labeledTabs(section) {
    return section.tabs.filter(function (tab) {
      if (!tab.label) return false;
      var week = recruitingWeek();
      if (section.id === 'recruiting' && isRecruitingHubTab(tab) && week >= 20 && week <= 26) {
        return false;
      }
      return true;
    });
  }

  function hubFromUrl() {
    try {
      var hub = new URLSearchParams(window.location.search).get('hub') || '';
      if (hub === 'pool' || hub === 'leans' || hub === 'visits') return hub;
    } catch (err) {}
    return '';
  }

  function isRecruitingHubTab(item) {
    return !!(item && (item.id === 'pool' || item.id === 'leans' || item.id === 'visits'));
  }

  function recruitingHubHref(hub) {
    var q = new URLSearchParams(window.location.search);
    q.set('hub', hub);
    var search = q.toString();
    var path = window.location.pathname || '/recruiting.html';
    return path + (search ? '?' + search : '');
  }

  function replaceRecruitingHub(hub, opts) {
    opts = opts || {};
    if (!pageMode || pageMode.file !== 'recruiting') return;
    if (hub !== 'pool' && hub !== 'leans' && hub !== 'visits') return;
    var href = recruitingHubHref(hub);
    var here = (window.location.pathname || '') + (window.location.search || '');
    if (here !== href && window.history && window.history.replaceState) {
      window.history.replaceState(window.history.state, '', href);
      if (window.GOBNav && typeof window.GOBNav.syncCurrent === 'function') window.GOBNav.syncCurrent();
    }
    pageMode.sub = hub;
    if (subtabHost && !recruitingRowOff) renderSubtabs(sectionById('recruiting'), hub);
    if (!opts.silent && window.RecruitingHub && typeof window.RecruitingHub.show === 'function') {
      window.RecruitingHub.show(hub);
      return;
    }
    if (!recruitingRowOff && window.RecruitingHub && typeof window.RecruitingHub.mountSearch === 'function') {
      window.RecruitingHub.mountSearch();
    }
  }

  function setRecruitingTabs(visible) {
    if (!pageMode || pageMode.file !== 'recruiting' || !subtabHost) return;
    recruitingRowOff = !visible;
    if (!visible) {
      subtabHost.hidden = true;
      var tools = subtabHost.querySelector('.pg-tools[data-owner="recruiting"]');
      if (tools) tools.remove();
      return;
    }
    subtabHost.hidden = false;
    renderSubtabs(sectionById('recruiting'), pageMode.sub || '');
    if (window.RecruitingHub && typeof window.RecruitingHub.mountSearch === 'function') {
      window.RecruitingHub.mountSearch();
    }
  }

  function onRecruitingPop() {
    if (!pageMode || pageMode.file !== 'recruiting') return;
    var hub = hubFromUrl() || 'pool';
    pageMode.sub = hub;
    if (subtabHost && !recruitingRowOff) renderSubtabs(sectionById('recruiting'), hub);
    if (window.RecruitingHub && typeof window.RecruitingHub.show === 'function') {
      window.RecruitingHub.show(hub);
    }
  }

  function activateSubtab(item) {
    if (!item || item.lockedWeek) return;
    if (pageMode && pageMode.file === 'recruiting' && isRecruitingHubTab(item)) {
      if (pageMode.sub === item.id) return;
      playClick();
      replaceRecruitingHub(item.id);
      return;
    }
    if (item.link) {
      if (pageMode && pageMode.sub === item.link) return;
      goLink(item.link);
      return;
    }
    if (pageMode) {
      if (pageMode.sub === item.id) return;
      playClick();
      var href = fccHref(item.id);
      if (window.GOBNav && window.GOBNav.replace) window.GOBNav.replace(href);
      else window.location.replace(href);
      return;
    }
    if (currentTab() === item.id) return;
    playClick();
    openTab(item.id, 'replace');
  }

  function renderSubtabs(section, tab) {
    if (!subtabHost || !window.GOBSubtabs) return;
    if (pageMode && pageMode.file === 'recruiting' && recruitingRowOff) {
      subtabHost.hidden = true;
      return;
    }
    var tabs = labeledTabs(section).map(function (item) {
      var lockedWeek = item.lock === 'tournament' ? tournamentLockWeek() : 0;
      return {
        id: item.id,
        label: item.label,
        link: item.link || '',
        lockedWeek: lockedWeek
      };
    });
    window.GOBSubtabs.render(subtabHost, {
      label: section.label,
      tabs: tabs,
      selected: tab || '',
      onActivate: activateSubtab
    });
    if (section.id === 'recruiting' && !tabs.length && recruitingWeek() >= 20 && recruitingWeek() <= 26) {
      subtabHost.hidden = false;
    }
    if (window.GOBTables && typeof window.GOBTables.placeTools === 'function') window.GOBTables.placeTools(subtabHost);
    window.GOBSubtabs.syncTools(subtabHost);
    if (section.id === 'recruiting' && window.RecruitingHub && typeof window.RecruitingHub.mountSearch === 'function') {
      window.RecruitingHub.mountSearch();
    }
  }

  function markSubtabs(tab) {
    if (!subtabHost || !window.GOBSubtabs) return;
    window.GOBSubtabs.select(subtabHost, tab || '');
  }

  function detailOrigin(tab) {
    if (tab !== 'player-view' && tab !== 'team-view') return '';
    var origin = '';
    try { origin = new URLSearchParams(window.location.search).get('origin') || ''; }
    catch (err) { origin = ''; }
    if (origin === 'team' || origin === 'league' || origin === 'office'
      || origin === 'prep' || origin === 'news') return origin;
    return '';
  }

  function detailMark(tab) {
    if (tab !== 'player-view' && tab !== 'team-view') return tab;
    try { return new URLSearchParams(window.location.search).get('return_tab') || ''; }
    catch (err) { return ''; }
  }

  function sync(tab) {
    if (leaveLockedTab(tab)) return;
    var sectionId = detailOrigin(tab) || TAB_SECTION[tab] || 'office';
    var mark = detailMark(tab);
    var section = sectionId === DETAIL_SECTION.id ? DETAIL_SECTION : sectionById(sectionId);
    document.querySelectorAll('.rail [data-gob-section]').forEach(function (el) {
      el.classList.toggle('on', el.getAttribute('data-gob-section') === sectionId);
    });
    Object.keys(sectionEls).forEach(function (id) {
      if (sectionEls[id]) sectionEls[id].classList.toggle('on', id === sectionId);
    });
    // gob-office is the Office-home layout (week cards, no page head). Lighting the
    // Office rail via ?origin=office on a drill-in must not turn that layout on —
    // otherwise #home-tab is forced visible and the week cards stack on the report.
    var officeHome = tab === 'home-tab';
    if (titleEl) {
      if (officeHome) titleEl.textContent = '';
      else titleEl.textContent = sectionId === 'office' ? '' : section.title;
    }
    document.documentElement.classList.toggle('gob-office', officeHome);
    if (paintedSection !== sectionId) {
      renderSubtabs(section, mark);
      paintedSection = sectionId;
    } else {
      markSubtabs(mark);
      if (window.GOBTables && typeof window.GOBTables.placeTools === 'function') window.GOBTables.placeTools(subtabHost);
      else if (window.GOBSubtabs) window.GOBSubtabs.syncTools(subtabHost);
    }
  }

  function railButton(section) {
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'rail-i';
    btn.dataset.gobSection = section.id;
    btn.title = section.label;
    btn.innerHTML = ICONS[section.icon] + '<span class="rail-l">' + section.label + '</span>';
    if (section.id === 'recruiting') btn.id = 'gob-rail-recruiting';
    btn.addEventListener('click', function () {
      if (section.id === 'prep') {
        if (pageMode && pageMode.section === 'prep') return;
        if (!pageMode && (TAB_SECTION[currentTab()] || 'office') === 'prep') return;
        playClick();
        if (pageMode) {
          var prepNav = window.GOBNav;
          var prepHref = fccHref('training-view');
          if (prepNav && prepNav.go) prepNav.go(prepHref);
          else window.location.assign(prepHref);
        } else {
          openTab('training-view', 'push');
        }
        return;
      }
      if (pageMode) {
        if (pageMode.section === section.id) return;
        playClick();
        var nav = window.GOBNav;
        if (section.go === 'recruiting') {
          var rec = fallbackHref('recruiting');
          if (nav && nav.go) nav.go(rec);
          else window.location.assign(rec);
          return;
        }
        var destPage = section.tabs.filter(function (item) { return !item.link; })[0];
        if (!destPage) return;
        var pageHref = fccHref(destPage.id);
        if (nav && nav.go) nav.go(pageHref);
        else window.location.assign(pageHref);
        return;
      }
      if (section.go === 'recruiting') {
        playClick();
        if (typeof window.openRecruitingSurface === 'function') {
          window.openRecruitingSurface();
          return;
        }
        goLink('recruiting');
        return;
      }
      var tab = currentTab();
      if ((TAB_SECTION[tab] || 'office') === section.id) return;
      var dest = section.tabs.filter(function (item) { return !item.link; })[0];
      if (!dest) return;
      playClick();
      openTab(dest.id, 'push');
    });
    sectionEls[section.id] = btn;
    return btn;
  }

  // `.gob .rail-i` sets display, which beats the [hidden] attribute.
  function setShown(btn, shown) {
    btn.hidden = !shown;
    btn.style.display = shown ? '' : 'none';
  }

  // authBarInit (loaded async by authGuard) creates #feedback-btn after its
  // stylesheet is ready, which is after a page shell boots. Show the rail item
  // once that button exists; pages without an auth bar never get one.
  function revealFeedbackWhenReady(btn) {
    setShown(btn, false);
    if (window.GOB_BUILD_PROFILE === 'desktop') return;
    if (document.getElementById('feedback-btn')) {
      setShown(btn, true);
      return;
    }
    if (typeof MutationObserver !== 'function' || !document.body) return;
    var watcher = new MutationObserver(function () {
      if (!document.getElementById('feedback-btn')) return;
      setShown(btn, true);
      watcher.disconnect();
    });
    watcher.observe(document.body, { childList: true, subtree: true });
    setTimeout(function () { watcher.disconnect(); }, 15000);
  }

  function utilButton(className, title, icon, id) {
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'rail-i ' + className;
    btn.title = title;
    if (id) btn.id = id;
    btn.innerHTML = ICONS[icon] + '<span class="rail-l">' + title + '</span>';
    return btn;
  }

  function paintRecord(data) {
    var source = document.getElementById('fcc-record-label');
    var valueEl = document.getElementById('gob-record-value');
    var wrap = document.getElementById('gob-record-stat');
    if (!valueEl || !wrap) return;
    var text = source ? String(source.textContent || '') : '';
    var cut = text.indexOf(':');
    var value = (cut === -1 ? text : text.slice(cut + 1)).trim();
    if (value === '--' || value === '—' || value === '-') value = '';
    if (!value && data && data.team_record && data.team_record.wins != null && data.team_record.losses != null) {
      value = String(data.team_record.wins) + '-' + String(data.team_record.losses);
    }
    if (!value) value = recordFromRankings(data);
    if (!value) {
      wrap.hidden = true;
      return;
    }
    wrap.hidden = false;
    valueEl.textContent = value;
  }

  function recordFromRankings(data) {
    var rankings = data && data.rankings;
    if (!rankings || !rankings.length) return '';
    var teamId = String(data.user_team_object_id || data.user_team_id || data.team_id || '');
    if (!teamId) return '';
    var row = null;
    for (var i = 0; i < rankings.length; i++) {
      if (String(rankings[i].team_id || '') === teamId) {
        row = rankings[i];
        break;
      }
    }
    if (!row || row.W == null || row.L == null) return '';
    return String(row.W) + '-' + String(row.L);
  }

  function paintRank(data) {
    var source = document.getElementById('fcc-rank-label');
    var valueEl = document.getElementById('gob-rank-value');
    var wrap = document.getElementById('gob-rank-stat');
    if (!valueEl || !wrap) return;
    var text = source ? String(source.textContent || '') : '';
    var match = text.match(/(\d+)/);
    if (!match && data && data.rank != null && data.rank !== '' && data.rank !== '--') {
      wrap.hidden = false;
      valueEl.textContent = '#' + data.rank;
      return;
    }
    wrap.hidden = false;
    valueEl.textContent = match ? ('#' + match[1]) : 'NR';
  }

  function paintWeek(week) {
    var valueEl = document.getElementById('gob-week-value');
    var phaseEl = document.getElementById('gob-week-phase');
    var wrap = document.getElementById('gob-week-stat');
    var top = document.querySelector('html.gob-shell .top');
    if (!valueEl || !wrap) return;
    var n = Number(week);
    currentWeek = n || 0;
    if (!n) {
      wrap.hidden = true;
      if (top) {
        top.classList.remove('is-tier');
        top.style.removeProperty('--tier-metal');
        top.style.removeProperty('--tier-metal-hi');
      }
      refreshTournamentLock();
      return;
    }
    wrap.hidden = false;
    valueEl.textContent = 'Week ' + n;
    if (phaseEl) {
      phaseEl.hidden = true;
      phaseEl.textContent = '';
    }
    var tier = window.GOBTierEmblem && window.GOBTierEmblem.tierForWeek
      ? window.GOBTierEmblem.tierForWeek(n)
      : null;
    var tokens = tier && window.GOBTierEmblem.TIER_TOKENS
      ? window.GOBTierEmblem.TIER_TOKENS[tier]
      : null;
    if (top && tokens && tokens.metal && tokens.metalHi) {
      top.classList.add('is-tier');
      top.style.setProperty('--tier-metal', tokens.metal);
      top.style.setProperty('--tier-metal-hi', tokens.metalHi);
    } else if (top) {
      top.classList.remove('is-tier');
      top.style.removeProperty('--tier-metal');
      top.style.removeProperty('--tier-metal-hi');
    }
    if (pageMode && pageMode.file === 'recruiting' && subtabHost && !recruitingRowOff) {
      renderSubtabs(sectionById('recruiting'), pageMode.sub || '');
    }
    refreshTournamentLock();
  }

  // Desktop resumes the last tab when the document was opened without ?tab=.
  // A resumed tab can be one the sub-tab row would not let you pick; an
  // explicit ?tab= link keeps its locked screen.
  var resumePending = (function () {
    try {
      var entry = performance.getEntriesByType('navigation')[0];
      var requested = new URL(entry ? entry.name : window.location.href);
      return !requested.searchParams.get('tab');
    } catch (err) {
      return false;
    }
  })();

  // Decided once, when the week is first known; tab toggles during boot pass
  // through other tabs first.
  function leaveLockedTab(tab) {
    if (!resumePending || pageMode) return false;
    if (!currentWeek || !firstTournamentWeek()) return false;
    resumePending = false;
    if (tab !== 'tournament-view' || !tournamentLockWeek()) return false;
    if (!window.CommandCenterTabs || typeof window.CommandCenterTabs.show !== 'function') return false;
    openTab('home-tab', 'replace');
    return true;
  }

  function refreshTournamentLock() {
    if (leaveLockedTab(currentTab())) return;
    if (paintedSection !== 'league' || !subtabHost) return;
    var tab = pageMode ? (pageMode.sub || '') : currentTab();
    var wantLock = !!tournamentLockWeek();
    var hasLock = !!subtabHost.querySelector('.tb.is-locked');
    var on = subtabHost.querySelector('.tb[aria-selected="true"]');
    var onKey = on ? (on.dataset.tab || on.dataset.link || '') : '';
    if (wantLock === hasLock && onKey === tab && subtabHost.childElementCount) return;
    renderSubtabs(sectionById('league'), tab);
  }

  function weekFromLabel() {
    var source = document.getElementById('fcc-season-label');
    var match = String((source && source.textContent) || '').match(/Week\s+(\d+)/i);
    return match ? Number(match[1]) : 0;
  }

  function syncTop(data) {
    paintRecord(data);
    paintRank(data);
    var week = data && data.week != null ? Number(data.week) : weekFromLabel();
    paintWeek(week);
  }

  function mount() {
    if (!document.getElementById('franchise-container')) return;
    if (document.querySelector('html.gob-shell .app')) return;
    document.documentElement.classList.add('gob', 'gob-shell');

    var app = document.createElement('div');
    app.className = 'app';

    var top = document.createElement('header');
    top.className = 'top';
    var topId = document.createElement('a');
    topId.className = 'top-id';
    topId.href = '#';
    topId.id = 'gob-top-id';
    var logo = document.getElementById('team-logo');
    if (logo) topId.appendChild(logo);
    topId.addEventListener('click', function (event) {
      event.preventDefault();
      var tab = currentTab();
      if (tab === 'roster-view' || tab === 'roster-tab') return;
      playClick();
      var mode = (TAB_SECTION[tab] || 'office') === 'team' ? 'replace' : 'push';
      openTab('roster-view', mode);
    });

    var divider = document.createElement('div');
    divider.className = 'top-div';

    var stats = document.createElement('div');
    stats.className = 'top-stats';
    stats.innerHTML = [
      '<div class="ts" id="gob-record-stat" hidden><b id="gob-record-value"></b><span>Record</span></div>',
      '<div class="ts" id="gob-rank-stat" hidden><b id="gob-rank-value"></b><span>National Rank</span></div>',
      '<div class="ts" id="gob-week-stat" hidden><b id="gob-week-value"></b><span id="gob-week-phase" hidden></span></div>'
    ].join('');

    var spacer = document.createElement('div');
    spacer.className = 'top-sp';

    var adv = document.createElement('div');
    adv.className = 'adv-wrap';
    var ghost = document.getElementById('fcc-edit-recruiting');
    var play = document.getElementById('play-now');
    if (ghost) adv.appendChild(ghost);
    if (play) {
      play.classList.add('advance');
      play.setAttribute('data-sfx', 'SFX_ADVANCE');
      adv.appendChild(play);
    }

    top.appendChild(topId);
    top.appendChild(divider);
    top.appendChild(stats);
    var emblem = document.getElementById('fcc-header-emblem');
    if (emblem) {
      var weekStat = stats.querySelector('#gob-week-stat');
      if (weekStat) weekStat.appendChild(emblem);
    }
    top.appendChild(spacer);
    top.appendChild(adv);

    var rail = document.createElement('nav');
    rail.className = 'rail';
    rail.setAttribute('aria-label', 'Franchise');
    var face = document.createElement('div');
    face.className = 'rail-face';
    SECTIONS.forEach(function (section) { face.appendChild(railButton(section)); });
    var spring = document.createElement('div');
    spring.className = 'rail-sp';
    face.appendChild(spring);
    var div = document.createElement('div');
    div.className = 'rail-div';
    face.appendChild(div);

    var tutorials = document.createElement('a');
    tutorials.className = 'rail-i util';
    tutorials.href = '/tutorial.html';
    tutorials.title = 'Tutorials';
    tutorials.innerHTML = ICONS.tutorials + '<span class="rail-l">Tutorials</span>';
    tutorials.addEventListener('click', function () { playClick(); });
    face.appendChild(tutorials);

    var feedback = utilButton('util', 'Feedback', 'feedback', 'gob-rail-feedback');
    feedback.addEventListener('click', function () {
      var existing = document.getElementById('feedback-btn');
      if (!existing) return;
      existing.click();
    });
    if (window.GOB_BUILD_PROFILE === 'desktop') setShown(feedback, false);
    face.appendChild(feedback);

    var settings = utilButton('util', 'Settings', 'settings', 'gob-rail-settings');
    settings.setAttribute('aria-expanded', 'false');
    settings.addEventListener('click', function () {
      playClick();
      import('/js/shared/gobSettings.js').then(function () {
        if (window.GOBSettings && window.GOBSettings.toggle) window.GOBSettings.toggle();
      }).catch(function () {});
    });
    face.appendChild(settings);

    var quiet = document.createElement('div');
    quiet.className = 'rail-div q';
    face.appendChild(quiet);

    var exitBtn = utilButton('exit', 'Exit Franchise', 'exit', 'gob-rail-exit');
    exitBtn.addEventListener('click', function () {
      var existing = document.getElementById('exit-franchise');
      if (existing) existing.click();
    });
    face.appendChild(exitBtn);
    rail.appendChild(face);

    var main = document.createElement('div');
    main.className = 'main scroll';
    main.id = 'gob-main';

    var head = document.createElement('div');
    head.className = 'pg-head';
    var titleRow = document.createElement('div');
    titleRow.className = 'pg-title';
    titleEl = document.createElement('h1');
    titleRow.appendChild(titleEl);
    subtabHost = document.createElement('div');
    subtabHost.className = 'nav-row';
    subtabHost.id = 'gob-subtabs';
    head.appendChild(titleRow);
    head.appendChild(subtabHost);

    var container = document.getElementById('franchise-container');
    main.appendChild(head);
    main.appendChild(container);
    app.appendChild(top);
    app.appendChild(rail);
    app.appendChild(main);
    document.body.insertBefore(app, document.body.firstChild);

    window.addEventListener('gob-tab-shown', function (event) {
      var tab = event.detail && event.detail.tab;
      if (tab === 'recruits-tab') {
        setTimeout(function () { openTab('home-tab', 'replace'); }, 0);
        return;
      }
      sync(tab || currentTab());
    });
    window.addEventListener('popstate', function () {
      setTimeout(function () {
        if (tabFromUrl() === 'recruits-tab') {
          openTab('home-tab', 'replace');
          return;
        }
        sync(currentTab());
      }, 0);
    });
    var tabsRoot = document.getElementById('tournament-tabs');
    if (tabsRoot && typeof MutationObserver === 'function') {
      new MutationObserver(function () { sync(currentTab()); }).observe(tabsRoot, {
        subtree: true,
        attributes: true,
        attributeFilter: ['class']
      });
    }
    if (tabFromUrl() === 'recruits-tab' || (document.getElementById('recruits-tab') && document.getElementById('recruits-tab').classList.contains('active'))) {
      setTimeout(function () { openTab('home-tab', 'replace'); }, 0);
    } else {
      sync(currentTab());
    }
    syncTop(null);

    ['fcc-record-label', 'fcc-rank-label', 'fcc-season-label'].forEach(function (id) {
      var el = document.getElementById(id);
      if (!el || typeof MutationObserver !== 'function') return;
      new MutationObserver(function () { syncTop(null); }).observe(el, {
        childList: true,
        characterData: true,
        subtree: true
      });
    });

    import('/js/shared/gobDensity.js').then(function (m) {
      m.bindGobDensity(document.documentElement);
    }).catch(function () {});
    import('/js/shared/gobSettings.js').catch(function () {});
    watchStickTop();
  }

  window.GOBShell = {
    sync: sync,
    syncTop: syncTop,
    syncRecord: function (data) {
      paintRecord(data || window.__gobCommandCenterData || null);
    },
    classifyTables: classifyTables,
    noteCommandCenter: noteCommandCenter,
    replaceRecruitingHub: replaceRecruitingHub,
    setRecruitingTabs: setRecruitingTabs
  };

  window.addEventListener('popstate', onRecruitingPop);

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

  function sectionFromReturn() {
    var q = new URLSearchParams(window.location.search);
    var tab = q.get('return_tab') || '';
    if (TAB_SECTION[tab] && TAB_SECTION[tab] !== DETAIL_SECTION.id) return TAB_SECTION[tab];
    var ret = q.get('return_url') || '';
    if (/practice-squad/.test(ret)) return 'team';
    if (/standings|rankings|schedule\.html|leaders|brackets/.test(ret)) return 'league';
    if (/recruiting\.html/.test(ret)) return 'recruiting';
    if (/news\.html|awards\.html/.test(ret)) return 'news';
    if (/training|game-plan|playbook|scout/.test(ret)) return 'prep';
    var viewed = q.get('team_id') || '';
    var owner = q.get('user_team_id') || '';
    if (owner && viewed && owner !== viewed) return 'league';
    return 'team';
  }

  function resolvePage() {
    var path = window.location.pathname || '';
    var spec = PAGES[path];
    if (!spec) return null;
    var q = new URLSearchParams(window.location.search);
    if (path === '/box-score.html') {
      if (q.get('return_url')) return { kind: 'browse', section: 'league', sub: '', keepBack: true };
      return { kind: 'focus' };
    }
    if (path === '/recruiting.html' && q.get('action') === 'run') return { kind: 'focus', file: 'recruiting' };
    if (path === '/game-plan.html' && (q.get('resume_from_timeout') === 'true' || q.get('mode') === 'tutorial')) {
      return { kind: 'focus', section: 'prep', sub: 'game-plan-tab' };
    }
    var out = {
      kind: spec.kind,
      section: spec.section,
      sub: spec.sub || '',
      file: spec.file || '',
      keepBack: !!spec.keepBack
    };
    if (out.file === 'recruiting') out.sub = hubFromUrl();
    if (out.section === 'context') out.section = sectionFromReturn();
    return out;
  }

  function syncPage() {
    if (!pageMode) return;
    var section = sectionById(pageMode.section || 'office');
    document.querySelectorAll('.rail [data-gob-section]').forEach(function (el) {
      el.classList.toggle('on', el.getAttribute('data-gob-section') === section.id);
    });
    if (titleEl) titleEl.textContent = section.title;
    paintedSection = '';
    if (pageMode.file === 'recruiting' && window.RecruitingHub && typeof window.RecruitingHub.rowVisible === 'function' && window.RecruitingHub.rowVisible() === false) {
      setRecruitingTabs(false);
      paintedSection = section.id;
      return;
    }
    var sub = pageMode.sub || '';
    if (pageMode.file === 'recruiting' && !sub && window.RecruitingHub && typeof window.RecruitingHub.current === 'function') {
      sub = window.RecruitingHub.current() || '';
      if (sub) {
        pageMode.sub = sub;
        replaceRecruitingHub(sub, { silent: true });
        paintedSection = section.id;
        return;
      }
    }
    renderSubtabs(section, sub);
    if (pageMode.file === 'recruiting' && window.RecruitingHub && typeof window.RecruitingHub.mountSearch === 'function') {
      window.RecruitingHub.mountSearch();
    }
    paintedSection = section.id;
  }

  function paintEmblem(data) {
    var slot = document.getElementById('fcc-header-emblem');
    var api = window.GOBTierEmblem;
    if (!slot || !api || !data || typeof api.tierForWeek !== 'function') return;
    var tier = api.tierForWeek(data.week);
    if (!tier) { slot.innerHTML = ''; return; }
    if (typeof api.injectCss === 'function') api.injectCss();
    var sz = api.EMBLEM_SIZING && api.EMBLEM_SIZING.fccFranchiseHeader;
    if (!sz || typeof api.renderLockup !== 'function') return;
    var value = null;
    if (tier === 'conference' && (data.user_conference === 0 || data.user_conference)) value = String(data.user_conference);
    if (tier === 'region') {
      if (data.user_region) value = String(data.user_region).toUpperCase();
      else {
        var c = Number(data.user_conference);
        if (c >= 1 && c <= 16) value = String.fromCharCode(65 + Math.floor((c - 1) / 2));
      }
    }
    slot.innerHTML = api.renderLockup({
      tier: tier,
      value: value,
      size: sz.emblem,
      l1: sz.labelL1,
      l2: sz.labelL2,
      variant: 'stack'
    });
  }

  function paintIdentity(data) {
    if (!data) return;
    var name = data.team || '';
    var logo = document.getElementById('team-logo');
    var topId = document.getElementById('gob-top-id');
    if (name && topId && !topId.getAttribute('aria-label')) topId.setAttribute('aria-label', name);
    if (logo && name) {
      if (!logo.alt) logo.alt = name;
      if (!logo.title) logo.title = name;
      if (!logo.getAttribute('src') && typeof getTeamAssetPath === 'function') {
        logo.src = getTeamAssetPath(name, 'banner_primary');
      }
    }
    paintEmblem(data);
  }

  function noteCommandCenter(data) {
    paintIdentity(data);
    if (pageMode && pageMode.file === 'recruiting' && window.GOBAdvance && window.GOBAdvance.ordersAreFocus(data)) {
      document.documentElement.classList.add('gob-focus');
    }
    document.documentElement.classList.remove('gob-pending');
  }

  function ensureExit() {
    if (document.getElementById('exit-franchise')) return;
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.id = 'exit-franchise';
    btn.hidden = true;
    btn.addEventListener('click', function () {
      import('/js/shared/uiSfx.js').then(function (m) { m.playSfx('x-back.mp3', 0.7); }).catch(function () {});
      import('/js/musicController.js').then(function (m) {
        if (m.clearFranchiseMusicState) m.clearFranchiseMusicState();
      }).catch(function () {});
      window.location.href = '/mode-select.html';
    });
    document.body.appendChild(btn);
  }

  function focusGear() {
    var gear = document.createElement('button');
    gear.type = 'button';
    gear.className = 'rail-i util';
    gear.id = 'gob-focus-settings';
    gear.title = 'Settings';
    gear.setAttribute('aria-expanded', 'false');
    gear.setAttribute('aria-label', 'Settings');
    gear.innerHTML = ICONS.settings;
    gear.addEventListener('click', function () {
      playClick();
      import('/js/shared/gobSettings.js').then(function () {
        if (window.GOBSettings && window.GOBSettings.toggle) window.GOBSettings.toggle();
      }).catch(function () {});
    });
    return gear;
  }

  function buildTop(withAdvance) {
    var top = document.createElement('header');
    top.className = 'top';
    var topId = document.createElement('a');
    topId.className = 'top-id';
    topId.href = '#';
    topId.id = 'gob-top-id';
    var logo = document.getElementById('team-logo');
    if (!logo) {
      logo = document.createElement('img');
      logo.id = 'team-logo';
      logo.alt = '';
    }
    topId.appendChild(logo);
    topId.addEventListener('click', function (event) {
      event.preventDefault();
      if (!pageMode) return;
      if (pageMode.section === 'team' && (pageMode.sub === 'roster-view' || pageMode.sub === 'roster-tab')) return;
      playClick();
      var href = fccHref('roster-view');
      var nav = window.GOBNav;
      if (pageMode.section === 'team') {
        if (nav && nav.replace) nav.replace(href);
        else window.location.replace(href);
      } else if (nav && nav.go) nav.go(href);
      else window.location.assign(href);
    });
    var divider = document.createElement('div');
    divider.className = 'top-div';
    var stats = document.createElement('div');
    stats.className = 'top-stats';
    stats.innerHTML = [
      '<div class="ts" id="gob-record-stat" hidden><b id="gob-record-value"></b><span>Record</span></div>',
      '<div class="ts" id="gob-rank-stat" hidden><b id="gob-rank-value"></b><span>National Rank</span></div>',
      '<div class="ts" id="gob-week-stat" hidden><b id="gob-week-value"></b><span id="gob-week-phase" hidden></span><span id="fcc-header-emblem"></span></div>'
    ].join('');
    var spacer = document.createElement('div');
    spacer.className = 'top-sp';
    top.appendChild(topId);
    top.appendChild(divider);
    top.appendChild(stats);
    top.appendChild(spacer);
    if (withAdvance) {
      var adv = document.createElement('div');
      adv.className = 'adv-wrap';
      var ghost = document.getElementById('fcc-edit-recruiting');
      if (!ghost) {
        ghost = document.createElement('button');
        ghost.type = 'button';
        ghost.id = 'fcc-edit-recruiting';
        ghost.style.display = 'none';
      }
      var play = document.getElementById('play-now');
      if (!play) {
        play = document.createElement('button');
        play.type = 'button';
        play.id = 'play-now';
        play.disabled = true;
      }
      play.classList.add('advance');
      play.setAttribute('data-sfx', 'SFX_ADVANCE');
      adv.appendChild(ghost);
      adv.appendChild(play);
      top.appendChild(adv);
    }
    top.appendChild(focusGear());
    return top;
  }

  function adoptMain(main) {
    var app = main.parentNode;
    var nodes = Array.prototype.slice.call(document.body.childNodes);
    nodes.forEach(function (node) {
      if (node === app) return;
      if (node.nodeType === 1 && node.tagName === 'SCRIPT') return;
      if (node.nodeType === 1 && node.id === 'site-footer') return;
      if (node.nodeType === 1 && node.classList && node.classList.contains('gob-modal-overlay')) return;
      main.appendChild(node);
    });
  }

  function syncStickTop() {
    var root = document.documentElement;
    var head = document.querySelector('html.gob-shell .pg-head');
    var top = 0;
    if (head && !root.classList.contains('gob-focus')) top = head.getBoundingClientRect().height;
    root.style.setProperty('--gob-stick-top', top + 'px');
    var row = 0;
    var first = document.querySelector('html.gob-shell .main thead tr:first-child th');
    var second = document.querySelector('html.gob-shell .main thead tr + tr th');
    if (first && second) row = first.getBoundingClientRect().height;
    root.style.setProperty('--gob-stick-row', row + 'px');
    document.querySelectorAll('html.gob-shell .main table').forEach(function (table) {
      var rowHead = table.querySelector('thead tr:first-child th');
      var rowNext = table.querySelector('thead tr + tr th');
      if (rowHead && rowNext) table.style.setProperty('--gob-stick-row', rowHead.getBoundingClientRect().height + 'px');
    });
    classifyTables();
  }

  function mainContentWidth(main) {
    var cs = getComputedStyle(main);
    return main.clientWidth - (parseFloat(cs.paddingLeft) || 0) - (parseFloat(cs.paddingRight) || 0);
  }

  function hostForTable(table) {
    var parent = table.parentElement;
    if (parent && (parent.classList.contains('gob-table-wrap') || parent.classList.contains('gob-wide-wrap'))) return parent;
    if (parent && parent.classList.contains('main')) return insertTableWrap(table);
    if (parent && parent.children.length === 1 && parent.children[0] === table) return parent;
    return insertTableWrap(table);
  }

  function insertTableWrap(table) {
    var wrap = document.createElement('div');
    wrap.className = 'gob-table-wrap';
    table.parentNode.insertBefore(wrap, table);
    wrap.appendChild(table);
    return wrap;
  }

  function intrinsicWidth(table) {
    var prevWidth = table.style.width;
    var prevMax = table.style.maxWidth;
    table.style.width = 'max-content';
    table.style.maxWidth = 'none';
    var width = table.scrollWidth;
    table.style.width = prevWidth;
    table.style.maxWidth = prevMax;
    return width;
  }

  function paintWideFade(wrap) {
    var hiddenRight = wrap.scrollWidth - wrap.clientWidth - wrap.scrollLeft > 1;
    var hiddenLeft = wrap.scrollLeft > 1;
    wrap.classList.toggle('is-fade-right', hiddenRight);
    wrap.classList.toggle('is-fade-left', hiddenLeft);
  }

  var classifying = false;
  var stickObserver = null;

  function classifyTables() {
    if (classifying) return;
    var main = document.querySelector('html.gob-shell .main');
    if (!main) return;
    classifying = true;
    var wide = [];
    try {
      var limit = mainContentWidth(main);
      Array.from(main.querySelectorAll('table')).forEach(function (table) {
        if (table.closest('.gob-settings-host, [role="dialog"]')) return;
        var wrap = hostForTable(table);
        var already = wrap.classList.contains('gob-wide-wrap');
        var sticksOut = !already && table.getBoundingClientRect().right > main.getBoundingClientRect().right + 1;
        var width = intrinsicWidth(table);
        var overflowInside = already && table.scrollWidth > wrap.clientWidth + 1;
        var isWide = width > limit + 1 || sticksOut || overflowInside;
        wrap.classList.toggle('gob-wide-wrap', isWide);
        if (isWide) {
          if (!wrap.__gobFade) {
            wrap.__gobFade = true;
            wrap.addEventListener('scroll', function () { paintWideFade(wrap); });
          }
          paintWideFade(wrap);
          wrap.dataset.gobTableWidth = String(width);
          wrap.dataset.gobWrapWidth = String(wrap.clientWidth);
          wide.push({
            id: table.id || String(table.className || '').slice(0, 80),
            table: width,
            wrap: wrap.clientWidth,
            main: Math.round(limit)
          });
        } else {
          wrap.classList.remove('is-fade-right', 'is-fade-left');
          delete wrap.dataset.gobTableWidth;
          delete wrap.dataset.gobWrapWidth;
        }
        if (stickObserver) {
          stickObserver.observe(table);
          stickObserver.observe(wrap);
        }
      });
    } finally {
      classifying = false;
    }
    window.__gobWideTables = wide;
  }

  function watchStickTop() {
    syncStickTop();
    if (window.__gobStickWatch) return;
    window.__gobStickWatch = true;
    var queued = false;
    function queueSync() {
      if (queued) return;
      queued = true;
      requestAnimationFrame(function () {
        queued = false;
        syncStickTop();
      });
    }
    if (typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', queueSync);
      return;
    }
    var observer = new ResizeObserver(queueSync);
    stickObserver = observer;
    var head = document.querySelector('html.gob-shell .pg-head');
    var main = document.querySelector('html.gob-shell .main');
    if (head) observer.observe(head);
    if (main) {
      observer.observe(main);
      if (typeof MutationObserver !== 'undefined') {
        new MutationObserver(queueSync).observe(main, { childList: true, subtree: true });
      }
    }
    window.addEventListener('resize', queueSync);
  }

  function finishShell() {
    watchStickTop();
    import('/js/shared/gobDensity.js').then(function (m) {
      m.bindGobDensity(document.documentElement);
      syncStickTop();
    }).catch(function () {});
    import('/js/shared/gobSettings.js').catch(function () {});
    import('/js/shared/tierEmblem.js').then(function () {
      refreshTournamentLock();
    }).catch(function () {});
    if (window.GOBAdvance && window.GOBAdvance.load) window.GOBAdvance.load();
  }

  function mountBrowse(spec) {
    if (document.querySelector('html.gob-shell .app')) return;
    pageMode = spec;
    document.documentElement.classList.add('gob', 'gob-shell');
    if (spec.keepBack) document.documentElement.setAttribute('data-gob-keep-back', '1');
    if (spec.file === 'recruiting') document.documentElement.classList.add('gob-pending');
    ensureExit();
    var app = document.createElement('div');
    app.className = 'app';
    var rail = document.createElement('nav');
    rail.className = 'rail';
    rail.setAttribute('aria-label', 'Franchise');
    var face = document.createElement('div');
    face.className = 'rail-face';
    SECTIONS.forEach(function (section) { face.appendChild(railButton(section)); });
    var spring = document.createElement('div');
    spring.className = 'rail-sp';
    face.appendChild(spring);
    var div = document.createElement('div');
    div.className = 'rail-div';
    face.appendChild(div);
    var tutorials = document.createElement('a');
    tutorials.className = 'rail-i util';
    tutorials.href = '/tutorial.html';
    tutorials.title = 'Tutorials';
    tutorials.innerHTML = ICONS.tutorials + '<span class="rail-l">Tutorials</span>';
    tutorials.addEventListener('click', function () { playClick(); });
    face.appendChild(tutorials);
    var feedback = utilButton('util', 'Feedback', 'feedback', 'gob-rail-feedback');
    feedback.addEventListener('click', function () {
      var existing = document.getElementById('feedback-btn');
      if (!existing) return;
      existing.click();
    });
    revealFeedbackWhenReady(feedback);
    face.appendChild(feedback);
    var settings = utilButton('util', 'Settings', 'settings', 'gob-rail-settings');
    settings.setAttribute('aria-expanded', 'false');
    settings.addEventListener('click', function () {
      playClick();
      import('/js/shared/gobSettings.js').then(function () {
        if (window.GOBSettings && window.GOBSettings.toggle) window.GOBSettings.toggle();
      }).catch(function () {});
    });
    face.appendChild(settings);
    var quiet = document.createElement('div');
    quiet.className = 'rail-div q';
    face.appendChild(quiet);
    var exitBtn = utilButton('exit', 'Exit Franchise', 'exit', 'gob-rail-exit');
    exitBtn.addEventListener('click', function () {
      var existing = document.getElementById('exit-franchise');
      if (existing) existing.click();
    });
    face.appendChild(exitBtn);
    rail.appendChild(face);
    var main = document.createElement('div');
    main.className = 'main scroll';
    main.id = 'gob-main';
    var head = document.createElement('div');
    head.className = 'pg-head';
    var titleRow = document.createElement('div');
    titleRow.className = 'pg-title';
    titleEl = document.createElement('h1');
    titleRow.appendChild(titleEl);
    subtabHost = document.createElement('div');
    subtabHost.className = 'nav-row';
    subtabHost.id = 'gob-subtabs';
    head.appendChild(titleRow);
    head.appendChild(subtabHost);
    main.appendChild(head);
    app.appendChild(buildTop(true));
    app.appendChild(rail);
    app.appendChild(main);
    document.body.insertBefore(app, document.body.firstChild);
    adoptMain(main);
    syncPage();
    syncTop(null);
    var play = document.getElementById('play-now');
    if (play && window.GOBAdvance) window.GOBAdvance.bind(play, function () {
      return window.GOBAdvance.browseEnv(window.__gobCommandCenterData || null);
    });
    finishShell();
  }

  function mountFocus(spec) {
    if (document.querySelector('html.gob-shell .app')) return;
    pageMode = spec || { kind: 'focus' };
    document.documentElement.classList.add('gob', 'gob-shell', 'gob-focus');
    var app = document.createElement('div');
    app.className = 'app';
    var main = document.createElement('div');
    main.className = 'main scroll';
    main.id = 'gob-main';
    app.appendChild(buildTop(false));
    app.appendChild(main);
    document.body.insertBefore(app, document.body.firstChild);
    adoptMain(main);
    syncTop(null);
    finishShell();
  }

  function boot() {
    if (document.getElementById('franchise-container')) {
      var prepTab = '';
      try { prepTab = new URLSearchParams(window.location.search).get('tab') || ''; }
      catch (err) { prepTab = ''; }
      var tab = '';
      try {
        tab = window.FranchiseContext && typeof window.FranchiseContext.get === 'function'
          ? (window.FranchiseContext.get('tab') || '') : prepTab;
      } catch (err) { tab = prepTab; }
      if (tab === 'training-report-view') {
        var bag = null;
        try {
          if (window.FranchiseContext && typeof window.FranchiseContext.toSearchParams === 'function') {
            bag = window.FranchiseContext.toSearchParams();
          }
        } catch (err) { bag = null; }
        if (bag) bag.delete('tab');
        var qs = bag ? bag.toString() : '';
        window.location.replace('/training-report.html' + (qs ? '?' + qs : ''));
        return;
      }
      mount();
      return;
    }
    var spec = resolvePage();
    if (!spec) return;
    if (spec.kind === 'focus') mountFocus(spec);
    else mountBrowse(spec);
  }
})();
