/* ===========================================================
   GOB Tutorial Hub — data, rendering, progress, toast
   IA: Players / Team / Strategy / Training

   Dead this pass: topic tiles with no LIVE page toast on click.
   Sub-pages call GOB.markSeen('<topic-id>') on load and progress / Continue / explored-✓ update automatically.
   =========================================================== */
(function () {
  'use strict';
  var I = (window.GOB && window.GOB.icons) || {};
  function sfx(f) { if (window.GOB && window.GOB.playSound) window.GOB.playSound(f); }

  /* ---- category + topic model ---- */
  // Grid fills left-to-right, top-to-bottom, so array order sets the layout:
  //   Players  | Training
  //   Team     | Strategy
  var CATS = [
    { id: 'players', name: 'Players', icon: I.player, topics: [
      { id: 'player-attributes', name: 'Player Attributes', icon: I.player }
    ]},
    { id: 'training', name: 'Training', icon: I.training, topics: [
      { id: 'training', name: 'Training', icon: I.training }
    ]},
    { id: 'team', name: 'Team', icon: I.team, topics: [
      { id: 'team-attributes', name: 'Team Attributes', icon: I.shield },
      { id: 'recruiting', name: 'Recruiting', icon: I.recruiting }
    ]},
    { id: 'strategy', name: 'Strategy', icon: I.strategy, topics: [
      { id: 'game-plans', name: 'Game Plans', icon: I.sliders },
      { id: 'playbooks', name: 'Playbooks', icon: I.playbook },
      { id: 'scouting', name: 'Scouting', icon: I.scout }
    ]}
  ];

  // progress denominator excludes TBD topics (none flagged this pass -> 7)
  var LEARNABLE = [];
  CATS.forEach(function (c) { c.topics.forEach(function (t) { if (t.tag !== 'tbd') LEARNABLE.push(t.id); }); });
  var TOTAL = LEARNABLE.length;

  var ADVANCED_TOPICS = [
    { id: 'momentum', name: 'Momentum', href: '/tutorial-advanced-momentum.html', available: true },
    { id: 'presses-traps', name: 'Presses & Traps', href: '/tutorial-advanced-press-trap.html', available: true },
    { id: 'practice-squad', name: 'Practice Squad', href: '/tutorial-advanced-practice-squads.html', available: true }
  ];
  var ADVANCED_TOTAL = ADVANCED_TOPICS.length;

  // recommended learning order for the “next up” cue
  var ORDER = ['player-attributes', 'training', 'team-attributes', 'game-plans', 'playbooks', 'scouting', 'recruiting'];
  // topics whose sub-page exists this pass → real links; everything else is dead (toast)
  var LIVE = { 'player-attributes': '/tutorial-player-attributes.html', 'training': '/tutorial-training.html', 'team-attributes': '/tutorial-team-attributes.html', 'recruiting': '/tutorial-recruiting.html', 'game-plans': '/tutorial-game-plans.html', 'playbooks': '/tutorial-playbooks.html', 'scouting': '/tutorial-scouting.html' };
  function catOf(id) { var f = CATS.find(function (c) { return c.topics.some(function (t) { return t.id === id; }); }); return f ? f.id : 'players'; }
  function topicOf(id) { var t; CATS.forEach(function (c) { c.topics.forEach(function (x) { if (x.id === id) t = x; }); }); return t; }
  function nextLesson() {
    var seen = (window.GOB ? window.GOB.seen() : []);
    var id = ORDER.find(function (x) { return seen.indexOf(x) === -1; });
    if (!id) return null; // all explored
    return { id: id, name: topicOf(id).name, cat: catOf(id) };
  }
  function updateNext() {
    var nx = nextLesson();
    var wrap = document.getElementById('continue-wrap');
    var link = document.getElementById('continue-link');
    var nameEl = document.getElementById('continue-name');
    if (!wrap || !link) return;

    if (nx) {
      if (nameEl) nameEl.textContent = nx.name;
      wrap.hidden = false;
      if (LIVE[nx.id]) {
        link.setAttribute('href', LIVE[nx.id]);
        link.removeAttribute('data-target');
      } else {
        link.setAttribute('href', '#cat-' + nx.cat);
        link.dataset.target = nx.id;
      }
    } else {
      wrap.hidden = true;
      link.removeAttribute('data-target');
    }
  }

  /* ---- category grid ---- */
  function renderCats() {
    var host = document.getElementById('cats');
    if (!host) return;
    host.innerHTML = CATS.map(function (c) {
      var tiles = c.topics.map(function (t) {
        var isTbd = t.tag === 'tbd';
        var cls = 'tile' + (isTbd ? ' tile--tbd' : '');
        // live topics navigate to their sub-page; dead ones toast via [data-soon]
        var nav = LIVE[t.id] ? 'href="' + LIVE[t.id] + '"' : 'data-soon href="#"';
        var orderNumber = ORDER.indexOf(t.id) + 1;
        return '<a class="' + cls + '" data-topic="' + t.id + '" ' + nav + '>' +
            '<span class="order-circle" aria-hidden="true">' + orderNumber + '</span>' +
            '<span class="t-main">' +
              '<span class="t-row"><span class="t-name">' + t.name + '</span></span>' +
            '</span>' +
            '<span class="seen-check" aria-label="Reviewed">✓</span>' +
            '<span class="t-go">→</span>' +
          '</a>';
      }).join('');
      return '<section class="cat panel" data-cat="' + c.id + '" id="cat-' + c.id + '">' +
          '<header class="cat-head">' +
            '<span class="cat-chip">' + (c.icon || '') + '</span>' +
            '<span class="cat-name">' + c.name + '</span>' +
          '</header>' +
          '<div class="cat-body">' + tiles + '</div>' +
        '</section>';
    }).join('');
    refreshSeen();
  }

  function renderAdvancedTopics() {
    var host = document.getElementById('advanced-topics-list');
    if (!host) return;
    host.innerHTML = ADVANCED_TOPICS.map(function (t) {
      // available topics render as live links to their sub-page; the rest stay "coming soon"
      if (t.available && t.href) {
        return '<a class="advanced-topic advanced-topic--live" data-advanced-topic="' + t.id + '" href="' + t.href + '">' +
            '<span class="advanced-topic__name">' + t.name + '</span>' +
            '<span class="seen-check" aria-label="Reviewed">✓</span>' +
            '<span class="advanced-topic__go" aria-hidden="true">→</span>' +
          '</a>';
      }
      return '<div class="advanced-topic" data-advanced-topic="' + t.id + '">' +
          '<span class="advanced-topic__name">' + t.name + '</span>' +
          '<span class="coming-soon" aria-disabled="true">Coming soon</span>' +
        '</div>';
    }).join('');
    refreshAdvancedProgress();
  }

  /* ---- progress ---- */
  function refreshSeen() {
    var seen = (window.GOB ? window.GOB.seen() : []);
    document.querySelectorAll('.tile[data-topic]').forEach(function (el) {
      el.classList.toggle('is-seen', seen.indexOf(el.getAttribute('data-topic')) !== -1);
    });
    var n = seen.filter(function (id) { return LEARNABLE.indexOf(id) !== -1; }).length;
    var pct = Math.round((n / TOTAL) * 100);
    set('pct', pct + '%'); set('seen-n', n); set('total-n', TOTAL);
    var bar = document.getElementById('bar'); if (bar) bar.style.width = pct + '%';
    updateNext();
    refreshAdvancedProgress();
  }
  function set(id, v) { var e = document.getElementById(id); if (e) e.textContent = v; }

  function refreshAdvancedProgress() {
    var seen = (window.GOB ? window.GOB.seen() : []);
    document.querySelectorAll('.advanced-topic[data-advanced-topic]').forEach(function (el) {
      el.classList.toggle('is-seen', seen.indexOf(el.getAttribute('data-advanced-topic')) !== -1);
    });
    var n = ADVANCED_TOPICS.filter(function (t) {
      return seen.indexOf(t.id) !== -1;
    }).length;
    var pct = ADVANCED_TOTAL ? Math.round((n / ADVANCED_TOTAL) * 100) : 0;
    set('advanced-seen-n', n);
    set('advanced-total-n', ADVANCED_TOTAL);
    var bar = document.getElementById('advanced-bar');
    if (bar) bar.style.width = pct + '%';
  }

  /* ---- toast (styleguide: bottom-right, single reused node) ---- */
  var toastTimer;
  function toast(title, sub) {
    var t = document.getElementById('toast');
    if (!t) return;
    t.querySelector('.tt').textContent = title;
    t.querySelector('.ts').textContent = sub || '';
    t.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { t.classList.remove('show'); }, 3200);
  }

  /* ---- wire ---- */
  function wire() {
    // dead topic tiles: toast preview + mark explored (the future-page hook)
    document.body.addEventListener('click', function (e) {
      var soon = e.target.closest('[data-soon]');
      if (!soon) return;
      e.preventDefault();
      sfx('click-tiny.wav');
      var tbd = soon.classList.contains('tile--tbd');
      if (tbd) {
        toast('In development', 'We’ll author this once the others are nailed.');
      } else {
        var id = soon.getAttribute('data-topic');
        var fresh = id && !window.GOB.isSeen(id);
        if (id) window.GOB.markSeen(id);
        toast(fresh ? 'Marked as explored' : 'Lesson preview', 'Full lesson lands in the next build pass.');
      }
    });

    // Reset progress
    var reset = document.getElementById('reset');
    if (reset) reset.addEventListener('click', function () { sfx('click-tiny.wav'); window.GOB.unseenAll(); toast('Progress reset', 'Your explored topics were cleared.'); });

    // Continue link (non-live lessons): scroll to category anchor, pulse target tile
    document.body.addEventListener('click', function (e) {
      var tgt = e.target.closest('[data-target]');
      if (!tgt) return;
      sfx('click-tiny.wav');
      var id = tgt.dataset.target;
      var tile = document.querySelector('.tile[data-topic="' + id + '"]');
      if (tile) {
        setTimeout(function () {
          tile.classList.add('pulse');
          setTimeout(function () { tile.classList.remove('pulse'); }, 1600);
        }, 480);
      }
    });

    window.addEventListener('gob:progress', refreshSeen);
  }

  renderCats();
  renderAdvancedTopics();
  wire();
})();
