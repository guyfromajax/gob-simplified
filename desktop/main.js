'use strict';

const fs = require('fs');
const path = require('path');
const { app, BrowserWindow, dialog, shell, Menu } = require('electron');
const engine = require('./engine');

const START_PAGE = '/mode-select.html';
const APP_NAME = 'Geeked-Out Basketball';

app.setName(APP_NAME);
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
    dialog.showErrorBox(APP_NAME, String(message || 'The game engine stopped. Quit the app and open it again.'));
  });
  void qs;
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    title: APP_NAME,
    show: true,
    backgroundColor: '#0b0d14',
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
      APP_NAME,
      'Geeked-Out Basketball could not find its game files (BackEnd/loopback.py). Reinstall the app, or if you are running from source, start it from the GOB folder (desktop/ after npm start).',
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
      APP_NAME,
      `Another program is already using port ${port} on this computer.\n\nThat is usually another Geeked-Out Basketball window or a leftover engine. Quit that copy, then open the game again.\n\nDo not change the port — your save and settings stay on this one.`,
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

function buildAppMenu() {
  const isMac = process.platform === 'darwin';
  const viewItems = [
    { role: 'reload' },
    { role: 'togglefullscreen' },
  ];
  if (!app.isPackaged) {
    viewItems.push({ type: 'separator' }, { role: 'toggleDevTools' });
  }
  const template = [];
  if (isMac) {
    template.push({
      label: APP_NAME,
      submenu: [
        { role: 'about' },
        { type: 'separator' },
        { role: 'hide' },
        { role: 'hideOthers' },
        { role: 'unhide' },
        { type: 'separator' },
        { role: 'quit' },
      ],
    });
  } else {
    template.push({
      label: 'File',
      submenu: [{ role: 'quit' }],
    });
  }
  template.push(
    {
      label: 'Edit',
      submenu: [
        { role: 'undo' },
        { role: 'redo' },
        { type: 'separator' },
        { role: 'cut' },
        { role: 'copy' },
        { role: 'paste' },
        { role: 'selectAll' },
      ],
    },
    { label: 'View', submenu: viewItems },
  );
  return Menu.buildFromTemplate(template);
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

  app.whenReady().then(() => {
    Menu.setApplicationMenu(buildAppMenu());
    return boot();
  });

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
