Set-Location D:\dsh-workflow\projects\FOXFall-repo
$srcPath = "desktop\src\renderer\app.js"
$src = [System.IO.File]::ReadAllText((Resolve-Path $srcPath))

# locate the exact old block boundaries by markers
$startMarker = "/* library rescan: real action (re-lists downloads into grid via history) */"
$endMarker = "/* ------------------------------------------------------------------ helpers */"
$startIdx = $src.IndexOf($startMarker)
$endIdx = $src.IndexOf($endMarker)
if ($startIdx -lt 0 -or $endIdx -lt 0 -or $endIdx -le $startIdx) { throw "markers not found: $startIdx..$endIdx" }

$new = @'
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
  meta.textContent = bits.join(' · ');
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
  $('libScanStatus').textContent = 'Indexing…';
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
        result.cancelled ? 'Scan cancelled — resumable' : '');
  loadLibrary();
}

$('libSearch').addEventListener('input', () => loadLibrary());
$('libSort').addEventListener('change', () => loadLibrary());
$('libFavOnly').addEventListener('click', () => {
  libFavoritesOnly = !libFavoritesOnly;
  $('libFavOnly').classList.toggle('btn-primary', libFavoritesOnly);
  loadLibrary();
});

/* ---------- Media Tools: real FFmpeg operations ---------- */
let activeTool = 'inspector';
let currentOpId = null;

document.querySelectorAll('.tool-item').forEach((btn) => {
  btn.addEventListener('click', () => {
    if (btn.disabled) return;
    document.querySelectorAll('.tool-item').forEach((b) =>
      b.classList.toggle('active', b === btn));
    activeTool = btn.dataset.tool;
    $('toolTitle').textContent =
      btn.textContent.replace('planned', '').trim();
    $('toolInspector').hidden = activeTool !== 'inspector';
    $('toolConvert').hidden = activeTool !== 'convert';
    $('toolAudio').hidden = activeTool !== 'audio';
    $('toolThumb').hidden = activeTool !== 'thumb';
  });
});

async function pickMediaFile(target) {
  const res = await api.invoke('pick_media_file', {});
  if (res.ok && res.path) target.value = res.path;
}
async function pickOutputDir(target) {
  const res = await api.invoke('pick_directory', {});
  if (res.ok && res.path) target.value = res.path;
}

$('convPickInput').addEventListener('click', () => pickMediaFile($('convInput')));
$('convPickOutput').addEventListener('click', () => pickOutputDir($('convOutput')));
$('audPickInput').addEventListener('click', () => pickMediaFile($('audInput')));
$('audPickOutput').addEventListener('click', () => pickOutputDir($('audOutput')));
$('thPickInput').addEventListener('click', () => pickMediaFile($('thInput')));
$('thPickOutput').addEventListener('click', () => pickOutputDir($('thOutput')));

function updateToolProgress(opId, pct) {
  if (currentOpId !== opId) return;
  const track = activeTool === 'audio' ? $('audTrack') : $('convTrack');
  const fill = activeTool === 'audio' ? $('audFill') : $('convFill');
  track.hidden = false;
  fill.style.width = `${pct}%`;
}

function finishTool(event) {
  if (currentOpId !== event.operation_id) return;
  currentOpId = null;
  const status = activeTool === 'audio' ? $('audStatus') : $('convStatus');
  if (event.ok) {
    status.innerHTML = `<span class="ok">✓ Completed: ${event.output}</span>`;
    toast('Tool finished', event.output);
  } else {
    status.innerHTML = `<span class="bad">✗ ${event.error}</span>`;
  }
  $('convCancel').hidden = true;
  $('audCancel').hidden = true;
}

$('convStart').addEventListener('click', async () => {
  const input = $('convInput').value, out = $('convOutput').value;
  if (!input || !out) {
    $('convStatus').textContent = 'Choose input and destination first.';
    return;
  }
  const name = input.split(/[\\/]/).pop().replace(/\.[^.]+$/, '') + '.mp4';
  const res = await api.invoke('tool_convert_start', {
    input, output: out.endsWith(name) ? out : out + '\\' + name,
    vcodec: 'libx264',
  });
  if (!res.ok || res.result.error) {
    $('convStatus').textContent = res.result?.error || res.error || 'Failed to start';
    return;
  }
  currentOpId = res.result.operation_id;
  $('convStatus').textContent = 'Converting…';
  $('convCancel').hidden = false;
});
$('convCancel').addEventListener('click', async () => {
  if (currentOpId) await api.invoke('tool_cancel', { operation_id: currentOpId });
});

$('audStart').addEventListener('click', async () => {
  const input = $('audInput').value, out = $('audOutput').value;
  const fmt = $('audFormat').value;
  if (!input || !out) {
    $('audStatus').textContent = 'Choose input and destination first.';
    return;
  }
  const name = input.split(/[\\/]/).pop().replace(/\.[^.]+$/, '') + '.' + fmt;
  const res = await api.invoke('tool_extract_start', {
    input, output: out + '\\' + name, format: fmt,
  });
  if (!res.ok || res.result.error) {
    $('audStatus').textContent = res.result?.error || res.error || 'Failed to start';
    return;
  }
  currentOpId = res.result.operation_id;
  $('audStatus').textContent = 'Extracting…';
  $('audCancel').hidden = false;
});
$('audCancel').addEventListener('click', async () => {
  if (currentOpId) await api.invoke('tool_cancel', { operation_id: currentOpId });
});

$('thStart').addEventListener('click', async () => {
  const input = $('thInput').value, out = $('thOutput').value;
  const fmt = $('thFormat').value;
  const ts = parseFloat($('thTimestamp').value || '1');
  if (!input || !out) {
    $('thStatus').textContent = 'Choose input and destination first.';
    return;
  }
  if (Number.isNaN(ts)) {
    $('thStatus').textContent = 'Invalid timestamp.';
    return;
  }
  const name = input.split(/[\\/]/).pop().replace(/\.[^.]+$/, '') + '.' + fmt;
  const res = await api.invoke('tool_thumbnail', {
    input, output: out + '\\' + name, timestamp: ts,
  });
  if (!res.ok || res.result.error) {
    $('thStatus').textContent = res.result?.error || res.error || 'Failed';
    return;
  }
  $('thStatus').innerHTML =
    `<span class="ok">✓ Generated: ${res.result.output} (${fmtSize(res.result.size)})</span>`;
});

'@

$src = $src.Remove($startIdx, $endIdx - $startIdx).Insert($startIdx, $new)
[System.IO.File]::WriteAllText((Resolve-Path $srcPath), $src)
"replaced OK"