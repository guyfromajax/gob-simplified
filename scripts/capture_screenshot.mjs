#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';
import { chromium } from '@playwright/test';
import { formatRecipeList, getRecipe, recipeNames } from './screenshot_recipes.mjs';

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(SCRIPT_DIR, '..');
const DEFAULT_OUTPUT_DIR = path.join(REPO_ROOT, 'tmp', 'screenshots');
const DEFAULT_VIEWPORT = { width: 1920, height: 1080 };
const DEFAULT_DELAY_MS = 1000;
const NAVIGATION_TIMEOUT_MS = 30_000;
const READINESS_TIMEOUT_MS = 30_000;
const MIN_VIEWPORT = 320;
const MAX_VIEWPORT = 7680;

const HELP = `GOB native browser screenshot tool

Usage:
  node scripts/capture_screenshot.mjs --url URL [options]

Required:
  --url URL                Absolute http:// or https:// URL (localhost allowed)

Options:
  --name LABEL             Output label (default: final URL path component)
  --recipe NAME            Apply a named screen readiness/capture recipe
  --viewport WIDTHxHEIGHT  Viewport in CSS pixels (default: 1920x1080)
  --full-page              Capture the entire document
  --selector CSS           Capture exactly one visible matching element
  --output-dir PATH        Output directory (default: tmp/screenshots)
  --wait-for CSS           Wait for a matching element to become visible
  --delay-ms N             Settling delay, 0-30000 (default: 1000)
  --state PATH             Existing Playwright storage-state JSON file
  --headed                 Show Chromium while capturing
  --help                   Show this help without launching Chromium

Constraints:
  --full-page and --selector cannot be combined.
  Viewport dimensions must each be between 320 and 7680.
  URLs containing embedded usernames or passwords are rejected.
  Output is PNG and existing files are never overwritten.

Examples:
  node scripts/capture_screenshot.mjs \\
    --url https://staging.geekedoutbasketball.com/mode-select.html \\
    --name mode-select

  node scripts/capture_screenshot.mjs \\
    --url http://localhost:8000/training.html \\
    --recipe training --headed

Recipes:
${formatRecipeList()}
`;

class CliError extends Error {
  constructor(message) {
    super(message);
    this.name = 'CliError';
  }
}

function takeValue(argv, index, flag) {
  const value = argv[index + 1];
  if (value == null || value.startsWith('--')) {
    throw new CliError(`${flag} requires a value.`);
  }
  return value;
}

export function parseArguments(argv) {
  const options = {
    fullPage: false,
    headed: false,
    delayMs: DEFAULT_DELAY_MS,
    viewport: { ...DEFAULT_VIEWPORT },
    outputDir: DEFAULT_OUTPUT_DIR,
  };
  const seen = new Set();
  const valueFlags = new Map([
    ['--url', 'url'],
    ['--name', 'name'],
    ['--recipe', 'recipeName'],
    ['--viewport', 'viewportRaw'],
    ['--selector', 'selector'],
    ['--output-dir', 'outputDirRaw'],
    ['--wait-for', 'waitFor'],
    ['--delay-ms', 'delayRaw'],
    ['--state', 'stateRaw'],
  ]);
  const booleanFlags = new Map([
    ['--full-page', 'fullPage'],
    ['--headed', 'headed'],
    ['--help', 'help'],
  ]);

  for (let index = 0; index < argv.length; index += 1) {
    const flag = argv[index];
    if (!flag.startsWith('--')) {
      throw new CliError(`Unexpected positional argument: ${flag}`);
    }
    if (seen.has(flag)) throw new CliError(`${flag} may only be supplied once.`);
    seen.add(flag);

    if (valueFlags.has(flag)) {
      options[valueFlags.get(flag)] = takeValue(argv, index, flag);
      index += 1;
    } else if (booleanFlags.has(flag)) {
      options[booleanFlags.get(flag)] = true;
    } else {
      throw new CliError(`Unknown option: ${flag}`);
    }
  }

  if (options.help) return options;
  if (!options.url) throw new CliError('--url is required.');
  let parsedUrl;
  try {
    parsedUrl = new URL(options.url);
  } catch {
    throw new CliError('--url must be an absolute http:// or https:// URL.');
  }
  if (!['http:', 'https:'].includes(parsedUrl.protocol)) {
    throw new CliError('--url must use http:// or https://.');
  }
  if (parsedUrl.username || parsedUrl.password) {
    throw new CliError('--url must not contain an embedded username or password.');
  }
  options.url = parsedUrl.href;

  if (options.recipeName) {
    const recipe = getRecipe(options.recipeName);
    if (!recipe) {
      throw new CliError(`Unknown recipe: ${options.recipeName}. Available recipes: ${recipeNames().join(', ')}`);
    }
    if (!recipe.pathPattern.test(parsedUrl.pathname)) {
      throw new CliError(`Recipe ${options.recipeName} does not match URL path ${parsedUrl.pathname}.`);
    }
    options.recipe = recipe;
    if (!seen.has('--name')) options.name = recipe.name;
    if (!seen.has('--viewport')) options.viewport = { ...recipe.viewport };
    if (!seen.has('--wait-for') && recipe.waitFor) options.waitFor = recipe.waitFor;
    if (!seen.has('--selector') && recipe.selector) options.selector = recipe.selector;
    if (!seen.has('--delay-ms') && recipe.delayMs != null) options.delayMs = recipe.delayMs;
    options.waitForHidden = recipe.waitForHidden;
  }

  if (options.fullPage && options.selector) {
    throw new CliError('--full-page cannot be combined with --selector.');
  }

  if (options.viewportRaw != null) {
    const match = /^(\d+)x(\d+)$/i.exec(options.viewportRaw);
    if (!match) throw new CliError('--viewport must use WIDTHxHEIGHT, for example 1920x1080.');
    const width = Number(match[1]);
    const height = Number(match[2]);
    if (width < MIN_VIEWPORT || width > MAX_VIEWPORT || height < MIN_VIEWPORT || height > MAX_VIEWPORT) {
      throw new CliError(`Viewport dimensions must each be between ${MIN_VIEWPORT} and ${MAX_VIEWPORT}.`);
    }
    options.viewport = { width, height };
  }

  if (options.delayRaw != null) {
    if (!/^\d+$/.test(options.delayRaw)) throw new CliError('--delay-ms must be an integer from 0 through 30000.');
    options.delayMs = Number(options.delayRaw);
    if (options.delayMs > 30_000) throw new CliError('--delay-ms must be an integer from 0 through 30000.');
  }

  const pathname = decodeURIComponent(parsedUrl.pathname);
  const lastPart = pathname.split('/').filter(Boolean).at(-1) || 'homepage';
  const defaultName = lastPart.replace(/\.[^.]+$/, '') || 'homepage';
  options.safeName = sanitizeName(options.name ?? defaultName);
  options.outputDir = path.resolve(REPO_ROOT, options.outputDirRaw ?? path.relative(REPO_ROOT, DEFAULT_OUTPUT_DIR));

  if (fs.existsSync(options.outputDir) && !fs.statSync(options.outputDir).isDirectory()) {
    throw new CliError(`--output-dir is not a directory: ${options.outputDir}`);
  }

  if (options.stateRaw != null) {
    options.statePath = path.resolve(process.cwd(), options.stateRaw);
    let stat;
    try {
      stat = fs.statSync(options.statePath);
    } catch {
      throw new CliError(`--state does not exist: ${options.statePath}`);
    }
    if (!stat.isFile()) throw new CliError(`--state is not a regular file: ${options.statePath}`);
    const relativeToRepo = path.relative(REPO_ROOT, options.statePath);
    if (relativeToRepo === '' || (!relativeToRepo.startsWith('..') && !path.isAbsolute(relativeToRepo))) {
      throw new CliError('--state must live outside the repository. Refresh it with scripts/save_screenshot_session.mjs.');
    }
    if (process.platform !== 'win32' && (stat.mode & 0o077) !== 0) {
      throw new CliError('--state must be private (file mode 0600). Run chmod 600 on the file.');
    }
    try {
      JSON.parse(fs.readFileSync(options.statePath, 'utf8'));
    } catch {
      throw new CliError(`--state is not valid JSON: ${options.statePath}`);
    }
  }

  return options;
}

export function sanitizeName(value) {
  const safe = String(value)
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^[-_]+|[-_]+$/g, '');
  if (!safe) throw new CliError('--name must contain at least one ASCII letter or digit.');
  return safe;
}

function utcTimestamp(date = new Date()) {
  return date.toISOString().replace(/[-:]/g, '').replace('T', '-').slice(0, 15);
}

export function chooseOutputPath(outputDir, safeName, date = new Date()) {
  const stem = `${safeName}-${utcTimestamp(date)}`;
  let candidate = path.join(outputDir, `${stem}.png`);
  let suffix = 2;
  while (fs.existsSync(candidate)) {
    candidate = path.join(outputDir, `${stem}-${suffix}.png`);
    suffix += 1;
  }
  return candidate;
}

async function waitForFonts(page, timeoutMs) {
  let timeoutId;
  try {
    await Promise.race([
      page.evaluate(() => (document.fonts ? document.fonts.ready : Promise.resolve())),
      new Promise((_, reject) => {
        timeoutId = setTimeout(
          () => reject(new Error('Timed out waiting for document fonts.')),
          timeoutMs,
        );
      }),
    ]);
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function resolveCaptureLocator(page, selector, timeoutMs = READINESS_TIMEOUT_MS) {
  let locator;
  try {
    locator = page.locator(selector);
    const count = await locator.count();
    if (count !== 1) {
      throw new Error(`--selector must match exactly one element; matched ${count}.`);
    }
    await locator.waitFor({ state: 'visible', timeout: timeoutMs });
  } catch (error) {
    throw new Error(`Capture selector failed (${JSON.stringify(selector)}): ${error.message}`);
  }
  return locator;
}

export async function captureScreenshot(options) {
  fs.mkdirSync(options.outputDir, { recursive: true });
  const outputPath = chooseOutputPath(options.outputDir, options.safeName);
  const readinessTimeoutMs = options.readinessTimeoutMs ?? READINESS_TIMEOUT_MS;
  let browser;

  try {
    browser = await chromium.launch({ headless: !options.headed });
    const context = await browser.newContext({
      viewport: options.viewport,
      deviceScaleFactor: 1,
      ...(options.statePath ? { storageState: options.statePath } : {}),
    });
    const page = await context.newPage();
    page.setDefaultTimeout(readinessTimeoutMs);
    page.setDefaultNavigationTimeout(NAVIGATION_TIMEOUT_MS);

    await page.goto(options.url, { waitUntil: 'domcontentloaded' });
    await waitForFonts(page, readinessTimeoutMs);

    if (options.statePath) {
      const appearsLoggedOut = await page.evaluate(() => {
        const pathLooksLikeLogin = /\/(login)(\.html)?\/?$/i.test(window.location.pathname);
        const hasLoginForm = Boolean(
          document.querySelector('#login-form')
          || document.querySelector('input[type="password"]'),
        );
        return pathLooksLikeLogin || hasLoginForm;
      });
      if (appearsLoggedOut) {
        throw new Error(
          'The saved browser session appears missing or expired. '
          + 'Refresh it with: node scripts/save_screenshot_session.mjs',
        );
      }
    }

    if (options.waitForHidden) {
      try {
        await page.locator(options.waitForHidden).first().waitFor({
          state: 'hidden',
          timeout: readinessTimeoutMs,
        });
      } catch (error) {
        throw new Error(
          `Recipe hidden-state readiness failed (${JSON.stringify(options.waitForHidden)}): ${error.message}`,
        );
      }
    }

    if (options.waitFor) {
      try {
        await page.locator(options.waitFor).first().waitFor({ state: 'visible', timeout: readinessTimeoutMs });
      } catch (error) {
        throw new Error(`Readiness selector failed (${JSON.stringify(options.waitFor)}): ${error.message}`);
      }
    }

    if (options.delayMs) await page.waitForTimeout(options.delayMs);

    if (options.selector) {
      const locator = await resolveCaptureLocator(page, options.selector, readinessTimeoutMs);
      await locator.screenshot({ path: outputPath, type: 'png' });
    } else {
      await page.screenshot({ path: outputPath, type: 'png', fullPage: options.fullPage });
    }

    return outputPath;
  } finally {
    if (browser) await browser.close();
  }
}

export async function main(argv = process.argv.slice(2)) {
  let options;
  try {
    options = parseArguments(argv);
  } catch (error) {
    if (error instanceof CliError) {
      console.error(`Error: ${error.message}\nRun with --help for usage.`);
      return 2;
    }
    throw error;
  }

  if (options.help) {
    process.stdout.write(HELP);
    return 0;
  }

  try {
    const outputPath = await captureScreenshot(options);
    process.stdout.write(`${outputPath}\n`);
    return 0;
  } catch (error) {
    console.error(`Screenshot failed: ${error.message}`);
    return 1;
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exitCode = await main();
}
