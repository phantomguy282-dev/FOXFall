$f = "D:\dsh-workflow\projects\FOXFall-repo\desktop\src\renderer\app.js"
$lines = [System.IO.File]::ReadAllLines($f)
# replace the notify() function (find its start/end) with toast()
$start = -1
for ($i = 0; $i -lt $lines.Length; $i++) {
  if ($lines[$i] -match "^function notify\(title, body\) \{") { $start = $i; break }
}
if ($start -lt 0) { throw "notify fn not found" }
# find the closing brace line (first line that is exactly "}")
$end = -1
for ($i = $start; $i -lt $lines.Length; $i++) {
  if ($lines[$i].Trim() -eq "}") { $end = $i; break }
}
if ($end -lt 0) { throw "end brace not found" }
$newFn = @(
  'function toast(title, body) {',
  "  \$('notifDot').hidden = false;",
  "  const area = \$('toasts');",
  '  if (!area) return;',
  "  const t = document.createElement('div');",
  "  t.className = 'toast';",
  "  const strong = document.createElement('strong');",
  '  strong.textContent = title;',
  "  const bodyEl = document.createElement('div');",
  "  bodyEl.textContent = body || '';",
  '  t.append(strong, bodyEl);',
  '  area.appendChild(t);',
  '  setTimeout(() => t.remove(), 6000);',
  '}'
)
$all = @()
$all += $lines[0..($start-1)]
$all += $newFn
$all += $lines[($end+1)..($lines.Length-1)]
[System.IO.File]::WriteAllLines($f, $all)
"notify -> toast replaced (lines $start..$end)"
