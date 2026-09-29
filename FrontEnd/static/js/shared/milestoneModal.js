/**
 * One milestone modal template (.mm) for every MILESTONE-tier Office moment.
 * Opened only by momentQueue from moments_for_this_visit. Does not invent fields.
 */
(function (global) {
  'use strict';

  var KIND_META = {
    signed_class: { eyebrow: 'Signing class', title: 'Signing class', dek: 'The Signing Day reveal stays on the hub. This is the recap.' },
    walk_on_welcome: { eyebrow: 'Walk-ons', title: 'Walk-ons', dek: 'They are on the roster now.' },
    bracket_reveal: { eyebrow: 'Bracket reveal', title: 'The bracket is set', dek: 'Your path, from the field that just posted.' },
    region_bye: { eyebrow: 'Region bye', title: 'Region Tournament Bye', dek: 'You sit the first region game.' },
    conference_rs_region: { eyebrow: 'Region field', title: 'Region Tournament Qualified', dek: 'The regular-season finish sent you through.' },
    first_archetype: { eyebrow: 'Archetype', title: 'Your first archetype', dek: 'How you win, written on the staff.' },
    elimination: { eyebrow: 'Season over', title: 'Season over', dek: 'The last result, then the record.' }
  };

  var LABEL = {
    signed_class: 'Signing class',
    walk_on_welcome: 'Walk-ons',
    bracket_reveal: 'Bracket reveal',
    region_bye: 'Region bye',
    conference_rs_region: 'Region field',
    first_archetype: 'Archetype',
    elimination: 'Season over',
    championship: 'Championship',
    season_review: 'Season review',
    recruit_visit: 'Recruit visit',
    archetype_evolution: 'Archetype'
  };

  var REGION_BYE_COPY = 'Hey Coach, congratulations! You won both your conference regular-season title and your conference tournament title. This means you\u2019ve earned a bye in the Region Tournament and have automatically qualified for the Region Championship game. Sim this week\u2019s games, then start preparing for the Region Championship!';

  var STING_MS = 200;
  var host = null;
  var lastFocus = null;
  var keyHandler = null;
  var stingTimer = null;
  var closeResolver = null;

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function initials(name) {
    var parts = String(name || '').trim().split(/\s+/).filter(Boolean);
    if (!parts.length) return '—';
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }

  function present(value) {
    return value != null && String(value).trim() !== '' && String(value) !== '--';
  }

  function rtHtml(value) {
    if (!present(value)) return '';
    var cls = '';
    var shown = String(value);
    try {
      if (typeof global.getRtBucketClass === 'function') cls = global.getRtBucketClass(value) || '';
    } catch (e) { /* ignore */ }
    try {
      if (typeof global.formatRtDisplay === 'function') shown = global.formatRtDisplay(value);
    } catch (e2) { /* ignore */ }
    return '<span class="rt-letter ' + esc(cls) + '">' + esc(shown) + '</span>';
  }

  function avatarHtml(name, imageId) {
    var inner = esc(initials(name));
    if (imageId && global.API_CONFIG && typeof global.API_CONFIG.getRecruitImageUrl === 'function') {
      try {
        var url = global.API_CONFIG.getRecruitImageUrl(imageId, { size: 'card' });
        if (url) inner = '<img src="' + esc(url) + '" alt="">';
      } catch (e) { /* initials */ }
    }
    return '<div class="av" aria-hidden="true">' + inner + '</div>';
  }

  function normalizeRecruit(r) {
    if (!r || typeof r !== 'object') return null;
    return {
      name: r.name,
      position: present(r.position) ? r.position : r.pos,
      home_region: r.home_region,
      rt_now: present(r.rt_now) ? r.rt_now : r.rt,
      rt_potential: present(r.rt_potential) ? r.rt_potential : r.potential_rt,
      image_id: r.image_id
    };
  }

  function recruitRow(raw) {
    var r = normalizeRecruit(raw);
    if (!r) return '';
    var meta = [r.position, r.home_region].filter(present).join(' · ');
    var rtBits = [];
    if (present(r.rt_now)) rtBits.push(rtHtml(r.rt_now));
    if (present(r.rt_potential)) rtBits.push(rtHtml(r.rt_potential));
    var rt = rtBits.length
      ? '<div class="rt">' + rtBits.join('<span class="rt-arrow"> → </span>') + '</div>'
      : '';
    return '<div class="rc">'
      + avatarHtml(r.name, r.image_id)
      + '<div><div class="who">' + esc(present(r.name) ? r.name : '—') + '</div>'
      + (meta ? '<div class="meta">' + esc(meta) + '</div>' : '')
      + '</div>'
      + rt
      + '</div>';
  }

  function teamName(id, names) {
    var tid = String(id || '');
    if (!tid) return '';
    return (names && names[tid]) || tid;
  }

  function matchupRows(matchup, userTeamId, names, seeds) {
    if (!matchup || typeof matchup !== 'object') return '';
    function row(id) {
      if (!present(id)) return '';
      var tid = String(id);
      var you = tid === String(userTeamId || '');
      var seed = seeds && present(seeds[tid])
        ? '<span class="sd">#' + esc(String(seeds[tid])) + '</span>'
        : '';
      return '<div class="row' + (you ? ' is-you' : '') + '">'
        + '<span class="who">' + esc(teamName(tid, names)) + '</span>'
        + seed
        + '</div>';
    }
    return '<div class="mu">' + row(matchup.away_team) + row(matchup.home_team) + '</div>';
  }

  function userPathRounds(bracket, userTeamId) {
    if (!bracket || typeof bracket !== 'object') return [];
    var tid = String(userTeamId || '');
    var out = [];
    ['round1', 'round2', 'final'].forEach(function (rk) {
      var list = bracket[rk] || [];
      for (var i = 0; i < list.length; i++) {
        var m = list[i];
        if (!m) continue;
        if (String(m.home_team) === tid || String(m.away_team) === tid) {
          out.push({ key: rk, matchup: m });
          break;
        }
      }
    });
    return out;
  }

  function roundLabel(key) {
    if (key === 'round1') return 'First round';
    if (key === 'round2') return 'Semifinal';
    if (key === 'final') return 'Final';
    return key;
  }

  function bodySignedClass(p) {
    var rec = (p && p.recruits) || [];
    var rows = rec.map(recruitRow).join('');
    var count = p && p.count != null ? p.count : rec.length;
    var sum = p && p.count != null
      ? '<p class="mm-sum"><strong>' + esc(String(count)) + '</strong> signed.</p>'
      : '';
    return (rows ? '<div>' + rows + '</div>' : '') + sum;
  }

  function bodyWalkOn(p) {
    var rec = (p && p.walk_ons) || [];
    var rows = rec.map(recruitRow).join('');
    var count = p && p.count != null ? p.count : rec.length;
    var sum = p && p.count != null
      ? '<p class="mm-sum"><strong>' + esc(String(count)) + '</strong> walk-on' + (Number(count) === 1 ? '' : 's') + '.</p>'
      : '';
    return (rows ? '<div>' + rows + '</div>' : '') + sum;
  }

  function bodyBracket(p, maps) {
    maps = maps || {};
    var userId = maps.userTeamId || (p && p.user_team_id) || (p && p.team_id);
    var names = maps.teamIdToNameMap || (p && p.team_id_to_name) || {};
    var seeds = (p && p.seeds) || {};
    var html = '';
    var mySeed = userId != null ? seeds[String(userId)] : null;
    if (present(mySeed)) {
      html += '<div class="seed is-you"><b>' + esc(String(mySeed)) + '</b> your seed</div>';
    }
    if (!p || !p.bracket) return html;
    var path = userPathRounds(p.bracket, userId);
    if (!path.length) return html;
    html += matchupRows(path[0].matchup, userId, names, seeds);
    if (path.length > 1 && path[1].key) {
      var nxt = path[1].matchup || {};
      var sides = [nxt.home_team, nxt.away_team].filter(present);
      if (sides.length >= 2) {
        html += '<p class="mm-sum">Then the ' + esc(roundLabel(path[1].key).toLowerCase()) + '.</p>';
        html += matchupRows(nxt, userId, names, seeds);
      }
    }
    return html;
  }

  function bodyRegionBye() {
    return '<p class="mm-sum">' + esc(REGION_BYE_COPY) + '</p>';
  }

  function bodyConferenceRs(p) {
    var lost = p && p.lost_round;
    var finalSentence = lost === 'final'
      ? "Let's go on to the Region Tourney now!"
      : "Let's sim the rest of the Conference Tourney, then get ready for the Region Tourney!";
    return '<p class="mm-sum">Hey Coach, we lost the game, but because you won the regular-season conference title, you still qualify for the Region Tournament. ' + esc(finalSentence) + '</p>';
  }

  function bodyArchetype(p) {
    var key = p && (p.archetype || p.archetype_key);
    var name = '';
    var copy = '';
    try {
      if (key && global.GOBArchetype) {
        if (typeof global.GOBArchetype.nameFor === 'function') name = global.GOBArchetype.nameFor(key);
        if (typeof global.GOBArchetype.descFor === 'function') {
          var desc = global.GOBArchetype.descFor(key);
          if (desc && desc !== 'TBD') copy = desc;
        }
      }
    } catch (e) { /* ignore */ }
    if (!name) name = (p && p.archetype_name) || key || '';
    if (!copy) {
      copy = 'Based on your coaching style, you\u2019re now known as the '
        + (name || 'this')
        + ' coaching archetype. Note this archetype handle will evolve as you develop your program\u2019s identity.';
    }
    var badge = '';
    try {
      if (key && global.GOBArchetype && typeof global.GOBArchetype.badgeHtml === 'function') {
        badge = global.GOBArchetype.badgeHtml(key, 72);
      }
    } catch (e2) { /* ignore */ }
    var label = name ? '<strong>' + esc(name) + '</strong>. ' : '';
    return '<div class="arch"><div class="badge">' + badge + '</div><div class="copy">' + label + esc(copy) + '</div></div>';
  }

  function bodyElimination(p) {
    var bits = [];
    if (p && p.score && (p.score.user != null || p.score.opponent != null)) {
      bits.push('<div class="sc">' + esc(String(p.score.user)) + '–' + esc(String(p.score.opponent)) + '</div>');
    }
    var facts = [];
    if (p && p.round_name) facts.push('<span><b>' + esc(p.round_name) + '</b></span>');
    if (p && p.record && (p.record.wins != null || p.record.losses != null)) {
      facts.push('<span>Season <b>' + esc(String(p.record.wins)) + '–' + esc(String(p.record.losses)) + '</b></span>');
    }
    if (p && p.conference_place != null) facts.push('<span>Conference <b>' + esc(String(p.conference_place)) + '</b></span>');
    if (p && p.national_rank != null) facts.push('<span>National <b>' + esc(String(p.national_rank)) + '</b></span>');
    if (p && p.user_seed != null) facts.push('<span>Seed <b>' + esc(String(p.user_seed)) + '</b></span>');
    if (p && p.opponent_seed != null) facts.push('<span>Opp seed <b>' + esc(String(p.opponent_seed)) + '</b></span>');
    if (facts.length) bits.push('<div class="facts">' + facts.join('') + '</div>');
    return '<div class="fin">' + bits.join('') + '</div>';
  }

  function bodyFor(kind, payload, maps) {
    if (kind === 'signed_class') return bodySignedClass(payload);
    if (kind === 'walk_on_welcome') return bodyWalkOn(payload);
    if (kind === 'bracket_reveal') return bodyBracket(payload, maps);
    if (kind === 'region_bye') return bodyRegionBye();
    if (kind === 'conference_rs_region') return bodyConferenceRs(payload);
    if (kind === 'first_archetype') return bodyArchetype(payload);
    if (kind === 'elimination') return bodyElimination(payload);
    return '';
  }

  function titleFor(kind, payload, item) {
    var meta = KIND_META[kind] || { title: 'Moment', dek: '' };
    var title = (item && item.title) || meta.title;
    var dek = (item && item.line) || meta.dek;
    if (kind === 'bracket_reveal' && payload && payload.eyebrow) title = payload.eyebrow;
    if (kind === 'first_archetype') {
      var key = payload && (payload.archetype || payload.archetype_key);
      try {
        if (key && global.GOBArchetype && typeof global.GOBArchetype.nameFor === 'function') {
          var nm = global.GOBArchetype.nameFor(key);
          if (nm) title = nm;
        }
      } catch (e) { /* ignore */ }
    }
    return { title: title, dek: dek };
  }

  function focusables(root) {
    return Array.prototype.slice.call(root.querySelectorAll(
      'button:not([disabled]), [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    )).filter(function (el) {
      return !el.hasAttribute('disabled') && el.getAttribute('aria-hidden') !== 'true';
    });
  }

  function trap(e) {
    if (!host || e.key !== 'Tab') return;
    var list = focusables(host);
    if (!list.length) return;
    var first = list[0];
    var last = list[list.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }

  function reducedMotion() {
    try {
      return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
    } catch (e) {
      return false;
    }
  }

  function playSting(item) {
    var name = item && item.sting;
    if (!name) return;
    try {
      (global.__gobMilestoneSfx || (global.__gobMilestoneSfx = [])).push(name);
    } catch (e) { /* ignore */ }
    import('/js/shared/uiSfx.js').then(function (m) {
      if (m && typeof m.playSfx === 'function') m.playSfx(name);
    }).catch(function () {});
  }

  function teardown(reason) {
    if (stingTimer) {
      clearTimeout(stingTimer);
      stingTimer = null;
    }
    if (keyHandler) {
      document.removeEventListener('keydown', keyHandler, true);
      keyHandler = null;
    }
    var resolve = closeResolver;
    closeResolver = null;
    var node = host;
    host = null;
    if (node && node.parentNode) node.parentNode.removeChild(node);
    if (lastFocus && typeof lastFocus.focus === 'function') {
      try { lastFocus.focus(); } catch (e) { /* ignore */ }
    }
    lastFocus = null;
    if (resolve) resolve(reason);
  }

  function requestClose(reason) {
    if (!host) return;
    host.classList.add('is-out');
    var wait = reducedMotion() ? 0 : 180;
    setTimeout(function () { teardown(reason); }, wait);
  }

  function mount(opts) {
    opts = opts || {};
    var item = opts.item || {};
    var kind = item.kind || opts.kind;
    var payload = opts.payload;
    if (payload == null || typeof payload !== 'object') payload = {};
    var index = opts.index || 1;
    var total = opts.total || 1;
    var nextKind = opts.nextKind || '';
    var nextTitle = opts.nextTitle || '';
    var isLast = !!opts.isLast;
    var style = item.style || (kind === 'elimination' ? 'quiet' : 'gold');
    var isGold = style === 'gold';

    if (host) teardown('supersede');

    lastFocus = document.activeElement;
    var meta = KIND_META[kind] || { eyebrow: 'Moment', title: 'Moment', dek: '' };
    var titles = titleFor(kind, payload, item);
    var dots = '';
    for (var i = 1; i <= total; i++) {
      dots += '<i' + (i === index ? ' class="on"' : '') + '></i>';
    }
    var up = isLast
      ? ''
      : '<span class="mm-up">Up next · ' + esc(nextTitle || LABEL[nextKind] || nextKind || 'Moment') + '</span>';
    var follow = '';
    if (kind === 'first_archetype') {
      follow = '<a class="mm-link" href="/coaching-archetypes.html">Explore archetypes</a>';
    }
    var btnLabel = isLast ? 'Done' : 'Next';
    var goldBits = isGold ? '<span class="mm-dia" aria-hidden="true"></span>' : '';
    var med = isGold ? '<div class="mm-med" aria-hidden="true">★</div>' : '';

    var wrap = document.createElement('div');
    wrap.className = 'mm-scrim';
    wrap.setAttribute('data-kind', kind);
    wrap.innerHTML =
      '<div class="mm ' + (isGold ? 'is-gold' : 'is-quiet') + '" role="dialog" aria-modal="true" aria-labelledby="mm-ttl">'
      + '<div class="mm-h">'
      + '<div class="mm-eye">' + goldBits + esc(meta.eyebrow) + '</div>'
      + '<div class="mq" aria-label="' + index + ' of ' + total + '">' + dots + '</div>'
      + '<button type="button" class="mm-x" aria-label="Close">×</button>'
      + '</div>'
      + med
      + '<h2 class="mm-ttl" id="mm-ttl">' + esc(titles.title) + '</h2>'
      + '<p class="mm-dek">' + esc(titles.dek) + '</p>'
      + '<div class="mm-body">' + bodyFor(kind, payload, opts.maps) + '</div>'
      + '<div class="mm-f">' + up + follow
      + '<button type="button" class="btn-ghost mm-go">' + esc(btnLabel) + '</button>'
      + '</div></div>';

    document.body.appendChild(wrap);
    host = wrap;

    var goBtn = wrap.querySelector('.mm-go');
    var xBtn = wrap.querySelector('.mm-x');

    keyHandler = function (e) {
      if (!host) return;
      if (e.key === 'Escape') {
        e.preventDefault();
        requestClose('dismiss');
        return;
      }
      if (e.key === 'Enter' && !(document.activeElement && document.activeElement.tagName === 'A')) {
        e.preventDefault();
        requestClose('next');
        return;
      }
      trap(e);
    };
    document.addEventListener('keydown', keyHandler, true);
    xBtn.addEventListener('click', function () { requestClose('dismiss'); });
    goBtn.addEventListener('click', function () { requestClose('next'); });
    wrap.addEventListener('mousedown', function (e) {
      if (e.target === wrap) requestClose('dismiss');
    });

    requestAnimationFrame(function () {
      wrap.classList.add('is-open');
      if (goBtn) goBtn.focus();
    });

    if (isGold && item.sting) {
      if (reducedMotion()) playSting(item);
      else {
        stingTimer = setTimeout(function () {
          stingTimer = null;
          playSting(item);
        }, STING_MS);
      }
    }

    return new Promise(function (resolve) {
      closeResolver = resolve;
    });
  }

  function show(opts) {
    opts = opts || {};
    var item = opts.item || {};
    var kind = item.kind || opts.kind;
    var ready = Promise.resolve();
    if (kind === 'first_archetype' && global.GOBArchetype && typeof global.GOBArchetype.ensureManifest === 'function') {
      ready = Promise.resolve(global.GOBArchetype.ensureManifest()).catch(function () {});
    }
    return ready.then(function () { return mount(opts); });
  }

  global.MilestoneModal = {
    show: show,
    isOpen: function () { return !!(host && host.classList.contains('is-open')); },
    close: function (reason) { requestClose(reason || 'dismiss'); },
    KIND_META: KIND_META
  };
})(typeof window !== 'undefined' ? window : this);
