/**
 * Franchise shell for franchise-command-center.html.
 * Rail section clicks push a history entry. Sub-tabs and the Stats toggle replace.
 * Does not run on the tournament command center or the live-game court.
 */
(function () {
  'use strict';

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
      { id: 'roster-tab', label: 'Roster' },
      { id: 'player-stats-tab', label: 'Stats' },
      { id: 'team-stats-tab', label: 'Development' },
      { id: 'practice-squad', label: 'Practice Squad', link: 'practice' }
    ]},
    { id: 'prep', label: 'Prep', title: 'Prep', icon: 'prep', tabs: [
      { id: 'training-tab', label: 'Training' },
      { id: 'lineup', label: 'Lineup', link: 'lineup' },
      { id: 'game-plan-tab', label: 'Game Plan' },
      { id: 'playbooks-tab', label: 'Playbooks' },
      { id: 'coaches-tab', label: 'Scouting' }
    ]},
    { id: 'league', label: 'League', title: 'League', icon: 'league', tabs: [
      { id: 'standings-tab', label: 'Standings' },
      { id: 'schedule-tab', label: 'Schedule & Results' },
      { id: 'rankings', label: 'Rankings', link: 'rankings' },
      { id: 'awards-tab', label: 'Leaders' },
      { id: 'brackets', label: 'Brackets', link: 'brackets' }
    ]},
    { id: 'recruiting', label: 'Recruiting', title: 'Recruiting', icon: 'recruiting', tabs: [{ id: 'recruits-tab' }] },
    { id: 'news', label: 'News', title: 'News', icon: 'news', tabs: [
      { id: 'press-tab', label: 'News' },
      { id: 'awards-page', label: 'Awards', link: 'awards' }
    ]}
  ];

  var TAB_SECTION = {
    'home-tab': 'office',
    'roster-tab': 'team',
    'player-stats-tab': 'team',
    'fcc-team-stats-summary-tab': 'team',
    'team-stats-tab': 'team',
    'training-tab': 'prep',
    'game-plan-tab': 'prep',
    'playbooks-tab': 'prep',
    'coaches-tab': 'prep',
    'standings-tab': 'league',
    'schedule-tab': 'league',
    'awards-tab': 'league',
    'recruits-tab': 'recruiting',
    'press-tab': 'news'
  };

  var sectionEls = {};
  var subtabHost = null;
  var titleEl = null;
  var toggleEl = null;
  var paintedSection = '';

  function sectionById(id) {
    for (var i = 0; i < SECTIONS.length; i++) {
      if (SECTIONS[i].id === id) return SECTIONS[i];
    }
    return SECTIONS[0];
  }

  function currentTab() {
    var active = document.querySelector('#tournament-tabs > .tab-content.active');
    return active ? active.id : 'home-tab';
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
      || hrefOf(document.getElementById('resources-rankings'));
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
    if (kind === 'lineup') {
      var line = document.querySelector('a[href*="set-lineup.html"]');
      return hrefOf(line);
    }
    return '';
  }

  function goLink(kind) {
    var href = linkHref(kind);
    if (!href) return;
    playClick();
    if (window.GOBNav && typeof window.GOBNav.go === 'function') window.GOBNav.go(href);
    else window.location.assign(href);
  }

  function labeledTabs(section) {
    return section.tabs.filter(function (tab) { return tab.label; });
  }

  function renderSubtabs(section, tab) {
    if (!subtabHost) return;
    var tabs = labeledTabs(section);
    if (toggleEl && toggleEl.parentNode) toggleEl.parentNode.removeChild(toggleEl);
    subtabHost.innerHTML = '';
    if (!tabs.length) {
      subtabHost.hidden = true;
      return;
    }
    subtabHost.hidden = false;
    tabs.forEach(function (item) {
      var el;
      if (item.link) {
        el = document.createElement('a');
        el.href = '#';
        el.className = 'stab';
        el.dataset.link = item.link;
        el.addEventListener('click', function (event) {
          event.preventDefault();
          goLink(item.link);
        });
      } else {
        el = document.createElement('button');
        el.type = 'button';
        el.className = 'stab';
        el.dataset.tab = item.id;
        el.addEventListener('click', function () {
          if (currentTab() === item.id) return;
          playClick();
          openTab(item.id, 'replace');
        });
      }
      el.textContent = item.label;
      subtabHost.appendChild(el);
      if (item.id === 'player-stats-tab' && toggleEl) subtabHost.appendChild(toggleEl);
    });
    markSubtabs(tab);
  }

  function markSubtabs(tab) {
    if (!subtabHost) return;
    var statsOn = tab === 'player-stats-tab' || tab === 'fcc-team-stats-summary-tab';
    subtabHost.querySelectorAll('.stab').forEach(function (el) {
      var on = el.dataset.tab === tab || (statsOn && el.dataset.tab === 'player-stats-tab');
      el.classList.toggle('on', !!on);
    });
    if (toggleEl) {
      var showToggle = statsOn;
      toggleEl.hidden = !showToggle;
      toggleEl.querySelectorAll('button').forEach(function (btn) {
        btn.classList.toggle('on', btn.dataset.tab === tab);
      });
    }
  }

  function sync(tab) {
    var sectionId = TAB_SECTION[tab] || 'office';
    var section = sectionById(sectionId);
    Object.keys(sectionEls).forEach(function (id) {
      if (sectionEls[id]) sectionEls[id].classList.toggle('on', id === sectionId);
    });
    if (titleEl) titleEl.textContent = section.title;
    if (paintedSection !== sectionId) {
      renderSubtabs(section, tab);
      paintedSection = sectionId;
    } else {
      markSubtabs(tab);
    }
  }

  function railButton(section) {
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'rail-i';
    btn.dataset.gobSection = section.id;
    btn.title = section.label;
    btn.innerHTML = ICONS[section.icon] + '<span>' + section.label + '</span>';
    if (section.id === 'recruiting') btn.id = 'gob-rail-recruiting';
    btn.addEventListener('click', function () {
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

  function utilButton(className, title, icon, id) {
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'rail-i ' + className;
    btn.title = title;
    if (id) btn.id = id;
    btn.innerHTML = ICONS[icon] + '<span>' + title + '</span>';
    return btn;
  }

  function paintRecord() {
    var source = document.getElementById('fcc-record-label');
    var valueEl = document.getElementById('gob-record-value');
    var wrap = document.getElementById('gob-record-stat');
    if (!valueEl || !wrap) return;
    var text = source ? String(source.textContent || '') : '';
    var cut = text.indexOf(':');
    var value = (cut === -1 ? text : text.slice(cut + 1)).trim();
    if (!value) {
      wrap.hidden = true;
      return;
    }
    wrap.hidden = false;
    valueEl.textContent = value;
  }

  function paintRank() {
    var source = document.getElementById('fcc-rank-label');
    var valueEl = document.getElementById('gob-rank-value');
    var wrap = document.getElementById('gob-rank-stat');
    if (!valueEl || !wrap) return;
    var text = source ? String(source.textContent || '') : '';
    var match = text.match(/(\d+)/);
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
    if (!n) {
      wrap.hidden = true;
      if (top) {
        top.classList.remove('is-tier');
        top.style.removeProperty('--tier-metal');
        top.style.removeProperty('--tier-metal-hi');
      }
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
  }

  function weekFromLabel() {
    var source = document.getElementById('fcc-season-label');
    var match = String((source && source.textContent) || '').match(/Week\s+(\d+)/i);
    return match ? Number(match[1]) : 0;
  }

  function syncTop(data) {
    paintRecord();
    paintRank();
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
    var name = document.createElement('span');
    name.className = 'top-name';
    name.id = 'gob-top-name';
    if (logo) topId.appendChild(logo);
    topId.appendChild(name);
    topId.addEventListener('click', function (event) {
      event.preventDefault();
      var tab = currentTab();
      if (tab === 'roster-tab') return;
      playClick();
      var mode = (TAB_SECTION[tab] || 'office') === 'team' ? 'replace' : 'push';
      openTab('roster-tab', mode);
    });

    var divider = document.createElement('div');
    divider.className = 'top-div';

    var stats = document.createElement('div');
    stats.className = 'top-stats';
    stats.innerHTML = [
      '<div class="ts" id="gob-record-stat" hidden><b id="gob-record-value"></b><span>Record</span></div>',
      '<div class="ts" id="gob-rank-stat" hidden><b id="gob-rank-value"></b><span>National</span></div>',
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
    tutorials.innerHTML = ICONS.tutorials + '<span>Tutorials</span>';
    tutorials.addEventListener('click', function () { playClick(); });
    face.appendChild(tutorials);

    var feedback = utilButton('util', 'Feedback', 'feedback', 'gob-rail-feedback');
    feedback.addEventListener('click', function () {
      var existing = document.getElementById('feedback-btn');
      if (!existing) return;
      playClick();
      existing.click();
    });
    if (window.GOB_BUILD_PROFILE === 'desktop') feedback.hidden = true;
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
    toggleEl = document.createElement('div');
    toggleEl.className = 'stats-toggle';
    toggleEl.id = 'gob-stats-toggle';
    toggleEl.hidden = true;
    [['player-stats-tab', 'Players'], ['fcc-team-stats-summary-tab', 'Team']].forEach(function (pair) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.dataset.tab = pair[0];
      btn.textContent = pair[1];
      btn.addEventListener('click', function () {
        if (currentTab() === pair[0]) return;
        playClick();
        openTab(pair[0], 'replace');
      });
      toggleEl.appendChild(btn);
    });
    subtabHost = document.createElement('div');
    subtabHost.className = 'subtabs';
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
      if (tab) sync(tab);
    });
    sync(currentTab());
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
  }

  window.GOBShell = {
    sync: sync,
    syncTop: syncTop,
    syncRecord: paintRecord
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount);
  } else {
    mount();
  }
})();
