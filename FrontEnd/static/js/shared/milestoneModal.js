/**
 * One milestone modal template (.mm) for every MILESTONE-tier Office moment.
 * Markup and classes match design_handoff_ch7/ch7.css. Does not invent fields.
 */
(function (global) {
  'use strict';

  var KIND_META = {
    signed_class: { eyebrow: 'Signing Day', title: 'Your class is signed', dek: 'The Signing Day reveal stays on the hub. This is the recap.' },
    walk_on_welcome: { eyebrow: 'Walk-ons', title: 'Walk-ons have arrived', dek: 'They are on the roster now.' },
    bracket_reveal: { eyebrow: 'Bracket reveal', title: 'The bracket is set', dek: 'Your path, from the field that just posted.' },
    region_bye: { eyebrow: 'Region bye', title: 'Region Tournament Bye', dek: 'You sit the first region game.' },
    conference_rs_region: { eyebrow: 'Region field', title: 'Region Tournament Qualified', dek: 'The regular-season finish sent you through.' },
    first_archetype: { eyebrow: 'Coach archetype', title: 'Your first archetype', dek: 'How you win, written on the staff.' },
    elimination: { eyebrow: 'Season over', title: 'Season over', dek: 'The last result, then the record.' }
  };

  var LABEL = {
    signed_class: 'Signing Day',
    walk_on_welcome: 'Walk-ons',
    bracket_reveal: 'Bracket reveal',
    region_bye: 'Region bye',
    conference_rs_region: 'Region field',
    first_archetype: 'Coach archetype',
    elimination: 'Season over',
    championship: 'Championship',
    season_review: 'Season review',
    recruit_visit: 'Recruit visit',
    archetype_evolution: 'Archetype'
  };

  var REGION_BYE_COPY = 'Hey Coach, congratulations! You won both your conference regular-season title and your conference tournament title. This means you\u2019ve earned a bye in the Region Tournament and have automatically qualified for the Region Championship game. Sim this week\u2019s games, then start preparing for the Region Championship!';

  var ROUND_WEEK = {
    conference: { round1: 27, round2: 28, final: 29 },
    region: { round1: 30, final: 31 },
    national: { round1: 32, round2: 33, final: 34 }
  };

  var STING_MS = 200;
  var host = null;
  var lastFocus = null;
  var keyHandler = null;
  var stingTimer = null;
  var closeResolver = null;
  var closeReason = null;

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

  function rtLetter(value) {
    if (!present(value)) return '';
    try {
      if (typeof global.formatRtDisplay === 'function') {
        var shown = global.formatRtDisplay(value);
        return shown && shown !== '--' ? shown : '';
      }
    } catch (e) { /* ignore */ }
    return String(value);
  }

  function rtTone(value) {
    var letter = rtLetter(value);
    var c = letter.charAt(0);
    if (c === 'A') return 't-blue';
    if (c === 'B') return 't-green';
    if (c === 'C') return 't-yellow';
    return 't-red';
  }

  function rtPair(now, pot) {
    var a = rtLetter(now);
    var b = rtLetter(pot);
    if (!a && !b) return '';
    var html = '<span class="rtl">';
    if (a) html += '<b class="' + rtTone(now) + '">' + esc(a) + '</b>';
    if (a && b) html += '<i>→</i>';
    if (b) html += '<b class="pot ' + rtTone(pot) + '">' + esc(b) + '</b>';
    return html + '</span>';
  }

  function avatarHtml(name, imageId) {
    var inner = esc(initials(name));
    if (imageId && global.API_CONFIG && typeof global.API_CONFIG.getRecruitImageUrl === 'function') {
      try {
        var url = global.API_CONFIG.getRecruitImageUrl(imageId, { size: 'card' });
        if (url) inner = '<img src="' + esc(url) + '" alt="">';
      } catch (e) { /* initials */ }
    }
    return '<span class="av" aria-hidden="true">' + inner + '</span>';
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
    return '<div class="rc">'
      + avatarHtml(r.name, r.image_id)
      + '<div class="rc-n"><b>' + esc(present(r.name) ? r.name : '—') + '</b>'
      + (meta ? '<span>' + esc(meta) + '</span>' : '')
      + '</div>'
      + rtPair(r.rt_now, r.rt_potential)
      + '</div>';
  }

  function teamName(id, names) {
    var tid = String(id || '');
    if (!tid) return '';
    return (names && names[tid]) || tid;
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
          out.push({ key: rk, matchup: m, index: i });
          break;
        }
      }
    });
    return out;
  }

  function siblingMatchup(list, index) {
    if (!list || !list.length || index == null || index < 0) return null;
    if (list.length === 2) return list[index === 0 ? 1 : 0] || null;
    var sib = index % 2 === 0 ? index + 1 : index - 1;
    return list[sib] || null;
  }

  function seedTag(id, seeds) {
    if (!present(id) || !seeds || !present(seeds[String(id)])) return '';
    return '#' + String(seeds[String(id)]);
  }

  function teamPhrase(id, names, seeds, userId, asYou) {
    if (!present(id)) return '';
    var tid = String(id);
    var label = (seedTag(tid, seeds) ? seedTag(tid, seeds) + ' ' : '') + teamName(tid, names);
    if (asYou || tid === String(userId || '')) {
      return '<span class="me"><b>' + esc(label) + '</b></span>';
    }
    return esc(label);
  }

  function roundCaption(key, pathLen) {
    if (key === 'round1') return 'Round 1';
    if (key === 'round2') return 'Round 2';
    if (key === 'final') return pathLen > 2 ? 'Round 3' : 'Final';
    return key;
  }

  function weekCaption(tier, key, matchup, userId) {
    var week = ROUND_WEEK[tier] && ROUND_WEEK[tier][key];
    if (week == null) return '';
    var site = '';
    if (matchup && present(userId)) {
      if (String(matchup.home_team) === String(userId)) site = ' · Home';
      else if (String(matchup.away_team) === String(userId)) site = ' · Away';
    }
    return 'Week ' + week + site;
  }

  function winnerOf(matchup, names, seeds, userId) {
    if (!matchup) return '';
    var a = teamPhrase(matchup.home_team, names, seeds, userId);
    var b = teamPhrase(matchup.away_team, names, seeds, userId);
    if (a && b) return 'Winner of ' + a + ' <em>/</em> ' + b;
    return '';
  }

  function vsLine(matchup, names, seeds, userId) {
    if (!matchup) return '';
    var home = teamPhrase(matchup.home_team, names, seeds, userId);
    var away = teamPhrase(matchup.away_team, names, seeds, userId);
    if (home && away) return home + '<em>vs</em>' + away;
    return '';
  }

  function muRow(label, line, week) {
    if (!line) return '';
    return '<div class="mu-r"><i>' + esc(label) + '</i><span>'
      + line + '</span>'
      + (week ? '<span>' + esc(week) + '</span>' : '')
      + '</div>';
  }

  function nextRoundKey(key, tier) {
    if (key === 'round1') return (ROUND_WEEK[tier] && ROUND_WEEK[tier].round2) ? 'round2' : 'final';
    if (key === 'round2') return 'final';
    return '';
  }

  function bodySignedClass(p) {
    var rec = (p && p.recruits) || [];
    var rows = rec.map(recruitRow).join('');
    return rows ? '<div class="rc-l wi" style="--i:1">' + rows + '</div>' : '';
  }

  function bodyWalkOn(p) {
    var rec = (p && p.walk_ons) || [];
    var rows = rec.map(recruitRow).join('');
    return rows ? '<div class="rc-l wi" style="--i:1">' + rows + '</div>' : '';
  }

  function bodyBracket(p, maps) {
    maps = maps || {};
    var userId = maps.userTeamId || (p && p.user_team_id) || (p && p.team_id);
    var names = maps.teamIdToNameMap || (p && p.team_id_to_name) || {};
    var seeds = (p && p.seeds) || {};
    var tier = p && p.tier;
    var mySeed = userId != null ? seeds[String(userId)] : null;
    var html = '<div class="seed wi" style="--i:0">';
    if (present(mySeed)) {
      html += '<div class="seed-n"><b>' + esc(String(mySeed)) + '</b><span>Seed</span></div>';
    }
    if (p && p.bracket) {
      var path = userPathRounds(p.bracket, userId);
      var rows = '';
      var shown = 0;
      path.forEach(function (step) {
        var line = vsLine(step.matchup, names, seeds, userId);
        if (!line) return;
        shown += 1;
        rows += muRow(
          roundCaption(step.key, path.length + 1),
          line,
          weekCaption(tier, step.key, step.matchup, userId)
        );
      });
      var first = path[0];
      if (first) {
        var sib = siblingMatchup(p.bracket[first.key] || [], first.index);
        var nxt = nextRoundKey(first.key, tier);
        var laterFilled = path.some(function (step) {
          return step.key === nxt && vsLine(step.matchup, names, seeds, userId);
        });
        if (sib && nxt && !laterFilled) {
          var nextLine = winnerOf(sib, names, seeds, userId);
          if (nextLine) {
            shown += 1;
            rows += muRow(
              roundCaption(nxt, shown + 1),
              nextLine,
              weekCaption(tier, nxt, null, userId)
            );
          }
        }
      }
      if (rows) html += '<div class="mu">' + rows + '</div>';
    }
    html += '</div>';
    return html;
  }

  function bodyRegionBye() {
    return '<p class="mm-d wi" style="--i:0">' + esc(REGION_BYE_COPY) + '</p>';
  }

  function bodyConferenceRs(p) {
    var lost = p && p.lost_round;
    var finalSentence = lost === 'final'
      ? "Let's go on to the Region Tourney now!"
      : "Let's sim the rest of the Conference Tourney, then get ready for the Region Tourney!";
    return '<p class="mm-d wi" style="--i:0">Hey Coach, we lost the game, but because you won the regular-season conference title, you still qualify for the Region Tournament. ' + esc(finalSentence) + '</p>';
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
    var letter = name ? name.charAt(0).toUpperCase() : 'A';
    return '<div class="arch wi" style="--i:0"><span class="med gold" style="--ms:64px">' + esc(letter) + '</span><p>' + esc(copy) + '</p></div>';
  }

  function ordinal(n) {
    var v = Number(n);
    if (!isFinite(v)) return String(n);
    var j = v % 10;
    var k = v % 100;
    var suf = (j === 1 && k !== 11) ? 'st' : (j === 2 && k !== 12) ? 'nd' : (j === 3 && k !== 13) ? 'rd' : 'th';
    return String(v) + suf;
  }

  function bodyElimination(p, maps) {
    maps = maps || {};
    var userId = maps.userTeamId || (p && p.user_team_id);
    var names = maps.teamIdToNameMap || {};
    var you = (userId && names[String(userId)]) || maps.teamName || '';
    var opp = (p && p.opponent_team_name) || '';
    var html = '';
    if (p && p.score && (p.score.user != null || p.score.opponent != null)) {
      html += '<div class="fin">';
      html += '<div class="fin-t">';
      if (you) html += '<b>' + esc(you) + '</b>';
      if (p.user_seed != null) html += '<span>#' + esc(String(p.user_seed)) + ' seed</span>';
      html += '</div>';
      html += '<div class="fin-s">' + esc(String(p.score.user)) + '<i>–</i>' + esc(String(p.score.opponent)) + '</div>';
      html += '<div class="fin-t r">';
      if (opp) html += '<b>' + esc(opp) + '</b>';
      if (p.opponent_seed != null) html += '<span>#' + esc(String(p.opponent_seed)) + ' seed</span>';
      html += '</div></div>';
    }
    var sums = [];
    if (p && p.record && (p.record.wins != null || p.record.losses != null)) {
      sums.push('<div><b>' + esc(String(p.record.wins)) + '–' + esc(String(p.record.losses)) + '</b><span>Record</span></div>');
    }
    if (p && p.conference_place != null) {
      sums.push('<div><b>' + esc(ordinal(p.conference_place)) + '</b><span>Conference</span></div>');
    }
    if (p && p.national_rank != null) {
      sums.push('<div><b>#' + esc(String(p.national_rank)) + '</b><span>National</span></div>');
    }
    if (sums.length) html += '<div class="mm-sum">' + sums.join('') + '</div>';
    return html;
  }

  function bodyFor(kind, payload, maps) {
    if (kind === 'signed_class') return bodySignedClass(payload);
    if (kind === 'walk_on_welcome') return bodyWalkOn(payload);
    if (kind === 'bracket_reveal') return bodyBracket(payload, maps);
    if (kind === 'region_bye') return bodyRegionBye();
    if (kind === 'conference_rs_region') return bodyConferenceRs(payload);
    if (kind === 'first_archetype') return bodyArchetype(payload);
    if (kind === 'elimination') return bodyElimination(payload, maps);
    return '';
  }

  function titleFor(kind, payload, item, maps) {
    var meta = KIND_META[kind] || { title: 'Moment', dek: '' };
    var title = (item && item.title) || meta.title;
    var dek = (item && item.line) || meta.dek;
    if (kind === 'signed_class') {
      title = meta.title;
      if (item && item.line) dek = item.line;
    }
    if (kind === 'bracket_reveal') {
      var userId = maps && (maps.userTeamId || (payload && payload.user_team_id));
      var seeds = payload && payload.seeds;
      var seed = userId != null && seeds ? seeds[String(userId)] : null;
      var place = '';
      if (payload && payload.tier === 'conference') place = 'Conference';
      else if (payload && payload.tier === 'region') place = 'Region';
      else if (payload && payload.tier === 'national') place = 'National';
      if (present(seed) && place) title = 'You\u2019re in: ' + String(seed) + ' seed, ' + place;
      else if (present(seed)) title = 'You\u2019re in: ' + String(seed) + ' seed';
      else if (payload && payload.eyebrow) title = payload.eyebrow;
      if (payload && payload.eyebrow) dek = payload.eyebrow;
    }
    if (kind === 'first_archetype') {
      var key = payload && (payload.archetype || payload.archetype_key);
      try {
        if (key && global.GOBArchetype && typeof global.GOBArchetype.nameFor === 'function') {
          var nm = global.GOBArchetype.nameFor(key);
          if (nm) title = 'You\u2019re a ' + nm;
        }
      } catch (e) { /* ignore */ }
    }
    if (kind === 'elimination' && payload && payload.round_name) {
      title = 'Eliminated in the ' + payload.round_name;
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
    closeReason = reason;
    var dialog = host.querySelector('.mm');
    if (reason === 'next' && dialog && !reducedMotion()) dialog.classList.add('q-out');
    else host.classList.add('is-out');
    var wait = reducedMotion() ? 0 : (reason === 'next' ? 180 : 180);
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
    var titles = titleFor(kind, payload, item, opts.maps);
    var kick = meta.eyebrow;
    if (kind === 'bracket_reveal' && payload && payload.eyebrow) {
      kick = String(payload.eyebrow).split('·')[0].trim() || meta.eyebrow;
    }
    var mq = '';
    if (total > 1) {
      var dots = '';
      for (var i = 1; i <= total; i++) {
        dots += '<i' + (i === index ? ' class="on"' : '') + '></i>';
      }
      mq = '<div class="mq" aria-label="Moment ' + index + ' of ' + total + '">' + dots + '<span>' + index + ' of ' + total + '</span></div>';
    }
    var up = isLast
      ? (kind === 'first_archetype'
        ? '<a class="lnk" href="/coaching-archetypes.html" data-sfx="SFX_SELECT">Explore archetypes</a>'
        : (kind === 'bracket_reveal'
          ? '<a class="lnk" href="/franchise-command-center.html?tab=tournament-view" data-sfx="SFX_SELECT">Full bracket</a>'
          : ''))
      : 'Up next <b>· ' + esc(LABEL[nextKind] || nextTitle || nextKind || 'Moment') + '</b>';
    var btnLabel = isLast ? 'Done' : 'Next';

    var wrap = document.createElement('div');
    wrap.className = 'mm-scrim mm-in';
    wrap.setAttribute('data-kind', kind);
    wrap.innerHTML =
      '<div class="mm ' + (isGold ? 'is-gold' : 'is-quiet') + '" role="dialog" aria-modal="true" aria-labelledby="mm-t">'
      + '<div class="mm-h">'
      + '<div class="mm-k">' + esc(kick) + '</div>'
      + mq
      + '<button type="button" class="mm-x" data-sfx="SFX_SELECT" aria-label="Close. Remaining moments wait for your next visit.">×</button>'
      + '</div>'
      + '<div class="mm-c"><div><h2 class="mm-t" id="mm-t">' + esc(titles.title) + '</h2><p class="mm-d">' + esc(titles.dek) + '</p></div>'
      + bodyFor(kind, payload, opts.maps)
      + '</div>'
      + '<div class="mm-f"><div class="mm-nx">' + up + '</div>'
      + '<button type="button" class="btn-ghost mm-go" data-sfx="SFX_SELECT">' + esc(btnLabel) + ' <kbd>Enter</kbd></button>'
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
