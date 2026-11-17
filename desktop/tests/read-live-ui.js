/**
 * Live UI proof: connects to the running FOXFall app via CDP, clicks
 * Settings, and reads the actual on-screen backend status + diagnostics.
 */
'use strict';
const WebSocket = require('ws');
const http = require('http');

http.get('http://127.0.0.1:9222/json', (res) => {
  let d = '';
  res.on('data', (c) => (d += c));
  res.on('end', () => {
    const page = JSON.parse(d).find((p) => p.type === 'page');
    if (!page) { console.error('no page'); process.exit(1); }
    const ws = new WebSocket(page.webSocketDebuggerUrl);
    ws.on('open', () => {
      ws.send(JSON.stringify({ id: 1, method: 'Runtime.evaluate', params: {
        expression: "document.querySelector('[data-view=\"settings\"]').click(); 'ok'",
      }}));
    });
    ws.on('message', (m) => {
      const msg = JSON.parse(m);
      if (msg.id === 1) {
        setTimeout(() => {
          ws.send(JSON.stringify({ id: 2, method: 'Runtime.evaluate', params: {
            expression: `(() => {
              const label = document.getElementById('backendLabel');
              const dot = document.getElementById('backendDot');
              const diag = document.getElementById('diagInfo');
              return JSON.stringify({
                backendLabel: label ? label.textContent : null,
                backendDotOk: dot ? dot.classList.contains('ok') : null,
                diagnostics: diag ? diag.textContent : null,
                visibleView: [...document.querySelectorAll('.view')]
                  .filter((v) => !v.hidden).map((v) => v.id),
              });
            })()`,
          }}));
        }, 1500);
      }
      if (msg.id === 2) {
        console.log('LIVE UI STATE:', msg.result.result.value);
        ws.close();
        process.exit(0);
      }
    });
  });
});