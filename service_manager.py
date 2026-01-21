"""
PDF Watcher Windows Service Installer
Install PDF Watcher as a Windows Service using NSSM
"""

import os
import sys
import subprocess
from pathlib import Path

# Configuration
SERVICE_NAME = "PDFWatcher"
SERVICE_DISPLAY_NAME = "PDF Folder Watcher with OCR"
SERVICE_DESCRIPTION = "Automatically monitors folder for PDF files and renames them based on header text using OCR"

# Paths
CURRENT_DIR = Path(__file__).parent.absolute()
PYTHON_EXE = sys.executable
SCRIPT_PATH = CURRENT_DIR / "pdf_watcher.py"
NSSM_PATH = CURRENT_DIR / "nssm.exe"

def check_admin():
    """Check if script is running with administrator privileges"""
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def download_nssm():
    """Instructions to download NSSM"""
    print("\n" + "="*60)
    print("NSSM (Non-Sucking Service Manager) is required")
    print("="*60)
    print("\nPlease download NSSM manually:")
    print("1. Go to: https://nssm.cc/download")
    print("2. Download the latest version (e.g., nssm-2.24.zip)")
    print("3. Extract the ZIP file")
    print("4. Copy 'nssm.exe' from win64 folder to:")
    print(f"   {CURRENT_DIR}")
    print("\nAfter copying nssm.exe, run this script again.")
    print("="*60 + "\n")

def install_service():
    """Install PDF Watcher as Windows Service"""
    if not check_admin():
        print("ERROR: Administrator privileges required!")
        print("Please run PowerShell as Administrator and try again.")
        return False
    
    if not NSSM_PATH.exists():
        download_nssm()
        return False
    
    print(f"\nInstalling service: {SERVICE_NAME}")
    print(f"Python: {PYTHON_EXE}")
    print(f"Script: {SCRIPT_PATH}")
    
    # Install service
    cmd = [
        str(NSSM_PATH),
        "install",
        SERVICE_NAME,
        str(PYTHON_EXE),
        str(SCRIPT_PATH)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"✓ Service installed successfully")
        
        # Set service display name
        subprocess.run([str(NSSM_PATH), "set", SERVICE_NAME, "DisplayName", SERVICE_DISPLAY_NAME], check=True)
        
        # Set service description
        subprocess.run([str(NSSM_PATH), "set", SERVICE_NAME, "Description", SERVICE_DESCRIPTION], check=True)
        
        # Set working directory
        subprocess.run([str(NSSM_PATH), "set", SERVICE_NAME, "AppDirectory", str(CURRENT_DIR)], check=True)
        
        # Set startup type to automatic
        subprocess.run([str(NSSM_PATH), "set", SERVICE_NAME, "Start", "SERVICE_AUTO_START"], check=True)
        
        # Redirect output to log files
        log_file = CURRENT_DIR / "service_output.log"
        error_file = CURRENT_DIR / "service_error.log"
        subprocess.run([str(NSSM_PATH), "set", SERVICE_NAME, "AppStdout", str(log_file)], check=True)
        subprocess.run([str(NSSM_PATH), "set", SERVICE_NAME, "AppStderr", str(error_file)], check=True)
        
        # Set service to restart on failure
        subprocess.run([str(NSSM_PATH), "set", SERVICE_NAME, "AppExit", "Default", "Restart"], check=True)
        
        print(f"✓ Service configured successfully")
        print(f"\nService details:")
        print(f"  Name: {SERVICE_NAME}")
        print(f"  Display Name: {SERVICE_DISPLAY_NAME}")
        print(f"  Status: Installed (not started)")
        print(f"\nTo start the service, run:")
        print(f"  net start {SERVICE_NAME}")
        print(f"or:")
        print(f"  nssm start {SERVICE_NAME}")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"✗ Error installing service: {e}")
        print(f"Output: {e.output if hasattr(e, 'output') else 'N/A'}")
        return False

def uninstall_service():
    """Uninstall PDF Watcher service"""
    if not check_admin():
        print("ERROR: Administrator privileges required!")
        print("Please run PowerShell as Administrator and try again.")
        return False
    
    if not NSSM_PATH.exists():
        download_nssm()
        return False
    
    print(f"\nUninstalling service: {SERVICE_NAME}")
    
    # Stop service first
    try:
        subprocess.run([str(NSSM_PATH), "stop", SERVICE_NAME], capture_output=True)
        print(f"✓ Service stopped")
    except:
        pass
    
    # Remove service
    cmd = [str(NSSM_PATH), "remove", SERVICE_NAME, "confirm"]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"✓ Service uninstalled successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Error uninstalling service: {e}")
        return False

def start_service():
    """Start the PDF Watcher service"""
    if not check_admin():
        print("ERROR: Administrator privileges required!")
        return False
    
    try:
        subprocess.run(["net", "start", SERVICE_NAME], check=True)
        print(f"✓ Service started successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Error starting service: {e}")
        return False

def stop_service():
    """Stop the PDF Watcher service"""
    if not check_admin():
        print("ERROR: Administrator privileges required!")
        return False
    
    try:
        subprocess.run(["net", "stop", SERVICE_NAME], check=True)
        print(f"✓ Service stopped successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Error stopping service: {e}")
        return False

def status_service():
    """Check service status"""
    try:
        result = subprocess.run(
            ["sc", "query", SERVICE_NAME],
            capture_output=True,
            text=True
        )
        
        if "does not exist" in result.stdout or result.returncode != 0:
            print(f"Service '{SERVICE_NAME}' is NOT installed")
        else:
            print(f"\nService Status:")
            print(result.stdout)
    except Exception as e:
        print(f"Error checking status: {e}")

def main():
    """Main function"""
    print("\n" + "="*60)
    print("PDF Watcher - Windows Service Manager")
    print("="*60)
    
    if len(sys.argv) < 2:
        print("\nUsage:")
        print(f"  python {Path(__file__).name} [install|uninstall|start|stop|status]")
        print("\nCommands:")
        print("  install   - Install as Windows Service")
        print("  uninstall - Remove the Windows Service")
        print("  start     - Start the service")
        print("  stop      - Stop the service")
        print("  status    - Check service status")
        print("\nNote: Must run as Administrator!")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "install":
        install_service()
    elif command == "uninstall":
        uninstall_service()
    elif command == "start":
        start_service()
    elif command == "stop":
        stop_service()
    elif command == "status":
        status_service()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()
