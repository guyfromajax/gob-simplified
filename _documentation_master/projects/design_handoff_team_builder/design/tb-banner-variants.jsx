/* GOB Team Builder — banner composition options.

   Five candidate draw functions in the SAME contract as production's
   drawChevronBanner(ctx, width, height, opts): card space is 400×141 and every
   composition scales from it rather than re-laying-out. Constants, ink rule and
   mascot-opacity rule are lifted from teamGeneratedArt.js verbatim so a chosen
   variant drops straight in.

   Variant A is the shipped generator, unmodified, as the control. */
const TGAV = window.TeamGeneratedArt;

const CARD_W = 400, CARD_H = 141;
const WORD_START = 50, WORD_FLOOR = 20, WORD_MAX_W = 300, WORD_Y = 78;
const MASCOT_Y = 99, MASCOT_SIZE = 10, GHOST_SIZE = 150;
const MASCOT_ALPHA = 0.6, FLOOR_RATIO = 4.5;
const BEBAS = '"Bebas Neue Pro", "Bebas Neue", Impact, sans-serif';
const OSWALD = 'Oswald, "Arial Narrow", sans-serif';

/* mirrors fitWordmark — not exported by the shipped module */
function fitWord(ctx, text, maxW, startSize, minSize) {
  let size = startSize, guard = 0;
  ctx.font = size + 'px ' + BEBAS;
  while (ctx.measureText(text).width > maxW && size > minSize && guard++ < 80) {
    size -= 1;
    ctx.font = size + 'px ' + BEBAS;
  }
  return { size, width: ctx.measureText(text).width, atFloor: size <= minSize };
}

/* mirrors drawSpacedText */
function spaced(ctx, text, x, y, tracking, align) {
  const chars = String(text || '').split('');
  const widths = chars.map(c => ctx.measureText(c).width);
  let total = widths.reduce((a, b) => a + b, 0) + tracking * Math.max(0, chars.length - 1);
  let cursor = align === 'left' ? x : x - total / 2;
  chars.forEach((c, i) => { ctx.fillText(c, cursor, y); cursor += widths[i] + tracking; });
}

function poly(ctx, pts) {
  ctx.beginPath();
  ctx.moveTo(pts[0][0], pts[0][1]);
  for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
  ctx.closePath();
  ctx.fill();
}

function base(ctx, w, h, opts) {
  const primary = opts.primary || '#27408E';
  const secondary = opts.secondary || '#15181f';
  return {
    primary, secondary,
    dark: TGAV.shadeHex(primary, -0.16),
    scale: w / CARD_W,
    initials: TGAV.initialsFromName(opts.name, opts.abbreviation, null),
    school: String(opts.name || 'Custom Program').toUpperCase(),
    mascot: String(opts.mascot || '').trim().toUpperCase()
  };
}

/* wordmark + mascot, drawn identically in every variant so only the field changes */
function type(ctx, s, w, h, ink, surface, align, x, maxCardW) {
  const maxW = (maxCardW == null ? WORD_MAX_W : maxCardW) * s.scale;
  const fit = fitWord(ctx, s.school, maxW, WORD_START * s.scale, WORD_FLOOR * s.scale);
  ctx.font = fit.size + 'px ' + BEBAS;
  ctx.fillStyle = ink;
  ctx.textAlign = align || 'center';
  ctx.textBaseline = 'alphabetic';
  const wx = x == null ? w / 2 : x;
  ctx.fillText(s.school, wx, WORD_Y * s.scale);
  let alpha = 0, ratio = null;
  if (s.mascot) {
    const mSurface = s.mascotSurface || surface;
    alpha = TGAV.opacityForContrast(ink, mSurface, MASCOT_ALPHA, FLOOR_RATIO);
    ratio = TGAV.contrastRatio(TGAV.compositeOver(ink, mSurface, alpha), mSurface);
    ctx.font = '300 ' + MASCOT_SIZE * s.scale + 'px ' + OSWALD;
    ctx.fillStyle = ink;
    ctx.globalAlpha = alpha;
    ctx.textAlign = 'left';
    spaced(ctx, s.mascot, wx, MASCOT_Y * s.scale, 4.5 * s.scale, align === 'left' ? 'left' : 'center');
    ctx.globalAlpha = 1;
  }
  return { wordSize: fit.size, atFloor: fit.atFloor, ink, surface, alpha, ratio,
    mascotSurface: s.mascotSurface || surface,
    contrast: TGAV.contrastRatio(ink, surface) };
}

function ghost(ctx, s, w, h, color, x) {
  ctx.font = GHOST_SIZE * s.scale + 'px ' + BEBAS;
  ctx.fillStyle = color;
  ctx.globalAlpha = 0.12;
  ctx.textAlign = 'left';
  ctx.textBaseline = 'alphabetic';
  if (typeof ctx.letterSpacing === 'string') ctx.letterSpacing = -2 * s.scale + 'px';
  ctx.fillText(s.initials, (x == null ? -14 : x) * s.scale, h + 26 * s.scale);
  if (typeof ctx.letterSpacing === 'string') ctx.letterSpacing = '0px';
  ctx.globalAlpha = 1;
}

/* ---------- A · Chevron (shipped, unmodified) ---------- */
function drawA(ctx, w, h, opts) {
  return TGAV.drawChevronBanner(ctx, w, h, opts);
}

/* ---------- B · Keel — secondary moves to the right edge, off the type ---------- */
function drawB(ctx, w, h, opts) {
  const s = base(ctx, w, h, opts);
  ctx.save();
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = s.primary;
  ctx.fillRect(0, 0, w, h);
  ctx.fillStyle = s.dark;
  ctx.fillRect(332 * s.scale, 0, w - 332 * s.scale, h);
  ctx.fillStyle = s.secondary;
  ctx.fillRect(322 * s.scale, 0, 10 * s.scale, h);
  ctx.globalAlpha = 0.4;
  ctx.fillRect(314 * s.scale, 0, 4 * s.scale, h);
  ctx.globalAlpha = 1;
  ghost(ctx, s, w, h, s.secondary);
  const ink = TGAV.inkOn(s.primary);
  const meta = type(ctx, s, 322 * s.scale, h, ink, s.primary);
  ctx.font = 34 * s.scale + 'px ' + BEBAS;
  ctx.fillStyle = TGAV.inkOn(s.dark);
  ctx.textAlign = 'center';
  ctx.fillText(s.initials, (332 + (400 - 332) / 2) * s.scale, 90 * s.scale);
  ctx.restore();
  return Object.assign(meta, { initials: s.initials, dark: s.dark });
}

/* ---------- C · Baseline — nothing crosses the type at all ---------- */
function drawC(ctx, w, h, opts) {
  const s = base(ctx, w, h, opts);
  ctx.save();
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = s.primary;
  ctx.fillRect(0, 0, w, h);
  const g = ctx.createLinearGradient(0, 0, 0, h);
  g.addColorStop(0, 'rgba(255,255,255,0.10)');
  g.addColorStop(0.55, 'rgba(0,0,0,0)');
  g.addColorStop(1, 'rgba(0,0,0,0.28)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, w, h);
  ghost(ctx, s, w, h, s.secondary);
  ctx.fillStyle = s.secondary;
  ctx.fillRect(0, h - 9 * s.scale, w, 9 * s.scale);
  ctx.globalAlpha = 0.35;
  ctx.fillRect(0, h - 13 * s.scale, w, 2 * s.scale);
  ctx.globalAlpha = 1;
  const ink = TGAV.inkOn(s.primary);
  const meta = type(ctx, s, w, h, ink, s.primary);
  ctx.restore();
  return Object.assign(meta, { initials: s.initials });
}

/* ---------- D · Plate — asymmetric; initials block, type left-aligned ---------- */
function drawD(ctx, w, h, opts) {
  const s = base(ctx, w, h, opts);
  const plateW = 104 * s.scale;
  ctx.save();
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = s.primary;
  ctx.fillRect(0, 0, w, h);
  ctx.fillStyle = 'rgba(0,0,0,0.16)';
  ctx.fillRect(plateW, 0, w - plateW, h);
  ctx.fillStyle = s.secondary;
  ctx.fillRect(0, 0, plateW, h);
  const plateInk = TGAV.inkOn(s.secondary);
  ctx.font = 62 * s.scale + 'px ' + BEBAS;
  ctx.fillStyle = plateInk;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'alphabetic';
  ctx.fillText(s.initials, plateW / 2, 92 * s.scale);
  const field = TGAV.shadeHex(s.primary, -0.06);
  const ink = TGAV.inkOn(s.primary);
  /* fit against the real field width, so a long name shrinks instead of clipping */
  const meta = type(ctx, s, w, h, ink, s.primary, 'left', plateW + 18 * s.scale, 264);
  ctx.restore();
  return Object.assign(meta, { initials: s.initials, plateInk, plateContrast: TGAV.contrastRatio(plateInk, s.secondary), field });
}

/* ---------- E · Sash — diagonal energy kept, but under the wordmark ---------- */
function drawE(ctx, w, h, opts) {
  const s = base(ctx, w, h, opts);
  ctx.save();
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = s.primary;
  ctx.fillRect(0, 0, w, h);
  ghost(ctx, s, w, h, s.secondary, 250);
  ctx.fillStyle = s.dark;
  poly(ctx, [[0, 122 * s.scale], [w, 105 * s.scale], [w, h], [0, h]]);
  ctx.fillStyle = s.secondary;
  ctx.globalAlpha = 0.92;
  poly(ctx, [[0, 122 * s.scale], [w, 105 * s.scale], [w, 109 * s.scale], [0, 126 * s.scale]]);
  ctx.globalAlpha = 1;
  const ink = TGAV.inkOn(s.primary);
  const meta = type(ctx, s, w, h, ink, s.primary);
  ctx.restore();
  return Object.assign(meta, { initials: s.initials, dark: s.dark });
}

const BANNER_VARIANTS = [
  { key: 'A', name: 'Chevron', tag: 'shipped today', draw: drawA,
    note: 'The diagonal runs from the baseline up through the centre of the card, which is exactly where the wordmark sits. On a light secondary the strip cuts through the letterforms.' },
  { key: 'B', name: 'Keel', tag: 'band moved off the type', draw: drawB,
    note: 'The same two-tone split and secondary strips, pushed to the right edge as a vertical keel with the initials in it. Nothing crosses the wordmark, and the secondary still reads at full strength.' },
  { key: 'C', name: 'Baseline', tag: 'no ornament over the field', draw: drawC,
    note: 'One full-width secondary rule along the bottom, a soft top light and the ghost initials. The quietest option and the most institutional — a banner rather than a jersey.' },
  { key: 'D', name: 'Plate', tag: 'asymmetric lockup', draw: drawD,
    note: 'A solid secondary plate carrying the initials, with the wordmark left-aligned on the field beside it. The only variant where the secondary carries type, and the only asymmetric composition — its narrower field means long names shrink sooner than in the other four.' },
  { key: 'E', name: 'Sash', tag: 'diagonal kept, lowered', draw: drawE,
    note: 'Keeps the diagonal gesture but drops it clear of both lines of type, so it reads as a raked foot to the card rather than a stripe across the name. Closest to the shipped feel of the five.' }
];

Object.assign(window, { BANNER_VARIANTS, CARD_W, CARD_H });
