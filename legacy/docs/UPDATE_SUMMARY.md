# Update Summary - API Logging Feature

## Changes Completed ✅

### 1. Source Code Updates

#### `pdf_extractor.py`
**Added:**
- Import statements: `requests`, `json`, `datetime`
- API configuration in `__init__()`: `api_url`, `enable_api_logging`
- New method: `_send_extraction_log()` - Sends detailed extraction results to API
- Updated `extract_header_text()` - Logs direct extraction results
- Updated `_ocr_extract()` - Passes filename and logs OCR results with error handling
- Updated `_try_multiple_ocr_methods()` - Returns tuple with (text, method_results dictionary)
- All 10 OCR methods now track results and scores in a dictionary

**Features:**
- Tracks all OCR method results (Method 0, 0B, 0C, 1-7) with scores
- Logs direct text extraction when successful
- Records final answer selected
- Includes debug image paths
- Comprehensive error handling with timeout protection (10 seconds)
- Graceful failure - doesn't break PDF processing if API fails

#### `config.ini`
**Added:**
```ini
# API Logging Configuration
enable_api_logging = True
api_log_url = http://mth-vm-pdw/pdw-picklist-api/api/PDW/AddExtractionLog
```

#### `requirements.txt`
**Added:**
```
# HTTP requests for API logging
requests==2.31.0
```

### 2. Documentation Created

#### `API_LOGGING_DOCUMENTATION.md` (New File)
Comprehensive documentation in both **English** and **Thai** covering:
- Overview and features
- Configuration instructions
- API endpoint specification
- Field descriptions
- Status values and scoring system
- Error handling
- Use cases
- Installation steps
- Testing procedures
- Troubleshooting guide

#### `FALLBACK_FILENAME_UPDATE.md` (Previously Created)
Documentation for the original filename fallback feature

### 3. Dependencies Installed

✅ `requests==2.31.0` - Successfully installed

## API Endpoint Details

### URL
```
POST http://mth-vm-pdw/pdw-picklist-api/api/PDW/AddExtractionLog
```

### Request Payload (All Fields)
```json
{
  "timestamp": "2024-01-15 10:30:00",
  "original_filename": "string",
  "page_number": 0,
  "method0_text": "string",
  "method0_score": 0,
  "method0B_text": "string",
  "method0B_score": 0,
  "method0C_text": "string",
  "method0C_score": 0,
  "method1_text": "string",
  "method1_score": 0,
  "method2_text": "string",
  "method2_score": 0,
  "method3_text": "string",
  "method3_score": 0,
  "method4_text": "string",
  "method4_score": 0,
  "method5_text": "string",
  "method5_score": 0,
  "method6_text": "string",
  "method6_score": 0,
  "method7_text": "string",
  "method7_score": 0,
  "direct_text": "string",
  "direct_score": 0,
  "status": "string",
  "error_message": "string",
  "debug_image_path": "string",
  "finnal_answer": "string"
}
```

### Response Format
```json
{
  "success": true,
  "message": "Extraction log added successfully",
  "data": {
    "log_id": 3,
    "timestamp": "2024-01-15 10:30:00",
    "original_filename": "string",
    "page_number": 0,
    "status": "string"
  }
}
```

## How It Works

### Flow Diagram

```
PDF File Arrives
    ↓
Extract Header Text (Direct)
    ↓
    ├─→ Text Found? → Log to API (status: direct_extraction_success)
    │                      ↓
    │                   Continue Processing
    ↓
No Text Found → Run OCR
    ↓
Try All 10 OCR Methods
    ↓
Score Each Result
    ↓
Select Best Result
    ↓
Log All Results to API
    ├─→ Success → API returns log_id
    ├─→ Timeout → Log warning, continue
    └─→ Error → Log error, continue
    ↓
Rename File (with original name fallback)
```

### Status Values Sent to API

1. **`direct_extraction_success`** - Text extracted without OCR
2. **`success`** - OCR extraction completed successfully
3. **`no_text_found`** - OCR ran but found no valid text
4. **`error`** - Exception occurred during processing

## Testing Steps

### 1. Quick Test (Disable API)
```ini
enable_api_logging = False
```
System should work normally without API calls.

### 2. Test API Connectivity
```bash
curl -X POST http://mth-vm-pdw/pdw-picklist-api/api/PDW/AddExtractionLog \
  -H "Content-Type: application/json" \
  -d '{"timestamp":"2024-01-15 10:30:00","original_filename":"test",...}'
```

### 3. Test with Real PDF
- Place a PDF in the watch folder
- Check logs for "Sending extraction log to API"
- Verify API receives the request
- Check response in logs

### 4. Test Error Handling
- Stop API server
- Process a PDF
- Verify system continues working
- Check logs for connection error message

## Configuration Options

### Enable/Disable API Logging
```ini
enable_api_logging = True    # Enable logging
enable_api_logging = False   # Disable logging
```

### Change API Endpoint
```ini
api_log_url = http://your-server/api/endpoint
```

## Benefits

1. **Quality Monitoring** - Track OCR method performance
2. **Error Analysis** - Identify problematic PDFs
3. **Method Comparison** - See which methods work best
4. **Debugging** - Access detailed logs and debug images
5. **Continuous Improvement** - Collect data for algorithm enhancement
6. **Audit Trail** - Complete history of all extractions

## Next Steps

1. ✅ Code updated
2. ✅ Dependencies installed
3. ✅ Documentation created
4. ⏭️ Test with real PDFs
5. ⏭️ Verify API receives data correctly
6. ⏭️ Monitor logs for any issues
7. ⏭️ Restart service if running

## Notes

- API calls have 10-second timeout to prevent hanging
- System continues working even if API is unavailable
- All 10 OCR methods are tracked and logged
- Scores help identify best extraction methods
- Original filenames are preserved when extraction fails
- Debug images are saved and paths logged to API

---

**Status**: ✅ Ready for testing
**Updated**: January 21, 2026
