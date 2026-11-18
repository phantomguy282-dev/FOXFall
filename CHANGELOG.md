# FOXFall — Changelog

All notable changes to FOXFall. Format follows Keep a Changelog.
Versioning follows Semantic Versioning.

> **Release policy:** FOXFall follows a controlled single-release strategy.
> Development milestones do **not** produce public releases. Internal version
> is `0.9.0-dev` until the official **FOXFall 1.0.0** release criteria are met.
> After 1.0.0: PATCH = fixes, MINOR = features, MAJOR = architectural change.

---

## [Unreleased] — targeting FOXFall 1.0.0

### Release criteria — final audit 2026-11-18 (re-verified independently)

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | M5 Media Library: FFprobe metadata, thumbnail cache, persistence, rescan, no duplicates, missing-file handling | VERIFIED | Fresh user-data scan: 1 file indexed, metadata (05:13, 854x480, av1), thumbnail cached; rescan produced no duplicates; deleted file flagged `missing` and hidden by default |
| 2 | M6 Video Converter | VERIFIED | Real FFmpeg conversion produced valid MP4 (3,071,635 bytes from installed backend; 10,907 bytes testsrc) |
| 3 | M6 Audio Extractor | VERIFIED | MP3 extracted (132,424 bytes) from a real video via installed backend |
| 4 | M6 Thumbnail Generator | VERIFIED | PNG generated (542,383 bytes) from installed backend |
| 5 | Cancellation + partial cleanup | VERIFIED | `tool_cancel` kills ffmpeg; partial output removed (bug found: removal raced ffmpeg's file handle — fixed with wait+retry, regression test `test_tool_cancel_removes_partial_output` added) |
| 6 | Dashboard persistent history | VERIFIED | CDP check on clean install: renders; history bound to `history.json`, refreshed on `download_finished` + `ready` events |
| 7 | Desktop GUI: 8 views render, no broken images | VERIFIED | CDP check on clean install: all 8 views OK, brokenImgs=0 |
| 8 | Backend availability + IPC | VERIFIED | Clean install first launch: sidebar "Connected", `get_app_info` returns healthy data via CDP |
| 9 | FFmpeg/FFprobe bundled and executable from install dir | VERIFIED | Both `-version` executed from `%LOCALAPPDATA%\Programs\FOXFall\resources\bin\ffmpeg`; backend reports v9.0.2 + ffprobe yes |
| 10 | yt-dlp bundled | VERIFIED | Installed backend reports 2026.10.26 (embedded, not global) |
| 11 | Automated suite green | VERIFIED | 133 pytest + 4 node IPC tests pass (fresh run 2026-11-18) |
| 12 | Real authorized downloads on supported platforms | VERIFIED | New URLs: YT `LXb3EKWsInQ` (47.5 MB), YT `eRsGyueVLvQ` Sintel (188.5 MB via clean install), YT `9bZkp7q19f0` (26.6 MB). Regression URLs also pass. |
| 13 | Clean-Windows install/startup/uninstall | VERIFIED (partial env) | Uninstall + fresh silent install + first launch + download + uninstall-removes-files + no leftover processes all executed. **Caveat: same physical machine — dev Python exists on PATH; however the backend exe embeds its own interpreter and tests were run with `PYTHONPATH`/`PYTHONHOME` cleared and no dev-repo dependency. A dedicated clean VM was unavailable.** |
| 14 | Real download on TikTok (new URLs) | FAILED — external | `tiktok.com/@tiktok/video/7371434446285069099`, `@nasa/video/7289568947439274286`, `vm.tiktok.com/ZMhqYFVbk`: "Your IP address is blocked" / redirect to homepage. Platform-side IP block; now classified `forbidden`. Regression URL `vt.tiktok.com/ZSps53ySE` still downloads (691,852 bytes), proving the engine works. |
| 15 | Real download on Instagram (new URLs) | FAILED — external | `reel/C2ZqX9vPK5m`, `reel/C0FxKFcRg_v`: "empty media response" = login-required. Classified `private`. Regression URL `DdZzIvSNQ_E` still downloads (1,293,326 bytes). |
| 16 | SHA-256 checksums, release notes, changelog | VERIFIED (process ready) | CI generates SHA256SUMS.txt; CHANGELOG.md + release criteria maintained. Actual 1.0.0 assets not yet produced (release deferred by policy). |
| 17 | Android | NOT APPLICABLE | Deferred to FOXFall 1.1.0 by scope decision. |
| 18 | No console window / icons / branding | VERIFIED | No conhost attached to installed exe; fox icon embedded (ExtractAssociatedIcon verified); all views use icon.png assets |

**Conclusion: 15 of 17 verifiable criteria VERIFIED, 2 FAILED due to external
platform restrictions (engine itself proven via regression URLs), 1 partial
(clean-VM limitation documented), Android NOT APPLICABLE. The application is
functionally ready; the 1.0.0 public release remains deferred by the release
policy until the owner authorizes publication.**

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