/**
 * Backend: managed Python child process with newline-delimited JSON IPC.
 * - hidden window on Windows (CREATE_NO_WINDOW)
 * - automatic restart on crash (bounded)
 * - request/response correlation by id
 * - event forwarding to the main process callback
 * - clean shutdown on app quit
 */
'use strict';
const { app, spawn } = (() => {
  // `app` is only available inside the Electron main process; tests load this
  // module under plain Node where electron is unavailable.
  try {
    const electron = require('electron');
    return { app: electron.app || null, spawn: require('child_process').spawn };
  } catch (_) {
    return { app: null, spawn: require('child_process').spawn };
  }
})();
const path = require('path');
const readline = require('readline');
const fs = require('fs');

class Backend {
  /**
   * @param {{onEvent: (event: object) => void, onExit?: (code: number|null) => void}} opts
   */
  constructor(opts) {
    this.onEvent = opts.onEvent || (() => {});
    this.onExit = opts.onExit || (() => {});
    this.userDataDir = opts.userDataDir || '';
    this.proc = null;
    this._ready = false;
    this.restarting = false;
    this.nextId = 1;
    this.pending = new Map(); // id -> {resolve, reject, timer}
    this.restartCount = 0;
    this.maxRestarts = 3;
    this.shuttingDown = false;
    this.rl = null;
  }

  /**
   * Resource layout root.
   *  - packaged: <install>\resources  (real files, outside app.asar)
   *  - dev:      <repo>\desktop       (backend lives in the repo root)
   */
  resourcesRoot() {
    if (app && app.isPackaged) {
      return path.dirname(process.resourcesPath); // .../resources
    }
    return path.resolve(__dirname, '..', '..', '..');
  }

  /**
   * Resolve the backend command.
   *
   * Strategy (in order):
   *  1. Packaged self-contained exe: <resources>/backend/foxfall-backend/
   *     foxfall-backend.exe (PyInstaller onedir; zero external deps).
   *  2. Packaged embedded runtime: <resources>/backend/runtime/python/
   *     python.exe running server.py (legacy layout, also self-contained).
   *  3. Dev: repo .venv python running server.py from the repo.
   * Each candidate is verified with fs.existsSync before use.
   */
  resolveBackend() {
    const res = process.resourcesPath;
    if (res) {
      const standalone = path.join(
        res, 'backend', 'foxfall-backend', 'foxfall-backend.exe');
      if (fs.existsSync(standalone)) {
        return { exe: standalone, args: [], cwd: path.dirname(standalone),
                 mode: 'standalone-exe' };
      }
      const py = path.join(
        res, 'backend', 'runtime', 'python', 'python.exe');
      const script = path.join(res, 'backend', 'server.py');
      if (fs.existsSync(py) && fs.existsSync(script)) {
        return { exe: py, args: [script], cwd: path.dirname(script),
                 mode: 'embedded-runtime' };
      }
    }
    // Env override (CI / tests)
    if (process.env.FOXFall_PYTHON && fs.existsSync(process.env.FOXFall_PYTHON)) {
      const devScript = path.join(this.resourcesRoot(), 'backend', 'server.py');
      if (fs.existsSync(devScript)) {
        return { exe: process.env.FOXFall_PYTHON, args: [devScript],
                 cwd: path.dirname(devScript), mode: 'env-override' };
      }
    }
    // Dev: repo .venv python running server.py from the repo
    const venv = path.join(this.resourcesRoot(), '.venv', 'Scripts', 'python.exe');
    const devScript = path.join(this.resourcesRoot(), 'backend', 'server.py');
    if (fs.existsSync(venv) && fs.existsSync(devScript)) {
      return { exe: venv, args: [devScript], cwd: path.dirname(devScript),
               mode: 'dev-venv' };
    }
    return null;
  }

  pythonExecutable() {
    const r = this.resolveBackend();
    return r ? r.exe : 'python';
  }

  serverScript() {
    const r = this.resolveBackend();
    return r ? (r.args[0] || r.exe) : '';
  }

  async start() {
    this.shuttingDown = false;
    const resolved = this.resolveBackend();
    if (!resolved) {
      const msg = 'FOXFall backend not found in the installation. '
        + 'Expected resources/backend/foxfall-backend/foxfall-backend.exe '
        + 'or resources/backend/server.py with a bundled Python runtime. '
        + 'The installation appears incomplete — reinstall FOXFall.';
      this.onEvent({ event: 'backend_failed', message: msg });
      throw new Error(msg);
    }
    this.mode = resolved.mode;

    const spawnOpts = {
      cwd: resolved.cwd,
      windowsHide: true,
      stdio: ['pipe', 'pipe', 'pipe'],
      // user data (settings/history/downloads/logs) must live outside the
      // install dir; the backend honors this env var in all layouts
      env: {
        ...process.env,
        FOXFall_USER_DATA: this.userDataDir || '',
      },
    };

    this.proc = spawn(resolved.exe, resolved.args, spawnOpts);
    this._ready = false;
    this.lastStderr = '';

    this.proc.on('error', (err) => {
      this._ready = false;
      this.onEvent({ event: 'log', level: 'error', message: `backend spawn failed: ${err.message}` });
      this.scheduleRestart();
    });

    this.proc.on('exit', (code) => {
      this._ready = false;
      if (this.rl) { try { this.rl.close(); } catch (_) {} this.rl = null; }
      for (const [, p] of this.pending) {
        clearTimeout(p.timer);
        p.reject(new Error('backend exited'));
      }
      this.pending.clear();
      this.onExit(code);
      if (!this.shuttingDown) this.scheduleRestart();
    });

    this.proc.stderr.on('data', (chunk) => {
      const text = String(chunk).trim();
      if (text) {
        this.lastStderr = text.slice(0, 800);
        this.onEvent({ event: 'log', level: 'error', message: this.lastStderr });
      }
    });

    this.rl = readline.createInterface({ input: this.proc.stdout });
    this.rl.on('line', (line) => this.handleLine(line));

    try {
      await this.waitForReady(20000);
    } catch (err) {
      // Surface the real cause: stderr tail + spawn diagnostics
      const detail = this.lastStderr
        ? `backend startup failed: ${err.message} | stderr: ${this.lastStderr}`
        : `backend startup failed: ${err.message} (backend: ${resolved.exe})`;
      this.onEvent({ event: 'backend_failed', message: detail });
      throw new Error(detail);
    }
    return true;
  }

  /** True while the backend process is alive and has completed handshake. */
  ready() {
    return !!(this.proc && this.proc.exitCode === null && this._ready);
  }

  waitForReady(timeoutMs) {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => { clearInterval(check); reject(new Error('backend startup timeout')); }, timeoutMs);
      const check = setInterval(() => {
        if (this._ready) { clearTimeout(timer); clearInterval(check); resolve(); }
        else if (!this.proc || this.proc.exitCode !== null) {
          clearTimeout(timer); clearInterval(check);
          reject(new Error('backend died during startup'));
        }
      }, 100);
      if (check.unref) check.unref();
    });
  }

  handleLine(line) {
    let msg;
    try { msg = JSON.parse(line); } catch (_) { return; } // ignore malformed
    if (!msg || typeof msg !== 'object') return;
    if (typeof msg.id === 'number' && this.pending.has(msg.id)) {
      const pending = this.pending.get(msg.id);
      clearTimeout(pending.timer);
      this.pending.delete(msg.id);
      if (msg.ok) pending.resolve(msg.result || {});
      else pending.reject(new Error(String(msg.error || 'backend error')));
      return;
    }
    if (typeof msg.event === 'string') {
      if (msg.event === 'ready') this._ready = true;
      this.onEvent(msg);
    }
  }

  request(action, payload = {}) {
    return new Promise((resolve, reject) => {
      if (!this.proc || this.proc.exitCode !== null) {
        reject(new Error('backend not running'));
        return;
      }
      const id = this.nextId++;
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`backend timeout: ${action}`));
      }, 120000);
      this.pending.set(id, { resolve, reject, timer });
      const line = JSON.stringify({ id, action, payload });
      try {
        this.proc.stdin.write(line + '\n');
      } catch (err) {
        clearTimeout(timer);
        this.pending.delete(id);
        reject(err);
      }
    });
  }

  scheduleRestart() {
    if (this.shuttingDown || this.restarting) return;
    if (this.restartCount >= this.maxRestarts) {
      this.onEvent({ event: 'backend_failed', message: 'backend restart limit reached' });
      return;
    }
    this.restarting = true;
    this.restartCount += 1;
    const delay = 1000 * this.restartCount;
    setTimeout(async () => {
      try {
        await this.start();
        this.restarting = false;
        this.onEvent({ event: 'log', level: 'info', message: 'backend restarted' });
      } catch (err) {
        this.restarting = false;
        this.scheduleRestart();
      }
    }, delay);
  }

  shutdown() {
    this.shuttingDown = true;
    this._ready = false;
    if (this.rl) { try { this.rl.close(); } catch (_) {} this.rl = null; }
    const proc = this.proc;
    if (!proc || proc.exitCode !== null) return;
    try { proc.stdin.end(); } catch (_) {}
    // force-kill after a short grace period so no orphan survives the app
    const t1 = setTimeout(() => {
      try { if (proc.exitCode === null) proc.kill(); } catch (_) {}
    }, 1200);
    const t2 = setTimeout(() => {
      try { if (proc.exitCode === null) proc.kill('SIGKILL'); } catch (_) {}
    }, 3000);
    if (t1.unref) t1.unref();
    if (t2.unref) t2.unref();
  }
}

module.exports = Backend;