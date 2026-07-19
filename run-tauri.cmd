@echo off
REM Start the Cabal Tauri desktop development shell.

setlocal
set "SCRIPT_DIR=%~dp0"

cd /d "%SCRIPT_DIR%apps\cabal-desktop" || exit /b 1
call pnpm tauri dev %*
exit /b %ERRORLEVEL%
