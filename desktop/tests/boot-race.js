/**
 * Reproduce the boot race: re-open the app fresh and IMMEDIATELY read the
 * diag panel, then again after 5s. If the first read shows "Backend
 * unavailable" while the backend is actually still starting, that's the bug.
 */
'use strict';
const WebSocket = require('ws');
const http = require('http');
const { execSync } = require('child_process');

try { execSync('taskkill /F /IM FOXFall.exe /T', { stdio: 'ignore' }); } catch (_) {}
try { execSync('taskkill /F /IM foxfall-backend.exe /T', { stdio: 'ignore' }); } catch (_) {}

const { spawn } = require('child_process');
spawn(process.env.LOCALAPPDATA + '\\Programs\\FOXFall\\FOXFall.exe',
      ['--remote-debugging-port=9223'], { detached: true, stdio: 'ignore' })
  .unref();

const waitForPage = (tries) => new Promise((resolve, reject) => {
  if (tries <= 0) return reject(new Error('no page'));
  http.get('http://127.0.0.1:9223/json', (res) => {
    let d = '';
    res.on('data', (c) => (d += c));
    res.on('end', () => {
      const page = JSON.parse(d).find((p) => p.type === 'page');
      page ? resolve(page) : setTimeout(() => waitForPage(tries - 1).then(resolve, reject), 500);
    });
  }).on('error', () => setTimeout(() => waitForPage(tries - 1).then(resolve, reject), 500));
});

(async () => {
  let lastError;
  for (let i = 0; i < 20; i++) {
    try { await waitForPage(1); lastError = null; break; }
    catch (e) { lastError = e; await new Promise((r) => setTimeout(r, 500)); }
  }
  if (lastError) throw lastError;

  const page = await waitForPage(30);
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  const evaluate = (expr, id) => new Promise((resolve) => {
    ws.send(JSON.stringify({ id, method: 'Runtime.evaluate', params: {
      expression: expr, awaitPromise: true, returnByValue: true,
    }}));
  });
  const results = {};
  ws.on('message', (m) => {
    const msg = JSON.parse(m);
    if (msg.id && msg.result && msg.result.result) {
      results[msg.id] = msg.result.result.value;
    }
    if (msg.id === 3) {
      console.log('T+0s  diag:', results[3]);
      // after 6s, re-read
      setTimeout(async () => {
        const v = await evaluate(`document.getElementById('diagInfo').textContent`, 4);
        console.log('T+6s  diag:', v.result.result.value);
        const l = await evaluate(`document.getElementById('backendLabel').textContent`, 5);
        console.log('T+6s  backend label:', l.result.result.value);
        ws.close();
        process.exit(0);
      }, 6000);
    }
  });
  ws.on('open', () => {
    evaluate(`document.getElementById('diagInfo').textContent`, 3);
  });
})();
