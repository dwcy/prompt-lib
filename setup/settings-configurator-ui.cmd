@echo off
REM settings-configurator-ui.cmd - Windows convenience launcher for settings-configurator-ui.py
REM Resolves Python, offers winget install when Python is missing, and runs the wizard.

setlocal

set "SCRIPT_DIR=%~dp0"
set "PYTHON_EXE="
set "PYTHON_ARGS="
set "PYTHON_WINGET_ID="
set "PYTHON_WINGET_VERSION="
set "DETECTED_ARCH=%PROCESSOR_ARCHITEW6432%"
if not defined DETECTED_ARCH set "DETECTED_ARCH=%PROCESSOR_ARCHITECTURE%"
if not defined DETECTED_ARCH set "DETECTED_ARCH=unknown"

call :find_python
if defined PYTHON_EXE goto :run_app

echo Python was not found. This wizard requires Python.
echo Detected architecture: %DETECTED_ARCH%

where winget >nul 2>nul
if not %ERRORLEVEL%==0 (
    echo winget was not found, so Python cannot be installed automatically.
    echo Install Python manually from https://www.python.org/downloads/ and run this launcher again.
    echo Cannot continue without Python.
    exit /b 1
)

echo Checking supported Python version available from winget...
call :find_winget_python
if not defined PYTHON_WINGET_ID (
    echo Could not find a supported Python package in winget.
    echo Winget search output:
    winget search --id Python.Python --source winget
    echo Cannot continue without Python.
    exit /b 1
)

echo Python available from winget: %PYTHON_WINGET_VERSION% [%PYTHON_WINGET_ID%]

choice /C YN /M "Install Python now with winget"
if errorlevel 2 (
    echo Cannot continue without Python.
    exit /b 1
)

echo Installing Python for this architecture via winget.
winget install --id %PYTHON_WINGET_ID% --exact --source winget --accept-source-agreements --accept-package-agreements
if not %ERRORLEVEL%==0 (
    echo Could not install Python for architecture %DETECTED_ARCH% using winget. See the winget error above.
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
py -3 -c "import sys; raise SystemExit(sys.version_info < (3, 14))" >nul 2>nul
if %ERRORLEVEL%==0 (
    set "PYTHON_EXE=py"
    set "PYTHON_ARGS=-3"
    exit /b 0
)

python -c "import sys; raise SystemExit(sys.version_info < (3, 14))" >nul 2>nul
if %ERRORLEVEL%==0 (
    set "PYTHON_EXE=python"
    set "PYTHON_ARGS="
    exit /b 0
)

for /f "delims=" %%P in ('dir /b /ad "%LOCALAPPDATA%\Programs\Python\Python*" 2^>nul') do (
    if exist "%LOCALAPPDATA%\Programs\Python\%%P\python.exe" (
        "%LOCALAPPDATA%\Programs\Python\%%P\python.exe" -c "import sys; raise SystemExit(sys.version_info < (3, 14))" >nul 2>nul
        if not errorlevel 1 (
            set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\%%P\python.exe"
            set "PYTHON_ARGS="
            exit /b 0
        )
    )
)

for /f "delims=" %%P in ('dir /b /ad "%ProgramFiles%\Python*" 2^>nul') do (
    if exist "%ProgramFiles%\%%P\python.exe" (
        "%ProgramFiles%\%%P\python.exe" -c "import sys; raise SystemExit(sys.version_info < (3, 14))" >nul 2>nul
        if not errorlevel 1 (
            set "PYTHON_EXE=%ProgramFiles%\%%P\python.exe"
            set "PYTHON_ARGS="
            exit /b 0
        )
    )
)

exit /b 1

:find_winget_python
for %%I in (Python.Python.3.14) do (
    for /f "tokens=2,*" %%A in ('winget show --id %%I --exact --source winget 2^>nul ^| findstr /B /C:"Version:"') do (
        set "PYTHON_WINGET_ID=%%I"
        set "PYTHON_WINGET_VERSION=%%A"
        exit /b 0
    )
)
exit /b 1

:end
endlocal
