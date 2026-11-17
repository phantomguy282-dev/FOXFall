/**
 * Direct IPC probe inside the running app: calls get_app_info exactly as
 * the Settings screen does and reports the raw response.
 */
'use strict';
const WebSocket = require('ws');
const http = require('http');

http.get('http://127.0.0.1:9222/json', (res) => {
  let d = '';
  res.on('data', (c) => (d += c));
  res.on('end', () => {
    const page = JSON.parse(d).find((p) => p.type === 'page');
    const ws = new WebSocket(page.webSocketDebuggerUrl);
    ws.on('open', () => {
      ws.send(JSON.stringify({
        id: 1,
        method: 'Runtime.evaluate',
        params: {
          expression: 'window.foxfall.invoke("get_app_info", {})' +
            '.then((r) => JSON.stringify(r))' +
            '.catch((e) => "PROMISE ERR: " + e.message)',
          awaitPromise: true,
          returnByValue: true,
        },
      }));
    });
    ws.on('message', (m) => {
      const msg = JSON.parse(m);
      if (msg.id === 1) {
        console.log('RAW get_app_info:',
          msg.result && msg.result.result ? msg.result.result.value : msg.result);
        ws.close();
        process.exit(0);
      }
    });
  });
});