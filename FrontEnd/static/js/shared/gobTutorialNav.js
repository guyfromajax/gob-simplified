/* ===========================================================
   GOB Tutorial Experience — shared behavior
   - Sub-page back button -> Tutorial Home (/tutorial.html)
   - Hub back button -> where the user entered from (or history / hub fallback)
   - Persistent bottom nav (active state + in-page smart scroll)
   - Per-topic progress (localStorage)  -> window.GOB
   - Contextual tip modal + per-topic mute (for future sub-pages)
   =========================================================== */
(function () {
  'use strict';

  var SEEN_KEY = 'gob_tut_seen';
  var MUTE_KEY = 'gob_tut_muted';
  var ORIGIN_KEY = 'gob_tut_origin';

  var HUB = '/tutorial.html';

  function isTutorialHub() {
    return /\/tutorial\.html$/i.test(location.pathname);
  }

  /* ---- sound hook (repo pattern: inline playSound over /sounds/) ---- */
  function playSound(filename) {
    try {
      var a = new Audio('/sounds/' + encodeURIComponent(filename));
      a.volume = 0.5;
      a.play().catch(function () {});
    } catch (e) {}
  }

  /* ---- storage helpers ---- */
  function load(key) { try { return JSON.parse(localStorage.getItem(key)) || []; } catch (e) { return []; } }
  function save(key, v) { try { localStorage.setItem(key, JSON.stringify(v)); } catch (e) {} }

  var GOB = window.GOB = window.GOB || {};
  GOB.playSound = playSound;
  GOB.seen = function () { return load(SEEN_KEY); };
  GOB.isSeen = function (id) { return load(SEEN_KEY).indexOf(id) !== -1; };
  GOB.markSeen = function (id) {
    var s = load(SEEN_KEY);
    if (s.indexOf(id) === -1) { s.push(id); save(SEEN_KEY, s); }
    window.dispatchEvent(new CustomEvent('gob:progress', { detail: { id: id } }));
  };
  GOB.unseenAll = function () { save(SEEN_KEY, []); window.dispatchEvent(new CustomEvent('gob:progress', {})); };
  GOB.isMuted = function (id) { return load(MUTE_KEY).indexOf(id) !== -1; };
  GOB.mute = function (id) { var m = load(MUTE_KEY); if (m.indexOf(id) === -1) { m.push(id); save(MUTE_KEY, m); } };

  /* ---- smart back: remember external entry point ---- */
  function rememberOrigin() {
    try {
      var ref = document.referrer;
      // any in-tutorial page (hub + per-topic sub-pages); extend as sub-pages ship
      var fromTutorial = ref && /tutorial|player-attributes|tutorial-training|team-attributes|tutorial-recruiting|tutorial-playbooks|game-plans|scouting/i.test(ref);
      // Only set origin if we arrived from OUTSIDE the tutorial and none stored yet
      if (ref && !fromTutorial && !sessionStorage.getItem(ORIGIN_KEY)) {
        sessionStorage.setItem(ORIGIN_KEY, ref);
      }
    } catch (e) {}
  }
  function goBack() {
    playSound('x-back.mp3');
    if (!isTutorialHub()) {
      location.href = HUB;
      return;
    }
    var origin = sessionStorage.getItem(ORIGIN_KEY);
    if (origin) { location.href = origin; return; }
    if (window.history.length > 1) { window.history.back(); return; }
    location.href = HUB;
  }

  /* ---- icon library (shared) ---- */
  var ICONS = {
    home: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V20h14V9.5"/><path d="M9.5 20v-5h5v5"/></svg>',
    player: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="7.5" r="3.3"/><path d="M5.5 20c0-3.6 2.9-6.2 6.5-6.2S18.5 16.4 18.5 20"/></svg>',
    team: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><circle cx="8.5" cy="8" r="2.7"/><circle cx="16" cy="9" r="2.3"/><path d="M3.5 19c0-2.9 2.2-5 5-5 1.8 0 3.3.9 4.2 2.3"/><path d="M13.5 19c.3-2.3 1.9-3.7 3.9-3.7 1.8 0 3.4 1.3 3.6 3.7"/></svg>',
    strategy: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M5 4.5h14a1 1 0 0 1 1 1V20a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5.5a1 1 0 0 1 1-1Z"/><path d="M8.5 3v3M15.5 3v3"/><path d="M8 11.5l2.3 2.3L16 8.5"/></svg>',
    training: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M6.5 8v8M17.5 8v8M3.5 10v4M20.5 10v4M6.5 12h11"/></svg>',
    recruiting: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><circle cx="9.5" cy="8" r="3.1"/><path d="M3.8 20c0-3.3 2.6-5.6 5.7-5.6 1.4 0 2.7.5 3.7 1.3"/><path d="M17.5 13.5v6M14.5 16.5h6"/></svg>',
    playbook: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M5 4h9l5 5v11H5z"/><path d="M13.5 4v5H19"/><path d="M8.5 13h7M8.5 16.5h5"/></svg>',
    sliders: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M5 7h14M5 12h14M5 17h14"/><circle cx="9" cy="7" r="2" fill="#fff"/><circle cx="15" cy="12" r="2" fill="#fff"/><circle cx="8" cy="17" r="2" fill="#fff"/></svg>',
    scout: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><circle cx="7.5" cy="13" r="3.3"/><circle cx="16.5" cy="13" r="3.3"/><path d="M10.8 12c.4-.6 2-.6 2.4 0"/><path d="M4.5 10 7 6.5h10L19.5 10"/></svg>',
    shield: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3.5 19 6v5.5c0 4.3-2.9 7.4-7 8.9-4.1-1.5-7-4.6-7-8.9V6z"/><path d="M9 11.5l2.2 2.2L15.5 9.5"/></svg>'
  };
  GOB.icons = ICONS;

  /* Bottom nav: Home -> hub top; categories -> their section anchor on the hub */
  var NAV = [
    { id: 'home', label: 'Tutorial Home', icon: ICONS.home, href: HUB },
    { id: 'players', label: 'Players', icon: ICONS.player, href: HUB + '#cat-players' },
    { id: 'training', label: 'Training', icon: ICONS.training, href: HUB + '#cat-training' },
    { id: 'team', label: 'Team', icon: ICONS.team, href: HUB + '#cat-team' },
    { id: 'strategy', label: 'Strategy', icon: ICONS.strategy, href: HUB + '#cat-strategy' }
  ];

  function smoothScrollTo(el) {
    if (!el) return;
    window.scrollTo({ top: el.getBoundingClientRect().top + window.pageYOffset - 80, behavior: 'smooth' });
  }

  function renderNav() {
    var wrap = document.getElementById('bottomnav');
    if (!wrap) return;
    var active = document.body.getAttribute('data-gob-nav');
    wrap.innerHTML = NAV.map(function (n) {
      return '<a class="gob-navbtn ' + n.id + (n.id === active ? ' active' : '') + '" data-nav="' + n.id + '" href="' + n.href + '">' +
        '<span class="ico">' + n.icon + '</span><span class="lbl">' + n.label + '</span></a>';
    }).join('');

    wrap.addEventListener('click', function (e) {
      var btn = e.target.closest('.gob-navbtn');
      if (!btn) return;
      playSound('click-tiny.wav');
      // if the target lives on this page (a #anchor on the hub), scroll smoothly
      var href = btn.getAttribute('href') || '';
      var hash = href.indexOf('#') !== -1 ? href.slice(href.indexOf('#')) : '';
      var onHub = /tutorial\.html(#|$)/.test(href) || href === HUB || href.charAt(0) === '#';
      if (onHub) {
        var target = hash ? document.querySelector(hash) : document.querySelector('.gob-shell');
        if (target) { e.preventDefault(); smoothScrollTo(target); if (hash) history.replaceState(null, '', hash); }
      }
    });
  }

  function isLessonSubPage() {
    return /\/(player-attributes|tutorial-training|team-attributes|game-plans|tutorial-playbooks|scouting|tutorial-recruiting)\.html$/i.test(location.pathname || '');
  }

  function loadAlertResumeScript() {
    if (!isLessonSubPage() || document.querySelector('script[src*="gobTutorialAlertResume.js"]')) return;
    var s = document.createElement('script');
    s.src = '/js/shared/gobTutorialAlertResume.js';
    document.body.appendChild(s);
  }

  /* ---- wire up on DOM ready ---- */
  function init() {
    rememberOrigin();
    renderNav();
    loadAlertResumeScript();
    var back = document.querySelector('[data-gob-back]');
    if (back) {
      if (!isTutorialHub()) {
        back.innerHTML = '<span class="chev">‹</span> Back To Tutorial Home';
      }
      back.addEventListener('click', goBack);
    }
  }

  /* ---- whistle glyph (rail mark) ---- */
  var WHISTLE_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="9" cy="14" r="6"></circle><path d="M15 11l6-3-1.2 4.2"></path><path d="M9 8V5h4"></path></svg>';

  /* ---- premium coach-card alert (full-screen takeover; serves all 7 lessons) ---- */
  function showAlertCard(opts) {
    var lessonNum = parseInt(opts.lessonIndex, 10) || 1;
    var lessonTotal = parseInt(opts.lessonTotal, 10) || 7;
    var portrait = opts.portrait || '/images/sammy_tutorial.png';

    var dots = '';
    for (var i = 0; i < lessonTotal; i++) {
      var cls = i < lessonNum - 1 ? ' class="done"' : (i === lessonNum - 1 ? ' class="on"' : '');
      dots += '<i' + cls + '></i>';
    }

    var overlay = document.createElement('div');
    overlay.className = 'gob-talert-overlay is-entering';
    overlay.innerHTML =
      '<div class="gob-talert" role="dialog" aria-modal="true" aria-labelledby="gob-talert-title">' +
        '<button class="gob-talert-close" aria-label="Close">✕</button>' +
        '<div class="gob-talert-rail">' +
          '<span class="gob-talert-mark">' + WHISTLE_SVG + 'Tutorial</span>' +
          '<span class="gob-talert-id">' +
            '<span class="gob-talert-portrait"><img src="' + portrait + '" alt="Coach Sammy"></span>' +
            '<span class="gob-talert-coach">Coach Sammy</span>' +
          '</span>' +
          '<span class="gob-talert-progress">' +
            '<span class="gob-talert-num">Lesson ' + lessonNum + ' of ' + lessonTotal + '</span>' +
            '<span class="gob-talert-dots">' + dots + '</span>' +
          '</span>' +
        '</div>' +
        '<div class="gob-talert-content">' +
          '<h2 class="gob-talert-title" id="gob-talert-title"></h2>' +
          '<p class="gob-talert-text"></p>' +
          '<div class="gob-talert-actions">' +
            '<a class="gob-talert-btn gob-talert-btn-primary" href="' + (opts.href || '#') + '">' + (opts.cta || 'Start lesson') + '</a>' +
            '<button class="gob-talert-btn gob-talert-btn-ghost" type="button">' + (opts.laterLabel || 'I’ll do this later') + '</button>' +
          '</div>' +
        '</div>' +
      '</div>';

    /* textContent (not innerHTML) for copy — avoids markup injection from config */
    overlay.querySelector('.gob-talert-title').textContent = opts.title || '';
    overlay.querySelector('.gob-talert-text').textContent = opts.body || '';

    document.body.appendChild(overlay);
    /* drop is-entering once the entrance finishes so the resting state is plain */
    function clearEntering() { overlay.classList.remove('is-entering'); }
    overlay.addEventListener('animationend', clearEntering);
    setTimeout(clearEntering, 800);

    var done = false;
    function close(started) {
      if (done) return;
      done = true;
      overlay.classList.add('is-leaving');
      setTimeout(function () { if (overlay.parentNode) overlay.parentNode.removeChild(overlay); }, 250);
      if (started) { if (typeof opts.onGo === 'function') opts.onGo(); }
      else if (typeof opts.onLater === 'function') opts.onLater();
    }

    overlay.querySelector('.gob-talert-close').addEventListener('click', function () { close(false); });
    overlay.querySelector('.gob-talert-btn-ghost').addEventListener('click', function () { close(false); });
    overlay.addEventListener('click', function (e) { if (e.target === overlay) close(false); });
    var go = overlay.querySelector('.gob-talert-btn-primary');
    go.addEventListener('click', function (e) {
      e.preventDefault();
      close(true);
      if (opts.href && opts.href !== '#') window.location.href = opts.href;
    });

    return function () { close(false); };
  }

  /* ---- modal builder (tutorial tips + contextual alerts) ---- */
  GOB.showTip = function (opts) {
    opts = opts || {};
    if (opts.alertMode) return showAlertCard(opts);
    var topicId = opts.id || 'generic';
    var alertMode = !!opts.alertMode;
    var overlay = document.createElement('div');
    overlay.className = 'gob-modal-overlay gob-tip-overlay';
    overlay.innerHTML =
      '<div class="gob-modal" role="dialog" aria-modal="true" aria-label="Tutorial tip">' +
        '<button class="gob-modal-x" aria-label="Close">&times;</button>' +
        '<div class="gob-modal-head">' +
          '<img class="gob-modal-avatar" src="' + (opts.avatar || '/images/sammy_tutorial.png') + '" alt="Coach Sammy">' +
          '<div>' +
            '<div class="gob-modal-kicker">' + (opts.kicker || 'Coach Sammy') + '</div>' +
            '<div class="gob-modal-title">' + (opts.title || 'There\u2019s a tutorial for that') + '</div>' +
          '</div>' +
        '</div>' +
        '<p class="gob-modal-body">' + (opts.body || '') + '</p>' +
        '<div class="gob-modal-actions">' +
          '<a class="btn btn-primary gob-modal-go" href="' + (opts.href || '#') + '">' + (opts.cta || (alertMode ? 'Tutorials' : 'Show me')) + '</a>' +
          '<button class="btn btn-ghost gob-modal-later" type="button">' + (opts.laterLabel || (alertMode ? 'I\u2019ll Do This Later' : 'Maybe later')) + '</button>' +
        '</div>' +
        (alertMode ? '' : ('<button class="gob-modal-mute" type="button">Got it \u2014 don\u2019t remind me about ' + (opts.topicLabel || 'this') + '</button>')) +
      '</div>';
    document.body.appendChild(overlay);
    requestAnimationFrame(function () { overlay.classList.add('open'); });

    function dismissLater() {
      overlay.classList.remove('open');
      setTimeout(function () { overlay.remove(); }, 220);
      if (typeof opts.onLater === 'function') opts.onLater();
    }
    function dismissGo(e) {
      if (e) e.preventDefault();
      overlay.classList.remove('open');
      setTimeout(function () { overlay.remove(); }, 220);
      if (typeof opts.onGo === 'function') opts.onGo();
      if (opts.href && opts.href !== '#') window.location.href = opts.href;
    }

    overlay.querySelector('.gob-modal-x').addEventListener('click', dismissLater);
    overlay.querySelector('.gob-modal-later').addEventListener('click', dismissLater);
    overlay.addEventListener('click', function (e) { if (e.target === overlay) dismissLater(); });
    var go = overlay.querySelector('.gob-modal-go');
    if (go) go.addEventListener('click', dismissGo);
    var mute = overlay.querySelector('.gob-modal-mute');
    if (mute) {
      mute.addEventListener('click', function () { GOB.mute(topicId); dismissLater(); });
    }
    return dismissLater;
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
