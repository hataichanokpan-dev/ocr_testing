# ========================================
# Uninstall PDF Watcher V3 Service
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
Write-Host "PDF Watcher V3 Service Uninstallation" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "Running with Administrator privileges..." -ForegroundColor Green
Write-Host ""

# Set paths
$ServiceName = "PDFWatcherV3"
$CurrentDir = Split-Path -Parent $PSCommandPath
$NssmPath = Join-Path $CurrentDir "nssm.exe"

# Check if NSSM exists
if (-not (Test-Path $NssmPath)) {
    Write-Host "ERROR: NSSM not found at $NssmPath" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Check if service exists
$service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if (-not $service) {
    Write-Host "Service $ServiceName does not exist." -ForegroundColor Yellow
    Write-Host "Nothing to uninstall."
    Read-Host "Press Enter to exit"
    exit 0
}

Write-Host "Current service status: $($service.Status)" -ForegroundColor Cyan
Write-Host ""

# Stop service if running
if ($service.Status -eq 'Running') {
    Write-Host "Stopping service..." -ForegroundColor Yellow
    Stop-Service -Name $ServiceName -Force
    Start-Sleep -Seconds 2
    Write-Host "Service stopped." -ForegroundColor Green
}

# Remove service
Write-Host "Removing service..." -ForegroundColor Cyan
& $NssmPath remove $ServiceName confirm

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Failed to remove service!" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Verify removal
Start-Sleep -Seconds 1
$service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($service) {
    Write-Host ""
    Write-Host "WARNING: Service still exists after removal attempt!" -ForegroundColor Yellow
} else {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "Service uninstalled successfully!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
}

Write-Host ""
Read-Host "Press Enter to exit"
