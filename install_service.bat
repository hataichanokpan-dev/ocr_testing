@echo off
REM PDF Watcher Service Installer
REM Run as Administrator

echo ========================================
echo PDF Watcher - Service Installation
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

echo Running service installation...
echo.

python service_manager.py install

if %errorLevel% equ 0 (
    echo.
    echo ========================================
    echo Installation completed successfully!
    echo ========================================
    echo.
    echo Would you like to start the service now?
    choice /C YN /M "Start service"
    
    if errorlevel 2 goto end
    if errorlevel 1 (
        echo.
        echo Starting service...
        python service_manager.py start
    )
) else (
    echo.
    echo Installation failed! Please check the error messages above.
)

:end
echo.
pause
