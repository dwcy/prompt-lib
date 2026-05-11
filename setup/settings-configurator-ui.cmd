@echo off
REM settings-configurator-ui.cmd — Windows convenience launcher for settings-configurator-ui.py
REM Resolves Python (py launcher preferred, then python) and runs the wizard.

setlocal

set "SCRIPT_DIR=%~dp0"

where py >nul 2>nul
if %ERRORLEVEL%==0 (
    py "%SCRIPT_DIR%settings-configurator-ui.py" %*
    goto :end
)

where python >nul 2>nul
if %ERRORLEVEL%==0 (
    python "%SCRIPT_DIR%settings-configurator-ui.py" %*
    goto :end
)

echo Python not found. Install Python 3.10+ from https://www.python.org/downloads/ or via winget:
echo   winget install Python.Python.3.12
exit /b 1

:end
endlocal
