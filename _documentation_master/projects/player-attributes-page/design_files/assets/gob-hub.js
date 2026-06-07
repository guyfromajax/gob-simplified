/* ===========================================================
   GOB Tutorial Hub — data, rendering, progress, toast
   IA: Players / Team / Strategy / Training
   =========================================================== */
(function () {
  'use strict';
  var I = (window.GOB && window.GOB.icons) || {};

  /* ---- category + topic model ----
     live:false  -> page not built yet (this pass = hub only)
     tag:'tbd'   -> content to be authored later (Recruiting, Scouting)
     priority    -> the one topic every coach must master first        */
  var CATS = [
    { id: 'players', name: 'Players', icon: I.player, topics: [
      { id: 'player-attributes', name: 'Player Attributes', icon: I.player, depth: 'foundational', priority: true,
        desc: 'The 14 attributes that determine the unique skill set of every player.' }
    ]},
    { id: 'training', name: 'Training', icon: I.training, topics: [
      { id: 'training', name: 'Training', icon: I.training, depth: 'foundational',
        desc: 'Player & team drills, playbook installs, scrimmages, and the coaching style that defines your team’s focus.' }
    ]},
    { id: 'team', name: 'Team', icon: I.team, topics: [
      { id: 'team-attributes', name: 'Team Attributes', icon: I.shield, depth: 'foundational',
        desc: 'Your program’s identity — compounding mindset traits vs. trained, decaying systems.' },
      { id: 'recruiting', name: 'Recruiting', icon: I.recruiting, depth: 'advanced',
        desc: 'Manage your recruiting pipeline by mastering invites, visits, and commitments.' }
    ]},
    { id: 'strategy', name: 'Strategy', icon: I.strategy, topics: [
      { id: 'game-plans', name: 'Game Plans', icon: I.sliders, depth: 'foundational',
        desc: 'The foundation of your strategy.' },
      { id: 'playbooks', name: 'Playbooks', icon: I.playbook, depth: 'advanced',
        desc: 'Learn how to build playbooks that match your coaching style.' },
      { id: 'scouting', name: 'Scouting', icon: I.scout, depth: 'advanced',
        desc: 'Learn how to study your upcoming opponents.' }
    ]}
  ];

  // progress denominator excludes TBD topics
  var LEARNABLE = [];
  CATS.forEach(function (c) { c.topics.forEach(function (t) { if (t.tag !== 'tbd') LEARNABLE.push(t.id); }); });
  var TOTAL = LEARNABLE.length;

  // recommended learning order for the “next up” cue
  var ORDER = ['player-attributes', 'training', 'team-attributes', 'game-plans', 'playbooks', 'scouting', 'recruiting'];
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
    var topic = document.getElementById('hero-topic');
    var kicker = document.getElementById('kicker-label');
    var btn = document.getElementById('cta-next');
    if (topic) topic.textContent = nx ? nx.name : 'You’re all caught up';
    if (kicker) kicker.textContent = nx ? 'Next up' : 'Nice work, coach';
    if (btn) {
      if (nx) { btn.textContent = 'Start lesson'; btn.setAttribute('href', '#cat-' + nx.cat); btn.dataset.target = nx.id; }
      else { btn.textContent = 'Browse all topics'; btn.setAttribute('href', '#topics'); delete btn.dataset.target; }
    }
  }

  /* ---- category grid ---- */
  function renderCats() {
    var host = document.getElementById('cats');
    if (!host) return;
    host.innerHTML = CATS.map(function (c) {
      var tiles = c.topics.map(function (t) {
        var isTbd = t.tag === 'tbd';
        var cls = 'tile' + (t.priority ? ' tile--priority' : '') + (isTbd ? ' tile--tbd' : '');
        var num = ORDER.indexOf(t.id) + 1;
        var badge = t.priority ? '<span class="tag-first">★ Master first</span>'
                  : isTbd ? '<span class="tag-tbd">TBD</span>'
                  : t.depth ? '<span class="depth ' + t.depth + '">' + t.depth + '</span>' : '';
        return '<a class="' + cls + '" data-topic="' + t.id + '" data-soon href="#">' +
            '<span class="t-num" aria-label="Recommended step ' + num + '">' + (num || '•') + '</span>' +
            '<span class="t-main">' +
              '<span class="t-row"><span class="t-name">' + t.name + '</span>' + badge + '</span>' +
              '<span class="t-desc">' + t.desc + '</span>' +
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
  }
  function set(id, v) { var e = document.getElementById(id); if (e) e.textContent = v; }

  /* ---- toast (styleguide: bottom-right) ---- */
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
    document.body.addEventListener('click', function (e) {
      var soon = e.target.closest('[data-soon]');
      if (soon) {
        e.preventDefault();
        var tbd = soon.classList.contains('tile--tbd');
        if (tbd) {
          toast('In development', 'We’ll author this once the others are nailed.');
        } else {
          var id = soon.getAttribute('data-topic');
          var fresh = id && !window.GOB.isSeen(id);
          if (id) window.GOB.markSeen(id);
          toast(fresh ? 'Marked as explored' : 'Lesson preview', 'Full lesson lands in the next build pass.');
        }
      }
    });
    var jump = document.getElementById('jump-cats');
    if (jump) jump.addEventListener('click', function (e) {
      e.preventDefault();
      var el = document.getElementById('topics');
      if (el) window.scrollTo({ top: el.getBoundingClientRect().top + window.pageYOffset - 24, behavior: 'smooth' });
    });
    var reset = document.getElementById('reset');
    if (reset) reset.addEventListener('click', function () { window.GOB.unseenAll(); toast('Progress reset', 'Your explored topics were cleared.'); });

    var seeRem = document.getElementById('see-reminders');
    if (seeRem) seeRem.addEventListener('click', function () { toast('Reminders', 'The reminders manager is part of the next build pass.'); });

    var demo = document.getElementById('demo-seen');
    if (demo) demo.addEventListener('click', function () {
      // lets the user feel the progress system without a built topic page
      var next = LEARNABLE.find(function (id) { return !window.GOB.isSeen(id); });
      if (next) { window.GOB.markSeen(next); toast('Topic marked explored', 'Watch your knowledge meter climb.'); }
      else toast('All caught up', 'You’ve explored every available lesson.');
    });

    document.body.addEventListener('click', function (e) {
      var tgt = e.target.closest('[data-target]');
      if (tgt) {
        var id = tgt.dataset.target;
        var tile = document.querySelector('.tile[data-topic="' + id + '"]');
        if (tile) {
          setTimeout(function () {
            tile.classList.add('pulse');
            setTimeout(function () { tile.classList.remove('pulse'); }, 1600);
          }, 480);
        }
      }
    });

    window.addEventListener('gob:progress', refreshSeen);
  }

  renderCats();
  wire();
})();
