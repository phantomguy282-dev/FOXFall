# FOXFall — Development Roadmap

Dependencies are noted; a milestone may not start before its dependencies are complete.

| # | Milestone | Depends on | Status |
|---|---|---|---|
| M1 | Repository audit + design-reference analysis | — | ✅ complete (`docs/FOXFall-Architecture-Audit.md`) |
| M2 | Design foundation: tokens, icons, shell, screen redesign | M1 | ✅ this release — tokens `desktop/src/renderer/tokens.css`, icons `icons.js`, shell redesign |
| M3 | Core stability: backend/IPC/packaging/download verification | — | ✅ complete (v2.3.0–2.4.1) |
| M4 | Desktop experience: Dashboard, Downloads, Queue, Preview, Quality, History, Settings | M2 | ✅ this release (Dashboard/Downloads/Queue/History/Settings/Diagnostics) |
| M5 | Media Library: indexing, thumbnails, search, filters, favorites | M2, M4 | ⏳ planned — requires backend actions `library_scan`, `library_thumb` (ffprobe/ffmpeg) |
| M6 | Media Tools: converter, audio extractor, metadata viewer, inspector, batch | M2, M4, M5 | ⏳ planned — requires backend actions `tool_convert`, `tool_extract_audio`, `tool_probe` |
| M7 | Android foundation: feasibility spike, mobile design system, shell | M2 | ⏳ not started |
| M8 | Android APK: download engine, notifications, library, signing | M7 | ⏳ not started |
| M9 | Advanced: clipboard detection, profiles, batch import, playlists, scheduler | M5 | ⏳ not started |
| M10 | Final polish, accessibility, docs, release | all | ⏳ not started |

## M2/M4 scope delivered in this change set

- Design tokens (color/space/radius/shadow/type scale) in `tokens.css`.
- Consistent inline-SVG icon set (Lucide-derived paths) in `icons.js` — no external dependency.
- Application shell: sidebar (Dashboard, Downloads, Queue, Media Library, Media Tools, History, Settings, About) + topbar (global search, notifications, version).
- Screens: **Dashboard** (KPI cards from real history/queue data, recent activity, quick actions, system status), **Downloads** (link analysis + preview + quality/format + start), **Queue** (real progress cards + actions), **Media Library** (empty state + indexing explained; live in M5), **Media Tools** (real FFprobe metadata viewer available now; converter/extractor marked M6), **History** (search/filter), **Settings**, **About**, **System Diagnostics**.
- All data flows through existing IPC; no fake data, no dead buttons (unavailable features are visibly labelled "planned" and disabled).