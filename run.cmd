@echo off
REM Root launcher for the settings configurator and graphical workspaces.

setlocal
set "SCRIPT_DIR=%~dp0"

if /I "%~1"=="web" goto :run_app
if /I "%~1"=="tauri" goto :run_app

call "%SCRIPT_DIR%setup\settings-configurator-ui.cmd" %*
exit /b %ERRORLEVEL%

:run_app
where pwsh >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    pwsh -NoProfile -File "%SCRIPT_DIR%run.ps1" %*
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%run.ps1" %*
)
exit /b %ERRORLEVEL%
