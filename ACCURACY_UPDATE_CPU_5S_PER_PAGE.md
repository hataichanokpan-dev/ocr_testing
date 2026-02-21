# Accuracy Update Guide (CPU Only, Target <= 5s/Page)

เอกสารนี้สำหรับปรับระบบให้อ่าน “แม่นที่สุด” ภายใต้ข้อจำกัด:

- ไม่ใช้ GPU
- ยอมรับเวลาเฉลี่ยสูงสุดประมาณ 5 วินาทีต่อหน้า

## คำตอบสั้น: ใช้ OCR Model โดยไม่ใช้ GPU ได้ไหม

ได้

- Tesseract: ทำงานบน CPU โดยตรง
- PaddleOCR: ใช้ CPU-only ได้ (ติดตั้งไว้ใน `requirements.txt` แล้ว)

หมายเหตุ:
- ความแม่นยำสูงสุดมักต้องแลกด้วยเวลา
- CPU-only ทำได้ แต่ควรตั้ง budget ต่อหน้าให้ชัดเจน

## เป้าหมายเชิงวัดผล

ใช้ metrics นี้ตัดสิน:

- `avg_processing_per_page_seconds <= 5.0`
- OCR header accuracy เพิ่มขึ้นจาก baseline
- จำนวน `low_confidence` ในรายงานลดลง

## Preset Config แนะนำ (แม่นยำสูง, CPU-only)

ใส่/ปรับใน `v3/config.ini`:

```ini
[Settings]
# OCR budget
max_ocr_attempts = 12
early_exit_score = 95
score_threshold_for_escalation = 80

# Adaptive rendering
adaptive_rendering = true
initial_render_scale = 2.0
max_render_scale = 6.0

# Tesseract
tesseract_psm_mode = 7
tesseract_char_whitelist = ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-

# OCR enhancement
enable_deskewing = true
enable_morphological_ops = true
enable_clahe = true
enable_pattern_correction = true

# Flexible validation
enable_pattern_check = true
header_pattern = ^[A-Z](?:-[A-Z0-9]{1,8}){2,3}$
tesseract_confidence_threshold = 82.0

# Paddle fallback (CPU)
enable_paddleocr_fallback = true
enable_ensemble_voting = true
```

## Strategy ปรับทีละขั้น (แนะนำ)

1. ล็อกคุณภาพ ROI ก่อน
- จูน `header_area_top/left/width/height` ให้ตัดเฉพาะ header
- ROI ดี = แม่นขึ้นมากกว่าการเพิ่ม model

2. เปิด OCR enhancement ครบ
- `deskew + clahe + morphology`

3. คุมเวลาไม่เกิน 5s/หน้า
- ถ้าเกิน 5 วินาที/หน้า ให้ลด `max_ocr_attempts` ก่อน
- ถ้ายังเกิน ให้ลด `max_render_scale` จาก 6.0 -> 3.0

4. เปิด Paddle fallback เฉพาะหน้าที่จำเป็น
- ปล่อยให้ fallback ทำงานเฉพาะหน้า confidence ต่ำ
- ช่วยแม่นขึ้นโดยไม่ลากเวลาทุกหน้า

## วิธีตรวจผลหลังปรับ

ดูไฟล์:

- `metrics.json`
- `daily/performance_metrics_YYYYMMDD.json`
- `reports/YYYY-MM-DD/extraction_report_*.xlsx`
- `reports/YYYY-MM-DD/errors_extraction_report_*.xlsx`

เช็กค่า:

- `avg_processing_per_page_seconds`
- จำนวนแถว `low_confidence`
- ความถูกต้องของชื่อไฟล์ split เทียบเอกสารจริง

## Rule สำหรับ production

- ถ้า `avg_processing_per_page_seconds > 5.0` ติดต่อกันหลายงาน:
1. ลด `max_ocr_attempts`
2. ลด `max_render_scale`
3. ปรับ ROI ให้แคบลง

- ถ้าเวลาผ่านแต่ความแม่นยังไม่พอ:
1. เปิด/ยืนยัน `enable_paddleocr_fallback = true`
2. เพิ่มคุณภาพภาพ scan ต้นทาง (300 DPI+)
3. เก็บเคสผิดจริงเพื่อปรับ pattern/normalization แบบเฉพาะจุด

## หมายเหตุสำคัญ

เอกสารที่มีการปกปิดข้อมูล (format ไม่คงที่) ไม่ควรใช้ rule เดาข้ามเอกสาร

แนวทางที่ปลอดภัยที่สุดคือ:
- ให้คะแนนและตัดสิน “ต่อหน้า”
- ใช้ confidence + validator ที่ยืดหยุ่น
- เปิด review flow สำหรับเคส low confidence
