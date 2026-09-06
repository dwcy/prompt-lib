@echo off
REM Start the Cabal backend and browser UI together.

setlocal
set "SCRIPT_DIR=%~dp0"

where pwsh >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    pwsh -NoProfile -File "%SCRIPT_DIR%run-web.ps1" %*
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%run-web.ps1" %*
)
exit /b %ERRORLEVEL%
