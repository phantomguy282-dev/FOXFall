/**
 * PHASE 4/5: end-to-end test through the REAL IPC protocol.
 * Starts the backend via Backend class, analyzes a URL, starts a download,
 * collects progress events, and verifies the resulting file on disk.
 *
 * Usage: node tests/e2e-download.cjs [url]
 */
'use strict';
const path = require('path');
const fs = require('fs');

process.env.FOXFall_PYTHON = process.env.FOXFall_PYTHON ||

const Backend = require(path.resolve(__dirname, '..', 'src', 'main', 'backend.cjs'));

const URL_ARG = process.argv[2] || 'https://www.youtube.com/watch?v=aqz-KE-bpKQ';

(async () => {
  const events = [];
  let resolveStarted;
  const started = new Promise((r) => { resolveStarted = r; });
  let resolveFinished;
  const finished = new Promise((r) => { resolveFinished = r; });

  const backend = new Backend({
    onEvent: (e) => {
      events.push(e);
      if (e.event === 'download_progress') {
        const p = e.progress;
        const pct = p.total_bytes ? p.percentage.toFixed(1) + '%' : '—';
        process.stdout.write(
          `\r  [${p.status}] ${pct.padStart(7)}  ` +
          `${(p.downloaded_bytes / 1048576).toFixed(2)} MB  ` +
          `${(p.speed / 1048576).toFixed(2)} MB/s  ` +
          `ETA ${p.eta_unknown ? 'Calculating…' : p.eta + 's'}      `);
      }
      if (e.event === 'download_finished') {
        process.stdout.write('\n');
        resolveFinished(e);
      }
    },
  });

  await backend.start();
  console.log('backend ready:', backend.ready());

  console.log('\n1) analyze:', URL_ARG);
  const analysis = await backend.request('analyze_url', { url: URL_ARG });
  if (analysis.error) {
    console.error('ANALYZE FAILED:', analysis.error);
    backend.shutdown();
    process.exit(1);
  }
  console.log('   title:', analysis.title);
  console.log('   platform:', analysis.platform, '| quals:', analysis.qualities.map((q) => q.label).join(', '));

  const quality = (analysis.qualities.find((q) => q.label === '360p') || analysis.qualities[0]).label;
  console.log('\n2) start_download quality=' + quality);
  const started_res = await backend.request('start_download', {
    url: URL_ARG, quality, format: 'mp4',
  });
  if (started_res.error) {
    console.error('START FAILED:', started_res.error);
    backend.shutdown();
    process.exit(1);
  }
  resolveStarted(started_res.download_id);
  const dlId = started_res.download_id;
  console.log('   download_id:', dlId);

  console.log('\n3) progress events:');
  const timeout = setTimeout(() => {
    console.error('\nTIMEOUT waiting for completion');
    backend.shutdown();
    process.exit(1);
  }, 240000);

  const result = await finished;
  clearTimeout(timeout);

  const p = result.progress;
  const progressEvents = events.filter((e) =>
    e.event === 'download_progress' && e.download_id === dlId);
  console.log('\n4) verification:');
  console.log('   progress events received:', progressEvents.length);
  const pcts = [...new Set(progressEvents.map((e) => e.progress.percentage))].sort((a, b) => a - b);
  console.log('   distinct percentages:', pcts.slice(0, 10).join(', '));
  const speeds = progressEvents.map((e) => e.progress.speed).filter((s) => s > 0);
  console.log('   max speed seen:', speeds.length ? (Math.max(...speeds) / 1048576).toFixed(2) + ' MB/s' : 'n/a');
  const etas = [...new Set(progressEvents.map((e) => e.progress.eta))];
  console.log('   distinct ETAs:', etas.slice(0, 8).join(', '));
  console.log('   final status:', p.status);
  console.log('   filepath:', p.filepath);

  let ok = p.status === 'done';
  if (ok && p.filepath && fs.existsSync(p.filepath)) {
    const size = fs.statSync(p.filepath).size;
    console.log('   file size:', size.toLocaleString(), 'bytes');
    ok = size > 0;
  } else if (ok) {
    console.log('   FILE MISSING');
    ok = false;
  }
  // progress isolation: every event must carry our id and sane values
  const badEvents = progressEvents.filter((e) =>
    e.download_id !== dlId || e.progress.percentage < 0 || e.progress.percentage > 100 ||
    Number.isNaN(e.progress.percentage));
  console.log('   malformed/mismatched events:', badEvents.length);
  ok = ok && badEvents.length === 0;

  backend.shutdown();
  await new Promise((r) => setTimeout(r, 1200));
  console.log('\n' + (ok ? 'E2E RESULT: PASS' : 'E2E RESULT: FAIL'));
  process.exit(ok ? 0 : 1);
})().catch((err) => {
  console.error('FATAL:', err);
  process.exit(1);
});