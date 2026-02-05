# PDF Extractor V3 - Setup Guide

## 📋 สารบัญ
1. [ความต้องการของระบบ](#ความต้องการของระบบ)
2. [โครงสร้าง Folder](#โครงสร้าง-folder)
3. [การติดตั้ง](#การติดตั้ง)
4. [การตั้งค่า Input/Output Paths](#การตั้งค่า-inputoutput-paths)
5. [การติดตั้ง Windows Service](#การติดตั้ง-windows-service)
6. [การใช้งาน](#การใช้งาน)
7. [Troubleshooting](#troubleshooting)

---

## ความต้องการของระบบ

### Software Requirements
- **Python 3.8+** (แนะนำ 3.9 ขึ้นไป)
- **Tesseract OCR** (สำหรับ OCR engine)
  - Download: https://github.com/UB-Mannheim/tesseract/wiki
  - ติดตั้งที่: `C:\Program Files\Tesseract-OCR\`
- **NSSM** (สำหรับติดตั้ง Windows Service)
  - Download: https://nssm.cc/download
  - Extract `nssm.exe` ไปที่ folder โปรเจค

### Python Packages
```bash
pip install -r requirements.txt
```

Required packages:
- PyMuPDF (fitz)
- pytesseract
- Pillow
- opencv-python
- numpy
- requests
- watchdog

---

## โครงสร้าง Folder

```
OCR_Picklist/
├── v3/                          # โฟลเดอร์ V3 (ใหม่)
│   ├── components/              # Core components
│   ├── utils/                   # Utilities
│   ├── tests/                   # Unit tests
│   ├── config.ini              # V3 Configuration
│   ├── pdf_watcher_v3.py       # Service script
│   ├── pdf_extractor_v3.py     # Main extractor
│   ├── install_service_v3.bat  # Install service
│   └── uninstall_service_v3.bat # Uninstall service
│
├── input/                       # INPUT PATH (ต้องสร้าง)
│   └── [วาง PDF ที่นี่]
│
├── output/                      # OUTPUT PATH (auto-created)
│   └── 2026/                    # ปี (YYYY)
│       └── 2026-02-05/         # วันที่ (YYYY-MM-DD)
│           ├── B-HK-WFE-S17975643_pages_1-3.pdf
│           └── P-F-W1A-S17995875_pages_4-6.pdf
│
├── logs/                        # Service logs (auto-created)
├── debug_images/                # Debug images (auto-created)
├── nssm.exe                    # NSSM executable
└── requirements.txt
```

---

## การติดตั้ง

### 1. ติดตั้ง Python และ Dependencies

```powershell
# ตรวจสอบ Python
python --version

# ติดตั้ง packages
cd d:\programing\Python\OCR_Picklist
pip install -r requirements.txt
```

### 2. ติดตั้ง Tesseract OCR

1. Download: https://github.com/UB-Mannheim/tesseract/wiki
2. ติดตั้งที่: `C:\Program Files\Tesseract-OCR\`
3. เพิ่ม path ใน Environment Variables (optional)

### 3. Download NSSM

1. Download: https://nssm.cc/download
2. Extract `nssm.exe` ไปที่: `d:\programing\Python\OCR_Picklist\`

---

## การตั้งค่า Input/Output Paths

### 📁 Input Path Setup

**Input folder** คือที่วาง PDF files ที่ต้องการ process

#### วิธีที่ 1: ใช้ folder เริ่มต้น (แนะนำ)
```powershell
# สร้าง input folder
cd d:\programing\Python\OCR_Picklist
mkdir input
```

#### วิธีที่ 2: ใช้ path อื่น
แก้ไขในไฟล์ `v3\pdf_watcher_v3.py`:
```python
# แก้บรรทัดที่ 78
input_folder = Path('input')  # เดิม
input_folder = Path('D:/your/custom/input/path')  # ใหม่
```

---

### 📁 Output Path Setup

**Output folder** จัดเก็บ PDF ที่แยกแล้วตาม structure: `{base}/{YYYY}/{YYYY-MM-DD}/`

#### ตั้งค่าใน config.ini

เปิดไฟล์ `v3\config.ini`:

```ini
# ===== Output Organization (NEW in V3) =====
# Folder structure: {output_base_dir}/{YYYY}/{YYYY-MM-DD}/files
output_base_dir = output

# เปลี่ยนเป็น path ที่ต้องการ
# output_base_dir = D:/PDFOutput

# เปิด/ปิดการจัดเรียงตามปี-วันที่
organize_by_year_and_date = true

# ระยะเวลาเก็บไฟล์ (วัน)
output_retention_days = 90
```

#### ตัวอย่าง Output Structure

**กรณีใช้ path เริ่มต้น:**
```
output/
└── 2026/
    ├── 2026-02-05/
    │   ├── B-HK-WFE-S17975643_pages_1-3.pdf
    │   └── P-F-W1A-S17995875_pages_4-6.pdf
    ├── 2026-02-06/
    │   └── B-TH-GTX-S12345678_pages_1-5.pdf
    └── 2026-02-07/
        └── ...
```

**กรณีใช้ custom path:**
```ini
output_base_dir = D:/Company/ProcessedPDFs
```
ผลลัพธ์:
```
D:/Company/ProcessedPDFs/
└── 2026/
    └── 2026-02-05/
        └── ...
```

---

## การติดตั้ง Windows Service

### ขั้นตอนการติดตั้ง

#### 1. เตรียม config.ini
```powershell
# คัดลอก config และแก้ไขตามต้องการ
cd d:\programing\Python\OCR_Picklist\v3
notepad config.ini
```

ตั้งค่าสำคัญ:
- `output_base_dir` - path สำหรับ output
- `api_log_url` - API endpoint (ถ้ามี)
- `enable_api_logging` - เปิด/ปิด API logging

#### 2. สร้าง input folder
```powershell
cd d:\programing\Python\OCR_Picklist
mkdir input
```

#### 3. ติดตั้ง Service

**⚠️ ต้อง Run as Administrator!**

```powershell
# คลิกขวาที่ PowerShell -> Run as Administrator
cd d:\programing\Python\OCR_Picklist\v3
.\install_service_v3.bat
```

Output ที่ถูกต้อง:
```
========================================
PDF Watcher V3 Service Installation
========================================

Current Directory: D:\programing\Python\OCR_Picklist\v3\
Python version: Python 3.9.x

Installing service...
Service installed successfully!
========================================

Service Name: PDFWatcherV3
Display Name: PDF Watcher V3
Status: Ready to start
```

#### 4. Start Service

**วิธีที่ 1: Command Line**
```powershell
net start PDFWatcherV3
```

**วิธีที่ 2: Services GUI**
1. กด `Win + R`
2. พิมพ์ `services.msc`
3. หา "PDF Watcher V3"
4. คลิกขวา -> Start

---

## การใช้งาน

### 🚀 การ Process PDF

#### 1. วิธีอัตโนมัติ (Service)
```
1. Start service (ถ้ายังไม่ start)
2. วาง PDF file ใน folder: input/
3. Service จะ process อัตโนมัติ
4. ผลลัพธ์จะอยู่ใน: output/YYYY/YYYY-MM-DD/
```

#### 2. วิธีแบบ Manual (ไม่ใช้ Service)
```powershell
cd d:\programing\Python\OCR_Picklist
python v3\pdf_watcher_v3.py
```

---

### 📊 ตรวจสอบ Metrics

Metrics จะถูกบันทึกอัตโนมัติที่ `metrics.json`

```powershell
# ดู metrics
cd d:\programing\Python\OCR_Picklist
type metrics.json
```

ตัวอย่าง metrics:
```json
{
  "summary": {
    "total_jobs": 150,
    "avg_processing_time_seconds": 3.45,
    "ocr_success_rate": 95.5,
    "api_success_rate": 98.2
  }
}
```

---

### 📝 ตรวจสอบ Logs

Logs จะอยู่ใน folder `logs/`:

```powershell
# ดู log ล่าสุด
cd d:\programing\Python\OCR_Picklist\logs
Get-Content -Path (Get-ChildItem | Sort-Object LastWriteTime -Descending | Select-Object -First 1).Name -Tail 50
```

Log files:
- `pdf_watcher_v3_YYYYMMDD.log` - Application log
- `service_stdout.log` - Service output
- `service_stderr.log` - Service errors

---

## Troubleshooting

### ❌ ปัญหา: Service ติดตั้งไม่ได้

**สาเหตุ:** ไม่ได้ Run as Administrator

**แก้ไข:**
```powershell
# คลิกขวา PowerShell -> Run as Administrator
cd d:\programing\Python\OCR_Picklist\v3
.\install_service_v3.bat
```

---

### ❌ ปัญหา: Python not found

**สาเหตุ:** Python ไม่ได้อยู่ใน PATH

**แก้ไข:**
1. เพิ่ม Python ใน PATH:
   - System Properties -> Environment Variables
   - เพิ่ม `C:\Users\YourName\AppData\Local\Programs\Python\Python39`
2. หรือแก้ใน `install_service_v3.bat`:
   ```batch
   set PYTHON_PATH=C:\Users\YourName\AppData\Local\Programs\Python\Python39\python.exe
   ```

---

### ❌ ปัญหา: Tesseract not found

**สาเหตุ:** Tesseract ไม่ได้ติดตั้งหรือไม่ได้ตั้ง path

**แก้ไข:**
1. ติดตั้ง Tesseract: https://github.com/UB-Mannheim/tesseract/wiki
2. ติดตั้งที่: `C:\Program Files\Tesseract-OCR\`
3. ถ้าติดตั้งที่อื่น แก้ใน `v3\pdf_extractor_v3.py`

---

### ❌ ปัญหา: Service เริ่มแล้วแต่ไม่ทำงาน

**ตรวจสอบ:**

1. **ดู service logs:**
   ```powershell
   cd d:\programing\Python\OCR_Picklist\logs
   type service_stderr.log
   ```

2. **ตรวจสอบ config:**
   ```powershell
   type v3\config.ini
   ```

3. **ลอง run manual:**
   ```powershell
   python v3\pdf_watcher_v3.py
   ```

---

### ❌ ปัญหา: Output folder ไม่ถูกสร้าง

**สาเหตุ:** Path ไม่มีสิทธิ์ write

**แก้ไข:**
1. ตรวจสอบ permissions ของ folder
2. ใช้ path ที่ user มีสิทธิ์เขียน
3. แก้ใน `config.ini`:
   ```ini
   output_base_dir = D:/temp/output
   ```

---

### ❌ ปัญหา: API logging error

**สาเหตุ:** API endpoint ไม่ตอบสนอง

**แก้ไข:**

**วิธีที่ 1: ปิด API logging**
```ini
# ใน config.ini
enable_api_logging = false
```

**วิธีที่ 2: ใช้ async mode (แนะนำ)**
```ini
# API จะไม่ block processing
api_log_async = true
```

---

## 🎯 Quick Start Summary

### การเริ่มต้นใช้งานแบบเร็ว

```powershell
# 1. ติดตั้ง dependencies
pip install -r requirements.txt

# 2. สร้าง input folder
mkdir input

# 3. แก้ไข config (ถ้าจำเป็น)
notepad v3\config.ini

# 4. ติดตั้ง service (Run as Admin)
cd v3
.\install_service_v3.bat

# 5. Start service
net start PDFWatcherV3

# 6. วาง PDF ใน input/ และรอผลลัพธ์ใน output/YYYY/YYYY-MM-DD/
```

---

## 📞 Support

หากพบปัญหา:
1. ตรวจสอบ logs ใน `logs/`
2. ดู metrics ใน `metrics.json`
3. ลอง run manual mode เพื่อ debug

---

**Version:** 3.0.0  
**Last Updated:** February 5, 2026
