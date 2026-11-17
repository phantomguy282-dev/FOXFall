# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec: self-contained FOXFall backend.

Produces backend/foxfall-backend/ (onedir) containing foxfall-backend.exe
plus all Python dependencies (yt-dlp, curl_cffi, etc.). The exe speaks the
same JSON-lines stdio protocol as backend/server.py and needs no system
Python, no pip packages, and no development repository.
"""
import os

ROOT = os.path.dirname(os.path.abspath(SPEC))

a = Analysis(
    [os.path.join(ROOT, "server.py")],
    pathex=[ROOT],
    binaries=[],
    datas=[],
    hiddenimports=[
        "yt_dlp",
        "yt_dlp.extractor",
        "curl_cffi",
        "curl_cffi.requests",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter", "matplotlib", "numpy", "pandas", "PyQt5", "PyQt6",
        "pytest", "PIL.ImageQt",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="foxfall-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,          # stdio protocol process; hidden by parent (windowsHide)
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="foxfall-backend",
)
