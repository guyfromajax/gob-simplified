#!/usr/bin/env node

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';
import { chromium } from '@playwright/test';

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(SCRIPT_DIR, '..');
const DEFAULT_LOGIN_URL = 'https://gob-test.netlify.app/login.html';
const DEFAULT_STATE_PATH = path.join(os.homedir(), '.config', 'gob', 'playwright-storage-state.json');
const LOGIN_TIMEOUT_MS = 10 * 60 * 1000;

const HELP = `GOB screenshot-session setup

Opens a headed Chromium window so you can log in manually, then saves private
Playwright browser state outside the repository.

Usage:
  node scripts/save_screenshot_session.mjs [options]

Options:
  --url URL       Localhost or staging/test login URL
                  (default: https://gob-test.netlify.app/login.html)
  --state PATH    Destination outside the repository
                  (default: ~/.config/gob/playwright-storage-state.json)
  --help          Show this help without launching Chromium

The helper does not accept usernames, passwords, tokens, cookies, or database
credentials. Complete login only inside the opened browser window. It waits up to
10 minutes for the application's authenticated browser state.
`;

class SessionSetupError extends Error {}

function takeValue(argv, index, flag) {
  const value = argv[index + 1];
  if (value == null || value.startsWith('--')) throw new SessionSetupError(`${flag} requires a value.`);
  return value;
}

function isAllowedHost(hostname) {
  const host = hostname.toLowerCase();
  if (host === 'localhost' || host === '127.0.0.1' || host === 'staging.geekedoutbasketball.com') return true;
  return (host.endsWith('.netlify.app') || host.endsWith('.railway.app'))
    && (host.includes('staging') || host.includes('test'));
}

export function parseSessionArguments(argv) {
  let urlRaw = DEFAULT_LOGIN_URL;
  let stateRaw = DEFAULT_STATE_PATH;
  let help = false;
  const seen = new Set();

  for (let index = 0; index < argv.length; index += 1) {
    const flag = argv[index];
    if (!flag.startsWith('--')) throw new SessionSetupError(`Unexpected positional argument: ${flag}`);
    if (seen.has(flag)) throw new SessionSetupError(`${flag} may only be supplied once.`);
    seen.add(flag);
    if (flag === '--url') {
      urlRaw = takeValue(argv, index, flag);
      index += 1;
    } else if (flag === '--state') {
      stateRaw = takeValue(argv, index, flag);
      index += 1;
    } else if (flag === '--help') {
      help = true;
    } else {
      throw new SessionSetupError(`Unknown option: ${flag}`);
    }
  }

  if (help) return { help: true };

  let loginUrl;
  try {
    loginUrl = new URL(urlRaw);
  } catch {
    throw new SessionSetupError('--url must be an absolute http:// or https:// URL.');
  }
  if (!['http:', 'https:'].includes(loginUrl.protocol) || loginUrl.username || loginUrl.password) {
    throw new SessionSetupError('--url must be credential-free and use http:// or https://.');
  }
  if (!isAllowedHost(loginUrl.hostname)) {
    throw new SessionSetupError('--url is restricted to localhost and staging/test hosts; production login is not allowed.');
  }

  const statePath = path.resolve(stateRaw.replace(/^~(?=$|[\\/])/, os.homedir()));
  const relativeToRepo = path.relative(REPO_ROOT, statePath);
  if (relativeToRepo === '' || (!relativeToRepo.startsWith('..') && !path.isAbsolute(relativeToRepo))) {
    throw new SessionSetupError('--state must live outside the repository.');
  }

  if (fs.existsSync(statePath) && !fs.statSync(statePath).isFile()) {
    throw new SessionSetupError(`--state is not a regular file: ${statePath}`);
  }
  return { help: false, loginUrl: loginUrl.href, statePath };
}

async function writePrivateStorageState(context, statePath) {
  const stateDir = path.dirname(statePath);
  const stateDirExisted = fs.existsSync(stateDir);
  fs.mkdirSync(stateDir, { recursive: true, mode: 0o700 });
  if (!stateDirExisted && process.platform !== 'win32') fs.chmodSync(stateDir, 0o700);

  const temporaryPath = `${statePath}.tmp-${process.pid}-${Date.now()}`;
  try {
    await context.storageState({ path: temporaryPath });
    if (process.platform !== 'win32') fs.chmodSync(temporaryPath, 0o600);
    fs.renameSync(temporaryPath, statePath);
    if (process.platform !== 'win32') fs.chmodSync(statePath, 0o600);
  } finally {
    if (fs.existsSync(temporaryPath)) fs.unlinkSync(temporaryPath);
  }
}

export async function saveScreenshotSession(options) {
  let browser;
  try {
    browser = await chromium.launch({ headless: false });
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.goto(options.loginUrl, { waitUntil: 'domcontentloaded', timeout: 30_000 });

    process.stdout.write(
      'Complete login in the Chromium window. Waiting for authenticated browser state...\n',
    );
    await page.waitForFunction(
      () => Boolean(localStorage.getItem('auth_token') && localStorage.getItem('auth_user')),
      undefined,
      { timeout: LOGIN_TIMEOUT_MS },
    );

    await writePrivateStorageState(context, options.statePath);
    return options.statePath;
  } finally {
    if (browser) await browser.close();
  }
}

export async function main(argv = process.argv.slice(2)) {
  let options;
  try {
    options = parseSessionArguments(argv);
  } catch (error) {
    if (error instanceof SessionSetupError) {
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
    const statePath = await saveScreenshotSession(options);
    process.stdout.write(`Session saved privately to: ${statePath}\n`);
    return 0;
  } catch (error) {
    console.error(
      `Session setup failed: ${error.message}\n`
      + 'No credentials were saved by this helper. Run it again to retry.',
    );
    return 1;
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exitCode = await main();
}
