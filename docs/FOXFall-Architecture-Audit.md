# FOXFall — Architecture Audit (Milestone 1)

Date: 2026-11-17 · Auditor: automated audit against commit `5a27560` + working tree.

## 1. Repository inventory

| Path | Purpose | Status |
|---|---|---|
| `desktop/src/main/main.cjs` | Electron main: window, IPC allowlist, logging | ✅ working |
| `desktop/src/main/backend.cjs` | Backend process manager (JSON-lines stdio, restarts) | ✅ working |
| `desktop/src/main/preload.cjs` | contextBridge (invoke/onEvent/backendStatus) | ✅ working |
| `desktop/src/renderer/{index.html,styles.css,app.js}` | Vanilla JS renderer, 5 views | ⚠️ functional but visually basic |
| `backend/server.py` | JSON-lines backend (analyze/download/queue/history/settings/diagnostics) | ✅ working |
| `core/*` | Download engine: url detection/normalization, yt-dlp engine, queue, history, settings | ✅ working |
| `utils/*` | ffmpeg locator, network diagnostics, validators, logger | ✅ working |
| `backend/foxfall-backend.spec` | PyInstaller onedir self-contained backend exe | ✅ working |
| `bin/ffmpeg/{ffmpeg,ffprobe}.exe` | bundled FFmpeg 9.0.2 | ✅ working |
| `.github/workflows/release.yml` | tag-driven desktop build + release | ✅ working |
| `desktop/tests/*` | IPC tests (node:test), E2E harnesses | ✅ 4/4 + E2E pass |
| `tests/*` | pytest suite (engine) | ✅ 122 pass |

## 2. What already works (verified in prior sessions)

- Self-contained PyInstaller backend exe; installed app boots it (`mode=standalone-exe`).
- Real analyze + download pipeline, real progress/speed/ETA via yt-dlp hooks; file verification.
- IPC success contract normalized (`{ok:true,result}` / `{ok:false,error}`).
- Diagnostics panel live-refreshes (boot-race fixed via CDP-verified regression test).
- NSIS + portable installers, fox icon embedded, no console window.
- Settings persistence, history persistence, duplicates warning, cancel/retry.

## 3. Gaps / problems

### UI/UX (primary)
- Only 5 views (Home/Queue/History/Settings/About). Missing: **Dashboard stats, Media Library, Media Tools, dedicated Downloads view**.
- Navigation is text buttons with unicode glyphs (`⌂ ⇣ ≡ ⚙`) — inconsistent icon style.
- No design tokens; colors hard-coded inline in CSS rules; spacing inconsistent.
- No empty/loading skeleton states beyond plain text lines.
- No topbar (global search / notifications / version).
- Settings panel diagnostics was stale after boot (fixed in 2.4.1, but panel itself is bare text).

### Functionality (secondary gaps vs product vision)
- Media Library: **absent** — needs indexing of real downloaded files (ffprobe metadata + thumbnails).
- Media Tools: **absent** — converter / audio extractor / metadata viewer / file inspector via FFmpeg.
- Dashboard: **absent** — no statistics or recent activity.
- Queue: no persistence across restarts; no pause/resume (yt-dlp supports resume via partial files — possible later); no reorder.
- No clipboard smart-link detection, profiles, batch import, scheduler (M9 scope).

### Packaging
- Windows ✅. Android ❌ not started (M7/M8 scope, separate project phase).

## 4. Security review

- contextIsolation: true, nodeIntegration: false, sandbox: true, CSP set in renderer ✅
- IPC allowlist (`ALLOWED_COMMANDS`) with per-command payload validation ✅
- No secrets in repo; signing not applicable (no cert) — documented ✅

## 5. Design references analysis (design-references/, 5 images)

Programmatic analysis (palette + layout maps via `tools/analyze_design.py`):

| Image | Size | Palette (dominant) | Layout reading |
|---|---|---|---|
| Dashboard.jpg | 1200×900 | #181818 (48%), #303030 (22%), orange accents ~17% | Left icon sidebar; header row; 4 KPI stat cards in a row; two-column mid-section (list left, activity right); bottom stat strip. Dark charcoal panels on near-black bg. |
| Download Manager.jpg | 2402×1440 | #000000 (44%), #181818 (36%), small blue accents | Left sidebar; top action row; table-like download list with rows of status+progress+right-side actions; right details panel. |
| Media Library.jpg | 900×506 | #000018 (22%), #000000 (14%), #181830 (11%) | Left filter rail; thumbnail grid ~4 columns with poster art; metadata rows under each tile; top search bar. |
| Media Tools.jpg | 2880×1878 | #000000 (53%), #181818 (21%) | Left tool list; large central preview/media area; right-side options panel. |
| Visual.jpg | 1544×961 | #000000 (32%), #181818 (17%) | Marketing-style composition; card grid with imagery; bottom CTA row. |

**Adopted decisions:** near-black canvas (`#111111`) with charcoal panels and 1px subtle borders; orange strictly as accent (active nav, primary buttons, progress fills, numeric highlights); sidebar with consistent icon set; card-based KPI row on Dashboard; table-style download rows with right-aligned actions; thumbnail grid for Library; tool-list + workspace split for Tools; restrained hover/transition animations.

**Rejected:** blue/purple accents seen in some references (breaks brand), poster-wall density without metadata, oversized gradient buttons.

## 6. Risk assessment

- Renderer rewrite risk: medium → mitigated by keeping `app.js` IPC layer functions intact and only restructuring DOM/CSS.
- Backend untouched: download/analysis behavior must not regress — protected by existing pytest + IPC tests.
- Library/Tools add new backend surface (ffprobe/file scan) — implement as new IPC actions, allowlisted.

## 7. Recommended milestone order

1. **M2 (this work):** design tokens + Lucide-style SVG icons + redesigned shell (7-item sidebar + topbar) + redesigned existing views (Home→Dashboard, Downloads, Queue, History, Settings, About, Diagnostics).
2. **M3 carried:** keep engine stable (regression tests).
3. **M5 next:** Media Library (index downloads dir via ffprobe; thumbnail cache).
4. **M6 next:** Media Tools (converter, audio extractor, inspector) via new backend actions.
5. **M7+:** Android (separate milestone, needs feasibility spike).
