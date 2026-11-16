@echo off
rem ---------------------------------------------------------------
rem build_exe.bat - create a standalone Windows executable with
rem PyInstaller. Output lands in dist\foxfall\.
rem ---------------------------------------------------------------
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo  [x] Run run.bat first to create the virtual environment.
    pause
    exit /b 1
)
call ".venv\Scripts\activate.bat"

python -c "import PyInstaller" >nul 2>nul
if errorlevel 1 (
    echo  [..] Installing PyInstaller...
    python -m pip install pyinstaller
    if errorlevel 1 (
        echo  [x] PyInstaller installation failed.
        pause
        exit /b 1
    )
)

echo  [..] Building executable...
python -m PyInstaller --name foxfall --onedir --console ^
    --add-data "config;config" ^
    --hidden-import yt_dlp.extractor ^
    main.py
if errorlevel 1 (
    echo  [x] Build failed.
    pause
    exit /b 1
)

echo  [OK] Built: dist\foxfall\foxfall.exe
echo      FFmpeg is NOT bundled - copy ffmpeg.exe next to the exe for full support.
pause
