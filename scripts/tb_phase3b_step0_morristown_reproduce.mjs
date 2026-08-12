/**
 * Phase 3b Step 0 — reproduce Morristown markings from measured geometry, then stop.
 *
 * Geometry constants are taken from scripts/generate_non_a1_courts.mjs (already
 * measured against Bentley-Truman / Morristown A1 courts). This script:
 *   1. Renders a markings-only mask from those constants
 *   2. Extracts a markings mask from the Morristown JPEG
 *   3. Reports per-feature and whole-mask pixel agreement
 *
 * Usage: node scripts/tb_phase3b_step0_morristown_reproduce.mjs
 */
import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'url';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
// Prefer sharp if present; else fall back to PNG via magick + pure JS.
let sharp = null;
try {
  sharp = require('sharp');
} catch (_) {
  sharp = null;
}

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(__dirname, '..');
const SOURCE = path.join(
  ROOT,
  'FrontEnd/static/images/teams/morristown/morristown_court.jpg'
);
const OUTDIR = path.join(ROOT, 'tmp/court-template/step0-morristown');

// ── Geometry from generate_non_a1_courts.mjs (do not invent new numbers) ──
const CANVAS = { w: 3333, h: 2083 };
const OOB_LINE_BOUNDS = { x1: 150, y1: 84, x2: 3183, y2: 1998 };
const TOP_HORIZONTAL_OOB_Y = 158;
const BOTTOM_HORIZONTAL_OOB_Y = 1924;
const THREE_POINT_LINE_LEFT = {
  startX: OOB_LINE_BOUNDS.x1,
  controlX: 1112,
  topY: 308,
  bottomY: 1770,
};
const THREE_POINT_LINE_RIGHT = {
  startX: OOB_LINE_BOUNDS.x2,
  controlX: 2213,
  topY: 308,
  bottomY: 1770,
};
const CENTER = { x: 1666, y: 1042 };
const LANE_LEFT_RECT = { x1: 150, y1: 806, x2: 872, y2: 1271 };
const LANE_RIGHT_RECT = { x1: 2452, y1: 806, x2: 3183, y2: 1271 };
const LEFT_HALF_CIRCLE = { x1: 641, y1: 808, x2: 1103, y2: 1269 };
const RIGHT_HALF_CIRCLE = { x1: 2221, y1: 808, x2: 2683, y2: 1269 };
const RIM_LEFT = { x: 300, y: 1042 };
const RIM_RIGHT = { x: 3033, y: 1042 };
const CENTER_CIRCLE_R = 1042 - 515; // from build_neutral_court_master circle
const STROKE = 8;

function ensureDir(dir) {
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
}

function runMagick(args) {
  execFileSync('magick', args, { stdio: 'pipe' });
}

function renderGeometryMarkingsMask(outfile) {
  // White markings on black — geometry only, no fills/branding.
  const args = [
    '-size',
    `${CANVAS.w}x${CANVAS.h}`,
    'xc:black',
    '-fill',
    'none',
    '-stroke',
    'white',
    '-strokewidth',
    String(STROKE),
    // OOB box
    '-draw',
    `line ${OOB_LINE_BOUNDS.x1},${TOP_HORIZONTAL_OOB_Y} ${OOB_LINE_BOUNDS.x2},${TOP_HORIZONTAL_OOB_Y}`,
    '-draw',
    `line ${OOB_LINE_BOUNDS.x1},${BOTTOM_HORIZONTAL_OOB_Y} ${OOB_LINE_BOUNDS.x2},${BOTTOM_HORIZONTAL_OOB_Y}`,
    '-draw',
    `line ${OOB_LINE_BOUNDS.x1},${TOP_HORIZONTAL_OOB_Y} ${OOB_LINE_BOUNDS.x1},${BOTTOM_HORIZONTAL_OOB_Y}`,
    '-draw',
    `line ${OOB_LINE_BOUNDS.x2},${TOP_HORIZONTAL_OOB_Y} ${OOB_LINE_BOUNDS.x2},${BOTTOM_HORIZONTAL_OOB_Y}`,
    // Centre line
    '-draw',
    `line ${CENTER.x},${TOP_HORIZONTAL_OOB_Y} ${CENTER.x},${BOTTOM_HORIZONTAL_OOB_Y}`,
    // Centre circle
    '-draw',
    `circle ${CENTER.x},${CENTER.y} ${CENTER.x},${CENTER.y - CENTER_CIRCLE_R}`,
    // 3-point arcs
    '-draw',
    `path 'M ${THREE_POINT_LINE_LEFT.startX},${THREE_POINT_LINE_LEFT.topY} Q ${THREE_POINT_LINE_LEFT.controlX},${THREE_POINT_LINE_LEFT.topY} ${THREE_POINT_LINE_LEFT.controlX},1042 Q ${THREE_POINT_LINE_LEFT.controlX},${THREE_POINT_LINE_LEFT.bottomY} ${THREE_POINT_LINE_LEFT.startX},${THREE_POINT_LINE_LEFT.bottomY}'`,
    '-draw',
    `path 'M ${THREE_POINT_LINE_RIGHT.startX},${THREE_POINT_LINE_RIGHT.topY} Q ${THREE_POINT_LINE_RIGHT.controlX},${THREE_POINT_LINE_RIGHT.topY} ${THREE_POINT_LINE_RIGHT.controlX},1042 Q ${THREE_POINT_LINE_RIGHT.controlX},${THREE_POINT_LINE_RIGHT.bottomY} ${THREE_POINT_LINE_RIGHT.startX},${THREE_POINT_LINE_RIGHT.bottomY}'`,
    // Lane rectangles
    '-draw',
    `rectangle ${LANE_LEFT_RECT.x1},${LANE_LEFT_RECT.y1} ${LANE_LEFT_RECT.x2},${LANE_LEFT_RECT.y2}`,
    '-draw',
    `rectangle ${LANE_RIGHT_RECT.x1},${LANE_RIGHT_RECT.y1} ${LANE_RIGHT_RECT.x2},${LANE_RIGHT_RECT.y2}`,
    // Free-throw half-arcs (solid outer + dashed inner as in generator)
    '-draw',
    `arc ${LEFT_HALF_CIRCLE.x1},${LEFT_HALF_CIRCLE.y1} ${LEFT_HALF_CIRCLE.x2},${LEFT_HALF_CIRCLE.y2} 270,90`,
    '-draw',
    `arc ${RIGHT_HALF_CIRCLE.x1},${RIGHT_HALF_CIRCLE.y1} ${RIGHT_HALF_CIRCLE.x2},${RIGHT_HALF_CIRCLE.y2} 90,270`,
    '-draw',
    `stroke-dasharray 40,62 stroke-dashoffset 20 arc ${LEFT_HALF_CIRCLE.x1},${LEFT_HALF_CIRCLE.y1} ${LEFT_HALF_CIRCLE.x2},${LEFT_HALF_CIRCLE.y2} 90,270`,
    '-draw',
    `stroke-dasharray 40,62 stroke-dashoffset 20 arc ${RIGHT_HALF_CIRCLE.x1},${RIGHT_HALF_CIRCLE.y1} ${RIGHT_HALF_CIRCLE.x2},${RIGHT_HALF_CIRCLE.y2} 270,90`,
    // Rims (runtime anchors) — filled rings for detection
    '-fill',
    'white',
    '-stroke',
    'white',
    '-strokewidth',
    '6',
    '-draw',
    `circle ${RIM_LEFT.x},${RIM_LEFT.y} ${RIM_LEFT.x + 46},${RIM_LEFT.y}`,
    '-draw',
    `circle ${RIM_RIGHT.x},${RIM_RIGHT.y} ${RIM_RIGHT.x + 46},${RIM_RIGHT.y}`,
    '-fill',
    'black',
    '-draw',
    `circle ${RIM_LEFT.x},${RIM_LEFT.y} ${RIM_LEFT.x + 34},${RIM_LEFT.y}`,
    '-draw',
    `circle ${RIM_RIGHT.x},${RIM_RIGHT.y} ${RIM_RIGHT.x + 34},${RIM_RIGHT.y}`,
    outfile,
  ];
  runMagick(args);
}

function extractSourceMarkingsMask(sourceJpg, outfile) {
  // Morristown lines are dark grey on warm wood / red paint.
  // Isolate dark line-like pixels inside the playable floor, exclude near-black borders
  // and saturated paint fills (keep only darker low-chroma strokes).
  runMagick([
    sourceJpg,
    '-colorspace',
    'Lab',
    '-channel',
    '0',
    '-separate',
    '+channel',
    '(',
    sourceJpg,
    '-colorspace',
    'HSI',
    '-channel',
    '1',
    '-separate',
    '+channel',
    ')',
    '-compose',
    'Mathematics',
    '-define',
    'compose:args=0,-1,1,0.35',
    '-composite',
    '-threshold',
    '42%',
    '-negate',
    '(',
    '+clone',
    '-fill',
    'black',
    '-draw',
    `rectangle 0,0 ${CANVAS.w - 1},${CANVAS.h - 1}`,
    '-fill',
    'white',
    '-draw',
    `rectangle ${OOB_LINE_BOUNDS.x1 - 20},${TOP_HORIZONTAL_OOB_Y - 20} ${OOB_LINE_BOUNDS.x2 + 20},${BOTTOM_HORIZONTAL_OOB_Y + 20}`,
    ')',
    '-compose',
    'Multiply',
    '-composite',
    // Drop thick paint fills: keep thin structures via morphological open-ish
    '-morphology',
    'Close',
    'Disk:1',
    '-morphology',
    'Open',
    'Disk:1',
    outfile,
  ]);
}

function loadMaskBinary(pngPath) {
  // Convert to raw gray via magick, parse in JS.
  const raw = execFileSync(
    'magick',
    [pngPath, '-depth', '8', 'gray:-'],
    { maxBuffer: 40 * 1024 * 1024 }
  );
  const expected = CANVAS.w * CANVAS.h;
  if (raw.length !== expected) {
    throw new Error(`mask size mismatch: got ${raw.length}, expected ${expected}`);
  }
  const bits = new Uint8Array(expected);
  for (let i = 0; i < expected; i++) bits[i] = raw[i] > 127 ? 1 : 0;
  return bits;
}

function dilate(mask, radius) {
  if (radius <= 0) return mask;
  const out = new Uint8Array(mask.length);
  const w = CANVAS.w;
  const h = CANVAS.h;
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      let hit = 0;
      for (let dy = -radius; dy <= radius && !hit; dy++) {
        for (let dx = -radius; dx <= radius && !hit; dx++) {
          const xx = x + dx;
          const yy = y + dy;
          if (xx < 0 || yy < 0 || xx >= w || yy >= h) continue;
          if (mask[yy * w + xx]) hit = 1;
        }
      }
      out[y * w + x] = hit;
    }
  }
  return out;
}

function maskStats(source, rendered, label) {
  let src = 0;
  let ren = 0;
  let both = 0;
  for (let i = 0; i < source.length; i++) {
    if (source[i]) src++;
    if (rendered[i]) ren++;
    if (source[i] && rendered[i]) both++;
  }
  const recall = src ? both / src : 0;
  const precision = ren ? both / ren : 0;
  const iou = src + ren - both ? both / (src + ren - both) : 0;
  return {
    label,
    sourcePixels: src,
    renderedPixels: ren,
    intersection: both,
    recall: Number(recall.toFixed(4)),
    precision: Number(precision.toFixed(4)),
    iou: Number(iou.toFixed(4)),
  };
}

function sampleAlongLine(mask, x1, y1, x2, y2, samples = 200) {
  let hits = 0;
  for (let i = 0; i < samples; i++) {
    const t = i / (samples - 1);
    const x = Math.round(x1 + (x2 - x1) * t);
    const y = Math.round(y1 + (y2 - y1) * t);
    if (x < 0 || y < 0 || x >= CANVAS.w || y >= CANVAS.h) continue;
    if (mask[y * CANVAS.w + x]) hits++;
  }
  return { hits, samples, rate: Number((hits / samples).toFixed(4)) };
}

function sampleQuadratic(mask, x0, y0, cx, cy, x1, y1, samples = 300) {
  // Approximate Q as two segments via de Casteljau samples
  let hits = 0;
  for (let i = 0; i < samples; i++) {
    const t = i / (samples - 1);
    const u = 1 - t;
    const x = Math.round(u * u * x0 + 2 * u * t * cx + t * t * x1);
    const y = Math.round(u * u * y0 + 2 * u * t * cy + t * t * y1);
    if (x < 0 || y < 0 || x >= CANVAS.w || y >= CANVAS.h) continue;
    if (mask[y * CANVAS.w + x]) hits++;
  }
  return { hits, samples, rate: Number((hits / samples).toFixed(4)) };
}

function sampleCircle(mask, cx, cy, r, samples = 360) {
  let hits = 0;
  for (let i = 0; i < samples; i++) {
    const a = (i / samples) * Math.PI * 2;
    const x = Math.round(cx + Math.cos(a) * r);
    const y = Math.round(cy + Math.sin(a) * r);
    if (x < 0 || y < 0 || x >= CANVAS.w || y >= CANVAS.h) continue;
    if (mask[y * CANVAS.w + x]) hits++;
  }
  return { hits, samples, rate: Number((hits / samples).toFixed(4)) };
}

function rimCentroidNear(sourceRgbPath, expectX, expectY, searchR = 80) {
  // Find reddish rim pixels near expected anchor; return centroid delta.
  const raw = execFileSync(
    'magick',
    [
      sourceRgbPath,
      '-crop',
      `${searchR * 2}x${searchR * 2}+${expectX - searchR}+${expectY - searchR}`,
      '+repage',
      '-depth',
      '8',
      'rgb:-',
    ],
    { maxBuffer: 20 * 1024 * 1024 }
  );
  const w = searchR * 2;
  const h = searchR * 2;
  let sx = 0;
  let sy = 0;
  let n = 0;
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = (y * w + x) * 3;
      const r = raw[i];
      const g = raw[i + 1];
      const b = raw[i + 2];
      // rim-ish: reddish / pinkish, not wood
      if (r > 160 && r > g + 20 && r > b + 10) {
        sx += x;
        sy += y;
        n++;
      }
    }
  }
  if (!n) return { found: false, dx: null, dy: null, n: 0 };
  const cx = sx / n;
  const cy = sy / n;
  return {
    found: true,
    n,
    dx: Number((cx - searchR).toFixed(2)),
    dy: Number((cy - searchR).toFixed(2)),
    abs: Number(Math.hypot(cx - searchR, cy - searchR).toFixed(2)),
  };
}

function featureWindowStats(source, rendered, x1, y1, x2, y2, label) {
  const w = CANVAS.w;
  let src = 0;
  let ren = 0;
  let both = 0;
  for (let y = y1; y <= y2; y++) {
    for (let x = x1; x <= x2; x++) {
      const i = y * w + x;
      if (source[i]) src++;
      if (rendered[i]) ren++;
      if (source[i] && rendered[i]) both++;
    }
  }
  return {
    label,
    box: { x1, y1, x2, y2 },
    sourcePixels: src,
    renderedPixels: ren,
    intersection: both,
    recall: src ? Number((both / src).toFixed(4)) : null,
    precision: ren ? Number((both / ren).toFixed(4)) : null,
    iou: src + ren - both ? Number((both / (src + ren - both)).toFixed(4)) : null,
  };
}

ensureDir(OUTDIR);

if (!existsSync(SOURCE)) {
  console.error('Missing Morristown court:', SOURCE);
  process.exit(1);
}

const geomMaskPath = path.join(OUTDIR, 'geometry_markings_mask.png');
const sourceMaskPath = path.join(OUTDIR, 'morristown_extracted_markings_mask.png');
const overlayPath = path.join(OUTDIR, 'agreement_overlay.png');

console.log('Rendering geometry markings mask…');
renderGeometryMarkingsMask(geomMaskPath);

console.log('Extracting Morristown markings mask…');
extractSourceMarkingsMask(SOURCE, sourceMaskPath);

// Visual overlay: source red, geometry green, agreement yellow
runMagick([
  '(',
  sourceMaskPath,
  '-fill',
  'red',
  '-opaque',
  'white',
  ')',
  '(',
  geomMaskPath,
  '-fill',
  'lime',
  '-opaque',
  'white',
  ')',
  '-compose',
  'screen',
  '-composite',
  overlayPath,
]);

console.log('Comparing masks…');
const sourceMask = loadMaskBinary(sourceMaskPath);
const geomMask = loadMaskBinary(geomMaskPath);
const exact = maskStats(sourceMask, geomMask, 'exact (0px)');
const tol1 = maskStats(sourceMask, dilate(geomMask, 1), 'source⊂geom±1px');
const tol2 = maskStats(sourceMask, dilate(geomMask, 2), 'source⊂geom±2px');
const tol2rev = maskStats(geomMask, dilate(sourceMask, 2), 'geom⊂source±2px');

const features = {
  oob_top: sampleAlongLine(
    sourceMask,
    OOB_LINE_BOUNDS.x1,
    TOP_HORIZONTAL_OOB_Y,
    OOB_LINE_BOUNDS.x2,
    TOP_HORIZONTAL_OOB_Y
  ),
  oob_bottom: sampleAlongLine(
    sourceMask,
    OOB_LINE_BOUNDS.x1,
    BOTTOM_HORIZONTAL_OOB_Y,
    OOB_LINE_BOUNDS.x2,
    BOTTOM_HORIZONTAL_OOB_Y
  ),
  oob_left: sampleAlongLine(
    sourceMask,
    OOB_LINE_BOUNDS.x1,
    TOP_HORIZONTAL_OOB_Y,
    OOB_LINE_BOUNDS.x1,
    BOTTOM_HORIZONTAL_OOB_Y
  ),
  oob_right: sampleAlongLine(
    sourceMask,
    OOB_LINE_BOUNDS.x2,
    TOP_HORIZONTAL_OOB_Y,
    OOB_LINE_BOUNDS.x2,
    BOTTOM_HORIZONTAL_OOB_Y
  ),
  centre_line: sampleAlongLine(
    sourceMask,
    CENTER.x,
    TOP_HORIZONTAL_OOB_Y,
    CENTER.x,
    BOTTOM_HORIZONTAL_OOB_Y
  ),
  centre_circle: sampleCircle(sourceMask, CENTER.x, CENTER.y, CENTER_CIRCLE_R),
  three_point_left: sampleQuadratic(
    sourceMask,
    THREE_POINT_LINE_LEFT.startX,
    THREE_POINT_LINE_LEFT.topY,
    THREE_POINT_LINE_LEFT.controlX,
    1042,
    THREE_POINT_LINE_LEFT.startX,
    THREE_POINT_LINE_LEFT.bottomY
  ),
  three_point_right: sampleQuadratic(
    sourceMask,
    THREE_POINT_LINE_RIGHT.startX,
    THREE_POINT_LINE_RIGHT.topY,
    THREE_POINT_LINE_RIGHT.controlX,
    1042,
    THREE_POINT_LINE_RIGHT.startX,
    THREE_POINT_LINE_RIGHT.bottomY
  ),
  lane_left_top: sampleAlongLine(
    sourceMask,
    LANE_LEFT_RECT.x1,
    LANE_LEFT_RECT.y1,
    LANE_LEFT_RECT.x2,
    LANE_LEFT_RECT.y1
  ),
  lane_left_bottom: sampleAlongLine(
    sourceMask,
    LANE_LEFT_RECT.x1,
    LANE_LEFT_RECT.y2,
    LANE_LEFT_RECT.x2,
    LANE_LEFT_RECT.y2
  ),
  lane_left_free_throw: sampleAlongLine(
    sourceMask,
    LANE_LEFT_RECT.x2,
    LANE_LEFT_RECT.y1,
    LANE_LEFT_RECT.x2,
    LANE_LEFT_RECT.y2
  ),
  lane_right_free_throw: sampleAlongLine(
    sourceMask,
    LANE_RIGHT_RECT.x1,
    LANE_RIGHT_RECT.y1,
    LANE_RIGHT_RECT.x1,
    LANE_RIGHT_RECT.y2
  ),
  ft_arc_left: sampleCircle(
    sourceMask,
    (LEFT_HALF_CIRCLE.x1 + LEFT_HALF_CIRCLE.x2) / 2,
    (LEFT_HALF_CIRCLE.y1 + LEFT_HALF_CIRCLE.y2) / 2,
    (LEFT_HALF_CIRCLE.x2 - LEFT_HALF_CIRCLE.x1) / 2
  ),
  ft_arc_right: sampleCircle(
    sourceMask,
    (RIGHT_HALF_CIRCLE.x1 + RIGHT_HALF_CIRCLE.x2) / 2,
    (RIGHT_HALF_CIRCLE.y1 + RIGHT_HALF_CIRCLE.y2) / 2,
    (RIGHT_HALF_CIRCLE.x2 - RIGHT_HALF_CIRCLE.x1) / 2
  ),
};

const rims = {
  away: rimCentroidNear(SOURCE, RIM_LEFT.x, RIM_LEFT.y),
  home: rimCentroidNear(SOURCE, RIM_RIGHT.x, RIM_RIGHT.y),
};

const windows = [
  featureWindowStats(
    sourceMask,
    geomMask,
    CENTER.x - 6,
    TOP_HORIZONTAL_OOB_Y,
    CENTER.x + 6,
    BOTTOM_HORIZONTAL_OOB_Y,
    'centre_line_band'
  ),
  featureWindowStats(
    sourceMask,
    geomMask,
    LANE_LEFT_RECT.x1 - 10,
    LANE_LEFT_RECT.y1 - 10,
    LANE_LEFT_RECT.x2 + 10,
    LANE_LEFT_RECT.y2 + 10,
    'lane_left'
  ),
  featureWindowStats(
    sourceMask,
    geomMask,
    LANE_RIGHT_RECT.x1 - 10,
    LANE_RIGHT_RECT.y1 - 10,
    LANE_RIGHT_RECT.x2 + 10,
    LANE_RIGHT_RECT.y2 + 10,
    'lane_right'
  ),
  featureWindowStats(
    sourceMask,
    geomMask,
    RIM_LEFT.x - 60,
    RIM_LEFT.y - 60,
    RIM_LEFT.x + 60,
    RIM_LEFT.y + 60,
    'away_rim'
  ),
  featureWindowStats(
    sourceMask,
    geomMask,
    RIM_RIGHT.x - 60,
    RIM_RIGHT.y - 60,
    RIM_RIGHT.x + 60,
    RIM_RIGHT.y + 60,
    'home_rim'
  ),
];

const report = {
  source: 'FrontEnd/static/images/teams/morristown/morristown_court.jpg',
  geometry_source: 'scripts/generate_non_a1_courts.mjs constants',
  canvas: CANVAS,
  stroke_width: STROKE,
  runtime_anchors: { RIM_LEFT, RIM_RIGHT, CENTER },
  mask_agreement: { exact, tol1, tol2, tol2rev },
  geometry_path_hit_rate_on_source_mask: features,
  rim_centroid_offset_px: rims,
  feature_windows: windows,
  artifacts: {
    geometry_mask: geomMaskPath,
    source_mask: sourceMaskPath,
    overlay: overlayPath,
  },
  verdict_notes: [
    'exact IoU is the hard bar for marking pixels.',
    'path hit-rate samples the measured polyline/arc on the extracted Morristown mask (1.0 = every sample lands on a source marking pixel).',
    'rim offsets are centroid deltas of reddish pixels near runtime anchors; abs > 2px fails the §2 placement bar.',
  ],
};

const reportPath = path.join(OUTDIR, 'step0_report.json');
writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`);

function pct(n) {
  return `${(n * 100).toFixed(1)}%`;
}

console.log('\n=== Phase 3b Step 0 — Morristown reproduction ===\n');
console.log(`Source: ${SOURCE}`);
console.log(`Geometry: generate_non_a1_courts.mjs (stroke ${STROKE}px)`);
console.log('');
console.log('Mask agreement (source markings vs rendered geometry):');
console.log(
  `  exact     recall=${pct(exact.recall)} precision=${pct(exact.precision)} IoU=${pct(exact.iou)}`
);
console.log(
  `  ±±1px   source⊂geom recall=${pct(tol1.recall)}`
);
console.log(
  `  ±±2px   source⊂geom recall=${pct(tol2.recall)}  geom⊂source recall=${pct(tol2rev.recall)}`
);
console.log('');
console.log('Path hit-rate on Morristown extracted mask (geometry coordinates):');
for (const [k, v] of Object.entries(features)) {
  const flag = v.rate >= 0.9 ? 'OK' : v.rate >= 0.5 ? 'WEAK' : 'FAIL';
  console.log(`  ${flag.padEnd(4)} ${k.padEnd(24)} ${pct(v.rate)} (${v.hits}/${v.samples})`);
}
console.log('');
console.log('Rim centroid offset vs runtime anchors (px):');
for (const [k, v] of Object.entries(rims)) {
  if (!v.found) console.log(`  FAIL ${k}: no rim-coloured pixels in search window`);
  else {
    const flag = v.abs <= 2 ? 'OK' : 'FAIL';
    console.log(`  ${flag} ${k}: dx=${v.dx} dy=${v.dy} |d|=${v.abs} (n=${v.n})`);
  }
}
console.log('');
console.log('Feature-window IoU (exact):');
for (const w of windows) {
  console.log(
    `  ${w.label.padEnd(18)} IoU=${w.iou == null ? 'n/a' : pct(w.iou)} recall=${w.recall == null ? 'n/a' : pct(w.recall)}`
  );
}

const rimFail = Object.values(rims).some((v) => !v.found || v.abs > 2);
const pathFail = Object.values(features).some((v) => v.rate < 0.9);
const maskFail = exact.iou < 0.85 || tol2.recall < 0.95;

console.log('');
console.log('Artifacts:');
console.log(`  ${geomMaskPath}`);
console.log(`  ${sourceMaskPath}`);
console.log(`  ${overlayPath}`);
console.log(`  ${reportPath}`);
console.log('');
if (rimFail || pathFail || maskFail) {
  console.log('VERDICT: FAIL — measured geometry does not reproduce Morristown markings at pixel agreement.');
  console.log('Stop here. Do not build the parametric generator until geometry is corrected.');
  process.exitCode = 1;
} else {
  console.log('VERDICT: PASS — markings agree; parametric layer may proceed.');
}
