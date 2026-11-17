/**
 * Verify the redesigned app: every view renders, dashboard has real data,
 * navigation works. Reads live DOM of the running installed app.
 */
'use strict';
const WebSocket = require('ws');
const wsUrl = process.argv[2];
const ws = new WebSocket(wsUrl);

const VIEWS = ['dashboard', 'downloads', 'queue', 'library', 'tools',
               'history', 'settings', 'about'];
const out = {};
let step = 0;

function evaluate(expr, id) {
  ws.send(JSON.stringify({ id, method: 'Runtime.evaluate', params: {
    expression: expr, returnByValue: true,
  }}));
}

ws.on('open', () => visit(0));

function visit(i) {
  if (i >= VIEWS.length) { report(); return; }
  const v = VIEWS[i];
  evaluate(`(() => {
    document.querySelector('[data-view="${v}"]').click();
    const view = document.getElementById('view-${v}');
    const visible = view && !view.hidden;
    const text = view ? view.textContent.replace(/\\s+/g, ' ').trim().slice(0, 80) : '';
    const broken = [...document.images].filter(im => im.complete && im.naturalWidth === 0).length;
    return JSON.stringify({ visible, text, broken });
  })()`, 100 + i);
}

ws.on('message', (m) => {
  const msg = JSON.parse(m);
  if (msg.id >= 100 && msg.result && msg.result.result) {
    const v = VIEWS[msg.id - 100];
    out[v] = JSON.parse(msg.result.result.value);
    setTimeout(() => visit(VIEWS.indexOf(v) + 1), 250);
  }
});

let allOk = true;
function report() {
  console.log('=== VIEW RENDER CHECK ===');
  for (const v of VIEWS) {
    const r = out[v] || {};
    const ok = r.visible;
    if (!ok) allOk = false;
    console.log(`${ok ? 'OK  ' : 'FAIL'} ${v.padEnd(10)} brokenImgs=${r.broken}  ${r.text.slice(0, 60)}`);
  }
  // dashboard data
  evaluate(`JSON.stringify({
    completed: document.getElementById('stCompleted').textContent,
    size: document.getElementById('stSize').textContent,
    sys: document.getElementById('dashSystem').textContent.slice(0, 120),
    recent: document.getElementById('dashRecent').children.length,
    recentEmptyHidden: document.getElementById('dashRecentEmpty').hidden,
  })`, 300);
}

ws.on('message', (m) => {
  const msg = JSON.parse(m);
  if (msg.id === 300 && msg.result && msg.result.result) {
    const d = JSON.parse(msg.result.result.value);
    console.log('=== DASHBOARD DATA ===');
    console.log(`completed=${d.completed} size=${d.size} recentRows=${d.recent}`);
    console.log('sys:', d.sys);
    const healthy = d.sys.includes('yt-dlp') && !d.sys.includes('unavailable');
    console.log('=== RESULT:', allOk && healthy ? 'PASS' : 'FAIL', '===');
    ws.close();
    process.exit(allOk && healthy ? 0 : 1);
  }
});