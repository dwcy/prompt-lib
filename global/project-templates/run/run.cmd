@echo off
rem Cross-platform run launcher - Windows shim. All logic lives in run.py.
setlocal
set "HERE=%~dp0"
where python >nul 2>nul && (
  python "%HERE%run.py" %*
  goto :eof
)
where py >nul 2>nul && (
  py -3 "%HERE%run.py" %*
  goto :eof
)
echo run: Python 3 is required but was not found on PATH 1>&2
exit /b 1
