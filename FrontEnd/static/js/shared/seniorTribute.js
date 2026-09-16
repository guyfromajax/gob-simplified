/**
 * Senior Tribute — full-screen slideshow of graduating active-roster seniors,
 * then a resolution roster. No pause/skip. Hold is 6000ms per card.
 *
 * Design "Last Page": _documentation_master/projects/senior-tribute-handoff/
 * (renderCard / renderResolution / flipPortrait are ported from the prototype's
 * renderSlide / renderRes / flip).
 *
 * FCC owns rollover: it starts finish-season in the background and passes
 * onAdvance. This module only presents, then calls onAdvance.
 */
(function () {
  'use strict';

  var HOLD_MS = 6000;
  var TRACK = 'pregame-national-tourney.mp3';
  var TITLE_LABELS = [
    { key: 'conf_rs', label: 'Conf. Regular Season' },
    { key: 'conf_t', label: 'Conf. Tourney' },
    { key: 'region', label: 'Region Tourney' },
    { key: 'national', label: 'National Tourney' },
  ];
  var SLIDE_OUT_MS = 320;            // outgoing slide removed after its 300ms fade + drift
  var FLIP_MS = 520;                 // last slide's portrait travels into its card
  var CARD_STAGGER_MS = 55;          // resolution cards arrive on this stagger
  var CTA_AFTER_LAST_CARD_MS = 300;  // CTA fades in this long after the last card starts
  var LONG_NAME_CHARS = 18;          // above this the slide name steps down a size

  var timer = null;
  var index = 0;
  var players = [];
  var season = 1;
  var onAdvance = null;
  var host = null;
  var flipClone = null;
  var flipTimer = null;

  function escapeHtml(value) {
    if (window.Common && typeof window.Common.escapeHtml === 'function') {
      return window.Common.escapeHtml(value);
    }
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function shotUrl(playerId, size) {
    if (window.API_CONFIG && typeof window.API_CONFIG.getPlayerImageUrl === 'function') {
      return window.API_CONFIG.getPlayerImageUrl(playerId, { size: size || 'modal' });
    }
    return '/images/players/generic_headshot.png';
  }

  function hasValue(value) {
    return value !== null && value !== undefined && String(value).trim() !== '';
  }

  function formatRate(value) {
    var n = Number(value);
    if (!Number.isFinite(n)) return '0.0';
    return n.toFixed(1);
  }

  function formatCount(value) {
    var n = Math.round(Number(value) || 0);
    return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  }

  function defPct(player) {
    return player.def_pct != null ? player.def_pct : 0;
  }

  function nameParts(player) {
    var first = String(player.first_name || '').trim();
    var last = String(player.last_name || '').trim();
    if (first || last) return { first: first, last: last };
    // Payload without split names (backend deployed behind the frontend).
    var words = String(player.name || '--').trim().split(/\s+/);
    return words.length > 1
      ? { first: words.shift(), last: words.join(' ') }
      : { first: '', last: words[0] || '--' };
  }

  function initials(player) {
    var parts = nameParts(player);
    return ((parts.first.charAt(0) || '') + (parts.last.charAt(0) || '')).toUpperCase() || '--';
  }

  function jersey(player) {
    return hasValue(player.jersey_number) ? String(player.jersey_number) : '';
  }

  function titleList(titles) {
    var src = titles || {};
    return TITLE_LABELS.map(function (item) {
      return { label: item.label, count: Number(src[item.key] || 0) };
    }).filter(function (item) { return item.count > 0; });
  }

  function reducedMotion() {
    try {
      return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    } catch (_) {
      return false;
    }
  }

  function tributeMusic(on) {
    var url = (window.API_CONFIG && API_CONFIG.buildStaticPath)
      ? API_CONFIG.buildStaticPath('/js/musicController.js')
      : '/js/musicController.js';
    import(url).then(function (m) {
      if (on) {
        if (m.clearFranchiseMusicState) m.clearFranchiseMusicState();
        if (m.playGameplayTrack) m.playGameplayTrack(TRACK);
      } else if (m.stopGameplayTrack) {
        m.stopGameplayTrack();
      }
    }).catch(function (err) { console.warn('[TRIBUTE] music skipped', err); });
  }

  function stopTimer() {
    if (timer) { clearInterval(timer); timer = null; }
  }

  function clearFlip() {
    if (flipTimer) { clearTimeout(flipTimer); flipTimer = null; }
    if (flipClone) { flipClone.remove(); flipClone = null; }
  }

  // ---------- markup ----------

  function statCellsHtml(player) {
    return '<u><em>ppg</em><b>' + escapeHtml(formatRate(player.ppg)) + '</b></u>' +
      '<u><em>rpg</em><b>' + escapeHtml(formatRate(player.rpg)) + '</b></u>' +
      '<u><em>apg</em><b>' + escapeHtml(formatRate(player.apg)) + '</b></u>' +
      '<u><em>def%</em><b>' + escapeHtml(String(defPct(player))) + '</b></u>';
  }

  function slideNoShotHtml(player) {
    var num = jersey(player);
    var sub = hasValue(player.position) ? player.position + ' · Senior' : 'Senior';
    return '<div class="st-noshot"><b>' + escapeHtml(num || initials(player)) + '</b>' +
      '<small>' + escapeHtml(sub) + '</small></div>';
  }

  function slideHtml(player) {
    var parts = nameParts(player);
    var fullName = (parts.first + ' ' + parts.last).trim();
    var num = jersey(player);
    var eyebrow = ['Class of Season ' + season];
    if (num) eyebrow.push('#' + num);
    if (hasValue(player.position)) eyebrow.push(String(player.position));

    var career = [];
    if (hasValue(player.games_played)) career.push(formatCount(player.games_played) + ' games');
    if (hasValue(player.career_points)) career.push(formatCount(player.career_points) + ' career points');

    var titles = titleList(player.titles);
    var titlesHtml = titles.length
      ? '<div class="st-titles">' + titles.map(function (item) {
        var text = item.count > 1 ? (item.count + '× ' + item.label) : item.label;
        return '<span><s aria-hidden="true"></s>' + escapeHtml(text) + '</span>';
      }).join('') + '</div>'
      : '';

    return '<div class="st-slide in">' +
      '<div class="st-copy">' +
        '<div class="st-eyebrow">' + escapeHtml(eyebrow.join(' · ')) + '</div>' +
        '<h2 class="st-name' + (fullName.length > LONG_NAME_CHARS ? ' long' : '') + '">' +
          (parts.first ? '<span>' + escapeHtml(parts.first) + '</span>' : '') +
          '<em>' + escapeHtml(parts.last || parts.first) + '</em>' +
        '</h2>' +
        '<div class="st-hr"></div>' +
        '<div class="st-stats">' + statCellsHtml(player) + '</div>' +
        (career.length ? '<div class="st-career">' + escapeHtml(career.join(' · ')) + '</div>' : '') +
        titlesHtml +
      '</div>' +
      '<div class="st-shot">' +
        (num ? '<div class="st-shot-num" aria-hidden="true">' + escapeHtml(num) + '</div>' : '') +
        '<img src="' + escapeHtml(shotUrl(player.player_id, 'modal')) + '" alt="" decoding="async">' +
      '</div>' +
    '</div>';
  }

  function cardHtml(player, i, single) {
    var num = jersey(player);
    var meta = [];
    if (hasValue(player.position)) meta.push(String(player.position));
    if (hasValue(player.games_played)) meta.push(formatCount(player.games_played) + ' games');
    var marks = titleList(player.titles).reduce(function (sum, item) { return sum + item.count; }, 0);
    var marksHtml = '';
    for (var m = 0; m < marks; m++) marksHtml += '<s></s>';
    return '<div class="st-card" style="--d:' + (i * CARD_STAGGER_MS) + 'ms">' +
      '<div class="st-shotbox">' +
        (num ? '<div class="st-cnum" aria-hidden="true">' + escapeHtml(num) + '</div>' : '') +
        '<img src="' + escapeHtml(shotUrl(player.player_id, single ? 'modal' : 'card')) +
          '" alt="" decoding="async" data-initials="' + escapeHtml(initials(player)) + '">' +
      '</div>' +
      '<div class="st-cnm">' + escapeHtml(player.name || '--') + '</div>' +
      (meta.length ? '<div class="st-cmeta">' + escapeHtml(meta.join(' · ')) + '</div>' : '') +
      '<div class="st-cst">' + statCellsHtml(player) + '</div>' +
      (marks ? '<div class="st-cti" aria-hidden="true">' + marksHtml + '</div>' : '') +
    '</div>';
  }

  function chromeHtml(right) {
    return '<div class="st-bar"><i></i></div>' +
      '<div class="st-top">' +
        '<div class="st-brand"><small>Season ' + escapeHtml(String(season)) +
          '</small><b>Senior Tribute</b></div>' +
        '<div class="st-count">' + escapeHtml(right) + '</div>' +
      '</div>';
  }

  // A portrait that fails to load falls back to the ghost numeral / initials — never a
  // broken image box. `complete && !naturalWidth` catches an error that already fired.
  function onImageFail(img, fallback) {
    if (!img) return;
    var done = false;
    var fail = function () {
      if (done) return;
      done = true;
      fallback(img);
    };
    img.addEventListener('error', fail);
    if (img.complete && img.getAttribute('src') && img.naturalWidth === 0) fail();
  }

  // ---------- render ----------

  function runBar() {
    var bar = host && host.querySelector('.st-bar i');
    if (!bar) return;
    bar.classList.remove('run');
    if (reducedMotion()) {
      // Steps per slide instead of animating; the 6s cadence is unchanged.
      bar.style.setProperty('--step', String((index + 1) / players.length));
      return;
    }
    void bar.offsetWidth; // restart the fill animation
    bar.style.setProperty('--hold', HOLD_MS + 'ms');
    bar.classList.add('run');
  }

  function renderCard() {
    if (!host) return;
    var player = players[index];
    var stage = host.querySelector('.st-stage');
    if (!stage) {
      host.innerHTML = chromeHtml('') + '<div class="st-stage"></div>';
      stage = host.querySelector('.st-stage');
    }
    host.querySelector('.st-count').textContent = (index + 1) + ' of ' + players.length;

    var prev = stage.querySelector('.st-slide');
    stage.insertAdjacentHTML('beforeend', slideHtml(player));
    var slide = stage.lastElementChild;
    onImageFail(slide.querySelector('.st-shot img'), function () {
      var shot = slide.querySelector('.st-shot');
      if (shot) shot.innerHTML = slideNoShotHtml(player);
    });

    // Outgoing and incoming overlap, so the stage is never empty.
    if (prev) {
      if (reducedMotion()) {
        prev.remove();
      } else {
        prev.classList.remove('in');
        prev.classList.add('out');
        setTimeout(function () { prev.remove(); }, SLIDE_OUT_MS);
      }
    }
    runBar();
  }

  function flipPortrait(fromRect, fromSrc) {
    var cards = host.querySelectorAll('.st-card');
    var target = cards[cards.length - 1]; // the last slide is the last card
    var img = target && target.querySelector('.st-shotbox img');
    if (!img) return;
    var to = img.getBoundingClientRect();
    var clone = document.createElement('img');
    clone.className = 'st-flip';
    clone.alt = '';
    clone.src = fromSrc;
    clone.style.left = fromRect.left + 'px';
    clone.style.top = fromRect.top + 'px';
    clone.style.width = fromRect.width + 'px';
    clone.style.height = fromRect.height + 'px';
    document.body.appendChild(clone);
    flipClone = clone;
    img.style.opacity = '0';
    requestAnimationFrame(function () {
      clone.style.transition = 'left ' + FLIP_MS + 'ms cubic-bezier(.3,.85,.25,1), top ' + FLIP_MS +
        'ms cubic-bezier(.3,.85,.25,1), width ' + FLIP_MS + 'ms cubic-bezier(.3,.85,.25,1), height ' +
        FLIP_MS + 'ms cubic-bezier(.3,.85,.25,1)';
      clone.style.left = to.left + 'px';
      clone.style.top = to.top + 'px';
      clone.style.width = to.width + 'px';
      clone.style.height = to.height + 'px';
    });
    flipTimer = setTimeout(function () {
      img.style.opacity = '';
      clearFlip();
    }, FLIP_MS + 40);
  }

  function renderResolution() {
    stopTimer();
    if (!host) return;
    var slideImg = host.querySelector('.st-slide.in .st-shot img');
    var fromRect = slideImg && !reducedMotion() ? slideImg.getBoundingClientRect() : null;
    var fromSrc = slideImg ? slideImg.currentSrc || slideImg.src : '';

    var count = players.length;
    var single = count === 1;
    host.className = 'st-host ' + (single ? 'st-c-1' : count <= 6 ? 'st-c-few' : 'st-c-many');
    host.style.setProperty('--cols', String(Math.min(count, 6)));
    var ctaDelay = (count - 1) * CARD_STAGGER_MS + CTA_AFTER_LAST_CARD_MS;

    host.innerHTML = chromeHtml('Class of Season ' + season) +
      '<div class="st-res">' +
        '<div class="st-head"><h2>Class of Season ' + escapeHtml(String(season)) + '</h2>' +
          '<small>' + count + ' senior' + (count > 1 ? 's' : '') + ' · thank you</small></div>' +
        '<div class="st-cards">' + players.map(function (player, i) {
          return cardHtml(player, i, single);
        }).join('') + '</div>' +
        '<button type="button" class="st-advance" id="st-advance" style="--d:' + ctaDelay + 'ms">' +
          'Advance To Next Season</button>' +
      '</div>';

    var bar = host.querySelector('.st-bar i');
    if (bar) bar.style.transform = 'scaleX(1)';

    host.querySelectorAll('.st-shotbox img').forEach(function (img) {
      onImageFail(img, function (failed) {
        var box = failed.parentNode;
        var mark = document.createElement('div');
        mark.className = 'st-cinit';
        mark.textContent = failed.getAttribute('data-initials') || '--';
        failed.replaceWith(mark);
        if (box && flipClone) clearFlip();
      });
    });

    var btn = host.querySelector('#st-advance');
    if (btn) btn.addEventListener('click', handleAdvance);

    if (fromRect && fromSrc) flipPortrait(fromRect, fromSrc);
  }

  function advanceCard() {
    index += 1;
    if (index >= players.length) {
      renderResolution();
      return;
    }
    renderCard();
  }

  function handleAdvance() {
    var btn = host && host.querySelector('#st-advance');
    if (btn) {
      btn.disabled = true;
      btn.textContent = 'Advancing…';
    }
    tributeMusic(false);
    if (typeof onAdvance === 'function') onAdvance();
  }

  function teardown() {
    stopTimer();
    clearFlip();
    tributeMusic(false);
    if (host) host.remove();
    host = null;
  }

  function start(opts) {
    teardown();
    players = (opts && opts.players) || [];
    season = Number(opts && opts.season) || 1;
    onAdvance = opts && opts.onAdvance;
    if (!players.length) {
      if (typeof onAdvance === 'function') onAdvance();
      return;
    }
    index = 0;
    host = document.createElement('div');
    host.className = 'st-host';
    host.id = 'senior-tribute';
    host.setAttribute('role', 'dialog');
    host.setAttribute('aria-modal', 'true');
    host.setAttribute('aria-label', 'Senior Tribute');
    // Team primary colour is atmosphere only (one soft radial on the host).
    if (opts && opts.teamColor) host.style.setProperty('--st-team', opts.teamColor);
    document.body.appendChild(host);
    tributeMusic(true);
    renderCard();
    timer = setInterval(advanceCard, HOLD_MS);
  }

  window.SeniorTribute = {
    start: start,
    teardown: teardown,
    HOLD_MS: HOLD_MS,
  };
})();
