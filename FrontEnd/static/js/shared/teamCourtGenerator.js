/**
 * GOB parametric court generator — browser canvas port of generate_non_a1_courts.mjs.
 * Canvas 3333×2083; geometry constants copied verbatim from the ImageMagick script.
 */
(function (global) {
  'use strict';

  var WIDTH = 3333;
  var HEIGHT = 2083;

  var CANVAS = { w: 3333, h: 2083 };
  var FLOOR = { x1: 75, y1: 60, x2: 3258, y2: 2023 };
  var OOB_LINE_BOUNDS = { x1: 150, y1: 84, x2: 3183, y2: 1998 };
  var TOP_HORIZONTAL_OOB_Y = 158;
  var BOTTOM_HORIZONTAL_OOB_Y = 1924;
  var FLOOR_EDGE_TOP_Y = 208;
  var FLOOR_EDGE_BOTTOM_Y = 1878;
  var THREE_POINT_LEFT = {
    startX: 96,
    controlX: 1112,
    topY: 308,
    bottomY: 1770,
  };
  var THREE_POINT_RIGHT = {
    startX: 3237,
    controlX: 2213,
    topY: 308,
    bottomY: 1770,
  };
  var THREE_POINT_LINE_LEFT = {
    startX: OOB_LINE_BOUNDS.x1,
    controlX: THREE_POINT_LEFT.controlX,
    topY: THREE_POINT_LEFT.topY,
    bottomY: THREE_POINT_LEFT.bottomY,
  };
  var THREE_POINT_LINE_RIGHT = {
    startX: OOB_LINE_BOUNDS.x2,
    controlX: THREE_POINT_RIGHT.controlX,
    topY: THREE_POINT_RIGHT.topY,
    bottomY: THREE_POINT_RIGHT.bottomY,
  };
  var FREE_THROW_LEFT_BBOX = { x1: 684, y1: 859, x2: 1044, y2: 1219, start: 248, end: 112 };
  var FREE_THROW_RIGHT_BBOX = { x1: 2288, y1: 859, x2: 2648, y2: 1219, start: 68, end: 292 };
  var CENTER = { x: 1666, y: 1042 };
  var LANE_LEFT_RECT = { x1: 150, y1: 806, x2: 872, y2: 1271 };
  var LANE_RIGHT_RECT = { x1: 2452, y1: 806, x2: 3183, y2: 1271 };
  var LEFT_HALF_CIRCLE = { x1: 641, y1: 808, x2: 1103, y2: 1269 };
  var RIGHT_HALF_CIRCLE = { x1: 2221, y1: 808, x2: 2683, y2: 1269 };
  var LANE_OUTSIDE_HASHES_LEFT_X = [458, 558, 658, 758];
  var LANE_OUTSIDE_HASHES_RIGHT_X = [2575, 2675, 2775, 2875];
  var LANE_OUTSIDE_HASH_TOP = { y1: 782, y2: LANE_LEFT_RECT.y1 };
  var LANE_OUTSIDE_HASH_BOTTOM = { y1: LANE_LEFT_RECT.y2, y2: 1296 };

  var HARDWOOD_TONES = {
    light: '#EAD8C6',
    medium: '#DBB891',
    dark: '#CB9D76',
  };

  var HARDWOOD_VARIANTS = {
    light_light: { inside: 'light', outside: 'light', pct: 5 },
    light_medium: { inside: 'light', outside: 'medium', pct: 10 },
    light_dark: { inside: 'light', outside: 'dark', pct: 5 },
    medium_light: { inside: 'medium', outside: 'light', pct: 10 },
    medium_medium: { inside: 'medium', outside: 'medium', pct: 35 },
    medium_dark: { inside: 'medium', outside: 'dark', pct: 10 },
    dark_light: { inside: 'dark', outside: 'light', pct: 5 },
    dark_medium: { inside: 'dark', outside: 'medium', pct: 10 },
    dark_dark: { inside: 'dark', outside: 'dark', pct: 10 },
  };

  var COLORS = {
    line: '#6e675f',
    rim: '#e35a4a',
    backboardOuter: '#d7dde8',
    backboardInner: '#f6f7fb',
    support: '#1b1b1b',
    backboardGlass: 'rgba(82,95,122,0.45)',
  };

  var LEFT_BACKBOARD_EXT = {
    outer: { x1: 166, y1: 882, x2: 196, y2: 1212 },
    glass: { x1: 172, y1: 888, x2: 190, y2: 1206 },
  };

  var RIGHT_BACKBOARD_EXT = {
    outer: { x1: 3137, y1: 882, x2: 3167, y2: 1212 },
    glass: { x1: 3143, y1: 888, x2: 3161, y2: 1206 },
  };

  var RIM_LEFT = { x: 300, y: 1042 };
  var RIM_RIGHT = { x: 3033, y: 1042 };

  var A1_REFERENCE_SLUGS = [
    'bentley_truman',
    'lancaster',
    'four_corners',
    'morristown',
    'ocean_city',
    'little_york',
    'xavien',
    'south_lancaster',
  ];

  var GEOMETRY = {
    CANVAS: CANVAS,
    FLOOR: FLOOR,
    OOB_LINE_BOUNDS: OOB_LINE_BOUNDS,
    TOP_HORIZONTAL_OOB_Y: TOP_HORIZONTAL_OOB_Y,
    BOTTOM_HORIZONTAL_OOB_Y: BOTTOM_HORIZONTAL_OOB_Y,
    FLOOR_EDGE_TOP_Y: FLOOR_EDGE_TOP_Y,
    FLOOR_EDGE_BOTTOM_Y: FLOOR_EDGE_BOTTOM_Y,
    THREE_POINT_LEFT: THREE_POINT_LEFT,
    THREE_POINT_RIGHT: THREE_POINT_RIGHT,
    THREE_POINT_LINE_LEFT: THREE_POINT_LINE_LEFT,
    THREE_POINT_LINE_RIGHT: THREE_POINT_LINE_RIGHT,
    FREE_THROW_LEFT_BBOX: FREE_THROW_LEFT_BBOX,
    FREE_THROW_RIGHT_BBOX: FREE_THROW_RIGHT_BBOX,
    CENTER: CENTER,
    LANE_LEFT_RECT: LANE_LEFT_RECT,
    LANE_RIGHT_RECT: LANE_RIGHT_RECT,
    LEFT_HALF_CIRCLE: LEFT_HALF_CIRCLE,
    RIGHT_HALF_CIRCLE: RIGHT_HALF_CIRCLE,
    LANE_OUTSIDE_HASHES_LEFT_X: LANE_OUTSIDE_HASHES_LEFT_X,
    LANE_OUTSIDE_HASHES_RIGHT_X: LANE_OUTSIDE_HASHES_RIGHT_X,
    LANE_OUTSIDE_HASH_TOP: LANE_OUTSIDE_HASH_TOP,
    LANE_OUTSIDE_HASH_BOTTOM: LANE_OUTSIDE_HASH_BOTTOM,
    LEFT_BACKBOARD_EXT: LEFT_BACKBOARD_EXT,
    RIGHT_BACKBOARD_EXT: RIGHT_BACKBOARD_EXT,
    RIM_LEFT: RIM_LEFT,
    RIM_RIGHT: RIM_RIGHT,
    CENTER_Y: 1042,
  };

  var OVERLAY_BASE = '/images/teams/general/court-overlays/';
  var OVERLAY_PATHS = {
    leftBasket: OVERLAY_BASE + 'bt_left_basket_alpha3.png',
    rightBasket: OVERLAY_BASE + 'bt_right_basket_alpha3.png',
    // Left backboard crop was never extracted; right-only matches the Node script's optional overlays.
    rightBackboard: OVERLAY_BASE + 'bt_right_backboard_support_crop.png',
    leftRimnet: OVERLAY_BASE + 'bt_left_rimnet_overlay.png',
    rightRimnet: OVERLAY_BASE + 'bt_right_rimnet_overlay.png',
  };

  var overlayCachePromise = null;

  function parseHex(hex) {
    var h = String(hex || '').trim().replace(/^#/, '');
    if (h.length === 3 && /^[0-9a-fA-F]{3}$/.test(h)) {
      h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
    }
    if (h.length !== 6 || !/^[0-9a-fA-F]{6}$/.test(h)) return null;
    return '#' + h.toLowerCase();
  }

  function shadeHex(hex, amt) {
    var h = String(hex || '').replace(/^#/, '');
    if (h.length !== 6) return hex;
    var r = parseInt(h.slice(0, 2), 16);
    var g = parseInt(h.slice(2, 4), 16);
    var b = parseInt(h.slice(4, 6), 16);
    function clamp(n) {
      return Math.max(0, Math.min(255, Math.round(n)));
    }
    return (
      '#' +
      [clamp(r + 255 * amt), clamp(g + 255 * amt), clamp(b + 255 * amt)]
        .map(function (n) {
          var s = n.toString(16);
          return s.length === 1 ? '0' + s : s;
        })
        .join('')
    );
  }

  function relativeLuminance(hex) {
    var h = String(hex || '').replace(/^#/, '');
    if (h.length !== 6) return 0;
    function ch(x) {
      x /= 255;
      return x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4);
    }
    var r = ch(parseInt(h.slice(0, 2), 16));
    var g = ch(parseInt(h.slice(2, 4), 16));
    var b = ch(parseInt(h.slice(4, 6), 16));
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  }

  function contrastRatio(a, b) {
    var l1 = relativeLuminance(a);
    var l2 = relativeLuminance(b);
    var lighter = Math.max(l1, l2);
    var darker = Math.min(l1, l2);
    return (lighter + 0.05) / (darker + 0.05);
  }

  function defaultsFromTeamColors(primary, secondary) {
    var p = parseHex(primary) || '#2a2a2a';
    var s = parseHex(secondary) || '#f2f2f2';
    var outsideTone = HARDWOOD_TONES[HARDWOOD_VARIANTS.medium_medium.outside];
    var oob = p;
    if (contrastRatio(oob, outsideTone) < 2.5) {
      oob = shadeHex(p, -0.18);
    }
    return {
      hardwoodStyle: 'medium_medium',
      oobColor: oob,
      laneColor: p,
      centreCourtColor: outsideTone,
      halfArcFillColor: s,
    };
  }

  function makeCanvas(w, h) {
    if (typeof document === 'undefined' || !document.createElement) {
      throw new Error('TeamCourtGenerator requires a DOM canvas');
    }
    var c = document.createElement('canvas');
    c.width = w;
    c.height = h;
    return c;
  }

  function degToRad(d) {
    return (d * Math.PI) / 180;
  }

  function halfCircleCenter(bbox) {
    return {
      cx: (bbox.x1 + bbox.x2) / 2,
      cy: (bbox.y1 + bbox.y2) / 2,
      rx: (bbox.x2 - bbox.x1) / 2,
      ry: (bbox.y2 - bbox.y1) / 2,
    };
  }

  function resolveWoodColors(opts) {
    var styleKey = opts.hardwoodStyle || 'medium_medium';
    var variant = HARDWOOD_VARIANTS[styleKey] || HARDWOOD_VARIANTS.medium_medium;
    var insideWood = HARDWOOD_TONES[variant.inside];
    var outsideWood =
      opts.centreCourtColor != null && String(opts.centreCourtColor).trim()
        ? parseHex(opts.centreCourtColor) || HARDWOOD_TONES[variant.outside]
        : HARDWOOD_TONES[variant.outside];
    return { insideWood: insideWood, outsideWood: outsideWood };
  }

  function resolveRenderParams(opts) {
    opts = opts || {};
    var primary = parseHex(opts.primary) || '#2a2a2a';
    var secondary = parseHex(opts.secondary) || '#f2f2f2';
    var defaults = defaultsFromTeamColors(primary, secondary);
    var wood = resolveWoodColors({
      hardwoodStyle: opts.hardwoodStyle || defaults.hardwoodStyle,
      centreCourtColor: opts.centreCourtColor != null ? opts.centreCourtColor : defaults.centreCourtColor,
    });
    return {
      hardwoodStyle: opts.hardwoodStyle || defaults.hardwoodStyle,
      oobColor: parseHex(opts.oobColor) || defaults.oobColor,
      laneColor: parseHex(opts.laneColor) || defaults.laneColor,
      centreCourtColor: wood.outsideWood,
      halfArcFillColor: parseHex(opts.halfArcFillColor) || defaults.halfArcFillColor,
      lineColor: parseHex(opts.lineColor) || COLORS.line,
      insideWood: wood.insideWood,
      outsideWood: wood.outsideWood,
      overlayImages: opts.overlayImages || null,
      useOverlays: opts.useOverlays !== false,
    };
  }

  function drawWoodBase(ctx, outsideWood, insideWood) {
    ctx.fillStyle = outsideWood;
    ctx.fillRect(
      OOB_LINE_BOUNDS.x1,
      TOP_HORIZONTAL_OOB_Y,
      OOB_LINE_BOUNDS.x2 - OOB_LINE_BOUNDS.x1,
      BOTTOM_HORIZONTAL_OOB_Y - TOP_HORIZONTAL_OOB_Y
    );

    ctx.fillStyle = insideWood;
    ctx.beginPath();
    ctx.moveTo(OOB_LINE_BOUNDS.x1, THREE_POINT_LINE_LEFT.topY);
    ctx.quadraticCurveTo(
      THREE_POINT_LINE_LEFT.controlX,
      THREE_POINT_LINE_LEFT.topY,
      THREE_POINT_LINE_LEFT.controlX,
      1042
    );
    ctx.quadraticCurveTo(
      THREE_POINT_LINE_LEFT.controlX,
      THREE_POINT_LINE_LEFT.bottomY,
      OOB_LINE_BOUNDS.x1,
      THREE_POINT_LINE_LEFT.bottomY
    );
    ctx.lineTo(OOB_LINE_BOUNDS.x1, THREE_POINT_LINE_LEFT.topY);
    ctx.closePath();
    ctx.fill();

    ctx.beginPath();
    ctx.moveTo(OOB_LINE_BOUNDS.x2, THREE_POINT_LINE_RIGHT.topY);
    ctx.quadraticCurveTo(
      THREE_POINT_LINE_RIGHT.controlX,
      THREE_POINT_LINE_RIGHT.topY,
      THREE_POINT_LINE_RIGHT.controlX,
      1042
    );
    ctx.quadraticCurveTo(
      THREE_POINT_LINE_RIGHT.controlX,
      THREE_POINT_LINE_RIGHT.bottomY,
      OOB_LINE_BOUNDS.x2,
      THREE_POINT_LINE_RIGHT.bottomY
    );
    ctx.lineTo(OOB_LINE_BOUNDS.x2, THREE_POINT_LINE_RIGHT.topY);
    ctx.closePath();
    ctx.fill();
  }

  function drawHardwoodFinish(ctx) {
    var grainCanvas = makeCanvas(WIDTH, HEIGHT);
    var g = grainCanvas.getContext('2d');
    var fullWidthStartX = OOB_LINE_BOUNDS.x1 + 22;
    var fullWidthEndX = OOB_LINE_BOUNDS.x2 - 22;
    var i;

    for (i = 0; i < 34; i += 1) {
      var bandTop = TOP_HORIZONTAL_OOB_Y + 12 + i * 52;
      var bandBottom = Math.min(bandTop + 28 + (i % 4) * 6, BOTTOM_HORIZONTAL_OOB_Y - 10);
      g.fillStyle = i % 2 === 0 ? 'rgba(255,248,238,0.055)' : 'rgba(140,101,66,0.042)';
      g.fillRect(OOB_LINE_BOUNDS.x1, bandTop, OOB_LINE_BOUNDS.x2 - OOB_LINE_BOUNDS.x1, bandBottom - bandTop);
    }

    for (i = 0; i < 26; i += 1) {
      var y = TOP_HORIZONTAL_OOB_Y + 38 + i * 68;
      var c1 = CENTER.x - 520 + (i % 5) * 28;
      var c2 = CENTER.x + 520 - (i % 4) * 34;
      var y1 = y + ((i % 3) - 1) * 12;
      var y2 = y + ((i % 4) - 1.5) * 10;
      g.strokeStyle = i % 3 === 0 ? 'rgba(255,248,237,0.18)' : 'rgba(145,104,68,0.12)';
      g.lineWidth = i % 5 === 0 ? 5 : 3;
      g.beginPath();
      g.moveTo(fullWidthStartX, y);
      g.quadraticCurveTo(c1, y1, CENTER.x, y + 6);
      g.quadraticCurveTo(c2, y2, fullWidthEndX, y + ((i % 2) * 6 - 3));
      g.stroke();
    }

    for (i = 0; i < 42; i += 1) {
      var startX = OOB_LINE_BOUNDS.x1 + 140 + ((i * 101) % 2350);
      var endX = Math.min(startX + 210 + (i % 6) * 38, OOB_LINE_BOUNDS.x2 - 120);
      var sy = TOP_HORIZONTAL_OOB_Y + 34 + ((i * 57) % (BOTTOM_HORIZONTAL_OOB_Y - TOP_HORIZONTAL_OOB_Y - 80));
      var c = startX + (endX - startX) / 2;
      var bend = ((i % 5) - 2) * 10;
      g.strokeStyle = i % 2 === 0 ? 'rgba(255,246,233,0.12)' : 'rgba(146,106,68,0.09)';
      g.lineWidth = i % 4 === 0 ? 3 : 2;
      g.beginPath();
      g.moveTo(startX, sy);
      g.quadraticCurveTo(c, sy + bend, endX, sy + ((i % 3) - 1) * 5);
      g.stroke();
    }

    var blurred = makeCanvas(WIDTH, HEIGHT);
    var b = blurred.getContext('2d');
    b.filter = 'blur(0.8px)';
    b.drawImage(grainCanvas, 0, 0);
    b.filter = 'none';
    ctx.drawImage(blurred, 0, 0);
  }

  function fillHalfEllipseCap(ctx, bbox, startDeg, endDeg) {
    var hc = halfCircleCenter(bbox);
    ctx.beginPath();
    // ImageMagick ellipse angles are CCW from east — match with counterclockwise=true.
    ctx.ellipse(hc.cx, hc.cy, hc.rx, hc.ry, 0, degToRad(startDeg), degToRad(endDeg), true);
    ctx.lineTo(hc.cx, hc.cy);
    ctx.closePath();
    ctx.fill();
  }

  function drawHalfCircleCaps(ctx, color) {
    ctx.fillStyle = color;
    fillHalfEllipseCap(ctx, LEFT_HALF_CIRCLE, 270, 90);
    fillHalfEllipseCap(ctx, RIGHT_HALF_CIRCLE, 90, 270);
  }

  function drawLaneRects(ctx, color) {
    ctx.fillStyle = color;
    ctx.fillRect(
      LANE_LEFT_RECT.x1,
      LANE_LEFT_RECT.y1,
      LANE_LEFT_RECT.x2 - LANE_LEFT_RECT.x1,
      LANE_LEFT_RECT.y2 - LANE_LEFT_RECT.y1
    );
    ctx.fillRect(
      LANE_RIGHT_RECT.x1,
      LANE_RIGHT_RECT.y1,
      LANE_RIGHT_RECT.x2 - LANE_RIGHT_RECT.x1,
      LANE_RIGHT_RECT.y2 - LANE_RIGHT_RECT.y1
    );
  }

  function strokeArcBBox(ctx, bbox, startDeg, endDeg) {
    var hc = halfCircleCenter(bbox);
    ctx.beginPath();
    ctx.ellipse(hc.cx, hc.cy, hc.rx, hc.ry, 0, degToRad(startDeg), degToRad(endDeg), true);
    ctx.stroke();
  }

  function drawPaintLinework(ctx, lineColor) {
    ctx.save();
    ctx.strokeStyle = lineColor;
    ctx.lineWidth = 8;
    ctx.fillStyle = 'none';
    ctx.setLineDash([]);
    ctx.lineDashOffset = 0;

    ctx.strokeRect(
      LANE_LEFT_RECT.x1,
      LANE_LEFT_RECT.y1,
      LANE_LEFT_RECT.x2 - LANE_LEFT_RECT.x1,
      LANE_LEFT_RECT.y2 - LANE_LEFT_RECT.y1
    );
    ctx.strokeRect(
      LANE_RIGHT_RECT.x1,
      LANE_RIGHT_RECT.y1,
      LANE_RIGHT_RECT.x2 - LANE_RIGHT_RECT.x1,
      LANE_RIGHT_RECT.y2 - LANE_RIGHT_RECT.y1
    );

    strokeArcBBox(ctx, LEFT_HALF_CIRCLE, 270, 90);
    strokeArcBBox(ctx, RIGHT_HALF_CIRCLE, 90, 270);

    ctx.setLineDash([40, 62]);
    ctx.lineDashOffset = -20;
    strokeArcBBox(ctx, LEFT_HALF_CIRCLE, 90, 270);
    strokeArcBBox(ctx, RIGHT_HALF_CIRCLE, 270, 90);
    ctx.restore();
  }

  function drawCourtLinework(ctx, lineColor) {
    ctx.save();
    ctx.strokeStyle = lineColor;
    ctx.lineWidth = 8;
    ctx.fillStyle = 'none';
    ctx.setLineDash([]);
    ctx.lineDashOffset = 0;

    ctx.beginPath();
    ctx.moveTo(OOB_LINE_BOUNDS.x1, TOP_HORIZONTAL_OOB_Y);
    ctx.lineTo(OOB_LINE_BOUNDS.x2, TOP_HORIZONTAL_OOB_Y);
    ctx.moveTo(OOB_LINE_BOUNDS.x1, BOTTOM_HORIZONTAL_OOB_Y);
    ctx.lineTo(OOB_LINE_BOUNDS.x2, BOTTOM_HORIZONTAL_OOB_Y);
    ctx.moveTo(OOB_LINE_BOUNDS.x1, TOP_HORIZONTAL_OOB_Y);
    ctx.lineTo(OOB_LINE_BOUNDS.x1, BOTTOM_HORIZONTAL_OOB_Y);
    ctx.moveTo(OOB_LINE_BOUNDS.x2, TOP_HORIZONTAL_OOB_Y);
    ctx.lineTo(OOB_LINE_BOUNDS.x2, BOTTOM_HORIZONTAL_OOB_Y);
    ctx.moveTo(CENTER.x, TOP_HORIZONTAL_OOB_Y);
    ctx.lineTo(CENTER.x, BOTTOM_HORIZONTAL_OOB_Y);
    ctx.stroke();

    ctx.beginPath();
    ctx.moveTo(THREE_POINT_LINE_LEFT.startX, THREE_POINT_LINE_LEFT.topY);
    ctx.quadraticCurveTo(
      THREE_POINT_LINE_LEFT.controlX,
      THREE_POINT_LINE_LEFT.topY,
      THREE_POINT_LINE_LEFT.controlX,
      1042
    );
    ctx.quadraticCurveTo(
      THREE_POINT_LINE_LEFT.controlX,
      THREE_POINT_LINE_LEFT.bottomY,
      THREE_POINT_LINE_LEFT.startX,
      THREE_POINT_LINE_LEFT.bottomY
    );
    ctx.stroke();

    ctx.beginPath();
    ctx.moveTo(THREE_POINT_LINE_RIGHT.startX, THREE_POINT_LINE_RIGHT.topY);
    ctx.quadraticCurveTo(
      THREE_POINT_LINE_RIGHT.controlX,
      THREE_POINT_LINE_RIGHT.topY,
      THREE_POINT_LINE_RIGHT.controlX,
      1042
    );
    ctx.quadraticCurveTo(
      THREE_POINT_LINE_RIGHT.controlX,
      THREE_POINT_LINE_RIGHT.bottomY,
      THREE_POINT_LINE_RIGHT.startX,
      THREE_POINT_LINE_RIGHT.bottomY
    );
    ctx.stroke();

    var hi;
    for (hi = 0; hi < LANE_OUTSIDE_HASHES_LEFT_X.length; hi += 1) {
      ctx.beginPath();
      ctx.moveTo(LANE_OUTSIDE_HASHES_LEFT_X[hi], LANE_OUTSIDE_HASH_TOP.y1);
      ctx.lineTo(LANE_OUTSIDE_HASHES_LEFT_X[hi], LANE_OUTSIDE_HASH_TOP.y2);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(LANE_OUTSIDE_HASHES_LEFT_X[hi], LANE_OUTSIDE_HASH_BOTTOM.y1);
      ctx.lineTo(LANE_OUTSIDE_HASHES_LEFT_X[hi], LANE_OUTSIDE_HASH_BOTTOM.y2);
      ctx.stroke();
    }
    for (hi = 0; hi < LANE_OUTSIDE_HASHES_RIGHT_X.length; hi += 1) {
      ctx.beginPath();
      ctx.moveTo(LANE_OUTSIDE_HASHES_RIGHT_X[hi], LANE_OUTSIDE_HASH_TOP.y1);
      ctx.lineTo(LANE_OUTSIDE_HASHES_RIGHT_X[hi], LANE_OUTSIDE_HASH_TOP.y2);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(LANE_OUTSIDE_HASHES_RIGHT_X[hi], LANE_OUTSIDE_HASH_BOTTOM.y1);
      ctx.lineTo(LANE_OUTSIDE_HASHES_RIGHT_X[hi], LANE_OUTSIDE_HASH_BOTTOM.y2);
      ctx.stroke();
    }
    ctx.restore();
  }

  function drawBackboardHeightExtensions(ctx, palette) {
    palette = palette || COLORS;
    ctx.fillStyle = palette.backboardOuter;
    ctx.fillRect(
      LEFT_BACKBOARD_EXT.outer.x1,
      LEFT_BACKBOARD_EXT.outer.y1,
      LEFT_BACKBOARD_EXT.outer.x2 - LEFT_BACKBOARD_EXT.outer.x1,
      LEFT_BACKBOARD_EXT.outer.y2 - LEFT_BACKBOARD_EXT.outer.y1
    );
    ctx.fillRect(
      RIGHT_BACKBOARD_EXT.outer.x1,
      RIGHT_BACKBOARD_EXT.outer.y1,
      RIGHT_BACKBOARD_EXT.outer.x2 - RIGHT_BACKBOARD_EXT.outer.x1,
      RIGHT_BACKBOARD_EXT.outer.y2 - RIGHT_BACKBOARD_EXT.outer.y1
    );
    ctx.fillStyle = palette.backboardGlass;
    ctx.fillRect(
      LEFT_BACKBOARD_EXT.glass.x1,
      LEFT_BACKBOARD_EXT.glass.y1,
      LEFT_BACKBOARD_EXT.glass.x2 - LEFT_BACKBOARD_EXT.glass.x1,
      LEFT_BACKBOARD_EXT.glass.y2 - LEFT_BACKBOARD_EXT.glass.y1
    );
    ctx.fillRect(
      RIGHT_BACKBOARD_EXT.glass.x1,
      RIGHT_BACKBOARD_EXT.glass.y1,
      RIGHT_BACKBOARD_EXT.glass.x2 - RIGHT_BACKBOARD_EXT.glass.x1,
      RIGHT_BACKBOARD_EXT.glass.y2 - RIGHT_BACKBOARD_EXT.glass.y1
    );
  }

  function drawRimFallbackStrokes(ctx, palette) {
    palette = palette || COLORS;
    ctx.save();
    ctx.lineWidth = 10;
    ctx.strokeStyle = palette.support;
    ctx.beginPath();
    ctx.moveTo(118, RIM_LEFT.y);
    ctx.lineTo(72, RIM_LEFT.y);
    ctx.moveTo(3215, RIM_RIGHT.y);
    ctx.lineTo(3261, RIM_RIGHT.y);
    ctx.stroke();

    ctx.strokeStyle = palette.backboardOuter;
    ctx.strokeRect(92, 895, 124 - 92, 1189 - 895);
    ctx.strokeRect(3209, 895, 3241 - 3209, 1189 - 895);

    ctx.lineWidth = 6;
    ctx.strokeStyle = palette.backboardInner;
    ctx.strokeRect(102, 971, 116 - 102, 1113 - 971);
    ctx.strokeRect(3219, 971, 3233 - 3219, 1113 - 971);

    ctx.lineWidth = 8;
    ctx.strokeStyle = palette.rim;
    ctx.beginPath();
    ctx.arc(RIM_LEFT.x, RIM_LEFT.y, 46, 0, Math.PI * 2);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(RIM_RIGHT.x, RIM_RIGHT.y, 46, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();
  }

  function overlaysReady(images) {
    return images && images.leftBasket && images.rightBasket;
  }

  function drawOverlays(ctx, images) {
    if (!overlaysReady(images)) return false;
    ctx.drawImage(images.leftBasket, 126, 922);
    ctx.drawImage(images.rightBasket, 3042, 922);
    if (images.leftBackboard && images.rightBackboard) {
      ctx.drawImage(images.leftBackboard, 132, 994);
      ctx.drawImage(images.rightBackboard, 3051, 994);
    }
    if (images.leftRimnet && images.rightRimnet) {
      ctx.drawImage(images.leftRimnet, 190, 930);
      ctx.drawImage(images.rightRimnet, 2923, 930);
    }
    return true;
  }

  function loadImage(url) {
    return new Promise(function (resolve, reject) {
      var img = new Image();
      img.crossOrigin = 'anonymous';
      img.onload = function () {
        resolve(img);
      };
      img.onerror = function () {
        reject(new Error('Failed to load ' + url));
      };
      img.src = url;
    });
  }

  function preloadOverlayImages() {
    if (overlayCachePromise) return overlayCachePromise;
    overlayCachePromise = Promise.all([
      loadImage(OVERLAY_PATHS.leftBasket).catch(function () {
        return null;
      }),
      loadImage(OVERLAY_PATHS.rightBasket).catch(function () {
        return null;
      }),
      loadImage(OVERLAY_PATHS.rightBackboard).catch(function () {
        return null;
      }),
      loadImage(OVERLAY_PATHS.leftRimnet).catch(function () {
        return null;
      }),
      loadImage(OVERLAY_PATHS.rightRimnet).catch(function () {
        return null;
      }),
    ]).then(function (parts) {
      return {
        leftBasket: parts[0],
        rightBasket: parts[1],
        leftBackboard: null,
        rightBackboard: parts[2],
        leftRimnet: parts[3],
        rightRimnet: parts[4],
      };
    });
    return overlayCachePromise;
  }

  function drawMarkingsOnly(ctx, params, palette) {
    palette = palette || COLORS;
    var line = params.lineColor;
    drawPaintLinework(ctx, line);
    drawCourtLinework(ctx, line);
    drawBackboardHeightExtensions(ctx, palette);
    drawRimFallbackStrokes(ctx, palette);
  }

  function renderCourtCanvas(opts) {
    var params = resolveRenderParams(opts);
    var canvas = makeCanvas(WIDTH, HEIGHT);
    var ctx = canvas.getContext('2d');

    ctx.fillStyle = params.oobColor;
    ctx.fillRect(0, 0, WIDTH, HEIGHT);

    drawWoodBase(ctx, params.outsideWood, params.insideWood);
    drawHardwoodFinish(ctx);
    drawHalfCircleCaps(ctx, params.halfArcFillColor);
    drawLaneRects(ctx, params.laneColor);
    drawPaintLinework(ctx, params.lineColor);
    drawCourtLinework(ctx, params.lineColor);
    drawBackboardHeightExtensions(ctx, COLORS);

    var usedOverlays =
      params.useOverlays && params.overlayImages && drawOverlays(ctx, params.overlayImages);
    if (!usedOverlays) {
      drawRimFallbackStrokes(ctx, COLORS);
    }

    return canvas;
  }

  function markingsMaskCanvas(opts) {
    var params = resolveRenderParams(opts);
    var canvas = makeCanvas(WIDTH, HEIGHT);
    var ctx = canvas.getContext('2d');
    ctx.fillStyle = '#000000';
    ctx.fillRect(0, 0, WIDTH, HEIGHT);
    ctx.save();
    ctx.strokeStyle = '#ffffff';
    ctx.fillStyle = '#ffffff';
    var whitePalette = {
      line: '#ffffff',
      rim: '#ffffff',
      backboardOuter: '#ffffff',
      backboardInner: '#ffffff',
      support: '#ffffff',
      backboardGlass: '#ffffff',
    };
    drawMarkingsOnly(ctx, { lineColor: '#ffffff' }, whitePalette);
    ctx.restore();
    return canvas;
  }

  function courtPreviewDataUrl(opts) {
    var full = renderCourtCanvas(Object.assign({}, opts, { useOverlays: false }));
    var previewW = 240;
    var previewH = Math.round(previewW * (HEIGHT / WIDTH));
    var preview = makeCanvas(previewW, previewH);
    var ctx = preview.getContext('2d');
    ctx.drawImage(full, 0, 0, previewW, previewH);
    return preview.toDataURL('image/jpeg', 0.85);
  }

  function courtObjectUrl(opts) {
    opts = opts || {};
    var renderOpts = Object.assign({}, opts);
    if (!renderOpts.overlayImages) {
      return preloadOverlayImages().then(function (images) {
        renderOpts.overlayImages = images;
        renderOpts.useOverlays = true;
        var canvas = renderCourtCanvas(renderOpts);
        return new Promise(function (resolve, reject) {
          if (!canvas.toBlob) {
            reject(new Error('canvas.toBlob unavailable'));
            return;
          }
          canvas.toBlob(
            function (blob) {
              if (!blob) {
                reject(new Error('court JPEG encode failed'));
                return;
              }
              resolve(URL.createObjectURL(blob));
            },
            'image/jpeg',
            0.92
          );
        });
      });
    }
    renderOpts.useOverlays = true;
    var syncCanvas = renderCourtCanvas(renderOpts);
    return new Promise(function (resolve, reject) {
      syncCanvas.toBlob(
        function (blob) {
          if (!blob) {
            reject(new Error('court JPEG encode failed'));
            return;
          }
          resolve(URL.createObjectURL(blob));
        },
        'image/jpeg',
        0.92
      );
    });
  }

  global.TeamCourtGenerator = {
    WIDTH: WIDTH,
    HEIGHT: HEIGHT,
    HARDWOOD_VARIANTS: HARDWOOD_VARIANTS,
    HARDWOOD_TONES: HARDWOOD_TONES,
    GEOMETRY: GEOMETRY,
    A1_REFERENCE_SLUGS: A1_REFERENCE_SLUGS,
    COLORS: COLORS,
    defaultsFromTeamColors: defaultsFromTeamColors,
    renderCourtCanvas: renderCourtCanvas,
    courtObjectUrl: courtObjectUrl,
    courtPreviewDataUrl: courtPreviewDataUrl,
    markingsMaskCanvas: markingsMaskCanvas,
    preloadOverlayImages: preloadOverlayImages,
  };
})(typeof window !== 'undefined' ? window : globalThis);
