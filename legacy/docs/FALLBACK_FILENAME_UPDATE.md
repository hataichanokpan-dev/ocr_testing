# Fallback Filename Update Documentation

## English Version

### Overview
Updated the PDF OCR system to preserve original filenames when text extraction fails, instead of defaulting to "unnamed".

### Changes Made

#### 1. Updated `pdf_extractor.py`
**Modified Method:** `sanitize_filename()`

**Before:**
- When no text was extracted, the method returned "unnamed"
- This resulted in files being renamed to "unnamed.pdf", "unnamed_1.pdf", etc.

**After:**
- Method now accepts an optional `original_filename` parameter
- When no text is extracted:
  - If `original_filename` is provided → uses the original filename
  - If `original_filename` is NOT provided → falls back to "unnamed"
- Logs a clear message when keeping the original filename

**Code Changes:**
```python
def sanitize_filename(self, text, original_filename=None):
    if not text:
        if original_filename:
            logger.info(f"No text extracted, keeping original filename: {original_filename}")
            return original_filename
        return "unnamed"
    # ... rest of sanitization logic
```

#### 2. Updated `pdf_watcher.py`
**Modified Method:** `process_pdf()`

**Changes:**
- Extracts the original filename (stem, without extension) using `Path(file_path).stem`
- Passes the original filename to `sanitize_filename()` as a fallback
- Updated log message to indicate when keeping original name
- Removed the intermediate step that set `header_text = "unnamed"`

**Code Flow:**
```python
# Extract header text
header_text = self.extractor.extract_header_text(file_path)

# Get original filename without extension
original_name = Path(file_path).stem

if not header_text:
    logger.warning(f"No text extracted from: {file_path}, keeping original name")

# Sanitize filename (will use original name if header_text is empty)
new_name = self.extractor.sanitize_filename(header_text, original_filename=original_name)
```

### Benefits

1. **Preserves Context**: Original filenames often contain useful information (dates, reference numbers, etc.)
2. **Better Traceability**: Easier to track which files failed OCR extraction
3. **Avoids Confusion**: Multiple "unnamed" files made it difficult to identify specific documents
4. **Backward Compatible**: Still returns "unnamed" if no original filename is provided

### Usage Examples

**Example 1: OCR Succeeds**
- Input file: `document123.pdf`
- Extracted text: `INV-2026-12345678`
- Output file: `INV-2026-12345678.pdf`

**Example 2: OCR Fails (NEW BEHAVIOR)**
- Input file: `invoice_jan_2026.pdf`
- Extracted text: *(empty/failed)*
- Output file: `invoice_jan_2026.pdf` *(keeps original name)*

**Example 3: OCR Fails (OLD BEHAVIOR)**
- Input file: `invoice_jan_2026.pdf`
- Extracted text: *(empty/failed)*
- Output file: `unnamed.pdf` *(lost original information)*

### Testing Recommendations

1. **Test with unreadable PDFs** (blank pages, corrupted files)
2. **Test with PDFs where header area has no text**
3. **Verify log messages** show when original filename is kept
4. **Check duplicate handling** still works correctly
5. **Ensure timestamp addition** (if enabled) works with original filenames

---

## Thai Version (เวอร์ชันภาษาไทย)

### ภาพรวม
อัปเดตระบบ PDF OCR เพื่อรักษาชื่อไฟล์เดิมไว้เมื่อการดึงข้อความล้มเหลว แทนที่จะใช้ชื่อเริ่มต้นเป็น "unnamed"

### การเปลี่ยนแปลงที่ทำ

#### 1. อัปเดต `pdf_extractor.py`
**เมธอดที่แก้ไข:** `sanitize_filename()`

**ก่อนการแก้ไข:**
- เมื่อดึงข้อความไม่ได้ เมธอดจะคืนค่า "unnamed"
- ทำให้ไฟล์ถูกเปลี่ยนชื่อเป็น "unnamed.pdf", "unnamed_1.pdf" เป็นต้น

**หลังการแก้ไข:**
- เมธอดรับพารามิเตอร์เพิ่มเติมชื่อ `original_filename` (ไม่บังคับ)
- เมื่อดึงข้อความไม่ได้:
  - ถ้ามี `original_filename` → ใช้ชื่อไฟล์เดิม
  - ถ้าไม่มี `original_filename` → ใช้ "unnamed" แทน
- บันทึกข้อความแจ้งเตือนที่ชัดเจนเมื่อเก็บชื่อไฟล์เดิม

**โค้ดที่เปลี่ยนแปลง:**
```python
def sanitize_filename(self, text, original_filename=None):
    if not text:
        if original_filename:
            logger.info(f"No text extracted, keeping original filename: {original_filename}")
            return original_filename
        return "unnamed"
    # ... ส่วนที่เหลือของการทำความสะอาดชื่อไฟล์
```

#### 2. อัปเดต `pdf_watcher.py`
**เมธอดที่แก้ไข:** `process_pdf()`

**การเปลี่ยนแปลง:**
- ดึงชื่อไฟล์เดิม (ไม่รวมนามสกุล) โดยใช้ `Path(file_path).stem`
- ส่งชื่อไฟล์เดิมไปยัง `sanitize_filename()` เป็นค่าสำรอง
- อัปเดตข้อความ log เพื่อแสดงเมื่อเก็บชื่อเดิม
- ลบขั้นตอนกลางที่ตั้งค่า `header_text = "unnamed"` ออก

**ขั้นตอนการทำงานของโค้ด:**
```python
# ดึงข้อความจากส่วนหัว
header_text = self.extractor.extract_header_text(file_path)

# ดึงชื่อไฟล์เดิม (ไม่รวมนามสกุล)
original_name = Path(file_path).stem

if not header_text:
    logger.warning(f"No text extracted from: {file_path}, keeping original name")

# ทำความสะอาดชื่อไฟล์ (จะใช้ชื่อเดิมถ้า header_text ว่างเปล่า)
new_name = self.extractor.sanitize_filename(header_text, original_filename=original_name)
```

### ประโยชน์ที่ได้รับ

1. **รักษาบริบท**: ชื่อไฟล์เดิมมักมีข้อมูลที่มีประโยชน์ (วันที่, เลขอ้างอิง ฯลฯ)
2. **ตรวจสอบได้ดีขึ้น**: ง่ายต่อการติดตามว่าไฟล์ใดล้มเหลวในการดึงข้อความด้วย OCR
3. **หลีกเลี่ยงความสับสน**: ไฟล์หลายไฟล์ที่ชื่อ "unnamed" ทำให้ยากต่อการระบุเอกสารเฉพาะ
4. **รองรับย้อนหลัง**: ยังคงคืนค่า "unnamed" ถ้าไม่มีชื่อไฟล์เดิมให้ใช้

### ตัวอย่างการใช้งาน

**ตัวอย่างที่ 1: OCR สำเร็จ**
- ไฟล์ต้นทาง: `document123.pdf`
- ข้อความที่ดึงได้: `INV-2026-12345678`
- ไฟล์ผลลัพธ์: `INV-2026-12345678.pdf`

**ตัวอย่างที่ 2: OCR ล้มเหลว (พฤติกรรมใหม่)**
- ไฟล์ต้นทาง: `invoice_jan_2026.pdf`
- ข้อความที่ดึงได้: *(ว่างเปล่า/ล้มเหลว)*
- ไฟล์ผลลัพธ์: `invoice_jan_2026.pdf` *(เก็บชื่อเดิมไว้)*

**ตัวอย่างที่ 3: OCR ล้มเหลว (พฤติกรรมเดิม)**
- ไฟล์ต้นทาง: `invoice_jan_2026.pdf`
- ข้อความที่ดึงได้: *(ว่างเปล่า/ล้มเหลว)*
- ไฟล์ผลลัพธ์: `unnamed.pdf` *(สูญเสียข้อมูลเดิม)*

### คำแนะนำในการทดสอบ

1. **ทดสอบกับไฟล์ PDF ที่อ่านไม่ได้** (หน้าว่าง, ไฟล์เสียหาย)
2. **ทดสอบกับไฟล์ PDF ที่ส่วนหัวไม่มีข้อความ**
3. **ตรวจสอบข้อความ log** ว่าแสดงเมื่อเก็บชื่อไฟล์เดิม
4. **ตรวจสอบการจัดการชื่อซ้ำ** ยังทำงานถูกต้อง
5. **ตรวจสอบการเพิ่ม timestamp** (ถ้าเปิดใช้งาน) ทำงานได้กับชื่อไฟล์เดิม

---

## Summary of Changes / สรุปการเปลี่ยนแปลง

### Files Modified / ไฟล์ที่แก้ไข:
1. `pdf_extractor.py` - Added `original_filename` parameter to `sanitize_filename()` / เพิ่มพารามิเตอร์ `original_filename` ใน `sanitize_filename()`
2. `pdf_watcher.py` - Pass original filename as fallback / ส่งชื่อไฟล์เดิมเป็นค่าสำรอง

### Impact / ผลกระทบ:
- **Positive / เชิงบวก**: Better file management, easier troubleshooting / การจัดการไฟล์ที่ดีขึ้น แก้ปัญหาง่ายขึ้น
- **No Breaking Changes / ไม่มีการเปลี่ยนแปลงที่ทำลายระบบ**: Backward compatible / รองรับย้อนหลัง
- **Logging / การบันทึก**: Enhanced logging for better visibility / ปรับปรุงการบันทึกเพื่อมองเห็นได้ชัดเจนขึ้น
