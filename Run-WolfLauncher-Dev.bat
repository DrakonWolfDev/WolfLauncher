@echo off
setlocal

rem Run the current source checkout, rather than a packaged release build.
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" main.py
) else (
    python main.py
)

if errorlevel 1 (
    echo.
    echo WolfLauncher exited with an error. Press any key to close this window.
    pause >nul
)

endlocal
