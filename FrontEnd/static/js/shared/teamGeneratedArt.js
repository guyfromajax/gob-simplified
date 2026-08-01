/**
 * Team Builder generated placeholder art (§3.3).
 *
 * Custom programs bypass getTeamAssetPath filesystem paths. Produce:
 *  - SVG mark from initials + primary/secondary
 *  - Card-sized banner data URL (~400×141, matches banner_card convention)
 *  - Simple jersey / court preview data URLs for the Colors step
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
    var accent = opts.accent || '#F79420';
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
    var accent = opts.accent || '#F79420';
    var preset = Number(opts.jerseyPreset || 1);
    var number = String(opts.number != null ? opts.number : 23);
    // 5 simple presets: solid, side panels, yoke, hoops, split
    var body = primary;
    var trim = secondary;
    if (preset === 2) trim = accent;
    var svg =
      '<svg xmlns="http://www.w3.org/2000/svg" width="160" height="200" viewBox="0 0 160 200">' +
      '<rect width="160" height="200" fill="#0b0d14"/>' +
      '<path d="M40 30 L55 18 L80 28 L105 18 L120 30 L130 70 L120 180 L40 180 L30 70 Z" fill="' +
      body +
      '" stroke="' +
      trim +
      '" stroke-width="4"/>' +
      (preset >= 3
        ? '<rect x="40" y="30" width="80" height="28" fill="' + trim + '" opacity="0.85"/>'
        : '') +
      (preset === 4
        ? '<rect x="40" y="90" width="80" height="10" fill="' +
          accent +
          '"/><rect x="40" y="110" width="80" height="10" fill="' +
          accent +
          '"/>'
        : '') +
      (preset === 5
        ? '<rect x="80" y="30" width="40" height="150" fill="' + trim + '" opacity="0.55"/>'
        : '') +
      '<text x="80" y="120" text-anchor="middle" font-family="Bebas Neue, sans-serif" font-size="48" fill="#fff">' +
      number +
      '</text></svg>';
    return svgToDataUrl(svg);
  }

  function courtPreviewDataUrl(opts) {
    opts = opts || {};
    var primary = opts.primary || '#27408E';
    var secondary = opts.secondary || '#1a1f2e';
    var accent = opts.accent || '#F79420';
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
          accent_color: team.accent || team.accent_color,
          jersey_preset: team.jerseyPreset || team.jersey_preset,
          asset_strategy: 'generated',
          is_custom: true,
          replaced_name: team.replaced_name,
        });
      }
      if (assetKey === 'logo_square' || assetKey === 'mark') return markDataUrl(team);
      if (assetKey === 'banner_card' || assetKey === 'banner_primary') return bannerCardDataUrl(team);
      if (assetKey === 'jersey') return jerseyPreviewDataUrl(team);
      if (assetKey === 'court') return courtPreviewDataUrl(team);
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
    svgMark: svgMark,
    markDataUrl: markDataUrl,
    bannerCardDataUrl: bannerCardDataUrl,
    jerseyPreviewDataUrl: jerseyPreviewDataUrl,
    courtPreviewDataUrl: courtPreviewDataUrl,
    resolveTeamVisual: resolveTeamVisual,
  };
})(typeof window !== 'undefined' ? window : globalThis);
