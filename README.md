# 🦊 FOXFall

**Your videos. Your world.**

FOXFall is a free, open-source video downloader for **Windows 10 / 11** with a
distinctive autumn-inspired terminal interface. Download publicly accessible
videos from **YouTube**, **Instagram** (Reels and public video posts) and
**TikTok** — desktop and mobile URLs alike.

![FOXFall fox mascot](assets/fox-256.png)

## Features

- 🍂 **Autumn identity** — fox mascot, orange/black/cream palette, animated
  startup with a falling-leaf gradient
- 🎬 **Multi-platform** — YouTube (watch, Shorts, youtu.be, music), Instagram
  Reels & posts, TikTok (desktop, `vm.`/`vt.` short links, mobile)
- 🔗 **Smart URL handling** — platform auto-detection, safe short-link
  resolution, tracking-parameter stripping that never removes identity params
- 🎚️ **Honest quality lists** — only what the source actually offers
  (2160p → 360p), never a promised resolution that doesn't exist
- 🎧 **MP3 extraction** — bundled FFmpeg, zero manual installs
- 📥 **Download queue** — sequential downloads, cancel, retry, duplicate
  detection, live speed and ETA
- 🗂️ **Download history** — persisted locally, clearable
- 🩺 **Diagnostics screen** — internet, DNS, SSL, per-platform connectivity,
  yt-dlp and FFmpeg checks with truthful error classification
- ⌨️ **Keyboard-first** — arrows navigate, Enter confirms, Esc goes back,
  `Q` quits with confirmation
- 📐 **Responsive** — redraws on terminal resize, works from small windows to
  fullscreen
- 🔒 **No telemetry, no accounts, no bypasses** — private/paywalled/DRM content
  is never accessed

## Supported platforms

| Platform | Accepted URL forms |
|----------|--------------------|
| YouTube | `youtube.com/watch?v=`, `youtu.be/`, `/shorts/`, `m.youtube.com`, `music.youtube.com`, `youtube-nocookie.com` |
| Instagram | `instagram.com/reel/`, `/p/`, `/reels/`, `m.instagram.com`, `instagr.am`, links with tracking params |
| TikTok | `tiktok.com/@user/video/`, `m.tiktok.com/v/<id>.html`, `vm.tiktok.com/`, `vt.tiktok.com/`, `tiktok.com/t/` |

## Installation

### Option A — portable executable (recommended)

1. Download `FOXFall-windows-portable.zip` from
   [Releases](https://github.com/phantomguy282-dev/FOXFall/releases).
2. Extract anywhere.
3. Run `FOXFall.exe`. No Python needed — FFmpeg is bundled.

### Option B — from source

```bat
git clone https://github.com/phantomguy282-dev/FOXFall.git
cd FOXFall
run.bat
```

`run.bat` detects Python (3.10+), creates `.venv`, installs dependencies once,
verifies FFmpeg and starts the app.

Manual equivalent:

```bat
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python main.py
```

## Building from source

```bat
build_exe.bat
```

or directly:

```bat
.venv\Scripts\pip install pyinstaller
.venv\Scripts\python -m PyInstaller foxfall.spec --noconfirm
```

Output: `dist\FOXFall\FOXFall.exe` (with `bin\ffmpeg` bundled).

## FFmpeg

FOXFall ships a portable FFmpeg build in `bin\ffmpeg\ffmpeg.exe` + `ffprobe.exe`
(official [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) essentials build).

- Detected automatically at startup (bundled → PATH → common install dirs).
- If missing, open **Diagnostics (5)** and use the automatic repair option.
- FFmpeg is required for MP3 extraction and merging high-resolution streams
  (1080p+ on YouTube). Without it, FOXFall falls back to single-format
  downloads and tells you.

## Controls

| Key | Action |
|-----|--------|
| ↑ / ↓ | navigate lists |
| ← / → | change setting value / container format |
| 1-3 | platform quick-pick |
| 4 | Settings |
| 5 | Diagnostics |
| Enter | confirm |
| Q | quit (asks for confirmation) |
| Esc | back |
| C | cancel active download |
| R | retry failed download |
| X | clear history (history screen) |

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| "Sign in to confirm you're not a bot" | Platform-side bot check. Wait, retry, or update yt-dlp. FOXFall never solves CAPTCHAs. |
| TikTok "Unexpected response" | Update yt-dlp and make sure `curl_cffi` is installed (browser impersonation). |
| MP3 option refuses to start | FFmpeg not detected — run Diagnostics → repair. |
| Downloads fail with HTTP 403/429 | Rate limited or restricted; report classified in the diagnostics log at `logs\foxfall.log`. |
| Nothing renders / garbled box chars | Use Windows Terminal with **Cascadia Code** (ships with Windows 11). |

## Version

`1.0.0` — single source of truth in `foxfall_version.py`.

## License

MIT. FOXFall is not affiliated with YouTube, Instagram or TikTok. Only download
content you are authorized to download and that is publicly accessible.