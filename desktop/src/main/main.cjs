/**
 * FOXFall desktop - Electron main process.
 * Architecture modeled on Aster Browser:
 *   - single instance lock
 *   - contextIsolation + sandbox + no nodeIntegration
 *   - restricted preload bridge
 *   - managed Python backend child process (hidden console) with JSON IPC
 *   - clean backend shutdown on quit
 */
'use strict';

const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');
const Backend = require('./backend.cjs');

/** @type {BrowserWindow | null} */
let mainWindow = null;
/** @type {Backend | null} */
let backend = null;
/** @type {(line: string) => void} */
let logger = () => {};

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });

  // User data lives outside the installation dir ( survives updates )
  const userData = path.join(app.getPath('appData'), 'FOXFall');
  app.setPath('userData', userData);

  // Diagnostic log file in app data (no sensitive info: paths + messages only)
  try {
    fs.mkdirSync(userData, { recursive: true });
    fs.mkdirSync(path.join(userData, 'logs'), { recursive: true });
    const logFile = path.join(userData, 'logs', `backend-${new Date().toISOString().slice(0, 10)}.log`);
    logger = (line) => {
      try {
        fs.appendFileSync(logFile,
          `${new Date().toISOString()} ${line}\n`);
      } catch (_) { /* logging must never crash the app */ }
    };
  } catch (_) {
    logger = () => {};
  }

  app.whenReady().then(async () => {
    backend = new Backend({
      userDataDir: userData,
      onEvent: (event) => {
        logger(`[event] ${JSON.stringify(event).slice(0, 600)}`);
        if (mainWindow && !mainWindow.isDestroyed()) {
          mainWindow.webContents.send('foxfall:event', event);
        }
      },
      onExit: (code) => {
        logger(`[backend exit] code=${code}`);
        if (mainWindow && !mainWindow.isDestroyed()) {
          mainWindow.webContents.send('foxfall:event', {
            event: 'backend_exit', code,
          });
        }
      },
    });
    try {
      await backend.start();
      logger(`[backend ready] mode=${backend.mode}`);
    } catch (err) {
      logger(`[backend start FAILED] ${err.message}`);
      dialog.showErrorBox(
        'FOXFall backend error',
        `${err.message}\n\nA diagnostic log was saved to:\n${path.join(userData, 'logs')}`);
    }
    createWindow();
  });

  app.on('window-all-closed', () => app.quit());
  app.on('before-quit', () => {
    if (backend) backend.shutdown();
  });
}

function backendDir() {
  // dev: repo root/backend ; packaged: resources/backend
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'backend');
  }
  return path.join(app.getAppPath(), 'backend');
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1180,
    height: 760,
    minWidth: 900,
    minHeight: 600,
    title: 'FOXFall',
    backgroundColor: '#111111',
    show: false,
    icon: resolveIcon(),
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
      spellcheck: false,
    },
  });
  mainWindow.loadFile(path.join(__dirname, '..', 'renderer', 'index.html'));
  mainWindow.once('ready-to-show', () => mainWindow.show());
  mainWindow.on('closed', () => { mainWindow = null; });
}

function resolveIcon() {
  const candidates = [
    path.join(backendDir(), '..', 'assets', 'foxfall.ico'),
    path.join(app.getAppPath(), 'assets', 'foxfall.ico'),
    path.join(process.resourcesPath || '', 'assets', 'foxfall.ico'),
  ];
  for (const c of candidates) {
    try { if (c && fs.existsSync(c)) return c; } catch (_) { /* ignore */ }
  }
  return undefined;
}

/* ------------------------------------------------------------------ */
/* IPC surface: validated, allowlisted commands through the backend.  */
/* ------------------------------------------------------------------ */
const ALLOWED_COMMANDS = new Set([
  'ping',
  'get_app_info',
  'get_settings',
  'set_settings',
  'pick_directory',
  'pick_media_file',
  'tool_probe',
  'library_scan',
  'library_cancel_scan',
  'library_list',
  'library_set_favorite',
  'library_remove',
  'library_count',
  'tool_convert_start',
  'tool_extract_start',
  'tool_thumbnail',
  'tool_cancel',
  'analyze_url',
  'start_download',
  'cancel_download',
  'retry_download',
  'list_queue',
  'list_history',
  'clear_history',
  'remove_history',
  'open_path',
  'reveal_path',
  'run_diagnostics',
  'check_backend_updates',
]);

ipcMain.handle('foxfall:command', async (_event, action, payload) => {
  if (!ALLOWED_COMMANDS.has(action)) {
    return { ok: false, error: 'unknown command' };
  }
  if (typeof payload !== 'object' || payload === null) payload = {};
  try {
    if (action === 'pick_directory') {
      const result = await dialog.showOpenDialog(mainWindow, {
        properties: ['openDirectory', 'createDirectory'],
        title: 'Choose download folder',
        defaultPath: typeof payload.current === 'string' ? payload.current : undefined,
      });
      return { ok: true, path: result.canceled ? null : result.filePaths[0] };
    }
    if (action === 'open_path' || action === 'reveal_path') {
      const p = String(payload.path || '');
      if (!p) return { ok: false, error: 'missing path' };
      const resolved = path.resolve(p);
      if (!fs.existsSync(resolved)) return { ok: false, error: 'path not found' };
      const { shell } = require('electron');
      if (action === 'open_path') {
        await shell.openPath(resolved);
      } else {
        shell.showItemInFolder(resolved);
      }
      return { ok: true };
    }
    if (action === 'pick_media_file') {
      const result = await dialog.showOpenDialog(mainWindow, {
        properties: ['openFile'],
        title: 'Choose a media file',
        filters: [
          { name: 'Media', extensions: ['mp4', 'webm', 'mkv', 'avi', 'mov',
            'm4a', 'mp3', 'wav', 'flac', 'aac', 'ogg'] },
          { name: 'All files', extensions: ['*'] },
        ],
      });
      return { ok: true, path: result.canceled ? null : result.filePaths[0] };
    }
    if (!backend || !backend.ready()) {
      return { ok: false, error: 'backend not running', backendOffline: true };
    }
    try {
      const result = await backend.request(action, payload);
      // backend.request() already unwraps the {ok, result} envelope and
      // rejects on error — normalize to the renderer contract {ok, ...}.
      return { ok: true, result };
    } catch (err) {
      return { ok: false, error: String(err.message || err) };
    }
  } catch (err) {
    return { ok: false, error: String(err.message || err) };
  }
});

ipcMain.handle('foxfall:backend_status', () => ({
  ready: backend ? backend.ready() : false,
  restarting: backend ? backend.restarting : false,
}));
