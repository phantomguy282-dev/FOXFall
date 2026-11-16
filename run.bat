@echo off
setlocal EnableDelayedExpansion
title FOXFall Launcher
cd /d "%~dp0"

rem ---------------------------------------------------------------
rem FOXFall launcher: check python, create venv, install deps,
rem verify ffmpeg, then start the app. Keeps window open on errors.
rem ---------------------------------------------------------------

echo.
echo  [..] Checking Python installation...

where python >nul 2>nul
if errorlevel 1 (
    echo  [x] Python was not found on this system.
    echo  [!] Install Python 3.10+ from https://www.python.org/downloads/
    echo      and enable "Add python.exe to PATH" during setup.
    goto :fail
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo  [OK] Python !PYVER! found.

rem --- virtual environment ------------------------------------------------
if not exist ".venv\Scripts\python.exe" (
    echo  [..] Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo  [x] Failed to create virtual environment.
        goto :fail
    )
    echo  [OK] Virtual environment created.
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo  [x] Could not activate the virtual environment.
    goto :fail
)

rem --- dependencies (only when missing) -----------------------------------
python -c "import yt_dlp" >nul 2>nul
if errorlevel 1 (
    echo  [..] Installing dependencies ^(first run only^)...
    python -m pip install --upgrade pip >nul 2>nul
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo  [x] Dependency installation failed.
        goto :fail
    )
    echo  [OK] Dependencies installed.
) else (
    echo  [OK] Dependencies already installed.
)

rem --- ffmpeg check: bundled bin\ffmpeg first, then PATH -------------------
if exist "bin\ffmpeg\ffmpeg.exe" (
    echo  [OK] FFmpeg found in bin\ffmpeg.
) else (
    where ffmpeg >nul 2>nul
    if errorlevel 1 (
        echo  [!] FFmpeg not found. Run Diagnostics ^(option 5^) inside
        echo      FOXFall for one-click automatic repair.
    ) else (
        echo  [OK] FFmpeg found on PATH.
    )
)

rem --- launch --------------------------------------------------------------
echo  [OK] Launching FOXFall...
python main.py
if errorlevel 1 goto :fail
goto :end

:fail
echo.
echo  [x] FOXFall could not start. Press any key to close this window.
pause >nul
exit /b 1

:end
endlocal
