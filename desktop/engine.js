'use strict';

const fs = require('fs');
const net = require('net');
const path = require('path');
const { spawn } = require('child_process');

const DEFAULT_PORT = 8765;
const READY_TIMEOUT_MS = 120000;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function findRepoRoot(startDir) {
  let dir = path.resolve(startDir);
  for (let i = 0; i < 12; i += 1) {
    if (fs.existsSync(path.join(dir, 'BackEnd', 'loopback.py'))) return dir;
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  return null;
}

function portIsFree(port) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.unref();
    server.once('error', () => resolve(false));
    server.once('listening', () => {
      server.close(() => resolve(true));
    });
    server.listen(port, '127.0.0.1');
  });
}

function resolvePython(repoRoot) {
  if (process.env.GOB_PYTHON && fs.existsSync(process.env.GOB_PYTHON)) {
    return process.env.GOB_PYTHON;
  }
  const venv = path.join(repoRoot, '.venv', 'bin', 'python');
  if (fs.existsSync(venv)) return venv;
  return null;
}

function resolveBinary(repoRoot) {
  const candidates = [
    path.join(repoRoot, 'dist', 'loopback', 'gob-loopback'),
    path.join(repoRoot, 'dist', 'loopback', 'gob-loopback.dist', 'gob-loopback'),
  ];
  return candidates.find((p) => fs.existsSync(p)) || null;
}

function assertStablePort(requested) {
  if (requested == null || requested === '') return DEFAULT_PORT;
  const port = Number(requested);
  if (!Number.isInteger(port) || port <= 0) {
    throw new Error(`Invalid GOB_LOOPBACK_PORT ${requested}`);
  }
  return port;
}

async function waitForReady({ readyPath, port, timeoutMs, child }) {
  const deadline = Date.now() + (timeoutMs || READY_TIMEOUT_MS);
  let lastErr = '';
  while (Date.now() < deadline) {
    if (child && child.exitCode != null) {
      throw new Error(`Engine exited before ready (code ${child.exitCode}). ${lastErr}`);
    }
    try {
      if (fs.existsSync(readyPath)) {
        const body = JSON.parse(fs.readFileSync(readyPath, 'utf8'));
        if (body && body.ready && Number(body.port) === Number(port)) {
          const res = await fetch(`http://127.0.0.1:${port}/health`);
          const health = await res.json();
          if (health && health.ready === true) return { ready: body, health };
          lastErr = `health not ready: ${JSON.stringify(health)}`;
        } else {
          lastErr = `ready file mismatch: ${JSON.stringify(body)}`;
        }
      }
    } catch (err) {
      lastErr = err && err.message ? err.message : String(err);
    }
    await sleep(250);
  }
  throw new Error(`Engine did not become ready on 127.0.0.1:${port} within ${timeoutMs || READY_TIMEOUT_MS}ms. ${lastErr}`);
}

function startEngine({ repoRoot, userData, port, mode, logPath }) {
  const env = { ...process.env };
  env.GOB_LOOPBACK = '1';
  env.GOB_BUILD_PROFILE = 'desktop';
  env.GOB_LOOPBACK_PORT = String(port);
  env.PORT = String(port);
  env.GOB_SQLITE_PATH = path.join(userData, 'local.sqlite');
  env.GOB_LOOPBACK_READY = path.join(userData, 'loopback-ready.json');
  env.GOB_BUNDLE_ROOT = repoRoot;
  const catalog = path.join(repoRoot, 'catalog.sqlite');
  if (fs.existsSync(catalog)) {
    env.GOB_CATALOG_SQLITE = catalog;
  }
  const league = path.join(repoRoot, 'base_league.sqlite');
  if (fs.existsSync(league)) {
    env.GOB_BASE_LEAGUE_SQLITE = league;
  }
  env.PYTHONUNBUFFERED = '1';
  const python = resolvePython(repoRoot);
  if (mode !== 'binary' && !python) {
    throw new Error('Source mode needs a virtualenv at .venv (see desktop/README.md).');
  }

  try {
    fs.unlinkSync(env.GOB_LOOPBACK_READY);
  } catch (_) { /* first launch */ }

  let cmd;
  let args;
  if (mode === 'binary') {
    const binary = resolveBinary(repoRoot);
    if (!binary) {
      throw new Error('Binary mode: no Nuitka build at dist/loopback/. Run scripts/compile_loopback.sh, or use source mode.');
    }
    cmd = binary;
    args = ['--port', String(port)];
  } else {
    cmd = python;
    args = ['-m', 'BackEnd.loopback', '--port', String(port)];
  }

  const out = fs.createWriteStream(logPath, { flags: 'a' });
  out.write(`\n--- engine start ${new Date().toISOString()} mode=${mode} cmd=${cmd} ---\n`);

  const child = spawn(cmd, args, {
    cwd: repoRoot,
    env,
    detached: true,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  child.stdout.pipe(out);
  child.stderr.pipe(out);
  child.once('exit', () => {
    try { out.end(); } catch (_) { /* ignore */ }
  });

  return {
    child,
    readyPath: env.GOB_LOOPBACK_READY,
    sqlitePath: env.GOB_SQLITE_PATH,
    catalogPath: env.GOB_CATALOG_SQLITE || null,
    logPath,
  };
}

function killProcessGroup(pid) {
  if (!pid) return;
  try {
    process.kill(-pid, 'SIGTERM');
  } catch (_) {
    try { process.kill(pid, 'SIGTERM'); } catch (__) { /* already gone */ }
  }
  setTimeout(() => {
    try { process.kill(-pid, 'SIGKILL'); } catch (_) { /* already gone */ }
    try { process.kill(pid, 'SIGKILL'); } catch (_) { /* already gone */ }
  }, 2000);
}

module.exports = {
  DEFAULT_PORT,
  READY_TIMEOUT_MS,
  findRepoRoot,
  portIsFree,
  resolvePython,
  resolveBinary,
  assertStablePort,
  waitForReady,
  startEngine,
  killProcessGroup,
};
