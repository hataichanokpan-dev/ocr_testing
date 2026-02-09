# ========================================
# Install PDF Watcher V3 as Windows Service
# PowerShell version with automatic elevation
# ========================================

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Yellow
    Write-Host "REQUESTING ADMINISTRATOR ACCESS" -ForegroundColor Yellow
    Write-Host "========================================" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "This script requires Administrator privileges."
    Write-Host "Restarting with elevated permissions..." -ForegroundColor Cyan
    Write-Host ""
    
    # Restart script with elevation
    Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "PDF Watcher V3 Service Installation" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "Running with Administrator privileges..." -ForegroundColor Green
Write-Host ""

# Set paths
$ServiceName = "PDFWatcherV3"
$CurrentDir = Split-Path -Parent $PSCommandPath
$ProjectRoot = Split-Path -Parent $CurrentDir
$ScriptPath = Join-Path $CurrentDir "pdf_watcher_v3.py"
$NssmPath = Join-Path $CurrentDir "nssm.exe"

Write-Host "Current Directory: $CurrentDir"
Write-Host "Project Root: $ProjectRoot"
Write-Host "Script Path: $ScriptPath"
Write-Host ""

# Check if Python exists and get full path
try {
    $pythonPath = (Get-Command python -ErrorAction Stop).Source
    $pythonVersion = & python --version 2>&1
    Write-Host "Python version: $pythonVersion" -ForegroundColor Green
    Write-Host "Python executable: $pythonPath" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Python not found in PATH!" -ForegroundColor Red
    Write-Host "Please install Python or add it to PATH"
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""

# Check if NSSM exists
if (-not (Test-Path $NssmPath)) {
    Write-Host "ERROR: NSSM not found at $NssmPath" -ForegroundColor Red
    Write-Host "Please download NSSM from https://nssm.cc/download"
    Write-Host "Extract nssm.exe to: $CurrentDir"
    Read-Host "Press Enter to exit"
    exit 1
}

# Check if script exists
if (-not (Test-Path $ScriptPath)) {
    Write-Host "ERROR: PDF Watcher script not found at $ScriptPath" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Check if service already exists
$existingService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($existingService) {
    Write-Host "Service $ServiceName already exists!" -ForegroundColor Yellow
    Write-Host "Please uninstall it first using uninstall_service_v3.ps1"
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "Installing service..." -ForegroundColor Cyan
Write-Host ""

# Install service with NSSM using absolute Python path
& $NssmPath install $ServiceName $pythonPath $ScriptPath
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Failed to install service!" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Set service parameters - AppDirectory should be PROJECT ROOT
& $NssmPath set $ServiceName AppDirectory $ProjectRoot
& $NssmPath set $ServiceName DisplayName "PDF Watcher V3"
& $NssmPath set $ServiceName Description "Monitors PDF files and extracts text automatically (V3 with Year/Date organization)"
& $NssmPath set $ServiceName Start SERVICE_AUTO_START

# Set logging
$LogDir = Join-Path $CurrentDir "logs"
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
}
& $NssmPath set $ServiceName AppStdout (Join-Path $LogDir "service_stdout.log")
& $NssmPath set $ServiceName AppStderr (Join-Path $LogDir "service_stderr.log")

# Set restart behavior
& $NssmPath set $ServiceName AppExit Default Restart
& $NssmPath set $ServiceName AppRestartDelay 5000

# Verify service installation
Start-Sleep -Seconds 1
$service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if (-not $service) {
    Write-Host ""
    Write-Host "ERROR: Service installation verification failed!" -ForegroundColor Red
    Write-Host "The service was not created successfully."
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Service installed successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Service Name: $ServiceName" -ForegroundColor Cyan
Write-Host "Display Name: PDF Watcher V3" -ForegroundColor Cyan
Write-Host "Status: $($service.Status)" -ForegroundColor Cyan
Write-Host ""
Write-Host "IMPORTANT SETUP STEPS:" -ForegroundColor Yellow
Write-Host "1. Create 'input' folder for PDF files to monitor"
Write-Host "2. Configure 'v3\config.ini' for your needs"
Write-Host "3. Output will be organized: output\YYYY\YYYY-MM-DD\files"
Write-Host ""
Write-Host "To start the service:" -ForegroundColor Yellow
Write-Host "  Start-Service $ServiceName" -ForegroundColor White
Write-Host "  or: net start $ServiceName" -ForegroundColor White
Write-Host "  or use Services (services.msc)" -ForegroundColor White
Write-Host ""
Write-Host "To check service status:" -ForegroundColor Yellow
Write-Host "  Get-Service $ServiceName" -ForegroundColor White
Write-Host ""
Write-Host "Logs location: $LogDir" -ForegroundColor Cyan
Write-Host ""
Read-Host "Press Enter to exit"
