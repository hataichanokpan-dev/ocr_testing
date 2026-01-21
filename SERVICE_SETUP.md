# PDF Watcher Windows Service Setup Guide

## 🎯 Running as Windows Service

Running PDF Watcher as a Windows Service provides:
- ✅ **Automatic startup** when Windows boots
- ✅ **Background operation** without user login
- ✅ **Automatic restart** on failure
- ✅ **System integration** managed by Windows

## 📋 Prerequisites

1. Administrator privileges
2. Python installed and working
3. NSSM (Non-Sucking Service Manager)

## 🚀 Installation Steps

### Step 1: Download NSSM

1. Visit [https://nssm.cc/download](https://nssm.cc/download)
2. Download the latest version (e.g., `nssm-2.24.zip`)
3. Extract the ZIP file
4. Copy `nssm.exe` from the `win64` folder to your project directory:
   ```
   C:\Programing\Microchip\OCR_PDW\
   ```

### Step 2: Install the Service

**Option A: Using Batch File (Easiest)**

1. Right-click `install_service.bat`
2. Select **"Run as administrator"**
3. Follow the prompts
4. Choose whether to start the service immediately

**Option B: Using PowerShell**

```powershell
# Run PowerShell as Administrator
cd C:\Programing\Microchip\OCR_PDW

# Install service
python service_manager.py install

# Start service
python service_manager.py start
```

**Option C: Manual NSSM Installation**

```powershell
# Run PowerShell as Administrator
cd C:\Programing\Microchip\OCR_PDW

# Install service
.\nssm.exe install PDFWatcher "C:\Path\To\Python\python.exe" "C:\Programing\Microchip\OCR_PDW\pdf_watcher.py"

# Set working directory
.\nssm.exe set PDFWatcher AppDirectory "C:\Programing\Microchip\OCR_PDW"

# Set startup type
.\nssm.exe set PDFWatcher Start SERVICE_AUTO_START

# Start service
.\nssm.exe start PDFWatcher
```

### Step 3: Verify Installation

```powershell
# Check service status
python service_manager.py status

# Or use Windows Services
services.msc
```

## 🎮 Managing the Service

### Start Service
```powershell
python service_manager.py start
# or
net start PDFWatcher
```

### Stop Service
```powershell
python service_manager.py stop
# or
net stop PDFWatcher
```

### Check Status
```powershell
python service_manager.py status
```

### Restart Service
```powershell
net stop PDFWatcher
net start PDFWatcher
```

## 🗑️ Uninstallation

**Option A: Using Batch File**
1. Right-click `uninstall_service.bat`
2. Select **"Run as administrator"**
3. Confirm uninstallation

**Option B: Using PowerShell**
```powershell
python service_manager.py uninstall
```

## 📝 Service Details

- **Service Name:** `PDFWatcher`
- **Display Name:** `PDF Folder Watcher with OCR`
- **Startup Type:** Automatic
- **Recovery:** Restarts automatically on failure

## 📊 Monitoring the Service

### Log Files

The service creates separate log files:
- `service_output.log` - Standard output
- `service_error.log` - Error messages
- `pdf_watcher.log` - Application log (as configured)

### View Logs
```powershell
# View output log
Get-Content service_output.log -Tail 50

# View error log
Get-Content service_error.log -Tail 50

# View application log
Get-Content pdf_watcher.log -Tail 50

# Monitor in real-time
Get-Content pdf_watcher.log -Wait
```

## 🔧 Troubleshooting

### Service Won't Start

1. **Check Python path:**
   ```powershell
   where python
   ```

2. **Check service configuration:**
   ```powershell
   .\nssm.exe get PDFWatcher AppDirectory
   .\nssm.exe get PDFWatcher Application
   ```

3. **Check error logs:**
   ```powershell
   Get-Content service_error.log
   ```

### Service Stops Unexpectedly

1. Check `service_error.log` for errors
2. Verify config.ini settings
3. Ensure watch_folder exists
4. Check Tesseract installation

### Update Configuration

After changing `config.ini`:
```powershell
# Restart service to apply changes
net stop PDFWatcher
net start PDFWatcher
```

## 🎯 Advanced Configuration

### Change Service Settings

```powershell
# Set service description
.\nssm.exe set PDFWatcher Description "Your custom description"

# Change startup type to Manual
.\nssm.exe set PDFWatcher Start SERVICE_DEMAND_START

# Set service to run as specific user
.\nssm.exe set PDFWatcher ObjectName "DOMAIN\Username" "Password"

# Set restart delay (milliseconds)
.\nssm.exe set PDFWatcher AppThrottle 1500

# Set restart count limit
.\nssm.exe set PDFWatcher AppRestartDelay 60000
```

### Edit Service via NSSM GUI

```powershell
.\nssm.exe edit PDFWatcher
```

This opens a GUI where you can configure:
- Application path and arguments
- Service name and description
- Log file locations
- Environment variables
- Process priority
- File rotation
- Dependencies

## 📋 Service Commands Reference

| Command | Description |
|---------|-------------|
| `python service_manager.py install` | Install service |
| `python service_manager.py uninstall` | Remove service |
| `python service_manager.py start` | Start service |
| `python service_manager.py stop` | Stop service |
| `python service_manager.py status` | Check status |
| `net start PDFWatcher` | Start via Windows |
| `net stop PDFWatcher` | Stop via Windows |
| `services.msc` | Open Windows Services |

## ✅ Best Practices

1. **Test First:** Run `pdf_watcher.py` manually before installing as service
2. **Check Logs:** Regularly monitor log files
3. **Update Safely:** Stop service before updating code
4. **Backup Config:** Keep backup of `config.ini`
5. **Document Changes:** Note any configuration changes

## 🔐 Security Considerations

- Service runs with SYSTEM privileges by default
- Consider running as specific user for better security
- Ensure watch_folder has appropriate permissions
- Protect config.ini from unauthorized access

## 🆘 Getting Help

If you encounter issues:
1. Check `service_error.log`
2. Check `pdf_watcher.log`
3. Verify Python and Tesseract installations
4. Test manual execution: `python pdf_watcher.py`
5. Check Windows Event Viewer for service errors

---

**Note:** Always run PowerShell or Command Prompt as **Administrator** when managing Windows Services.
