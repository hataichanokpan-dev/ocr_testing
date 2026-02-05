# 🚀 PDF Extractor V3 - Quick Start

## ✅ สิ่งที่สร้างเสร็จแล้ว

### 📁 โครงสร้าง V3
```
v3/
├── 📄 config.ini                    # V3 Configuration
├── 📄 README_V3_SETUP.md           # คู่มือฉบับเต็ม
├── 📄 pdf_watcher_v3.py            # Service script
├── 📄 install_service_v3.bat       # ติดตั้ง service
├── 📄 uninstall_service_v3.bat     # ถอนการติดตั้ง service
│
├── components/                      # Core components
│   ├── output_organizer.py         # ✨ NEW: Year/Date folder management
│   ├── extraction_logger.py        # ✨ NEW: Async API logging
│   └── (หมายเหตุ: ยังขาด OCRPipeline, HeaderValidator, PdfSplitter)
│
└── utils/                          # Utilities
    ├── config_manager.py          # ✨ NEW: Type-safe config
    ├── metrics_tracker.py         # ✨ NEW: Performance metrics
    └── ocr_context.py             # ✨ NEW: Thread-safe context
```

---

## ⚙️ การตั้งค่าและใช้งาน (3 นาที)

### 1️⃣ สร้าง Input Folder
```powershell
cd D:\programing\Python\OCR_Picklist
mkdir input
```

### 2️⃣ ตรวจสอบ Config
```powershell
notepad v3\config.ini
```

**ตั้งค่าสำคัญ:**
```ini
# Output จะจัดเป็น: output/2026/2026-02-05/files
output_base_dir = output

# เปิด/ปิด API logging
enable_api_logging = true
api_log_async = true

# Performance metrics
enable_metrics_tracking = true
```

### 3️⃣ ติดตั้ง Service (Run as Admin)
```powershell
# คลิกขวา PowerShell -> Run as Administrator
cd D:\programing\Python\OCR_Picklist\v3
.\install_service_v3.bat
```

### 4️⃣ Start Service
```powershell
net start PDFWatcherV3
```

### 5️⃣ ทดสอบ
```
1. วาง PDF file ใน: D:\programing\Python\OCR_Picklist\input\
2. รอ 2-3 วินาที
3. ตรวจสอบผลลัพธ์ใน: output\2026\2026-02-05\
```

---

## 📊 Output Structure (NEW!)

**ผลลัพธ์จะจัดเป็น Year → Date:**
```
output/
└── 2026/                          # ปี
    ├── 2026-02-05/               # วันที่
    │   ├── B-HK-WFE-S17975643_pages_1-3.pdf
    │   └── P-F-W1A-S17995875_pages_4-6.pdf
    │
    ├── 2026-02-06/
    │   └── B-TH-GTX-S12345678.pdf
    │
    └── 2026-02-07/
        └── ...
```

**ข้อดี:**
- ✅ จัดระเบียบอัตโนมัติ
- ✅ หาไฟล์ง่าย (เรียงตามวันที่)
- ✅ ลบไฟล์เก่าอัตโนมัติ (retention policy)

---

## 📝 ตรวจสอบสถานะ

### ดู Service Status
```powershell
sc query PDFWatcherV3
```

### ดู Logs
```powershell
cd D:\programing\Python\OCR_Picklist\logs
Get-Content -Tail 20 service_stdout.log
```

### ดู Metrics
```powershell
type metrics.json
```

---

## ⚠️ สิ่งที่ยังไม่เสร็จ (TODO)

สถานะปัจจุบัน: **Foundation Complete (40%)**

### ไฟล์ที่ยังต้องสร้าง:
```
v3/
├── components/
│   ├── ❌ ocr_pipeline.py        # OCR methods + adaptive rendering
│   ├── ❌ header_validator.py   # Pattern validation + scoring
│   └── ❌ pdf_splitter.py        # PDF splitting logic
│
├── utils/
│   ├── ❌ image_processor.py     # Image preprocessing
│   └── ❌ debug_manager.py       # Debug image management
│
├── ❌ pdf_extractor_v3.py         # Main orchestrator
│
└── tests/
    ├── ❌ test_output_organizer.py
    ├── ❌ test_ocr_pipeline.py
    └── ❌ test_integration.py
```

### ทำไมยังใช้ไม่ได้?
**ไฟล์หลัก `pdf_extractor_v3.py` ยังไม่ได้สร้าง** - ต้องมีก่อนถึงจะรันได้

---

## 🎯 ขั้นตอนต่อไป

### Option 1: สร้างไฟล์ที่เหลือ
ต้องสร้างอีก ~2,000 บรรทัดโค้ด:
- `pdf_extractor_v3.py` (~800 lines)
- `ocr_pipeline.py` (~600 lines) 
- `header_validator.py` (~300 lines)
- `pdf_splitter.py` (~200 lines)
- `image_processor.py` + `debug_manager.py` (~300 lines)

### Option 2: ใช้ V2 ต่อไปก่อน
ระหว่างพัฒนา V3 สามารถใช้ `pdf_extractorV2.py` ได้ตามปกติ

---

## 💡 สรุป

### ✅ สิ่งที่ได้แล้ว:
- โครงสร้าง folder สมบูรณ์
- Output organizer (Year/Date structure) ✨
- Metrics tracking system ✨
- Async API logging ✨
- Thread-safe context ✨
- Type-safe configuration ✨
- Service installation scripts
- Complete setup documentation

### ⏳ ยังรอทำ:
- Core OCR components (4-5 ไฟล์)
- Main orchestrator
- Unit tests

**คุณต้องการให้:**
1. ทำ V3 ต่อจนเสร็จ? (ใช้เวลา ~2-3 ชม.)
2. หรือให้เอาเอกสารไปศึกษาก่อน แล้วค่อยทำต่อภายหลัง?

---

**สถานะ:** Foundation Complete (40%)  
**เวอร์ชัน:** 3.0.0-beta  
**วันที่:** February 5, 2026
