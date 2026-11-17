/** Identify exactly which image is broken in the running app. */
'use strict';
const WebSocket = require('ws');
const ws = new WebSocket(process.argv[2]);
ws.on('open', () => {
  ws.send(JSON.stringify({ id: 1, method: 'Runtime.evaluate', params: {
    expression: `JSON.stringify([...document.images]
      .filter(im => im.complete && im.naturalWidth === 0)
      .map(im => ({ src: im.getAttribute('src'), cls: im.className, id: im.id })))`,
    returnByValue: true,
  }}));
});
ws.on('message', (m) => {
  const msg = JSON.parse(m);
  if (msg.id === 1) {
    console.log(msg.result.result.value);
    ws.close();
    process.exit(0);
  }
});