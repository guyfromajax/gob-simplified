/**
 * Page Load Overlay – shared full-page loader for court, FCC, TCC, set-lineup
 *
 * Prevents stale data from being visible on initial load. Show overlay as soon as
 * the destination page runs; hide when the page is "ready" (data loaded, UI rendered).
 *
 * Usage:
 *   PageLoadOverlay.show();   // at start of page init
 *   PageLoadOverlay.hide();   // when data is loaded and UI is ready
 *
 * Load early (e.g. in <head>) so overlay can be shown before body content paints.
 */
(function (global) {
  'use strict';

  var OVERLAY_ID = 'page-load-overlay';
  var LOADER_IMG_PATH = '/images/loader1.gif';
  var Z_INDEX = 999999;
  var DEFAULT_BANNER_PATH = '/images/teams/general/general_banner_primary.jpg';
  var pulseFeedTimer = null;

  function clearPulseFeedTimer() {
    if (pulseFeedTimer) {
      clearInterval(pulseFeedTimer);
      pulseFeedTimer = null;
    }
  }

  function getPulseImageSrc(options) {
    if (options && options.imageSrc) return options.imageSrc;
    if (
      options &&
      options.teamName &&
      typeof global.getTeamAssetPath === 'function'
    ) {
      return global.getTeamAssetPath(options.teamName, options.assetKey || 'banner_primary');
    }
    return DEFAULT_BANNER_PATH;
  }

  function ensureOverlayStructure(overlay) {
    if (!overlay) return overlay;

    overlay.style.cssText =
      'position:fixed;inset:0;z-index:' + Z_INDEX + ';' +
      'background:rgba(0,0,0,0.92);' +
      'display:flex;align-items:center;justify-content:center;' +
      'margin:0;padding:0;';

    var content = overlay.querySelector('.page-load-overlay-content');
    if (!content) {
      content = document.createElement('div');
      content.className = 'page-load-overlay-content';
      content.style.cssText = 'display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px;text-align:center;';

      while (overlay.firstChild) {
        content.appendChild(overlay.firstChild);
      }
      overlay.appendChild(content);
    }

    // Spinner must use .page-load-overlay-spinner so applyPulseVariant can hide it. Static HTML
    // (e.g. court.html) may inject a bare <img> loader without that class.
    var spinnerImg = content.querySelector('.page-load-overlay-spinner');
    if (!spinnerImg) {
      for (var ci = 0; ci < content.children.length; ci++) {
        var ch = content.children[ci];
        if (
          ch &&
          ch.tagName === 'IMG' &&
          !ch.classList.contains('page-load-overlay-pulse-image')
        ) {
          ch.className = 'page-load-overlay-spinner';
          ch.alt = 'Loading…';
          spinnerImg = ch;
          break;
        }
      }
    }
    if (!spinnerImg) {
      spinnerImg = document.createElement('img');
      spinnerImg.className = 'page-load-overlay-spinner';
      spinnerImg.alt = 'Loading…';
      content.appendChild(spinnerImg);
    }
    spinnerImg.src = LOADER_IMG_PATH;
    spinnerImg.style.cssText = 'width:240px;height:auto;max-width:90vw;';

    var message = content.querySelector('.page-load-overlay-message');
    if (!message) {
      message = document.createElement('div');
      message.className = 'page-load-overlay-message';
      message.style.cssText = 'color:#ffffff;font-weight:700;font-size:24px;line-height:1.2;';
      content.appendChild(message);
    }

    var pulse = content.querySelector('.page-load-overlay-pulse');
    if (!pulse) {
      pulse = document.createElement('div');
      pulse.className = 'page-load-overlay-pulse';
      pulse.style.cssText = 'display:none;width:min(560px,100%);text-align:center;';
      pulse.innerHTML = [
        '<p class="page-load-overlay-pulse-label"></p>',
        '<img class="page-load-overlay-pulse-image" alt="">',
        '<h2 class="page-load-overlay-pulse-title"></h2>',
        '<p class="page-load-overlay-pulse-subtitle"></p>',
        '<p class="page-load-overlay-pulse-stat"></p>',
        '<div class="page-load-overlay-pulse-indicator" aria-hidden="true"><span></span></div>'
      ].join('');
      content.appendChild(pulse);
    }

    var pulseLabel = pulse.querySelector('.page-load-overlay-pulse-label');
    if (pulseLabel) {
      pulseLabel.style.cssText =
        "display:none;margin:0 0 18px;font-family:'Inter',sans-serif;font-size:16px;line-height:1.4;letter-spacing:0;color:rgba(255,255,255,0.72);";
    }

    var pulseImage = pulse.querySelector('.page-load-overlay-pulse-image');
    if (pulseImage) {
      pulseImage.style.cssText = 'width:100%;display:block;border-radius:18px;box-shadow:0 18px 36px rgba(0,0,0,0.28);';
    }

    var pulseTitle = pulse.querySelector('.page-load-overlay-pulse-title');
    if (pulseTitle) {
      pulseTitle.style.cssText =
        "margin:26px 0 10px;font-family:'Bebas Neue',sans-serif;font-size:48px;line-height:1;letter-spacing:0.03em;color:#ffffff;";
    }

    var pulseSubtitle = pulse.querySelector('.page-load-overlay-pulse-subtitle');
    if (pulseSubtitle) {
      pulseSubtitle.style.cssText = 'margin:0 0 22px;font-size:16px;color:rgba(255,255,255,0.68);';
    }

    var pulseStat = pulse.querySelector('.page-load-overlay-pulse-stat');
    if (pulseStat) {
      pulseStat.style.cssText =
        "display:none;min-height:44px;margin:22px auto 22px;max-width:min(620px,92vw);font-family:'Inter',sans-serif;font-size:16px;line-height:1.4;letter-spacing:0;color:rgba(255,255,255,0.86);";
    }

    var pulseIndicator = pulse.querySelector('.page-load-overlay-pulse-indicator');
    if (pulseIndicator) {
      pulseIndicator.style.cssText =
        'width:min(220px,100%);height:8px;margin:0 auto;border-radius:999px;overflow:hidden;background:rgba(255,255,255,0.08);box-shadow:inset 0 1px 0 rgba(255,255,255,0.05);';
    }

    var pulseBar = pulse.querySelector('.page-load-overlay-pulse-indicator span');
    if (pulseBar) {
      pulseBar.style.cssText =
        'display:block;width:100%;height:100%;border-radius:inherit;background:linear-gradient(90deg, rgba(52,236,39,0.35), #34EC27 48%, rgba(52,236,39,0.45));transform-origin:left center;animation:pageLoadOverlayPulseBar 1.2s ease-in-out infinite;';
    }

    if (!document.getElementById('page-load-overlay-pulse-style')) {
      var style = document.createElement('style');
      style.id = 'page-load-overlay-pulse-style';
      style.textContent = '@keyframes pageLoadOverlayPulseBar { 0%, 100% { opacity: 0.5; transform: scaleX(0.35); } 50% { opacity: 1; transform: scaleX(1); } }';
      document.head.appendChild(style);
    }

    return overlay;
  }

  function normalizeOptions(input) {
    if (typeof input === 'string' || input == null) {
      return { variant: 'spinner', message: input || '' };
    }
    if (typeof input === 'object') {
      return {
        variant: input.variant || 'spinner',
        message: input.message || input.title || '',
        title: input.title || input.message || '',
        subtitle: input.subtitle || '',
        label: input.label || input.pulseLabel || '',
        statLines: Array.isArray(input.statLines) ? input.statLines : [],
        statIntervalMs: Number(input.statIntervalMs) > 0 ? Number(input.statIntervalMs) : 8000,
        imageSrc: input.imageSrc || '',
        teamName: input.teamName || '',
        assetKey: input.assetKey || 'banner_primary'
      };
    }
    return { variant: 'spinner', message: '' };
  }

  function applySpinnerVariant(overlay, options) {
    var content = overlay.querySelector('.page-load-overlay-content');
    if (!content) return;
    var spinner = content.querySelector('.page-load-overlay-spinner');
    var message = content.querySelector('.page-load-overlay-message');
    var pulse = content.querySelector('.page-load-overlay-pulse');
    if (spinner) spinner.style.display = 'block';
    if (message) {
      message.style.display = 'block';
      message.textContent = options.message || '';
    }
    if (pulse) pulse.style.display = 'none';
    clearPulseFeedTimer();
  }

  function applyPulseVariant(overlay, options) {
    clearPulseFeedTimer();
    var content = overlay.querySelector('.page-load-overlay-content');
    if (!content) return;
    var spinners = content.querySelectorAll('.page-load-overlay-spinner');
    for (var si = 0; si < spinners.length; si++) {
      spinners[si].style.display = 'none';
    }
    var message = content.querySelector('.page-load-overlay-message');
    var pulse = content.querySelector('.page-load-overlay-pulse');
    if (message) message.style.display = 'none';
    if (!pulse) return;

    var pulseImage = pulse.querySelector('.page-load-overlay-pulse-image');
    var pulseLabel = pulse.querySelector('.page-load-overlay-pulse-label');
    var pulseTitle = pulse.querySelector('.page-load-overlay-pulse-title');
    var pulseSubtitle = pulse.querySelector('.page-load-overlay-pulse-subtitle');
    var pulseStat = pulse.querySelector('.page-load-overlay-pulse-stat');
    var titleText = options.title || '';
    var subtitleText = options.subtitle || '';
    var labelText = options.label || '';
    var statLines = Array.isArray(options.statLines)
      ? options.statLines.filter(function (line) { return typeof line === 'string' && line.trim(); })
      : [];

    if (pulseLabel) {
      pulseLabel.textContent = labelText;
      pulseLabel.style.display = labelText ? 'block' : 'none';
    }

    if (pulseImage) {
      pulseImage.src = getPulseImageSrc(options);
      pulseImage.alt = options.teamName || titleText || subtitleText || 'Loading';
    }
    if (pulseTitle) {
      pulseTitle.textContent = titleText;
      pulseTitle.style.display = titleText ? 'block' : 'none';
    }
    if (pulseSubtitle) {
      pulseSubtitle.textContent = subtitleText;
      pulseSubtitle.style.display = subtitleText ? 'block' : 'none';
      // With a title, subtitle is secondary. With no title (e.g. training load: logo + feed only),
      // subtitle is the main copy — use readable body type, not oversized display type.
      if (titleText) {
        pulseSubtitle.style.fontFamily = "'Inter', sans-serif";
        pulseSubtitle.style.fontSize = '16px';
        pulseSubtitle.style.lineHeight = '1.4';
        pulseSubtitle.style.letterSpacing = '0';
        pulseSubtitle.style.color = 'rgba(255,255,255,0.68)';
        pulseSubtitle.style.margin = '0 0 22px';
      } else {
        pulseSubtitle.style.fontFamily = "'Inter', sans-serif";
        pulseSubtitle.style.fontSize = '17px';
        pulseSubtitle.style.lineHeight = '1.45';
        pulseSubtitle.style.letterSpacing = '0';
        pulseSubtitle.style.color = 'rgba(255,255,255,0.88)';
        pulseSubtitle.style.margin = '26px 0 22px';
        pulseSubtitle.style.maxWidth = 'min(520px, 92vw)';
      }
    }
    if (pulseStat) {
      if (statLines.length) {
        var statIndex = 0;
        pulseStat.textContent = statLines[0];
        pulseStat.style.display = 'block';
        if (statLines.length > 1) {
          pulseFeedTimer = setInterval(function () {
            statIndex = (statIndex + 1) % statLines.length;
            pulseStat.textContent = statLines[statIndex];
          }, options.statIntervalMs || 8000);
        }
      } else {
        pulseStat.textContent = '';
        pulseStat.style.display = 'none';
      }
    }
    pulse.style.display = 'block';
  }

  /**
   * Update pulse subtitle only (e.g. rotating training highlights) without re-running full show().
   */
  function updatePulseSubtitle(subtitleText) {
    if (typeof document === 'undefined') return;
    var overlay = document.getElementById(OVERLAY_ID);
    if (!overlay) return;
    var pulse = overlay.querySelector('.page-load-overlay-pulse');
    if (!pulse || pulse.style.display === 'none') return;
    var pulseSubtitle = pulse.querySelector('.page-load-overlay-pulse-subtitle');
    if (pulseSubtitle) pulseSubtitle.textContent = subtitleText || '';
  }

  function getOrCreateOverlay() {
    var existing = document.getElementById(OVERLAY_ID);
    if (existing) return ensureOverlayStructure(existing);

    var overlay = document.createElement('div');
    overlay.id = OVERLAY_ID;
    overlay.setAttribute('aria-hidden', 'false');
    overlay.setAttribute('aria-busy', 'true');
    overlay.setAttribute('role', 'status');
    overlay.setAttribute('aria-live', 'polite');

    ensureOverlayStructure(overlay);
    document.body.appendChild(overlay);
    return overlay;
  }

  function show(messageText) {
    var options = normalizeOptions(messageText);
    if (typeof document === 'undefined' || !document.body) {
      if (typeof document !== 'undefined' && document.addEventListener) {
        document.addEventListener('DOMContentLoaded', function onReady() {
          document.removeEventListener('DOMContentLoaded', onReady);
          var readyOverlay = getOrCreateOverlay();
          if (options.variant === 'pulse') {
            applyPulseVariant(readyOverlay, options);
          } else {
            applySpinnerVariant(readyOverlay, options);
          }
          readyOverlay.style.display = 'flex';
        });
      }
      return;
    }
    var overlay = getOrCreateOverlay();
    if (options.variant === 'pulse') {
      applyPulseVariant(overlay, options);
    } else {
      applySpinnerVariant(overlay, options);
    }
    overlay.style.display = 'flex';
  }

  function hide() {
    if (typeof document === 'undefined') return;
    var el = document.getElementById(OVERLAY_ID);
    if (el) {
      el.setAttribute('aria-hidden', 'true');
      el.setAttribute('aria-busy', 'false');
      el.style.display = 'none';
    }
    clearPulseFeedTimer();
  }

  function getTeamNameFromGameDoc(gameDoc, side) {
    if (!gameDoc || (side !== 'home' && side !== 'away')) return '';
    var teamId = side === 'home' ? gameDoc.home_team_id : gameDoc.away_team_id;
    var teams = gameDoc.teams || {};
    var team = teamId && teams ? (teams[teamId] || teams[String(teamId)]) : null;
    if (team && typeof team === 'object') return team.name || team.team_name || '';
    var fallback = side === 'home' ? gameDoc.home_team : gameDoc.away_team;
    if (fallback && typeof fallback === 'object') return fallback.name || fallback.team_name || '';
    return typeof fallback === 'string' ? fallback : '';
  }

  function getBoxScoreForSide(gameDoc, side) {
    if (!gameDoc || !gameDoc.box_score || (side !== 'home' && side !== 'away')) return {};
    var teamId = side === 'home' ? gameDoc.home_team_id : gameDoc.away_team_id;
    var teamName = getTeamNameFromGameDoc(gameDoc, side);
    var boxScore = gameDoc.box_score || {};
    return (teamId && (boxScore[teamId] || boxScore[String(teamId)])) ||
      (teamName && boxScore[teamName]) ||
      {};
  }

  function pluralizeStat(value, singular, plural) {
    return value + ' ' + (value === 1 ? singular : (plural || singular + 's'));
  }

  function formatPostgameStatLine(playerData) {
    var name = playerData.name || 'Unknown';
    var jersey = playerData.jersey;
    if (jersey == null || jersey === '') jersey = playerData.jerseyNumber;
    if (jersey == null || jersey === '') jersey = playerData.jersey_number;
    var prefix = name + (jersey != null && jersey !== '' ? ' (#' + jersey + ')' : '');
    var points = Number(playerData.PTS || 0);
    var treb = Number(playerData.TREB != null ? playerData.TREB : (Number(playerData.DREB || 0) + Number(playerData.OREB || 0)));
    var assists = Number(playerData.AST || 0);
    var steals = Number(playerData.STL || 0);
    var blocks = Number(playerData.BLK || 0);
    var minutes = Math.floor(Number(playerData.MIN || 0) / 60);
    var parts = [pluralizeStat(points, 'point')];
    if (treb > 0) parts.push(pluralizeStat(treb, 'rebound'));
    if (assists > 0) parts.push(pluralizeStat(assists, 'assist'));
    if (steals > 0) parts.push(pluralizeStat(steals, 'steal'));
    if (blocks > 0) parts.push(pluralizeStat(blocks, 'block'));
    parts.push(pluralizeStat(minutes, 'minute') + ' played');
    return prefix + ': ' + parts.join(', ');
  }

  function collectSideStatLines(gameDoc, side) {
    var box = getBoxScoreForSide(gameDoc, side);
    return Object.keys(box || {})
      .map(function (key, index) {
        var row = box[key];
        if (!row || typeof row !== 'object' || !row.name) return null;
        var minutes = Math.floor(Number(row.MIN || 0) / 60);
        if (minutes <= 0) return null;
        return {
          index: index,
          points: Number(row.PTS || 0),
          line: formatPostgameStatLine(row)
        };
      })
      .filter(Boolean)
      .sort(function (a, b) {
        if (b.points !== a.points) return b.points - a.points;
        return a.index - b.index;
      })
      .map(function (entry) { return entry.line; });
  }

  function buildPostgameStatFeed(gameDoc, options) {
    if (!gameDoc || !gameDoc.box_score) return [];
    options = options || {};
    var userSide = options.userTeamSide === 'away' ? 'away' : 'home';
    var opponentSide = userSide === 'home' ? 'away' : 'home';
    return collectSideStatLines(gameDoc, userSide).concat(collectSideStatLines(gameDoc, opponentSide));
  }

  var api = {
    show: show,
    hide: hide,
    updatePulseSubtitle: updatePulseSubtitle,
    buildPostgameStatFeed: buildPostgameStatFeed
  };
  global.PageLoadOverlay = api;

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }
})(typeof window !== 'undefined' ? window : this);
