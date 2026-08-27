@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\build-windows-release.ps1"
set "exit_code=%ERRORLEVEL%"
if not "%exit_code%"=="0" (
    echo.
    echo Windows release build failed with exit code %exit_code%.
) else (
    echo.
    echo Windows ZIP and Inno Setup installer are in dist\windows.
)
pause
exit /b %exit_code%
