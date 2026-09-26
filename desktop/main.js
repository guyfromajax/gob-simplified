'use strict';

const fs = require('fs');
const path = require('path');
const { app, BrowserWindow, dialog, shell } = require('electron');
const engine = require('./engine');

const START_PAGE = '/mode-select.html';

app.setName('GOB');
if (process.env.GOB_USER_DATA) {
  app.setPath('userData', process.env.GOB_USER_DATA);
}

let mainWindow = null;
let engineHandle = null;
let quitting = false;
let engineAlive = false;

function desktopDir() {
  return __dirname;
}

function repoRoot() {
  return engine.findRepoRoot(desktopDir());
}

function isLoopbackUrl(url) {
  try {
    const parsed = new URL(url);
    if (parsed.protocol === 'file:') return true;
    if (parsed.hostname !== '127.0.0.1' && parsed.hostname !== 'localhost') return false;
    const port = engine.assertStablePort(process.env.GOB_LOOPBACK_PORT || engine.DEFAULT_PORT);
    return Number(parsed.port || 80) === port;
  } catch (_) {
    return false;
  }
}

function attachNavigationGuards(win) {
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (isLoopbackUrl(url)) return { action: 'allow' };
    shell.openExternal(url);
    return { action: 'deny' };
  });
  win.webContents.on('will-navigate', (event, url) => {
    if (isLoopbackUrl(url)) return;
    event.preventDefault();
    shell.openExternal(url);
  });
}

function showError(message) {
  if (!mainWindow || mainWindow.isDestroyed()) return;
  const html = path.join(desktopDir(), 'error.html');
  const qs = new URLSearchParams({ message: String(message || 'The engine stopped.') }).toString();
  mainWindow.loadFile(html, { query: { message: String(message || 'The engine stopped.') } }).catch(() => {
    dialog.showErrorBox('GOB', message);
  });
  void qs;
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    title: 'GOB',
    show: true,
    backgroundColor: '#0b1020',
    webPreferences: {
      preload: path.join(desktopDir(), 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  attachNavigationGuards(win);
  win.on('closed', () => {
    if (mainWindow === win) mainWindow = null;
  });
  return win;
}

async function boot() {
  const root = repoRoot();
  if (!root) {
    dialog.showErrorBox(
      'GOB',
      'Could not find the GOB checkout (BackEnd/loopback.py). Run this app from the repo, or from desktop/ after npm start.',
    );
    app.quit();
    return;
  }

  const port = engine.assertStablePort(process.env.GOB_LOOPBACK_PORT || engine.DEFAULT_PORT);
  process.env.GOB_LOOPBACK_PORT = String(port);
  process.env.GOB_BUILD_PROFILE = 'desktop';

  const free = await engine.portIsFree(port);
  if (!free) {
    dialog.showErrorBox(
      'GOB',
      `Port ${port} is already in use on this Mac.\n\nGOB keeps this port stable so your save and settings survive relaunch. Quit the other app using ${port} (often another GOB window or a leftover engine), then open GOB again.\n\nDo not change the port.`,
    );
    app.quit();
    return;
  }

  process.env.GOB_BUILD_ID = engine.resolveBuildId(root);
  const userData = app.getPath('userData');
  fs.mkdirSync(userData, { recursive: true });
  const logPath = path.join(userData, 'engine.log');
  const mode = (process.env.GOB_ENGINE_MODE || 'source').toLowerCase() === 'binary' ? 'binary' : 'source';

  mainWindow = createWindow();
  await mainWindow.loadFile(path.join(desktopDir(), 'splash.html'));

  try {
    engineHandle = engine.startEngine({ repoRoot: root, userData, port, mode, logPath });
    engineAlive = true;
    engineHandle.child.on('exit', (code, signal) => {
      engineAlive = false;
      if (!quitting) {
        showError(`The engine stopped unexpectedly (code ${code}, signal ${signal || 'none'}). See ${logPath}.`);
      }
    });
    await engine.waitForReady({
      readyPath: engineHandle.readyPath,
      port,
      child: engineHandle.child,
    });
  } catch (err) {
    showError(err.message);
    return;
  }

  if (!mainWindow || mainWindow.isDestroyed()) return;
  await mainWindow.loadURL(`http://127.0.0.1:${port}${START_PAGE}`);
}

function stopEngine() {
  if (!engineHandle || !engineHandle.child) return;
  engine.killProcessGroup(engineHandle.child.pid);
  engineHandle = null;
}

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.show();
      mainWindow.focus();
    }
  });

  app.whenReady().then(boot);

  app.on('before-quit', () => {
    quitting = true;
    stopEngine();
  });

  app.on('window-all-closed', () => {
    quitting = true;
    stopEngine();
    app.quit();
  });

  app.on('activate', () => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.show();
    } else if (app.isReady() && engineAlive) {
      mainWindow = createWindow();
      const port = engine.assertStablePort(process.env.GOB_LOOPBACK_PORT || engine.DEFAULT_PORT);
      mainWindow.loadURL(`http://127.0.0.1:${port}${START_PAGE}`);
    }
  });
}
