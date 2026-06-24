@echo off
REM Root launcher for the settings configurator.

setlocal
set "SCRIPT_DIR=%~dp0"

call "%SCRIPT_DIR%setup\settings-configurator-ui.cmd" %*
exit /b %ERRORLEVEL%
