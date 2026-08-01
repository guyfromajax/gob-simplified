/**
 * Team Builder generated placeholder art (§3.3).
 *
 * Custom programs bypass getTeamAssetPath filesystem paths. Produce:
 *  - SVG mark from initials + primary/secondary
 *  - Card-sized banner data URL (~400×141, matches banner_card convention)
 *  - Simple jersey / court preview data URLs for the Colors step
 *
 * Third tones are derived from primary + secondary (no stored accent).
 * Jersey presets: 1 = SOLID (body only), 2 = SOLID WITH TRIM (body + trim).
 */
(function (global) {
  'use strict';

  var CARD_W = 400;
  var CARD_H = 141; // 400 * (679/1920) ≈ 141 — matches primary banner aspect

  function initialsFromName(name, abbreviation, teamId) {
    if (abbreviation && String(abbreviation).trim()) {
      return String(abbreviation).trim().toUpperCase().slice(0, 3);
    }
    if (typeof global.resolveTeamAbbreviation === 'function') {
      var resolved = global.resolveTeamAbbreviation(name, teamId);
      if (resolved && resolved !== '—' && resolved !== '???') return resolved;
    }
    var parts = String(name || '')
      .trim()
      .split(/[\s\-]+/)
      .filter(Boolean);
    if (!parts.length) return 'TB';
    if (parts.length === 1) return parts[0].slice(0, 3).toUpperCase();
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
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

  /** Third tone from the two chosen colors — used for banner stripe / court lines. */
  function deriveThirdTone(primary, secondary) {
    var a = parseHex(primary);
    var b = parseHex(secondary);
    if (!a && !b) return '#F79420';
    if (!a) return secondary;
    if (!b) return primary;
    // Mix secondary with a lightened primary so the highlight differs from both.
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

  function svgMark(opts) {
    opts = opts || {};
    var primary = opts.primary || '#27408E';
    var secondary = opts.secondary || '#F79420';
    var text = initialsFromName(opts.name, opts.abbreviation, opts.teamId || opts.object_id);
    var size = opts.size || 128;
    return (
      '<svg xmlns="http://www.w3.org/2000/svg" width="' +
      size +
      '" height="' +
      size +
      '" viewBox="0 0 128 128">' +
      '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">' +
      '<stop offset="0%" stop-color="' +
      primary +
      '"/>' +
      '<stop offset="100%" stop-color="' +
      secondary +
      '"/>' +
      '</linearGradient></defs>' +
      '<rect width="128" height="128" rx="18" fill="url(#g)"/>' +
      '<circle cx="64" cy="64" r="46" fill="none" stroke="rgba(255,255,255,0.35)" stroke-width="3"/>' +
      '<text x="64" y="74" text-anchor="middle" font-family="Bebas Neue, Bebas Neue Pro, sans-serif" ' +
      'font-size="42" fill="#ffffff" letter-spacing="2">' +
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

  function bannerCardDataUrl(opts) {
    opts = opts || {};
    var primary = opts.primary || '#27408E';
    var secondary = opts.secondary || '#15181f';
    var accent = deriveThirdTone(primary, secondary);
    var text = initialsFromName(opts.name, opts.abbreviation, opts.teamId || opts.object_id);
    var label = String(opts.name || 'Custom Program');
    var svg =
      '<svg xmlns="http://www.w3.org/2000/svg" width="' +
      CARD_W +
      '" height="' +
      CARD_H +
      '" viewBox="0 0 ' +
      CARD_W +
      ' ' +
      CARD_H +
      '">' +
      '<defs><linearGradient id="b" x1="0" y1="0" x2="1" y2="0">' +
      '<stop offset="0%" stop-color="' +
      primary +
      '"/>' +
      '<stop offset="100%" stop-color="' +
      secondary +
      '"/>' +
      '</linearGradient></defs>' +
      '<rect width="' +
      CARD_W +
      '" height="' +
      CARD_H +
      '" fill="url(#b)"/>' +
      '<rect x="0" y="' +
      (CARD_H - 8) +
      '" width="' +
      CARD_W +
      '" height="8" fill="' +
      accent +
      '"/>' +
      '<text x="24" y="64" font-family="Bebas Neue, Bebas Neue Pro, sans-serif" font-size="48" fill="#fff" letter-spacing="2">' +
      text +
      '</text>' +
      '<text x="24" y="100" font-family="Inter, sans-serif" font-size="14" fill="rgba(255,255,255,0.85)">' +
      label.replace(/[<>&]/g, '') +
      '</text></svg>';
    return svgToDataUrl(svg);
  }

  function jerseyPreviewDataUrl(opts) {
    opts = opts || {};
    var primary = opts.primary || '#27408E';
    var secondary = opts.secondary || '#ffffff';
    var preset = normalizeJerseyPreset(opts.jerseyPreset);
    var number = String(opts.number != null ? opts.number : 23);
    // 1 SOLID = body only; 2 SOLID WITH TRIM = body + trim (manifest body/trim).
    var body = primary;
    var trim = preset === 2 ? secondary : primary;
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
      '<text x="80" y="120" text-anchor="middle" font-family="Bebas Neue, sans-serif" font-size="48" fill="#fff">' +
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
          primary_color: team.primary || team.primary_color,
          secondary_color: team.secondary || team.secondary_color,
          jersey_preset: normalizeJerseyPreset(team.jerseyPreset || team.jersey_preset),
          asset_strategy: 'generated',
          is_custom: true,
          replaced_name: team.replaced_name,
        });
      }
      if (assetKey === 'logo_square' || assetKey === 'mark') return markDataUrl(team);
      if (assetKey === 'banner_card' || assetKey === 'banner_primary') return bannerCardDataUrl(team);
      if (assetKey === 'jersey') return jerseyPreviewDataUrl(team);
      // Court: filesystem until §6.3 (same policy as getTeamAssetPath).
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
    initialsFromName: initialsFromName,
    deriveThirdTone: deriveThirdTone,
    normalizeJerseyPreset: normalizeJerseyPreset,
    svgMark: svgMark,
    markDataUrl: markDataUrl,
    bannerCardDataUrl: bannerCardDataUrl,
    jerseyPreviewDataUrl: jerseyPreviewDataUrl,
    courtPreviewDataUrl: courtPreviewDataUrl,
    resolveTeamVisual: resolveTeamVisual,
  };
})(typeof window !== 'undefined' ? window : globalThis);
