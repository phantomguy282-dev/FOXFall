'use strict';
const WebSocket = require('ws');
const wsUrl = process.argv[2];
const ws = new WebSocket(wsUrl);
const evaluate = (expr, id) => ws.send(JSON.stringify({ id, method: 'Runtime.evaluate', params: {
  expression: expr, returnByValue: true,
}}));
const out = {};
ws.on('open', () => {
  // navigate to Settings immediately (during/just after backend startup)
  evaluate("document.querySelector('[data-view=\"settings\"]').click(); 'ok'", 1);
});
ws.on('message', (m) => {
  const msg = JSON.parse(m);
  if (msg.id === 1) {
    // read diag right away
    evaluate(`JSON.stringify({
      diag: document.getElementById('diagInfo').textContent,
      label: document.getElementById('backendLabel').textContent,
      view: [...document.querySelectorAll('.view')].filter(v=>!v.hidden).map(v=>v.id),
    })`, 2);
  }
  if (msg.id === 2) {
    out.t0 = JSON.parse(msg.result.result.value);
    console.log('T+0 :', JSON.stringify(out.t0));
    // wait 6s: backend should have become ready; the ready handler must refresh
    setTimeout(() => {
      evaluate(`JSON.stringify({
        diag: document.getElementById('diagInfo').textContent,
        label: document.getElementById('backendLabel').textContent,
      })`, 3);
    }, 6000);
  }
  if (msg.id === 3) {
    out.t6 = JSON.parse(msg.result.result.value);
    console.log('T+6s:', JSON.stringify(out.t6));
    // click Settings again (view switch refresh) and read once more
    evaluate("document.querySelector('[data-view=\"home\"]').click(); document.querySelector('[data-view=\"settings\"]').click(); 'ok'", 4);
  }
  if (msg.id === 4) {
    setTimeout(() => {
      evaluate(`document.getElementById('diagInfo').textContent`, 5);
    }, 1500);
  }
  if (msg.id === 5) {
    out.afterReopen = msg.result.result.value;
    console.log('After reopen Settings:', out.afterReopen);
    const pass = !/unavailable/i.test(out.t6.diag) && !/unavailable/i.test(out.afterReopen);
    console.log('RACE FIX VERIFICATION:', pass ? 'PASS (diagnostics healthy)' : 'FAIL (still unavailable)');
    process.exit(pass ? 0 : 1);
  }
});
