/**
 * FCC "Big News" modals — Bracket Reveal & Recruiting Results (shared Arena Card shell).
 */
(function (global) {
  'use strict';

  var TROPHY_SVG =
    '<svg viewBox="0 0 48 48" fill="none" aria-hidden="true">' +
    '<path d="M14 7h20v8a10 10 0 0 1-20 0V7z" fill="url(#bn-tg)" stroke="#f0c560" stroke-width="1.2"/>' +
    '<path d="M14 9H8v3a7 7 0 0 0 7 7" stroke="#d4a848" stroke-width="2" fill="none" stroke-linecap="round"/>' +
    '<path d="M34 9h6v3a7 7 0 0 1-7 7" stroke="#d4a848" stroke-width="2" fill="none" stroke-linecap="round"/>' +
    '<path d="M24 25v7" stroke="#d4a848" stroke-width="2.4" stroke-linecap="round"/>' +
    '<path d="M17 40c0-3 3-5 7-5s7 2 7 5H17z" fill="url(#bn-tg)" stroke="#f0c560" stroke-width="1.2"/>' +
    '<rect x="20" y="32" width="8" height="4" rx="1" fill="#d4a848"/>' +
    '<defs><linearGradient id="bn-tg" x1="24" y1="7" x2="24" y2="41" gradientUnits="userSpaceOnUse">' +
    '<stop stop-color="#f4d27a"/><stop offset="1" stop-color="#c79a3e"/></linearGradient></defs></svg>';

  var STAR_SEAL_SVG =
    '<svg viewBox="0 0 48 48" fill="none" aria-hidden="true">' +
    '<circle cx="24" cy="24" r="20" fill="url(#bn-seal)" stroke="#f0c560" stroke-width="1.2"/>' +
    '<path d="M24 10l2.8 8.6h9.1l-7.4 5.4 2.8 8.6L24 27.2l-7.3 5.4 2.8-8.6-7.4-5.4h9.1L24 10z" fill="#f0c560"/>' +
    '<defs><linearGradient id="bn-seal" x1="24" y1="4" x2="24" y2="44" gradientUnits="userSpaceOnUse">' +
    '<stop stop-color="#3a3018"/><stop offset="1" stop-color="#1a1408"/></linearGradient></defs></svg>';

  var presentedBracket = false;
  var presentedRecruiting = false;
  var activeOverlay = null;
  var pendingTopData = null;
  var retryTimer = null;
  var retries = 0;
  var MAX_RETRIES = 300;
  var fitObservers = [];

  function blockerVisible() {
    return Boolean(
      document.querySelector(
        '.cm-overlay.is-visible,' +
          '.arch-reveal-overlay.is-visible,' +
          '.afm-overlay.is-visible,' +
          '.gob-talert-overlay,' +
          '.sammy-modal-backdrop.open,' +
          '.fcc-modal-overlay,' +
          '.bn-overlay.show,' +
          '.celebrate.show'
      )
    );
  }

  function franchiseId() {
    return global.franchiseId || new URLSearchParams(window.location.search).get('franchise_id');
  }

  function authHeaders() {
    return typeof API_CONFIG !== 'undefined' && API_CONFIG.getAuthHeaders
      ? API_CONFIG.getAuthHeaders()
      : {};
  }

  function spawnConfetti(container, count) {
    if (!container) return;
    container.innerHTML = '';
    var colors = ['#f0c560', '#d4a848', '#2bd66a', '#ffffff'];
    var motionOk = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    for (var i = 0; i < count; i += 1) {
      var piece = document.createElement('i');
      piece.style.left = Math.random() * 100 + '%';
      piece.style.background = colors[i % colors.length];
      if (motionOk) {
        piece.style.animationDuration = 3.6 + Math.random() * 2.4 + 's';
        piece.style.animationDelay = Math.random() * 1.2 + 's';
      }
      container.appendChild(piece);
    }
  }

  function disconnectFitObservers() {
    fitObservers.forEach(function (obs) {
      try {
        obs.disconnect();
      } catch (e) {}
    });
    fitObservers = [];
  }

  function fitBracketToContainer(fitEl, scaleEl, onSuccess) {
    if (!fitEl || !scaleEl) return;

    var attempt = 0;
    var maxAttempts = 12;

    function runFit() {
      attempt += 1;
      var fitWidth = fitEl.clientWidth;
      if (fitWidth <= 0) {
        if (attempt < maxAttempts) {
          setTimeout(runFit, 80);
        }
        return;
      }

      scaleEl.style.transform = 'none';
      scaleEl.style.height = 'auto';
      var bracketWidth = scaleEl.offsetWidth;
      if (bracketWidth <= 0) {
        if (attempt < maxAttempts) {
          setTimeout(runFit, 80);
        }
        return;
      }

      var scale = Math.min(1, fitWidth / bracketWidth);
      if (scale <= 0) return;

      scaleEl.style.transform = 'scale(' + scale + ')';
      scaleEl.style.height = scaleEl.offsetHeight * scale + 'px';

      if (typeof onSuccess === 'function') {
        onSuccess(scale);
      }
    }

    runFit();

    if (typeof ResizeObserver !== 'undefined') {
      var obs = new ResizeObserver(function () {
        runFit();
      });
      obs.observe(fitEl);
      fitObservers.push(obs);
    }

    if (!scaleEl._bnResizeBound) {
      scaleEl._bnResizeBound = true;
      var resizeTimer;
      window.addEventListener('resize', function () {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(runFit, 120);
      });
    }
  }

  function closeOverlay(markSeenFn) {
    if (!activeOverlay) return;
    activeOverlay.classList.remove('show');
    activeOverlay.setAttribute('aria-hidden', 'true');
    disconnectFitObservers();
    var done = markSeenFn ? markSeenFn() : Promise.resolve();
    activeOverlay = null;
    return done.then(function () {
      if (pendingTopData) {
        var data = pendingTopData;
        pendingTopData = null;
        maybeShow(data);
      }
    });
  }

  function buildShell(opts) {
    var overlay = document.createElement('div');
    overlay.className = 'bn-overlay';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-hidden', 'true');

    var rays = document.createElement('div');
    rays.className = 'bn-rays';
    rays.setAttribute('aria-hidden', 'true');

    var confetti = document.createElement('div');
    confetti.className = 'confetti';
    confetti.setAttribute('aria-hidden', 'true');
    spawnConfetti(confetti, opts.confettiCount || 60);

    var modal = document.createElement('div');
    modal.className = 'bn-modal';

    var closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.className = 'bn-close';
    closeBtn.setAttribute('aria-label', 'Close');
    closeBtn.textContent = '\u00d7';

    var head = document.createElement('div');
    head.className = 'bn-head';

    var emblem = document.createElement('div');
    emblem.className = 'bn-emblem';
    emblem.innerHTML = opts.emblemSvg || TROPHY_SVG;

    var eyebrow = document.createElement('div');
    eyebrow.className = 'bn-eyebrow';
    eyebrow.textContent = opts.eyebrow || '';

    var title = document.createElement('div');
    title.className = 'bn-title';
    title.textContent = opts.title || '';

    var sub = document.createElement('div');
    sub.className = 'bn-sub';
    sub.textContent = opts.subtitle || '';

    head.appendChild(emblem);
    head.appendChild(eyebrow);
    head.appendChild(title);
    head.appendChild(sub);

    var body = document.createElement('div');
    body.className = 'bn-body';
    if (opts.bodyNode) body.appendChild(opts.bodyNode);

    var foot = document.createElement('div');
    foot.className = 'bn-foot';
    var cta = document.createElement('button');
    cta.type = 'button';
    cta.className = 'bn-cta';
    cta.textContent = opts.ctaLabel || 'Got it';
    foot.appendChild(cta);

    modal.appendChild(closeBtn);
    modal.appendChild(head);
    modal.appendChild(body);
    modal.appendChild(foot);

    overlay.appendChild(rays);
    overlay.appendChild(confetti);
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    function dismiss() {
      closeOverlay(opts.onDismiss);
    }

    closeBtn.addEventListener('click', dismiss);
    cta.addEventListener('click', dismiss);
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) dismiss();
    });

    return { overlay: overlay, body: body, cta: cta };
  }

  function markBracketSeen(revealKey) {
    var fid = franchiseId();
    if (!fid || !revealKey || typeof API_CONFIG === 'undefined') return Promise.resolve();
    return fetch(API_CONFIG.buildUrl('/franchise/bracket-reveal-modal-seen'), {
      method: 'PATCH',
      headers: Object.assign({ 'Content-Type': 'application/json' }, authHeaders()),
      body: JSON.stringify({ franchise_id: fid, reveal_key: revealKey }),
    }).catch(function (err) {
      console.warn('[BigNewsModals] bracket seen persist failed:', err);
    });
  }

  function markRecruitingSeen() {
    var fid = franchiseId();
    if (!fid || typeof API_CONFIG === 'undefined') return Promise.resolve();
    return fetch(API_CONFIG.buildUrl('/franchise/recruiting-results-modal-seen'), {
      method: 'PATCH',
      headers: Object.assign({ 'Content-Type': 'application/json' }, authHeaders()),
      body: JSON.stringify({ franchise_id: fid }),
    }).catch(function (err) {
      console.warn('[BigNewsModals] recruiting seen persist failed:', err);
    });
  }

  function rtClass(rt, year) {
    if (typeof getRecruitRtBucketClassForYear === 'function') {
      return getRecruitRtBucketClassForYear(rt, year);
    }
    if (typeof getRecruitRtBucketClass === 'function') {
      return getRecruitRtBucketClass(rt);
    }
    var v = Number(rt);
    if (!isFinite(v)) return '';
    if (v <= 29) return 'rt-low';
    if (v <= 39) return 'rt-mid';
    if (v <= 49) return 'rt-high';
    return 'rt-elite';
  }

  function formatHt(raw) {
    if (typeof formatHeight === 'function') return formatHeight(raw);
    return raw != null ? String(raw) : '--';
  }

  function showRecruitingModal(payload) {
    presentedRecruiting = true;
    var recruits = payload.recruits || [];
    var list = document.createElement('div');
    list.className = 'bn-recruits';

    recruits.forEach(function (r, idx) {
      var card = document.createElement('div');
      card.className = 'rc';
      card.style.setProperty('--d', idx * 70 + 'ms');

      var pos = document.createElement('div');
      pos.className = 'rc__pos';
      pos.textContent = r.pos || '--';

      var mid = document.createElement('div');
      var name = document.createElement('div');
      name.className = 'rc__name';
      name.textContent = r.name || '--';
      var meta = document.createElement('div');
      meta.className = 'rc__meta';
      var wt = r.weight != null ? r.weight + ' lbs' : '--';
      meta.textContent = [r.archetype || '--', formatHt(r.height), wt].join(' \u00b7 ');
      mid.appendChild(name);
      mid.appendChild(meta);

      var rtWrap = document.createElement('div');
      rtWrap.className = 'rc__rt';
      var rtNum = document.createElement('div');
      rtNum.className = 'rc__rtnum ' + rtClass(r.rt, r.year);
      rtNum.textContent = r.rt != null ? String(r.rt) : '--';
      var rtLabel = document.createElement('div');
      rtLabel.className = 'rc__rtlabel';
      rtLabel.textContent = 'RT';
      rtWrap.appendChild(rtNum);
      rtWrap.appendChild(rtLabel);

      card.appendChild(pos);
      card.appendChild(mid);
      card.appendChild(rtWrap);
      list.appendChild(card);
    });

    var footer = document.createElement('div');
    footer.className = 'bn-recruits__footer';
    var n = payload.count != null ? payload.count : recruits.length;
    footer.textContent = n + ' recruit' + (n === 1 ? '' : 's') + ' signed \u2014 welcome to the program.';
    list.appendChild(footer);

    var shell = buildShell({
      emblemSvg: STAR_SEAL_SVG,
      eyebrow: 'Recruiting Results \u00b7 Signing Day',
      title: 'Congrats, Coach!',
      subtitle: 'You signed the following recruits to the program.',
      ctaLabel: 'Continue',
      confettiCount: 75,
      bodyNode: list,
      onDismiss: markRecruitingSeen,
    });

    activeOverlay = shell.overlay;
    activeOverlay.classList.add('show');
    activeOverlay.setAttribute('aria-hidden', 'false');
  }

  function showBracketModal(payload, topData, maps) {
    presentedBracket = true;
    maps = maps || {};

    var fit = document.createElement('div');
    fit.className = 'bn-bracket-fit';

    var scale = document.createElement('div');
    scale.className = 'bn-bracket-scale';
    fit.appendChild(scale);

    if (typeof FccTournamentStyleA !== 'undefined' && FccTournamentStyleA.renderInto) {
      var tierTitles = {
        conference: 'Conference Tournament',
        region: 'Region Tournament',
        national: 'National Tournament',
      };
      FccTournamentStyleA.renderInto(scale, {
        sectionTitle: tierTitles[payload.tier] || 'Tournament',
        layout: payload.layout || 'full',
        bracket: payload.bracket || {},
        seeds: payload.seeds || {},
        teamIdToNameMap: maps.teamIdToNameMap || topData.team_name_map || {},
        teamIdMetaMap: maps.teamIdMetaMap || {},
        userTeamId: maps.userTeamId || topData.team_id,
        topData: Object.assign({}, topData, { week: payload.display_week || topData.week }),
        revealMode: true,
        tierHint: payload.tier,
      });
    } else {
      scale.innerHTML = '<p>Tournament bracket UI not loaded.</p>';
    }

    var shell = buildShell({
      emblemSvg: TROPHY_SVG,
      eyebrow: payload.eyebrow || '',
      title: 'The Bracket Is Set!',
      subtitle: 'Eight teams. One title. Here\u2019s the road ahead.',
      ctaLabel: 'Got it',
      confettiCount: 60,
      bodyNode: fit,
      onDismiss: function () {
        return markBracketSeen(payload.reveal_key);
      },
    });

    activeOverlay = shell.overlay;
    activeOverlay.classList.add('show');
    activeOverlay.setAttribute('aria-hidden', 'false');

    fitBracketToContainer(fit, scale, function () {
      var grid = scale.querySelector('.fcc-tb-classic, .fcc-tb-region');
      if (grid && typeof FccTournamentStyleA !== 'undefined' && FccTournamentStyleA.scheduleConnectorRedraw) {
        FccTournamentStyleA.scheduleConnectorRedraw(grid, maps.userTeamId || topData.team_id, { revealMode: true });
      }
    });
  }

  function scheduleRetry(data) {
    if (retryTimer || retries >= MAX_RETRIES) return;
    retryTimer = setTimeout(function () {
      retryTimer = null;
      retries += 1;
      maybeShow(data);
    }, 1000);
  }

  function maybeShow(topData, maps) {
    if (!topData || activeOverlay) return;
    if (blockerVisible()) {
      pendingTopData = topData;
      scheduleRetry(topData);
      return;
    }

    var bracketPayload = topData.bracket_reveal_modal;
    if (!presentedBracket && bracketPayload && bracketPayload.eligible) {
      showBracketModal(bracketPayload, topData, maps);
      return;
    }

    var recruitingPayload = topData.recruiting_results_modal;
    if (!presentedRecruiting && recruitingPayload && recruitingPayload.eligible) {
      showRecruitingModal(recruitingPayload);
    }
  }

  global.BigNewsModals = {
    maybeShow: maybeShow,
    fitBracketToContainer: fitBracketToContainer,
  };
})(typeof window !== 'undefined' ? window : this);
