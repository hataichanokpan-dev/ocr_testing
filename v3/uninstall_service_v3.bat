@echo off
REM ========================================
REM Uninstall PDF Watcher V3 Windows Service
REM ========================================

echo ========================================
echo PDF Watcher V3 Service Uninstallation
echo ========================================
echo.

REM Check if running as Administrator
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: This script must be run as Administrator!
    echo Right-click and select "Run as Administrator"
    pause
    exit /b 1
)

set SERVICE_NAME=PDFWatcherV3
set NSSM_PATH=%~dp0nssm.exe

REM Check if NSSM exists
if not exist "%NSSM_PATH%" (
    echo ERROR: NSSM not found at %NSSM_PATH%
    echo Cannot uninstall service without NSSM
    pause
    exit /b 1
)

REM Check if service exists
sc query %SERVICE_NAME% >nul 2>&1
if %errorlevel% neq 0 (
    echo Service %SERVICE_NAME% is not installed.
    pause
    exit /b 0
)

echo Stopping service (if running)...
net stop %SERVICE_NAME% 2>nul

echo Removing service...
"%NSSM_PATH%" remove %SERVICE_NAME% confirm

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo Service uninstalled successfully!
    echo ========================================
) else (
    echo.
    echo ERROR: Failed to uninstall service
    echo Please try manually: sc delete %SERVICE_NAME%
)

echo.
pause
