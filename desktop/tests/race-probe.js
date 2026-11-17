'use strict';
const WebSocket = require('ws');
const ws = new WebSocket(process.argv[2]);
const read = (id) => ws.send(JSON.stringify({ id, method: 'Runtime.evaluate', params: {
  expression: `JSON.stringify({
    diag: document.getElementById('diagInfo').textContent,
    label: document.getElementById('backendLabel').textContent,
  })`, returnByValue: true,
}}));
const out = {};
ws.on('open', () => read(1));
ws.on('message', (m) => {
  const msg = JSON.parse(m);
  if (msg.id && msg.result && msg.result.result) {
    out[msg.id] = msg.result.result.value;
    if (msg.id === 1) {
      console.log('T+0:', out[1]);
      setTimeout(() => read(2), 6000);
    } else if (msg.id === 2) {
      console.log('T+6s:', out[2]);
      process.exit(0);
    }
  }
});
