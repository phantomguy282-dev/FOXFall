# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for FOXFall (Windows one-file-ish onedir build with icon)."""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(SPEC))

block_cipher = None

datas = [
    (os.path.join(ROOT, "config", "settings.json"), "config"),
    (os.path.join(ROOT, "assets", "foxfall.ico"), "assets"),
]
# Bundle FFmpeg so the packaged app needs no manual install.
ffmpeg_bin = os.path.join(ROOT, "bin", "ffmpeg")
if os.path.isdir(ffmpeg_bin):
    datas.append((ffmpeg_bin, os.path.join("bin", "ffmpeg")))

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "yt_dlp.extractor",
        "yt_dlp.compat",
        "curl_cffi",
        "curl_cffi.requests",
        "rich",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "pandas", "PIL.ImageQt"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FOXFall",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    icon=os.path.join(ROOT, "assets", "foxfall.ico"),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="FOXFall",
)