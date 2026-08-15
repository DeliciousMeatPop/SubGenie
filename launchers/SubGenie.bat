@echo off
REM ============================================================================
REM  SubGenie launcher for Windows.
REM
REM  Drag a movie file (or several) onto this .bat and drop. It hands the file
REM  paths to SubGenie. Double-clicking with no file runs setup/help.
REM
REM  Requires Python 3 on PATH (python.org installer: tick "Add to PATH").
REM ============================================================================

setlocal
set "SCRIPT_DIR=%~dp0"

REM Find a Python launcher: prefer the 'py' launcher, fall back to 'python'.
where py >nul 2>nul
if %ERRORLEVEL%==0 (
    set "PY=py -3"
) else (
    set "PY=python"
)

%PY% "%SCRIPT_DIR%..\run.py" %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo SubGenie exited with an error.
    pause
)
endlocal
