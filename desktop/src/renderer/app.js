/* FOXFall renderer logic. Talks only through window.foxfall (preload bridge). */
'use strict';

const api = window.foxfall;
const $ = (id) => document.getElementById(id);

/* ------------------------------------------------------------------ state */
let currentAnalysis = null;
let queueItems = new Map(); // download_id -> item
const unsub = api.onEvent(handleEvent);

/* ------------------------------------------------------------------ views */
document.querySelectorAll('.nav-item').forEach((btn) => {
  btn.addEventListener('click', () => showView(btn.dataset.view));
});

function showView(name) {
  document.querySelectorAll('.nav-item').forEach((b) =>
    b.classList.toggle('active', b.dataset.view === name));
  document.querySelectorAll('.view').forEach((v) => {
    v.hidden = v.id !== `view-${name}`;
  });
  if (name === 'history') loadHistory();
  if (name === 'queue') renderQueue();
  if (name === 'dashboard') refreshDashboard();
  if (name === 'settings') {
    // Always refresh diagnostics when Settings is opened so the panel
    // reflects the current backend state (never a stale boot-time value).
    loadSystemInfo();
  }
}

/* ------------------------------------------------------- dashboard data */
async function refreshDashboard() {
  // stats from real queue + history
  const items = [...queueItems.values()].map((i) => i.progress || {});
  const completed = items.filter((p) => p.status === 'done').length;
  const active = items.filter((p) =>
    ['preparing', 'downloading', 'merging'].includes(p.status)).length;
  const failed = items.filter((p) => p.status === 'error').length;
  const speed = items
    .filter((p) => ['downloading', 'merging'].includes(p.status))
    .reduce((sum, p) => sum + (p.speed || 0), 0);
  $('stCompleted').textContent = String(completed);
  $('stActive').textContent = String(active);
  $('stFailed').textContent = String(failed);
  $('stSpeed').textContent = speed > 0 ? fmtSpeed(speed) : '—';

  // completed size from real history (backend)
  const res = await api.invoke('list_history', { limit: 200 });
  if (res.ok && res.result) {
    const hist = (res.result.items || []).filter((i) => i.status === 'completed');
    const totalBytes = hist.reduce((s, i) => s + (i.filesize || 0), 0);
    $('stSize').textContent = totalBytes > 0 ? fmtSize(totalBytes) : '—';
    renderRecent(hist.slice(0, 6));
  } else {
    $('stSize').textContent = '—';
    $('dashRecentEmpty').hidden = false;
    $('dashRecent').innerHTML = '';
  }
}

function renderRecent(hist) {
  const list = $('dashRecent');
  const empty = $('dashRecentEmpty');
  list.innerHTML = '';
  empty.hidden = hist.length > 0;
  for (const it of hist) {
    const row = document.createElement('div');
    row.className = 'recent-row';
    const title = document.createElement('span');
    title.className = 'r-title';
    title.textContent = it.title || '(untitled)';
    const meta = document.createElement('span');
    meta.className = 'r-meta';
    const size = it.filesize ? fmtSize(it.filesize) : '';
    meta.textContent = `${it.platform || ''} · ${size}`;
    const actions = document.createElement('div');
    actions.className = 'r-actions';
    if (it.filepath) {
      actions.appendChild(mkIconBtn('open', 'Open file', async () => {
        await api.invoke('open_path', { path: it.filepath });
      }));
      actions.appendChild(mkIconBtn('folder', 'Show in folder', async () => {
        await api.invoke('reveal_path', { path: it.filepath });
      }));
    }
    row.append(title, meta, actions);
    list.appendChild(row);
  }
}

function mkIconBtn(iconName, title, fn) {
  const b = document.createElement('button');
  b.className = 'iconbtn';
  b.title = title;
  b.setAttribute('aria-label', title);
  b.innerHTML = icon(iconName, 15);
  b.addEventListener('click', fn);
  return b;
}

/* ------------------------------------------------------- dashboard system status */
async function renderDashSystem() {
  const info = await api.invoke('get_app_info', {});
  const el = $('dashSystem');
  if (!info.ok) {
    el.innerHTML = sysRow('bad', 'Backend', 'unavailable');
    return;
  }
  const i = info.result;
  const ffOk = !i.ffmpeg.includes('NOT FOUND');
  const ffOkb = !i.ffmpeg.includes('ffprobe: no');
  el.innerHTML =
    sysRow('ok', 'Backend', `v${i.version}`) +
    sysRow('ok', 'yt-dlp', i.yt_dlp) +
    sysRow(ffOk ? 'ok' : 'bad', 'FFmpeg', ffOk ? 'v' + ffmpegVer(i.ffmpeg) : 'not found') +
    sysRow(ffOkb ? 'ok' : 'bad', 'FFprobe', ffOkb ? 'available' : 'not found');
}

function sysRow(state, name, value) {
  return `<div class="sys-row"><span class="dot ${state}"></span>${name}<b>${value}</b></div>`;
}

function ffmpegVer(diagText) {
  const m = /v([0-9.]+)/.exec(diagText);
  return m ? m[1] : 'available';
}

/* ------------------------------------------------------------------ backend status */
async function pollBackend() {
  const status = await api.backendStatus();
  const dot = $('backendDot');
  const label = $('backendLabel');
  dot.classList.toggle('ok', status.ready);
  dot.classList.toggle('bad', !status.ready && !status.restarting);
  label.textContent = status.ready ? 'Connected'
    : status.restarting ? 'Reconnecting…' : 'Backend offline';
}

setInterval(pollBackend, 2000);
pollBackend();

/* ------------------------------------------------------------------ events from backend */
function handleEvent(event) {
  switch (event.event) {
    case 'download_progress':
      updateQueueItem(event.download_id, event.progress);
      break;
    case 'download_finished':
      updateQueueItem(event.download_id, event.progress);
      if (event.progress && event.progress.status === 'done') {
        toast('Download completed', event.progress.filename);
        $('notifDot').hidden = false;
      }
      // Dashboard must reflect persistent history, not only this session.
      refreshDashboard();
      break;
    case 'library_progress': {
      const bar = $('libScanProgress');
      if (bar) {
        bar.hidden = false;
        const pct = event.total ? (event.scanned / event.total * 100) : 0;
        $('libScanFill').style.width = `${pct}%`;
        $('libScanStatus').textContent =
          `Indexing ${event.scanned}/${event.total} — ${event.path.split(/[\\/]/).pop()}`;
      }
      break;
    }
    case 'library_entry':
      renderLibTile(event.entry);
      $('libEmpty').hidden = true;
      break;
    case 'library_scan_done':
      finishLibraryScan(event.result || {});
      break;
    case 'tool_progress':
      updateToolProgress(event.operation_id, event.percentage);
      break;
    case 'tool_finished':
      finishTool(event);
      break;
    case 'queue_status':
      if (Array.isArray(event.items)) {
        const seen = new Set();
        for (const item of event.items) {
          seen.add(item.download_id);
          queueItems.set(item.download_id, item);
        }
        for (const id of [...queueItems.keys()]) {
          if (!seen.has(id)) queueItems.delete(id);
        }
        renderQueue();
        updateQueuePill();
      }
      break;
    case 'ready':
      // Backend just confirmed readiness. Refresh diagnostics + dashboard,
      // which may have been rendered before the backend finished starting.
      loadSystemInfo();
      renderDashSystem();
      if (typeof loadSettings === 'function') loadSettings();
      break;
    case 'backend_exit':
    case 'backend_failed':
      setMessage('homeMessage', 'Backend connection lost. Restarting…', 'error');
      loadSystemInfo();
      renderDashSystem();
      break;
    default:
      break;
  }
}

function updateQueuePill() {
  const active = [...queueItems.values()].filter((i) =>
    ['pending', 'preparing', 'downloading', 'merging'].includes(i.progress.status)).length;
  const pill = $('queuePill');
  pill.hidden = active === 0;
  pill.textContent = String(active);
}

function toast(title, body) {
  $("notifDot").hidden = false;
  const area = $("toasts");
  if (!area) return;
  const t = document.createElement('div');
  t.className = 'toast';
  const strong = document.createElement('strong');
  strong.textContent = title;
  const bodyEl = document.createElement('div');
  bodyEl.textContent = body || '';
  t.append(strong, bodyEl);
  area.appendChild(t);
  setTimeout(() => t.remove(), 6000);
}

/* global search filters history when on History view; jumps there otherwise */
$('globalSearch').addEventListener('keydown', (e) => {
  if (e.key !== 'Enter') return;
  showView('history');
  const s = $('globalSearch').value;
  $('histSearch').value = s;
  loadHistory();
});
$('histSearch').addEventListener('input', () => loadHistory());
$('histFilter').addEventListener('change', () => loadHistory());
$('notifBtn').addEventListener('click', () => {
  $('notifDot').hidden = true;
  showView('queue');
});

/* dashboard quick actions */
$('dashNewBtn').addEventListener('click', () => showView('downloads'));
$('qaNew').addEventListener('click', () => showView('downloads'));
$('qaLibrary').addEventListener('click', () => showView('library'));
$('qaTools').addEventListener('click', () => showView('tools'));
$('qaHistory').addEventListener('click', () => showView('history'));
$('dashToHistory').addEventListener('click', () => showView('history'));
$('dashDiagBtn').addEventListener('click', async () => {
  showView('settings');
  $('runDiagBtn').click();
});

/* ---------- Media Library: real index via backend (ffprobe+ffmpeg) ---------- */
let libFavoritesOnly = false;

async function loadLibrary() {
  const res = await api.invoke('library_list', {
    query: $('libSearch').value || '',
    sort: $('libSort').value || 'date',
  });
  const grid = $('libGrid');
  grid.innerHTML = '';
  const items = res.ok && res.result ? res.result.items : [];
  const shown = libFavoritesOnly ? items.filter((i) => i.favorite) : items;
  $('libEmpty').hidden = shown.length > 0;
  for (const entry of shown) renderLibTile(entry);
}

function renderLibTile(entry) {
  const grid = $('libGrid');
  if (document.querySelector(`.lib-tile[data-path="${CSS.escape(entry.path)}"]`)) {
    return; // no duplicate tiles on rescan
  }
  const tile = document.createElement('div');
  tile.className = 'lib-tile';
  tile.dataset.path = entry.path;
  if (entry.missing) tile.classList.add('missing');

  const img = document.createElement('img');
  img.className = 'lib-thumb';
  img.loading = 'lazy';
  img.alt = entry.title || '';
  img.src = entry.thumb ||
    'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';

  const info = document.createElement('div');
  info.className = 'lib-info';
  const name = document.createElement('div');
  name.className = 'lib-name';
  name.textContent = entry.title || '(untitled)';
  const meta = document.createElement('div');
  meta.className = 'lib-meta';
  const bits = [];
  if (entry.missing) bits.push('file missing');
  if (entry.duration_text) bits.push(entry.duration_text);
  if (entry.resolution) bits.push(entry.resolution);
  if (entry.size) bits.push(fmtSize(entry.size));
  meta.textContent = bits.join(' Â· ');
  info.append(name, meta);

  const acts = document.createElement('div');
  acts.className = 'lib-actions';
  acts.appendChild(mkIconBtn(entry.favorite ? 'check' : 'about',
    entry.favorite ? 'Unfavorite' : 'Favorite', async () => {
      await api.invoke('library_set_favorite',
        { path: entry.path, favorite: !entry.favorite });
      loadLibrary();
    }));
  if (!entry.missing) {
    acts.appendChild(mkIconBtn('open', 'Open file', async () => {
      await api.invoke('open_path', { path: entry.path });
    }));
    acts.appendChild(mkIconBtn('folder', 'Show in folder', async () => {
      await api.invoke('reveal_path', { path: entry.path });
    }));
  }
  acts.appendChild(mkIconBtn('trash', 'Remove from library', async () => {
    await api.invoke('library_remove', { path: entry.path });
    tile.remove();
    loadLibrary();
  }));

  tile.append(img, info, acts);
  grid.appendChild(tile);
}

$('libRescanBtn').addEventListener('click', async () => {
  $('libRescanBtn').disabled = true;
  $('libScanProgress').hidden = false;
  $('libScanFill').style.width = '0%';
  $('libScanStatus').textContent = 'Indexingâ€¦';
  $('libGrid').innerHTML = '';
  const res = await api.invoke('library_scan', {});
  if (!res.ok || res.result.error) {
    $('libScanStatus').textContent = res.result?.error || res.error || 'Scan failed';
    $('libScanStatus').classList.add('bad');
    $('libRescanBtn').disabled = false;
  }
});

function finishLibraryScan(result) {
  $('libScanProgress').hidden = true;
  $('libRescanBtn').disabled = false;
  if (result.error) {
    $('libScanStatus').textContent = result.error;
    return;
  }
  toast(`Library indexed: ${result.indexed} files`,
        result.cancelled ? 'Scan cancelled â€” resumable' : '');
  loadLibrary();
}

$('libSearch').addEventListener('input', () => loadLibrary());
$('libSort').addEventListener('change', () => loadLibrary());
$('libFavOnly').addEventListener('click', () => {
  libFavoritesOnly = !libFavoritesOnly;
  $('libFavOnly').classList.toggle('btn-primary', libFavoritesOnly);
  loadLibrary();
});

/* ------------------------------------------------------------------ helpers */
function setMessage(id, text, kind = '') {
  const el = $(id);
  if (!el) return;
  el.textContent = text;
  el.className = `message ${kind}`;
}

function fmtSize(bytes) {
  if (!bytes || bytes <= 0) return '—';
  const units = ['B', 'KB', 'MB', 'GB'];
  let u = 0, n = bytes;
  while (n >= 1024 && u < units.length - 1) { n /= 1024; u++; }
  return `${n.toFixed(1)} ${units[u]}`;
}

function fmtEta(seconds, status) {
  if (status === 'done') return 'Completed';
  if (status === 'merging') return 'Finalizing…';
  if (seconds == null || seconds < 0) return 'Calculating…';
  if (seconds < 60) return `${Math.round(seconds)} seconds`;
  const m = Math.floor(seconds / 60), s = Math.round(seconds % 60);
  const h = Math.floor(m / 60);
  if (h) return `${h}:${String(m % 60).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  return `${m}:${String(s).padStart(2, '0')}`;
}

function fmtSpeed(bps) {
  if (!bps || bps <= 0) return '—';
  const units = ['B/s', 'KB/s', 'MB/s', 'GB/s'];
  let u = 0, n = bps;
  while (n >= 1024 && u < units.length - 1) { n /= 1024; u++; }
  return `${n.toFixed(1)} ${units[u]}`;
}

/* ------------------------------------------------------------------ analyze flow */
$('pasteBtn').addEventListener('click', async () => {
  try {
    const text = await navigator.clipboard.readText();
    if (text) {
      $('urlInput').value = text.trim();
      analyze();
    }
  } catch {
    setMessage('homeMessage', 'Clipboard unavailable — paste manually with Ctrl+V.', 'error');
  }
});
$('clearBtn').addEventListener('click', () => {
  $('urlInput').value = '';
  $('analysisCard').hidden = true;
  currentAnalysis = null;
  setMessage('homeMessage', '');
});
$('analyzeBtn').addEventListener('click', analyze);
$('urlInput').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') analyze();
});

async function analyze() {
  const url = $('urlInput').value.trim();
  if (!url) return;
  $('analyzeBtn').disabled = true;
  setMessage('homeMessage', 'Analyzing…');
  const status = await api.backendStatus();
  if (!status.ready) {
    $('analyzeBtn').disabled = false;
    setMessage('homeMessage',
      status.restarting
        ? 'The backend is restarting — try again in a few seconds.'
        : 'Backend unavailable. FOXFall could not start its download engine. '
          + 'Reinstall the application; if the problem persists, check the '
          + 'diagnostics in Settings.',
      'error');
    return;
  }
  const res = await api.invoke('analyze_url', { url });
  $('analyzeBtn').disabled = false;
  if (!res.ok) {
    setMessage('homeMessage', res.error || 'Analysis failed', 'error');
    return;
  }
  if (res.result && res.result.error) {
    setMessage('homeMessage', res.result.error, 'error');
    return;
  }
  currentAnalysis = res.result;
  renderAnalysis(res.result);
  setMessage('homeMessage', '');
}

function renderAnalysis(info) {
  $('analysisCard').hidden = false;
  $('videoTitle').textContent = info.title || '(untitled)';
  $('platformChip').textContent = info.platform_name || info.platform;
  $('uploader').textContent = info.uploader ? `by ${info.uploader}` : '';
  $('duration').textContent = info.duration_text ? `⏱ ${info.duration_text}` : '';
  $('views').textContent = info.views ? `👁 ${info.views.toLocaleString()}` : '';
  const thumb = $('thumb');
  if (info.thumbnail) {
    thumb.src = info.thumbnail;
    thumb.onerror = () => { thumb.style.visibility = 'hidden'; };
    thumb.onload = () => { thumb.style.visibility = 'visible'; };
  } else {
    thumb.style.visibility = 'hidden';
  }
  const qs = $('qualitySelect');
  qs.innerHTML = '';
  for (const q of info.qualities || []) {
    const opt = document.createElement('option');
    opt.value = q.label;
    opt.textContent = q.label + (q.kind === 'audio' ? ' ♫' : '');
    qs.appendChild(opt);
  }
  const fs2 = $('formatSelect');
  fs2.innerHTML = '';
  for (const f of info.formats || ['mp4']) {
    const opt = document.createElement('option');
    opt.value = f;
    opt.textContent = f.toUpperCase();
    fs2.appendChild(opt);
  }
  const prefFmt = (info.formats || []).includes('mp4') ? 'mp4' : (info.formats || ['mp4'])[0];
  fs2.value = prefFmt;
}

$('downloadBtn').addEventListener('click', async () => {
  if (!currentAnalysis) return;
  $('downloadBtn').disabled = true;
  const res = await api.invoke('start_download', {
    url: currentAnalysis.url,
    quality: $('qualitySelect').value,
    format: $('formatSelect').value,
  });
  $('downloadBtn').disabled = false;
  if (!res.ok || res.result.error) {
    setMessage('homeMessage', res.result?.error || res.error || 'Could not start download', 'error');
    return;
  }
  setMessage('homeMessage', `Download started: ${res.result.title}`, 'ok');
  showView('queue');
});

$('openFolderBtn').addEventListener('click', async () => {
  const s = await api.invoke('get_settings', {});
  const dir = s.ok && s.result ? s.result.download_dir : '';
  const settings = await api.invoke('get_settings', {});
  await api.invoke('reveal_path', {
    path: (settings.result && settings.result.download_dir) || dir || '',
  });
});

/* ------------------------------------------------------------------ queue */
function renderQueue() {
  const list = $('queueList');
  const items = [...queueItems.values()];
  $('queueEmpty').hidden = items.length > 0;
  list.innerHTML = '';
  for (const item of items) {
    list.appendChild(renderQueueCard(item));
  }
}

function renderQueueCard(item) {
  const p = item.progress || {};
  const card = document.createElement('div');
  card.className = 'queue-card';
  card.dataset.id = item.download_id;

  const img = document.createElement('img');
  img.className = 'queue-thumb';
  if (item.thumbnail) img.src = item.thumbnail;

  const body = document.createElement('div');
  body.className = 'queue-body';

  const head = document.createElement('div');
  head.className = 'queue-head';
  const title = document.createElement('div');
  title.className = 'queue-title';
  title.textContent = item.title || '';
  const status = document.createElement('div');
  status.className = `queue-status st-${p.status || 'pending'}`;
  status.textContent = (p.status || 'pending').replace('_', ' ');
  head.append(title, status);

  const track = document.createElement('div');
  track.className = 'progress-track';
  const fill = document.createElement('div');
  fill.className = 'progress-fill';
  if (p.total) {
    fill.style.width = `${Math.min(100, p.percentage || 0)}%`;
  } else if (p.status === 'downloading') {
    fill.classList.add('indeterminate');
    fill.style.width = '60%';
  }
  track.appendChild(fill);

  const stats = document.createElement('div');
  stats.className = 'queue-stats';
  const pct = p.total ? `<b>${(p.percentage || 0).toFixed(1)}%</b>` : '';
  stats.innerHTML =
    `${pct}<span>${fmtSize(p.downloaded_bytes)}${p.total ? ' / ' + fmtSize(p.total) : ''}</span>` +
    `<span>Speed <b>${fmtSpeed(p.speed)}</b></span>` +
    `<span>ETA <b>${fmtEta(p.eta, p.status)}</b></span>` +
    `<span>${item.quality || ''} · ${(item.format || '').toUpperCase()}</span>`;

  const buttons = document.createElement('div');
  buttons.className = 'queue-buttons';
  const mkBtn = (label, cls, fn) => {
    const b = document.createElement('button');
    b.className = `btn btn-small ${cls}`;
    b.textContent = label;
    b.addEventListener('click', fn);
    return b;
  };
  const active = ['pending', 'preparing', 'downloading', 'merging'].includes(p.status);
  if (active) {
    buttons.appendChild(mkBtn('Cancel', 'btn-danger', async () => {
      await api.invoke('cancel_download', { download_id: item.download_id });
    }));
  } else if (p.status === 'error') {
    buttons.appendChild(mkBtn('Retry', 'btn-primary', async () => {
      await api.invoke('retry_download', { download_id: item.download_id });
    }));
  }
  if (p.filepath) {
    buttons.appendChild(mkBtn('Open file', 'btn-ghost', async () => {
      await api.invoke('open_path', { path: p.filepath });
    }));
    buttons.appendChild(mkBtn('Show in folder', 'btn-ghost', async () => {
      await api.invoke('reveal_path', { path: p.filepath });
    }));
  }

  body.append(head, track, stats);
  if (p.error && p.status === 'error') {
    const err = document.createElement('div');
    err.className = 'queue-err';
    err.textContent = p.error;
    body.appendChild(err);
  }
  body.appendChild(buttons);
  card.append(img, body);
  return card;
}

$('clearQueueBtn').addEventListener('click', () => {
  for (const [id, item] of [...queueItems.entries()]) {
    if (['done', 'cancelled', 'error'].includes(item.progress.status)) {
      queueItems.delete(id);
    }
  }
  renderQueue();
  updateQueuePill();
});

$('openDownloadsBtn').addEventListener('click', async () => {
  const res = await api.invoke('get_settings', {});
  const dir = res.ok && res.result ? res.result.download_dir : '';
  await api.invoke('open_path', { path: dir || '' });
});

/* ------------------------------------------------------------------ history */
async function loadHistory() {
  const res = await api.invoke('list_history', { limit: 100 });
  const items = res.ok && res.result ? res.result.items : [];
  const list = $('historyList');
  list.innerHTML = '';
  // client-side search + status filter (real data filtering)
  const q = ($('histSearch').value || '').toLowerCase();
  const status = $('histFilter').value || '';
  const filtered = items.filter((it) => {
    if (status && it.status !== status) return false;
    if (q && !`${it.title} ${it.platform}`.toLowerCase().includes(q)) return false;
    return true;
  });
  $('historyEmpty').hidden = filtered.length > 0;
  for (const entry of filtered) {
    list.appendChild(renderHistoryRow(entry));
  }
}

function renderHistoryRow(entry) {
  const row = document.createElement('div');
  row.className = 'history-row';
  const date = entry.timestamp ? new Date(entry.timestamp * 1000) : null;
  row.innerHTML = `
    <img class="history-thumb" alt="">
    <div class="history-body">
      <div class="history-title"></div>
      <div class="history-meta"></div>
    </div>
    <div class="history-actions-row"></div>`;
  row.querySelector('.history-title').textContent = entry.title || '';
  row.querySelector('.history-meta').innerHTML =
    `<span>${entry.platform || ''}</span>` +
    `<span>${date ? date.toLocaleString() : ''}</span>` +
    `<span>${entry.quality || ''} · ${(entry.format || '').toUpperCase()}</span>` +
    `<span>${entry.filesize ? fmtSize(entry.filesize) : ''}</span>` +
    `<span class="st-${entry.status === 'completed' ? 'done' : entry.status}">${entry.status || ''}</span>`;

  const actions = row.querySelector('.history-actions-row');
  const mk = (label, fn) => {
    const b = document.createElement('button');
    b.className = 'btn btn-small btn-ghost';
    b.textContent = label;
    b.addEventListener('click', fn);
    return b;
  };
  if (entry.filepath) {
    actions.appendChild(mk('Open', async () => {
      await api.invoke('open_path', { path: entry.filepath });
    }));
    actions.appendChild(mk('Folder', async () => {
      await api.invoke('reveal_path', { path: entry.filepath });
    }));
  }
  actions.appendChild(mk('Remove', async () => {
    await api.invoke('remove_history', { id: entry.id });
    loadHistory();
  }));
  return row;
}

$('clearHistoryBtn').addEventListener('click', async () => {
  await api.invoke('clear_history', {});
  loadHistory();
});

/* ------------------------------------------------------------------ settings */
async function loadSettings() {
  const res = await api.invoke('get_settings', {});
  if (!res.ok) return;
  const s = res.result;
  $('setDownloadDir').value = s.download_dir || '';
  $('setQuality').value = s.default_quality || 'best';
  $('setFormat').value = s.preferred_format || 'mp4';
  $('setNotifications').checked = !!s.show_notifications;
  $('setUpdates').checked = !!s.check_updates;
}

$('browseDirBtn').addEventListener('click', async () => {
  const res = await api.invoke('pick_directory', { current: $('setDownloadDir').value });
  if (res.ok && res.path) $('setDownloadDir').value = res.path;
});

$('saveSettingsBtn').addEventListener('click', async () => {
  const res = await api.invoke('set_settings', {
    download_dir: $('setDownloadDir').value,
    default_quality: $('setQuality').value,
    preferred_format: $('setFormat').value,
    show_notifications: $('setNotifications').checked,
    check_updates: $('setUpdates').checked,
  });
  $('saveState').textContent = res.ok && res.result?.saved ? 'Saved ✓' : 'Save failed';
  setTimeout(() => { $('saveState').textContent = ''; }, 2500);
  await loadSystemInfo();
});

async function loadSystemInfo() {
  const res = await api.invoke('get_app_info', {});
  if (!res.ok) {
    $('diagInfo').textContent = 'Backend unavailable';
    return;
  }
  const info = res.result;
  $('diagInfo').textContent =
    `App version ${info.version}\n` +
    `yt-dlp ${info.yt_dlp}\n` +
    info.ffmpeg.replace(/FFmpeg: /, 'FFmpeg ');
  $('aboutInfo').innerHTML =
    `<div><span>Application</span><b>FOXFall</b></div>` +
    `<div><span>Version</span><b>${info.version}</b></div>` +
    `<div><span>Engine (yt-dlp)</span><b>${info.yt_dlp}</b></div>` +
    `<div><span>FFmpeg</span><b>${info.ffmpeg.includes('NOT FOUND') ? 'not found' : 'bundled ✓'}</b></div>` +
    `<div><span>Tagline</span><b>${info.tagline}</b></div>`;
  $('aboutVersion').textContent = `v${info.version}`;
  $('sidebarVer').textContent = `v${info.version}`;
  $('topbarVer').textContent = `v${info.version}`;
}

$('runDiagBtn').addEventListener('click', async () => {
  $('runDiagBtn').disabled = true;
  $('diagResults').textContent = 'Running diagnostics…';
  const res = await api.invoke('run_diagnostics', {});
  $('runDiagBtn').disabled = false;
  if (!res.ok) {
    $('diagResults').textContent = res.error || 'Diagnostics failed';
    return;
  }
  const lines = res.result.checks.map((c) =>
    `${c.ok ? '✓' : '✗'} ${c.name}${c.detail ? ' — ' + c.detail : ''}`);
  $('diagResults').innerHTML =
    lines.map((l) => l.startsWith('✓')
      ? `<span class="ok">${l}</span>` : `<span class="bad">${l}</span>`).join('\n');
});

/* ------------------------------------------------------- media tools */
let activeTool = 'inspector';
document.querySelectorAll('.tool-item').forEach((btn) => {
  btn.addEventListener('click', () => {
    if (btn.disabled) return;
    document.querySelectorAll('.tool-item').forEach((b) =>
      b.classList.toggle('active', b === btn));
    activeTool = btn.dataset.tool;
    if (activeTool === 'inspector') $('toolResult').textContent = '';
  });
});

$('toolPickBtn').addEventListener('click', async () => {
  const res = await api.invoke('pick_media_file', {});
  if (!res.ok || !res.path) return;
  $('toolResult').textContent = 'Inspecting…';
  const probe = await api.invoke('tool_probe', { path: res.path });
  if (!probe.ok) {
    $('toolResult').textContent = probe.error || 'Inspection failed';
    return;
  }
  if (probe.result.error) {
    $('toolResult').textContent = probe.result.error;
    return;
  }
  renderProbe(probe.result);
});

function renderProbe(info) {
  const rows = [
    ['Container', info.container],
    ['Duration', info.duration_text],
    ['Resolution', info.resolution],
    ['Video codec', info.vcodec],
    ['Audio codec', info.acodec],
    ['Bitrate', info.bitrate],
    ['File size', info.size_text],
    ['Streams', String(info.streams)],
  ].filter(([, v]) => v);
  $('toolResult').innerHTML = rows
    .map(([k, v]) => `${k}: <b>${v}</b>`).join('\n');
}

/* ------------------------------------------------------------------ boot */
(async function boot() {
  hydrateIcons();
  await loadSettings();
  await loadSystemInfo();
  renderDashSystem();
  // Restore any queued downloads from a previous session of this run.
  const res = await api.invoke('list_queue', {});
  if (res.ok && Array.isArray(res.result.items)) {
    for (const item of res.result.items) queueItems.set(item.download_id, item);
    renderQueue();
    updateQueuePill();
  }
  refreshDashboard();
})();
