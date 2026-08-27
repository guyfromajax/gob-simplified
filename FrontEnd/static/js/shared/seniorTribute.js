/**
 * Senior Tribute — full-screen slideshow of graduating active-roster seniors,
 * then a resolution roster. No pause/skip. Hold is 6000ms per card.
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

  var timer = null;
  var index = 0;
  var players = [];
  var season = 1;
  var onAdvance = null;
  var host = null;

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

  function formatRate(value) {
    var n = Number(value);
    if (!Number.isFinite(n)) return '0.0';
    return n.toFixed(1);
  }

  function titleChips(titles) {
    var src = titles || {};
    var chips = TITLE_LABELS.map(function (item) {
      var count = Number(src[item.key] || 0);
      if (!count) return '';
      var text = count > 1 ? (count + '× ' + item.label) : item.label;
      return '<span class="st-chip">' + escapeHtml(text) + '</span>';
    }).filter(Boolean);
    return chips.length ? chips.join('') : '';
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

  function cardHtml(player) {
    if (!player) return '';
    var chips = titleChips(player.titles);
    return '<div class="st-card">' +
      '<div class="st-shot"><img src="' + escapeHtml(shotUrl(player.player_id, 'modal')) +
        '" alt="" decoding="async"></div>' +
      '<div class="st-name">' + escapeHtml(player.name || '--') + '</div>' +
      '<div class="st-meta">' +
        '<div><small>PPG</small><b>' + escapeHtml(formatRate(player.ppg)) + '</b></div>' +
        '<div><small>RPG</small><b>' + escapeHtml(formatRate(player.rpg)) + '</b></div>' +
        '<div><small>APG</small><b>' + escapeHtml(formatRate(player.apg)) + '</b></div>' +
        '<div><small>DEF%</small><b>' + escapeHtml(String(player.def_pct != null ? player.def_pct : 0)) + '</b></div>' +
      '</div>' +
      (chips ? '<div class="st-titles">' + chips + '</div>' : '') +
    '</div>';
  }

  function resolutionHtml() {
    var rows = players.map(function (player) {
      var chips = titleChips(player.titles);
      var stats = formatRate(player.ppg) + ' PPG · ' + formatRate(player.rpg) +
        ' RPG · ' + formatRate(player.apg) + ' APG · ' +
        (player.def_pct != null ? player.def_pct : 0) + ' DEF%';
      return '<div class="st-row">' +
        '<div class="st-row-shot"><img src="' + escapeHtml(shotUrl(player.player_id, 'card')) +
          '" alt="" decoding="async"></div>' +
        '<div class="st-row-nm">' + escapeHtml(player.name || '--') + '</div>' +
        '<div class="st-row-stats">' + escapeHtml(stats) + '</div>' +
        '<div class="st-row-titles">' + chips + '</div>' +
      '</div>';
    }).join('');
    return '<div class="st-res">' +
      '<div class="st-res-list">' + rows + '</div>' +
      '<button type="button" class="st-advance" id="st-advance">Advance To Next Season</button>' +
    '</div>';
  }

  function headerHtml(subtitle) {
    return '<div class="st-top">' +
      '<div class="st-brand"><small>Season ' + escapeHtml(String(season)) +
        '</small><b>Senior Tribute</b></div>' +
      '<div class="st-prog">' + escapeHtml(subtitle) + '</div>' +
    '</div>';
  }

  function renderCard() {
    if (!host) return;
    var player = players[index];
    host.innerHTML = headerHtml((index + 1) + ' of ' + players.length) +
      '<div class="st-stage">' + cardHtml(player) + '</div>';
  }

  function renderResolution() {
    stopTimer();
    if (!host) return;
    host.innerHTML = headerHtml('Class of Season ' + season) + resolutionHtml();
    var btn = host.querySelector('#st-advance');
    if (btn) btn.addEventListener('click', handleAdvance);
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
