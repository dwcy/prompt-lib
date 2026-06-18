@echo off
REM settings-configurator-ui.cmd - Windows convenience launcher for settings-configurator-ui.py
REM Resolves Python, offers winget install when Python is missing, and runs the wizard.

setlocal

set "SCRIPT_DIR=%~dp0"
set "PYTHON_EXE="
set "PYTHON_ARGS="

call :find_python
if defined PYTHON_EXE goto :run_app

echo Python was not found. This wizard requires Python 3.11 or newer.

where winget >nul 2>nul
if not %ERRORLEVEL%==0 (
    echo winget was not found, so Python cannot be installed automatically.
    echo Install Python manually from https://www.python.org/downloads/ and run this launcher again.
    echo Cannot continue without Python.
    exit /b 1
)

echo Checking latest Python version available from winget...
set "PYTHON_LATEST="
for /f "tokens=2,*" %%A in ('winget show --id Python.Python.3 --exact 2^>nul ^| findstr /B /C:"Version:"') do set "PYTHON_LATEST=%%A"
if defined PYTHON_LATEST (
    echo Latest Python available from winget: %PYTHON_LATEST%
) else (
    echo Latest Python available from winget: latest Python 3 package candidate
)

choice /C YN /M "Install Python now with winget"
if errorlevel 2 (
    echo Cannot continue without Python.
    exit /b 1
)

winget install --id Python.Python.3 --exact --accept-source-agreements --accept-package-agreements
if not %ERRORLEVEL%==0 (
    echo Python installation failed or was cancelled.
    echo Cannot continue without Python.
    exit /b 1
)

call :find_python
if not defined PYTHON_EXE (
    echo Python installed, but this terminal cannot find it yet.
    echo Open a new terminal and run this launcher again.
    echo Cannot continue without Python.
    exit /b 1
)

:run_app
"%PYTHON_EXE%" %PYTHON_ARGS% "%SCRIPT_DIR%settings-configurator-ui.py" %*
goto :end

:find_python
py -3 -c "import sys; raise SystemExit(sys.version_info < (3, 11))" >nul 2>nul
if %ERRORLEVEL%==0 (
    set "PYTHON_EXE=py"
    set "PYTHON_ARGS=-3"
    exit /b 0
)

python -c "import sys; raise SystemExit(sys.version_info < (3, 11))" >nul 2>nul
if %ERRORLEVEL%==0 (
    set "PYTHON_EXE=python"
    set "PYTHON_ARGS="
    exit /b 0
)

for /f "delims=" %%P in ('dir /b /ad "%LOCALAPPDATA%\Programs\Python\Python*" 2^>nul') do (
    if exist "%LOCALAPPDATA%\Programs\Python\%%P\python.exe" (
        "%LOCALAPPDATA%\Programs\Python\%%P\python.exe" -c "import sys; raise SystemExit(sys.version_info < (3, 11))" >nul 2>nul
        if not errorlevel 1 (
            set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\%%P\python.exe"
            set "PYTHON_ARGS="
            exit /b 0
        )
    )
)

for /f "delims=" %%P in ('dir /b /ad "%ProgramFiles%\Python*" 2^>nul') do (
    if exist "%ProgramFiles%\%%P\python.exe" (
        "%ProgramFiles%\%%P\python.exe" -c "import sys; raise SystemExit(sys.version_info < (3, 11))" >nul 2>nul
        if not errorlevel 1 (
            set "PYTHON_EXE=%ProgramFiles%\%%P\python.exe"
            set "PYTHON_ARGS="
            exit /b 0
        )
    )
)

exit /b 1

:end
endlocal
