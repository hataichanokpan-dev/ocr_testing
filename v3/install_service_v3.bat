@echo off
REM ========================================
REM Install PDF Watcher V3 as Windows Service
REM Using NSSM (Non-Sucking Service Manager)
REM ========================================

REM Check for Administrator privileges first
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ========================================
    echo ERROR: ADMINISTRATOR ACCESS REQUIRED
    echo ========================================
    echo.
    echo This script MUST be run as Administrator to install a Windows Service.
    echo.
    echo Please:
    echo   1. Right-click on this file: install_service_v3.bat
    echo   2. Select "Run as administrator"
    echo   3. Click "Yes" when prompted
    echo.
    echo ========================================
    pause
    exit /b 1
)

echo ========================================
echo PDF Watcher V3 Service Installation
echo ========================================
echo Running with Administrator privileges...
echo.

REM Set paths
set SERVICE_NAME=PDFWatcherV3
set CURRENT_DIR=%~dp0
set PROJECT_ROOT=%~dp0..
set PYTHON_PATH=python
set SCRIPT_PATH=%CURRENT_DIR%pdf_watcher_v3.py
set NSSM_PATH=%CURRENT_DIR%nssm.exe

REM Get absolute Python path
for /f "delims=" %%i in ('where python 2^>nul') do set PYTHON_FULL_PATH=%%i

echo Current Directory: %CURRENT_DIR%
echo Project Root: %PROJECT_ROOT%
echo Python Path: %PYTHON_FULL_PATH%
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

REM Verify Python full path was found
if "%PYTHON_FULL_PATH%"=="" (
    echo ERROR: Could not determine Python full path!
    pause
    exit /b 1
)

echo Python version:
python --version
echo Python executable: %PYTHON_FULL_PATH%
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

REM Install service with NSSM using absolute Python path
"%NSSM_PATH%" install %SERVICE_NAME% "%PYTHON_FULL_PATH%" "%SCRIPT_PATH%"
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Failed to install service!
    echo Make sure you are running as Administrator.
    pause
    exit /b 1
)

REM Set service parameters - AppDirectory should be PROJECT ROOT not v3/
"%NSSM_PATH%" set %SERVICE_NAME% AppDirectory "%PROJECT_ROOT%"
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

REM Verify service installation
sc query %SERVICE_NAME% >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Service installation verification failed!
    echo The service was not created successfully.
    pause
    exit /b 1
)

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
