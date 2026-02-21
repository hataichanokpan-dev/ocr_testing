@echo off
REM PDF Watcher Service Uninstaller
REM Run as Administrator

echo ========================================
echo PDF Watcher - Service Uninstallation
echo ========================================
echo.

REM Check for administrator privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ERROR: This script must be run as Administrator!
    echo.
    echo Right-click this file and select "Run as administrator"
    echo.
    pause
    exit /b 1
)

echo Are you sure you want to uninstall the PDF Watcher service?
choice /C YN /M "Continue with uninstallation"

if errorlevel 2 (
    echo.
    echo Uninstallation cancelled.
    goto end
)

echo.
echo Stopping and uninstalling service...
echo.

python service_manager.py uninstall

if %errorLevel% equ 0 (
    echo.
    echo ========================================
    echo Uninstallation completed successfully!
    echo ========================================
) else (
    echo.
    echo Uninstallation failed! Please check the error messages above.
)

:end
echo.
pause
