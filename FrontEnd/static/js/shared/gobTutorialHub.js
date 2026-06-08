/* ===========================================================
   GOB Tutorial Hub — data, rendering, progress, toast
   IA: Players / Team / Strategy / Training

   Dead this pass: topic tiles, core-loop steps, hero action button,
   "Next up" pill, "See All Reminders" — they never navigate to a
   sub-page (those don't exist yet). When a sub-page ships it only has
   to call GOB.markSeen('<topic-id>') on load and the whole progress /
   next-up / explored-✓ system lights up automatically.
   =========================================================== */
(function () {
  'use strict';
  var I = (window.GOB && window.GOB.icons) || {};
  function sfx(f) { if (window.GOB && window.GOB.playSound) window.GOB.playSound(f); }

  /* ---- category + topic model ----
     priority -> the one topic every coach must master first
     (Recruiting & Scouting content is TBD/authored later, but they are
      presented as normal Advanced lessons here — not flagged as TBD.)   */
  // Grid fills left-to-right, top-to-bottom, so array order sets the layout:
  //   Players  | Training
  //   Team     | Strategy
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

  // progress denominator excludes TBD topics (none flagged this pass -> 7)
  var LEARNABLE = [];
  CATS.forEach(function (c) { c.topics.forEach(function (t) { if (t.tag !== 'tbd') LEARNABLE.push(t.id); }); });
  var TOTAL = LEARNABLE.length;

  // recommended learning order for the “next up” cue
  var ORDER = ['player-attributes', 'training', 'team-attributes', 'game-plans', 'playbooks', 'scouting', 'recruiting'];
  // topics whose sub-page exists this pass → real links; everything else is dead (toast)
  var LIVE = { 'player-attributes': '/player-attributes.html', 'training': '/tutorial-training.html', 'team-attributes': '/team-attributes.html', 'recruiting': '/tutorial-recruiting.html', 'game-plans': '/game-plans.html', 'playbooks': '/tutorial-playbooks.html', 'scouting': '/scouting.html' };
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
    var headline = document.getElementById('hero-topic');
    var kick = document.getElementById('kicker-label');
    var btn = document.getElementById('cta-next');
    // headline = the dynamic next-lesson name (single source of truth)
    if (headline) headline.textContent = nx ? nx.name : 'You’re all caught up';
    // kicker keeps its orange tick bar
    if (kick) kick.innerHTML = '<span class="tick"></span> ' + (nx ? 'Next up' : 'Nice work, coach');
    // CTA: navigate to the next lesson's page if it exists; otherwise inert (scroll + pulse)
    if (btn) {
      if (nx) {
        btn.textContent = 'Start lesson';
        if (LIVE[nx.id]) { btn.setAttribute('href', LIVE[nx.id]); btn.removeAttribute('data-target'); }
        else { btn.setAttribute('href', '#cat-' + nx.cat); btn.dataset.target = nx.id; }
      } else { btn.textContent = 'Browse all topics'; btn.setAttribute('href', '#topics'); btn.removeAttribute('data-target'); }
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
        var badge = t.priority ? '<span class="tag-first">★ Master first</span>'
                  : isTbd ? '<span class="tag-tbd">TBD</span>'
                  : t.depth ? '<span class="depth ' + t.depth + '">' + t.depth + '</span>' : '';
        // recommended-order step number (1–7 across all categories; non-contiguous within a panel)
        var step = ORDER.indexOf(t.id) + 1;
        // live topics navigate to their sub-page; dead ones toast via [data-soon]
        var nav = LIVE[t.id] ? 'href="' + LIVE[t.id] + '"' : 'data-soon href="#"';
        return '<a class="' + cls + '" data-topic="' + t.id + '" ' + nav + '>' +
            '<span class="t-num">' + step + '</span>' +
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

    // "Browse all topics" -> smooth scroll to the topics section
    var jump = document.getElementById('jump-cats');
    if (jump) jump.addEventListener('click', function (e) {
      e.preventDefault();
      sfx('click-tiny.wav');
      var el = document.getElementById('topics');
      if (el) window.scrollTo({ top: el.getBoundingClientRect().top + window.pageYOffset - 80, behavior: 'smooth' });
    });

    // Reset progress
    var reset = document.getElementById('reset');
    if (reset) reset.addEventListener('click', function () { sfx('click-tiny.wav'); window.GOB.unseenAll(); toast('Progress reset', 'Your explored topics were cleared.'); });

    // "See All Reminders" — dead (manager not built)
    var seeRem = document.getElementById('see-reminders');
    if (seeRem) seeRem.addEventListener('click', function () { sfx('click-tiny.wav'); toast('Reminders', 'The reminders manager is part of the next build pass.'); });

    // hero "next up" cue: scroll to the category, pulse its target tile
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
  wire();
})();
