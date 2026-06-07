/* ===========================================================
   GOB Tutorial Experience — shared behavior
   - Smart back button (returns to where the user entered from)
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
      var fromTutorial = ref && /tutorial|player-attributes|tutorial-training|team-attributes|tutorial-recruiting/i.test(ref);
      // Only set origin if we arrived from OUTSIDE the tutorial and none stored yet
      if (ref && !fromTutorial && !sessionStorage.getItem(ORIGIN_KEY)) {
        sessionStorage.setItem(ORIGIN_KEY, ref);
      }
    } catch (e) {}
  }
  function goBack() {
    playSound('x-back.mp3');
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

  /* ---- wire up on DOM ready ---- */
  function init() {
    rememberOrigin();
    renderNav();
    var back = document.querySelector('[data-gob-back]');
    if (back) back.addEventListener('click', goBack);
  }

  /* ---- modal builder (used by future per-topic / contextual tips) ---- */
  GOB.showTip = function (opts) {
    opts = opts || {};
    var topicId = opts.id || 'generic';
    var overlay = document.createElement('div');
    overlay.className = 'gob-modal-overlay';
    overlay.innerHTML =
      '<div class="gob-modal" role="dialog" aria-modal="true" aria-label="Tutorial tip">' +
        '<button class="gob-modal-x" aria-label="Close">&times;</button>' +
        '<div class="gob-modal-head">' +
          '<img class="gob-modal-avatar" src="' + (opts.avatar || '/images/sammy_tutorial.png') + '" alt="Coach Sammy">' +
          '<div>' +
            '<div class="gob-modal-kicker">' + (opts.kicker || 'Coach Sammy') + '</div>' +
            '<div class="gob-modal-title">' + (opts.title || 'There’s a tutorial for that') + '</div>' +
          '</div>' +
        '</div>' +
        '<p class="gob-modal-body">' + (opts.body || '') + '</p>' +
        '<div class="gob-modal-actions">' +
          '<a class="btn btn-primary gob-modal-go" href="' + (opts.href || '#') + '">' + (opts.cta || 'Show me') + '</a>' +
          '<button class="btn btn-ghost gob-modal-later">Maybe later</button>' +
        '</div>' +
        '<button class="gob-modal-mute">Got it — don’t remind me about ' + (opts.topicLabel || 'this') + '</button>' +
      '</div>';
    document.body.appendChild(overlay);
    requestAnimationFrame(function () { overlay.classList.add('open'); });

    function close() { overlay.classList.remove('open'); setTimeout(function () { overlay.remove(); }, 220); }
    overlay.querySelector('.gob-modal-x').addEventListener('click', close);
    overlay.querySelector('.gob-modal-later').addEventListener('click', close);
    overlay.addEventListener('click', function (e) { if (e.target === overlay) close(); });
    overlay.querySelector('.gob-modal-mute').addEventListener('click', function () { GOB.mute(topicId); close(); });
    return close;
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
