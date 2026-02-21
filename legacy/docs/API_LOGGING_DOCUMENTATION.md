# API Logging Feature Documentation

## English Version

### Overview
The PDF OCR system now logs all extraction results to an external API endpoint for monitoring, analysis, and quality improvement. Every extraction attempt is recorded with detailed information about all OCR methods, their results, and scores.

### Features

#### 1. **Comprehensive Logging**
- Logs results from all 10 OCR methods (Method 0, 0B, 0C, 1-7)
- Captures direct text extraction (if successful)
- Records scores for each method
- Tracks final answer selected
- Includes debug image paths
- Logs errors with detailed messages

#### 2. **Configurable**
- Enable/disable via `config.ini`
- Customizable API endpoint URL
- Timeout protection (10 seconds)
- Graceful error handling (won't break PDF processing if API fails)

#### 3. **Real-time Monitoring**
- Sends logs immediately after each extraction
- Includes timestamp for tracking
- Returns log ID from API for reference

### Configuration

#### config.ini Settings
```ini
[Settings]
# API Logging Configuration
enable_api_logging = True
api_log_url = http://mth-vm-pdw/pdw-picklist-api/api/PDW/AddExtractionLog
```

**Parameters:**
- `enable_api_logging`: Set to `True` to enable API logging, `False` to disable
- `api_log_url`: Full URL of the API endpoint

### API Endpoint Specification

#### Request Format
```http
POST /api/PDW/AddExtractionLog
Content-Type: application/json
Accept: */*
```

#### Request Body
```json
{
  "timestamp": "2024-01-15 10:30:00",
  "original_filename": "invoice_2024.pdf",
  "page_number": 1,
  "method0_text": "B-F-GTX-S17893848",
  "method0_score": 160,
  "method0B_text": "B-F-GTX-S17893848",
  "method0B_score": 150,
  "method0C_text": "",
  "method0C_score": 0,
  "method1_text": "B-F-GTX-S17893848",
  "method1_score": 140,
  "method2_text": "B-F-GTX-S17893848",
  "method2_score": 160,
  "method3_text": "B-F-GTX-S17893848",
  "method3_score": 155,
  "method4_text": "B-F-GTX-S17893848",
  "method4_score": 150,
  "method5_text": "B-F-GTX-S17893848",
  "method5_score": 145,
  "method6_text": "",
  "method6_score": 0,
  "method7_text": "B-F-GTX-S17893848",
  "method7_score": 165,
  "direct_text": "",
  "direct_score": 0,
  "status": "success",
  "error_message": "",
  "debug_image_path": "debug_page1_extracted_area.png",
  "finnal_answer": "B-F-GTX-S17893848"
}
```

#### Response Format
```json
{
  "success": true,
  "message": "Extraction log added successfully",
  "data": {
    "log_id": 123,
    "timestamp": "2024-01-15 10:30:00",
    "original_filename": "invoice_2024.pdf",
    "page_number": 1,
    "status": "success"
  }
}
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | string | When the extraction was performed (YYYY-MM-DD HH:MM:SS) |
| `original_filename` | string | Original PDF filename (without extension) |
| `page_number` | integer | Page number processed (1-based) |
| `method0_text` | string | Text extracted using Method 0 (Hough line removal) |
| `method0_score` | integer | Quality score for Method 0 result |
| `method0B_text` | string | Text from Method 0B (multi-kernel line removal) |
| `method0B_score` | integer | Quality score for Method 0B result |
| `method0C_text` | string | Text from Method 0C (connected components) |
| `method0C_score` | integer | Quality score for Method 0C result |
| `method1_text` | string | Text from Method 1 (line removal) |
| `method1_score` | integer | Quality score for Method 1 result |
| `method2_text` | string | Text from Method 2 (high threshold) |
| `method2_score` | integer | Quality score for Method 2 result |
| `method3_text` | string | Text from Method 3 (adaptive threshold) |
| `method3_score` | integer | Quality score for Method 3 result |
| `method4_text` | string | Text from Method 4 (OTSU with denoising) |
| `method4_score` | integer | Quality score for Method 4 result |
| `method5_text` | string | Text from Method 5 (bilateral filter) |
| `method5_score` | integer | Quality score for Method 5 result |
| `method6_text` | string | Text from Method 6 (black hat transform) |
| `method6_score` | integer | Quality score for Method 6 result |
| `method7_text` | string | Text from Method 7 (morphological gradient) |
| `method7_score` | integer | Quality score for Method 7 result |
| `direct_text` | string | Text extracted directly from PDF (without OCR) |
| `direct_score` | integer | Quality score for direct extraction |
| `status` | string | Processing status: "success", "no_text_found", "direct_extraction_success", "error" |
| `error_message` | string | Error details if status is "error" |
| `debug_image_path` | string | Path to debug image file |
| `finnal_answer` | string | Final text selected as the best result (Note: API typo "finnal") |

### Status Values

- **`success`**: OCR extraction completed successfully
- **`no_text_found`**: OCR ran but couldn't extract any valid text
- **`direct_extraction_success`**: Text was extracted directly from PDF without OCR
- **`error`**: An error occurred during processing

### Scoring System

Scores range from -1 (invalid) to 200+ (perfect match):
- **-1**: Invalid or empty result
- **0-50**: Poor quality, doesn't match expected format
- **50-100**: Acceptable, partial match
- **100-150**: Good quality, matches expected format
- **150-200+**: Excellent quality, perfect format match

Higher scores indicate better quality and format compliance.

### Error Handling

The system includes robust error handling:
- **Connection errors**: Logged but don't stop PDF processing
- **Timeouts**: 10-second timeout prevents hanging
- **API failures**: Gracefully handled with warning logs
- **Missing API**: System continues to work without API logging

### Use Cases

1. **Quality Monitoring**: Track which OCR methods perform best
2. **Performance Analysis**: Identify difficult PDFs that need manual review
3. **Method Comparison**: Compare effectiveness of different preprocessing methods
4. **Error Tracking**: Monitor extraction failures and patterns
5. **Debugging**: Access debug images and detailed logs for troubleshooting
6. **Training Data**: Collect data for improving OCR algorithms

### Installation

1. **Install requests library**:
   ```bash
   pip install requests
   ```
   Or install all requirements:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure API endpoint** in `config.ini`:
   ```ini
   enable_api_logging = True
   api_log_url = http://your-api-server/api/PDW/AddExtractionLog
   ```

3. **Restart the service** if running as Windows service

### Testing

#### Test API Connection
```python
import requests
import json

payload = {
    "timestamp": "2024-01-15 10:30:00",
    "original_filename": "test.pdf",
    "page_number": 1,
    "method0_text": "TEST",
    "method0_score": 100,
    # ... other fields
    "status": "success",
    "finnal_answer": "TEST"
}

response = requests.post(
    "http://mth-vm-pdw/pdw-picklist-api/api/PDW/AddExtractionLog",
    json=payload,
    headers={'Content-Type': 'application/json'}
)

print(response.status_code)
print(response.json())
```

#### Disable API Logging (for testing)
```ini
enable_api_logging = False
```

### Troubleshooting

#### Issue: API requests timing out
**Solution**: 
- Check network connectivity to API server
- Verify API server is running
- Increase timeout in code if needed
- Consider disabling API logging temporarily

#### Issue: API returns error
**Solution**:
- Check API logs for detailed error messages
- Verify request payload format matches API specification
- Ensure all required fields are included
- Check API authentication if required

#### Issue: Too many API requests
**Solution**:
- API is called once per page processed
- For high-volume processing, consider batch logging
- Monitor API server capacity

---

## Thai Version (เวอร์ชันภาษาไทย)

### ภาพรวม
ระบบ PDF OCR ตอนนี้บันทึกผลการดึงข้อความทั้งหมดไปยัง API ภายนอกเพื่อการติดตาม วิเคราะห์ และปรับปรุงคุณภาพ ทุกครั้งที่พยายามดึงข้อความจะถูกบันทึกพร้อมข้อมูลรายละเอียดเกี่ยวกับ OCR ทุกวิธี ผลลัพธ์ และคะแนน

### ฟีเจอร์

#### 1. **การบันทึกแบบครบถ้วน**
- บันทึกผลลัพธ์จาก OCR ทั้ง 10 วิธี (Method 0, 0B, 0C, 1-7)
- จับข้อความที่ดึงได้โดยตรง (ถ้าสำเร็จ)
- บันทึกคะแนนของแต่ละวิธี
- ติดตามคำตอบสุดท้ายที่เลือก
- รวมพาธของรูปภาพ debug
- บันทึก error พร้อมข้อความรายละเอียด

#### 2. **ปรับแต่งได้**
- เปิด/ปิดผ่าน `config.ini`
- กำหนด URL ของ API endpoint ได้
- มีการป้องกัน timeout (10 วินาที)
- จัดการ error อย่างเหมาะสม (ไม่ทำให้การประมวลผล PDF หยุดทำงานถ้า API ล้มเหลว)

#### 3. **การติดตามแบบ Real-time**
- ส่ง log ทันทีหลังจากดึงข้อความแต่ละครั้ง
- รวม timestamp สำหรับการติดตาม
- คืนค่า log ID จาก API เพื่ออ้างอิง

### การตั้งค่า

#### ตั้งค่าใน config.ini
```ini
[Settings]
# การตั้งค่า API Logging
enable_api_logging = True
api_log_url = http://mth-vm-pdw/pdw-picklist-api/api/PDW/AddExtractionLog
```

**พารามิเตอร์:**
- `enable_api_logging`: ตั้งเป็น `True` เพื่อเปิดใช้งาน API logging, `False` เพื่อปิด
- `api_log_url`: URL เต็มของ API endpoint

### รูปแบบ API Endpoint

#### รูปแบบ Request
```http
POST /api/PDW/AddExtractionLog
Content-Type: application/json
Accept: */*
```

#### เนื้อหา Request
*(ดูตัวอย่างในส่วนภาษาอังกฤษข้างต้น)*

#### รูปแบบ Response
```json
{
  "success": true,
  "message": "Extraction log added successfully",
  "data": {
    "log_id": 123,
    "timestamp": "2024-01-15 10:30:00",
    "original_filename": "invoice_2024.pdf",
    "page_number": 1,
    "status": "success"
  }
}
```

### คำอธิบายฟิลด์

| ฟิลด์ | ชนิด | คำอธิบาย |
|-------|------|----------|
| `timestamp` | string | เวลาที่ดึงข้อความ (YYYY-MM-DD HH:MM:SS) |
| `original_filename` | string | ชื่อไฟล์ PDF ต้นฉบับ (ไม่รวมนามสกุล) |
| `page_number` | integer | หมายเลขหน้าที่ประมวลผล (เริ่มจาก 1) |
| `method0_text` | string | ข้อความที่ดึงได้จาก Method 0 |
| `method0_score` | integer | คะแนนคุณภาพสำหรับ Method 0 |
| `direct_text` | string | ข้อความที่ดึงได้โดยตรงจาก PDF (ไม่ใช้ OCR) |
| `status` | string | สถานะการประมวลผล |
| `error_message` | string | รายละเอียด error ถ้ามี |
| `finnal_answer` | string | ข้อความสุดท้ายที่เลือกเป็นผลลัพธ์ที่ดีที่สุด |

### ค่าสถานะ (Status)

- **`success`**: การดึงข้อความด้วย OCR สำเร็จ
- **`no_text_found`**: OCR ทำงานแล้วแต่ดึงข้อความที่ถูกต้องไม่ได้
- **`direct_extraction_success`**: ดึงข้อความได้โดยตรงจาก PDF โดยไม่ต้องใช้ OCR
- **`error`**: เกิดข้อผิดพลาดระหว่างการประมวลผล

### ระบบให้คะแนน

คะแนนอยู่ในช่วง -1 (ไม่ถูกต้อง) ถึง 200+ (สมบูรณ์แบบ):
- **-1**: ผลลัพธ์ไม่ถูกต้องหรือว่างเปล่า
- **0-50**: คุณภาพต่ำ ไม่ตรงกับรูปแบบที่คาดหวัง
- **50-100**: ยอมรับได้ ตรงกับรูปแบบบางส่วน
- **100-150**: คุณภาพดี ตรงกับรูปแบบที่คาดหวัง
- **150-200+**: คุณภาพเยี่ยม ตรงกับรูปแบบอย่างสมบูรณ์แบบ

คะแนนที่สูงกว่าแสดงถึงคุณภาพและความสอดคล้องกับรูปแบบที่ดีกว่า

### การจัดการข้อผิดพลาด

ระบบมีการจัดการ error ที่แข็งแกร่ง:
- **Connection errors**: บันทึกแต่ไม่หยุดการประมวลผล PDF
- **Timeouts**: timeout 10 วินาทีป้องกันการค้าง
- **API failures**: จัดการอย่างเหมาะสมพร้อม warning logs
- **Missing API**: ระบบทำงานต่อไปได้โดยไม่มี API logging

### กรณีการใช้งาน

1. **ติดตามคุณภาพ**: ติดตามว่าวิธี OCR ไหนทำงานได้ดีที่สุด
2. **วิเคราะห์ประสิทธิภาพ**: ระบุ PDF ที่ยากต้องตรวจสอบด้วยตนเอง
3. **เปรียบเทียบวิธีการ**: เปรียบเทียบประสิทธิภาพของวิธีประมวลผลต่างๆ
4. **ติดตาม Error**: ติดตามความล้มเหลวและรูปแบบ
5. **การแก้ไขข้อบกพร่อง**: เข้าถึงรูปภาพ debug และ log รายละเอียดเพื่อแก้ปัญหา
6. **ข้อมูลฝึกอบรม**: รวบรวมข้อมูลเพื่อปรับปรุง algorithm OCR

### การติดตั้ง

1. **ติดตั้ง library requests**:
   ```bash
   pip install requests
   ```
   หรือติดตั้งทุก requirements:
   ```bash
   pip install -r requirements.txt
   ```

2. **ตั้งค่า API endpoint** ใน `config.ini`:
   ```ini
   enable_api_logging = True
   api_log_url = http://your-api-server/api/PDW/AddExtractionLog
   ```

3. **รีสตาร์ทเซอร์วิส** ถ้ารันเป็น Windows service

### การทดสอบ

#### ทดสอบการเชื่อมต่อ API
```python
import requests

response = requests.post(
    "http://mth-vm-pdw/pdw-picklist-api/api/PDW/AddExtractionLog",
    json={"timestamp": "2024-01-15 10:30:00", ...},
    headers={'Content-Type': 'application/json'}
)

print(response.status_code)
print(response.json())
```

#### ปิด API Logging (เพื่อทดสอบ)
```ini
enable_api_logging = False
```

### การแก้ไขปัญหา

#### ปัญหา: API requests timeout
**วิธีแก้**: 
- ตรวจสอบการเชื่อมต่อเครือข่ายไปยัง API server
- ตรวจสอบว่า API server กำลังทำงาน
- พิจารณาปิด API logging ชั่วคราว

#### ปัญหา: API คืนค่า error
**วิธีแก้**:
- ตรวจสอบ API logs สำหรับข้อความ error รายละเอียด
- ตรวจสอบว่ารูปแบบ request payload ตรงกับ API specification
- ตรวจสอบว่ามีฟิลด์ที่จำเป็นทั้งหมด

---

## Summary / สรุป

### Files Modified / ไฟล์ที่แก้ไข:
1. `pdf_extractor.py` - Added API logging functionality
2. `config.ini` - Added API configuration settings
3. `requirements.txt` - Added requests library

### New Features / ฟีเจอร์ใหม่:
- ✅ Automatic logging of all OCR extraction results to API
- ✅ Tracks all 10 OCR methods with scores
- ✅ Configurable via config.ini
- ✅ Graceful error handling
- ✅ Real-time monitoring capability
- ✅ Support for success/error/no_text_found statuses
