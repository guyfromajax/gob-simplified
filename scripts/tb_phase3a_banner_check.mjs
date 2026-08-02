/**
 * Phase 3a — Chevron banner acceptance (fit + contrast across 128 + custom).
 *
 * Usage: node scripts/tb_phase3a_banner_check.mjs
 *
 * Criterion 4:
 *  (1) wordmark solid-ink contrast ≥ 4.58:1 (best-of-two guarantee)
 *  (2) mascot composited contrast ≥ 4.5:1 (or explicitly exempt in §6.2)
 */
import assert from 'assert';
import fs from 'fs';
import http from 'http';
import path from 'path';
import { fileURLToPath } from 'url';
import { execFileSync } from 'child_process';
import { chromium } from '@playwright/test';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(__dirname, '..');
const STATIC = path.join(ROOT, 'FrontEnd/static');
const TEAMS = JSON.parse(
  fs.readFileSync(path.join(__dirname, 'fixtures/tb_phase3a_teams.json'), 'utf8')
);

const CUSTOM = {
  name: 'South Lancaster Technical',
  abbreviation: 'SLT',
  mascot: 'Wolfpack',
  primary: '#f4f0e6',
  secondary: '#5c5c5c',
};

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.otf': 'font/otf',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
  '.json': 'application/json',
};

function contentType(filePath) {
  return MIME[path.extname(filePath).toLowerCase()] || 'application/octet-stream';
}

function startServer() {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      const urlPath = decodeURIComponent((req.url || '/').split('?')[0]);
      const rel = urlPath === '/' ? '/_banner_check.html' : urlPath;
      const filePath = path.join(STATIC, rel.replace(/^\//, ''));
      if (!filePath.startsWith(STATIC) || !fs.existsSync(filePath)) {
        res.writeHead(404);
        res.end('missing');
        return;
      }
      res.writeHead(200, { 'Content-Type': contentType(filePath) });
      fs.createReadStream(filePath).pipe(res);
    });
    server.listen(0, '127.0.0.1', () => {
      const { port } = server.address();
      resolve({ server, base: `http://127.0.0.1:${port}` });
    });
  });
}

const harnessHtml = `<!DOCTYPE html>
<html><head>
<link rel="stylesheet" href="/css/fonts.css">
<script src="/js/shared/teamGeneratedArt.js"></script>
</head><body></body></html>`;

fs.writeFileSync(path.join(STATIC, '_banner_check.html'), harnessHtml);

const genSrc = fs.readFileSync(path.join(STATIC, 'js/shared/teamGeneratedArt.js'), 'utf8');
assert.ok(!/linearGradient/.test(genSrc), 'generator still contains linearGradient');
assert.ok(!/LUM_INK_THRESHOLD/.test(genSrc), 'luminance threshold still present');
assert.ok(genSrc.includes('inkCandidates') || genSrc.includes('best-of-two') || genSrc.includes('Best-of-two'), 'missing best-of-two ink');
assert.ok(genSrc.includes('compositedContrast') || genSrc.includes('compositeOver'), 'missing composited contrast helpers');

const generalPrimary = path.join(STATIC, 'images/teams/general/general_banner_primary.jpg');
assert.ok(fs.existsSync(generalPrimary), 'missing general_banner_primary.jpg');

const { server, base } = await startServer();
const browser = await chromium.launch();
const page = await browser.newPage();
await page.goto(base + '/', { waitUntil: 'networkidle' });

const report = await page.evaluate(async ({ teams, custom }) => {
  await window.TeamGeneratedArt.ensureBannerFonts();
  const WORD_FLOOR = 4.58;
  const MASCOT_FLOOR = 4.5;
  const subjects = teams.concat([custom]);
  const overflows = [];
  const fails = [];
  let minWord = Infinity;
  let minMascot = Infinity;
  let minWordRow = null;
  let minMascotRow = null;
  let maxMascotAlpha = 0;
  const dims = { card: null, primary: null };

  for (const team of subjects) {
    const card = window.TeamGeneratedArt.analyzeBanner(team, 'card');
    const primarySize = window.TeamGeneratedArt.analyzeBanner(team, 'primary');
    if (!dims.card) {
      dims.card = { w: card.width, h: card.height };
      dims.primary = { w: primarySize.width, h: primarySize.height };
    }
    if (card.overflows) {
      overflows.push({ name: team.name, size: card.wordSize, floor: card.wordFloor });
    }

    const wordRatio = card.contrastPrimary;
    if (wordRatio < minWord) {
      minWord = wordRatio;
      minWordRow = {
        name: team.name,
        primary: card.primary,
        ink: card.inkPrimary,
        ratio: wordRatio,
        darkRatio: card.primaryCandidates.darkRatio,
        lightRatio: card.primaryCandidates.lightRatio,
      };
    }

    const mascotRatio = card.mascotContrast;
    if (mascotRatio != null && mascotRatio < minMascot) {
      minMascot = mascotRatio;
      minMascotRow = {
        name: team.name,
        primary: card.primary,
        ink: card.inkPrimary,
        alpha: card.mascotAlpha,
        composite: card.mascotComposite,
        ratio: mascotRatio,
      };
    }
    if (card.mascotAlpha > maxMascotAlpha) maxMascotAlpha = card.mascotAlpha;

    const wordFail = wordRatio < WORD_FLOOR;
    const mascotFail = mascotRatio != null && mascotRatio < MASCOT_FLOOR;
    if (wordFail || mascotFail) {
      fails.push({
        name: team.name,
        primary: card.primary,
        secondary: card.secondary,
        ink: card.inkPrimary,
        wordRatio: Number(wordRatio.toFixed(3)),
        darkCandidate: Number(card.primaryCandidates.darkRatio.toFixed(3)),
        lightCandidate: Number(card.primaryCandidates.lightRatio.toFixed(3)),
        mascotRatio: mascotRatio == null ? null : Number(mascotRatio.toFixed(3)),
        mascotAlpha: card.mascotAlpha,
        wordFail,
        mascotFail,
      });
    }
  }

  function probe(url) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve({ w: img.naturalWidth, h: img.naturalHeight });
      img.onerror = reject;
      img.src = url;
    });
  }
  const cardImg = await probe(window.TeamGeneratedArt.bannerCardDataUrl(teams[0]));
  const primaryImg = await probe(window.TeamGeneratedArt.bannerPrimaryDataUrl(teams[0]));

  return {
    count: subjects.length,
    dims,
    cardImg,
    primaryImg,
    overflows,
    fails,
    minWord,
    minMascot: Number.isFinite(minMascot) ? minMascot : null,
    minWordRow,
    minMascotRow,
    maxMascotAlpha,
    sample: window.TeamGeneratedArt.analyzeBanner(
      teams.find((t) => t.name === 'IDA') || teams[0],
      'card'
    ),
    coral: window.TeamGeneratedArt.analyzeBanner(
      { name: 'Coral', abbreviation: 'COR', mascot: 'Test', primary: '#ff6f61', secondary: '#111111' },
      'card'
    ),
  };
}, { teams: TEAMS, custom: CUSTOM });

await browser.close();
server.close();
fs.unlinkSync(path.join(STATIC, '_banner_check.html'));

assert.strictEqual(report.dims.card.w, 400);
assert.strictEqual(report.dims.card.h, 141);
assert.strictEqual(report.dims.primary.w, 1920);
assert.strictEqual(report.dims.primary.h, 679);
assert.strictEqual(report.cardImg.w, 400);
assert.strictEqual(report.cardImg.h, 141);
assert.strictEqual(report.primaryImg.w, 1920);
assert.strictEqual(report.primaryImg.h, 679);
assert.strictEqual(report.count, 129);
assert.deepStrictEqual(report.overflows, [], 'wordmark overflow:\n' + JSON.stringify(report.overflows, null, 2));

// Coral sanity: best-of-two must pick dark ink (pure black), not white
assert.strictEqual(report.coral.inkPrimary, '#000000', 'coral should pick dark ink');
assert.ok(report.coral.contrastPrimary > 7, 'coral dark-ink contrast should be ~7.7');
console.log(
  'coral sanity:',
  report.coral.inkPrimary,
  'word',
  report.coral.contrastPrimary.toFixed(3),
  'dark/light',
  report.coral.primaryCandidates.darkRatio.toFixed(3) + '/' + report.coral.primaryCandidates.lightRatio.toFixed(3)
);

console.log('programs checked:', report.count);
console.log('card / primary dims:', report.cardImg, report.primaryImg);
console.log(
  'min wordmark contrast:',
  report.minWord.toFixed(3) + ':1',
  '—',
  report.minWordRow.name,
  report.minWordRow.primary,
  'ink',
  report.minWordRow.ink,
  `(dark ${report.minWordRow.darkRatio.toFixed(3)} / light ${report.minWordRow.lightRatio.toFixed(3)})`
);
console.log(
  'min mascot composited contrast:',
  report.minMascot == null ? 'n/a' : report.minMascot.toFixed(3) + ':1',
  report.minMascotRow
    ? `— ${report.minMascotRow.name} α=${report.minMascotRow.alpha} composite=${report.minMascotRow.composite}`
    : ''
);
console.log('max mascot opacity used:', report.maxMascotAlpha);
console.log(
  'IDA ink:',
  report.sample.inkPrimary,
  'word',
  report.sample.contrastPrimary.toFixed(3),
  'mascot',
  report.sample.mascotContrast == null ? 'n/a' : report.sample.mascotContrast.toFixed(3)
);
console.log('under floor:', report.fails.length);
if (report.fails.length) {
  for (const row of report.fails) {
    console.log(
      `  FAIL ${row.name} primary=${row.primary} ink=${row.ink}` +
        ` word=${row.wordRatio} (dark ${row.darkCandidate} / light ${row.lightCandidate})` +
        ` mascot=${row.mascotRatio} α=${row.mascotAlpha}` +
        (row.wordFail ? ' [word]' : '') +
        (row.mascotFail ? ' [mascot]' : '')
    );
  }
}

try {
  const out = execFileSync(
    'sips',
    ['-g', 'pixelWidth', '-g', 'pixelHeight', generalPrimary],
    { encoding: 'utf8' }
  );
  assert.ok(/pixelWidth:\s*1920/.test(out), out);
  assert.ok(/pixelHeight:\s*679/.test(out), out);
  console.log('general_banner_primary.jpg: 1920×679');
} catch (e) {
  console.warn('sips check skipped', e.message);
}

const wordOk = report.minWord >= 4.58;
const mascotOk = report.minMascot == null || report.minMascot >= 4.5;
console.log('--- summary ---');
if (wordOk && mascotOk && report.fails.length === 0) {
  console.log('passed criterion 4');
} else {
  console.log(
    `criterion 4 incomplete — wordmark min ${report.minWord.toFixed(3)} (need ≥4.58);` +
      ` mascot min ${report.minMascot == null ? 'n/a' : report.minMascot.toFixed(3)} (need ≥4.5)`
  );
  process.exitCode = 1;
}
