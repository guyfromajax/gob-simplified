/**
 * Team Builder generated placeholder art (§3.3 / §6.1–6.2).
 *
 * Custom programs bypass getTeamAssetPath filesystem paths. Produce:
 *  - SVG mark from initials + primary/secondary
 *  - Chevron banner on canvas (card 400×141, primary 1920×679) — offline-capable
 *  - Simple jersey / court preview data URLs for the Colors step
 *
 * Third tones are derived from primary + secondary (no stored accent).
 * Jersey presets: 1 = SOLID (body only), 2 = SOLID WITH TRIM (body + trim).
 */
(function (global) {
  'use strict';

  var CARD_W = 400;
  var CARD_H = 141; // 400 * (679/1920) ≈ 141 — matches banner_card convention
  var PRIMARY_W = 1920;
  var PRIMARY_H = 679;

  // Composition constants from banner-variants.html direction A (card space).
  var WORD_START = 50;
  var WORD_FLOOR = 20; // ~40% of start
  var WORD_MAX_W = 300;
  var WORD_Y = 78;
  var MASCOT_Y = 99;
  var MASCOT_SIZE = 10;
  var GHOST_SIZE = 150;
  // Pure black/white — the best-of-two tie floor is ~4.58:1 only for these two.
  // Near-black (#14181f) undercuts the guarantee on mid-luminance primaries.
  var INK_DARK = '#000000';
  var INK_LIGHT = '#ffffff';
  /** Target mascot opacity; raised when composited contrast would miss 4.5:1 (§6.2). */
  var MASCOT_OPACITY_TARGET = 0.6;
  var CONTRAST_FLOOR = 4.5;

  var BEBAS_STACK = '"Bebas Neue Pro", "Bebas Neue", Impact, sans-serif';
  var OSWALD_STACK = 'Oswald, "Arial Narrow", sans-serif';

  var fontsReadyPromise = null;

  function initialsFromName(name, abbreviation, teamId) {
    if (abbreviation && String(abbreviation).trim()) {
      return String(abbreviation).trim().toUpperCase().slice(0, 3);
    }
    if (typeof global.resolveTeamAbbreviation === 'function') {
      var resolved = global.resolveTeamAbbreviation(name, teamId);
      if (resolved && resolved !== '—' && resolved !== '???') return resolved;
    }
    if (typeof global.deriveTeamAbbreviationFromName === 'function') {
      var derived = global.deriveTeamAbbreviationFromName(name);
      if (derived && derived !== '—') return derived;
    }
    var clean = String(name || '').replace(/[^A-Za-z0-9]/g, '');
    return (clean.slice(0, 3) || 'TB').toUpperCase();
  }

  function parseHex(hex) {
    var h = String(hex || '').trim().replace(/^#/, '');
    if (h.length === 3 && /^[0-9a-fA-F]{3}$/.test(h)) {
      h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
    }
    if (h.length !== 6 || !/^[0-9a-fA-F]{6}$/.test(h)) return null;
    return {
      r: parseInt(h.slice(0, 2), 16),
      g: parseInt(h.slice(2, 4), 16),
      b: parseInt(h.slice(4, 6), 16),
    };
  }

  function toHex(r, g, b) {
    return (
      '#' +
      [r, g, b]
        .map(function (n) {
          var v = Math.max(0, Math.min(255, Math.round(n)));
          var s = v.toString(16);
          return s.length === 1 ? '0' + s : s;
        })
        .join('')
    );
  }

  /** Match banner-variants.html shade() — RGB channel offset, not HSL. */
  function shadeHex(hex, amt) {
    var c = parseHex(hex);
    if (!c) return hex;
    return toHex(
      Math.min(255, Math.max(0, c.r + 255 * amt)),
      Math.min(255, Math.max(0, c.g + 255 * amt)),
      Math.min(255, Math.max(0, c.b + 255 * amt))
    );
  }

  function relativeLuminance(hex) {
    var c = parseHex(hex);
    if (!c) return 0;
    function f(channel) {
      var x = channel / 255;
      return x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4);
    }
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
  }

  function contrastRatio(fgHex, bgHex) {
    var l1 = relativeLuminance(fgHex);
    var l2 = relativeLuminance(bgHex);
    var lighter = Math.max(l1, l2);
    var darker = Math.min(l1, l2);
    return (lighter + 0.05) / (darker + 0.05);
  }

  /**
   * Best-of-two ink for a surface (§6.2). Pick dark or light by WCAG contrast —
   * never threshold on luminance. Tie floor is ~4.58:1, so the winner is always ≥4.5.
   */
  function inkOn(bgHex) {
    var darkRatio = contrastRatio(INK_DARK, bgHex);
    var lightRatio = contrastRatio(INK_LIGHT, bgHex);
    return lightRatio > darkRatio ? INK_LIGHT : INK_DARK;
  }

  function inkCandidates(bgHex) {
    return {
      dark: INK_DARK,
      light: INK_LIGHT,
      darkRatio: contrastRatio(INK_DARK, bgHex),
      lightRatio: contrastRatio(INK_LIGHT, bgHex),
      chosen: inkOn(bgHex),
    };
  }

  /** sRGB composite of fg over bg at opacity a — the colour that reaches the screen. */
  function compositeOver(fgHex, bgHex, alpha) {
    var fg = parseHex(fgHex);
    var bg = parseHex(bgHex);
    if (!fg || !bg) return fgHex;
    var a = Math.max(0, Math.min(1, alpha));
    return toHex(
      fg.r * a + bg.r * (1 - a),
      fg.g * a + bg.g * (1 - a),
      fg.b * a + bg.b * (1 - a)
    );
  }

  function compositedContrast(fgHex, bgHex, alpha) {
    return contrastRatio(compositeOver(fgHex, bgHex, alpha), bgHex);
  }

  /** Opacity ≥ target that clears the contrast floor against bg; 1.0 if still short. */
  function opacityForContrast(fgHex, bgHex, targetAlpha, floor) {
    var floorRatio = floor == null ? CONTRAST_FLOOR : floor;
    var alpha = targetAlpha == null ? MASCOT_OPACITY_TARGET : targetAlpha;
    if (compositedContrast(fgHex, bgHex, alpha) >= floorRatio) return alpha;
    var a = alpha;
    while (a < 1 && compositedContrast(fgHex, bgHex, a) < floorRatio) {
      a = Math.min(1, Math.round((a + 0.01) * 100) / 100);
    }
    return a;
  }

  /** Third tone from the two chosen colors — used for court lines. */
  function deriveThirdTone(primary, secondary) {
    var a = parseHex(primary);
    var b = parseHex(secondary);
    if (!a && !b) return '#F79420';
    if (!a) return secondary;
    if (!b) return primary;
    var lr = a.r + (255 - a.r) * 0.35;
    var lg = a.g + (255 - a.g) * 0.35;
    var lb = a.b + (255 - a.b) * 0.35;
    return toHex(b.r * 0.55 + lr * 0.45, b.g * 0.55 + lg * 0.45, b.b * 0.55 + lb * 0.45);
  }

  /** 1 = SOLID, 2 = SOLID WITH TRIM. Anything else → SOLID. */
  function normalizeJerseyPreset(value) {
    var n = Number(value);
    return n === 2 ? 2 : 1;
  }

  function ensureBannerFonts() {
    if (fontsReadyPromise) return fontsReadyPromise;
    if (typeof document === 'undefined' || !document.fonts || !document.fonts.load) {
      fontsReadyPromise = Promise.resolve();
      return fontsReadyPromise;
    }
    fontsReadyPromise = Promise.all([
      document.fonts.load('400 150px "Bebas Neue Pro"'),
      document.fonts.load('400 50px "Bebas Neue Pro"'),
      document.fonts.load('300 10px Oswald'),
    ]).then(function () {
      return document.fonts.ready;
    }).catch(function () {
      /* offline / missing face — draw with fallbacks */
    });
    return fontsReadyPromise;
  }

  function fitWordmark(ctx, text, maxW, startSize, minSize) {
    var size = startSize;
    var guard = 0;
    ctx.font = size + 'px ' + BEBAS_STACK;
    while (ctx.measureText(text).width > maxW && size > minSize && guard++ < 80) {
      size -= 1;
      ctx.font = size + 'px ' + BEBAS_STACK;
    }
    return {
      size: size,
      width: ctx.measureText(text).width,
      atFloor: size <= minSize,
      overflows: ctx.measureText(text).width > maxW,
    };
  }

  function fillPath(ctx, points) {
    ctx.beginPath();
    ctx.moveTo(points[0][0], points[0][1]);
    for (var i = 1; i < points.length; i++) ctx.lineTo(points[i][0], points[i][1]);
    ctx.closePath();
    ctx.fill();
  }

  function drawSpacedText(ctx, text, x, y, letterSpacing) {
    var chars = String(text || '').split('');
    var total = 0;
    var widths = [];
    for (var i = 0; i < chars.length; i++) {
      var w = ctx.measureText(chars[i]).width;
      widths.push(w);
      total += w;
      if (i < chars.length - 1) total += letterSpacing;
    }
    var cursor = x - total / 2;
    for (var j = 0; j < chars.length; j++) {
      ctx.fillText(chars[j], cursor, y);
      cursor += widths[j] + letterSpacing;
    }
  }

  /**
   * Chevron composition (§6.2 / banner-variants.html A), back to front.
   * Same layout at any size — scale from the 400×141 card, do not re-lay-out.
   */
  function drawChevronBanner(ctx, width, height, opts) {
    opts = opts || {};
    var primary = opts.primary || '#27408E';
    var secondary = opts.secondary || '#15181f';
    var dark = shadeHex(primary, -0.16);
    // Per-surface ink (§6.2). Wordmark + mascot sit on the primary-dominant band.
    var inkPrimary = inkOn(primary);
    var inkDark = inkOn(dark);
    var primaryCandidates = inkCandidates(primary);
    var darkCandidates = inkCandidates(dark);
    var scale = width / CARD_W;
    var initials = initialsFromName(opts.name, opts.abbreviation, opts.teamId || opts.object_id);
    var school = String(opts.name || 'Custom Program').toUpperCase();
    var mascot = String(opts.mascot || '').trim().toUpperCase();
    var mascotAlpha = 0;
    var mascotComposite = null;
    var mascotContrast = null;

    ctx.save();
    ctx.clearRect(0, 0, width, height);

    // 1. Flat primary
    ctx.fillStyle = primary;
    ctx.fillRect(0, 0, width, height);

    // 2. Angled split — darkened primary right of diagonal (~38%→75%)
    ctx.fillStyle = dark;
    fillPath(ctx, [
      [150 * scale, height],
      [300 * scale, 0],
      [width, 0],
      [width, height],
    ]);

    // 3. Chevron edge — secondary strips (no flat accent bar)
    ctx.fillStyle = secondary;
    ctx.globalAlpha = 0.9;
    fillPath(ctx, [
      [138 * scale, height],
      [288 * scale, 0],
      [300 * scale, 0],
      [150 * scale, height],
    ]);
    ctx.globalAlpha = 0.35;
    fillPath(ctx, [
      [128 * scale, height],
      [278 * scale, 0],
      [283 * scale, 0],
      [133 * scale, height],
    ]);
    ctx.globalAlpha = 1;

    // 4. Ghost initials — decorative depth only (12%); exempt from contrast floor (§6.2)
    ctx.font = GHOST_SIZE * scale + 'px ' + BEBAS_STACK;
    ctx.fillStyle = secondary;
    ctx.globalAlpha = 0.12;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'alphabetic';
    if (typeof ctx.letterSpacing === 'string') ctx.letterSpacing = -2 * scale + 'px';
    ctx.fillText(initials, -14 * scale, height + 26 * scale);
    if (typeof ctx.letterSpacing === 'string') ctx.letterSpacing = '0px';
    ctx.globalAlpha = 1;

    // 5. Wordmark — shrink-to-fit, centred, above vertical midline
    var fit = fitWordmark(
      ctx,
      school,
      WORD_MAX_W * scale,
      WORD_START * scale,
      WORD_FLOOR * scale
    );
    ctx.font = fit.size + 'px ' + BEBAS_STACK;
    ctx.fillStyle = inkPrimary;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'alphabetic';
    ctx.fillText(school, width / 2, WORD_Y * scale);

    // 6. Mascot — Oswald light, wide tracking; opacity clears composited 4.5:1
    if (mascot) {
      mascotAlpha = opacityForContrast(inkPrimary, primary, MASCOT_OPACITY_TARGET, CONTRAST_FLOOR);
      mascotComposite = compositeOver(inkPrimary, primary, mascotAlpha);
      mascotContrast = contrastRatio(mascotComposite, primary);
      ctx.font = '300 ' + MASCOT_SIZE * scale + 'px ' + OSWALD_STACK;
      ctx.fillStyle = inkPrimary;
      ctx.globalAlpha = mascotAlpha;
      ctx.textAlign = 'left';
      drawSpacedText(ctx, mascot, width / 2, MASCOT_Y * scale, 4.5 * scale);
      ctx.globalAlpha = 1;
    }

    ctx.restore();
    return {
      width: width,
      height: height,
      ink: inkPrimary,
      inkPrimary: inkPrimary,
      inkDark: inkDark,
      dark: dark,
      primary: primary,
      secondary: secondary,
      initials: initials,
      wordSize: fit.size,
      wordFloor: WORD_FLOOR * scale,
      atFloor: fit.atFloor,
      overflows: fit.overflows,
      contrastPrimary: contrastRatio(inkPrimary, primary),
      contrastDark: contrastRatio(inkDark, dark),
      primaryCandidates: primaryCandidates,
      darkCandidates: darkCandidates,
      mascotAlpha: mascotAlpha,
      mascotComposite: mascotComposite,
      mascotContrast: mascotContrast,
    };
  }

  function makeCanvas(width, height) {
    if (typeof document !== 'undefined' && document.createElement) {
      var c = document.createElement('canvas');
      c.width = width;
      c.height = height;
      return c;
    }
    throw new Error('TeamGeneratedArt banner requires a DOM canvas');
  }

  function renderBanner(opts, width, height, mime, quality) {
    var canvas = makeCanvas(width, height);
    var ctx = canvas.getContext('2d');
    var meta = drawChevronBanner(ctx, width, height, opts);
    var url =
      mime === 'image/jpeg'
        ? canvas.toDataURL('image/jpeg', quality == null ? 0.92 : quality)
        : canvas.toDataURL('image/png');
    meta.dataUrl = url;
    return meta;
  }

  function bannerCardDataUrl(opts) {
    return renderBanner(opts, CARD_W, CARD_H, 'image/png').dataUrl;
  }

  function bannerPrimaryDataUrl(opts) {
    return renderBanner(opts, PRIMARY_W, PRIMARY_H, 'image/jpeg', 0.92).dataUrl;
  }

  /** Diagnostics for acceptance (fit + contrast). Does not return pixels. */
  function analyzeBanner(opts, size) {
    var width = size === 'primary' ? PRIMARY_W : CARD_W;
    var height = size === 'primary' ? PRIMARY_H : CARD_H;
    var canvas = makeCanvas(width, height);
    var ctx = canvas.getContext('2d');
    return drawChevronBanner(ctx, width, height, opts);
  }

  function svgMark(opts) {
    opts = opts || {};
    var primary = opts.primary || '#27408E';
    var secondary = opts.secondary || '#F79420';
    var text = initialsFromName(opts.name, opts.abbreviation, opts.teamId || opts.object_id);
    var size = opts.size || 128;
    var ink = inkOn(primary);
    return (
      '<svg xmlns="http://www.w3.org/2000/svg" width="' +
      size +
      '" height="' +
      size +
      '" viewBox="0 0 128 128">' +
      '<rect width="128" height="128" rx="18" fill="' +
      primary +
      '"/>' +
      '<circle cx="64" cy="64" r="46" fill="none" stroke="' +
      secondary +
      '" stroke-opacity="0.55" stroke-width="3"/>' +
      '<text x="64" y="74" text-anchor="middle" font-family="Bebas Neue Pro, Bebas Neue, sans-serif" ' +
      'font-size="42" fill="' +
      ink +
      '" letter-spacing="2">' +
      text +
      '</text></svg>'
    );
  }

  function svgToDataUrl(svg) {
    return 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
  }

  function markDataUrl(opts) {
    return svgToDataUrl(svgMark(opts));
  }

  function jerseyPreviewDataUrl(opts) {
    opts = opts || {};
    var primary = opts.primary || '#27408E';
    var secondary = opts.secondary || '#ffffff';
    var preset = normalizeJerseyPreset(opts.jerseyPreset);
    var number = String(opts.number != null ? opts.number : 23);
    var body = primary;
    var trim = preset === 2 ? secondary : primary;
    var ink = inkOn(primary);
    var svg =
      '<svg xmlns="http://www.w3.org/2000/svg" width="160" height="200" viewBox="0 0 160 200">' +
      '<rect width="160" height="200" fill="#0b0d14"/>' +
      '<path d="M40 30 L55 18 L80 28 L105 18 L120 30 L130 70 L120 180 L40 180 L30 70 Z" fill="' +
      body +
      '" stroke="' +
      trim +
      '" stroke-width="' +
      (preset === 2 ? '8' : '2') +
      '"/>' +
      '<text x="80" y="120" text-anchor="middle" font-family="Bebas Neue Pro, Bebas Neue, sans-serif" font-size="48" fill="' +
      ink +
      '">' +
      number +
      '</text></svg>';
    return svgToDataUrl(svg);
  }

  /**
   * Colors-step preview swatch only — not the gameplay court.
   * Gameplay uses general_court.jpg via getTeamAssetPath until §6.3.
   */
  function courtPreviewDataUrl(opts) {
    opts = opts || {};
    var primary = opts.primary || '#27408E';
    var secondary = opts.secondary || '#1a1f2e';
    var accent = deriveThirdTone(primary, secondary);
    var svg =
      '<svg xmlns="http://www.w3.org/2000/svg" width="240" height="140" viewBox="0 0 240 140">' +
      '<rect width="240" height="140" fill="' +
      secondary +
      '"/>' +
      '<rect x="8" y="8" width="224" height="124" fill="none" stroke="' +
      primary +
      '" stroke-width="3"/>' +
      '<circle cx="120" cy="70" r="22" fill="none" stroke="' +
      accent +
      '" stroke-width="2"/>' +
      '<line x1="120" y1="8" x2="120" y2="132" stroke="' +
      primary +
      '" stroke-width="2"/>' +
      '<rect x="8" y="40" width="36" height="60" fill="none" stroke="' +
      accent +
      '" stroke-width="2"/>' +
      '<rect x="196" y="40" width="36" height="60" fill="none" stroke="' +
      accent +
      '" stroke-width="2"/>' +
      '</svg>';
    return svgToDataUrl(svg);
  }

  /**
   * Resolve an asset URL for a team that may be custom.
   * Prefer getTeamAssetPath (franchise-aware shared producer). Falls back to
   * filesystem helpers when generating locally in the wizard before Apply.
   */
  function resolveTeamVisual(team, assetKey) {
    team = team || {};
    if (team.asset_strategy === 'generated' || team.is_custom) {
      if (typeof global.getTeamAssetPath === 'function') {
        return global.getTeamAssetPath(team.name || team.slug, assetKey, {
          name: team.name,
          abbreviation: team.abbreviation,
          mascot: team.mascot,
          primary_color: team.primary || team.primary_color,
          secondary_color: team.secondary || team.secondary_color,
          jersey_preset: normalizeJerseyPreset(team.jerseyPreset || team.jersey_preset),
          asset_strategy: 'generated',
          is_custom: true,
          replaced_name: team.replaced_name,
        });
      }
      if (assetKey === 'logo_square' || assetKey === 'mark') return markDataUrl(team);
      if (assetKey === 'banner_card') return bannerCardDataUrl(team);
      if (assetKey === 'banner_primary' || assetKey === 'background') return bannerPrimaryDataUrl(team);
      if (assetKey === 'jersey') return jerseyPreviewDataUrl(team);
      if (assetKey === 'court') {
        return typeof global.filesystemTeamAssetPath === 'function'
          ? global.filesystemTeamAssetPath(null, 'court')
          : '/images/teams/general/general_court.jpg';
      }
    }
    if (typeof global.filesystemTeamAssetPath === 'function') {
      return global.filesystemTeamAssetPath(team.name || team.slug, assetKey === 'mark' ? 'logo_square' : assetKey);
    }
    if (typeof global.getTeamAssetPath === 'function') {
      return global.getTeamAssetPath(team.name || team.slug, assetKey === 'mark' ? 'logo_square' : assetKey);
    }
    return '/images/teams/general/general_logo_square.png';
  }

  global.TeamGeneratedArt = {
    CARD_W: CARD_W,
    CARD_H: CARD_H,
    PRIMARY_W: PRIMARY_W,
    PRIMARY_H: PRIMARY_H,
    WORD_START: WORD_START,
    WORD_FLOOR: WORD_FLOOR,
    INK_DARK: INK_DARK,
    INK_LIGHT: INK_LIGHT,
    MASCOT_OPACITY_TARGET: MASCOT_OPACITY_TARGET,
    CONTRAST_FLOOR: CONTRAST_FLOOR,
    initialsFromName: initialsFromName,
    shadeHex: shadeHex,
    relativeLuminance: relativeLuminance,
    inkOn: inkOn,
    inkCandidates: inkCandidates,
    compositeOver: compositeOver,
    compositedContrast: compositedContrast,
    opacityForContrast: opacityForContrast,
    contrastRatio: contrastRatio,
    deriveThirdTone: deriveThirdTone,
    normalizeJerseyPreset: normalizeJerseyPreset,
    ensureBannerFonts: ensureBannerFonts,
    drawChevronBanner: drawChevronBanner,
    analyzeBanner: analyzeBanner,
    svgMark: svgMark,
    markDataUrl: markDataUrl,
    bannerCardDataUrl: bannerCardDataUrl,
    bannerPrimaryDataUrl: bannerPrimaryDataUrl,
    jerseyPreviewDataUrl: jerseyPreviewDataUrl,
    courtPreviewDataUrl: courtPreviewDataUrl,
    resolveTeamVisual: resolveTeamVisual,
  };
})(typeof window !== 'undefined' ? window : globalThis);
