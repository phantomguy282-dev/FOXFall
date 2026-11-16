/**
 * tests/ipc.test.cjs
 * Node test-runner tests for the desktop layer: backend protocol wiring
 * (spawn/JSON/response correlation/restart) and preload security config.
 */
const test = require('node:test');
const assert = require('node:assert');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const REPO = path.resolve(__dirname, '..', '..');

test('main process config declares secure webPreferences', () => {
  const src = fs.readFileSync(path.join(REPO, 'desktop/src/main/main.cjs'), 'utf8');
  assert.match(src, /contextIsolation:\s*true/);
  assert.match(src, /nodeIntegration:\s*false/);
  assert.match(src, /sandbox:\s*true/);
  assert.match(src, /requestSingleInstanceLock/);
  assert.match(src, /ALLOWED_COMMANDS/);
});

test('preload exposes only allowlisted bridge', () => {
  const src = fs.readFileSync(path.join(REPO, 'desktop/src/main/preload.cjs'), 'utf8');
  assert.match(src, /contextBridge\.exposeInMainWorld/);
  assert.match(src, /prevent duplicate listeners/);
  // no nodeIntegration leaks
  assert.doesNotMatch(src, /require\(['"]fs['"]\)/);
});

test('backend manager handles crash + restart + clean shutdown', async () => {
  const Backend = require(path.join(REPO, 'desktop/src/main/backend.cjs'));
  const events = [];
  const backend = new Backend({
    onEvent: (e) => events.push(e),
  });
  await backend.start();
  assert.ok(backend.ready(), 'backend should become ready');

  // request/response correlation
  const pong = await backend.request('ping', {});
  assert.equal(pong.pong, true);

  // unknown action -> error response, not crash
  await assert.rejects(() => backend.request('no_such_action', {}));

  // clean shutdown
  const proc = backend.proc;
  backend.shutdown();
  await new Promise((r) => setTimeout(r, 2000));
  assert.ok(backend.shuttingDown);
  assert.ok(!proc || proc.exitCode !== null, 'backend process must be terminated');
  if (proc && proc.exitCode === null) {
    try { proc.kill(); } catch (_) {}
  }
}, { timeout: 30000 });

test('backend server speaks JSON-lines protocol', async () => {
  const py = path.join(REPO, '.venv/Scripts/python.exe');
  const exe = fs.existsSync(py) ? py : 'python';
  const script = path.join(REPO, 'backend/server.py');
  const proc = spawn(exe, [script, '--stdio'], { cwd: path.dirname(script) });

  const lines = [];
  const rl = require('readline').createInterface({ input: proc.stdout });
  const ready = new Promise((resolve) => {
    rl.on('line', (l) => {
      try {
        const obj = JSON.parse(l);
        lines.push(obj);
        if (obj.event === 'ready') resolve();
      } catch (_) { /* skip */ }
    });
  });
  await Promise.race([ready, new Promise((_, rej) =>
    setTimeout(() => rej(new Error('backend ready timeout')), 20000))]);

  // ping round trip
  const pong = new Promise((resolve) => {
    const check = setInterval(() => {
      const found = lines.find((m) => m.id === 1);
      if (found) { clearInterval(check); resolve(found); }
    }, 50);
  });
  proc.stdin.write(JSON.stringify({ id: 1, action: 'ping', payload: {} }) + '\n');
  const response = await Promise.race([pong,
    new Promise((_, rej) => setTimeout(() => rej(new Error('ping timeout')), 15000))]);
  assert.equal(response.ok, true);
  assert.ok(response.result.pong);

  proc.kill();
  await new Promise((r) => setTimeout(r, 500));
}, { timeout: 45000 });
