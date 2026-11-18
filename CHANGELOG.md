# FOXFall — Changelog

All notable changes to FOXFall. Format follows Keep a Changelog.
Versioning follows Semantic Versioning.

> **Release policy:** FOXFall follows a controlled single-release strategy.
> Development milestones do **not** produce public releases. Internal version
> is `0.9.0-dev` until the official **FOXFall 1.0.0** release criteria are met.
> After 1.0.0: PATCH = fixes, MINOR = features, MAJOR = architectural change.

---

## [Unreleased] — targeting FOXFall 1.0.0

### Release criteria (all must be verified before publishing 1.0.0)
- [x] M5 — Media Library indexing complete (FFprobe metadata, thumbnail cache,
      persistence, rescan, no duplicates, graceful missing-file handling)
- [x] M6 — Media Tools complete (Video Converter, Audio Extractor,
      Thumbnail Generator) with real progress, cancellation, error handling
- [x] Final Dashboard (persistent recent activity via history, navigation, states)
- [ ] Complete automated suite green + real integration tests
- [ ] Clean-Windows install/startup/uninstall verified
- [ ] Backend availability + FFmpeg/FFprobe packaging verified
- [ ] Real authorized downloads verified on supported platforms
- [ ] SHA-256 checksums, release notes, changelog
- Android is deferred to **FOXFall 1.1.0**

### Changed — release process
- CI no longer publishes on git tag push; the workflow is manual and only
  attaches installers to a clearly-labelled **internal test pre-release**.
- Internal version moved to `0.9.0-dev` (development builds are never
  labelled 1.0.0).
- v2.x GitHub releases are converted to **pre-releases** and marked as
  internal development builds, not official releases.

### Added — M5/M6 groundwork
- `docs/1.0.0-implementation-plan.md` — phased implementation plan.

---

## [2.5.0] — 2026-11-17 (internal development build)

### Added
- **Design system**: `tokens.css` (official palette, spacing, radius, shadow,
  typography, motion tokens incl. `prefers-reduced-motion`), `icons.js`
  (consistent Lucide-derived SVG icon set, no external dependency).
- **New application shell**: sidebar with 8 destinations (Dashboard, Downloads,
  Queue, Media Library, Media Tools, History, Settings, About) and a topbar
  with global search (filters history), notification center and version.
- **Dashboard**: KPI cards (completed, active, failed, total size, current
  speed) computed from real queue/history data; recent activity with open /
  show-in-folder actions; quick actions; live system status from the backend
  (backend version, yt-dlp, FFmpeg, FFprobe).
- **Media Tools → File Inspector**: real FFprobe inspection of any local media
  file (container, duration, resolution, codecs, bitrate, size, streams) with a
  native file picker.
- **History**: search and status filtering over real entries.
- **Media Library**: Rescan lists real completed downloads; honest empty state
  (full indexing planned in M5).
- Toast notifications; global search wired to history.
- `docs/FOXFall-Architecture-Audit.md`, `docs/FOXFall-Development-Roadmap.md`,
  `tools/analyze_design.py`, `tools/validate_sitemap.py`.

### Fixed
- Broken-image indicator on the empty analysis thumbnail.

---

## [2.4.1] — 2026-11-17 (internal development build)

### Fixed
- **Root cause of "Backend unavailable" / "Analysis failed"**: the IPC handler
  unwrapped backend responses, while the renderer required `{ok:true, result}`.
  Every *successful* backend response was therefore treated as a failure.
  Responses are now normalized in one place.
- Diagnostics panel no longer freezes at its boot-time state: it refreshes on
  the backend `ready` event and whenever Settings is opened.
- "IP address is blocked" errors are classified as `forbidden` with a clear
  message.

---

## [2.3.0] — 2026-11-16 (internal development build)

### Changed
- Backend is now a **self-contained PyInstaller executable**
  (`backend/foxfall-backend/`), bundling Python, yt-dlp and curl_cffi — no
  system Python, pip packages or development repository required.
- Backend resolution tries, in order: standalone exe → embedded runtime →
  `FOXFall_PYTHON` override → dev venv, each verified before use.
- Diagnostic logging to `%APPDATA%\FOXFall\logs\backend-YYYY-MM-DD.log`.

---

## [2.2.0] — 2026-11-16 (internal development build)

### Fixed
- Packaged-app path resolution (`process.resourcesPath`), backend startup
  diagnostics surfaced to the UI.
- Renderer image paths; supplied `desktop-icon.png` converted to a
  multi-resolution `.ico` and embedded via an `afterPack` rcedit hook;
  `icon.png` used for in-app icons.

---

## [2.1.0] / [2.0.0] / [1.0.0] — 2026-11-16 (internal development builds)

- Electron desktop application introduced (window, sidebar, IPC, Python
  backend), replacing the terminal-only UI.
- Download engine repairs: queue no longer rebuilds the downloader without the
  FFmpeg path; completion resolves the real output file (intermediate
  `.fNNN` files excluded); resilient format-selector fallbacks; metadata
  cached between Analyze and Download.
- ETA/progress: yt-dlp `eta` preferred, else `remaining/speed`, else
  "Calculating…"; "Completed" on finish. No fabricated progress.
- TikTok: canonicalization of short/username-less URLs; `curl_cffi`
  impersonation support fixing WAF failures.
- Error classification: dns / ssl / captcha / rate_limit / forbidden /
  outdated_extractor / private / unsupported / redirect / http / timeout /
  disk / ffmpeg.
- FFmpeg 9.0.2 bundled; frozen-path detection for all layouts.
- NSIS installer + portable build; release automation; SHA-256 checksums.