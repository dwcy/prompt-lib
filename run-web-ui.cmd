@echo off
REM Root launcher for the Cabal read-only web UI.

setlocal
set "SCRIPT_DIR=%~dp0"

if not defined CABAL_WEB_HOST set "CABAL_WEB_HOST=127.0.0.1"
if not defined CABAL_WEB_PORT set "CABAL_WEB_PORT=8765"
if not defined CABAL_WEB_PROJECT set "CABAL_WEB_PROJECT=."

pushd "%SCRIPT_DIR%" >nul

where uv >nul 2>nul
if errorlevel 1 goto :run_python

uv run python -m cabal.web --host "%CABAL_WEB_HOST%" --port "%CABAL_WEB_PORT%" --project "%CABAL_WEB_PROJECT%" %*
set "EXIT_CODE=%ERRORLEVEL%"
goto :end

:run_python
python -m cabal.web --host "%CABAL_WEB_HOST%" --port "%CABAL_WEB_PORT%" --project "%CABAL_WEB_PROJECT%" %*
set "EXIT_CODE=%ERRORLEVEL%"

:end
popd >nul
exit /b %EXIT_CODE%
