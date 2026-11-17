/**
 * Full pipeline test through the RUNNING installed app via CDP:
 * Analyze + Download with NEW test URLs (not used in prior sessions).
 * Usage: node tests/app-pipeline.js <url> <quality>
 */
'use strict';
const WebSocket = require('ws');
const http = require('http');
const fs = require('fs');

const URL = process.argv[2];
const QUALITY = process.argv[3] || 'Best available';
if (!URL) { console.error('usage: node app-pipeline.js <url> [quality]'); process.exit(1); }

http.get('http://127.0.0.1:9226/json', (res) => {
  let d = '';
  res.on('data', (c) => (d += c));
  res.on('end', () => {
    const page = JSON.parse(d).find((p) => p.type === 'page');
    const ws = new WebSocket(page.webSocketDebuggerUrl);
    let downloadId = null;
    let analysis = null;
    const progress = [];

    ws.on('open', () => {
      ws.send(JSON.stringify({
        id: 1, method: 'Runtime.evaluate', params: {
          expression: `window.foxfall.invoke("analyze_url", {url: ${JSON.stringify(URL)}})` +
            '.then(r => JSON.stringify(r))' +
            '.catch(e => "ERR: " + e.message)',
          awaitPromise: true, returnByValue: true,
        },
      }));
    });
    ws.on('message', (m) => {
      const msg = JSON.parse(m);
      if (msg.id === 1) {
        const raw = msg.result.result.value;
        const res = JSON.parse(raw);
        if (!res.ok || (res.result && res.result.error)) {
          console.log('ANALYZE FAILED:', JSON.stringify(res.result || res).slice(0, 300));
          process.exit(1);
        }
        analysis = res.result;
        console.log('ANALYZE OK:');
        console.log('  title:', analysis.title);
        console.log('  platform:', analysis.platform, '| uploader:', analysis.uploader);
        console.log('  duration:', analysis.duration_text, '| views:', analysis.views);
        console.log('  qualities:', analysis.qualities.map((q) => q.label).join(', '));
        console.log('  thumbnail:', (analysis.thumbnail || 'none').slice(0, 70));

        // start download
        const q = analysis.qualities.find((x) => x.label === QUALITY) || analysis.qualities[0];
        ws.send(JSON.stringify({
          id: 2, method: 'Runtime.evaluate', params: {
            expression: `window.foxfall.invoke("start_download", {url: ${JSON.stringify(analysis.url)}, quality: ${JSON.stringify(q.label)}, format: "mp4"})` +
              '.then(r => JSON.stringify(r))' +
              '.catch(e => "ERR: " + e.message)',
            awaitPromise: true, returnByValue: true,
          },
        }));
      }
      if (msg.id === 2) {
        const res = JSON.parse(msg.result.result.value);
        if (!res.ok || res.result.error) {
          console.log('START FAILED:', JSON.stringify(res.result || res).slice(0, 300));
          process.exit(1);
        }
        downloadId = res.result.download_id;
        console.log('DOWNLOAD STARTED:', downloadId, `(${res.result.quality})`);
        // start a progress poller via queue_status events (listen to events)
        pollEvents();
      }
    });

    const pollEvents = () => {
      ws.send(JSON.stringify({
        id: 3, method: 'Runtime.evaluate', params: {
          expression: `window.__ffEvents = window.__ffEvents || [];
            window.foxfall.onEvent((e) => window.__ffEvents.push(e));
            'listening'`,
        },
      }));
      // poll collected events every second
      const interval = setInterval(() => {
        ws.send(JSON.stringify({
          id: 'poll' + Math.random(), method: 'Runtime.evaluate', params: {
            expression: `JSON.stringify((window.__ffEvents||[]).filter(e => e.event === 'download_progress' && e.download_id === ${JSON.stringify(downloadId)}).map(e => e.progress))`,
            returnByValue: true,
          },
        }));
      }, 1000);
      // finish check
      const finish = setInterval(() => {
        ws.send(JSON.stringify({
          id: 'fin' + Math.random(), method: 'Runtime.evaluate', params: {
            expression: `window.foxfall.invoke("list_queue", {}).then(r => JSON.stringify(r))` +
              '.catch(e => "ERR: " + e.message)',
            awaitPromise: true, returnByValue: true,
          },
        }));
      }, 3000);
      let lastPollId = 0;
      ws.on('message', (m) => {
        const msg = JSON.parse(m);
        if (typeof msg.id === 'string' && msg.id.startsWith('poll') && msg.result && msg.result.result) {
          const items = JSON.parse(msg.result.result.value);
          for (const p of items) {
            if (!progress.length || progress[progress.length - 1].downloaded_bytes !== p.downloaded_bytes) {
              progress.push(p);
              console.log(`  [${p.status}] ${(p.percentage || 0).toFixed(1)}%  ` +
                `${(p.downloaded_bytes / 1048576).toFixed(2)} MB  ` +
                `${((p.speed || 0) / 1048576).toFixed(2)} MB/s  ` +
                `ETA ${p.eta_unknown ? 'Calc…' : p.eta + 's'}`);
            }
        }
        }
        if (typeof msg.id === 'string' && msg.id.startsWith('fin') && msg.result && msg.result.result) {
          const r = JSON.parse(msg.result.result.value);
          if (!r.ok) return;
          const item = (r.result.items || []).find((i) => i.download_id === downloadId);
          if (!item) return;
          const p = item.progress;
          if (['done', 'error', 'cancelled'].includes(p.status)) {
            clearInterval(interval); clearInterval(finish);
            console.log('\nFINAL STATUS:', p.status);
            console.log('filepath:', p.filepath || '(none)');
            if (p.error) console.log('error:', p.error);
            if (p.filepath && fs.existsSync(p.filepath)) {
              const size = fs.statSync(p.filepath).size;
              console.log('FILE VERIFIED:', `${size.toLocaleString()} bytes`, size > 0 ? 'NONZERO OK' : 'ZERO-SIZE FAIL');
              console.log('\nPIPELINE RESULT:', 'PASS');
            } else {
              console.log('\nPIPELINE RESULT:', 'FAIL (file missing)');
            }
            ws.close();
            process.exit(p.status === 'done' ? 0 : 1);
          }
        }
      });
    };
  });
});