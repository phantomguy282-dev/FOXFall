# 🦊 FOXFall 2.0

**Your videos. Your world.**

FOXFall is a **native Windows desktop application** for downloading publicly
accessible videos from YouTube, Instagram (Reels/posts) and TikTok — with an
autumn-inspired graphical interface. No terminal, no Python install, no
FFmpeg install: double-click and it works.

![FOXFall fox mascot](assets/fox-256.png)

## Highlights

- 🖥️ **Real desktop app** — Electron window with sidebar navigation
  (Home / Queue / History / Settings / About), custom fox icon, no console
- 🍂 **Autumn identity** — orange `#F28C28` / black / cream palette
- 🎬 **YouTube · Instagram · TikTok** — desktop, mobile and short-link URLs
- 📊 **Real progress** — live percentage, speed and ETA from yt-dlp hooks
  (never fabricated; unknown ETA shows "Calculating…", completed shows
  "Completed")
- 📥 **Download queue** — sequential queue with per-item state, cancel,
  retry, open file / show in folder
- 🗂️ **History** — persisted in user data, re-download, remove entries
- ⚙️ **Settings** — download folder picker, default quality/format,
  notifications, diagnostics (network, DNS, SSL, per-platform, FFmpeg)
- 🔒 **Secure & honest** — `contextIsolation` + sandboxed renderer with a
  restricted preload bridge; no telemetry; never bypasses logins, CAPTCHAs
  or paywalls

## Architecture

```
FOXFall.exe (Electron shell, no console window)
└── backend/server.py      Python child process (hidden), JSON-lines IPC
    ├── core/              yt-dlp engine: detection, normalization, queue
    ├── utils/             FFmpeg locator, network diagnostics, logging
    └── runtime/python/    embedded CPython 3.12 (no system Python needed)
bin/ffmpeg/                bundled FFmpeg + FFprobe (official gyan.dev build)
```

- Renderer ↔ main process: `contextBridge` preload, allowlisted commands only
- Main ↔ backend: newline-delimited JSON over stdio with request-id
  correlation, automatic restart (bounded) on crash, clean shutdown on quit
- User data (settings, history, downloads) lives in `%APPDATA%\FOXFall` so
  updates never erase it

## Installation

Download `FOXFall-Setup-2.0.0.exe` (or the portable `FOXFall-Portable-2.0.0.exe`)
from [Releases](https://github.com/phantomguy282-dev/FOXFall/releases) and run it.
The installer creates a Start Menu and desktop shortcut. SHA-256 checksums are
published alongside each release.

## Building from source

Requirements: Node.js 18+, Python 3.10+.

```bat
:: backend test environment
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m pytest tests

:: desktop app
cd desktop
npm install
npm start            :: dev run
npx electron-builder --win nsis portable --x64
```

FFmpeg is bundled automatically when `bin\ffmpeg\ffmpeg.exe` exists; CI
downloads it before packaging.

## Controls

Everything is mouse-first: sidebar navigation, Paste / Analyze / Clear
buttons, quality and format dropdowns, per-card Cancel / Retry / Open buttons.
Keyboard works too (Enter analyzes, Esc closes dialogs).

## Troubleshooting

| Symptom | What it means |
|---------|----------------|
| "Calculating…" for ETA | Download size unknown; ETA appears once speed is measured |
| "The platform is limiting or bot-checking this request" | Platform-side verification. Retry later. FOXFall never bypasses it |
| MP3 option unavailable | FFmpeg missing — the app bundles it; if detection fails, reinstall |
| Backend offline indicator | The Python backend crashed; FOXFall restarts it automatically (3 attempts) |

## Version

`2.0.0` — single source of truth: `foxfall_version.py` (app) and
`desktop/package.json` (desktop build).

## License

MIT. Not affiliated with YouTube, Instagram or TikTok. Only download content
that is publicly accessible and that you are authorized to download.