/**
 * Season-peak takeover: one .pk title for every championship in the visit,
 * then the .rv review when season_review is in the queue. Does not invent
 * fields (no program-title count, no region seed).
 */
(function (global) {
  'use strict';

  var ROOT_ID = 'season-peak-root';
  var STING_MS = 600;
  var CONFETTI_N = 60;
  // One eyebrow for every title: "Season N". The headline names the title.
  var TITLE_TYPES = [
    { type: 'national_championship', letter: 'N', label: 'National Champions', headline: 'National Champions' },
    { type: 'banner_raise', letter: 'N', label: 'National Champions', headline: 'National Champions' },
    { type: 'region_championship', letter: 'R', label: 'Region Champions', headline: 'Region Champions' },
    { type: 'conference_championship', letter: 'C', label: 'Conference Tournament Champions', headline: 'Conference Tournament Champions' },
    { type: 'conference_tournament_championship', letter: 'C', label: 'Conference Tournament Champions', headline: 'Conference Tournament Champions' },
    { type: 'trophy_spotlight', letter: 'C', label: 'Regular Season Conference Champions', headline: 'Regular Season Conference Champions' },
    { type: 'conference_regular_season_championship', letter: 'C', label: 'Regular Season Conference Champions', headline: 'Regular Season Conference Champions' }
  ];
  var TROPHY_TITLE = {
    national: { letter: 'N', label: 'National Champions' },
    region: { letter: 'R', label: 'Region Champions' },
    conf_t: { letter: 'C', label: 'Conference Tournament Champions' },
    conf_rs: { letter: 'C', label: 'Regular Season Conference Champions' }
  };
  var AA_LABEL = {
    all_american_1: '1st team',
    all_american_2: '2nd team',
    all_american_3: '3rd team',
    all_conference_1: '1st team',
    all_conference_2: '2nd team',
    first_team: '1st team',
    second_team: '2nd team',
    third_team: '3rd team'
  };

  /** "All-American 1st team" / "All-Conference 2nd team": a player can carry both. */
  function honourTags(p) {
    var tags = [];
    var aa = aaLabel(p && p.all_american);
    var ac = aaLabel(p && p.all_conference);
    if (aa) tags.push('All-American ' + aa);
    if (ac) tags.push('All-Conference ' + ac);
    return tags;
  }

  var stingTimer = null;
  var keyHandler = null;
  var closeResolver = null;

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function present(value) {
    return value != null && String(value).trim() !== '' && String(value) !== '--';
  }

  function reducedMotion() {
    return !!(global.matchMedia && global.matchMedia('(prefers-reduced-motion: reduce)').matches);
  }

  function initials(name) {
    var parts = String(name || '').trim().split(/\s+/).filter(Boolean);
    if (!parts.length) return '—';
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }

  function ordinal(n) {
    var v = Number(n);
    if (!isFinite(v)) return String(n);
    var i = Math.abs(Math.round(v));
    var mod = i % 100;
    if (mod >= 11 && mod <= 13) return i + 'th';
    if (i % 10 === 1) return i + 'st';
    if (i % 10 === 2) return i + 'nd';
    if (i % 10 === 3) return i + 'rd';
    return i + 'th';
  }

  function specForType(type) {
    var i;
    for (i = 0; i < TITLE_TYPES.length; i++) {
      if (TITLE_TYPES[i].type === type) return TITLE_TYPES[i];
    }
    return null;
  }

  function featuredMoment(moments) {
    var i;
    for (i = 0; i < TITLE_TYPES.length; i++) {
      var hit = moments.filter(function (m) { return m && m.type === TITLE_TYPES[i].type; })[0];
      if (hit) return hit;
    }
    return moments[0];
  }

  function medallionsFromMoments(moments) {
    var seen = {};
    var out = [];
    TITLE_TYPES.forEach(function (spec) {
      if (seen[spec.letter + spec.label]) return;
      var hit = moments.filter(function (m) { return m && m.type === spec.type; })[0];
      if (!hit) return;
      seen[spec.letter + spec.label] = 1;
      var sub = [];
      if (present(hit.conference)) sub.push(String(hit.conference));
      if (present(hit.region)) sub.push(String(hit.region));
      if (present(hit.season)) sub.push('Season ' + hit.season);
      out.push({ letter: spec.letter, label: spec.label, sub: sub.join(' · '), lg: spec.letter === 'N' });
    });
    return out;
  }

  function medallionsFromTrophies(trophies) {
    var out = [];
    (trophies || []).forEach(function (t, i) {
      var spec = t && TROPHY_TITLE[t.kind];
      if (!spec) return;
      var sub = [];
      if (present(t.team_name)) sub.push(String(t.team_name));
      if (present(t.season)) sub.push('Season ' + t.season);
      out.push({ letter: spec.letter, label: spec.label, sub: sub.join(' · '), j: i, lg: spec.letter === 'N' });
    });
    return out;
  }

  function scoreParts(moment) {
    var s = moment && moment.score;
    if (!s || typeof s !== 'object') return null;
    if (present(s.winner) && present(s.loser)) {
      return { win: s.winner, lose: s.loser, winName: moment.winner_team_name, loseName: moment.loser_team_name };
    }
    if (present(s.home) && present(s.away)) {
      var userWin = moment.user_is_winner !== false;
      return {
        win: userWin ? s.home : s.away,
        lose: userWin ? s.away : s.home,
        winName: moment.winner_team_name,
        loseName: moment.loser_team_name
      };
    }
    return null;
  }

  function bannerSrc(teamName) {
    if (!present(teamName) || typeof global.getTeamAssetPath !== 'function') return '';
    try { return global.getTeamAssetPath(teamName, 'banner_primary') || ''; }
    catch (e) { return ''; }
  }

  function confettiHtml() {
    if (reducedMotion()) return '';
    var h = '';
    var seed = 7;
    function rnd() {
      seed = (seed * 9301 + 49297) % 233280;
      return seed / 233280;
    }
    var i;
    for (i = 0; i < CONFETTI_N; i++) {
      var c = i % 3 === 0 ? 'w' : (i % 5 === 0 ? 'd' : 'g');
      h += '<i class="' + c + '" style="left:' + (rnd() * 100).toFixed(1) + '%;--d:'
        + Math.round(rnd() * 900) + 'ms;--x:' + Math.round((rnd() - 0.5) * 160)
        + 'px;--r:' + Math.round(360 + rnd() * 540) + 'deg;transform:rotate('
        + Math.round(rnd() * 180) + 'deg)"></i>';
    }
    return '<div class="cf" aria-hidden="true">' + h + '</div>';
  }

  function mqHtml(index, total) {
    if (!total || total < 2) return '';
    var dots = '';
    var i;
    for (i = 1; i <= total; i++) dots += '<i class="' + (i === index ? 'on' : '') + '"></i>';
    return '<div class="mq" aria-label="Moment ' + index + ' of ' + total + '">' + dots + '<span>' + index + ' of ' + total + '</span></div>';
  }

  function medHtml(meds, extraClass) {
    if (!meds || !meds.length) return '';
    return '<div class="' + (extraClass || 'pk-meds') + '"' + (extraClass ? '' : ' style="--i:2"') + '>'
      + meds.map(function (m) {
        return '<div class="tro"><span class="med gold' + (m.lg ? ' lg' : '') + '"'
          + (m.j != null ? ' style="--j:' + m.j + '"' : '') + '>' + esc(m.letter)
          + '</span><div><b>' + esc(m.label) + '</b>'
          + (m.sub ? '<span>' + esc(m.sub) + '</span>' : '') + '</div></div>';
      }).join('')
      + '</div>';
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

  function playerAvatar(player) {
    var url = '';
    if (player && player.image_url) url = player.image_url;
    if (!url && player && player.player_id && global.API_CONFIG && typeof global.API_CONFIG.getPlayerImageUrl === 'function') {
      try { url = global.API_CONFIG.getPlayerImageUrl(player.player_id, { size: 'card' }) || ''; }
      catch (e) { url = ''; }
    }
    if (url) return '<span class="av" aria-hidden="true"><img src="' + esc(url) + '" alt=""></span>';
    return '<span class="av" aria-hidden="true">' + esc(initials(player && player.name)) + '</span>';
  }

  function fmtStat(n) {
    if (n == null || n === '') return '';
    var v = Number(n);
    if (!isFinite(v)) return String(n);
    return (Math.round(v * 10) / 10).toFixed(1).replace(/\.0$/, '');
  }

  function playerStats(player) {
    var s = (player && player.stats) || {};
    var bits = [];
    if (present(s.ppg)) bits.push({ n: fmtStat(s.ppg), k: 'PPG' });
    if (present(s.rpg)) bits.push({ n: fmtStat(s.rpg), k: 'RPG' });
    if (present(s.apg)) bits.push({ n: fmtStat(s.apg), k: 'APG' });
    if (present(s.spg)) bits.push({ n: fmtStat(s.spg), k: 'SPG' });
    else if (present(s.bpg)) bits.push({ n: fmtStat(s.bpg), k: 'BPG' });
    return bits;
  }

  function aaLabel(kind) {
    return AA_LABEL[kind] || '';
  }

  // The server names the sting. A row that says "no sting" (another team's title)
  // stays silent; only a caller with no queue row at all gets the default.
  function stingName(item) {
    if (item && Object.prototype.hasOwnProperty.call(item, 'sting')) return item.sting || '';
    return 'STING_SEASON_PEAK';
  }

  function playSting(item) {
    var name = stingName(item);
    if (!name) return;
    try { (global.__gobSeasonPeakSfx || (global.__gobSeasonPeakSfx = [])).push(name); } catch (e) { /* tests */ }
    import('/js/shared/uiSfx.js').then(function (m) {
      if (m && m.playSfx) m.playSfx(name);
    }).catch(function () {});
  }

  function clearSting() {
    if (stingTimer) { clearTimeout(stingTimer); stingTimer = null; }
  }

  function scheduleSting(item) {
    clearSting();
    stingTimer = setTimeout(function () {
      stingTimer = null;
      playSting(item);
    }, STING_MS);
  }

  function rootEl() {
    var el = document.getElementById(ROOT_ID);
    if (!el) {
      el = document.createElement('div');
      el.id = ROOT_ID;
      el.className = 'gob';
      document.body.appendChild(el);
    }
    return el;
  }

  function unbindKeys() {
    if (keyHandler) {
      document.removeEventListener('keydown', keyHandler, true);
      keyHandler = null;
    }
  }

  function close() {
    if (keyHandler) {
      document.removeEventListener('keydown', keyHandler, true);
      keyHandler = null;
    }
    var el = document.getElementById(ROOT_ID);
    if (el) el.innerHTML = '';
    var r = closeResolver;
    closeResolver = null;
    if (r) r();
  }

  function bindContinue(sel) {
    var btn = rootEl().querySelector(sel);
    keyHandler = function (e) {
      if (e.key === 'Escape' || e.key === 'Enter') {
        if (e.key === 'Enter' && document.activeElement && document.activeElement.tagName === 'A') return;
        e.preventDefault();
        close();
      }
    };
    document.addEventListener('keydown', keyHandler, true);
    if (btn) btn.addEventListener('click', function () { close(); });
  }

  function boxScoreHref(moment, options) {
    var url = (options && options.boxScoreUrl) || '';
    if (!url && options && typeof options.boxScoreUrlBuilder === 'function') {
      try { url = options.boxScoreUrlBuilder(moment) || ''; } catch (e) { url = ''; }
    }
    if (!url && moment && present(moment.game_id)) {
      url = '/game.html?game_id=' + encodeURIComponent(moment.game_id);
    }
    return url;
  }

  function showTitle(opts) {
    opts = opts || {};
    var moments = (opts.moments || []).filter(Boolean);
    if (!moments.length) return Promise.resolve();
    return new Promise(function (resolve) {
      unbindKeys();
      closeResolver = resolve;
      var featured = featuredMoment(moments);
      // Someone else's title is an announcement, not the coach's reward:
      // no confetti, no sting, and nothing goes in the Trophy Case.
      var userWon = moments.some(function (m) { return !!(m && m.user_is_winner); });
      var quiet = !userWon || !!(opts.item && opts.item.style === 'quiet');
      var spec = specForType(featured.type) || TITLE_TYPES[0];
      var score = scoreParts(featured);
      var team = featured.winner_team_name || '';
      var art = bannerSrc(team);
      var meds = medallionsFromMoments(moments);
      var q = opts.queue || {};
      var index = q.index || 1;
      var total = q.total || 1;
      var eyebrow = [];
      if (present(featured.season)) eyebrow.push('Season ' + featured.season);
      var nextHint = (total > 1 && opts.nextKind === 'season_review')
        ? ' Your season review is next.'
        : '';
      var box = boxScoreHref(featured, opts);
      var scoreHtml = '';
      if (score) {
        scoreHtml = '<div class="pk-score" style="--i:1">'
          + '<span><b>' + esc(score.win) + '</b>'
          + (present(score.winName) ? ' ' + esc(score.winName) : '') + '</span>'
          + '<i>·</i>'
          + '<span class="l">'
          + (present(score.loseName) ? esc(score.loseName) + ' ' : '')
          + '<b>' + esc(score.lose) + '</b></span></div>';
      }
      var html = '<section class="pk is-open' + (quiet ? ' is-quiet' : '') + (reducedMotion() ? ' rm pk-in' : '') + '" role="dialog" aria-modal="true" aria-labelledby="pk-t">'
        + (art ? '<img class="pk-art" src="' + esc(art) + '" alt="">' : '')
        + (quiet ? '' : confettiHtml())
        + (eyebrow.length ? '<div class="pk-k">' + esc(eyebrow.join(' · ')) + '</div>' : '')
        + '<h1 class="pk-t" id="pk-t">' + esc(spec.headline) + '</h1>'
        + '<div class="pk-rule"></div>'
        + (present(team) ? '<div class="pk-team" style="--i:0">' + esc(team) + '</div>' : '')
        + scoreHtml
        + medHtml(meds)
        + '<div class="pk-f"><p>' + (quiet ? '' : 'Added to your <em>Trophy Case</em>.') + nextHint + '</p>'
        + mqHtml(index, total)
        + (box ? '<a class="lnk" href="' + esc(box) + '" data-sfx="SFX_SELECT">Box score</a>' : '')
        + '<button type="button" class="btn-ghost lg pk-go" data-sfx="SFX_SELECT">Continue</button></div></section>';

      var host = rootEl();
      host.innerHTML = html;
      if (!reducedMotion()) {
        requestAnimationFrame(function () {
          var pk = host.querySelector('.pk');
          if (pk) pk.classList.add('pk-in');
        });
      }
      if (quiet) clearSting();
      else scheduleSting(opts.item);
      bindContinue('.pk-go');
      var go = host.querySelector('.pk-go');
      if (go) go.focus();
    });
  }

  function namedBit(value) {
    if (!present(value)) return '';
    var s = String(value).trim();
    if (/^\d+$/.test(s)) return '';
    return s;
  }

  function pickNamed(key, payload, extras) {
    var list = [payload].concat(extras || []);
    var i;
    var v;
    for (i = 0; i < list.length; i++) {
      if (!list[i]) continue;
      v = namedBit(list[i][key]);
      if (v) return v;
    }
    return '';
  }

  function conferenceLabel(name) {
    var n = namedBit(name);
    if (!n) return 'Conference';
    if (/^conference\b/i.test(n)) return n;
    return 'Conference ' + n;
  }

  function regionLabel(name) {
    var n = namedBit(name);
    if (!n) return 'Region';
    if (/^region\b/i.test(n)) return n;
    return 'Region ' + n;
  }

  function reviewContext(opts, payload) {
    var extras = [].concat(opts.titleMoments || [], opts.titleTrophies || []);
    return {
      conference: pickNamed('conference_name', payload, extras) || pickNamed('conference', payload, extras),
      region: pickNamed('region', payload, extras)
    };
  }

  function reviewMedallions(opts, payload) {
    var ctx = reviewContext(opts, payload);
    var raw;
    if (opts.titleMedallions && opts.titleMedallions.length) {
      raw = opts.titleMedallions;
    } else {
      raw = medallionsFromTrophies(opts.titleTrophies);
    }
    return (raw || []).map(function (m, i) {
      // The two conference titles keep their own wording ("Regular Season
      // Conference Champions", "Conference Tournament Champions"): a named
      // "Conference A2 Champions" cannot say which of the two it is.
      var label = m.label;
      if (m.letter === 'R') {
        label = regionLabel(ctx.region) + ' Champions';
      }
      return {
        letter: m.letter,
        label: label,
        sub: '',
        lg: false,
        j: m.j != null ? m.j : i
      };
    });
  }

  function finishBits(payload, ctx) {
    var bits = [];
    if (!payload) return bits;
    if (present(payload.national_rank)) {
      bits.push({ v: '#' + payload.national_rank, k: 'National' });
    }
    if (present(payload.conf_finish) || present(payload.conference_place)) {
      var place = payload.conf_finish != null ? payload.conf_finish : payload.conference_place;
      bits.push({ v: ordinal(place), k: conferenceLabel(ctx && ctx.conference) });
    }
    return bits;
  }

  function recordHtml(payload) {
    if (!payload) return '';
    if (payload.wins != null && payload.losses != null) {
      return '<div class="rv-rec"><b>' + esc(payload.wins) + '–' + esc(payload.losses) + '</b><span>Record</span></div>';
    }
    return '';
  }

  function bestPlayersHtml(players) {
    if (!players || !players.length) return '';
    return '<div class="sec"><div class="sec-h"><h3>Best Players</h3><span>Season lines</span></div>'
      + players.map(function (p) {
        var meta = [p.position, p.class_year].filter(present).join(' · ');
        var stats = playerStats(p);
        return '<div class="bp">' + playerAvatar(p)
          + '<div class="bp-n"><span class="nm">' + esc(p.name || '') + '</span>'
          + '<span>' + esc(meta)
          + honourTags(p).map(function (tag) { return ' <span class="tg">' + esc(tag) + '</span>'; }).join('')
          + '</span>'
          + (stats.length ? '<div class="bp-l">' + stats.map(function (s) {
            return '<div><b>' + esc(s.n) + '</b><i>' + esc(s.k) + '</i></div>';
          }).join('') + '</div>' : '')
          + '</div></div>';
      }).join('')
      + '</div>';
  }

  function awardsHtml(players) {
    var rows = (players || []).filter(function (p) { return p && (p.all_american || p.all_conference); });
    if (!rows.length) return '';
    var both = rows.some(function (p) { return p.all_american; }) && rows.some(function (p) { return p.all_conference; });
    var sub = both ? 'All-American and All-Conference teams'
      : (rows[0].all_american ? 'All-American teams' : 'All-Conference teams');
    return '<div class="sec"><div class="sec-h"><h3>Awards</h3><span>' + esc(sub) + '</span></div>'
      + rows.map(function (p) {
        var line = [p.position, present(p.stats && p.stats.ppg) ? fmtStat(p.stats.ppg) + ' PPG' : ''].filter(Boolean).join(' · ');
        return '<div class="aw"><div><b>' + esc(p.name || '') + '</b>'
          + (line ? '<span>' + esc(line) + '</span>' : '') + '</div>'
          + honourTags(p).map(function (tag) { return '<span class="tg">' + esc(tag) + '</span>'; }).join('')
          + '</div>';
      }).join('')
      + '</div>';
  }

  function classHtml(recruits) {
    if (!recruits || !recruits.length) return '';
    return '<div class="sec"><div class="sec-h"><h3>Class Signed</h3><span>' + recruits.length
      + ' recruit' + (recruits.length === 1 ? '' : 's') + '</span></div><div class="rc-l">'
      + recruits.map(function (r) {
        var name = r.name || '';
        var pos = present(r.position) ? r.position : r.pos;
        var meta = [pos, r.home_region].filter(present).join(' · ');
        var now = present(r.rt_now) ? r.rt_now : r.rt;
        var pot = present(r.rt_potential) ? r.rt_potential : r.potential_rt_ratcheted;
        return '<div class="rc">' + avatarHtml(name, r.image_id)
          + '<div class="rc-n"><b>' + esc(name) + '</b>'
          + (meta ? '<span>' + esc(meta) + '</span>' : '') + '</div>'
          + rtPair(now, pot) + '</div>';
      }).join('')
      + '</div></div>';
  }

  function showReview(opts) {
    opts = opts || {};
    var payload = opts.payload || {};
    if (payload.eligible === false) return Promise.resolve();
    return new Promise(function (resolve) {
      unbindKeys();
      closeResolver = resolve;
      var q = opts.queue || {};
      var team = payload.program || payload.team_name || opts.teamName || '';
      var season = payload.season != null ? payload.season : opts.season;
      var meds = reviewMedallions(opts, payload);
      var finish = finishBits(payload, reviewContext(opts, payload));
      var rec = recordHtml(payload);
      var players = payload.best_players || [];
      var cols = bestPlayersHtml(players) + awardsHtml(players) + classHtml(payload.class_signed);
      var wash = '';
      if (opts.teamColor) wash = ' style="--team-primary:' + esc(opts.teamColor) + '"';
      var letter = team ? team.charAt(0).toUpperCase() : '';
      var html = '<section class="rv is-open' + (reducedMotion() ? ' rv-in' : '') + '" role="dialog" aria-modal="true" aria-labelledby="rv-t"' + wash + '>'
        + '<div class="rv-h">'
        + (letter ? '<span class="logo">' + esc(letter) + '</span>' : '')
        + '<div>'
        + (present(season) ? '<small>Season ' + esc(season) + ' in review</small>' : '')
        + '<h1 id="rv-t">' + esc(team || 'Season review') + '</h1></div>'
        + (opts.readonly ? '' : mqHtml(q.index || 1, q.total || 1))
        + '</div>'
        + '<div class="rv-top">' + rec
        + (finish.length ? '<div class="rv-fin">' + finish.map(function (f) {
          return '<div><b>' + esc(f.v) + '</b><span>' + esc(f.k) + '</span></div>';
        }).join('') + '</div>' : '')
        + medHtml(meds, 'rv-t')
        + '</div>'
        + '<div class="rv-cols">' + cols + '</div>'
        + '<div class="rv-f"><p>Saved to your <em>Trophy Case</em>'
        + (opts.readonly ? '.' : '. Open it any time from Home Base.')
        + '</p><button type="button" class="btn-ghost lg rv-go" data-sfx="SFX_SELECT">Continue</button></div></section>';

      var host = rootEl();
      host.innerHTML = html;
      if (!reducedMotion()) {
        requestAnimationFrame(function () {
          var rv = host.querySelector('.rv');
          if (rv) rv.classList.add('rv-in');
        });
      }
      bindContinue('.rv-go');
      var go = host.querySelector('.rv-go');
      if (go) go.focus();
    });
  }

  global.SeasonPeak = {
    showTitle: showTitle,
    showReview: showReview,
    close: close,
  };
})(typeof window !== 'undefined' ? window : this);
