# OCR Picklist V3

ระบบอ่านหัวเอกสารจาก PDF และแยกไฟล์อัตโนมัติ โดยเน้นความแม่นยำของ OCR บน CPU (ไม่ต้องใช้ GPU)

## สิ่งที่ระบบทำ

- เฝ้าดูไฟล์ PDF ใหม่ในโฟลเดอร์ `input/`
- อ่าน header ของแต่ละหน้า
- จัดกลุ่มหน้าตาม header
- แยกเป็น PDF ย่อยและตั้งชื่อไฟล์จาก header
- บันทึกรายงาน (`reports/`) และ metrics (`metrics.json`, `daily/`)

## OCR Flow (หลักการก่อนเริ่มทำงาน)

ลำดับการอ่าน OCR ของระบบ:

1. กำหนดขอบเขต header
- ใช้ค่า `header_area_top/left/width/height` (เปอร์เซ็นต์ของหน้า)
- ลดพื้นที่ที่ OCR ต้องอ่าน เพื่อเพิ่มความแม่นและความเร็ว

2. ลองอ่านข้อความตรงจาก PDF ก่อน
- ถ้า PDF มี text layer และผ่าน validator จะใช้ผลนี้ทันที
- เร็วที่สุดและผิดพลาดต่ำสุด

3. OCR แบบ adaptive rendering
- เริ่มที่ scale ต่ำก่อน แล้วค่อยเพิ่มเมื่อคะแนนไม่พอ
- ใช้ preprocessing หลายแบบ (threshold/adaptive/otsu/bilateral)
- ใช้หลาย Tesseract PSM (เช่น 7/6/13) เพื่อเพิ่มโอกาสอ่านถูก

4. ให้คะแนนและเลือกผลที่ดีที่สุด (ต่อหน้า)
- ใช้คะแนนโครงสร้าง header + confidence OCR
- เลือกผลแบบ weighted voting จากหลาย candidate
- ไม่มีการเดาข้ามเอกสารแบบ hard rule

5. ตรวจรูปแบบ header แบบยืดหยุ่น
- รองรับทั้ง:
`prefix/code/serial`
`prefix/country/serial`
`prefix/country/code/serial`
- มี normalization เฉพาะจุดที่ปลอดภัย (เช่น separator หาย)

6. แยกไฟล์ PDF
- grouping ตามผล header ที่ match กัน
- save แบบ atomic + retry เพื่อลดปัญหาไฟล์ถูกล็อก

## โครงสร้างโปรเจกต์ (Active)

```text
v3/                  # โค้ดหลัก
tests/v3/            # tests ของ V3
input/               # ไฟล์ขาเข้า
output/              # ไฟล์ผลลัพธ์ที่แยกแล้ว
reports/             # รายงาน extraction/error
logs/                # runtime logs
debug_images/        # ภาพ debug OCR
legacy/              # โค้ดเก่า V1/V2 (archive)
```

## ติดตั้ง

1. ติดตั้ง dependencies
```powershell
pip install -r requirements.txt
```

2. ติดตั้ง Tesseract OCR
- Windows ปกติ: `C:\Program Files\Tesseract-OCR\tesseract.exe`
- ถ้าไม่อยู่ใน PATH ให้ตั้งใน `v3/config.ini`:
`tesseract_cmd = C:/Program Files/Tesseract-OCR/tesseract.exe`

## เริ่มใช้งาน

รัน watcher:

```powershell
python v3/pdf_watcher_v3.py
```

ระบบจะเฝ้าโฟลเดอร์ `input/` อัตโนมัติ

## Configuration หลัก (v3/config.ini)

- OCR:
`tesseract_cmd`
`tesseract_psm_mode`
`max_ocr_attempts`
`adaptive_rendering`
`initial_render_scale`
`max_render_scale`

- Pattern/Validation:
`enable_pattern_check`
`header_pattern`
`expected_separator`
`pattern_serial_allowed_prefixes`

- Split:
`enable_pdf_splitting`
`header_similarity_threshold`
`enable_serial_based_matching`
`split_naming_pattern`

- Metrics:
`enable_metrics_tracking`
`metrics_export_path`

## Metrics และ Summary รายวัน

ระบบสร้าง metrics 2 ระดับ:

1. ไฟล์รวมล่าสุด
- `metrics.json`

2. ไฟล์แยกตามวัน
- `daily/performance_metrics_YYYYMMDD.json`

ข้อมูลสำคัญที่มี:
- `avg_processing_time_seconds` (เฉลี่ยต่อไฟล์)
- `avg_processing_per_page_seconds` (เฉลี่ยต่อหน้า)
- `total_pages_processed`
- OCR/API success rate

## แนวทางความแม่นยำสูงสุด (CPU-only)

ดูไฟล์นี้:

`ACCURACY_UPDATE_CPU_5S_PER_PAGE.md`

ไฟล์นี้มี preset config และขั้นตอน tuning สำหรับเป้าหมาย “แม่นที่สุด” โดยรับเวลาประมาณไม่เกิน 5 วินาที/หน้า และไม่ใช้ GPU

## Troubleshooting สั้นๆ

- `tesseract is not installed or it's not in PATH`
ตั้ง `tesseract_cmd` ใน `v3/config.ini`

- ไฟล์ split ไม่ได้เพราะไฟล์ปลายทางถูกใช้งาน
ระบบมี retry + fallback อัตโนมัติแล้ว แต่ควรปิดโปรแกรมที่เปิดไฟล์ PDF ปลายทางอยู่

- ความแม่นยำตก
ตรวจ `debug_images/` + ปรับ `header_area_*` ให้ครอบเฉพาะข้อความ header จริง
