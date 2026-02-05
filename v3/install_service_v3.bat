@echo off
REM ========================================
REM Install PDF Watcher V3 as Windows Service
REM Using NSSM (Non-Sucking Service Manager)
REM ========================================

echo ========================================
echo PDF Watcher V3 Service Installation
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

REM Set paths
set SERVICE_NAME=PDFWatcherV3
set CURRENT_DIR=%~dp0
set PYTHON_PATH=python
set SCRIPT_PATH=%CURRENT_DIR%v3\pdf_watcher_v3.py
set NSSM_PATH=%CURRENT_DIR%nssm.exe

echo Current Directory: %CURRENT_DIR%
echo Python Path: %PYTHON_PATH%
echo Script Path: %SCRIPT_PATH%
echo.

REM Check if Python exists
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found in PATH!
    echo Please install Python or add it to PATH
    pause
    exit /b 1
)

echo Python version:
python --version
echo.

REM Check if NSSM exists
if not exist "%NSSM_PATH%" (
    echo ERROR: NSSM not found at %NSSM_PATH%
    echo Please download NSSM from https://nssm.cc/download
    echo Extract nssm.exe to: %CURRENT_DIR%
    pause
    exit /b 1
)

REM Check if script exists
if not exist "%SCRIPT_PATH%" (
    echo ERROR: PDF Watcher script not found at %SCRIPT_PATH%
    pause
    exit /b 1
)

REM Check if service already exists
sc query %SERVICE_NAME% >nul 2>&1
if %errorlevel% equ 0 (
    echo Service %SERVICE_NAME% already exists!
    echo Please uninstall it first using uninstall_service_v3.bat
    pause
    exit /b 1
)

echo Installing service...
echo.

REM Install service with NSSM
"%NSSM_PATH%" install %SERVICE_NAME% "%PYTHON_PATH%" "%SCRIPT_PATH%"

REM Set service parameters
"%NSSM_PATH%" set %SERVICE_NAME% AppDirectory "%CURRENT_DIR%"
"%NSSM_PATH%" set %SERVICE_NAME% DisplayName "PDF Watcher V3"
"%NSSM_PATH%" set %SERVICE_NAME% Description "Monitors PDF files and extracts text automatically (V3 with Year/Date organization)"
"%NSSM_PATH%" set %SERVICE_NAME% Start SERVICE_AUTO_START

REM Set logging
set LOG_DIR=%CURRENT_DIR%logs
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
"%NSSM_PATH%" set %SERVICE_NAME% AppStdout "%LOG_DIR%\service_stdout.log"
"%NSSM_PATH%" set %SERVICE_NAME% AppStderr "%LOG_DIR%\service_stderr.log"

REM Set restart behavior
"%NSSM_PATH%" set %SERVICE_NAME% AppExit Default Restart
"%NSSM_PATH%" set %SERVICE_NAME% AppRestartDelay 5000

echo.
echo ========================================
echo Service installed successfully!
echo ========================================
echo.
echo Service Name: %SERVICE_NAME%
echo Display Name: PDF Watcher V3
echo Status: Ready to start
echo.
echo IMPORTANT SETUP STEPS:
echo 1. Create 'input' folder for PDF files to monitor
echo 2. Configure 'v3\config.ini' for your needs
echo 3. Output will be organized: output\YYYY\YYYY-MM-DD\files
echo.
echo To start the service:
echo   net start %SERVICE_NAME%
echo   or use Services (services.msc)
echo.
echo To check service status:
echo   sc query %SERVICE_NAME%
echo.
echo Logs location: %LOG_DIR%
echo.
pause
