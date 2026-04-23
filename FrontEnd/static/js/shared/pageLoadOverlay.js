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

    var img = content.querySelector('img');
    if (!img) {
      img = document.createElement('img');
      img.className = 'page-load-overlay-spinner';
      img.alt = 'Loading…';
      content.appendChild(img);
    }
    img.src = LOADER_IMG_PATH;
    img.style.cssText = 'width:240px;height:auto;max-width:90vw;';

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
        '<img class="page-load-overlay-pulse-image" alt="">',
        '<h2 class="page-load-overlay-pulse-title"></h2>',
        '<p class="page-load-overlay-pulse-subtitle"></p>',
        '<div class="page-load-overlay-pulse-indicator" aria-hidden="true"><span></span></div>'
      ].join('');
      content.appendChild(pulse);
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
  }

  function applyPulseVariant(overlay, options) {
    var content = overlay.querySelector('.page-load-overlay-content');
    if (!content) return;
    var spinner = content.querySelector('.page-load-overlay-spinner');
    var message = content.querySelector('.page-load-overlay-message');
    var pulse = content.querySelector('.page-load-overlay-pulse');
    if (spinner) spinner.style.display = 'none';
    if (message) message.style.display = 'none';
    if (!pulse) return;

    var pulseImage = pulse.querySelector('.page-load-overlay-pulse-image');
    var pulseTitle = pulse.querySelector('.page-load-overlay-pulse-title');
    var pulseSubtitle = pulse.querySelector('.page-load-overlay-pulse-subtitle');
    var titleText = options.title || '';
    var subtitleText = options.subtitle || '';

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
      pulseSubtitle.style.fontFamily = titleText ? "'Inter', sans-serif" : "'Bebas Neue', sans-serif";
      pulseSubtitle.style.fontSize = titleText ? '16px' : '48px';
      pulseSubtitle.style.lineHeight = titleText ? '1.4' : '1';
      pulseSubtitle.style.letterSpacing = titleText ? '0' : '0.03em';
      pulseSubtitle.style.color = titleText ? 'rgba(255,255,255,0.68)' : '#ffffff';
      pulseSubtitle.style.margin = titleText ? '0 0 22px' : '26px 0 22px';
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
  }

  var api = { show: show, hide: hide, updatePulseSubtitle: updatePulseSubtitle };
  global.PageLoadOverlay = api;

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }
})(typeof window !== 'undefined' ? window : this);
